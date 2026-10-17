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
#
# NO cache mount here, on purpose: this image is built by `agent-gpu build` for
# the O2.4 real tier (ruling 188), whose Containerfile contract refuses any flag
# on RUN ("--mount= included") and any ONBUILD -- the contract is transcribed at
# ai/vlm/Dockerfile:3-10, the file that dropped its own ccache mount the same way.
# Cost, stated: every build re-downloads the wheel set below (the mount bought
# "~5-10x faster rebuilds"). What keeps pip's cache out of the layer instead is
# --no-cache-dir on both installs below, which is hadolint DL3042's own remedy
# ("Avoid use of cache directory with pip"), so DL3042 left the ignore line when
# the flag went in. --no-cache-dir is a PIP argument, not an instruction flag, so
# the contract holds. Pinned by the test named in this file's header comment:
# ai/gateway/tests/test_dockerfile_agent_gpu_buildable.py
# hadolint ignore=DL3013,SC2102
RUN rm -rf /usr/local/lib/python3.12/dist-packages/numpy-1.26.4.dist-info && \
    pip install --no-cache-dir --force-reinstall packaging numpy && \
    pip install --no-cache-dir \
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

# Copy central model configuration (read by entrypoint.sh to export device env vars
# and by patch_triton_configs.py to rewrite Triton instance_group at startup)
COPY models.yml /app/models.yml
COPY ai/gateway/patch_triton_configs.py /app/patch_triton_configs.py

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
