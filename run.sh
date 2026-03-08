#!/bin/bash

# Script para ejecutar ACE Content Getter en Linux/Mac

# Variables de entorno con valores por defecto
export M3U_URL="${M3U_URL:-http://ejemplo.com/playlist.m3u}"
export SERVER_PORT="${SERVER_PORT:-8080}"
export OLD_IP="${OLD_IP:-127.0.0.1}"
export NEW_IP="${NEW_IP:-192.168.1.151}"

echo ""
echo "===================================="
echo "  ACE Content Getter"
echo "===================================="
echo ""
echo "Configuración:"
echo "  URL del m3u: $M3U_URL"
echo "  Puerto: $SERVER_PORT"
echo "  IP original: $OLD_IP"
echo "  IP nueva: $NEW_IP"
echo ""
echo "Accede a http://localhost:$SERVER_PORT/"
echo ""
echo "===================================="
echo ""

python3 app.py
