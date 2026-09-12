"""内存 SVG 缓存的容量与淘汰行为。"""
import threading

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


def test_render_svg_renders_a_same_key_miss_once_for_concurrent_callers():
    """Given eight same-key misses, when the renderer blocks, then one SVG serves every caller."""
    cache.cache_clear()
    renderer_started = threading.Event()
    release_renderer = threading.Event()
    render_count = 0
    render_count_lock = threading.Lock()
    svgs: list[str] = []
    svgs_lock = threading.Lock()
    def render() -> str:
        nonlocal render_count
        with render_count_lock:
            render_count += 1
        renderer_started.set()
        release_renderer.wait()
        return "<svg>single-flight</svg>"

    def request_svg() -> None:
        svg = cache.render_cached("same-key", render)
        with svgs_lock:
            svgs.append(svg)

    leader = threading.Thread(target=request_svg)
    leader.start()
    assert renderer_started.wait(timeout=1)
    threads = [threading.Thread(target=request_svg) for _ in range(7)]
    for thread in threads:
        thread.start()
    release_renderer.set()
    leader.join(timeout=1)
    assert not leader.is_alive()
    for thread in threads:
        thread.join(timeout=1)
        assert not thread.is_alive()

    assert render_count == 1
    assert svgs == ["<svg>single-flight</svg>"] * 8
    cache.cache_clear()


def test_render_svg_limits_different_keys_to_configured_concurrency(monkeypatch):
    """Given three different misses and a limit of two, when rendering, then no more than two run together."""
    cache.cache_clear()
    monkeypatch.setattr(cache, "_render_semaphore", threading.BoundedSemaphore(2), raising=False)
    callers = threading.Barrier(3)
    two_renderers_started = threading.Event()
    release_renderers = threading.Event()
    active_renderers = 0
    maximum_active_renderers = 0
    active_renderers_lock = threading.Lock()

    def render() -> str:
        nonlocal active_renderers, maximum_active_renderers
        with active_renderers_lock:
            active_renderers += 1
            maximum_active_renderers = max(maximum_active_renderers, active_renderers)
            if active_renderers == 2:
                two_renderers_started.set()
        release_renderers.wait()
        with active_renderers_lock:
            active_renderers -= 1
        return "<svg>bounded</svg>"

    def request_svg(key: str) -> None:
        callers.wait()
        cache.render_cached(key, render)

    threads = [threading.Thread(target=request_svg, args=(f"key-{index}",)) for index in range(3)]
    for thread in threads:
        thread.start()

    assert two_renderers_started.wait(timeout=1)
    with active_renderers_lock:
        assert active_renderers == 2
        assert maximum_active_renderers == 2
    release_renderers.set()
    for thread in threads:
        thread.join(timeout=1)
        assert not thread.is_alive()

    assert maximum_active_renderers == 2
    cache.cache_clear()


def test_render_svg_wakes_same_key_waiters_after_error_and_allows_retry():
    """Given a failing same-key render, when waiters wake, then errors are uncached and a retry renders anew."""
    cache.cache_clear()
    renderer_started = threading.Event()
    release_renderer = threading.Event()
    render_count = 0
    render_count_lock = threading.Lock()
    errors: list[RuntimeError] = []
    errors_lock = threading.Lock()

    def failing_render() -> str:
        nonlocal render_count
        with render_count_lock:
            render_count += 1
        renderer_started.set()
        release_renderer.wait()
        raise RuntimeError("renderer failed")

    def request_svg() -> None:
        try:
            cache.render_cached("failing-key", failing_render)
        except RuntimeError as error:
            with errors_lock:
                errors.append(error)

    leader = threading.Thread(target=request_svg)
    leader.start()
    assert renderer_started.wait(timeout=1)
    waiter = threading.Thread(target=request_svg)
    waiter.start()
    release_renderer.set()
    leader.join(timeout=1)
    waiter.join(timeout=1)
    assert not leader.is_alive()
    assert not waiter.is_alive()

    assert render_count == 1
    assert [str(error) for error in errors] == ["renderer failed", "renderer failed"]
    assert cache.render_cached("failing-key", lambda: "<svg>retry</svg>") == "<svg>retry</svg>"
    assert render_count == 1
    cache.cache_clear()
