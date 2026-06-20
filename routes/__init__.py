"""
Routes package - API and UI route blueprints
"""

from .api import api_bp, init_api
from .ui import ui_bp, init_ui


def register_routes(app, dependencies):
    """
    Registra todos los blueprints de rutas en la aplicación Flask.
    
    Args:
        app: Instancia de Flask
        dependencies: Diccionario con las dependencias necesarias:
            - stream_manager: StreamManager
            - m3u_modification_manager: M3UModificationManager
            - cache: M3UCache
            - update_cache_func: función para actualizar caché
    """
    # Inicializar módulos con dependencias
    init_api(
        dependencies['stream_manager'],
        dependencies['m3u_modification_manager'],
        dependencies['cache'],
        dependencies['update_cache_func']
    )
    
    init_ui(
        dependencies['cache'],
        dependencies['stream_manager'],
        dependencies['m3u_modification_manager']
    )
    
    # Registrar blueprints
    app.register_blueprint(api_bp)
    app.register_blueprint(ui_bp)


__all__ = ['register_routes', 'api_bp', 'ui_bp']
