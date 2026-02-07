#!/bin/bash
# Download GGUF quantizations of Nemotron-3-Nano-30B-A3B from HuggingFace.
#
# Downloads from: bartowski/nvidia_Nemotron-3-Nano-30B-A3B-GGUF
# Saves to:       ${AI_MODELS_PATH}/nemotron/
#
# Usage:
#   ./scripts/benchmark/download_gguf.sh iq4_xs        # Download IQ4_XS
#   ./scripts/benchmark/download_gguf.sh q4_k_s        # Download Q4_K_S
#   ./scripts/benchmark/download_gguf.sh q4_k_m        # Download Q4_K_M
#   ./scripts/benchmark/download_gguf.sh q3_k_m        # Download Q3_K_M
#   ./scripts/benchmark/download_gguf.sh --list         # Show available quantizations
#
# Environment:
#   AI_MODELS_PATH  Base path for AI models (default: /export/ai_models)
#   HF_TOKEN        HuggingFace token for gated models (optional for public repos)
#
# Dependencies:
#   - huggingface-cli (pip install huggingface-hub) OR wget/curl

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────
AI_MODELS_PATH="${AI_MODELS_PATH:-/export/ai_models}"
DOWNLOAD_DIR="${AI_MODELS_PATH}/nemotron"
HF_REPO="bartowski/nvidia_Nemotron-3-Nano-30B-A3B-GGUF"

# ─── Available quantizations ─────────────────────────────────────────────────
# Map from lowercase shorthand to actual filename on HuggingFace.
# File sizes are approximate.
declare -A QUANT_FILES=(
    # Importance Matrix quantizations (imatrix - better quality at same size)
    ["iq4_xs"]="nvidia_Nemotron-3-Nano-30B-A3B-IQ4_XS.gguf"
    ["iq4_nl"]="nvidia_Nemotron-3-Nano-30B-A3B-IQ4_NL.gguf"
    ["iq3_m"]="nvidia_Nemotron-3-Nano-30B-A3B-IQ3_M.gguf"
    ["iq3_xs"]="nvidia_Nemotron-3-Nano-30B-A3B-IQ3_XS.gguf"
    ["iq2_m"]="nvidia_Nemotron-3-Nano-30B-A3B-IQ2_M.gguf"

    # Standard k-quant quantizations
    ["q8_0"]="nvidia_Nemotron-3-Nano-30B-A3B-Q8_0.gguf"
    ["q6_k"]="nvidia_Nemotron-3-Nano-30B-A3B-Q6_K.gguf"
    ["q5_k_m"]="nvidia_Nemotron-3-Nano-30B-A3B-Q5_K_M.gguf"
    ["q5_k_s"]="nvidia_Nemotron-3-Nano-30B-A3B-Q5_K_S.gguf"
    ["q4_k_m"]="nvidia_Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf"
    ["q4_k_s"]="nvidia_Nemotron-3-Nano-30B-A3B-Q4_K_S.gguf"
    ["q3_k_m"]="nvidia_Nemotron-3-Nano-30B-A3B-Q3_K_M.gguf"
    ["q3_k_s"]="nvidia_Nemotron-3-Nano-30B-A3B-Q3_K_S.gguf"
    ["q3_k_l"]="nvidia_Nemotron-3-Nano-30B-A3B-Q3_K_L.gguf"
    ["q2_k_l"]="nvidia_Nemotron-3-Nano-30B-A3B-Q2_K_L.gguf"
    ["q2_k"]="nvidia_Nemotron-3-Nano-30B-A3B-Q2_K.gguf"
)

# Approximate sizes for display
declare -A QUANT_SIZES=(
    ["iq4_xs"]="~8.5 GB"
    ["iq4_nl"]="~8.8 GB"
    ["iq3_m"]="~7.0 GB"
    ["iq3_xs"]="~6.4 GB"
    ["iq2_m"]="~5.3 GB"
    ["q8_0"]="~17.0 GB"
    ["q6_k"]="~13.0 GB"
    ["q5_k_m"]="~11.0 GB"
    ["q5_k_s"]="~10.5 GB"
    ["q4_k_m"]="~9.5 GB"
    ["q4_k_s"]="~9.0 GB"
    ["q3_k_m"]="~7.5 GB"
    ["q3_k_s"]="~7.0 GB"
    ["q3_k_l"]="~8.0 GB"
    ["q2_k_l"]="~6.0 GB"
    ["q2_k"]="~5.5 GB"
)

# Quality/size tradeoff notes
declare -A QUANT_NOTES=(
    ["iq4_xs"]="Best quality-per-bit at 4-bit. Recommended candidate for benchmarking."
    ["iq4_nl"]="Slightly larger than IQ4_XS, marginally better quality."
    ["iq3_m"]="Good 3-bit imatrix. Significant quality loss possible."
    ["iq3_xs"]="Aggressive 3-bit. Noticeable quality degradation expected."
    ["iq2_m"]="Experimental 2-bit. Likely significant quality loss."
    ["q8_0"]="Near-lossless. Too large for most single-GPU setups."
    ["q6_k"]="Excellent quality. Requires ~13GB VRAM."
    ["q5_k_m"]="Very good quality. Good balance for 16GB+ GPUs."
    ["q5_k_s"]="Good quality, slightly smaller than Q5_K_M."
    ["q4_k_m"]="Production default. Good quality/size balance for 24GB GPU."
    ["q4_k_s"]="Slightly smaller than Q4_K_M, minor quality difference."
    ["q3_k_m"]="Compact. Some quality loss, good for VRAM-constrained setups."
    ["q3_k_s"]="Smaller than Q3_K_M. More quality loss."
    ["q3_k_l"]="Larger 3-bit variant. Better quality than Q3_K_S/M."
    ["q2_k_l"]="Aggressive quantization. Significant quality loss expected."
    ["q2_k"]="Most aggressive. Expect notable quality degradation."
)

# ─── Functions ────────────────────────────────────────────────────────────────

usage() {
    cat <<EOF
Usage: $0 <quantization> [--list]

Download GGUF quantizations of Nemotron-3-Nano-30B-A3B from HuggingFace.

Arguments:
  <quantization>   Quantization format to download (e.g., iq4_xs, q4_k_m)
  --list           List all available quantizations with sizes and notes

Environment Variables:
  AI_MODELS_PATH   Base path for AI models (default: /export/ai_models)
  HF_TOKEN         HuggingFace token (optional for public repos)

Examples:
  $0 iq4_xs                    # Download IQ4_XS quantization
  $0 q4_k_s                   # Download Q4_K_S quantization
  $0 --list                    # Show available quantizations

Downloaded files are saved to: \${AI_MODELS_PATH}/nemotron/
EOF
}

list_quantizations() {
    echo "Available Nemotron-3-Nano-30B-A3B GGUF Quantizations"
    echo "====================================================="
    echo ""
    echo "Source: https://huggingface.co/${HF_REPO}"
    echo "Download directory: ${DOWNLOAD_DIR}"
    echo ""

    # Group by type
    echo "--- Importance Matrix (imatrix) Quantizations ---"
    echo "  These use importance matrices for better quality-per-bit."
    echo ""
    printf "  %-12s %-12s %s\n" "Format" "Size" "Notes"
    printf "  %-12s %-12s %s\n" "------" "----" "-----"
    for q in iq4_xs iq4_nl iq3_m iq3_xs iq2_m; do
        printf "  %-12s %-12s %s\n" "$q" "${QUANT_SIZES[$q]}" "${QUANT_NOTES[$q]}"
    done

    echo ""
    echo "--- Standard k-quant Quantizations ---"
    echo ""
    printf "  %-12s %-12s %s\n" "Format" "Size" "Notes"
    printf "  %-12s %-12s %s\n" "------" "----" "-----"
    for q in q8_0 q6_k q5_k_m q5_k_s q4_k_m q4_k_s q3_k_m q3_k_s q3_k_l q2_k_l q2_k; do
        printf "  %-12s %-12s %s\n" "$q" "${QUANT_SIZES[$q]}" "${QUANT_NOTES[$q]}"
    done

    echo ""
    echo "Recommended benchmark pairs:"
    echo "  Production baseline:  q4_k_m  (~9.5 GB, current default)"
    echo "  Primary candidate:    iq4_xs  (~8.5 GB, best quality-per-bit at 4-bit)"
    echo "  Size reduction test:  q3_k_m  (~7.5 GB, tests quality floor)"
}

download_with_huggingface_cli() {
    local filename="$1"
    echo "Downloading with huggingface-cli..."
    huggingface-cli download "${HF_REPO}" "${filename}" \
        --local-dir "${DOWNLOAD_DIR}" \
        --local-dir-use-symlinks False
}

download_with_wget() {
    local filename="$1"
    local url="https://huggingface.co/${HF_REPO}/resolve/main/${filename}"
    local output="${DOWNLOAD_DIR}/${filename}"

    echo "Downloading with wget..."
    echo "  URL: ${url}"
    echo "  Destination: ${output}"

    local auth_header=""
    if [ -n "${HF_TOKEN:-}" ]; then
        auth_header="--header=Authorization: Bearer ${HF_TOKEN}"
    fi

    wget -c ${auth_header} -O "${output}" "${url}"
}

download_with_curl() {
    local filename="$1"
    local url="https://huggingface.co/${HF_REPO}/resolve/main/${filename}"
    local output="${DOWNLOAD_DIR}/${filename}"

    echo "Downloading with curl..."
    echo "  URL: ${url}"
    echo "  Destination: ${output}"

    local auth_args=()
    if [ -n "${HF_TOKEN:-}" ]; then
        auth_args=(-H "Authorization: Bearer ${HF_TOKEN}")
    fi

    curl -L -C - "${auth_args[@]}" -o "${output}" "${url}"
}

# ─── Main ─────────────────────────────────────────────────────────────────────

if [ $# -eq 0 ]; then
    usage
    exit 1
fi

# Handle --list flag
if [ "$1" = "--list" ] || [ "$1" = "-l" ]; then
    list_quantizations
    exit 0
fi

# Handle --help flag
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    usage
    exit 0
fi

# Validate quantization format
QUANT_FORMAT=$(echo "$1" | tr '[:upper:]' '[:lower:]')

if [ -z "${QUANT_FILES[$QUANT_FORMAT]+x}" ]; then
    echo "ERROR: Unknown quantization format: $1"
    echo ""
    echo "Available formats:"
    for q in "${!QUANT_FILES[@]}"; do
        echo "  $q"
    done | sort
    echo ""
    echo "Run '$0 --list' for details."
    exit 1
fi

FILENAME="${QUANT_FILES[$QUANT_FORMAT]}"
DEST_PATH="${DOWNLOAD_DIR}/${FILENAME}"

echo "Nemotron-3-Nano-30B-A3B GGUF Download"
echo "======================================="
echo "  Format:      ${QUANT_FORMAT}"
echo "  File:        ${FILENAME}"
echo "  Size:        ${QUANT_SIZES[$QUANT_FORMAT]}"
echo "  Destination: ${DEST_PATH}"
echo "  Source:      ${HF_REPO}"
echo ""

# Check if already downloaded
if [ -f "${DEST_PATH}" ]; then
    existing_size=$(stat -c%s "${DEST_PATH}" 2>/dev/null || stat -f%z "${DEST_PATH}" 2>/dev/null)
    echo "File already exists: ${DEST_PATH} ($(numfmt --to=iec-i --suffix=B ${existing_size} 2>/dev/null || echo "${existing_size} bytes"))"
    echo "Re-downloading will resume if partial, or skip if complete."
    echo ""
fi

# Create download directory
mkdir -p "${DOWNLOAD_DIR}"

# Download using best available tool
if command -v huggingface-cli &>/dev/null; then
    download_with_huggingface_cli "${FILENAME}"
elif command -v wget &>/dev/null; then
    download_with_wget "${FILENAME}"
elif command -v curl &>/dev/null; then
    download_with_curl "${FILENAME}"
else
    echo "ERROR: No download tool found."
    echo "Install one of: huggingface-cli (recommended), wget, or curl"
    echo ""
    echo "  pip install huggingface-hub   # For huggingface-cli"
    echo "  sudo dnf install wget         # For wget"
    exit 1
fi

# Verify download
if [ -f "${DEST_PATH}" ]; then
    final_size=$(stat -c%s "${DEST_PATH}" 2>/dev/null || stat -f%z "${DEST_PATH}" 2>/dev/null)
    echo ""
    echo "Download complete!"
    echo "  File: ${DEST_PATH}"
    echo "  Size: $(numfmt --to=iec-i --suffix=B ${final_size} 2>/dev/null || echo "${final_size} bytes")"
    echo ""
    echo "To use this quantization:"
    echo "  1. Set LLM_MODEL_PATH in .env:"
    echo "     LLM_MODEL_PATH=/models/${FILENAME}"
    echo ""
    echo "  2. Update the volume mount in docker-compose.prod.yml (or use the"
    echo "     AI_MODELS_PATH/nemotron directory which is already mounted)."
    echo ""
    echo "  3. Restart the ai-llm container:"
    echo "     podman compose -f docker-compose.prod.yml restart ai-llm"
    echo ""
    echo "To benchmark this quantization:"
    echo "  uv run python scripts/benchmark/llm_quantization_benchmark.py \\"
    echo "    --baseline q4_k_m --candidate ${QUANT_FORMAT}"
else
    echo "ERROR: Download failed. File not found at ${DEST_PATH}"
    exit 1
fi
