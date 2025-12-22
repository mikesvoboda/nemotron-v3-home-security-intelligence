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

# TODO: Uncomment and configure once RT-DETRv2 model is set up
# python -m rtdetr.server \
#   --model-path "$RTDETR_DIR/rtdetrv2_r50vd.pth" \
#   --port $MODEL_PORT \
#   --device cuda:0 \
#   --confidence-threshold 0.5

echo "Placeholder: Configure RT-DETRv2 model path and uncomment startup command"
