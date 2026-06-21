"""
Aplicación que descarga un archivo m3u, reemplaza IPs y lo sirve mediante HTTP
con caché automático y descarga cada 12 horas
"""

import requests
from flask import Flask, send_file, jsonify, request
from io import BytesIO
import logging
import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import threading
import json
from parser import scrape_acestream_links, remove_duplicates, generate_m3u_content

# Configuración
m3u_url = os.getenv('M3U_URL', 'http://ejemplo.com/playlist.m3u')
server_port = int(os.getenv('SERVER_PORT', 8082))
old_ip = os.getenv('OLD_IP', '127.0.0.1')
new_ip = os.getenv('NEW_IP', '192.168.1.151')
update_interval = int(os.getenv('UPDATE_INTERVAL', 12))  # Horas

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Sistema de caché
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

cache = M3UCache()
scheduler = BackgroundScheduler()

# Gestión de streams personalizados
DATA_DIR = os.getenv('DATA_DIR', '/app/data')
CUSTOM_STREAMS_FILE = os.path.join(DATA_DIR, 'custom_streams.json')

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
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(streams, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error al guardar streams: {e}")
            raise

def init_data_directory():
    """Crea el directorio de datos si no existe"""
    data_dir = os.path.dirname(CUSTOM_STREAMS_FILE)
    if data_dir and not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir, mode=0o777, exist_ok=True)
            logger.info(f"Directorio de datos creado: {data_dir}")
        except Exception as e:
            logger.error(f"Error al crear directorio de datos: {e}")
            logger.warning("Usando directorio actual como fallback")

# Configuración de origen M3U
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')
PARSER_UPDATE_INTERVAL = int(os.getenv('PARSER_UPDATE_INTERVAL', 6))  # Horas para modo parser

class ConfigManager:
    """Clase para gestionar la configuración de la aplicación (modo de origen M3U)"""
    def __init__(self, file_path=CONFIG_FILE):
        self.file_path = file_path
        self.lock = threading.Lock()
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Crea el archivo de configuración si no existe"""
        if not os.path.exists(self.file_path):
            default_config = {
                'source': 'online',  # 'online' o 'parser'
                'last_parser_run': None,
                'created_at': datetime.now().isoformat()
            }
            self._save_config(default_config)
    
    def _get_config_unlocked(self):
        """Obtiene la configuración sin usar lock (para uso interno)"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error al leer configuración: {e}")
            return {'source': 'online'}
    
    def get_config(self):
        """Obtiene la configuración actual"""
        with self.lock:
            return self._get_config_unlocked()
    
    def get_source(self):
        """Obtiene el modo de origen actual"""
        config = self.get_config()
        return config.get('source', 'online')
    
    def set_source(self, source):
        """Establece el modo de origen ('online' o 'parser')"""
        if source not in ('online', 'parser'):
            raise ValueError("source debe ser 'online' o 'parser'")
        
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
    
    def update_last_parser_run(self):
        """Actualiza la marca de tiempo de última ejecución del parser"""
        with self.lock:
            try:
                config = self._get_config_unlocked()
                config['last_parser_run'] = datetime.now().isoformat()
                self._save_config(config)
            except Exception as e:
                logger.error(f"Error al actualizar timestamp de parser: {e}")
    
    def _save_config(self, config):
        """Guarda la configuración en el archivo"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error al guardar configuración: {e}")
            raise

stream_manager = StreamManager()
config_manager = ConfigManager()


def generate_m3u_with_streams(base_content, streams):
    """Genera contenido M3U combinando la URL principal + streams personalizados"""
    # Asegurarse que empieza con header
    if not base_content.startswith('#EXTM3U'):
        content = '#EXTM3U\n' + base_content
    else:
        content = base_content
    
    # Agregar streams personalizados
    if streams:
        if not content.endswith('\n'):
            content += '\n'
        
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


def fetch_from_parser():
    """Obtiene contenido M3U ejecutando el parser local"""
    try:
        logger.info("Ejecutando parser local para obtener streams...")
        
        # URL de scraping (misma que usa parser.py)
        scrape_url = 'https://ciriaco.netlify.app/'
        
        # Scrape, remove duplicates, generate content
        links = scrape_acestream_links(scrape_url)
        if not links:
            logger.warning("El parser no encontró streams")
            return None
        
        unique_links = remove_duplicates(links)
        duplicates_removed = len(links) - len(unique_links)
        
        if duplicates_removed > 0:
            logger.info(f"Se removieron {duplicates_removed} enlaces duplicados")
        
        # Generar contenido M3U
        content = generate_m3u_content(unique_links)
        
        if content:
            logger.info(f"Parser completado: {len(unique_links)} streams únicos")
            config_manager.update_last_parser_run()
            return content
        else:
            logger.error("El parser no generó contenido M3U válido")
            return None
    
    except Exception as e:
        logger.error(f"Error ejecutando parser: {e}")
        return None


def download_and_modify_m3u():
    """Descarga el archivo m3u principal (online u parser) y lo combina con streams personalizados"""
    try:
        combined_content = ""
        source = config_manager.get_source()
        
        # Obtener contenido según la fuente configurada
        if source == 'parser':
            logger.info("[PARSER MODE] Obteniendo contenido desde parser local...")
            combined_content = fetch_from_parser()
            if not combined_content:
                logger.error("Parser falló, usando fallback a caché anterior")
                return None
        else:  # online (default)
            logger.info(f"[ONLINE MODE] Descargando m3u principal desde: {m3u_url}")
            try:
                response = requests.get(m3u_url, timeout=10)
                response.raise_for_status()
                combined_content = response.text
                logger.info(f"URL principal descargada ({len(response.text)} bytes)")
            except requests.exceptions.RequestException as e:
                logger.error(f"Error al descargar URL principal: {e}")
                logger.warning("Descarga falló, usando fallback a caché anterior")
                return None
        
        # Obtener streams personalizados
        streams = stream_manager.get_streams()
        
        # Generar el M3U combinado con streams personalizados
        combined_content = generate_m3u_with_streams(combined_content, streams)
        
        if not combined_content:
            raise Exception("No se pudo generar contenido M3U")
        
        # Realizar el reemplazo de IP
        modified_content = combined_content.replace(old_ip, new_ip)
        
        logger.info(f"Reemplazo completado: {old_ip} -> {new_ip}")
        logger.info(f"Streams personalizados incluidos: {len(streams)}")
        logger.info(f"Tamaño original: {len(combined_content)} bytes")
        logger.info(f"Tamaño modificado: {len(modified_content)} bytes")
        
        return modified_content
        
    except Exception as e:
        logger.error(f"Error al procesar los archivos: {e}")
        return None

def update_cache():
    """Actualiza el caché descargando el archivo m3u más reciente"""
    if cache.update_in_progress:
        logger.info("Una actualización ya está en progreso, saltando...")
        return
    
    cache.update_in_progress = True
    try:
        source = config_manager.get_source()
        interval = PARSER_UPDATE_INTERVAL if source == 'parser' else update_interval
        logger.info(f"[ACTUALIZACIÓN PROGRAMADA] Obteniendo contenido en modo {source.upper()} (cada {interval}h)")
        
        modified_content = download_and_modify_m3u()
        
        if modified_content:
            cache.set(modified_content)
            logger.info("[ACTUALIZACIÓN PROGRAMADA] Caché actualizado exitosamente")
        else:
            error_msg = "Falló obtener contenido M3U de ambas fuentes"
            logger.error(error_msg)
            cache.set_error(error_msg)
    except Exception as e:
        error_msg = f"Error al actualizar caché: {str(e)}"
        logger.error(error_msg)
        cache.set_error(error_msg)
    finally:
        cache.update_in_progress = False


@app.route('/stream.m3u')
def serve_m3u():
    """Sirve el archivo m3u modificado desde caché"""
    try:
        # Si el caché no está disponible, actualizar ahora
        if not cache.is_valid():
            logger.info("Caché vacío, descargando...")
            update_cache()
        
        modified_content = cache.get()
        
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

@app.route('/health')
def health():
    """Endpoint para verificar que el servidor está activo"""
    if cache.is_valid():
        return {'status': 'ok', 'cache': 'ready'}, 200
    else:
        return {'status': 'ok', 'cache': 'not-ready'}, 200

@app.route('/status')
def status():
    """Endpoint para obtener el estado de la aplicación"""
    status_info = {
        'server': 'running',
        'cache': {
            'available': cache.is_valid(),
            'last_update': cache.last_update.isoformat() if cache.last_update else None,
            'update_in_progress': cache.update_in_progress,
            'last_error': cache.last_error
        },
        'configuration': {
            'update_interval_hours': update_interval,
            'm3u_url': m3u_url,
            'old_ip': old_ip,
            'new_ip': new_ip
        }
    }
    return jsonify(status_info), 200

@app.route('/api/streams', methods=['GET'])
def get_streams():
    """Obtiene la lista de streams personalizados"""
    try:
        streams = stream_manager.get_streams()
        return jsonify({'streams': streams, 'count': len(streams)}), 200
    except Exception as e:
        logger.error(f"Error al obtener streams: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/streams', methods=['POST'])
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
            update_cache()
            return jsonify({'message': message}), 201
        else:
            return jsonify({'error': message}), 409
    except Exception as e:
        logger.error(f"Error al agregar stream: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/streams/<stream_id>', methods=['PUT'])
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
            update_cache()
            return jsonify({'message': message}), 200
        else:
            return jsonify({'error': message}), 404
    except Exception as e:
        logger.error(f"Error al actualizar stream: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/streams/<stream_id>', methods=['DELETE'])
def delete_stream_api(stream_id):
    """Elimina un stream personalizado"""
    try:
        success, message = stream_manager.delete_stream(stream_id)
        
        if success:
            # Forzar actualización del caché
            update_cache()
            return jsonify({'message': message}), 200
        else:
            return jsonify({'error': message}), 404
    except Exception as e:
        logger.error(f"Error al eliminar stream: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/source', methods=['POST'])
def set_source_config():
    """Cambia la fuente de M3U (online u parser)"""
    try:
        data = request.get_json()
        source = data.get('source', '').strip().lower()
        
        if not source:
            return jsonify({'error': 'source es requerido'}), 400
        
        if source not in ('online', 'parser'):
            return jsonify({'error': 'source debe ser "online" o "parser"'}), 400
        
        # Cambiar configuración
        success, message = config_manager.set_source(source)
        
        if success:
            # Reconfigura el scheduler con el nuevo intervalo
            reconfigure_scheduler(source)
            
            # Forzar actualización inmediata del caché
            update_cache()
            
            config = config_manager.get_config()
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

@app.route('/')
def index():
    """Página de inicio"""
    cache_status = "✓ Disponible" if cache.is_valid() else "✗ No disponible"
    last_update = cache.last_update.strftime('%Y-%m-%d %H:%M:%S') if cache.last_update else "Nunca"
    streams = stream_manager.get_streams()
    
    # Información del modo de origen
    current_source = config_manager.get_source()
    source_label_online = "Online (URL Remota)" if current_source == 'online' else "Online (URL Remota)"
    source_label_parser = "Parser Local (Acestream)" if current_source == 'parser' else "Parser Local (Acestream)"
    online_checked = 'checked="checked"' if current_source == 'online' else ""
    parser_checked = 'checked="checked"' if current_source == 'parser' else ""
    current_interval = update_interval if current_source == 'online' else PARSER_UPDATE_INTERVAL
    config = config_manager.get_config()
    last_parser_run = config.get('last_parser_run')
    if last_parser_run:
        try:
            last_parser_run = datetime.fromisoformat(last_parser_run).strftime('%Y-%m-%d %H:%M:%S')
        except:
            last_parser_run = "Error al parsear"
    else:
        last_parser_run = "Nunca"
    
    streams_html = ""
    if streams:
        streams_html = "<div id='streams_list'>"
        for stream in streams:
            logo_html = f"<img src='{stream['logo']}' alt='logo' style='width: 50px; height: auto;'>" if stream.get('logo') else "<div style='width: 50px; text-align: center;'>📺</div>"
            
            streams_html += f"""
            <div class="stream-item">
                <div class="stream-logo">
                    {logo_html}
                </div>
                <div class="stream-info">
                    <strong>{stream['name']}</strong>
                    <br><small>Grupo: {stream['group']}</small>
                    <br><small style='color: #666;'>{stream['url']}</small>
                </div>
                <div class="stream-actions">
                    <button onclick="editStream('{stream['id']}')">✏️ Editar</button>
                    <button onclick="deleteStream('{stream['id']}')">🗑️ Eliminar</button>
                </div>
            </div>
            """
        streams_html += "</div>"
    else:
        streams_html = "<p style='color: #999;'>No hay streams personalizados agregados. ¡Agrega uno para comenzar!</p>"
    
    return f"""
    <html>
    <head>
        <title>M3U Content Getter - Gestor de Streams</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 1100px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }}
            h1 {{
                color: white;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
                margin-bottom: 5px;
            }}
            .header {{
                background: rgba(0,0,0,0.1);
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 20px;
                color: white;
            }}
            .header p {{
                opacity: 0.9;
                margin-top: 10px;
            }}
            h2 {{
                color: #333;
                margin-top: 25px;
                font-size: 1.3em;
                border-left: 4px solid #667eea;
                padding-left: 12px;
            }}
            .section {{
                background: white;
                padding: 25px;
                margin: 15px 0;
                border-radius: 8px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            }}
            .status-ok {{
                color: #28a745;
                font-weight: bold;
            }}
            .status-error {{
                color: #dc3545;
                font-weight: bold;
            }}
            ul {{
                list-style: none;
                padding: 0;
            }}
            li {{
                padding: 10px 0;
                border-bottom: 1px solid #eee;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            li:last-child {{
                border-bottom: none;
            }}
            code {{
                background: #f0f0f0;
                padding: 4px 8px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
                font-size: 0.9em;
            }}
            a {{
                color: #667eea;
                text-decoration: none;
                font-weight: bold;
            }}
            a:hover {{
                text-decoration: underline;
            }}
            .form-group {{
                margin-bottom: 15px;
            }}
            label {{
                display: block;
                margin-bottom: 8px;
                font-weight: 600;
                color: #333;
            }}
            input[type="text"],
            input[type="url"],
            select {{
                width: 100%;
                padding: 12px;
                border: 2px solid #ddd;
                border-radius: 6px;
                font-size: 14px;
                transition: border-color 0.3s;
            }}
            input[type="text"]:focus,
            input[type="url"]:focus,
            select:focus {{
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }}
            .form-row {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 15px;
            }}
            button {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 600;
                transition: transform 0.2s, box-shadow 0.2s;
            }}
            button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            }}
            button:active {{
                transform: translateY(0);
            }}
            .btn-secondary {{
                background: #6c757d;
            }}
            .btn-secondary:hover {{
                background: #5a6268;
            }}
            .btn-delete {{
                background: #dc3545;
                padding: 6px 12px;
                font-size: 12px;
            }}
            .btn-delete:hover {{
                background: #c82333;
            }}
            .btn-edit {{
                background: #007bff;
                padding: 6px 12px;
                font-size: 12px;
            }}
            .btn-edit:hover {{
                background: #0056b3;
            }}
            .stream-item {{
                display: grid;
                grid-template-columns: 60px 1fr 200px;
                gap: 15px;
                align-items: center;
                padding: 15px;
                background: #f9f9f9;
                border-radius: 6px;
                margin-bottom: 12px;
                border: 1px solid #e9ecef;
                transition: all 0.3s;
            }}
            .stream-item:hover {{
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                background: #ffffff;
            }}
            .stream-logo {{
                display: flex;
                align-items: center;
                justify-content: center;
                height: 60px;
            }}
            .stream-logo img {{
                max-width: 100%;
                max-height: 100%;
                border-radius: 4px;
            }}
            .stream-info {{
                line-height: 1.6;
            }}
            .stream-info strong {{
                color: #333;
                display: block;
                margin-bottom: 4px;
            }}
            .stream-info small {{
                color: #666;
            }}
            .stream-actions {{
                display: flex;
                gap: 8px;
            }}
            .stream-actions button {{
                padding: 8px 12px;
                font-size: 12px;
                width: 100%;
            }}
            .loading {{
                display: none;
                color: #667eea;
                font-weight: bold;
                margin-top: 10px;
            }}
            .message {{
                padding: 12px 16px;
                margin: 10px 0;
                border-radius: 6px;
                display: none;
                border-left: 4px solid;
                animation: slideIn 0.3s ease;
            }}
            @keyframes slideIn {{
                from {{
                    opacity: 0;
                    transform: translateY(-10px);
                }}
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}
            .message.success {{
                background-color: #d4edda;
                color: #155724;
                border-color: #28a745;
            }}
            .message.error {{
                background-color: #f8d7da;
                color: #721c24;
                border-color: #dc3545;
            }}
            .required {{
                color: #dc3545;
            }}
            .source-selector {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
                margin: 15px 0;
            }}
            .source-option {{
                position: relative;
            }}
            .source-option input[type="radio"] {{
                display: none;
            }}
            .source-option label {{
                display: block;
                padding: 16px;
                border: 2px solid #ddd;
                border-radius: 6px;
                background: #f9f9f9;
                cursor: pointer;
                transition: all 0.3s;
                text-align: center;
                margin: 0;
            }}
            .source-option input[type="radio"]:checked + label {{
                border-color: #667eea;
                background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
                font-weight: 600;
                color: #667eea;
            }}
            .source-option label:hover {{
                border-color: #667eea;
                background: rgba(102, 126, 234, 0.05);
            }}
            .source-info {{
                font-size: 12px;
                color: #666;
                margin-top: 4px;
                text-align: center;
            }}
            @media (max-width: 768px) {{
                .source-selector {{
                    grid-template-columns: 1fr;
                }}

                .form-row {{
                    grid-template-columns: 1fr;
                }}
                .stream-item {{
                    grid-template-columns: 50px 1fr;
                }}
                .stream-actions {{
                    grid-column: 1 / -1;
                }}
                .stream-actions button {{
                    flex: 1;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📺 M3U Content Getter</h1>
            <p>Aplicación que descarga y modifica archivos m3u con actualización automática cada {update_interval} horas</p>
        </div>
        
        <div class="section">
            <h2>📊 Estado del Sistema</h2>
            <ul>
                <li>
                    <span><strong>Caché:</strong></span>
                    <span class="status-ok">{cache_status}</span>
                </li>
                <li>
                    <span><strong>Última actualización:</strong></span>
                    <span>{last_update}</span>
                </li>
                <li>
                    <span><strong>Intervalo de actualización:</strong></span>
                    <span>{update_interval} horas</span>
                </li>
            </ul>
        </div>
        
        <div class="section">
            <h2>⚙️ Configuración Principal</h2>
            <ul>
                <li>
                    <span><strong>URL de origen M3U:</strong></span>
                    <code>{m3u_url}</code>
                </li>
                <li>
                    <span><strong>IP a reemplazar:</strong></span>
                    <code>{old_ip}</code> → <code>{new_ip}</code>
                </li>
            </ul>
        </div>
        
        <div class="section">
            <h2>🔄 Configuración de Origen M3U</h2>
            <p style="margin-bottom: 15px; color: #666;">Elige la fuente de origen para obtener la lista M3U:</p>
            
            <div class="source-selector">
                <div class="source-option">
                    <input type="radio" id="sourceOnline" name="source" value="online" onchange="changeSource('online')" {online_checked}>
                    <label for="sourceOnline">
                        🌐 Online<br>
                        <div class="source-info">Descarga desde URL remota</div>
                    </label>
                </div>
                <div class="source-option">
                    <input type="radio" id="sourceParser" name="source" value="parser" onchange="changeSource('parser')" {parser_checked}>
                    <label for="sourceParser">
                        📊 Parser Local<br>
                        <div class="source-info">Ejecuta script parser.py</div>
                    </label>
                </div>
            </div>
            
            <div style="background: #f0f0f0; padding: 12px; border-radius: 6px; font-size: 14px; margin-top: 15px;">
                <p><strong>Modo actual:</strong> <span id="currentSource" style="color: #667eea; font-weight: bold;">{current_source.upper()}</span></p>
                <p><strong>Intervalo de actualización:</strong> <span id="updateInterval" style="color: #667eea; font-weight: bold;">{current_interval} horas</span></p>
                {f'<p><strong>Última ejecución del parser:</strong> {last_parser_run}</p>' if current_source == 'parser' else ''}
            </div>
            
            <button onclick="forceUpdate()" style="margin-top: 15px; width: 100%;">🔄 Actualizar ahora</button>
            <span id="updateLoading" class="loading">Actualizando contenido...</span>
        </div>
        
        <div class="section">
            <h2>➕ Agregar Nuevo Stream</h2>
            <div id="message" class="message"></div>
            
            <div class="form-row">
                <div class="form-group">
                    <label for="nameInput">Nombre del Canal <span class="required">*</span></label>
                    <input type="text" id="nameInput" placeholder="ej: HBO, CNN, TN, etc" />
                </div>
                <div class="form-group">
                    <label for="groupInput">Grupo/Categoría</label>
                    <input type="text" id="groupInput" placeholder="ej: Películas, Deportes, Noticias" />
                </div>
            </div>
            
            <div class="form-group">
                <label for="urlInput">URL del Stream <span class="required">*</span></label>
                <input type="url" id="urlInput" placeholder="ej: http://streaming.ejemplo.com/canal.m3u8" />
            </div>
            
            <div class="form-group">
                <label for="logoInput">URL del Logo (opcional)</label>
                <input type="url" id="logoInput" placeholder="ej: https://ejemplo.com/logo.png" />
            </div>
            
            <button onclick="addStream()">Agregar Stream</button>
            <span id="loading" class="loading">Agregando stream y actualizando caché...</span>
        </div>
        
        <div class="section">
            <h2>📋 Streams Personalizados ({len(streams)})</h2>
            {streams_html}
        </div>
        
        <div class="section">
            <h2>🔗 Endpoints Disponibles</h2>
            <ul>
                <li>
                    <span><a href="/stream.m3u">/stream.m3u</a></span>
                    <span>Descargar el archivo M3U modificado</span>
                </li>
                <li>
                    <span><a href="/status">/status</a></span>
                    <span>JSON con estado detallado</span>
                </li>
                <li>
                    <span><a href="/health">/health</a></span>
                    <span>Verificar disponibilidad</span>
                </li>
                <li>
                    <span><code>/api/streams</code></span>
                    <span>API para gestionar streams (GET/POST/PUT/DELETE)</span>
                </li>
            </ul>
        </div>
        
        <div class="section">
            <h2>💡 Cómo Usar</h2>
            <p><strong>En VLC, Kodi, Plex u otros reproductores:</strong></p>
            <code style="display: block; margin-top: 10px;">http://IP_DEL_SERVIDOR:8082/stream.m3u</code>
            <p style="margin-top: 15px;"><strong>Agregando Streams:</strong></p>
            <ol style="margin-left: 20px; margin-top: 10px;">
                <li>Ingresa el nombre del canal o stream</li>
                <li>Pega la URL del archivo M3U o stream directo</li>
                <li>Opcionalmente agrega logo y categoría</li>
                <li>¡El caché se actualiza automáticamente!</li>
            </ol>
        </div>
        
        <script>
            async function addStream() {{
                const name = document.getElementById('nameInput').value.trim();
                const url = document.getElementById('urlInput').value.trim();
                const logo = document.getElementById('logoInput').value.trim();
                const group = document.getElementById('groupInput').value.trim();
                const messageDiv = document.getElementById('message');
                const loading = document.getElementById('loading');
                
                messageDiv.style.display = 'none';
                messageDiv.className = 'message';
                
                if (!name) {{
                    messageDiv.textContent = '❌ Por favor ingresa un nombre para el stream';
                    messageDiv.classList.add('error');
                    messageDiv.style.display = 'block';
                    return;
                }}
                
                if (!url) {{
                    messageDiv.textContent = '❌ Por favor ingresa una URL';
                    messageDiv.classList.add('error');
                    messageDiv.style.display = 'block';
                    return;
                }}
                
                loading.style.display = 'inline';
                
                try {{
                    const response = await fetch('/api/streams', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                        }},
                        body: JSON.stringify({{name, url, logo, group}})
                    }});
                    
                    const data = await response.json();
                    
                    if (response.ok) {{
                        messageDiv.textContent = '✅ Stream agregado exitosamente. Actualizando caché...';
                        messageDiv.classList.add('success');
                        messageDiv.style.display = 'block';
                        document.getElementById('nameInput').value = '';
                        document.getElementById('urlInput').value = '';
                        document.getElementById('logoInput').value = '';
                        document.getElementById('groupInput').value = '';
                        setTimeout(() => location.reload(), 1500);
                    }} else {{
                        messageDiv.textContent = '❌ Error: ' + data.error;
                        messageDiv.classList.add('error');
                        messageDiv.style.display = 'block';
                    }}
                }} catch (error) {{
                    messageDiv.textContent = '❌ Error de red: ' + error.message;
                    messageDiv.classList.add('error');
                    messageDiv.style.display = 'block';
                }} finally {{
                    loading.style.display = 'none';
                }}
            }}
            
            async function deleteStream(streamId) {{
                if (!confirm('¿Seguro que deseas eliminar este stream?')) {{
                    return;
                }}
                
                try {{
                    const response = await fetch('/api/streams/' + streamId, {{
                        method: 'DELETE'
                    }});
                    
                    if (response.ok) {{
                        alert('✅ Stream eliminado. Actualizando página...');
                        location.reload();
                    }} else {{
                        const data = await response.json();
                        alert('❌ Error: ' + data.error);
                    }}
                }} catch (error) {{
                    alert('❌ Error de red: ' + error.message);
                }}
            }}
            
            function editStream(streamId) {{
                alert('La edición de streams estará disponible en la próxima versión.');
                // TODO: Implementar modal de edición
            }}
            
            async function changeSource(newSource) {{
                const loading = document.getElementById('updateLoading');
                const currentSourceSpan = document.getElementById('currentSource');
                const updateIntervalSpan = document.getElementById('updateInterval');
                
                loading.style.display = 'inline';
                
                try {{
                    const response = await fetch('/api/config/source', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                        }},
                        body: JSON.stringify({{source: newSource}})
                    }});
                    
                    const data = await response.json();
                    
                    if (response.ok) {{
                        console.log('✅ Fuente cambiada a: ' + newSource);
                        // Actualizar UI después de 2 segundos (tiempo para completar actualización)
                        setTimeout(() => location.reload(), 2000);
                    }} else {{
                        alert('❌ Error al cambiar fuente: ' + data.error);
                        // Revertir selección
                        document.querySelectorAll('input[name="source"]').forEach(radio => {{
                            radio.checked = false;
                        }});
                    }}
                }} catch (error) {{
                    alert('❌ Error de red: ' + error.message);
                    document.querySelectorAll('input[name="source"]').forEach(radio => {{
                        radio.checked = false;
                    }});
                }} finally {{
                    loading.style.display = 'none';
                }}
            }}
            
            async function forceUpdate() {{
                const loading = document.getElementById('updateLoading');
                loading.style.display = 'inline';
                loading.textContent = '🔄 Actualizando contenido...';
                
                try {{
                    // Llamar a endpoint que fuerza actualización
                    const response = await fetch('/status');
                    
                    if (response.ok) {{
                        setTimeout(() => {{
                            loading.textContent = '✅ Contenido actualizado exitosamente';
                            loading.style.display = 'inline';
                            setTimeout(() => location.reload(), 1500);
                        }}, 2000);
                    }} else {{
                        loading.textContent = '❌ Error en la actualización';
                        loading.style.display = 'inline';
                    }}
                }} catch (error) {{
                    loading.textContent = '❌ Error de red: ' + error.message;
                    loading.style.display = 'inline';
                }}
            }}
            
            // Auto-submit al presionar Enter
            ['nameInput', 'urlInput', 'logoInput', 'groupInput'].forEach(id => {{
                document.getElementById(id).addEventListener('keypress', function(e) {{
                    if (e.key === 'Enter') addStream();
                }});
            }});
        </script>
    </body>
    </html>
    """

def reconfigure_scheduler(source_type=None):
    """Reconfigura el scheduler con el intervalo correcto según la fuente de M3U"""
    if source_type is None:
        source_type = config_manager.get_source()
    
    interval = PARSER_UPDATE_INTERVAL if source_type == 'parser' else update_interval
    
    try:
        # Remover job anterior si existe
        if scheduler.running:
            try:
                scheduler.remove_job('m3u_update')
            except:
                pass
        
        # Agregar nuevo job con intervalo correcto
        scheduler.add_job(
            func=update_cache,
            trigger="interval",
            hours=interval,
            id='m3u_update',
            name=f'Actualización de caché M3U ({source_type})',
            replace_existing=True
        )
        
        logger.info(f"Scheduler reconfigurado: modo {source_type.upper()}, actualización cada {interval} horas")
        return True
    except Exception as e:
        logger.error(f"Error reconfigurando scheduler: {e}")
        return False


def init_scheduler():
    """Inicializa el scheduler para actualizaciones automáticas"""
    if not scheduler.running:
        source_type = config_manager.get_source()
        interval = PARSER_UPDATE_INTERVAL if source_type == 'parser' else update_interval
        
        scheduler.add_job(
            func=update_cache,
            trigger="interval",
            hours=interval,
            id='m3u_update',
            name=f'Actualización de caché M3U ({source_type})',
            replace_existing=True
        )
        scheduler.start()
        logger.info(f"Scheduler iniciado: modo {source_type.upper()}, actualización cada {interval} horas")


if __name__ == '__main__':
    logger.info("="*60)
    logger.info("INICIANDO M3U CONTENT GETTER")
    logger.info("="*60)
    logger.info(f"Puerto: {server_port}")
    logger.info(f"URL del m3u: {m3u_url}")
    logger.info(f"IP original: {old_ip}")
    logger.info(f"IP nueva: {new_ip}")
    logger.info(f"Intervalo de actualización: {update_interval} horas")
    logger.info(f"Directorio de datos: {DATA_DIR}")
    logger.info("="*60)
    
    # Inicializar directorio de datos
    init_data_directory()
    
    # Descargar el contenido inicial
    logger.info("Descargando contenido inicial...")
    update_cache()
    
    # Iniciar el scheduler
    init_scheduler()
    
    # Iniciar el servidor Flask
    logger.info(f"Servidor iniciado en http://0.0.0.0:{server_port}")
    app.run(host='0.0.0.0', port=server_port, debug=False, use_reloader=False)
