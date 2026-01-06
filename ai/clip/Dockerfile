# CLIP Embedding Server
# Uses HuggingFace Transformers for model loading and inference
# Port: 8093 | Expected VRAM: ~800MB

FROM docker.io/pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime

# OCI labels for security and metadata
LABEL org.opencontainers.image.title="CLIP Embedding Server"
LABEL org.opencontainers.image.description="CLIP ViT-L embedding server for entity re-identification"
LABEL org.opencontainers.image.vendor="home-security-intelligence"
LABEL org.opencontainers.image.source="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence"
LABEL org.opencontainers.image.licenses="MIT"
LABEL maintainer="home-security-intelligence"

# System dependencies for image processing and utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Add httpx for health check
RUN pip install --no-cache-dir httpx

# Create non-root user for security
RUN groupadd -g 1000 clip && \
    useradd -u 1000 -g clip -s /bin/bash -m clip

# Copy application files
COPY model.py .

# Environment variables
ENV HOST=0.0.0.0
ENV PORT=8093
ENV CLIP_MODEL_PATH=/models/clip-vit-l
ENV HF_HOME=/cache/huggingface

# Create cache directory for HuggingFace models
RUN mkdir -p /cache/huggingface && chown -R clip:clip /cache/huggingface

# Set ownership of app directory
RUN chown -R clip:clip /app

# Expose port
EXPOSE 8093

# Switch to non-root user
USER clip

# Health check using Python/httpx on /health endpoint
# Start period of 60s allows time for model loading (CLIP ViT-L is smaller than Florence)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8093/health'); r.raise_for_status()"

# Run the server
CMD ["python", "model.py"]
