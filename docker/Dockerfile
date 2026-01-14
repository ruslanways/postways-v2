# Use uv official image with pinned version
FROM ghcr.io/astral-sh/uv:0.9.25 AS uv

FROM python:3.12-slim

# Prevent Python from writing .pyc files and ensure output is unbuffered
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy uv binary from official image
COPY --from=uv /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files first (better layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies as root (before creating user)
RUN uv sync --frozen

# Copy application code
COPY . .

# Create non-root user, directories, and set permissions in one layer
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    mkdir -p staticfiles && \
    chown -R appuser:appuser .

# Switch to non-root user
USER appuser