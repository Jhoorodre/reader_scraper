# Teste Simples do Cloudflare Turnstile

## Arquivos

- `simple_proxy.py` - Proxy minimalista para bypass do Turnstile
- `test.py` - Script de teste
- `README.md` - Este arquivo

## Como usar

### 1. Instalar dependências
```bash
pip install flask nodriver requests
```

### 2. Executar o proxy
```bash
# Terminal 1
cd turnstile_test
python simple_proxy.py
```

Aguarde ver a mensagem: "Running on http://0.0.0.0:3333"

### 3. Testar
```bash
# Terminal 2 
cd turnstile_test
python test.py
```

## O que faz

1. **Proxy simples**: Abre Chrome, navega para URL, tenta clicar no Turnstile
2. **Tratamento de termos**: Aceita termos automaticamente no SussyToons
3. **Teste direto**: Verifica se consegue baixar o conteúdo

## Debug

- Proxy abre Chrome **visível** - você pode ver o que acontece
- Logs mostram cada passo
- Teste mostra quantos bytes foram baixados

## Funcionamento

1. Abre Chrome
2. Navega para URL
3. Procura e aceita termos de serviço
4. Procura iframe do Turnstile e clica
5. Aguarda resolução
=======
# Teste Simples do Cloudflare Turnstile

## Arquivos

- `simple_proxy.py` - Proxy minimalista para bypass do Turnstile
- `test.py` - Script de teste
- `README.md` - Este arquivo

## Como usar

### 1. Instalar dependências
```bash
pip install flask nodriver requests
```

### 2. Executar o proxy
```bash
# Terminal 1
cd turnstile_test
python simple_proxy.py
```

Aguarde ver a mensagem: "Running on http://0.0.0.0:3333"

### 3. Testar
```bash
# Terminal 2 
cd turnstile_test
python test.py
```

## O que faz

1. **Proxy simples**: Abre Chrome, navega para URL, tenta clicar no Turnstile
2. **Tratamento de termos**: Aceita termos automaticamente no SussyToons
3. **Teste direto**: Verifica se consegue baixar o conteúdo

## Debug

- Proxy abre Chrome **visível** - você pode ver o que acontece
- Logs mostram cada passo
- Teste mostra quantos bytes foram baixados

## Funcionamento

1. Abre Chrome
2. Navega para URL
3. Procura e aceita termos de serviço
4. Procura iframe do Turnstile e clica
5. Aguarda resolução
6. Retorna conteúdo final