"""
Rutas API de Flask
Expone todos los endpoints de la aplicación
"""

from io import BytesIO
from flask import Blueprint, send_file, jsonify, request, render_template
from app.utils.logger import get_logger
from app.models.cache import M3UCache
from app.models.config import ConfigManager
from app.services.stream_manager import StreamManager
from app.services.cache_updater import CacheUpdater

logger = get_logger(__name__)


class APIRoutes:
    """Gestor de rutas API Flask"""
    
    def __init__(
        self,
        cache: M3UCache,
        config_manager: ConfigManager,
        stream_manager: StreamManager,
        cache_updater: CacheUpdater,
        m3u_url: str,
        update_interval: int,
        parser_update_interval: int,
    ):
        """
        Inicializa las rutas
        
        Args:
            cache: Instancia del caché
            config_manager: Gestor de configuración
            stream_manager: Gestor de streams
            cache_updater: Actualizador de caché
            m3u_url: URL del M3U configurada
            update_interval: Intervalo de actualización online
            parser_update_interval: Intervalo de actualización parser
        """
        self.cache = cache
        self.config_manager = config_manager
        self.stream_manager = stream_manager
        self.cache_updater = cache_updater
        self.m3u_url = m3u_url
        self.update_interval = update_interval
        self.parser_update_interval = parser_update_interval
        
        self.blueprint = Blueprint('api', __name__)
        self._register_routes()
    
    def _register_routes(self):
        """Registra todas las rutas en el blueprint"""
        self.blueprint.route('/stream.m3u')(self.serve_m3u)
        self.blueprint.route('/health')(self.health)
        self.blueprint.route('/status')(self.status)
        self.blueprint.route('/api/streams', methods=['GET'])(self.get_streams)
        self.blueprint.route('/api/streams', methods=['POST'])(self.add_stream)
        self.blueprint.route('/api/streams/<stream_id>', methods=['PUT'])(self.update_stream)
        self.blueprint.route('/api/streams/<stream_id>', methods=['DELETE'])(self.delete_stream)
        self.blueprint.route('/api/config/source', methods=['POST'])(self.set_source_config)
        self.blueprint.route('/')(self.index)
    
    def serve_m3u(self):
        """Sirve el archivo m3u modificado desde caché"""
        try:
            # Si el caché no está disponible, actualizar ahora
            if not self.cache.is_valid():
                logger.info("Caché vacío, descargando...")
                self.cache_updater.update()
            
            modified_content = self.cache.get()
            
            if modified_content is None:
                return {'error': 'No se pudo obtener el archivo m3u'}, 503
            
            # Crear un archivo en memoria
            file_stream = BytesIO(modified_content.encode('utf-8'))
            
            return send_file(
                file_stream,
                mimetype='application/vnd.apple.mpegurl',
                as_attachment=True,
                download_name='stream.m3u'
            )
        except Exception as e:
            logger.error(f"Error al servir el archivo: {e}")
            return {'error': str(e)}, 500
    
    def health(self):
        """Endpoint para verificar que el servidor está activo"""
        if self.cache.is_valid():
            return {'status': 'ok', 'cache': 'ready'}, 200
        else:
            return {'status': 'ok', 'cache': 'not-ready'}, 200
    
    def status(self):
        """Endpoint para obtener el estado de la aplicación"""
        cache_info = self.cache.get_info()
        source = self.config_manager.get_source()
        current_interval = self.parser_update_interval if source == 'parser' else self.update_interval
        
        status_info = {
            'server': 'running',
            'cache': cache_info,
            'configuration': {
                'source': source,
                'update_interval_hours': current_interval,
                'm3u_url': self.m3u_url,
            }
        }
        return jsonify(status_info), 200
    
    def get_streams(self):
        """Obtiene la lista de streams personalizados"""
        try:
            streams = self.stream_manager.get_streams()
            return jsonify({'streams': streams, 'count': len(streams)}), 200
        except Exception as e:
            logger.error(f"Error al obtener streams: {e}")
            return jsonify({'error': str(e)}), 500
    
    def add_stream(self):
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
            from app.utils.constants import ALLOWED_PROTOCOLS
            if not url.startswith(ALLOWED_PROTOCOLS):
                return jsonify({
                    'error': f'URL debe comenzar con {", ".join(ALLOWED_PROTOCOLS)}'
                }), 400
            
            success, message = self.stream_manager.add_stream(name, url, logo, group)
            
            if success:
                # Forzar actualización del caché
                self.cache_updater.update()
                return jsonify({'message': message}), 201
            else:
                return jsonify({'error': message}), 409
        except Exception as e:
            logger.error(f"Error al agregar stream: {e}")
            return jsonify({'error': str(e)}), 500
    
    def update_stream(self, stream_id):
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
            from app.utils.constants import ALLOWED_PROTOCOLS
            if not url.startswith(ALLOWED_PROTOCOLS):
                return jsonify({
                    'error': f'URL debe comenzar con {", ".join(ALLOWED_PROTOCOLS)}'
                }), 400
            
            success, message = self.stream_manager.update_stream(stream_id, name, url, logo, group)
            
            if success:
                # Forzar actualización del caché
                self.cache_updater.update()
                return jsonify({'message': message}), 200
            else:
                return jsonify({'error': message}), 404
        except Exception as e:
            logger.error(f"Error al actualizar stream: {e}")
            return jsonify({'error': str(e)}), 500
    
    def delete_stream(self, stream_id):
        """Elimina un stream personalizado"""
        try:
            success, message = self.stream_manager.delete_stream(stream_id)
            
            if success:
                # Forzar actualización del caché
                self.cache_updater.update()
                return jsonify({'message': message}), 200
            else:
                return jsonify({'error': message}), 404
        except Exception as e:
            logger.error(f"Error al eliminar stream: {e}")
            return jsonify({'error': str(e)}), 500
    
    def set_source_config(self):
        """Cambia la fuente de M3U (online u parser)"""
        try:
            data = request.get_json()
            source = data.get('source', '').strip().lower()
            
            if not source:
                return jsonify({'error': 'source es requerido'}), 400
            
            if source not in ('online', 'parser'):
                return jsonify({'error': 'source debe ser "online" o "parser"'}), 400
            
            # Cambiar configuración
            success, message = self.config_manager.set_source(source)
            
            if success:
                # Notificar a AppManager para reconfigurar scheduler (será llamado por referencia)
                # Forzar actualización inmediata del caché
                self.cache_updater.update()
                
                config = self.config_manager.get_config()
                return jsonify({
                    'message': message,
                    'source': source,
                    'config': config
                }), 200
            else:
                return jsonify({'error': message}), 500
        except Exception as e:
            logger.error(f"Error al cambiar fuente: {e}")
            return jsonify({'error': str(e)}), 500
    
    def index(self):
        """Página de inicio (requiere template HTML)"""
        try:
            cache_status = "✓ Disponible" if self.cache.is_valid() else "✗ No disponible"
            cache_info = self.cache.get_info()
            last_update = cache_info['last_update']
            streams = self.stream_manager.get_streams()
            
            # Información del modo de origen
            current_source = self.config_manager.get_source()
            config = self.config_manager.get_config()
            last_parser_run = config.get('last_parser_run')
            
            if last_parser_run:
                try:
                    from datetime import datetime
                    last_parser_run = datetime.fromisoformat(last_parser_run).strftime('%Y-%m-%d %H:%M:%S')
                except:
                    last_parser_run = "Error al parsear"
            else:
                last_parser_run = "Nunca"
            
            current_interval = self.parser_update_interval if current_source == 'parser' else self.update_interval
            
            return render_template(
                'index.html',
                cache_status=cache_status,
                last_update=last_update,
                update_interval=self.update_interval,
                m3u_url=self.m3u_url,
                streams=streams,
                streams_count=len(streams),
                current_source=current_source,
                current_interval=current_interval,
                last_parser_run=last_parser_run,
            )
        except Exception as e:
            logger.error(f"Error al servir página de inicio: {e}")
            return {'error': str(e)}, 500
