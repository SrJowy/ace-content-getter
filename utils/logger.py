"""
Configuración centralizada de logging
"""

import logging

def setup_logger(name=None):
    """
    Configura y retorna un logger con formato estandarizado
    
    Args:
        name: Nombre del logger (por defecto el nombre del módulo)
    
    Returns:
        logging.Logger: Logger configurado
    """
    logger = logging.getLogger(name)
    
    # Solo configura si no está ya configurado
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    return logger


# Logger global de la aplicación
logger = setup_logger(__name__)

__all__ = ['setup_logger', 'logger']
