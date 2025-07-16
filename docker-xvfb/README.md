
# Docker + Xvfb Setup

Esta pasta contém a configuração Docker com Xvfb para executar o scraper com display virtual.

## Como usar:

### 1. Build da imagem:
```bash
cd docker-xvfb
docker-compose build
```

### 2. Executar:
```bash
docker-compose up
```

### 3. Ou em background:
```bash
docker-compose up -d
```

## O que acontece:
- Container Ubuntu é criado
- Xvfb cria display virtual :99
- Chrome roda invisível no display virtual
- Proxy fica disponível na porta 3333
- Bypass Turnstile funciona normalmente

## Vantagens:
- ✅ Totalmente invisível
- ✅ Isolado do sistema host
- ✅ Fácil deploy em VPS
=======
# Docker + Xvfb Setup

Esta pasta contém a configuração Docker com Xvfb para executar o scraper com display virtual.

## Como usar:

### 1. Build da imagem:
```bash
cd docker-xvfb
docker-compose build
```

### 2. Executar:
```bash
docker-compose up
```

### 3. Ou em background:
```bash
docker-compose up -d
```

## O que acontece:
- Container Ubuntu é criado
- Xvfb cria display virtual :99
- Chrome roda invisível no display virtual
- Proxy fica disponível na porta 3333
- Bypass Turnstile funciona normalmente

## Vantagens:
- ✅ Totalmente invisível
- ✅ Isolado do sistema host
- ✅ Fácil deploy em VPS

- ✅ Turnstile não detecta headless