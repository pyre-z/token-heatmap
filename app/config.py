"""应用配置与 SVG 布局常量。"""
from __future__ import annotations

import os
import zoneinfo

TZ = zoneinfo.ZoneInfo("Asia/Shanghai")
# 服务端 SVG 缓存 TTL（秒），可用环境变量覆盖
CACHE_TTL_SECONDS = float(os.environ.get("CACHE_TTL_SECONDS", "60"))
CELL = 11
GAP = 3
PAD_TOP = 30
PAD_LEFT = 34
PAD_RIGHT = 20
PAD_BOTTOM = 26
WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]
LEVELS = 5
LEVEL_COLORS = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]
