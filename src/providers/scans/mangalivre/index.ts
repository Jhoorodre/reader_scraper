import { Pages } from "../../base/entities";
import { WordPressMadara } from "../../generic/madara";
import { JSDOM } from 'jsdom';

export class MangaLivreProvider extends WordPressMadara {
    constructor() {
        super();
        this.url = 'https://mangalivre.tv';
        this.path = '/';
        
        // Seletores específicos do MangaLivre.tv
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
            const response = await this.http.getInstance().get(new URL(chapter.id, this.url).toString(), { 
                timeout: this.timeout 
            });
            const dom = new JSDOM(response.data);
            const document = dom.window.document;

            // Primeiro, tentar buscar imagens diretamente no conteúdo
            let images = Array.from(document.querySelectorAll(this.query_pages));
            
            if (images.length === 0) {
                // Fallback: buscar imagens do CDN MangaLivre
                images = Array.from(document.querySelectorAll('img[src*="cdn.mangalivre"], img[data-src*="mangalivre"]'));
            }
            
            if (images.length === 0) {
                // Último fallback: buscar qualquer imagem no container de leitura
                images = Array.from(document.querySelectorAll('.reading-content img, .page-break img, .wp-manga-chapter-img img'));
            }

            const pages = images
                .map(img => {
                    // Tentar diferentes atributos de imagem
                    return img.getAttribute('src') || 
                           img.getAttribute('data-src') || 
                           img.getAttribute('data-lazy-src') ||
                           img.getAttribute('data-original');
                })
                .filter(Boolean)
                .map(src => src.trim())
                .filter(src => src && !src.includes('data:image')) // Filtrar imagens base64/placeholder
                .map(src => {
                    // Converter URLs relativas para absolutas
                    if (src.startsWith('//')) {
                        return 'https:' + src;
                    } else if (src.startsWith('/')) {
                        return this.url + src;
                    }
                    return src;
                })
                .filter(src => {
                    // Filtrar apenas URLs válidas de imagem
                    return src.match(/\.(jpg|jpeg|png|webp|gif)(\?|$)/i) || src.includes('cdn.mangalivre');
                });

            console.log(`📖 [MangaLivre] Encontradas ${pages.length} páginas para ${chapter.name}`);
            
            if (pages.length === 0) {
                throw new Error(`Nenhuma página encontrada para o capítulo ${chapter.name}`);
            }

            return new Pages(chapter.id, chapter.number, chapter.name, pages);
            
        } catch (error) {
            console.error(`❌ [MangaLivre] Erro ao obter páginas do capítulo ${chapter.name}:`, error.message);
            
            // Retry em caso de erro
            if (attemptNumber < 3) {
                console.log(`🔄 [MangaLivre] Tentativa ${attemptNumber + 1} para ${chapter.name}`);
                await new Promise(resolve => setTimeout(resolve, 2000 * attemptNumber));
                return this.getPages(chapter, attemptNumber + 1);
            }
            
            throw error;
        }
    }

    // Override para customizar busca de capítulos se necessário
    async getChapters(id: string) {
        try {
            console.log(`🔍 [MangaLivre] Buscando capítulos para: ${id}`);
            const chapters = await super.getChapters(id);
            
            // Filtrar apenas capítulos válidos (evitar CSS e outros elementos)
            const validChapters = chapters.filter(chapter => {
                const number = chapter.number;
                // Verificar se contém número de capítulo válido
                return number && number.match(/cap[ií]tulo\s*\d+/i) && !number.includes('{') && !number.includes('css');
            });
            
            console.log(`📚 [MangaLivre] Encontrados ${validChapters.length} capítulos válidos`);
            return validChapters;
        } catch (error) {
            console.error(`❌ [MangaLivre] Erro ao buscar capítulos:`, error.message);
            throw error;
        }
    }

    // Override para customizar busca de manga se necessário
    async getManga(link: string) {
        try {
            console.log(`🎯 [MangaLivre] Buscando manga: ${link}`);
            const manga = await super.getManga(link);
            console.log(`📖 [MangaLivre] Manga encontrado: ${manga.name}`);
            return manga;
        } catch (error) {
            console.error(`❌ [MangaLivre] Erro ao buscar manga:`, error.message);
            throw error;
        }
    }
}