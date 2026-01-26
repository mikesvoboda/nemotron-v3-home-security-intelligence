# Lightweight Enrichment Service (GPU 1 - A400 4GB)
# Hosts small, efficient models: pose, threat, reid, pet, depth
# Port: 8096 | Expected VRAM: ~1.2GB (with TensorRT optimization)

FROM docker.io/pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime

LABEL maintainer="home-security-intelligence"
LABEL description="Lightweight enrichment service for pose, threat, re-id, pet, and depth models"

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
COPY ai/enrichment-light/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-cache -r requirements.txt

# Install py-spy for continuous profiling
RUN uv tool install py-spy && \
    cp /root/.local/bin/py-spy /usr/local/bin/py-spy && \
    chmod +x /usr/local/bin/py-spy

# Copy profiler and entrypoint scripts
COPY --chmod=755 scripts/pyroscope-profiler.sh /usr/local/bin/pyroscope-profiler.sh
COPY --chmod=755 scripts/ai-entrypoint.sh /usr/local/bin/ai-entrypoint.sh

# Create non-root user for security
RUN groupadd -g 1000 enrichment && \
    useradd -u 1000 -g enrichment -s /bin/bash -m enrichment

# Copy application files
COPY ai/enrichment-light/*.py ./
COPY ai/enrichment-light/models/*.py ./models/
# Copy shared utilities from ai/ directory
COPY ai/torch_optimizations.py ./

# Environment variables
ENV HOST=0.0.0.0
ENV PORT=8096
# Light model paths
ENV POSE_MODEL_PATH=/models/yolov8n-pose/yolov8n-pose.pt
ENV THREAT_MODEL_PATH=/models/threat-detection-yolov8n/weights/best.pt
ENV REID_MODEL_PATH=/models/osnet-x0-25/osnet_x0_25.pth
ENV PET_MODEL_PATH=/models/pet-classifier
ENV DEPTH_MODEL_PATH=/models/depth-anything-v2-small
# HuggingFace cache configuration (NEM-3812)
ENV HF_HOME=/cache/huggingface
ENV HF_HUB_CACHE=/cache/huggingface/hub
ENV TRANSFORMERS_CACHE=/cache/huggingface
ENV HF_HUB_DISABLE_TELEMETRY=1
# TensorRT acceleration for YOLO models
ENV POSE_USE_TENSORRT=${POSE_USE_TENSORRT:-true}
ENV THREAT_USE_TENSORRT=${THREAT_USE_TENSORRT:-true}
# TensorRT engine cache directory (writable for non-root user)
ENV TENSORRT_ENGINE_CACHE=/cache/tensorrt
ENV POSE_TENSORRT_ENGINE_PATH=/cache/tensorrt/yolov8n-pose.engine
ENV THREAT_TENSORRT_ENGINE_PATH=/cache/tensorrt/threat-detector.engine

# Create cache directories for HuggingFace and TensorRT engines
RUN mkdir -p /cache/huggingface /cache/tensorrt && chown -R enrichment:enrichment /cache

# Set ownership of app directory
RUN chown -R enrichment:enrichment /app

# Expose port
EXPOSE 8096

# Switch to non-root user
USER enrichment

# Health check using Python/httpx on /health endpoint
# Start period of 90s allows time for loading models
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8096/health'); r.raise_for_status()"

# Use entrypoint for optional profiling
ENTRYPOINT ["/usr/local/bin/ai-entrypoint.sh"]

# Run the server
CMD ["python", "model.py"]
