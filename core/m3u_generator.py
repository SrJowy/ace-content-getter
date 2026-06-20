"""
Generación y procesamiento de archivos M3U
"""

import requests

from config import M3U_URL, OLD_IP, NEW_IP
from utils.logger import setup_logger
from .m3u_parser import M3UParser

logger = setup_logger(__name__)


def generate_m3u_with_streams(base_content, streams, m3u_modification_manager):
    """
    Genera contenido M3U combinando la URL principal + streams personalizados,
    aplicando modificaciones.
    
    Args:
        base_content (str): Contenido base del M3U original
        streams (list): Lista de streams personalizados
        m3u_modification_manager: Instancia de M3UModificationManager
    
    Returns:
        str: Contenido M3U generado con todas las modificaciones aplicadas
    """
    # Parsear el contenido base para extraer streams del M3U original
    m3u_streams = M3UParser.parse_m3u(base_content)
    
    # Aplicar modificaciones a los streams del M3U
    deleted_ids = m3u_modification_manager.get_all_deleted_ids()
    m3u_streams = [s for s in m3u_streams if s['id'] not in deleted_ids]
    
    # Aplicar cambios a streams modificados
    for stream in m3u_streams:
        modification = m3u_modification_manager.get_modification(stream['id'])
        if modification:
            stream['name'] = modification['name'] or stream['name']
            stream['logo'] = modification['logo'] or stream['logo']
            stream['group'] = modification['group'] or stream['group']
    
    # Asegurarse que empieza con header
    if not base_content.startswith('#EXTM3U'):
        content = '#EXTM3U\n'
    else:
        content = '#EXTM3U\n'
    
    # Agregar streams del M3U modificados
    for stream in m3u_streams:
        extinf = f"#EXTINF:-1"
        
        if stream.get('id'):
            extinf += f" tvg-id=\"{stream['id']}\""
        
        if stream.get('name'):
            extinf += f" tvg-name=\"{stream['name']}\""
        
        if stream.get('logo'):
            extinf += f" tvg-logo=\"{stream['logo']}\""
        
        if stream.get('group'):
            extinf += f" group-title=\"{stream['group']}\""
        
        extinf += f", {stream['name']}\n{stream['url']}\n"
        content += extinf
    
    # Agregar streams personalizados
    if streams:
        for stream in streams:
            extinf = f"#EXTINF:-1"
            
            if stream.get('id'):
                extinf += f" tvg-id=\"{stream['id']}\""
            
            if stream.get('name'):
                extinf += f" tvg-name=\"{stream['name']}\""
            
            if stream.get('logo'):
                extinf += f" tvg-logo=\"{stream['logo']}\""
            
            if stream.get('group'):
                extinf += f" group-title=\"{stream['group']}\""
            
            extinf += f", {stream['name']}\n{stream['url']}\n"
            content += extinf
    
    return content


def download_and_modify_m3u(stream_manager, m3u_modification_manager):
    """
    Descarga el archivo m3u principal y lo combina con streams personalizados,
    aplicando reemplazo de IPs.
    
    Args:
        stream_manager: Instancia de StreamManager
        m3u_modification_manager: Instancia de M3UModificationManager
    
    Returns:
        str: Contenido M3U modificado con reemplazo de IPs
    
    Raises:
        Exception: Si hay error al procesar los archivos
    """
    try:
        combined_content = ""
        
        # Descargar URL principal
        try:
            logger.info(f"Descargando m3u principal desde: {M3U_URL}")
            response = requests.get(M3U_URL, timeout=10)
            response.raise_for_status()
            combined_content = response.text
            logger.info(f"URL principal descargada ({len(response.text)} bytes)")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al descargar URL principal: {e}")
            logger.warning("Iniciando con contenido vacío")
            combined_content = "#EXTM3U\n"
        
        # Obtener streams personalizados
        streams = stream_manager.get_streams()
        
        # Generar el M3U combinado
        combined_content = generate_m3u_with_streams(
            combined_content, 
            streams, 
            m3u_modification_manager
        )
        
        if not combined_content:
            raise Exception("No se pudo generar contenido M3U")
        
        # Realizar el reemplazo
        modified_content = combined_content.replace(OLD_IP, NEW_IP)
        
        logger.info(f"Reemplazo completado: {OLD_IP} -> {NEW_IP}")
        logger.info(f"Streams personalizados incluidos: {len(streams)}")
        logger.info(f"Tamaño original: {len(combined_content)} bytes")
        logger.info(f"Tamaño modificado: {len(modified_content)} bytes")
        
        return modified_content
        
    except Exception as e:
        logger.error(f"Error al procesar los archivos: {e}")
        raise


__all__ = ['generate_m3u_with_streams', 'download_and_modify_m3u']
