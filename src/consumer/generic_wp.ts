import fs from 'fs';
import Bluebird from 'bluebird';
import { downloadImage } from '../download/images';
import { promptUser } from '../utils/prompt';
import { WordPressMadara } from '../providers/generic/madara';
import logger from '../utils/logger';
import path from 'path';
import { getMangaBasePath, cleanTempFiles, cleanupAfterChapter } from '../utils/folder';

export class GenericConstructor extends WordPressMadara {
    constructor(urlBase) {
        super();
        this.url = urlBase
        logger.info(`Using url base: ${urlBase}`)
    }
}

async function downloadManga() {
    const reportFile = 'download_report.txt';

    try {
        const mangaUrl = await promptUser('Digite a URL da obra: ') as string;

        // Extrai a URL base da URL da obra
        const urlBase = new URL(mangaUrl).origin;

        // Cria o provider usando a URL base extraída
        const provider = new GenericConstructor(urlBase);

        const manga = await provider.getManga(mangaUrl);
        console.log('\n=== Informações do Manga ===');
        console.log('Título:', manga.name);
        console.log('Link:', manga.id);

        fs.writeFileSync(reportFile, `Relatório de Download - Manga: ${manga.name}\n\n`);

        const chapters = await provider.getChapters(manga.id);

        console.log('\n=== Capítulos Disponíveis ===');
        chapters.forEach((chapter, index) => {
            console.log(`Índice: ${index} - Capítulo: ${chapter.number}`);
        });
        
        console.log('\nOpções de Download:');
        console.log('1. Baixar tudo');
        console.log('2. Baixar intervalo de capítulos');
        console.log('3. Escolher capítulos específicos');
        
        const option = await promptUser('Escolha uma opção (1, 2 ou 3): ');
        
        let selectedChapters = [];
        
        if (option === '1') { 
            selectedChapters = chapters;
        } else if (option === '2') {
            //@ts-ignore
            const start = parseInt(await promptUser('Digite o índice inicial do intervalo: '), 10);
            //@ts-ignore
            const end = parseInt(await promptUser('Digite o índice final do intervalo: '), 10);
            selectedChapters = chapters.slice(start, end + 1);
        } else if (option === '3') {
            const chaptersInput = await promptUser('Digite os índices dos capítulos que deseja baixar, separados por vírgula (ex: 0,1,4): ');
            //@ts-ignore
            const indices = chaptersInput.split(',').map(num => parseInt(num.trim(), 10));
            selectedChapters = indices.map(index => chapters[index]).filter(chapter => chapter !== undefined);
        } else {
            console.log('Opção inválida. Tente novamente.');
        }
        
        console.log('\nCapítulos selecionados para download:');
        selectedChapters.forEach(chapter => console.log(`Capítulo: ${chapter.number}`));

        console.log('\n=== Capítulos Selecionados ===');
        selectedChapters.forEach((chapter, index) => {
            console.log(`Capítulo ${index + 1}: ${chapter.number}`);
        });

        
        await Bluebird.map(selectedChapters, async (chapter) => {
            console.log(`\n=== Processando Capítulo: ${chapter.number} ===`);
            let chapterSuccess = true;
            fs.appendFileSync(reportFile, `Capítulo: ${chapter.number}\n`);
        
            // Obter as páginas do capítulo
            const pages = await provider.getPages(chapter);
            console.log(`Total de Páginas: ${pages.pages.length}`);
        
            await Bluebird.map(pages.pages, async (pageUrl, pageIndex) => {
                const capitulo = (pageIndex + 1 ) <= 9 ? `0${pageIndex + 1}` :`${pageIndex + 1}`
                console.log(`Baixando Página ${capitulo}: ${pageUrl}`);
        
                try {
                    // Criar o diretório para o capítulo
                    const sanitizedName = manga.name?.replace(`Capítulo`, ``).replace(/[\\\/:*?"<>|]/g, '-');  // substitui caracteres inválidos por '-'
                    const dirPath = path.join(getMangaBasePath(), path.normalize(sanitizedName), chapter.number.toString());
        
                    // Verificar se o diretório existe, se não, criar
                    if (!fs.existsSync(dirPath)) {
                        fs.mkdirSync(dirPath, { recursive: true });
                    }
        
                    // Caminho completo para salvar a imagem
                    const imagePath = path.join(dirPath, `${capitulo}.jpg`);
        
                    // Baixar a imagem
                    await downloadImage(pageUrl, imagePath);
                } catch (error) {
                    console.error(`Erro ao baixar a Página ${capitulo}: ${error.message}`);
                    chapterSuccess = false;
                }
            }, { concurrency: 5 });
        
            // Registrar o sucesso ou falha do capítulo
            if (chapterSuccess) {
                fs.appendFileSync(reportFile, `Capítulo ${chapter.number} baixado com sucesso.\n`);
                
                // Limpeza imediata e específica após capítulo baixado
                cleanupAfterChapter();
                cleanTempFiles();
            } else {
                fs.appendFileSync(reportFile, `Falha no download do capítulo ${chapter.number}.\n`);
            }
        }, { concurrency: 5 });
        
        console.log('\nDownload completo. Relatório salvo em:', reportFile);
    } catch (error) {
        console.error('Erro durante a execução:', error);
        fs.appendFileSync(reportFile, `Erro durante a execução: ${error.message}\n`);
    }
}
