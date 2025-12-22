#!/bin/bash
#
# Nemotron LLM Server Startup Script (via llama.cpp)
#
# Port: 8002
# VRAM Usage: ~18GB
# Quantization: Q4_K_M

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NEMOTRON_DIR="$SCRIPT_DIR/nemotron"
MODEL_PORT=8002
MODEL_FILE="$NEMOTRON_DIR/nemotron-mini-4b-instruct-q4_k_m.gguf"
CONTEXT_SIZE=8192
GPU_LAYERS=99

echo "Starting Nemotron LLM Server via llama.cpp..."
echo "Model: $MODEL_FILE"
echo "Port: $MODEL_PORT"
echo "Context size: $CONTEXT_SIZE"
echo "GPU layers: $GPU_LAYERS"
echo "Expected VRAM usage: ~18GB"

# TODO: Uncomment once llama.cpp and model are configured
# llama-server \
#   --model "$MODEL_FILE" \
#   --host 0.0.0.0 \
#   --port $MODEL_PORT \
#   --ctx-size $CONTEXT_SIZE \
#   --n-gpu-layers $GPU_LAYERS \
#   --batch-size 512 \
#   --flash-attn \
#   --cont-batching

echo "Placeholder: Download Nemotron GGUF model and configure llama-server path"
