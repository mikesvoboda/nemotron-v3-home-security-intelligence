# syntax=docker/dockerfile:1
# VLM service Dockerfile - llama.cpp llama-server with CUDA, aarch64, GB300 (sm_103)
#
# agent-gpu Containerfile contract (violations are refused before any build):
#   - every FROM needs an explicit registry (docker.io/...) - "Builds never pull:
#     pull base images first, with `agent-gpu pull <registry>/<image>` for every
#     FROM and COPY --from, before building."
#   - "A Containerfile may not put flags on RUN (--mount= included) and may not
#     use ONBUILD" -> unlike ai/nemotron/Dockerfile there is NO --mount=type=cache
#     here (that is buildah 1.33.7, which "cannot be trusted to check one").
#
# Build (after `agent-gpu pull` of BOTH base images below):
#   agent-gpu build --context workspace:ai/vlm --tag ai-vlm:sm103 \
#       --build-arg CUDA_ARCHITECTURES=103

# =============================================================================
# Stage 1: Builder - compile llama.cpp for GB300 sm_103 (compute capability 10.3)
# =============================================================================
FROM docker.io/nvidia/cuda:13.3.1-devel-ubuntu22.04 AS builder

# apt cmake is 3.22.1 on jammy: verified to configure+build CUDA arch 103 against
# nvcc 13.3 (CMake >= 3.18 only requires numeric archs; nvcc does the real check).
# ccache is intentionally NOT installed: its cache mount was not allowed by agent-gpu.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    cmake \
    build-essential \
    libcurl4-openssl-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
# ggml-org is the current home (org moved from ggerganov; the redirect resolves inside
# the build container too, but use the canonical URL).
RUN git clone https://github.com/ggml-org/llama.cpp.git
WORKDIR /build/llama.cpp
# Pin rationale: compiling FOR sm_103 (CC 10.3, GB300) is nvcc's job, not llama.cpp's
# - an explicit -DCMAKE_CUDA_ARCHITECTURES=103 configures cleanly at b7972 (verified
# in-container with the exact flags below and apt cmake 3.22.1). No newer pin is
# required to compile sm_103; bump to a recent release (e.g. b11090, 2026-09-21,
# verified to exist) via --build-arg LLAMA_CPP_REF=... for newer VLM/mmproj features.
# NOTE for every pin through HEAD (b11165): ggml gates the Blackwell tensor-core MMA
# path on __CUDA_ARCH__ >= 1200 (sm_120); a GB300 (cc 1030) compiles/runs the
# Ampere/Turing MMA + cuBLAS paths (common.cuh at b7972 AND b11165 verified).
ARG LLAMA_CPP_REF=b7972
RUN git checkout "${LLAMA_CPP_REF}"

# CUDA stubs for build-time linking; the real libcuda.so.1 is driver-injected at run
# time (verified present under /lib/aarch64-linux-gnu in a GPU container).
RUN ln -s /usr/local/cuda/lib64/stubs/libcuda.so /usr/local/cuda/lib64/stubs/libcuda.so.1 && \
    cp /usr/local/cuda/lib64/stubs/libcuda.so /usr/local/cuda/lib64/libcuda.so && \
    ln -s /usr/local/cuda/lib64/libcuda.so /usr/local/cuda/lib64/libcuda.so.1 && \
    ldconfig

# Single-arch build for this host's GPU: 103 == sm_103 (verified: nvcc 13.3 emits
# -gencode arch=compute_103,code=sm_103 and the binary runs on GB300, driver 610.57.04).
# ONE Dockerfile, two hosts (Phase 1.2 scope call - no per-host fork): the arch
# is a build-arg, so GB300 dev passes CUDA_ARCHITECTURES=103 (aarch64) and the
# A5500 bring-up (1.7) passes 86 (sm_86, x86) to THIS context unchanged.
# GGML_NATIVE=ON is safe when CMAKE_CUDA_ARCHITECTURES is set explicitly (b7972's
# GGML_NATIVE block only substitutes arches when the var is NOT DEFINED; configure
# with these exact flags at b7972 succeeded in-container).
ARG CUDA_ARCHITECTURES=""
# hadolint ignore=SC2046
RUN CUDA_ARCH_FLAG=""; \
    if [ -n "${CUDA_ARCHITECTURES}" ]; then \
        CUDA_ARCH_FLAG="-DCMAKE_CUDA_ARCHITECTURES=${CUDA_ARCHITECTURES}"; \
        echo "Building for GPU compute capability: ${CUDA_ARCHITECTURES}"; \
    else \
        echo "Building for default llama.cpp architectures"; \
    fi && \
    cmake -B build \
    -DGGML_CUDA=ON \
    -DGGML_CUDA_FA_ALL_QUANTS=ON \
    -DGGML_NATIVE=ON \
    ${CUDA_ARCH_FLAG} \
    -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build --config Release --target llama-server -j"$(nproc)"

# =============================================================================
# Stage 2: Runtime - minimal image with the server binary
# (runtime-ubuntu22.04 already ships libcublas/libcublasLt/libcudart/libnvrtc 13.x
#  for sbsa-linux - verified in the pulled arm64 image)
# =============================================================================
FROM docker.io/nvidia/cuda:13.3.1-runtime-ubuntu22.04

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1000 llama && \
    useradd -u 1000 -g llama -s /bin/bash -m llama

COPY --from=builder /build/llama.cpp/build/bin/llama-server /usr/local/bin/llama-server
COPY --from=builder /build/llama.cpp/build/bin/*.so* /usr/local/lib/
RUN chmod +x /usr/local/bin/llama-server && ldconfig

# Model weights are mounted read-only from $AGENT_GPU_DIR/models (agent-gpu run
# --mount models:/models); the service never downloads weights.
ENV MODEL_PATH=/models/vlm/model.gguf
# Must stay UNSET at build time: the runtime CMD tests it with `[ -n "" ]`, which
# fails only when it is empty. A built-in default would silently turn multimodal
# on for text-only runs (and vice versa, an unset one here makes the test useless).
ENV MMPROJ_PATH=
# Spec section 2 flags, same unset-at-build doctrine (compose sets real values):
# MODEL_ALIAS names the model in the REST API (/props, /v1/models) so
# provenance records what actually served; empty = llama.cpp's own default.
ENV MODEL_ALIAS=
# SLEEP_IDLE_SECONDS: llama.cpp sleep mode - after this many idle seconds the
# weights go to CPU RAM and VRAM is released to other residents (spec section 2's
# residency mechanism; 1.4 layers control on top). Empty = never sleep.
ENV SLEEP_IDLE_SECONDS=
# 8098: the container-side port is FIXED to match the compose contract
# (host-side AI_VLM_PORT is a separate mapping; internal URL = ai-vlm:8098).
ENV PORT=8098
ENV GPU_LAYERS=99
ENV CTX_SIZE=8192
ENV PARALLEL=1
ENV FLASH_ATTENTION=true
ENV THREADS=8
ENV BATCH_SIZE=2048
ENV UBATCH_SIZE=512

EXPOSE 8098

RUN mkdir -p /models && chown -R llama:llama /models

USER llama

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["sh", "-c", "FLASH_ARGS=''; \
    if [ \"${FLASH_ATTENTION}\" = 'true' ]; then FLASH_ARGS='--flash-attn on'; fi; \
    MM_ARGS=''; \
    if [ -n \"${MMPROJ_PATH}\" ]; then MM_ARGS=\"--mmproj ${MMPROJ_PATH}\"; fi; \
    ALIAS_ARGS=''; \
    if [ -n \"${MODEL_ALIAS}\" ]; then ALIAS_ARGS=\"--alias ${MODEL_ALIAS}\"; fi; \
    SLEEP_ARGS=''; \
    if [ -n \"${SLEEP_IDLE_SECONDS}\" ]; then SLEEP_ARGS=\"--sleep-idle-seconds ${SLEEP_IDLE_SECONDS}\"; fi; \
    llama-server \
    --model ${MODEL_PATH} \
    ${MM_ARGS} \
    ${ALIAS_ARGS} \
    ${SLEEP_ARGS} \
    --host 0.0.0.0 \
    --port ${PORT} \
    --n-gpu-layers ${GPU_LAYERS} \
    --ctx-size ${CTX_SIZE} \
    --parallel ${PARALLEL} \
    --threads ${THREADS} \
    --threads-batch ${THREADS} \
    --batch-size ${BATCH_SIZE} \
    --ubatch-size ${UBATCH_SIZE} \
    --cont-batching \
    --metrics \
    --cache-reuse 256 \
    --jinja \
    ${FLASH_ARGS}"]
