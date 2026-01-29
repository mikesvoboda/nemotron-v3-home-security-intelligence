# VEO3 Video Generation

This directory contains the VEO3 video generator for creating AI-animated videos using Google's Veo 3.1 model via NVIDIA's API.

## Quick Start

```bash
# Set your API key (from ~/.bashrc or export manually)
export NVIDIA_API_KEY='your-key-here'

# List all available videos
./docs/media/generate_veo3_videos.sh list

# Generate a specific video
./docs/media/generate_veo3_videos.sh generate --id scene04-what-if-moment

# Generate a category in parallel
./docs/media/generate_veo3_videos.sh generate --category mascot-branded --parallel 3

# Generate all videos (9 total)
./docs/media/generate_veo3_videos.sh generate --all --parallel 3

# Preview a prompt before generating
./docs/media/generate_veo3_videos.sh preview --id scene08-nemotron-hero
```

## Files

| File | Purpose |
|------|---------|
| `generate_veo3_videos.py` | Python script for VEO3 API video generation |
| `generate_veo3_videos.sh` | Bash wrapper with API key check |
| `nemotron-mascot.jpg` | Reference image for mascot character (153K) |
| `veo3-video-specs.json` | Video specifications (single source of truth) |

## Generated Videos

Videos are saved to:
- **Mascot videos (V3):** `docs/media/veo3-mascot-branded-v3/` (6 videos, ~24M)
- **Mascot variants:** `docs/media/veo3-mascot-variants/` (10 videos, ~40M)
- **Architecture videos:** `docs/media/veo3-architecture-tech/` (14 videos, ready to generate)

## Video Specifications

Video specs are defined in `docs/media/veo3-video-specs.json` (same directory as generator):

```json
{
  "defaults": {
    "duration_seconds": 8,
    "resolution": "720p",
    "aspect_ratio": "16:9"
  },
  "categories": {
    "mascot-branded": {
      "output_dir": "docs/media/veo3-mascot-branded-v3",
      "videos": [ ... ]
    },
    "architecture-tech": {
      "output_dir": "docs/media/veo3-architecture-tech",
      "videos": [ ... ]
    }
  }
}
```

## Mascot Character

The Nano mascot is defined by the reference image and embedded prompt description:

- **Body:** Lime green metallic throughout
- **Head:** Rounded with dark visor screen
- **Eyes:** TWO friendly glowing green cartoon eyes
- **Chest:** "NVIDIA" text in black letters (no logo, just text)
- **Details:** Small ear modules, circuit traces
- **Style:** Pixar-style 3D animated character

**Critical:** The full mascot description must be embedded at the start of every mascot-branded prompt for character consistency.

## API Details

- **Endpoint:** `https://inference-api.nvidia.com/v1/videos`
- **Model:** `gcp/google/veo-3.1-generate-001`
- **Cost:** ~$0.50-1.00 per 8-second video
- **Generation time:** 2-5 minutes per video
- **Parallel limit:** 3 concurrent jobs recommended

## Requirements

```bash
# Python dependencies (handled by uv)
httpx

# Environment
NVIDIA_API_KEY or NVAPIKEY environment variable
```

## Tips

1. **Always use parallel generation** for multiple videos to save time
2. **Preview prompts first** to verify the description before generating
3. **Keep reference images** in this directory (nemotron-mascot.jpg)
4. **Full mascot description** is required in prompts for character consistency
5. **Test with one video first** before generating entire batches

## Troubleshooting

**API key not found:**
```bash
source ~/.bashrc  # Load from your shell config
# or
export NVIDIA_API_KEY='sk-...'
```

**Wrong character generated:**
- Verify full mascot description is in the prompt
- Check that `nemotron-mascot.jpg` exists in this directory
- Ensure using the correct API endpoint (`inference-api.nvidia.com`)

**Videos not appearing:**
- Check `output_dir` in video specs matches expected location
- Verify generator has write permissions to output directory

## Architecture Videos

Architecture videos use actual project diagrams as reference images, ensuring they match your real system design.

### Reference Images

All architecture videos use per-video reference images specified in the video specs:

| Reference Image | Size | Used By |
|----------------|------|---------|
| arch-system-overview.png | 4.8M | 6 videos (scenes 4, 9, 28) |
| ai-pipeline-hero.png | 1.5M | 1 video (scene 6a) |
| flow-batch-aggregator.png | 4.9M | 4 videos (scenes 6b, 14) |
| arch-model-zoo.png | 5.3M | 2 videos (scene 7) |
| security-architecture.png | 33K | 1 video (scene 9b) |
| container-architecture.png | 1.4M | 2 videos (scene 29) |

### Architecture Video Categories

**Scene 4: "What If" Moment (8s)**
- Network boundary emphasis
- Data flow containment

**Scene 6: AI Pipeline (8s)**
- Sequential pipeline flow
- Performance metrics emphasis

**Scene 7: Model Zoo (6s)**
- 24 models loading into VRAM
- Concurrent model execution

**Scene 9: Privacy by Design (8s)**
- Privacy shield activation
- Local processing emphasis

**Scene 14: Batch Aggregation (8s)**
- Queue filling with timer
- Batch trigger mechanism

**Scene 28: Full Architecture (8s)**
- Layer-by-layer reveal
- Complete system pan

**Scene 29: Container Architecture (6s)**
- GPU passthrough visualization
- One-command deployment

### Generating Architecture Videos

```bash
# Generate entire architecture category (14 videos)
source ~/.bashrc && ./docs/media/generate_veo3_videos.sh generate --category architecture-tech --parallel 3

# Generate specific scene variants
source ~/.bashrc && ./docs/media/generate_veo3_videos.sh generate --id arch04a-network-boundary
source ~/.bashrc && ./docs/media/generate_veo3_videos.sh generate --id arch04b-data-containment

# Preview before generating
source ~/.bashrc && ./docs/media/generate_veo3_videos.sh preview --id arch28a-layer-reveal
```

## Version History

- **V1:** Initial generation with placeholder mascot (❌ wrong character)
- **V2:** Regenerated with "real" mascot image (❌ still wrong character)
- **V3:** Final generation with full mascot description in prompts (✅ correct green NVIDIA robot)

Current versions use V3 for mascot videos.
