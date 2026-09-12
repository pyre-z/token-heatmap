"""SVG 文档组装与底部图例/星期标签（自 heatmap.py 抽出）。

- svg_document：外层 <svg> 组装；darkmode=auto 时注入双套 CSS 变量
- weekday_labels：GitHub 风格左侧 周一/周三/周五（en: Mon/Wed/Fri）
- legend_html：右对齐图例（Less □□□□□ More）
"""
from __future__ import annotations

try:
    from config import CELL, GAP, LEVELS, PAD_TOP
except ModuleNotFoundError:  # pragma: no cover
    from .config import CELL, GAP, LEVELS, PAD_TOP


def svg_document(width: int, height: int, family: dict, mode: str, body: str, scale: float = 1.0, bg: bool = False) -> str:
    """组装 SVG。auto 模式注入双套 CSS 变量（默认 day，dark 系统切 night）。

    bg=True 时画全幅背景 rect（用主题 background 色；auto 模式用 var(--bg)，随系统深浅切换），
    bg=False（默认）背景透明不画底。
    """
    w, h = width * scale, height * scale
    style = ""
    rect = ""
    if mode == "auto":
        day, night = family["day"], family["night"]
        d = "".join(f"--c{i}:{day['colors'][i]};" for i in range(5)) + f"--tx:{day['text']};--tt:{day['title']};--lg:{day['legend']};--bg:{day['background']}"
        n = "".join(f"--c{i}:{night['colors'][i]};" for i in range(5)) + f"--tx:{night['text']};--tt:{night['title']};--lg:{night['legend']};--bg:{night['background']}"
        style = f"<style>:root{{{d}}}@media (prefers-color-scheme: dark){{:root{{{n}}}}}</style>"
        if bg:
            rect = '<rect width="100%" height="100%" fill="var(--bg)"/>'
    elif bg:
        pal = family["day"] if mode == "day" else family["night"]
        rect = f'<rect width="100%" height="100%" fill="{pal["background"]}"/>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}" height="{h:g}" viewBox="0 0 {width} {height}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">{style}{rect}{body}</svg>'


def weekday_labels(lang: str, pal: dict) -> str:
    """GitHub 风格：左侧只标注 周一/周三/周五 三行（周日开头 r=0，Mon/Wed/Fri 在 r=1/3/5）。"""
    if lang == "zh":
        day_labels = {1: "周一", 3: "周三", 5: "周五"}
    else:
        day_labels = {1: "Mon", 3: "Wed", 5: "Fri"}
    return "".join(
        f'<text x="16" y="{PAD_TOP+r*(CELL+GAP)+CELL//2+3}" font-size="9" fill="{pal["text"]}" text-anchor="middle">{label}</text>'
        for r, label in day_labels.items()
    )


def legend_html(width: int, ly: int, pal: dict, colors: list, lang_words: dict) -> str:
    """图例 HTML：整组右对齐到画布右缘留 ~12px（GitHub 风格：Less □□□□□ More）。"""
    more_text = lang_words["more"]
    less_text = lang_words["less"]
    right_edge = width - 12
    more_x = right_edge  # More 文字右端
    more_w = len(more_text) * 6.0 + 4  # 9px 字体：拉丁 ~5.5px/字符，CJK ~9px/字符，粗估偏宽
    legend_right = more_x - more_w  # 色块区右端
    legend_left = legend_right - LEVELS * 14  # 色块区左端
    legend = "".join(
        f'<rect x="{legend_left + i * 14}" y="{ly - 8}" width="10" height="10" rx="2" fill="{color}"/>'
        for i, color in enumerate(colors)
    )
    less_x = legend_left - 6  # Less 文字右端（锚 end）
    return (
        f'<text x="{less_x}" y="{ly}" font-size="9" fill="{pal["legend"]}" text-anchor="end">{less_text}</text>'
        f"{legend}"
        f'<text x="{more_x}" y="{ly}" font-size="9" fill="{pal["legend"]}" text-anchor="end">{more_text}</text>'
    )
