"""
Generador de contenido M3U
Combina contenido M3U base con streams personalizados
"""

from typing import List, Dict
from app.utils.logger import get_logger
from app.utils.constants import M3U_HEADER, CHANNEL_CATEGORIES

logger = get_logger(__name__)


class M3UGenerator:
    """Clase para generar contenido M3U"""
    
    def __init__(self):
        """Inicializa el generador"""
        pass
    
    def generate_content(self, base_content: str, custom_streams: List[Dict[str, str]] = None) -> str:
        """
        Genera contenido M3U combinando contenido base + streams personalizados
        
        Args:
            base_content: Contenido M3U base (desde URL o parser)
            custom_streams: Lista de streams personalizados agregados por el usuario
        
        Returns:
            Contenido M3U combinado
        """
        # Asegurar que empieza con header M3U
        if not base_content.startswith('#EXTM3U'):
            content = '#EXTM3U\n' + base_content
        else:
            content = base_content
        
        # Agregar streams personalizados
        if custom_streams:
            if not content.endswith('\n'):
                content += '\n'
            
            for stream in custom_streams:
                extinf = self._build_extinf_line(stream)
                content += extinf + f"{stream['url']}\n"
        
        return content
    
    def _build_extinf_line(self, stream: Dict[str, str]) -> str:
        """
        Construye la línea EXTINF para un stream
        
        Args:
            stream: Diccionario con datos del stream
        
        Returns:
            Línea EXTINF formateada
        """
        extinf = "#EXTINF:-1"
        
        if stream.get('id'):
            extinf += f" tvg-id=\"{stream['id']}\""
        
        if stream.get('name'):
            extinf += f" tvg-name=\"{stream['name']}\""
        
        if stream.get('logo'):
            extinf += f" tvg-logo=\"{stream['logo']}\""
        
        if stream.get('group'):
            extinf += f" group-title=\"{stream['group']}\""
        
        extinf += f", {stream['name']}\n"
        return extinf
    
    def apply_ip_replacement(self, content: str, old_ip: str, new_ip: str) -> str:
        """
        Reemplaza IPs en el contenido M3U
        
        Args:
            content: Contenido M3U
            old_ip: IP a reemplazar
            new_ip: Nueva IP
        
        Returns:
            Contenido con IPs reemplazadas
        """
        return content.replace(old_ip, new_ip)
    
    @staticmethod
    def generate_with_categories(acestream_links: List[Dict[str, str]]) -> str:
        """
        Genera contenido M3U desde acestream links agrupados por categoría
        
        Args:
            acestream_links: Lista de enlaces acestream categorizados
        
        Returns:
            Contenido M3U como string
        """
        if not acestream_links:
            return None
        
        try:
            # Agrupar por categoría
            categories = {}
            for category in list(CHANNEL_CATEGORIES.keys()) + ['OTROS']:
                categories[category] = []
            
            for link in acestream_links:
                category = link.get('category', 'OTROS')
                if category not in categories:
                    categories[category] = []
                categories[category].append(link)
            
            # Generar contenido
            content = M3U_HEADER
            
            # Escribir canales agrupados por categoría
            for category in list(CHANNEL_CATEGORIES.keys()) + ['OTROS']:
                if categories.get(category):
                    for link in categories[category]:
                        channel_name = _get_channel_name(link['name'])
                        content += f"#EXTINF:-1, tvg-id=\"{channel_name}\",group-title=\"{category}\",{link['name']}\n"
                        content += f"{link['url']}\n"
            
            logger.info(f"Contenido M3U generado: {len(acestream_links)} streams")
            return content
            
        except Exception as e:
            logger.error(f"Error generando contenido M3U: {e}")
            return None


def _get_channel_name(channel_name: str) -> str:
    """
    Genera un tvg-id válido desde el nombre del canal
    
    Args:
        channel_name: Nombre del canal
    
    Returns:
        tvg-id limpio
    """
    splitter = re.split(r'1080p|720p|-->|\*', channel_name)
    tvg_id = splitter[0].strip()
    return tvg_id


import re
