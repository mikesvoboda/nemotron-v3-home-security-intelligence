# CLIP Embedding Server
# Uses HuggingFace Transformers for model loading with optional TensorRT inference
# Port: 8093 | Expected VRAM: ~800MB (PyTorch) / ~600MB (TensorRT)

FROM nvcr.io/nvidia/tensorrt:25.12-py3

LABEL maintainer="home-security-intelligence"
LABEL description="CLIP ViT-L embedding server for entity re-identification"

# System dependencies for image processing and utilities
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
COPY ai/clip/requirements.txt .
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
RUN groupadd -g 1000 clip && \
    useradd -u 1000 -g clip -s /bin/bash -m clip

# Copy application files
COPY ai/clip/model.py .
COPY ai/clip/tensorrt_inference.py .
COPY ai/clip/export_onnx.py .

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

# Create cache directories for HuggingFace models and TensorRT engines
RUN mkdir -p /cache/huggingface /cache/tensorrt && \
    chown -R clip:clip /cache/huggingface /cache/tensorrt

# Set ownership of app directory
RUN chown -R clip:clip /app

# Expose port
EXPOSE 8093

# Switch to non-root user
USER clip

# Health check using Python/httpx on /health endpoint
# Start period of 300s allows time for model loading and TensorRT auto-export on first run
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8093/health'); r.raise_for_status()"

# Use entrypoint for optional profiling
ENTRYPOINT ["/usr/local/bin/ai-entrypoint.sh"]

# Run the server
CMD ["python", "model.py"]
