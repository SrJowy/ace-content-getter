#!/bin/bash

# Script para gestionar Docker Compose fácilmente en Linux/Mac

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para mostrar help
show_help() {
    cat << 'EOF'

╔════════════════════════════════════════════════════════════════════╗
║        ACE Content Getter - Docker Management Script               ║
╚════════════════════════════════════════════════════════════════════╝

Uso: ./docker-docker.sh [opción]

Opciones disponibles:

  up          - Iniciar el contenedor
  down        - Detener el contenedor
  restart     - Reiniciar el contenedor
  logs        - Ver logs en tiempo real
  status      - Ver estado del contenedor
  build       - Compilar la imagen Docker
  rebuild     - Recompilar sin caché
  shell       - Abrir shell dentro del contenedor
  test        - Probar conectividad
  clean       - Detener y eliminar todo (volúmenes incluidos)

Ejemplos:

  ./docker-docker.sh up              # Inicia el contenedor
  ./docker-docker.sh logs            # Ver logs del contenedor
  ./docker-docker.sh status          # Ver estado

Configuración:
  - Editar .env para cambiar variables
  - Editar docker-compose.yml para cambiar puertos/recursos

EOF
}

# Función auxiliar para imprimir
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Verificar si docker-compose existe
if ! command -v docker compose &> /dev/null && ! command -v docker &> /dev/null; then
    print_error "Docker o Docker Compose no está instalado"
    exit 1
fi

# Procesar comandos
case "${1:-}" in
    up)
        print_info "Iniciando contenedor..."
        docker compose up -d
        print_success "Contenedor iniciado exitosamente"
        echo ""
        echo "Accede a: http://localhost:8080/"
        echo ""
        print_info "Para ver logs: ./docker-docker.sh logs"
        ;;
    
    down)
        print_info "Deteniendo contenedor..."
        docker compose down
        print_success "Contenedor detenido"
        ;;
    
    restart)
        print_info "Reiniciando contenedor..."
        docker compose restart ace-content-getter
        print_success "Contenedor reiniciado"
        ;;
    
    logs)
        echo "Mostrando logs en tiempo real (presiona Ctrl+C para salir)..."
        docker compose logs -f ace-content-getter
        ;;
    
    status)
        echo "Estado del contenedor:"
        docker compose ps
        ;;
    
    build)
        print_info "Compilando imagen..."
        docker compose build
        print_success "Imagen compilada exitosamente"
        ;;
    
    rebuild)
        print_info "Recompilando imagen sin caché..."
        docker compose build --no-cache
        print_success "Imagen recompilada exitosamente"
        ;;
    
    shell)
        print_info "Abriendo shell dentro del contenedor..."
        docker compose exec ace-content-getter /bin/bash
        ;;
    
    test)
        print_info "Probando conectividad..."
        if docker compose exec ace-content-getter curl -s http://localhost:8080/health > /dev/null 2>&1; then
            print_success "Servidor respondiendo correctamente"
            docker compose exec ace-content-getter curl -s http://localhost:8080/health | jq . 2>/dev/null || echo ""
        else
            print_error "El servidor no está respondiendo"
            exit 1
        fi
        ;;
    
    clean)
        print_info "Limpiando contenedores y volúmenes..."
        docker compose down -v
        print_success "Limpieza completada"
        ;;
    
    "")
        show_help
        ;;
    
    *)
        print_error "Comando desconocido: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
