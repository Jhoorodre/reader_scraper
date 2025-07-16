#!/bin/bash

echo "🐳 Iniciando container com Xvfb..."

# Iniciar Xvfb (display virtual)
echo "📺 Iniciando display virtual..."
Xvfb :99 -screen 0 ${SCREEN_WIDTH}x${SCREEN_HEIGHT}x${SCREEN_DEPTH} > /dev/null 2>&1 &
XVFB_PID=$!

# Aguardar Xvfb inicializar
sleep 2

# Verificar se Xvfb está rodando
if ps -p $XVFB_PID > /dev/null; then
    echo "✅ Display virtual :99 criado (${SCREEN_WIDTH}x${SCREEN_HEIGHT})"
else
    echo "❌ Erro ao iniciar Xvfb"
    exit 1
fi

# Configurar variáveis
export DISPLAY=:99

# Iniciar aplicação Python
echo "🚀 Iniciando proxy Python..."
python3 app.py

# Cleanup ao sair
=======
#!/bin/bash

echo "🐳 Iniciando container com Xvfb..."

# Iniciar Xvfb (display virtual)
echo "📺 Iniciando display virtual..."
Xvfb :99 -screen 0 ${SCREEN_WIDTH}x${SCREEN_HEIGHT}x${SCREEN_DEPTH} > /dev/null 2>&1 &
XVFB_PID=$!

# Aguardar Xvfb inicializar
sleep 2

# Verificar se Xvfb está rodando
if ps -p $XVFB_PID > /dev/null; then
    echo "✅ Display virtual :99 criado (${SCREEN_WIDTH}x${SCREEN_HEIGHT})"
else
    echo "❌ Erro ao iniciar Xvfb"
    exit 1
fi

# Configurar variáveis
export DISPLAY=:99

# Iniciar aplicação Python
echo "🚀 Iniciando proxy Python..."
python3 app.py

# Cleanup ao sair
trap "kill $XVFB_PID" EXIT