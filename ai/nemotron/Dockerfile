# syntax=docker/dockerfile:1
# Nemotron LLM Service Dockerfile
# Multi-stage build for llama.cpp with CUDA support

# =============================================================================
# Stage 1: Builder - Compile llama.cpp with CUDA support
# =============================================================================
FROM docker.io/nvidia/cuda:13.1.1-devel-ubuntu22.04 AS builder

# Install build dependencies
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    cmake \
    build-essential \
    libcurl4-openssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Clone llama.cpp and checkout specific commit for stability
WORKDIR /build
RUN git clone https://github.com/ggerganov/llama.cpp.git
WORKDIR /build/llama.cpp
RUN git checkout 9496bbb80

# Build llama.cpp with CUDA support
# Set up CUDA stubs for linking (actual libcuda.so provided at runtime by driver)
# Create versioned symlink and copy stub to standard location
RUN ln -s /usr/local/cuda/lib64/stubs/libcuda.so /usr/local/cuda/lib64/stubs/libcuda.so.1 && \
    cp /usr/local/cuda/lib64/stubs/libcuda.so /usr/local/cuda/lib64/libcuda.so && \
    ln -s /usr/local/cuda/lib64/libcuda.so /usr/local/cuda/lib64/libcuda.so.1 && \
    ldconfig
# hadolint ignore=SC2046
RUN cmake -B build \
    -DGGML_CUDA=ON \
    -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build --config Release --target llama-server -j"$(nproc)"

# =============================================================================
# Stage 2: Runtime - Minimal image with just the server binary
# =============================================================================
FROM docker.io/nvidia/cuda:13.1.1-runtime-ubuntu22.04

# Install runtime dependencies
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -g 1000 llama && \
    useradd -u 1000 -g llama -s /bin/bash -m llama

# Copy the compiled binaries and shared libraries from builder stage
COPY --from=builder /build/llama.cpp/build/bin/llama-server /usr/local/bin/llama-server
COPY --from=builder /build/llama.cpp/build/bin/*.so* /usr/local/lib/
RUN chmod +x /usr/local/bin/llama-server && ldconfig

# Environment variables for configuration
# NEM-5528: MODEL_PATH is overridden at runtime via docker-compose environment.
# docker-compose.prod.yml passes: MODEL_PATH=${LLM_MODEL_PATH:-/models/...}
# This allows swapping quantizations (e.g., IQ4_XS vs Q4_K_M) without rebuilding.
# Set LLM_MODEL_PATH in .env to change the active quantization.
ENV MODEL_PATH=/models/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf
ENV PORT=8091
ENV GPU_LAYERS=35
# NEM-5369: Reduced default context size from 131072 to 32768 to save ~4GB VRAM
ENV CTX_SIZE=32768
ENV PARALLEL=2
# NEM-5369: Flash attention enabled by default to reduce VRAM usage
ENV FLASH_ATTENTION=true
# Thread count for CPU-offloaded layers (match container CPU limit)
ENV THREADS=4
# Batch sizes for prompt processing throughput
ENV BATCH_SIZE=2048
ENV UBATCH_SIZE=512
# KV cache quantization (Q8_0 saves ~50% KV memory with negligible quality loss)
# Only 6 of 52 layers are attention (rest are Mamba), so savings are modest (~192MB)
ENV CACHE_TYPE_K=q8_0
ENV CACHE_TYPE_V=q8_0
# MoE expert offloading: keep attention+Mamba on GPU, offload MoE FFN experts to CPU
# Experts are activated 6-of-128 per token, so CPU latency is minimal
ENV MOE_OFFLOAD_PATTERN=

# Expose the service port
EXPOSE 8091

# Create model directory as root and set ownership before switching user
RUN mkdir -p /models && chown -R llama:llama /models

# Switch to non-root user
USER llama

# Create model directory as non-root user (owns directory automatically)
RUN mkdir -p /models

# Health check with 120s start period for large model loading
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run llama-server with configuration
# Model is expected to be mounted at /models/
# NEM-5369: Conditionally enable flash attention for VRAM savings
CMD ["sh", "-c", "FLASH_ARGS=''; \
    if [ \"${FLASH_ATTENTION}\" = 'true' ]; then FLASH_ARGS='--flash-attn on'; fi; \
    MOE_ARGS=''; \
    if [ -n \"${MOE_OFFLOAD_PATTERN}\" ]; then MOE_ARGS=\"--override-tensor ${MOE_OFFLOAD_PATTERN}=CPU\"; fi; \
    llama-server \
    --model ${MODEL_PATH} \
    --host 0.0.0.0 \
    --port ${PORT} \
    --n-gpu-layers ${GPU_LAYERS} \
    --ctx-size ${CTX_SIZE} \
    --parallel ${PARALLEL} \
    --threads ${THREADS} \
    --threads-batch ${THREADS} \
    --batch-size ${BATCH_SIZE} \
    --ubatch-size ${UBATCH_SIZE} \
    --cache-type-k ${CACHE_TYPE_K} \
    --cache-type-v ${CACHE_TYPE_V} \
    --cont-batching \
    --metrics \
    ${FLASH_ARGS} \
    ${MOE_ARGS}"]
