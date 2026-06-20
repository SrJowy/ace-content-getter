"""
M3U Content Getter - Aplicación principal

Descarga un archivo m3u, reemplaza IPs y lo sirve mediante HTTP
con caché automático y descarga cada 12 horas
"""

import os
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

# Importar configuración
from config import (
    M3U_URL, SERVER_PORT, OLD_IP, NEW_IP, UPDATE_INTERVAL,
    DATA_DIR, CUSTOM_STREAMS_FILE, M3U_MODIFICATIONS_FILE
)

# Importar modelos
from models import M3UCache, StreamManager, M3UModificationManager

# Importar core
from core import download_and_modify_m3u

# Importar rutas
from routes import register_routes

# Importar logging
from utils import setup_logger, logger

# Configurar logging global
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
logger.addHandler(__import__('logging').StreamHandler())
logger.setLevel(__import__('logging').INFO)

# Crear aplicación Flask
app = Flask(__name__)

# Inicializar componentes globales
cache = M3UCache()
stream_manager = StreamManager(CUSTOM_STREAMS_FILE)
m3u_modification_manager = M3UModificationManager(M3U_MODIFICATIONS_FILE)
scheduler = BackgroundScheduler()


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


def update_cache():
    """Actualiza el caché descargando el archivo m3u más reciente"""
    if cache.update_in_progress:
        logger.info("Una actualización ya está en progreso, saltando...")
        return
    
    cache.update_in_progress = True
    try:
        logger.info(f"[ACTUALIZACIÓN PROGRAMADA] Descargando archivo m3u (cada {UPDATE_INTERVAL}h)")
        modified_content = download_and_modify_m3u(stream_manager, m3u_modification_manager)
        cache.set(modified_content)
        logger.info("[ACTUALIZACIÓN PROGRAMADA] Caché actualizado exitosamente")
    except Exception as e:
        error_msg = f"Error al actualizar caché: {str(e)}"
        logger.error(error_msg)
        cache.set_error(error_msg)
    finally:
        cache.update_in_progress = False


def init_scheduler():
    """Inicializa el scheduler para actualizaciones automáticas"""
    if not scheduler.running:
        scheduler.add_job(
            func=update_cache,
            trigger="interval",
            hours=UPDATE_INTERVAL,
            id='m3u_update',
            name='Actualización de caché M3U',
            replace_existing=True
        )
        scheduler.start()
        logger.info(f"Scheduler iniciado: actualización cada {UPDATE_INTERVAL} horas")


def init_app():
    """Inicializa la aplicación con todas las dependencias"""
    logger.info("="*60)
    logger.info("INICIANDO M3U CONTENT GETTER")
    logger.info("="*60)
    logger.info(f"Puerto: {SERVER_PORT}")
    logger.info(f"URL del m3u: {M3U_URL}")
    logger.info(f"IP original: {OLD_IP}")
    logger.info(f"IP nueva: {NEW_IP}")
    logger.info(f"Intervalo de actualización: {UPDATE_INTERVAL} horas")
    logger.info(f"Directorio de datos: {DATA_DIR}")
    logger.info("="*60)
    
    # Inicializar directorio de datos
    init_data_directory()
    
    # Descargar el contenido inicial
    logger.info("Descargando contenido inicial...")
    update_cache()
    
    # Registrar rutas
    dependencies = {
        'stream_manager': stream_manager,
        'm3u_modification_manager': m3u_modification_manager,
        'cache': cache,
        'update_cache_func': update_cache
    }
    register_routes(app, dependencies)
    
    # Iniciar el scheduler
    init_scheduler()
    
    logger.info(f"Servidor iniciado en http://0.0.0.0:{SERVER_PORT}")


if __name__ == '__main__':
    init_app()
    app.run(host='0.0.0.0', port=SERVER_PORT, debug=False, use_reloader=False)
