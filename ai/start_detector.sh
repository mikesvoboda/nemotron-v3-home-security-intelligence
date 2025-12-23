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

echo "Starting RT-DETRv2 Detection Server..."
echo "Model directory: $RTDETR_DIR"
echo "Port: $MODEL_PORT"
echo "Expected VRAM usage: ~4GB"

# Check if model file exists
if [ ! -f "$RTDETR_DIR/rtdetrv2_r50vd.onnx" ]; then
    echo "WARNING: Model file not found at $RTDETR_DIR/rtdetrv2_r50vd.onnx"
    echo "Server will start but detection will fail until model is available"
    echo "Please download RT-DETRv2 ONNX model and place it in $RTDETR_DIR"
fi

# Start the inference server
cd "$RTDETR_DIR"
python model.py
