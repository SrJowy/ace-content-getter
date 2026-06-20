"""
Gestión de modificaciones de streams del M3U (ediciones y eliminaciones)
"""

import os
import json
import threading

from config import M3U_MODIFICATIONS_FILE
from utils.logger import setup_logger

logger = setup_logger(__name__)


class M3UModificationManager:
    """Gestiona las modificaciones (ediciones y eliminaciones) de streams del M3U"""
    
    def __init__(self, file_path=M3U_MODIFICATIONS_FILE):
        self.file_path = file_path
        self.lock = threading.Lock()
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Crea el archivo si no existe"""
        if not os.path.exists(self.file_path):
            self._save_modifications({'deleted_ids': [], 'modified_streams': {}})
    
    def _get_modifications(self):
        """Obtiene las modificaciones sin lock"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error al leer modificaciones: {e}")
            return {'deleted_ids': [], 'modified_streams': {}}
    
    def _save_modifications(self, modifications):
        """Guarda las modificaciones"""
        try:
            # Asegurar que el directorio existe
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(modifications, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error al guardar modificaciones: {e}")
            raise
    
    def delete_stream(self, stream_id):
        """Marca un stream como eliminado"""
        with self.lock:
            mods = self._get_modifications()
            if stream_id not in mods['deleted_ids']:
                mods['deleted_ids'].append(stream_id)
            self._save_modifications(mods)
    
    def restore_stream(self, stream_id):
        """Restaura un stream eliminado"""
        with self.lock:
            mods = self._get_modifications()
            if stream_id in mods['deleted_ids']:
                mods['deleted_ids'].remove(stream_id)
            self._save_modifications(mods)
    
    def update_stream(self, stream_id, name, logo='', group=''):
        """Modifica un stream del M3U"""
        with self.lock:
            mods = self._get_modifications()
            mods['modified_streams'][stream_id] = {
                'name': name.strip(),
                'logo': logo.strip(),
                'group': group.strip()
            }
            self._save_modifications(mods)
    
    def is_deleted(self, stream_id):
        """Verifica si un stream está marcado como eliminado"""
        mods = self._get_modifications()
        return stream_id in mods['deleted_ids']
    
    def get_modification(self, stream_id):
        """Obtiene la modificación de un stream"""
        mods = self._get_modifications()
        return mods['modified_streams'].get(stream_id, None)
    
    def get_all_deleted_ids(self):
        """Obtiene todos los IDs de streams eliminados"""
        mods = self._get_modifications()
        return mods['deleted_ids']


__all__ = ['M3UModificationManager']
