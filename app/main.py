"""Token 热力图服务的 FastAPI 路由。"""
from __future__ import annotations

import datetime as dt
import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, Response

try:
    from cache import cache_get, cache_set
    from heatmap import THEMES, build_day_svg, build_month_svg, build_svg, shanghai_today
    from repository import fetch_daily_tokens, fetch_daily_tokens_in_range, fetch_hourly_tokens, month_epoch_bounds
except ModuleNotFoundError:  # pragma: no cover
    from .cache import cache_get, cache_set
    from .heatmap import THEMES, build_day_svg, build_month_svg, build_svg, shanghai_today
    from .repository import fetch_daily_tokens, fetch_daily_tokens_in_range, fetch_hourly_tokens, month_epoch_bounds

logger = logging.getLogger(__name__)
app = FastAPI(title="Token Heatmap", docs_url=None, redoc_url=None)

def _invalid() -> None:
    raise HTTPException(status_code=400, detail="invalid parameter")

def _validate(grain: str, year: int | None, month: int | None, day: int | None, theme: str) -> tuple[int, int | None, int | None]:
    if theme not in THEMES or grain not in {"year", "month", "day"}: _invalid()
    today = shanghai_today()
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

def _render_svg(key: str, render: object) -> Response:
    """带 TTL 缓存的 SVG 渲染：命中直接返回，未命中渲染后写入缓存。DB 错误不缓存。"""
    cached = cache_get(key)
    if cached is not None:
        return _svg_response(cached)
    svg = render()  # type: ignore[operator]
    cache_set(key, svg)
    return _svg_response(svg)

@app.get("/token/@")
def token_svg(grain: str = "year", year: str | None = Query(None), month: str | None = Query(None), day: str | None = Query(None), theme: str = "github", lang: str = "zh", scale: str = "1") -> Response:
    """根据 grain 粒度生成年度、月度或日度 SVG。scale 控制缩放（0.1-10）。"""
    try:
        year, month, day = (int(value) if value is not None else None for value in (year, month, day))
        scale = float(scale)
    except ValueError:
        _invalid()
    if not 0.1 <= scale <= 10:
        _invalid()
    year, month, day = _validate(grain, year, month, day, theme)
    lang = lang if lang in {"zh", "en"} else "zh"
    key = f"{grain}|{year}|{month}|{day}|{theme}|{lang}|{scale:g}"
    try:
        if grain == "year":
            return _render_svg(key, lambda: build_svg(year, fetch_daily_tokens(year), theme, lang, scale))
        if grain == "month":
            return _render_svg(key, lambda: build_month_svg(year, month, fetch_daily_tokens_in_range(*month_epoch_bounds(year, month)), theme, lang, scale))
        return _render_svg(key, lambda: build_day_svg(year, month, day, fetch_hourly_tokens(year, month, day), theme, lang, scale))
    except Exception:  # noqa: BLE001
        logger.exception("读取 token 热力图数据失败")
        raise HTTPException(status_code=502, detail="db error") from None

@app.get("/token/", response_class=HTMLResponse)
def config_page() -> str:
    """返回参数式嵌入链接配置页。"""
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Token 用量热力图</title><style>body{font:14px sans-serif;max-width:760px;margin:40px auto}label{margin:8px;display:inline-block}input,select,button,textarea{padding:6px}textarea{display:block;width:100%;height:64px}img{display:block;max-width:100%;margin:20px 0}</style><h1>Token 用量热力图</h1><label><input type="radio" name="grain" value="year" checked>年</label><label><input type="radio" name="grain" value="month">月</label><label><input type="radio" name="grain" value="day">日</label><label>主题 <select id="theme"><option>github</option><option>github-dark</option></select></label><label>语言 <select id="lang"><option value="zh">中文</option><option value="en">English</option></select></label><br><label>年份 <input id="year" type="number" min="2000" max="2100"></label><label>月份 <input id="month" type="number" min="1" max="12"></label><label>日期 <input id="day" type="number" min="1" max="31"></label>缩放 <input id="scale" type="number" min="0.1" max="10" step="0.1" value="1">（0.1-10x）</label><label><input id="current" type="checkbox" checked>使用当前日期</label><img id="preview"><textarea id="embed" readonly></textarea><button id="copy">复制嵌入代码</button><script>const q=s=>document.querySelector(s),now=new Date();for(const k of ['year','month','day'])q('#'+k).value=k==='year'?now.getFullYear():k==='month'?now.getMonth()+1:now.getDate();function render(){let g=q('input[name=grain]:checked').value,p=new URLSearchParams({theme:q('#theme').value,lang:q('#lang').value,grain:g});let sc=parseFloat(q('#scale').value);if(sc>=0.1&&sc<=10&&sc!==1)p.set('scale',String(sc));if(!q('#current').checked){p.set('year',q('#year').value);if(g!=='year')p.set('month',q('#month').value);if(g==='day')p.set('day',q('#day').value)}let u='/token/@?'+p,full=location.origin+u;q('#preview').src=u;q('#embed').value='<img src="'+full+'" alt="Token 用量热力图">'}document.querySelectorAll('input,select').forEach(x=>x.oninput=render);q('#copy').onclick=()=>navigator.clipboard.writeText(q('#embed').value);render()</script>'''
