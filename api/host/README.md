# 🚀 BuzzHeavier Sync API v2.0

Sistema modular de sincronização com BuzzHeavier. Arquitetura dual **API REST + CLI** mantendo funcionalidade original.

## 📁 Estrutura Modular

```
api/host/
├── services/           # Serviços core
│   ├── buzzheavier/   # Cliente BuzzHeavier (auth, upload)
│   ├── sync/          # Gerenciamento de sincronização
│   └── file/          # Scanner e validação de arquivos
├── routes/            # API REST endpoints
├── cli/               # Interface linha de comando
├── models/            # Modelos de dados
├── utils/             # Utilitários (config, progress)
└── app.py             # Aplicação Flask
```

## 🚀 Instalação e Uso

### Instalação Automática
```bash
cd api/host
python install.py
# Segue instruções do instalador
```

### Uso Rápido

#### CLI Interativo (Modo Original)
```bash
python sync_cli.py
# Ou: python cli/interactive.py
```

#### Comandos CLI (Novo)
```bash
# Sincronização direta
python sync_cli.py sync /path/to/manga --token YOUR_TOKEN

# Escaneamento
python sync_cli.py scan /path/to/manga --json

# Status
python sync_cli.py status
```

#### API REST (Novo)
```bash
# Iniciar servidor
python app.py --port 5000

# Testar endpoints
curl http://localhost:5000/health
```

## 📚 API REST Endpoints

### 🔄 Sincronização
- `POST /sync/start` - Iniciar sincronização
- `GET /sync/status` - Status atual  
- `GET /sync/stats` - Estatísticas detalhadas
- `POST /sync/stop` - Parar sincronização
- `POST /sync/retry-failed` - Reprocessar falhas
- `GET /sync/history` - Histórico
- `GET/PUT /sync/config` - Configuração
- `POST /sync/clear-state` - Limpar estado

### 📁 Arquivos
- `POST /files/scan` - Escanear diretório
- `POST /files/validate` - Validar arquivos
- `POST /files/hierarchy` - Analisar hierarquia
- `POST /files/duplicates` - Encontrar duplicatas
- `POST /files/storage-check` - Verificar espaço
- `POST /files/info` - Info de arquivo
- `POST /files/clear-cache` - Limpar cache

## 📋 Exemplos de Uso

### Iniciar Sincronização
```bash
curl -X POST http://localhost:5000/sync/start \
  -H "Content-Type: application/json" \
  -d '{
    "root_path": "/path/to/manga",
    "config": {
      "max_concurrent_uploads": 5,
      "retry_attempts": 3
    }
  }'
```

### Escanear Diretório
```bash
curl -X POST http://localhost:5000/files/scan \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/path/to/manga",
    "use_cache": true
  }'
```

### Ver Status
```bash
curl http://localhost:5000/sync/status
```

## ⚙️ Configuração

### Token BuzzHeavier
```bash
# Via CLI
python cli/interactive.py
# Opção 7 -> 1 -> inserir token

# Via API
curl -X PUT http://localhost:5000/sync/config \
  -H "Content-Type: application/json" \
  -d '{"buzzheavier_token": "seu_token_aqui"}'
```

### config.ini
```ini
[DEFAULT]
buzzheavier_token = seu_token
max_concurrent_uploads = 5
retry_attempts = 3
timeout_seconds = 30
chunk_size = 8192
auto_consolidate = false

[logging]
level = INFO
log_dir = _LOGS
max_log_files = 10
```

## 🔧 Instalação

```bash
# Dependências
cd api/host
pip install -r requirements.txt

# Configurar token
python cli/interactive.py  # Opção 7
```

## 🎯 Funcionalidades

### ✅ Implementado (Fases 1-4)
- 📊 **Modelos de dados** - EstruturaHierarquica, SyncStats, SyncConfig
- ⚙️ **Configuração centralizada** - ConfigManager, StateManager
- 🔐 **BuzzHeavier Client** - Auth, upload, API calls
- 📁 **File Scanner** - Estrutura hierárquica, validação
- 🔄 **Sync Manager** - Coordenação, retry, estado
- 📊 **Stats Manager** - Estatísticas thread-safe
- 🌐 **API REST** - Endpoints completos + Flask app
- 💻 **CLI Modular** - Interface preservada usando serviços

### 🔮 Planejado (Fases 5-6)
- 🔗 **Integração Scraper** - Upload automático pós-download
- 🌐 **Interface Web** - Monitoramento visual
- 📊 **Métricas Avançadas** - Alertas, backup/restore
- 🚀 **Otimizações** - Filas, compressão, retry inteligente

## 🏗️ Arquitetura

### Padrões Utilizados
- **Service Layer** - Lógica de negócio isolada
- **Repository Pattern** - Abstração de dados
- **Factory Pattern** - Criação de objetos
- **Observer Pattern** - Callbacks de progresso
- **Singleton Pattern** - Managers globais

### Principais Componentes

#### 🔐 BuzzHeavier Services
- `BuzzHeavierClient` - HTTP client com retry
- `AuthManager` - Autenticação e sessão
- `FileUploader` - Upload com progresso

#### 📁 File Services  
- `FileScanner` - Escaneamento de estruturas
- `FileValidator` - Validação robusta
- `HierarchyAnalyzer` - Análise hierárquica

#### 🔄 Sync Services
- `SyncManager` - Coordenação principal
- `SyncStateManager` - Estado persistente
- `SyncStatsManager` - Estatísticas thread-safe

## 🤝 Compatibilidade

### ✅ Mantém 100% de compatibilidade com:
- CLI original - mesmo workflow
- Estrutura de arquivos - mesmo formato
- Configurações - config.ini preservado
- Estado - logs e histórico preservados

### ➕ Adiciona:
- API REST para automação
- Arquitetura modular
- Testabilidade melhorada
- Extensibilidade facilitada

## 📝 Logs e Estado

### Arquivos de Estado
- `config.ini` - Configurações
- `sync_state.json` - Estado persistente
- `_LOGS/` - Logs de sincronização

### Logging Estruturado
```python
import logging
logger = logging.getLogger(__name__)
logger.info("Sincronização iniciada", extra={
    'root_path': path,
    'files_count': count
})
```

## 🐛 Solução de Problemas

### Token Inválido
```bash
# Verificar token
curl http://localhost:5000/sync/config

# Reconfigurar
python cli/interactive.py  # Opção 7 -> 1
```

### Arquivos com Falha
```bash
# Ver falhas
curl http://localhost:5000/sync/stats

# Reprocessar
curl -X POST http://localhost:5000/sync/retry-failed
```

### Cache/Estado Corrompido
```bash
# Limpar via CLI
python cli/interactive.py  # Opção 8

# Limpar via API  
curl -X POST http://localhost:5000/sync/clear-state \
  -H "Content-Type: application/json" \
  -d '{"type": "all"}'
```

## 📈 Próximos Passos

1. **Integração com Scraper TypeScript** - Upload automático
2. **Interface Web** - Dashboard de monitoramento  
3. **Métricas Avançadas** - Alertas e notificações
4. **Otimizações** - Performance e confiabilidade

---

**🚀 BuzzHeavier Sync API v2.0** - Modular, Escalável, Compatível