"""极简线程安全 TTL 缓存（内存 dict + monotonic 时钟，无外部依赖）。"""
from __future__ import annotations

import threading
import time

try:
    from config import CACHE_TTL_SECONDS
except ModuleNotFoundError:  # pragma: no cover
    from .config import CACHE_TTL_SECONDS

_cache_store: dict[str, tuple[float, str]] = {}
_cache_lock = threading.Lock()


def cache_get(key: str) -> str | None:
    """返回未过期的缓存 SVG；缺失或已过期返回 None。"""
    now = time.monotonic()
    with _cache_lock:
        entry = _cache_store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if now >= expires_at:
            _cache_store.pop(key, None)
            return None
        return value


def cache_set(key: str, value: str) -> None:
    """写入缓存，过期时间为 CACHE_TTL_SECONDS 后。"""
    with _cache_lock:
        _cache_store[key] = (time.monotonic() + CACHE_TTL_SECONDS, value)


def cache_clear() -> None:
    """清空全部缓存（调试/测试用）。"""
    with _cache_lock:
        _cache_store.clear()


def cache_size() -> int:
    """当前缓存条目数。"""
    with _cache_lock:
        return len(_cache_store)
