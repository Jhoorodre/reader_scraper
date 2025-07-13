export class Chapter {
    constructor(
        public id: string[], // Array de strings para o ID do capítulo
        public number: string, // Número do capítulo
        public name: string // Nome do capítulo
    ) {}

    // Método estático para criar uma instância de Chapter a partir de um objeto
    static fromDict(id: string, number: string, name: string): Chapter {
        return new Chapter([id], number, name);
    }
}

export class Pages {
    constructor(
        public id: string[], // Array de strings para o ID das páginas
        public number: string, // Número da página
        public name: string, // Nome da página
        public pages: string[] // Lista de URLs das páginas
    ) {}

    // Método estático para criar uma instância de Pages a partir de um objeto
    static fromDict(id: string, number: string, name: string, pages: string[]): Pages {
        return new Pages([id], number, name, pages);
    }
}

export class Manga {
    constructor(
        public id: string, // ID do mangá
        public name: string // Nome do mangá
    ) {}

    // Método estático para criar uma instância de Manga a partir de um objeto
    static fromDict(data: { id: string; name: string }): Manga {
        return new Manga(data.id, data.name);
    }
}