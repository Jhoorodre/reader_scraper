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
        
        // Padrões expandidos para incluir arquivos de imagem temporários
        const patterns = [
            'node-compile-cache',
            'chrome_*',
            'puppeteer_*',
            'nodriver_*',
            // Novos padrões para arquivos de imagem temporários
            '*Cap*',           // Arquivos com "Cap" no nome
            '*.png',           // Imagens PNG temporárias
            '*.jpg',           // Imagens JPG temporárias
            '*.jpeg',          // Imagens JPEG temporárias
            '*Arquiteto*',     // Padrão específico para manga "Arquiteto de Dungeons"
            '*_Cap*',          // Arquivos com prefixo + "Cap"
            'tmp*',            // Arquivos temporários genéricos
            'temp*',           // Arquivos temporários genéricos
            // Novos padrões para arquivos .tmp bloqueados
            '*.tmp',           // Todos os arquivos .tmp
            '*-*-*-*-*.tmp',   // UUIDs .tmp (formato: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.tmp)
            '*guid*.tmp',      // Arquivos GUID temporários
            '*uuid*.tmp'       // Arquivos UUID temporários
        ];
        
        const items = fs.readdirSync(tempDir);
        let cleaned = 0;
        let totalSize = 0;
        
        items.forEach(item => {
            const shouldClean = patterns.some(pattern => {
                if (pattern.includes('*')) {
                    // Usar regex para patterns com wildcard
                    const regex = new RegExp(pattern.replace(/\*/g, '.*'), 'i');
                    return regex.test(item);
                } else {
                    return item.includes(pattern);
                }
            });
            
            if (shouldClean) {
                try {
                    const itemPath = path.join(tempDir, item);
                    const stats = fs.statSync(itemPath);
                    
                    // Calcular tamanho antes da remoção
                    if (stats.isFile()) {
                        totalSize += stats.size;
                    }
                    
                    if (stats.isDirectory()) {
                        fs.rmSync(itemPath, { recursive: true, force: true });
                    } else {
                        fs.unlinkSync(itemPath);
                    }
                    cleaned++;
                } catch (e) {
                    // Para arquivos .tmp bloqueados, ignorar silenciosamente
                    if (item.endsWith('.tmp') && (e.code === 'EBUSY' || e.code === 'ENOTEMPTY')) {
                        // Não reportar arquivos .tmp em uso (muito comum no Windows)
                    } else {
                        // Reportar outros erros de permissão
                        console.log(`⚠️ Não foi possível limpar: ${item} (${e.message})`);
                    }
                }
            }
        });
        
        if (cleaned > 0) {
            const sizeMB = (totalSize / 1024 / 1024).toFixed(2);
            console.log(`🧹 Limpeza completa: ${cleaned} itens removidos (${sizeMB}MB liberados)`);
        }
    } catch (e) {
        console.log('⚠️ Erro na limpeza de temp files:', e.message);
    }
}

// Nova função para limpeza de emergência (força remoção de todos os temp files)
export function emergencyCleanTempFiles(): void {
    try {
        const os = require('os');
        const tempDir = os.tmpdir();
        
        console.log('🚨 Iniciando limpeza de emergência...');
        
        const items = fs.readdirSync(tempDir);
        let cleaned = 0;
        let totalSize = 0;
        
        items.forEach(item => {
            // Limpeza mais agressiva - todos os arquivos suspeitos
            const isImageFile = /\.(png|jpg|jpeg|gif|webp)$/i.test(item);
            const isMangaRelated = /cap|capítulo|arquiteto|manga/i.test(item);
            const isTempFile = /^(tmp|temp|node|chrome|puppeteer|nodriver)/i.test(item);
            const isTmpFile = /\.tmp$/i.test(item);
            const isUuidTmpFile = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.tmp$/i.test(item);
            
            if (isImageFile || isMangaRelated || isTempFile || isTmpFile || isUuidTmpFile) {
                try {
                    const itemPath = path.join(tempDir, item);
                    const stats = fs.statSync(itemPath);
                    
                    if (stats.isFile()) {
                        totalSize += stats.size;
                        fs.unlinkSync(itemPath);
                        cleaned++;
                    } else if (stats.isDirectory()) {
                        fs.rmSync(itemPath, { recursive: true, force: true });
                        cleaned++;
                    }
                } catch (e) {
                    // Para arquivos .tmp, ignorar silenciosamente durante limpeza de emergência
                    if (item.endsWith('.tmp') && (e.code === 'EBUSY' || e.code === 'ENOTEMPTY')) {
                        // Ignorar arquivos .tmp em uso durante limpeza de emergência
                    }
                    // Continuar mesmo com outros erros
                }
            }
        });
        
        const sizeMB = (totalSize / 1024 / 1024).toFixed(2);
        console.log(`🧹 Limpeza de emergência concluída: ${cleaned} itens (${sizeMB}MB)`);
    } catch (e) {
        console.log('⚠️ Erro na limpeza de emergência:', e.message);
    }
}

// Função para configurar handlers de saída do processo
export function setupCleanupHandlers(): void {
    // Handler para saída normal
    process.on('exit', () => {
        console.log('🧹 Limpando arquivos temporários na saída...');
        cleanTempFiles();
    });
    
    // Handler para Ctrl+C (SIGINT)
    process.on('SIGINT', () => {
        console.log('\n🛑 Interrupção detectada (Ctrl+C) - limpando e saindo...');
        cleanTempFiles();
        process.exit(0);
    });
    
    // Handler para término do processo (SIGTERM)
    process.on('SIGTERM', () => {
        console.log('🛑 Término do processo detectado - limpando...');
        cleanTempFiles();
        process.exit(0);
    });
    
    // Handler para exceções não capturadas
    process.on('uncaughtException', (error) => {
        console.error('💥 Exceção não capturada:', error.message);
        console.log('🧹 Limpando arquivos temporários antes de sair...');
        cleanTempFiles();
        process.exit(1);
    });
    
    // Handler para promises rejeitadas não tratadas
    process.on('unhandledRejection', (reason, promise) => {
        console.error('💥 Promise rejeitada não tratada:', reason);
        console.log('🧹 Limpando arquivos temporários...');
        cleanTempFiles();
    });
    
    console.log('✅ Handlers de limpeza configurados');
}

// Função para limpeza periódica (executar a cada N downloads)
let downloadCount = 0;
export function periodicCleanup(): void {
    downloadCount++;
    
    // Limpar a cada 5 downloads
    if (downloadCount % 5 === 0) {
        console.log(`🔄 Limpeza periódica (${downloadCount} downloads)...`);
        cleanTempFiles();
    }
    
    // Limpeza de emergência a cada 20 downloads
    if (downloadCount % 20 === 0) {
        console.log(`🚨 Limpeza de emergência programada (${downloadCount} downloads)...`);
        emergencyCleanTempFiles();
    }
}

