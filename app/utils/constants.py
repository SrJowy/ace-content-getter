"""
Constantes globales de la aplicación
"""

# Categorías de canales para parser
CHANNEL_CATEGORIES = {
    'LaLiga': ['la liga', 'laliga'],
    'DAZN': ['dazn'],
    'Eurosport': ['eurosport'],
    'M+ Deportes': ['m+ deportes'],
    '1RFEF': ['1rfef', 'rfef'],
}

DEFAULT_CATEGORY = 'OTROS'

# Headers HTTP
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

# Configuración de M3U
M3U_HEADER = '#EXTM3U url-tvg="https://raw.githubusercontent.com/davidmuma/EPG_dobleM/refs/heads/master/guiatv.xml,https://epgshare01.online/epgshare01/epg_ripper_NL1.xml.gz,https://raw.githubusercontent.com/davidmuma/EPG_dobleM/master/guiatv.xml" refresh="3600"\n#EXTVLCOPT:network-caching=1000\n\n'

# Protocos permitidos para URLs
ALLOWED_PROTOCOLS = ('http://', 'https://', 'rtmp://', 'rtmps://')

# Timeout por defecto para requests
DEFAULT_TIMEOUT = 10

# Permisos por defecto
DEFAULT_MKDIR_MODE = 0o777
