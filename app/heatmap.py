"""Rank-based token levels and SVG calendar rendering."""
from __future__ import annotations

import bisect
import calendar
import datetime as dt

try:  # ``main:app`` from /app in the container, or ``app.*`` in tests.
    from config import CELL, GAP, LEVELS, LEVEL_COLORS, PAD_BOTTOM, PAD_LEFT, PAD_RIGHT, PAD_TOP, TZ, WEEKDAYS
except ModuleNotFoundError:  # pragma: no cover - selected by import context
    from .config import CELL, GAP, LEVELS, LEVEL_COLORS, PAD_BOTTOM, PAD_LEFT, PAD_RIGHT, PAD_TOP, TZ, WEEKDAYS


def compute_levels(daily: dict[str, int]) -> dict[str, int]:
    """Map each day to 0..4 with rank buckets; equal values share a level."""
    nonzero = sorted(value for value in daily.values() if value > 0)
    count = len(nonzero)
    if count == 0:
        return {key: 0 for key in daily}
    levels: dict[str, int] = {}
    for key, value in daily.items():
        if value <= 0:
            levels[key] = 0
            continue
        # A left rank deliberately puts tied values in the same deployed bucket.
        rank = bisect.bisect_left(nonzero, value)
        levels[key] = min((rank * (LEVELS - 1)) // count, LEVELS - 2) + 1
    return levels


def shanghai_today() -> dt.date:
    """Today's date for the same timezone used by aggregation."""
    return dt.datetime.now(TZ).date()


def build_svg(year: int, daily: dict[str, int]) -> str:
    """Build the unchanged GitHub-style annual heatmap SVG."""
    jan1 = dt.date(year, 1, 1)
    first_col = jan1.weekday()
    n_days = 366 if calendar.isleap(year) else 365
    n_cols = (first_col + n_days + 6) // 7
    width = PAD_LEFT + n_cols * (CELL + GAP) - GAP + PAD_RIGHT
    height = PAD_TOP + 7 * (CELL + GAP) - GAP + PAD_BOTTOM
    levels = compute_levels(daily)
    month_cols = []
    for month in range(1, 13):
        day = dt.date(year, month, 1)
        month_cols.append(((day.toordinal() - jan1.toordinal() + first_col) // 7, month))
    rects: list[str] = []
    day0, today = jan1.toordinal(), shanghai_today()
    for index in range(n_days):
        day = dt.date.fromordinal(day0 + index)
        col, row = (index + first_col) // 7, (index + first_col) % 7
        x, y = PAD_LEFT + col * (CELL + GAP), PAD_TOP + row * (CELL + GAP)
        key, value = day.isoformat(), daily.get(day.isoformat(), 0)
        fill = LEVEL_COLORS[levels.get(key, 0)] if value > 0 and day <= today else "#ebedf0"
        rects.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{fill}"><title>{key}: {value:,} tokens</title></rect>')
    month_labels = [f'<text x="{PAD_LEFT + col * (CELL + GAP)}" y="18" font-size="10" fill="#767676">{month}月</text>' for col, month in month_cols]
    weekday_labels = [f'<text x="14" y="{PAD_TOP + row * (CELL + GAP) + CELL // 2 + 3}" font-size="9" fill="#767676" text-anchor="middle">{WEEKDAYS[row]}</text>' for row in range(7)]
    legend_y = height - 16
    legend_x0 = width - PAD_RIGHT - (LEVELS * (10 + 4)) - 60
    legend_rects = [f'<rect x="{legend_x0 + index * 14}" y="{legend_y - 8}" width="10" height="10" rx="2" fill="{LEVEL_COLORS[index]}"/>' for index in range(LEVELS)]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif">
  <rect width="100%" height="100%" fill="white"/>
  {''.join(month_labels)}
  {''.join(weekday_labels)}
  {''.join(rects)}
  <text x="{legend_x0 - 8}" y="{legend_y}" font-size="9" fill="#767676" text-anchor="end">少</text>
  {''.join(legend_rects)}
  <text x="{legend_x0 + LEVELS * 14 + 6}" y="{legend_y}" font-size="9" fill="#767676" text-anchor="start">更多</text>
</svg>'''
