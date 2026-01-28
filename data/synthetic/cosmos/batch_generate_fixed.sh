#!/bin/bash
# Fixed batch video generation with proper duration support
# - Reads num_output_frames from each JSON prompt
# - Enables autoregressive mode for longer videos (>120 frames)
# - Processes one file at a time to ensure correct parameters per video

set -e

COSMOS_DIR="/home/shadeform/cosmos-predict2.5"
PROMPTS_DIR="/home/shadeform/nemotron-v3-home-security-intelligence/data/synthetic/cosmos/prompts/generated"
OUTPUT_BASE="${COSMOS_DIR}/outputs/security_videos"
LOG_DIR="/home/shadeform/nemotron-v3-home-security-intelligence/data/synthetic/cosmos/logs"

NUM_GPUS=8

# Parse arguments
FILTER_DURATION=""  # e.g., "5s" "10s" "30s" or empty for all
SKIP_EXISTING=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --duration)
            FILTER_DURATION="$2"
            shift 2
            ;;
        --no-skip)
            SKIP_EXISTING=false
            shift
            ;;
        --gpus)
            NUM_GPUS="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

mkdir -p "${OUTPUT_BASE}"
mkdir -p "${LOG_DIR}"

# Get prompt files, optionally filtered by duration
if [[ -n "$FILTER_DURATION" ]]; then
    mapfile -t PROMPT_FILES < <(ls ${PROMPTS_DIR}/*_${FILTER_DURATION}.json 2>/dev/null | sort)
    echo "Filtered to ${FILTER_DURATION} videos only"
else
    mapfile -t PROMPT_FILES < <(ls ${PROMPTS_DIR}/*.json | grep -v generation_queue | sort -t'_' -k2 -V)
fi

TOTAL_FILES=${#PROMPT_FILES[@]}

if [[ $TOTAL_FILES -eq 0 ]]; then
    echo "No prompt files found!"
    exit 1
fi

echo "=========================================="
echo "Fixed Batch Video Generation"
echo "=========================================="
echo "Total videos: ${TOTAL_FILES}"
echo "GPUs: ${NUM_GPUS}"
echo "Duration filter: ${FILTER_DURATION:-all}"
echo "Skip existing: ${SKIP_EXISTING}"
echo "Output: ${OUTPUT_BASE}"
echo "=========================================="

# Function to generate a single video with correct parameters
generate_single_video() {
    local GPU_ID=$1
    local PROMPT_FILE=$2
    local LOG_FILE="${LOG_DIR}/gpu${GPU_ID}.log"
    
    local FNAME=$(basename "$PROMPT_FILE" .json)
    local OUTPUT_PATH="${OUTPUT_BASE}/${FNAME}.mp4"
    
    # Skip if exists
    if [[ "$SKIP_EXISTING" == "true" && -f "$OUTPUT_PATH" ]]; then
        # Check if it's a real video (not a tiny file)
        local SIZE=$(stat -f%z "$OUTPUT_PATH" 2>/dev/null || stat -c%s "$OUTPUT_PATH" 2>/dev/null)
        if [[ $SIZE -gt 10000 ]]; then
            echo "[GPU ${GPU_ID}] Skipping ${FNAME} (already exists, ${SIZE} bytes)" | tee -a "$LOG_FILE"
            return 0
        fi
    fi
    
    # Extract num_output_frames from JSON
    local NUM_FRAMES=$(jq -r '.num_output_frames' "$PROMPT_FILE")
    
    # Determine if autoregressive mode needed (model native is ~77 frames)
    local EXTRA_ARGS=""
    if [[ $NUM_FRAMES -gt 120 ]]; then
        EXTRA_ARGS="--enable-autoregressive"
        echo "[GPU ${GPU_ID}] ${FNAME}: ${NUM_FRAMES} frames (autoregressive mode)" | tee -a "$LOG_FILE"
    else
        echo "[GPU ${GPU_ID}] ${FNAME}: ${NUM_FRAMES} frames (standard mode)" | tee -a "$LOG_FILE"
    fi
    
    # Run Docker for single video
    docker run --rm \
        --gpus "device=${GPU_ID}" \
        --ipc=host \
        --ulimit memlock=-1 \
        --ulimit stack=67108864 \
        -v "${COSMOS_DIR}:/workspace" \
        -v "/home/shadeform/.cache/huggingface:/root/.cache/huggingface" \
        -v "${PROMPTS_DIR}:/prompts" \
        -w /workspace \
        cosmos-b300 \
        python examples/inference.py \
        -i "/prompts/${FNAME}.json" \
        -o /workspace/outputs/security_videos \
        --inference-type=text2world \
        --model=14B/post-trained \
        --disable-guardrails \
        $EXTRA_ARGS \
        2>&1 | tee -a "$LOG_FILE"
    
    echo "[GPU ${GPU_ID}] Completed: ${FNAME}" | tee -a "$LOG_FILE"
}

# Function to run a GPU worker
run_gpu_worker() {
    local GPU_ID=$1
    shift
    local -a FILES=("$@")
    
    echo "[GPU ${GPU_ID}] Starting worker with ${#FILES[@]} videos"
    
    for PROMPT_FILE in "${FILES[@]}"; do
        generate_single_video "$GPU_ID" "$PROMPT_FILE"
    done
    
    echo "[GPU ${GPU_ID}] Worker complete!"
}

# Split files across GPUs using round-robin
echo ""
echo "Starting generation on ${NUM_GPUS} GPUs..."
echo ""

for GPU_ID in $(seq 0 $((NUM_GPUS - 1))); do
    # Round-robin distribution
    GPU_FILES=()
    for ((IDX=GPU_ID; IDX<TOTAL_FILES; IDX+=NUM_GPUS)); do
        GPU_FILES+=("${PROMPT_FILES[$IDX]}")
    done
    
    if [[ ${#GPU_FILES[@]} -gt 0 ]]; then
        # Count durations
        COUNT_5S=$(printf '%s\n' "${GPU_FILES[@]}" | grep -c '_5s.json' || true)
        COUNT_10S=$(printf '%s\n' "${GPU_FILES[@]}" | grep -c '_10s.json' || true)
        COUNT_30S=$(printf '%s\n' "${GPU_FILES[@]}" | grep -c '_30s.json' || true)
        echo "[GPU ${GPU_ID}] Assigned ${#GPU_FILES[@]} videos: ${COUNT_5S}x5s + ${COUNT_10S}x10s + ${COUNT_30S}x30s"
        
        # Launch worker in background
        run_gpu_worker ${GPU_ID} "${GPU_FILES[@]}" &
    fi
done

echo ""
echo "All GPU workers launched. Waiting for completion..."
echo "Monitor with: tail -f ${LOG_DIR}/gpu*.log"
echo ""

# Wait for all background jobs
wait

echo ""
echo "=========================================="
echo "Generation complete!"
echo "=========================================="
echo "Output videos: ${OUTPUT_BASE}"
ls "${OUTPUT_BASE}"/*.mp4 2>/dev/null | wc -l
echo "videos generated"

# Validation summary
echo ""
echo "=== Validation Summary ==="
echo "Checking for proper durations..."

for DURATION in 5s 10s 30s; do
    COUNT=$(ls "${OUTPUT_BASE}"/*_${DURATION}.mp4 2>/dev/null | wc -l)
    echo "${DURATION} videos: ${COUNT}"
done

echo ""
echo "Checking for duplicates..."
UNIQUE=$(md5sum "${OUTPUT_BASE}"/*.mp4 2>/dev/null | awk '{print $1}' | sort | uniq | wc -l)
TOTAL=$(ls "${OUTPUT_BASE}"/*.mp4 2>/dev/null | wc -l)
echo "Unique videos: ${UNIQUE} / ${TOTAL}"
