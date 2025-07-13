import { Base } from "../../../providers/base/base";
import { Manga, Chapter, Pages } from "../../../providers/base/entities";

class MockDownloadProvider extends Base {
    name = 'Mock Download Provider';
    lang = 'en';
    domain = ['example.com'];
    hasLogin = false;

    async login(): Promise<void> {
        // Mock implementation
    }

    async getManga(link: string): Promise<Manga> {
        return new Manga(link, 'Mock Manga');
    }

    async getChapters(id: string): Promise<Chapter[]> {
        return [new Chapter([id, '1'], 'Chapter 1', 'Mock Manga')];
    }

    async getPages(ch: Chapter): Promise<Pages> {
        return new Pages(ch.id, ch.number, ch.name, ['url1', 'url2']);
    }
}

describe('Download', () => {
    let provider: MockDownloadProvider;

    beforeEach(() => {
        provider = new MockDownloadProvider();
    });

    test('download should execute without errors', async () => {
        const pages = new Pages(['123', '1'], '1', 'Chapter 1', ['url1', 'url2']);
        const mockFn = jest.fn();

        await expect(provider.download(pages, mockFn)).resolves.not.toThrow();
        expect(mockFn).toHaveBeenCalled();
    });
});