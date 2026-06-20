"""
Gestión de streams personalizados
"""

import os
import json
import threading
from datetime import datetime

from config import CUSTOM_STREAMS_FILE
from utils.logger import setup_logger

logger = setup_logger(__name__)


class StreamManager:
    """Clase para gestionar streams personalizados (URLs individuales)"""
    
    def __init__(self, file_path=CUSTOM_STREAMS_FILE):
        self.file_path = file_path
        self.lock = threading.Lock()
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Crea el archivo si no existe"""
        if not os.path.exists(self.file_path):
            self._save_streams([])
    
    def get_streams(self):
        """Obtiene todos los streams personalizados"""
        with self.lock:
            return self._get_streams_unlocked()
    
    def _get_streams_unlocked(self):
        """Obtiene streams sin usar lock (para uso interno)"""
        logger.info(f"Obteniendo streams personalizados desde: {self.file_path}")
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error al leer streams: {e}")
            return []
    
    def add_stream(self, name, url, logo='', group=''):
        """Añade un nuevo stream personalizado"""
        with self.lock:
            try:
                streams = self._get_streams_unlocked()
                
                # Verificar que no sea duplicada
                if any(s['url'] == url for s in streams):
                    return False, "URL ya existe"
                
                # Generar ID único
                stream_id = f"stream_{len(streams)}_{int(datetime.now().timestamp())}"
                
                streams.append({
                    'id': stream_id,
                    'name': name.strip(),
                    'url': url.strip(),
                    'logo': logo.strip(),
                    'group': group.strip() or 'Sin categoría',
                    'added_at': datetime.now().isoformat()
                })
                self._save_streams(streams)
                logger.info(f"Stream agregado: {name} ({url})")
                return True, "Stream agregado exitosamente"
            except Exception as e:
                logger.error(f"Error al agregar stream: {e}")
                return False, str(e)
    
    def update_stream(self, stream_id, name, url, logo='', group=''):
        """Actualiza un stream existente"""
        with self.lock:
            try:
                streams = self._get_streams_unlocked()
                
                # Buscar el stream
                stream = next((s for s in streams if s['id'] == stream_id), None)
                if not stream:
                    return False, "Stream no encontrado"
                
                # Verificar URL duplicada (en otro stream)
                if any(s['url'] == url and s['id'] != stream_id for s in streams):
                    return False, "URL ya existe en otro stream"
                
                stream['name'] = name.strip()
                stream['url'] = url.strip()
                stream['logo'] = logo.strip()
                stream['group'] = group.strip() or 'Sin categoría'
                
                self._save_streams(streams)
                logger.info(f"Stream actualizado: {name}")
                return True, "Stream actualizado exitosamente"
            except Exception as e:
                logger.error(f"Error al actualizar stream: {e}")
                return False, str(e)
    
    def delete_stream(self, stream_id):
        """Elimina un stream personalizado"""
        with self.lock:
            try:
                streams = self._get_streams_unlocked()
                stream = next((s for s in streams if s['id'] == stream_id), None)
                
                if not stream:
                    return False, "Stream no encontrado"
                
                streams = [s for s in streams if s['id'] != stream_id]
                self._save_streams(streams)
                logger.info(f"Stream eliminado: {stream['name']}")
                return True, "Stream eliminado exitosamente"
            except Exception as e:
                logger.error(f"Error al eliminar stream: {e}")
                return False, str(e)
    
    def _save_streams(self, streams):
        """Guarda los streams en el archivo"""
        try:
            # Asegurar que el directorio existe
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(streams, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error al guardar streams: {e}")
            raise


__all__ = ['StreamManager']
