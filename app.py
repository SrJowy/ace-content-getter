"""
Compatibilidad histórica: app.py refactorizado
Este archivo ahora importa de la estructura modular en app/

La aplicación ha sido refactorizada para usar una arquitectura modular.
Usar: python main.py en lugar de python app.py

Este archivo se mantiene por compatibilidad.
"""

from app.app_manager import AppManager


if __name__ == '__main__':
    app_manager = AppManager()
    app_manager.run()
