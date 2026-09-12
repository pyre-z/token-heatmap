"""极简线程安全 TTL 缓存（内存 dict + monotonic 时钟，无外部依赖）。"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable

try:
    from config import CACHE_MAX_ENTRIES, CACHE_TTL_SECONDS, MAX_RENDER_CONCURRENCY
except ModuleNotFoundError:  # pragma: no cover
    from .config import CACHE_MAX_ENTRIES, CACHE_TTL_SECONDS, MAX_RENDER_CONCURRENCY

_cache_store: dict[str, tuple[float, int, str]] = {}
_cache_lock = threading.Lock()
_cache_sequence = 0
_inflight_renders: dict[str, _RenderFlight] = {}
_render_semaphore = threading.BoundedSemaphore(MAX_RENDER_CONCURRENCY)


class _RenderFlight:
    """Mutable state shared by callers awaiting one process-local render."""

    def __init__(self) -> None:
        self.ready = threading.Event()
        self.svg: str | None = None
        self.error: BaseException | None = None


def _get_cached_locked(key: str, now: float) -> str | None:
    """Return a non-expired value while the cache lock is held."""
    entry = _cache_store.get(key)
    if entry is None:
        return None
    expires_at, _, value = entry
    if now >= expires_at:
        _cache_store.pop(key, None)
        return None
    return value


def _set_cached_locked(key: str, value: str, now: float) -> None:
    """Store one SVG and enforce cache capacity while the cache lock is held."""
    global _cache_sequence
    expired = [cache_key for cache_key, (expires_at, _, _) in _cache_store.items() if now >= expires_at]
    for cache_key in expired:
        _cache_store.pop(cache_key, None)
    _cache_sequence += 1
    _cache_store[key] = (now + CACHE_TTL_SECONDS, _cache_sequence, value)
    while len(_cache_store) > CACHE_MAX_ENTRIES:
        oldest_key = min(_cache_store, key=lambda cache_key: _cache_store[cache_key][1])
        _cache_store.pop(oldest_key)


def cache_get(key: str) -> str | None:
    """返回未过期的缓存 SVG；缺失或已过期返回 None。"""
    now = time.monotonic()
    with _cache_lock:
        return _get_cached_locked(key, now)


def cache_set(key: str, value: str) -> None:
    """写入缓存并限制条目数，优先清除过期项，再淘汰最早写入的项。"""
    now = time.monotonic()
    with _cache_lock:
        _set_cached_locked(key, value, now)


def render_cached(key: str, render: Callable[[], str]) -> str:
    """Return cached SVG or coordinate one bounded render per key within this process."""
    with _cache_lock:
        cached = _get_cached_locked(key, time.monotonic())
        if cached is not None:
            return cached
        flight = _inflight_renders.get(key)
        if flight is None:
            flight = _RenderFlight()
            _inflight_renders[key] = flight
            is_renderer = True
        else:
            is_renderer = False

    if not is_renderer:
        flight.ready.wait()
        if flight.error is not None:
            raise flight.error
        if flight.svg is None:
            raise RuntimeError("render flight completed without a result")
        return flight.svg

    try:
        with _render_semaphore:
            svg = render()
    except BaseException as error:
        with _cache_lock:
            flight.error = error
            _inflight_renders.pop(key, None)
            flight.ready.set()
        raise

    with _cache_lock:
        _set_cached_locked(key, svg, time.monotonic())
        flight.svg = svg
        _inflight_renders.pop(key, None)
        flight.ready.set()
    return svg


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
