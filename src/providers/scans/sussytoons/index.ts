import { JSDOM } from 'jsdom';
import { CustomAxios } from '../../../services/axios';
import { Chapter, Manga, Pages } from  '../../../providers/base/entities'
import logger from '../../../utils/logger';
import { TimeoutManager, ErrorType } from '../../../services/timeout_manager';

class AntiBotCircuitBreaker {
    private failures = 0;
    private lastFailure = 0;
    private readonly threshold = 5; // Aumentado para 5 falhas
    private readonly cooldown = 60000; // Reduzido para 1 minuto
    private readonly backoffMultiplier = 1.2; // Backoff mais suave
    private readonly resetWindow = 300000; // 5 minutos para resetar contador
    
    public async executeWithBreaker<T>(operation: () => Promise<T>): Promise<T> {
        // Reset automático se passou tempo suficiente
        if (Date.now() - this.lastFailure > this.resetWindow) {
            this.reset();
        }
        
        if (this.isOpen()) {
            const waitTime = this.getRemainingCooldown();
            if (waitTime > 0) {
                console.log(`🚫 Circuit breaker ativo - aguardando ${waitTime/1000}s`);
                await this.delay(waitTime);
            }
            // Após o cooldown, tentar reduzir failures gradualmente
            this.failures = Math.max(0, this.failures - 1);
            if (this.failures === 0) {
                console.log('🔄 Circuit breaker resetado após cooldown');
            }
        }
        
        try {
            const result = await operation();
            this.onSuccess();
            return result;
        } catch (error) {
            // Só contar como falha se for erro relacionado a anti-bot
            if (this.isAntiBotError(error)) {
                this.onFailure();
            }
            throw error;
        }
    }
    
    private isOpen(): boolean {
        return this.failures >= this.threshold;
    }
    
    private getRemainingCooldown(): number {
        if (!this.isOpen()) return 0;
        const elapsed = Date.now() - this.lastFailure;
        const dynamicCooldown = this.cooldown * Math.pow(this.backoffMultiplier, this.failures - this.threshold);
        return Math.max(0, dynamicCooldown - elapsed);
    }
    
    private onSuccess(): void {
        this.failures = 0;
        this.lastFailure = 0;
    }
    
    private onFailure(): void {
        this.failures++;
        this.lastFailure = Date.now();
        console.log(`⚠️ Circuit breaker: ${this.failures}/${this.threshold} falhas`);
    }
    
    private isAntiBotError(error: any): boolean {
        const message = error.message?.toLowerCase() || '';
        return message.includes('anti-bot') || 
               message.includes('ofuscado') || 
               message.includes('cloudflare') ||
               message.includes('just a moment') ||
               message.includes('checking') ||
               (error.response?.status === 403) ||
               (error.response?.status === 429);
    }
    
    private reset(): void {
        if (this.failures > 0) {
            console.log('🔄 Circuit breaker resetado');
        }
        this.failures = 0;
        this.lastFailure = 0;
    }
    
    private delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    public getStatus(): { isOpen: boolean; failures: number; remainingCooldown: number } {
        return {
            isOpen: this.isOpen(),
            failures: this.failures,
            remainingCooldown: this.getRemainingCooldown()
        };
    }
}

export class NewSussyToonsProvider  {
    name = 'New Sussy Toons';
    lang = 'pt_Br';
    domain = [
        'new.sussytoons.site',
        'www.sussyscan.com',
        'www.sussytoons.site',  
    ];
    private base = 'https://api.sussytoons.wtf';
    private CDN = 'https://cdn.sussytoons.site';
    private old =
        'https://oldi.sussytoons.site/wp-content/uploads/WP-manga/data/';
    private oldCDN = 'https://oldi.sussytoons.site/scans/1/obras';
    private webBase = 'https://www.sussytoons.wtf';

    private http: CustomAxios;
    private antiBotBreaker: AntiBotCircuitBreaker;

    constructor() {
        this.http = new CustomAxios(false); // Desabilita proxies externos - usa apenas proxy Python local
        this.antiBotBreaker = new AntiBotCircuitBreaker();
    }
    
    /**
     * Aplica timeouts progressivos baseado no ciclo atual
     */
    public applyProgressiveTimeouts(): void {
        const timeoutManager = TimeoutManager.getInstance();
        const axiosTimeout = timeoutManager.getTimeoutFor('provider_operation');
        this.http.updateTimeout(axiosTimeout);
        // this.http.applyCentralizedTimeouts(); // Removido para evitar erro de referência
        
        console.log(`🕐 Provider timeouts atualizados: ${axiosTimeout/1000}s`);
    }
    
    /**
     * Restaura timeouts para valores padrão
     */
    public resetTimeouts(): void {
        const timeoutManager = TimeoutManager.getInstance();
        timeoutManager.resetToDefaults();
        this.http.resetTimeout();
        console.log(`🔄 Provider timeouts restaurados para padrão`);
    }
    
    /**
     * Verifica se a resposta contém JavaScript ofuscado (proteção anti-bot)
     */
    private isProtectedResponse(htmlContent: string): boolean {
        // Verifica se o conteúdo é muito pequeno (provável erro/proteção)
        if (htmlContent.length < 1000) {
            return true;
        }
        
        // Verifica se contém apenas JavaScript sem conteúdo HTML útil
        const hasUsefulContent = htmlContent.includes('chakra-image') || 
                                htmlContent.includes('img') || 
                                htmlContent.includes('chapter') ||
                                htmlContent.includes('manga') ||
                                htmlContent.includes('image');
        
        if (!hasUsefulContent) {
            return true;
        }
        
        // Detectar padrões específicos de proteção anti-bot apenas se não há conteúdo útil
        const protectionPatterns = [
            /just\s+a\s+moment/i,         // Cloudflare "Just a moment"
            /checking.*browser/i,         // Mensagens de verificação
            /please.*wait/i,              // Mensagens de espera
            /enable.*javascript/i,        // Avisos sobre JavaScript
            /ray\s+id/i                   // Cloudflare Ray ID
        ];
        
        return protectionPatterns.some(pattern => pattern.test(htmlContent));
    }
    
    /**
     * Obtém status do circuit breaker
     */
    public getCircuitBreakerStatus(): { isOpen: boolean; failures: number; remainingCooldown: number } {
        return this.antiBotBreaker.getStatus();
    }

    async getManga(link: string): Promise<Manga> {
        const match = link.match(/\/obra\/(\d+)/);
        if (!match || !match[1]) throw new Error('Invalid link');

        const idValue = match[1];
        logger.info(`calling url: ${this.base}/obras/${idValue}`);
        const response = await this.http.getInstance().get(`${this.base}/obras/${idValue}`);
        logger.info(`called`);

        const title = response.data.resultado.obr_nome;

        return new Manga(link, title);
    }

    async getChapters(id: string): Promise<Chapter[]> {
        try {
            const match = id.match(/\/obra\/(\d+)/);
            if (!match || !match[1]) throw new Error('Invalid ID');

            const idValue = match[1];
            const response = await this.http.getInstance().get(`${this.base}/obras/${idValue}`);
            const title = response.data.resultado.obr_nome;

            return response.data.resultado.capitulos.map((ch: any) => 
                new Chapter([idValue, ch.cap_id], ch.cap_nome, title));
        } catch (e) {
            console.error(e);
            return [];
        }
    }

    private async getPagesWithPuppeteer(url: string, attemptNumber: number = 1): Promise<string> {
        return await this.antiBotBreaker.executeWithBreaker(async () => {
            // Monta a URL da API, codificando a URL de destino
            logger.info(`calling url: ${url}`);
            const apiUrl = `http://localhost:3333/scrape?url=${encodeURIComponent(url)}`;
            
            const timeoutManager = TimeoutManager.getInstance();
            const baseTimeout = timeoutManager.getTimeoutFor('bypass_cloudflare');
            
            // Calcular timeout progressivo: 35s, 42s, 50.4s (20% de aumento por tentativa)
            const progressiveTimeout = baseTimeout * Math.pow(1.2, attemptNumber - 1);
            
            const startTime = Date.now();
            
            console.log(`📡 Bypass Cloudflare (tentativa ${attemptNumber}, timeout: ${progressiveTimeout/1000}s)...`);
            
            try {
                // Realiza a requisição à API utilizando fetch com timeout progressivo
                const response = await Promise.race([
                    fetch(apiUrl),
                    new Promise<never>((_, reject) => 
                        setTimeout(() => reject(new Error('Timeout na requisição')), progressiveTimeout)
                    )
                ]);
                
                const responseTime = Date.now() - startTime;
                timeoutManager.recordResponseTime('scrape', responseTime);
                
                if (!response.ok) {
                    const error = new Error(`Erro HTTP: ${response.status}`);
                    timeoutManager.recordError('scrape', ErrorType.NETWORK);
                    throw error;
                }
                
                const data = await response.json();
                
                // Verificar se o HTML contém proteção anti-bot
                if (this.isProtectedResponse(data.html)) {
                    timeoutManager.recordError('scrape', ErrorType.ANTI_BOT);
                    logger.info('Proteção anti-bot detectada, aguardando bypass...');
                    
                    // Aguarda mais tempo para o bypass Cloudflare funcionar completamente
                    await this.delay(8000); // Aumentado para 8s
                    
                    // Tenta novamente com timeout maior para dar tempo ao bypass
                    const retryResponse = await Promise.race([
                        fetch(apiUrl),
                        new Promise<never>((_, reject) => 
                            setTimeout(() => reject(new Error('Timeout no retry')), progressiveTimeout * 1.5)
                        )
                    ]);
                    
                    if (!retryResponse.ok) {
                        throw new Error(`Erro HTTP no retry: ${retryResponse.status}`);
                    }
                    
                    const retryData = await retryResponse.json();
                    
                    // Se ainda tiver proteção, aguarda mais tempo
                    if (this.isProtectedResponse(retryData.html)) {
                        logger.info('Ainda protegido, aguardando bypass completo...');
                        await this.delay(15000); // Aumentado para 15s
                        
                        // Terceira tentativa com timeout extendido
                        const finalResponse = await Promise.race([
                            fetch(apiUrl),
                            new Promise<never>((_, reject) => 
                                setTimeout(() => reject(new Error('Timeout na tentativa final')), progressiveTimeout * 2)
                            )
                        ]);
                        
                        if (!finalResponse.ok) {
                            throw new Error(`Erro HTTP na tentativa final: ${finalResponse.status}`);
                        }
                        
                        const finalData = await finalResponse.json();
                        
                        if (this.isProtectedResponse(finalData.html)) {
                            const error = new Error('Página protegida por anti-bot (JavaScript ofuscado detectado)');
                            timeoutManager.recordError('scrape', ErrorType.ANTI_BOT);
                            throw error;
                        }
                        
                        return finalData.html;
                    }
                    
                    return retryData.html;
                }
                
                // Retorna o conteúdo HTML obtido da API
                return data.html;
            } catch (error) {
                console.error("Erro ao consumir a API:", error);
                
                // Registrar tipo de erro
                if (error.message.includes('Timeout')) {
                    timeoutManager.recordError('scrape', ErrorType.TIMEOUT);
                } else if (error.message.includes('anti-bot')) {
                    timeoutManager.recordError('scrape', ErrorType.ANTI_BOT);
                } else {
                    timeoutManager.recordError('scrape', ErrorType.NETWORK);
                }
                
                throw error;
            }
        });
    }
      
      private delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
      }

    public async getPages(ch: Chapter, attemptNumber: number = 1): Promise<Pages> {
        try {
            let list: string[] = [];
            
            const html = await this.getPagesWithPuppeteer(`${this.webBase}/capitulo/${ch.id[1]}`, attemptNumber);
            const dom = new JSDOM(html);
            //@ts-ignore
            const images = [...dom.window.document.querySelectorAll('img.chakra-image.css-8atqhb')].map(img => img.src);
            
            if (images && images.length > 0) {
                list.push(...images);
            } else {
                console.log(`⚠️ Tentativa ${attemptNumber}/5: 0 páginas encontradas, aguardando bypass Cloudflare...`);
                
                // Aguarda mais tempo para o bypass Cloudflare processar completamente
                const delay = 10000 * attemptNumber; // 10s, 20s, 30s, 40s, 50s
                console.log(`⏳ Aguardando ${delay/1000}s para bypass Cloudflare completar...`);
                await this.delay(delay);
                
                // Tentar novamente após delay
                const retryHtml = await this.getPagesWithPuppeteer(`${this.webBase}/capitulo/${ch.id[1]}`, attemptNumber);
                const retryDom = new JSDOM(retryHtml);
                //@ts-ignore
                const retryImages = [...retryDom.window.document.querySelectorAll('img.chakra-image.css-8atqhb')].map(img => img.src);
                
                if (retryImages && retryImages.length > 0) {
                    list.push(...retryImages);
                }
            }

            return new Pages(ch.id, ch.number, ch.name, list);
        } catch (error) {
            logger.error(error);
            throw error;
        }
    }
}