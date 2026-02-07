#!/usr/bin/env bash
# Inspect Nemotron model tensors for MoE-aware offloading (NEM-5536)
#
# This script inspects the Nemotron-3-Nano-30B GGUF model's tensor structure
# to identify MoE (Mixture of Experts) expert layers that can be offloaded
# to CPU for VRAM savings with minimal performance impact.
#
# Nemotron-3-Nano-30B-A3B uses a hybrid architecture:
#   - 23 Mamba layers (state-space model, no attention)
#   - 23 MoE layers (128 experts per layer, 6 active per token)
#   - 6 GQA attention layers (grouped-query attention)
#
# MoE experts are ideal offloading candidates because only 6 of 128 experts
# activate per token (~4.7%). CPU-offloaded experts add minimal latency since
# only the active experts need to be fetched for each token.
#
# Usage:
#   ./scripts/inspect-model-tensors.sh                    # Run inside container
#   ./scripts/inspect-model-tensors.sh --local /path/to   # Run on host with local binary
#   ./scripts/inspect-model-tensors.sh --all               # Show all tensors (not just MoE)
#
# Output:
#   Lists MoE-related tensors and recommends an LLM_MOE_OFFLOAD_PATTERN value
#   for use in .env to enable expert offloading via --override-tensor.
#
# Prerequisites:
#   - ai-llm container must be running (or use --local with a llama-server binary)
#   - Model GGUF file mounted at /models/ inside the container

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default settings
CONTAINER_NAME="ai-llm"
MODEL_PATH="/models/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf"
SHOW_ALL=false
USE_LOCAL=false
LOCAL_BINARY=""

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Inspect Nemotron model tensors to identify MoE expert layers for CPU offloading."
    echo ""
    echo "Options:"
    echo "  --all                  Show all tensors, not just MoE-related ones"
    echo "  --local <binary_path>  Use a local llama-server binary instead of container"
    echo "  --model <path>         Override model path (default: ${MODEL_PATH})"
    echo "  --container <name>     Override container name (default: ${CONTAINER_NAME})"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                          # Inspect via ai-llm container"
    echo "  $0 --all                                    # Show all tensors"
    echo "  $0 --local /usr/local/bin/llama-server      # Use local binary"
    echo "  $0 --model /models/custom-model.gguf        # Custom model path"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --all)
            SHOW_ALL=true
            shift
            ;;
        --local)
            USE_LOCAL=true
            LOCAL_BINARY="$2"
            shift 2
            ;;
        --model)
            MODEL_PATH="$2"
            shift 2
            ;;
        --container)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}" >&2
            usage
            exit 1
            ;;
    esac
done

echo -e "${BLUE}=== Nemotron MoE Tensor Inspector (NEM-5536) ===${NC}"
echo ""

# Determine how to run llama-server
if [ "$USE_LOCAL" = true ]; then
    if [ ! -x "$LOCAL_BINARY" ]; then
        echo -e "${RED}Error: Local binary not found or not executable: ${LOCAL_BINARY}${NC}" >&2
        exit 1
    fi
    echo -e "Using local binary: ${LOCAL_BINARY}"
    echo -e "Model path: ${MODEL_PATH}"
    echo ""

    TENSOR_OUTPUT=$("$LOCAL_BINARY" --model "$MODEL_PATH" --list-tensors 2>/dev/null) || {
        echo -e "${RED}Error: Failed to list tensors. Ensure the model file exists at: ${MODEL_PATH}${NC}" >&2
        echo -e "${YELLOW}Hint: If llama-server does not support --list-tensors, upgrade to a recent build.${NC}" >&2
        exit 1
    }
else
    # Check if container is running
    if ! podman ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER_NAME}$"; then
        # Try with common prefixes
        FOUND_CONTAINER=$(podman ps --format '{{.Names}}' 2>/dev/null | grep "${CONTAINER_NAME}" | head -1) || true
        if [ -z "$FOUND_CONTAINER" ]; then
            echo -e "${RED}Error: Container '${CONTAINER_NAME}' is not running.${NC}" >&2
            echo -e "${YELLOW}Hint: Start the ai-llm container first:${NC}" >&2
            echo -e "${YELLOW}  podman compose -f docker-compose.prod.yml up -d ai-llm${NC}" >&2
            echo -e ""
            echo -e "${YELLOW}Or use --local to run with a local llama-server binary.${NC}" >&2
            exit 1
        fi
        CONTAINER_NAME="$FOUND_CONTAINER"
    fi

    echo -e "Container: ${CONTAINER_NAME}"
    echo -e "Model path: ${MODEL_PATH}"
    echo ""

    TENSOR_OUTPUT=$(podman exec "$CONTAINER_NAME" llama-server --model "$MODEL_PATH" --list-tensors 2>/dev/null) || {
        echo -e "${RED}Error: Failed to list tensors from container '${CONTAINER_NAME}'.${NC}" >&2
        echo -e "${YELLOW}Possible causes:${NC}" >&2
        echo -e "${YELLOW}  - Model file not found at ${MODEL_PATH}${NC}" >&2
        echo -e "${YELLOW}  - llama-server binary does not support --list-tensors${NC}" >&2
        echo -e "${YELLOW}  - Container is not in a healthy state${NC}" >&2
        exit 1
    }
fi

if [ -z "$TENSOR_OUTPUT" ]; then
    echo -e "${RED}Error: No tensor output received. The model file may not exist or the binary may not support --list-tensors.${NC}" >&2
    exit 1
fi

# Count total tensors
TOTAL_TENSORS=$(echo "$TENSOR_OUTPUT" | wc -l)
echo -e "${GREEN}Total tensors found: ${TOTAL_TENSORS}${NC}"
echo ""

if [ "$SHOW_ALL" = true ]; then
    echo -e "${BLUE}--- All Tensors ---${NC}"
    echo "$TENSOR_OUTPUT"
    echo ""
fi

# Filter for MoE-related tensors (experts, FFN, MoE gate/router)
echo -e "${BLUE}--- MoE Expert Tensors ---${NC}"
MOE_TENSORS=$(echo "$TENSOR_OUTPUT" | grep -iE "ffn.*exp|expert|moe|gate.*exp" || true)

if [ -z "$MOE_TENSORS" ]; then
    echo -e "${YELLOW}No MoE expert tensors found with standard patterns.${NC}"
    echo ""
    echo -e "Searching for FFN-related tensors..."
    MOE_TENSORS=$(echo "$TENSOR_OUTPUT" | grep -iE "ffn|feed.forward|mlp" || true)
    if [ -z "$MOE_TENSORS" ]; then
        echo -e "${RED}No FFN/MoE tensors found. The model may not use a Mixture of Experts architecture,${NC}"
        echo -e "${RED}or the tensor naming convention is different than expected.${NC}"
        echo ""
        echo -e "${YELLOW}Try running with --all to see all tensor names and identify the pattern manually.${NC}"
        exit 1
    fi
fi

MOE_COUNT=$(echo "$MOE_TENSORS" | wc -l)
echo -e "${GREEN}MoE-related tensors: ${MOE_COUNT}${NC}"
echo ""
echo "$MOE_TENSORS"
echo ""

# Analyze tensor naming patterns to suggest a regex
echo -e "${BLUE}--- Tensor Name Pattern Analysis ---${NC}"

# Extract unique patterns from MoE tensor names
# Look for common patterns like: blk.N.ffn_*_exps.weight, experts.N.*, etc.
PATTERNS=$(echo "$MOE_TENSORS" | sed 's/[0-9]\+/N/g' | sort -u | head -20)
echo "Unique name patterns (numbers replaced with N):"
echo "$PATTERNS"
echo ""

# Try to identify the best offloading pattern
# Common patterns in llama.cpp GGUF models:
#   - blk.N.ffn_gate_exps.weight   (MoE gate experts)
#   - blk.N.ffn_down_exps.weight   (MoE down-projection experts)
#   - blk.N.ffn_up_exps.weight     (MoE up-projection experts)
EXPERT_WEIGHT_PATTERN=""

if echo "$MOE_TENSORS" | grep -q "ffn_.*_exps\.weight"; then
    EXPERT_WEIGHT_PATTERN='\.ffn_.*_exps\.weight'
    MATCHING=$(echo "$MOE_TENSORS" | grep -c "ffn_.*_exps\.weight" || true)
    echo -e "${GREEN}Detected llama.cpp MoE expert weight pattern: ${EXPERT_WEIGHT_PATTERN}${NC}"
    echo -e "Matching tensors: ${MATCHING}"
elif echo "$MOE_TENSORS" | grep -q "experts\.\|expert\."; then
    EXPERT_WEIGHT_PATTERN='\.experts?\.'
    MATCHING=$(echo "$MOE_TENSORS" | grep -cE "experts?\." || true)
    echo -e "${GREEN}Detected expert submodule pattern: ${EXPERT_WEIGHT_PATTERN}${NC}"
    echo -e "Matching tensors: ${MATCHING}"
elif echo "$MOE_TENSORS" | grep -q "ffn.*exp"; then
    EXPERT_WEIGHT_PATTERN='\.ffn.*exp'
    MATCHING=$(echo "$MOE_TENSORS" | grep -c "ffn.*exp" || true)
    echo -e "${GREEN}Detected FFN expert pattern: ${EXPERT_WEIGHT_PATTERN}${NC}"
    echo -e "Matching tensors: ${MATCHING}"
else
    echo -e "${YELLOW}Could not auto-detect a reliable offloading pattern.${NC}"
    echo -e "Review the tensor names above and construct a regex pattern manually."
    echo -e "The pattern should match expert FFN weight tensors but NOT:"
    echo -e "  - Attention layers (attn_k, attn_v, attn_q, attn_output)"
    echo -e "  - Mamba layers (ssm_*, mamba_*)"
    echo -e "  - Embedding layers (token_embd, output)"
    echo -e "  - Router/gate weights (ffn_gate_inp, moe_gate)"
fi

echo ""
echo -e "${BLUE}=== Recommended Configuration ===${NC}"
echo ""

if [ -n "$EXPERT_WEIGHT_PATTERN" ]; then
    echo -e "Add the following to your ${GREEN}.env${NC} file to enable MoE expert offloading:"
    echo ""
    echo -e "  ${GREEN}LLM_MOE_OFFLOAD_PATTERN=${EXPERT_WEIGHT_PATTERN}${NC}"
    echo ""
    echo -e "This will pass ${GREEN}--override-tensor ${EXPERT_WEIGHT_PATTERN}=CPU${NC} to llama-server,"
    echo -e "offloading MoE expert FFN weights to system RAM while keeping attention,"
    echo -e "Mamba, and router weights on GPU."
    echo ""
    echo -e "${YELLOW}Important notes:${NC}"
    echo -e "  - Test inference quality and latency after enabling offloading"
    echo -e "  - Monitor VRAM usage: the freed GPU memory allows more GPU layers or larger context"
    echo -e "  - Only 6 of 128 experts activate per token, so CPU access latency is minimal"
    echo -e "  - Verify via llama.cpp logs: look for 'offloaded N/M tensors to CPU' on startup"
    echo -e "  - The pattern is model-specific and may change with different GGUF versions"
else
    echo -e "${YELLOW}No automatic pattern could be determined.${NC}"
    echo -e "Manually inspect the tensor names above and set LLM_MOE_OFFLOAD_PATTERN in .env."
    echo -e "See docs/development/moe-offloading.md for guidance."
fi

echo ""
echo -e "${BLUE}=== VRAM Savings Estimate ===${NC}"
echo ""

# Estimate VRAM savings based on tensor count and typical Q4_K_M sizes
if [ -n "$EXPERT_WEIGHT_PATTERN" ] && [ -n "${MATCHING:-}" ]; then
    # Rough estimate: each expert tensor in Q4_K_M is approximately 0.5-2MB
    # With 128 experts per layer and ~23 MoE layers, there are many tensors
    # Typical savings for Nemotron-3-Nano-30B: 3-6GB
    echo -e "Expert tensors to offload: ${MATCHING}"
    echo -e "Estimated VRAM savings: ${GREEN}3-6 GB${NC} (varies by quantization and tensor dimensions)"
    echo -e "This freed VRAM can be used for:"
    echo -e "  - Fitting more model layers on GPU (reduce CPU overflow)"
    echo -e "  - Increasing CTX_SIZE for larger context windows"
    echo -e "  - Running additional parallel inference slots"
else
    echo -e "Unable to estimate savings without a confirmed offloading pattern."
fi

echo ""
echo -e "${GREEN}Done.${NC} See docs/development/moe-offloading.md for full documentation."
