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
    """返回指定/默认数据源；未知名回退 new-api。"""
    key = name or SOURCE
    return _SOURCES.get(key, _SOURCES["new-api"])
