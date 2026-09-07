import datetime as dt
import re

from app import heatmap


def test_compute_levels_empty_and_zeroes():
    assert heatmap.compute_levels({}) == {}
    assert heatmap.compute_levels({"2026-01-01": 0, "2026-01-02": -1}) == {
        "2026-01-01": 0,
        "2026-01-02": 0,
    }


def test_compute_levels_rank_buckets_keep_ties_together():
    daily = {"a": 1, "b": 1, "c": 5, "d": 10, "e": 20, "z": 0}
    levels = heatmap.compute_levels(daily)
    assert levels["a"] == levels["b"] == 1
    assert levels["z"] == 0
    assert set(levels.values()) <= {0, 1, 2, 3, 4}
    assert levels["e"] == 4


def test_svg_empty_common_year_structure(monkeypatch):
    monkeypatch.setattr(heatmap, "shanghai_today", lambda: dt.date(2026, 12, 31))
    svg = heatmap.build_svg(2026, {})
    assert '<svg xmlns="http://www.w3.org/2000/svg" width="793" height="161"' in svg
    assert svg.count("<title>") == 365
    # 每日格子 + 五个图例色块（背景透明，无全幅画布 rect）。
    assert svg.count("<rect ") == 365 + 5


def test_year_svg_has_bottom_stats_line(monkeypatch):
    monkeypatch.setattr(heatmap, "shanghai_today", lambda: dt.date(2026, 9, 7))
    daily = {
        "2026-09-07": 452_200_000,          # 今日 452.2M
        "2026-09-01": 1_000_000,             # 本月其他
        "2026-08-31": 5_000_000,             # 上月（不在本月/今年之外？在年内）
        "2026-12-31": 999,                   # 未来日期（不应计入 year_total? 实际计入——见口径）
    }
    svg = heatmap.build_svg(2026, daily, darkmode="0")
    # 今日 = 452.2M
    assert "今日 452.2M" in svg
    # 本月 = 452.2M + 1M = 453.2M
    assert "本月 453.2M" in svg
    # 今年 = 452.2M + 1M + 5M + 999（所有 <2026-09-08 的键；12-31 未来不计因为 > today）
    assert "今年 458.2M" in svg
    # 年份在底部统计行（y 为 height-8，不再贴底）
    assert 'font-size="10" fill="#24292f">2026</text>' in svg


def test_year_svg_stats_uses_b_units_for_large(monkeypatch):
    monkeypatch.setattr(heatmap, "shanghai_today", lambda: dt.date(2026, 9, 7))
    daily = {"2026-09-07": 35_000_000_000}  # 今日 35B
    svg = heatmap.build_svg(2026, daily, darkmode="0")
    assert "今日 35.00B" in svg


def test_year_svg_english_stats_labels(monkeypatch):
    monkeypatch.setattr(heatmap, "shanghai_today", lambda: dt.date(2026, 9, 7))
    daily = {"2026-09-07": 1_000}
    svg = heatmap.build_svg(2026, daily, lang="en", darkmode="0")
    assert "Today 1.0K" in svg
    assert "Month" in svg
    assert "Year" in svg


def test_non_current_year_stats_show_year_total(monkeypatch):
    monkeypatch.setattr(heatmap, "shanghai_today", lambda: dt.date(2026, 9, 7))
    daily = {"2025-01-01": 100, "2025-12-31": 200}
    svg = heatmap.build_svg(2025, daily, darkmode="0")
    assert "今日 0" in svg
    assert "今年 300" in svg


def test_svg_leap_year_and_future_is_uncolored(monkeypatch):
    monkeypatch.setattr(heatmap, "shanghai_today", lambda: dt.date(2024, 2, 28))
    svg = heatmap.build_svg(2024, {"2024-02-28": 10, "2024-02-29": 999}, darkmode="0")
    assert svg.count("<title>") == 366
    assert re.search(r'<rect[^>]*fill="#9be9a8"><title>2024-02-28: 10 tokens</title>', svg)
    assert re.search(r'<rect[^>]*fill="#ebedf0"><title>2024-02-29: 999 tokens</title>', svg)


def test_svg_has_all_color_levels_for_spread_values(monkeypatch):
    monkeypatch.setattr(heatmap, "shanghai_today", lambda: dt.date(2026, 12, 31))
    daily = {f"2026-01-{day:02d}": day for day in range(1, 21)}
    svg = heatmap.build_svg(2026, daily, darkmode="0")
    for color in heatmap.LEVEL_COLORS:
        assert color in svg


def test_month_svg_has_one_title_for_each_calendar_day(monkeypatch):
    monkeypatch.setattr(heatmap, "shanghai_today", lambda: dt.date(2026, 9, 30))
    svg = heatmap.build_month_svg(2026, 9, {"2026-09-01": 12})
    assert "2026年9月" in svg
    assert svg.count("<title>") == 30
    assert "2026-09-01: 12 tokens" in svg
    assert "2026-09-30: 0 tokens" in svg


def test_day_svg_has_24_hourly_bars():
    svg = heatmap.build_day_svg(2026, 9, 7, {0: 10, 12: 20})
    assert "2026-09-07" in svg
    assert svg.count('class="bar"') == 24
    assert svg.count("<title>") == 24
    assert "12:00-12:59: 20 tokens" in svg


def test_theme_and_english_labels():
    svg = heatmap.build_month_svg(2026, 9, {}, theme="github", lang="en", darkmode="1")
    # 背景透明：不应有全幅背景 rect；night 配色（硬编码 hex）在
    assert '<rect width="100%" height="100%"' not in svg
    assert "#161b22" in svg  # github night 空格子色
    assert "#8b949e" in svg  # github night 文字色
    assert "Sep 2026" in svg
    assert "Mo" in svg and "Tu" in svg and "Su" in svg
    assert "Less" in svg
    assert "More" in svg


def test_year_svg_weekday_labels_github_style(monkeypatch):
    """GitHub 风格：年图左侧只显示 周一/周三/周五 三个标签（zh=一三五 / en=Mon Wed Fri）。"""
    monkeypatch.setattr(heatmap, "shanghai_today", lambda: dt.date(2026, 12, 31))
    zh = heatmap.build_svg(2026, {}, darkmode="0")
    # zh: 只含 一/三/五，不含 二/四/六/日 的独立 weekday 标签
    for label in ("一", "三", "五"):
        assert f'>{label}</text>' in zh
    en = heatmap.build_svg(2026, {}, lang="en", darkmode="0")
    for label in ("Mon", "Wed", "Fri"):
        assert f'>{label}</text>' in en
    # 月图不受影响：仍 7 个完整 weekday（Mo~Su 2 字母）
    month = heatmap.build_month_svg(2026, 9, {}, lang="en", darkmode="0")
    for label in ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"):
        assert f'>{label}</text>' in month


def test_darkmode_0_uses_day_palette():
    svg = heatmap.build_svg(2026, {}, darkmode="0")
    assert "#ebedf0" in svg  # github day 空格子色
    assert "#24292f" in svg  # github day 标题色
    assert "<style>" not in svg


def test_darkmode_1_uses_night_palette():
    svg = heatmap.build_svg(2026, {}, darkmode="1")
    assert "#161b22" in svg  # github night 空格子色
    assert "#c9d1d9" in svg  # github night 标题色
    assert "<style>" not in svg


def test_darkmode_auto_embeds_css_variables_and_media_query():
    svg = heatmap.build_svg(2026, {}, theme="github", darkmode="auto")
    # 内嵌 <style>：默认 day 值，prefers-color-scheme: dark 覆盖为 night 值
    assert "<style>" in svg
    assert "--c0:#ebedf0" in svg  # day 空格子
    assert "--c0:#161b22" in svg  # night 空格子
    assert "--tx:#767676" in svg
    assert "--tx:#8b949e" in svg
    assert "prefers-color-scheme: dark" in svg
    # body 颜色用 var() 引用
    assert 'fill="var(--c0)"' in svg


def test_bg_0_default_transparent_no_background_rect():
    svg = heatmap.build_svg(2026, {}, darkmode="0")  # 默认 bg=False
    assert '<rect width="100%" height="100%"' not in svg
    # auto 默认也应无背景 rect
    svg_auto = heatmap.build_svg(2026, {}, darkmode="auto")
    assert '<rect width="100%" height="100%"' not in svg_auto


def test_bg_1_adds_theme_background_rect():
    # day 模式：白底
    svg = heatmap.build_svg(2026, {}, darkmode="0", bg=True)
    assert '<rect width="100%" height="100%" fill="#ffffff"/>' in svg
    # night 模式：黑底
    svg2 = heatmap.build_svg(2026, {}, darkmode="1", bg=True)
    assert '<rect width="100%" height="100%" fill="#0d1117"/>' in svg2
    # auto 模式：var(--bg)
    svg3 = heatmap.build_svg(2026, {}, darkmode="auto", bg=True)
    assert '<rect width="100%" height="100%" fill="var(--bg)"/>' in svg3
    assert "--bg:#ffffff" in svg3  # day 背景
    assert "--bg:#0d1117" in svg3  # night 背景
