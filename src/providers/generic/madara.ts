import { JSDOM } from 'jsdom';
import { URL } from 'url';
import { CustomAxios } from '../../services/axios';
import { Manga, Chapter, Pages } from '../base/entities';

export abstract class WordPressMadara {
    url: string | null = null;
    path: string = '';
    query_mangas: string = 'div.post-title h3 a, div.post-title h5 a';
    query_chapters: string = 'li.wp-manga-chapter > a';
    query_chapters_title_bloat: string | null = null;
    query_pages: string = 'div.page-break.no-gaps';
    query_title_for_uri: string = 'head meta[property="og:title"]';
    query_placeholder: string = '[id^="manga-chapters-holder"][data-id]';
    timeout: number | null = null;

    http: CustomAxios;

    constructor() {
        this.http = new CustomAxios(false); // Habilita o uso de proxies
    }

    async getManga(link: string): Promise<Manga> {
        const response = await this.http.getInstance().get(link, { timeout: this.timeout });
        const dom = new JSDOM(response.data);
        const document = dom.window.document;
        const element = document.querySelector(this.query_title_for_uri);
        const title = element?.getAttribute('content')?.trim() || element?.textContent?.trim() || '';
        return new Manga(link, title);
    }

    async getChapters(id: string): Promise<Chapter[]> {
        const uri = new URL(id, this.url!).toString();
        const response = await this.http.getInstance().get(uri, { timeout: this.timeout });
        const dom = new JSDOM(response.data);
        const document = dom.window.document;
        const titleElement = document.querySelector(this.query_title_for_uri);
        const title = titleElement?.getAttribute('content')?.trim() || titleElement?.textContent?.trim() || '';
        let data = Array.from(document.querySelectorAll(this.query_chapters));
        const placeholder = document.querySelector(this.query_placeholder);

        if (placeholder) {
            try {
                data = await this.getChaptersAjax(id);
            } catch {
                try {
                    data = await this.getChaptersAjaxOld(placeholder.getAttribute('data-id')!);
                } catch {}
            }
        }

        const chapters = data.map(el => {
            //@ts-ignore
            return new Chapter(this.getRootRelativeOrAbsoluteLink(el as HTMLAnchorElement, uri), el.textContent!.trim(), title);
        });
        return chapters.reverse();
    }

    async getPages(chapter: Chapter): Promise<Pages> {
        let uri = new URL(chapter.id, this.url!).toString();
        uri = this.addQueryParams(uri, { style: 'list' });
        let response = await this.http.getInstance().get(uri, { timeout: this.timeout });
        let dom = new JSDOM(response.data);
        let data = Array.from(dom.window.document.querySelectorAll(this.query_pages));

        if (!data.length) {
            uri = this.removeQueryParams(uri, ['style']);
            response = await this.http.getInstance().get(uri, { timeout: this.timeout });
            dom = new JSDOM(response.data);
            data = Array.from(dom.window.document.querySelectorAll(this.query_pages));
        }

        const pages = data.map(el => this.processPageElement(el as HTMLElement, uri));
        const numberMatch = chapter.number.match(/\d+\.?\d*/);
        const number = numberMatch ? numberMatch[0] : '';

        return new Pages(chapter.id, number, chapter.name, pages);
    }

    protected async getChaptersAjax(mangaId: string): Promise<Element[]> {
        if (!mangaId.endsWith('/')) mangaId += '/';
        const uri = new URL(`${mangaId}ajax/chapters/`, this.url!).toString();
        const response = await this.http.getInstance().post(uri, {}, { timeout: this.timeout });
        const dom = new JSDOM(response.data);
        return Array.from(dom.window.document.querySelectorAll(this.query_chapters));
    }

    protected async getChaptersAjaxOld(dataId: string): Promise<Element[]> {
        const uri = new URL(`${this.path}/wp-admin/admin-ajax.php`, this.url!).toString();
        const response = await this.http.getInstance().post(uri, `action=manga_get_chapters&manga=${dataId}`, {
            headers: { 'content-type': 'application/x-www-form-urlencoded', 'x-referer': this.url! },
            timeout: this.timeout,
        });
        const dom = new JSDOM(response.data);
        return Array.from(dom.window.document.querySelectorAll(this.query_chapters));
    }

    protected processPageElement(element: HTMLElement, referer: string): string {
        const img = element.querySelector('img') || element.querySelector('image');
        const src = img?.getAttribute('data-url') || img?.getAttribute('data-src') || img?.getAttribute('srcset') || img?.getAttribute('src');

        if (src && src.startsWith('data:image')) {
            return src.split(' ')[0];
        } else {
            const urlMatch = src.match(/https?:\/\/[^\s]+/);
            //console.log('URL extraída:', urlMatch[0]);
            if(urlMatch) {
                return this.createConnectorUri({ url: urlMatch[0], referer });
            }
            const absolutePath = this.getAbsolutePath(img as HTMLElement, referer);
            return this.createConnectorUri({ url: absolutePath, referer });
        }
    }

    protected addQueryParams(url: string, params: Record<string, string>): string {
        const urlObj = new URL(url);
        Object.keys(params).forEach(key => urlObj.searchParams.append(key, params[key]));
        return urlObj.toString();
    }

    protected removeQueryParams(url: string, params: string[]): string {
        const urlObj = new URL(url);
        params.forEach(param => urlObj.searchParams.delete(param));
        return urlObj.toString();
    }

    protected getRootRelativeOrAbsoluteLink(element: HTMLAnchorElement, baseUrl: string): string {
        return new URL(element.href, baseUrl).toString();
    }

    protected getAbsolutePath(element: HTMLElement, baseUrl: string): string {
        return new URL(element.getAttribute('src')!, baseUrl).toString();
    }

    protected createConnectorUri(payload: { url: string, referer: string }): string {
        return payload.url;
    }
}