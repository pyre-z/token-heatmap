"""主题族加载器：从 ``themes/*.json`` 读取主题族配置，并用 watchdog 热更新。

设计：
- 主题族 = JSON 文件名（如 ``github.json`` -> 族名 ``github``），内容为
  ``{"day": {...}, "night": {...}}`` 两套配色（与旧硬编码 THEMES 结构一致）。
- **内置 github 兜底**：内置主题永远可用。``themes/`` 目录不存在/为空时仍能
  渲染 github；同名 ``github.json`` 存在时以文件内容覆盖内置配色。
- **热更新**：start_watch() 用 watchdog 监听目录，新增/修改/删除任意 ``*.json``
  都会重算主题表（删除即移除该族；删光后回落到内置 github）。
- watchdog 未安装时静默降级为仅启动时加载（不影响无 watchdog 环境运行/测试）。
"""
from __future__ import annotations

import copy
import json
import logging
import os
import re
import threading
from pathlib import Path

logger = logging.getLogger(__name__)
_HEX_COLOR_RE = re.compile(r"\A#[0-9A-Fa-f]{6}\Z")

try:  # watchdog 可选依赖；未安装时静默降级
    from watchdog.events import FileSystemEventHandler

    # 用 PollingObserver（轮询式）而非默认 inotify Observer：
    # 容器 bind mount 场景下宿主侧文件写入不产生容器内 inotify 事件，
    # 轮询式能可靠感知宿主编辑 themes/*.json 的变化（默认 1s 轮询）。
    from watchdog.observers.polling import PollingObserver as Observer
except ModuleNotFoundError:  # pragma: no cover
    FileSystemEventHandler = None
    Observer = None

# 内置兜底主题（与 themes/github.json 同构；代码随仓库分发，永不依赖磁盘）
BUILTIN_THEMES: dict = {
    "github": {
        "day": {"colors": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"], "text": "#767676", "title": "#24292f", "legend": "#767676", "background": "#ffffff"},
        "night": {"colors": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"], "text": "#8b949e", "title": "#c9d1d9", "legend": "#7d8590", "background": "#0d1117"},
    },
}

_lock = threading.RLock()

# Current theme table (copy-on-reload: replace whole dict, reader gets complete dict)
_THEMES: dict = {}
# Monotonic generation counter: increments only after a complete theme-table replacement
_generation: int = 0


def _default_dir() -> Path:
    """默认主题目录：项目根 themes/（app/theme_loader.py 的上级上级）。"""
    return Path(__file__).resolve().parent.parent / "themes"


def theme_dir() -> Path:
    """主题目录：优先 THEMES_DIR 环境变量，否则项目根 themes/。"""
    return Path(os.environ.get("THEMES_DIR", _default_dir()))


def get_themes() -> dict:
    """当前主题表（内置 github + 目录内 json，同名文件覆盖内置）。"""
    with _lock:
        return _themes()


def theme_generation() -> int:
    """Monotonic theme generation counter: increments only after a complete theme-table replacement."""
    with _lock:
        return _generation


def _themes() -> dict:
    global _THEMES
    if not _THEMES:
        _THEMES = _load_from_disk()
    return _THEMES


def _valid_family(name: str, data: object) -> dict | None:
    """校验单个主题族 JSON 结构；不合法返回 None。"""
    if not isinstance(data, dict):
        return None
    fam: dict = {}
    for mode in ("day", "night"):
        pal = data.get(mode)
        if not isinstance(pal, dict):
            logger.warning("主题 %s 缺少 %s 配色，跳过", name, mode)
            return None
        colors = pal.get("colors")
        if not isinstance(colors, list) or len(colors) != 5 or not all(isinstance(c, str) and _HEX_COLOR_RE.match(c) for c in colors):
            logger.warning("主题 %s.%s colors 必须为 5 个十六进制色，跳过", name, mode)
            return None
        for key in ("text", "title", "legend", "background"):
            if not isinstance(pal.get(key), str) or not _HEX_COLOR_RE.match(pal[key]):
                logger.warning("主题 %s.%s.%s 必须为十六进制色，跳过", name, mode, key)
                return None
        fam[mode] = {
            "colors": list(colors),
            "text": pal["text"],
            "title": pal["title"],
            "legend": pal["legend"],
            "background": pal["background"],
        }
    return fam


def _load_from_disk() -> dict:
    """扫描主题目录，重建主题表 = 内置兜底 + 目录 json（同名覆盖内置）。"""
    result = copy.deepcopy(BUILTIN_THEMES)
    directory = theme_dir()
    if not directory.is_dir():
        return result
    for path in sorted(directory.glob("*.json")):
        name = path.stem
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("主题文件 %s 读取失败: %s", path, exc)
            continue
        fam = _valid_family(name, data)
        if fam is not None:
            result[name] = fam
    return result


def reload() -> None:
    """重算主题表并整体替换（供 load 与 watchdog 事件共用）。"""
    global _THEMES, _generation
    fresh = _load_from_disk()
    with _lock:
        _THEMES = fresh
        _generation += 1


def load() -> None:
    """启动加载（幂等）。"""
    reload()


# Conditionally define _ThemeHandler based on watchdog availability
if FileSystemEventHandler is not None:

    class _ThemeHandler(FileSystemEventHandler):  # type: ignore[misc]
        """watchdog 事件：*.json 增/删/改/移动 -> 防抖后 reload()。"""

        def __init__(self) -> None:
            self._debounce: threading.Timer | None = None

        def _schedule_reload(self) -> None:
            if self._debounce is not None:
                self._debounce.cancel()
            # 文件写入可能触发多次事件，聚合 300ms 内的变更只 reload 一次
            self._debounce = threading.Timer(0.3, reload)
            self._debounce.daemon = True
            self._debounce.start()

        def on_created(self, event) -> None:
            if not event.is_directory and event.src_path.endswith(".json"):
                self._schedule_reload()

        def on_modified(self, event) -> None:
            if not event.is_directory and event.src_path.endswith(".json"):
                self._schedule_reload()

        def on_deleted(self, event) -> None:
            if not event.is_directory and event.src_path.endswith(".json"):
                self._schedule_reload()

        def on_moved(self, event) -> None:
            # 原子替换（编辑器先写临时文件再 move）可能产生 on_moved
            if not event.is_directory:
                src_json = event.src_path.endswith(".json")
                dst_json = getattr(event, "dest_path", "").endswith(".json")
                if src_json or dst_json:
                    self._schedule_reload()

else:
    # watchdog absent: provide a no-op handler so start_watch has something to reference
    class _ThemeHandler:  # type: ignore[misc]
        """watchdog 不可用时的空实现。"""

        def __init__(self) -> None:
            pass


_observer: Observer | None = None


def stop_watch() -> None:
    """停止 watchdog 监听：取消防抖计时器、停止并 join 观察者线程。"""
    global _observer

    # Cancel any pending debounce timers on all scheduled handlers
    if _observer is not None:
        for handler_set in getattr(_observer, "_handlers", {}).values():
            for handler in handler_set:
                if hasattr(handler, "_debounce") and handler._debounce is not None:
                    handler._debounce.cancel()
                    handler._debounce = None

    # Stop observer thread
    with _lock:
        if _observer is not None:
            _observer.stop()
            # Bounded join: wait up to 2s for watchdog thread to finish
            _observer.join(timeout=2.0)
            _observer = None


def start_watch() -> bool:
    """启动 watchdog 监听主题目录（幂等）。返回是否真正启动（无 watchdog 时为 False）。"""
    global _observer
    if Observer is None:  # pragma: no cover
        logger.info("watchdog 未安装，主题仅启动加载一次")
        return False
    with _lock:
        if _observer is not None:
            return True
        directory = theme_dir()
        directory.mkdir(parents=True, exist_ok=True)
        observer = Observer()
        observer.schedule(_ThemeHandler(), str(directory), recursive=False)
        observer.daemon = True
        observer.start()
        _observer = observer
    logger.info("主题 watchdog 已监听 %s", directory)
    return True


# import 即完成一次启动加载（含内置兜底；目录有 json 则覆盖/扩展）
reload()
