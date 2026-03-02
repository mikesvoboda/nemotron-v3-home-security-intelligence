# syntax=docker/dockerfile:1
# CLIP Embedding Server
# Uses HuggingFace Transformers for model loading with optional TensorRT inference
# Port: 8093 | Expected VRAM: ~800MB (PyTorch) / ~600MB (TensorRT)
#
# TensorRT Engine Pre-build (NEM-4999):
#   When CLIP_USE_TENSORRT=true, the TensorRT engine is exported on first startup
#   if not already present. Set CLIP_PREBUILD_ENGINE=true (default) to build the
#   engine during container startup before serving requests.
#   TensorRT engines are GPU-architecture-specific - rebuild for each target GPU.

FROM nvcr.io/nvidia/tensorrt:26.02-py3

LABEL maintainer="home-security-intelligence"
LABEL description="CLIP ViT-L embedding server for entity re-identification"

# System dependencies for image processing and utilities
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

# Copy and install Python dependencies
# Use BuildKit cache mount to cache uv downloads between builds (~5-10x faster)
COPY ai/clip/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --break-system-packages --no-cache -r requirements.txt

# Add httpx for health check
# hadolint ignore=DL3059
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --break-system-packages --no-cache httpx

# Install py-spy for continuous profiling
RUN uv tool install py-spy && \
    cp /root/.local/bin/py-spy /usr/local/bin/py-spy && \
    chmod +x /usr/local/bin/py-spy

# Copy profiler and entrypoint scripts
COPY --chmod=755 scripts/pyroscope-profiler.sh /usr/local/bin/pyroscope-profiler.sh
COPY --chmod=755 scripts/ai-entrypoint.sh /usr/local/bin/ai-entrypoint.sh

# Create non-root user for security (handle pre-existing GID/UID in NVIDIA images)
RUN (groupadd -g 1000 clip || true) && \
    (useradd -u 1000 -g 1000 -s /bin/bash -m clip || true)

# Copy application files with ownership set to non-root user
COPY --chown=1000:1000 ai/clip/model.py .
COPY --chown=1000:1000 ai/clip/tensorrt_inference.py .
COPY --chown=1000:1000 ai/clip/export_onnx.py .
COPY --chown=1000:1000 ai/clip/build_engine.py .
# Copy shared TensorRT pre-build utilities
COPY --chown=1000:1000 ai/tensorrt_prebuild.py .
COPY --chown=1000:1000 ai/gpu_oom_handler.py .

# Environment variables
ENV HOST=0.0.0.0
ENV PORT=8093
ENV CLIP_MODEL_PATH=/models/clip-vit-l
# HuggingFace cache configuration (NEM-3812)
# HF_HOME is the root directory, others are derived for backward compatibility
ENV HF_HOME=/cache/huggingface
ENV HF_HUB_CACHE=/cache/huggingface/hub
ENV TRANSFORMERS_CACHE=/cache/huggingface
ENV HF_HUB_DISABLE_TELEMETRY=1

# TensorRT environment variables (disabled by default)
# Set CLIP_USE_TENSORRT=true and CLIP_ENGINE_PATH to enable TensorRT
ENV CLIP_USE_TENSORRT=false
# CLIP_ENGINE_PATH is set via docker-compose when TensorRT is enabled

# Expose port
EXPOSE 8093

# Create cache directories as root and set ownership before switching user
RUN mkdir -p /cache/huggingface /cache/tensorrt && chown -R 1000:1000 /cache

# Switch to non-root user (use numeric UID for compatibility)
USER 1000

# Create cache directories for HuggingFace models and TensorRT engines as non-root user (owns directory automatically)
RUN mkdir -p /cache/huggingface /cache/tensorrt

# Health check using Python/httpx on /health endpoint
# Start period of 300s allows time for model loading and TensorRT auto-export on first run
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8093/health'); r.raise_for_status()"

# Use entrypoint for optional profiling
ENTRYPOINT ["/usr/local/bin/ai-entrypoint.sh"]

# Run the server
CMD ["python", "model.py"]
