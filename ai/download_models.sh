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
# That rule yields 5 of the 10 catalogue entries and 763 MB of models.yml
# size_mb estimates — figures a reader can re-measure (parse models.yml, or
# run backend/tests/unit/setup_lib/test_download_models_script_vlm_retirement.py,
# which re-derives them and pins this script's fetch list to the rule).  The 5
# excluded entries are the download_method: skip ones (face-detector-scrfd,
# face-recognizer, fast-alpr, paddleocr, yolo26-general) — their libraries
# fetch what they need at runtime.
#
# R8 (slices S1-S3, 2026-09-29, ledger items 46-55) retired the ~32GB legacy
# zoo this script used to provision: the Nemotron GGUF (the text-only LLM path
# — deleted; the shipped reasoning engine is the profiled ai-vlm llama.cpp
# container, whose identity is config per ledger D5, so this script never
# provisions or names a VLM), Florence x2, SigLIP/CLIP, vehicle-segment, pet,
# depth, age/gender, weather, violence, smoke-fire, pose (vitpose/yolov8n-
# pose), segformer, vehicle-damage, stgcn, yolo-world and fashion-clip.  Each
# row's death was re-measured against live readers before deletion (nothing
# populates enrichment_data["violence_detection"]; smoke_fire_loader.py no
# longer exists and alert_engine's _check_smoke_fire is documented mock; the
# gateway serves only the yolo26/reid/threat Triton names under
# GATEWAY_MODEL_SET=vlm, so the other exports could never load).
#
# The `enabled` flag governs backend model_zoo VRAM slots, NOT disk
# provisioning — yolo26 is `enabled: false` yet is still fetched because live
# code reads its .pt files off disk: ai/gateway/export/export_yolo26.py +
# export_all.sh read model-zoo/yolo26/yolo26m.pt and
# scripts/prebuild-tensorrt-engines.sh builds the TensorRT engine from it.
#
# Models fetched (5 entries, 763 MB by models.yml size_mb):
#   - YOLO26 n/s/m .pt - 67MB - object detection (gateway Triton export input)
#   - OSNet-AIN x1.0 - 10MB - person re-ID (Triton `reid`; osnet_loader.py
#       reads the short-name link this script creates)
#   - Threat-Detection-YOLOv8n - 25MB - weapon detection (Triton `threat`)
#   - YOLO11 face - 11MB - face detection on person crops
#   - YOLO11 license-plate - 650MB - plate detection
#
# Deliberately NOT provisioned by anything in this repo: the shipped reasoning
# engine's GGUF pair.  VLM_MODEL_PATH + VLM_MMPROJ_PATH (one identity — the
# projector file is part of it; without it the serve is text-only and every
# vlm_assess degrades silently) are read from ${AI_MODELS_PATH}/vlm, which
# compose mounts read-only into ai-vlm at /models.  Identity is operator config
# (.env), so no script fetches it and this one never will (ledger D5).  The
# opt-in ai-llm-vllm benchmarking harness (--profile vllm) is separate again:
# it wants HF-format models under ${AI_MODELS_PATH}/huggingface.
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
    ["Subh775/Threat-Detection-YOLOv8n"]=""
    ["AdamCodd/YOLOv11n-face-detection"]=""
    ["morsetechlab/yolov11-license-plate-detection"]=""
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

# Create directory structure.  The vlm/ dir is where the operator places the
# GGUF pair consumed by VLM_MODEL_PATH/VLM_MMPROJ_PATH (compose mounts it
# read-only into ai-vlm at /models); this script creates the directory but
# never fetches or names the weights — identity is operator config (ledger D5).
mkdir -p "${AI_MODELS_PATH}/vlm"
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
# plain HuggingFace snapshot (no download_method, but a non-empty hf_repo):
#   name | hf_repo | local_path | size_mb
# Keep in sync with models.yml — regenerate with the same filter setup_lib uses:
#   download_method != "skip" and (hf_repo or download_method)
# The two custom-method rows the rule selects (yolo26, osnet-ain-x1-0) are
# fetched in their own sections below.  R8 retired the other 13 rows this
# array used to carry (their readers died with slices S1-S3; see the header).
# test_download_models_script_vlm_retirement.py pins this array to a
# re-derivation of the rule, so a models.yml row that changes selection fails
# a test instead of quietly over- or under-provisioning a deploy.
HF_DOWNLOADS=(
    "threat-detection-yolov8n|Subh775/Threat-Detection-YOLOv8n|model-zoo/threat-detection-yolov8n|25"
    "yolo11-face|AdamCodd/YOLOv11n-face-detection|model-zoo/yolo11-face-detection|11"
    "yolo11-license-plate|morsetechlab/yolov11-license-plate-detection|model-zoo/yolo11-license-plate|650"
)

# 2 custom-method sections (yolo26, osnet) + the HF snapshot rows above.
# Nothing else: R8 retired pose/stgcn/yolo-world/fashion-clip/nemotron.
TOTAL=$(( 2 + ${#HF_DOWNLOADS[@]} ))
STEP=0

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
echo "Directory structure (5 entries fetched, 763 MB by models.yml size_mb;"
echo "the rule selects exactly these — see the header re-derivation):"
echo "  ${AI_MODELS_PATH}/"
echo "  ├── model-zoo/"
echo "  │   ├── yolo26/                        (Detection — n/s/m .pt; gateway export)"
echo "  │   ├── osnet-ain-x1-0/                (Person Re-ID — Triton reid)"
echo "  │   ├── threat-detection-yolov8n/      (Weapons — Triton threat)"
echo "  │   ├── yolo11-face-detection/         (Faces)"
echo "  │   └── yolo11-license-plate/          (License plates)"
echo "  ├── triton/                            (TensorRT/ONNX engine cache)"
echo "  └── quantized/                         (INT8 variants)"
echo ""
echo "Reasoning engine (the shipped ai-vlm llama.cpp container) — NOT fetched"
echo "by this script; its identity is operator config (ledger D5):"
echo "  Place the GGUF pair named by VLM_MODEL_PATH + VLM_MMPROJ_PATH (they are"
echo "  one identity — the mmproj projector is required, without it the serve"
echo "  is text-only and every vlm_assess call degrades silently) under:"
echo "    ${AI_MODELS_PATH}/vlm/"
echo "  which compose mounts read-only into ai-vlm at /models. ai-vlm starts"
echo "  with the stack:    podman compose -f docker-compose.prod.yml up -d ai-vlm"
echo "  (The opt-in --profile vllm benchmarking harness is separate: it wants"
echo "  HF-format models under ${AI_MODELS_PATH}/huggingface.)"
echo ""
echo "Not downloaded (models.yml download_method: skip — their library fetches"
echo "them at runtime, so the download rule excludes them):"
echo "  - face-detector-scrfd, face-recognizer (insightface/onnxruntime),"
echo "    fast-alpr (ONNX auto-download), paddleocr"
echo "  - yolo26-general (weights not released yet — models.yml comment)"
echo ""
echo "Note: \`enabled\` in models.yml governs backend model_zoo VRAM slots, not"
echo "disk provisioning — yolo26 and yolo26-general are enabled: false; yolo26"
echo "is still downloaded here because the gateway export/TensorRT-prebuild"
echo "path reads its .pt files off disk."
echo ""
echo "Security verification:"
echo "  - Direct downloads: SHA256 checksum verification"
echo "  - Git LFS repos: Content-addressable storage (built-in)"
echo ""
echo "Next steps:"
echo "  1. Ensure docker-compose.prod.yml has correct AI_MODELS_PATH"
echo "  2. Start services: podman-compose -f docker-compose.prod.yml up -d"
echo "     (ai-vlm starts with the rest. With no GPU it fails at start and the"
echo "      others still come up — nothing depends_on it; until O2.1's fake-AI"
echo "      overlay lands, list the services you want and leave ai-vlm off.)"
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
