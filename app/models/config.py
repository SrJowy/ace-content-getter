"""
Gestión de configuración persistente (config.json)
Controla el modo de origen M3U (online vs parser)
"""

import json
import os
import threading
from datetime import datetime
from typing import Tuple
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ConfigManager:
    """Clase para gestionar la configuración persistente de la aplicación"""
    
    def __init__(self, file_path: str):
        """
        Inicializa el gestor de configuración
        
        Args:
            file_path: Ruta al archivo de configuración (config.json)
        """
        self.file_path = file_path
        self.lock = threading.Lock()
        self._ensure_file_exists()
    
    def _ensure_file_exists(self) -> None:
        """Crea el archivo de configuración si no existe con valores por defecto"""
        if not os.path.exists(self.file_path):
            # Crear directorio padre si no existe
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            
            default_config = {
                'source': 'online',  # 'online' o 'parser'
                'last_parser_run': None,
                'created_at': datetime.now().isoformat()
            }
            self._save_config(default_config)
    
    def _get_config_unlocked(self) -> dict:
        """
        Obtiene la configuración sin usar lock (para uso interno)
        
        Returns:
            Diccionario con la configuración
        """
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error al leer configuración: {e}")
            return {'source': 'online'}
    
    def get_config(self) -> dict:
        """
        Obtiene toda la configuración actual
        
        Returns:
            Diccionario con la configuración
        """
        with self.lock:
            return self._get_config_unlocked()
    
    def get_source(self) -> str:
        """
        Obtiene el modo de origen actual
        
        Returns:
            'online' o 'parser'
        """
        config = self.get_config()
        return config.get('source', 'online')
    
    def set_source(self, source: str) -> Tuple[bool, str]:
        """
        Establece el modo de origen ('online' o 'parser')
        
        Args:
            source: Modo a establecer ('online' o 'parser')
        
        Returns:
            Tupla (éxito, mensaje)
        """
        if source not in ('online', 'parser'):
            return False, "source debe ser 'online' o 'parser'"
        
        with self.lock:
            try:
                config = self._get_config_unlocked()
                config['source'] = source
                config['updated_at'] = datetime.now().isoformat()
                self._save_config(config)
                logger.info(f"Configuración de origen actualizada a: {source}")
                return True, "Configuración actualizada"
            except Exception as e:
                logger.error(f"Error al actualizar configuración: {e}")
                return False, str(e)
    
    def update_last_parser_run(self) -> None:
        """Actualiza la marca de tiempo de última ejecución del parser"""
        with self.lock:
            try:
                config = self._get_config_unlocked()
                config['last_parser_run'] = datetime.now().isoformat()
                self._save_config(config)
                logger.debug("Timestamp de parser actualizado")
            except Exception as e:
                logger.error(f"Error al actualizar timestamp de parser: {e}")
    
    def _save_config(self, config: dict) -> None:
        """
        Guarda la configuración en el archivo
        
        Args:
            config: Diccionario con la configuración a guardar
        
        Raises:
            Exception: Si hay error al escribir el archivo
        """
        try:
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error al guardar configuración: {e}")
            raise
