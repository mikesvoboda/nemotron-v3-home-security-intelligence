#!/bin/bash
#
# Nemotron LLM Server Startup Script (via llama.cpp)
#
# Port: 8002
# VRAM Usage: ~3GB (Q4_K_M quantization)
# Context: 4096 tokens
# Parallelism: 2 concurrent requests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NEMOTRON_DIR="$SCRIPT_DIR/nemotron"
MODEL_FILE="$NEMOTRON_DIR/nemotron-mini-4b-instruct-q4_k_m.gguf"
MODEL_PORT=8002

# Check if model exists
if [ ! -f "$MODEL_FILE" ]; then
    echo "Error: Model not found at $MODEL_FILE"
    echo "Run: ./ai/download_models.sh"
    exit 1
fi

echo "Starting Nemotron LLM Server via llama.cpp..."
echo "Model: $MODEL_FILE"
echo "Port: $MODEL_PORT"
echo "Context size: 4096"
echo "GPU layers: 99 (all layers)"
echo "Expected VRAM usage: ~3GB"

llama-server \
  --model "$MODEL_FILE" \
  --port $MODEL_PORT \
  --ctx-size 4096 \
  --n-gpu-layers 99 \
  --host 0.0.0.0 \
  --parallel 2 \
  --cont-batching
