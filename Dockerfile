FROM ghcr.io/astral-sh/uv:0.11.17 AS uv

FROM python:3.12-slim

COPY --from=uv /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0

COPY pyproject.toml uv.lock ./
RUN UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --frozen --no-dev

# 应用与默认主题随镜像分发：生产镜像可独立运行，不依赖宿主机 bind mount
COPY app ./app
COPY themes ./themes
ENV THEMES_DIR=/app/themes

# 以非 root 用户运行
RUN groupadd --system --gid 10001 appuser \
    && useradd --system --uid 10001 --gid appuser --create-home appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["/opt/venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
