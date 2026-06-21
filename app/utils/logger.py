"""
Configuración centralizada de logging
"""

import logging
from app.config import LOG_LEVEL, LOG_FORMAT


def setup_logger(name: str) -> logging.Logger:
    """
    Configura y retorna un logger con el nombre dado
    
    Args:
        name: Nombre del logger (generalmente __name__)
    
    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    
    # Solo configurar si no está ya configurado
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(LOG_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Alias para setup_logger (para compatibilidad)
    """
    return setup_logger(name)
