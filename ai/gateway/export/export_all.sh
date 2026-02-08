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
    shift
    echo "  -> ${description}..."
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

# CLIP -> ONNX (TensorRT too large for 4GB A400, ONNX Runtime is sufficient)
run_export "CLIP ViT-L/14 -> ONNX" \
    python3 "${SCRIPT_DIR}/export_clip.py" \
        --model-path "${MODELS_ZOO}/clip-vit-l" \
        --output-path "${CACHE_DIR}/clip/1/model.plan" \
        --onnx-only
# Rename vision_encoder.onnx -> model.onnx for Triton
[ -f "${CACHE_DIR}/clip/1/vision_encoder.onnx" ] && mv "${CACHE_DIR}/clip/1/vision_encoder.onnx" "${CACHE_DIR}/clip/1/model.onnx"

# Fashion-CLIP -> ONNX
run_export "Fashion-CLIP -> ONNX" \
    python3 "${SCRIPT_DIR}/export_fashion_clip.py" \
        --model-path "${MODELS_ZOO}/fashion-clip" \
        --output-path "${CACHE_DIR}/fashion_clip/1/model.plan" \
        --onnx-only
[ -f "${CACHE_DIR}/fashion_clip/1/vision_encoder.onnx" ] && mv "${CACHE_DIR}/fashion_clip/1/vision_encoder.onnx" "${CACHE_DIR}/fashion_clip/1/model.onnx"

# YOLOv8n-pose -> ONNX (TensorRT too large for 4GB A400)
run_export "YOLOv8n-pose -> ONNX" \
    python3 "${SCRIPT_DIR}/export_yolo_pose.py" \
        --model-path "${MODELS_ZOO}/yolov8n-pose/yolov8n-pose.pt" \
        --output-path "${CACHE_DIR}/pose/1/model.onnx" \
        --device "${CUDA_DEVICE}" \
        --onnx-only
# Rename if Ultralytics produced a differently-named .onnx file
[ -f "${CACHE_DIR}/pose/1/yolov8n-pose.onnx" ] && mv "${CACHE_DIR}/pose/1/yolov8n-pose.onnx" "${CACHE_DIR}/pose/1/model.onnx"

# YOLOv8n threat detection -> ONNX (TensorRT too large for 4GB A400)
run_export "YOLOv8n threat detection -> ONNX" \
    python3 "${SCRIPT_DIR}/export_yolo_threat.py" \
        --model-path "${MODELS_ZOO}/threat-detection-yolov8n/weights/best.pt" \
        --output-path "${CACHE_DIR}/threat/1/model.onnx" \
        --device "${CUDA_DEVICE}" \
        --onnx-only
# Rename if Ultralytics produced a differently-named .onnx file
[ -f "${CACHE_DIR}/threat/1/best.onnx" ] && mv "${CACHE_DIR}/threat/1/best.onnx" "${CACHE_DIR}/threat/1/model.onnx"

# YOLO26 engine (pre-built, just copy)
run_export "YOLO26 TensorRT engine -> copy" \
    python3 "${SCRIPT_DIR}/copy_yolo26_engine.py" \
        --model-path "${MODELS_ZOO}/yolo26" \
        --output-path "${CACHE_DIR}/yolo26/1/model.plan"

# ---------------------------------------------------------------------------
# Phase 2: ONNX exports (can run on CPU)
# ---------------------------------------------------------------------------
log_step "[2/4] Exporting ONNX models (CPU compatible)..."

# Vehicle classifier -> ONNX
run_export "Vehicle classifier (ResNet-50) -> ONNX" \
    python3 "${SCRIPT_DIR}/export_vehicle.py" \
        --model-path "${MODELS_ZOO}/vehicle-segment-classification" \
        --output-path "${CACHE_DIR}/vehicle/1/model.onnx"

# Demographics (age + gender) -> ONNX
run_export "Demographics (age + gender) -> ONNX" \
    python3 "${SCRIPT_DIR}/export_demographics.py" \
        --model-path-age "${MODELS_ZOO}/vit-age-classifier" \
        --model-path-gender "${MODELS_ZOO}/vit-gender-classifier" \
        --output-dir "${CACHE_DIR}"

# Pet classifier -> ONNX
run_export "Pet classifier (ResNet-18) -> ONNX" \
    python3 "${SCRIPT_DIR}/export_pet.py" \
        --model-path "${MODELS_ZOO}/pet-classifier" \
        --output-path "${CACHE_DIR}/pet/1/model.onnx"

# Depth estimation -> ONNX
run_export "Depth Anything V2 Small -> ONNX" \
    python3 "${SCRIPT_DIR}/export_depth.py" \
        --model-path "${MODELS_ZOO}/depth-anything-v2-small" \
        --output-path "${CACHE_DIR}/depth/1/model.onnx"

# Person Re-ID -> ONNX
run_export "OSNet-x0.25 Re-ID -> ONNX" \
    python3 "${SCRIPT_DIR}/export_reid.py" \
        --model-path "${MODELS_ZOO}/osnet-x0-25/osnet_x0_25.pth" \
        --output-path "${CACHE_DIR}/reid/1/model.onnx"

# ---------------------------------------------------------------------------
# Phase 3: Verify config files
# ---------------------------------------------------------------------------
log_step "[3/4] Verifying Triton model repository config files..."

CONFIG_OK=true
for model in yolo26 clip pose threat fashion_clip vehicle demographics_age demographics_gender pet depth reid florence2 xclip_action; do
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
echo "  TensorRT engines (.plan):"
check_file "${CACHE_DIR}/yolo26/1/model.plan"         "yolo26"        || true

echo ""
echo "  ONNX models (.onnx):"
check_file "${CACHE_DIR}/pose/1/model.onnx"                 "pose"                || true
check_file "${CACHE_DIR}/threat/1/model.onnx"               "threat"              || true
check_file "${CACHE_DIR}/clip/1/model.onnx"                 "clip"                || true
check_file "${CACHE_DIR}/fashion_clip/1/model.onnx"         "fashion_clip"        || true
check_file "${CACHE_DIR}/vehicle/1/model.onnx"              "vehicle"             || true
check_file "${CACHE_DIR}/demographics_age/1/model.onnx"     "demographics_age"    || true
check_file "${CACHE_DIR}/demographics_gender/1/model.onnx"  "demographics_gender" || true
check_file "${CACHE_DIR}/pet/1/model.onnx"                  "pet"                 || true
check_file "${CACHE_DIR}/depth/1/model.onnx"                "depth"               || true
check_file "${CACHE_DIR}/reid/1/model.onnx"                 "reid"                || true

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
