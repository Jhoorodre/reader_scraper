import fetch from 'node-fetch';
import fs from 'fs';
import path from 'path'; // Importando o módulo path para manipulação de diretórios

export async function downloadImage(imageUrl, filePath) {
    try {
        const response = await fetch(imageUrl, {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
            }
        });

        if (!response.ok) {
            // Detectar se é erro 404 (imagem não encontrada no CDN)
            if (response.status === 404) {
                throw new Error(`Failed to fetch ${imageUrl}: Not Found`);
            }
            throw new Error(`Failed to fetch ${imageUrl}: ${response.statusText}`);
        }

        const buffer = await response.buffer();

        // Caminho do diretório onde a imagem será salva
        const dirPath = path.dirname(filePath);

        // Cria a pasta principal, se não existir
        if (!fs.existsSync(dirPath)) {
            fs.mkdirSync(dirPath);  // Cria o diretório
            console.log(`Diretório criado: ${dirPath}`);
        }

        // Salvando a imagem no caminho especificado
        fs.writeFileSync(filePath, buffer);
        //console.log(`Ima    gem baixada com sucesso: ${filePath}`);
        return filePath
    } catch (error) {
        console.error(`Erro ao baixar a imagem: ${error.message}`);
        throw error;
    }
}
