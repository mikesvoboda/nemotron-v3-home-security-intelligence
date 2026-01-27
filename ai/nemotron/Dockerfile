# Nemotron LLM Service Dockerfile
# Multi-stage build for llama.cpp with CUDA support

# =============================================================================
# Stage 1: Builder - Compile llama.cpp with CUDA support
# =============================================================================
FROM docker.io/nvidia/cuda:13.1.1-devel-ubuntu22.04 AS builder

# Install build dependencies
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
RUN cmake -B build \
    -DGGML_CUDA=ON \
    -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build --config Release --target llama-server -j$(nproc)

# =============================================================================
# Stage 2: Runtime - Minimal image with just the server binary
# =============================================================================
FROM docker.io/nvidia/cuda:13.1.1-runtime-ubuntu22.04

# Install runtime dependencies
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

# Create model directory
RUN mkdir -p /models && chown llama:llama /models

# Environment variables for configuration
ENV MODEL_PATH=/models/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf
ENV PORT=8091
ENV GPU_LAYERS=35
ENV CTX_SIZE=131072
ENV PARALLEL=1

# Expose the service port
EXPOSE 8091

# Switch to non-root user
USER llama

# Health check with 120s start period for large model loading
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run llama-server with configuration
# Model is expected to be mounted at /models/
CMD ["sh", "-c", "llama-server \
    --model ${MODEL_PATH} \
    --host 0.0.0.0 \
    --port ${PORT} \
    --n-gpu-layers ${GPU_LAYERS} \
    --ctx-size ${CTX_SIZE} \
    --parallel ${PARALLEL} \
    --cont-batching \
    --metrics"]
