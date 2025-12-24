#!/bin/bash
#
# Download AI models for home security system
#
# Models:
#   - Nemotron Mini 4B Instruct (Q4_K_M quantized) - ~2.5GB
#   - RT-DETRv2 (from Hugging Face transformers) - ~160MB
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "AI Model Download Script"
echo "=========================================="
echo ""

# Download (or locate) Nemotron Mini 4B Instruct (quantized GGUF)
NEMOTRON_DIR="${SCRIPT_DIR}/nemotron"
NEMOTRON_MODEL="nemotron-mini-4b-instruct-q4_k_m.gguf"
NEMOTRON_PATH="${NEMOTRON_DIR}/${NEMOTRON_MODEL}"
NEMOTRON_URL="https://huggingface.co/bartowski/nemotron-mini-4b-instruct-GGUF/resolve/main/nemotron-mini-4b-instruct-Q4_K_M.gguf"

mkdir -p "$NEMOTRON_DIR"

if [ -f "$NEMOTRON_PATH" ]; then
    echo "[SKIP] Nemotron model already exists: $NEMOTRON_PATH"
else
    echo "[INFO] Resolving Nemotron GGUF model..."
    echo "       Target: $NEMOTRON_PATH"

    # Prefer existing on-disk model caches before downloading.
    if [ -n "${NEMOTRON_GGUF_PATH:-}" ] && [ -f "${NEMOTRON_GGUF_PATH}" ]; then
        echo "[COPY] Using NEMOTRON_GGUF_PATH=${NEMOTRON_GGUF_PATH}"
        cp "${NEMOTRON_GGUF_PATH}" "${NEMOTRON_PATH}"
        echo "[OK] Nemotron model copied"
    else
        SEARCH_ROOTS=()
        if [ -n "${NEMOTRON_MODELS_DIR:-}" ]; then
            SEARCH_ROOTS+=("${NEMOTRON_MODELS_DIR}")
        fi
        SEARCH_ROOTS+=("/export/ai_models/nemotron" "/export/ai_models/weights" "/export/ai_models/cache")

        FOUND_GGUF=""
        for root in "${SEARCH_ROOTS[@]}"; do
            if [ -d "${root}" ]; then
                FOUND_GGUF="$(find "${root}" -type f -name '*.gguf' 2>/dev/null | grep -i 'nemotron' | head -n 1 || true)"
                if [ -z "${FOUND_GGUF}" ]; then
                    FOUND_GGUF="$(find "${root}" -type f -name '*.gguf' 2>/dev/null | head -n 1 || true)"
                fi
                if [ -n "${FOUND_GGUF}" ]; then
                    break
                fi
            fi
        done

        if [ -n "${FOUND_GGUF}" ]; then
            echo "[FOUND] ${FOUND_GGUF}"
            cp "${FOUND_GGUF}" "${NEMOTRON_PATH}"
            echo "[OK] Nemotron model copied from existing model store"
        else
            echo "[DOWNLOAD] Nemotron Mini 4B Instruct (Q4_K_M) - ~2.5GB"
            echo "Source: ${NEMOTRON_URL}"
            echo "Target: ${NEMOTRON_PATH}"
            echo ""
            # Do not fail the entire script if offline; print a warning and continue.
            set +e
            wget -O "${NEMOTRON_PATH}" "${NEMOTRON_URL}"
            WGET_EXIT=$?
            set -e
            if [ $WGET_EXIT -ne 0 ]; then
                echo ""
                echo "[WARN] Nemotron download failed (offline or URL issue)."
                echo "       Provide one of the following to use existing models on disk:"
                echo "       - NEMOTRON_GGUF_PATH=/path/to/model.gguf"
                echo "       - NEMOTRON_MODELS_DIR=/export/ai_models/nemotron (or similar)"
                echo ""
                # Remove partial file if any
                rm -f "${NEMOTRON_PATH}"
            else
                echo ""
                echo "[OK] Nemotron model downloaded successfully"
            fi
        fi
    fi
fi

echo ""

#
# RT-DETRv2 ONNX model
#
# The RT-DETR server in this repo expects an ONNX file at:
#   ai/rtdetr/rtdetrv2_r50vd.onnx
#
# Many deployments already have model artifacts on disk (e.g. /export/ai_models/...).
# This script tries, in order:
#   1) Use RTDETR_ONNX_PATH if set
#   2) Search common model roots (default /export/ai_models/rt-detrv2)
#   3) If RTDETR_ONNX_URL is set, download it
#
RTDETR_DIR="${SCRIPT_DIR}/rtdetr"
RTDETR_ONNX_NAME="rtdetrv2_r50vd.onnx"
RTDETR_ONNX_TARGET="${RTDETR_DIR}/${RTDETR_ONNX_NAME}"

mkdir -p "$RTDETR_DIR"

if [ -f "$RTDETR_ONNX_TARGET" ]; then
    echo "[SKIP] RT-DETRv2 ONNX already exists: $RTDETR_ONNX_TARGET"
else
    echo "[INFO] Resolving RT-DETRv2 ONNX model..."
    echo "       Target: $RTDETR_ONNX_TARGET"

    if [ -n "${RTDETR_ONNX_PATH:-}" ] && [ -f "${RTDETR_ONNX_PATH}" ]; then
        echo "[COPY] Using RTDETR_ONNX_PATH=${RTDETR_ONNX_PATH}"
        cp "${RTDETR_ONNX_PATH}" "${RTDETR_ONNX_TARGET}"
        echo "[OK] RT-DETRv2 ONNX copied"
    else
        # Default search roots (customizable)
        SEARCH_ROOTS=()
        if [ -n "${RTDETR_MODELS_DIR:-}" ]; then
            SEARCH_ROOTS+=("${RTDETR_MODELS_DIR}")
        fi
        SEARCH_ROOTS+=("/export/ai_models/rt-detrv2" "/export/ai_models/rt-detrv2/weights" "/export/ai_models/rt-detrv2/optimized")

        FOUND_ONNX=""
        for root in "${SEARCH_ROOTS[@]}"; do
            if [ -d "${root}" ]; then
                # Prefer files that mention r50vd; otherwise take first .onnx found.
                FOUND_ONNX="$(find "${root}" -type f -name '*.onnx' 2>/dev/null | grep -i 'r50vd' | head -n 1 || true)"
                if [ -z "${FOUND_ONNX}" ]; then
                    FOUND_ONNX="$(find "${root}" -type f -name '*.onnx' 2>/dev/null | head -n 1 || true)"
                fi
                if [ -n "${FOUND_ONNX}" ]; then
                    break
                fi
            fi
        done

        if [ -n "${FOUND_ONNX}" ]; then
            echo "[FOUND] ${FOUND_ONNX}"
            cp "${FOUND_ONNX}" "${RTDETR_ONNX_TARGET}"
            echo "[OK] RT-DETRv2 ONNX copied from existing model store"
        else
            if [ -n "${RTDETR_ONNX_URL:-}" ]; then
                echo "[DOWNLOAD] RT-DETRv2 ONNX from RTDETR_ONNX_URL"
                echo "Source: ${RTDETR_ONNX_URL}"
                wget -O "${RTDETR_ONNX_TARGET}" "${RTDETR_ONNX_URL}"
                echo "[OK] RT-DETRv2 ONNX downloaded successfully"
            else
                echo "[WARN] RT-DETRv2 ONNX not found."
                echo "       Provide one of the following:"
                echo "       - RTDETR_ONNX_PATH=/path/to/model.onnx"
                echo "       - RTDETR_MODELS_DIR=/export/ai_models/rt-detrv2 (or similar)"
                echo "       - RTDETR_ONNX_URL=https://.../rtdetrv2_r50vd.onnx"
                echo ""
                echo "       The detector server will still start, but /detect will return 503 until the model is present."
            fi
        fi
    fi
fi

echo ""
echo "=========================================="
echo "Download Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Ensure llama.cpp is installed (llama-server command available)"
echo "  2. Start the detection server: ./ai/start_detector.sh"
echo "  3. Start the LLM server: ./ai/start_llm.sh"
echo ""
