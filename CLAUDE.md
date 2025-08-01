# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Prerequisites
- Python 3.x
- Node.js (22) and npm/yarn
- Chrome (for undetected-chromedriver)
- PM2 (for Python server auto-restart)

## Setup and Execution

### 1. Install Dependencies
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
npm install

# Install PM2 for process management (recommended)
npm install -g pm2
```

### 2. Python Proxy Service Setup
```bash
# Start Python proxy server with PM2 (recommended - auto-restart)
pm2 start app.py --name "manga-proxy" --interpreter python

# Alternative: Start directly (no auto-restart)
python app.py

# Check server status
pm2 status
pm2 logs manga-proxy -f
```

### 3. TypeScript Downloader Execution
```bash
# Single manga download
npx ts-node --transpileOnly src/consumer/sussy.ts

# Batch mode (multiple mangas from obra_urls.txt)
npx ts-node --transpileOnly src/consumer/sussy.ts urls

# Rentry mode (reprocess failures)
npx ts-node --transpileOnly src/consumer/sussy.ts rentry

# Other providers
npx ts-node --transpileOnly src/consumer/seita.ts
npx ts-node --transpileOnly src/consumer/generic_wp.ts

# New sites (WordPress Madara)
npx ts-node --transpileOnly src/consumer/manhastro.ts    # ManhAstro.net with on-demand discovery
npx ts-node --transpileOnly src/consumer/mangalivre.ts   # MangaLivre.tv
```

## Development Commands

### Testing
```bash
# Run all tests
npx jest

# Run specific test by pattern
npx jest --testPathPattern=provider_repository.test.ts
npx jest --testPathPattern=base.test.ts

# Run specific test by file path
npx jest src/__tests__/providers/base/base.test.ts
npx jest src/__tests__/services/proxy_manager.test.ts

# Run integration tests (Redis Phase 1)
npx jest src/__tests__/integration/redis_phase1.test.ts

# Watch mode for development
npx jest --watch
```

### Build and Type Checking
```bash
# Compile TypeScript
npx tsc

# Type check without compilation
npx tsc --noEmit

# Run linter (ESLint if configured)
npx eslint src/**/*.ts
```

### NPM Scripts
```bash
# Development mode with formatted logging (server.ts)
npm run dev

# Production mode (server.ts with HTTPS)
npm run prod

# Debug mode with inspector
npm run debug

# MangaDex specific download
npm run dex
```

### Servidor Python (PM2)
```bash
# Iniciar servidor proxy com PM2 (recomendado)
pm2 start app.py --name "manga-proxy" --interpreter python

# Status do servidor
pm2 status

# Logs em tempo real
pm2 logs manga-proxy -f

# Reiniciar servidor
pm2 restart manga-proxy

# Parar servidor
pm2 stop manga-proxy
```

### Docker
```bash
# Executar com Docker
docker-compose up --build
```

## Arquitetura

Sistema dual **Python/TypeScript** com duas partes principais que se comunicam via API:

### Proxy Service (Python - app.py)
- **Porta**: 3333 (Flask server)
- **Tecnologia**: `nodriver` + `undetected-chromedriver`
- **Função**: Bypass de proteções Cloudflare/Turnstile
- **Endpoint**: `/scrape?url=<encoded_url>`
- **Recursos**:
  - Seleção de modo do browser (Normal/Minimized/Headless)
  - Resolução automática de challenges Turnstile
  - Fallback para FlareSolverr
  - Gerenciamento de sessões e cookies
  - Minimização automática de janelas Chrome

### Downloader (TypeScript)
Sistema orientado a **Provider Pattern** com as seguintes camadas:

#### Consumer Layer (`src/consumer/`)
- **sussy.ts**: Consumer principal com funcionalidades avançadas
  - Modos: Single, Batch, Rentry
  - Sistema de retry com 3 tentativas por capítulo
  - Logging individual por capítulo
  - Detecção inteligente de capítulos novos
  - Recovery automático multi-ciclo (até 10 ciclos)
  - Timeouts progressivos por ciclo
- **seita.ts**: Consumer para Seita Celestial
- **generic_wp.ts**: Consumer genérico para sites WordPress

#### Provider Layer (`src/providers/`)
**Base Classes** (`src/providers/base/`):
- `base.ts`: Classe abstrata definindo interface comum
- `entities.ts`: Estruturas de dados (Manga, Chapter, Pages)
- `provider_repository.ts`: Contrato repository
- `download.ts`: Caso de uso de download

**Implementações Concretas** (`src/providers/scans/`):
- `sussytoons/index.ts`: Implementação SussyToons
- `seitacelestial/index.ts`: Implementação Seita Celestial

#### Services Layer (`src/services/`)
- **axios.ts**: Cliente HTTP customizado
  - Rate limiting e retry automático (10 tentativas)
  - Integração com proxy manager
  - Headers anti-detecção
  - Timeout management progressivo
- **proxy_manager.ts**: Gerenciamento de proxies
  - Redis cache distribuído para listas de proxy (Phase 1)
  - Rotação automática e banimento de proxies falhos
  - Retry com backoff exponencial
  - Graceful fallback quando Redis não disponível
- **redis_client.ts**: Cliente Redis wrapper (Phase 1)
  - Singleton pattern com configuração flexível
  - Operações de cache com namespace
  - Health checks e monitoramento
  - Tratamento de erro e reconexão automática
- **timeout_manager.ts**: Singleton para timeouts progressivos
  - Escalação de 50% por ciclo de retry
  - Coordenação global de timeouts (axios, proxy, download, request)

#### Utils Layer (`src/utils/`)
- **chapter_logger.ts**: Sistema de logging avançado
  - Logs individuais por capítulo organizados por obra
  - Separação sucesso/falha (logs/success/, logs/failed/)
  - Detecção de duplicatas baseada em logs
  - Estatísticas por obra e migração automática de logs antigos
- **logger.ts**: Logger estruturado com Pino
- **folder.ts**: Utilitários de sistema de arquivos
- **prompt.ts**: Utilities de entrada do usuário

## Sistema de Retry e Recovery

### Estratégia Multi-Camada
1. **Retry por capítulo**: 3 tentativas com backoff exponencial
2. **Reprocessamento por obra**: Segunda fase para falhas
3. **Recovery cíclico**: Até 10 ciclos automáticos de rentry
4. **Timeouts progressivos**: Aumento de 50% por ciclo (15s → 22.5s → 30s...)

### Detecção Inteligente
- **Capítulos novos**: Comparação com logs para detectar novos vs já baixados
- **Proteção anti-bot**: Detecção de JavaScript ofuscado e challenges
- **Validação de capítulos**: Detecção de 0 páginas e retry automático
- **Logging de falhas**: Persistência em `url_fails.txt` para reprocessamento

## Organização de Arquivos

### Estrutura de Download Hierárquica
```
MANGA_BASE_PATH/
├── [Publisher]/
│   ├── [Site]/
│   │   ├── [Obra]/
│   │   │   ├── Capítulo [numero]/
│   │   │   │   ├── 01.jpg
│   │   │   │   ├── 02.jpg
│   │   │   │   └── ...
│   │   │   └── Capítulo [numero+1]/
│   │   └── [Outra Obra]/
│   └── [Outro Site]/
└── [Outro Publisher]/
```

### Exemplo Real
```
D:\MOE\Obras\
└── Gikamura\
    ├── Sussy Toons\
    │   ├── Arquiteto de Dungeons\
    │   │   ├── Capítulo 01\
    │   │   │   ├── 01.jpg
    │   │   │   ├── 02.jpg
    │   │   │   └── ...
    │   │   └── Capítulo 02\
    │   └── Outra Obra\
    ├── ManhAstro\
    │   └── Boundless Necromancer\
    ├── MangaLivre\
    │   └── [obras do MangaLivre]
    └── Seita Celestial\
        └── [obras da Seita]
```

### Estrutura de Logs
```
logs/
├── success/[obra].json    # Sucessos por obra
├── failed/[obra].json     # Falhas por obra
└── ...
```

### Arquivos de Configuração
- `obra_urls.txt`: URLs de obras para modo batch
- `url_fails.txt`: URLs de falhas para reprocessamento
- `.env`: Configurações de ambiente (veja .env.example)

## Funcionalidades Avançadas

### Download Concorrente
- 5 downloads simultâneos por capítulo
- Rate limiting configurável
- Controle de concorrência com Bluebird

### Anti-Bot Handling
- Detecção automática de proteções Cloudflare
- Resolução de Turnstile challenges
- Aceitação automática de Terms of Service
- Fallback para múltiplas estratégias

### Sistema de Logs
- Logging estruturado JSON com Pino
- Logs por capítulo individual
- Estatísticas de progresso por obra
- Recovery baseado em estado persistido

## API Host Service - BuzzHeavier Sync

### Overview
The `api/host/` directory contains a modular Flask service for BuzzHeavier synchronization with dual **REST API + CLI** architecture.

### Service Structure
```
api/host/
├── app.py                 # Flask application
├── sync_cli.py           # CLI synchronization interface  
├── install.py            # Installation script
├── models/               # Data models (sync stats, file models)
├── routes/               # REST API endpoints (/sync, /files)
├── services/             # Business logic services
│   ├── buzzheavier/      # BuzzHeavier client (auth, upload)
│   ├── file/             # File scanning and validation
│   └── sync/             # Sync management and state
├── cli/                  # Command line interface
└── utils/                # Utilities (config, progress)
```

### Setup and Usage
```bash
# Install API-specific dependencies
cd api/host && pip install -r requirements.txt

# Automated installation
python install.py

# Interactive CLI (original mode)
python sync_cli.py

# Direct CLI commands
python sync_cli.py sync /path/to/manga --token YOUR_TOKEN
python sync_cli.py scan /path/to/manga --json

# REST API server
python app.py --port 5000
```

### Key REST Endpoints
```bash
# Sync operations
POST /sync/start          # Start synchronization
GET  /sync/status         # Current status
GET  /sync/stats          # Detailed statistics
POST /sync/stop           # Stop synchronization
POST /sync/retry-failed   # Reprocess failures
GET  /sync/history        # Sync history
GET/PUT /sync/config      # Configuration management
POST /sync/clear-state    # Clear state

# File operations  
POST /files/scan          # Scan directory
POST /files/validate      # Validate files
POST /files/hierarchy     # Analyze hierarchy
POST /files/duplicates    # Find duplicates
POST /files/storage-check # Check storage space
POST /files/info          # File information
POST /files/clear-cache   # Clear cache

# Health and monitoring
GET  /health              # API health check
```

## Environment Configuration

### Environment Variables (.env)
Copy `.env.example` and configure:
```bash
# Download Configuration
MANGA_BASE_PATH=/path/to/manga/downloads
DOWNLOAD_CONCURRENCY=5
CHAPTER_CONCURRENCY=2
URL_FILE_BATCH_PATH=./obra_urls.txt

# Proxy Configuration
PROXY_URL=https://proxy.webshare.io/api/v2/proxy/list/download/[TOKEN]/-/any/username/direct/-/
PROXY_USERNAME=username
PROXY_PASSWORD=password

# Server Configuration
PROXY_SERVER_PORT=3333
WEB_INTERFACE_PORT=8080
API_URL=http://localhost:3333

# Logging Configuration
LOG_LEVEL=info
LOG_FILE_SUCCESS=./logs/success
LOG_FILE_FAILED=./logs/failed

# Timeout Configuration (milliseconds)
REQUEST_TIMEOUT=15000
DOWNLOAD_TIMEOUT=30000
PROXY_TIMEOUT=600000

# Chrome/Browser Configuration
CHROME_PATH=/usr/bin/google-chrome
HEADLESS=false
PUPPETEER_NO_SANDBOX=1

# Redis Configuration (Phase 1)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
REDIS_TTL=300
```

## Critical Workflow Notes

### Startup Sequence
1. **ALWAYS** start Python proxy service first: `pm2 start app.py --name "manga-proxy" --interpreter python`
2. Verify proxy is running on port 3333: `curl http://localhost:3333/health`
3. Then run TypeScript consumers: `npx ts-node --transpileOnly src/consumer/sussy.ts`

### State Management
- Log files serve as application state (avoid unnecessary re-downloads)
- `logs/success/` and `logs/failed/` directories track chapter completion
- `url_fails.txt` stores failed URLs for rentry mode
- `obra_urls.txt` contains batch mode manga URLs

### Performance Notes
- Use PM2 for Python server auto-restart in development
- TypeScript uses `ts-node --transpileOnly` for fast builds without type checking
- System supports Docker deployment via `docker-compose.yml`
- Multi-layer retry strategy: chapter-level → work-level → cyclic recovery (up to 10 cycles)
- **Redis Integration**: Phase 1 implemented - ProxyManager now uses Redis for distributed caching with graceful fallback

### API Integration
- BuzzHeavier sync service in `api/host/` is independent of main scraper
- Can run REST API server (`python app.py`) or use CLI (`python sync_cli.py`)
- Both maintain 100% compatibility with original CLI workflow