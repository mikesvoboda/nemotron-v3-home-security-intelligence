#!/bin/bash
# AI Gateway entrypoint script.
#
# Starts Triton Inference Server in the background, waits for it to become
# ready, then starts the FastAPI gateway with uvicorn. Handles SIGTERM for
# graceful shutdown of both processes.

set -e

TRITON_MODEL_REPO="${TRITON_MODEL_REPOSITORY:-/models/repository}"
GATEWAY_PORT="${GATEWAY_PORT:-8090}"
TRITON_HTTP_PORT=8000
TRITON_GRPC_PORT=8001
TRITON_METRICS_PORT=8002

# Track child PIDs for cleanup
TRITON_PID=""
GATEWAY_PID=""

cleanup() {
    echo "[entrypoint] Received shutdown signal, stopping services..."

    if [ -n "$GATEWAY_PID" ] && kill -0 "$GATEWAY_PID" 2>/dev/null; then
        echo "[entrypoint] Stopping gateway (PID $GATEWAY_PID)..."
        kill -TERM "$GATEWAY_PID" 2>/dev/null
        wait "$GATEWAY_PID" 2>/dev/null || true
    fi

    if [ -n "$TRITON_PID" ] && kill -0 "$TRITON_PID" 2>/dev/null; then
        echo "[entrypoint] Stopping Triton (PID $TRITON_PID)..."
        kill -TERM "$TRITON_PID" 2>/dev/null
        wait "$TRITON_PID" 2>/dev/null || true
    fi

    echo "[entrypoint] Shutdown complete."
    exit 0
}

trap cleanup SIGTERM SIGINT

# ---------------------------------------------------------------------------
# 0. Export per-model device settings from models.yml
# ---------------------------------------------------------------------------
# Triton Python backend workers (florence2, xclip_action) read their target
# device from environment variables.  models.yml is the single source of truth
# for which device each model should use.  We export those env vars here so
# the tritonserver subprocess inherits them.
#
# docker-compose / host env vars that are already set take precedence:
# the Python snippet only exports a variable if it is not already defined.

MODELS_YAML="${MODELS_YAML_PATH:-/app/models.yml}"
if [ -f "$MODELS_YAML" ]; then
    echo "[entrypoint] Exporting model device settings from models.yml..."
    while IFS= read -r line; do
        [ -n "$line" ] && eval "$line" && echo "[entrypoint]   $line"
    done < <(python3 -c "
import yaml, os, sys
try:
    with open('${MODELS_YAML}') as f:
        config = yaml.safe_load(f)
    for m in config.get('models', []):
        var = m.get('device_env_var')
        dev = m.get('device')
        if var and dev and var not in os.environ:
            print('export {}={}'.format(var, dev))
except Exception as e:
    print('echo [entrypoint] WARN: models.yml device export failed: {}'.format(e), file=sys.stderr)
" 2>/dev/null)
else
    echo "[entrypoint] WARN: ${MODELS_YAML} not found, using model.py defaults"
fi

# ---------------------------------------------------------------------------
# 0. Link exported model files into the Triton model repository
# ---------------------------------------------------------------------------
# Model configs (config.pbtxt) are baked into the image at /models/repository/.
# Exported model files (.onnx, .plan, .data) live in /models/cache/ (volume).
# Symlink each model's version directory so Triton finds both.

MODEL_CACHE="${MODEL_CACHE_DIR:-/models/cache}"

if [ -d "$MODEL_CACHE" ]; then
    echo "[entrypoint] Linking model cache -> repository..."
    for model_dir in "$MODEL_CACHE"/*/; do
        model_name=$(basename "$model_dir")
        repo_model="${TRITON_MODEL_REPO}/${model_name}"
        cache_version="${model_dir}1"
        # Only link if cache has a version dir AND repo has a config
        if [ -d "$repo_model" ] && [ -d "$cache_version" ]; then
            rm -rf "${repo_model}/1"
            ln -sf "$cache_version" "${repo_model}/1" 2>/dev/null && \
                echo "[entrypoint]   ${model_name}/1 -> ${cache_version}" || \
                echo "[entrypoint]   WARN: failed to link ${model_name}"
        fi
    done
fi

# ---------------------------------------------------------------------------
# 1. Start Triton Inference Server in background
# ---------------------------------------------------------------------------
echo "[entrypoint] Starting Triton Inference Server..."
echo "[entrypoint]   Model repository: ${TRITON_MODEL_REPO}"
echo "[entrypoint]   HTTP port: ${TRITON_HTTP_PORT}"
echo "[entrypoint]   gRPC port: ${TRITON_GRPC_PORT}"
echo "[entrypoint]   Metrics port: ${TRITON_METRICS_PORT}"

tritonserver \
    --model-repository="${TRITON_MODEL_REPO}" \
    --http-port="${TRITON_HTTP_PORT}" \
    --grpc-port="${TRITON_GRPC_PORT}" \
    --metrics-port="${TRITON_METRICS_PORT}" \
    --model-control-mode=none \
    --strict-model-config=false \
    --exit-on-error=false \
    --log-verbose=0 \
    --rate-limit=execution_count \
    --pinned-memory-pool-byte-size=33554432 \
    --cuda-memory-pool-byte-size=0:268435456 \
    &

TRITON_PID=$!
echo "[entrypoint] Triton started with PID ${TRITON_PID}"

# ---------------------------------------------------------------------------
# 2. Wait for Triton to become ready
# ---------------------------------------------------------------------------
echo "[entrypoint] Waiting for Triton to become ready..."

MAX_WAIT=120
WAITED=0

while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -sf "http://localhost:${TRITON_HTTP_PORT}/v2/health/ready" > /dev/null 2>&1; then
        echo "[entrypoint] Triton is ready (waited ${WAITED}s)"
        break
    fi

    # Check if Triton process is still alive
    if ! kill -0 "$TRITON_PID" 2>/dev/null; then
        echo "[entrypoint] ERROR: Triton process exited unexpectedly"
        exit 1
    fi

    sleep 2
    WAITED=$((WAITED + 2))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo "[entrypoint] WARNING: Triton not ready after ${MAX_WAIT}s, starting gateway anyway"
fi

# ---------------------------------------------------------------------------
# 3. Start the AI Gateway (FastAPI + uvicorn)
# ---------------------------------------------------------------------------
echo "[entrypoint] Starting AI Gateway on port ${GATEWAY_PORT}..."

python3 -m uvicorn ai.gateway.main:app \
    --host 0.0.0.0 \
    --port "${GATEWAY_PORT}" \
    --log-level info \
    --access-log \
    &

GATEWAY_PID=$!
echo "[entrypoint] Gateway started with PID ${GATEWAY_PID}"

# ---------------------------------------------------------------------------
# 4. Wait for either process to exit
# ---------------------------------------------------------------------------
echo "[entrypoint] AI Gateway + Triton running. Waiting for shutdown..."

# Wait for either child to exit. If one dies, clean up the other.
wait -n "$TRITON_PID" "$GATEWAY_PID" 2>/dev/null || true

EXIT_CODE=$?
echo "[entrypoint] A child process exited with code ${EXIT_CODE}"

# Clean up remaining process
cleanup
