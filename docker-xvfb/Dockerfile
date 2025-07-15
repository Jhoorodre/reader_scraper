# Base Ubuntu com Python
FROM ubuntu:22.04

# Evitar prompts interativos
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependências
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    wget \
    curl \
    unzip \
    xvfb \
    xauth \
    && rm -rf /var/lib/apt/lists/*

# Instalar Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Configurar display virtual
ENV DISPLAY=:99
ENV SCREEN_WIDTH=1920
ENV SCREEN_HEIGHT=1080
ENV SCREEN_DEPTH=24

# Diretório de trabalho
WORKDIR /app

# Copiar arquivos
COPY ../requirements.txt .
COPY ../app.py .
COPY ../src/ ./src/
COPY ../package.json .
COPY ../tsconfig.json .

# Instalar dependências Python
RUN pip3 install -r requirements.txt

# Instalar Node.js e dependências
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && npm install

# Script de inicialização
COPY start.sh .
RUN chmod +x start.sh

# Porta do proxy
EXPOSE 3333

# Comando de inicialização
CMD ["./start.sh"]