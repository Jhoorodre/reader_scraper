// Correção para o modo batch - substitua o Bluebird.map por um for sequencial

// EM VEZ DE:
await Bluebird.map(mangaUrls, async (mangaUrl, urlIndex) => {
    // processamento...
}, { concurrency: 1 });

// USE ISTO:
for (const [urlIndex, mangaUrl] of mangaUrls.entries()) {
    console.log(`\n${'='.repeat(60)}`);
    console.log(`🚀 Processando obra ${urlIndex + 1}/${mangaUrls.length}: ${mangaUrl}`);
    console.log(`${'='.repeat(60)}`);
    
    try {
        const manga = await provider.getManga(mangaUrl);
        console.log('\n=== Informações do Manga ===');
        console.log('Título:', manga.name);
        console.log('Link:', manga.id);

        fs.appendFileSync(reportFile, `\n=== OBRA ${urlIndex + 1}: ${manga.name} ===\n`);

        console.log('\n🔍 Carregando lista de capítulos...');
        const chapters = await provider.getChapters(manga.id);

        if (chapters.length === 0) {
            throw new Error(`Nenhum capítulo encontrado para ${manga.name}`);
        }

        // Extrair ID da obra para o log
        const workMatch = mangaUrl.match(/\/obra\/(\d+)/);
        const workId = workMatch ? workMatch[1] : 'unknown';
        
        // Criar nome sanitizado uma vez para reutilizar
        const sanitizedName = manga.name?.replace(`Capítulo`, ``).replace(/[\\\/:*?"<>|]/g, '-');
        
        console.log('\n🔍 Detectando capítulos novos baseado nos logs...');
        const selectedChapters = chapterLogger.detectNewChapters(manga.name, chapters);
        
        if (selectedChapters.length === 0) {
            console.log('✅ Nenhum capítulo novo detectado - obra já atualizada');
            chapterLogger.showWorkStats(manga.name);
            successfulUrls.push(mangaUrl);
            continue; // Vai para próxima obra
        }
        
        console.log(`\n📦 Modo automático: baixando ${selectedChapters.length} capítulos (novos + falhas)...`);
        
        // Processar capítulos sequencialmente também
        for (const chapter of selectedChapters) {
            console.log(`\n=== Processando Capítulo: ${chapter.number} ===`);
            
            // Verificar se o capítulo já foi baixado
            if (chapterLogger.isChapterDownloaded(manga.name, chapter.number)) {
                console.log(`⏭️ Capítulo ${chapter.number} já baixado - pulando...`);
                continue;
            }
            
            // Tentar baixar o capítulo (com retry)
            let chapterSuccess = false;
            for (let attempt = 1; attempt <= maxRetries; attempt++) {
                try {
                    if (attempt > 1) {
                        console.log(`🔄 Tentativa ${attempt}/${maxRetries} para capítulo: ${chapter.number}`);
                        await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
                    }
                    
                    const pages = await provider.getPages(chapter);
                    console.log(`Total de Páginas: ${pages.pages.length}`);

                    if (pages.pages.length === 0) {
                        throw new Error(`Capítulo ${chapter.number} retornou 0 páginas`);
                    }
        
                    // Baixar páginas
                    await Bluebird.map(pages.pages, async (pageUrl, pageIndex) => {
                        const capitulo = (pageIndex + 1) <= 9 ? `0${pageIndex + 1}` : `${pageIndex + 1}`;
                        console.log(`Baixando Página ${capitulo}: ${pageUrl}`);
                
                        const dirPath = path.join('manga', path.normalize(sanitizedName), chapter.number.toString());
                        if (!fs.existsSync(dirPath)) {
                            fs.mkdirSync(dirPath, { recursive: true });
                        }
                        const imagePath = path.join(dirPath, `${capitulo}.jpg`);
                        await downloadImage(pageUrl, imagePath);
                    }, { concurrency: 5 });
            
                    console.log(`✅ Capítulo ${chapter.number} baixado com sucesso`);
                    
                    // Salvar log de sucesso
                    const downloadPath = path.join('manga', path.normalize(sanitizedName), chapter.number.toString());
                    chapterLogger.saveChapterSuccess(manga.name, workId, chapter.number, chapter.id[1], pages.pages.length, downloadPath);
                    
                    chapterSuccess = true;
                    break;
                    
                } catch (error) {
                    console.error(`❌ Tentativa ${attempt}/${maxRetries} falhou: ${error.message}`);
                    
                    if (attempt === maxRetries) {
                        // Salvar log de falha
                        chapterLogger.saveChapterFailure(manga.name, workId, chapter.number, chapter.id[1], maxRetries, error.message);
                    }
                }
            }
        }
        
        successfulUrls.push(mangaUrl);
        
    } catch (error) {
        console.error(`❌ Erro crítico ao processar obra ${urlIndex + 1}: ${error.message}`);
        failedUrls.push(mangaUrl);
    }
}