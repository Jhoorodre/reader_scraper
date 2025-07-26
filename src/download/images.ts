import fetch from 'node-fetch';
import fs from 'fs';
import path from 'path';
import os from 'os';
import crypto from 'crypto';

// Track de arquivos temporários ativos para limpeza
const activeTempFiles = new Set<string>();

export async function downloadImage(imageUrl, filePath) {
    let tempFilePath: string | null = null;
    
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

        // Cria a pasta principal, se não existir (recursivo para subpastas)
        if (!fs.existsSync(dirPath)) {
            fs.mkdirSync(dirPath, { recursive: true });
            console.log(`Diretório criado: ${dirPath}`);
        }

        // DOWNLOAD ATÔMICO: Usar mesmo drive que o destino para evitar EXDEV
        const targetDir = path.dirname(filePath);
        const fileExt = path.extname(filePath);
        const randomId = crypto.randomUUID();
        tempFilePath = path.join(targetDir, `.tmp_download_${randomId}${fileExt}`);
        
        // Track arquivo temporário
        activeTempFiles.add(tempFilePath);
        
        // Escrever no arquivo temporário primeiro
        fs.writeFileSync(tempFilePath, buffer);
        
        // Operação atômica: mover arquivo temporário para destino final
        fs.renameSync(tempFilePath, filePath);
        
        // Remove do tracking após sucesso
        activeTempFiles.delete(tempFilePath);
        tempFilePath = null;
        
        return filePath;
        
    } catch (error) {
        console.error(`Erro ao baixar a imagem: ${error.message}`);
        
        // Limpeza de arquivo temporário em caso de erro
        if (tempFilePath && fs.existsSync(tempFilePath)) {
            try {
                fs.unlinkSync(tempFilePath);
                activeTempFiles.delete(tempFilePath);
            } catch (cleanupError) {
                console.warn(`Erro ao limpar arquivo temporário ${tempFilePath}: ${cleanupError.message}`);
            }
        }
        
        throw error;
    }
}

// Função para limpar arquivos temporários órfãos
export function cleanupOrphanedTempFiles(): { cleaned: number; totalSize: number } {
    let cleaned = 0;
    let totalSize = 0;
    
    for (const tempFile of activeTempFiles) {
        try {
            if (fs.existsSync(tempFile)) {
                const stats = fs.statSync(tempFile);
                totalSize += stats.size;
                fs.unlinkSync(tempFile);
                cleaned++;
            }
            activeTempFiles.delete(tempFile);
        } catch (error) {
            console.warn(`Erro ao limpar arquivo temporário órfão ${tempFile}: ${error}`);
        }
    }
    
    return { cleaned, totalSize };
}

// Export do Set para monitoramento externo
export { activeTempFiles };
