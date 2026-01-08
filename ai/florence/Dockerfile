# Florence-2 Vision-Language Server
# Uses HuggingFace Transformers for model loading and inference
# Port: 8092 | Expected VRAM: ~1.2GB

FROM docker.io/pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime

LABEL maintainer="home-security-intelligence"
LABEL description="Florence-2 vision-language server for attribute extraction"

# System dependencies for image processing and utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy and install Python dependencies
# Use BuildKit cache mount to cache uv downloads between builds (~5-10x faster)
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-cache -r requirements.txt

# Add httpx for health check
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-cache httpx

# Create non-root user for security
RUN groupadd -g 1000 florence && \
    useradd -u 1000 -g florence -s /bin/bash -m florence

# Copy application files
COPY model.py .

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

# Run the server
CMD ["python", "model.py"]
