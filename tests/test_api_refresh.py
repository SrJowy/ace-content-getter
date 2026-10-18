from urllib.parse import parse_qs, urlsplit

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


def test_acestream_proxy_follows_safe_redirects_without_explicit_stop(tmp_path, monkeypatch):
    info_hash = 'a' * 40
    source_url = f'http://192.168.1.151:8088/ace/getstream?id={info_hash}'
    session_url_prefix = f'{source_url}&format=json&pid='
    playback_url = 'http://192.168.1.151:6878/ace/r/' + 'c' * 40 + '/' + 'd' * 32
    content_url = 'http://192.168.1.151:6878/content/' + 'c' * 40 + '/segment'
    app = Flask(__name__)
    cache = M3UCache()
    cache.set(f'#EXTM3U\n#EXTINF:-1,Test\n{source_url}\n')
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

    class FakeUpstream:
        status_code = 200
        headers = {'Content-Type': 'video/mp2t'}

        def iter_content(self, chunk_size):
            assert chunk_size == 64 * 1024
            yield b'stream-data'

        def close(self):
            pass

    class FakeSession:
        status_code = 200
        headers = {'Content-Type': 'application/json'}

        def json(self):
            return {
                'response': {
                    'playback_url': playback_url,
                },
                'error': None,
            }

        def close(self):
            pass

    class FakeRedirect:
        status_code = 302

        def __init__(self, location):
            self.headers = {'Location': location}

        def close(self):
            pass

    requested_urls = []
    requested_headers = []
    session_urls = []

    def fake_get(url, **kwargs):
        requested_urls.append(url)
        requested_headers.append(kwargs['headers'])
        assert kwargs['allow_redirects'] is False
        if url.startswith(session_url_prefix):
            session_urls.append(url)
            return FakeSession()
        assert kwargs['stream'] is True
        if url == playback_url:
            return FakeRedirect(content_url)
        return FakeUpstream()

    monkeypatch.setattr('app.api.routes.requests.get', fake_get)
    client = app.test_client()

    assert client.get('/api/player/acestream/not-a-hash').status_code == 400
    assert client.get(f'/api/player/acestream/{"b" * 40}').status_code == 404

    response = client.get(f'/api/player/acestream/{info_hash}', headers={'Range': 'bytes=0-'})

    assert response.status_code == 200
    assert response.data == b'stream-data'
    assert response.content_type == 'video/mp2t'
    assert requested_urls == [session_urls[0], playback_url, content_url]
    assert len(parse_qs(urlsplit(session_urls[0]).query)['pid'][0]) == 32
    assert all(headers['Range'] == 'bytes=0-' for headers in requested_headers[1:3])
    assert requested_headers[0] == {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    requested_urls.clear()
    requested_headers.clear()

    def fake_localhost_redirect(url, **kwargs):
        requested_urls.append(url)
        if url.startswith(session_url_prefix):
            session_urls.append(url)
            return FakeSession()
        return FakeRedirect('http://127.0.0.1:6878/ace/r/test')

    monkeypatch.setattr('app.api.routes.requests.get', fake_localhost_redirect)
    response = client.get(f'/api/player/acestream/{info_hash}')

    assert response.status_code == 502
    assert requested_urls == [session_urls[1], playback_url]
    assert parse_qs(urlsplit(session_urls[0]).query)['pid'] != parse_qs(urlsplit(session_urls[1]).query)['pid']


def test_acestream_away_proxy_uses_away_cache(tmp_path, monkeypatch):
    info_hash = 'a' * 40
    home_url = f'http://192.168.1.151:8088/ace/getstream?id={info_hash}'
    away_url = f'http://100.80.52.89:8088/ace/getstream?id={info_hash}'
    away_playback_url = 'http://100.80.52.89:6878/ace/r/' + 'c' * 40 + '/' + 'd' * 32
    away_content_url = 'http://100.80.52.89:6878/content/' + 'c' * 40 + '/segment'
    app = Flask(__name__)
    cache = M3UCache()
    cache.set(f'#EXTM3U\n#EXTINF:-1,Home\n{home_url}\n')
    cache.set_away(f'#EXTM3U\n#EXTINF:-1,Away\n{away_url}\n')
    routes = APIRoutes(
        cache=cache,
        config_manager=ConfigManager(str(tmp_path / 'config.json')),
        stream_manager=StreamManager(str(tmp_path / 'custom_streams.json')),
        cache_updater=DummyCacheUpdater(),
        m3u_url='http://example.com/list.m3u',
        update_interval=6,
        parser_update_interval=12,
    )
    app.register_blueprint(routes.blueprint)

    class FakeResponse:
        status_code = 200
        headers = {'Content-Type': 'application/json'}

        def json(self):
            return {'response': {'playback_url': away_playback_url}, 'error': None}

        def close(self):
            pass

    class FakeRedirect:
        status_code = 302

        def __init__(self, location):
            self.headers = {'Location': location}

        def close(self):
            pass

    class FakeMedia:
        status_code = 200
        headers = {'Content-Type': 'video/mp2t'}

        def iter_content(self, chunk_size):
            yield b'away-stream'

        def close(self):
            pass

    requested_urls = []

    def fake_get(url, **kwargs):
        requested_urls.append(url)
        if url.startswith('http://100.80.52.89:8088/'):
            return FakeResponse()
        if url == away_playback_url:
            return FakeRedirect(away_content_url)
        return FakeMedia()

    monkeypatch.setattr('app.api.routes.requests.get', fake_get)
    response = app.test_client().get(f'/api/player/acestream/away/{info_hash}')

    assert response.status_code == 200
    assert response.data == b'away-stream'
    assert requested_urls[0].startswith(away_url + '&format=json&pid=')
    assert requested_urls[0] != home_url
