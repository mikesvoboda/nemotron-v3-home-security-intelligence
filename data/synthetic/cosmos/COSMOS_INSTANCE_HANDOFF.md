# Cosmos Instance Handoff - Video Generation Continuation

**Date:** 2026-01-28
**Purpose:** Instructions for continuing/resuming Cosmos video generation
**Status:** Instance can be safely suspended; documentation preserved for future use

---

## Current State Summary

### What Was Generated

| Metric             | Count        |
| ------------------ | ------------ |
| Total video files  | 496          |
| Unique videos      | 207          |
| Duration per video | ~5.8 seconds |
| Resolution         | 1280x704     |
| Frame rate         | 16 fps       |

### What Was NOT Generated (Due to Pipeline Bug)

| Missing                  | Expected   | Actual                      |
| ------------------------ | ---------- | --------------------------- |
| 10-second variants       | 240 frames | 93 frames (duplicate of 5s) |
| 30-second variants       | 720 frames | 93 frames (duplicate of 5s) |
| Autoregressive sequences | 6×5s clips | Not implemented             |

### Quality Assessment

- **Visual quality:** Excellent - production ready
- **Content accuracy:** Good - matches prompts
- **Technical issues:** Duration bug, duplicates
- **Usability:** 207 unique 5.8s clips are usable for testing

---

## Pipeline Bug Details

### Root Cause

The `batch_generate.sh` script does **not** pass `--num-output-frames` to Cosmos inference:

```bash
# CURRENT (broken):
python examples/inference.py -i $prompt_file -o $output_dir

# Cosmos uses default: 93 frames at 16fps = 5.81 seconds
```

### Required Fix

```bash
# FIXED version:
num_frames=$(jq -r '.num_output_frames' $prompt_file)
python examples/inference.py \
  -i $prompt_file \
  -o $output_dir \
  --num-output-frames $num_frames \
  --disable-guardrails
```

### For 30-Second Videos

30-second videos require autoregressive sliding window generation:

```bash
# 30s = 6 × 5s clips with overlap
python examples/inference.py \
  -i $prompt_file \
  -o $output_dir \
  --num-output-frames 720 \
  --autoregressive \
  --sliding-window \
  --disable-guardrails
```

---

## Resuming Generation

### Pre-Flight Checklist

1. [ ] Verify Cosmos instance is running
2. [ ] Verify GPU availability: `nvidia-smi`
3. [ ] Verify model is loaded: `ls checkpoints/Cosmos-Predict2.5-14B/`
4. [ ] Verify prompts are synced: `ls prompts/generated/*.json | wc -l` (should be 501)

### Option 1: Regenerate All Duration Variants

Generate proper 5s/10s/30s versions for all 167 video IDs:

```bash
# On Cosmos machine:
cd /home/shadeform/cosmos-predict2.5

# Sync prompts from git
git pull origin main
cp -r /path/to/nemotron/data/synthetic/cosmos/prompts/generated/* inputs/

# Run fixed generation script
./batch_generate_fixed.sh --all
```

### Option 2: Generate Only Missing 10s/30s

Skip the 5s variants (already good) and generate only longer durations:

```bash
# Generate only 10s and 30s variants
./batch_generate_fixed.sh --durations 10s,30s
```

### Option 3: Generate Specific Series

Focus on high-priority series:

```bash
# Threats only (R and T series)
./batch_generate_fixed.sh --series R,T --durations 5s,10s,30s

# Presentation videos only
./batch_generate_fixed.sh --series P --durations 5s,10s,30s
```

---

## Fixed Generation Script

Create this as `batch_generate_fixed.sh`:

```bash
#!/bin/bash
# Fixed Cosmos batch generation script
# Properly passes num_output_frames to inference

set -e

PROMPTS_DIR="${1:-inputs}"
OUTPUT_DIR="${2:-outputs}"
GPU_ID="${GPU_ID:-0}"

echo "=== Cosmos Fixed Batch Generation ==="
echo "Prompts: $PROMPTS_DIR"
echo "Output: $OUTPUT_DIR"
echo "GPU: $GPU_ID"

mkdir -p "$OUTPUT_DIR"

for prompt_file in "$PROMPTS_DIR"/*.json; do
    name=$(basename "$prompt_file" .json)
    output_path="$OUTPUT_DIR/$name"

    if [[ -f "$output_path.mp4" ]]; then
        echo "Skipping $name (already exists)"
        continue
    fi

    echo "Generating: $name"

    # Extract num_output_frames from JSON
    num_frames=$(jq -r '.num_output_frames' "$prompt_file")

    # Determine if autoregressive mode needed (>240 frames)
    extra_args=""
    if [[ $num_frames -gt 240 ]]; then
        echo "  Using autoregressive mode for $num_frames frames"
        extra_args="--autoregressive --sliding-window"
    fi

    # Run inference with correct parameters
    CUDA_VISIBLE_DEVICES=$GPU_ID python examples/inference.py \
        -i "$prompt_file" \
        -o "$output_path" \
        --inference-type text2world \
        --model 14B/post-trained \
        --num-output-frames "$num_frames" \
        --disable-guardrails \
        $extra_args

    echo "  Completed: $name"
done

echo "=== Generation Complete ==="
```

---

## Parallel Generation (8 GPU)

For faster generation on multi-GPU systems:

```bash
#!/bin/bash
# parallel_generate_fixed.sh

PROMPTS_DIR="${1:-inputs}"
OUTPUT_DIR="${2:-outputs}"
NUM_GPUS=8

# Split prompts across GPUs
total=$(ls "$PROMPTS_DIR"/*.json | wc -l)
per_gpu=$((total / NUM_GPUS + 1))

for gpu_id in $(seq 0 $((NUM_GPUS - 1))); do
    (
        export GPU_ID=$gpu_id
        start=$((gpu_id * per_gpu))

        ls "$PROMPTS_DIR"/*.json | tail -n +$((start + 1)) | head -n $per_gpu | while read prompt_file; do
            # Same generation logic as single GPU
            ./batch_generate_fixed.sh "$prompt_file" "$OUTPUT_DIR"
        done
    ) &
done

wait
echo "All GPUs finished"
```

---

## Post-Generation Validation

After generating videos, run validation:

```bash
# Check durations
for f in outputs/*.mp4; do
    expected=$(basename "$f" .mp4 | grep -oE '[0-9]+s' | tr -d 's')
    actual=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f" | cut -d. -f1)

    if [[ "$actual" -lt "$expected" ]]; then
        echo "FAIL: $f (expected ${expected}s, got ${actual}s)"
    fi
done

# Check for duplicates
echo "Checking for duplicate hashes..."
md5sum outputs/*.mp4 | sort | uniq -d -w32

# Verify unique content per video ID
for id in C01 E01 P01 R01 T01; do
    echo "=== $id ==="
    md5sum outputs/${id}_*.mp4 2>/dev/null || echo "No files for $id"
done
```

---

## Pushing Generated Videos to Git

After generation and validation:

```bash
# On Cosmos machine:
cd /path/to/nemotron

# Copy generated videos
cp outputs/*.mp4 data/synthetic/cosmos/videos/

# Add to Git LFS and push
git add data/synthetic/cosmos/videos/*.mp4
git commit -m "feat: add regenerated Cosmos videos with correct durations"
git lfs push --all origin
git push origin main
```

---

## Hardware Requirements

| GPU  | VRAM  | Generation Time (per 5s video) |
| ---- | ----- | ------------------------------ |
| B300 | 267GB | ~45 seconds                    |
| H200 | 141GB | ~60 seconds                    |
| H100 | 80GB  | ~90 seconds                    |

### For 30-Second Videos (Autoregressive)

Multiply by 6x for autoregressive generation:

- B300: ~4.5 minutes per 30s video
- H200: ~6 minutes per 30s video

### Total Time Estimates

| Task                  | Video Count | Time (8×B300) |
| --------------------- | ----------- | ------------- |
| Regenerate all 5s     | 167         | ~16 minutes   |
| Generate all 10s      | 167         | ~16 minutes   |
| Generate all 30s      | 167         | ~1.5 hours    |
| **Full regeneration** | **501**     | **~2 hours**  |

---

## Files Preserved in Repository

These files are preserved for future generation:

```
data/synthetic/cosmos/
├── HANDOFF.md                    # Original setup documentation
├── REGENERATION_HANDOFF.md       # Analysis and regeneration instructions
├── COSMOS_INSTANCE_HANDOFF.md    # THIS FILE - instance continuation
├── VIDEO_CATEGORY_MAPPING.md     # Category mapping reference
├── generation_manifest.yaml      # Video definitions (167 videos)
├── prompts/
│   ├── templates/                # Reusable prompt components
│   └── generated/                # 501 ready-to-use prompt files
├── batch_generate.sh             # Original script (has bug)
├── parallel_generate.py          # Multi-GPU script
├── monitor.sh                    # Progress monitoring
└── generate_prompts.py           # Prompt generation script
```

---

## Contact & Resources

- **NVIDIA Cosmos Documentation:** https://github.com/nvidia-cosmos/cosmos-predict2.5
- **Model Download:** `huggingface-cli download nvidia/Cosmos-Predict2.5-14B`
- **NGC Container:** `nvcr.io/nvidia/pytorch:25.10-py3`

---

## Quick Reference Commands

```bash
# Check GPU status
nvidia-smi

# Verify Cosmos installation
docker run --rm --gpus all cosmos-b300 python -c "import cosmos; print('OK')"

# Test single generation
python examples/inference.py \
  -i prompts/generated/C01_5s.json \
  -o test_output \
  --num-output-frames 120 \
  --disable-guardrails

# Monitor generation progress
watch -n 5 'ls outputs/*.mp4 | wc -l'
```
