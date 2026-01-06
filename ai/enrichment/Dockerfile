# Combined Enrichment Service
# Hosts Vehicle Classification, Pet Classification, and FashionCLIP models
# Port: 8094 | Expected VRAM: ~2.5GB

FROM docker.io/pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime

# OCI labels for security and metadata
LABEL org.opencontainers.image.title="Enrichment Service"
LABEL org.opencontainers.image.description="Combined enrichment service for vehicle, pet, and clothing classification"
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
RUN groupadd -g 1000 enrichment && \
    useradd -u 1000 -g enrichment -s /bin/bash -m enrichment

# Copy application files
COPY model.py .

# Environment variables
ENV HOST=0.0.0.0
ENV PORT=8094
ENV VEHICLE_MODEL_PATH=/models/vehicle-segment-classification
ENV PET_MODEL_PATH=/models/pet-classifier
ENV CLOTHING_MODEL_PATH=/models/fashion-clip
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
# Start period of 180s allows time for loading all three models
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8094/health'); r.raise_for_status()"

# Run the server
CMD ["python", "model.py"]
