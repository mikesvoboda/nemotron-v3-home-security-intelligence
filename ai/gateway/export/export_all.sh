#!/bin/bash
# Master export script for the Triton Model Export Pipeline.
#
# Converts all models from their native formats (PyTorch, HuggingFace)
# into Triton-compatible formats (TensorRT .plan, ONNX .onnx) and
# places them in the model cache volume.
#
# TensorRT exports require a GPU and must run on the target GPU architecture
# (engines are architecture-specific).  ONNX exports can run on CPU.
#
# Environment Variables:
#   MODELS_ZOO  - Root of the model zoo volume (default: /export/ai_models/model-zoo)
#   CACHE_DIR   - Root of the Triton model cache (default: /export/ai_models/triton)
#   REPO_DIR    - Root of the Triton model repository configs (default: /models/repository)
#   CUDA_DEVICE - CUDA device index for TensorRT exports (default: 0)
#
# Usage:
#   ./export_all.sh                                     # Use defaults
#   MODELS_ZOO=/data/models CACHE_DIR=/data/cache ./export_all.sh  # Custom paths

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODELS_ZOO="${MODELS_ZOO:-/export/ai_models/model-zoo}"
CACHE_DIR="${CACHE_DIR:-/export/ai_models/triton}"
REPO_DIR="${REPO_DIR:-/models/repository}"
CUDA_DEVICE="${CUDA_DEVICE:-0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log_step() {
    echo ""
    echo "================================================================"
    echo "  $1"
    echo "================================================================"
}

run_export() {
    local description="$1"
    local skip_check_path="$2"
    shift 2

    # Skip if model already exists (check for .onnx or .plan file)
    if [ -n "$skip_check_path" ] && { [ -f "$skip_check_path" ] || [ -f "${skip_check_path%.onnx}.plan" ]; }; then
        echo "  -> ${description}... CACHED (skipping)"
        SKIP_COUNT=$((SKIP_COUNT + 1))
        return 0
    fi

    echo "  -> ${description}..."
    # Ensure output directories exist for all --output-path and --output-dir args
    local args=("$@")
    for ((i=0; i<${#args[@]}; i++)); do
        if [ "${args[i]}" = "--output-path" ] && [ $((i+1)) -lt ${#args[@]} ]; then
            mkdir -p "$(dirname "${args[i+1]}")"
        elif [ "${args[i]}" = "--output-dir" ] && [ $((i+1)) -lt ${#args[@]} ]; then
            mkdir -p "${args[i+1]}"
        fi
    done
    if [ -n "$skip_check_path" ]; then
        mkdir -p "$(dirname "$skip_check_path")"
    fi
    if "$@"; then
        echo "     OK"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "     FAILED"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

check_file() {
    local path="$1"
    local label="$2"
    if [ -f "$path" ]; then
        local size
        size=$(stat -c%s "$path" 2>/dev/null || stat -f%z "$path" 2>/dev/null || echo 0)
        local size_mb=$((size / 1024 / 1024))
        echo "     ${label}: ${size_mb} MB"
        return 0
    else
        echo "     ${label}: MISSING"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo "=== Triton Model Export Pipeline ==="
echo ""
echo "  Model zoo:  ${MODELS_ZOO}"
echo "  Cache dir:  ${CACHE_DIR}"
echo "  Repository: ${REPO_DIR}"
echo "  CUDA device: ${CUDA_DEVICE}"
echo ""
echo "  Started at: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"

# ---------------------------------------------------------------------------
# Phase 1: GPU model exports (TensorRT + ONNX via Ultralytics)
# ---------------------------------------------------------------------------
log_step "[1/4] Exporting GPU models (TensorRT + ONNX)..."

# YOLOv8n threat detection -> ONNX (NEM-5551: promoted to GPU, VRAM constraint removed)
run_export "YOLOv8n threat detection -> ONNX" "${CACHE_DIR}/threat/1/model.onnx" \
    python3 "${SCRIPT_DIR}/export_yolo_threat.py" \
        --model-path "${MODELS_ZOO}/threat-detection-yolov8n/weights/best.pt" \
        --output-path "${CACHE_DIR}/threat/1/model.onnx" \
        --device "${CUDA_DEVICE}" \
        --onnx-only
# Rename if Ultralytics produced a differently-named .onnx file
[ -f "${CACHE_DIR}/threat/1/best.onnx" ] && mv "${CACHE_DIR}/threat/1/best.onnx" "${CACHE_DIR}/threat/1/model.onnx"

# YOLO26m -> ONNX (FP32, no INT8 - avoids ONNX Runtime provider compatibility issues)
run_export "YOLO26m -> ONNX" "${CACHE_DIR}/yolo26/1/model.onnx" \
    python3 "${SCRIPT_DIR}/export_yolo26.py" \
        --model-path "${MODELS_ZOO}/yolo26/yolo26m.pt" \
        --output-path "${CACHE_DIR}/yolo26/1/model.onnx" \
        --device "${CUDA_DEVICE}"
# Rename if Ultralytics produced a differently-named .onnx file
[ -f "${CACHE_DIR}/yolo26/1/yolo26m.onnx" ] && mv "${CACHE_DIR}/yolo26/1/yolo26m.onnx" "${CACHE_DIR}/yolo26/1/model.onnx"

# ---------------------------------------------------------------------------
# Phase 2: ONNX exports (can run on CPU)
# ---------------------------------------------------------------------------
log_step "[2/4] Exporting ONNX models (CPU compatible)..."

# Person Re-ID -> ONNX
run_export "OSNet-AIN x1.0 Re-ID -> ONNX" "${CACHE_DIR}/reid/1/model.onnx" \
    python3 "${SCRIPT_DIR}/export_reid.py" \
        --model-path "${MODELS_ZOO}/osnet-ain-x1-0/osnet_ain_x1_0_msmt17.pth" \
        --output-path "${CACHE_DIR}/reid/1/model.onnx"

# ---------------------------------------------------------------------------
# Phase 3: Verify config files
# ---------------------------------------------------------------------------
log_step "[3/4] Verifying Triton model repository config files..."

CONFIG_OK=true
for model in yolo26 threat reid; do
    config_path="${REPO_DIR}/${model}/config.pbtxt"
    if [ -f "$config_path" ]; then
        echo "  [OK] ${model}/config.pbtxt"
    else
        echo "  [MISSING] ${model}/config.pbtxt"
        CONFIG_OK=false
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
done

if [ "$CONFIG_OK" = false ]; then
    echo ""
    echo "  WARNING: Some config.pbtxt files are missing."
    echo "  These must be created before Triton can serve the models."
fi

# ---------------------------------------------------------------------------
# Phase 4: Validate exported files
# ---------------------------------------------------------------------------
log_step "[4/4] Validating exported model files..."

echo ""
echo "  ONNX models (.onnx):"
check_file "${CACHE_DIR}/yolo26/1/model.onnx"                 "yolo26"              || true
check_file "${CACHE_DIR}/threat/1/model.onnx"                 "threat"              || true
check_file "${CACHE_DIR}/reid/1/model.onnx"                   "reid"                || true

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "================================================================"
echo "  Export Pipeline Complete"
echo "================================================================"
echo ""
echo "  Passed: ${PASS_COUNT}"
echo "  Failed: ${FAIL_COUNT}"
echo "  Finished at: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo "  WARNING: ${FAIL_COUNT} export(s) failed. Review logs above."
    echo "  Full inference validation will run when Triton starts."
    exit 1
fi

echo "  All exports succeeded."
echo "  Run 'tritonserver --model-repository=${REPO_DIR}' to load models."
echo ""
echo "=== Export complete ==="
