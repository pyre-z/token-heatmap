"""Token 分档与 SVG 热力图渲染。"""
from __future__ import annotations

import bisect
import calendar
import datetime as dt

try:
    from config import CELL, GAP, LEVELS, PAD_BOTTOM, PAD_LEFT, PAD_RIGHT, PAD_TOP, TZ
except ModuleNotFoundError:  # pragma: no cover
    from .config import CELL, GAP, LEVELS, PAD_BOTTOM, PAD_LEFT, PAD_RIGHT, PAD_TOP, TZ

THEMES = {
    "github": {"background": "#ffffff", "colors": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"], "text": "#767676", "title": "#24292f", "legend": "#767676"},
    "github-dark": {"background": "#0d1117", "colors": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"], "text": "#8b949e", "title": "#c9d1d9", "legend": "#7d8590"},
}
LEVEL_COLORS = THEMES["github"]["colors"]
LANG = {"zh": {"months": [f"{i}月" for i in range(1, 13)], "weekdays": list("一二三四五六日"), "less": "少", "more": "更多"}, "en": {"months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], "weekdays": ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"], "less": "Less", "more": "More"}}

def compute_levels(daily: dict[str, int]) -> dict[str, int]:
    """按排名把非零值映射至五个颜色档位。"""
    nonzero = sorted(v for v in daily.values() if v > 0)
    if not nonzero:
        return {k: 0 for k in daily}
    return {k: 0 if v <= 0 else min((bisect.bisect_left(nonzero, v) * (LEVELS - 1)) // len(nonzero), LEVELS - 2) + 1 for k, v in daily.items()}

def shanghai_today() -> dt.date:
    """返回与聚合口径一致的上海当天日期。"""
    return dt.datetime.now(TZ).date()

def _options(theme: str, lang: str):
    return THEMES.get(theme, THEMES["github"]), LANG.get(lang, LANG["zh"])

def _svg(width: int, height: int, theme: dict, body: str, scale: float = 1.0) -> str:
    """scale > 1 放大、< 1 缩小：渲染尺寸乘 scale，viewBox 保持原值（矢量等比缩放，文字/格子一起变）。"""
    w, h = width * scale, height * scale
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}" height="{h:g}" viewBox="0 0 {width} {height}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif"><rect width="100%" height="100%" fill="{theme["background"]}"/>{body}</svg>'

def build_svg(year: int, daily: dict[str, int], theme: str = "github", lang: str = "zh", scale: float = 1.0) -> str:
    """生成年度热力图。"""
    t, l = _options(theme, lang); colors = t["colors"]; jan1 = dt.date(year, 1, 1); offset = jan1.weekday(); days = 366 if calendar.isleap(year) else 365
    cols = (offset + days + 6) // 7; width = PAD_LEFT + cols * (CELL + GAP) - GAP + PAD_RIGHT; height = PAD_TOP + 7 * (CELL + GAP) - GAP + PAD_BOTTOM; levels = compute_levels(daily); today = shanghai_today(); cells = []
    for index in range(days):
        current = jan1 + dt.timedelta(days=index); col, row = divmod(index + offset, 7); key = current.isoformat(); value = daily.get(key, 0); fill = colors[levels.get(key, 0)] if value > 0 and current <= today else colors[0]
        cells.append(f'<rect x="{PAD_LEFT + col*(CELL+GAP)}" y="{PAD_TOP + row*(CELL+GAP)}" width="{CELL}" height="{CELL}" rx="2" fill="{fill}"><title>{key}: {value:,} tokens</title></rect>')
    months = ''.join(f'<text x="{PAD_LEFT + (((dt.date(year,m,1)-jan1).days+offset)//7)*(CELL+GAP)}" y="18" font-size="10" fill="{t["text"]}">{l["months"][m-1]}</text>' for m in range(1, 13))
    weekdays = ''.join(f'<text x="14" y="{PAD_TOP+r*(CELL+GAP)+CELL//2+3}" font-size="9" fill="{t["text"]}" text-anchor="middle">{l["weekdays"][r]}</text>' for r in range(7))
    ly = height - 16; lx = width - PAD_RIGHT - LEVELS * 14 - 60; legend = ''.join(f'<rect x="{lx+i*14}" y="{ly-8}" width="10" height="10" rx="2" fill="{color}"/>' for i, color in enumerate(colors))
    return _svg(width, height, t, f'{months}{weekdays}{"".join(cells)}<text x="{lx-8}" y="{ly}" font-size="9" fill="{t["legend"]}" text-anchor="end">{l["less"]}</text>{legend}<text x="{lx+LEVELS*14+6}" y="{ly}" font-size="9" fill="{t["legend"]}">{l["more"]}</text><text x="{PAD_LEFT}" y="{height-2}" font-size="10" fill="{t["title"]}">{year}</text>', scale)

def build_month_svg(year: int, month: int, daily: dict[str, int], theme: str = "github", lang: str = "zh", scale: float = 1.0) -> str:
    """生成按周排列的月度热力图（横向 7 列 = 周一~周日，纵向按周堆叠）。"""
    t, l = _options(theme, lang); colors = t["colors"]; first = dt.date(year, month, 1); count = calendar.monthrange(year, month)[1]
    rows = (first.weekday() + count + 6) // 7  # 当月占几周
    gy = 38; legend_h = 26
    width = PAD_LEFT + 7 * (CELL + GAP) - GAP + PAD_RIGHT
    height = gy + rows * (CELL + GAP) - GAP + legend_h
    levels = compute_levels(daily); today = shanghai_today(); cells = []
    for number in range(1, count + 1):
        current = dt.date(year, month, number)
        row, col = divmod(first.weekday() + number - 1, 7)  # row=第几周, col=星期几(0=周一)
        key = current.isoformat(); value = daily.get(key, 0)
        fill = colors[levels.get(key, 0)] if value > 0 and current <= today else colors[0]
        cells.append(f'<rect x="{PAD_LEFT + col * (CELL + GAP)}" y="{gy + row * (CELL + GAP)}" width="{CELL}" height="{CELL}" rx="2" fill="{fill}"><title>{key}: {value:,} tokens</title></rect>')
    labels = ''.join(f'<text x="{PAD_LEFT + c * (CELL + GAP) + CELL // 2}" y="32" font-size="9" fill="{t["text"]}" text-anchor="middle">{l["weekdays"][c]}</text>' for c in range(7))
    # 图例右对齐：右缘 = 画布右缘 - PAD_RIGHT，More 文字锚定右缘，色块在其左，Less 在色块左
    ly = height - 8
    more_text = l["more"]; less_text = l["less"]
    right_edge = width - PAD_RIGHT
    more_x = right_edge  # More 文字右端
    # 色块右端 = more_x - more文字估算宽 - 间距(4)
    more_w = len(more_text) * 6.0 + 4  # 9px 字体：拉丁 ~5.5px/字符，CJK ~9px/字符，粗估偏宽
    legend_right = more_x - more_w  # 色块区右端
    legend_left = legend_right - LEVELS * 14  # 色块区左端
    legend = ''.join(f'<rect x="{legend_left + i * 14}" y="{ly - 8}" width="10" height="10" rx="2" fill="{color}"/>' for i, color in enumerate(colors))
    less_x = legend_left - 6  # Less 文字右端（锚 end）
    title = f'{year}年{month}月' if lang == 'zh' else f'{l["months"][month - 1]} {year}'
    return _svg(width, height, t, f'<text x="{PAD_LEFT}" y="20" font-size="12" fill="{t["title"]}">{title}</text>{labels}{"".join(cells)}<text x="{less_x}" y="{ly}" font-size="9" fill="{t["legend"]}" text-anchor="end">{less_text}</text>{legend}<text x="{more_x}" y="{ly}" font-size="9" fill="{t["legend"]}" text-anchor="end">{more_text}</text>', scale)

def build_day_svg(year: int, month: int, day: int, hourly: dict[int, int], theme: str = "github", lang: str = "zh", scale: float = 1.0) -> str:
    """生成指定日期的 24 小时柱状图。"""
    t, _ = _options(theme, lang)
    width, height = 530, 190
    left, right, top, bottom = 48, 18, 34, 38  # left 加宽以容纳 Y 轴刻度
    chart_width, chart_height = width - left - right, height - top - bottom
    maximum = max(hourly.values(), default=0)
    # Y 轴刻度：以 M（百万）为单位，取 nice 上限等分
    max_m = maximum / 1_000_000
    if max_m <= 0:
        y_max, nice_step, n_ticks = 1, 1, 0  # 全 0：只画 X 轴，无网格/刻度
    else:
        # nice step：1/2/5 × 10^k，期望 5 档左右刻度
        import math
        raw_step = max_m / 6  # 期望 6 档间隔（含 0 共 7 个刻度）
        pow10 = 10 ** math.floor(math.log10(raw_step)) if raw_step > 0 else 1
        nice_step = min(n for n in (1 * pow10, 2 * pow10, 5 * pow10, 10 * pow10) if n >= raw_step)
        y_max = math.ceil(max_m / nice_step) * nice_step
        n_ticks = int(round(y_max / nice_step))
    bar_width = 12
    slot = chart_width / 24  # 每 1 小时的真实像素宽度（刻度按此等分）
    bars = []
    for hour in range(24):
        value = hourly.get(hour, 0)
        bar_height = value / 1_000_000 / y_max * chart_height if maximum else 0
        # 柱子居中于该小时槽 [hour*slot, (hour+1)*slot]，与底部时刻度对齐不累积偏移
        x = left + hour * slot + (slot - bar_width) / 2
        y = top + chart_height - bar_height
        bars.append(f'<rect class="bar" x="{x:.2f}" y="{y:.2f}" width="{bar_width}" height="{bar_height:.2f}" rx="2" fill="{t["colors"][-1]}"><title>{hour:02d}:00-{hour:02d}:59: {value:,} tokens</title></rect>')
    # Y 轴刻度与网格线（单位 M）
    grid = []
    for i in range(n_ticks + 1):
        val_m = i * nice_step
        gy = top + chart_height - val_m / y_max * chart_height
        if i > 0:  # 0 线用实线（X 轴），其余用淡网格
            grid.append(f'<line x1="{left}" y1="{gy:.2f}" x2="{width - right}" y2="{gy:.2f}" stroke="{t["text"]}" stroke-opacity="0.15" stroke-width="0.5"/>')
        # 刻度文字：4 位有效数字去尾零；加 M 后缀（0 除外）
        label = f"{val_m:.4g}"
        text = label if val_m == 0 else f"{label}M"
        grid.append(f'<text x="{left - 6}" y="{gy + 3:.2f}" font-size="8" fill="{t["text"]}" text-anchor="end">{text}</text>')
    ticks = ''.join(f'<text x="{left + mark / 24 * chart_width:.2f}" y="{height - 14}" font-size="9" fill="{t["text"]}" text-anchor="middle">{mark}</text>' for mark in (0, 6, 12, 18, 24))
    grid = "".join(grid)
    return _svg(width, height, t, f'<text x="{left}" y="20" font-size="12" fill="{t["title"]}">{year:04d}-{month:02d}-{day:02d}</text><line x1="{left}" y1="{top + chart_height}" x2="{width - right}" y2="{top + chart_height}" stroke="{t["text"]}"/>{grid}{"".join(bars)}{ticks}', scale)
