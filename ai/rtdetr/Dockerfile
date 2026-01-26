# RT-DETRv2 Object Detection Server (Multi-Stage Build)
# Uses HuggingFace Transformers for model loading and inference
# Port: 8090 | Expected VRAM: ~3GB
#
# Build Optimizations:
#   - Multi-stage build separates build dependencies (uv, py-spy) from runtime
#   - Reduces runtime image size by excluding build tools
#   - BuildKit cache mounts for pip/uv cache (~5-10x faster rebuilds)
#
# Usage:
#   DOCKER_BUILDKIT=1 docker build -t ai-rtdetr:latest .
#   podman-compose build ai-detector  # Automatically enables BuildKit

# =============================================================================
# Stage 1: Builder - Install dependencies and tools
# =============================================================================
FROM docker.io/pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime AS builder

LABEL maintainer="home-security-intelligence"
LABEL description="RT-DETRv2 object detection server (builder stage)"

# Install build dependencies and utilities
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy and install Python dependencies
# Use BuildKit cache mount to cache uv downloads between builds (~5-10x faster)
COPY ai/rtdetr/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv,sharing=shared \
    uv pip install --system --no-cache -r requirements.txt

# Add httpx for health check (used by example_client.py)
# hadolint ignore=DL3059
RUN --mount=type=cache,target=/root/.cache/uv,sharing=shared \
    uv pip install --system --no-cache httpx

# Install py-spy for continuous profiling
RUN uv tool install py-spy && \
    cp /root/.local/bin/py-spy /usr/local/bin/py-spy && \
    chmod +x /usr/local/bin/py-spy

# Copy profiler and entrypoint scripts
COPY --chmod=755 scripts/pyroscope-profiler.sh /usr/local/bin/pyroscope-profiler.sh
COPY --chmod=755 scripts/ai-entrypoint.sh /usr/local/bin/ai-entrypoint.sh

# Copy application files
COPY ai/rtdetr/model.py .
COPY ai/rtdetr/example_client.py .

# =============================================================================
# Stage 2: Runtime - Minimal image without build dependencies
# =============================================================================
FROM docker.io/pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime

LABEL maintainer="home-security-intelligence"
LABEL description="RT-DETRv2 object detection server for home security monitoring"

# Install only runtime dependencies (no curl here, copied from builder)
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user for security (same UID/GID as builder for permission compatibility)
RUN groupadd -g 1000 rtdetr && \
    useradd -u 1000 -g rtdetr -s /bin/bash -m rtdetr

# Copy installed packages from builder (all Python packages are in /usr/local)
COPY --from=builder --chown=rtdetr:rtdetr /usr/local /usr/local
COPY --from=builder --chown=rtdetr:rtdetr /app .

# Copy profiler tools and scripts
COPY --from=builder --chmod=755 /usr/local/bin/py-spy /usr/local/bin/py-spy
COPY --from=builder --chmod=755 /usr/local/bin/pyroscope-profiler.sh /usr/local/bin/pyroscope-profiler.sh
COPY --from=builder --chmod=755 /usr/local/bin/ai-entrypoint.sh /usr/local/bin/ai-entrypoint.sh

# Environment variables
ENV HOST=0.0.0.0
ENV PORT=8090
ENV RTDETR_CONFIDENCE=0.5
# HuggingFace cache configuration (NEM-3812)
# HF_HOME is the root directory, others are derived for backward compatibility
ENV HF_HOME=/cache/huggingface
ENV HF_HUB_CACHE=/cache/huggingface/hub
ENV TRANSFORMERS_CACHE=/cache/huggingface
ENV HF_HUB_DISABLE_TELEMETRY=1

# Create cache directory for HuggingFace models
RUN mkdir -p /cache/huggingface && chown -R rtdetr:rtdetr /cache/huggingface

# Expose port
EXPOSE 8090

# Switch to non-root user
USER rtdetr

# Health check using Python/httpx on /health endpoint
# Start period of 60s allows time for model loading
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8090/health'); r.raise_for_status()"

# Use entrypoint for optional profiling
ENTRYPOINT ["/usr/local/bin/ai-entrypoint.sh"]

# Run the server
CMD ["python", "model.py"]
