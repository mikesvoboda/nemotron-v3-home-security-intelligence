#!/usr/bin/env bash
#
# YOLO26v2 Detection Server Startup Script
#
# HOST-RUN DEV STAND-IN ONLY. The standalone ai-yolo26 GPU image was retired
# 2026-09-23 (recipe at archive/ai-yolo26-image/Dockerfile): production
# detection is served by Triton inside ai-gateway (router /yolo26 on 8090).
# This script runs ai/yolo26/model.py directly on the host for debugging a
# model outside a container - it still works, but it is not the prod path.
#
# Port: 8090 (configurable via YOLO26_PORT) - collides with ai-gateway's
#       host port, so run it with ai-gateway down or on a free port.
# VRAM Usage: ~4GB

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
YOLO26_DIR="$SCRIPT_DIR/yolo26"
MODEL_PORT="${YOLO26_PORT:-8090}"

echo "Starting YOLO26v2 Detection Server..."
echo "Model directory: $YOLO26_DIR"
echo "Port: $MODEL_PORT"
echo "Expected VRAM usage: ~4GB"

echo "YOLO26v2 model source:"
echo "  - Controlled by YOLO26_MODEL_PATH (HuggingFace model id or local path)"
echo "  - If not set, the server uses its internal default and may download weights via HuggingFace cache"

# Start the inference server
# Note: Host binding defaults to 0.0.0.0 in model.py to allow connections from
# Docker/Podman containers. Override with HOST environment variable if needed.
cd "$YOLO26_DIR"
export PORT="${PORT:-$MODEL_PORT}"
python model.py
