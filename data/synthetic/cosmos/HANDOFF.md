# Cosmos Video Generation Handoff

## Overview

You are generating **88 synthetic security camera videos** using NVIDIA Cosmos models on an H200 instance. This document contains everything you need.

---

## Installation Guide

### System Requirements

| Requirement | Specification                         |
| ----------- | ------------------------------------- |
| **OS**      | Linux (Ubuntu 20.04, 22.04, or 24.04) |
| **Python**  | 3.10.x (required)                     |
| **GPU**     | H200 (or A100/H100 with 80GB+ VRAM)   |
| **CUDA**    | 12.x                                  |
| **Conda**   | Required for environment management   |

### Step 1: Clone Cosmos-Predict2.5 Repository

```bash
# Clone the latest Cosmos-Predict2.5 repository (Dec 2025)
git clone https://github.com/nvidia-cosmos/cosmos-predict2.5.git
cd cosmos-predict2.5
```

### Step 2: Create Environment with uv (Recommended)

Cosmos-Predict2.5 uses `uv` for fast dependency management:

```bash
# Install uv if not present
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv sync

# Activate the environment
source .venv/bin/activate
```

**Alternative: Conda Setup**

```bash
# Create conda environment
conda create -n cosmos-predict2.5 python=3.10
conda activate cosmos-predict2.5

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Install CUDA Dependencies

```bash
# Install Transformer Engine for H200 optimization
pip install transformer-engine[pytorch]

# Install NATTEN for sparse attention (2.5x speedup on Hopper/Blackwell)
pip install natten
```

### Step 4: Authenticate with Hugging Face

```bash
# Install huggingface CLI if not present
pip install huggingface_hub

# Login to Hugging Face (requires account with accepted model license)
huggingface-cli login
# Enter your HF token when prompted (needs 'Read' permission)
```

### Step 5: Download Cosmos-Predict2.5-14B Model

**We use the 14B model exclusively for maximum quality on H200.**

```bash
# Create checkpoints directory
mkdir -p checkpoints

# Download Cosmos-Predict2.5-14B (unified Text/Image/Video2World)
# This is the largest and highest quality model available
huggingface-cli download nvidia/Cosmos-Predict2.5-14B \
  --local-dir checkpoints/Cosmos-Predict2.5-14B
```

**Alternative: Using Python**

```python
from huggingface_hub import snapshot_download

# Download 14B model (largest available)
snapshot_download(
    repo_id="nvidia/Cosmos-Predict2.5-14B",
    local_dir="checkpoints/Cosmos-Predict2.5-14B"
)
```

### Step 6: Install Cosmos-Reason1 (Quality Scoring)

Cosmos-Reason1 scores generated videos for physical plausibility (1-5 scale):

```bash
# Clone Cosmos-Reason1 repository
git clone https://github.com/nvidia-cosmos/cosmos-reason1.git
cd cosmos-reason1
uv sync
cd ..

# Download Cosmos-Reason1-7B model
huggingface-cli download nvidia/Cosmos-Reason1-7B \
  --local-dir checkpoints/Cosmos-Reason1-7B
```

### Step 7: Verify Installation

```bash
# Verify GPU access (should show H200)
nvidia-smi

# Test environment
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
python -c "import torch; print(f'GPU: {torch.cuda.get_device_name(0)}')"

# Test a simple inference
python -m cosmos_predict2_5.inference.text2world \
    --model_path checkpoints/Cosmos-Predict2.5-14B \
    --prompt "A simple test scene with a person walking on a suburban sidewalk" \
    --output_path test_output.mp4 \
    --resolution 720 \
    --fps 16 \
    --natten
```

### Model Storage & VRAM Requirements

| Model                     | Disk Size | VRAM Required | Notes                           |
| ------------------------- | --------- | ------------- | ------------------------------- |
| **Cosmos-Predict2.5-14B** | ~30 GB    | ~50 GB        | Largest & highest quality model |

**H200 (141 GB VRAM)** provides exceptional headroom for the 14B model:

- **91 GB free** after model load for batch processing
- NATTEN sparse attention enabled (2.5x speedup on Hopper architecture)
- CUDA graphs acceleration for faster inference
- Room for parallel video generation if needed

### Docker Alternative

```bash
# Build Docker image
docker build -f Dockerfile . -t cosmos-predict2.5:latest

# Run container with GPU access
docker run --gpus all -it --rm \
  -v $(pwd):/workspace \
  -v /path/to/checkpoints:/checkpoints \
  cosmos-predict2.5:latest /bin/bash
```

---

## Quick Start

```bash
# 1. Verify Cosmos installation
python -c "import cosmos; print(cosmos.__version__)"

# 2. Verify GPU
nvidia-smi  # Should show H200

# 3. Navigate to working directory
cd /path/to/project/data/synthetic/cosmos

# 4. Read the manifest
cat generation_manifest.yaml

# 5. Generate first video (test)
python scripts/cosmos_prompt_generator.py --id P01 --preview  # Preview prompt
python scripts/cosmos_prompt_generator.py --id P01            # Generate prompt file

# 6. Run Cosmos inference
python -m cosmos.predict1.diffusion.inference \
    --checkpoint_dir /models/cosmos-diffusion-14b \
    --prompt "$(cat cosmos_prompts/P01.txt)" \
    --output_path presentation/threat_escalation/P01_delivery_baseline.mp4
```

---

## Directory Structure

```
data/synthetic/cosmos/
├── HANDOFF.md                    # This file
├── generation_manifest.yaml      # Master list of 88 videos
├── generation_status.json        # Track progress (you update this)
│
├── prompts/
│   └── templates/
│       ├── base_prompt.jinja2    # Master template
│       ├── scenes/*.yaml         # Scene components
│       ├── subjects/*.yaml       # Subject components
│       ├── environments/*.yaml   # Environment components
│       └── actions/*.yaml        # Action sequences
│
├── presentation/                 # Output: 48 Diffusion videos
│   ├── threat_escalation/
│   ├── cross_camera/
│   ├── household_recognition/
│   └── vehicle_person/
│
└── training/                     # Output: 40 Autoregressive videos
    ├── threat_patterns/
    ├── tracking_sequences/
    ├── enrichment_stress/
    └── edge_cases/
```

---

## Generation Manifest Format

`generation_manifest.yaml` defines every video. Key fields:

```yaml
videos:
  - id: 'P01'
    category: 'presentation'
    scenario: 'threat_escalation'
    variation: 'delivery_baseline'
    model: 'cosmos-diffusion-14b'
    duration_seconds: 15
    environment: 'night_clear'
    scene: 'front_porch'
    subject: 'person_normal'
    action: 'deliver_package'
    output_path: 'presentation/threat_escalation/P01_delivery_baseline.mp4'
```

---

## How to Generate Prompts

### Option A: Use the Generator Script

```bash
# Generate prompt for single video
python scripts/cosmos_prompt_generator.py --id P01

# Generate all prompts (writes to cosmos_prompts/)
python scripts/cosmos_prompt_generator.py --all

# Preview without writing
python scripts/cosmos_prompt_generator.py --id P01 --preview
```

### Option B: Manual Template Rendering

```python
from jinja2 import Environment, FileSystemLoader
import yaml

env = Environment(loader=FileSystemLoader('prompts/templates'))
template = env.get_template('base_prompt.jinja2')

# Load components
scene = yaml.safe_load(open('prompts/templates/scenes/front_porch.yaml'))
environment = yaml.safe_load(open('prompts/templates/environments/night_clear.yaml'))
subject = yaml.safe_load(open('prompts/templates/subjects/person_suspicious.yaml'))
action = yaml.safe_load(open('prompts/templates/actions/test_handle.yaml'))

prompt = template.render(
    scene=scene,
    environment=environment,
    subject=subject,
    action=action,
    generation={'duration_seconds': 15}
)
print(prompt)
```

---

## Cosmos Model Commands

**We use Cosmos-Predict2.5-14B for all generation** - the latest and highest quality model, optimized for H200.

### Presentation Videos (48 total) - Text2World

```bash
# Maximum quality settings for presentation videos
python -m cosmos_predict2_5.inference.text2world \
    --model_path checkpoints/Cosmos-Predict2.5-14B \
    --prompt "$(cat cosmos_prompts/P01.txt)" \
    --output_path presentation/threat_escalation/P01_delivery_baseline.mp4 \
    --resolution 720 \
    --fps 16 \
    --guidance 7.0 \
    --negative_prompt "blurry, low quality, artifacts, glitches, distorted, unrealistic motion, multiple camera angles" \
    --aspect_ratio 16:9 \
    --seed 42 \
    --natten \
    --use_cuda_graphs
```

**Output specs:**

- Resolution: 1280×704 (720P)
- Frame rate: 16 FPS
- Duration: 5 seconds per generation
- Format: MP4

### Training Videos (40 total) - Extended Duration with Sliding Window

For 30-second training videos, use autoregressive sliding window mode:

```bash
# Generate 30s video using sliding window (6 × 5s clips)
python -m cosmos_predict2_5.inference.video2world \
    --model_path checkpoints/Cosmos-Predict2.5-14B \
    --prompt "$(cat cosmos_prompts/T01.txt)" \
    --output_path training/threat_patterns/T01_weapon_handgun.mp4 \
    --resolution 720 \
    --fps 16 \
    --guidance 7.0 \
    --negative_prompt "blurry, low quality, artifacts, camera shake, jump cuts" \
    --num_iterations 6 \
    --autoregressive_mode sliding_window \
    --aspect_ratio 16:9 \
    --natten \
    --use_cuda_graphs
```

**Training video specs:**

- Resolution: 1280×704 (720P)
- Frame rate: 16 FPS
- Duration: 30 seconds (6 × 5s iterations)
- Format: MP4

### Quality Parameters Explained

| Parameter           | Value   | Purpose                                                         |
| ------------------- | ------- | --------------------------------------------------------------- |
| `--guidance 7.0`    | 7.0     | Classifier-free guidance scale (higher = more prompt adherence) |
| `--negative_prompt` | Text    | Elements to avoid in generation                                 |
| `--natten`          | Flag    | NATTEN sparse attention - **2.5x speedup on H200**              |
| `--use_cuda_graphs` | Flag    | CUDA acceleration for faster inference                          |
| `--seed`            | Integer | Reproducible generation                                         |

### Batch Generation

```bash
# Generate all presentation videos from JSONL
python -m cosmos_predict2_5.inference.text2world \
    --model_path checkpoints/Cosmos-Predict2.5-14B \
    --batch_input_json cosmos_prompts/presentation_batch.jsonl \
    --output_dir presentation/ \
    --resolution 720 \
    --fps 16 \
    --guidance 7.0 \
    --natten \
    --use_cuda_graphs
```

JSONL format:

```json
{"prompt": "Security camera footage...", "negative_prompt": "blurry...", "output_name": "P01_delivery_baseline", "seed": 42}
{"prompt": "Security camera footage...", "negative_prompt": "blurry...", "output_name": "P02_lingering_mild", "seed": 43}
```

---

## Progress Tracking

Update `generation_status.json` as you generate:

```json
{
  "started_at": "2026-01-27T10:00:00Z",
  "last_updated": "2026-01-27T12:30:00Z",
  "total": 88,
  "completed": 23,
  "failed": 1,
  "in_progress": "P24",
  "videos": {
    "P01": { "status": "completed", "duration_sec": 45, "file_size_mb": 12.3 },
    "P02": { "status": "completed", "duration_sec": 52, "file_size_mb": 14.1 },
    "P03": { "status": "failed", "error": "OOM - retry with offload" },
    "P04": { "status": "pending" }
  }
}
```

**Status values:** `pending`, `in_progress`, `completed`, `failed`

---

## Output Requirements

Each generated video must have:

1. **Video file**: `{id}_{variation}.mp4`
2. **Metadata file**: `{id}_{variation}_metadata.json`
3. **Thumbnail**: `{id}_{variation}_thumb.jpg` (first frame)

### Metadata Format

```json
{
  "id": "P01",
  "generated_at": "2026-01-27T10:15:32Z",
  "model": "cosmos-diffusion-14b",
  "prompt": "Security camera footage from elevated doorbell camera...",
  "parameters": {
    "guidance_scale": 7.5,
    "num_inference_steps": 50,
    "seed": 42,
    "fps": 24,
    "resolution": "1280x704"
  },
  "generation_time_seconds": 45,
  "file_size_bytes": 12903424
}
```

### Extract Thumbnail

```bash
ffmpeg -i P01_delivery_baseline.mp4 -vframes 1 -q:v 2 P01_delivery_baseline_thumb.jpg
```

---

## Prompt Engineering Rules

Follow these rules for all prompts:

1. **~120 words** - Not too short, not over 300
2. **Single scene only** - No shot changes
3. **No camera movement** - Always "fixed camera" or "static camera"
4. **Security camera aesthetic**:
   - "IR-tinted footage" for night
   - "Wide-angle lens distortion"
   - "Timestamp overlay"
   - "Slight grain" for realism
5. **Ground in physics** - Realistic motion, lighting, spatial relationships
6. **Specific over abstract** - "Porch light" not "ambient illumination"

### Example Good Prompt

> Security camera footage from elevated doorbell camera, suburban home front porch at night. Single porch light provides harsh overhead illumination with deep shadows. A person in dark hoodie with hood up approaches the front door from the driveway, walking with deliberate slow pace. They stop at the door, lean close to peer through the side window, then reach down to test the door handle. Their face remains obscured by the hood. Fixed camera position, wide-angle lens with slight barrel distortion, IR-tinted footage quality typical of home security systems. Realistic human motion, 15-second duration.

---

## Debugging & Quality Metrics

Capture comprehensive debugging outputs for each generated video to enable troubleshooting and quality filtering.

### Required Outputs Per Video

For each generated video, capture and save:

| Output        | File                             | Purpose                     |
| ------------- | -------------------------------- | --------------------------- |
| Video file    | `{id}_{variation}.mp4`           | The generated video         |
| Metadata      | `{id}_{variation}_metadata.json` | All generation parameters   |
| Thumbnail     | `{id}_{variation}_thumb.jpg`     | First frame preview         |
| Timing        | `{id}_{variation}_timing.json`   | Performance metrics         |
| Quality score | `{id}_{variation}_quality.json`  | Physical plausibility score |
| GPU log       | `{id}_{variation}_gpu.log`       | Resource utilization        |

### Enhanced Metadata Format

Save comprehensive metadata for reproducibility:

```json
{
  "id": "P01",
  "variation": "delivery_baseline",
  "generated_at": "2026-01-27T10:15:32Z",

  "model": {
    "name": "Cosmos-Predict2.5-14B",
    "checkpoint_path": "checkpoints/Cosmos-Predict2.5-14B",
    "version": "2.5"
  },

  "parameters": {
    "seed": 42,
    "guidance": 7.0,
    "resolution": 720,
    "fps": 16,
    "aspect_ratio": "16:9",
    "negative_prompt": "blurry, low quality, artifacts...",
    "natten_enabled": true,
    "cuda_graphs_enabled": true
  },

  "prompt": {
    "text": "Security camera footage from elevated doorbell camera...",
    "word_count": 97,
    "template_components": {
      "scene": "front_porch",
      "environment": "night_clear",
      "subject": "person_normal",
      "action": "deliver_package"
    }
  },

  "output": {
    "file_path": "presentation/threat_escalation/P01_delivery_baseline.mp4",
    "file_size_bytes": 12903424,
    "duration_seconds": 5.0,
    "resolution": "1280x704",
    "frame_count": 80
  },

  "performance": {
    "generation_time_seconds": 45.2,
    "gpu_peak_memory_gb": 48.3,
    "gpu_utilization_avg_percent": 95
  },

  "quality": {
    "physical_plausibility_score": 4,
    "cosmos_reason_version": "1.0",
    "reasoning_summary": "Good adherence to physical laws..."
  }
}
```

### Benchmark Mode for Timing

Always run with `--benchmark` to capture timing:

```bash
python -m cosmos_predict2_5.inference.text2world \
    --model_path checkpoints/Cosmos-Predict2.5-14B \
    --prompt "$(cat cosmos_prompts/P01.txt)" \
    --output_path output.mp4 \
    --benchmark \
    --natten \
    --use_cuda_graphs \
    2>&1 | tee timing_P01.log
```

### Physical Plausibility Scoring with Cosmos-Reason1

**Install Cosmos-Reason1:**

```bash
# Clone Cosmos-Reason1 repository
git clone https://github.com/nvidia-cosmos/cosmos-reason1.git
cd cosmos-reason1
uv sync
```

**Score generated videos (1-5 scale):**

| Score | Meaning                                          |
| ----- | ------------------------------------------------ |
| 1     | Completely implausible - no adherence to physics |
| 2     | Mostly unrealistic - poor physics                |
| 3     | Mixed - moderate physics adherence               |
| 4     | Mostly realistic - good physics                  |
| 5     | Completely plausible - perfect physics           |

```bash
# Score a single video
python -m cosmos_reason1.inference.video_reward \
    --video_path presentation/threat_escalation/P01_delivery_baseline.mp4 \
    --output_json P01_quality.json

# Batch score all videos in a directory
for video in presentation/**/*.mp4; do
    base=$(basename "$video" .mp4)
    python -m cosmos_reason1.inference.video_reward \
        --video_path "$video" \
        --output_json "quality_scores/${base}_quality.json"
done
```

**Quality score output format:**

```json
{
  "video_path": "presentation/threat_escalation/P01_delivery_baseline.mp4",
  "physical_plausibility_score": 4,
  "reasoning": {
    "object_behavior": "Person moves naturally with realistic gait",
    "motion_consistency": "Smooth motion without teleportation",
    "interaction_plausibility": "Door handle interaction looks realistic",
    "temporal_continuity": "No frame jumps or artifacts"
  },
  "scored_at": "2026-01-27T12:30:00Z"
}
```

### Best-of-N Generation (Quality Optimization)

Generate multiple variations and automatically select the best:

```bash
# Generate 3 variations, score each, keep best
python -m cosmos_predict2_5.inference.video2world_bestofn \
    --model_path checkpoints/Cosmos-Predict2.5-14B \
    --prompt "$(cat cosmos_prompts/P01.txt)" \
    --output_dir bestofn_P01/ \
    --num_generations 3 \
    --num_critic_trials 2 \
    --resolution 720 \
    --fps 16 \
    --natten
```

**Output structure:**

```
bestofn_P01/
├── generation_0.mp4     # First variation
├── generation_1.mp4     # Second variation
├── generation_2.mp4     # Third variation
├── scores.json          # Quality scores for each
└── best.mp4            # Symlink to highest scored
```

### GPU Monitoring

Capture GPU utilization during generation:

```bash
# Start GPU monitoring in background
nvidia-smi --query-gpu=timestamp,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw \
    --format=csv -l 1 > gpu_log_P01.csv &
GPU_MONITOR_PID=$!

# Run generation
python -m cosmos_predict2_5.inference.text2world \
    --model_path checkpoints/Cosmos-Predict2.5-14B \
    --prompt "$(cat cosmos_prompts/P01.txt)" \
    --output_path P01.mp4 \
    --natten

# Stop monitoring
kill $GPU_MONITOR_PID
```

### Automated Quality Pipeline

Run this after each video generation:

```bash
#!/bin/bash
# quality_check.sh - Run after each video generation

VIDEO_PATH=$1
BASE_NAME=$(basename "$VIDEO_PATH" .mp4)
OUTPUT_DIR="quality_reports"

mkdir -p "$OUTPUT_DIR"

# 1. Extract thumbnail
ffmpeg -i "$VIDEO_PATH" -vframes 1 -q:v 2 "${OUTPUT_DIR}/${BASE_NAME}_thumb.jpg"

# 2. Get video metadata
ffprobe -v quiet -print_format json -show_format -show_streams "$VIDEO_PATH" \
    > "${OUTPUT_DIR}/${BASE_NAME}_ffprobe.json"

# 3. Score physical plausibility
python -m cosmos_reason1.inference.video_reward \
    --video_path "$VIDEO_PATH" \
    --output_json "${OUTPUT_DIR}/${BASE_NAME}_quality.json"

# 4. Check quality threshold (reject if score < 3)
SCORE=$(jq '.physical_plausibility_score' "${OUTPUT_DIR}/${BASE_NAME}_quality.json")
if [ "$SCORE" -lt 3 ]; then
    echo "WARNING: ${BASE_NAME} scored ${SCORE}/5 - consider regenerating"
    echo "$BASE_NAME" >> "${OUTPUT_DIR}/low_quality_videos.txt"
fi

echo "Quality check complete for ${BASE_NAME}: Score ${SCORE}/5"
```

### Quality Thresholds for This Project

| Category            | Minimum Score | Action if Below                    |
| ------------------- | ------------- | ---------------------------------- |
| Presentation videos | 4             | Regenerate with different seed     |
| Training videos     | 3             | Regenerate or exclude from dataset |

**Regeneration command:**

```bash
# Regenerate with new seed if quality score < threshold
python -m cosmos_predict2_5.inference.text2world \
    --model_path checkpoints/Cosmos-Predict2.5-14B \
    --prompt "$(cat cosmos_prompts/P01.txt)" \
    --output_path P01_retry.mp4 \
    --seed 12345 \  # Different seed
    --guidance 7.5 \  # Slightly higher guidance
    --natten
```

---

## Troubleshooting

### Out of Memory (OOM)

H200 has 141GB VRAM so OOM is extremely unlikely with the 14B model (~50GB). If it occurs:

```bash
# Disable CUDA graphs (reduces memory overhead)
python -m cosmos_predict2_5.inference.text2world \
    --model_path checkpoints/Cosmos-Predict2.5-14B \
    --prompt "..." \
    --natten
    # Note: --use_cuda_graphs flag removed
```

### Poor Quality Output

1. Check prompt length (~120 words optimal, max 300)
2. Ensure single scene focus (no shot changes)
3. Try different seed: `--seed 12345`
4. Increase guidance scale: `--guidance 8.0` (more prompt adherence)
5. Add specific negative prompts for artifacts you see
6. Ensure "fixed camera" or "static camera" is in prompt

### Temporal Inconsistency (Sliding Window)

For 30s training videos using sliding window:

1. Ensure prompt describes continuous action
2. Reduce guidance slightly: `--guidance 6.0`
3. Check that first frame of each iteration aligns
4. Consider shorter iterations: `--num_iterations 4` (20s total)

### NATTEN Issues

If NATTEN causes problems:

```bash
# Run without NATTEN (slower but stable)
python -m cosmos_predict2_5.inference.text2world \
    --model_path checkpoints/Cosmos-Predict2.5-14B \
    # Remove --natten flag
    ...
```

### Video Corruption

```bash
# Verify video integrity
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 video.mp4

# Check for frame issues
ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=nb_read_frames video.mp4
```

### Known Cosmos-Predict2.5 Limitations

Be aware of these documented limitations:

- Fast camera movements may cause artifacts
- Overlapping human-object interactions can be imprecise
- Low lighting with motion blur is challenging
- Multiple simultaneous actions may not render well

**Mitigation:** Our prompts are designed for static security cameras, which avoids most of these issues.

---

## Validation Checklist

Before marking a video complete:

- [ ] Video plays without corruption
- [ ] Duration matches spec (±1 second)
- [ ] Resolution is correct (1280x704 for Diffusion, 1024x640 for AR)
- [ ] Content matches prompt intent
- [ ] No obvious artifacts or glitches
- [ ] Metadata file created
- [ ] Thumbnail extracted
- [ ] generation_status.json updated

---

## Video Categories Summary

### Presentation (48 videos)

| Scenario              | IDs     | Time  | Purpose                        |
| --------------------- | ------- | ----- | ------------------------------ |
| Threat Escalation     | P01-P12 | Night | Show risk scoring intelligence |
| Cross-Camera Tracking | P13-P24 | Dusk  | Show ReID and correlation      |
| Household Recognition | P25-P36 | Day   | Show known vs unknown contrast |
| Vehicle + Person      | P37-P48 | Day   | Show full enrichment pipeline  |

### Training (40 videos)

| Category           | IDs     | Purpose                            |
| ------------------ | ------- | ---------------------------------- |
| Threat Patterns    | T01-T10 | Weapon detection, aggressive poses |
| Tracking Sequences | T11-T18 | ReID, cross-angle consistency      |
| Enrichment Stress  | T19-T30 | Exercise all Model Zoo models      |
| Edge Cases         | T31-T40 | Adverse conditions testing         |

---

## Expected Timeline

With Cosmos-Predict2.5-14B on H200 (NATTEN + CUDA graphs enabled):

| Phase                     | Videos | Duration Each | Estimated Time   |
| ------------------------- | ------ | ------------- | ---------------- |
| Presentation (Text2World) | 48     | 5s clips      | ~3-4 hours       |
| Training (Sliding Window) | 40     | 30s (6×5s)    | ~5-6 hours       |
| Validation & Retries      | ~5-10  | -             | ~1 hour          |
| **Total**                 | **88** |               | **~10-12 hours** |

**Note:** NATTEN sparse attention provides ~2.5x speedup on H200's Hopper architecture compared to standard attention.

---

## References

### Official Documentation

- [NVIDIA Cosmos Documentation](https://docs.nvidia.com/cosmos/)
- [Cosmos Diffusion Reference](https://docs.nvidia.com/cosmos/latest/predict1/diffusion/reference.html)
- [Cosmos Diffusion Quickstart](https://docs.nvidia.com/cosmos/1.1.0/predict/diffusion/quickstart_guide.html)
- [Cosmos Autoregressive Reference](https://docs.nvidia.com/cosmos/latest/predict1/autoregressive/reference.html)

### GitHub Repositories

- [cosmos-predict1](https://github.com/nvidia-cosmos/cosmos-predict1) - Main inference repository
- [Cosmos-Tokenizer](https://github.com/NVIDIA/Cosmos-Tokenizer) - Video/image tokenizers
- [NVIDIA Cosmos GitHub](https://github.com/nvidia-cosmos) - All Cosmos repositories

### Hugging Face Models

- [Cosmos-1.0-Diffusion-7B-Text2World](https://huggingface.co/nvidia/Cosmos-1.0-Diffusion-7B-Text2World)
- [Cosmos-1.0-Diffusion-14B-Text2World](https://huggingface.co/nvidia/Cosmos-1.0-Diffusion-14B-Text2World)
- [Cosmos-1.0-Autoregressive-13B-Video2World](https://huggingface.co/nvidia/Cosmos-1.0-Autoregressive-13B-Video2World)

### Tutorials & Guides

- [Cosmos Cookbook Blog](https://developer.nvidia.com/blog/how-to-scale-data-generation-for-physical-ai-with-the-nvidia-cosmos-cookbook/)
- [Analytics Vidhya Cosmos Tutorial](https://www.analyticsvidhya.com/blog/2025/02/nvidia-cosmos-1-0-diffusion/)

---

Good luck with generation!
