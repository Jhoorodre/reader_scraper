import { Chapter, Pages, Manga } from './entities';

export interface ProviderRepository {
    name: string;
    lang: string;
    domain: string[];
    hasLogin?: boolean;

    login(): void;
    getManga(link: string): Promise<Manga>;
    getChapters(id: string): Promise<Chapter[]>;
    getPages(ch: Chapter): Promise<Pages>;
    download(pages: Pages, fn: any, headers?: any, cookies?: any): Promise<void>;
}
