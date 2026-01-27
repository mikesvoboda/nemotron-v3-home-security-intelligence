# Cosmos Video Generation Handoff

## Overview

You are generating **88 synthetic security camera videos** using NVIDIA Cosmos models on an H200 instance. This document contains everything you need, **verified and tested on 2026-01-27**.

---

## Quick Status

| Item | Status | Notes |
|------|--------|-------|
| Environment | ✅ Bootstrapped | `/home/ubuntu/cosmos-predict2.5` |
| Cosmos-Predict2.5-14B | ✅ Downloaded | 54GB in `checkpoints/` |
| Cosmos-Reason1-7B | ✅ Downloaded | 16GB in cosmos-reason1 |
| Test Generation | ✅ Verified | 5.8s video generated successfully |
| HuggingFace Auth | ✅ Configured | Token saved to cache |

---

## Verified System Specifications

| Component | Specification | Verified |
|-----------|---------------|----------|
| **GPU** | NVIDIA H200 | ✅ 139.8 GB VRAM |
| **CUDA** | 13.0 | ✅ |
| **Python** | 3.10.19 (via uv) | ✅ Auto-installed |
| **PyTorch** | 2.7.0+cu128 | ✅ |
| **OS** | Ubuntu 24.04 | ✅ |

---

## Bootstrap Process (Verified Working)

### Step 1: Clone Repository

```bash
cd /home/ubuntu
git clone https://github.com/nvidia-cosmos/cosmos-predict2.5.git
cd cosmos-predict2.5
```

### Step 2: Create Environment with uv

**IMPORTANT:** Use `--extra cu128` (NOT cu130 - has platform compatibility issues)

```bash
# uv is pre-installed on this machine
uv sync --extra cu128
```

This installs 246 packages including:
- PyTorch 2.7.0+cu128
- flash-attn 2.7.3+cu128
- natten 0.21.0+cu128
- transformer-engine 2.2+cu128

### Step 3: Install Git LFS and Pull Assets

```bash
sudo apt-get install -y git-lfs
git lfs install
git lfs pull
```

### Step 4: Authenticate with Hugging Face

**CRITICAL:** You must accept licenses for ALL these models on HuggingFace before proceeding:

| Model | URL | Required For |
|-------|-----|--------------|
| nvidia/Cosmos-Predict2.5-14B | https://huggingface.co/nvidia/Cosmos-Predict2.5-14B | Main generation |
| nvidia/Cosmos-Predict2.5-2B | https://huggingface.co/nvidia/Cosmos-Predict2.5-2B | Config loading |
| nvidia/Cosmos-Guardrail1 | https://huggingface.co/nvidia/Cosmos-Guardrail1 | Safety checks |
| nvidia/Cosmos-Reason1-7B | https://huggingface.co/nvidia/Cosmos-Reason1-7B | Quality scoring |

```bash
source .venv/bin/activate
huggingface-cli login --token YOUR_HF_TOKEN
```

### Step 5: Download Models

```bash
# Create checkpoints directory
mkdir -p checkpoints

# Download Cosmos-Predict2.5-14B (54GB total)
huggingface-cli download nvidia/Cosmos-Predict2.5-14B \
  --local-dir checkpoints/Cosmos-Predict2.5-14B

# Verify download
ls -la checkpoints/Cosmos-Predict2.5-14B/base/
# Should show: post-trained/ (27GB) and pre-trained/ (27GB)
```

### Step 6: Install Cosmos-Reason1 (Optional - for quality scoring)

```bash
cd /home/ubuntu
git clone https://github.com/nvidia-cosmos/cosmos-reason1.git
cd cosmos-reason1
uv sync

# Download model
mkdir -p checkpoints
huggingface-cli download nvidia/Cosmos-Reason1-7B \
  --local-dir checkpoints/Cosmos-Reason1-7B
```

### Step 7: Verify Installation

```bash
cd /home/ubuntu/cosmos-predict2.5
source .venv/bin/activate

# Verify PyTorch and GPU
python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA: {torch.cuda.is_available()}')
print(f'GPU: {torch.cuda.get_device_name(0)}')
print(f'VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB')
"

# Expected output:
# PyTorch: 2.7.0+cu128
# CUDA: True
# GPU: NVIDIA H200
# VRAM: 139.8 GB
```

---

## Test Generation Results (Verified 2026-01-27)

### Command Used

```bash
cd /home/ubuntu/cosmos-predict2.5
source .venv/bin/activate

python examples/inference.py \
  -i assets/base/snowy_stop_light.json \
  -o outputs/test \
  --inference-type=text2world \
  --model=14B/post-trained
```

### Performance Metrics

| Metric | Value |
|--------|-------|
| **Generation Time** | 14:58 (35 steps × 25.4s/step) |
| **Peak VRAM Usage** | 65 GB (45% of 140 GB) |
| **GPU Utilization** | 100% during diffusion steps |
| **Model Load Time** | ~4 minutes (first run downloads additional checkpoints) |

### Output Video Specifications

| Property | Value |
|----------|-------|
| **File Size** | 598 KB |
| **Resolution** | 1280×704 (720p) |
| **Duration** | 5.81 seconds |
| **Frame Rate** | 16 fps |
| **Total Frames** | 93 |
| **Codec** | H.264 |
| **Bitrate** | 843 kbps |

### Generated Files

```
outputs/test/
├── config.yaml              # Model configuration
├── console.log              # Generation logs
├── debug.log                # Detailed debug info
├── snowy_stop_light.json    # Input parameters
└── snowy_stop_light.mp4     # Generated video (598 KB)
```

---

## Video Generation Summary

### Total Videos: 88

| Category | Count | Duration Range | Subtotal Runtime |
|----------|-------|----------------|------------------|
| **Presentation** | 48 | 15-20s | 13.7 min |
| **Training** | 40 | 30s each | 20.0 min |
| **TOTAL** | **88** | - | **33.7 min** |

### Duration Breakdown

| Duration | Count | Generation Method |
|----------|-------|-------------------|
| 15s | 23 | 3 × 5s clips concatenated |
| 18s | 12 | 4 × 5s clips concatenated |
| 20s | 13 | 4 × 5s clips concatenated |
| 30s | 40 | 6 iterations (sliding window) |

### Estimated Generation Time

Based on verified test results (5s clip = ~15 minutes):

| Video Type | Count | Time Each | Total Time |
|------------|-------|-----------|------------|
| 15s presentation | 23 | 45 min (3 clips) | 17.25 hours |
| 18s presentation | 12 | 60 min (4 clips) | 12 hours |
| 20s presentation | 13 | 60 min (4 clips) | 13 hours |
| 30s training | 40 | 75 min (6 iterations) | 50 hours |
| **TOTAL** | **88** | - | **~92 hours** |

### Parallel Generation Options

With 65GB peak usage and 140GB total VRAM:

| Configuration | Time | Risk |
|---------------|------|------|
| Serial (1× 14B) | ~92 hours | Safe |
| 1× 14B + 1× 2B | ~55 hours | Safe (85GB total) |
| 2× 14B | ~46 hours | Risky (130GB, 10GB buffer) |

---

## Working Inference Commands

### Text2World (Presentation Videos)

```bash
cd /home/ubuntu/cosmos-predict2.5
source .venv/bin/activate

python examples/inference.py \
  -i assets/base/snowy_stop_light.json \
  -o outputs/presentation \
  --inference-type=text2world \
  --model=14B/post-trained
```

### Custom Prompt Generation

Create a JSON file like `my_video.json`:

```json
{
  "inference_type": "text2world",
  "name": "my_custom_video",
  "prompt": "Security camera footage from elevated doorbell camera, suburban home front porch at night. A person in dark hoodie approaches the front door..."
}
```

Then run:

```bash
python examples/inference.py \
  -i my_video.json \
  -o outputs/custom \
  --inference-type=text2world \
  --model=14B/post-trained
```

### Extended Duration (30s Training Videos)

For videos longer than 5s, use autoregressive mode:

```bash
python examples/inference.py \
  -i assets/base/bus_terminal_long.json \
  -o outputs/long_video \
  --model=14B/post-trained
```

### All Available Options

```bash
python examples/inference.py --help
```

Key options:
- `--model`: `2B/post-trained`, `2B/pre-trained`, `14B/post-trained`, `14B/pre-trained`
- `--inference-type`: `text2world`, `image2world`, `video2world`
- `--disable-guardrails`: Skip safety checks (not recommended)
- `--seed`: Set random seed for reproducibility
- `--guidance`: Prompt adherence (default 7.0)

---

## Directory Structure

```
/home/ubuntu/
├── cosmos-predict2.5/                    # Main Cosmos installation
│   ├── .venv/                            # Python virtual environment
│   ├── checkpoints/
│   │   └── Cosmos-Predict2.5-14B/        # 54GB model
│   │       └── base/
│   │           ├── post-trained/         # 27GB - USE THIS
│   │           └── pre-trained/          # 27GB
│   ├── assets/base/                      # Example input files
│   ├── examples/inference.py             # Main inference script
│   └── outputs/                          # Generated videos
│
├── cosmos-reason1/                       # Quality scoring (optional)
│   ├── .venv/                            # Separate environment
│   └── checkpoints/
│       └── Cosmos-Reason1-7B/            # 16GB model
│
└── nemotron-v3-home-security-intelligence/
    └── data/synthetic/cosmos/
        ├── HANDOFF.md                    # This file
        ├── generation_manifest.yaml      # All 88 video definitions
        └── generation_status.json        # Progress tracking
```

---

## First-Run Behavior

**IMPORTANT:** On first inference run, additional models are automatically downloaded:

| Model | Size | Purpose |
|-------|------|---------|
| Cosmos-Guardrail1 | ~2GB | Content safety |
| Cosmos-Predict2.5-2B | ~5GB | Config dependencies |
| Cosmos-Reason1-7B | ~16GB | Text encoder |
| Tokenizer | ~1GB | Video tokenization |

This adds ~5 minutes to the first run. Subsequent runs use cached models.

---

## Memory Usage Profile

### During Model Loading
- Base model: ~50 GB
- Total with tokenizer/guardrails: ~65 GB

### During Generation (Peak)
- **65 GB** at diffusion step execution
- GPU utilization: 100%
- 75 GB free headroom

### Memory Timeline
```
Start      → Load model     → Generate      → Save
0 GB       → 50 GB          → 65 GB (peak)  → 50 GB
```

---

## Troubleshooting

### "GatedRepoError: 403 Client Error"

**Cause:** HuggingFace license not accepted

**Solution:** Visit each model's HuggingFace page and accept the license:
- https://huggingface.co/nvidia/Cosmos-Predict2.5-14B
- https://huggingface.co/nvidia/Cosmos-Predict2.5-2B  
- https://huggingface.co/nvidia/Cosmos-Guardrail1
- https://huggingface.co/nvidia/Cosmos-Reason1-7B

### "decord" Platform Error with cu130

**Cause:** CUDA 13.0 wheels only available for ARM64

**Solution:** Use `--extra cu128` instead:
```bash
uv sync --extra cu128  # NOT cu130
```

### Slow First Run

**Cause:** Additional models being downloaded

**Solution:** Wait ~5 minutes for downloads to complete. Check progress:
```bash
tail -f outputs/test/console.log
```

### Generation Hangs at 0%

**Cause:** CUDA kernel compilation (torch.compile)

**Solution:** Wait 2-3 minutes. First run compiles kernels which are cached for subsequent runs.

### Out of Memory

**Cause:** Should not happen with 14B on H200 (65GB << 140GB)

**If it occurs:**
```bash
# Disable CUDA graphs
python examples/inference.py ... 
# Remove any --use_cuda_graphs flag if present
```

---

## Quality Scoring with Cosmos-Reason1

```bash
cd /home/ubuntu/cosmos-reason1
source .venv/bin/activate

# Score a video (1-5 scale for physical plausibility)
python -m cosmos_reason1.inference.video_reward \
  --video_path /path/to/video.mp4 \
  --output_json quality_score.json
```

---

## Batch Generation Strategy

### Recommended Approach

1. **Keep model loaded** - Process videos in batches to avoid reload time
2. **Use JSONL batch input** - Multiple prompts in one file
3. **Parallel processes** - Run 14B + 2B simultaneously (85GB total)

### Batch Input Format

Create `batch.jsonl`:
```json
{"inference_type": "text2world", "name": "P01", "prompt": "Security camera footage..."}
{"inference_type": "text2world", "name": "P02", "prompt": "Security camera footage..."}
```

---

## Hardware Considerations

### Current: H200 (140GB VRAM)

| Metric | Value |
|--------|-------|
| Peak usage | 65 GB (45%) |
| Free during generation | 75 GB |
| Parallel capacity | 1× 14B + 1× 2B safely |

### Upgrade Options

| GPU | Expected Speedup | Notes |
|-----|------------------|-------|
| 2× H200 | 2× | Run two 14B instances |
| B200 (Blackwell) | ~2.5× | Higher memory bandwidth |
| GB200 NVL | ~4× | Rack-scale parallelism |

---

## Files Reference

### Key Paths

| File | Path |
|------|------|
| Cosmos environment | `/home/ubuntu/cosmos-predict2.5/.venv/bin/activate` |
| 14B model | `/home/ubuntu/cosmos-predict2.5/checkpoints/Cosmos-Predict2.5-14B` |
| Inference script | `/home/ubuntu/cosmos-predict2.5/examples/inference.py` |
| Video manifest | `/home/ubuntu/nemotron-v3-home-security-intelligence/data/synthetic/cosmos/generation_manifest.yaml` |
| Test output | `/home/ubuntu/cosmos-predict2.5/outputs/test/snowy_stop_light.mp4` |

### Environment Activation

```bash
cd /home/ubuntu/cosmos-predict2.5
source .venv/bin/activate
```

---

## Generation Manifest Quick Reference

### Presentation Videos (48)

| Category | IDs | Duration | Environment |
|----------|-----|----------|-------------|
| Threat Escalation | P01-P12 | 15-20s | Night |
| Cross-Camera | P13-P24 | 15-20s | Dusk |
| Household Recognition | P25-P36 | 15-18s | Day |
| Vehicle + Person | P37-P48 | 15-20s | Day |

### Training Videos (40)

| Category | IDs | Duration | Purpose |
|----------|-----|----------|---------|
| Threat Patterns | T01-T10 | 30s | Weapons, aggressive poses |
| Tracking Sequences | T11-T18 | 30s | ReID testing |
| Enrichment Stress | T19-T30 | 30s | Model Zoo exercise |
| Edge Cases | T31-T40 | 30s | Adverse conditions |

---

## Next Steps for Generation

1. **Review manifest**: `cat /home/ubuntu/nemotron-v3-home-security-intelligence/data/synthetic/cosmos/generation_manifest.yaml`

2. **Create prompt files**: Generate prompts from manifest templates

3. **Start with presentation videos**: They're shorter and needed first

4. **Track progress**: Update `generation_status.json` after each video

5. **Quality check**: Score videos with Cosmos-Reason1

---

## Verified By

- **Date:** 2026-01-27
- **Test:** snowy_stop_light.json → snowy_stop_light.mp4
- **Result:** ✅ Success (598 KB, 5.81s, 1280×704)
- **GPU:** NVIDIA H200, 65GB peak usage
- **Time:** 14:58 generation time

---

Good luck with generation!
