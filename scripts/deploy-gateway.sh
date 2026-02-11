#!/bin/bash
# Production deploy script using podman compose with Triton gateway.
# Uses ai-gateway (single Triton container) instead of 5 individual AI containers.
# All services managed via compose — single source of truth for configuration.
#
# Usage:
#   ./scripts/deploy-gateway.sh                    # Normal deploy (skips export, uses cached models)
#   ./scripts/deploy-gateway.sh --export           # Export models before deploy (first deploy or model updates)
#   ./scripts/deploy-gateway.sh --force-export     # Force re-export all models (rebuilds cache)
#   ./scripts/deploy-gateway.sh --destroy-volumes  # Fresh deploy (destroys all data)
#   ./scripts/deploy-gateway.sh --skip-build       # Skip image builds (use existing)
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$PROJECT_ROOT/.env"

# Increase open files limit for frontend builds (Vite/Rollup requires many file handles)
# This prevents "EMFILE: too many open files" errors during npm build
# Note: This only affects the current shell session and child processes (build containers)
# For persistent system-wide config, run setup.py which configures /etc/security/limits.d/
ulimit -n 65536 2>/dev/null || true

# Parse arguments
DESTROY_VOLUMES=false
SKIP_EXPORT=true  # Default: skip export (use cached models from Triton volume)
FORCE_EXPORT=false
SKIP_BUILD=false
for arg in "$@"; do
    case "$arg" in
        --destroy-volumes) DESTROY_VOLUMES=true ;;
        --export) SKIP_EXPORT=false ;;  # Explicitly enable export
        --force-export) FORCE_EXPORT=true; SKIP_EXPORT=false ;;
        --skip-build) SKIP_BUILD=true ;;
    esac
done

# Auto-detect podman compose command (Podman 5.x native vs 4.x external)
# Fedora 43 (Podman 5.x): "podman compose" (native subcommand, no hyphen)
# Ubuntu 22.04 (Podman 4.x): "podman-compose" (external Python tool, with hyphen)
if podman compose version &>/dev/null; then
    COMPOSE_CMD="podman compose"
    echo "Detected: podman compose (native, Podman 5.x+)"
else
    COMPOSE_CMD="podman-compose"
    echo "Detected: podman-compose (external, Podman 4.x)"
fi

# Compose command — gateway mode is the default deployment
# Individual AI services (ai-yolo26, ai-florence, etc.) are profiled as "standalone"
# and won't start unless explicitly requested with --profile standalone
COMPOSE="$COMPOSE_CMD -f $PROJECT_ROOT/docker-compose.prod.yml -f $PROJECT_ROOT/docker-compose.gateway.yml"

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
# Stop rootful dcgm-exporter if running (separate from rootless compose)
sudo systemctl stop dcgm-exporter 2>/dev/null || true

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

    # Get GPU compute capability for optimized CUDA builds
    # This reduces ai-llm build time by ~6x by only compiling for the detected GPU
    # Reads from .env (set by setup.py), or detects at runtime if not configured
    CUDA_ARCH=""
    
    if [ -n "${CUDA_ARCHITECTURES:-}" ]; then
        # Use value from .env (set by setup.py during initial setup)
        CUDA_ARCH="--build-arg CUDA_ARCHITECTURES=${CUDA_ARCHITECTURES}"
        echo "  GPU architecture: ${CUDA_ARCHITECTURES:0:1}.${CUDA_ARCHITECTURES:1} (from .env)"
    elif command -v nvidia-smi &> /dev/null; then
        # Fallback: detect at runtime
        COMPUTE_CAP=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | tr -d '.')
        if [ -n "$COMPUTE_CAP" ]; then
            CUDA_ARCH="--build-arg CUDA_ARCHITECTURES=${COMPUTE_CAP}"
            echo "  GPU architecture: ${COMPUTE_CAP:0:1}.${COMPUTE_CAP:1} (detected, consider running setup.py)"
        fi
    fi
    
    if [ -z "$CUDA_ARCH" ]; then
        echo "  GPU not detected - building for common architectures (6x slower)"
        echo "  Run setup.py to configure CUDA_ARCHITECTURES in .env"
    fi

    # Build base image first (backend depends on it)
    echo "  Building base (sequential — backend depends on this)..."
    podman build --no-cache -f "$PROJECT_ROOT/docker/base.Dockerfile" \
        -t ghcr.io/mikesvoboda/nemotron-base:latest "$PROJECT_ROOT" 2>&1 | tail -1

    # Build all service images via compose (ensures correct image naming)
    echo "  Building all services via compose..."
    $COMPOSE build --no-cache $CUDA_ARCH backend frontend ai-gateway ai-llm 2>&1 | tail -5

    echo "  All images built."
fi

# ==========================================================================
# Phase 3: Export models for Triton
# ==========================================================================
# Auto-detect if model exports are needed by checking for core model files
TRITON_CACHE="/export/ai_models/triton"
CORE_MODELS="yolo26 clip clip_text pose threat reid depth pet vehicle demographics_age demographics_gender fashion_clip"
MISSING_MODELS=0

# Always check for missing models (unless force export is set)
if [ "$FORCE_EXPORT" != true ]; then
    for model in $CORE_MODELS; do
        if [ ! -f "$TRITON_CACHE/$model/1/model.onnx" ] && [ ! -f "$TRITON_CACHE/$model/1/model.plan" ]; then
            MISSING_MODELS=$((MISSING_MODELS + 1))
        fi
    done
else
    MISSING_MODELS=999  # Force re-export all
fi

if [ "$MISSING_MODELS" -gt 0 ] && [ "$SKIP_EXPORT" = true ]; then
    echo ""
    echo "[3/6] Models missing - automatic export required"
    echo "  Triton loads models from: /export/ai_models/triton/"
    echo "  ⚠️  $MISSING_MODELS models not found in cache!"
    echo ""
    echo "  Automatically enabling model export (first deploy or cache cleared)"
    SKIP_EXPORT=false
fi

if [ "$SKIP_EXPORT" = true ]; then
    echo ""
    echo "[3/6] Skipping model export (default - using cached models)"
    echo "  Triton loads models from: /export/ai_models/triton/"
    echo "  ✓ All $( echo $CORE_MODELS | wc -w) models cached"
    echo "  Use --force-export to rebuild cache"
elif [ "$MISSING_MODELS" -eq 0 ]; then
    echo ""
    echo "[3/6] All $( echo $CORE_MODELS | wc -w) core models cached — skipping export"
    echo "  Use --force-export to rebuild, or delete /export/ai_models/triton/ to re-export all"
else
    echo ""
    echo "[3/6] Exporting models for Triton ($MISSING_MODELS missing)..."
    mkdir -p "$TRITON_CACHE"

    # Run export in background while infrastructure starts
    # Use full localhost image name to avoid short-name resolution prompt
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
        -v "$TRITON_CACHE:/models/cache" \
        localhost/nemotron-v3-home-security-intelligence_ai-gateway:latest \
        -c "cd /app/gateway/export && bash export_all.sh" > /tmp/export-models.log 2>&1 &
    PID_EXPORT=$!
fi

# ==========================================================================
# Phase 4: Start infrastructure + observability (while export runs)
# ==========================================================================
echo ""
echo "[4/6] Starting infrastructure + observability..."
$COMPOSE up -d --no-build postgres redis go2rtc 2>&1 | tail -3
echo "  Waiting for postgres/redis..."
sleep 10

$COMPOSE up -d --no-build \
    prometheus grafana loki tempo alertmanager alloy \
    node-exporter pyroscope blackbox-exporter json-exporter redis-exporter \
    cadvisor 2>&1 | tail -3

# dcgm-exporter runs as a rootful systemd service (DCGM requires host-level root).
# It is NOT part of the rootless compose stack. See monitoring/dcgm/dcgm-exporter.service.
if systemctl is-enabled dcgm-exporter.service &>/dev/null; then
    sudo systemctl restart dcgm-exporter 2>/dev/null \
        && echo "  dcgm-exporter: restarted (rootful systemd service)" \
        || echo "  dcgm-exporter: failed to restart (check: sudo journalctl -u dcgm-exporter)"
else
    echo "  dcgm-exporter: skipped (not installed — run setup.py or see monitoring/dcgm/)"
fi
echo "  Infrastructure + observability up."

# Wait for model export if it was started
if [ "$SKIP_EXPORT" != true ] && [ "${MISSING_MODELS:-0}" -gt 0 ]; then
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
$COMPOSE up -d --no-build 2>&1 | tail -5
echo "  All services started."

# ==========================================================================
# Phase 6: Health check
# ==========================================================================
echo ""
echo "[6/6] Health check (waiting 30s for model loading)..."
sleep 30

# Auto-register default admin if first deploy (resolves SetupGuard 503s)
SETUP_STATUS=$(curl -sf "http://localhost:${API_PORT:-8000}/api/auth/setup-status" 2>/dev/null)
if echo "$SETUP_STATUS" | python3 -c "import json,sys; sys.exit(0 if json.load(sys.stdin).get('setup_required') else 1)" 2>/dev/null; then
    echo "  Registering default admin user..."
    REGISTER_RESULT=$(curl -sf -X POST "http://localhost:${API_PORT:-8000}/api/auth/register" \
        -H "Content-Type: application/json" \
        -d '{"username":"admin","email":"admin@local.host","password":"ChangeMe123!"}' 2>/dev/null)  # pragma: allowlist secret
    if [ $? -eq 0 ]; then
        echo "    Admin registered: admin / ChangeMe123!"
        echo "    IMPORTANT: Change this password after first login."
    else
        echo "    Admin registration failed (may already exist)"
    fi
fi

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
