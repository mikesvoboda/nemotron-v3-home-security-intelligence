#!/usr/bin/env bash
#
# Download AI models for Home Security Intelligence
#
# Usage:
#   ./ai/download_models.sh                    # Use default path /export/ai_models
#   AI_MODELS_PATH=./models ./ai/download_models.sh  # Use custom path
#
# Models downloaded (~42GB total):
#   - Nemotron-3-Nano-30B (Q4_K_M) - ~18GB - Risk reasoning LLM
#   - RT-DETRv2 - Auto-downloaded by HuggingFace on first run
#   - Florence-2-Large - ~3GB - Vision-language captions
#   - CLIP-ViT-L - ~1.7GB - Entity re-identification
#   - Model Zoo (~19GB):
#     - Fashion-CLIP - Clothing classification
#     - Vehicle-Segment-Classification - Vehicle types
#     - Pet-Classifier - Cat/dog detection
#     - Depth-Anything-V2-Small - Depth estimation
#

set -e

# Configurable base path (default: /export/ai_models)
AI_MODELS_PATH="${AI_MODELS_PATH:-/export/ai_models}"

echo "=========================================="
echo "AI Model Download Script"
echo "=========================================="
echo ""
echo "Target directory: ${AI_MODELS_PATH}"
echo ""

# Create directory structure
mkdir -p "${AI_MODELS_PATH}/nemotron"
mkdir -p "${AI_MODELS_PATH}/model-zoo"

# Check for required tools
check_tool() {
    if ! command -v "$1" &> /dev/null; then
        echo "[ERROR] Required tool not found: $1"
        echo "        Install with: $2"
        exit 1
    fi
}

check_tool "wget" "apt install wget / brew install wget"
check_tool "git" "apt install git / brew install git"

# Helper: Clone or update HuggingFace repo
clone_or_update_hf() {
    local repo=$1
    local target=$2
    local name=$3

    if [ -d "$target" ] && [ -d "$target/.git" ]; then
        echo "[SKIP] $name already exists: $target"
    elif [ -d "$target" ] && [ ! -d "$target/.git" ]; then
        echo "[SKIP] $name exists (non-git): $target"
    else
        echo "[CLONE] $name"
        echo "        From: https://huggingface.co/$repo"
        echo "        To: $target"
        GIT_LFS_SKIP_SMUDGE=0 git clone "https://huggingface.co/$repo" "$target"
        echo "[OK] $name downloaded"
    fi
}

# Helper: Download single file
download_file() {
    local url=$1
    local target=$2
    local name=$3
    local size=$4

    if [ -f "$target" ]; then
        echo "[SKIP] $name already exists: $target"
    else
        echo "[DOWNLOAD] $name (~$size)"
        echo "           From: $url"
        echo "           To: $target"
        wget --progress=bar:force -O "$target" "$url" || {
            echo "[ERROR] Failed to download $name"
            rm -f "$target"
            return 1
        }
        echo "[OK] $name downloaded"
    fi
}

echo ""
echo "=========================================="
echo "1/6 - Nemotron-3-Nano-30B (Risk Reasoning LLM)"
echo "=========================================="
echo ""

NEMOTRON_DIR="${AI_MODELS_PATH}/nemotron/nemotron-3-nano-30b-a3b-q4km"
NEMOTRON_MODEL="${NEMOTRON_DIR}/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf"
NEMOTRON_URL="https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF/resolve/main/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf"

mkdir -p "$NEMOTRON_DIR"

if [ -f "$NEMOTRON_MODEL" ]; then
    echo "[SKIP] Nemotron model already exists: $NEMOTRON_MODEL"
else
    # Check for existing model in common locations
    FOUND_MODEL=""
    for search_path in \
        "${NEMOTRON_GGUF_PATH:-}" \
        "/export/ai_models/weights/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf" \
        "$HOME/.cache/huggingface/hub/models--nvidia--Nemotron-3-Nano-30B-A3B-GGUF/snapshots/*/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf"; do
        if [ -n "$search_path" ] && [ -f "$search_path" ]; then
            FOUND_MODEL="$search_path"
            break
        fi
    done

    if [ -n "$FOUND_MODEL" ]; then
        echo "[FOUND] Existing Nemotron model: $FOUND_MODEL"
        echo "        Creating symlink to: $NEMOTRON_MODEL"

        # NEM-1091: Improved symlink error handling
        # Check if target already exists and is a symlink pointing to the same file
        if [ -L "$NEMOTRON_MODEL" ]; then
            EXISTING_TARGET=$(readlink -f "$NEMOTRON_MODEL" 2>/dev/null || true)
            FOUND_MODEL_RESOLVED=$(readlink -f "$FOUND_MODEL" 2>/dev/null || echo "$FOUND_MODEL")
            if [ "$EXISTING_TARGET" = "$FOUND_MODEL_RESOLVED" ]; then
                echo "[SKIP] Symlink already exists and points to the correct target"
            else
                echo "[INFO] Updating symlink (was pointing to: $EXISTING_TARGET)"
                rm -f "$NEMOTRON_MODEL"
                ln -sf "$FOUND_MODEL" "$NEMOTRON_MODEL" || {
                    echo "[ERROR] Failed to create symlink"
                    echo "        Source: $FOUND_MODEL"
                    echo "        Target: $NEMOTRON_MODEL"
                    echo "        Check permissions and that the target directory exists"
                    exit 1
                }
                echo "[OK] Nemotron model linked"
            fi
        elif [ -e "$NEMOTRON_MODEL" ]; then
            # Target exists but is not a symlink (regular file)
            echo "[ERROR] Target path exists and is not a symlink: $NEMOTRON_MODEL"
            echo "        Remove or rename the existing file first"
            exit 1
        else
            # Create new symlink
            ln -sf "$FOUND_MODEL" "$NEMOTRON_MODEL" || {
                echo "[ERROR] Failed to create symlink"
                echo "        Source: $FOUND_MODEL"
                echo "        Target: $NEMOTRON_MODEL"
                echo "        Check permissions and that the target directory exists"
                exit 1
            }
            echo "[OK] Nemotron model linked"
        fi
    else
        echo "[DOWNLOAD] Nemotron-3-Nano-30B-A3B (Q4_K_M) - ~18GB"
        echo "           This may take 10-30 minutes depending on connection speed"
        echo "           URL: $NEMOTRON_URL"
        wget --progress=bar:force -O "$NEMOTRON_MODEL" "$NEMOTRON_URL" || {
            echo "[ERROR] Nemotron download failed"
            echo "        You can manually download from: https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF"
            echo "        Place the .gguf file at: $NEMOTRON_MODEL"
            rm -f "$NEMOTRON_MODEL"
        }
    fi
fi

echo ""
echo "=========================================="
echo "2/6 - RT-DETRv2 (Object Detection)"
echo "=========================================="
echo ""
echo "[INFO] RT-DETRv2 models are auto-downloaded by HuggingFace Transformers"
echo "       on first container start. No manual download needed."
echo "       Model: PekingU/rtdetr_r50vd_coco_o365 (~165MB)"

echo ""
echo "=========================================="
echo "3/6 - Florence-2-Large (Vision-Language)"
echo "=========================================="
echo ""

FLORENCE_DIR="${AI_MODELS_PATH}/model-zoo/florence-2-large"
clone_or_update_hf "microsoft/Florence-2-large" "$FLORENCE_DIR" "Florence-2-Large (~3GB)"

echo ""
echo "=========================================="
echo "4/6 - CLIP-ViT-L (Embeddings/Re-ID)"
echo "=========================================="
echo ""

CLIP_DIR="${AI_MODELS_PATH}/model-zoo/clip-vit-l"
clone_or_update_hf "openai/clip-vit-large-patch14" "$CLIP_DIR" "CLIP-ViT-L (~1.7GB)"

echo ""
echo "=========================================="
echo "5/6 - Fashion-CLIP (Clothing Classification)"
echo "=========================================="
echo ""

FASHION_DIR="${AI_MODELS_PATH}/model-zoo/fashion-clip"
clone_or_update_hf "patrickjohncyh/fashion-clip" "$FASHION_DIR" "Fashion-CLIP (~3.5GB)"

echo ""
echo "=========================================="
echo "6/6 - Enrichment Models"
echo "=========================================="
echo ""

# Vehicle classification
VEHICLE_DIR="${AI_MODELS_PATH}/model-zoo/vehicle-segment-classification"
clone_or_update_hf "microsoft/resnet-50" "$VEHICLE_DIR" "Vehicle-Segment-Classification (~100MB)"

# Pet classifier
PET_DIR="${AI_MODELS_PATH}/model-zoo/pet-classifier"
clone_or_update_hf "microsoft/resnet-50" "$PET_DIR" "Pet-Classifier (~100MB)"

# Depth estimation
DEPTH_DIR="${AI_MODELS_PATH}/model-zoo/depth-anything-v2-small"
clone_or_update_hf "depth-anything/Depth-Anything-V2-Small-hf" "$DEPTH_DIR" "Depth-Anything-V2-Small (~95MB)"

echo ""
echo "=========================================="
echo "Download Complete!"
echo "=========================================="
echo ""
echo "Models installed to: ${AI_MODELS_PATH}"
echo ""
echo "Directory structure:"
echo "  ${AI_MODELS_PATH}/"
echo "  ├── nemotron/"
echo "  │   └── nemotron-3-nano-30b-a3b-q4km/  (Nemotron LLM)"
echo "  └── model-zoo/"
echo "      ├── florence-2-large/              (Vision-language)"
echo "      ├── clip-vit-l/                    (Embeddings)"
echo "      ├── fashion-clip/                  (Clothing)"
echo "      ├── vehicle-segment-classification/ (Vehicles)"
echo "      ├── pet-classifier/                (Pets)"
echo "      └── depth-anything-v2-small/       (Depth)"
echo ""
echo "Next steps:"
echo "  1. Ensure docker-compose.prod.yml has correct AI_MODELS_PATH"
echo "  2. Start services: podman-compose -f docker-compose.prod.yml up -d"
echo "  3. Wait for AI models to load (~2-3 minutes)"
echo "  4. Check health: curl http://localhost:8000/api/system/health/ready"
echo ""
if [ "${AI_MODELS_PATH}" != "/export/ai_models" ]; then
    echo "NOTE: You used a custom path. Set this in your environment:"
    echo "  export AI_MODELS_PATH=${AI_MODELS_PATH}"
    echo ""
fi
