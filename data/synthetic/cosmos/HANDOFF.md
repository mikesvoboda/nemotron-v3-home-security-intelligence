# Cosmos Video Generation Handoff

## Overview

You are generating **501 synthetic security camera videos** (167 prompts × 3 durations) using NVIDIA Cosmos models. This document contains everything you need, **updated 2026-01-27**.

---

## Quick Status

| Item | Status | Notes |
|------|--------|-------|
| Environment | ✅ Bootstrapped | Docker container `cosmos-b300` |
| Cosmos-Predict2.5-14B | ✅ Downloaded | 54GB in `checkpoints/` |
| Cosmos-Reason1-7B | ✅ Downloaded | 16GB in cosmos-reason1 |
| Test Generation | ✅ Verified | NVRTC JIT tests pass on B300 |
| HuggingFace Auth | ✅ Configured | Token saved to cache |
| Prompt Files | ✅ Generated | **501 JSON files** (167 × 3 durations) |
| Batch Scripts | ✅ Ready | `batch_generate.sh`, `monitor.sh` |
| 8-GPU Parallel | ✅ Verified | All GPUs 100% utilization |
| Guardrails | ✅ Disabled | Required for security training data |
| Prompt Format | ✅ Fixed | Perspective-centric (no camera in frame) |

---

## Supported Hardware

| GPU | Architecture | Compute Capability | Setup Method |
|-----|--------------|-------------------|--------------|
| **NVIDIA B300** | Blackwell | sm_103 (10.3) | **Docker (Required)** |
| **NVIDIA B200/B100** | Blackwell | sm_100 (10.0) | Docker (Recommended) |
| **NVIDIA H200/H100** | Hopper | sm_90 (9.0) | Native uv or Docker |

**IMPORTANT:** B300 GPUs require the Docker container due to PyTorch NVRTC JIT compilation issues with sm_103 architecture. The NGC PyTorch 25.10 container includes proper Blackwell support.

---

## B300 Blackwell Setup (Docker - Required)

### System Specifications (B300)

| Component | Specification | Verified |
|-----------|---------------|----------|
| **GPU** | 8× NVIDIA B300 SXM6 AC | ✅ 267 GB VRAM each |
| **CUDA** | 12.8.93 | ✅ |
| **Compute Capability** | 10.3 (sm_103) | ✅ |
| **Container** | NGC PyTorch 25.10 | ✅ |
| **PyTorch** | 2.9.0a0+nv25.10 | ✅ |
| **flash-attn** | 2.7.4.post1 | ✅ |
| **OS** | Ubuntu 24.04 | ✅ |

### Step 1: Clone Repository and Download Models

```bash
cd /home/shadeform
git clone https://github.com/nvidia-cosmos/cosmos-predict2.5.git
cd cosmos-predict2.5

# Install git-lfs
sudo apt-get install -y git-lfs
git lfs install
git lfs pull

# Authenticate with HuggingFace
huggingface-cli login --token YOUR_HF_TOKEN

# Download models
mkdir -p checkpoints
huggingface-cli download nvidia/Cosmos-Predict2.5-14B \
  --local-dir checkpoints/Cosmos-Predict2.5-14B
```

### Step 2: Build the Docker Container

```bash
cd /home/shadeform/cosmos-predict2.5

# Build the Blackwell-compatible container
docker build -f docker/nightly.Dockerfile -t cosmos-b300 .
```

This builds a container based on `nvcr.io/nvidia/pytorch:25.10-py3` with:
- Full Blackwell sm_103 NVRTC support
- flash-attn 2.7.4 pre-built
- transformer-engine pre-built
- All Cosmos dependencies

### Step 3: Run Inference

```bash
docker run --rm --gpus all \
  --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 \
  -v /home/shadeform/cosmos-predict2.5:/workspace/cosmos \
  -v /home/shadeform/.cache/huggingface:/root/.cache/huggingface \
  --entrypoint python \
  cosmos-b300 \
  /workspace/cosmos/examples/inference.py \
  -i /workspace/cosmos/assets/base/snowy_stop_light.json \
  -o /workspace/cosmos/outputs/test \
  --inference-type=text2world \
  --model=14B/post-trained
```

### Step 4: Verify Installation

```bash
docker run --rm --gpus all \
  --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 \
  --entrypoint python \
  cosmos-b300 \
  -c "
import torch
print(f'GPU: {torch.cuda.get_device_name(0)}')
print(f'PyTorch: {torch.__version__}')
x = torch.randn(100, device='cuda')
y = torch.erfinv(x)
print('NVRTC JIT test: PASSED')
import flash_attn
print(f'flash-attn: {flash_attn.__version__}')
"
```

Expected output:
```
GPU: NVIDIA B300 SXM6 AC
PyTorch: 2.9.0a0+145a3a7bda.nv25.10
NVRTC JIT test: PASSED
flash-attn: 2.7.4.post1
```

---

## H200/Hopper Setup (Native - Alternative)

For H200 and older GPUs, you can use the native uv installation method.

### Verified System Specifications (H200)

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

### Total Videos: 501 (167 prompts × 3 durations)

| Category | Prompts | × Durations | Total Videos |
|----------|---------|-------------|--------------|
| **Presentation (P)** | 48 | × 3 | 144 |
| **Training (T)** | 40 | × 3 | 120 |
| **False Positives (F)** | 16 | × 3 | 48 |
| **Real Threats (R)** | 18 | × 3 | 54 |
| **Everyday Recognition (E)** | 22 | × 3 | 66 |
| **Challenging Conditions (C)** | 23 | × 3 | 69 |
| **TOTAL** | **167** | × 3 | **501** |

### Duration Variants (Each Prompt)

| Duration | Frames @ 24fps | Use Case |
|----------|----------------|----------|
| **5 seconds** | 120 frames | Quick demos, thumbnails |
| **10 seconds** | 240 frames | Standard training clips |
| **30 seconds** | 720 frames | Extended scenarios |

### Video Category Details

| Prefix | Category | Description |
|--------|----------|-------------|
| P | Presentation | Threat escalation, cross-camera tracking, household recognition, vehicle+person |
| T | Training | Threat patterns, tracking sequences, enrichment stress, edge cases |
| F | False Positives | Wildlife, wind effects, shadows/reflections, passing pedestrians |
| R | Real Threats | Package theft, vehicle crime, vandalism, casing, break-ins, trespassing |
| E | Everyday Recognition | Deliveries, home services, utilities, solicitors, visitors |
| C | Challenging Conditions | Weather, lighting, occlusion, speed, clothing variations |

### Estimated Generation Time (8× B300 GPUs)

| Duration | Count | Time Each | Total Time (8 GPUs) |
|----------|-------|-----------|---------------------|
| 5s videos | 167 | ~17 min | ~6 hours |
| 10s videos | 167 | ~25 min | ~9 hours |
| 30s videos | 167 | ~60 min | ~21 hours |
| **TOTAL** | **501** | - | **~18-24 hours** |

**Note:** Generation is sorted so ALL 5s videos complete first, then 10s, then 30s. This allows quality checking the 5s videos while longer ones continue generating.

---

## Working Inference Commands

### B300 Docker Commands

#### Text2World (Presentation Videos)

```bash
docker run --rm --gpus all \
  --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 \
  -v /home/shadeform/cosmos-predict2.5:/workspace/cosmos \
  -v /home/shadeform/.cache/huggingface:/root/.cache/huggingface \
  --entrypoint python \
  cosmos-b300 \
  /workspace/cosmos/examples/inference.py \
  -i /workspace/cosmos/assets/base/snowy_stop_light.json \
  -o /workspace/cosmos/outputs/presentation \
  --inference-type=text2world \
  --model=14B/post-trained \
  --disable-guardrails
```

#### Custom Prompt Generation

Create a JSON file like `my_video.json`:

```json
{
  "name": "my_custom_video",
  "inference_type": "text2world",
  "prompt": "Suburban home front porch at night, viewed from an elevated vantage point near the door. A person in dark hoodie approaches...",
  "negative_prompt": "visible camera, security camera device, doorbell camera, camera lens visible, camera equipment, camera housing, surveillance camera in frame, slow motion, time lapse",
  "guidance": 7,
  "seed": 0,
  "num_output_frames": 120
}
```

**CRITICAL:** Use perspective-centric language ("viewed from elevated vantage point") NOT device-centric language ("security camera footage from doorbell camera"). The latter causes Cosmos to render camera equipment IN the frame.

Then run:

```bash
docker run --rm --gpus all \
  --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 \
  -v /home/shadeform/cosmos-predict2.5:/workspace/cosmos \
  -v /home/shadeform/.cache/huggingface:/root/.cache/huggingface \
  --entrypoint python \
  cosmos-b300 \
  /workspace/cosmos/examples/inference.py \
  -i /workspace/cosmos/my_video.json \
  -o /workspace/cosmos/outputs/custom \
  --inference-type=text2world \
  --model=14B/post-trained
```

#### Interactive Shell (for debugging)

```bash
docker run --rm --gpus all -it \
  --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 \
  -v /home/shadeform/cosmos-predict2.5:/workspace/cosmos \
  -v /home/shadeform/.cache/huggingface:/root/.cache/huggingface \
  --entrypoint bash \
  cosmos-b300
```

---

### H200 Native Commands

#### Text2World (Presentation Videos)

```bash
cd /home/ubuntu/cosmos-predict2.5
source .venv/bin/activate

python examples/inference.py \
  -i assets/base/snowy_stop_light.json \
  -o outputs/presentation \
  --inference-type=text2world \
  --model=14B/post-trained
```

#### Custom Prompt Generation

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

---

### Extended Duration (30s Training Videos)

For videos longer than 5s, use autoregressive mode:

```bash
# Docker (B300)
docker run --rm --gpus all \
  --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 \
  -v /home/shadeform/cosmos-predict2.5:/workspace/cosmos \
  -v /home/shadeform/.cache/huggingface:/root/.cache/huggingface \
  --entrypoint python \
  cosmos-b300 \
  /workspace/cosmos/examples/inference.py \
  -i /workspace/cosmos/assets/base/bus_terminal_long.json \
  -o /workspace/cosmos/outputs/long_video \
  --model=14B/post-trained

# Native (H200)
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

### B300 Setup (Docker)

```
/home/shadeform/
├── cosmos-predict2.5/                    # Main Cosmos installation
│   ├── docker/
│   │   └── nightly.Dockerfile            # Blackwell-compatible Dockerfile
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
│   └── checkpoints/
│       └── Cosmos-Reason1-7B/            # 16GB model
│
├── .cache/huggingface/                   # HuggingFace model cache
│
└── nemotron-v3-home-security-intelligence/
    └── data/synthetic/cosmos/
        ├── HANDOFF.md                    # This file
        ├── generation_manifest.yaml      # All 167 video definitions
        ├── generation_status.json        # Progress tracking
        ├── batch_generate.sh             # 8-GPU parallel generation
        ├── generate_prompts.py           # Prompt file generator (3 durations)
        ├── monitor.sh                    # Progress monitoring + auto git sync
        ├── logs/                         # Per-GPU generation logs
        │   └── gpu[0-7].log
        ├── videos/                       # Generated videos (synced to git)
        ├── videos_deprecated/            # Old videos with camera-in-frame issues
        └── prompts/
            ├── templates/                # Jinja2 templates
            │   ├── base_prompt.jinja2    # Perspective-centric prompt template
            │   ├── scenes/               # Scene definitions
            │   ├── environments/         # Lighting/weather
            │   ├── subjects/             # Person/vehicle descriptions
            │   └── actions/              # Action sequences
            └── generated/                # 501 JSON prompt files
                ├── C01_5s.json ... C23_30s.json   # Challenging Conditions
                ├── E01_5s.json ... E22_30s.json   # Everyday Recognition
                ├── F01_5s.json ... F16_30s.json   # False Positives
                ├── P01_5s.json ... P48_30s.json   # Presentation
                ├── R01_5s.json ... R18_30s.json   # Real Threats
                ├── T01_5s.json ... T40_30s.json   # Training
                └── generation_queue.json          # Full manifest
```

### H200 Setup (Native)

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

### "nvrtc: error: invalid value for --gpu-architecture (-arch)" (B300/Blackwell)

**Cause:** PyTorch's NVRTC JIT compilation doesn't recognize sm_103 (B300) architecture in native installations.

**Solution:** Use the Docker container approach. The NGC PyTorch 25.10+ containers include proper Blackwell NVRTC support.

```bash
# Build and use the cosmos-b300 container
docker build -f docker/nightly.Dockerfile -t cosmos-b300 .

# Run inference in container
docker run --rm --gpus all \
  --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 \
  -v $(pwd):/workspace/cosmos \
  --entrypoint python \
  cosmos-b300 \
  /workspace/cosmos/examples/inference.py ...
```

**Key insight:** B300 = sm_103, which is different from B100/B200 (sm_100). Many "Blackwell" builds only target sm_100.

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

**Cause:** Should not happen with 14B on H200 (65GB << 140GB) or B300 (267GB)

**If it occurs:**
```bash
# Disable CUDA graphs
python examples/inference.py ... 
# Remove any --use_cuda_graphs flag if present
```

### flash-attn or transformer-engine ImportError (Native Install)

**Cause:** Binary incompatibility with PyTorch version after upgrade

**Solution:** Either rebuild from source (slow) or use Docker container (recommended):

```bash
# Option 1: Rebuild flash-attn for your architecture (takes ~70 minutes)
FLASH_ATTN_CUDA_ARCHS="100" uv pip install --upgrade flash-attn --no-build-isolation

# Option 2: Use Docker container (recommended)
docker build -f docker/nightly.Dockerfile -t cosmos-b300 .
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

### Presentation Videos (P01-P48)

| Category | IDs | Description |
|----------|-----|-------------|
| Threat Escalation | P01-P12 | Progressive suspicious behavior at night |
| Cross-Camera Tracking | P13-P24 | Zone movement at dusk |
| Household Recognition | P25-P36 | Known vs unknown during day |
| Vehicle + Person | P37-P48 | Vehicle arrivals/exits |

### Training Videos (T01-T40)

| Category | IDs | Purpose |
|----------|-----|---------|
| Threat Patterns | T01-T10 | Weapons, aggressive poses |
| Tracking Sequences | T11-T18 | ReID testing |
| Enrichment Stress | T19-T30 | Face/clothing/pet detection |
| Edge Cases | T31-T40 | Weather/lighting challenges |

### False Positive Training (F01-F16)

| Category | IDs | Description |
|----------|-----|-------------|
| Wildlife | F01-F05 | Deer, raccoon, coyote, cat, birds |
| Wind Effects | F06-F08 | Trash, branches, flags |
| Shadows/Reflections | F09-F11 | Headlights, clouds, glare |
| Passing Pedestrians | F12-F14 | Joggers, dog walkers |
| Innocent Intrusions | F15-F16 | Wrong delivery, ball retrieval |

### Real Threats (R01-R18)

| Category | IDs | Description |
|----------|-----|-------------|
| Package Theft | R01-R03 | Quick grab, casual, follow delivery |
| Vehicle Crime | R04-R07 | Car break-in, theft, catalytic converter |
| Vandalism | R08-R10 | Graffiti, mailbox, egging |
| Casing | R11-R12 | Photography, note-taking |
| Break-ins | R13-R16 | Home invasion, garage, shed |
| Trespassing | R17-R18 | Shortcut, camping |

### Everyday Recognition (E01-E22)

| Category | IDs | Description |
|----------|-----|-------------|
| Deliveries | E01-E07 | Amazon, UPS, FedEx, USPS, food, grocery, drone |
| Home Services | E08-E11 | Landscaper, pool, cleaner, pest control |
| Utilities | E12-E14 | Meter reader, electric, gas |
| Solicitors | E15-E17 | Sales, religious, political |
| Visitors | E18-E22 | Guests, rideshare, contractor, realtor, neighbor |

### Challenging Conditions (C01-C23)

| Category | IDs | Description |
|----------|-----|-------------|
| Weather | C01-C05 | Rain, snow, fog, hail, wind |
| Lighting | C06-C10 | Glare, headlights, flashlight, lightning, sunrise |
| Occlusion | C11-C14 | Umbrella, package, crowd, stroller |
| Speed | C15-C16 | Sprint, fast cyclist |
| Clothing | C17-C20 | Rain gear, winter, costume, helmet |
| Other | C21-C23 | Distance, angle, multi-event |

---

## Next Steps for Generation (Quick Start)

```bash
cd /home/shadeform/nemotron-v3-home-security-intelligence/data/synthetic/cosmos

# 1. Activate environment and regenerate prompts (if needed)
source .venv/bin/activate
python generate_prompts.py

# 2. Start generation (runs in background)
./batch_generate.sh

# 3. Monitor progress (auto-syncs videos to git)
./monitor.sh 60
```

### Quality Check Workflow

1. **First 5s videos complete in ~6 hours** - Check for camera-in-frame issues
2. **Use ffmpeg to extract frames**: `ffmpeg -ss 2 -i video.mp4 -vframes 1 frame.jpg`
3. **Verify**: No camera equipment visible, elevated perspective, real-time motion
4. **If issues found**: Stop generation, fix prompts, restart

---

## Batch Generation with 8 GPUs (Verified Working)

### Optimal Approach: Persistent Containers

The most efficient approach for generating 501 videos is to run **8 persistent Docker containers** (one per GPU), each processing ~63 videos sequentially. This loads the model once per GPU and processes all assigned videos.

**Why not other approaches?**
- **Single GPU serial**: 100+ hours (too slow)
- **New container per video**: Model reload (~4 min) for each video (wasteful)
- **Context parallelism for single video**: Faster per-video but lower total throughput

### Generation Scripts

| Script | Purpose |
|--------|---------|
| `batch_generate.sh` | Main parallel generation script (sorted by duration) |
| `generate_prompts.py` | Renders 501 prompts (167 × 3 durations) from manifest |
| `monitor.sh` | Real-time progress monitoring + auto git sync |
| `parallel_generate.py` | Alternative Python-based approach |

### Running Batch Generation

```bash
cd /home/shadeform/nemotron-v3-home-security-intelligence/data/synthetic/cosmos

# Generate all prompt JSON files first (501 files)
source .venv/bin/activate
python generate_prompts.py

# Start parallel generation on 8 GPUs
./batch_generate.sh

# Monitor progress with auto-sync to git (in separate terminal)
./monitor.sh 60     # Refresh every 60s, auto-commits new videos
```

### Generation Order (Quality Check Strategy)

Prompts are sorted so **ALL 5s videos generate first**, then 10s, then 30s:

```
C01_5s.json, C02_5s.json, ... T40_5s.json    # First ~6 hours
C01_10s.json, C02_10s.json, ... T40_10s.json # Next ~9 hours
C01_30s.json, C02_30s.json, ... T40_30s.json # Final ~9 hours
```

This allows you to quality check the 5s videos while longer videos continue generating.

### Output Locations

```
# Raw generation output (Docker container writes here)
/home/shadeform/cosmos-predict2.5/outputs/security_videos/*.mp4

# Git-synced location (monitor.sh auto-copies here)
/home/shadeform/nemotron-v3-home-security-intelligence/data/synthetic/cosmos/videos/*.mp4
```

Both paths persist on the host filesystem (not inside containers).

---

## Critical: Camera-in-Frame Issue (FIXED)

### The Problem

Early video generations showed **camera equipment visible IN the frame** (~60% of videos). This happened because prompts used device-centric language like:
- "Security camera footage from elevated doorbell camera"
- "Camera mounted on garage"

Cosmos interpreted these as instructions to SHOW a camera rather than simulate the camera's POV.

### The Solution

1. **Use perspective-centric language** in prompts:
   - ❌ BAD: `Security camera footage from elevated doorbell camera`
   - ✅ GOOD: `Suburban home front porch, viewed from an elevated vantage point near the front door`

2. **Include camera exclusions in negative_prompt:**
   ```
   visible camera, security camera device, doorbell camera, camera lens visible,
   camera equipment, camera housing, surveillance camera in frame, camera mount,
   camera on wall, camera on ceiling, CCTV camera visible, Ring doorbell visible
   ```

3. **Add real-time speed specification:**
   ```
   Real-time speed, natural fluid motion at 1x playback rate.
   ```

The `generate_prompts.py` script and `base_prompt.jinja2` template implement these fixes.

---

## Critical: Guardrails and Security Training Data

### The Problem

Cosmos includes content safety guardrails (BLOCKLIST, QWEN3GUARD) that **will block** prompts containing:
- Weapon descriptions (handgun, knife, bat)
- Violence (kicking door, breaking window)
- Threatening behavior
- Concealed faces (ski masks)

**Our training videos (T01-T10, R01-R18) explicitly require these scenarios for threat detection training.**

### The Solution

Use `--disable-guardrails` flag:

```bash
python examples/inference.py \
  -i prompts.json \
  -o outputs/ \
  --inference-type=text2world \
  --model=14B/post-trained \
  --disable-guardrails  # Required for security training data
```

The `batch_generate.sh` script includes this flag by default.

### Videos Requiring Disabled Guardrails

| Video ID | Content | Why Blocked |
|----------|---------|-------------|
| T01 | Visible handgun | Weapon |
| T02 | Large knife | Weapon |
| T03 | Baseball bat as weapon | Weapon |
| T05 | Kicking door | Violence |
| T06 | Breaking window | Violence |
| T07 | Pry bar forced entry | Break-in tool |
| T08 | Ski mask and gloves | Face concealment |
| T09 | Multiple intruders | Coordinated threat |

---

## Important: tyro Argument Syntax

### Correct Way to Pass Multiple Input Files

Cosmos uses `tyro` for argument parsing. For list arguments, use **space-separated values after a single flag**:

```bash
# ✅ CORRECT - All files after single -i
python inference.py -i file1.json file2.json file3.json -o output/

# ❌ WRONG - Repeated flags (only last file processed)
python inference.py -i file1.json -i file2.json -i file3.json -o output/
```

This is critical for batch processing multiple videos in a single container.

---

## B300 8-GPU Generation Performance (Verified)

### Actual Metrics from Production Run

| Metric | Value |
|--------|-------|
| **GPUs Used** | 8× NVIDIA B300 |
| **VRAM per GPU** | ~65 GB |
| **GPU Utilization** | 100% during diffusion |
| **Time per Step** | ~29 seconds |
| **Steps per Video** | 35 |

### Time per Video by Duration

| Duration | Frames | Approx Time |
|----------|--------|-------------|
| **5 seconds** | 120 | ~17 minutes |
| **10 seconds** | 240 | ~25 minutes |
| **30 seconds** | 720 | ~60 minutes |

### Total Generation Time (501 Videos)

| Duration | Count | Time per GPU | Total (8 GPUs) |
|----------|-------|--------------|----------------|
| 5s videos | 167 | ~7 hours | ~6 hours |
| 10s videos | 167 | ~10 hours | ~9 hours |
| 30s videos | 167 | ~21 hours | ~9 hours |
| **TOTAL** | **501** | - | **~18-24 hours** |

### Parallelization Efficiency

| Configuration | Total Time | Speedup |
|---------------|------------|---------|
| 1 GPU (serial) | ~150 hours | 1× |
| 8 GPUs (parallel) | ~18-24 hours | ~7-8× |

---

## Verified By

### B300 Blackwell (Docker)

- **Date:** 2026-01-27
- **Container:** `cosmos-b300` (built from `nightly.Dockerfile`)
- **Base Image:** `nvcr.io/nvidia/pytorch:25.10-py3`
- **GPU:** 8× NVIDIA B300 SXM6 AC (267GB VRAM each)
- **PyTorch:** 2.9.0a0+nv25.10
- **flash-attn:** 2.7.4.post1
- **NVRTC JIT Test:** ✅ PASSED (erfinv kernel compiles for sm_103)
- **Cosmos Import:** ✅ PASSED

### H200 Hopper (Native)

- **Date:** 2026-01-27
- **Test:** snowy_stop_light.json → snowy_stop_light.mp4
- **Result:** ✅ Success (598 KB, 5.81s, 1280×704)
- **GPU:** NVIDIA H200, 65GB peak usage
- **Time:** 14:58 generation time

---

## Quick Reference: Docker Run Command

```bash
# Standard inference command for B300
docker run --rm --gpus all \
  --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 \
  -v /home/shadeform/cosmos-predict2.5:/workspace/cosmos \
  -v /home/shadeform/.cache/huggingface:/root/.cache/huggingface \
  --entrypoint python \
  cosmos-b300 \
  /workspace/cosmos/examples/inference.py \
  -i /workspace/cosmos/INPUT_FILE.json \
  -o /workspace/cosmos/outputs/OUTPUT_DIR \
  --inference-type=text2world \
  --model=14B/post-trained
```

---

---

## Redeployment on New Node (Quick Reference)

If you need to redeploy on a fresh B300 or H200 node:

### 1. Clone Repositories

```bash
cd /home/shadeform  # or /home/ubuntu for H200
git clone https://github.com/nvidia-cosmos/cosmos-predict2.5.git
git clone https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence.git
cd nemotron-v3-home-security-intelligence
git checkout msvoboda/nemo3
```

### 2. Build Docker Container (B300)

```bash
cd /home/shadeform/cosmos-predict2.5
docker build -f docker/nightly.Dockerfile -t cosmos-b300 .
```

### 3. Setup Python Environment (for prompt generation)

```bash
cd /home/shadeform/nemotron-v3-home-security-intelligence/data/synthetic/cosmos
apt install -y python3-venv
python3 -m venv .venv
source .venv/bin/activate
pip install pyyaml jinja2
```

### 4. Authenticate HuggingFace

```bash
# Accept licenses at:
# - https://huggingface.co/nvidia/Cosmos-Predict2.5-14B
# - https://huggingface.co/nvidia/Cosmos-Predict2.5-2B
# - https://huggingface.co/nvidia/Cosmos-Guardrail1
# - https://huggingface.co/nvidia/Cosmos-Reason1-7B

huggingface-cli login --token YOUR_TOKEN
```

### 5. Generate Prompts and Start

```bash
cd /home/shadeform/nemotron-v3-home-security-intelligence/data/synthetic/cosmos
source .venv/bin/activate
python generate_prompts.py  # Creates 501 prompt files
./batch_generate.sh         # Starts 8-GPU generation
./monitor.sh 60             # Monitor + auto-sync to git
```

### Key Files to Verify

| File | Purpose | Check |
|------|---------|-------|
| `generation_manifest.yaml` | Video definitions | 167 videos defined |
| `prompts/templates/base_prompt.jinja2` | Prompt template | Perspective-centric language |
| `prompts/generated/*.json` | Cosmos inputs | 501 files, correct format |
| `batch_generate.sh` | Generation script | `--disable-guardrails` present |

---

Good luck with generation!
