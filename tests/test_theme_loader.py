"""theme_loader 测试：主题目录加载、结构校验、内置 github 兜底、watchdog 事件热更新。

用 tmp_path 作为主题目录 + monkeypatch THEMES_DIR，避免污染真实 themes/。
真实 watchdog Observer 线程不在单测里启动（避免跨用例状态污染），
热更新逻辑通过 handler._schedule_reload -> reload() 链路验证（等防抖窗口）。
"""
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


def _make_theme(colors: list[str], scalar_fields: dict[str, str]) -> dict:
    """Build a valid theme structure with day/night palettes."""
    return {
        "day": {
            "colors": colors,
            "text": scalar_fields["text"],
            "title": scalar_fields["title"],
            "legend": scalar_fields["legend"],
            "background": scalar_fields["background"],
        },
        "night": {
            "colors": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
            "text": "#8b949e",
            "title": "#c9d1d9",
            "legend": "#7d8590",
            "background": "#0d1117",
        },
    }


class TestStrictHexColorValidation:
    """Ensure only exact 6-digit #[0-9A-Fa-f]{6} colors are accepted."""

    @pytest.mark.parametrize("field", ["text", "title", "legend", "background"])
    def test_rejected_scalar_field_wrong_length(self, field, theme_tmp):
        """Wrong-length value in scalar field must be rejected."""
        night_pal = dict(GITHUB_JSON["night"])
        night_pal[field] = "#abc"
        night_pal["colors"] = GITHUB_JSON["night"]["colors"]
        day_pal = dict(GITHUB_JSON["day"])
        day_pal[field] = "#abc"
        day_pal["colors"] = GITHUB_JSON["day"]["colors"]
        theme = {"day": day_pal, "night": night_pal}
        (theme_tmp / f"scal{field}.json").write_text(json.dumps(theme), encoding="utf-8")
        theme_loader.reload()
        themes = theme_loader.get_themes()
        assert f"scal{field}" not in themes, f"Wrong-length {field} must be rejected"

    @pytest.mark.parametrize("field", ["text", "title", "legend", "background"])
    def test_rejected_scalar_field_injection(self, field, theme_tmp):
        """Malicious injection in scalar field must be rejected."""
        injection = '#fff" onload="alert(1)'
        night_pal = dict(GITHUB_JSON["night"])
        night_pal[field] = injection
        night_pal["colors"] = GITHUB_JSON["night"]["colors"]
        day_pal = dict(GITHUB_JSON["day"])
        day_pal[field] = injection
        day_pal["colors"] = GITHUB_JSON["day"]["colors"]
        theme = {"day": day_pal, "night": night_pal}
        (theme_tmp / f"scalinj{field}.json").write_text(json.dumps(theme), encoding="utf-8")
        theme_loader.reload()
        themes = theme_loader.get_themes()
        assert f"scalinj{field}" not in themes, f"Injection in {field} must be rejected"

    @pytest.mark.parametrize(
        "invalid",
        [
            pytest.param("#fff", id="3-digit"),
            pytest.param("#abcd", id="4-digit"),
            pytest.param("#abcde", id="5-digit"),
            pytest.param("#gggggg", id="non-hex"),
            pytest.param("#ffffff\n", id="trailing-nl"),
            pytest.param("#", id="empty-hash"),
            pytest.param('#fff" onload="alert(1)', id="xml-injection"),
        ],
    )
    def test_rejected_colors_variants(self, invalid, theme_tmp):
        """Invalid color forms must be rejected."""
        night_colors = list(GITHUB_JSON["night"]["colors"])
        night_colors[0] = invalid
        day_colors = list(GITHUB_JSON["day"]["colors"])
        day_colors[0] = "#9be9a8"
        theme = {
            "day": {
                "colors": day_colors,
                "text": "#767676",
                "title": "#24292f",
                "legend": "#767676",
                "background": "#ffffff",
            },
            "night": {
                "colors": night_colors,
                "text": "#8b949e",
                "title": "#c9d1d9",
                "legend": "#7d8590",
                "background": "#0d1117",
            },
        }
        safe_name = invalid.replace("\n", "_").replace("/", "_").replace("\\", "_").replace('"', "_")[:20]
        (theme_tmp / f"rej{safe_name}.json").write_text(json.dumps(theme), encoding="utf-8")
        theme_loader.reload()
        themes = theme_loader.get_themes()
        assert f"rej{safe_name}" not in themes, f"Invalid color {invalid!r} must be rejected"

    def test_accepted_uppercase_six_digit(self, theme_tmp):
        """Uppercase six-digit hex colors must be accepted."""
        theme = _make_theme(
            ["#EBEDF0", "#9BE9A8", "#40C463", "#30A14E", "#216E39"],
            {"text": "#767676", "title": "#24292F", "legend": "#767676", "background": "#FFFFFF"},
        )
        (theme_tmp / "upper.json").write_text(json.dumps(theme), encoding="utf-8")
        theme_loader.reload()
        themes = theme_loader.get_themes()
        assert "upper" in themes, "Valid uppercase six-digit hex must be accepted"
        assert themes["upper"]["day"]["colors"][0] == "#EBEDF0"

    def test_accepted_lowercase_six_digit(self, theme_tmp):
        """Lowercase six-digit hex colors must be accepted."""
        theme = _make_theme(
            ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
            {"text": "#767676", "title": "#24292f", "legend": "#767676", "background": "#ffffff"},
        )
        (theme_tmp / "lower.json").write_text(json.dumps(theme), encoding="utf-8")
        theme_loader.reload()
        themes = theme_loader.get_themes()
        assert "lower" in themes, "Valid lowercase six-digit hex must be accepted"


class TestWatchdogAbsentSafety:
    """Verify module imports and operates safely when watchdog is unavailable."""

    def test_import_safe_when_watchdog_absent(self, monkeypatch):
        """Module must not raise when watchdog Observer is None; start_watch returns False."""
        # Monkeypatch Observer to None locally - no module reload needed.
        # Production code already handles this gracefully (start_watch returns False).
        monkeypatch.setattr(theme_loader, "Observer", None)
        result = theme_loader.start_watch()
        assert result is False

class TestOnMovedHandler:
    """Verify on_moved triggers debounced reload for atomic JSON operations."""

    def test_on_moved_triggers_reload(self, theme_tmp, monkeypatch):
        """on_moved on JSON src_path should schedule reload."""
        handler = theme_loader._ThemeHandler()
        custom = {
            "day": {"colors": ["#a1a1a1"] * 5, "text": "#111111", "title": "#222222", "legend": "#333333", "background": "#444444"},
            "night": {"colors": ["#a1a1a1"] * 5, "text": "#111111", "title": "#222222", "legend": "#333333", "background": "#444444"},
        }
        src = theme_tmp / "moveme.json"
        dst = theme_tmp / "moved.json"
        src.write_text(json.dumps(custom), encoding="utf-8")
        theme_loader.reload()
        assert "moveme" in theme_loader.get_themes()
        # Simulate atomic move: delete src, write dst
        src.unlink()
        dst.write_text(json.dumps(custom), encoding="utf-8")
        # on_moved: src_path=old location, dest_path=new location
        event = type("E", (), {"is_directory": False, "src_path": str(src), "dest_path": str(dst)})()
        handler.on_moved(event)
        time.sleep(0.6)  # wait for debounce
        themes = theme_loader.get_themes()
        assert "moveme" not in themes
        assert "moved" in themes

    def test_on_moved_ignores_directory(self, theme_tmp, monkeypatch):
        """on_moved on directory should be ignored."""
        handler = theme_loader._ThemeHandler()
        event = type("E", (), {"is_directory": True, "src_path": str(theme_tmp / "subdir"), "dest_path": str(theme_tmp / "subdir_new")})()
        # Should not raise, no reload scheduled
        handler.on_moved(event)
        assert handler._debounce is None

    def test_on_moved_ignores_non_json(self, theme_tmp, monkeypatch):
        """on_moved on non-JSON file should be ignored."""
        handler = theme_loader._ThemeHandler()
        event = type("E", (), {"is_directory": False, "src_path": str(theme_tmp / "readme.txt"), "dest_path": str(theme_tmp / "readme_new.txt")})()
        handler.on_moved(event)
        assert handler._debounce is None


class TestStopWatch:
    """Verify stop_watch cleanly shuts down watcher and timer."""

    def test_stop_watch_cancels_pending_debounce(self, theme_tmp, monkeypatch):
        """stop_watch must cancel any pending debounce timer from started observer."""
        monkeypatch.setenv("THEMES_DIR", str(theme_tmp))
        theme_loader.reload()
        started = theme_loader.start_watch()
        if not started:
            pytest.skip("watchdog not available")
        # Get handler from the observer's _handlers dict
        handlers = list(getattr(theme_loader._observer, "_handlers", {}).values())
        assert len(handlers) > 0, "No handlers found"
        handler = list(handlers[0])[0]  # get first handler from first watch's handler set
        assert hasattr(handler, "_debounce")
        custom = {
            "day": {"colors": ["#c1c1c1"] * 5, "text": "#111111", "title": "#222222", "legend": "#333333", "background": "#444444"},
            "night": {"colors": ["#c1c1c1"] * 5, "text": "#111111", "title": "#222222", "legend": "#333333", "background": "#444444"},
        }
        target = theme_tmp / "stop.json"
        target.write_text(json.dumps(custom), encoding="utf-8")
        theme_loader.reload()
        # Trigger debounce on the observer's handler
        event = type("E", (), {"is_directory": False, "src_path": str(target)})()
        handler.on_modified(event)
        assert handler._debounce is not None
        # stop_watch should cancel it
        theme_loader.stop_watch()
        assert handler._debounce is None or not handler._debounce.is_alive()

    def test_stop_watch_stops_observer(self, theme_tmp, monkeypatch):
        """stop_watch must stop the observer thread."""
        monkeypatch.setenv("THEMES_DIR", str(theme_tmp))
        theme_loader.reload()
        started = theme_loader.start_watch()
        if not started:
            pytest.skip("watchdog not available")
        assert theme_loader._observer is not None
        theme_loader.stop_watch()
        assert theme_loader._observer is None

    def test_stop_watch_idempotent(self, theme_tmp, monkeypatch):
        """stop_watch must be safe to call multiple times."""
        monkeypatch.setenv("THEMES_DIR", str(theme_tmp))
        theme_loader.reload()
        # Call stop when not watching - should not raise
        theme_loader.stop_watch()
        theme_loader.stop_watch()  # idempotent
        # Now start and stop
        started = theme_loader.start_watch()
        if started:
            theme_loader.stop_watch()
            theme_loader.stop_watch()  # idempotent after stop

    def test_lifespan_calls_stop_watch(self, theme_tmp, monkeypatch):
        """Lifespan must call stop_watch after yield."""
        from unittest.mock import patch

        with patch(
            "app.main.stop_watch",
        ) as mock_stop, patch("app.main.start_watch", return_value=True) as mock_start:
            import asyncio

            from app.main import lifespan

            async def run_lifespan():
                async with lifespan(None) as _:
                    pass

            asyncio.run(run_lifespan())
            mock_start.assert_called_once()
            mock_stop.assert_called_once()
