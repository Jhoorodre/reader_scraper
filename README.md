# Manga Scraper com Auto-Recovery

Sistema robusto de download de capítulos de mangá com recuperação automática e monitoramento avançado.

## Pré-requisitos
- Python 3.x
- Node.js (22) e npm/yarn
- Chrome (para o undetected-chromedriver)
- PM2 (para auto-restart do servidor Python)

## Configuração e Execução

### 1. Instalar Dependências
```bash
# Instalar dependências Python
pip install -r requirements.txt

# Instalar dependências Node.js
npm install

# Instalar PM2 para gerenciamento de processos
npm install -g pm2
```

### 2. Configurar Variáveis de Ambiente
Crie um arquivo `.env` na raiz do projeto:
```env
# Caminho da pasta de download
MANGA_BASE_PATH=D:\

# Modo do navegador: 1=Normal, 2=Minimizado, 3=Headless
BROWSER_MODE=2

# Configurações de proxy (opcional)
PROXY_URL=
API_URL=http://api:5001
```

### 3. Iniciar Servidor Python (Com Auto-Restart)
```bash
# Iniciar com PM2 (recomendado - reinicia automaticamente)
pm2 start app.py --name "manga-proxy" --interpreter python

# Ver status do servidor
pm2 status

# Ver logs em tempo real
pm2 logs manga-proxy -f

# Parar servidor
pm2 stop manga-proxy
```

#### 🪟 **Janelas CMD no Windows**
O PM2 pode abrir janelas CMD extras no Windows. Isso é normal! Soluções:

```bash
# Opção 1: Iniciar sem mostrar janelas (recomendado)
pm2 stop all && pm2 delete all
pm2 start app.py --name "manga-proxy" --interpreter python --silent

# Opção 2: Fechar janelas CMD abertas (cuidado!)
taskkill /F /IM cmd.exe /FI "WINDOWTITLE eq python*"

# Opção 3: Se persistir, simplesmente minimize as janelas
# O sistema funciona normalmente com elas minimizadas
```

### 4. Executar Downloaders (TypeScript)
```bash
# Modo normal (uma obra)
npx ts-node --transpileOnly src/consumer/sussy.ts

# Modo batch (múltiplas obras do obra_urls.txt)
npx ts-node --transpileOnly src/consumer/sussy.ts urls

# Modo rentry (reprocessar falhas)
npx ts-node --transpileOnly src/consumer/sussy.ts rentry

# Outros providers
npx ts-node --transpileOnly src/consumer/seita.ts
npx ts-node --transpileOnly src/consumer/generic_wp.ts
npx ts-node --transpileOnly src/consumer/manhastro.ts
npx ts-node --transpileOnly src/consumer/mangalivre.ts
```

## Funcionalidades Principais

### 🚀 **Sistema Robusto**
- **Auto-recovery**: Servidor Python reinicia automaticamente se travar
- **Rate limiting**: Controle inteligente de requisições (2s mínimo)
- **Emergency restart**: Reset automático em erros críticos
- **Monitoramento avançado**: Estatísticas em tempo real

### 📂 **Downloads Inteligentes**
- **Configurável via .env**: Escolha o diretório de download
- **Sistema de retry**: 3 tentativas por capítulo com backoff exponencial
- **Reprocessamento automático**: Modo rentry para falhas
- **Logging detalhado**: Logs separados por sucesso/falha

### ⚡ **Performance**
- **Bypass Cloudflare**: Contorna proteções automaticamente
- **Downloads concorrentes**: 5 downloads simultâneos por capítulo
- **Timeouts progressivos**: Aumentam automaticamente em caso de problemas
- **Detecção anti-bot**: Identifica e contorna proteções JavaScript

## Monitoramento e Diagnóstico

### 📊 **Comandos de Monitoramento**
```bash
# Health check do servidor
curl http://localhost:3333/health

# Status detalhado PM2
pm2 status

# Monitor visual com CPU/RAM
pm2 monit

# Logs em tempo real
pm2 logs manga-proxy -f

# Estatísticas de uptime
pm2 show manga-proxy
```

### 🛠️ **Comandos de Recovery**
```bash
# Emergency restart do servidor (sem PM2)
curl -X POST http://localhost:3333/emergency-restart

# Reiniciar PM2
pm2 restart manga-proxy

# Reset completo
pm2 delete all && pm2 start app.py --name "manga-proxy" --interpreter python
```

### 📁 **Estrutura de Arquivos**
```
projeto/
├── manga/                     # Downloads (ou path configurado)
├── logs/
│   ├── success/              # Logs de sucessos por obra
│   └── failed/               # Logs de falhas por obra
├── obra_urls.txt             # URLs para modo batch
├── url_fails.txt             # URLs de falhas para reentry
└── .env                      # Configurações
```

## Desenvolvimento e Docker

### 🐳 **Docker (Opcional)**
```bash
# Build e execução com Docker
docker-compose up --build
```

### 🧪 **Testes**
```bash
# Executar todos os testes
npx jest

# Teste específico
npx jest --testPathPattern=provider_repository.test.ts
```

### 📝 **Scripts NPM**
```bash
npm run dev          # Modo desenvolvimento
npm run prod         # Modo produção  
npm run debug        # Modo debug com inspector
npm run dex          # Download específico do MangaDex
```

## Troubleshooting

### ⚠️ **Problemas Comuns**
- **Servidor não inicia**: Verifique porta 3333 livre
- **ECONNREFUSED**: Servidor Python travou - PM2 reinicia automaticamente
- **Timeout requests**: Rate limiting ativo - aguarde
- **Chrome crashes**: Emergency restart automático
- **Janelas CMD aparecem**: Normal no Windows - minimize ou use `--silent`

### 🔧 **Soluções**
- **Chrome travado**: `taskkill /F /IM chrome.exe`
- **Porta ocupada**: `netstat -ano | findstr :3333`
- **Janelas CMD**: `pm2 start app.py --name "manga-proxy" --interpreter python --silent`
- **Fechar CMD**: `taskkill /F /IM cmd.exe /FI "WINDOWTITLE eq python*"`
- **Reset completo**: Reinicie o PM2 e delete pasta manga temporariamente

## Arquitetura

### 🏗️ **Componentes**
- **Python Flask (app.py)**: Servidor proxy com bypass Cloudflare
- **TypeScript Consumers**: Downloaders com retry e logging
- **PM2**: Gerenciador de processos com auto-restart
- **Provider Pattern**: Sistema extensível para novos sites

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

## Observações Importantes
- **ALWAYS** start Python server with PM2 (`pm2 start app.py --name "manga-proxy" --interpreter python`)
- Server must be running on port 3333 before executing downloaders
- System uses logs to avoid unnecessary re-downloads
- Docker support available for deployment
- Log files serve as application state