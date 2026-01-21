# Combined Enrichment Service
# Hosts Vehicle Classification, Pet Classification, FashionCLIP, YOLOv8 Pose, and OSNet Re-ID models
# Port: 8094 | Expected VRAM: ~3.5GB (with new models)

FROM docker.io/pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime

LABEL maintainer="home-security-intelligence"
LABEL description="Combined enrichment service for vehicle, pet, clothing, pose detection, and re-identification"

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
# httpx is now included in requirements.txt for health checks
COPY ai/enrichment/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-cache -r requirements.txt

# Install py-spy for continuous profiling
RUN uv tool install py-spy && ln -s /root/.local/bin/py-spy /usr/local/bin/py-spy

# Copy profiler and entrypoint scripts
COPY --chmod=755 scripts/pyroscope-profiler.sh /usr/local/bin/pyroscope-profiler.sh
COPY --chmod=755 scripts/ai-entrypoint.sh /usr/local/bin/ai-entrypoint.sh

# Create non-root user for security
RUN groupadd -g 1000 enrichment && \
    useradd -u 1000 -g enrichment -s /bin/bash -m enrichment

# Copy application files (all Python modules)
COPY ai/enrichment/*.py ./

# Environment variables
ENV HOST=0.0.0.0
ENV PORT=8094
ENV VEHICLE_MODEL_PATH=/models/vehicle-segment-classification
ENV PET_MODEL_PATH=/models/pet-classifier
ENV CLOTHING_MODEL_PATH=/models/fashion-clip
ENV POSE_MODEL_PATH=/models/yolov8-pose
ENV THREAT_CLASSIFIER_PATH=/models/threat-classifier
ENV REID_MODEL_PATH=/models/osnet-reid
ENV HF_HOME=/cache/huggingface

# Create cache directory for HuggingFace models
RUN mkdir -p /cache/huggingface && chown -R enrichment:enrichment /cache/huggingface

# Set ownership of app directory
RUN chown -R enrichment:enrichment /app

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
