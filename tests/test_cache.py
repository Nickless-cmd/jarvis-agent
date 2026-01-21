import time

from jarvis.agent_core.cache import TTLCache


def test_ttlcache_hit_and_expire():
    cache = TTLCache(default_ttl=0.1)
    cache.set("k1", {"a": 1})
    assert cache.get("k1") == {"a": 1}
    time.sleep(0.15)
    assert cache.get("k1") is None


def test_ttlcache_deepcopy_and_clear():
    cache = TTLCache(default_ttl=1.0)
    value = {"a": {"b": 2}}
    cache.set("k2", value)
    fetched = cache.get("k2")
    assert fetched == value
    # mutate fetched should not alter cache
    fetched["a"]["b"] = 3
    assert cache.get("k2") == {"a": {"b": 2}}
    cache.clear()
    assert cache.get("k2") is None
