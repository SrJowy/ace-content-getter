"""
Gestión de caché en memoria para archivos M3U
"""

import threading
from datetime import datetime
from typing import Optional


class M3UCache:
    """Clase para gestionar el caché del archivo m3u en memoria"""
    
    def __init__(self):
        """Inicializa el caché vacío"""
        self.data: Optional[str] = None
        self.away_data: Optional[str] = None
        self.last_update: Optional[datetime] = None
        self.lock = threading.Lock()
        self.update_in_progress = False
        self.last_error: Optional[str] = None
    
    def is_valid(self) -> bool:
        """
        Verifica si el caché contiene datos válidos
        
        Returns:
            True si hay datos en caché, False en caso contrario
        """
        with self.lock:
            return self.data is not None
    
    def get(self) -> Optional[str]:
        """
        Obtiene el contenido en caché
        
        Returns:
            Contenido M3U en caché o None si está vacío
        """
        with self.lock:
            return self.data

    def get_away(self) -> Optional[str]:
        """
        Obtiene el contenido M3U alternativo con la IP away
        """
        with self.lock:
            return self.away_data
    
    def set(self, data: str) -> None:
        """
        Establece el contenido en caché
        
        Args:
            data: Contenido M3U a guardar
        """
        with self.lock:
            self.data = data
            self.last_update = datetime.now()
            self.last_error = None

    def set_away(self, data: str) -> None:
        """Establece el contenido M3U alternativo para la IP away."""
        with self.lock:
            self.away_data = data
            if self.last_update is None:
                self.last_update = datetime.now()
            self.last_error = None
    
    def set_error(self, error_msg: str) -> None:
        """
        Registra un error en la actualización
        
        Args:
            error_msg: Mensaje de error
        """
        with self.lock:
            self.last_error = error_msg
    
    def clear(self) -> None:
        """Limpia el caché"""
        with self.lock:
            self.data = None
            self.away_data = None
            self.last_update = None
            self.last_error = None
    
    def get_info(self) -> dict:
        """
        Obtiene información sobre el caché
        
        Returns:
            Diccionario con información del caché
        """
        with self.lock:
            return {
                'available': self.data is not None,
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'update_in_progress': self.update_in_progress,
                'last_error': self.last_error,
                'size_bytes': len(self.data) if self.data else 0,
                'away_size_bytes': len(self.away_data) if self.away_data else 0,
            }
