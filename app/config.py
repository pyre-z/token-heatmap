"""应用配置与 SVG 布局常量。"""
from __future__ import annotations

import os
import zoneinfo

TZ = zoneinfo.ZoneInfo("Asia/Shanghai")
# 默认数据源：new-api（默认）或 sub2api；多源并存时部署多实例各指定 SOURCE
SOURCE = os.environ.get("SOURCE", "new-api")
# 服务端 SVG 缓存 TTL（秒），可用环境变量覆盖
CACHE_TTL_SECONDS = float(os.environ.get("CACHE_TTL_SECONDS", "60"))
# 内存 SVG 缓存的最大条目数，避免公开端点的高基数参数耗尽进程内存。
CACHE_MAX_ENTRIES = max(1, int(os.environ.get("CACHE_MAX_ENTRIES", "2000")))
CELL = 11
GAP = 3
PAD_TOP = 30
PAD_LEFT = 34
PAD_RIGHT = 20
PAD_BOTTOM = 26
LEVELS = 5
