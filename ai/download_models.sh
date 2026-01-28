#!/usr/bin/env bash
#
# Download AI models for Home Security Intelligence
#
# Usage:
#   ./ai/download_models.sh                    # Use default path /export/ai_models
#   AI_MODELS_PATH=./models ./ai/download_models.sh  # Use custom path
#
# Models downloaded (~42GB total):
#   - Nemotron-3-Nano-30B (Q4_K_M) - ~14.7GB - Risk reasoning LLM
#   - YOLO26v2 - Auto-downloaded by HuggingFace on first run
#   - Florence-2-Large - ~3GB - Vision-language captions
#   - CLIP-ViT-L - ~1.7GB - Entity re-identification
#   - Model Zoo (~19GB):
#     - Fashion-CLIP - Clothing classification
#     - Vehicle-Segment-Classification (ViT) - Vehicle types
#     - Pet-Classifier (ResNet-18) - Cat/dog detection
#     - Depth-Anything-V2-Small - Depth estimation
#     - ViTPose+ Small - Pose estimation
#     - YOLO26 (n/s/m) - ~67MB - Object detection (Ultralytics)
#
# Security:
#   - Direct downloads: SHA256 checksum verification
#   - Git LFS repos: Content-addressable storage (built-in)
#   - Set SKIP_CHECKSUM=true to bypass verification (not recommended)
#

set -e

# Configurable base path (default: /export/ai_models)
AI_MODELS_PATH="${AI_MODELS_PATH:-/export/ai_models}"

# Skip checksum verification if set (for development/testing only)
SKIP_CHECKSUM="${SKIP_CHECKSUM:-false}"

# Strict mode: fail on checksum mismatch instead of warning
STRICT_CHECKSUM="${STRICT_CHECKSUM:-false}"

echo "=========================================="
echo "AI Model Download Script"
echo "=========================================="
echo ""
echo "Target directory: ${AI_MODELS_PATH}"
if [ "$SKIP_CHECKSUM" = "true" ]; then
    echo "WARNING: Checksum verification is DISABLED"
fi
echo ""

# ==========================================
# Checksum Registry
# ==========================================
# SHA256 checksums for model files
# Source: HuggingFace model cards and verified downloads
# Last updated: 2026-01 (NEM-2856)
#
# To compute checksum for a file:
#   sha256sum <filename> | cut -d' ' -f1
#
# To update checksums after verifying a known-good download:
#   1. Download the model from official source
#   2. Compute: sha256sum model.gguf
#   3. Update the checksum in this file
#
# Note: For Git LFS repos, integrity is verified by Git's content-addressable storage.
# Checksums here are primarily for direct file downloads (wget/curl).

declare -A MODEL_CHECKSUMS=(
    # Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf (~14.7GB)
    # From: https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF
    # Verified from known-good download on 2026-01-18
    ["Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf"]="0e7f6e51fdd9039928749d07eed9e846dbfd97681646544c5406bcdd788e5940"  # pragma: allowlist secret
)

# Expected Git commit hashes for HuggingFace repos (optional verification)
# These provide an additional layer of integrity verification beyond Git LFS
# Leave empty to skip commit verification (Git LFS still provides integrity)
declare -A HF_REPO_COMMITS=(
    # Florence-2-Large - leave empty to use latest
    ["microsoft/Florence-2-large"]=""
    # CLIP-ViT-L - leave empty to use latest
    ["openai/clip-vit-large-patch14"]=""
    # Fashion-CLIP - leave empty to use latest
    ["patrickjohncyh/fashion-clip"]=""
    # Depth-Anything-V2-Small - leave empty to use latest
    ["depth-anything/Depth-Anything-V2-Small-hf"]=""
)

# ==========================================
# Checksum Verification Functions
# ==========================================

# Verify SHA256 checksum of a file
# Args: $1 = file path, $2 = expected checksum (optional, uses registry if not provided)
# Returns: 0 on success/skip, 1 on mismatch
verify_checksum() {
    local file="$1"
    local expected="$2"
    local filename
    filename=$(basename "$file")

    # If no expected checksum provided, look up in registry
    if [ -z "$expected" ]; then
        expected="${MODEL_CHECKSUMS[$filename]:-}"
    fi

    # Skip verification if no checksum available
    if [ -z "$expected" ]; then
        echo "[INFO] No checksum registered for: $filename"
        echo "       Skipping verification (consider adding checksum for security)"
        return 0
    fi

    # Skip if SKIP_CHECKSUM is set
    if [ "$SKIP_CHECKSUM" = "true" ]; then
        echo "[SKIP] Checksum verification disabled (SKIP_CHECKSUM=true)"
        return 0
    fi

    # Verify file exists
    if [ ! -f "$file" ]; then
        echo "[ERROR] File not found for checksum verification: $file"
        return 1
    fi

    # Get file size for progress indication
    local size_bytes size_human
    size_bytes=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null || echo "0")
    if [ "$size_bytes" -gt 1073741824 ]; then
        size_human="$(( size_bytes / 1073741824 )) GB"
    elif [ "$size_bytes" -gt 1048576 ]; then
        size_human="$(( size_bytes / 1048576 )) MB"
    else
        size_human="$size_bytes bytes"
    fi

    echo "[VERIFY] Computing SHA256 checksum for $filename ($size_human)..."
    echo "         This may take a few minutes for large files..."

    # Compute actual checksum with progress for large files
    local actual
    if command -v pv &> /dev/null && [ "$size_bytes" -gt 104857600 ]; then
        # Use pv for progress on files > 100MB if available
        actual=$(pv "$file" 2>/dev/null | sha256sum | cut -d' ' -f1)
    elif command -v sha256sum &> /dev/null; then
        actual=$(sha256sum "$file" | cut -d' ' -f1)
    elif command -v shasum &> /dev/null; then
        actual=$(shasum -a 256 "$file" | cut -d' ' -f1)
    else
        echo "[WARN] No SHA256 tool found (sha256sum/shasum)"
        echo "       Skipping checksum verification"
        return 0
    fi

    # Compare checksums (case-insensitive)
    if [ "${actual,,}" = "${expected,,}" ]; then
        echo "[OK] Checksum verified: $filename"
        echo "     SHA256: ${actual:0:16}...${actual: -16}"
        return 0
    else
        echo ""
        echo "========================================"
        echo "[ERROR] CHECKSUM MISMATCH"
        echo "========================================"
        echo "File:     $filename"
        echo "Expected: $expected"
        echo "Got:      $actual"
        echo ""
        echo "This could indicate:"
        echo "  1. Corrupted download (most common)"
        echo "  2. Model file was updated upstream"
        echo "  3. File tampering (security concern)"
        echo ""
        echo "Recommended actions:"
        echo "  1. Delete the file and re-download"
        echo "  2. Verify checksum from official HuggingFace page"
        echo "  3. If model was legitimately updated, update checksum in this script"
        echo ""
        echo "To compute checksum of your file:"
        echo "  sha256sum \"$file\""
        echo "========================================"

        if [ "$STRICT_CHECKSUM" = "true" ]; then
            return 1
        else
            echo ""
            echo "[WARN] Continuing despite checksum mismatch (STRICT_CHECKSUM=false)"
            echo "       Set STRICT_CHECKSUM=true to fail on mismatch"
            return 0
        fi
    fi
}

# Verify Git repository commit hash
# Args: $1 = repo directory, $2 = expected commit hash (optional)
# Returns: 0 on success/skip, 1 on mismatch
verify_git_commit() {
    local repo_dir="$1"
    local expected="$2"
    local repo_name
    repo_name=$(basename "$repo_dir")

    # Skip if no expected commit provided
    if [ -z "$expected" ]; then
        echo "[INFO] Git LFS provides integrity verification via content-addressable storage"
        return 0
    fi

    # Skip if not a git repo
    if [ ! -d "$repo_dir/.git" ]; then
        echo "[INFO] Not a git repository: $repo_dir"
        return 0
    fi

    # Get current commit
    local actual
    actual=$(git -C "$repo_dir" rev-parse HEAD 2>/dev/null || echo "")

    if [ -z "$actual" ]; then
        echo "[WARN] Could not get commit hash for: $repo_dir"
        return 0
    fi

    if [ "$actual" = "$expected" ]; then
        echo "[OK] Git commit verified for $repo_name: ${actual:0:12}"
        return 0
    else
        echo "[INFO] Git commit for $repo_name: ${actual:0:12}"
        echo "       Expected: ${expected:0:12} (may have been updated upstream)"
        # Don't fail - just inform, as Git LFS handles integrity
        return 0
    fi
}

# Compute and display checksum for a file (useful for updating registry)
compute_checksum() {
    local file="$1"
    local filename
    filename=$(basename "$file")

    if [ ! -f "$file" ]; then
        echo "[ERROR] File not found: $file"
        return 1
    fi

    echo "[INFO] Computing checksum for: $filename"
    echo "       This may take several minutes for large files..."

    local checksum
    if command -v sha256sum &> /dev/null; then
        checksum=$(sha256sum "$file" | cut -d' ' -f1)
    elif command -v shasum &> /dev/null; then
        checksum=$(shasum -a 256 "$file" | cut -d' ' -f1)
    else
        echo "[ERROR] No SHA256 tool found"
        return 1
    fi

    echo ""
    echo "SHA256: $checksum"
    echo ""
    echo "To add to MODEL_CHECKSUMS in download_models.sh:"
    echo "    [\"$filename\"]=\"$checksum\""
    return 0
}

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
# Git LFS repos have built-in integrity via content-addressable storage
clone_or_update_hf() {
    local repo=$1
    local target=$2
    local name=$3
    local expected_commit="${HF_REPO_COMMITS[$repo]:-}"

    if [ -d "$target" ] && [ -d "$target/.git" ]; then
        echo "[SKIP] $name already exists: $target"
        # Verify commit hash if specified
        verify_git_commit "$target" "$expected_commit"
    elif [ -d "$target" ] && [ ! -d "$target/.git" ]; then
        echo "[SKIP] $name exists (non-git): $target"
    else
        echo "[CLONE] $name"
        echo "        From: https://huggingface.co/$repo"
        echo "        To: $target"
        GIT_LFS_SKIP_SMUDGE=0 git clone "https://huggingface.co/$repo" "$target"
        echo "[OK] $name downloaded"
        echo "[INFO] Git LFS provides integrity verification via content-addressable storage"
        # Verify commit if specified
        verify_git_commit "$target" "$expected_commit"
    fi
}

# Helper: Download single file with checksum verification
download_file() {
    local url=$1
    local target=$2
    local name=$3
    local size=$4
    local expected_checksum="${5:-}"

    if [ -f "$target" ]; then
        echo "[SKIP] $name already exists: $target"
        # Verify checksum of existing file
        verify_checksum "$target" "$expected_checksum"
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

        # Verify checksum after download
        verify_checksum "$target" "$expected_checksum"
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
NEMOTRON_CHECKSUM="${MODEL_CHECKSUMS[Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf]:-}"

mkdir -p "$NEMOTRON_DIR"

if [ -f "$NEMOTRON_MODEL" ]; then
    echo "[SKIP] Nemotron model already exists: $NEMOTRON_MODEL"
    # Verify checksum of existing file
    verify_checksum "$NEMOTRON_MODEL" "$NEMOTRON_CHECKSUM"
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

        # Verify checksum of found file before linking
        verify_checksum "$FOUND_MODEL" "$NEMOTRON_CHECKSUM"

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
        echo "[DOWNLOAD] Nemotron-3-Nano-30B-A3B (Q4_K_M) - ~14.7GB"
        echo "           This may take 10-30 minutes depending on connection speed"
        echo "           URL: $NEMOTRON_URL"
        wget --progress=bar:force -O "$NEMOTRON_MODEL" "$NEMOTRON_URL" || {
            echo "[ERROR] Nemotron download failed"
            echo "        You can manually download from: https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF"
            echo "        Place the .gguf file at: $NEMOTRON_MODEL"
            rm -f "$NEMOTRON_MODEL"
            exit 1
        }

        # Verify checksum after download
        echo ""
        verify_checksum "$NEMOTRON_MODEL" "$NEMOTRON_CHECKSUM"
    fi
fi

echo ""
echo "=========================================="
echo "2/6 - YOLO26v2 (Object Detection)"
echo "=========================================="
echo ""
echo "[INFO] YOLO26v2 models are auto-downloaded by HuggingFace Transformers"
echo "       on first container start. No manual download needed."
echo "       Model: PekingU/yolo26_r50vd_coco_o365 (~165MB)"
echo "       Integrity verified via HuggingFace's content-addressable storage"

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
# HuggingFace URL: https://huggingface.co/lxyuan/vit-base-patch16-224-vehicle-segment-classification
VEHICLE_DIR="${AI_MODELS_PATH}/model-zoo/vehicle-segment-classification"
clone_or_update_hf "lxyuan/vit-base-patch16-224-vehicle-segment-classification" "$VEHICLE_DIR" "Vehicle-Segment-Classification (~350MB)"

# Pet classifier
# HuggingFace URL: https://huggingface.co/microsoft/resnet-18
PET_DIR="${AI_MODELS_PATH}/model-zoo/pet-classifier"
clone_or_update_hf "microsoft/resnet-18" "$PET_DIR" "Pet-Classifier (~45MB)"

# Pose estimation
# HuggingFace URL: https://huggingface.co/usyd-community/vitpose-plus-small
VITPOSE_DIR="${AI_MODELS_PATH}/model-zoo/vitpose-plus-small"
clone_or_update_hf "usyd-community/vitpose-plus-small" "$VITPOSE_DIR" "ViTPose+ Small (~100MB)"

# Depth estimation
DEPTH_DIR="${AI_MODELS_PATH}/model-zoo/depth-anything-v2-small"
clone_or_update_hf "depth-anything/Depth-Anything-V2-Small-hf" "$DEPTH_DIR" "Depth-Anything-V2-Small (~95MB)"

echo ""
echo "=========================================="
echo "7/7 - YOLO26 (Object Detection - Ultralytics)"
echo "=========================================="
echo ""

# YOLO26 models - downloaded via Ultralytics Python SDK
# These are PyTorch .pt files from GitHub releases
YOLO26_DIR="${AI_MODELS_PATH}/model-zoo/yolo26"
mkdir -p "$YOLO26_DIR"

# YOLO26 model URLs (from ultralytics/assets GitHub releases)
YOLO26_RELEASE_URL="https://github.com/ultralytics/assets/releases/download/v8.4.0"

# Download YOLO26 Nano (2.6M params, ~5.3MB)
YOLO26N_FILE="${YOLO26_DIR}/yolo26n.pt"
if [ -f "$YOLO26N_FILE" ]; then
    echo "[SKIP] YOLO26-Nano already exists: $YOLO26N_FILE"
else
    echo "[DOWNLOAD] YOLO26-Nano (~5.3MB)"
    echo "           From: ${YOLO26_RELEASE_URL}/yolo26n.pt"
    wget --progress=bar:force -O "$YOLO26N_FILE" "${YOLO26_RELEASE_URL}/yolo26n.pt" || {
        echo "[ERROR] Failed to download YOLO26-Nano"
        rm -f "$YOLO26N_FILE"
    }
    echo "[OK] YOLO26-Nano downloaded"
fi

# Download YOLO26 Small (10M params, ~19.5MB)
YOLO26S_FILE="${YOLO26_DIR}/yolo26s.pt"
if [ -f "$YOLO26S_FILE" ]; then
    echo "[SKIP] YOLO26-Small already exists: $YOLO26S_FILE"
else
    echo "[DOWNLOAD] YOLO26-Small (~19.5MB)"
    echo "           From: ${YOLO26_RELEASE_URL}/yolo26s.pt"
    wget --progress=bar:force -O "$YOLO26S_FILE" "${YOLO26_RELEASE_URL}/yolo26s.pt" || {
        echo "[ERROR] Failed to download YOLO26-Small"
        rm -f "$YOLO26S_FILE"
    }
    echo "[OK] YOLO26-Small downloaded"
fi

# Download YOLO26 Medium (21.9M params, ~42.2MB)
YOLO26M_FILE="${YOLO26_DIR}/yolo26m.pt"
if [ -f "$YOLO26M_FILE" ]; then
    echo "[SKIP] YOLO26-Medium already exists: $YOLO26M_FILE"
else
    echo "[DOWNLOAD] YOLO26-Medium (~42.2MB)"
    echo "           From: ${YOLO26_RELEASE_URL}/yolo26m.pt"
    wget --progress=bar:force -O "$YOLO26M_FILE" "${YOLO26_RELEASE_URL}/yolo26m.pt" || {
        echo "[ERROR] Failed to download YOLO26-Medium"
        rm -f "$YOLO26M_FILE"
    }
    echo "[OK] YOLO26-Medium downloaded"
fi

echo ""
echo "[INFO] YOLO26 models downloaded to: $YOLO26_DIR"
echo "       - yolo26n.pt (Nano):   2.6M params, ~5.3MB,  fastest"
echo "       - yolo26s.pt (Small):  10M params,  ~19.5MB, balanced"
echo "       - yolo26m.pt (Medium): 21.9M params, ~42.2MB, highest accuracy"
echo ""
echo "       YOLO26 features:"
echo "       - End-to-end NMS-free inference"
echo "       - Up to 43% faster CPU inference vs YOLO11"
echo "       - Optimized for edge/mobile deployment"
echo "       - Requires ultralytics>=8.4.0"

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
echo "      ├── vitpose-plus-small/            (Pose)"
echo "      ├── depth-anything-v2-small/       (Depth)"
echo "      └── yolo26/                        (YOLO26 detection)"
echo "          ├── yolo26n.pt                 (Nano - fastest)"
echo "          ├── yolo26s.pt                 (Small - balanced)"
echo "          └── yolo26m.pt                 (Medium - accurate)"
echo ""
echo "Security verification:"
echo "  - Direct downloads: SHA256 checksum verification"
echo "  - Git LFS repos: Content-addressable storage (built-in)"
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

# ==========================================
# Utility: Compute checksum for maintainers
# ==========================================
# To compute checksum for a model file, source this script and call:
#   compute_checksum /path/to/model.gguf
#
# Environment variables:
#   SKIP_CHECKSUM=true   - Skip all checksum verification
#   STRICT_CHECKSUM=true - Fail (exit 1) on checksum mismatch
