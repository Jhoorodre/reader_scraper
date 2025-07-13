import { Manga, Chapter, Pages } from "../../../providers/base/entities";

describe('Entities', () => {
    describe('Manga', () => {
        test('should create a Manga instance with correct properties', () => {
            const manga = new Manga('123', 'One Piece');
            expect(manga.id).toBe('123');
            expect(manga.name).toBe('One Piece');
        });

        test('fromDict should create a Manga instance from a dictionary', () => {
            const data = { id: '123', name: 'One Piece' };
            const manga = Manga.fromDict(data);
            expect(manga).toBeInstanceOf(Manga);
            expect(manga.id).toBe('123');
            expect(manga.name).toBe('One Piece');
        });
    });

    describe('Chapter', () => {
        test('should create a Chapter instance with correct properties', () => {
            const chapter = new Chapter(['123', '456'], '1', 'Chapter 1');
            expect(chapter.id).toEqual(['123', '456']);
            expect(chapter.number).toBe('1');
            expect(chapter.name).toBe('Chapter 1');
        });

        test('fromDict should create a Chapter instance from a dictionary', () => {
            const chapter = Chapter.fromDict('123', '1', 'Chapter 1');
            expect(chapter).toBeInstanceOf(Chapter);
            expect(chapter.id).toEqual(['123']);
            expect(chapter.number).toBe('1');
            expect(chapter.name).toBe('Chapter 1');
        });
    });

    describe('Pages', () => {
        test('should create a Pages instance with correct properties', () => {
            const pages = new Pages(['123', '456'], '1', 'Chapter 1', ['url1', 'url2']);
            expect(pages.id).toEqual(['123', '456']);
            expect(pages.number).toBe('1');
            expect(pages.name).toBe('Chapter 1');
            expect(pages.pages).toEqual(['url1', 'url2']);
        });

        test('fromDict should create a Pages instance from a dictionary', () => {
            const pages = Pages.fromDict('123', '1', 'Chapter 1', ['url1', 'url2']);
            expect(pages).toBeInstanceOf(Pages);
            expect(pages.id).toEqual(['123']);
            expect(pages.number).toBe('1');
            expect(pages.name).toBe('Chapter 1');
            expect(pages.pages).toEqual(['url1', 'url2']);
        });
    });
});