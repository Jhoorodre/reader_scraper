import { Pages } from "./entities";

export class DownloadUseCase {
    // Método estático para executar o download
    static async execute(pages: Pages, fn: any, headers?: any, cookies?: any): Promise<void> {
        try {
            console.log('Starting download...');
            // Simulação de download
            for (const pageUrl of pages.pages) {
                console.log(`Downloading page: ${pageUrl}`);
                // Aqui você pode adicionar a lógica real de download, como usar axios ou fetch
                // Exemplo: await axios.get(pageUrl, { headers, ... });
            }
            console.log('Download completed!');
            if (fn) fn(); // Executa a função de callback, se fornecida
        } catch (error) {
            console.error('Download failed:', error);
            throw error;
        }
    }
}