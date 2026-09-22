#!/usr/bin/env bash
#
# Download AI models for Home Security Intelligence
#
# Usage:
#   ./ai/download_models.sh                    # Use default path /export/ai_models
#   AI_MODELS_PATH=./models ./ai/download_models.sh  # Use custom path
#
# The fetch list below is derived from models.yml at the repo root — the single
# source of truth for the model catalogue — using the SAME rule setup_lib uses
# (setup_lib/models_config.get_downloadable_models / model_downloader.
# build_model_specs):
#
#     download_method != "skip"  AND  (hf_repo OR download_method)
#
# That rule yields 25 of the 30 catalogue entries and 33579 MB = 32.79 GiB
# (~32.8GB) of models.yml size_mb estimates.  The 5 excluded entries are the
# download_method: skip ones (brisque-quality, fast-alpr, paddleocr,
# yolo26-general, zero-dce-plus-plus) — their libraries fetch what they need at
# runtime.
#
# The `enabled` flag governs backend model_zoo VRAM slots, NOT disk
# provisioning — so three `enabled: false` entries are still downloaded here
# because live code reads their files off disk: yolo26 (ai/gateway/export/
# export_yolo26.py + export_all.sh and scripts/prebuild-tensorrt-engines.sh
# need model-zoo/yolo26/*.pt), xclip-base (backend/services/
# action_recognition_service.py -> xclip_loader.py), and florence-2-large
# (backend/services/florence_extractor.py via the model_zoo loader map).
#
# Models downloaded (25 entries, 32.79 GiB by models.yml size_mb):
#   PHASE 0 — required (~16.2GB):
#     - Nemotron-3-Nano-30B (Q4_K_M) - ~14.7GB - Risk reasoning LLM
#     - Florence-2-Base - ~1GB - Vision-language captions (ai-gateway)
#     - SigLIP 2 Base ONNX - ~400MB - Entity re-identification embeddings
#     - YOLO26 (n/s/m) - ~67MB - Object detection (enabled: false but the
#         gateway export/TensorRT-prebuild path needs the .pt files on disk)
#   PHASE 1 — core enrichment (~543MB):
#     - Vehicle-Segment-Classification (ResNet-50) - ~358MB - Vehicle types
#     - Pet-Classifier (ResNet-18) - ~46MB - Cat/dog detection
#     - Depth-Anything-V2-Tiny - ~98MB - Depth estimation
#     - OSNet-AIN x1.0 - ~10MB - Person re-identification
#     - YOLOv8n-pose - ~6MB - Human pose estimation
#     - Threat-Detection-YOLOv8n - ~25MB - Weapon detection
#   PHASE 2 — demographics and action recognition (~1.3GB):
#     - ViT-Age / ViT-Gender classifiers - ~358MB each
#     - ST-GCN++ - ~20MB - Skeleton action recognition
#     - X-CLIP Base - ~600MB - Video action recognition (enabled: false — the
#         gateway has migrated to stgcn_action, but xclip_loader is still in
#         the model_zoo loader map)
#   PHASE 3 — specialized (~14.8GB):
#     - Fashion-CLIP (Marqo FashionSigLIP) - ~4.4GB - Clothing classification
#     - Florence-2-Large - ~3GB - VLM attribute extraction (enabled: false —
#         still in the model_zoo loader map)
#     - Weather / Violence classifiers - ~200MB / ~350MB
#     - YOLO11 face / license-plate detectors - ~11MB / ~650MB
#     - Smoke-Fire-YOLOv8n - ~25MB - CRITICAL safety model
#     - YOLO-World-S - ~1.5GB - Open-vocabulary detection
#     - ViTPose+ Small - ~1.5GB - Pose estimation
#     - SegFormer-B2-Clothes - ~1.5GB - Clothing segmentation
#     - Vehicle-Damage-Detection - ~2GB - Damage segmentation
#   Not fetched here (models.yml download_method: skip — the library fetches them):
#     - brisque-quality (piq), fast-alpr (ONNX), paddleocr, yolo26-general,
#       zero-dce-plus-plus
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
# Last updated: 2026-09 (models.yml catalogue re-derivation)
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
    # From: https://huggingface.co/unsloth/Nemotron-3-Nano-30B-A3B-GGUF (models.yml hf_repo)
    # Verified from known-good download on 2026-01-18; matches the LFS oid published
    # by the unsloth repo, so it still verifies against the models.yml source repo.
    ["Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf"]="0e7f6e51fdd9039928749d07eed9e846dbfd97681646544c5406bcdd788e5940"  # pragma: allowlist secret
    # YOLO26 ultralytics weights (GitHub release v8.4.0 assets).  Computed with
    # sha256sum from the v8.4.0 assets downloaded 2026-09-22; the v8.4.0 release
    # is immutable so these hold unless a maintainer changes the pinned release.
    ["yolo26n.pt"]="9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef"  # pragma: allowlist secret
    ["yolo26s.pt"]="646f8bc3fe0a656803d95c294f7852321748cb29d13466a1af8862e2db384a1b"  # pragma: allowlist secret
    ["yolo26m.pt"]="401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7"  # pragma: allowlist secret
)

# Expected Git commit hashes for HuggingFace repos (optional verification)
# These provide an additional layer of integrity verification beyond Git LFS
# Leave empty to skip commit verification (Git LFS still provides integrity)
declare -A HF_REPO_COMMITS=(
    ["microsoft/Florence-2-base"]=""
    ["microsoft/Florence-2-large"]=""
    ["microsoft/xclip-base-patch32"]=""
    ["onnx-community/siglip2-base-patch16-224-ONNX"]=""
    ["AventIQ-AI/ResNet-50-Vehicle-Segment-classification"]=""
    ["microsoft/resnet-18"]=""
    ["depth-anything/Depth-Anything-V2-Small-hf"]=""
    ["Subh775/Threat-Detection-YOLOv8n"]=""
    ["nateraw/vit-age-classifier"]=""
    ["rizvandwiki/gender-classification"]=""
    ["prithivMLmods/Weather-Image-Classification"]=""
    ["jaranohaal/vit-base-violence-detection"]=""
    ["AdamCodd/YOLOv11n-face-detection"]=""
    ["morsetechlab/yolov11-license-plate-detection"]=""
    ["SHOU-ISD/fire-and-smoke"]=""
    ["usyd-community/vitpose-plus-small"]=""
    ["mattmdjaga/segformer_b2_clothes"]=""
    ["harpreetsahota/car-dd-segmentation-yolov11"]=""
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

# Human-readable size label from a models.yml size_mb value
human_size() {
    local mb=$1
    if [ "$mb" -ge 1024 ]; then
        awk -v mb="$mb" 'BEGIN { printf "~%.1fGB", mb / 1024 }'
    else
        echo "~${mb}MB"
    fi
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

# ==========================================
# models.yml download set — HuggingFace snapshots
# ==========================================
# One row per models.yml entry that the rule selects and that is fetched as a
# plain HuggingFace snapshot (no download_method, or a hf_repo with no method):
#   name | hf_repo | local_path | size_mb
# Keep in sync with models.yml — regenerate with the same filter setup_lib uses:
#   download_method != "skip" and (hf_repo or download_method)
# Entries with a custom download_method, plus yolov8n-pose (whose hf_repo
# ultralytics/yolov8n-pose is not a public HF repo — its section below mirrors
# setup_lib's ultralytics release path instead), are handled in their own
# sections.  xclip-base and florence-2-large are enabled: false — kept because
# the rule (disk provisioning) not `enabled` (backend VRAM slots) governs.
HF_DOWNLOADS=(
    # PHASE 0 — required
    "florence-2-base|microsoft/Florence-2-base|model-zoo/florence-2-base|1024"
    "siglip2-base-patch16-224|onnx-community/siglip2-base-patch16-224-ONNX|model-zoo/siglip2-base-patch16-224|400"
    # PHASE 1 — core enrichment
    "vehicle-segment-classification|AventIQ-AI/ResNet-50-Vehicle-Segment-classification|model-zoo/vehicle-segment-classification|358"
    "pet-classifier|microsoft/resnet-18|model-zoo/pet-classifier|46"
    "depth-anything-v2-tiny|depth-anything/Depth-Anything-V2-Small-hf|model-zoo/depth-anything-v2-tiny|98"
    "threat-detection-yolov8n|Subh775/Threat-Detection-YOLOv8n|model-zoo/threat-detection-yolov8n|25"
    # PHASE 2 — demographics and action recognition
    "vit-age-classifier|nateraw/vit-age-classifier|model-zoo/vit-age-classifier|358"
    "vit-gender-classifier|rizvandwiki/gender-classification|model-zoo/vit-gender-classifier|358"
    "xclip-base|microsoft/xclip-base-patch32|model-zoo/xclip-base|600"
    # PHASE 3 — specialized
    "weather-classification|prithivMLmods/Weather-Image-Classification|model-zoo/weather-classification|200"
    "violence-detection|jaranohaal/vit-base-violence-detection|model-zoo/violence-detection|350"
    "yolo11-face|AdamCodd/YOLOv11n-face-detection|model-zoo/yolo11-face-detection|11"
    "yolo11-license-plate|morsetechlab/yolov11-license-plate-detection|model-zoo/yolo11-license-plate|650"
    "smoke-fire-yolov8n|SHOU-ISD/fire-and-smoke|model-zoo/smoke-fire-yolov8n|25"
    "vitpose-small|usyd-community/vitpose-plus-small|model-zoo/vitpose-small|1500"
    "segformer-b2-clothes|mattmdjaga/segformer_b2_clothes|model-zoo/segformer-b2-clothes|1500"
    "vehicle-damage-detection|harpreetsahota/car-dd-segmentation-yolov11|model-zoo/vehicle-damage-detection|2000"
    "florence-2-large|microsoft/Florence-2-large|model-zoo/florence-2-large|3000"
)

# 1 nemotron + HF snapshot rows + 6 custom-method sections
# (yolo26 / yolov8n-pose / osnet / stgcn / yolo-world / fashion-clip)
TOTAL=$(( 1 + ${#HF_DOWNLOADS[@]} + 6 ))
STEP=0

# ==========================================
# Nemotron-3-Nano-30B (Risk Reasoning LLM)
# models.yml: service ai-llm, download_method nemotron_gguf
# ==========================================
STEP=$(( STEP + 1 ))
echo ""
echo "=========================================="
echo "${STEP}/${TOTAL} - Nemotron-3-Nano-30B (Risk Reasoning LLM)"
echo "=========================================="
echo ""

NEMOTRON_DIR="${AI_MODELS_PATH}/nemotron/nemotron-3-nano-30b-a3b-q4km"
NEMOTRON_MODEL="${NEMOTRON_DIR}/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf"
NEMOTRON_URL="https://huggingface.co/unsloth/Nemotron-3-Nano-30B-A3B-GGUF/resolve/main/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf"
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
        "$HOME/.cache/huggingface/hub/models--unsloth--Nemotron-3-Nano-30B-A3B-GGUF/snapshots/*/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf"; do
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
            echo "        You can manually download from: https://huggingface.co/unsloth/Nemotron-3-Nano-30B-A3B-GGUF"
            echo "        Place the .gguf file at: $NEMOTRON_MODEL"
            rm -f "$NEMOTRON_MODEL"
            exit 1
        }

        # Verify checksum after download
        echo ""
        verify_checksum "$NEMOTRON_MODEL" "$NEMOTRON_CHECKSUM"
    fi
fi

# ==========================================
# yolo26 — models.yml download_method: yolo26
# enabled: false in models.yml (no backend VRAM slot) but the gateway needs the
# .pt files on disk: ai/gateway/export/export_yolo26.py + export_all.sh read
# model-zoo/yolo26/yolo26m.pt and scripts/prebuild-tensorrt-engines.sh builds
# the TensorRT engine from it.  Mirrors setup_lib/model_downloader.
# download_yolo26_models() — ultralytics GitHub release v8.4.0, not HuggingFace.
# ==========================================
STEP=$(( STEP + 1 ))
echo ""
echo "=========================================="
echo "${STEP}/${TOTAL} - YOLO26 n/s/m (Object Detection)"
echo "=========================================="
echo ""
YOLO26_DIR="${AI_MODELS_PATH}/model-zoo/yolo26"
# Pinned release — mirrors setup_lib/model_downloader.download_yolo26_models()
YOLO26_RELEASE="https://github.com/ultralytics/assets/releases/download/v8.4.0"
mkdir -p "$YOLO26_DIR"
download_file "${YOLO26_RELEASE}/yolo26n.pt" \
    "${YOLO26_DIR}/yolo26n.pt" "YOLO26-Nano" "5.3MB"
download_file "${YOLO26_RELEASE}/yolo26s.pt" \
    "${YOLO26_DIR}/yolo26s.pt" "YOLO26-Small" "19.5MB"
download_file "${YOLO26_RELEASE}/yolo26m.pt" \
    "${YOLO26_DIR}/yolo26m.pt" "YOLO26-Medium" "42.2MB"

# ==========================================
# Single-file downloads (models.yml custom download_method)
# ==========================================

# Ultralytics weights are served from GitHub releases, not HuggingFace
ULTRALYTICS_RELEASE="https://github.com/ultralytics/assets/releases/download/v8.2.0"

# yolov8n-pose — models.yml download_method: (runtime_file yolov8n-pose.pt)
# models.yml hf_repo (ultralytics/yolov8n-pose) is not a public HF repo, so this
# mirrors setup_lib/model_downloader.download_yolov8n_pose() instead.
STEP=$(( STEP + 1 ))
echo ""
echo "=========================================="
echo "${STEP}/${TOTAL} - YOLOv8n-pose (Human Pose Estimation)"
echo "=========================================="
echo ""
POSE_DIR="${AI_MODELS_PATH}/model-zoo/yolov8n-pose"
mkdir -p "$POSE_DIR"
download_file "${ULTRALYTICS_RELEASE}/yolov8n-pose.pt" \
    "${POSE_DIR}/yolov8n-pose.pt" "YOLOv8n-pose (~6MB)" "6MB"

# osnet-ain-x1-0 — models.yml download_method: osnet
# The MSMT17 checkpoint lives in kaiyangzhou/osnet under a long filename; the
# runtime (backend/services/osnet_loader.py) looks for the short name.
STEP=$(( STEP + 1 ))
echo ""
echo "=========================================="
echo "${STEP}/${TOTAL} - OSNet-AIN x1.0 (Person Re-ID)"
echo "=========================================="
echo ""
OSNET_DIR="${AI_MODELS_PATH}/model-zoo/osnet-ain-x1-0"
OSNET_LONG="osnet_ain_x1_0_msmt17_256x128_amsgrad_ep50_lr0.0015_coslr_b64_fb10_softmax_labsmth_flip_jitter.pth"
OSNET_LINK="${OSNET_DIR}/osnet_ain_x1_0_msmt17.pth"
mkdir -p "$OSNET_DIR"
download_file "https://huggingface.co/kaiyangzhou/osnet/resolve/main/${OSNET_LONG}" \
    "${OSNET_DIR}/${OSNET_LONG}" "OSNet-AIN x1.0 (~10MB)" "10MB"
if [ ! -e "$OSNET_LINK" ]; then
    ln -s "$OSNET_LONG" "$OSNET_LINK"
    echo "[OK] Linked: $(basename "$OSNET_LINK")"
fi

# stgcn-plus-plus — models.yml download_method: stgcn
STEP=$(( STEP + 1 ))
echo ""
echo "=========================================="
echo "${STEP}/${TOTAL} - ST-GCN++ (Skeleton Action Recognition)"
echo "=========================================="
echo ""
STGCN_DIR="${AI_MODELS_PATH}/model-zoo/stgcn-plus-plus"
mkdir -p "$STGCN_DIR"
download_file "http://download.openmmlab.com/mmaction/pyskl/ckpt/stgcnpp/stgcnpp_ntu60_xsub_hrnet/j.pth" \
    "${STGCN_DIR}/stgcnpp_ntu60_xsub_hrnet_j.pth" "ST-GCN++ (~20MB)" "20MB"

# yolo-world-s — models.yml download_method: yolo_world
STEP=$(( STEP + 1 ))
echo ""
echo "=========================================="
echo "${STEP}/${TOTAL} - YOLO-World-S (Open-Vocabulary Detection)"
echo "=========================================="
echo ""
YOLO_WORLD_DIR="${AI_MODELS_PATH}/model-zoo/yolo-world-s"
mkdir -p "$YOLO_WORLD_DIR"
download_file "${ULTRALYTICS_RELEASE}/yolov8s-worldv2.pt" \
    "${YOLO_WORLD_DIR}/yolov8s-worldv2.pt" "YOLO-World-S (~46MB)" "46MB"

# ==========================================
# fashion-clip (Marqo FashionSigLIP) — models.yml download_method: hf_cache
# open_clip loads this as "hf-hub:Marqo/marqo-fashionSigLIP", which requires the
# standard HuggingFace hub cache layout — it is deliberately NOT stored under
# model-zoo (see setup_lib/model_downloader.download_marqo_fashionsiglip()).
# ==========================================
STEP=$(( STEP + 1 ))
echo ""
echo "=========================================="
echo "${STEP}/${TOTAL} - Fashion-CLIP / FashionSigLIP (Clothing)"
echo "=========================================="
echo ""
HF_CACHE="${HF_HOME:-$HOME/.cache/huggingface}/hub"
MARQO_SNAPSHOTS="${HF_CACHE}/models--Marqo--marqo-fashionSigLIP/snapshots"
if [ -d "$MARQO_SNAPSHOTS" ] && [ -n "$(ls -A "$MARQO_SNAPSHOTS" 2>/dev/null)" ]; then
    echo "[SKIP] FashionSigLIP already in HuggingFace hub cache: $MARQO_SNAPSHOTS"
elif command -v hf &> /dev/null; then
    echo "[DOWNLOAD] Marqo/marqo-fashionSigLIP (~4.4GB) into ${HF_CACHE}"
    hf download Marqo/marqo-fashionSigLIP
elif command -v huggingface-cli &> /dev/null; then
    echo "[DOWNLOAD] Marqo/marqo-fashionSigLIP (~4.4GB) into ${HF_CACHE}"
    huggingface-cli download Marqo/marqo-fashionSigLIP
else
    echo "[WARN] Neither 'hf' nor 'huggingface-cli' found — open_clip needs this"
    echo "       model in the HuggingFace hub cache, which only the CLI can"
    echo "       populate. Install it (pip install -U huggingface_hub) or run"
    echo "       'python setup.py' and re-run this step."
fi

# ==========================================
# models.yml download set — HuggingFace snapshots
# ==========================================
for entry in "${HF_DOWNLOADS[@]}"; do
    IFS='|' read -r MODEL_NAME MODEL_REPO MODEL_PATH MODEL_SIZE <<< "$entry"
    STEP=$(( STEP + 1 ))
    echo ""
    echo "=========================================="
    echo "${STEP}/${TOTAL} - ${MODEL_NAME} ($(human_size "$MODEL_SIZE"))"
    echo "=========================================="
    echo ""
    mkdir -p "$(dirname "${AI_MODELS_PATH}/${MODEL_PATH}")"
    clone_or_update_hf "$MODEL_REPO" "${AI_MODELS_PATH}/${MODEL_PATH}" \
        "${MODEL_NAME} ($(human_size "$MODEL_SIZE"))"
done

echo ""
echo "=========================================="
echo "Download Complete!"
echo "=========================================="
echo ""
echo "Models installed to: ${AI_MODELS_PATH}"
echo ""
echo "Directory structure (models.yml download set — 25 entries, 32.79 GiB):"
echo "  ${AI_MODELS_PATH}/"
echo "  ├── nemotron/"
echo "  │   └── nemotron-3-nano-30b-a3b-q4km/  (Nemotron LLM)"
echo "  ├── model-zoo/"
echo "  │   ├── yolo26/                        (Detection — n/s/m .pt; gateway export)"
echo "  │   ├── florence-2-base/               (Vision-language)"
echo "  │   ├── florence-2-large/              (Vision-language — enabled: false)"
echo "  │   ├── siglip2-base-patch16-224/      (Re-ID embeddings)"
echo "  │   ├── vehicle-segment-classification/ (Vehicles)"
echo "  │   ├── pet-classifier/                (Pets)"
echo "  │   ├── depth-anything-v2-tiny/        (Depth)"
echo "  │   ├── osnet-ain-x1-0/                (Person Re-ID)"
echo "  │   ├── yolov8n-pose/                  (Pose)"
echo "  │   ├── threat-detection-yolov8n/      (Weapons)"
echo "  │   ├── vit-age-classifier/            (Age)"
echo "  │   ├── vit-gender-classifier/         (Gender)"
echo "  │   ├── stgcn-plus-plus/               (Action recognition)"
echo "  │   ├── xclip-base/                    (Video action — enabled: false)"
echo "  │   ├── weather-classification/        (Weather)"
echo "  │   ├── violence-detection/            (Violence)"
echo "  │   ├── yolo11-face-detection/         (Faces)"
echo "  │   ├── yolo11-license-plate/          (License plates)"
echo "  │   ├── smoke-fire-yolov8n/            (Smoke/fire)"
echo "  │   ├── yolo-world-s/                  (Open-vocab detection)"
echo "  │   ├── vitpose-small/                 (Pose)"
echo "  │   ├── segformer-b2-clothes/          (Clothing segmentation)"
echo "  │   └── vehicle-damage-detection/      (Damage segmentation)"
echo "  ├── triton/                            (TensorRT/ONNX engine cache)"
echo "  └── quantized/                         (INT8 variants)"
echo ""
echo "  fashion-clip lives in the HuggingFace hub cache, not in model-zoo:"
echo "    ${MARQO_SNAPSHOTS}"
echo ""
echo "Not downloaded (models.yml download_method: skip — their library fetches"
echo "them at runtime, so the download rule excludes them):"
echo "  - brisque-quality (piq), fast-alpr (ONNX), paddleocr"
echo "  - yolo26-general (weights not released), zero-dce-plus-plus (TF/"
echo "    PyTorch mismatch — see the models.yml comment)"
echo ""
echo "Note: \`enabled\` in models.yml governs backend model_zoo VRAM slots, not"
echo "disk provisioning — yolo26, xclip-base and florence-2-large are enabled:"
echo "false yet still downloaded here because live loaders/exporters read them."
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
