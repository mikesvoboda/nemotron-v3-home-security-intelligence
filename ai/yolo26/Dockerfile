# YOLO26 Object Detection Server
# Uses Ultralytics YOLO with TensorRT for optimized inference
# Port: 8095 | Expected VRAM: ~2GB

FROM nvcr.io/nvidia/tensorrt:24.09-py3

LABEL maintainer="home-security-intelligence"
LABEL description="YOLO26 TensorRT object detection server for home security monitoring"

# System dependencies for OpenCV and utilities
# procps for pgrep (needed by profiler)
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy and install Python dependencies
# Use BuildKit cache mount to cache uv downloads between builds (~5-10x faster)
COPY ai/yolo26/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-cache -r requirements.txt

# Add httpx for health check
# hadolint ignore=DL3059
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-cache httpx

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
