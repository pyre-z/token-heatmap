"""内存 SVG 缓存的容量与淘汰行为。"""
from app import cache


def test_cache_set_evicts_oldest_entry_at_capacity(monkeypatch):
    cache.cache_clear()
    monkeypatch.setattr(cache, "CACHE_MAX_ENTRIES", 2)
    now = [1.0]
    monkeypatch.setattr(cache.time, "monotonic", lambda: now[0])

    cache.cache_set("first", "1")
    now[0] = 2.0
    cache.cache_set("second", "2")
    now[0] = 3.0
    cache.cache_set("third", "3")

    assert cache.cache_size() == 2
    assert cache.cache_get("first") is None
    assert cache.cache_get("second") == "2"
    assert cache.cache_get("third") == "3"
    cache.cache_clear()


def test_cache_set_removes_expired_entries_before_evicting(monkeypatch):
    cache.cache_clear()
    monkeypatch.setattr(cache, "CACHE_MAX_ENTRIES", 2)
    monkeypatch.setattr(cache, "CACHE_TTL_SECONDS", 1)
    now = [0.0]
    monkeypatch.setattr(cache.time, "monotonic", lambda: now[0])

    cache.cache_set("expired", "old")
    now[0] = 2.0
    cache.cache_set("fresh-one", "1")
    cache.cache_set("fresh-two", "2")

    assert cache.cache_size() == 2
    assert cache.cache_get("expired") is None
    assert cache.cache_get("fresh-one") == "1"
    assert cache.cache_get("fresh-two") == "2"
    cache.cache_clear()
