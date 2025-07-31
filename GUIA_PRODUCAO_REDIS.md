# 🚀 Guia Completo de Produção - Manga Scraper com Redis

## 📋 Índice
- [Pré-requisitos](#pré-requisitos)
- [Inicialização do Sistema](#inicialização-do-sistema)
- [Downloads de Produção](#downloads-de-produção)
- [Monitoramento Redis](#monitoramento-redis)
- [Gerenciamento PM2](#gerenciamento-pm2)
- [Comandos Redis Úteis](#comandos-redis-úteis)
- [Troubleshooting](#troubleshooting)
- [Sequências Práticas](#sequências-práticas)

---

## 🔧 Pré-requisitos

### Verificar se tudo está instalado:
```bash
# Verificar Node.js
node --version

# Verificar Python
python --version

# Verificar Redis (WSL2)
wsl redis-cli ping

# Verificar PM2
pm2 --version
# Se não tiver: npm install -g pm2
```

### Estrutura de pastas esperada:
```
reader_scraper/
├── app.py              # Servidor proxy Python
├── obra_urls.txt       # URLs para download em lote
├── src/consumer/       # Downloaders TypeScript
├── manga/             # Downloads salvos aqui
└── logs/              # Logs de sucessos/falhas
```

---

## 🚀 Inicialização do Sistema

### Método 1: PM2 (Recomendado para Produção)

**Passo 1 - Iniciar Proxy Server:**
```bash
pm2 start app.py --name "manga-proxy" --interpreter python
```

**Passo 2 - Verificar Status:**
```bash
pm2 status
# Deve mostrar: manga-proxy | online
```

**Passo 3 - Ver Logs:**
```bash
pm2 logs manga-proxy -f
# Deve mostrar: "🚀 Servidor proxy iniciado na porta 3333"
```

### Método 2: Manual (Para Debug)

**Terminal 1 - Proxy Server:**
```bash
python app.py
# Deixar rodando, não fechar este terminal
```

---

## 📥 Downloads de Produção

### Download de Uma Obra (Interativo)
```bash
npx ts-node --transpileOnly src/consumer/sussy.ts
# Vai pedir URL da obra
# Escolher capítulos para baixar
```

### Download em Lote
```bash
# 1. Editar arquivo com URLs
notepad obra_urls.txt
# Adicionar uma URL por linha

# 2. Executar batch
npx ts-node --transpileOnly src/consumer/sussy.ts urls
# Vai processar todas as URLs do arquivo
```

### Reprocessar Falhas
```bash
npx ts-node --transpileOnly src/consumer/sussy.ts rentry
# Reprocessa capítulos que falharam anteriormente
```

### Outros Sites
```bash
# Seita Celestial
npx ts-node --transpileOnly src/consumer/seita.ts

# Sites WordPress genéricos
npx ts-node --transpileOnly src/consumer/generic_wp.ts
```

---

## 👀 Monitoramento Redis

### Verificações Básicas
```bash
# Testar conexão
wsl redis-cli ping
# Resultado esperado: PONG

# Ver todas as chaves em cache
wsl redis-cli keys "*"
# Mostra: proxy:list, health:data, etc.

# Ver número total de chaves
wsl redis-cli dbsize
```

### Monitor em Tempo Real
```bash
# Ver todos os comandos Redis em tempo real
wsl redis-cli monitor
# Deixar rodando em terminal separado durante downloads
```

### Cache de Proxies
```bash
# Ver cache de proxies
wsl redis-cli keys "proxy*"

# Ver lista de proxies atual
wsl redis-cli get "proxy:list"

# Ver dados de saúde
wsl redis-cli keys "*health*"
```

### Estatísticas de Performance
```bash
# Uso de memória
wsl redis-cli info memory

# Estatísticas gerais
wsl redis-cli info stats

# Latência do Redis
wsl redis-cli --latency-history
```

---

## 🔄 Gerenciamento PM2

### Comandos Essenciais
```bash
# Ver todos os processos
pm2 list

# Ver status detalhado
pm2 show manga-proxy

# Reiniciar proxy
pm2 restart manga-proxy

# Parar proxy
pm2 stop manga-proxy

# Remover processo
pm2 delete manga-proxy
```

### Logs e Debug
```bash
# Logs em tempo real
pm2 logs manga-proxy -f

# Últimas 50 linhas de log
pm2 logs manga-proxy --lines 50

# Apenas logs de erro
pm2 logs manga-proxy --err

# Limpar logs
pm2 flush manga-proxy
```

### Configuração Avançada
```bash
# Salvar configuração atual
pm2 save

# Auto-iniciar no boot do sistema
pm2 startup

# Monitor gráfico
pm2 monit
```

---

## 🔧 Comandos Redis Úteis

### Parar/Iniciar Redis
```bash
# Parar Redis (Windows)
redis-cli shutdown

# Parar Redis (WSL2) 
wsl redis-cli shutdown
# Resultado esperado: "Connection refused" se já parado

# Iniciar Redis (WSL2)
wsl sudo service redis-server start

# Verificar se Redis está rodando
wsl redis-cli ping
# Resultado esperado: PONG

# Status do Redis
wsl sudo service redis-server status
```

### Limpeza de Cache
```bash
# Limpar tudo (cuidado!)
wsl redis-cli flushall

# Limpar apenas database atual
wsl redis-cli flushdb

# Deletar chave específica
wsl redis-cli del "proxy:list"

# Deletar múltiplas chaves
wsl redis-cli del "proxy:list" "health:data"
```

### Backup e Restore
```bash
# Fazer backup
wsl redis-cli save

# Ver localização do backup
wsl redis-cli config get dir

# Restaurar (copiar dump.rdb para diretório Redis)
```

### Configuração TTL
```bash
# Ver tempo restante de uma chave
wsl redis-cli ttl "proxy:list"

# Definir expiração (em segundos)
wsl redis-cli expire "proxy:list" 300

# Remover expiração
wsl redis-cli persist "proxy:list"
```

---

## 🚨 Troubleshooting

### Redis não conecta
```bash
# Verificar se Redis está rodando
wsl sudo service redis-server status

# Iniciar Redis se necessário
wsl sudo service redis-server start

# Testar conexão
wsl redis-cli ping
```

### Proxy server não inicia
```bash
# Verificar se porta 3333 está livre
netstat -an | findstr 3333

# Ver logs de erro do PM2
pm2 logs manga-proxy --err

# Reiniciar proxy
pm2 restart manga-proxy
```

### Downloads falham
```bash
# Verificar se proxy está rodando
pm2 status

# Ver logs em tempo real
pm2 logs manga-proxy -f

# Verificar cache Redis
wsl redis-cli keys "*"

# Limpar cache e tentar novamente
wsl redis-cli flushall
```

### Performance lenta
```bash
# Verificar latência Redis
wsl redis-cli --latency

# Ver uso de memória
wsl redis-cli info memory

# Verificar número de conexões
wsl redis-cli info clients
```

---

## 📋 Sequências Práticas

### 🎯 Sequência 1: Iniciar Sistema pela Primeira Vez
```bash
# 1. Verificar pré-requisitos
wsl redis-cli ping
pm2 --version

# 2. Iniciar proxy
pm2 start app.py --name "manga-proxy" --interpreter python

# 3. Verificar se iniciou
pm2 status

# 4. Testar download
npx ts-node --transpileOnly src/consumer/sussy.ts
```

### 🎯 Sequência 2: Download em Lote (Produção)
```bash
# Terminal 1: Monitorar proxy
pm2 logs manga-proxy -f

# Terminal 2: Monitorar Redis
wsl redis-cli monitor

# Terminal 3: Executar downloads
notepad obra_urls.txt  # Adicionar URLs
npx ts-node --transpileOnly src/consumer/sussy.ts urls

# Terminal 4: Monitorar sistema
pm2 monit
```

### 🎯 Sequência 3: Reprocessar Falhas
```bash
# 1. Ver quantas falhas existem
dir logs\failed

# 2. Limpar cache Redis
wsl redis-cli flushall

# 3. Executar rentry
npx ts-node --transpileOnly src/consumer/sussy.ts rentry

# 4. Monitorar progresso
pm2 logs manga-proxy -f
```

### 🎯 Sequência 4: Manutenção Diária
```bash
# 1. Verificar status geral
pm2 status
wsl redis-cli ping
wsl redis-cli dbsize

# 2. Ver estatísticas de download
dir manga /s
dir logs\success

# 3. Limpeza se necessário
wsl redis-cli flushall
pm2 restart manga-proxy

# 4. Backup logs importantes
copy logs\success\*.json backup\
```

### 🎯 Sequência 5: Debug de Problemas
```bash
# 1. Verificar todos os serviços
pm2 status
wsl redis-cli ping
netstat -an | findstr 3333

# 2. Ver logs de erro
pm2 logs manga-proxy --err --lines 20

# 3. Testar componentes isoladamente
node test_redis_playground.js

# 4. Reiniciar tudo se necessário
pm2 delete manga-proxy
wsl sudo service redis-server restart
pm2 start app.py --name "manga-proxy" --interpreter python
```

---

## 📊 Comandos de Monitoramento Avançado

### Durante Downloads Ativos
```bash
# Terminal 1: Logs do proxy
pm2 logs manga-proxy -f

# Terminal 2: Monitor Redis
wsl redis-cli monitor

# Terminal 3: Estatísticas Redis
watch -n 5 'wsl redis-cli info stats | grep -E "keyspace_hits|keyspace_misses|used_memory_human"'

# Terminal 4: Espaço em disco
watch -n 10 'du -sh manga/'
```

### Alertas Automáticos
```bash
# Script para alertar se Redis ficar sem memória
wsl redis-cli info memory | grep used_memory_human

# Script para alertar se proxy cair
pm2 status | grep manga-proxy | grep online
```

---

## 🎉 Dicas de Produção

### Performance
- **Redis**: Use TTL de 300s para cache de proxies
- **PM2**: Use `pm2 monit` para monitorar recursos
- **Downloads**: Execute em horários de menor tráfego

### Segurança
- **Redis**: Configure senha se expor para rede
- **Proxy**: Use rate limiting para evitar bans
- **Logs**: Faça backup regular dos logs de sucesso

### Manutenção
- **Diária**: Verificar logs de erro
- **Semanal**: Limpar cache Redis antigo
- **Mensal**: Backup completo dos downloads

---

## 📞 Comandos de Emergência

### Sistema Travou
```bash
# Parar Redis completamente
redis-cli shutdown
wsl redis-cli shutdown

# Matar todos os processos relacionados
pm2 delete all
taskkill /f /im python.exe
taskkill /f /im node.exe

# Reiniciar Redis
wsl sudo service redis-server restart

# Verificar se Redis iniciou
wsl redis-cli ping

# Reiniciar sistema
pm2 start app.py --name "manga-proxy" --interpreter python
```

### Disco Cheio
```bash
# Ver uso do disco
dir manga /s
wsl df -h

# Limpar arquivos temporários
del /s /q temp\*
wsl redis-cli flushall
```

### Cache Corrompido
```bash
# Limpar tudo e recomeçar
wsl redis-cli flushall
pm2 restart manga-proxy
wsl redis-cli save
```

---

**📚 Este guia cobre todos os cenários de produção. Mantenha-o atualizado conforme o sistema evolui!**