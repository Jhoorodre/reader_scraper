# 🚀 BuzzHeavier Sync - Sistema Modular

Sistema de sincronização com BuzzHeavier completamente modularizado. **100% compatível** com o `sync_buzzheavier.py` original + funcionalidades extras.

## 📁 Estrutura

```
api/
├── sync_buzzheavier.py    # ⚠️ ORIGINAL (mantido para referência)
├── host/                  # ✅ SISTEMA MODULARIZADO
│   ├── sync_cli.py       # Ponto de entrada principal
│   ├── install.py        # Instalador automático
│   └── ...              # 31 arquivos modulares
└── README.md             # Este arquivo
```

## 🚀 Como Iniciar

### 📦 **1. Instalação Automática (Recomendado)**

```bash
# Navegar para o sistema modularizado
cd api/host

# Executar instalador automático
python install.py
```

**O instalador fará:**
- ✅ Verificar Python 3.7+
- ✅ Instalar dependências
- ✅ Criar diretórios necessários  
- ✅ Criar arquivo `config.ini`
- ✅ Copiar configurações existentes (se houver)
- ✅ Testar instalação

### ⚙️ **2. Configurar Token BuzzHeavier**

#### Opção A: Via arquivo config.ini
```bash
# Editar config.ini
nano config.ini

# Adicionar seu token
[DEFAULT]
buzzheavier_token = SEU_TOKEN_AQUI
```

#### Opção B: Via menu interativo
```bash
python sync_cli.py
# Menu → Opção 7 (Configurações) → Opção 1 (Token)
```

#### Opção C: Via comando CLI
```bash
python sync_cli.py config set buzzheavier_token SEU_TOKEN_AQUI
```

## 🎯 **3. Modos de Uso**

### 🖥️ **Modo Interativo (100% Original)**
```bash
# Menu familiar idêntico ao sync_buzzheavier.py
python sync_cli.py

# Mesma interface, mesmas opções, zero curva de aprendizado
```

### ⌨️ **Comandos CLI (Novo)**
```bash
# Sincronização direta
python sync_cli.py sync /path/to/manga --token SEU_TOKEN

# Escanear diretório
python sync_cli.py scan /path/to/manga --json

# Ver status do sistema
python sync_cli.py status

# Reprocessar arquivos com falha
python sync_cli.py retry-failed

# Gerenciar configuração
python sync_cli.py config show
python sync_cli.py config set max_concurrent_uploads 10
```

### 🌐 **API REST (Novo)**
```bash
# Iniciar servidor
python app.py --port 5000

# Testar saúde da API
curl http://localhost:5000/health

# Documentação automática
open http://localhost:5000
```

## 📋 **Exemplo Prático Completo**

### **Primeira Execução**
```bash
# 1. Instalação
cd api/host
python install.py

# 2. Configurar token
python sync_cli.py config set buzzheavier_token SEU_TOKEN_AQUI

# 3. Verificar configuração
python sync_cli.py config show

# 4. Sincronizar (modo original)
python sync_cli.py
# → 1 (Selecionar diretório)
# → 2 (Escanear)  
# → 4 (Sincronizar)
```

### **Uso Avançado com Comandos**
```bash
# Sincronização automatizada
python sync_cli.py sync /mnt/c/manga/SussyToons --max-uploads 8

# Escaneamento com saída JSON
python sync_cli.py scan /mnt/c/manga/SussyToons --json > scan_result.json

# Monitoramento de status
python sync_cli.py status --json
```

### **Integração via API**
```bash
# Iniciar servidor em background
python app.py --port 5000 &

# Iniciar sincronização via API
curl -X POST http://localhost:5000/sync/start \
  -H "Content-Type: application/json" \
  -d '{"root_path": "/mnt/c/manga/SussyToons"}'

# Monitorar progresso
curl http://localhost:5000/sync/status

# Ver estatísticas
curl http://localhost:5000/sync/stats
```

## 🛠️ **Configuração Avançada**

### **config.ini**
```ini
[DEFAULT]
# Token BuzzHeavier (obrigatório)
buzzheavier_token = SEU_TOKEN_AQUI

# Configurações de upload
max_concurrent_uploads = 5
retry_attempts = 3
timeout_seconds = 30
chunk_size = 8192
auto_consolidate = false

[logging]
# Configurações de log
level = INFO
log_dir = _LOGS
max_log_files = 10
```

### **Variáveis de Ambiente**
```bash
# Configuração via variáveis (opcional)
export BUZZHEAVIER_TOKEN="seu_token"
export LOG_LEVEL="DEBUG"
export MAX_UPLOADS="10"
```

## 🆘 **Resolução de Problemas**

### ❌ **"Token obrigatório"**
```bash
# Verificar configuração
python sync_cli.py config show

# Configurar token
python sync_cli.py config set buzzheavier_token SEU_TOKEN
```

### ❌ **"Módulo não encontrado"**
```bash
# Instalar dependências
cd api/host
pip install -r requirements.txt

# Ou usar instalador completo
python install.py
```

### ❌ **"Arquivo não encontrado"**
```bash
# Verificar estrutura
ls -la api/host/

# Recriar instalação
cd api/host
python install.py
```

### ❌ **"Erro de permissão"**
```bash
# WSL: Ajustar permissões
chmod +x api/host/sync_cli.py

# Windows: Executar como administrador se necessário
```

### ❌ **"API não responde"**
```bash
# Verificar se servidor está rodando
curl http://localhost:5000/health

# Iniciar servidor
cd api/host
python app.py --port 5000
```

## 📊 **Migração do Original**

### **Para usuários do sync_buzzheavier.py:**

**✅ Compatibilidade Total:**
- Menu idêntico
- Mesmas funcionalidades
- Mesmo workflow
- Mesmos arquivos de configuração

**➕ Funcionalidades Extras:**
- API REST para automação
- Comandos CLI para scripts
- Instalador automático
- Sistema modular extensível

**🔄 Migração Simples:**
```bash
# 1. Backup da configuração atual (opcional)
cp config.ini config.ini.backup
cp sync_state.json sync_state.json.backup

# 2. Instalar sistema modular
cd api/host
python install.py
# O instalador detecta e copia automaticamente!

# 3. Usar normalmente
python sync_cli.py
# Interface idêntica ao original
```

## 📚 **Ajuda e Documentação**

### **Ajuda Rápida**
```bash
# Ajuda geral
python sync_cli.py --help

# Ajuda de comando específico  
python sync_cli.py sync --help
python sync_cli.py config --help

# Versão
python sync_cli.py --version
```

### **Documentação Completa**
```bash
# README detalhado do sistema modular
cat api/host/README.md

# Roadmap e arquitetura
cat api/ROADMAP.md

# API documentation (quando servidor rodando)
open http://localhost:5000
```

### **Logs e Debug**
```bash
# Ver logs de sincronização
ls -la api/host/_LOGS/

# Status detalhado
python sync_cli.py status

# Configuração atual
python sync_cli.py config show
```

## 🎯 **Comandos Essenciais**

| Função | Comando Original | Comando Modular |
|--------|------------------|-----------------|
| **Menu interativo** | `python sync_buzzheavier.py` | `python sync_cli.py` |
| **Sincronizar** | Menu → Opção 4 | `python sync_cli.py sync /path` |
| **Configurar** | Menu → Opção 7 | `python sync_cli.py config set key value` |
| **Ver status** | Menu → Opção 5 | `python sync_cli.py status` |
| **Reprocessar** | Menu → Opção 6 | `python sync_cli.py retry-failed` |

## 🏆 **Vantagens do Sistema Modular**

### **Para Usuários Finais:**
- ✅ **Zero impacto**: Interface idêntica
- ✅ **Mais estável**: Código organizado
- ✅ **Mais rápido**: Cache otimizado
- ✅ **Mais opções**: CLI + API

### **Para Desenvolvedores:**
- ✅ **Testável**: Módulos isolados
- ✅ **Extensível**: Arquitetura modular
- ✅ **Manutenível**: Código limpo
- ✅ **Integrável**: API REST

### **Para Automação:**
- ✅ **Scripts**: Comandos CLI
- ✅ **Integração**: API REST
- ✅ **Monitoramento**: Endpoints de status
- ✅ **CI/CD**: Saídas JSON

---

## 🚀 **Início Rápido (TL;DR)**

```bash
# 1. Instalar
cd api/host && python install.py

# 2. Configurar
python sync_cli.py config set buzzheavier_token SEU_TOKEN

# 3. Usar (igual ao original)
python sync_cli.py
```

**🎯 Pronto para usar! Interface familiar + funcionalidades extras!**

---

**📞 Suporte**: Consulte `api/host/README.md` para documentação completa ou `api/ROADMAP.md` para detalhes técnicos.