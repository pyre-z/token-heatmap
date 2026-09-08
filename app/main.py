"""Token 热力图服务的 FastAPI 路由。"""
from __future__ import annotations

import datetime as dt
import html
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from starlette.middleware.gzip import GZipMiddleware

try:
    from cache import cache_get, cache_set
    from heatmap import build_auto_svg, build_day_svg, build_month_svg, build_svg, shanghai_today
    from sources import get_source
    from theme_loader import get_themes, start_watch
except ModuleNotFoundError:  # pragma: no cover
    from .cache import cache_get, cache_set
    from .heatmap import build_auto_svg, build_day_svg, build_month_svg, build_svg, shanghai_today
    from .sources import get_source
    from .theme_loader import get_themes, start_watch

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """启动主题目录 watchdog（幂等；无 watchdog 环境静默降级）。"""
    start_watch()
    yield


app = FastAPI(title="Token Heatmap", docs_url=None, redoc_url=None, lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)

def _invalid() -> None:
    raise HTTPException(status_code=400, detail="invalid parameter")

def _validate(grain: str, year: int | None, month: int | None, day: int | None, theme: str) -> tuple[int, int | None, int | None]:
    if grain not in {"auto", "year", "month", "day"}: _invalid()
    # theme 只接受主题族名（动态从 themes/ 加载，含内置 github；旧 github-dark 已不保留）
    if theme not in get_themes(): _invalid()
    today = shanghai_today()
    # auto（滚动年）：区间由今天决定，忽略 year/month/day 参数
    if grain == "auto":
        return 0, None, None
    year = today.year if year is None else year
    month = today.month if month is None else month
    day = today.day if day is None else day
    if not 2000 <= year <= 2100 or not 1 <= month <= 12 or not 1 <= day <= 31: _invalid()
    try:
        dt.date(year, month, day)
    except ValueError: _invalid()
    # grain 与参数层级一致：year 粒度忽略 day；month 粒度忽略 day
    if grain == "year":
        return year, None, None
    if grain == "month":
        return year, month, None
    return year, month, day

def _svg_response(svg: str) -> Response:
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=600"})

@app.get("/token/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}

def _render_svg(key: str, render: Callable[[], str]) -> Response:
    """带 TTL 缓存的 SVG 渲染：命中直接返回，未命中渲染后写入缓存。DB 错误不缓存。"""
    cached = cache_get(key)
    if cached is not None:
        return _svg_response(cached)
    svg = render()
    cache_set(key, svg)
    return _svg_response(svg)

@app.get("/token/@")
def token_svg(grain: str = "auto", year: str | None = Query(None), month: str | None = Query(None), day: str | None = Query(None), theme: str = "github", lang: str = "zh", darkmode: str = "auto", bg: str = "0", scale: str = "1") -> Response:
    """根据 grain 粒度生成滚动年(auto)/年度/月度/日度 SVG。scale 控制缩放（0.1-10）；darkmode=0/1/auto；bg=0 透明/1 主题背景色。数据源由 SOURCE env 决定。"""
    if darkmode not in {"0", "1", "auto"} or bg not in {"0", "1"}:
        _invalid()
    try:
        year, month, day = (int(value) if value is not None else None for value in (year, month, day))
        scale = float(scale)
    except ValueError:
        _invalid()
    if not 0.1 <= scale <= 10:
        _invalid()
    year, month, day = _validate(grain, year, month, day, theme)
    lang = lang if lang in {"zh", "en"} else "zh"
    source = get_source()
    src_key = source.name
    key = f"{src_key}|{grain}|{year}|{month}|{day}|{theme}|{lang}|{scale:g}|{darkmode}|{bg}"
    try:
        if grain == "auto":
            today = shanghai_today()
            start = today - dt.timedelta(days=364)
            end = today + dt.timedelta(days=1)
            return _render_svg(key, lambda: build_auto_svg(source.daily_tokens_in_range(start, end), theme, lang, scale, darkmode, bg == "1"))
        if grain == "year":
            start = dt.date(year, 1, 1); end = dt.date(year + 1, 1, 1)
            return _render_svg(key, lambda: build_svg(year, source.daily_tokens_in_range(start, end), theme, lang, scale, darkmode, bg == "1"))
        if grain == "month":
            start = dt.date(year, month, 1)
            end = dt.date(year + 1, 1, 1) if month == 12 else dt.date(year, month + 1, 1)
            return _render_svg(key, lambda: build_month_svg(year, month, source.daily_tokens_in_range(start, end), theme, lang, scale, darkmode, bg == "1"))
        day_date = dt.date(year, month, day)
        return _render_svg(key, lambda: build_day_svg(year, month, day, source.hourly_tokens(day_date), theme, lang, scale, darkmode, bg == "1"))
    except Exception:  # noqa: BLE001
        logger.exception("读取 token 热力图数据失败")
        raise HTTPException(status_code=502, detail="db error") from None

@app.get("/token/", response_class=HTMLResponse)
def config_page() -> str:
    """返回参数式嵌入链接配置页。"""
    theme_options = "".join(f"<option>{html.escape(name)}</option>" for name in get_themes())
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Token 用量热力图</title><style>body{font:14px sans-serif;max-width:760px;margin:40px auto}label{margin:8px;display:inline-block}input,select,button,textarea{padding:6px}textarea{display:block;width:100%;height:64px}img{display:block;max-width:100%;margin:20px 0}</style><h1>Token 用量热力图</h1><label><input type="radio" name="grain" value="auto" checked>最近一年</label><label><input type="radio" name="grain" value="year">年</label><label><input type="radio" name="grain" value="month">月</label><label><input type="radio" name="grain" value="day">日</label><label>主题 <select id="theme">__THEME_OPTIONS__</select></label><label>深浅 <select id="darkmode"><option value="auto">自动</option><option value="0">白天</option><option value="1">夜晚</option></select></label><label>背景 <select id="bg"><option value="0">透明</option><option value="1">主题色</option></select></label><label>语言 <select id="lang"><option value="zh">中文</option><option value="en">English</option></select></label><br><label>年份 <input id="year" type="number" min="2000" max="2100"></label><label>月份 <input id="month" type="number" min="1" max="12"></label><label>日期 <input id="day" type="number" min="1" max="31"></label>缩放 <input id="scale" type="number" min="0.1" max="10" step="0.1" value="1">（0.1-10x）</label><label><input id="current" type="checkbox" checked>使用当前日期</label><img id="preview"><textarea id="embed" readonly></textarea><button id="copy">复制嵌入代码</button><script>const q=s=>document.querySelector(s),now=new Date();for(const k of ['year','month','day'])q('#'+k).value=k==='year'?now.getFullYear():k==='month'?now.getMonth()+1:now.getDate();function render(){let g=q('input[name=grain]:checked').value,p=new URLSearchParams({theme:q('#theme').value,lang:q('#lang').value,grain:g,darkmode:q('#darkmode').value});let sc=parseFloat(q('#scale').value);if(sc>=0.1&&sc<=10&&sc!==1)p.set('scale',String(sc));if(q('#bg').value==='1')p.set('bg','1');if(g==='auto'){q('#year').disabled=q('#month').disabled=q('#day').disabled=true}else{q('#year').disabled=q('#month').disabled=q('#day').disabled=false;if(!q('#current').checked){p.set('year',q('#year').value);if(g!=='year')p.set('month',q('#month').value);if(g==='day')p.set('day',q('#day').value)}}let u='/token/@?'+p,full=location.origin+u;q('#preview').src=u;q('#embed').value='<img src="'+full+'" alt="Token 用量热力图">'}document.querySelectorAll('input,select').forEach(x=>x.oninput=render);q('#copy').onclick=()=>navigator.clipboard.writeText(q('#embed').value);render()</script>'''.replace("__THEME_OPTIONS__", theme_options)
