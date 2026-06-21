"""
Gestor principal de la aplicación
Orquesta todas las dependencias y servicios
"""

import os
from flask import Flask, render_template_string
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app import config
from app.utils.logger import get_logger
from app.models.cache import M3UCache
from app.models.config import ConfigManager
from app.services.stream_manager import StreamManager
from app.services.cache_updater import CacheUpdater
from app.api.routes import APIRoutes

logger = get_logger(__name__)


class AppManager:
    """Gestor central de la aplicación"""
    
    def __init__(self):
        """Inicializa todos los componentes de la aplicación"""
        logger.info("Inicializando AppManager...")
        
        # Cargar configuración
        app_config = config.get_config()
        
        # Crear directorios de datos si no existen
        self._init_data_directory(app_config['paths']['data_dir'])
        
        # Inicializar modelos
        self.cache = M3UCache()
        self.config_manager = ConfigManager(app_config['paths']['config_file'])
        self.stream_manager = StreamManager(app_config['paths']['custom_streams_file'])
        
        # Inicializar servicios
        self.cache_updater = CacheUpdater(
            cache=self.cache,
            config_manager=self.config_manager,
            stream_manager=self.stream_manager,
            m3u_url=app_config['m3u']['url'],
            old_ip=app_config['ip_replacement']['old_ip'],
            new_ip=app_config['ip_replacement']['new_ip'],
        )
        
        # Guardar config para acceso posterior
        self.app_config = app_config
        
        # Crear app Flask
        self.flask_app = Flask(__name__, template_folder=str(self._get_template_folder()))
        
        # Registrar rutas API
        api_routes = APIRoutes(
            cache=self.cache,
            config_manager=self.config_manager,
            stream_manager=self.stream_manager,
            cache_updater=self.cache_updater,
            m3u_url=app_config['m3u']['url'],
            update_interval=app_config['intervals']['online'],
            parser_update_interval=app_config['intervals']['parser'],
        )
        self.flask_app.register_blueprint(api_routes.blueprint)
        
        # Inicializar scheduler
        self.scheduler = BackgroundScheduler()
        self._setup_scheduler()
        
        logger.info("AppManager inicializado correctamente")
    
    def _init_data_directory(self, data_dir: str) -> None:
        """
        Crea el directorio de datos si no existe
        
        Args:
            data_dir: Ruta del directorio de datos
        """
        if data_dir and not os.path.exists(data_dir):
            try:
                os.makedirs(data_dir, mode=0o777, exist_ok=True)
                logger.info(f"Directorio de datos creado: {data_dir}")
            except Exception as e:
                logger.error(f"Error al crear directorio de datos: {e}")
                logger.warning("Usando directorio actual como fallback")
    
    def _get_template_folder(self):
        """Retorna la ruta de la carpeta de templates"""
        from pathlib import Path
        return Path(__file__).parent / 'templates'
    
    def _setup_scheduler(self) -> None:
        """Configura el scheduler para actualizaciones automáticas"""
        source = self.config_manager.get_source()
        interval = self.app_config['intervals']['parser'] if source == 'parser' \
                   else self.app_config['intervals']['online']
        
        self.scheduler.add_job(
            func=self.cache_updater.update,
            trigger=IntervalTrigger(hours=interval),
            id='m3u_update',
            name=f'Actualización de caché M3U ({source})',
            replace_existing=True
        )
        
        logger.info(f"Scheduler configurado: modo {source.upper()}, actualización cada {interval} horas")
    
    def reconfigure_scheduler(self, source: str = None) -> bool:
        """
        Reconfigura el scheduler con el intervalo correcto según la fuente
        
        Args:
            source: Fuente de M3U ('online' o 'parser'). Si es None, usa la configurada.
        
        Returns:
            True si la reconfiguración fue exitosa
        """
        if source is None:
            source = self.config_manager.get_source()
        
        interval = self.app_config['intervals']['parser'] if source == 'parser' \
                   else self.app_config['intervals']['online']
        
        try:
            # Remover job anterior si existe
            if self.scheduler.running:
                try:
                    self.scheduler.remove_job('m3u_update')
                except:
                    pass
            
            # Agregar nuevo job
            self.scheduler.add_job(
                func=self.cache_updater.update,
                trigger=IntervalTrigger(hours=interval),
                id='m3u_update',
                name=f'Actualización de caché M3U ({source})',
                replace_existing=True
            )
            
            logger.info(f"Scheduler reconfigurado: modo {source.upper()}, actualización cada {interval} horas")
            return True
        except Exception as e:
            logger.error(f"Error reconfigurando scheduler: {e}")
            return False
    
    def init_cache(self) -> None:
        """Realiza una actualización inicial del caché"""
        logger.info("Descargando contenido inicial...")
        self.cache_updater.update()
    
    def start_scheduler(self) -> None:
        """Inicia el scheduler de actualizaciones automáticas"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler iniciado")
    
    def stop_scheduler(self) -> None:
        """Detiene el scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler detenido")
    
    def run(self, host: str = None, port: int = None, debug: bool = None) -> None:
        """
        Inicia el servidor Flask
        
        Args:
            host: Host donde ejecutar (usa config si es None)
            port: Puerto donde ejecutar (usa config si es None)
            debug: Modo debug (usa config si es None)
        """
        host = host or self.app_config['server']['host']
        port = port or self.app_config['server']['port']
        debug = debug if debug is not None else self.app_config['server']['debug']
        
        logger.info("="*60)
        logger.info("INICIANDO M3U CONTENT GETTER")
        logger.info("="*60)
        logger.info(f"Puerto: {port}")
        logger.info(f"Host: {host}")
        logger.info(f"URL del m3u: {self.app_config['m3u']['url']}")
        logger.info(f"IP original: {self.app_config['ip_replacement']['old_ip']}")
        logger.info(f"IP nueva: {self.app_config['ip_replacement']['new_ip']}")
        logger.info(f"Directorio de datos: {self.app_config['paths']['data_dir']}")
        logger.info("="*60)
        
        # Inicializar caché
        self.init_cache()
        
        # Iniciar scheduler
        self.start_scheduler()
        
        # Iniciar servidor Flask
        logger.info(f"Servidor iniciado en http://{host}:{port}")
        self.flask_app.run(host=host, port=port, debug=debug, use_reloader=False)
