import { Pages, Manga, Chapter } from "../../base/entities";
import { WordPressMadara } from "../../generic/madara";
import { JSDOM } from 'jsdom';
import fs from 'fs';
import path from 'path';

export class ManhAstroProvider extends WordPressMadara {
    constructor() {
        super();
        this.url = 'https://manhastro.net';
        this.path = '/';
        
        // Seletores específicos do ManhAstro.net
        this.query_mangas = 'div.post-title h3 a, div.post-title h5 a';
        this.query_chapters = 'li.wp-manga-chapter > a[href*="capitulo"], .listing-chapters_wrap li a[href*="capitulo"]';
        this.query_pages = 'div.reading-content img[src], div.page-break img[src]';
        this.query_title_for_uri = 'head meta[property="og:title"]';
        this.query_placeholder = '[id^="manga-chapters-holder"][data-id]';
        
        // Timeout específico para este provedor
        this.timeout = 30000; // 30 segundos
    }

    async getPages(chapter, attemptNumber = 1) {
        const maxRetries = 3;
        try {
            console.log(`📖 [ManhAstro] Carregando páginas para ${chapter.name} (tentativa ${attemptNumber}/${maxRetries})`);
            
            const pageUrl = new URL(chapter.id[0], this.url).toString();
            
            // USAR FETCH DIRETO POR ENQUANTO (proxy está travando)
            console.log(`🔄 [ManhAstro] Usando fetch direto...`);
            
            const response = await this.http.getInstance().get(pageUrl, { 
                timeout: this.timeout 
            });
            const htmlContent = response.data;
            const usedProxy = false;
            
            // ESTRATÉGIA PARA MANHASTRO: Buscar array JavaScript de imagens
            console.log(`📖 Carregando páginas do capítulo...`);
            
            const foundImages = new Set();
            
            // 1. Buscar array "imageLinks" no JavaScript 
            const imageLinksMatch = htmlContent.match(/var\s+imageLinks\s*=\s*\[(.*?)\]/s);
            if (imageLinksMatch) {
                
                try {
                    // Extrair URLs do array (estão em base64)
                    const imageLinksStr = imageLinksMatch[1];
                    const base64URLs = imageLinksStr.match(/"([^"]+)"/g);
                    
                    if (base64URLs) {
                        base64URLs.forEach(base64Str => {
                            try {
                                const base64 = base64Str.replace(/"/g, '');
                                const decodedUrl = Buffer.from(base64, 'base64').toString('utf-8');
                                
                                // Aceitar qualquer URL de manhastro que pareça ser imagem
                                if ((decodedUrl.includes('manhastro.net') || decodedUrl.includes('manhastro.com')) && 
                                    (decodedUrl.match(/\.(avif|jpg|jpeg|png|webp|gif|bmp|tiff|svg)(\.|$)/i) || 
                                     decodedUrl.includes('/manga_') || 
                                     decodedUrl.includes('capitulo-'))) {
                                    // SUPORTE NATIVO AVIF: Priorizar formato AVIF se disponível
                                    const hasAvif = decodedUrl.match(/\.avif(\.|$)/i);
                                    if (hasAvif) {
                                        console.log(`🎯 [ManhAstro] Imagem AVIF detectada: ${decodedUrl.substring(0, 50)}...`);
                                    }
                                    foundImages.add(decodedUrl);
                                }
                            } catch (decodeError) {
                                // Ignorar erros de decode
                            }
                        });
                        
                    }
                } catch (parseError) {
                    console.log(`⚠️ Erro ao processar páginas: ${parseError.message}`);
                }
            }
            
            // 2. Fallback: padrões regex tradicionais
            if (foundImages.size === 0) {
                console.log(`🔍 Método alternativo: busca por padrões...`);
                
                const patterns = [
                    // PRIORIZAR AVIF: Colocar AVIF primeiro na busca
                    /https?:\/\/albums\.manhastro\.net\/[^"'\s]+\.avif/gi,
                    /https?:\/\/img\.manhastro\.net\/[^"'\s]+\.avif/gi,
                    /https?:\/\/albums\.manhastro\.net\/[^"'\s]+\.(webp|jpg|jpeg|png)/gi,
                    /https?:\/\/img\.manhastro\.net\/[^"'\s]+\.(webp|jpg|jpeg|png)/gi
                ];
                
                patterns.forEach(pattern => {
                    let match;
                    while ((match = pattern.exec(htmlContent)) !== null) {
                        const url = match[0];
                        if (!url.toLowerCase().includes('logo') && 
                            !url.toLowerCase().includes('capa.manhastro') &&
                            !url.includes('/wp-content/uploads/')) {
                            foundImages.add(url);
                        }
                    }
                });
            }
            
            if (foundImages.size > 0) {
                // Ordenar numericamente baseado no número da página no nome do arquivo
                const imageList = Array.from(foundImages).sort((a, b) => {
                    // Extrair número da página (formato: 001.jpg, 024.jpg, etc.)
                    const getPageNumber = (url) => {
                        const match = url.match(/\/(\d+)\.(?:jpg|jpeg|png|webp|avif|gif|bmp|tiff|svg)/i);
                        return match ? parseInt(match[1], 10) : 0;
                    };
                    
                    return getPageNumber(a) - getPageNumber(b);
                });
                
                console.log(`📋 Encontradas ${imageList.length} páginas`);
                
                // DESCOBERTA INTELIGENTE: Expandir sequência testando URLs incrementais
                const expandedImages = await this.expandImageSequence(imageList as string[], usedProxy);
                
                if (expandedImages.length > imageList.length) {
                    console.log(`🔍 Páginas adicionais encontradas: ${expandedImages.length} total`);
                }
                
                
                return new Pages(chapter.id, chapter.number, chapter.name, expandedImages);
            }
            
            // FALLBACK: Usar seletores específicos que funcionam
            console.log(`⚠️ [ManhAstro] Usando fallback com seletores específicos...`);
            
            const dom = new JSDOM(htmlContent);
            const document = dom.window.document;
            
            // Usar seletores específicos que descobrimos que funcionam
            const specificSelectors = [
                'div.reading-content img[src]',
                'div.page-break img[src]',
                'img.wp-manga-chapter-img[src]'
            ];
            
            const images = [];
            specificSelectors.forEach(selector => {
                const selectorImages = Array.from(document.querySelectorAll(selector))
                    .map(img => img.getAttribute('src'))
                    .filter(Boolean);
                images.push(...selectorImages);
            });
            
            // Filtrar e processar URLs com priorização AVIF
            const processedImages = images
                .filter(src => {
                    return src && 
                           src.length > 10 &&
                           src.match(/\.(jpg|jpeg|png|webp|avif)$/i) &&
                           !src.includes('data:image') &&
                           !src.toLowerCase().includes('logo') &&
                           !src.toLowerCase().includes('aviso') &&
                           !src.toLowerCase().includes('capa.manhastro') &&
                           !src.includes('/wp-content/uploads/'); // Exclui uploads (avisos/banners)
                })
                // SUPORTE NATIVO AVIF: Ordenar priorizando AVIF
                .sort((a, b) => {
                    const aIsAvif = a.match(/\.avif$/i);
                    const bIsAvif = b.match(/\.avif$/i);
                    if (aIsAvif && !bIsAvif) return -1;
                    if (!aIsAvif && bIsAvif) return 1;
                    return 0;
                })
                .map(src => {
                    if (src.startsWith('//')) return 'https:' + src;
                    if (src.startsWith('/')) return this.url + src;
                    return src;
                })
                .filter((src, index, array) => array.indexOf(src) === index); // Remove duplicatas

            console.log(`📖 Encontradas ${processedImages.length} páginas (método alternativo)`);
            
            // Se ainda não encontrou, tentar buscar no HTML bruto novamente com padrões mais amplos
            if (images.length === 0) {
                console.log(`🔍 Busca ampla no HTML...`);
                // SUPORTE NATIVO AVIF: Incluir AVIF na busca ampla
                const broadImagePattern = /https?:\/\/[^"'\s]+\.(avif|jpg|jpeg|png|webp)/gi;
                const foundUrls = new Set();
                
                let match;
                while ((match = broadImagePattern.exec(htmlContent)) !== null) {
                    const url = match[0];
                    if (!url.toLowerCase().includes('logo') && 
                        !url.toLowerCase().includes('aviso') &&
                        !url.toLowerCase().includes('spinner') &&
                        !url.toLowerCase().includes('loading')) {
                        foundUrls.add(url);
                    }
                }
                
                const broadImages = Array.from(foundUrls);
                console.log(`🎯 Busca ampla encontrou ${broadImages.length} imagens`);
                
                if (broadImages.length > 0) {
                    return new Pages(chapter.id, chapter.number, chapter.name, broadImages as string[]);
                }
            }
            
            if (processedImages.length === 0) {
                throw new Error(`Nenhuma página encontrada para o capítulo ${chapter.name}`);
            }

            return new Pages(chapter.id, chapter.number, chapter.name, processedImages);
            
        } catch (error) {
            // LOGGING DE ERROS DE PÁGINAS ESPECÍFICAS
            this.logPageError(chapter, error, attemptNumber);
            
            if (attemptNumber < maxRetries) {
                const delay = 2000 * attemptNumber; // Backoff exponencial
                console.log(`🔄 Tentativa ${attemptNumber + 1}/${maxRetries} em ${delay}ms...`);
                await new Promise(resolve => setTimeout(resolve, delay));
                return this.getPages(chapter, attemptNumber + 1);
            }
            
            throw error;
        }
    }

    // Expandir sequência de imagens testando URLs incrementalmente
    private async expandImageSequence(initialImages: string[], usedProxy: boolean): Promise<string[]> {
        console.log(`🔍 Verificando páginas adicionais...`);
        
        if (initialImages.length === 0) return [];
        
        // Analisar padrão das URLs iniciais
        const sampleUrl = initialImages[0];
        const urlPattern = sampleUrl.match(/^(https?:\/\/[^\/]+\/[^\/]+\/[^\/]+\/[^\/]+\/)(\d+)\.(\w+)$/);
        
        if (!urlPattern) {
            console.log(`⚠️ Padrão de URL não detectado, usando páginas encontradas`);
            return initialImages;
        }
        
        const [, baseUrl, , extension] = urlPattern;
        // Descobrir números já existentes
        const existingNumbers = new Set<number>();
        initialImages.forEach(url => {
            const match = url.match(/\/(\d+)\.\w+$/);
            if (match) {
                existingNumbers.add(parseInt(match[1]));
            }
        });
        
        const maxExisting = Math.max(...Array.from(existingNumbers));
        
        // Testar sequência expandida - MUITO mais agressivo 
        const maxToTest = Math.max(50, maxExisting + 30); // Garantir mínimo de 50 páginas testadas
        const foundUrls = new Set(initialImages);
        let consecutiveNotFound = 0;
        const maxConsecutiveNotFound = 10; // Mais tolerância a falhas
        
        
        for (let i = 1; i <= maxToTest; i++) {
            const testUrl = `${baseUrl}${i}.${extension}`;
            
            // Se já temos essa URL, apenas resetar contador
            if (foundUrls.has(testUrl)) {
                consecutiveNotFound = 0;
                continue;
            }
            
            try {
                // HEAD request rápido para testar existência
                const response = await this.http.getInstance().head(testUrl, { 
                    timeout: 2000,
                    validateStatus: (status) => status < 500 // Aceita 404, rejeita apenas erros de servidor
                });
                
                if (response.status === 200) {
                    foundUrls.add(testUrl);
                    consecutiveNotFound = 0;
                } else {
                    consecutiveNotFound++;
                }
                
            } catch (error) {
                consecutiveNotFound++;
            }
            
            // Parar se muitas páginas consecutivas não existem
            if (consecutiveNotFound >= maxConsecutiveNotFound) {
                break;
            }
            
            // Pequena pausa para não sobrecarregar
            if (i % 20 === 0) {
                await new Promise(resolve => setTimeout(resolve, 50));
            }
        }
        
        const finalImages = Array.from(foundUrls).sort((a, b) => {
            const numA = parseInt(a.match(/\/(\d+)\.\w+$/)?.[1] || '0');
            const numB = parseInt(b.match(/\/(\d+)\.\w+$/)?.[1] || '0');
            return numA - numB;
        });
        
        
        return finalImages;
    }

    // Override para buscar apenas capítulos visíveis (descoberta sob demanda)
    async getChapters(id: string) {
        try {
            console.log(`🔍 [ManhAstro] Buscando capítulos visíveis...`);
            
            // Obter apenas os capítulos visíveis na página
            const visibleChapters = await super.getChapters(id);
            const validVisible = visibleChapters.filter(chapter => {
                const number = chapter.number;
                return number && number.match(/cap[ií]tulo\s*\d+/i) && !number.includes('{') && !number.includes('css');
            });
            
            if (validVisible.length === 0) {
                console.log(`📚 [ManhAstro] Nenhum capítulo encontrado`);
                return [];
            }
            
            // Detectar padrões decimais para uso posterior
            const decimalPatterns = this.detectDecimalPatterns(validVisible);
            if (decimalPatterns.length > 0) {
                console.log(`💡 [ManhAstro] Padrão decimal detectado: ${decimalPatterns.join(', ')}`);
            }
            
            const totalVisible = validVisible.length;
            const numbers = validVisible.map(ch => {
                const match = ch.number.match(/\d+\.?\d*/);
                return match ? parseFloat(match[0]) : 0;
            }).filter(n => n > 0);
            
            const minChapter = Math.min(...numbers);
            const maxChapter = Math.max(...numbers);
            
            console.log(`📚 [ManhAstro] Encontrados ${totalVisible} capítulos visíveis (${minChapter}-${maxChapter})`);
            
            // Armazenar metadados para uso no download
            (validVisible as any).metadata = {
                decimalPatterns,
                minVisible: minChapter,
                maxVisible: maxChapter,
                mangaId: id
            };
            
            return validVisible;
            
        } catch (error) {
            console.error(`❌ [ManhAstro] Erro ao buscar capítulos:`, error.message);
            throw error;
        }
    }

    // Detectar padrões decimais dos capítulos visíveis
    private detectDecimalPatterns(chapters: any[]): number[] {
        const patterns = new Set<number>();
        
        chapters.forEach(chapter => {
            const match = chapter.number.match(/\d+\.(\d+)/);
            if (match) {
                const decimal = parseFloat('0.' + match[1]);
                patterns.add(decimal);
            }
        });
        
        return Array.from(patterns).sort();
    }

    // Método para descoberta e download simultâneo
    async discoverAndDownloadChapters(mangaId: string, strategy: 'all' | 'range', range?: {start: number, end: number}, downloadCallback?: (chapter: Chapter) => Promise<void>): Promise<Chapter[]> {
        console.log(`🚀 [ManhAstro] Iniciando descoberta sequencial com download simultâneo...`);
        
        // Obter capítulos visíveis para encontrar ponto de partida
        const visibleChapters = await this.getChapters(mangaId);
        if (visibleChapters.length === 0) {
            console.log(`❌ [ManhAstro] Nenhum capítulo visível encontrado`);
            return [];
        }
        
        const foundChapters: Chapter[] = [];
        
        if (strategy === 'all') {
            // Descoberta completa com download simultâneo
            console.log(`🚀 [ManhAstro] Iniciando descoberta completa com navegação sequencial...`);
            
            if (downloadCallback) {
                // Usar método otimizado que baixa durante a descoberta
                return await this.discoverAllChaptersWithDownload(visibleChapters, downloadCallback);
            } else {
                // Descoberta sem download
                return await this.discoverAllChaptersSequentially(visibleChapters);
            }
        } else if (strategy === 'range' && range) {
            // Estratégia: Descobrir faixa específica via navegação
            return await this.discoverRangeSequentially(visibleChapters, range.start, range.end);
        }
        
        return foundChapters;
    }

    // Descobrir e baixar todos os capítulos simultaneamente (ORDEM DECRESCENTE)
    private async discoverAllChaptersWithDownload(visibleChapters: Chapter[], downloadCallback?: (chapter: Chapter) => Promise<void>): Promise<Chapter[]> {
        console.log(`🔍 [ManhAstro] Descobrindo e baixando capítulos em tempo real...`);
        
        const allChapters: Chapter[] = [];
        const processedUrls = new Set<string>();
        
        // Começar do último capítulo visível (mais recente)
        let currentChapter = visibleChapters[visibleChapters.length - 1];
        
        // Primeiro, verificar se há capítulos APÓS o último visível
        console.log(`🔍 [ManhAstro] Verificando se há capítulos após ${currentChapter.name}...`);
        const realLastChapter = await this.findRealLastChapter(currentChapter);
        
        // NOVA ESTRATÉGIA: Começar do último e ir para trás (ORDEM DECRESCENTE)
        currentChapter = realLastChapter;
        let chapterCount = 0;
        
        console.log(`🚀 [ManhAstro] Iniciando download decrescente a partir de: ${currentChapter.name}`);
        
        while (currentChapter && chapterCount < 100) { // Limite reduzido para segurança
            if (!processedUrls.has(currentChapter.id[0])) {
                allChapters.push(currentChapter);
                processedUrls.add(currentChapter.id[0]);
                chapterCount++;
                
                console.log(`📖 [${chapterCount}] Descoberto: ${currentChapter.name}`);
                
                // 🚀 BAIXAR IMEDIATAMENTE!
                if (downloadCallback) {
                    try {
                        await downloadCallback(currentChapter);
                        console.log(`✅ [${chapterCount}] Baixado: ${currentChapter.name}`);
                    } catch (error) {
                        console.error(`❌ [${chapterCount}] Erro ao baixar ${currentChapter.name}:`, error.message);
                    }
                }
            }
            
            // Debug: mostrar estado atual
            const currentNum = this.extractChapterNumber(currentChapter.id[0]);
            console.log(`🔎 [ManhAstro] Capítulo atual: ${currentNum}, buscando anterior...`);
            
            // Buscar capítulo anterior (navegação reversa)
            const prevChapter = await this.findPreviousChapter(currentChapter);
            if (!prevChapter) {
                console.log(`🏁 [ManhAstro] Chegou ao início - primeiro capítulo: ${currentChapter.name}`);
                break;
            }
            
            // Debug: mostrar navegação
            const prevNum = this.extractChapterNumber(prevChapter.id[0]);
            console.log(`🔎 [ManhAstro] Encontrado anterior: ${prevNum}`);
            
            // SIMPLIFICADO: Se existe botão prev, é navegação válida!
            // O site já garante que o prev é realmente anterior
            console.log(`✅ [ManhAstro] Navegação válida: ${currentNum} → ${prevNum}`);
            
            // Proteção apenas contra loops infinitos (mesma URL)
            if (processedUrls.has(prevChapter.id[0])) {
                console.log(`🔄 [ManhAstro] Capítulo ${prevNum} já processado - parando para evitar loop`);
                break;
            }
            
            currentChapter = prevChapter;
            
            // Pequena pausa para ser respeitoso
            await new Promise(resolve => setTimeout(resolve, 200));
        }
        
        console.log(`🎉 [ManhAstro] Descoberta e download concluídos: ${allChapters.length} capítulos`);
        return allChapters;
    }

    // Descobrir todos os capítulos seguindo navegação sequencial (método original mantido)
    private async discoverAllChaptersSequentially(visibleChapters: Chapter[]): Promise<Chapter[]> {
        console.log(`🔍 [ManhAstro] Descobrindo todos os capítulos via navegação sequencial...`);
        
        const allChapters: Chapter[] = [];
        const processedUrls = new Set<string>();
        
        // Começar do último capítulo visível (mais recente)
        let currentChapter = visibleChapters[visibleChapters.length - 1];
        
        // Primeiro, verificar se há capítulos APÓS o último visível
        console.log(`🔍 [ManhAstro] Verificando se há capítulos após ${currentChapter.name}...`);
        const realLastChapter = await this.findRealLastChapter(currentChapter);
        
        // Agora ir para o início navegando com "Previous" a partir do real último
        const firstChapter = await this.findFirstChapter(realLastChapter);
        if (!firstChapter) {
            console.log(`❌ [ManhAstro] Não foi possível encontrar o primeiro capítulo`);
            return visibleChapters; // Fallback para capítulos visíveis
        }
        
        // Navegar sequencialmente com "Next" a partir do primeiro
        currentChapter = firstChapter;
        let chapterCount = 0;
        
        while (currentChapter && chapterCount < 500) { // Limite de segurança
            if (!processedUrls.has(currentChapter.id[0])) {
                allChapters.push(currentChapter);
                processedUrls.add(currentChapter.id[0]);
                chapterCount++;
                
                if (chapterCount % 10 === 0) {
                    console.log(`📖 [ManhAstro] Descobertos ${chapterCount} capítulos...`);
                }
            }
            
            // Buscar próximo capítulo
            const nextChapter = await this.findNextChapter(currentChapter);
            if (!nextChapter) {
                console.log(`🏁 [ManhAstro] Chegou ao final - último capítulo: ${currentChapter.name}`);
                break;
            }
            
            currentChapter = nextChapter;
            
            // Pequena pausa para ser respeitoso
            await new Promise(resolve => setTimeout(resolve, 200));
        }
        
        console.log(`🎉 [ManhAstro] Descoberta sequencial concluída: ${allChapters.length} capítulos`);
        return allChapters;
    }

    // Descobrir faixa específica via navegação
    private async discoverRangeSequentially(visibleChapters: Chapter[], start: number, end: number): Promise<Chapter[]> {
        console.log(`🔍 [ManhAstro] Descobrindo capítulos ${start}-${end} via navegação...`);
        
        // Para faixa específica, ainda é mais eficiente usar descoberta direta
        // mas com lógica de navegação para validar continuidade
        const foundChapters: Chapter[] = [];
        
        for (let i = start; i <= end; i++) {
            const chapter = await this.testChapterExistsFast(visibleChapters[0].id[0].replace(/capitulo-\d+.*$/, ''), i, `Capítulo ${i}`);
            if (chapter) {
                foundChapters.push(chapter);
                console.log(`✅ Capítulo ${i} encontrado`);
            }
            
            // Pausa entre requisições
            if (i % 5 === 0) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }
        }
        
        return foundChapters;
    }

    // Encontrar o REAL último capítulo testando se há "Next" + busca direta
    private async findRealLastChapter(startChapter: Chapter): Promise<Chapter> {
        console.log(`➡️ [ManhAstro] Testando se há capítulos após ${startChapter.name}...`);
        
        let currentChapter = startChapter;
        let iterationCount = 0;
        const maxIterations = 30; // Aumentado para buscar mais capítulos
        const visitedUrls = new Set<string>();
        
        // Primeira fase: Navegação via botões Next
        while (iterationCount < maxIterations) {
            // Detectar loops infinitos
            if (visitedUrls.has(currentChapter.id[0])) {
                console.log(`🔄 [ManhAstro] Loop infinito detectado, parando em: ${currentChapter.name}`);
                break;
            }
            visitedUrls.add(currentChapter.id[0]);
            
            const nextChapter = await this.findNextChapter(currentChapter);
            if (!nextChapter) {
                console.log(`🏁 [ManhAstro] Fim da navegação encontrado: ${currentChapter.name}`);
                break;
            }
            
            // Verificar se está voltando em vez de avançar
            const currentNum = this.extractChapterNumber(currentChapter.id[0]);
            const nextNum = this.extractChapterNumber(nextChapter.id[0]);
            
            if (nextNum <= currentNum) {
                console.log(`🏁 [ManhAstro] Capítulo "Next" (${nextNum}) é menor/igual ao atual (${currentNum}) - fim navegação`);
                break;
            }
            
            console.log(`✅ [${iterationCount + 1}] ${currentChapter.name} → ${nextChapter.name}`);
            currentChapter = nextChapter;
            iterationCount++;
            
            await new Promise(resolve => setTimeout(resolve, 50));
        }
        
        // Segunda fase: Teste direto de capítulos posteriores (VALIDAÇÃO RIGOROSA)
        const lastFound = this.extractChapterNumber(currentChapter.id[0]);
        console.log(`🔍 [ManhAstro] Testando capítulos após ${lastFound} diretamente...`);
        
        const baseUrl = currentChapter.id[0].replace(/capitulo-\d+.*$/, '');
        let testChapter = lastFound + 1;
        let consecutiveNotFound = 0;
        
        while (consecutiveNotFound < 3 && testChapter <= lastFound + 5) { // Reduzido drasticamente
            const testUrl = `${baseUrl}capitulo-${testChapter}/`;
            try {
                // VALIDAÇÃO RIGOROSA: HEAD + conteúdo real
                const headResponse = await this.http.getInstance().head(testUrl, { timeout: 2000 });
                if (headResponse.status === 200) {
                    // Verificar se o capítulo tem conteúdo real
                    const contentValid = await this.validateChapterContent(testUrl);
                    if (contentValid) {
                        console.log(`🎯 [ManhAstro] Capítulo ${testChapter} encontrado e validado!`);
                        currentChapter = new Chapter([testUrl], `Capítulo ${testChapter}`, currentChapter.name.split(' - ')[0]);
                        consecutiveNotFound = 0;
                    } else {
                        console.log(`⚠️ [ManhAstro] Capítulo ${testChapter} existe mas sem conteúdo válido`);
                        consecutiveNotFound++;
                    }
                } else {
                    consecutiveNotFound++;
                }
            } catch {
                consecutiveNotFound++;
            }
            testChapter++;
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        
        console.log(`🏁 [ManhAstro] Real último capítulo encontrado: ${currentChapter.name}`);
        return currentChapter;
    }

    // Encontrar o primeiro capítulo via navegação + busca direta agressiva
    private async findFirstChapter(startChapter: Chapter): Promise<Chapter | null> {
        console.log(`⏪ [ManhAstro] Buscando primeiro capítulo a partir de: ${startChapter.name}`);
        
        let currentChapter = startChapter;
        let iterationCount = 0;
        const maxIterations = 30; // Aumentado para buscar mais
        const visitedUrls = new Set<string>();
        
        // Primeira fase: Navegação via botões Previous
        while (iterationCount < maxIterations) {
            // Detectar loops infinitos
            if (visitedUrls.has(currentChapter.id[0])) {
                console.log(`🔄 [ManhAstro] Loop infinito detectado, parando em: ${currentChapter.name}`);
                break;
            }
            visitedUrls.add(currentChapter.id[0]);
            
            const prevChapter = await this.findPreviousChapter(currentChapter);
            if (!prevChapter) {
                console.log(`🏁 [ManhAstro] Fim da navegação encontrado: ${currentChapter.name}`);
                break;
            }
            
            // Verificar se está avançando em vez de voltar
            const currentNum = this.extractChapterNumber(currentChapter.id[0]);
            const prevNum = this.extractChapterNumber(prevChapter.id[0]);
            
            if (prevNum >= currentNum) {
                console.log(`🔄 [ManhAstro] Capítulo "Prev" (${prevNum}) é maior/igual ao atual (${currentNum}) - fim navegação`);
                break;
            }
            
            console.log(`⏪ [${iterationCount + 1}] ${currentChapter.name} → ${prevChapter.name}`);
            currentChapter = prevChapter;
            iterationCount++;
            
            await new Promise(resolve => setTimeout(resolve, 50));
        }
        
        // Segunda fase: Busca direta de capítulos anteriores
        const firstFound = this.extractChapterNumber(currentChapter.id[0]);
        console.log(`🔍 [ManhAstro] Testando capítulos antes de ${firstFound} diretamente...`);
        
        const baseUrl = currentChapter.id[0].replace(/capitulo-\d+.*$/, '');
        
        // Testar capítulos comuns: 1, 0, 0.5, 2, 3...
        const testNumbers = [1, 0, 0.5, 2, 3, 4, 5];
        
        for (const testNum of testNumbers) {
            if (testNum >= firstFound) continue; // Só testar números menores
            
            const testUrl = testNum === Math.floor(testNum) ? 
                `${baseUrl}capitulo-${testNum}/` : 
                `${baseUrl}capitulo-${testNum.toString().replace('.', '-')}/`;
                
            try {
                const response = await this.http.getInstance().head(testUrl, { timeout: 3000 });
                if (response.status === 200) {
                    console.log(`🎯 [ManhAstro] Capítulo ${testNum} encontrado via busca direta!`);
                    currentChapter = new Chapter([testUrl], `Capítulo ${testNum}`, currentChapter.name.split(' - ')[0]);
                    break; // Usar o primeiro encontrado (ordem crescente)
                }
            } catch {
                // Continuar testando
            }
            await new Promise(resolve => setTimeout(resolve, 50));
        }
        
        console.log(`🎯 [ManhAstro] Primeiro capítulo determinado: ${currentChapter.name}`);
        return currentChapter;
    }

    // Buscar capítulo anterior via botão "Previous"
    private async findPreviousChapter(chapter: Chapter): Promise<Chapter | null> {
        try {
            const response = await this.http.getInstance().get(chapter.id[0], { timeout: this.timeout });
            const dom = new JSDOM(response.data);
            const document = dom.window.document;
            
            // MÚTIPLOS SELETORES PARA NAVEGAÇÃO PREV
            const prevSelectors = [
                'a.btn.prev_page',
                'a[rel="prev"]',
                '.wp-manga-nav a[href*="capitulo"]:first-child',
                '.nav-previous a',
                '.prev-chapter a',
                'a:contains("Anterior")',
                'a:contains("Previous")',
                '.nav-links a[href*="capitulo"]:first-child'
            ];
            
            let prevLink: HTMLAnchorElement | null = null;
            
            for (const selector of prevSelectors) {
                if (selector.includes(':contains')) {
                    // Buscar manualmente por conteúdo de texto
                    const links = document.querySelectorAll('a[href*="capitulo"]') as NodeListOf<HTMLAnchorElement>;
                    for (const link of links) {
                        const text = (link.textContent || '').toLowerCase();
                        if ((text.includes('anterior') || text.includes('previous') || text.includes('prev')) && 
                            link.href !== chapter.id[0]) {
                            prevLink = link;
                            break;
                        }
                    }
                } else {
                    prevLink = document.querySelector(selector) as HTMLAnchorElement;
                }
                
                if (prevLink && prevLink.href && prevLink.href !== chapter.id[0]) {
                    const prevUrl = new URL(prevLink.href, this.url).toString();
                    const prevName = this.extractChapterName(prevLink.textContent || '', prevUrl);
                    console.log(`⏪ [ManhAstro] Prev encontrado: ${prevName} (${prevUrl})`);
                    return new Chapter([prevUrl], prevName, chapter.name.split(' - ')[0]);
                }
            }
            
            console.log(`⚠️ [ManhAstro] Nenhum botão Previous encontrado para: ${chapter.name}`);
            
            // DEBUG: Mostrar todos os links disponíveis para diagnóstico
            const allLinks = document.querySelectorAll('a[href*="capitulo"]') as NodeListOf<HTMLAnchorElement>;
            console.log(`🔍 [ManhAstro] Links de capítulos disponíveis (${allLinks.length}):`);
            Array.from(allLinks).slice(0, 5).forEach((link, index) => {
                console.log(`  ${index + 1}. "${(link.textContent || '').trim().substring(0, 30)}..." -> ${link.href}`);
            });
            
            return null;
        } catch (error) {
            console.log(`❌ [ManhAstro] Erro ao buscar Previous: ${error.message}`);
            return null;
        }
    }

    // Buscar próximo capítulo via botão "Next"
    private async findNextChapter(chapter: Chapter): Promise<Chapter | null> {
        try {
            const response = await this.http.getInstance().get(chapter.id[0], { timeout: this.timeout });
            const dom = new JSDOM(response.data);
            const document = dom.window.document;
            
            // MÚTIPLOS SELETORES PARA NAVEGAÇÃO NEXT
            const nextSelectors = [
                'a.btn.next_page',
                'a[rel="next"]',
                '.wp-manga-nav a[href*="capitulo"]:last-child',
                '.nav-next a',
                '.next-chapter a',
                'a:contains("Próximo")',
                'a:contains("Next")',
                '.nav-links a[href*="capitulo"]:last-child'
            ];
            
            let nextLink: HTMLAnchorElement | null = null;
            
            for (const selector of nextSelectors) {
                if (selector.includes(':contains')) {
                    // Buscar manualmente por conteúdo de texto
                    const links = document.querySelectorAll('a[href*="capitulo"]') as NodeListOf<HTMLAnchorElement>;
                    for (const link of links) {
                        const text = (link.textContent || '').toLowerCase();
                        if ((text.includes('próximo') || text.includes('next')) && 
                            link.href !== chapter.id[0]) {
                            nextLink = link;
                            break;
                        }
                    }
                } else {
                    nextLink = document.querySelector(selector) as HTMLAnchorElement;
                }
                
                if (nextLink && nextLink.href && nextLink.href !== chapter.id[0]) {
                    const nextUrl = new URL(nextLink.href, this.url).toString();
                    const nextName = this.extractChapterName(nextLink.textContent || '', nextUrl);
                    console.log(`➡️ [ManhAstro] Next encontrado: ${nextName} (${nextUrl})`);
                    return new Chapter([nextUrl], nextName, chapter.name.split(' - ')[0]);
                }
            }
            
            console.log(`⚠️ [ManhAstro] Nenhum botão Next encontrado para: ${chapter.name}`);
            
            // DEBUG: Mostrar todos os links disponíveis para diagnóstico
            const allLinks = document.querySelectorAll('a[href*="capitulo"]') as NodeListOf<HTMLAnchorElement>;
            console.log(`🔍 [ManhAstro] Links de capítulos disponíveis (${allLinks.length}):`);
            Array.from(allLinks).slice(0, 5).forEach((link, index) => {
                console.log(`  ${index + 1}. "${(link.textContent || '').trim().substring(0, 30)}..." -> ${link.href}`);
            });
            
            return null;
        } catch (error) {
            console.log(`❌ [ManhAstro] Erro ao buscar Next: ${error.message}`);
            return null;
        }
    }

    // Extrair número do capítulo da URL
    private extractChapterNumber(url: string): number {
        const match = url.match(/capitulo-(\d+(?:\.\d+)?)/);
        return match ? parseFloat(match[1]) : 0;
    }

    // Extrair nome do capítulo de forma inteligente
    private extractChapterName(text: string, url: string): string {
        // SEMPRE extrair da URL primeiro (mais confiável)
        const urlMatch = url.match(/capitulo-(\d+(?:\.\d+)?)/);
        if (urlMatch) {
            const chapterNum = urlMatch[1];
            return `Capítulo ${chapterNum}`;
        }
        
        // Fallback: tentar extrair do texto do link
        if (text && text.trim()) {
            let cleanText = text.trim().replace(/\s+/g, ' ');
            
            // Limpar texto extra do ManhAstro (mesmo processo do manga)
            cleanText = cleanText
                .replace(/^Ler\s+/i, '')  // Remove "Ler " do início
                .replace(/\s+Manga\s+Online.*$/i, '')  // Remove " Manga Online..." do final
                .replace(/\s*–\s*Manhastro.*$/i, '')  // Remove "– Manhastro!!" do final
                .replace(/\s*-\s*Manhastro.*$/i, '')   // Remove "- Manhastro!!" do final
                .trim();
            
            if (cleanText.match(/cap[íi]tulo\s*\d+/i)) {
                return cleanText;
            }
        }
        
        // Fallback: extrair da URL
        const chapterMatch = url.match(/capitulo-(\d+\.?\d*)/);
        if (chapterMatch) {
            return `Capítulo ${chapterMatch[1]}`;
        }
        
        return 'Capítulo Desconhecido';
    }

    // Analisar metadados da página para heurísticas
    private async analyzePageMetadata(id: string): Promise<void> {
        try {
            const response = await this.http.getInstance().get(id, { timeout: this.timeout });
            const dom = new JSDOM(response.data);
            const document = dom.window.document;
            
            // Buscar informações estruturadas
            const jsonLd = document.querySelector('script[type="application/ld+json"]');
            if (jsonLd) {
                try {
                    const data = JSON.parse(jsonLd.textContent || '');
                    console.log(`🔍 [ManhAstro] Metadados estruturados encontrados`);
                } catch (e) {
                    // Ignore JSON parse errors
                }
            }
            
            // Buscar indicadores de total de capítulos no HTML
            const bodyText = document.body.textContent || '';
            const totalMatches = bodyText.match(/(\d+)\s*cap[íi]tulos?/i) || 
                               bodyText.match(/total[^\d]*(\d+)/i) ||
                               bodyText.match(/(\d+)\s*chapters?/i);
            
            if (totalMatches) {
                console.log(`💡 [ManhAstro] Possível total de capítulos: ${totalMatches[1]}`);
            }
            
        } catch (error) {
            // Metadados não críticos, continuar sem eles
        }
    }

    // Detectar capítulo inicial usando heurísticas inteligentes
    private async detectStartChapter(id: string, minVisible: number): Promise<number> {
        // Testar possibilidades comuns de início
        const possibleStarts = [0, 1, 0.5]; // Prólogo/Capítulo 0, Capítulo 1, Capítulo 0.5
        
        for (const start of possibleStarts) {
            try {
                const testUrl = start === Math.floor(start) ? 
                    `${id}capitulo-${start}/` : 
                    `${id}capitulo-${start.toString().replace('.', '-')}/`;
                    
                const response = await this.http.getInstance().head(testUrl, { timeout: 3000 });
                if (response.status === 200) {
                    return start;
                }
            } catch (error) {
                continue;
            }
        }
        
        // Se nenhum padrão comum funcionar, assumir 1
        return 1;
    }

    // Buscar capítulos em uma faixa específica
    private async findChaptersInRange(id: string, start: number, end: number, baseTitle: string): Promise<Chapter[]> {
        const foundChapters: Chapter[] = [];
        const concurrency = 5; // Limite de requisições simultâneas
        
        // Dividir em lotes para evitar sobrecarga
        for (let i = start; i <= end; i += concurrency) {
            const batch = [];
            const maxInBatch = Math.min(i + concurrency - 1, end);
            
            for (let j = i; j <= maxInBatch; j++) {
                batch.push(this.testChapterExists(id, j, baseTitle));
            }
            
            const results = await Promise.allSettled(batch);
            results.forEach((result) => {
                if (result.status === 'fulfilled' && result.value) {
                    foundChapters.push(result.value);
                }
            });
            
            // Pequena pausa entre lotes para ser respeitoso
            if (i + concurrency <= end) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }
        }
        
        return foundChapters;
    }

    // Buscar capítulos após o último conhecido (rápido e inteligente)
    private async findChaptersAfter(id: string, lastKnown: number, baseTitle: string): Promise<Chapter[]> {
        const foundChapters: Chapter[] = [];
        let current = lastKnown + 1;
        let consecutiveNotFound = 0;
        const maxConsecutiveNotFound = 3; // Reduzido para 3
        const maxChaptersToTest = 20; // Reduzido para 20
        
        console.log(`🔍 [ManhAstro] Testando capítulos posteriores (limite: ${maxChaptersToTest})...`);
        
        while (consecutiveNotFound < maxConsecutiveNotFound && (current - lastKnown) <= maxChaptersToTest) {
            try {
                // Apenas HEAD request rápido - sem validação completa
                const chapter = await this.testChapterExistsFast(id, current, baseTitle);
                if (chapter) {
                    foundChapters.push(chapter);
                    consecutiveNotFound = 0;
                } else {
                    consecutiveNotFound++;
                }
            } catch (error) {
                consecutiveNotFound++;
            }
            
            current++;
        }
        
        if (consecutiveNotFound >= maxConsecutiveNotFound) {
            console.log(`🛑 [ManhAstro] Parado após ${maxConsecutiveNotFound} falhas consecutivas`);
        }
        
        return foundChapters;
    }

    // Testar se um capítulo específico existe (verificação rigorosa)
    private async testChapterExists(id: string, chapterNum: number, baseTitle: string): Promise<Chapter | null> {
        try {
            const testUrl = chapterNum === Math.floor(chapterNum) ? 
                `${id}capitulo-${chapterNum}/` : 
                `${id}capitulo-${chapterNum.toString().replace('.', '-')}/`;
                
            // Primeiro teste: HEAD request
            const headResponse = await this.http.getInstance().head(testUrl, { timeout: 3000 });
            
            if (headResponse.status !== 200) {
                return null;
            }
            
            // Segundo teste: GET request para verificar conteúdo real
            const getResponse = await this.http.getInstance().get(testUrl, { timeout: 5000 });
            const dom = new JSDOM(getResponse.data);
            const document = dom.window.document;
            
            // Verificar se existem imagens de páginas reais
            const images = document.querySelectorAll('div.reading-content img[src], div.page-break img[src]');
            
            // Verificar se não é uma página de erro ou redirecionamento
            const title = document.title?.toLowerCase() || '';
            const bodyText = document.body?.textContent?.toLowerCase() || '';
            
            // Rejeitar se:
            if (images.length === 0 || // Sem imagens
                title.includes('erro') || title.includes('error') || title.includes('404') ||
                bodyText.includes('não encontrado') || bodyText.includes('not found') ||
                bodyText.includes('página não existe') || bodyText.includes('page not found')) {
                return null;
            }
            
            // Log silencioso - só mostrar erros importantes
            return new Chapter(
                [testUrl],
                `Capitulo ${chapterNum}`,
                baseTitle
            );
            
        } catch (error) {
            // Capítulo não existe ou erro de rede
            return null;
        }
    }

    // Teste rápido - apenas HEAD request (para busca posterior)
    private async testChapterExistsFast(id: string, chapterNum: number, baseTitle: string): Promise<Chapter | null> {
        try {
            const testUrl = chapterNum === Math.floor(chapterNum) ? 
                `${id}capitulo-${chapterNum}/` : 
                `${id}capitulo-${chapterNum.toString().replace('.', '-')}/`;
                
            const response = await this.http.getInstance().head(testUrl, { timeout: 2000 });
            
            if (response.status === 200) {
                return new Chapter(
                    [testUrl],
                    `Capitulo ${chapterNum}`,
                    baseTitle
                );
            }
        } catch (error) {
            // Capítulo não existe
        }
        
        return null;
    }

    // Validar se capítulo tem conteúdo real (imagens)
    private async validateChapterContent(chapterUrl: string): Promise<boolean> {
        try {
            const response = await this.http.getInstance().get(chapterUrl, { timeout: 5000 });
            const htmlContent = response.data;
            
            // Verificar se há JavaScript com imageLinks (padrão do ManhAstro)
            const hasImageLinks = htmlContent.includes('var imageLinks');
            if (hasImageLinks) {
                const imageLinksMatch = htmlContent.match(/var\s+imageLinks\s*=\s*\[(.*?)\]/s);
                if (imageLinksMatch && imageLinksMatch[1].trim().length > 10) {
                    return true; // Tem array de imagens
                }
            }
            
            // Fallback: buscar por imagens diretas no HTML
            const dom = new JSDOM(htmlContent);
            const document = dom.window.document;
            const images = document.querySelectorAll('div.reading-content img[src], div.page-break img[src]');
            
            // Considerar válido apenas se tiver pelo menos 3 imagens
            return images.length >= 3;
            
        } catch (error) {
            return false;
        }
    }

    // Override para customizar busca de manga se necessário
    async getManga(link: string) {
        try {
            console.log(`🎯 [ManhAstro] Buscando manga: ${link}`);
            
            const response = await this.http.getInstance().get(link, { timeout: this.timeout });
            const dom = new JSDOM(response.data);
            const document = dom.window.document;
            
            // Remover todos os elementos de estilo para evitar CSS no output
            const styleElements = document.querySelectorAll('style, script');
            styleElements.forEach(el => el.remove());
            
            const element = document.querySelector(this.query_title_for_uri);
            let title = element?.getAttribute('content')?.trim() || element?.textContent?.trim() || '';
            
            // Limpar o título removendo texto extra do ManhAstro
            if (title) {
                // Remover padrões comuns: "Ler [Nome] Manga Online – Manhastro!!"
                title = title
                    .replace(/^Ler\s+/i, '')  // Remove "Ler " do início
                    .replace(/\s+Manga\s+Online.*$/i, '')  // Remove " Manga Online..." do final
                    .replace(/\s*–\s*Manhastro.*$/i, '')  // Remove "– Manhastro!!" do final
                    .replace(/\s*-\s*Manhastro.*$/i, '')   // Remove "- Manhastro!!" do final
                    .trim();
            }
            
            console.log(`📖 [ManhAstro] Manga encontrado: ${title}`);
            return new Manga(link, title);
        } catch (error) {
            console.error(`❌ [ManhAstro] Erro ao buscar manga:`, error.message);
            throw error;
        }
    }

    // LOGGING DE ERROS DE PÁGINAS ESPECÍFICAS
    private logPageError(chapter: Chapter, error: any, attemptNumber: number): void {
        const timestamp = new Date().toISOString();
        const chapterNumber = this.extractChapterNumber(chapter.id[0]);
        
        const errorData = {
            timestamp,
            chapterUrl: chapter.id[0],
            chapterNumber,
            chapterName: chapter.name,
            attemptNumber,
            errorType: error.constructor.name,
            errorMessage: error.message,
            errorStack: error.stack?.split('\n').slice(0, 3).join('\n'), // Apenas primeiras 3 linhas
            httpStatus: error.response?.status,
            httpStatusText: error.response?.statusText
        };
        
        // Log estruturado no console
        console.error(`❌ [ManhAstro] Erro página específica:`, {
            capítulo: chapterNumber,
            tentativa: attemptNumber,
            erro: error.message
        });
        
        // Salvar em arquivo de log específico
        const logDir = path.join(process.cwd(), 'logs', 'manhastro_errors');
        if (!fs.existsSync(logDir)) {
            fs.mkdirSync(logDir, { recursive: true });
        }
        
        const logFile = path.join(logDir, 'page_errors.jsonl');
        const logLine = JSON.stringify(errorData) + '\n';
        
        try {
            fs.appendFileSync(logFile, logLine);
        } catch (logError) {
            console.warn(`⚠️ [ManhAstro] Falha ao salvar log de erro:`, logError.message);
        }
    }

    // LOGGING DE ERROS DE IMAGENS ESPECÍFICAS (para uso no consumer)
    public logImageError(chapterNumber: string, pageNumber: number, imageUrl: string, error: any): void {
        const timestamp = new Date().toISOString();
        
        const errorData = {
            timestamp,
            chapterNumber,
            pageNumber,
            imageUrl: imageUrl.substring(0, 100) + '...', // Truncar URL longa
            errorType: error.constructor.name,
            errorMessage: error.message,
            httpStatus: error.response?.status,
            httpStatusText: error.response?.statusText
        };
        
        // Log estruturado no console
        console.error(`❌ [ManhAstro] Erro imagem específica:`, {
            capítulo: chapterNumber,
            página: pageNumber,
            erro: error.message
        });
        
        // Salvar em arquivo de log específico
        const logDir = path.join(process.cwd(), 'logs', 'manhastro_errors');
        if (!fs.existsSync(logDir)) {
            fs.mkdirSync(logDir, { recursive: true });
        }
        
        const logFile = path.join(logDir, 'image_errors.jsonl');
        const logLine = JSON.stringify(errorData) + '\n';
        
        try {
            fs.appendFileSync(logFile, logLine);
        } catch (logError) {
            console.warn(`⚠️ [ManhAstro] Falha ao salvar log de erro de imagem:`, logError.message);
        }
    }
}