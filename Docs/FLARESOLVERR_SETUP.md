# FlareSolverr Setup - Fallback para Cloudflare

Este arquivo explica como configurar o FlareSolverr como fallback para contornar proteções Cloudflare.

## O que é o FlareSolverr?

FlareSolverr é um servidor proxy que contorna proteções Cloudflare usando um navegador real (Chrome). Ele funciona como um serviço separado que recebe requisições HTTP e retorna o conteúdo da página após resolver os desafios Cloudflare.

## Métodos de Instalação

### 1. Docker (Recomendado)

```bash
# Executar FlareSolverr com Docker
docker run -d \
  --name=flaresolverr \
  -p 8191:8191 \
  -e LOG_LEVEL=info \
  -e DRIVER=nodriver \
  --restart unless-stopped \
  ghcr.io/flaresolverr/flaresolverr:latest
```

### 2. Docker Compose

Adicione ao seu `docker-compose.yml`:

```yaml
version: '3'
services:
  flaresolverr:
    image: ghcr.io/flaresolverr/flaresolverr:latest
    container_name: flaresolverr
    environment:
      - LOG_LEVEL=info
      - DRIVER=nodriver
    ports:
      - "8191:8191"
    restart: unless-stopped
```

### 3. Executável (Windows/Linux)

1. Baixe o executável em: https://github.com/FlareSolverr/FlareSolverr/releases
2. Execute: `./flaresolverr` (Linux) ou `flaresolverr.exe` (Windows)

## Verificação da Instalação

Teste se o FlareSolverr está funcionando:

```bash
curl -X POST 'http://localhost:8191/v1' \
-H 'Content-Type: application/json' \
--data-raw '{
  "cmd": "sessions.list"
}'
```

Resposta esperada:
```json
{
  "status": "ok",
  "message": "",
  "sessions": []
}
```

## Como o Fallback Funciona

1. **Método Primário**: O sistema tenta usar `nodriver` com nosso `CFBypass` customizado
2. **Fallback Automático**: Se o método primário falhar, automaticamente tenta o FlareSolverr
3. **Logs Informativos**: Todos os métodos são logados para debug

## Configuração no Sistema

O fallback está configurado em `app.py` e funciona automaticamente:

- **Porta padrão**: 8191
- **Endpoint**: `http://localhost:8191/v1`
- **Timeout**: 60 segundos
- **Sessões persistentes**: Sim (otimização de performance)

## Variáveis de Ambiente do FlareSolverr

- `LOG_LEVEL`: info, debug, warning, error
- `DRIVER`: nodriver (recomendado) ou undetected-chromedriver
- `CAPTCHA_SOLVER`: none (padrão)
- `PORT`: 8191 (padrão)

## Monitoramento

Verifique se o FlareSolverr está ativo:

```bash
# Verificar container Docker
docker ps | grep flaresolverr

# Verificar logs
docker logs flaresolverr

# Teste de conectividade
curl http://localhost:8191/v1
```

## Troubleshooting

### Erro: "FlareSolverr service is not running"
- Verifique se o Docker container está rodando: `docker ps`
- Verifique se a porta 8191 está acessível: `netstat -an | grep 8191`

### Performance
- FlareSolverr é mais lento que o método primário (usa navegador completo)
- Use apenas como fallback para casos difíceis
- Monitore uso de memória (pode ser alto)

### Logs
O sistema mostrará nos logs quando está usando o fallback:
```
INFO:__main__:Primary scraping method failed: ...
INFO:__main__:Trying FlareSolverr fallback...
INFO:__main__:FlareSolverr fallback successful!
```