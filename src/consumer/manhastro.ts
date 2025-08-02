import fs from 'fs';
import Bluebird from 'bluebird';
import { downloadImage } from '../download/images';
import { promptUser } from '../utils/prompt';
import { ManhAstroProvider } from '../providers/scans/manhastro';
import path from 'path';
import { ChapterLogger } from '../utils/chapter_logger';
import { getMangaPathForSite, cleanTempFiles, cleanupAfterChapter } from '../utils/folder';

async function downloadManga() {
    // FILTRO GLOBAL ANTI-CSS
    const originalWrite = process.stdout.write;
    const originalLog = console.log;
    const originalError = console.error;
    const originalWarn = console.warn;
    
    const filterCSS = (text: string) => {
        return !text.includes('{') && 
               !text.includes('}') && 
               !text.includes('@media') && 
               !text.includes('css') && 
               !text.includes('.tela-') &&
               !text.includes('max-width') &&
               !text.includes('font-size') &&
               !text.includes('color:') &&
               !text.includes('cursor:') &&
               !text.includes('padding:') &&
               !text.includes('margin:');
    };
    
    process.stdout.write = (chunk: any) => {
        const text = chunk.toString();
        if (filterCSS(text)) {
            return originalWrite.call(process.stdout, chunk);
        }
        return true;
    };
    
    console.log = (...args) => {
        const message = args.join(' ');
        if (filterCSS(message)) {
            originalLog.apply(console, args);
        }
    };
    
    console.error = (...args) => {
        const message = args.join(' ');
        if (filterCSS(message)) {
            originalError.apply(console, args);
        }
    };
    
    console.warn = (...args) => {
        const message = args.join(' ');
        if (filterCSS(message)) {
            originalWarn.apply(console, args);
        }
    };

    const provider = new ManhAstroProvider();
    const chapterLogger = new ChapterLogger();
    const reportFile = 'download_report.txt';

    try {
        console.log('\n' + '='.repeat(80));
        console.log('🌟 MANHASTRO.NET DOWNLOADER');
        console.log('='.repeat(80));

        const mangaUrl = await promptUser('Digite a URL da obra do ManhAstro: ') as string;

        // Validar URL
        if (!mangaUrl.includes('manhastro.net')) {
            throw new Error('URL deve ser do ManhAstro.net');
        }

        const manga = await provider.getManga(mangaUrl);
        console.log('\n=== Informações do Manga ===');
        console.log('Título:', manga.name);
        console.log('Link:', manga.id);

        fs.writeFileSync(reportFile, `Relatório de Download - ManhAstro.net\nManga: ${manga.name}\nURL: ${manga.id}\n\n`);

        const chapters = await provider.getChapters(manga.id);

        console.log('\n=== Capítulos Disponíveis ===');
        chapters.slice(0, 10).forEach((chapter, index) => {
            console.log(`Índice: ${index} - Capítulo: ${chapter.number} - Nome: ${chapter.name}`);
        });
        
        if (chapters.length > 10) {
            console.log(`... e mais ${chapters.length - 10} capítulos`);
        }
        
        console.log('\n📋 Opções de Download:');
        console.log('1. Baixar todos (navegação sequencial prev/next)');
        console.log('2. Baixar por faixa personalizada (ex: 1-50)');
        console.log('3. Baixar apenas capítulos visíveis');
        console.log('4. Baixar capítulo específico');
        
        const downloadOption = await promptUser('Escolha uma opção (1-4): ') as string;
        
        let chaptersToDownload = [];
        
        switch (downloadOption) {
            case '1':
                // Descoberta sequencial via navegação prev/next (ORIGINAL)
                console.log('🚀 Iniciando navegação sequencial com download...');
                
                // Definir pasta de destino antecipadamente
                const mangaDir = getMangaPathForSite('ManhAstro', manga.name);
                console.log(`📁 Pasta de destino: ${mangaDir}`);
                
                // Criar callback para baixar cada capítulo descoberto
                const downloadCallback = async (chapter) => {
                    const numberMatch = chapter.number.match(/\d+\.?\d*/);
                    const chapterNumber = numberMatch ? numberMatch[0] : chapter.number;
                    
                    // Verificar se já foi baixado
                    if (chapterLogger.isChapterDownloaded(manga.name, chapterNumber)) {
                        console.log(`⏭️ Capítulo ${chapterNumber} já baixado - pulando`);
                        return;
                    }

                    const chapterDir = path.join(mangaDir, `Capítulo ${chapterNumber}`);
                    
                    const pages = await provider.getPages(chapter);
                    console.log(`📄 Encontradas ${pages.pages.length} páginas para ${chapter.name}`);

                    // Criar diretório do capítulo
                    if (!fs.existsSync(chapterDir)) {
                        fs.mkdirSync(chapterDir, { recursive: true });
                    }

                    // Download das páginas com anti-duplicação inteligente
                    await Bluebird.map(pages.pages, async (pageUrl, pageIndex) => {
                        const pageNumber = String(pageIndex + 1).padStart(2, '0');
                        
                        // Detectar extensão da imagem da URL
                        const urlExtension = pageUrl.match(/\.(avif|jpg|jpeg|png|webp|gif|bmp|tiff|svg)(\?|$)/i);
                        const extension = urlExtension ? urlExtension[1].toLowerCase() : 'jpg';
                        const imagePath = path.join(chapterDir, `${pageNumber}.${extension}`);
                        
                        // ANTI-DUPLICAÇÃO: Verificar se QUALQUER versão da página já existe
                        const possibleExtensions = ['avif', 'jpg', 'jpeg', 'png', 'webp', 'gif'];
                        const pageAlreadyExists = possibleExtensions.some(ext => {
                            const testPath = path.join(chapterDir, `${pageNumber}.${ext}`);
                            return fs.existsSync(testPath);
                        });
                        
                        if (!pageAlreadyExists) {
                            try {
                                await downloadImage(pageUrl, imagePath);
                                console.log(`✅ Página ${pageNumber}.${extension} baixada`);
                            } catch (imageError) {
                                // Log erro específico da imagem
                                provider.logImageError(chapterNumber, pageIndex + 1, pageUrl, imageError);
                                throw imageError; // Re-throw para manter comportamento
                            }
                        } else {
                            console.log(`⏭️ Página ${pageNumber} já existe - pulando`);
                        }
                    }, { concurrency: 3 });

                    // Log de sucesso
                    chapterLogger.saveChapterSuccess(
                        manga.name,
                        manga.id,
                        chapterNumber,
                        chapter.id[0], // Primeiro ID do array
                        pages.pages.length,
                        chapterDir
                    );

                    await cleanupAfterChapter();
                };
                
                chaptersToDownload = await provider.discoverAndDownloadChapters(manga.id, 'all', undefined, downloadCallback);
                
                // Pular o loop de download normal pois já foi feito
                console.log('\n=== DOWNLOAD CONCLUÍDO ===');
                console.log(`✅ Total processado: ${chaptersToDownload.length} capítulos`);
                console.log(`📁 Pasta: ${mangaDir}`);
                return;
                break;
                
            case '2':
                const range = await promptUser('Digite a faixa (ex: 1-50): ') as string;
                const [start, end] = range.split('-').map(n => parseInt(n.trim()));
                
                if (isNaN(start) || isNaN(end) || start < 1 || end < start) {
                    throw new Error('Faixa inválida (ex: 1-50)');
                }
                
                console.log(`🚀 Descobrindo capítulos ${start}-${end}...`);
                chaptersToDownload = await provider.discoverAndDownloadChapters(manga.id, 'range', {start, end});
                break;
                
            case '3':
                // Apenas os capítulos visíveis (comportamento original)
                chaptersToDownload = chapters;
                break;
                
            case '4':
                const chapterIndex = await promptUser('Digite o índice do capítulo: ') as string;
                const index = parseInt(chapterIndex);
                
                if (isNaN(index) || index < 0 || index >= chapters.length) {
                    throw new Error('Índice inválido');
                }
                
                chaptersToDownload = [chapters[index]];
                break;
                
            default:
                throw new Error('Opção inválida');
        }

        console.log(`\n🚀 Iniciando download de ${chaptersToDownload.length} capítulos...`);
        console.log('='.repeat(80));

        // Usar estrutura hierárquica: Site → Obra
        const mangaDir = getMangaPathForSite('ManhAstro', manga.name);
        console.log(`📁 Pasta de destino: ${mangaDir}`);

        let successCount = 0;
        let failCount = 0;
        
        for (let i = 0; i < chaptersToDownload.length; i++) {
            const chapter = chaptersToDownload[i];
            const progress = `[${i + 1}/${chaptersToDownload.length}]`;
            
            // Extrair número do capítulo (remover texto extra)
            const numberMatch = chapter.number.match(/\d+\.?\d*/);
            const chapterNumber = numberMatch ? numberMatch[0] : chapter.number;
            
            console.log(`\n${progress} 📖 Processando: ${chapter.name}`);
            
            // Verificar se já foi baixado
            if (chapterLogger.isChapterDownloaded(manga.name, chapterNumber)) {
                console.log(`✅ ${progress} Capítulo ${chapterNumber} já baixado - pulando`);
                continue;
            }

            const chapterDir = path.join(mangaDir, `Capítulo ${chapterNumber}`);

            try {
                const pages = await provider.getPages(chapter);
                console.log(`${progress} 📄 Encontradas ${pages.pages.length} páginas`);

                // Criar diretório do capítulo
                if (!fs.existsSync(chapterDir)) {
                    fs.mkdirSync(chapterDir, { recursive: true });
                }

                // Download das páginas com anti-duplicação inteligente
                await Bluebird.map(pages.pages, async (pageUrl, pageIndex) => {
                    const pageNumber = String(pageIndex + 1).padStart(2, '0');
                    
                    // Detectar extensão da imagem da URL
                    const urlExtension = pageUrl.match(/\.(avif|jpg|jpeg|png|webp|gif|bmp|tiff|svg)(\?|$)/i);
                    const extension = urlExtension ? urlExtension[1].toLowerCase() : 'jpg';
                    const imagePath = path.join(chapterDir, `${pageNumber}.${extension}`);
                    
                    // ANTI-DUPLICAÇÃO: Verificar se QUALQUER versão da página já existe
                    const possibleExtensions = ['avif', 'jpg', 'jpeg', 'png', 'webp', 'gif'];
                    const pageAlreadyExists = possibleExtensions.some(ext => {
                        const testPath = path.join(chapterDir, `${pageNumber}.${ext}`);
                        return fs.existsSync(testPath);
                    });
                    
                    if (!pageAlreadyExists) {
                        try {
                            await downloadImage(pageUrl, imagePath);
                            console.log(`${progress} ⬇️  Página ${pageNumber}/${pages.pages.length} baixada (.${extension})`);
                        } catch (imageError) {
                            // Log erro específico da imagem
                            provider.logImageError(chapterNumber, pageIndex + 1, pageUrl, imageError);
                            console.error(`${progress} ❌ Erro na página ${pageNumber}: ${imageError.message}`);
                            throw imageError; // Re-throw para manter comportamento
                        }
                    } else {
                        console.log(`${progress} ⏭️  Página ${pageNumber} já existe - pulando`);
                    }
                }, { concurrency: 3 }); // Concorrência reduzida para ser mais respeitoso

                // Log de sucesso
                chapterLogger.saveChapterSuccess(
                    manga.name,
                    manga.id,
                    chapterNumber,
                    chapter.id[0], // Primeiro ID do array
                    pages.pages.length,
                    chapterDir
                );

                console.log(`✅ ${progress} Capítulo ${chapterNumber} baixado com sucesso!`);
                successCount++;
                
                // Limpeza após cada capítulo
                await cleanupAfterChapter();

            } catch (error) {
                console.error(`❌ ${progress} Erro no capítulo ${chapterNumber}:`, error.message);
                
                // Log de falha
                chapterLogger.saveChapterFailure(
                    manga.name,
                    manga.id,
                    chapterNumber,
                    chapter.id[0], // Primeiro ID do array
                    1, // attempts
                    error.message
                );
                
                failCount++;
                
                // Continuar com próximo capítulo
                continue;
            }
        }

        // Relatório final
        console.log('\n' + '='.repeat(80));
        console.log('📊 RELATÓRIO FINAL');
        console.log('='.repeat(80));
        console.log(`✅ Sucessos: ${successCount}`);
        console.log(`❌ Falhas: ${failCount}`);
        console.log(`📁 Pasta: ${mangaDir}`);
        
        const finalReport = `\n--- RELATÓRIO FINAL ---\n` +
                          `Sucessos: ${successCount}\n` +
                          `Falhas: ${failCount}\n` +
                          `Pasta: ${mangaDir}\n`;
        
        fs.appendFileSync(reportFile, finalReport);
        
        if (failCount > 0) {
            console.log(`\n💡 Dica: Execute o modo rentry para tentar baixar as falhas novamente`);
        }

    } catch (error) {
        console.error('❌ Erro crítico:', error.message);
        process.exit(1);
    } finally {
        // Restaurar console original
        process.stdout.write = originalWrite;
        console.log = originalLog;
        console.error = originalError;
        console.warn = originalWarn;
        
        // Limpeza final
        console.log('\n🧹 Executando limpeza final...');
        cleanTempFiles();
    }
}

// Executar se chamado diretamente
if (require.main === module) {
    downloadManga().catch(console.error);
}

export { downloadManga };