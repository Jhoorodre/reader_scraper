# Usar uma imagem base do Python
FROM python:3.10-slim

# Instalar dependências do sistema
RUN apt-get update && \
    apt-get install -y \
    wget \
    curl \
    gnupg \
    ca-certificates \
    libx11-dev \
    libxi6 \
    libgconf-2-4 \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Baixar e instalar o Google Chrome estável
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Definir diretório de trabalho
WORKDIR /app

# Copiar os arquivos do projeto para dentro do contêiner
COPY . .

# Instalar as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Definir variável de ambiente para o caminho do Google Chrome
ENV CHROME_PATH=/usr/bin/google-chrome
ENV PUPPETEER_NO_SANDBOX=1

# Expor a porta 3333 para acesso à API
EXPOSE 3333

# Comando para rodar o servidor Flask
CMD ["python", "app.py"]
