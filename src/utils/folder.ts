const fs = require('fs');
const path = require('path');

export function deleteFolder(dirPath) {
    if (fs.existsSync(dirPath)) {
        fs.rmSync(dirPath, { recursive: true, force: true });
        console.log(`Deleted: ${dirPath}`);
    } else {
        console.log(`Folder not found: ${dirPath}`);
    }
}

export function getMangaBasePath(): string {
    // Carregar .env de forma mais segura
    try {
        const dotenv = require('dotenv');
        dotenv.config();
    } catch (e) {
        // Se dotenv não estiver disponível, continua sem erro
    }
    
    const mangaPath = process.env.MANGA_BASE_PATH || 'manga';
    return mangaPath;
}

export function cleanTempFiles(): void {
    try {
        const os = require('os');
        const tempDir = os.tmpdir();
        
        // Limpar arquivos específicos do Node.js e Chrome
        const patterns = [
            'node-compile-cache',
            'chrome_*',
            'puppeteer_*',
            'nodriver_*'
        ];
        
        const items = fs.readdirSync(tempDir);
        let cleaned = 0;
        
        items.forEach(item => {
            const shouldClean = patterns.some(pattern => 
                item.includes(pattern.replace('*', ''))
            );
            
            if (shouldClean) {
                try {
                    const itemPath = path.join(tempDir, item);
                    if (fs.statSync(itemPath).isDirectory()) {
                        fs.rmSync(itemPath, { recursive: true, force: true });
                    } else {
                        fs.unlinkSync(itemPath);
                    }
                    cleaned++;
                } catch (e) {
                    // Ignorar erros de arquivos em uso
                }
            }
        });
        
        if (cleaned > 0) {
            console.log(`🧹 Arquivos temp limpos: ${cleaned} itens`);
        }
    } catch (e) {
        // Falha silenciosa na limpeza
        console.log('⚠️ Erro na limpeza de temp files:', e.message);
    }
}

