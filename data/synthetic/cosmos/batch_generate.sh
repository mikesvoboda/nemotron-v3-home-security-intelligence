#!/bin/bash
# Batch video generation with persistent model per GPU
# Each GPU loads model once, then processes ~11 videos sequentially

set -e

COSMOS_DIR="/home/shadeform/cosmos-predict2.5"
PROMPTS_DIR="/home/shadeform/nemotron-v3-home-security-intelligence/data/synthetic/cosmos/prompts/generated"
OUTPUT_BASE="${COSMOS_DIR}/outputs/security_videos"
LOG_DIR="/home/shadeform/nemotron-v3-home-security-intelligence/data/synthetic/cosmos/logs"

NUM_GPUS=8

mkdir -p "${OUTPUT_BASE}"
mkdir -p "${LOG_DIR}"

# Get all prompt files (excluding generation_queue.json)
mapfile -t PROMPT_FILES < <(ls ${PROMPTS_DIR}/*.json | grep -v generation_queue | sort)
TOTAL_FILES=${#PROMPT_FILES[@]}
FILES_PER_GPU=$(( (TOTAL_FILES + NUM_GPUS - 1) / NUM_GPUS ))

echo "=========================================="
echo "Batch Video Generation"
echo "=========================================="
echo "Total videos: ${TOTAL_FILES}"
echo "GPUs: ${NUM_GPUS}"
echo "Videos per GPU: ~${FILES_PER_GPU}"
echo "Output: ${OUTPUT_BASE}"
echo "=========================================="

# Function to run a batch on a specific GPU
run_gpu_batch() {
    local GPU_ID=$1
    shift
    local -a FILES=("$@")
    
    if [ ${#FILES[@]} -eq 0 ]; then
        echo "[GPU ${GPU_ID}] No files to process"
        return
    fi
    
    echo "[GPU ${GPU_ID}] Processing ${#FILES[@]} videos..."
    
    # Build list of input files (space-separated after single -i)
    local -a INPUT_FILES=()
    for f in "${FILES[@]}"; do
        fname=$(basename "$f")
        INPUT_FILES+=("/prompts/${fname}")
    done
    
    echo "[GPU ${GPU_ID}] Input files: ${INPUT_FILES[*]}"
    
    # Run Docker with all inputs - model loads once, processes all
    # Note: tyro requires -i file1 file2 file3 (not -i file1 -i file2)
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
        -i ${INPUT_FILES[*]} \
        -o /workspace/outputs/security_videos \
        --inference-type=text2world \
        --model=14B/post-trained \
        --disable-guardrails \
        2>&1 | tee "${LOG_DIR}/gpu${GPU_ID}.log"
    
    echo "[GPU ${GPU_ID}] Batch complete!"
}

# Split files across GPUs and launch in parallel
echo ""
echo "Starting generation on ${NUM_GPUS} GPUs..."
echo ""

for GPU_ID in $(seq 0 $((NUM_GPUS - 1))); do
    START_IDX=$((GPU_ID * FILES_PER_GPU))
    
    # Get this GPU's batch of files
    GPU_FILES=()
    for i in $(seq 0 $((FILES_PER_GPU - 1))); do
        IDX=$((START_IDX + i))
        if [ $IDX -lt $TOTAL_FILES ]; then
            GPU_FILES+=("${PROMPT_FILES[$IDX]}")
        fi
    done
    
    if [ ${#GPU_FILES[@]} -gt 0 ]; then
        echo "[GPU ${GPU_ID}] Assigned ${#GPU_FILES[@]} videos: $(basename ${GPU_FILES[0]}) ... $(basename ${GPU_FILES[-1]})"
        
        # Launch in background
        run_gpu_batch ${GPU_ID} "${GPU_FILES[@]}" &
    fi
done

echo ""
echo "All GPU jobs launched. Waiting for completion..."
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
