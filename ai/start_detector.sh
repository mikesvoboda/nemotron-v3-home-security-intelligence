#!/bin/bash
#
# RT-DETRv2 Detection Server Startup Script
#
# Port: 8001
# VRAM Usage: ~4GB

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RTDETR_DIR="$SCRIPT_DIR/rtdetr"
MODEL_PORT=8001
MODEL_PATH_DEFAULT="$RTDETR_DIR/rtdetrv2_r50vd.onnx"

echo "Starting RT-DETRv2 Detection Server..."
echo "Model directory: $RTDETR_DIR"
echo "Port: $MODEL_PORT"
echo "Expected VRAM usage: ~4GB"

# Check if model file exists
MODEL_PATH="${MODEL_PATH:-$MODEL_PATH_DEFAULT}"
if [ ! -f "$MODEL_PATH" ]; then
    echo "WARNING: Model file not found at $MODEL_PATH"
    echo "Server will start but detection will fail until model is available"
    echo "Please provide an ONNX model:"
    echo "  - copy to: $MODEL_PATH_DEFAULT"
    echo "  - OR run: ./ai/download_models.sh (will try to auto-locate from /export/ai_models)"
    echo "  - OR set: MODEL_PATH=/path/to/model.onnx"
fi

# Start the inference server
cd "$RTDETR_DIR"
export MODEL_PATH
export PORT="${PORT:-$MODEL_PORT}"
python model.py
