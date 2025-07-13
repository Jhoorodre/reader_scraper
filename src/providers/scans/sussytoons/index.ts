import { JSDOM } from 'jsdom';
import { CustomAxios } from '../../../services/axios';
import { Chapter, Manga, Pages } from  '../../../providers/base/entities'
import logger from '../../../utils/logger';
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
        this.http = new CustomAxios(false); // Habilita o uso de proxies
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
      
          // Retorna o conteúdo HTML obtido da API
          return data.html;
        } catch (error) {
          console.error("Erro ao consumir a API:", error);
          throw error;
        }
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
