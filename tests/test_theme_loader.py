"""theme_loader 测试：主题目录加载、结构校验、内置 github 兜底、watchdog 事件热更新。

用 tmp_path 作为主题目录 + monkeypatch THEMES_DIR，避免污染真实 themes/。
真实 watchdog Observer 线程不在单测里启动（避免跨用例状态污染），
热更新逻辑通过 handler._schedule_reload -> reload() 链路验证（等防抖窗口）。
"""
import datetime as dt
import json
import time

import pytest

from app import heatmap, theme_loader

GITHUB_JSON = {
    "day": {"colors": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"], "text": "#767676", "title": "#24292f", "legend": "#767676", "background": "#ffffff"},
    "night": {"colors": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"], "text": "#8b949e", "title": "#c9d1d9", "legend": "#7d8590", "background": "#0d1117"},
}


@pytest.fixture
def theme_tmp(tmp_path, monkeypatch):
    """指向临时目录的 THEMES_DIR + 干净的模块态。"""
    monkeypatch.setenv("THEMES_DIR", str(tmp_path))
    theme_loader.reload()  # 重新加载（此时目录空 → 只剩内置 github）
    yield tmp_path
    theme_loader.reload()  # 还原（读真实 themes/）


def test_empty_dir_falls_back_to_builtin(theme_tmp):
    themes = theme_loader.get_themes()
    assert set(themes) == {"github"}
    assert themes["github"]["day"]["colors"][0] == "#ebedf0"


def test_loads_json_files_into_themes(theme_tmp):
    (theme_tmp / "github.json").write_text(json.dumps(GITHUB_JSON), encoding="utf-8")
    custom = {
        "day": {"colors": ["#111111", "#222222", "#333333", "#444444", "#555555"], "text": "#666666", "title": "#777777", "legend": "#888888", "background": "#999999"},
        "night": {"colors": ["#aaaaaa", "#bbbbbb", "#cccccc", "#dddddd", "#eeeeee"], "text": "#ffffff", "title": "#ffffff", "legend": "#ffffff", "background": "#000000"},
    }
    (theme_tmp / "sakura.json").write_text(json.dumps(custom), encoding="utf-8")
    theme_loader.reload()
    themes = theme_loader.get_themes()
    assert set(themes) == {"github", "sakura"}
    assert themes["sakura"]["day"]["colors"][0] == "#111111"


def test_invalid_json_is_skipped(theme_tmp):
    (theme_tmp / "bad.json").write_text("{not json", encoding="utf-8")
    (theme_tmp / "nogithub.json").write_text(json.dumps({"day": {}}), encoding="utf-8")
    (theme_tmp / "shortcolors.json").write_text(json.dumps({"day": {"colors": ["#111111"]}, "night": GITHUB_JSON["night"]}), encoding="utf-8")
    theme_loader.reload()
    themes = theme_loader.get_themes()
    assert set(themes) == {"github"}  # 非法文件全部跳过


def test_same_name_json_overrides_builtin(theme_tmp):
    modified = json.loads(json.dumps(GITHUB_JSON))
    modified["day"]["colors"][0] = "#ff0000"  # 空色改红
    (theme_tmp / "github.json").write_text(json.dumps(modified), encoding="utf-8")
    theme_loader.reload()
    assert theme_loader.get_themes()["github"]["day"]["colors"][0] == "#ff0000"


def test_deleting_custom_theme_removes_it(theme_tmp):
    (theme_tmp / "custom.json").write_text(json.dumps(GITHUB_JSON), encoding="utf-8")
    theme_loader.reload()
    assert "custom" in theme_loader.get_themes()
    (theme_tmp / "custom.json").unlink()
    theme_loader.reload()
    themes = theme_loader.get_themes()
    assert "custom" not in themes
    assert "github" in themes  # 兜底保留


def test_watchdog_handler_reloads_on_change(theme_tmp):
    """事件 handler 触发防抖 reload：新增 json 后 get_themes 能看到新主题。"""
    handler = theme_loader._ThemeHandler()
    custom = {
        "day": {"colors": ["#010101", "#020202", "#030303", "#040404", "#050505"], "text": "#060606", "title": "#070707", "legend": "#080808", "background": "#090909"},
        "night": {"colors": ["#111111", "#121212", "#131313", "#141414", "#151515"], "text": "#161616", "title": "#171717", "legend": "#181818", "background": "#191919"},
    }
    target = theme_tmp / "watch.json"
    target.write_text(json.dumps(custom), encoding="utf-8")
    handler.on_created(type("E", (), {"is_directory": False, "src_path": str(target)})())
    time.sleep(0.6)  # 等防抖 300ms
    assert "watch" in theme_loader.get_themes()
    # 删除
    target.unlink()
    handler.on_deleted(type("E", (), {"is_directory": False, "src_path": str(target)})())
    time.sleep(0.6)
    assert "watch" not in theme_loader.get_themes()


def test_heatmap_renders_custom_theme(theme_tmp):
    """渲染链路：自定义主题族出现在 SVG（darkmode=1 night 配色）。"""
    custom = {
        "day": {"colors": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"], "text": "#767676", "title": "#24292f", "legend": "#767676", "background": "#ffffff"},
        "night": {"colors": ["#0d1117", "#123456", "#abcdef", "#fedcba", "#010101"], "text": "#8b949e", "title": "#c9d1d9", "legend": "#7d8590", "background": "#0d1117"},
    }
    (theme_tmp / "neon.json").write_text(json.dumps(custom), encoding="utf-8")
    theme_loader.reload()
    svg = heatmap.build_svg(2026, {}, theme="neon", darkmode="1")
    assert "#123456" in svg  # night 第二档
    assert "#abcdef" in svg  # night 第三档


def test_builtin_github_still_renders_without_any_json(theme_tmp):
    svg = heatmap.build_svg(2026, {}, theme="github", darkmode="0")
    assert "#ebedf0" in svg


def test_family_fallback_to_github_for_unknown(theme_tmp):
    # 未知族回落 github，不抛错
    svg = heatmap.build_svg(2026, {}, theme="does-not-exist", darkmode="0")
    assert "#ebedf0" in svg
