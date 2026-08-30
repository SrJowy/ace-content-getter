"""
Configuración centralizada de la aplicación
Carga todas las variables de entorno
"""

import os
from pathlib import Path

# Directorio raíz del proyecto
PROJECT_ROOT = Path(__file__).parent.parent

# Configuración del servidor
SERVER_PORT = int(os.getenv('SERVER_PORT', 8082))
SERVER_HOST = os.getenv('SERVER_HOST', '0.0.0.0')
DEBUG_MODE = os.getenv('DEBUG', 'false').lower() == 'true'

# URLs y configuración de M3U
M3U_URL = os.getenv('M3U_URL', 'http://ejemplo.com/playlist.m3u')
SCRAPE_URL = os.getenv('SCRAPE_URL', 'https://ciriaco.netlify.app/')

# Reemplazo de IP
OLD_IP = os.getenv('OLD_IP', '127.0.0.1')
NEW_IP = os.getenv('NEW_IP', '192.168.1.151')
AWAY_IP = os.getenv('AWAY_IP', '100.80.52.89')

# Intervalos de actualización (en horas)
UPDATE_INTERVAL = int(os.getenv('UPDATE_INTERVAL', 12))  # Modo online
PARSER_UPDATE_INTERVAL = int(os.getenv('PARSER_UPDATE_INTERVAL', 6))  # Modo parser

# Directorio de datos
DATA_DIR = os.getenv('DATA_DIR', str(PROJECT_ROOT / 'data'))
CUSTOM_STREAMS_FILE = os.path.join(DATA_DIR, 'custom_streams.json')
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


def get_config() -> dict:
    """Retorna un diccionario con toda la configuración"""
    return {
        'server': {
            'port': SERVER_PORT,
            'host': SERVER_HOST,
            'debug': DEBUG_MODE,
        },
        'm3u': {
            'url': M3U_URL,
            'scrape_url': SCRAPE_URL,
        },
        'ip_replacement': {
            'old_ip': OLD_IP,
            'new_ip': NEW_IP,
            'away_ip': AWAY_IP,
        },
        'intervals': {
            'online': UPDATE_INTERVAL,
            'parser': PARSER_UPDATE_INTERVAL,
        },
        'paths': {
            'data_dir': DATA_DIR,
            'custom_streams_file': CUSTOM_STREAMS_FILE,
            'config_file': CONFIG_FILE,
        },
        'logging': {
            'level': LOG_LEVEL,
            'format': LOG_FORMAT,
        },
    }
