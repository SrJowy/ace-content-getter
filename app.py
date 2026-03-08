"""
Aplicación que descarga un archivo m3u, reemplaza IPs y lo sirve mediante HTTP
con caché automático y descarga cada 12 horas
"""

import requests
from flask import Flask, send_file, jsonify
from io import BytesIO
import logging
import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import threading

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


def download_and_modify_m3u():
    """Descarga el archivo m3u y reemplaza las IPs"""
    try:
        logger.info(f"Descargando m3u desde: {m3u_url}")
        response = requests.get(m3u_url, timeout=10)
        response.raise_for_status()
        
        # Obtener contenido
        content = response.text
        
        # Realizar el reemplazo
        modified_content = content.replace(old_ip, new_ip)
        
        logger.info(f"Reemplazo completado: {old_ip} -> {new_ip}")
        logger.info(f"Tamaño original: {len(content)} bytes")
        logger.info(f"Tamaño modificado: {len(modified_content)} bytes")
        
        return modified_content
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al descargar el archivo m3u: {e}")
        raise
    except Exception as e:
        logger.error(f"Error al procesar el archivo: {e}")
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

@app.route('/')
def index():
    """Página de inicio"""
    cache_status = "✓ Disponible" if cache.is_valid() else "✗ No disponible"
    last_update = cache.last_update.strftime('%Y-%m-%d %H:%M:%S') if cache.last_update else "Nunca"
    
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
            <h2>⚙️ Configuración actual:</h2>
            <ul>
                <li><strong>URL del m3u:</strong> <code>{m3u_url}</code></li>
                <li><strong>IP original:</strong> <code>{old_ip}</code></li>
                <li><strong>IP nueva:</strong> <code>{new_ip}</code></li>
                <li><strong>Puerto del servidor:</strong> <code>{server_port}</code></li>
            </ul>
        </div>
        
        <div class="section">
            <h2>🔗 Endpoints disponibles:</h2>
            <ul>
                <li><a href="/stream.m3u">/stream.m3u</a> - Descargar el archivo m3u modificado</li>
                <li><a href="/status">/status</a> - JSON con estado detallado de la aplicación</li>
                <li><a href="/health">/health</a> - Verificar disponibilidad del servidor</li>
            </ul>
        </div>
        
        <div class="section">
            <h2>💡 Cómo usar:</h2>
            <p><strong>En VLC:</strong></p>
            <code>http://localhost:{server_port}/stream.m3u</code>
            <p><strong>En Kodi y otros reproductores:</strong></p>
            <code>http://IP_DEL_SERVIDOR:{server_port}/stream.m3u</code>
        </div>
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
    logger.info("="*60)
    
    # Descargar el contenido inicial
    logger.info("Descargando contenido inicial...")
    update_cache()
    
    # Iniciar el scheduler
    init_scheduler()
    
    # Iniciar el servidor Flask
    logger.info(f"Servidor iniciado en http://0.0.0.0:{server_port}")
    app.run(host='0.0.0.0', port=server_port, debug=False, use_reloader=False)
