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

# Download Nemotron Mini 4B Instruct (quantized GGUF)
NEMOTRON_DIR="${SCRIPT_DIR}/nemotron"
NEMOTRON_MODEL="nemotron-mini-4b-instruct-q4_k_m.gguf"
NEMOTRON_PATH="${NEMOTRON_DIR}/${NEMOTRON_MODEL}"
NEMOTRON_URL="https://huggingface.co/bartowski/nemotron-mini-4b-instruct-GGUF/resolve/main/nemotron-mini-4b-instruct-Q4_K_M.gguf"

mkdir -p "$NEMOTRON_DIR"

if [ -f "$NEMOTRON_PATH" ]; then
    echo "[SKIP] Nemotron model already exists: $NEMOTRON_PATH"
else
    echo "[DOWNLOAD] Nemotron Mini 4B Instruct (Q4_K_M) - ~2.5GB"
    echo "Source: $NEMOTRON_URL"
    echo "Target: $NEMOTRON_PATH"
    echo ""
    wget -O "$NEMOTRON_PATH" "$NEMOTRON_URL"
    echo ""
    echo "[OK] Nemotron model downloaded successfully"
fi

echo ""

# RT-DETRv2 model (from Hugging Face transformers)
RTDETR_DIR="${SCRIPT_DIR}/rtdetr"
mkdir -p "$RTDETR_DIR"

echo "[INFO] RT-DETRv2 model will be downloaded automatically on first use"
echo "       via Hugging Face transformers library"
echo "       Model: PekingU/rtdetr_r50vd_coco_o365"
echo "       Size: ~160MB"

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
