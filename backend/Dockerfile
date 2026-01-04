# Multi-stage Dockerfile for backend (dev and production targets)
# Uses Debian slim for PyTorch/ultralytics compatibility (Alpine's musl libc is incompatible)
#
# Usage:
#   docker build --target dev -t backend:dev .
#   docker build --target prod -t backend:prod .

# =============================================================================
# Base stage: shared Python setup with build dependencies
# =============================================================================
FROM python:3.14-slim-bookworm AS base

WORKDIR /app

# Install build dependencies for Python packages with C extensions
# and runtime dependencies for healthcheck and video processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libffi-dev \
    wget \
    curl \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

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

# Copy application code to backend subdirectory (for absolute imports)
COPY backend/ ./backend/

# Create data directory for logs and thumbnails
RUN mkdir -p /app/data/thumbnails /app/data/logs

# Create non-root user
RUN groupadd -g 1000 appgroup && \
    useradd -m -u 1000 -g appgroup appuser

# Change ownership of app directory to non-root user
RUN chown -R appuser:appgroup /app

# Add venv to PATH
ENV PATH=/app/.venv/bin:$PATH

# Expose FastAPI port
EXPOSE 8000

# Switch to non-root user
USER appuser

# Health check - use /ready endpoint to verify database/redis connectivity
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; exit(0 if httpx.get('http://localhost:8000/api/system/health/ready').status_code == 200 else 1)"

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
# =============================================================================
FROM python:3.14-slim-bookworm AS prod

WORKDIR /app

# Install runtime dependencies only (no build tools like gcc)
# wget for healthcheck, ffmpeg for video processing,
# libgl1 and libglib2.0-0 for OpenCV (required by ultralytics)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Copy Python virtual environment from builder (no dev deps, no build tools)
COPY --from=builder /app/.venv /app/.venv

# Copy application code to backend subdirectory (for absolute imports)
COPY backend/ ./backend/

# Create data directory for logs and thumbnails
RUN mkdir -p /app/data/thumbnails /app/data/logs

# Set ownership of app directories
RUN chown -R appuser:appuser /app

# Add venv to PATH
ENV PATH=/app/.venv/bin:$PATH

# Switch to non-root user
USER appuser

# Expose FastAPI port
EXPOSE 8000

# Health check - use /ready endpoint to verify database/redis connectivity
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; exit(0 if httpx.get('http://localhost:8000/api/system/health/ready').status_code == 200 else 1)"

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
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
