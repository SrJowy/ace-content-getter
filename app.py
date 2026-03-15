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
                streams = self.get_streams()
                
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
                streams = self.get_streams()
                
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
                streams = self.get_streams()
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

stream_manager = StreamManager()


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
            
            extinf += f"\n{stream['name']}\n{stream['url']}\n"
            content += extinf
    
    return content


def download_and_modify_m3u():
    """Descarga el archivo m3u principal y lo combina con streams personalizados"""
    try:
        combined_content = ""
        
        # Descargar URL principal
        try:
            logger.info(f"Descargando m3u principal desde: {m3u_url}")
            response = requests.get(m3u_url, timeout=10)
            response.raise_for_status()
            combined_content = response.text
            logger.info(f"URL principal descargada ({len(response.text)} bytes)")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al descargar URL principal: {e}")
            logger.warning("Iniciando con contenido vacío")
            combined_content = "#EXTM3U\n"
        
        # Obtener streams personalizados
        streams = stream_manager.get_streams()
        
        # Generar el M3U combinado
        combined_content = generate_m3u_with_streams(combined_content, streams)
        
        if not combined_content:
            raise Exception("No se pudo generar contenido M3U")
        
        # Realizar el reemplazo
        modified_content = combined_content.replace(old_ip, new_ip)
        
        logger.info(f"Reemplazo completado: {old_ip} -> {new_ip}")
        logger.info(f"Streams personalizados incluidos: {len(streams)}")
        logger.info(f"Tamaño original: {len(combined_content)} bytes")
        logger.info(f"Tamaño modificado: {len(modified_content)} bytes")
        
        return modified_content
        
    except Exception as e:
        logger.error(f"Error al procesar los archivos: {e}")
        raise

def update_cache():
    """Actualiza el caché descargando el archivo m3u más reciente"""
    if cache.update_in_progress:
        logger.info("Una actualización ya está en progreso, saltando...")
        return
    
    cache.update_in_progress = True
    try:
        logger.info(f"[ACTUALIZACIÓN PROGRAMADA] Descargando archivo m3u (cada {update_interval}h)")
        modified_content = download_and_modify_m3u()
        cache.set(modified_content)
        logger.info("[ACTUALIZACIÓN PROGRAMADA] Caché actualizado exitosamente")
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

@app.route('/')
def index():
    """Página de inicio"""
    cache_status = "✓ Disponible" if cache.is_valid() else "✗ No disponible"
    last_update = cache.last_update.strftime('%Y-%m-%d %H:%M:%S') if cache.last_update else "Nunca"
    streams = stream_manager.get_streams()
    
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
            @media (max-width: 768px) {{
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

def init_scheduler():
    """Inicializa el scheduler para actualizaciones automáticas"""
    if not scheduler.running:
        scheduler.add_job(
            func=update_cache,
            trigger="interval",
            hours=update_interval,
            id='m3u_update',
            name='Actualización de caché M3U',
            replace_existing=True
        )
        scheduler.start()
        logger.info(f"Scheduler iniciado: actualización cada {update_interval} horas")

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
