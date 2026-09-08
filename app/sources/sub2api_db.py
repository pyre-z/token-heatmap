"""sub2api 数据源：直连其 PostgreSQL ``usage_logs`` 表（只读）。

口径：usage_logs 只记录有 token 用量回报的调用（成功/部分失败），无需过滤状态；
token = input_tokens + output_tokens + cache_creation_tokens + cache_read_tokens（同官方口径）；
created_at 为 timestamptz，按 Asia/Shanghai 自然日/小时聚合。

连接使用独立环境变量（SUB2API_PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD），
避免与 new-api 的 PG* 混用。未配置这些变量时视为"源不可用"，返回空数据（不抛错）。
"""
from __future__ import annotations

import datetime as dt
import os

from sqlalchemy import URL, BigInteger, Column, Engine, Integer, DateTime, func
from sqlmodel import Field, SQLModel, Session, create_engine, select

try:
    from config import TZ
except ModuleNotFoundError:  # pragma: no cover
    from ..config import TZ

try:
    from sources.base import Source
except ModuleNotFoundError:  # pragma: no cover
    from .base import Source

_PG_ENV = {
    "host": "SUB2API_PGHOST",
    "port": "SUB2API_PGPORT",
    "db": "SUB2API_PGDATABASE",
    "user": "SUB2API_PGUSER",
    "password": "SUB2API_PGPASSWORD",
}


class UsageLog(SQLModel, table=True):
    """sub2api 的 usage_logs 表映射（只读所需字段子集）。"""

    __tablename__ = "usage_logs"

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    created_at: dt.datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    input_tokens: int | None = Field(default=None, sa_column=Column(Integer))
    output_tokens: int | None = Field(default=None, sa_column=Column(Integer))
    cache_creation_tokens: int | None = Field(default=None, sa_column=Column(Integer))
    cache_read_tokens: int | None = Field(default=None, sa_column=Column(Integer))


_engine: Engine | None = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = URL.create(
            "postgresql+psycopg2",
            username=os.environ[_PG_ENV["user"]],
            password=os.environ[_PG_ENV["password"]],
            host=os.environ[_PG_ENV["host"]],
            port=int(os.environ.get(_PG_ENV["port"], "5432")),
            database=os.environ[_PG_ENV["db"]],
        )
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=2,
            connect_args={"connect_timeout": 5},
        )
    return _engine


def _env_missing() -> bool:
    return not all(os.environ.get(v) for v in _PG_ENV.values())


def _tz_range(start: dt.date, end: dt.date) -> tuple[dt.datetime, dt.datetime]:
    """date 半开区间 -> Asia/Shanghai aware datetime。"""
    return (
        dt.datetime(start.year, start.month, start.day, tzinfo=TZ),
        dt.datetime(end.year, end.month, end.day, tzinfo=TZ),
    )


def _total_expr():
    return func.sum(
        func.coalesce(UsageLog.input_tokens, 0)
        + func.coalesce(UsageLog.output_tokens, 0)
        + func.coalesce(UsageLog.cache_creation_tokens, 0)
        + func.coalesce(UsageLog.cache_read_tokens, 0)
    ).label("total")


class Sub2ApiSource(Source):
    """sub2api ``usage_logs`` 表数据源（含缓存 token 口径）。"""

    name = "sub2api"

    def daily_tokens_in_range(self, start: dt.date, end: dt.date) -> dict[str, int]:
        if _env_missing():
            return {}
        day = func.to_char(
            func.timezone("Asia/Shanghai", UsageLog.created_at),
            "YYYY-MM-DD",
        ).label("day")
        statement = (
            select(day, _total_expr())
            .where(UsageLog.created_at >= _tz_range(start, end)[0], UsageLog.created_at < _tz_range(start, end)[1])
            .group_by(day)
        )
        with Session(_get_engine()) as session:
            return {day: int(total) for day, total in session.exec(statement).all()}

    def hourly_tokens(self, day: dt.date) -> dict[int, int]:
        if _env_missing():
            return {}
        start_dt, end_dt = _tz_range(day, day + dt.timedelta(days=1))
        hour = func.extract(
            "hour", func.timezone("Asia/Shanghai", UsageLog.created_at)
        ).label("hour")
        statement = (
            select(hour, _total_expr())
            .where(UsageLog.created_at >= start_dt, UsageLog.created_at < end_dt)
            .group_by(hour)
        )
        with Session(_get_engine()) as session:
            return {int(hour): int(total) for hour, total in session.exec(statement).all()}
