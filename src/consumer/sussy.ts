import { NewSussyToonsProvider } from '../providers/scans/sussytoons';
import fs from 'fs';
import Bluebird from 'bluebird';
import { downloadImage } from '../download/images';
import { promptUser } from '../utils/prompt';
import path from 'path';
import { ChapterLogger } from '../utils/chapter_logger';
import { TimeoutManager } from '../services/timeout_manager';

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
                        
                        const dirPath = path.join('manga', path.normalize(sanitizedName), failedChapter.chapterNumber.toString());
                        
                        if (!fs.existsSync(dirPath)) {
                            fs.mkdirSync(dirPath, { recursive: true });
                        }
                        
                        const imagePath = path.join(dirPath, `${capitulo}.jpg`);
                        await downloadImage(pageUrl, imagePath);
                    }, { concurrency: 5 });
                    
                    console.log(`✅ RENTRY SUCESSO: ${failedChapter.chapterNumber} baixado com sucesso na tentativa ${attempt}`);
                    fs.appendFileSync(reportFile, `RENTRY SUCESSO: ${failedChapter.chapterNumber} - tentativa ${attempt}\n`);
                    
                    // Salvar como sucesso e remover das falhas
                    const downloadPath = path.join('manga', path.normalize(sanitizedName), failedChapter.chapterNumber.toString());
                    chapterLogger.saveChapterSuccess(workName, failedChapter.workId, failedChapter.chapterNumber, failedChapter.chapterId, pages.pages.length, downloadPath);
                    
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

async function executeCyclicRecovery(): Promise<void> {
    const chapterLogger = new ChapterLogger();
    const reportFile = 'download_report.txt';
    let cycleCount = 0;
    const maxCycles = 10; // Máximo de 10 tentativas de rentry
    
    console.log('\n' + '='.repeat(90));
    console.log('🔄 MODO CICLO AUTOMÁTICO DE RENTRY ATIVADO');
    console.log('='.repeat(90));
    console.log('📝 Estratégia: Múltiplas tentativas de rentry até eliminar todas as falhas');
    console.log('⚡ Cada ciclo dá novas chances para capítulos que falharam anteriormente');
    console.log('='.repeat(90));
    
    fs.appendFileSync(reportFile, `\n${'='.repeat(90)}\n🔄 MODO CICLO AUTOMÁTICO DE RENTRY INICIADO\n${'='.repeat(90)}\n`);
    
    while (cycleCount < maxCycles) {
        cycleCount++;
        
        console.log(`\n🔄 === CICLO DE RENTRY ${cycleCount}/${maxCycles} ===`);
        fs.appendFileSync(reportFile, `\n=== CICLO DE RENTRY ${cycleCount} ===\n`);
        
        // Verificar se ainda há falhas para processar
        if (!chapterLogger.hasFailedChapters()) {
            console.log('✅ Nenhuma falha encontrada - ciclo automático concluído!');
            fs.appendFileSync(reportFile, 'CICLO CONCLUÍDO: Nenhuma falha restante\n');
            break;
        }
        
        // Mostrar status atual das falhas
        const failedWorks = chapterLogger.getAllFailedChapters();
        const totalFailedChapters = failedWorks.reduce((acc, work) => acc + work.chapters.length, 0);
        
        console.log(`📊 Status antes do Ciclo ${cycleCount}:`);
        console.log(`   📁 Obras com falhas: ${failedWorks.length}`);
        console.log(`   📄 Capítulos falhados: ${totalFailedChapters}`);
        
        failedWorks.forEach(work => {
            console.log(`   - ${work.workName}: ${work.chapters.length} capítulos`);
        });
        
        // Aplicar timeouts progressivos para este ciclo
        const timeoutManager = TimeoutManager.getInstance();
        timeoutManager.setCycle(cycleCount);
        
        if (cycleCount > 1) {
            const increasePercent = timeoutManager.getIncreasePercentage();
            console.log(`🕐 Aplicando timeouts progressivos: +${increasePercent}% (Ciclo ${cycleCount})`);
        }
        
        // Executar rentry
        console.log(`\n🔄 Executando RENTRY - Ciclo ${cycleCount}`);
        console.log('-'.repeat(60));
        
        const reprocessedCount = await executeRentryPhase(cycleCount);
        
        // Verificar se rentry resolveu todas as falhas
        if (!chapterLogger.hasFailedChapters()) {
            console.log('🎉 Rentry resolveu todas as falhas - ciclo concluído!');
            fs.appendFileSync(reportFile, `CICLO ${cycleCount} CONCLUÍDO: Rentry resolveu todas as falhas\n`);
            break;
        }
        
        // Se não houve progresso, parar o ciclo
        if (reprocessedCount === 0) {
            console.log(`⚠️ Ciclo ${cycleCount} não corrigiu nenhuma falha - parando ciclo automático`);
            console.log('📋 Falhas restantes são persistentes e requerem atenção manual');
            fs.appendFileSync(reportFile, `CICLO ${cycleCount}: Sem progresso - falhas persistentes\n`);
            break;
        }
        
        console.log(`\n📊 Resultado do Ciclo ${cycleCount}:`);
        console.log(`   ✅ Capítulos corrigidos: ${reprocessedCount}`);
        console.log(`   📈 Progresso positivo - continuando...`);
        
        // Pequena pausa entre ciclos
        console.log('⏳ Aguardando 3 segundos antes do próximo ciclo...');
        await new Promise(resolve => setTimeout(resolve, 3000));
    }
    
    // Relatório final do ciclo
    const finalFailedWorks = chapterLogger.getAllFailedChapters();
    const finalFailedCount = finalFailedWorks.reduce((acc, work) => acc + work.chapters.length, 0);
    
    console.log('\n' + '='.repeat(90));
    console.log('📊 RELATÓRIO FINAL DO CICLO AUTOMÁTICO DE RENTRY');
    console.log('='.repeat(90));
    console.log(`🔄 Ciclos de rentry executados: ${cycleCount}`);
    console.log(`📄 Falhas restantes: ${finalFailedCount} capítulos`);
    
    if (finalFailedCount === 0) {
        console.log('🎉 SUCESSO TOTAL: Todas as falhas foram eliminadas!');
        console.log('🏆 O ciclo automático conseguiu corrigir 100% das falhas!');
        fs.appendFileSync(reportFile, `\nSUCESSO TOTAL: Ciclo eliminou todas as falhas em ${cycleCount} iterações\n`);
    } else {
        console.log('⚠️ Falhas persistentes que requerem atenção manual:');
        finalFailedWorks.forEach(work => {
            console.log(`   - ${work.workName}: ${work.chapters.length} capítulos`);
            work.chapters.forEach(ch => {
                console.log(`     ❌ ${ch.chapterNumber}: ${ch.errorMessage}`);
            });
        });
        fs.appendFileSync(reportFile, `\nCiclo finalizado com ${finalFailedCount} falhas persistentes\n`);
        
        const totalInitialFailed = 'desconhecido'; // Poderia calcular se salvássemos o estado inicial
        console.log(`📈 Muitas falhas podem ter sido corrigidas durante os ${cycleCount} ciclos!`);
    }
    
    // Restaurar timeouts para valores padrão após completar ciclos
    const timeoutManager = TimeoutManager.getInstance();
    timeoutManager.resetToDefaults();
    provider.resetTimeouts();
    
    console.log('='.repeat(90));
}

async function executeRentryPhase(cycleNumber: number): Promise<number> {
    console.log(`🔄 Executando fase RENTRY do ciclo ${cycleNumber}...`);
    
    const chapterLogger = new ChapterLogger();
    const initialFailedWorks = chapterLogger.getAllFailedChapters();
    const initialFailedCount = initialFailedWorks.reduce((acc, work) => acc + work.chapters.length, 0);
    
    // Configurar timeouts para este ciclo
    const timeoutManager = TimeoutManager.getInstance();
    timeoutManager.setCycle(cycleNumber);
    
    // Executar rentry
    await executeAutoRentry();
    
    // Calcular quantos foram corrigidos
    const finalFailedWorks = chapterLogger.getAllFailedChapters();
    const finalFailedCount = finalFailedWorks.reduce((acc, work) => acc + work.chapters.length, 0);
    
    const correctedCount = initialFailedCount - finalFailedCount;
    console.log(`📊 Rentry fase: ${correctedCount} capítulos corrigidos`);
    
    return correctedCount;
}


async function downloadManga() {
    const provider = new NewSussyToonsProvider();
    const reportFile = 'download_report.txt';
    const failsFile = 'url_fails.txt';
    const args = process.argv.slice(2);
    const isBatchMode = args.includes('urls');
    const isRetryMode = args.includes('rentry');
    const maxRetries = 3;
    const chapterLogger = new ChapterLogger();

    try {
        let mangaUrls: string[] = [];
        
        if (isRetryMode) {
            console.log('🔁 Modo rentry manual ativado - usando sistema de logs...');
            await executeAutoRentry();
            return;
        } else if (isBatchMode) {
            console.log('🔄 Modo batch ativado - processando múltiplas URLs...');
            const urlsFile = 'obra_urls.txt';
            if (!fs.existsSync(urlsFile)) {
                console.error(`❌ Arquivo ${urlsFile} não encontrado!`);
                return;
            }
            const urlsContent = fs.readFileSync(urlsFile, 'utf-8');
            mangaUrls = urlsContent.split('\n').filter(url => url.trim().length > 0);
            console.log(`📋 Encontradas ${mangaUrls.length} URLs para processar`);
        } else {
            const mangaUrl = await promptUser('Digite a URL da obra: ') as string;
            mangaUrls = [mangaUrl];
        }

        fs.writeFileSync(reportFile, `Relatório de Download - ${isRetryMode ? 'Reprocessamento de Falhas' : isBatchMode ? 'Múltiplas Obras' : 'Obra Única'}\n\n`);
        
        const successfulUrls: string[] = [];
        const failedUrls: string[] = [];

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
                
                // Verificar se obra já tem logs
                chapterLogger.hasWorkLogs(manga.name);
                
                console.log('\n=== Capítulos Disponíveis no Site ===');
                chapters.forEach((chapter, index) => {
                    console.log(`Índice: ${index} - Capítulo: ${chapter.number}`);
                });
                
                let selectedChapters = [];
                
                if (isBatchMode || isRetryMode) {
                    console.log('\n🔍 Detectando capítulos novos baseado nos logs...');
                    selectedChapters = chapterLogger.detectNewChapters(manga.name, chapters);
                    
                    if (selectedChapters.length === 0) {
                        console.log('✅ Nenhum capítulo novo detectado - obra já atualizada');
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
                        const chapterDir = path.join('manga', path.normalize(sanitizedName), chapter.number.toString());
                        
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
                                    await new Promise(resolve => setTimeout(resolve, 1000 * chapterAttempt));
                                }
                                // Obter as páginas do capítulo com timeout de segurança
                                console.log(`⏱️ Obtendo páginas (timeout: ${TimeoutManager.getInstance().getTimeout('request')/1000}s)...`);
                                const pages = await Promise.race([
                                    provider.getPages(chapter),
                                    new Promise((_, reject) => 
                                        setTimeout(() => reject(new Error('Timeout na obtenção de páginas')), 
                                            TimeoutManager.getInstance().getTimeout('request'))
                                    )
                                ]);
                                console.log(`Total de Páginas: ${pages.pages.length}`);

                                if (pages.pages.length === 0) {
                                    throw new Error(`Capítulo ${chapter.number} retornou 0 páginas`);
                                }
                    
                                await Bluebird.map(pages.pages, async (pageUrl, pageIndex) => {
                                    const capitulo = (pageIndex + 1 ) <= 9 ? `0${pageIndex + 1}` :`${pageIndex + 1}`
                                    console.log(`Baixando Página ${capitulo}: ${pageUrl}`);
                            
                                    // Criar o diretório para o capítulo
                                    const dirPath = path.join('manga', path.normalize(sanitizedName), chapter.number.toString());
                            
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
                                const downloadPath = path.join('manga', path.normalize(sanitizedName), chapter.number.toString());
                                chapterLogger.saveChapterSuccess(manga.name, workId, chapter.number, chapter.id[1], pages.pages.length, downloadPath);
                                
                                chapterSuccess = true;
                                break;
                                
                            } catch (error) {
                                lastChapterError = error;
                                console.error(`❌ Tentativa ${chapterAttempt}/${maxRetries} falhou para capítulo ${chapter.number}: ${error.message}`);
                                fs.appendFileSync(reportFile, `ERRO tentativa ${chapterAttempt}: ${error.message}\n`);
                                
                                // Para erros de proteção anti-bot, esperar mais tempo antes da próxima tentativa
                                if (error.message.includes('anti-bot') || error.message.includes('ofuscado')) {
                                    const extraDelay = 3000 * chapterAttempt; // 3s, 6s, 9s extra
                                    console.log(`🛡️ Proteção anti-bot detectada - aguardando ${extraDelay/1000}s extra...`);
                                    await new Promise(resolve => setTimeout(resolve, extraDelay));
                                }
                                
                                if (chapterAttempt === maxRetries) {
                                    console.error(`💀 Todas as ${maxRetries} tentativas falharam para capítulo: ${chapter.number}`);
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
                    
                    const failureRate = failedChapters / totalChapters;
                    console.log(`\n📊 Estatísticas: ${totalChapters - failedChapters}/${totalChapters} capítulos baixados (${Math.round((1 - failureRate) * 100)}% sucesso)`);
                    
                    console.log(`\n📊 Primeira fase concluída: ${manga.name}`);
                    console.log(`📊 Estatísticas: ${totalChapters - failedChapters}/${totalChapters} capítulos baixados (${Math.round((1 - failureRate) * 100)}% sucesso)`);
                    
                    // SEGUNDA FASE: Reprocessar falhas desta obra
                    if (failedChapters > 0) {
                        console.log(`\n🔄 SEGUNDA FASE: Reprocessando ${failedChapters} capítulos falhados de ${manga.name}...`);
                        fs.appendFileSync(reportFile, `\n=== SEGUNDA FASE - REPROCESSAMENTO DE FALHAS ===\n`);
                        
                        // Ler falhas do arquivo que são desta obra
                        const currentFails = fs.existsSync(failsFile) ? 
                            fs.readFileSync(failsFile, 'utf-8').split('\n').filter(url => url.trim().length > 0) : [];
                        
                        const thisWorkFails = currentFails.filter(url => {
                            // Extrair ID da obra da URL atual
                            const workMatch = mangaUrl.match(/\/obra\/(\d+)/);
                            if (!workMatch) return false;
                            const workId = workMatch[1];
                            
                            // Verificar se a URL de falha é desta obra
                            return url.includes(`sussytoons.wtf`) && 
                                   (url.includes(`/obras/${workId}/`) || url.includes(`/capitulo/`));
                        });
                        
                        console.log(`📋 Encontradas ${thisWorkFails.length} falhas desta obra para reprocessar`);
                        
                        if (thisWorkFails.length > 0) {
                            const reprocessedSuccesses: string[] = [];
                            const finalFails: string[] = [];
                            
                            for (const failUrl of thisWorkFails) {
                                console.log(`\n🔄 Reprocessando: ${failUrl}`);
                                
                                let reprocessSuccess = false;
                                let lastReprocessError = null;
                                
                                // 3 tentativas para reprocessar
                                for (let reprocessAttempt = 1; reprocessAttempt <= maxRetries; reprocessAttempt++) {
                                    try {
                                        if (reprocessAttempt > 1) {
                                            console.log(`🔄 Tentativa ${reprocessAttempt}/${maxRetries} para reprocessamento: ${failUrl}`);
                                            await new Promise(resolve => setTimeout(resolve, 2000 * reprocessAttempt));
                                        }
                                        
                                        // Extrair ID do capítulo da URL
                                        const chapterMatch = failUrl.match(/\/capitulo\/(\d+)/);
                                        if (!chapterMatch) throw new Error('URL de capítulo inválida');
                                        
                                        const chapterId = chapterMatch[1];
                                        
                                        // Encontrar o capítulo na lista
                                        const chapterToReprocess = selectedChapters.find(ch => ch.id[1] === chapterId);
                                        if (!chapterToReprocess) throw new Error('Capítulo não encontrado na lista');
                                        
                                        // Verificar se já foi baixado durante reprocessamento (PRIORIDADE 1: LOGS)
                                        if (chapterLogger.isChapterDownloaded(manga.name, chapterToReprocess.number)) {
                                            console.log(`✅ Capítulo ${chapterToReprocess.number} já foi baixado (confirmado por log) durante reprocessamento`);
                                            reprocessSuccess = true;
                                            break;
                                        }
                                        
                                        // Verificação secundária na pasta física
                                        const chapterDirReprocess = path.join('manga', path.normalize(sanitizedName), chapterToReprocess.number.toString());
                                        
                                        if (fs.existsSync(chapterDirReprocess)) {
                                            const existingFiles = fs.readdirSync(chapterDirReprocess);
                                            if (existingFiles.length > 0) {
                                                console.log(`⚠️ Capítulo ${chapterToReprocess.number} existe na pasta mas sem log - criando log retroativo...`);
                                                // Criar log retroativo
                                                chapterLogger.saveChapterSuccess(manga.name, workId, chapterToReprocess.number, chapterToReprocess.id[1], existingFiles.length, chapterDirReprocess);
                                                reprocessSuccess = true;
                                                break;
                                            }
                                        }
                                        
                                        // Tentar baixar novamente
                                        const pages = await provider.getPages(chapterToReprocess);
                                        console.log(`Total de Páginas: ${pages.pages.length}`);
                                        
                                        if (pages.pages.length === 0) {
                                            throw new Error(`Capítulo ${chapterToReprocess.number} ainda retorna 0 páginas`);
                                        }
                                        
                                        await Bluebird.map(pages.pages, async (pageUrl, pageIndex) => {
                                            const capitulo = (pageIndex + 1 ) <= 9 ? `0${pageIndex + 1}` :`${pageIndex + 1}`
                                            console.log(`Baixando Página ${capitulo}: ${pageUrl}`);
                                    
                                            // Criar o diretório para o capítulo
                                            const dirPath = path.join('manga', path.normalize(sanitizedName), chapterToReprocess.number.toString());
                                    
                                            if (!fs.existsSync(dirPath)) {
                                                fs.mkdirSync(dirPath, { recursive: true });
                                            }
                                    
                                            const imagePath = path.join(dirPath, `${capitulo}.jpg`);
                                            await downloadImage(pageUrl, imagePath);
                                        }, { concurrency: 5 });
                                        
                                        console.log(`✅ Reprocessamento bem-sucedido: Capítulo ${chapterToReprocess.number}`);
                                        fs.appendFileSync(reportFile, `REPROCESSAMENTO SUCESSO: Capítulo ${chapterToReprocess.number}\n`);
                                        
                                        // Salvar log individual do capítulo reprocessado
                                        const downloadPath = path.join('manga', path.normalize(sanitizedName), chapterToReprocess.number.toString());
                                        chapterLogger.saveChapterSuccess(manga.name, workId, chapterToReprocess.number, chapterToReprocess.id[1], pages.pages.length, downloadPath);
                                        reprocessSuccess = true;
                                        break;
                                        
                                    } catch (error) {
                                        lastReprocessError = error;
                                        console.error(`❌ Reprocessamento tentativa ${reprocessAttempt}/${maxRetries} falhou: ${error.message}`);
                                        fs.appendFileSync(reportFile, `REPROCESSAMENTO ERRO tentativa ${reprocessAttempt}: ${error.message}\n`);
                                    }
                                }
                                
                                if (reprocessSuccess) {
                                    reprocessedSuccesses.push(failUrl);
                                } else {
                                    finalFails.push(failUrl);
                                    console.log(`💀 Reprocessamento falhou definitivamente: ${failUrl}`);
                                    fs.appendFileSync(reportFile, `REPROCESSAMENTO FALHA FINAL: ${failUrl} - ${lastReprocessError?.message}\n`);
                                }
                            }
                            
                            // Atualizar arquivo de falhas
                            const remainingFails = currentFails.filter(url => !reprocessedSuccesses.includes(url));
                            
                            // Marcar falhas finais com flag especial
                            const markedFinalFails = finalFails.map(url => `${url} # TODAS_TENTATIVAS_ESGOTADAS`);
                            const updatedFails = [...remainingFails.filter(url => !finalFails.includes(url.split(' #')[0])), ...markedFinalFails];
                            
                            if (updatedFails.length === 0) {
                                if (fs.existsSync(failsFile)) {
                                    fs.unlinkSync(failsFile);
                                    console.log(`🗑️ Arquivo de falhas removido - todas as falhas foram resolvidas!`);
                                }
                            } else {
                                fs.writeFileSync(failsFile, updatedFails.join('\n') + '\n');
                                console.log(`📝 Arquivo de falhas atualizado`);
                            }
                            
                            console.log(`\n📊 Resultado do reprocessamento:`);
                            console.log(`✅ Sucessos: ${reprocessedSuccesses.length}`);
                            console.log(`❌ Falhas finais: ${finalFails.length}`);
                            
                            fs.appendFileSync(reportFile, `\nRESULTADO REPROCESSAMENTO: ${reprocessedSuccesses.length} sucessos, ${finalFails.length} falhas finais\n`);
                        }
                    }
                    
                    // Mostrar estatísticas da obra
                    chapterLogger.showWorkStats(manga.name);
                    
                    console.log(`\n✅ Obra ${urlIndex + 1} TOTALMENTE concluída: ${manga.name}`);
                    fs.appendFileSync(reportFile, `=== FIM COMPLETO DA OBRA ${urlIndex + 1}: ${manga.name} ===\n\n`);
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
        
        if (isRetryMode && successfulUrls.length > 0) {
            console.log('\n🧹 Removendo URLs bem-sucedidas do arquivo de falhas...');
            const remainingFails = mangaUrls.filter(url => !successfulUrls.includes(url));
            if (remainingFails.length === 0) {
                if (fs.existsSync(failsFile)) {
                    fs.unlinkSync(failsFile);
                    console.log('🗑️ Arquivo de falhas removido - todas as falhas foram resolvidas!');
                }
            } else {
                fs.writeFileSync(failsFile, remainingFails.join('\n') + '\n');
                console.log(`📝 Arquivo de falhas atualizado. Restam ${remainingFails.length} falhas.`);
            }
        } else if (failedUrls.length > 0 && !isBatchMode && !isRetryMode) {
            // Salvar falhas apenas se não for modo batch (no batch já foram salvas imediatamente)
            const existingFails = fs.existsSync(failsFile) ? 
                fs.readFileSync(failsFile, 'utf-8').split('\n').filter(url => url.trim().length > 0) : [];
            
            const allFails = [...new Set([...existingFails, ...failedUrls])];
            fs.writeFileSync(failsFile, allFails.join('\n') + '\n');
            console.log(`💾 ${failedUrls.length} falhas salvas em ${failsFile}`);
        } else if (isBatchMode && failedUrls.length > 0) {
            console.log(`📝 ${failedUrls.length} falhas já foram salvas individualmente durante o processamento`);
        }
        
        console.log('\n🎉 Processamento batch completo. Relatório salvo em:', reportFile);
        
        // Ativar ciclo automático se houver falhas nos logs
        if (isBatchMode && !isRetryMode) {
            await executeCyclicRecovery();
        }
    } catch (error) {
        console.error('Erro durante a execução:', error);
        fs.appendFileSync(reportFile, `Erro durante a execução: ${error.message}\n`);
    }
}

downloadManga();
