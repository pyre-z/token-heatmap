FROM ghcr.io/astral-sh/uv:0.11.17 AS uv

FROM python:3.12-slim

COPY --from=uv /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0

COPY pyproject.toml uv.lock ./
RUN UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --frozen --no-dev
