# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Pré-requisitos
- Python 3.x
- Node.js (22) e npm/yarn
- Chrome (para o undetected-chromedriver)

## Configuração e Execução

### 1. Configuração do Proxy (Python)
```bash
# Instalar dependências Python
pip install -r requirements.txt

# Iniciar o servidor proxy (porta 3333)
python app.py
```

### 2. Configuração do Downloader (TypeScript)
```bash
# Instalar dependências Node.js
npm install  # ou yarn install

# Executar o downloader em diferentes modos:

# Modo normal (uma obra)
npx ts-node --transpileOnly src/consumer/sussy.ts

# Modo batch (múltiplas obras do arquivo obra_urls.txt)
npx ts-node --transpileOnly src/consumer/sussy.ts urls

# Modo rentry (reprocessar falhas)
npx ts-node --transpileOnly src/consumer/sussy.ts rentry

# Outros providers
npx ts-node --transpileOnly src/consumer/seita.ts
npx ts-node --transpileOnly src/consumer/generic_wp.ts
```

## Comandos de Desenvolvimento

### Testes
```bash
# Executar todos os testes
npx jest

# Executar teste específico com pattern
npx jest --testPathPattern=provider_repository.test.ts
npx jest --testPathPattern=base.test.ts

# Executar teste específico por nome do arquivo
npx jest src/__tests__/providers/base/base.test.ts
npx jest src/__tests__/services/proxy_manager.test.ts

# Watch mode para desenvolvimento
npx jest --watch
```

### Build e Linting
```bash
# Compilar TypeScript
npx tsc

# Verificar tipos sem compilar
npx tsc --noEmit

# Executar o linter (se configurado)
npx eslint src/**/*.ts
```

### Scripts NPM
```bash
# Modo desenvolvimento com logging formatado
npm run dev

# Modo produção
npm run prod

# Modo debug com inspector
npm run debug

# Download específico do MangaDex
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
  - Cache LRU para listas de proxy
  - Rotação automática e banimento de proxies falhos
  - Retry com backoff exponencial
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

### Estrutura de Download
```
manga/[nome-sanitizado]/[numero-capitulo]/[pagina].jpg
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

## API Host Service

### Estrutura da API
A pasta `api/host/` contém um serviço Flask separado para sincronização com BuzzHeavier:

```
api/host/
├── app.py                 # Aplicação Flask principal
├── sync_cli.py           # Interface CLI para sincronização
├── install.py            # Script de instalação
├── models/               # Modelos de dados
├── routes/               # Rotas da API (files, sync)
├── services/             # Serviços de negócio
│   ├── buzzheavier/      # Cliente BuzzHeavier
│   ├── file/             # Escaneamento e validação
│   └── sync/             # Gerenciamento de sync
├── cli/                  # Interface de linha de comando
└── utils/                # Utilitários (config, progress)
```

### Comandos da API Host
```bash
# Instalar dependências específicas da API
cd api/host && pip install -r requirements.txt

# Executar servidor da API
cd api/host && python app.py

# Sincronização via CLI
cd api/host && python sync_cli.py

# Modo interativo
cd api/host && python cli/interactive.py
```

## Configuração do Ambiente

### Variáveis de Ambiente (.env)
```bash
# Configuração de Paths
MANGA_BASE_PATH=/path/to/manga/downloads
LOG_FILE_SUCCESS=./logs/success
LOG_FILE_FAILED=./logs/failed

# Configuração de Proxy
PROXY_URL=your_proxy_url
PROXY_USERNAME=username
PROXY_PASSWORD=password

# Configuração de Timeouts (milissegundos)
REQUEST_TIMEOUT=15000
DOWNLOAD_TIMEOUT=30000
PROXY_TIMEOUT=600000

# Configuração de Concorrência
DOWNLOAD_CONCURRENCY=5
CHAPTER_CONCURRENCY=2

# Configuração do Servidor
PROXY_SERVER_PORT=3333
WEB_INTERFACE_PORT=8080
```

## Observações Importantes
- **ALWAYS** start Python proxy (`python app.py` ou PM2) before TypeScript consumers
- Proxy deve estar na porta 3333 antes de executar downloaders
- Sistema usa logs para evitar re-downloads desnecessários
- Suporte a Docker para deployment
- Arquivos de log servem como estado de aplicação
- Para development, use PM2 para auto-restart do servidor Python
- TypeScript usa ts-node com --transpileOnly para builds rápidos