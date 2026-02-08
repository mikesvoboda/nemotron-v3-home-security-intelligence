#!/bin/bash
# Simple deploy script for Triton gateway mode.
# Replaces 5 AI containers with 1 gateway + 1 LLM.
# Usage: ./scripts/deploy-gateway.sh [--destroy-volumes]
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$PROJECT_ROOT/.env"

DESTROY_VOLUMES="${1:-}"
NETWORK="nemotron-v3-home-security-intelligence_security-net"

echo "=== Triton Gateway Deploy ==="
echo "Branch: $(git -C "$PROJECT_ROOT" branch --show-current)"
echo "Commit: $(git -C "$PROJECT_ROOT" rev-parse --short HEAD)"
echo ""

# Phase 1: Stop everything
echo "[1/7] Stopping all containers..."
podman stop -a 2>/dev/null || true
podman rm -a 2>/dev/null || true

if [ "$DESTROY_VOLUMES" = "--destroy-volumes" ]; then
    echo "  Destroying volumes..."
    podman volume prune -f 2>/dev/null || true
    podman compose -f "$PROJECT_ROOT/docker-compose.prod.yml" down --volumes 2>/dev/null || true
fi
echo "  Done."

# Phase 2: Build images (only what we need)
echo ""
echo "[2/7] Building images..."

echo "  Building base..."
podman build --no-cache -f "$PROJECT_ROOT/docker/base.Dockerfile" -t ghcr.io/mikesvoboda/nemotron-base:latest "$PROJECT_ROOT" 2>&1 | tail -1

echo "  Building backend..."
podman build --no-cache -f "$PROJECT_ROOT/backend/Dockerfile" -t backend "$PROJECT_ROOT" 2>&1 | tail -1

echo "  Building frontend..."
podman build --no-cache --target prod -f "$PROJECT_ROOT/frontend/Dockerfile" -t frontend "$PROJECT_ROOT/frontend" 2>&1 | tail -1

echo "  Building ai-gateway..."
podman build --no-cache -f "$PROJECT_ROOT/ai/gateway/Dockerfile" -t ai-gateway "$PROJECT_ROOT" 2>&1 | tail -1

echo "  Building ai-llm..."
podman build --no-cache -f "$PROJECT_ROOT/ai/nemotron/Dockerfile" -t ai-llm "$PROJECT_ROOT" 2>&1 | tail -1

echo "  All images built."

# Phase 3: Export models for Triton (runs inside gateway container with GPU)
echo ""
echo "[3/8] Exporting models for Triton..."
echo "  This converts PyTorch/HuggingFace models to TensorRT/ONNX for Triton."
echo "  Cached exports in /export/ai_models/triton/ are reused if present."

mkdir -p /export/ai_models/triton

# Run export_all.sh inside a temporary gateway container with GPU access
podman run --rm \
  --name ai-gateway-export \
  --entrypoint bash \
  --device "nvidia.com/gpu=${GPU_AI_SERVICES:-1}" \
  --security-opt label=disable \
  -e CUDA_VISIBLE_DEVICES=0 \
  -e MODELS_ZOO=/models/zoo \
  -e CACHE_DIR=/models/cache \
  -e REPO_DIR=/models/repository \
  -v "/export/ai_models/model-zoo:/models/zoo:ro" \
  -v "/export/ai_models/triton:/models/cache" \
  ai-gateway \
  -c "cd /app/gateway/export && bash export_all.sh" 2>&1 | tail -30

echo "  Model exports complete."
echo "  Exported files:"
ls -lh /export/ai_models/triton/*/1/ 2>/dev/null | grep -E "model\.(plan|onnx)" || echo "  (no exports found — models will load on demand)"

# Phase 4: Start infrastructure (compose)
echo ""
echo "[4/8] Starting infrastructure..."
podman compose -f "$PROJECT_ROOT/docker-compose.prod.yml" up -d postgres redis go2rtc 2>&1 | tail -3
echo "  Waiting for postgres/redis..."
sleep 10
echo "  Infrastructure up."

# Phase 5: Start observability (compose)
echo ""
echo "[5/8] Starting observability..."
podman compose -f "$PROJECT_ROOT/docker-compose.prod.yml" up -d prometheus grafana loki jaeger elasticsearch alertmanager alloy node-exporter pyroscope blackbox-exporter json-exporter redis-exporter 2>&1 | tail -3
echo "  Observability up."

# Phase 6: Start AI services (standalone — gateway mode)
echo ""
echo "[6/8] Starting AI services (gateway mode)..."

# AI Gateway (Triton + FastAPI) on GPU 1
echo "  Starting ai-gateway on GPU ${GPU_AI_SERVICES:-1}..."
podman run -d \
  --name ai-gateway \
  --network "$NETWORK" \
  --device "nvidia.com/gpu=${GPU_AI_SERVICES:-1}" \
  --security-opt label=disable \
  -e GATEWAY_PORT=8090 \
  -e CUDA_VISIBLE_DEVICES=0 \
  -v "/export/ai_models/model-zoo:/models/zoo:ro" \
  -v "/export/ai_models/triton:/models/cache" \
  -p "127.0.0.1:${AI_GATEWAY_PORT:-8090}:8090" \
  ai-gateway 2>&1 | tail -1

# LLM on GPU 0
echo "  Starting ai-llm on GPU ${GPU_LLM:-0}..."
podman run -d \
  --name ai-llm \
  --network "$NETWORK" \
  --device "nvidia.com/gpu=${GPU_LLM:-0}" \
  --security-opt label=disable \
  -e PORT="${LLM_PORT:-8091}" \
  -e CUDA_VISIBLE_DEVICES=0 \
  -e GPU_LAYERS="${GPU_LAYERS:-48}" \
  -e CTX_SIZE="${CTX_SIZE:-32768}" \
  -e PARALLEL="${PARALLEL:-2}" \
  -v "/export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km:/models:ro,z" \
  -p "127.0.0.1:${LLM_PORT:-8091}:${LLM_PORT:-8091}" \
  ai-llm 2>&1 | tail -1

echo "  AI services started (2 containers)."

# Phase 7: Start backend + frontend (standalone)
echo ""
echo "[7/8] Starting backend + frontend..."

echo "  Starting backend..."
podman run -d \
  --name backend \
  --network "$NETWORK" \
  --env-file "$PROJECT_ROOT/.env" \
  -e DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER:-security}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-security}" \
  -e REDIS_URL="redis://:${REDIS_PASSWORD}@redis:6379" \
  -e AI_GATEWAY_URL="http://ai-gateway:8090" \
  -e USE_AI_GATEWAY=true \
  -e YOLO26_URL="http://ai-gateway:8090/yolo26" \
  -e NEMOTRON_URL="http://ai-llm:${LLM_PORT:-8091}" \
  -e FLORENCE_URL="http://ai-gateway:8090/florence" \
  -e CLIP_URL="http://ai-gateway:8090/clip" \
  -e ENRICHMENT_URL="http://ai-gateway:8090/enrichment" \
  -e ENRICHMENT_LIGHT_URL="http://ai-gateway:8090/enrich-lt" \
  -e FOSCAM_BASE_PATH=/cameras \
  -v "${FOSCAM_BASE_PATH:-/export/foscam}:/cameras:ro,z" \
  -p "127.0.0.1:${API_PORT:-8000}:8000" \
  backend 2>&1 | tail -1

echo "  Starting frontend..."
podman run -d \
  --name frontend \
  --network "$NETWORK" \
  --env-file "$PROJECT_ROOT/.env" \
  -p "127.0.0.1:${FRONTEND_PORT:-5173}:5173" \
  -p "127.0.0.1:${FRONTEND_HTTPS_PORT:-8444}:8443" \
  frontend 2>&1 | tail -1

echo "  Backend + frontend started."

# Phase 8: Health check
echo ""
echo "[8/8] Checking health..."
sleep 15

echo "  Backend:"
curl -s "http://localhost:${API_PORT:-8000}/api/system/health" 2>/dev/null | python3 -m json.tool 2>/dev/null | head -5 || echo "  Not ready yet (may need more time)"

echo ""
echo "  AI Gateway:"
curl -s "http://localhost:${AI_GATEWAY_PORT:-8090}/health" 2>/dev/null | python3 -m json.tool 2>/dev/null | head -5 || echo "  Not ready yet (Triton loading models)"

echo ""
echo "  LLM:"
curl -s "http://localhost:${LLM_PORT:-8091}/health" 2>/dev/null || echo "  Not ready yet (loading model)"

echo ""
echo ""
echo "=== Deploy Complete ==="
echo "  Frontend: https://localhost:${FRONTEND_HTTPS_PORT:-8444}"
echo "  Backend:  http://localhost:${API_PORT:-8000}"
echo "  Gateway:  http://localhost:${AI_GATEWAY_PORT:-8090}"
echo ""
echo "  Containers: $(podman ps -q | wc -l) running"
echo "  GPU usage:"
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader 2>/dev/null || echo "  nvidia-smi not available"
