const fs = require('fs');
const path = require('path');

// Storage monitoring e tracking melhorado
let cleanupCount = 0;
let lastCleanupSize = 0;
let totalCleaned = 0;
let totalCleanedSize = 0;

interface StorageInfo {
    total: number;
    free: number;
    used: number;
    freePercent: number;
}

function getStorageInfo(): StorageInfo | null {
    try {
        const { execSync } = require('child_process');
        const os = require('os');
        
        // Detectar plataforma e usar comando apropriado
        if (os.platform() === 'win32') {
            // Windows: usar PowerShell para obter info de disco
            const drive = process.cwd().charAt(0); // C, D, etc
            const psCommand = `Get-WmiObject -Class Win32_LogicalDisk -Filter "DeviceID='${drive}:'" | Select-Object Size,FreeSpace | ConvertTo-Json`;
            const output = execSync(`powershell -Command "${psCommand}"`, { encoding: 'utf8' });
            
            const diskInfo = JSON.parse(output);
            const total = parseInt(diskInfo.Size);
            const free = parseInt(diskInfo.FreeSpace);
            const used = total - free;
            const freePercent = (free / total) * 100;
            
            return { total, free, used, freePercent };
        } else {
            // Linux/WSL: usar df command
            const output = execSync('df -h . | tail -1', { encoding: 'utf8' });
            const parts = output.trim().split(/\s+/);
            
            if (parts.length >= 4) {
                const total = parseSize(parts[1]);
                const used = parseSize(parts[2]);
                const free = parseSize(parts[3]);
                const freePercent = (free / total) * 100;
                
                return { total, free, used, freePercent };
            }
        }
    } catch (error) {
        // Fallback silencioso - não mostrar erro
        return null;
    }
    return null;
}

function parseSize(sizeStr: string): number {
    const num = parseFloat(sizeStr);
    const unit = sizeStr.slice(-1).toLowerCase();
    const multipliers = { 'k': 1024, 'm': 1024**2, 'g': 1024**3, 't': 1024**4 };
    return num * (multipliers[unit] || 1);
}

function formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

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

export function getMangaPathForSite(siteName: string, mangaName: string, publisher?: string): string {
    const basePath = getMangaBasePath();
    const sanitizedSiteName = siteName.replace(/[\\/:*?"<>|\.]/g, '-');
    const sanitizedMangaName = mangaName.replace(/[\\/:*?"<>|]/g, '-');
    
    const path = require('path');
    
    // Determinar publisher baseado no site se não fornecido
    const sitePublisherMap = {
        'ManhAstro': 'Gikamura',
        'Sussy Toons': 'Gikamura', 
        'SussyToons': 'Gikamura',
        'MangaLivre': 'Gikamura',
        'Seita Celestial': 'Gikamura'
    };
    
    const finalPublisher = publisher || sitePublisherMap[siteName] || 'Outros';
    const sanitizedPublisher = finalPublisher.replace(/[\\/:*?"<>|\.]/g, '-');
    
    return path.join(basePath, sanitizedPublisher, sanitizedSiteName, sanitizedMangaName);
}

function getCorrectTempDir(): string {
    const os = require('os');
    const path = require('path');
    
    // Se estivermos no WSL, tentar usar o diretório temp do Windows
    if (process.platform === 'linux' && process.env.WSL_DISTRO_NAME) {
        const windowsTempPaths = [
            '/mnt/c/Users/Admin/AppData/Local/Temp',
            '/mnt/c/Windows/Temp',
            process.env.TEMP && process.env.TEMP.replace(/\\/g, '/').replace(/^([A-Z]):/, '/mnt/$1').toLowerCase(),
            process.env.TMP && process.env.TMP.replace(/\\/g, '/').replace(/^([A-Z]):/, '/mnt/$1').toLowerCase()
        ].filter(Boolean);
        
        for (const tempPath of windowsTempPaths) {
            try {
                const fs = require('fs');
                if (fs.existsSync(tempPath)) {
                    return tempPath;
                }
            } catch (e) {
                continue;
            }
        }
    }
    
    // Fallback para o padrão do OS
    return os.tmpdir();
}

export function cleanTempFiles(): void {
    try {
        const tempDir = getCorrectTempDir();
        
        console.log(`🧹 [CLEANUP] Iniciando limpeza em: ${tempDir}`);
        
        // Primeiro, limpar arquivos temporários de download órfãos
        try {
            const { cleanupOrphanedTempFiles } = require('../download/images');
            const orphanResult = cleanupOrphanedTempFiles();
            if (orphanResult.cleaned > 0) {
                console.log(`🗑️ [CLEANUP] Arquivos órfãos de download: ${orphanResult.cleaned} (${formatBytes(orphanResult.totalSize)})`);
                totalCleaned += orphanResult.cleaned;
                totalCleanedSize += orphanResult.totalSize;
            }
        } catch (importError) {
            console.warn('⚠️ [CLEANUP] Não foi possível importar limpeza de orphaned files:', importError.message);
        }
        
        // Padrões expandidos e mais agressivos
        const patterns = [
            'node-compile-cache',
            'chrome_*',
            'puppeteer_*',
            'nodriver_*',
            // Padrões de imagem temporários
            '*Cap*',           
            '*.png',           
            '*.jpg',           
            '*.jpeg',          
            '*.webp',          // Adicionar WebP
            '*Arquiteto*',     
            '*_Cap*',          
            'tmp*',            
            'temp*',           
            // Padrões .tmp mais abrangentes
            '*.tmp',           
            '*-*-*-*-*.tmp',   // UUIDs
            '*guid*.tmp',      
            '*uuid*.tmp',
            'download_*.jpg',  // Nossos downloads temporários (temp dir)
            'download_*.png',  
            'download_*.jpeg',
            'download_*.webp',
            '.tmp_download_*', // Nossos downloads temporários (target dir)
            // Padrões do browser
            'scoped_dir*',
            'chrome-driver*',
            'chromium*',
            // Cache patterns
            '*cache*',
            '*Cache*'
        ];
        
        const items = fs.readdirSync(tempDir);
        let cleaned = 0;
        let totalSize = 0;
        
        items.forEach(item => {
            // Ignorar arquivos específicos do sistema
            const systemFiles = [
                'is-SBUAT.tmp',           // VSCode update files
                'CodeSetup-stable-',      // VSCode installers
                'node-compile-cache',     // Node.js cache em uso
                'vscode-',                // Outros arquivos VSCode
                'electron-',              // Electron apps
                'Microsoft',              // Arquivos Microsoft
                'Windows'                 // Arquivos Windows
            ];
            
            const isSystemFile = systemFiles.some(sysFile => item.includes(sysFile));
            if (isSystemFile) {
                return; // Pular arquivos do sistema sem tentar limpar
            }
            
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
                    if (item.endsWith('.tmp') && (e.code === 'EBUSY' || e.code === 'ENOTEMPTY' || e.code === 'EPERM')) {
                        // Não reportar arquivos .tmp em uso (muito comum no Windows)
                    } else {
                        // Reportar apenas erros inesperados
                        console.log(`⚠️ Não foi possível limpar: ${item} (${e.message})`);
                    }
                }
            }
        });
        
        // Atualizar contadores globais
        cleanupCount++;
        lastCleanupSize = totalSize;
        totalCleaned += cleaned;
        totalCleanedSize += totalSize;
        
        if (cleaned > 0) {
            console.log(`✅ [CLEANUP] Limpeza #${cleanupCount}: ${cleaned} itens (${formatBytes(totalSize)})`);
        }
        
        // Mostrar estatísticas totais periodicamente
        if (cleanupCount % 10 === 0) {
            console.log(`📊 [STATS] Total geral: ${totalCleaned} arquivos, ${formatBytes(totalCleanedSize)} liberados`);
        }
        
    } catch (e) {
        console.log('⚠️ Erro na limpeza de temp files:', e.message);
    }
}

// Função para obter estatísticas de limpeza
export function getCleanupStats() {
    return {
        cleanupCount,
        lastCleanupSize: formatBytes(lastCleanupSize),
        totalCleaned,
        totalCleanedSize: formatBytes(totalCleanedSize)
    };
}

// Nova função para limpeza de emergência (força remoção de todos os temp files)
export function emergencyCleanTempFiles(): void {
    try {
        console.log('🚨 [EMERGENCY] Iniciando limpeza de emergência...');
        const tempDir = getCorrectTempDir();
        
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

// Limpeza leve e rápida após cada capítulo (foco em browser/Chrome)
export function cleanupAfterChapter(): void {
    try {
        const tempDir = getCorrectTempDir();
        const fs = require('fs');
        let cleaned = 0;
        let totalSize = 0;
        
        // Padrões críticos para limpeza imediata após capítulo
        const criticalPatterns = [
            'uc_*',           // Chrome undetected instances (maior problema)
            'chrome_*',       // Chrome temporários
            'nodriver_*',     // nodriver temporários
            '*.tmp',          // Arquivos .tmp genéricos
            '.tmp_download_*' // Nossos downloads temporários
        ];
        
        const items = fs.readdirSync(tempDir);
        
        items.forEach(item => {
            const shouldClean = criticalPatterns.some(pattern => {
                const regex = new RegExp(pattern.replace(/\*/g, '.*'), 'i');
                return regex.test(item);
            });
            
            if (shouldClean) {
                try {
                    const itemPath = path.join(tempDir, item);
                    const stats = fs.statSync(itemPath);
                    
                    if (stats.isFile()) {
                        totalSize += stats.size;
                        fs.unlinkSync(itemPath);
                        cleaned++;
                    } else if (stats.isDirectory()) {
                        // Para diretórios uc_*, remover completamente
                        if (item.startsWith('uc_')) {
                            fs.rmSync(itemPath, { recursive: true, force: true });
                            cleaned++;
                        }
                    }
                } catch (e) {
                    // Ignorar arquivos em uso silenciosamente
                }
            }
        });
        
        if (cleaned > 0) {
            console.log(`🧹 [CAPÍTULO] Limpeza pós-capítulo: ${cleaned} itens (${formatBytes(totalSize)})`);
        }
        
    } catch (error) {
        // Limpeza silenciosa - não interromper download por erro de limpeza
    }
}

// Função para limpeza periódica (executar a cada N downloads)
let downloadCount = 0;
export function periodicCleanup(): void {
    downloadCount++;
    
    // Limpeza leve a cada capítulo (sempre)
    cleanupAfterChapter();
    
    // Limpar a cada 3 downloads (reduzido de 5)
    if (downloadCount % 3 === 0) {
        console.log(`🔄 Limpeza periódica (${downloadCount} downloads)...`);
        cleanTempFiles();
    }
    
    // Limpeza de emergência a cada 10 downloads (reduzido de 20)
    if (downloadCount % 10 === 0) {
        console.log(`🚨 Limpeza de emergência programada (${downloadCount} downloads)...`);
        emergencyCleanTempFiles();
    }
}

