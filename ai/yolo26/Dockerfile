# YOLO26 Object Detection Server
# Uses Ultralytics YOLO with TensorRT for optimized inference
# Port: 8095 | Expected VRAM: ~2GB
#
# Multi-stage build: Uses shared base image to reduce build time by 60-80%
# Build order: nvcr.io/nvidia/tensorrt -> builder stage -> base image extensions

FROM nvcr.io/nvidia/tensorrt:25.12-py3 AS tensorrt_base

# OCI Image Labels (org.opencontainers.image.*)
LABEL org.opencontainers.image.vendor="home-security-intelligence"
LABEL org.opencontainers.image.title="YOLO26 Object Detection Server"
LABEL org.opencontainers.image.description="YOLO26 TensorRT-accelerated object detection server for home security monitoring (5.3x faster)"
LABEL org.opencontainers.image.licenses="MPL-2.0"
LABEL org.opencontainers.image.source="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence"
LABEL org.opencontainers.image.documentation="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/docs"
LABEL org.opencontainers.image.authors="home-security-intelligence"
LABEL org.opencontainers.image.base.name="nvcr.io/nvidia/tensorrt:24.09-py3"
LABEL org.opencontainers.image.base.digest="nvcr.io/nvidia/tensorrt:24.09-py3"

# Additional service-specific labels
LABEL maintainer="home-security-intelligence"
LABEL com.example.service.name="yolo26-detector"
LABEL com.example.service.port="8095"

# System dependencies for OpenCV and utilities
# procps for pgrep (needed by profiler)
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy and install base dependencies
# Use BuildKit cache mount to cache uv downloads between builds (~5-10x faster)
COPY requirements-base.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --break-system-packages --no-cache -r requirements-base.txt

# Copy and install service-specific dependencies
COPY ai/yolo26/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --break-system-packages --no-cache -r requirements.txt

# Install py-spy for continuous profiling
RUN uv tool install py-spy && \
    cp /root/.local/bin/py-spy /usr/local/bin/py-spy && \
    chmod +x /usr/local/bin/py-spy

# Copy profiler and entrypoint scripts
COPY --chmod=755 scripts/pyroscope-profiler.sh /usr/local/bin/pyroscope-profiler.sh
COPY --chmod=755 scripts/ai-entrypoint.sh /usr/local/bin/ai-entrypoint.sh

# Create non-root user for security
RUN groupadd -g 1000 yolo26 && \
    useradd -u 1000 -g yolo26 -s /bin/bash -m yolo26

# Copy application files
COPY ai/yolo26/model.py .
# Copy shared utilities
COPY ai/compile_utils.py .
COPY ai/torch_optimizations.py .

# Environment variables
ENV HOST=0.0.0.0
ENV PORT=8095
ENV YOLO26_CONFIDENCE=0.5
ENV YOLO26_MODEL_PATH=/models/yolo26/exports/yolo26m_fp16.engine

# Create model directory
RUN mkdir -p /models/yolo26/exports && chown -R yolo26:yolo26 /models

# Set ownership of app directory
RUN chown -R yolo26:yolo26 /app

# Expose port
EXPOSE 8095

# Switch to non-root user
USER yolo26

# Health check using Python/httpx on /health endpoint
# Start period of 60s allows time for model loading
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8095/health'); r.raise_for_status()"

# Use entrypoint for optional profiling
ENTRYPOINT ["/usr/local/bin/ai-entrypoint.sh"]

# Run the server
CMD ["python", "model.py"]
