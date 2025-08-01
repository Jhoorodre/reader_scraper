import { Pages, Manga, Chapter } from "../../base/entities";
import { WordPressMadara } from "../../generic/madara";
import { JSDOM } from 'jsdom';

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
        try {
            console.log(`📖 [ManhAstro] Carregando páginas para ${chapter.name} (tentativa ${attemptNumber})`);
            
            const pageUrl = new URL(chapter.id, this.url).toString();
            const response = await this.http.getInstance().get(pageUrl, { 
                timeout: this.timeout 
            });
            
            const htmlContent = response.data;
            
            // ESTRATÉGIA SIMPLES E DIRETA: Buscar padrão img.manhastro.net no HTML bruto
            const mangaImagePattern = /https?:\/\/img\.manhastro\.net\/manga_[^\/]+\/capitulo-[^\/]+\/(\d+)\.(webp|jpg|jpeg|png)/gi;
            const foundImages = new Set();
            
            let match;
            while ((match = mangaImagePattern.exec(htmlContent)) !== null) {
                const url = match[0];
                const pageNumber = parseInt(match[1]);
                
                if (pageNumber && pageNumber > 0) {
                    foundImages.add(url);
                }
            }
            
            console.log(`🎯 [ManhAstro] Encontradas ${foundImages.size} páginas img.manhastro.net`);
            
            // Se encontrou páginas do manhastro, expandir a sequência
            if (foundImages.size > 0) {
                const firstImage = Array.from(foundImages)[0];
                const basePattern = firstImage.replace(/\/\d+\.(webp|jpg|jpeg|png)$/i, '/');
                
                console.log(`🔍 [ManhAstro] Padrão base: ${basePattern}`);
                
                // Descobrir o número máximo de páginas testando
                let maxPage = 0;
                Array.from(foundImages).forEach(url => {
                    const pageMatch = url.match(/\/(\d+)\.(webp|jpg|jpeg|png)$/i);
                    if (pageMatch) {
                        const num = parseInt(pageMatch[1]);
                        if (num > maxPage) maxPage = num;
                    }
                });
                
                console.log(`📊 [ManhAstro] Página máxima encontrada: ${maxPage}`);
                
                // Gerar sequência completa de 1 até max+5 (margem de segurança)
                const allPages = [];
                for (let i = 1; i <= Math.max(maxPage + 5, 30); i++) {
                    allPages.push(`${basePattern}${i}.webp`);
                }
                
                console.log(`📈 [ManhAstro] Gerada sequência de ${allPages.length} páginas`);
                
                // Retornar páginas em ordem
                return new Pages(chapter.id, chapter.number, chapter.name, allPages);
            }
            
            // FALLBACK: Se não encontrou img.manhastro.net, usar método original simples
            console.log(`⚠️ [ManhAstro] Não encontrou img.manhastro.net, usando fallback...`);
            
            const dom = new JSDOM(response.data);
            const document = dom.window.document;
            
            const images = Array.from(document.querySelectorAll('img[src], img[data-src]'))
                .map(img => {
                    return img.getAttribute('src') || 
                           img.getAttribute('data-src') || 
                           img.getAttribute('data-lazy-src') ||
                           img.getAttribute('data-original');
                })
                .filter(Boolean)
                .filter(src => {
                    return src && 
                           src.match(/\.(jpg|jpeg|png|webp)$/i) &&
                           !src.includes('data:image') &&
                           !src.toLowerCase().includes('logo') &&
                           !src.toLowerCase().includes('aviso');
                })
                .map(src => {
                    if (src.startsWith('//')) return 'https:' + src;
                    if (src.startsWith('/')) return this.url + src;
                    return src;
                });

            console.log(`📖 [ManhAstro] Fallback encontrou ${images.length} páginas`);
            
            if (images.length === 0) {
                throw new Error(`Nenhuma página encontrada para o capítulo ${chapter.name}`);
            }

            return new Pages(chapter.id, chapter.number, chapter.name, images);
            
        } catch (error) {
            console.error(`❌ [ManhAstro] Erro ao obter páginas do capítulo ${chapter.name}:`, error.message);
            
            if (attemptNumber < 3) {
                console.log(`🔄 [ManhAstro] Tentativa ${attemptNumber + 1} para ${chapter.name}`);
                await new Promise(resolve => setTimeout(resolve, 2000 * attemptNumber));
                return this.getPages(chapter, attemptNumber + 1);
            }
            
            throw error;
        }
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
            // Estratégia: Descobrir e baixar TODOS os capítulos via navegação
            return await this.discoverAllChaptersWithDownload(visibleChapters, downloadCallback);
        } else if (strategy === 'range' && range) {
            // Estratégia: Descobrir faixa específica via navegação
            return await this.discoverRangeSequentially(visibleChapters, range.start, range.end);
        }
        
        return foundChapters;
    }

    // Descobrir e baixar todos os capítulos simultaneamente
    private async discoverAllChaptersWithDownload(visibleChapters: Chapter[], downloadCallback?: (chapter: Chapter) => Promise<void>): Promise<Chapter[]> {
        console.log(`🔍 [ManhAstro] Descobrindo e baixando capítulos em tempo real...`);
        
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
        
        // Navegar sequencialmente com "Next" a partir do primeiro E BAIXAR CADA UM
        currentChapter = firstChapter;
        let chapterCount = 0;
        
        console.log(`🚀 [ManhAstro] Iniciando download sequencial a partir de: ${currentChapter.name}`);
        
        while (currentChapter && chapterCount < 500) { // Limite de segurança
            if (!processedUrls.has(currentChapter.id)) {
                allChapters.push(currentChapter);
                processedUrls.add(currentChapter.id);
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
            if (!processedUrls.has(currentChapter.id)) {
                allChapters.push(currentChapter);
                processedUrls.add(currentChapter.id);
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
            const chapter = await this.testChapterExistsFast(visibleChapters[0].id.replace(/capitulo-\d+.*$/, ''), i, `Capítulo ${i}`);
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

    // Encontrar o REAL último capítulo testando se há "Next"
    private async findRealLastChapter(startChapter: Chapter): Promise<Chapter> {
        console.log(`➡️ [ManhAstro] Testando se há capítulos após ${startChapter.name}...`);
        
        let currentChapter = startChapter;
        let iterationCount = 0;
        const maxIterations = 50; // Limite menor para busca forward
        
        while (iterationCount < maxIterations) {
            const nextChapter = await this.findNextChapter(currentChapter);
            if (!nextChapter) {
                console.log(`🏁 [ManhAstro] Real último capítulo encontrado: ${currentChapter.name}`);
                return currentChapter;
            }
            
            // Verificar se realmente avançou (evitar loop infinito)
            if (nextChapter.id === currentChapter.id) {
                console.log(`🔄 [ManhAstro] Detectado loop infinito, parando em: ${currentChapter.name}`);
                return currentChapter;
            }
            
            // Verificar se está voltando em vez de avançar (detectar se Next está errado)
            const currentNum = this.extractChapterNumber(currentChapter.id);
            const nextNum = this.extractChapterNumber(nextChapter.id);
            
            if (nextNum <= currentNum) {
                console.log(`🏁 [ManhAstro] Capítulo "Next" (${nextNum}) é menor/igual ao atual (${currentNum}) - chegou ao final`);
                return currentChapter;
            }
            
            console.log(`✅ [ManhAstro] Encontrado capítulo posterior: ${nextChapter.name}`);
            console.log(`   URL atual: ${currentChapter.id}`);
            console.log(`   URL próximo: ${nextChapter.id}`);
            currentChapter = nextChapter;
            iterationCount++;
            
            // Pausa para ser respeitoso
            await new Promise(resolve => setTimeout(resolve, 200));
        }
        
        console.log(`⚠️ [ManhAstro] Limite atingido na busca forward, usando: ${currentChapter.name}`);
        return currentChapter;
    }

    // Encontrar o primeiro capítulo navegando com "Previous"
    private async findFirstChapter(startChapter: Chapter): Promise<Chapter | null> {
        console.log(`⏪ [ManhAstro] Buscando primeiro capítulo a partir de: ${startChapter.name}`);
        
        let currentChapter = startChapter;
        let iterationCount = 0;
        const maxIterations = 100; // Limite de segurança
        
        while (iterationCount < maxIterations) {
            const prevChapter = await this.findPreviousChapter(currentChapter);
            if (!prevChapter) {
                console.log(`🎯 [ManhAstro] Primeiro capítulo encontrado: ${currentChapter.name}`);
                return currentChapter;
            }
            
            currentChapter = prevChapter;
            iterationCount++;
            
            // Pausa para ser respeitoso
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        
        console.log(`⚠️ [ManhAstro] Limite de iterações atingido, usando: ${currentChapter.name}`);
        return currentChapter;
    }

    // Buscar capítulo anterior via botão "Previous"
    private async findPreviousChapter(chapter: Chapter): Promise<Chapter | null> {
        try {
            const response = await this.http.getInstance().get(chapter.id, { timeout: this.timeout });
            const dom = new JSDOM(response.data);
            const document = dom.window.document;
            
            // Seletor específico descoberto na análise real
            const prevLink = document.querySelector('a.btn.prev_page') as HTMLAnchorElement;
            
            if (prevLink && prevLink.href && prevLink.href !== chapter.id) {
                const prevUrl = new URL(prevLink.href, this.url).toString();
                const prevName = this.extractChapterName(prevLink.textContent || '', prevUrl);
                return new Chapter(prevUrl, prevName, chapter.name.split(' - ')[0]);
            }
            
            // Fallback: seletores alternativos
            const fallbackSelectors = [
                '.nav-previous a',
                'a[class*="prev"]',
                '.wp-manga-nav a[href*="capitulo"]:first-child'
            ];
            
            for (const selector of fallbackSelectors) {
                const link = document.querySelector(selector) as HTMLAnchorElement;
                if (link && link.href && link.href !== chapter.id && link.href.includes('capitulo')) {
                    const url = new URL(link.href, this.url).toString();
                    const name = this.extractChapterName(link.textContent || '', url);
                    return new Chapter(url, name, chapter.name.split(' - ')[0]);
                }
            }
            
            return null;
        } catch (error) {
            return null;
        }
    }

    // Buscar próximo capítulo via botão "Next"
    private async findNextChapter(chapter: Chapter): Promise<Chapter | null> {
        try {
            const response = await this.http.getInstance().get(chapter.id, { timeout: this.timeout });
            const dom = new JSDOM(response.data);
            const document = dom.window.document;
            
            // Seletor específico descoberto na análise real
            const nextLink = document.querySelector('a.btn.next_page') as HTMLAnchorElement;
            
            if (nextLink && nextLink.href && nextLink.href !== chapter.id) {
                const nextUrl = new URL(nextLink.href, this.url).toString();
                const nextName = this.extractChapterName(nextLink.textContent || '', nextUrl);
                return new Chapter(nextUrl, nextName, chapter.name.split(' - ')[0]);
            }
            
            // Fallback: seletores alternativos
            const fallbackSelectors = [
                '.nav-next a',
                'a[class*="next"]',
                '.wp-manga-nav a[href*="capitulo"]:last-child'
            ];
            
            for (const selector of fallbackSelectors) {
                const link = document.querySelector(selector) as HTMLAnchorElement;
                if (link && link.href && link.href !== chapter.id && link.href.includes('capitulo')) {
                    const url = new URL(link.href, this.url).toString();
                    const name = this.extractChapterName(link.textContent || '', url);
                    return new Chapter(url, name, chapter.name.split(' - ')[0]);
                }
            }
            
            return null;
        } catch (error) {
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
        // Tentar extrair do texto do link
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
        const urlMatch = url.match(/capitulo-(\d+\.?\d*)/);
        if (urlMatch) {
            return `Capítulo ${urlMatch[1]}`;
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
                testUrl,
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
                    testUrl,
                    `Capitulo ${chapterNum}`,
                    baseTitle
                );
            }
        } catch (error) {
            // Capítulo não existe
        }
        
        return null;
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
}