"""new-api 数据源：直连其 PostgreSQL ``logs`` 表（只读）。

口径：type=2（成功请求）的 prompt_tokens + completion_tokens，
按 Asia/Shanghai 自然日/小时聚合（logs.created_at 为 bigint epoch 秒）。
"""
from __future__ import annotations

import datetime as dt
import os

from sqlalchemy import URL, BigInteger, Column, Engine, Text, func
from sqlmodel import Field, SQLModel, Session, create_engine, select

try:
    from config import TZ
except ModuleNotFoundError:  # pragma: no cover
    from ..config import TZ

try:
    from sources.base import Source, shanghai_date_range
except ModuleNotFoundError:  # pragma: no cover
    from .base import Source, shanghai_date_range

_PG_PREFIX = "PG"  # new-api 用 PG* 系列环境变量


class Log(SQLModel, table=True):
    """new-api 已有的日志表映射；服务只执行 SELECT，不管理表结构。"""

    __tablename__ = "logs"

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    type: int | None = Field(default=None, sa_column=Column(BigInteger))
    created_at: int | None = Field(default=None, sa_column=Column(BigInteger))
    prompt_tokens: int | None = Field(default=None, sa_column=Column(BigInteger))
    completion_tokens: int | None = Field(default=None, sa_column=Column(BigInteger))
    model_name: str | None = Field(default=None, sa_column=Column(Text))


_engine: Engine | None = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = URL.create(
            "postgresql+psycopg2",
            username=os.environ["PGUSER"],
            password=os.environ["PGPASSWORD"],
            host=os.environ["PGHOST"],
            port=int(os.environ.get("PGPORT", "5432")),
            database=os.environ["PGDATABASE"],
        )
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=2,
            connect_args={"connect_timeout": 5},
        )
    return _engine


class NewApiSource(Source):
    """new-api ``logs`` 表数据源。"""

    name = "new-api"

    def daily_tokens_in_range(self, start: dt.date, end: dt.date) -> dict[str, int]:
        start_epoch, end_epoch = shanghai_date_range(start, end)
        day = func.to_char(
            func.timezone("Asia/Shanghai", func.to_timestamp(Log.created_at)),
            "YYYY-MM-DD",
        ).label("day")
        total = func.sum(Log.prompt_tokens + Log.completion_tokens).label("total")
        statement = (
            select(day, total)
            .where(
                Log.type == 2,
                Log.created_at >= start_epoch,
                Log.created_at < end_epoch,
            )
            .group_by(day)
        )
        with Session(_get_engine()) as session:
            return {day: int(total) for day, total in session.exec(statement).all()}

    def hourly_tokens(self, day: dt.date) -> dict[int, int]:
        start_epoch, end_epoch = shanghai_date_range(day, day + dt.timedelta(days=1))
        hour = func.extract(
            "hour", func.timezone("Asia/Shanghai", func.to_timestamp(Log.created_at))
        ).label("hour")
        total = func.sum(Log.prompt_tokens + Log.completion_tokens).label("total")
        statement = (
            select(hour, total)
            .where(Log.type == 2, Log.created_at >= start_epoch, Log.created_at < end_epoch)
            .group_by(hour)
        )
        with Session(_get_engine()) as session:
            return {int(hour): int(total) for hour, total in session.exec(statement).all()}
