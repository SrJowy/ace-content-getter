"""
API routes - RESTful API endpoints for stream management
"""

from flask import Blueprint, jsonify, request

from models import StreamManager, M3UModificationManager
from core import M3UParser
from utils.logger import setup_logger

logger = setup_logger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Estas variables se inyectarán desde app.py
stream_manager = None
m3u_modification_manager = None
cache = None
update_cache_func = None


def init_api(sm, m3um, c, ucf):
    """Inicializa las dependencias del módulo API"""
    global stream_manager, m3u_modification_manager, cache, update_cache_func
    stream_manager = sm
    m3u_modification_manager = m3um
    cache = c
    update_cache_func = ucf


@api_bp.route('/streams', methods=['GET'])
def get_streams():
    """Obtiene la lista de streams personalizados"""
    try:
        streams = stream_manager.get_streams()
        return jsonify({'streams': streams, 'count': len(streams)}), 200
    except Exception as e:
        logger.error(f"Error al obtener streams: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/streams', methods=['POST'])
def add_stream():
    """Añade un nuevo stream personalizado"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        url = data.get('url', '').strip()
        logo = data.get('logo', '').strip()
        group = data.get('group', '').strip()
        
        if not name:
            return jsonify({'error': 'Nombre es requerido'}), 400
        
        if not url:
            return jsonify({'error': 'URL es requerida'}), 400
        
        # Validar que sea una URL válida
        if not url.startswith(('http://', 'https://', 'rtmp://', 'rtmps://')):
            return jsonify({'error': 'URL debe comenzar con http://, https://, rtmp:// o rtmps://'}), 400
        
        success, message = stream_manager.add_stream(name, url, logo, group)
        
        if success:
            # Forzar actualización del caché
            update_cache_func()
            return jsonify({'message': message}), 201
        else:
            return jsonify({'error': message}), 409
    except Exception as e:
        logger.error(f"Error al agregar stream: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/streams/<stream_id>', methods=['PUT'])
def update_stream_api(stream_id):
    """Actualiza un stream existente"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        url = data.get('url', '').strip()
        logo = data.get('logo', '').strip()
        group = data.get('group', '').strip()
        
        if not name:
            return jsonify({'error': 'Nombre es requerido'}), 400
        
        if not url:
            return jsonify({'error': 'URL es requerida'}), 400
        
        # Validar que sea una URL válida
        if not url.startswith(('http://', 'https://', 'rtmp://', 'rtmps://')):
            return jsonify({'error': 'URL debe comenzar con http://, https://, rtmp:// o rtmps://'}), 400
        
        success, message = stream_manager.update_stream(stream_id, name, url, logo, group)
        
        if success:
            # Forzar actualización del caché
            update_cache_func()
            return jsonify({'message': message}), 200
        else:
            return jsonify({'error': message}), 404
    except Exception as e:
        logger.error(f"Error al actualizar stream: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/streams/<stream_id>', methods=['DELETE'])
def delete_stream_api(stream_id):
    """Elimina un stream personalizado"""
    try:
        success, message = stream_manager.delete_stream(stream_id)
        
        if success:
            # Forzar actualización del caché
            update_cache_func()
            return jsonify({'message': message}), 200
        else:
            return jsonify({'error': message}), 404
    except Exception as e:
        logger.error(f"Error al eliminar stream: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/m3u-streams', methods=['GET'])
def get_m3u_streams():
    """Obtiene los streams del M3U actual (sin deleteos aplicados)"""
    try:
        # Obtener el contenido actual del caché
        m3u_content = cache.get()
        if not m3u_content:
            return jsonify({'streams': [], 'count': 0}), 200
        
        # Parsear el M3U
        streams = M3UParser.parse_m3u(m3u_content)
        
        # Filtrar streams eliminados
        deleted_ids = m3u_modification_manager.get_all_deleted_ids()
        active_streams = [s for s in streams if s['id'] not in deleted_ids]
        
        # Aplicar modificaciones
        for stream in active_streams:
            mod = m3u_modification_manager.get_modification(stream['id'])
            if mod:
                stream['name'] = mod['name'] or stream['name']
                stream['logo'] = mod['logo'] or stream['logo']
                stream['group'] = mod['group'] or stream['group']
        
        return jsonify({'streams': active_streams, 'count': len(active_streams)}), 200
    except Exception as e:
        logger.error(f"Error al obtener streams del M3U: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/m3u-streams/<stream_id>', methods=['PUT'])
def update_m3u_stream_api(stream_id):
    """Actualiza un stream del M3U"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        logo = data.get('logo', '').strip()
        group = data.get('group', '').strip()
        
        if not name:
            return jsonify({'error': 'Nombre es requerido'}), 400
        
        # Guardar la modificación
        m3u_modification_manager.update_stream(stream_id, name, logo, group)
        
        # Forzar actualización del caché
        update_cache_func()
        
        return jsonify({'message': 'Stream actualizado exitosamente'}), 200
    except Exception as e:
        logger.error(f"Error al actualizar stream del M3U: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/m3u-streams/<stream_id>', methods=['DELETE'])
def delete_m3u_stream_api(stream_id):
    """Elimina un stream del M3U (lo marca como eliminado)"""
    try:
        m3u_modification_manager.delete_stream(stream_id)
        
        # Forzar actualización del caché
        update_cache_func()
        
        return jsonify({'message': 'Stream eliminado exitosamente'}), 200
    except Exception as e:
        logger.error(f"Error al eliminar stream del M3U: {e}")
        return jsonify({'error': str(e)}), 500


__all__ = ['api_bp', 'init_api']
