"""数据源抽象接口。

每种 AI API Gateway 实现一个 Source 子类，提供统一的按日期聚合查询。
渲染层（heatmap.py / main.py）只依赖本接口，不感知具体网关的表结构差异。

实现约定：
- daily_tokens_in_range 返回 {YYYY-MM-DD: int}，半开区间 [start, end)，按 Asia/Shanghai 自然日聚合
- hourly_tokens 返回 {0-23: int}，某 Asia/Shanghai 自然日按小时聚合
- token 口径由各源自行决定并在 docstring 注明（如 new-api 仅成功请求、sub2api 含 cache tokens）
"""
from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod

try:
    from config import TZ
except ModuleNotFoundError:  # pragma: no cover
    from ..config import TZ


def shanghai_date_range(start: dt.date, end: dt.date) -> tuple[int, int]:
    """把 [start, end) 的 date 区间转成 Asia/Shanghai epoch 秒半开区间（供 epoch 存储的源使用）。"""
    s = dt.datetime(start.year, start.month, start.day, tzinfo=TZ)
    e = dt.datetime(end.year, end.month, end.day, tzinfo=TZ)
    return int(s.timestamp()), int(e.timestamp())


class Source(ABC):
    """AI API Gateway 用量数据源。"""

    #: 数据源标识，与配置 SOURCE 取值对应（如 new-api / sub2api）
    name: str = "base"

    @abstractmethod
    def daily_tokens_in_range(self, start: dt.date, end: dt.date) -> dict[str, int]:
        """返回 [start, end) 每日 token 总量；key 为 YYYY-MM-DD 字符串。"""

    @abstractmethod
    def hourly_tokens(self, day: dt.date) -> dict[int, int]:
        """返回 day 当天 0-23 点各小时 token 总量。"""
