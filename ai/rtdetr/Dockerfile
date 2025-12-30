# RT-DETRv2 Object Detection Server
# Uses HuggingFace Transformers for model loading and inference
# Port: 8090 | Expected VRAM: ~3GB

FROM docker.io/pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime

LABEL maintainer="home-security-intelligence"
LABEL description="RT-DETRv2 object detection server for home security monitoring"

# System dependencies for OpenCV and utilities
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

# Add httpx for health check (used by example_client.py)
RUN pip install --no-cache-dir httpx

# Copy application files
COPY model.py .
COPY example_client.py .

# Environment variables
ENV HOST=0.0.0.0
ENV PORT=8090
ENV RTDETR_CONFIDENCE=0.5
ENV HF_HOME=/cache/huggingface

# Create cache directory for HuggingFace models
RUN mkdir -p /cache/huggingface

# Expose port
EXPOSE 8090

# Health check using Python/httpx on /health endpoint
# Start period of 60s allows time for model loading
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8090/health'); r.raise_for_status()"

# Run the server
CMD ["python", "model.py"]
