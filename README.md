# Novo Scraper

Sistema de download e verificação de capítulos de mangá.

## Pré-requisitos
- Python 3.x
- Node.js (22) e npm/yarn
- Chrome (para o undetected-chromedriver)

## Configuração e Execução

### 1. Configuração do Proxy (Python)
```bash
# Instalar dependências Python
pip install -r requirements.txt

# Iniciar o servidor proxy
python app.py
```

### 2. Configuração do Downloader (TypeScript)
```bash
# Instalar dependências Node.js (escolha um dos comandos)
npm install
# ou
yarn install

# Executar o downloader

  # Modo normal (uma obra)
  npx ts-node --transpileOnly src/consumer/sussy.ts

  # Modo batch (múltiplas obras)
  npx ts-node --transpileOnly src/consumer/sussy.ts urls

  # Modo rentry (reprocessar falhas)
  npx ts-node --transpileOnly src/consumer/sussy.ts rentry
```

## Funcionalidades
- O sistema funciona como um proxy que permite download offline de capítulos
- Verifica automaticamente se o capítulo está correto
- Preparado para integração futura com uploaders
- Possibilidade de execução headless (não testada)
- Pode ser executado em VPS

## Observações
- O sistema está em desenvolvimento
- A funcionalidade de upload automático está planejada para implementação futura
- A execução headless ainda não foi testada
- O projeto pode ser containerizado usando Docker (arquivos Dockerfile e docker-compose.yml presentes)

## TODO
- [ ] Documentar porta padrão do proxy
- [ ] Adicionar informações sobre variáveis de ambiente necessárias
- [ ] Documentar formato dos dados de entrada para o downloader
- [ ] Documentar formato dos dados de saída