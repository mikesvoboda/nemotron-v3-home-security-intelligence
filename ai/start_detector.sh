#!/usr/bin/env bash
#
# RT-DETRv2 Detection Server Startup Script
#
# Port: 8090 (configurable via RTDETR_PORT)
# VRAM Usage: ~4GB

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RTDETR_DIR="$SCRIPT_DIR/rtdetr"
MODEL_PORT="${RTDETR_PORT:-8090}"

echo "Starting RT-DETRv2 Detection Server..."
echo "Model directory: $RTDETR_DIR"
echo "Port: $MODEL_PORT"
echo "Expected VRAM usage: ~4GB"

echo "RT-DETRv2 model source:"
echo "  - Controlled by RTDETR_MODEL_PATH (HuggingFace model id or local path)"
echo "  - If not set, the server uses its internal default and may download weights via HuggingFace cache"

# Start the inference server
# Note: Host binding defaults to 0.0.0.0 in model.py to allow connections from
# Docker/Podman containers. Override with HOST environment variable if needed.
cd "$RTDETR_DIR"
export PORT="${PORT:-$MODEL_PORT}"
python model.py
