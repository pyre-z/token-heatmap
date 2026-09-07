"""FastAPI routes for the token heatmap service."""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

try:  # container starts ``uvicorn main:app`` from /app
    from heatmap import build_svg
    from repository import fetch_daily_tokens
except ModuleNotFoundError:  # root-side tests import ``app.main``
    from .heatmap import build_svg
    from .repository import fetch_daily_tokens

logger = logging.getLogger(__name__)
app = FastAPI(title="Token Heatmap", docs_url=None, redoc_url=None)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/token/{filename}")
def token_svg(filename: str) -> Response:
    if not (filename.endswith(".svg") and filename[:-4].isdigit()):
        raise HTTPException(status_code=404, detail="not found")
    year = int(filename[:-4])
    if not 2000 <= year <= 2100:
        raise HTTPException(status_code=404, detail="not found")
    try:
        daily = fetch_daily_tokens(year)
    except Exception:  # noqa: BLE001 - driver errors vary by deployment
        logger.exception("Failed to fetch token heatmap data for year %d", year)
        raise HTTPException(status_code=502, detail="db error") from None
    return Response(content=build_svg(year, daily), media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=600"})
