import datetime as dt

from sqlalchemy.dialects import postgresql

from app.config import TZ
from app import repository


def test_year_epoch_bounds_use_shanghai_calendar():
    assert repository.year_epoch_bounds(2026) == (
        int(dt.datetime(2026, 1, 1, tzinfo=TZ).timestamp()),
        int(dt.datetime(2027, 1, 1, tzinfo=TZ).timestamp()),
    )


def test_month_and_day_epoch_bounds_use_natural_boundaries():
    assert repository.month_epoch_bounds(2026, 12) == (
        int(dt.datetime(2026, 12, 1, tzinfo=TZ).timestamp()),
        int(dt.datetime(2027, 1, 1, tzinfo=TZ).timestamp()),
    )
    assert repository.day_epoch_bounds(2026, 9, 7) == (
        int(dt.datetime(2026, 9, 7, tzinfo=TZ).timestamp()),
        int(dt.datetime(2026, 9, 8, tzinfo=TZ).timestamp()),
    )


def test_repository_uses_epoch_index_window(monkeypatch):
    statements = []

    class Result:
        def all(self):
            return [("2026-01-01", 42)]

    class FakeSession:
        def __init__(self, engine):
            assert engine == "test-engine"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def exec(self, statement):
            statements.append(statement)
            return Result()

    monkeypatch.setattr(repository, "get_engine", lambda: "test-engine")
    monkeypatch.setattr(repository, "Session", FakeSession)

    assert repository.fetch_daily_tokens(2026) == {"2026-01-01": 42}
    sql = str(statements[0].compile(dialect=postgresql.dialect()))
    assert "logs.created_at >=" in sql
    assert "logs.created_at <" in sql
    assert "logs.type =" in sql
    where_sql = sql.split("WHERE", 1)[1].split("GROUP BY", 1)[0]
    assert "to_timestamp(logs.created_at)" not in where_sql


def test_hourly_repository_uses_epoch_window(monkeypatch):
    statements = []

    class Result:
        def all(self):
            return [(0, 42)]

    class FakeSession:
        def __init__(self, engine):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def exec(self, statement):
            statements.append(statement)
            return Result()

    monkeypatch.setattr(repository, "get_engine", lambda: "test-engine")
    monkeypatch.setattr(repository, "Session", FakeSession)
    assert repository.fetch_hourly_tokens(2026, 9, 7) == {0: 42}
    sql = str(statements[0].compile(dialect=postgresql.dialect()))
    where_sql = sql.split("WHERE", 1)[1].split("GROUP BY", 1)[0]
    assert "logs.created_at >=" in where_sql
    assert "logs.created_at <" in where_sql
    assert "to_timestamp(logs.created_at)" not in where_sql
