import { Pages } from "../../base/entities";
import { WordPressMadara } from "../../generic/madara";
import { JSDOM } from 'jsdom';

export class SeitaCelestialProvider extends WordPressMadara {
    constructor() {
        super();
        this.url = 'https://seitacelestial.com';
        this.path = '/';
        this.query_mangas = 'ul.manga-list li a';
        this.query_chapters = 'div#chapterlist ul li a';
        this.query_pages = 'div#readerarea img';
        this.query_title_for_uri = 'h1.entry-title';
    }

    async getPages(chapter, attemptNumber = 1) {
        const response = await this.http.getInstance().get(new URL(chapter.id, this.url).toString());
        const dom = new JSDOM(response.data);
        const document = dom.window.document;

        const linkTag = document.querySelector('link[rel="alternate"][title="JSON"]');
        if (!linkTag) throw new Error('JSON link not found');

        const jsonUrl = linkTag.getAttribute('href');
        const jsonResponse = await this.http.getInstance().get(jsonUrl);
        const jsonData = jsonResponse.data;

        const jsonDom = new JSDOM(jsonData.content.rendered);
        const images = Array.from(jsonDom.window.document.querySelectorAll('img'));

        const pages = images.map(img => img.getAttribute('src')?.trim()).filter(Boolean);

        return new Pages(chapter.id, chapter.number, chapter.name, pages);
    }
}