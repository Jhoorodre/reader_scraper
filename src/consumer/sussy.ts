import { NewSussyToonsProvider } from '../providers/scans/sussytoons';
import fs from 'fs';
import Bluebird from 'bluebird';
import { downloadImage } from '../download/images';
import { promptUser } from '../utils/prompt';
import path from 'path';
import { ChapterLogger } from '../utils/chapter_logger';
import { TimeoutManager } from '../services/timeout_manager';
import { getMangaBasePath, cleanTempFiles, setupCleanupHandlers, periodicCleanup } from '../utils/folder';

async function executeAutoRentry(): Promise<void> {
    const chapterLogger = new ChapterLogger();
    const provider = new NewSussyToonsProvider();
    const reportFile = 'download_report.txt';
    
    // Aplicar timeouts progressivos no provider
    provider.applyProgressiveTimeouts();
    
    console.log('\n' + '='.repeat(80));
    console.log('🔄 MODO RENTRY AUTOMÁTICO ATIVADO');
    console.log('='.repeat(80));
    
    // Verificar se há falhas para reprocessar
    if (!chapterLogger.hasFailedChapters()) {
        console.log('✅ Nenhuma falha encontrada nos logs - rentry não necessário');
        return;
    }
    
    // Obter todas as falhas dos logs
    const allFailedWorks = chapterLogger.getAllFailedChapters();
    const totalFailed = allFailedWorks.reduce((acc, work) => acc + work.chapters.length, 0);
    
    console.log(`📋 Encontradas ${allFailedWorks.length} obras com falhas para reprocessar:`);
    allFailedWorks.forEach(work => {
        console.log(`  - ${work.workName}: ${work.chapters.length} capítulos falhados`);
    });
    console.log(`📊 Total: ${totalFailed} capítulos para reprocessar\n`);
    
    fs.appendFileSync(reportFile, `\n${'='.repeat(80)}\n🔄 MODO RENTRY AUTOMÁTICO INICIADO\n${'='.repeat(80)}\n`);
    
    let totalReprocessed = 0;
    let totalStillFailed = 0;
    
    // Processar cada obra com falhas
    for (let workIndex = 0; workIndex < allFailedWorks.length; workIndex++) {
        const failedWork = allFailedWorks[workIndex];
        const workName = failedWork.workName;
        const failedChapters = failedWork.chapters;
        
        console.log(`\n${'='.repeat(60)}`);
        console.log(`🔄 Reprocessando obra ${workIndex + 1}/${allFailedWorks.length}: ${workName}`);
        console.log(`📊 Capítulos falhados: ${failedChapters.length}`);
        console.log(`${'='.repeat(60)}`);
        
        fs.appendFileSync(reportFile, `\n=== RENTRY OBRA ${workIndex + 1}: ${workName} ===\n`);
        
        // Processar cada capítulo falhado desta obra
        for (const failedChapter of failedChapters) {
            console.log(`\n🔄 Reprocessando: ${failedChapter.chapterNumber}`);
            
            let reprocessSuccess = false;
            let lastError = null;
            const maxRetries = 3;
            
            // 3 novas tentativas para cada capítulo
            for (let attempt = 1; attempt <= maxRetries; attempt++) {
                try {
                    if (attempt > 1) {
                        console.log(`🔄 Tentativa ${attempt}/${maxRetries} para: ${failedChapter.chapterNumber}`);
                        await new Promise(resolve => setTimeout(resolve, 2000 * attempt));
                    }
                    
                    // Criar objeto chapter-like para compatibilidade
                    const chapterToReprocess = {
                        number: failedChapter.chapterNumber,
                        id: ['', failedChapter.chapterId] // Formato esperado [?, chapterId]
                    };
                    
                    // Verificar se já foi baixado (pode ter sido corrigido manualmente)
                    if (chapterLogger.isChapterDownloaded(workName, failedChapter.chapterNumber)) {
                        console.log(`✅ Capítulo ${failedChapter.chapterNumber} já foi corrigido - removendo das falhas`);
                        reprocessSuccess = true;
                        break;
                    }
                    
                    // Tentar baixar novamente
                    const pages = await provider.getPages(chapterToReprocess);
                    console.log(`📄 Total de Páginas: ${pages.pages.length}`);
                    
                    if (pages.pages.length === 0) {
                        throw new Error(`Capítulo ${failedChapter.chapterNumber} ainda retorna 0 páginas`);
                    }
                    
                    // Baixar todas as páginas
                    const sanitizedName = workName.replace(`Capítulo`, ``).replace(/[\\\/:*?"<>|]/g, '-');
                    
                    await Bluebird.map(pages.pages, async (pageUrl, pageIndex) => {
                        const capitulo = (pageIndex + 1) <= 9 ? `0${pageIndex + 1}` : `${pageIndex + 1}`;
                        console.log(`📥 Baixando Página ${capitulo}: ${pageUrl}`);
                        
                        const dirPath = path.join(getMangaBasePath(), path.normalize(sanitizedName), failedChapter.chapterNumber.toString());
                        
                        if (!fs.existsSync(dirPath)) {
                            fs.mkdirSync(dirPath, { recursive: true });
                        }
                        
                        const imagePath = path.join(dirPath, `${capitulo}.jpg`);
                        await downloadImage(pageUrl, imagePath);
                    }, { concurrency: 5 });
                    
                    console.log(`✅ RENTRY SUCESSO: ${failedChapter.chapterNumber} baixado com sucesso na tentativa ${attempt}`);
                    fs.appendFileSync(reportFile, `RENTRY SUCESSO: ${failedChapter.chapterNumber} - tentativa ${attempt}\n`);
                    
                    // Salvar como sucesso e remover das falhas
                    const downloadPath = path.join(getMangaBasePath(), path.normalize(sanitizedName), failedChapter.chapterNumber.toString());
                    chapterLogger.saveChapterSuccess(workName, failedChapter.workId, failedChapter.chapterNumber, failedChapter.chapterId, pages.pages.length, downloadPath);
                    
                    // Limpar arquivos temporários após sucesso
                    cleanTempFiles();
                    
                    reprocessSuccess = true;
                    totalReprocessed++;
                    break;
                    
                } catch (error) {
                    lastError = error;
                    console.error(`❌ RENTRY tentativa ${attempt}/${maxRetries} falhou: ${error.message}`);
                    fs.appendFileSync(reportFile, `RENTRY ERRO tentativa ${attempt}: ${error.message}\n`);
                    
                    // Para erros de proteção anti-bot, esperar mais tempo antes da próxima tentativa
                    if (error.message.includes('anti-bot') || error.message.includes('ofuscado')) {
                        const extraDelay = 5000 * attempt; // 5s, 10s, 15s extra
                        console.log(`🛡️ Proteção anti-bot detectada - aguardando ${extraDelay/1000}s extra...`);
                        await new Promise(resolve => setTimeout(resolve, extraDelay));
                    }
                }
            }
            
            if (!reprocessSuccess) {
                console.log(`💀 RENTRY falhou definitivamente: ${failedChapter.chapterNumber} - ${lastError?.message}`);
                fs.appendFileSync(reportFile, `RENTRY FALHA FINAL: ${failedChapter.chapterNumber} - ${lastError?.message}\n`);
                totalStillFailed++;
            }
        }
        
        console.log(`\n📊 Obra ${workIndex + 1} reprocessada: ${workName}`);
    }
    
    console.log('\n' + '='.repeat(80));
    console.log('📊 RESULTADO FINAL DO RENTRY AUTOMÁTICO');
    console.log('='.repeat(80));
    console.log(`✅ Capítulos corrigidos: ${totalReprocessed}`);
    console.log(`❌ Capítulos ainda com falha: ${totalStillFailed}`);
    console.log(`📈 Taxa de sucesso: ${totalReprocessed > 0 ? Math.round((totalReprocessed / (totalReprocessed + totalStillFailed)) * 100) : 0}%`);
    
    fs.appendFileSync(reportFile, `\n${'='.repeat(80)}\nRESULTADO RENTRY: ${totalReprocessed} sucessos, ${totalStillFailed} falhas\n${'='.repeat(80)}\n`);
    
    if (totalStillFailed === 0) {
        console.log('🎉 Todas as falhas foram corrigidas!');
    } else {
        console.log(`⚠️ ${totalStillFailed} capítulos ainda precisam de atenção manual`);
    }
}

async function downloadManga() {
    // Configurar handlers de limpeza no início da aplicação
    setupCleanupHandlers();
    
    const provider = new NewSussyToonsProvider();
    const reportFile = 'download_report.txt';
    const failsFile = 'url_fails.txt';
    const args = process.argv.slice(2);
    const isBatchMode = args.includes('urls');
    const isRetryMode = args.includes('rentry');
    const maxRetries = 3;
    const chapterLogger = new ChapterLogger();

    // Escanear pasta manga e criar/atualizar logs automaticamente
    console.log('📂 Escaneando pasta manga e atualizando logs...');
    chapterLogger.initializeLogsFromManga(getMangaBasePath());
    console.log('✅ Logs atualizados com base na pasta manga\n');

    try {
        let mangaUrls: string[] = [];
        
        if (isRetryMode) {
            console.log('🔁 Modo rentry manual ativado - usando sistema de logs...');
            await executeAutoRentry();
            return;
        } else if (isBatchMode) {
            console.log('🔄 Modo batch ativado - processando múltiplas URLs...');
            
            // Aplicar timeouts progressivos no provider (igual ao rentry)
            provider.applyProgressiveTimeouts();
            
            const urlsFile = 'obra_urls.txt';
            if (!fs.existsSync(urlsFile)) {
                console.error(`❌ Arquivo ${urlsFile} não encontrado!`);
                return;
            }
            const urlsContent = fs.readFileSync(urlsFile, 'utf-8');
            mangaUrls = urlsContent.split('\n').filter(url => url.trim().length > 0).map(url => url.trim());
            console.log(`📋 Encontradas ${mangaUrls.length} URLs para processar`);
        } else {
            const mangaUrl = await promptUser('Digite a URL da obra: ') as string;
            mangaUrls = [mangaUrl];
        }

        fs.writeFileSync(reportFile, `Relatório de Download - ${isRetryMode ? 'Reprocessamento de Falhas' : isBatchMode ? 'Múltiplas Obras' : 'Obra Única'}\n\n`);
        
        const successfulUrls: string[] = [];
        const failedUrls: string[] = [];

        console.log(`🚀 Processando ${mangaUrls.length} obras...`);
        
        await Bluebird.map(mangaUrls, async (mangaUrl, urlIndex) => {
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
                
                console.log('\n=== Capítulos Disponíveis no Site ===');
                chapters.forEach((chapter, index) => {
                    console.log(`Índice: ${index} - Capítulo: ${chapter.number}`);
                });
                
                let selectedChapters = [];
                
                if (isBatchMode || isRetryMode) {
                    console.log('\n🔍 Detectando capítulos novos baseado nos logs...');
                    selectedChapters = chapterLogger.detectNewChapters(manga.name, chapters);
                    
                    if (selectedChapters.length === 0) {
                        console.log(`✅ Obra ${urlIndex + 1}/${mangaUrls.length}: Nenhum capítulo novo detectado - obra já atualizada (${manga.name})`);
                        chapterLogger.showWorkStats(manga.name);
                        successfulUrls.push(mangaUrl);
                        return;
                    }
                    
                    console.log(`\n📦 Modo automático: baixando ${selectedChapters.length} capítulos (novos + falhas)...`);
                } else {
                    console.log('\nOpções de Download:');
                    console.log('1. Baixar tudo');
                    console.log('2. Baixar intervalo de capítulos');
                    console.log('3. Escolher capítulos específicos');
                    
                    const option = await promptUser('Escolha uma opção (1, 2 ou 3): ');
                    
                    if (option === '1') {
                        selectedChapters = chapters;
                    } else if (option === '2') {
                        const start = parseInt(await promptUser('Digite o índice inicial do intervalo: '), 10);
                        const end = parseInt(await promptUser('Digite o índice final do intervalo: '), 10);
                        selectedChapters = chapters.slice(start, end + 1);
                    } else if (option === '3') {
                        const chaptersInput = await promptUser('Digite os índices dos capítulos que deseja baixar, separados por vírgula (ex: 0,1,4): ');
                        const indices = chaptersInput.split(',').map(num => parseInt(num.trim(), 10));
                        selectedChapters = indices.map(index => chapters[index]).filter(chapter => chapter !== undefined);
                    } else {
                        throw new Error('Opção inválida selecionada.');
                    }
                }
                
                console.log('\nCapítulos selecionados para download:');
                selectedChapters.forEach(chapter => console.log(`Capítulo: ${chapter.number}`));
                
                let failedChapters = 0;
                const totalChapters = selectedChapters.length;
                
                await Bluebird.map(selectedChapters, async (chapter) => {
                        console.log(`\n=== Processando Capítulo: ${chapter.number} ===`);
                        
                        // Verificar se o capítulo já foi baixado (PRIORIDADE 1: LOGS)
                        if (chapterLogger.isChapterDownloaded(manga.name, chapter.number)) {
                            console.log(`⏭️ Capítulo ${chapter.number} já baixado (confirmado por log) - pulando...`);
                            fs.appendFileSync(reportFile, `Capítulo ${chapter.number} - JÁ BAIXADO (confirmado por log)\n`);
                            return;
                        }
                        
                        // Verificação secundária na pasta física (apenas como backup)
                        const chapterDir = path.join(getMangaBasePath(), path.normalize(sanitizedName), chapter.number.toString());
                        
                        if (fs.existsSync(chapterDir)) {
                            const existingFiles = fs.readdirSync(chapterDir);
                            if (existingFiles.length > 0) {
                                console.log(`⚠️ Capítulo ${chapter.number} existe na pasta mas sem log - criando log de sucesso...`);
                                // Criar log retroativo para manter consistência
                                chapterLogger.saveChapterSuccess(manga.name, workId, chapter.number, chapter.id[1], existingFiles.length, chapterDir);
                                fs.appendFileSync(reportFile, `Capítulo ${chapter.number} - LOG RETROATIVO CRIADO\n`);
                                return;
                            }
                        }
                        
                        fs.appendFileSync(reportFile, `Capítulo: ${chapter.number}\n`);
                        
                        // Sistema de retry para capítulo individual
                        let chapterSuccess = false;
                        let lastChapterError = null;
                        
                        for (let chapterAttempt = 1; chapterAttempt <= maxRetries; chapterAttempt++) {
                            try {
                                if (chapterAttempt > 1) {
                                    console.log(`🔄 Tentativa ${chapterAttempt}/${maxRetries} para capítulo: ${chapter.number}`);
                                    await new Promise(resolve => setTimeout(resolve, 2000 * chapterAttempt));
                                }
                                // Obter as páginas do capítulo com timeout de segurança
                                console.log(`⏱️ Obtendo páginas...`);
                                const pages = await provider.getPages(chapter);
                                console.log(`Total de Páginas: ${pages.pages.length}`);

                                if (pages.pages.length === 0) {
                                    throw new Error(`Capítulo ${chapter.number} retornou 0 páginas`);
                                }
                    
                                await Bluebird.map(pages.pages, async (pageUrl, pageIndex) => {
                                    const capitulo = (pageIndex + 1 ) <= 9 ? `0${pageIndex + 1}` :`${pageIndex + 1}`
                                    console.log(`Baixando Página ${capitulo}: ${pageUrl}`);
                            
                                    // Criar o diretório para o capítulo
                                    const dirPath = path.join(getMangaBasePath(), path.normalize(sanitizedName), chapter.number.toString());
                            
                                    // Verificar se o diretório existe, se não, criar
                                    if (!fs.existsSync(dirPath)) {
                                        fs.mkdirSync(dirPath, { recursive: true });
                                    }
                            
                                    // Caminho completo para salvar a imagem
                                    const imagePath = path.join(dirPath, `${capitulo}.jpg`);
                            
                                    // Baixar a imagem
                                    await downloadImage(pageUrl, imagePath);
                                }, { concurrency: 5 });
                        
                                console.log(`✅ Capítulo ${chapter.number} baixado com sucesso na tentativa ${chapterAttempt}`);
                                fs.appendFileSync(reportFile, `Capítulo ${chapter.number} baixado com sucesso.\n`);
                                
                                // Salvar log individual do capítulo
                                const downloadPath = path.join(getMangaBasePath(), path.normalize(sanitizedName), chapter.number.toString());
                                chapterLogger.saveChapterSuccess(manga.name, workId, chapter.number, chapter.id[1], pages.pages.length, downloadPath);
                                
                                // Limpar arquivos temporários após sucesso
                                cleanTempFiles();
                                
                                // Limpeza periódica a cada N downloads
                                periodicCleanup();
                                
                                chapterSuccess = true;
                                break;
                                
                            } catch (error) {
                                lastChapterError = error;
                                console.error(`❌ Tentativa ${chapterAttempt}/${maxRetries} falhou para capítulo ${chapter.number}: ${error.message}`);
                                fs.appendFileSync(reportFile, `ERRO tentativa ${chapterAttempt}: ${error.message}\n`);
                                
                                // Para erros de proteção anti-bot, esperar mais tempo antes da próxima tentativa
                                if (error.message.includes('anti-bot') || error.message.includes('ofuscado')) {
                                    const extraDelay = 5000 * chapterAttempt; // 5s, 10s, 15s extra
                                    console.log(`🛡️ Proteção anti-bot detectada - aguardando ${extraDelay/1000}s extra...`);
                                    await new Promise(resolve => setTimeout(resolve, extraDelay));
                                }
                                
                                if (chapterAttempt === maxRetries) {
                                    console.error(`💀 Todas as ${maxRetries} tentativas falharam para capítulo: ${chapter.number}`);
                                    // Limpeza de arquivos temporários após falha final
                                    console.log('🧹 Limpando arquivos temporários após falha...');
                                    cleanTempFiles();
                                }
                            }
                        }
                        
                        // Se capítulo falhou após 3 tentativas, salvar logs
                        if (!chapterSuccess) {
                            failedChapters++;
                            const chapterUrl = `https://www.sussytoons.wtf/capitulo/${chapter.id[1]}`;
                            
                            // Salvar log individual de falha
                            chapterLogger.saveChapterFailure(manga.name, workId, chapter.number, chapter.id[1], maxRetries, lastChapterError?.message || 'Erro desconhecido');
                            
                            if (isBatchMode || isRetryMode) {
                                console.log(`💾 Salvando capítulo falhado: ${chapterUrl}`);
                                
                                // Ler falhas existentes
                                const existingFails = fs.existsSync(failsFile) ? 
                                    fs.readFileSync(failsFile, 'utf-8').split('\n').filter(url => url.trim().length > 0) : [];
                                
                                // Adicionar nova falha se não existir
                                if (!existingFails.includes(chapterUrl)) {
                                    existingFails.push(chapterUrl);
                                    fs.writeFileSync(failsFile, existingFails.join('\n') + '\n');
                                    console.log(`✅ Capítulo falhado salvo em ${failsFile}`);
                                }
                            }
                            
                            fs.appendFileSync(reportFile, `FALHA DEFINITIVA: Capítulo ${chapter.number} - ${lastChapterError?.message}\n`);
                        }
                    }, { concurrency: 2 });
                    
                    // Mostrar estatísticas da obra
                    chapterLogger.showWorkStats(manga.name);
                    
                    console.log(`\n✅ Obra ${urlIndex + 1} concluída: ${manga.name}`);
                    fs.appendFileSync(reportFile, `=== FIM DA OBRA ${urlIndex + 1}: ${manga.name} ===\n\n`);
                    successfulUrls.push(mangaUrl);
                    
            } catch (error) {
                console.error(`❌ Erro crítico ao processar obra ${urlIndex + 1} (${mangaUrl}): ${error.message}`);
                fs.appendFileSync(reportFile, `ERRO CRÍTICO na obra: ${error.message}\n\n`);
                failedUrls.push(mangaUrl);
            }
        }, { concurrency: 1 });
        
        console.log('\n📊 Resultado Final:');
        console.log(`✅ Sucessos: ${successfulUrls.length}`);
        console.log(`❌ Falhas: ${failedUrls.length}`);
        
        console.log('\n🎉 Processamento batch completo. Relatório salvo em:', reportFile);
        
    } catch (error) {
        console.error('Erro durante a execução:', error);
        fs.appendFileSync(reportFile, `Erro durante a execução: ${error.message}\n`);
        
        // Limpeza de emergência em caso de erro crítico
        console.log('🚨 Erro crítico detectado - executando limpeza de emergência...');
        cleanTempFiles();
    }
}

downloadManga();