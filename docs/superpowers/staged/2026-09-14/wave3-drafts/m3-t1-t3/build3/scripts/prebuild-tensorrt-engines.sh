#!/usr/bin/env bash
# DEPRECATED: Use ai/gateway/export/export_all.sh instead (Triton gateway mode)
#
# Pre-build TensorRT engines for all AI services (NEM-4999)
#
# This script pre-builds TensorRT engines for YOLO26, CLIP, and enrichment-light
# models. Run this once after deploying to a new GPU to eliminate cold-start latency.
#
# TensorRT engines are GPU-architecture-specific. An engine built on one GPU
# (e.g., RTX A5500 / sm_86) will NOT work on a different GPU architecture
# (e.g., RTX A400 / sm_75). You must rebuild engines for each target GPU.
#
# Prerequisites:
#   - NVIDIA GPU with CUDA support
#   - AI model files downloaded (run ./ai/download_models.sh first)
#   - Python environment with ultralytics, tensorrt packages
#
# Usage:
#   ./scripts/prebuild-tensorrt-engines.sh              # Build all engines
#   ./scripts/prebuild-tensorrt-engines.sh yolo26        # Build YOLO26 only
#   ./scripts/prebuild-tensorrt-engines.sh clip          # Build CLIP only
#   ./scripts/prebuild-tensorrt-engines.sh enrichment    # Build enrichment models only
#
# Or via podman exec (for containerized builds):
#   podman exec -it ai-yolo26 python build_engine.py \
#       --model /models/yolo26/yolo26m.pt \
#       --output /models/yolo26/exports/yolo26m_fp16.engine
#
# GPU Compute Capabilities (for reference):
#   sm_75: RTX 2080 / T4 / RTX A400
#   sm_86: RTX 3090 / A5500 / A40
#   sm_89: RTX 4090 / L4 / L40
#   sm_90: H100 / H200

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default model paths (override via environment variables)
AI_MODELS_PATH="${AI_MODELS_PATH:-/export/ai_models}"
YOLO26_PT_PATH="${AI_MODELS_PATH}/model-zoo/yolo26/yolo26m.pt"
YOLO26_ENGINE_PATH="${AI_MODELS_PATH}/model-zoo/yolo26/exports/yolo26m_fp16.engine"

info() { echo "[INFO] $*"; }
warn() { echo "[WARN] $*" >&2; }
error() { echo "[ERROR] $*" >&2; }

check_cuda() {
    if ! python3 -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
        error "CUDA not available. TensorRT engine building requires an NVIDIA GPU."
        exit 1
    fi
    GPU_NAME=$(python3 -c "import torch; print(torch.cuda.get_device_name(0))" 2>/dev/null || echo "unknown")
    GPU_CC=$(python3 -c "import torch; p=torch.cuda.get_device_properties(0); print(f'sm_{p.major}{p.minor}')" 2>/dev/null || echo "unknown")
    info "GPU detected: ${GPU_NAME} (${GPU_CC})"
}

build_yolo26() {
    info "=== Building YOLO26 TensorRT Engine ==="
    if [ ! -f "$YOLO26_PT_PATH" ]; then
        warn "YOLO26 model not found at $YOLO26_PT_PATH"
        warn "Download models first: ./ai/download_models.sh"
        return 1
    fi

    mkdir -p "$(dirname "$YOLO26_ENGINE_PATH")"

    python3 "$PROJECT_ROOT/ai/yolo26/build_engine.py" \
        --model "$YOLO26_PT_PATH" \
        --output "$YOLO26_ENGINE_PATH" \
        --imgsz 640 \
        --half

    if [ -f "$YOLO26_ENGINE_PATH" ]; then
        info "YOLO26 engine built: $YOLO26_ENGINE_PATH"
    else
        error "YOLO26 engine build failed"
        return 1
    fi
}

build_clip() {
    info "=== Building CLIP TensorRT Engine ==="
    CLIP_MODEL_PATH="${AI_MODELS_PATH}/model-zoo/siglip2-base-patch16-224"
    CLIP_ENGINE_PATH="${AI_MODELS_PATH}/model-zoo/siglip2-base-patch16-224/vision_encoder_fp16.engine"

    if [ ! -d "$CLIP_MODEL_PATH" ]; then
        warn "CLIP model not found at $CLIP_MODEL_PATH"
        warn "Download models first: ./ai/download_models.sh"
        return 1
    fi

    python3 "$PROJECT_ROOT/ai/clip/build_engine.py" \
        --model-path "$CLIP_MODEL_PATH" \
        --output "$CLIP_ENGINE_PATH" \
        --precision fp16

    if [ -f "$CLIP_ENGINE_PATH" ]; then
        info "CLIP engine built: $CLIP_ENGINE_PATH"
    else
        error "CLIP engine build failed"
        return 1
    fi
}

build_enrichment() {
    info "=== Building Enrichment TensorRT Engines ==="

    # Pose model
    POSE_PT_PATH="${AI_MODELS_PATH}/model-zoo/yolov8n-pose/yolov8n-pose.pt"
    POSE_ENGINE_PATH="${AI_MODELS_PATH}/model-zoo/yolov8n-pose/yolov8n-pose.engine"
    if [ -f "$POSE_PT_PATH" ]; then
        info "Building pose TensorRT engine..."
        python3 "$PROJECT_ROOT/ai/enrichment/scripts/export_pose_tensorrt.py" \
            --model "$POSE_PT_PATH" \
            --output "$POSE_ENGINE_PATH" \
            --precision fp16 2>/dev/null || warn "Pose engine build failed"
    else
        warn "Pose model not found: $POSE_PT_PATH"
    fi

    # Threat model
    THREAT_PT_PATH="${AI_MODELS_PATH}/model-zoo/threat-detection-yolov8n/weights/best.pt"
    THREAT_ENGINE_PATH="${AI_MODELS_PATH}/model-zoo/threat-detection-yolov8n/weights/best.engine"
    if [ -f "$THREAT_PT_PATH" ]; then
        info "Building threat TensorRT engine..."
        python3 "$PROJECT_ROOT/ai/enrichment/scripts/export_threat_tensorrt.py" \
            --model "$THREAT_PT_PATH" \
            --precision fp16 2>/dev/null || warn "Threat engine build failed"
    else
        warn "Threat model not found: $THREAT_PT_PATH"
    fi
}

main() {
    local target="${1:-all}"

    info "TensorRT Engine Pre-build Script (NEM-4999)"
    info "Target: $target"

    check_cuda

    case "$target" in
        yolo26)
            build_yolo26
            ;;
        clip)
            build_clip
            ;;
        enrichment)
            build_enrichment
            ;;
        all)
            build_yolo26 || true
            build_clip || true
            build_enrichment || true
            ;;
        *)
            error "Unknown target: $target"
            echo "Usage: $0 [yolo26|clip|enrichment|all]"
            exit 1
            ;;
    esac

    info "Pre-build complete."
}

main "$@"
