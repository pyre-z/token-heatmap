"""Token 分档与 SVG 热力图渲染。

主题按「族」组织，每族含 day/night 两套配色（github / github-dark 之外的
未来主题同样提供两套）。darkmode 参数决定用哪套或按访问者系统自动切换：

- darkmode=0   -> 直接使用 day 配色（硬编码 fill，兼容性最好）
- darkmode=1   -> 直接使用 night 配色（硬编码 fill）
- darkmode=auto（默认）-> 输出内嵌 <style> 的 CSS 变量版：默认 day，
  访问者系统 prefers-color-scheme: dark 时自动切 night。
"""
from __future__ import annotations

import bisect
import calendar
import datetime as dt

try:
    from config import CELL, GAP, LEVELS, PAD_BOTTOM, PAD_LEFT, PAD_RIGHT, PAD_TOP, TZ
except ModuleNotFoundError:  # pragma: no cover
    from .config import CELL, GAP, LEVELS, PAD_BOTTOM, PAD_LEFT, PAD_RIGHT, PAD_TOP, TZ

# 主题族 -> {day: 配色, night: 配色}。colors[0] 为空数据格底色；background 供 bg=1 时使用。
THEMES = {
    "github": {
        "day": {"colors": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"], "text": "#767676", "title": "#24292f", "legend": "#767676", "background": "#ffffff"},
        "night": {"colors": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"], "text": "#8b949e", "title": "#c9d1d9", "legend": "#7d8590", "background": "#0d1117"},
    },
}
LEVEL_COLORS = THEMES["github"]["day"]["colors"]
LANG = {"zh": {"months": [f"{i}月" for i in range(1, 13)], "weekdays": list("日一二三四五六"), "less": "少", "more": "更多"}, "en": {"months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], "weekdays": ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"], "less": "Less", "more": "More"}}


def compute_levels(daily: dict[str, int]) -> dict[str, int]:
    """按排名把非零值映射至五个颜色档位。"""
    nonzero = sorted(v for v in daily.values() if v > 0)
    if not nonzero:
        return {k: 0 for k in daily}
    return {k: 0 if v <= 0 else min((bisect.bisect_left(nonzero, v) * (LEVELS - 1)) // len(nonzero), LEVELS - 2) + 1 for k, v in daily.items()}


def shanghai_today() -> dt.date:
    """返回与聚合口径一致的上海当天日期。"""
    return dt.datetime.now(TZ).date()


def _family(theme: str) -> dict:
    """按族名取主题族；未知族回退 github。"""
    return THEMES.get(theme, THEMES["github"])


def _mode(darkmode: str) -> str:
    """darkmode 参数 -> 'day' | 'night' | 'auto'（非法值回落 auto）。"""
    if darkmode == "0":
        return "day"
    if darkmode == "1":
        return "night"
    return "auto"


def _palette(family: dict, mode: str) -> dict:
    """返回供 body 直接引用的调色板 dict（colors/text/title/legend/background）。

    - mode=day/night：值为具体 hex（fill 硬编码，兼容性最好）
    - mode=auto：值为 CSS 变量 var(--c0)...（由 <style> 提供默认 day + dark 覆盖 night）
    """
    if mode == "auto":
        return {
            "colors": [f"var(--c{i})" for i in range(5)],
            "text": "var(--tx)",
            "title": "var(--tt)",
            "legend": "var(--lg)",
            "background": "var(--bg)",
        }
    pal = family["day"] if mode == "day" else family["night"]
    return {"colors": list(pal["colors"]), "text": pal["text"], "title": pal["title"], "legend": pal["legend"], "background": pal["background"]}


def _svg(width: int, height: int, family: dict, mode: str, body: str, scale: float = 1.0, bg: bool = False) -> str:
    """组装 SVG。auto 模式注入双套 CSS 变量（默认 day，dark 系统切 night）。

    bg=True 时画全幅背景 rect（用主题 background 色；auto 模式用 var(--bg)，随系统深浅切换），
    bg=False（默认）背景透明不画底。
    """
    w, h = width * scale, height * scale
    style = ""
    rect = ""
    if mode == "auto":
        day, night = family["day"], family["night"]
        d = "".join(f"--c{i}:{day['colors'][i]};" for i in range(5)) + f"--tx:{day['text']};--tt:{day['title']};--lg:{day['legend']};--bg:{day['background']}"
        n = "".join(f"--c{i}:{night['colors'][i]};" for i in range(5)) + f"--tx:{night['text']};--tt:{night['title']};--lg:{night['legend']};--bg:{night['background']}"
        style = f"<style>:root{{{d}}}@media (prefers-color-scheme: dark){{:root{{{n}}}}}</style>"
        if bg:
            rect = '<rect width="100%" height="100%" fill="var(--bg)"/>'
    elif bg:
        pal = family["day"] if mode == "day" else family["night"]
        rect = f'<rect width="100%" height="100%" fill="{pal["background"]}"/>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}" height="{h:g}" viewBox="0 0 {width} {height}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">{style}{rect}{body}</svg>'


def _fmt_count(n: int) -> str:
    """把 token 数格式化为 K/M/B（1B=1000M）紧凑单位。"""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _fmt_count_zh(n: int) -> str:
    """中文单位：≥1 亿用 亿（2 位小数），≥1 万用 万（1 位小数），否则原数。"""
    if n >= 100_000_000:
        return f"{n / 100_000_000:.2f}亿"
    if n >= 10_000:
        return f"{n / 10_000:.1f}万"
    return str(n)


def _stats_info(daily: dict[str, int], today: dt.date, year: int) -> tuple[int, int, int]:
    """从 daily 计算 今日/本月/今年 累计。

    统计口径年为 year：build_svg 传图年份（历史年图显示该年整年累计），
    build_auto_svg 传 today.year（滚动窗口含去年尾部，按前缀过滤只算今年）。
    month/today 仅当 year == today.year 才非 0（历史年图无"今日/本月"语义）。
    返回 (today_total, month_total, year_total)。
    """
    y_prefix = f"{year}-"
    year_total = 0
    if year == today.year:
        today_total = daily.get(today.isoformat(), 0)
        ym_prefix = f"{today.year}-{today.month:02d}-"
        month_total = 0
        today_key = today.isoformat()
        for k, v in daily.items():
            if k > today_key:
                continue
            if k.startswith(ym_prefix):
                month_total += v
            if k.startswith(y_prefix):
                year_total += v
        return today_total, month_total, year_total
    # 历史年份图：整年累计（daily 为该年全年数据）
    for k, v in daily.items():
        if k.startswith(y_prefix):
            year_total += v
    return 0, 0, year_total


def _weekday_labels(lang: str, pal: dict) -> str:
    """GitHub 风格：左侧只标注 周一/周三/周五 三行（周日开头 r=0，Mon/Wed/Fri 在 r=1/3/5）。"""
    if lang == "zh":
        day_labels = {1: "周一", 3: "周三", 5: "周五"}
    else:
        day_labels = {1: "Mon", 3: "Wed", 5: "Fri"}
    return "".join(
        f'<text x="16" y="{PAD_TOP+r*(CELL+GAP)+CELL//2+3}" font-size="9" fill="{pal["text"]}" text-anchor="middle">{label}</text>'
        for r, label in day_labels.items()
    )


def _stats_text(today_total: int, month_total: int, year_total: int, lang: str) -> str:
    """统计行 HTML：标签粗体。zh 用 亿/万 中文单位，en 用 K/M/B。"""
    if lang == "zh":
        return (f'<tspan font-weight="bold">今日</tspan> {_fmt_count_zh(today_total)}　'
                f'<tspan font-weight="bold">本月</tspan> {_fmt_count_zh(month_total)}　'
                f'<tspan font-weight="bold">今年</tspan> {_fmt_count_zh(year_total)}')
    return (f'<tspan font-weight="bold">Today</tspan> {_fmt_count(today_total)}  '
            f'<tspan font-weight="bold">Month</tspan> {_fmt_count(month_total)}  '
            f'<tspan font-weight="bold">Year</tspan> {_fmt_count(year_total)}')


def _legend_html(width: int, ly: int, pal: dict, colors: list, lang_words: dict) -> str:
    """图例 HTML：整组右对齐到画布右缘留 ~12px（GitHub 风格：Less □□□□□ More）。"""
    more_text = lang_words["more"]
    less_text = lang_words["less"]
    right_edge = width - 12
    more_x = right_edge  # More 文字右端
    more_w = len(more_text) * 6.0 + 4  # 9px 字体：拉丁 ~5.5px/字符，CJK ~9px/字符，粗估偏宽
    legend_right = more_x - more_w  # 色块区右端
    legend_left = legend_right - LEVELS * 14  # 色块区左端
    legend = "".join(
        f'<rect x="{legend_left + i * 14}" y="{ly - 8}" width="10" height="10" rx="2" fill="{color}"/>'
        for i, color in enumerate(colors)
    )
    less_x = legend_left - 6  # Less 文字右端（锚 end）
    return (
        f'<text x="{less_x}" y="{ly}" font-size="9" fill="{pal["legend"]}" text-anchor="end">{less_text}</text>'
        f"{legend}"
        f'<text x="{more_x}" y="{ly}" font-size="9" fill="{pal["legend"]}" text-anchor="end">{more_text}</text>'
    )


def build_svg(year: int, daily: dict[str, int], theme: str = "github", lang: str = "zh", scale: float = 1.0, darkmode: str = "auto", bg: bool = False) -> str:
    """生成年度热力图。"""
    family = _family(theme); mode = _mode(darkmode); pal = _palette(family, mode); colors = pal["colors"]
    l = LANG.get(lang, LANG["zh"])
    jan1 = dt.date(year, 1, 1); offset = (jan1.weekday() + 1) % 7; days = 366 if calendar.isleap(year) else 365
    cols = (offset + days + 6) // 7; width = PAD_LEFT + cols * (CELL + GAP) - GAP + PAD_RIGHT; levels = compute_levels(daily); today = shanghai_today(); cells = []
    # 底部统计行高度（今日/本月/今年），图例下方再留一行
    stats_extra = 10
    height = PAD_TOP + 7 * (CELL + GAP) - GAP + PAD_BOTTOM + stats_extra
    for index in range(days):
        current = jan1 + dt.timedelta(days=index); col, row = divmod(index + offset, 7); key = current.isoformat(); value = daily.get(key, 0); fill = colors[levels.get(key, 0)] if value > 0 and current <= today else colors[0]
        cells.append(f'<rect x="{PAD_LEFT + col*(CELL+GAP)}" y="{PAD_TOP + row*(CELL+GAP)}" width="{CELL}" height="{CELL}" rx="2" fill="{fill}"><title>{key}: {value:,} tokens</title></rect>')
    months = ''.join(f'<text x="{PAD_LEFT + (((dt.date(year,m,1)-jan1).days+offset)//7)*(CELL+GAP)}" y="24" font-size="10" fill="{pal["text"]}">{l["months"][m-1]}</text>' for m in range(1, 13))
    weekdays = _weekday_labels(lang, pal)
    # 底部一行（GitHub 风格）：图例与统计同行，距最后一行格子留足 ~16px，底部留白 ~10px
    ly = height - 12  # 图例 baseline
    legend_html = _legend_html(width, ly, pal, colors, l)
    # 底部统计行：今日/本月/今年（截至今天）；年份居左，统计紧跟其后
    today_total, month_total, year_total = _stats_info(daily, today, year)
    stats_text = _stats_text(today_total, month_total, year_total, lang)
    stats_y = height - 12  # 与图例同 baseline（GitHub 底部一行）
    stats_x = PAD_LEFT + 56  # 年份（4 字符 ~28px）右侧留间距，统计左对齐
    return _svg(width, height, family, mode, f'{months}{weekdays}{"".join(cells)}{legend_html}<text x="{PAD_LEFT}" y="{stats_y}" font-size="11" fill="{pal["title"]}">{year}</text><text x="{stats_x}" y="{stats_y}" font-size="11" fill="{pal["text"]}">{stats_text}</text>', scale, bg)


def build_auto_svg(daily: dict[str, int], theme: str = "github", lang: str = "zh", scale: float = 1.0, darkmode: str = "auto", bg: bool = False) -> str:
    """生成滚动年热力图：从今日往前 365 天（GitHub 风格，今日在最后一列）。

    daily 应为 [today-364, today] 区间（含两端）的按日 dict；
    布局以 start 所在周的周日为第一列，today 所在周为最后一列（整周显示），
    无标题；底部统计沿用 今日/本月/今年（自然年口径，_stats_info 前缀过滤天然正确）。
    """
    family = _family(theme); mode = _mode(darkmode); pal = _palette(family, mode); colors = pal["colors"]
    l = LANG.get(lang, LANG["zh"])
    today = shanghai_today()
    start = today - dt.timedelta(days=364)  # 含今天共 365 天
    # 第一列 = start 所在周的周日；最后一列 = today 所在周（到周六整周）
    col_start = start - dt.timedelta(days=(start.weekday() + 1) % 7)
    col_end_sat = today + dt.timedelta(days=(5 - today.weekday()) % 7)
    cols = (col_end_sat - col_start).days // 7 + 1
    width = PAD_LEFT + cols * (CELL + GAP) - GAP + PAD_RIGHT
    stats_extra = 10
    height = PAD_TOP + 7 * (CELL + GAP) - GAP + PAD_BOTTOM + stats_extra
    levels = compute_levels(daily)
    cells = []
    # 逐列逐格：只画 <= today 的日期（GitHub 风格，未来日期不出现格子）
    cursor = col_start
    while cursor <= col_end_sat:
        for row in range(7):
            current = cursor + dt.timedelta(days=row)
            if current > today:
                continue  # 未来不画
            key = current.isoformat()
            value = daily.get(key, 0)
            fill = colors[levels.get(key, 0)] if value > 0 else colors[0]
            x = PAD_LEFT + ((cursor - col_start).days // 7) * (CELL + GAP)
            y = PAD_TOP + row * (CELL + GAP)
            cells.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{fill}"><title>{key}: {value:,} tokens</title></rect>')
        cursor += dt.timedelta(days=7)
    # 月份标签：GitHub 风格——列首(周日)进入新月份时标注该月（首列含 9/7 会正确标 9月）
    month_texts = []
    cursor = col_start
    cidx = 0
    last_label_month = None
    while cursor <= col_end_sat:
        m = cursor.month
        if m != last_label_month:
            x = PAD_LEFT + cidx * (CELL + GAP)
            month_texts.append(f'<text x="{x}" y="24" font-size="10" fill="{pal["text"]}">{l["months"][m-1]}</text>')
            last_label_month = m
        cursor += dt.timedelta(days=7)
        cidx += 1
    weekdays = _weekday_labels(lang, pal)
    # 底部一行（GitHub 风格）：图例与统计同行，距格子 ~16px，底部留白 ~10px
    ly = height - 12  # 图例 baseline
    legend_html = _legend_html(width, ly, pal, colors, l)
    today_total, month_total, year_total = _stats_info(daily, today, today.year)
    stats_text = _stats_text(today_total, month_total, year_total, lang)
    stats_y = height - 12  # 与图例同 baseline（GitHub 底部一行）
    return _svg(width, height, family, mode, f'{"".join(month_texts)}{weekdays}{"".join(cells)}{legend_html}<text x="{PAD_LEFT}" y="{stats_y}" font-size="11" fill="{pal["text"]}">{stats_text}</text>', scale, bg)


def build_month_svg(year: int, month: int, daily: dict[str, int], theme: str = "github", lang: str = "zh", scale: float = 1.0, darkmode: str = "auto", bg: bool = False) -> str:
    """生成按周排列的月度热力图（横向 7 列 = 周日~周六，纵向按周堆叠）。"""
    family = _family(theme); mode = _mode(darkmode); pal = _palette(family, mode); colors = pal["colors"]
    l = LANG.get(lang, LANG["zh"])
    first = dt.date(year, month, 1); count = calendar.monthrange(year, month)[1]
    first_offset = (first.weekday() + 1) % 7  # 周日开头：周日=0
    rows = (first_offset + count + 6) // 7  # 当月占几周
    gy = 38; legend_h = 26
    width = PAD_LEFT + 7 * (CELL + GAP) - GAP + PAD_RIGHT
    height = gy + rows * (CELL + GAP) - GAP + legend_h
    levels = compute_levels(daily); today = shanghai_today(); cells = []
    for number in range(1, count + 1):
        current = dt.date(year, month, number)
        row, col = divmod(first_offset + number - 1, 7)  # row=第几周, col=星期几(0=周日)
        key = current.isoformat(); value = daily.get(key, 0)
        fill = colors[levels.get(key, 0)] if value > 0 and current <= today else colors[0]
        cells.append(f'<rect x="{PAD_LEFT + col * (CELL + GAP)}" y="{gy + row * (CELL + GAP)}" width="{CELL}" height="{CELL}" rx="2" fill="{fill}"><title>{key}: {value:,} tokens</title></rect>')
    labels = ''.join(f'<text x="{PAD_LEFT + c * (CELL + GAP) + CELL // 2}" y="32" font-size="9" fill="{pal["text"]}" text-anchor="middle">{l["weekdays"][c]}</text>' for c in range(7))
    # 图例右对齐：右缘 = 画布右缘 - PAD_RIGHT，More 文字锚定右缘，色块在其左，Less 在色块左
    ly = height - 8
    more_text = l["more"]; less_text = l["less"]
    right_edge = width - PAD_RIGHT
    more_x = right_edge  # More 文字右端
    more_w = len(more_text) * 6.0 + 4  # 9px 字体：拉丁 ~5.5px/字符，CJK ~9px/字符，粗估偏宽
    legend_right = more_x - more_w  # 色块区右端
    legend_left = legend_right - LEVELS * 14  # 色块区左端
    legend = ''.join(f'<rect x="{legend_left + i * 14}" y="{ly - 8}" width="10" height="10" rx="2" fill="{color}"/>' for i, color in enumerate(colors))
    less_x = legend_left - 6  # Less 文字右端（锚 end）
    title = f'{year}年{month}月' if lang == 'zh' else f'{l["months"][month - 1]} {year}'
    return _svg(width, height, family, mode, f'<text x="{PAD_LEFT}" y="20" font-size="12" fill="{pal["title"]}">{title}</text>{labels}{"".join(cells)}<text x="{less_x}" y="{ly}" font-size="9" fill="{pal["legend"]}" text-anchor="end">{less_text}</text>{legend}<text x="{more_x}" y="{ly}" font-size="9" fill="{pal["legend"]}" text-anchor="end">{more_text}</text>', scale, bg)


def build_day_svg(year: int, month: int, day: int, hourly: dict[int, int], theme: str = "github", lang: str = "zh", scale: float = 1.0, darkmode: str = "auto", bg: bool = False) -> str:
    """生成指定日期的 24 小时柱状图。"""
    family = _family(theme); mode = _mode(darkmode); pal = _palette(family, mode); colors = pal["colors"]
    width, height = 530, 190
    left, right, top, bottom = 48, 18, 34, 38  # left 加宽以容纳 Y 轴刻度
    chart_width, chart_height = width - left - right, height - top - bottom
    maximum = max(hourly.values(), default=0)
    # Y 轴刻度：以 M（百万）为单位，取 nice 上限等分
    max_m = maximum / 1_000_000
    if max_m <= 0:
        y_max, nice_step, n_ticks = 1, 1, 0  # 全 0：只画 X 轴，无网格/刻度
    else:
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
        bars.append(f'<rect class="bar" x="{x:.2f}" y="{y:.2f}" width="{bar_width}" height="{bar_height:.2f}" rx="2" fill="{colors[-1]}"><title>{hour:02d}:00-{hour:02d}:59: {value:,} tokens</title></rect>')
    # Y 轴刻度与网格线（单位 M）
    grid = []
    for i in range(n_ticks + 1):
        val_m = i * nice_step
        gy = top + chart_height - val_m / y_max * chart_height
        if i > 0:  # 0 线用实线（X 轴），其余用淡网格
            grid.append(f'<line x1="{left}" y1="{gy:.2f}" x2="{width - right}" y2="{gy:.2f}" stroke="{pal["text"]}" stroke-opacity="0.15" stroke-width="0.5"/>')
        label = f"{val_m:.4g}"
        text = label if val_m == 0 else f"{label}M"
        grid.append(f'<text x="{left - 6}" y="{gy + 3:.2f}" font-size="8" fill="{pal["text"]}" text-anchor="end">{text}</text>')
    ticks = ''.join(f'<text x="{left + mark / 24 * chart_width:.2f}" y="{height - 14}" font-size="9" fill="{pal["text"]}" text-anchor="middle">{mark}</text>' for mark in (0, 6, 12, 18, 24))
    grid = "".join(grid)
    return _svg(width, height, family, mode, f'<text x="{left}" y="20" font-size="12" fill="{pal["title"]}">{year:04d}-{month:02d}-{day:02d}</text><line x1="{left}" y1="{top + chart_height}" x2="{width - right}" y2="{top + chart_height}" stroke="{pal["text"]}"/>{grid}{"".join(bars)}{ticks}', scale, bg)
