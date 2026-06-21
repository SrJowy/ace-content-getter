"""
Actualización de caché
Orquesta la descarga y generación de contenido M3U
"""

import requests
from app.utils.logger import get_logger
from app.utils.constants import DEFAULT_TIMEOUT
from app.models.cache import M3UCache
from app.models.config import ConfigManager
from app.services.acestream_parser import AcestreamParser
from app.services.m3u_generator import M3UGenerator
from app.services.stream_manager import StreamManager

logger = get_logger(__name__)


class CacheUpdater:
    """Orquesta la descarga y actualización del caché M3U"""
    
    def __init__(
        self,
        cache: M3UCache,
        config_manager: ConfigManager,
        stream_manager: StreamManager,
        m3u_url: str,
        old_ip: str,
        new_ip: str,
    ):
        """
        Inicializa el actualizador de caché
        
        Args:
            cache: Instancia del caché M3U
            config_manager: Gestor de configuración
            stream_manager: Gestor de streams personalizados
            m3u_url: URL del M3U online
            old_ip: IP a reemplazar
            new_ip: Nueva IP
        """
        self.cache = cache
        self.config_manager = config_manager
        self.stream_manager = stream_manager
        self.m3u_url = m3u_url
        self.old_ip = old_ip
        self.new_ip = new_ip
        self.parser = AcestreamParser()
        self.m3u_generator = M3UGenerator()
    
    def fetch_from_parser(self, scrape_url: str = None) -> str:
        """
        Obtiene contenido M3U ejecutando el parser local
        
        Args:
            scrape_url: URL a scrapear (usa default del parser si no se especifica)
        
        Returns:
            Contenido M3U o None si hay error
        """
        try:
            logger.info("Ejecutando parser local para obtener streams...")
            
            # Procesar enlaces
            links = self.parser.process_links(scrape_url)
            if not links:
                logger.warning("El parser no encontró streams")
                return None
            
            logger.info(f"Parser completado: {len(links)} streams únicos")
            
            # Generar contenido M3U
            content = M3UGenerator.generate_with_categories(links)
            
            if content:
                self.config_manager.update_last_parser_run()
                return content
            else:
                logger.error("El parser no generó contenido M3U válido")
                return None
                
        except Exception as e:
            logger.error(f"Error ejecutando parser: {e}")
            return None
    
    def fetch_from_online_url(self, url: str = None) -> str:
        """
        Descarga M3U desde URL online
        
        Args:
            url: URL a descargar (usa m3u_url configurada si no se especifica)
        
        Returns:
            Contenido M3U o None si hay error
        """
        target_url = url or self.m3u_url
        
        try:
            logger.info(f"[ONLINE MODE] Descargando m3u principal desde: {target_url}")
            response = requests.get(target_url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            
            logger.info(f"URL principal descargada ({len(response.text)} bytes)")
            return response.text
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al descargar URL principal: {e}")
            return None
    
    def update(self) -> bool:
        """
        Actualiza el caché con contenido M3U
        
        Returns:
            True si la actualización fue exitosa, False en caso contrario
        """
        if self.cache.update_in_progress:
            logger.info("Una actualización ya está en progreso, saltando...")
            return False
        
        self.cache.update_in_progress = True
        
        try:
            source = self.config_manager.get_source()
            logger.info(f"[ACTUALIZACIÓN] Obteniendo contenido en modo {source.upper()}")
            
            # Obtener contenido según la fuente
            if source == 'parser':
                base_content = self.fetch_from_parser()
            else:  # online (default)
                base_content = self.fetch_from_online_url()
            
            if not base_content:
                error_msg = f"Falló obtener contenido M3U desde {source}"
                logger.error(error_msg)
                self.cache.set_error(error_msg)
                return False
            
            # Obtener streams personalizados
            streams = self.stream_manager.get_streams()
            
            # Generar M3U combinado
            combined_content = self.m3u_generator.generate_content(base_content, streams)
            
            if not combined_content:
                error_msg = "No se pudo generar contenido M3U"
                logger.error(error_msg)
                self.cache.set_error(error_msg)
                return False
            
            # Reemplazar IPs
            modified_content = self.m3u_generator.apply_ip_replacement(
                combined_content,
                self.old_ip,
                self.new_ip
            )
            
            # Guardar en caché
            self.cache.set(modified_content)
            
            logger.info(f"Reemplazo completado: {self.old_ip} -> {self.new_ip}")
            logger.info(f"Streams personalizados incluidos: {len(streams)}")
            logger.info(f"Tamaño original: {len(combined_content)} bytes")
            logger.info(f"Tamaño modificado: {len(modified_content)} bytes")
            logger.info("[ACTUALIZACIÓN] Caché actualizado exitosamente")
            
            return True
            
        except Exception as e:
            error_msg = f"Error al actualizar caché: {str(e)}"
            logger.error(error_msg)
            self.cache.set_error(error_msg)
            return False
            
        finally:
            self.cache.update_in_progress = False
