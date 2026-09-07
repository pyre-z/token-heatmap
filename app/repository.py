"""new-api ``logs`` 表的只读查询。"""
from __future__ import annotations

import datetime as dt
import os

from sqlalchemy import URL, BigInteger, Column, Engine, Text, func
from sqlmodel import Field, SQLModel, Session, create_engine, select

try:  # 容器从 /app 以 ``main:app`` 启动，测试则导入 ``app.*``。
    from config import TZ
except ModuleNotFoundError:  # pragma: no cover - 由导入上下文决定
    from .config import TZ


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


def get_engine() -> Engine:
    """惰性创建共享连接池，避免导入应用时立即访问数据库。"""
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


def year_epoch_bounds(year: int) -> tuple[int, int]:
    """返回 Asia/Shanghai 自然年的 epoch 秒半开区间。"""
    start = dt.datetime(year, 1, 1, tzinfo=TZ)
    end = dt.datetime(year + 1, 1, 1, tzinfo=TZ)
    return int(start.timestamp()), int(end.timestamp())


def fetch_daily_tokens(year: int) -> dict[str, int]:
    """返回成功请求按 Asia/Shanghai 自然日聚合的 token 总数。"""
    start, end = year_epoch_bounds(year)
    day = func.to_char(
        func.timezone("Asia/Shanghai", func.to_timestamp(Log.created_at)),
        "YYYY-MM-DD",
    ).label("day")
    total = func.sum(Log.prompt_tokens + Log.completion_tokens).label("total")
    statement = (
        select(day, total)
        .where(
            Log.type == 2,
            Log.created_at >= start,
            Log.created_at < end,
        )
        .group_by(day)
    )
    with Session(get_engine()) as session:
        return {day: int(total) for day, total in session.exec(statement).all()}
