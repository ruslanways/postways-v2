FROM ghcr.io/astral-sh/uv:0.9.25 AS uv

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen

COPY app/ ./app/

RUN useradd --system --create-home --shell /usr/sbin/nologin appuser && \
    chown -R appuser:appuser /app /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
