# Development Dockerfile using Alpine for smaller image and fewer CVEs
FROM python:3.12-alpine

WORKDIR /app

# Install build dependencies for Python packages with C extensions
# and runtime dependencies for healthcheck and video processing
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    wget \
    ffmpeg

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code to backend subdirectory (for absolute imports)
COPY . ./backend/

# Create data directory for logs and thumbnails
RUN mkdir -p /app/data

# Create non-root user
RUN addgroup -g 1000 appgroup && \
    adduser -D -u 1000 -G appgroup appuser

# Change ownership of app directory to non-root user
RUN chown -R appuser:appgroup /app

# Expose FastAPI port
EXPOSE 8000

# Switch to non-root user
USER appuser

# Health check - use /ready endpoint to verify database/redis connectivity
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; exit(0 if httpx.get('http://localhost:8000/api/system/health/ready').status_code == 200 else 1)"

# Run FastAPI with uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
