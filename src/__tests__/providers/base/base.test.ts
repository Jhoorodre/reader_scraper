import { Base } from "../../../providers/base/base";
import { Manga, Chapter, Pages } from "../../../providers/base/entities";

class ConcreteProvider extends Base {
    name = 'Concrete Provider';
    lang = 'en';
    domain = ['example.com'];
    hasLogin = false;

    async login(): Promise<void> {
        // Mock implementation
    }

    async getManga(link: string): Promise<Manga> {
        return new Manga(link, 'Concrete Manga');
    }

    async getChapters(id: string): Promise<Chapter[]> {
        return [new Chapter([id, '1'], 'Chapter 1', 'Concrete Manga')];
    }

    async getPages(ch: Chapter): Promise<Pages> {
        return new Pages(ch.id, ch.number, ch.name, ['url1', 'url2']);
    }
}

describe('Base', () => {
    let provider: ConcreteProvider;

    beforeEach(() => {
        provider = new ConcreteProvider();
    });

    test('getManga should return a Manga object', async () => {
        const manga = await provider.getManga('https://example.com/manga/123');
        expect(manga).toBeInstanceOf(Manga);
        expect(manga.name).toBe('Concrete Manga');
    });

    test('getChapters should return an array of Chapter objects', async () => {
        const chapters = await provider.getChapters('123');
        expect(chapters).toHaveLength(1);
        expect(chapters[0]).toBeInstanceOf(Chapter);
    });

    test('getPages should return a Pages object', async () => {
        const chapter = new Chapter(['123', '1'], 'Chapter 1', 'Concrete Manga');
        const pages = await provider.getPages(chapter);
        expect(pages).toBeInstanceOf(Pages);
        expect(pages.pages).toEqual(['url1', 'url2']);
    });
});