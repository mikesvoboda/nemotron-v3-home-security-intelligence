#!/usr/bin/env bash
#
# Nemotron LLM Server Startup Script (via llama.cpp)
# Called by ServiceHealthMonitor for auto-recovery
#
# Port: 8091 (configurable via NEMOTRON_PORT)
# VRAM Usage: ~16GB (Nemotron-3-Nano-30B-A3B Q4_K_M quantization)
# Context: 12288 tokens
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${NEMOTRON_PORT:-8091}"
# Default to 0.0.0.0 to allow connections from Docker/Podman containers.
# When running natively on host while backend runs in containers, binding to
# 127.0.0.1 would prevent container-to-host connectivity. Use 0.0.0.0 to bind
# to all interfaces, enabling both local and container access.
HOST="${NEMOTRON_HOST:-0.0.0.0}"
# Health check should use localhost since we're checking from the same host
HEALTH_URL="http://127.0.0.1:$PORT/health"
LOG_FILE="/tmp/nemotron.log"
STARTUP_TIMEOUT=90  # Model loading takes time for large models

# Model configuration - check multiple possible locations
MODEL_PATHS=(
    "${NEMOTRON_MODEL_PATH:-}"
    "/export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf"
    "$SCRIPT_DIR/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf"
)

# llama-server configuration - check multiple possible locations
LLAMA_SERVER_PATHS=(
    "${LLAMA_SERVER_PATH:-}"
    "/usr/bin/llama-server"
    "/export/ai_models/nemotron/llama.cpp/build/bin/llama-server"
)

# GPU layers (use all by default)
GPU_LAYERS="${NEMOTRON_GPU_LAYERS:-35}"
CONTEXT_SIZE="${NEMOTRON_CONTEXT_SIZE:-12288}"

# Check if already running
if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
    echo "Nemotron already running on port $PORT"
    exit 0
fi

# Find model file
MODEL_PATH=""
for path in "${MODEL_PATHS[@]}"; do
    if [ -n "$path" ] && [ -f "$path" ]; then
        MODEL_PATH="$path"
        break
    fi
done

if [ -z "$MODEL_PATH" ]; then
    echo "ERROR: Nemotron model not found"
    echo "Searched paths:"
    for path in "${MODEL_PATHS[@]}"; do
        [ -n "$path" ] && echo "  - $path"
    done
    echo ""
    echo "Set NEMOTRON_MODEL_PATH environment variable or download model:"
    echo "  ./ai/download_models.sh"
    exit 1
fi

# Find llama-server binary
LLAMA_SERVER=""
for path in "${LLAMA_SERVER_PATHS[@]}"; do
    if [ -n "$path" ] && [ -x "$path" ]; then
        LLAMA_SERVER="$path"
        break
    fi
done

if [ -z "$LLAMA_SERVER" ]; then
    # Try to find in PATH
    if command -v llama-server > /dev/null 2>&1; then
        LLAMA_SERVER="$(command -v llama-server)"
    else
        echo "ERROR: llama-server binary not found"
        echo "Searched paths:"
        for path in "${LLAMA_SERVER_PATHS[@]}"; do
            [ -n "$path" ] && echo "  - $path"
        done
        echo ""
        echo "Install llama.cpp or set LLAMA_SERVER_PATH environment variable"
        exit 1
    fi
fi

echo "Starting Nemotron LLM Server via llama.cpp..."
echo "Model: $MODEL_PATH"
echo "Binary: $LLAMA_SERVER"
echo "Host: $HOST:$PORT"
echo "GPU layers: $GPU_LAYERS"
echo "Context size: $CONTEXT_SIZE"
echo "Log file: $LOG_FILE"

# Start llama-server
nohup "$LLAMA_SERVER" \
    --model "$MODEL_PATH" \
    --host "$HOST" \
    --port "$PORT" \
    -ngl "$GPU_LAYERS" \
    -c "$CONTEXT_SIZE" \
    --parallel 2 \
    --cont-batching \
    > "$LOG_FILE" 2>&1 &

SERVER_PID=$!

echo "Started Nemotron server process (PID: $SERVER_PID)"
echo "Waiting for health check (max ${STARTUP_TIMEOUT}s)..."

# Wait for health check (large model loading can take 60-90 seconds)
for i in $(seq 1 $STARTUP_TIMEOUT); do
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        echo "Nemotron started successfully on port $PORT"
        exit 0
    fi
    # Check if process is still running
    if ! kill -0 $SERVER_PID 2>/dev/null; then
        echo "ERROR: Nemotron process exited unexpectedly"
        echo "Last 20 lines of log:"
        tail -20 "$LOG_FILE" 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

echo "ERROR: Nemotron failed to start within ${STARTUP_TIMEOUT} seconds"
echo "Last 20 lines of log:"
tail -20 "$LOG_FILE" 2>/dev/null || true
exit 1
