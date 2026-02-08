#!/bin/bash
# Production deploy script using podman compose with Triton gateway.
# Uses ai-gateway (single Triton container) instead of 5 individual AI containers.
# All services managed via compose — single source of truth for configuration.
#
# Usage:
#   ./scripts/deploy-gateway.sh                    # Normal deploy
#   ./scripts/deploy-gateway.sh --destroy-volumes  # Fresh deploy (destroys all data)
#   ./scripts/deploy-gateway.sh --skip-export      # Skip model export (use cached)
#   ./scripts/deploy-gateway.sh --skip-build       # Skip image builds (use existing)
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$PROJECT_ROOT/.env"

# Parse arguments
DESTROY_VOLUMES=false
SKIP_EXPORT=false
SKIP_BUILD=false
for arg in "$@"; do
    case "$arg" in
        --destroy-volumes) DESTROY_VOLUMES=true ;;
        --skip-export) SKIP_EXPORT=true ;;
        --skip-build) SKIP_BUILD=true ;;
    esac
done

# Compose command — gateway mode is the default deployment
# Individual AI services (ai-yolo26, ai-florence, etc.) are profiled as "standalone"
# and won't start unless explicitly requested with --profile standalone
COMPOSE="podman compose -f $PROJECT_ROOT/docker-compose.prod.yml -f $PROJECT_ROOT/docker-compose.gateway.yml"

echo "=== Triton Gateway Deploy ==="
echo "Branch: $(git -C "$PROJECT_ROOT" branch --show-current)"
echo "Commit: $(git -C "$PROJECT_ROOT" rev-parse --short HEAD)"
echo "Mode:   compose + gateway profile"
echo ""

# ==========================================================================
# Phase 1: Stop everything
# ==========================================================================
echo "[1/6] Stopping all containers..."
$COMPOSE down 2>/dev/null || true
podman stop -a 2>/dev/null || true
podman rm -a 2>/dev/null || true

if [ "$DESTROY_VOLUMES" = true ]; then
    echo "  Destroying volumes..."
    podman volume prune -f 2>/dev/null || true
fi
echo "  Done."

# ==========================================================================
# Phase 2: Build images
# ==========================================================================
if [ "$SKIP_BUILD" = true ]; then
    echo ""
    echo "[2/6] Skipping image builds (--skip-build)"
else
    echo ""
    echo "[2/6] Building images..."

    # Build base image first (backend depends on it)
    echo "  Building base (sequential — backend depends on this)..."
    podman build --no-cache -f "$PROJECT_ROOT/docker/base.Dockerfile" \
        -t ghcr.io/mikesvoboda/nemotron-base:latest "$PROJECT_ROOT" 2>&1 | tail -1

    # Build all service images in parallel
    echo "  Building backend + frontend + ai-gateway + ai-llm in parallel..."
    podman build --no-cache -f "$PROJECT_ROOT/backend/Dockerfile" -t backend "$PROJECT_ROOT" > /tmp/build-backend.log 2>&1 &
    PID_BACKEND=$!
    podman build --no-cache --target prod -f "$PROJECT_ROOT/frontend/Dockerfile" -t frontend "$PROJECT_ROOT/frontend" > /tmp/build-frontend.log 2>&1 &
    PID_FRONTEND=$!
    podman build --no-cache -f "$PROJECT_ROOT/ai/gateway/Dockerfile" -t ai-gateway "$PROJECT_ROOT" > /tmp/build-gateway.log 2>&1 &
    PID_GATEWAY=$!
    podman build --no-cache -f "$PROJECT_ROOT/ai/nemotron/Dockerfile" -t ai-llm "$PROJECT_ROOT" > /tmp/build-llm.log 2>&1 &
    PID_LLM=$!

    # Wait for all builds
    FAILED=0
    for name_pid in "backend:$PID_BACKEND" "frontend:$PID_FRONTEND" "ai-gateway:$PID_GATEWAY" "ai-llm:$PID_LLM"; do
        name="${name_pid%%:*}"
        pid="${name_pid##*:}"
        if wait "$pid"; then
            echo "    ✓ $name"
        else
            echo "    ✗ $name FAILED (see /tmp/build-${name}.log)"
            FAILED=1
        fi
    done

    if [ "$FAILED" -eq 1 ]; then
        echo "  ERROR: One or more builds failed."
        exit 1
    fi
    echo "  All images built."
fi

# ==========================================================================
# Phase 3: Export models for Triton
# ==========================================================================
if [ "$SKIP_EXPORT" = true ]; then
    echo ""
    echo "[3/6] Skipping model export (--skip-export)"
else
    echo ""
    echo "[3/6] Exporting models for Triton..."
    mkdir -p /export/ai_models/triton

    # Run export in background while infrastructure starts
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
fi

# ==========================================================================
# Phase 4: Start infrastructure + observability (while export runs)
# ==========================================================================
echo ""
echo "[4/6] Starting infrastructure + observability..."
$COMPOSE up -d postgres redis go2rtc 2>&1 | tail -3
echo "  Waiting for postgres/redis..."
sleep 10

$COMPOSE up -d \
    prometheus grafana loki tempo alertmanager alloy \
    node-exporter pyroscope blackbox-exporter json-exporter redis-exporter \
    dcgm-exporter cadvisor 2>&1 | tail -3
echo "  Infrastructure + observability up."

# Wait for model export if it was started
if [ "$SKIP_EXPORT" != true ]; then
    echo ""
    echo "  Waiting for model export to complete..."
    if wait "$PID_EXPORT"; then
        echo "  Model exports complete."
    else
        echo "  WARNING: Export had failures (see /tmp/export-models.log)"
    fi
    echo "  Exported files:"
    ls -lh /export/ai_models/triton/*/1/ 2>/dev/null | grep -E "model\.(plan|onnx)" || echo "  (none — models load on demand)"
fi

# ==========================================================================
# Phase 5: Start AI + application services via compose
# ==========================================================================
echo ""
echo "[5/6] Starting AI + application services..."
$COMPOSE up -d 2>&1 | tail -5
echo "  All services started."

# ==========================================================================
# Phase 6: Health check
# ==========================================================================
echo ""
echo "[6/6] Health check (waiting 30s for model loading)..."
sleep 30

echo "  Backend:"
curl -s "http://localhost:${API_PORT:-8000}/api/system/health" 2>/dev/null \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'    Status: {d[\"status\"]}')" 2>/dev/null \
    || echo "    Not ready yet"

echo "  AI Gateway:"
curl -s "http://localhost:${AI_GATEWAY_PORT:-8090}/health" 2>/dev/null \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'    Status: {d[\"status\"]}  Models: {d[\"models_loaded\"]}/{d[\"models_total\"]}')" 2>/dev/null \
    || echo "    Not ready yet (Triton loading models)"

echo "  LLM:"
curl -s "http://localhost:${LLM_PORT:-8091}/health" 2>/dev/null \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'    Status: {d[\"status\"]}')" 2>/dev/null \
    || echo "    Not ready yet (loading 30B model)"

echo ""
echo "=== Deploy Complete ==="
echo "  Frontend: https://localhost:${FRONTEND_HTTPS_PORT:-8444}"
echo "  Backend:  http://localhost:${API_PORT:-8000}"
echo "  Gateway:  http://localhost:${AI_GATEWAY_PORT:-8090}"
echo ""
echo "  Containers: $(podman ps -q | wc -l) running"
echo "  GPU usage:"
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader 2>/dev/null || echo "  nvidia-smi not available"
