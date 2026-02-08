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

# Phase 2: Build images (parallel where possible)
# Dependency graph: base → backend (sequential), frontend/ai-gateway/ai-llm (independent)
echo ""
echo "[2/7] Building images..."

# Step 1: Build base image first (backend depends on it)
echo "  Building base (sequential — backend depends on this)..."
podman build --no-cache -f "$PROJECT_ROOT/docker/base.Dockerfile" -t ghcr.io/mikesvoboda/nemotron-base:latest "$PROJECT_ROOT" 2>&1 | tail -1

# Step 2: Build all 4 images in parallel
# - backend: depends on base (now built)
# - frontend, ai-gateway, ai-llm: fully independent
echo "  Building backend + frontend + ai-gateway + ai-llm in parallel..."
podman build --no-cache -f "$PROJECT_ROOT/backend/Dockerfile" -t backend "$PROJECT_ROOT" > /tmp/build-backend.log 2>&1 &
PID_BACKEND=$!
podman build --no-cache --target prod -f "$PROJECT_ROOT/frontend/Dockerfile" -t frontend "$PROJECT_ROOT/frontend" > /tmp/build-frontend.log 2>&1 &
PID_FRONTEND=$!
podman build --no-cache -f "$PROJECT_ROOT/ai/gateway/Dockerfile" -t ai-gateway "$PROJECT_ROOT" > /tmp/build-gateway.log 2>&1 &
PID_GATEWAY=$!
podman build --no-cache -f "$PROJECT_ROOT/ai/nemotron/Dockerfile" -t ai-llm "$PROJECT_ROOT" > /tmp/build-llm.log 2>&1 &
PID_LLM=$!

# Wait for all builds and report results
FAILED=0
for name_pid in "backend:$PID_BACKEND" "frontend:$PID_FRONTEND" "ai-gateway:$PID_GATEWAY" "ai-llm:$PID_LLM"; do
    name="${name_pid%%:*}"
    pid="${name_pid##*:}"
    if wait "$pid"; then
        echo "    ✓ $name built successfully"
    else
        echo "    ✗ $name build FAILED (see /tmp/build-${name}.log)"
        FAILED=1
    fi
done

if [ "$FAILED" -eq 1 ]; then
    echo ""
    echo "  ERROR: One or more builds failed. Check logs in /tmp/build-*.log"
    exit 1
fi

echo "  All images built."

# Phase 3+4+5: Export models + Start infrastructure + Start observability (in parallel)
# These are independent: model export uses GPU, infrastructure uses CPU/network
echo ""
echo "[3/8] Exporting models + starting infrastructure (parallel)..."

mkdir -p /export/ai_models/triton

# Start model export in background (GPU-bound, takes 5-15 min)
echo "  Starting model export (background)..."
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
  -c "cd /app/gateway/export && bash export_all.sh" > /tmp/export-models.log 2>&1 &
PID_EXPORT=$!

# Start infrastructure while export runs (CPU-bound, fast)
echo "[4/8] Starting infrastructure..."
podman compose -f "$PROJECT_ROOT/docker-compose.prod.yml" up -d postgres redis go2rtc 2>&1 | tail -3
echo "  Waiting for postgres/redis..."
sleep 10
echo "  Infrastructure up."

echo "[5/8] Starting observability..."
podman compose -f "$PROJECT_ROOT/docker-compose.prod.yml" up -d prometheus grafana loki tempo alertmanager alloy node-exporter pyroscope blackbox-exporter json-exporter redis-exporter 2>&1 | tail -3
echo "  Observability up."

# Wait for model export to finish
echo ""
echo "  Waiting for model export to complete..."
if wait "$PID_EXPORT"; then
    echo "  Model exports complete."
else
    echo "  WARNING: Export returned non-zero exit (partial failures are normal)"
    echo "  See /tmp/export-models.log for details"
fi
echo "  Exported files:"
ls -lh /export/ai_models/triton/*/1/ 2>/dev/null | grep -E "model\.(plan|onnx)" || echo "  (no exports found — models will load on demand)"

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
  -p "127.0.0.1:${AI_GATEWAY_METRICS_PORT:-8002}:8002" \
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
  -e GPU_LAYERS="${GPU_LAYERS:-45}" \
  -e GGML_CUDA_GRAPH_OPT=1 \
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
