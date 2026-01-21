# Multi-stage Dockerfile for backend (dev and production targets)
# Uses Debian slim for PyTorch/ultralytics compatibility (Alpine's musl libc is incompatible)
#
# Security Features:
#   - Non-root user execution
#   - Minimal production image (no build tools)
#   - Health checks for container orchestration
#   - Read-only root filesystem compatible (mark volumes as needed)
#
# Usage:
#   docker build --target dev -t backend:dev .
#   docker build --target prod -t backend:prod .

# =============================================================================
# Base stage: shared Python setup with build dependencies
# Uses Python 3.14 (standard build)
# Note: Free-threaded Python (3.14t) is not yet available in official Docker images.
# The application will gracefully fall back to GIL-enabled mode.
# =============================================================================
FROM python:3.14-slim-bookworm AS base

# Security labels
LABEL org.opencontainers.image.vendor="home-security-intelligence"
LABEL org.opencontainers.image.title="Backend API Server"
LABEL org.opencontainers.image.description="FastAPI backend for home security monitoring"
LABEL org.opencontainers.image.licenses="MPL-2.0"
LABEL org.opencontainers.image.source="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence"

WORKDIR /app

# Install build dependencies for Python packages with C extensions
# and runtime dependencies for healthcheck and video processing
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libffi-dev \
    wget \
    curl \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files from project root (context is project root in CI)
COPY pyproject.toml uv.lock ./

# =============================================================================
# Development target: includes dev dependencies, has build tools
# =============================================================================
FROM base AS dev

# Install all dependencies including dev (for development container)
# Use BuildKit cache mount to cache uv downloads between builds (~5-10x faster)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Create non-root user before copying files (for COPY --chown)
RUN groupadd -g 1000 appgroup && \
    useradd -m -u 1000 -g appgroup -s /usr/sbin/nologin appuser

# Copy application code with proper ownership (avoids separate chown layer)
COPY --chown=appuser:appgroup backend/ ./backend/

# Create data directory for logs and thumbnails with proper ownership
RUN mkdir -p /app/data/thumbnails /app/data/logs && \
    chown -R appuser:appgroup /app/data /app/.venv

# Add venv to PATH
ENV PATH=/app/.venv/bin:$PATH

# Default API port (configurable via environment variable)
ENV API_PORT=8000

# Expose FastAPI port
EXPOSE 8000

# Switch to non-root user
USER appuser

# Health check - use /ready endpoint to verify database/redis connectivity
# Uses API_PORT environment variable for configurable port
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os, httpx; port=os.getenv('API_PORT', '8000'); exit(0 if httpx.get(f'http://localhost:{port}/api/system/health/ready').status_code == 200 else 1)"

# Use entrypoint script to run Alembic migrations before starting the server
# The entrypoint runs migrations with retry logic, then executes CMD
ENTRYPOINT ["/app/backend/entrypoint.sh"]

# Run FastAPI with uvicorn (hot reload enabled for dev)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# =============================================================================
# Builder stage: install production dependencies only
# =============================================================================
FROM base AS builder

# Install production dependencies only (no dev/test deps)
# Use BuildKit cache mount to cache uv downloads between builds (~5-10x faster)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# =============================================================================
# Production target: minimal runtime image without build tools
# Uses Python 3.14 (standard build)
# Note: Free-threaded Python (3.14t) is not yet available in official Docker images.
# The application will gracefully fall back to GIL-enabled mode.
# =============================================================================
FROM python:3.14-slim-bookworm AS prod

# Security labels
LABEL org.opencontainers.image.vendor="home-security-intelligence"
LABEL org.opencontainers.image.title="Backend API Server"
LABEL org.opencontainers.image.description="FastAPI backend for home security monitoring"
LABEL org.opencontainers.image.licenses="MPL-2.0"
LABEL org.opencontainers.image.source="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence"

WORKDIR /app

# Install runtime dependencies only (no build tools like gcc)
# ffmpeg for video processing, libgl1 and libglib2.0-0 for OpenCV (required by ultralytics)
# procps for pgrep (needed by profiler)
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    procps \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install py-spy for continuous profiling (pushes to Pyroscope)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN uv tool install py-spy && ln -s /root/.local/bin/py-spy /usr/local/bin/py-spy

# Copy profiler script
COPY --chmod=755 scripts/pyroscope-profiler.sh /usr/local/bin/pyroscope-profiler.sh

# Create non-root user for security (no login shell for additional security)
RUN useradd -m -u 1000 -s /usr/sbin/nologin appuser

# Copy Python virtual environment from builder (no dev deps, no build tools)
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code with proper ownership
COPY --chown=appuser:appuser backend/ ./backend/

# Create data directory for logs and thumbnails with proper ownership
RUN mkdir -p /app/data/thumbnails /app/data/logs && \
    chown -R appuser:appuser /app/data

# Add venv to PATH
ENV PATH=/app/.venv/bin:$PATH

# Default API port (configurable via environment variable)
ENV API_PORT=8000

# Switch to non-root user
USER appuser

# Expose FastAPI port
EXPOSE 8000

# Health check - use /ready endpoint to verify database/redis connectivity
# Uses API_PORT environment variable for configurable port
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os, httpx; port=os.getenv('API_PORT', '8000'); exit(0 if httpx.get(f'http://localhost:{port}/api/system/health/ready').status_code == 200 else 1)"

# ============================================================================
# IMPORTANT: Single Worker Requirement for In-Process Background Services
# ============================================================================
# This application runs background services (FileWatcher, PipelineWorkerManager,
# SystemBroadcaster) in the FastAPI lifespan context.
#
# Running multiple uvicorn workers (--workers > 1) would cause:
# - Duplicate file processing: Each worker starts its own FileWatcher
# - Race conditions: Multiple PipelineWorkerManagers processing the same queues
# - Duplicate WebSocket broadcasts: Multiple SystemBroadcasters sending duplicates
#
# For scaling beyond a single worker, extract background services to separate
# containers using: python -m backend.services.pipeline_workers
# See: backend/services/pipeline_workers.py for standalone worker mode.
# ============================================================================

# Use entrypoint script to run Alembic migrations before starting the server
# The entrypoint runs migrations with retry logic, then executes CMD
ENTRYPOINT ["/app/backend/entrypoint.sh"]

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
