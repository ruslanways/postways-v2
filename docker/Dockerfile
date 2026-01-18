# Use uv official image with pinned version
FROM ghcr.io/astral-sh/uv:0.9.25 AS uv

FROM python:3.12-slim

# Prevent Python from writing .pyc files and ensure output is unbuffered
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Put the project virtual environment outside /app so it isn't affected by bind mounts.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Install OS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Copy uv binary from official image
COPY --from=uv /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files first (better layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies into the project virtualenv as root during build
RUN uv sync --frozen

# Copy application code
COPY . .

# Create a non-root system user (no shell), and ensure app + venv are readable/writable
RUN useradd --system --create-home --home-dir /home/appuser --shell /usr/sbin/nologin --user-group appuser && \
    mkdir -p /app/staticfiles /app/logs /app/media /app/var && \
    chown -R appuser:appuser /app /home/appuser /opt/venv

# Ensure Python uses the project virtualenv by default.
ENV HOME=/home/appuser \
    PATH="/opt/venv/bin:$PATH"

# Switch to non-root user
USER appuser
