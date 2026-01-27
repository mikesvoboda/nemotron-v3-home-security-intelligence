# Combined Enrichment Service (Multi-Stage Build)
# Hosts Vehicle Classification, Pet Classification, FashionCLIP, YOLOv8 Pose, OSNet Re-ID,
# and video analytics with Supervision (ByteTrack tracking, annotators, heatmaps)
# Port: 8094 | Expected VRAM: ~3.5GB (with new models)
#
# Build Optimizations:
#   - Multi-stage build separates build dependencies (uv, py-spy) from runtime
#   - Reduces runtime image size by excluding build tools
#   - BuildKit cache mounts for pip/uv cache (~5-10x faster rebuilds)
#
# Usage:
#   DOCKER_BUILDKIT=1 docker build -t ai-enrichment:latest .
#   podman-compose build ai-enrichment  # Automatically enables BuildKit

# =============================================================================
# Stage 1: Builder - Install dependencies and tools
# =============================================================================
FROM docker.io/pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime AS builder

# OCI Image Labels on builder stage
LABEL org.opencontainers.image.vendor="home-security-intelligence"
LABEL org.opencontainers.image.title="Enrichment Service (Builder)"
LABEL org.opencontainers.image.description="Builder stage for enrichment service"
LABEL org.opencontainers.image.licenses="MPL-2.0"

# System dependencies for image processing and utilities
# procps for pgrep (needed by profiler)
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy and install base dependencies first
# Use BuildKit cache mount to cache uv downloads between builds (~5-10x faster)
COPY requirements-base.txt .
RUN --mount=type=cache,target=/root/.cache/uv,sharing=shared \
    uv pip install --system --break-system-packages --no-cache -r requirements-base.txt

# Copy and install service-specific Python dependencies
# httpx is now included in requirements.txt for health checks
COPY ai/enrichment/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv,sharing=shared \
    uv pip install --system --break-system-packages --no-cache -r requirements.txt

# Install py-spy for continuous profiling
RUN uv tool install py-spy && \
    cp /root/.local/bin/py-spy /usr/local/bin/py-spy && \
    chmod +x /usr/local/bin/py-spy

# Copy profiler and entrypoint scripts
COPY --chmod=755 scripts/pyroscope-profiler.sh /usr/local/bin/pyroscope-profiler.sh
COPY --chmod=755 scripts/ai-entrypoint.sh /usr/local/bin/ai-entrypoint.sh

# Copy application files (all Python modules)
COPY ai/enrichment/*.py ./
COPY ai/enrichment/models/ ./models/
COPY ai/enrichment/utils/ ./utils/

# =============================================================================
# Stage 2: Runtime - Minimal image without build dependencies
# =============================================================================
FROM docker.io/pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime

# OCI Image Labels (org.opencontainers.image.*)
LABEL org.opencontainers.image.vendor="home-security-intelligence"
LABEL org.opencontainers.image.title="Enrichment Service"
LABEL org.opencontainers.image.description="Multi-model enrichment service for vehicle, pet, clothing, pose detection, and re-identification"
LABEL org.opencontainers.image.licenses="MPL-2.0"
LABEL org.opencontainers.image.source="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence"
LABEL org.opencontainers.image.documentation="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/docs"
LABEL org.opencontainers.image.authors="home-security-intelligence"
LABEL org.opencontainers.image.base.name="pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime"
LABEL org.opencontainers.image.base.digest="pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime"

# Additional service-specific labels
LABEL maintainer="home-security-intelligence"
LABEL com.example.service.name="enrichment-service"
LABEL com.example.service.port="8094"

# Install only runtime dependencies (curl and procps removed - not needed at runtime)
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user for security (same UID/GID as builder for permission compatibility)
RUN groupadd -g 1000 enrichment && \
    useradd -u 1000 -g enrichment -s /bin/bash -m enrichment

# Copy installed packages from builder (pytorch images use /opt/conda for Python)
COPY --from=builder --chown=enrichment:enrichment /opt/conda /opt/conda
COPY --from=builder --chown=enrichment:enrichment /app .

# Copy profiler tools and scripts
COPY --from=builder --chmod=755 /usr/local/bin/py-spy /usr/local/bin/py-spy
COPY --from=builder --chmod=755 /usr/local/bin/pyroscope-profiler.sh /usr/local/bin/pyroscope-profiler.sh
COPY --from=builder --chmod=755 /usr/local/bin/ai-entrypoint.sh /usr/local/bin/ai-entrypoint.sh

# Environment variables
ENV HOST=0.0.0.0
ENV PORT=8094
ENV VEHICLE_MODEL_PATH=/models/vehicle-segment-classification
ENV PET_MODEL_PATH=/models/pet-classifier
ENV CLOTHING_MODEL_PATH=/models/fashion-clip
ENV POSE_MODEL_PATH=/models/yolov8-pose
ENV THREAT_CLASSIFIER_PATH=/models/threat-classifier
ENV REID_MODEL_PATH=/models/osnet-reid
# HuggingFace cache configuration (NEM-3812)
# HF_HOME is the root directory, others are derived for backward compatibility
ENV HF_HOME=/cache/huggingface
ENV HF_HUB_CACHE=/cache/huggingface/hub
ENV TRANSFORMERS_CACHE=/cache/huggingface
ENV HF_HUB_DISABLE_TELEMETRY=1

# Create cache directory for HuggingFace models
RUN mkdir -p /cache/huggingface && chown -R enrichment:enrichment /cache/huggingface

# Expose port
EXPOSE 8094

# Switch to non-root user
USER enrichment

# Health check using Python/httpx on /health endpoint
# Start period of 180s allows time for loading all models (vehicle, pet, clothing, pose, re-id)
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8094/health'); r.raise_for_status()"

# Use entrypoint for optional profiling
ENTRYPOINT ["/usr/local/bin/ai-entrypoint.sh"]

# Run the server
CMD ["python", "model.py"]
