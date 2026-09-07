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
    assert '<svg xmlns="http://www.w3.org/2000/svg" width="793" height="151"' in svg
    assert svg.count("<title>") == 365
    # 每日格子、白色画布和五个图例色块。
    assert svg.count("<rect ") == 365 + 1 + 5


def test_svg_leap_year_and_future_is_uncolored(monkeypatch):
    monkeypatch.setattr(heatmap, "shanghai_today", lambda: dt.date(2024, 2, 28))
    svg = heatmap.build_svg(2024, {"2024-02-28": 10, "2024-02-29": 999})
    assert svg.count("<title>") == 366
    assert re.search(r'<rect[^>]*fill="#9be9a8"><title>2024-02-28: 10 tokens</title>', svg)
    assert re.search(r'<rect[^>]*fill="#ebedf0"><title>2024-02-29: 999 tokens</title>', svg)


def test_svg_has_all_color_levels_for_spread_values(monkeypatch):
    monkeypatch.setattr(heatmap, "shanghai_today", lambda: dt.date(2026, 12, 31))
    daily = {f"2026-01-{day:02d}": day for day in range(1, 21)}
    svg = heatmap.build_svg(2026, daily)
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
    svg = heatmap.build_month_svg(2026, 9, {}, theme="github-dark", lang="en")
    assert "#0d1117" in svg
    assert "Sep 2026" in svg
    assert "Mo" in svg and "Tu" in svg and "Su" in svg
    assert "Less" in svg
    assert "More" in svg
