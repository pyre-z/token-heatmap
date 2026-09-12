"""统计格式化与今日/本月/今年累计（自 heatmap.py 抽出）。

- fmt_count / fmt_count_zh：英文 K/M/B、中文 万/亿 紧凑单位
- stats_info / stats_text：按自然年口径计算累计并拼装底部统计行
"""
from __future__ import annotations

import datetime as dt


def fmt_count(n: int) -> str:
    """把 token 数格式化为 K/M/B（1B=1000M）紧凑单位。"""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def fmt_count_zh(n: int) -> str:
    """中文单位：≥1 亿用 亿（2 位小数），≥1 万用 万（1 位小数），否则原数。"""
    if n >= 100_000_000:
        return f"{n / 100_000_000:.2f}亿"
    if n >= 10_000:
        return f"{n / 10_000:.1f}万"
    return str(n)


def stats_info(daily: dict[str, int], today: dt.date, year: int) -> tuple[int, int, int]:
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


def stats_text(today_total: int, month_total: int, year_total: int, lang: str) -> str:
    """统计行 HTML：标签粗体。zh 用 亿/万 中文单位，en 用 K/M/B。"""
    if lang == "zh":
        return (f'<tspan font-weight="bold">今日</tspan> {fmt_count_zh(today_total)}　'
                f'<tspan font-weight="bold">本月</tspan> {fmt_count_zh(month_total)}　'
                f'<tspan font-weight="bold">今年</tspan> {fmt_count_zh(year_total)}')
    return (f'<tspan font-weight="bold">Today</tspan> {fmt_count(today_total)}<tspan dx="12" font-weight="bold">Month</tspan> {fmt_count(month_total)}<tspan dx="12" font-weight="bold">Year</tspan> {fmt_count(year_total)}')
