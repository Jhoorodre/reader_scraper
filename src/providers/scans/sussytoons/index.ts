import { JSDOM } from 'jsdom';
import { CustomAxios } from '../../../services/axios';
import { Chapter, Manga, Pages } from  '../../../providers/base/entities'
import logger from '../../../utils/logger';
import { TimeoutManager } from '../../../services/timeout_manager';

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

    constructor() {
        this.http = new CustomAxios(false); // Desabilita proxies externos - usa apenas proxy Python local
    }
    
    /**
     * Aplica timeouts progressivos baseado no ciclo atual
     */
    public applyProgressiveTimeouts(): void {
        const timeoutManager = TimeoutManager.getInstance();
        const axiosTimeout = timeoutManager.getTimeout('axios');
        this.http.updateTimeout(axiosTimeout);
    }
    
    /**
     * Restaura timeouts para valores padrão
     */
    public resetTimeouts(): void {
        this.http.resetTimeout();
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

    private async getPagesWithPuppeteer(url: string): Promise<string> {
        // Monta a URL da API, codificando a URL de destino
        logger.info(`calling url: ${url}`);
        const apiUrl = `http://localhost:3333/scrape?url=${encodeURIComponent(url)}`;
      
        try {
          // Realiza a requisição à API utilizando fetch
          const response = await fetch(apiUrl);
      
          // Verifica se a resposta foi satisfatória
          if (!response.ok) {
            throw new Error(`Erro HTTP: ${response.status}`);
          }
      
          // Converte a resposta para JSON
          const data = await response.json();
          
          // Verificar se o HTML contém proteção anti-bot
          if (this.isProtectedResponse(data.html)) {
            logger.info('Proteção anti-bot detectada, aguardando bypass...');
            
            // Aguarda mais tempo para o bypass funcionar
            await this.delay(5000);
            
            // Tenta novamente
            const retryResponse = await fetch(apiUrl);
            if (!retryResponse.ok) {
              throw new Error(`Erro HTTP no retry: ${retryResponse.status}`);
            }
            
            const retryData = await retryResponse.json();
            
            // Se ainda tiver proteção após o delay, aguarda mais um pouco
            if (this.isProtectedResponse(retryData.html)) {
              logger.info('Ainda protegido, aguardando mais tempo...');
              await this.delay(10000);
              
              // Terceira tentativa
              const finalResponse = await fetch(apiUrl);
              if (!finalResponse.ok) {
                throw new Error(`Erro HTTP na tentativa final: ${finalResponse.status}`);
              }
              
              const finalData = await finalResponse.json();
              
              if (this.isProtectedResponse(finalData.html)) {
                throw new Error('Página protegida por anti-bot (JavaScript ofuscado detectado)');
              }
              
              return finalData.html;
            }
            
            return retryData.html;
          }
      
          // Retorna o conteúdo HTML obtido da API
          return data.html;
        } catch (error) {
          console.error("Erro ao consumir a API:", error);
          throw error;
        }
      }
      
      private delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
      }

    public async getPages(ch: Chapter): Promise<Pages> {
        try {
            let list: string[] = [];
            let whileIsTrue = true;
            let currentPage = 0;
            let sleepTime = 10;
            
            while (whileIsTrue) {
                const html = await this.getPagesWithPuppeteer(`${this.webBase}/capitulo/${ch.id[1]}`);
                const dom = new JSDOM(html);
                //@ts-ignore
                const images = [...dom.window.document.querySelectorAll('img.chakra-image.css-8atqhb')].map(img => img.src);
                
                if (images) {
                    list.push(...images);
                }
                    break;
            }

            return new Pages(ch.id, ch.number, ch.name, list);
        } catch (error) {
            logger.error(error);
            throw error;
        }
    }
}