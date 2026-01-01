# Development Dockerfile using Debian for PyTorch/ultralytics compatibility
# Note: Alpine uses musl libc which is incompatible with PyTorch and OpenCV
FROM python:3.14-slim-bookworm

WORKDIR /app

# Install build dependencies for Python packages with C extensions
# and runtime dependencies for healthcheck and video processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libffi-dev \
    wget \
    ffmpeg \
    curl \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files from project root (context is project root in CI)
COPY pyproject.toml uv.lock ./

# Install all dependencies including dev (for development container)
RUN uv sync --frozen --no-install-project

# Copy application code to backend subdirectory (for absolute imports)
# Context is project root, so we copy backend/ directory
COPY backend/ ./backend/

# Create data directory for logs and thumbnails
RUN mkdir -p /app/data

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
# Note: /ready is the canonical readiness probe (checks DB, Redis, pipeline workers)
# For simple liveness only, use /health instead
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; exit(0 if httpx.get('http://localhost:8000/api/system/health/ready').status_code == 200 else 1)"

# Run FastAPI with uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
