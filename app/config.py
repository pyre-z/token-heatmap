"""应用配置与 SVG 布局常量。"""
from __future__ import annotations

import math
import os
import zoneinfo


def _parse_cache_ttl(raw: str) -> float:
    """Parse and validate CACHE_TTL_SECONDS: must be a finite positive float."""
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"CACHE_TTL_SECONDS must be a number; got {raw!r}") from None
    if not (value > 0 and math.isfinite(value)):
        raise ValueError(f"CACHE_TTL_SECONDS must be a finite positive number; got {raw!r}")
    return value


def _parse_cache_max_entries(raw: str) -> int:
    """Parse and validate CACHE_MAX_ENTRIES: must be a positive integer."""
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"CACHE_MAX_ENTRIES must be an integer; got {raw!r}") from None
    if value <= 0:
        raise ValueError(f"CACHE_MAX_ENTRIES must be a positive integer; got {raw!r}")
    return value


def _parse_max_render_concurrency(raw: str) -> int:
    """Parse and validate MAX_RENDER_CONCURRENCY: must be a positive integer."""
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"MAX_RENDER_CONCURRENCY must be an integer; got {raw!r}") from None
    if value <= 0:
        raise ValueError(f"MAX_RENDER_CONCURRENCY must be a positive integer; got {raw!r}")
    return value


def _parse_db_statement_timeout(raw: str) -> int:
    """Parse and validate DB_STATEMENT_TIMEOUT_MS: must be a positive integer (ms)."""
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"DB_STATEMENT_TIMEOUT_MS must be an integer; got {raw!r}") from None
    if value <= 0:
        raise ValueError(f"DB_STATEMENT_TIMEOUT_MS must be a positive integer; got {raw!r}")
    return value

TZ = zoneinfo.ZoneInfo("Asia/Shanghai")
# 默认数据源：new-api（默认）或 sub2api；多源并存时部署多实例各指定 SOURCE
SOURCE = os.environ.get("SOURCE", "new-api")
# 服务端 SVG 缓存 TTL（秒），可用环境变量覆盖
CACHE_TTL_SECONDS = _parse_cache_ttl(os.environ.get("CACHE_TTL_SECONDS", "60"))
# 内存 SVG 缓存的最大条目数，避免公开端点的高基数参数耗尽进程内存。
CACHE_MAX_ENTRIES = max(1, _parse_cache_max_entries(os.environ.get("CACHE_MAX_ENTRIES", "2000")))
# 每个进程同时执行的 SVG/数据库渲染上限；反向代理限流仍是部署层保护。
MAX_RENDER_CONCURRENCY = _parse_max_render_concurrency(os.environ.get("MAX_RENDER_CONCURRENCY", "4"))
# PostgreSQL statement timeout in milliseconds；控制查询最大执行时间。
DB_STATEMENT_TIMEOUT_MS = _parse_db_statement_timeout(os.environ.get("DB_STATEMENT_TIMEOUT_MS", "5000"))

CELL = 11
GAP = 3
PAD_TOP = 30
PAD_LEFT = 34
PAD_RIGHT = 20
PAD_BOTTOM = 26
LEVELS = 5
