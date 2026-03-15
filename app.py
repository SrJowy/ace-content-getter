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

# Gestión de URLs personalizadas
DATA_DIR = os.getenv('DATA_DIR', '/app/data')
CUSTOM_URLS_FILE = os.path.join(DATA_DIR, 'custom_urls.json')

class URLManager:
    """Clase para gestionar las URLs personalizadas"""
    def __init__(self, file_path=CUSTOM_URLS_FILE):
        self.file_path = file_path
        self.lock = threading.Lock()
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Crea el archivo si no existe"""
        if not os.path.exists(self.file_path):
            self._save_urls([])
    
    def get_urls(self):
        """Obtiene todas las URLs personalizadas"""
        with self.lock:
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error al leer URLs personalizadas: {e}")
                return []
    
    def add_url(self, url, name=''):
        """Añade una nueva URL personalizada"""
        with self.lock:
            try:
                urls = self.get_urls()
                # Verificar que no sea duplicada
                if any(u['url'] == url for u in urls):
                    return False, "URL ya existe"
                
                urls.append({
                    'url': url,
                    'name': name or url,
                    'added_at': datetime.now().isoformat()
                })
                self._save_urls(urls)
                logger.info(f"URL personalizada agregada: {url}")
                return True, "URL agregada exitosamente"
            except Exception as e:
                logger.error(f"Error al agregar URL: {e}")
                return False, str(e)
    
    def remove_url(self, url):
        """Elimina una URL personalizada"""
        with self.lock:
            try:
                urls = self.get_urls()
                urls = [u for u in urls if u['url'] != url]
                self._save_urls(urls)
                logger.info(f"URL personalizada eliminada: {url}")
                return True, "URL eliminada exitosamente"
            except Exception as e:
                logger.error(f"Error al eliminar URL: {e}")
                return False, str(e)
    
    def _save_urls(self, urls):
        """Guarda las URLs en el archivo"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(urls, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error al guardar URLs: {e}")
            raise

def init_data_directory():
    """Crea el directorio de datos si no existe"""
    data_dir = os.path.dirname(CUSTOM_URLS_FILE)
    if data_dir and not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir, mode=0o777, exist_ok=True)
            logger.info(f"Directorio de datos creado: {data_dir}")
        except Exception as e:
            logger.error(f"Error al crear directorio de datos: {e}")
            # Intentar escribir en el directorio actual como fallback
            logger.warning("Usando directorio actual como fallback")

url_manager = URLManager()


def download_and_modify_m3u():
    """Descarga los archivos m3u (principal + URLs personalizadas) y reemplaza las IPs"""
    try:
        combined_content = ""
        downloaded_urls = []
        failed_urls = []
        
        # Descargar URL principal
        try:
            logger.info(f"Descargando m3u principal desde: {m3u_url}")
            response = requests.get(m3u_url, timeout=10)
            response.raise_for_status()
            combined_content = response.text
            downloaded_urls.append(m3u_url)
            logger.info(f"URL principal descargada ({len(response.text)} bytes)")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al descargar URL principal: {e}")
            failed_urls.append(f"{m3u_url} - {str(e)}")
        
        # Descargar URLs personalizadas
        custom_urls = url_manager.get_urls()
        for url_obj in custom_urls:
            url = url_obj['url']
            try:
                logger.info(f"Descargando URL personalizada: {url}")
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                
                # Agregar contenido personalizado (sin el header #EXTM3U si ya existe)
                content = response.text
                if combined_content and not combined_content.endswith('\n'):
                    combined_content += '\n'
                
                # Evitar múltiples headers
                if not content.startswith('#EXTM3U'):
                    combined_content += content
                else:
                    # Saltar el header si el contenido principal ya lo tiene
                    lines = content.split('\n')
                    combined_content += '\n'.join(lines[1:]) if len(lines) > 1 else ''
                
                downloaded_urls.append(url)
                logger.info(f"URL personalizada descargada ({len(content)} bytes): {url}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Error al descargar URL personalizada {url}: {e}")
                failed_urls.append(f"{url} - {str(e)}")
        
        if not combined_content:
            raise Exception("No se pudo descargar contenido de ninguna fuente")
        
        # Realizar el reemplazo
        modified_content = combined_content.replace(old_ip, new_ip)
        
        logger.info(f"Reemplazo completado: {old_ip} -> {new_ip}")
        logger.info(f"URLs descargadas exitosamente: {len(downloaded_urls)}")
        if failed_urls:
            logger.warning(f"URLs que fallaron: {len(failed_urls)}")
            for failed in failed_urls:
                logger.warning(f"  - {failed}")
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

@app.route('/api/custom-urls', methods=['GET'])
def get_custom_urls():
    """Obtiene la lista de URLs personalizadas"""
    try:
        urls = url_manager.get_urls()
        return jsonify({'urls': urls, 'count': len(urls)}), 200
    except Exception as e:
        logger.error(f"Error al obtener URLs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/custom-urls', methods=['POST'])
def add_custom_url():
    """Añade una nueva URL personalizada"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        name = data.get('name', '').strip()
        
        if not url:
            return jsonify({'error': 'URL es requerida'}), 400
        
        # Validar que sea una URL válida
        if not url.startswith(('http://', 'https://')):
            return jsonify({'error': 'URL debe comenzar con http:// o https://'}), 400
        
        success, message = url_manager.add_url(url, name)
        
        if success:
            # Forzar actualización del caché
            update_cache()
            return jsonify({'message': message, 'url': url}), 201
        else:
            return jsonify({'error': message}), 409
    except Exception as e:
        logger.error(f"Error al agregar URL: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/custom-urls/<path:url>', methods=['DELETE'])
def delete_custom_url(url):
    """Elimina una URL personalizada"""
    try:
        url = url.strip()
        success, message = url_manager.remove_url(url)
        
        if success:
            # Forzar actualización del caché
            update_cache()
            return jsonify({'message': message}), 200
        else:
            return jsonify({'error': message}), 404
    except Exception as e:
        logger.error(f"Error al eliminar URL: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    """Página de inicio"""
    cache_status = "✓ Disponible" if cache.is_valid() else "✗ No disponible"
    last_update = cache.last_update.strftime('%Y-%m-%d %H:%M:%S') if cache.last_update else "Nunca"
    custom_urls = url_manager.get_urls()
    
    urls_html = ""
    if custom_urls:
        urls_html = "<ul id='urls_list'>"
        for idx, url_obj in enumerate(custom_urls):
            urls_html += f"""
            <li class="url-item">
                <div class="url-info">
                    <strong>{url_obj['name']}</strong>
                    <br><small>{url_obj['url']}</small>
                    <br><small>Agregado: {url_obj['added_at'][:10]}</small>
                </div>
                <button onclick="deleteURL('{url_obj['url']}', this)" class="btn-delete">Eliminar</button>
            </li>
            """
        urls_html += "</ul>"
    else:
        urls_html = "<p style='color: #999;'>No hay URLs personalizadas agregadas</p>"
    
    return f"""
    <html>
    <head>
        <title>M3U Content Getter</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            h1 {{
                color: #333;
                border-bottom: 3px solid #4CAF50;
                padding-bottom: 10px;
            }}
            h2 {{
                color: #555;
                margin-top: 25px;
                font-size: 1.3em;
            }}
            .section {{
                background: white;
                padding: 20px;
                margin: 15px 0;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            .status-ok {{
                color: #4CAF50;
                font-weight: bold;
            }}
            .status-error {{
                color: #f44336;
                font-weight: bold;
            }}
            ul {{
                list-style: none;
                padding: 0;
            }}
            li {{
                padding: 8px 0;
                border-bottom: 1px solid #eee;
            }}
            li:last-child {{
                border-bottom: none;
            }}
            code {{
                background: #f0f0f0;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: monospace;
            }}
            a {{
                color: #4CAF50;
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
                margin-bottom: 5px;
                font-weight: bold;
                color: #333;
            }}
            input[type="text"],
            input[type="url"] {{
                width: 100%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
                box-sizing: border-box;
            }}
            input[type="text"]:focus,
            input[type="url"]:focus {{
                outline: none;
                border-color: #4CAF50;
                box-shadow: 0 0 5px rgba(76, 175, 80, 0.3);
            }}
            button {{
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                font-weight: bold;
            }}
            button:hover {{
                background-color: #45a049;
            }}
            .btn-delete {{
                background-color: #f44336;
                padding: 6px 12px;
                font-size: 12px;
            }}
            .btn-delete:hover {{
                background-color: #da190b;
            }}
            .url-item {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px !important;
                background-color: #f9f9f9;
                border-radius: 4px;
                margin-bottom: 10px;
                border: 1px solid #eee;
            }}
            .url-info {{
                flex: 1;
            }}
            .url-info small {{
                color: #666;
            }}
            .loading {{
                display: none;
                color: #4CAF50;
                font-weight: bold;
            }}
            .message {{
                padding: 10px;
                margin: 10px 0;
                border-radius: 4px;
                display: none;
            }}
            .message.success {{
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
                display: block;
            }}
            .message.error {{
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
                display: block;
            }}
            #message {{
                display: none;
            }}
        </style>
    </head>
    <body>
        <h1>📺 M3U Content Getter</h1>
        <p>Aplicación que descarga y modifica archivos m3u con actualización automática cada {update_interval} horas</p>
        
        <div class="section">
            <h2>📊 Estado del Sistema</h2>
            <ul>
                <li><strong>Caché:</strong> <span class="status-ok">{cache_status}</span></li>
                <li><strong>Última actualización:</strong> {last_update}</li>
                <li><strong>Intervalo de actualización:</strong> {update_interval} horas</li>
            </ul>
        </div>
        
        <div class="section">
            <h2>⚙️ Configuración principal:</h2>
            <ul>
                <li><strong>URL del m3u:</strong> <code>{m3u_url}</code></li>
                <li><strong>IP original:</strong> <code>{old_ip}</code></li>
                <li><strong>IP nueva:</strong> <code>{new_ip}</code></li>
                <li><strong>Puerto del servidor:</strong> <code>{server_port}</code></li>
            </ul>
        </div>
        
        <div class="section">
            <h2>➕ Agregar URL Personalizada</h2>
            <div id="message" class="message"></div>
            <div class="form-group">
                <label for="urlInput">URL del archivo M3U:</label>
                <input type="url" id="urlInput" placeholder="https://ejemplo.com/playlist.m3u" />
            </div>
            <div class="form-group">
                <label for="nameInput">Nombre (opcional):</label>
                <input type="text" id="nameInput" placeholder="Mi lista personal" />
            </div>
            <button onclick="addURL()">Agregar URL</button>
            <span id="loading" class="loading">Agregando URL y actualizando caché...</span>
        </div>
        
        <div class="section">
            <h2>📋 URLs Personalizadas ({len(custom_urls)})</h2>
            {urls_html}
        </div>
        
        <div class="section">
            <h2>🔗 Endpoints disponibles:</h2>
            <ul>
                <li><a href="/stream.m3u">/stream.m3u</a> - Descargar el archivo m3u modificado</li>
                <li><a href="/status">/status</a> - JSON con estado detallado de la aplicación</li>
                <li><a href="/health">/health</a> - Verificar disponibilidad del servidor</li>
                <li><a href="/api/custom-urls">/api/custom-urls</a> - Lista de URLs personalizadas (GET/POST)</li>
            </ul>
        </div>
        
        <div class="section">
            <h2>💡 Cómo usar:</h2>
            <p><strong>En VLC, Kodi u otros reproductores:</strong></p>
            <code>http://IP_DEL_SERVIDOR:{server_port}/stream.m3u</code>
        </div>
        
        <script>
            async function addURL() {{
                const url = document.getElementById('urlInput').value.trim();
                const name = document.getElementById('nameInput').value.trim();
                const messageDiv = document.getElementById('message');
                const loading = document.getElementById('loading');
                
                messageDiv.style.display = 'none';
                
                if (!url) {{
                    messageDiv.textContent = 'Por favor ingresa una URL';
                    messageDiv.className = 'message error';
                    messageDiv.style.display = 'block';
                    return;
                }}
                
                loading.style.display = 'inline';
                
                try {{
                    const response = await fetch('/api/custom-urls', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                        }},
                        body: JSON.stringify({{url: url, name: name}})
                    }});
                    
                    const data = await response.json();
                    
                    if (response.ok) {{
                        messageDiv.textContent = '✓ URL agregada exitosamente. Caché actualizado.';
                        messageDiv.className = 'message success';
                        messageDiv.style.display = 'block';
                        document.getElementById('urlInput').value = '';
                        document.getElementById('nameInput').value = '';
                        setTimeout(() => location.reload(), 2000);
                    }} else {{
                        messageDiv.textContent = '✗ Error: ' + data.error;
                        messageDiv.className = 'message error';
                        messageDiv.style.display = 'block';
                    }}
                }} catch (error) {{
                    messageDiv.textContent = '✗ Error de red: ' + error.message;
                    messageDiv.className = 'message error';
                    messageDiv.style.display = 'block';
                }} finally {{
                    loading.style.display = 'none';
                }}
            }}
            
            async function deleteURL(url, button) {{
                if (!confirm('¿Estás seguro de que deseas eliminar esta URL?')) {{
                    return;
                }}
                
                try {{
                    const response = await fetch('/api/custom-urls/' + encodeURIComponent(url), {{
                        method: 'DELETE'
                    }});
                    
                    if (response.ok) {{
                        alert('URL eliminada. Recargando página...');
                        location.reload();
                    }} else {{
                        const data = await response.json();
                        alert('Error: ' + data.error);
                    }}
                }} catch (error) {{
                    alert('Error de red: ' + error.message);
                }}
            }}
            
            // Auto-submit al presionar Enter
            document.getElementById('nameInput').addEventListener('keypress', function(e) {{
                if (e.key === 'Enter') addURL();
            }});
            document.getElementById('urlInput').addEventListener('keypress', function(e) {{
                if (e.key === 'Enter') addURL();
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
