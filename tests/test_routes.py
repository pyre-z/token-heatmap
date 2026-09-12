
import re

from fastapi.testclient import TestClient

from app import cache, main
from app.sources.base import Source


class FakeSource(Source):
    """测试用：返回空数据，可计数调用次数。"""

    name = "test"

    def __init__(self):
        self.daily_calls = 0
        self.hourly_calls = 0

    def daily_tokens_in_range(self, start, end):
        self.daily_calls += 1
        return {}

    def hourly_tokens(self, day):
        self.hourly_calls += 1
        return {}


def client_with_source(monkeypatch, source=None):
    source = source or FakeSource()
    monkeypatch.setattr(main, "get_source", lambda: source)
    return TestClient(main.app), source


def test_svg_granularities_and_headers(monkeypatch):
    cache.cache_clear()
    client, _ = client_with_source(monkeypatch)
    paths = [
        "/token/@",
        "/token/@?grain=year&year=2026",
        "/token/@?grain=year",
        "/token/@?grain=month&year=2026&month=9",
        "/token/@?grain=month&year=2026&month=9&day=7",
        "/token/@?grain=month",
        "/token/@?grain=day&year=2026&month=9&day=7",
        "/token/@?grain=day&year=2026&month=9&day=1",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, f"{path} -> {response.status_code}"
        assert response.headers["content-type"].startswith("image/svg+xml")
        assert response.headers["cache-control"] == "public, no-cache"


def test_invalid_parameters(monkeypatch):
    cache.cache_clear()
    client, _ = client_with_source(monkeypatch)
    for path in (
        "/token/@?grain=week",
        "/token/@?grain=year&year=1999",
        "/token/@?grain=month&month=13",
        "/token/@?grain=day&day=0",
        "/token/@?grain=month&year=abc",
        "/token/@?grain=year&theme=nope",
        "/token/@?grain=day&year=2026&month=2&day=30",
        "/token/@?grain=month&year=2026&month=2&day=30",
        "/token/@?grain=month&year=2026&month=9&scale=11",
        "/token/@?grain=month&year=2026&month=9&scale=abc",
    ):
        assert client.get(path).status_code == 400, f"{path} 期望 400"


def test_health_page_and_removed_paths():
    client = TestClient(main.app)
    assert client.get("/token/healthz").json() == {"status": "ok"}
    page = client.get("/token/")
    assert page.status_code == 200 and page.headers["content-type"].startswith("text/html")
    assert "/token/@?" in page.text
    for path in ("/token/year.svg", "/token/2026.svg", "/token/month.svg", "/healthz"):
        assert client.get(path).status_code == 404


def test_config_page_grain_radios_bound_as_group():
    """回归：querySelector 只返回单个元素，误接 .forEach 会抛 TypeError 中断脚本，预览因此不再渲染。"""
    script = TestClient(main.app).get("/token/").text.split("<script>", 1)[1].split("</script>", 1)[0]
    assert "querySelectorAll" in script, "grain radio 组必须整组绑定 change 事件"
    assert re.search(r"(?:\bq|querySelector)\([^)]*\)\.forEach", script) is None, "单个元素没有 forEach"


def test_readyz_ready_with_configured_source(monkeypatch):
    """就绪：数据源已配置时返回 200 且不查数据库。"""
    client, src = client_with_source(monkeypatch)
    response = client.get("/token/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert src.daily_calls == 0 and src.hourly_calls == 0


def test_readyz_not_ready_for_invalid_source(monkeypatch):
    """SOURCE 非法时返回 503，且不泄露连接信息。"""
    def boom() -> Source:
        raise ValueError("Unknown source: 'typo'. Supported: ['new-api', 'sub2api']")
    monkeypatch.setattr(main, "get_source", boom)
    response = TestClient(main.app).get("/token/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body == {"status": "not-ready", "reason": "invalid-source"}
    assert "typo" not in response.text and "Supported" not in response.text


def test_readyz_not_ready_when_source_unconfigured(monkeypatch):
    """数据源缺少必需配置时返回 503。"""
    class UnconfiguredSource(FakeSource):
        def is_configured(self) -> bool:
            return False
    monkeypatch.setattr(main, "get_source", lambda: UnconfiguredSource())
    response = TestClient(main.app).get("/token/readyz")
    assert response.status_code == 503
    assert response.json() == {"status": "not-ready", "reason": "source-unconfigured"}


def test_large_html_and_svg_responses_are_gzipped(monkeypatch):
    cache.cache_clear()
    client, _ = client_with_source(monkeypatch)
    assert client.get("/token/").headers["content-encoding"] == "gzip"
    assert client.get("/token/@?grain=year&year=2026").headers["content-encoding"] == "gzip"
    cache.cache_clear()


def test_database_error_is_hidden(monkeypatch):
    cache.cache_clear()

    class BoomSource(FakeSource):
        def daily_tokens_in_range(self, start, end):
            raise RuntimeError("secret")

    monkeypatch.setattr(main, "get_source", lambda: BoomSource())
    response = TestClient(main.app).get("/token/@?grain=year&year=2026")
    assert response.status_code == 502
    assert response.json()["detail"] == "db error"
    cache.cache_clear()


def test_auto_default_grain_uses_auto(monkeypatch):
    """默认 grain=auto：请求不带 grain 走滚动年分支，调用 daily_tokens_in_range。"""
    cache.cache_clear()
    client, src = client_with_source(monkeypatch)
    r = client.get("/token/@")
    assert r.status_code == 200
    assert src.daily_calls == 1
    cache.cache_clear()


def test_auto_ignores_date_params(monkeypatch):
    """grain=auto 忽略 year/month/day，返回 200。"""
    cache.cache_clear()
    client, src = client_with_source(monkeypatch)
    r = client.get("/token/@?grain=auto&year=1999&month=13&day=99")
    assert r.status_code == 200
    assert src.daily_calls == 1
    cache.cache_clear()


def test_svg_cache_second_hit_skips_db(monkeypatch):
    """首次请求渲染并写缓存；TTL 内再次请求直接命中缓存，不再调用 source。"""
    cache.cache_clear()
    client, src = client_with_source(monkeypatch)
    r1 = client.get("/token/@?grain=year&year=2026")
    assert r1.status_code == 200
    assert src.daily_calls == 1
    assert cache.cache_size() == 1
    # 第二次同参数请求命中缓存，不再查数据源
    r2 = client.get("/token/@?grain=year&year=2026")
    assert r2.status_code == 200
    assert src.daily_calls == 1
    assert r2.text == r1.text
    cache.cache_clear()

def test_svg_cache_key_differs_by_params(monkeypatch):
    """不同参数（grain/darkmode/日期）应各自独立缓存条目。"""
    cache.cache_clear()
    client, _ = client_with_source(monkeypatch)
    client.get("/token/@?grain=year&year=2026")
    client.get("/token/@?grain=year&year=2026&darkmode=1")
    client.get("/token/@?grain=year&year=2026&darkmode=0")
    client.get("/token/@?grain=month&year=2026&month=9")
    client.get("/token/@?grain=day&year=2026&month=9&day=7")
    client.get("/token/@?grain=year&year=2026&scale=2")
    assert cache.cache_size() == 6
    cache.cache_clear()


def test_theme_reload_invalidates_svg_cache(monkeypatch, tmp_path):
    """Theme reload increments generation and causes new SVG + different ETag (not stale cache)."""
    import json
    import os
    cache.cache_clear()
    client, _ = client_with_source(monkeypatch)
    # Write a custom theme
    custom = {
        "day": {"colors": ["#111111", "#222222", "#333333", "#444444", "#555555"], "text": "#666666", "title": "#777777", "legend": "#888888", "background": "#999999"},
        "night": {"colors": ["#aaaaaa", "#bbbbbb", "#cccccc", "#dddddd", "#eeeeee"], "text": "#ffffff", "title": "#ffffff", "legend": "#ffffff", "background": "#000000"},
    }
    (tmp_path / "test_theme.json").write_text(json.dumps(custom), encoding="utf-8")
    original_themes_dir = os.environ.get("THEMES_DIR", "")
    try:
        monkeypatch.setenv("THEMES_DIR", str(tmp_path))
        from app import theme_loader
        theme_loader.reload()
        # First request with test_theme
        r1 = client.get("/token/@?grain=year&year=2026&theme=test_theme")
        assert r1.status_code == 200
        # Get the SVG content
        svg1 = r1.text
        etag1 = r1.headers.get("etag")
        # Verify it contains our custom color
        assert "#111111" in svg1
        gen_before = theme_loader.theme_generation()
        # Change the theme
        custom["day"]["colors"][0] = "#ff0000"
        (tmp_path / "test_theme.json").write_text(json.dumps(custom), encoding="utf-8")
        theme_loader.reload()
        gen_after = theme_loader.theme_generation()
        assert gen_after > gen_before, "Generation must increase after reload"
        # Same request should return new SVG with new color (not stale from cache)
        r2 = client.get("/token/@?grain=year&year=2026&theme=test_theme")
        assert r2.status_code == 200
        svg2 = r2.text
        etag2 = r2.headers.get("etag")
        # Must be the new SVG, not stale cached
        assert "#ff0000" in svg2, "Theme reload should produce new SVG, not stale cache"
        assert "#111111" not in svg2, "Stale cached SVG should not be returned"
        assert etag2 != etag1, "ETag must change when theme reloads"
    finally:
        monkeypatch.setenv("THEMES_DIR", original_themes_dir)
        cache.cache_clear()
        theme_loader.reload()


def test_dynamic_svg_cache_headers_and_etag(monkeypatch):
    """Dynamic SVG responses must use Cache-Control: public, no-cache and a valid ETag."""
    cache.cache_clear()
    client, _ = client_with_source(monkeypatch)
    r = client.get("/token/@?grain=year&year=2026")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    # Must use no-cache for revalidation-friendly behavior
    assert r.headers["cache-control"] == "public, no-cache", f"Expected 'public, no-cache', got {r.headers.get('cache-control')}"
    # ETag must be present and change when SVG content changes
    etag = r.headers.get("etag")
    assert etag is not None, "ETag header must be present"
    assert etag.startswith(("W/", '"')), f"ETag should be a quoted string, got {etag}"
    # Change theme and verify ETag changes
    cache.cache_clear()
    # Force a different render by using different darkmode
    r2 = client.get("/token/@?grain=year&year=2026&darkmode=1")
    assert r2.status_code == 200
    etag2 = r2.headers.get("etag")
    assert etag2 is not None
    assert etag != etag2, "ETag must change when SVG content changes"
    cache.cache_clear()
