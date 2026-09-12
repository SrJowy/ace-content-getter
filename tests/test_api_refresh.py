from flask import Flask

from app.api.routes import APIRoutes
from app.models.cache import M3UCache
from app.models.config import ConfigManager
from app.services.stream_manager import StreamManager


class DummyCacheUpdater:
    def __init__(self):
        self.calls = 0

    def update(self):
        self.calls += 1
        return True


def test_refresh_endpoint_forces_cache_update(tmp_path):
    app = Flask(__name__)
    cache = M3UCache()
    config_manager = ConfigManager(str(tmp_path / 'config.json'))
    stream_manager = StreamManager(str(tmp_path / 'custom_streams.json'))
    cache_updater = DummyCacheUpdater()

    routes = APIRoutes(
        cache=cache,
        config_manager=config_manager,
        stream_manager=stream_manager,
        cache_updater=cache_updater,
        m3u_url='http://example.com/list.m3u',
        update_interval=6,
        parser_update_interval=12,
    )
    app.register_blueprint(routes.blueprint)

    client = app.test_client()
    response = client.post('/api/refresh')
    payload = response.get_json()

    assert response.status_code == 200
    assert payload['status'] == 'updated'
    assert 'last_update' in payload
    assert cache_updater.calls == 1
