#!/usr/bin/env python3
"""
Entry point principal de M3U Content Getter
Inicia la aplicación con toda la estructura modular
"""

from app.app_manager import AppManager


def main():
    """Inicia la aplicación"""
    app_manager = AppManager()
    app_manager.run()


if __name__ == '__main__':
    main()
