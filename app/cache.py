"""极简线程安全 TTL 缓存（内存 dict + monotonic 时钟，无外部依赖）。"""
from __future__ import annotations

import threading
import time

try:
    from config import CACHE_MAX_ENTRIES, CACHE_TTL_SECONDS
except ModuleNotFoundError:  # pragma: no cover
    from .config import CACHE_MAX_ENTRIES, CACHE_TTL_SECONDS

_cache_store: dict[str, tuple[float, int, str]] = {}
_cache_lock = threading.Lock()
_cache_sequence = 0


def cache_get(key: str) -> str | None:
    """返回未过期的缓存 SVG；缺失或已过期返回 None。"""
    now = time.monotonic()
    with _cache_lock:
        entry = _cache_store.get(key)
        if entry is None:
            return None
        expires_at, _, value = entry
        if now >= expires_at:
            _cache_store.pop(key, None)
            return None
        return value


def cache_set(key: str, value: str) -> None:
    """写入缓存并限制条目数，优先清除过期项，再淘汰最早写入的项。"""
    now = time.monotonic()
    global _cache_sequence
    with _cache_lock:
        # 惰性回收：只有读写缓存时才扫描过期项，避免额外后台任务。
        expired = [cache_key for cache_key, (expires_at, _, _) in _cache_store.items() if now >= expires_at]
        for cache_key in expired:
            _cache_store.pop(cache_key, None)
        _cache_sequence += 1
        _cache_store[key] = (now + CACHE_TTL_SECONDS, _cache_sequence, value)
        while len(_cache_store) > CACHE_MAX_ENTRIES:
            oldest_key = min(_cache_store, key=lambda cache_key: _cache_store[cache_key][1])
            _cache_store.pop(oldest_key)


def cache_clear() -> None:
    """清空全部缓存（调试/测试用）。"""
    global _cache_sequence
    with _cache_lock:
        _cache_store.clear()
        _cache_sequence = 0


def cache_size() -> int:
    """当前缓存条目数。"""
    with _cache_lock:
        return len(_cache_store)
