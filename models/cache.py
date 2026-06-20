"""
Gestión de caché para archivos M3U
"""

import threading
from datetime import datetime


class M3UCache:
    """Clase para gestionar el caché del archivo m3u"""
    
    def __init__(self):
        self.data = None
        self.last_update = None
        self.lock = threading.Lock()
        self.update_in_progress = False
        self.last_error = None
    
    def is_valid(self):
        """Verifica si el caché es válido"""
        return self.data is not None
    
    def get(self):
        """Obtiene el contenido en caché"""
        with self.lock:
            return self.data
    
    def set(self, data):
        """Establece el contenido en caché"""
        with self.lock:
            self.data = data
            self.last_update = datetime.now()
            self.last_error = None
    
    def set_error(self, error_msg):
        """Registra un error en la actualización"""
        with self.lock:
            self.last_error = error_msg


__all__ = ['M3UCache']
