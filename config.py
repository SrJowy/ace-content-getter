"""
Configuración centralizada de la aplicación
"""

import os

# Variables de configuración desde variables de entorno
M3U_URL = "https://k2k4r8lm8tkmuxbc8lkmq1in3v0oya1p6pe9o5bu0hu30br5ko08k2gb.ipns.dweb.link/data/listas/lista_iptv.m3u" #os.getenv('M3U_URL', 'http://ejemplo.com/playlist.m3u')
SERVER_PORT = int(os.getenv('SERVER_PORT', 8082))
OLD_IP = os.getenv('OLD_IP', '127.0.0.1')
NEW_IP = os.getenv('NEW_IP', '192.168.1.151')
UPDATE_INTERVAL = int(os.getenv('UPDATE_INTERVAL', 12))  # Horas

# Configuración de directorios de datos
DATA_DIR = os.getenv('DATA_DIR', '/app/data')
CUSTOM_STREAMS_FILE = os.path.join(DATA_DIR, 'custom_streams.json')
M3U_MODIFICATIONS_FILE = os.path.join(DATA_DIR, 'm3u_modifications.json')

__all__ = [
    'M3U_URL',
    'SERVER_PORT',
    'OLD_IP',
    'NEW_IP',
    'UPDATE_INTERVAL',
    'DATA_DIR',
    'CUSTOM_STREAMS_FILE',
    'M3U_MODIFICATIONS_FILE'
]
