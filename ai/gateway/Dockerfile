ARG TRITON_IMAGE=nvcr.io/nvidia/tritonserver:26.09-py3
FROM ${TRITON_IMAGE}

# Resolve dependencies on the same import path the application uses. Newer
# bases expose DALI-only packages that disappear when PYTHONPATH becomes /app.
# (O2.5 venue fix, ruling 287 item 7: the maui venue builds this image on the
# Triton 26.09 arm64 base by digest via --build-arg TRITON_IMAGE=..., and its
# pip installs must see /app from the first RUN, not only after the last ENV.)
ENV PYTHONPATH=/app

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends libxcb1 libgl1 && \
    rm -rf /var/lib/apt/lists/*

# Install gateway runtime + surviving export dependencies (setup_lib/deploy_phases.py
# runs export_all.sh and scripts/uplevel/reid_real_tier.sh runs export_reid.py and
# stage_probe.py inside this image; O3.1 stripped the 4 packages only the deleted
# export scripts used: transformers, open_clip_torch, timm, einops).
# Note: packaging must be force-reinstalled (Triton base has system version pip skips)
# Triton 26.01 ships stale numpy-1.26.4.dist-info with broken metadata; remove
# it before installing numpy.
#
# NO cache mount here, on purpose: this image is built by `agent-gpu build` for
# the O2.4 real tier (ruling 188), whose Containerfile contract refuses any flag
# on RUN ("--mount= included") and any ONBUILD -- the contract is transcribed at
# ai/vlm/Dockerfile:3-10, the file that dropped its own ccache mount the same way.
# What keeps pip's cache out of the layer instead is --no-cache-dir on both
# installs below, which is hadolint DL3042's own remedy ("Avoid use of cache
# directory with pip"). Pinned by:
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
    ultralytics \
    onnx \
    onnxscript \
    onnxruntime-gpu

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

# The gateway listens on 8090; Triton gRPC on 8001, HTTP on 8000, metrics on 8002
# Only 8090 is exposed externally
EXPOSE 8090

ENTRYPOINT ["/entrypoint.sh"]
