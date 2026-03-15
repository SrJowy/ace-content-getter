#!/bin/bash

# Script para preparar el entorno Docker en Linux/Mac
# Ejecuta este script una única vez para configurar todo

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║        ACE Content Getter - Docker Setup para Linux/Mac            ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Verificar si Docker está instalado
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ ERROR: Docker no está instalado${NC}"
    echo ""
    echo "Instálalo con:"
    echo "  Ubuntu/Debian: sudo apt-get install docker.io docker compose"
    echo "  Mac: brew install --cask docker"
    echo "  Otros: https://docs.docker.com/get-docker/"
    exit 1
fi

echo -e "${GREEN}✓ Docker detectado${NC}"
docker --version

echo ""

# Verificar si docker compose está instalado
if ! command -v docker compose &> /dev/null; then
    if ! docker compose version &> /dev/null; then
        echo -e "${RED}✗ ERROR: Docker Compose no está disponible${NC}"
        echo ""
        echo "Instálalo con:"
        echo "  sudo apt-get install docker compose"
        echo "  o"
        echo "  pip install docker compose"
        exit 1
    else
        echo -e "${GREEN}✓ Docker Compose v2 detectado${NC}"
        docker compose version
    fi
else
    echo -e "${GREEN}✓ Docker Compose detectado${NC}"
    docker compose --version
fi

echo ""

# Crear archivo .env si no existe
if [ ! -f ".env" ]; then
    echo -e "${BLUE}Creando archivo .env...${NC}"
    cat > .env << 'EOF'
# URL del archivo m3u a descargar
M3U_URL=https://ipfs.io/ipns/k2k4r8oqlcjxsritt5mczkcn4mmvcmymbqw7113fz2flkrerfwfps004/data/listas/lista_iptv.m3u

# IP original a reemplazar
OLD_IP=127.0.0.1

# IP nueva
NEW_IP=192.168.1.151

# Intervalo de actualización
UPDATE_INTERVAL=12
EOF
    echo -e "${GREEN}✓ Archivo .env creado${NC}"
    echo ""
    echo -e "${BLUE}IMPORTANTE: Edita .env con tus valores${NC}"
    echo ""
else
    echo -e "${GREEN}✓ Archivo .env ya existe${NC}"
    echo ""
    echo "Para cambiar la configuración, edita el archivo .env"
    echo ""
fi

# Hacer ejecutable el script docker-docker.sh
if [ -f "docker-docker.sh" ]; then
    chmod +x docker-docker.sh
    echo -e "${GREEN}✓ Script docker-docker.sh hecho ejecutable${NC}"
fi

# Compilar la imagen
echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                        Compilando imagen...                         ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

docker compose build

if [ $? -eq 0 ]; then
    echo ""
    echo "╔════════════════════════════════════════════════════════════════════╗"
    echo "║                     ¡Setup completado!                             ║"
    echo "╚════════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Próximos pasos:"
    echo ""
    echo "1. Edita el archivo .env si quieres cambiar la configuración"
    echo ""
    echo "2. Inicia el contenedor con uno de estos comandos:"
    echo ""
    echo "   docker compose up -d"
    echo "   o"
    echo "   ./docker-docker.sh up"
    echo ""
    echo "3. Accede a http://localhost:8080/"
    echo ""
    echo "4. Ver logs con:"
    echo ""
    echo "   docker compose logs -f"
    echo "   o"
    echo "   ./docker-docker.sh logs"
    echo ""
    echo "Comandos útiles:"
    echo ""
    echo "   ./docker-docker.sh up          - Iniciar"
    echo "   ./docker-docker.sh down        - Detener"
    echo "   ./docker-docker.sh logs        - Ver logs"
    echo "   ./docker-docker.sh status      - Estado"
    echo "   ./docker-docker.sh restart     - Reiniciar"
    echo "   ./docker-docker.sh clean       - Limpiar todo"
    echo ""
else
    echo ""
    echo -e "${RED}✗ ERROR durante la compilación${NC}"
    echo ""
    exit 1
fi
