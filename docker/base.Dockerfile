# Shared Base Image for Python Services
# Contains common dependencies used across backend and AI services
# Reduces build time by caching common dependencies
#
# Usage:
#   docker build -f docker/base.Dockerfile -t ghcr.io/mikesvoboda/nemotron-base:latest .
#   docker push ghcr.io/mikesvoboda/nemotron-base:latest
#
# Services using this base image:
#   - backend (with FastAPI, SQLAlchemy, Redis, etc.)
#   - AI services (with FastAPI, httpx for health checks)

FROM python:3.14-slim-bookworm

# OCI Image Labels (org.opencontainers.image.*)
LABEL org.opencontainers.image.vendor="home-security-intelligence"
LABEL org.opencontainers.image.title="Python Base Image for Services"
LABEL org.opencontainers.image.description="Shared base image with common Python dependencies for home security services"
LABEL org.opencontainers.image.licenses="MPL-2.0"
LABEL org.opencontainers.image.source="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence"
LABEL org.opencontainers.image.documentation="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/docs"
LABEL org.opencontainers.image.authors="home-security-intelligence"
LABEL org.opencontainers.image.base.name="python:3.14-slim-bookworm"
LABEL org.opencontainers.image.base.digest="python:3.14-slim-bookworm"

WORKDIR /app

# Install build dependencies for Python packages with C extensions
# These are needed for packages like psycopg2, greenlet, etc.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy base requirements containing shared dependencies
COPY requirements-base.txt .

# Install base Python dependencies with BuildKit cache mount
# (~5-10x faster for rebuilds as we cache pip/uv downloads)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-cache -r requirements-base.txt
