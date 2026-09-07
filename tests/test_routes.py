from fastapi.testclient import TestClient
from app import main, cache


def client_with_data(monkeypatch):
    monkeypatch.setattr(main, "fetch_daily_tokens", lambda _: {})
    monkeypatch.setattr(main, "fetch_daily_tokens_in_range", lambda *_: {})
    monkeypatch.setattr(main, "fetch_hourly_tokens", lambda *_: {})
    return TestClient(main.app)


def test_svg_granularities_and_headers(monkeypatch):
    cache.cache_clear()
    client = client_with_data(monkeypatch)
    paths = [
        # grain=year（缺省也是 year）
        "/token/@",
        "/token/@?grain=year&year=2026",
        "/token/@?grain=year",
        # grain=month
        "/token/@?grain=month&year=2026&month=9",
        "/token/@?grain=month&year=2026&month=9&day=7",  # day 被忽略
        "/token/@?grain=month",
        # grain=day
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
    client = client_with_data(monkeypatch)
    for path in (
        "/token/@?grain=week",          # 非法 grain
        "/token/@?grain=year&year=1999",
        "/token/@?grain=month&month=13",
        "/token/@?grain=day&day=0",
        "/token/@?grain=month&year=abc",
        "/token/@?grain=year&theme=nope",
        "/token/@?grain=day&year=2026&month=2&day=30",  # 真实日期校验
        "/token/@?grain=month&year=2026&month=2&day=30",  # month 粒度仍校验日期合法性
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


def test_database_error_is_hidden(monkeypatch):
    cache.cache_clear()
    monkeypatch.setattr(main, "fetch_daily_tokens", lambda _: (_ for _ in ()).throw(RuntimeError("secret")))
    response = TestClient(main.app).get("/token/@?grain=year&year=2026")
    assert response.status_code == 502
    assert response.json()["detail"] == "db error"
    cache.cache_clear()


def test_svg_cache_second_hit_skips_db(monkeypatch):
    """首次请求渲染并写缓存；TTL 内再次请求直接命中缓存，不再调用 fetch。"""
    cache.cache_clear()
    calls = {"n": 0}

    def counting_fetch(year):
        calls["n"] += 1
        return {}

    monkeypatch.setattr(main, "fetch_daily_tokens", counting_fetch)
    client = TestClient(main.app)
    r1 = client.get("/token/@?grain=year&year=2026")
    assert r1.status_code == 200
    assert calls["n"] == 1
    assert cache.cache_size() == 1
    # 第二次同参数请求命中缓存，不查库
    r2 = client.get("/token/@?grain=year&year=2026")
    assert r2.status_code == 200
    assert calls["n"] == 1  # fetch 仍只调了一次
    assert r2.text == r1.text
    cache.cache_clear()


def test_svg_cache_key_differs_by_params(monkeypatch):
    """不同参数（theme/grain/日期）应各自独立缓存条目。"""
    cache.cache_clear()
    monkeypatch.setattr(main, "fetch_daily_tokens", lambda _: {})
    monkeypatch.setattr(main, "fetch_daily_tokens_in_range", lambda *_: {})
    monkeypatch.setattr(main, "fetch_hourly_tokens", lambda *_: {})
    client = TestClient(main.app)
    client.get("/token/@?grain=year&year=2026")
    client.get("/token/@?grain=year&year=2026&theme=github-dark")
    client.get("/token/@?grain=month&year=2026&month=9")
    client.get("/token/@?grain=day&year=2026&month=9&day=7")
    client.get("/token/@?grain=year&year=2026&scale=2")
    assert cache.cache_size() == 5
    cache.cache_clear()
