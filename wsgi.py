"""
WSGI entrypoint for VS Code debugging and WSGI servers.
Exposes `app` (Flask instance) and runs when executed directly.
"""

from app.app_manager import AppManager


app_manager = AppManager()
app = app_manager.flask_app


if __name__ == "__main__":
    app_manager.run()
