"""数据源注册与默认源选择。

默认源由 config.SOURCE（env SOURCE）决定：new-api（默认）或 sub2api。
URL 不暴露 source 参数；如需多源并存，部署多个实例并各自指定 SOURCE。
"""
from __future__ import annotations

try:  # 容器以 sources 顶层包运行（uvicorn main:app 从 /app 启动）
    from config import SOURCE
    from sources.base import Source
    from sources.newapi import NewApiSource
    from sources.sub2api_db import Sub2ApiSource
except ModuleNotFoundError:  # pragma: no cover - 测试以 app.sources 包导入
    from ..config import SOURCE
    from .base import Source
    from .newapi import NewApiSource
    from .sub2api_db import Sub2ApiSource

_SOURCES: dict[str, Source] = {
    NewApiSource.name: NewApiSource(),
    Sub2ApiSource.name: Sub2ApiSource(),
}


def get_source(name: str | None = None) -> Source:
    """Return the specified or default data source."""
    key = name or SOURCE
    if key not in _SOURCES:
        raise ValueError(f"Unknown source: {key!r}. Supported: {list(_SOURCES.keys())}")
    return _SOURCES[key]
