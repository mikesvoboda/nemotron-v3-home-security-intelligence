FROM nvcr.io/nvidia/tritonserver:26.01-py3

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends libxcb1 libgl1 && \
    rm -rf /var/lib/apt/lists/*

# Install gateway + model export dependencies
# Note: packaging must be force-reinstalled (Triton base has system version pip skips)
# PyTorch/transformers/ultralytics needed for model export pipeline (export_all.sh)
# Triton 26.01 ships stale numpy-1.26.4.dist-info with broken metadata that prevents
# transformers from detecting numpy version.  Remove it before installing numpy.
#
# Uses BuildKit cache mount to cache pip downloads between builds (~5-10x faster rebuilds)
# Cache persists even when using --no-cache flag (only image layers are rebuilt)
# hadolint ignore=DL3013,SC2102
RUN --mount=type=cache,target=/root/.cache/pip,sharing=shared \
    rm -rf /usr/local/lib/python3.12/dist-packages/numpy-1.26.4.dist-info && \
    pip install --force-reinstall packaging numpy && \
    pip install \
    fastapi \
    uvicorn[standard] \
    "tritonclient[grpc]" \
    pillow \
    prometheus-client \
    httpx \
    python-multipart \
    torch \
    transformers \
    ultralytics \
    onnx \
    onnxscript \
    onnxruntime-gpu \
    open_clip_torch \
    timm \
    einops

# Copy gateway application code
COPY ai/gateway/ /app/gateway/

# Ensure the gateway package is importable
# The adapters import from ai.gateway.*, so we create the package structure
RUN mkdir -p /app/ai/gateway && \
    cp -r /app/gateway/* /app/ai/gateway/ && \
    touch /app/ai/__init__.py /app/ai/gateway/__init__.py

# Copy Triton model repository
COPY ai/triton/model_repository/ /models/repository/

# Copy entrypoint script
COPY ai/gateway/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Environment configuration
ENV TRITON_MODEL_REPOSITORY=/models/repository
ENV GATEWAY_PORT=8090
ENV TRITON_GRPC_URL=localhost:8001
ENV TRITON_HTTP_URL=http://localhost:8000
ENV TRITON_METRICS_URL=http://localhost:8002
ENV PYTHONPATH=/app

# The gateway listens on 8090; Triton gRPC on 8001, HTTP on 8000, metrics on 8002
# Only 8090 is exposed externally
EXPOSE 8090

ENTRYPOINT ["/entrypoint.sh"]
