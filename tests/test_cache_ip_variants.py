from app.models.cache import M3UCache
from app.models.config import ConfigManager
from app.services.cache_updater import CacheUpdater
from app.services.stream_manager import StreamManager


def test_cache_stores_default_and_away_ip_variants(tmp_path):
    cache = M3UCache()
    config_manager = ConfigManager(str(tmp_path / 'config.json'))
    stream_manager = StreamManager(str(tmp_path / 'custom_streams.json'))

    updater = CacheUpdater(
        cache=cache,
        config_manager=config_manager,
        stream_manager=stream_manager,
        m3u_url='http://example.com/list.m3u',
        old_ip='127.0.0.1',
        new_ip='192.168.1.151',
        away_ip='100.80.52.89',
    )
    updater.fetch_from_online_url = lambda url=None: '#EXTM3U\nhttp://127.0.0.1:6878/stream\n'
    stream_manager.get_streams = lambda: []

    assert updater.update() is True
    assert '192.168.1.151' in cache.get()
    assert '100.80.52.89' in cache.get_away()
    assert '127.0.0.1' not in cache.get_away()
