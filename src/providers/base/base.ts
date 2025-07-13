import { DownloadUseCase } from "./download";
import { Manga, Chapter, Pages } from "./entities";
import { ProviderRepository } from "./provider_repository";

export abstract class Base implements ProviderRepository {
    name: string = '';
    lang: string = '';
    domain: string[] = [''];
    hasLogin?: boolean = false;

    // Método abstrato para login (deve ser implementado pelas classes filhas)
    abstract login(): void;

    // Método abstrato para obter um mangá (deve ser implementado pelas classes filhas)
    abstract getManga(link: string): Promise<Manga>;

    // Método abstrato para obter os capítulos de um mangá (deve ser implementado pelas classes filhas)
    abstract getChapters(id: string): Promise<Chapter[]>;

    // Método abstrato para obter as páginas de um capítulo (deve ser implementado pelas classes filhas)
    abstract getPages(ch: Chapter): Promise<Pages>;

    // Método concreto para realizar o download das páginas
    async download(pages: Pages, fn: any, headers?: any, cookies?: any): Promise<void> {
        return DownloadUseCase.execute(pages, fn, headers, cookies);
    }
}