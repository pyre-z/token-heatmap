import datetime as dt

from fastapi.testclient import TestClient

from app import main, cache
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
        assert response.headers["cache-control"] == "public, max-age=600"


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
