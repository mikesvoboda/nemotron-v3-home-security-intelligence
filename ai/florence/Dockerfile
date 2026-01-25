# Florence-2 Vision-Language Server
# Uses HuggingFace Transformers for model loading and inference
# Port: 8092 | Expected VRAM: ~1.2GB

FROM docker.io/pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime

LABEL maintainer="home-security-intelligence"
LABEL description="Florence-2 vision-language server for attribute extraction"

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
COPY ai/florence/requirements.txt .
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
RUN groupadd -g 1000 florence && \
    useradd -u 1000 -g florence -s /bin/bash -m florence

# Copy application files
COPY ai/florence/model.py .
COPY ai/torch_optimizations.py .

# Environment variables
ENV HOST=0.0.0.0
ENV PORT=8092
ENV FLORENCE_MODEL_PATH=/models/florence-2-large
ENV HF_HOME=/cache/huggingface

# Create cache directory for HuggingFace models
RUN mkdir -p /cache/huggingface && chown -R florence:florence /cache/huggingface

# Set ownership of app directory
RUN chown -R florence:florence /app

# Expose port
EXPOSE 8092

# Switch to non-root user
USER florence

# Health check using Python/httpx on /health endpoint
# Start period of 120s allows time for model loading (Florence-2 is larger)
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8092/health'); r.raise_for_status()"

# Use entrypoint for optional profiling
ENTRYPOINT ["/usr/local/bin/ai-entrypoint.sh"]

# Run the server
CMD ["python", "model.py"]
