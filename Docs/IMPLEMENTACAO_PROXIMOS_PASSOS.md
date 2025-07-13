# Implementação dos Próximos Passos

## 📋 Visão Geral

Este documento detalha como implementar as 4 melhorias prioritárias identificadas no roadmap:

1. **Melhorar Documentação** (criar .env.example, guias)
2. **Adicionar Health Checks**
3. **Implementar Verificação de Integridade das Imagens**
4. **Criar Interface Web para Monitoramento**

---

## 1. 📚 Melhorar Documentação

### **Objetivo**
Facilitar setup e configuração do projeto para novos usuários e ambientes.

### **1.1 Criar arquivo .env.example**

**Localização:** `c:\Projetos\Projetos-code\Meu PC\reader_scraper\.env.example`

```env
# Configuração do Proxy
PROXY_URL=https://proxy.webshare.io/api/v2/proxy/list/download/[SEU_TOKEN]/-/any/username/direct/-/
PROXY_USERNAME=seu_usuario
PROXY_PASSWORD=sua_senha

# Configuração do Chrome/Puppeteer
CHROME_PATH=/usr/bin/google-chrome
PUPPETEER_NO_SANDBOX=1

# Configuração de Logs
LOG_LEVEL=info

# Configuração de Download
DOWNLOAD_CONCURRENCY=5
CHAPTER_CONCURRENCY=2
MANGA_BASE_PATH=./manga

# Configuração do Servidor
PROXY_SERVER_PORT=3333
WEB_INTERFACE_PORT=8080

# Configuração de Timeouts (em milissegundos)
REQUEST_TIMEOUT=15000
DOWNLOAD_TIMEOUT=30000
PROXY_TIMEOUT=600000
```

### **1.2 Guias de Setup**

**Arquivo:** `c:\Projetos\Projetos-code\Meu PC\reader_scraper\Docs\SETUP_GUIDE.md`

#### **Conteúdo do Guia:**

- **Setup para Windows**
- **Setup para Linux**
- **Setup para Docker**
- **Configuração de Proxies**
- **Troubleshooting comum**
- **Variáveis de ambiente explicadas**

### **1.3 Scripts de Setup Automatizado**

**Windows:** `setup.bat`
```batch
@echo off
echo === Manga Scraper Setup ===
echo.

REM Verificar se Node.js está instalado
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Node.js não encontrado. Instale Node.js 18+ primeiro.
    pause
    exit /b 1
)

REM Verificar se Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python não encontrado. Instale Python 3.8+ primeiro.
    pause
    exit /b 1
)

echo [INFO] Instalando dependências Python...
pip install -r requirements.txt

echo [INFO] Instalando dependências Node.js...
npm install

echo [INFO] Copiando arquivo de configuração...
if not exist .env (
    copy .env.example .env
    echo [INFO] Arquivo .env criado. Configure suas variáveis antes de usar.
)

echo.
echo === Setup concluído! ===
echo 1. Configure o arquivo .env com suas credenciais
echo 2. Execute: python app.py (em um terminal)
echo 3. Execute: npx ts-node src/consumer/sussy.ts (em outro terminal)
pause
```

**Linux/Mac:** `setup.sh`
```bash
#!/bin/bash
echo "=== Manga Scraper Setup ==="
echo

# Verificar Node.js
if ! command -v node &> /dev/null; then
    echo "[ERRO] Node.js não encontrado. Instale Node.js 18+ primeiro."
    exit 1
fi

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "[ERRO] Python não encontrado. Instale Python 3.8+ primeiro."
    exit 1
fi

echo "[INFO] Instalando dependências Python..."
pip3 install -r requirements.txt

echo "[INFO] Instalando dependências Node.js..."
npm install

echo "[INFO] Copiando arquivo de configuração..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[INFO] Arquivo .env criado. Configure suas variáveis antes de usar."
fi

echo
echo "=== Setup concluído! ==="
echo "1. Configure o arquivo .env com suas credenciais"
echo "2. Execute: python3 app.py (em um terminal)"
echo "3. Execute: npx ts-node src/consumer/sussy.ts (em outro terminal)"
```

---

## 2. 🏥 Adicionar Health Checks

### **Objetivo**
Monitorar a saúde dos serviços e detectar problemas precocemente.

### **2.1 Health Check no Backend Python**

**Arquivo:** Modificar `app.py`

```python
from datetime import datetime
import requests

@app.route('/health', methods=['GET'])
def health_check():
    checks = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'services': {
            'driver': 'unknown',
            'proxy_list': 'unknown',
            'memory': 'unknown'
        },
        'metrics': {
            'uptime_seconds': 0,
            'requests_processed': 0
        }
    }
    
    # Verificar driver
    try:
        global driver
        if driver is not None:
            checks['services']['driver'] = 'healthy'
        else:
            checks['services']['driver'] = 'not_initialized'
    except Exception as e:
        checks['services']['driver'] = f'error: {str(e)}'
    
    # Verificar acesso à lista de proxies
    try:
        if 'BASE_URL_PROXY' in globals():
            response = requests.get(BASE_URL_PROXY, timeout=5)
            if response.status_code == 200:
                checks['services']['proxy_list'] = 'healthy'
            else:
                checks['services']['proxy_list'] = f'error: HTTP {response.status_code}'
        else:
            checks['services']['proxy_list'] = 'not_configured'
    except Exception as e:
        checks['services']['proxy_list'] = f'unreachable: {str(e)}'
    
    # Verificar memória
    import psutil
    memory_percent = psutil.virtual_memory().percent
    if memory_percent < 80:
        checks['services']['memory'] = 'healthy'
    elif memory_percent < 90:
        checks['services']['memory'] = 'warning'
    else:
        checks['services']['memory'] = 'critical'
    
    # Status geral
    unhealthy_services = [k for k, v in checks['services'].items() 
                         if not v.startswith('healthy')]
    
    if len(unhealthy_services) == 0:
        checks['status'] = 'healthy'
    elif len(unhealthy_services) <= 1:
        checks['status'] = 'degraded'
    else:
        checks['status'] = 'unhealthy'
    
    status_code = 200 if checks['status'] in ['healthy', 'degraded'] else 503
    return jsonify(checks), status_code

# Endpoint para métricas específicas
@app.route('/metrics', methods=['GET'])
def metrics():
    import psutil
    
    return jsonify({
        'system': {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'uptime_seconds': time.time() - start_time
        },
        'process': {
            'memory_mb': psutil.Process().memory_info().rss / 1024 / 1024,
            'cpu_percent': psutil.Process().cpu_percent(),
            'threads': psutil.Process().num_threads()
        }
    })
```

### **2.2 Health Check no Frontend TypeScript**

**Arquivo:** `src/services/health_checker.ts`

```typescript
import axios from 'axios';

export interface HealthStatus {
    service: string;
    status: 'healthy' | 'degraded' | 'unhealthy';
    timestamp: string;
    details?: any;
}

export class HealthChecker {
    private static readonly PROXY_SERVER_URL = 'http://localhost:3333';
    
    static async checkProxyService(): Promise<HealthStatus> {
        try {
            const response = await axios.get(`${this.PROXY_SERVER_URL}/health`, {
                timeout: 5000
            });
            
            return {
                service: 'proxy_server',
                status: response.data.status,
                timestamp: new Date().toISOString(),
                details: response.data
            };
        } catch (error) {
            return {
                service: 'proxy_server',
                status: 'unhealthy',
                timestamp: new Date().toISOString(),
                details: { error: error.message }
            };
        }
    }
    
    static async checkProxyManager(): Promise<HealthStatus> {
        try {
            const { ProxyManager } = await import('./proxy_manager');
            await ProxyManager.getProxyList();
            
            return {
                service: 'proxy_manager',
                status: 'healthy',
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            return {
                service: 'proxy_manager',
                status: 'unhealthy',
                timestamp: new Date().toISOString(),
                details: { error: error.message }
            };
        }
    }
    
    static async checkDiskSpace(): Promise<HealthStatus> {
        try {
            const fs = await import('fs');
            const path = await import('path');
            
            const stats = fs.statSync('./manga');
            const free = fs.statSync('.').size; // Simplificado
            
            return {
                service: 'disk_space',
                status: 'healthy', // Implementar lógica real
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            return {
                service: 'disk_space',
                status: 'unhealthy',
                timestamp: new Date().toISOString(),
                details: { error: error.message }
            };
        }
    }
    
    static async checkAllServices(): Promise<HealthStatus[]> {
        const checks = await Promise.allSettled([
            this.checkProxyService(),
            this.checkProxyManager(),
            this.checkDiskSpace()
        ]);
        
        return checks.map(result => 
            result.status === 'fulfilled' ? result.value : {
                service: 'unknown',
                status: 'unhealthy' as const,
                timestamp: new Date().toISOString(),
                details: { error: 'Check failed' }
            }
        );
    }
}
```

---

## 3. 🔍 Verificação de Integridade das Imagens

### **Objetivo**
Garantir que as imagens baixadas estão íntegras e não corrompidas.

### **3.1 Validador de Imagens**

**Arquivo:** `src/utils/image_validator.ts`

```typescript
import sharp from 'sharp';
import fs from 'fs';
import path from 'path';

export interface ImageValidationResult {
    valid: boolean;
    error?: string;
    metadata?: {
        width?: number;
        height?: number;
        format?: string;
        size: number;
    };
}

export interface ChapterValidationResult {
    totalImages: number;
    validImages: number;
    invalidImages: Array<{
        file: string;
        error: string;
    }>;
    completeness: number; // Percentual de imagens válidas
}

export class ImageValidator {
    private static readonly MIN_FILE_SIZE = 1024; // 1KB
    private static readonly MIN_DIMENSIONS = { width: 50, height: 50 };
    private static readonly MAX_DIMENSIONS = { width: 5000, height: 8000 };
    
    static async validateImage(filePath: string): Promise<ImageValidationResult> {
        try {
            // Verificar se o arquivo existe
            if (!fs.existsSync(filePath)) {
                return { valid: false, error: 'File not found' };
            }
            
            // Verificar tamanho do arquivo
            const stats = fs.statSync(filePath);
            if (stats.size < this.MIN_FILE_SIZE) {
                return { 
                    valid: false, 
                    error: `File too small: ${stats.size} bytes`,
                    metadata: { size: stats.size }
                };
            }
            
            // Verificar se é uma imagem válida
            const metadata = await sharp(filePath).metadata();
            
            const result: ImageValidationResult = {
                valid: true,
                metadata: {
                    width: metadata.width,
                    height: metadata.height,
                    format: metadata.format,
                    size: stats.size
                }
            };
            
            // Verificar dimensões
            if (!metadata.width || !metadata.height) {
                return { ...result, valid: false, error: 'Invalid image dimensions' };
            }
            
            if (metadata.width < this.MIN_DIMENSIONS.width || 
                metadata.height < this.MIN_DIMENSIONS.height) {
                return { 
                    ...result, 
                    valid: false, 
                    error: `Dimensions too small: ${metadata.width}x${metadata.height}` 
                };
            }
            
            if (metadata.width > this.MAX_DIMENSIONS.width || 
                metadata.height > this.MAX_DIMENSIONS.height) {
                return { 
                    ...result, 
                    valid: false, 
                    error: `Dimensions too large: ${metadata.width}x${metadata.height}` 
                };
            }
            
            // Verificar se não é um pixel de erro (comum em alguns sites)
            if (metadata.width === 1 && metadata.height === 1) {
                return { 
                    ...result, 
                    valid: false, 
                    error: 'Likely error page pixel' 
                };
            }
            
            // Verificar ratio muito estranho (provavelmente erro)
            const ratio = metadata.width / metadata.height;
            if (ratio > 10 || ratio < 0.1) {
                return { 
                    ...result, 
                    valid: false, 
                    error: `Suspicious aspect ratio: ${ratio.toFixed(2)}` 
                };
            }
            
            return result;
            
        } catch (error) {
            return { 
                valid: false, 
                error: `Validation error: ${error.message}` 
            };
        }
    }
    
    static async validateChapterImages(chapterPath: string): Promise<ChapterValidationResult> {
        if (!fs.existsSync(chapterPath)) {
            return {
                totalImages: 0,
                validImages: 0,
                invalidImages: [],
                completeness: 0
            };
        }
        
        const imageExtensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif'];
        const files = fs.readdirSync(chapterPath).filter(file => {
            const ext = path.extname(file).toLowerCase();
            return imageExtensions.includes(ext);
        });
        
        const results: ChapterValidationResult = {
            totalImages: files.length,
            validImages: 0,
            invalidImages: [],
            completeness: 0
        };
        
        for (const file of files) {
            const filePath = path.join(chapterPath, file);
            const validation = await this.validateImage(filePath);
            
            if (validation.valid) {
                results.validImages++;
            } else {
                results.invalidImages.push({
                    file: file,
                    error: validation.error || 'Unknown error'
                });
            }
        }
        
        results.completeness = results.totalImages > 0 
            ? (results.validImages / results.totalImages) * 100 
            : 0;
        
        return results;
    }
    
    static async validateMangaDirectory(mangaPath: string): Promise<{
        totalChapters: number;
        validChapters: number;
        chapterResults: Array<{
            chapter: string;
            validation: ChapterValidationResult;
        }>;
    }> {
        if (!fs.existsSync(mangaPath)) {
            return {
                totalChapters: 0,
                validChapters: 0,
                chapterResults: []
            };
        }
        
        const chapters = fs.readdirSync(mangaPath).filter(item => {
            const chapterPath = path.join(mangaPath, item);
            return fs.statSync(chapterPath).isDirectory();
        });
        
        const results = {
            totalChapters: chapters.length,
            validChapters: 0,
            chapterResults: [] as Array<{
                chapter: string;
                validation: ChapterValidationResult;
            }>
        };
        
        for (const chapter of chapters) {
            const chapterPath = path.join(mangaPath, chapter);
            const validation = await this.validateChapterImages(chapterPath);
            
            results.chapterResults.push({
                chapter: chapter,
                validation: validation
            });
            
            // Considerar válido se tem pelo menos 80% das imagens válidas
            if (validation.completeness >= 80) {
                results.validChapters++;
            }
        }
        
        return results;
    }
}
```

### **3.2 Integração no Sistema de Download**

**Modificar:** `src/consumer/sussy.ts` (e outros consumers)

```typescript
// Adicionar no início do arquivo
import { ImageValidator } from '../utils/image_validator';

// Modificar a seção de download das páginas
await Bluebird.map(pages.pages, async (pageUrl, pageIndex) => {
    const capitulo = (pageIndex + 1) <= 9 ? `0${pageIndex + 1}` : `${pageIndex + 1}`;
    const imagePath = path.join(dirPath, `${capitulo}.jpg`);
    
    console.log(`Baixando Página ${capitulo}: ${pageUrl}`);
    
    try {
        // Download da imagem
        await downloadImage(pageUrl, imagePath);
        
        // Validar a imagem baixada
        const validation = await ImageValidator.validateImage(imagePath);
        
        if (!validation.valid) {
            console.error(`❌ Imagem inválida ${capitulo}: ${validation.error}`);
            fs.appendFileSync(reportFile, 
                `Erro na página ${capitulo}: ${validation.error}\n`);
            
            // Remover arquivo inválido
            if (fs.existsSync(imagePath)) {
                fs.unlinkSync(imagePath);
            }
            
            chapterSuccess = false;
        } else {
            const { width, height, size } = validation.metadata!;
            console.log(`✅ Página ${capitulo} válida: ${width}x${height} (${(size/1024).toFixed(1)}KB)`);
        }
        
    } catch (error) {
        console.error(`Erro ao baixar a Página ${capitulo}: ${error.message}`);
        chapterSuccess = false;
    }
}, { concurrency: 5 });

// Validação final do capítulo
const chapterValidation = await ImageValidator.validateChapterImages(dirPath);
console.log(`\n📊 Validação do Capítulo ${chapter.number}:`);
console.log(`   Total: ${chapterValidation.totalImages} imagens`);
console.log(`   Válidas: ${chapterValidation.validImages} imagens`);
console.log(`   Completude: ${chapterValidation.completeness.toFixed(1)}%`);

if (chapterValidation.completeness < 80) {
    console.log(`⚠️  Capítulo incompleto (< 80% válido)`);
    chapterSuccess = false;
}

// Registrar no relatório
fs.appendFileSync(reportFile, 
    `Capítulo ${chapter.number}: ${chapterValidation.validImages}/${chapterValidation.totalImages} imagens válidas (${chapterValidation.completeness.toFixed(1)}%)\n`);

if (chapterValidation.invalidImages.length > 0) {
    fs.appendFileSync(reportFile, `Imagens com problema:\n`);
    chapterValidation.invalidImages.forEach(img => {
        fs.appendFileSync(reportFile, `  - ${img.file}: ${img.error}\n`);
    });
}
```

---

## 4. 🌐 Interface Web para Monitoramento

### **Objetivo**
Criar dashboard web para monitorar o sistema e visualizar downloads.

### **4.1 Estrutura do Projeto Web**

```
web/
├── public/
│   ├── index.html
│   ├── css/
│   │   └── dashboard.css
│   ├── js/
│   │   ├── dashboard.js
│   │   └── utils.js
│   └── assets/
│       └── favicon.ico
└── server/
    └── web_server.ts
```

### **4.2 Servidor Web (Backend)**

**Arquivo:** `src/web/web_server.ts`

```typescript
import express from 'express';
import path from 'path';
import fs from 'fs';
import { HealthChecker } from '../services/health_checker';
import { ImageValidator } from '../utils/image_validator';

const app = express();
const PORT = process.env.WEB_INTERFACE_PORT || 8080;

// Servir arquivos estáticos
app.use(express.static(path.join(__dirname, '../../web/public')));
app.use(express.json());

// API para status do sistema
app.get('/api/status', async (req, res) => {
    try {
        const healthChecks = await HealthChecker.checkAllServices();
        
        res.json({
            timestamp: new Date().toISOString(),
            overall_status: healthChecks.every(h => h.status === 'healthy') ? 'healthy' : 'degraded',
            services: healthChecks,
            system: {
                uptime: process.uptime(),
                memory: process.memoryUsage(),
                platform: process.platform,
                node_version: process.version
            }
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// API para listar mangás
app.get('/api/mangas', async (req, res) => {
    try {
        const mangaPath = './manga';
        if (!fs.existsSync(mangaPath)) {
            return res.json([]);
        }
        
        const mangas = fs.readdirSync(mangaPath).filter(item => {
            const itemPath = path.join(mangaPath, item);
            return fs.statSync(itemPath).isDirectory();
        });
        
        const mangaData = await Promise.all(mangas.map(async (manga) => {
            const mangaDir = path.join(mangaPath, manga);
            const chapters = fs.readdirSync(mangaDir).filter(item => {
                const chapterPath = path.join(mangaDir, item);
                return fs.statSync(chapterPath).isDirectory();
            });
            
            // Validar alguns capítulos para estatísticas
            const validationSample = await Promise.all(
                chapters.slice(0, 3).map(async (chapter) => {
                    const chapterPath = path.join(mangaDir, chapter);
                    return await ImageValidator.validateChapterImages(chapterPath);
                })
            );
            
            const avgCompleteness = validationSample.length > 0
                ? validationSample.reduce((sum, v) => sum + v.completeness, 0) / validationSample.length
                : 0;
            
            return {
                name: manga,
                chapters: chapters.length,
                last_modified: fs.statSync(mangaDir).mtime,
                avg_completeness: avgCompleteness
            };
        }));
        
        res.json(mangaData);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// API para detalhes de um mangá específico
app.get('/api/mangas/:mangaName', async (req, res) => {
    try {
        const mangaName = decodeURIComponent(req.params.mangaName);
        const mangaPath = path.join('./manga', mangaName);
        
        if (!fs.existsSync(mangaPath)) {
            return res.status(404).json({ error: 'Manga not found' });
        }
        
        const validation = await ImageValidator.validateMangaDirectory(mangaPath);
        
        res.json({
            name: mangaName,
            path: mangaPath,
            validation: validation,
            last_modified: fs.statSync(mangaPath).mtime
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// API para logs recentes
app.get('/api/logs', (req, res) => {
    try {
        const logFiles = ['download_report.txt', 'url_fails.txt'].filter(file => 
            fs.existsSync(file)
        );
        
        const logs = logFiles.map(file => {
            const content = fs.readFileSync(file, 'utf8');
            const lines = content.split('\n').filter(line => line.trim());
            
            return {
                file: file,
                lines: lines.slice(-50), // Últimas 50 linhas
                total_lines: lines.length,
                last_modified: fs.statSync(file).mtime
            };
        });
        
        res.json(logs);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// API para limpar logs
app.post('/api/logs/clear', (req, res) => {
    try {
        const logFiles = ['download_report.txt', 'url_fails.txt'];
        
        logFiles.forEach(file => {
            if (fs.existsSync(file)) {
                fs.writeFileSync(file, '');
            }
        });
        
        res.json({ success: true, message: 'Logs cleared' });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Iniciar servidor
app.listen(PORT, () => {
    console.log(`🌐 Web interface disponível em http://localhost:${PORT}`);
});

export { app };
```

### **4.3 Interface Web (Frontend)**

**Arquivo:** `web/public/index.html`

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Manga Scraper Dashboard</title>
    <link rel="stylesheet" href="css/dashboard.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
</head>
<body>
    <div class="dashboard">
        <header class="header">
            <h1><i class="fas fa-book"></i> Manga Scraper Dashboard</h1>
            <div class="last-update">
                Última atualização: <span id="last-update">--</span>
            </div>
        </header>

        <div class="main-content">
            <!-- Status Panel -->
            <section class="panel status-panel">
                <h2><i class="fas fa-heartbeat"></i> Status do Sistema</h2>
                <div id="system-status" class="status-grid">
                    <div class="status-loading">Carregando...</div>
                </div>
            </section>

            <!-- Manga List Panel -->
            <section class="panel manga-panel">
                <h2><i class="fas fa-list"></i> Mangás Baixados</h2>
                <div class="panel-controls">
                    <button onclick="refreshMangas()" class="btn btn-primary">
                        <i class="fas fa-sync"></i> Atualizar
                    </button>
                </div>
                <div id="manga-list" class="manga-grid">
                    <div class="loading">Carregando mangás...</div>
                </div>
            </section>

            <!-- Logs Panel -->
            <section class="panel logs-panel">
                <h2><i class="fas fa-file-alt"></i> Logs Recentes</h2>
                <div class="panel-controls">
                    <button onclick="refreshLogs()" class="btn btn-secondary">
                        <i class="fas fa-sync"></i> Atualizar
                    </button>
                    <button onclick="clearLogs()" class="btn btn-danger">
                        <i class="fas fa-trash"></i> Limpar Logs
                    </button>
                </div>
                <div id="logs-container" class="logs-container">
                    <div class="loading">Carregando logs...</div>
                </div>
            </section>

            <!-- Controls Panel -->
            <section class="panel controls-panel">
                <h2><i class="fas fa-cogs"></i> Controles</h2>
                <div class="controls-grid">
                    <button onclick="refreshAll()" class="btn btn-primary">
                        <i class="fas fa-sync-alt"></i> Atualizar Tudo
                    </button>
                    <button onclick="downloadStatus()" class="btn btn-info">
                        <i class="fas fa-download"></i> Status Downloads
                    </button>
                    <button onclick="systemInfo()" class="btn btn-secondary">
                        <i class="fas fa-info-circle"></i> Info Sistema
                    </button>
                </div>
            </section>
        </div>
    </div>

    <!-- Modal para detalhes -->
    <div id="modal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <div id="modal-body"></div>
        </div>
    </div>

    <script src="js/utils.js"></script>
    <script src="js/dashboard.js"></script>
</body>
</html>
```

### **4.4 Estilos CSS**

**Arquivo:** `web/public/css/dashboard.css`

```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    color: #333;
}

.dashboard {
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px;
}

.header {
    background: white;
    padding: 20px;
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    margin-bottom: 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.header h1 {
    color: #4a5568;
    font-size: 2rem;
}

.header h1 i {
    color: #667eea;
    margin-right: 10px;
}

.last-update {
    color: #718096;
    font-size: 0.9rem;
}

.main-content {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 20px;
}

.panel {
    background: white;
    border-radius: 10px;
    padding: 20px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

.panel h2 {
    color: #4a5568;
    margin-bottom: 15px;
    font-size: 1.3rem;
}

.panel h2 i {
    color: #667eea;
    margin-right: 8px;
}

.panel-controls {
    margin-bottom: 15px;
    display: flex;
    gap: 10px;
}

.btn {
    padding: 8px 16px;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    font-size: 0.9rem;
    transition: all 0.2s;
    display: inline-flex;
    align-items: center;
    gap: 5px;
}

.btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

.btn-primary {
    background: #4299e1;
    color: white;
}

.btn-secondary {
    background: #718096;
    color: white;
}

.btn-danger {
    background: #e53e3e;
    color: white;
}

.btn-info {
    background: #38b2ac;
    color: white;
}

.status-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 15px;
}

.status-item {
    padding: 15px;
    border-radius: 8px;
    text-align: center;
    transition: all 0.2s;
}

.status-item:hover {
    transform: scale(1.02);
}

.status-healthy {
    background: #c6f6d5;
    border-left: 4px solid #38a169;
}

.status-degraded {
    background: #feebc8;
    border-left: 4px solid #ed8936;
}

.status-unhealthy {
    background: #fed7d7;
    border-left: 4px solid #e53e3e;
}

.status-item h3 {
    margin-bottom: 5px;
    color: #2d3748;
}

.status-item .status-value {
    font-size: 1.2rem;
    font-weight: bold;
}

.manga-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 15px;
}

.manga-item {
    padding: 15px;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    transition: all 0.2s;
    cursor: pointer;
}

.manga-item:hover {
    border-color: #667eea;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.manga-item h3 {
    color: #4a5568;
    margin-bottom: 8px;
    font-size: 1rem;
}

.manga-stats {
    display: flex;
    justify-content: space-between;
    color: #718096;
    font-size: 0.85rem;
}

.completeness-bar {
    width: 100%;
    height: 8px;
    background: #e2e8f0;
    border-radius: 4px;
    margin: 8px 0;
    overflow: hidden;
}

.completeness-fill {
    height: 100%;
    background: linear-gradient(90deg, #38a169, #68d391);
    transition: width 0.3s;
}

.logs-container {
    max-height: 400px;
    overflow-y: auto;
    background: #f7fafc;
    border-radius: 5px;
    padding: 10px;
}

.log-file {
    margin-bottom: 20px;
}

.log-file h4 {
    color: #4a5568;
    margin-bottom: 8px;
    font-size: 0.9rem;
}

.log-line {
    font-family: 'Courier New', monospace;
    font-size: 0.8rem;
    color: #2d3748;
    margin: 2px 0;
    padding: 2px 5px;
    border-radius: 3px;
}

.log-line:hover {
    background: #edf2f7;
}

.controls-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 10px;
}

.loading {
    text-align: center;
    color: #718096;
    padding: 20px;
}

.modal {
    display: none;
    position: fixed;
    z-index: 1000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0,0,0,0.5);
}

.modal-content {
    background-color: white;
    margin: 5% auto;
    padding: 20px;
    border-radius: 10px;
    width: 80%;
    max-width: 600px;
    max-height: 80%;
    overflow-y: auto;
}

.close {
    color: #aaa;
    float: right;
    font-size: 28px;
    font-weight: bold;
    cursor: pointer;
}

.close:hover {
    color: #000;
}

@media (max-width: 768px) {
    .main-content {
        grid-template-columns: 1fr;
    }
    
    .header {
        flex-direction: column;
        gap: 10px;
        text-align: center;
    }
    
    .status-grid,
    .manga-grid {
        grid-template-columns: 1fr;
    }
}
```

### **4.5 JavaScript do Dashboard**

**Arquivo:** `web/public/js/dashboard.js`

```javascript
let refreshInterval;

// Inicializar dashboard
document.addEventListener('DOMContentLoaded', function() {
    refreshAll();
    startAutoRefresh();
});

function startAutoRefresh() {
    // Atualizar a cada 30 segundos
    refreshInterval = setInterval(() => {
        refreshStatus();
        updateLastUpdate();
    }, 30000);
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
}

function updateLastUpdate() {
    document.getElementById('last-update').textContent = new Date().toLocaleString('pt-BR');
}

async function refreshAll() {
    await Promise.all([
        refreshStatus(),
        refreshMangas(),
        refreshLogs()
    ]);
    updateLastUpdate();
}

async function refreshStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        displaySystemStatus(data);
    } catch (error) {
        console.error('Erro ao carregar status:', error);
        displayError('system-status', 'Erro ao carregar status do sistema');
    }
}

function displaySystemStatus(data) {
    const container = document.getElementById('system-status');
    const overallStatus = data.overall_status;
    
    let html = `
        <div class="status-item status-${overallStatus}">
            <h3>Status Geral</h3>
            <div class="status-value">${getStatusIcon(overallStatus)} ${overallStatus.toUpperCase()}</div>
        </div>
    `;
    
    data.services.forEach(service => {
        html += `
            <div class="status-item status-${service.status}" onclick="showServiceDetails('${service.service}', ${JSON.stringify(service).replace(/"/g, '&quot;')})">
                <h3>${formatServiceName(service.service)}</h3>
                <div class="status-value">${getStatusIcon(service.status)} ${service.status.toUpperCase()}</div>
            </div>
        `;
    });
    
    // Adicionar métricas do sistema
    if (data.system) {
        const uptimeHours = Math.floor(data.system.uptime / 3600);
        const memoryMB = Math.round(data.system.memory.rss / 1024 / 1024);
        
        html += `
            <div class="status-item status-healthy">
                <h3>Uptime</h3>
                <div class="status-value">${uptimeHours}h</div>
            </div>
            <div class="status-item status-healthy">
                <h3>Memória</h3>
                <div class="status-value">${memoryMB}MB</div>
            </div>
        `;
    }
    
    container.innerHTML = html;
}

async function refreshMangas() {
    try {
        const response = await fetch('/api/mangas');
        const mangas = await response.json();
        displayMangas(mangas);
    } catch (error) {
        console.error('Erro ao carregar mangás:', error);
        displayError('manga-list', 'Erro ao carregar lista de mangás');
    }
}

function displayMangas(mangas) {
    const container = document.getElementById('manga-list');
    
    if (mangas.length === 0) {
        container.innerHTML = '<div class="loading">Nenhum mangá encontrado</div>';
        return;
    }
    
    let html = '';
    mangas.forEach(manga => {
        const completeness = Math.round(manga.avg_completeness);
        const lastModified = new Date(manga.last_modified).toLocaleDateString('pt-BR');
        
        html += `
            <div class="manga-item" onclick="showMangaDetails('${manga.name}')">
                <h3>${manga.name}</h3>
                <div class="manga-stats">
                    <span>${manga.chapters} capítulos</span>
                    <span>${lastModified}</span>
                </div>
                <div class="completeness-bar">
                    <div class="completeness-fill" style="width: ${completeness}%"></div>
                </div>
                <div style="text-align: center; font-size: 0.8rem; color: #718096;">
                    ${completeness}% íntegro
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

async function refreshLogs() {
    try {
        const response = await fetch('/api/logs');
        const logs = await response.json();
        displayLogs(logs);
    } catch (error) {
        console.error('Erro ao carregar logs:', error);
        displayError('logs-container', 'Erro ao carregar logs');
    }
}

function displayLogs(logs) {
    const container = document.getElementById('logs-container');
    
    if (logs.length === 0) {
        container.innerHTML = '<div class="loading">Nenhum log encontrado</div>';
        return;
    }
    
    let html = '';
    logs.forEach(log => {
        html += `
            <div class="log-file">
                <h4>${log.file} (${log.total_lines} linhas)</h4>
                ${log.lines.map(line => `<div class="log-line">${escapeHtml(line)}</div>`).join('')}
            </div>
        `;
    });
    
    container.innerHTML = html;
}

async function clearLogs() {
    if (!confirm('Tem certeza que deseja limpar todos os logs?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/logs/clear', { method: 'POST' });
        const result = await response.json();
        
        if (result.success) {
            alert('Logs limpos com sucesso!');
            refreshLogs();
        } else {
            alert('Erro ao limpar logs');
        }
    } catch (error) {
        console.error('Erro ao limpar logs:', error);
        alert('Erro ao limpar logs');
    }
}

async function showMangaDetails(mangaName) {
    try {
        const response = await fetch(`/api/mangas/${encodeURIComponent(mangaName)}`);
        const manga = await response.json();
        
        let html = `
            <h2>${manga.name}</h2>
            <p><strong>Caminho:</strong> ${manga.path}</p>
            <p><strong>Última modificação:</strong> ${new Date(manga.last_modified).toLocaleString('pt-BR')}</p>
            
            <h3>Validação dos Capítulos</h3>
            <p><strong>Total:</strong> ${manga.validation.totalChapters} capítulos</p>
            <p><strong>Válidos:</strong> ${manga.validation.validChapters} capítulos</p>
            
            <div style="max-height: 300px; overflow-y: auto; margin-top: 15px;">
        `;
        
        manga.validation.chapterResults.forEach(result => {
            const completeness = Math.round(result.validation.completeness);
            const statusClass = completeness >= 80 ? 'status-healthy' : 
                              completeness >= 50 ? 'status-degraded' : 'status-unhealthy';
            
            html += `
                <div class="status-item ${statusClass}" style="margin-bottom: 10px;">
                    <h4>${result.chapter}</h4>
                    <p>${result.validation.validImages}/${result.validation.totalImages} imagens (${completeness}%)</p>
                    ${result.validation.invalidImages.length > 0 ? 
                        `<details>
                            <summary>Problemas (${result.validation.invalidImages.length})</summary>
                            ${result.validation.invalidImages.map(img => 
                                `<div style="font-size: 0.8rem;">${img.file}: ${img.error}</div>`
                            ).join('')}
                        </details>` : ''
                    }
                </div>
            `;
        });
        
        html += '</div>';
        
        showModal(html);
    } catch (error) {
        console.error('Erro ao carregar detalhes do mangá:', error);
        alert('Erro ao carregar detalhes do mangá');
    }
}

function showServiceDetails(serviceName, serviceData) {
    let html = `
        <h2>Detalhes do Serviço: ${formatServiceName(serviceName)}</h2>
        <p><strong>Status:</strong> ${getStatusIcon(serviceData.status)} ${serviceData.status.toUpperCase()}</p>
        <p><strong>Timestamp:</strong> ${new Date(serviceData.timestamp).toLocaleString('pt-BR')}</p>
    `;
    
    if (serviceData.details) {
        html += `
            <h3>Detalhes Técnicos</h3>
            <pre style="background: #f7fafc; padding: 10px; border-radius: 5px; overflow-x: auto;">${JSON.stringify(serviceData.details, null, 2)}</pre>
        `;
    }
    
    showModal(html);
}

function showModal(content) {
    document.getElementById('modal-body').innerHTML = content;
    document.getElementById('modal').style.display = 'block';
}

function closeModal() {
    document.getElementById('modal').style.display = 'none';
}

// Fechar modal clicando fora
window.onclick = function(event) {
    const modal = document.getElementById('modal');
    if (event.target === modal) {
        closeModal();
    }
}

function displayError(containerId, message) {
    document.getElementById(containerId).innerHTML = `
        <div style="color: #e53e3e; text-align: center; padding: 20px;">
            <i class="fas fa-exclamation-triangle"></i> ${message}
        </div>
    `;
}

// Funções auxiliares
function getStatusIcon(status) {
    switch(status) {
        case 'healthy': return '<i class="fas fa-check-circle" style="color: #38a169;"></i>';
        case 'degraded': return '<i class="fas fa-exclamation-triangle" style="color: #ed8936;"></i>';
        case 'unhealthy': return '<i class="fas fa-times-circle" style="color: #e53e3e;"></i>';
        default: return '<i class="fas fa-question-circle" style="color: #718096;"></i>';
    }
}

function formatServiceName(serviceName) {
    const names = {
        'proxy_server': 'Servidor Proxy',
        'proxy_manager': 'Gerenciador de Proxy',
        'disk_space': 'Espaço em Disco'
    };
    return names[serviceName] || serviceName;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Funções dos botões de controle
function downloadStatus() {
    alert('Funcionalidade em desenvolvimento');
}

function systemInfo() {
    refreshStatus().then(() => {
        // O status já mostra as informações do sistema
        alert('Informações do sistema atualizadas no painel de status');
    });
}
```

### **4.6 Script de Inicialização**

**Arquivo:** `src/web/start_web.ts`

```typescript
#!/usr/bin/env ts-node

import { app } from './web_server';

console.log('🚀 Iniciando interface web do Manga Scraper...');
console.log('📍 Acesse: http://localhost:8080');
console.log('📖 Documentação: ./Docs/');
console.log('⭐ Para parar: Ctrl+C');
```

---

## 🚀 Ordem de Implementação Recomendada

### **Prioridade 1: Documentação**
1. Criar `.env.example`
2. Criar `SETUP_GUIDE.md`
3. Criar scripts `setup.bat` e `setup.sh`

### **Prioridade 2: Health Checks**
1. Implementar endpoints no `app.py`
2. Criar `HealthChecker` class
3. Adicionar dependência `psutil` ao `requirements.txt`

### **Prioridade 3: Validação de Imagens**
1. Implementar `ImageValidator` class
2. Integrar nos consumers existentes
3. Adicionar `sharp` ao `package.json`

### **Prioridade 4: Interface Web**
1. Criar estrutura de pastas
2. Implementar servidor web
3. Criar interface HTML/CSS/JS
4. Integrar com APIs existentes

---

## 📦 Dependências Adicionais Necessárias

### **Python (requirements.txt)**
```
psutil>=5.9.0
```

### **Node.js (package.json)**
```json
{
  "dependencies": {
    "sharp": "^0.32.6",
    "express": "^4.18.2"
  }
}
```

---

## 🔄 Atualização do Roadmap

Após implementar essas funcionalidades, atualizar o `ROADMAP.md` marcando como concluído:

- [x] Melhorar documentação (criar .env.example, guias)
- [x] Adicionar health checks  
- [x] Implementar verificação de integridade das imagens
- [x] Criar interface web para monitoramento
