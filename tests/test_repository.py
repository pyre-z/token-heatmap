import datetime as dt

from sqlalchemy.dialects import postgresql

from app.sources.base import shanghai_date_range
from app.config import TZ
from app.sources import newapi
from app.sources import sub2api_db


def test_shanghai_date_range_uses_calendar_bounds():
    start, end = shanghai_date_range(dt.date(2026, 1, 1), dt.date(2027, 1, 1))
    assert start == int(dt.datetime(2026, 1, 1, tzinfo=TZ).timestamp())
    assert end == int(dt.datetime(2027, 1, 1, tzinfo=TZ).timestamp())
    # 月界
    start, end = shanghai_date_range(dt.date(2026, 12, 1), dt.date(2027, 1, 1))
    assert start == int(dt.datetime(2026, 12, 1, tzinfo=TZ).timestamp())
    assert end == int(dt.datetime(2027, 1, 1, tzinfo=TZ).timestamp())
    # 日界
    start, end = shanghai_date_range(dt.date(2026, 9, 7), dt.date(2026, 9, 8))
    assert start == int(dt.datetime(2026, 9, 7, tzinfo=TZ).timestamp())
    assert end == int(dt.datetime(2026, 9, 8, tzinfo=TZ).timestamp())


def _compile_newapi_sql(monkeypatch, method, *args):
    statements = []
    rows = [(0, 42)] if method == "hourly_tokens" else [("2026-01-01", 42)]

    class Result:
        def all(self):
            return rows

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

    monkeypatch.setattr(newapi, "_get_engine", lambda: "test-engine")
    monkeypatch.setattr(newapi, "Session", FakeSession)
    source = newapi.NewApiSource()
    out = getattr(source, method)(*args)
    return str(statements[0].compile(dialect=postgresql.dialect()))


def test_newapi_daily_uses_epoch_index_window_and_type_filter(monkeypatch):
    sql = _compile_newapi_sql(
        monkeypatch, "daily_tokens_in_range", dt.date(2026, 1, 1), dt.date(2027, 1, 1)
    )
    where_sql = sql.split("WHERE", 1)[1].split("GROUP BY", 1)[0]
    assert "logs.created_at >=" in where_sql
    assert "logs.created_at <" in where_sql
    assert "logs.type =" in where_sql
    assert "to_timestamp(logs.created_at)" not in where_sql
    assert "coalesce(logs.prompt_tokens, %(coalesce_1)s)" in sql
    assert "coalesce(logs.completion_tokens, %(coalesce_2)s)" in sql


def test_newapi_daily_returns_day_string_keyed_dict(monkeypatch):
    statements = []

    class Result:
        def all(self):
            return [("2026-01-01", 42)]

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

    monkeypatch.setattr(newapi, "_get_engine", lambda: "test-engine")
    monkeypatch.setattr(newapi, "Session", FakeSession)
    out = newapi.NewApiSource().daily_tokens_in_range(dt.date(2026, 1, 1), dt.date(2027, 1, 1))
    assert out == {"2026-01-01": 42}


def test_newapi_hourly_uses_epoch_window(monkeypatch):
    sql = _compile_newapi_sql(monkeypatch, "hourly_tokens", dt.date(2026, 9, 7))
    where_sql = sql.split("WHERE", 1)[1].split("GROUP BY", 1)[0]
    assert "logs.created_at >=" in where_sql
    assert "logs.created_at <" in where_sql
    assert "to_timestamp(logs.created_at)" not in where_sql


def test_sub2api_missing_env_returns_empty():
    import os

    saved = {k: os.environ.pop(k, None) for k in sub2api_db._PG_ENV.values()}
    try:
        source = sub2api_db.Sub2ApiSource()
        assert source.daily_tokens_in_range(dt.date(2026, 1, 1), dt.date(2027, 1, 1)) == {}
        assert source.hourly_tokens(dt.date(2026, 9, 7)) == {}
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_sub2api_sql_uses_cache_tokens_and_tz(monkeypatch):
    statements = []

    class Result:
        def all(self):
            return [("2026-01-01", 100)]

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

    monkeypatch.setattr(sub2api_db, "_get_engine", lambda: "test-engine")
    monkeypatch.setattr(sub2api_db, "Session", FakeSession)
    monkeypatch.setattr(sub2api_db, "_env_missing", lambda: False)
    source = sub2api_db.Sub2ApiSource()
    out = source.daily_tokens_in_range(dt.date(2026, 1, 1), dt.date(2027, 1, 1))
    assert out == {"2026-01-01": 100}
    sql = str(statements[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "usage_logs.created_at >=" in sql
    assert "usage_logs.created_at <" in sql
    assert "coalesce(usage_logs.input_tokens, 0)" in sql
    assert "coalesce(usage_logs.output_tokens, 0)" in sql
    assert "coalesce(usage_logs.cache_creation_tokens, 0)" in sql
    assert "coalesce(usage_logs.cache_read_tokens, 0)" in sql
    # 无 type 过滤（usage_logs 无成功标记语义）
    assert "usage_logs.type" not in sql
