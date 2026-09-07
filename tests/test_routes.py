from fastapi.testclient import TestClient

from app import main


def test_healthz():
    response = TestClient(main.app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_token_filename_validation_does_not_access_database(monkeypatch):
    client = TestClient(main.app)
    def fail(_: int):
        raise AssertionError("database should not be queried")
    monkeypatch.setattr(main, "fetch_daily_tokens", fail)
    assert client.get("/token/abc.svg").status_code == 404
    assert client.get("/token/1999.svg").status_code == 404
    assert client.get("/token/2101.svg").status_code == 404


def test_token_svg_headers_and_db_error_hiding(monkeypatch):
    client = TestClient(main.app)
    monkeypatch.setattr(main, "fetch_daily_tokens", lambda _: {})
    response = client.get("/token/2026.svg")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.headers["cache-control"] == "public, max-age=600"
    monkeypatch.setattr(main, "fetch_daily_tokens", lambda _: (_ for _ in ()).throw(RuntimeError("postgres://secret")))
    response = client.get("/token/2026.svg")
    assert response.status_code == 502
    assert response.json()["detail"] == "db error"
