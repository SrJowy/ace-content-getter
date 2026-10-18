"""
Rutas API de Flask
Expone todos los endpoints de la aplicación
"""

import re
import uuid
from io import BytesIO
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit
import requests
from flask import Blueprint, Response, send_file, jsonify, request, render_template, stream_with_context
from app.utils.logger import get_logger
from app.models.cache import M3UCache
from app.models.config import ConfigManager
from app.services.stream_manager import StreamManager
from app.services.cache_updater import CacheUpdater
from app.utils.constants import DEFAULT_TIMEOUT, USER_AGENT

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
        self.blueprint.route('/stream_away.m3u')(self.serve_m3u_away)
        self.blueprint.route('/health')(self.health)
        self.blueprint.route('/status')(self.status)
        self.blueprint.route('/api/refresh', methods=['POST'])(self.refresh_cache)
        self.blueprint.route('/api/player/acestream/<info_hash>', methods=['GET'])(self.proxy_acestream)
        self.blueprint.route('/api/player/acestream/away/<info_hash>', methods=['GET'])(self.proxy_acestream_away)
        self.blueprint.route('/api/player/acestream/hls/<info_hash>', methods=['GET'])(self.create_acestream_hls)
        self.blueprint.route('/api/player/acestream/hls/away/<info_hash>', methods=['GET'])(self.create_acestream_hls_away)
        self.blueprint.route('/api/streams', methods=['GET'])(self.get_streams)
        self.blueprint.route('/api/streams', methods=['POST'])(self.add_stream)
        self.blueprint.route('/api/streams/<stream_id>', methods=['PUT'])(self.update_stream)
        self.blueprint.route('/api/streams/<stream_id>', methods=['DELETE'])(self.delete_stream)
        self.blueprint.route('/api/config/source', methods=['POST'])(self.set_source_config)
        self.blueprint.route('/')(self.index)
    
    def _serve_cached_m3u(self, getter, filename: str):
        """Sirve una versión del archivo m3u desde caché."""
        try:
            if not self.cache.is_valid():
                logger.info("Caché vacío, descargando...")
                self.cache_updater.update()

            content = getter()

            if content is None:
                return {'error': f'No se pudo obtener el archivo {filename}'}, 503

            file_stream = BytesIO(content.encode('utf-8'))
            return send_file(
                file_stream,
                mimetype='application/vnd.apple.mpegurl',
                as_attachment=True,
                download_name=filename
            )
        except Exception as e:
            logger.error(f"Error al servir el archivo {filename}: {e}")
            return {'error': str(e)}, 500

    def serve_m3u(self):
        """Sirve el archivo m3u principal desde caché"""
        return self._serve_cached_m3u(self.cache.get, 'stream.m3u')

    def serve_m3u_away(self):
        """Sirve el archivo m3u alternativo con la IP away"""
        return self._serve_cached_m3u(self.cache.get_away, 'stream_away.m3u')
    
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

    def refresh_cache(self):
        """Forza una actualización inmediata del caché y de los streams."""
        try:
            success = self.cache_updater.update()
            cache_info = self.cache.get_info()
            last_update = cache_info.get('last_update')

            if success:
                return jsonify({
                    'status': 'updated',
                    'message': 'Caché actualizado correctamente',
                    'last_update': last_update,
                }), 200
            return jsonify({
                'status': 'skipped',
                'message': 'La actualización ya estaba en progreso o falló',
                'last_update': last_update,
            }), 200
        except Exception as e:
            logger.error(f"Error al forzar actualización del caché: {e}")
            return jsonify({'error': str(e)}), 500

    def proxy_acestream_away(self, info_hash):
        """Retransmite la variante away de un stream AceStream."""
        return self.proxy_acestream(info_hash, away=True)

    def create_acestream_hls_away(self, info_hash):
        """Inicia una sesión HLS para la lista away."""
        return self.create_acestream_hls(info_hash, away=True)

    def create_acestream_hls(self, info_hash, away=False):
        """Devuelve la URL HLS nativa de una sesión AceStream."""
        if not re.fullmatch(r'[a-fA-F0-9]{40}', info_hash):
            return jsonify({'error': 'ID AceStream no válido'}), 400

        m3u_content = self.cache.get_away() if away else self.cache.get()
        source_url = None
        for line in (m3u_content or '').splitlines():
            candidate = line.strip()
            if not candidate.startswith('http://'):
                continue

            try:
                parsed_url = urlsplit(candidate)
                if parsed_url.path != '/ace/getstream' or parsed_url.port != 8088:
                    continue
            except ValueError:
                continue

            if parse_qs(parsed_url.query).get('id') == [info_hash]:
                source_url = candidate
                break

        if source_url is None:
            return jsonify({'error': 'El stream no está en la lista M3U solicitada'}), 404

        source = urlsplit(source_url)
        session_query = parse_qs(source.query)
        session_query['format'] = ['json']
        session_query['pid'] = [uuid.uuid4().hex]
        session_url = urlunsplit((
            source.scheme,
            source.netloc,
            '/ace/manifest.m3u8',
            urlencode(session_query, doseq=True),
            '',
        ))

        try:
            session_response = requests.get(
                session_url,
                headers={'User-Agent': USER_AGENT},
                timeout=(DEFAULT_TIMEOUT, 10),
                allow_redirects=False,
            )
            session_payload = session_response.json()
            session_response.close()
        except (requests.RequestException, ValueError) as error:
            logger.warning(f"No se pudo iniciar la sesión HLS AceStream {info_hash}: {error}")
            return jsonify({'error': 'No se pudo iniciar la sesión HLS AceStream'}), 502

        session = session_payload.get('response')
        playback_url = session.get('playback_url') if isinstance(session, dict) else None
        try:
            playback = urlsplit(playback_url)
            valid_playback_url = (
                playback.scheme == 'http'
                and playback.hostname == source.hostname
                and playback.port == 6878
                and playback.path.startswith('/ace/m/')
                and playback.path.endswith('.m3u8')
            )
        except (TypeError, ValueError):
            valid_playback_url = False

        if not valid_playback_url:
            return jsonify({'error': 'El motor AceStream no devolvió una URL HLS válida'}), 502

        return jsonify({'playback_url': playback_url}), 200

    def proxy_acestream(self, info_hash, away=False):
        """Retransmite un stream AceStream desde la M3U cacheada, evitando CORS."""
        if not re.fullmatch(r'[a-fA-F0-9]{40}', info_hash):
            return jsonify({'error': 'ID AceStream no válido'}), 400

        source_url = None
        m3u_content = self.cache.get_away() if away else self.cache.get()
        for line in (m3u_content or '').splitlines():
            candidate = line.strip()
            if not candidate.startswith('http://'):
                continue

            try:
                parsed_url = urlsplit(candidate)
                if parsed_url.path != '/ace/getstream' or parsed_url.port != 8088:
                    continue
            except ValueError:
                continue

            if parse_qs(parsed_url.query).get('id') == [info_hash]:
                source_url = candidate
                break

        if source_url is None:
            return jsonify({'error': 'El stream no está en la lista M3U solicitada'}), 404

        source = urlsplit(source_url)
        source_host = source.hostname
        session_query = parse_qs(source.query)
        session_query['format'] = ['json']
        session_query['pid'] = [uuid.uuid4().hex]
        session_url = urlunsplit((
            source.scheme,
            source.netloc,
            source.path,
            urlencode(session_query, doseq=True),
            source.fragment,
        ))

        try:
            session_response = requests.get(
                session_url,
                headers={'User-Agent': USER_AGENT},
                timeout=(DEFAULT_TIMEOUT, 10),
                allow_redirects=False,
            )
            session_payload = session_response.json()
            session_response.close()
        except (requests.RequestException, ValueError) as error:
            logger.warning(f"No se pudo iniciar la sesión AceStream {info_hash}: {error}")
            return jsonify({'error': 'No se pudo iniciar la sesión AceStream'}), 502

        session = session_payload.get('response')
        if not isinstance(session, dict):
            return jsonify({'error': 'El motor AceStream no devolvió datos de sesión'}), 502

        playback_url = session.get('playback_url')
        try:
            playback = urlsplit(playback_url)
            valid_playback_url = (
                playback.scheme == 'http'
                and playback.hostname == source_host
                and playback.port == 6878
                and playback.path.startswith('/ace/r/')
            )
        except (TypeError, ValueError):
            valid_playback_url = False

        if not valid_playback_url:
            return jsonify({'error': 'El motor AceStream devolvió URLs de sesión no válidas'}), 502

        headers = {'User-Agent': USER_AGENT}
        if request.headers.get('Range'):
            headers['Range'] = request.headers['Range']

        upstream_url = playback_url
        for _ in range(5):
            try:
                upstream = requests.get(
                    upstream_url,
                    headers=headers,
                    stream=True,
                    timeout=(DEFAULT_TIMEOUT, 30),
                    allow_redirects=False,
                )
            except requests.RequestException as error:
                logger.warning(f"No se pudo abrir el stream AceStream {info_hash}: {error}")
                return jsonify({'error': 'No se pudo conectar con el motor AceStream'}), 502

            if upstream.status_code not in (301, 302, 303, 307, 308):
                break

            location = upstream.headers.get('Location')
            if not location:
                upstream.close()
                return jsonify({'error': 'El motor AceStream devolvió una redirección sin destino'}), 502

            redirected_url = urljoin(upstream_url, location)
            try:
                redirected = urlsplit(redirected_url)
                redirect_is_valid = (
                    redirected.scheme == 'http'
                    and redirected.hostname == source_host
                    and redirected.port == 6878
                )
            except ValueError:
                redirect_is_valid = False

            upstream.close()
            if not redirect_is_valid:
                return jsonify({'error': 'El motor AceStream redirigió a un destino no permitido'}), 502

            upstream_url = redirected_url
        else:
            upstream.close()
            return jsonify({'error': 'Demasiadas redirecciones del motor AceStream'}), 502

        response_headers = {'Cache-Control': 'no-store'}
        for header in ('Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges'):
            if header in upstream.headers:
                response_headers[header] = upstream.headers[header]

        def stream_chunks():
            try:
                for chunk in upstream.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        yield chunk
            finally:
                upstream.close()

        return Response(
            stream_with_context(stream_chunks()),
            status=upstream.status_code,
            headers=response_headers,
        )
    
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
    
    def _extract_m3u_channels(self, content: str):
        """Extrae nombre, grupo y URL de cada canal del contenido M3U actual."""
        if not content:
            return []

        channels = []
        pending = None

        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue

            if line.startswith('#EXTINF:'):
                pending = {'name': '', 'group': '', 'url': ''}
                group_match = re.search(r'group-title="([^"]+)"', line)
                if group_match:
                    pending['group'] = group_match.group(1)

                name_match = re.search(r',\s*(.*)$', line)
                if name_match:
                    pending['name'] = name_match.group(1).strip()
                continue

            if line.startswith('http') or line.startswith('rtmp') or line.startswith('udp'):
                if pending is not None:
                    pending['url'] = line
                    channels.append(pending)
                    pending = None

        return channels

    def index(self):
        """Página de inicio (requiere template HTML)"""
        try:
            cache_status = "✓ Disponible" if self.cache.is_valid() else "✗ No disponible"
            cache_info = self.cache.get_info()
            last_update = cache_info['last_update']
            streams = self.stream_manager.get_streams()
            current_channels = self._extract_m3u_channels(self.cache.get() or '')
            away_channels = self._extract_m3u_channels(self.cache.get_away() or '')
            
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
                streams=streams,
                streams_count=len(streams),
                current_source=current_source,
                current_interval=current_interval,
                last_parser_run=last_parser_run,
                current_channels=current_channels,
                channels_count=len(current_channels),
                away_channels=away_channels,
                away_channels_count=len(away_channels),
            )
        except Exception as e:
            logger.error(f"Error al servir página de inicio: {e}")
            return {'error': str(e)}, 500
