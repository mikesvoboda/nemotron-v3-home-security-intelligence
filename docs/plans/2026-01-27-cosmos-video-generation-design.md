# NVIDIA Cosmos Video Generation Design

**Date:** 2026-01-27
**Status:** Approved
**Author:** Mike Svoboda + maui

## Overview

This design documents the integration of NVIDIA Cosmos world foundation models for generating synthetic security camera footage. The generated videos serve two purposes:

1. **Presentation demos** (48 videos) - High-quality footage for a 5-minute team presentation
2. **Training/testing data** (40 videos) - Synthetic data to stress-test all AI enrichment models

## Goals

- Generate 88 synthetic security camera videos using Cosmos models
- Create reusable prompt templates for consistent generation
- Extend existing `data/synthetic/` evaluation framework for video
- Provide complete handoff documentation for H200 agent execution

## Model Selection

**We use Cosmos-Predict2.5-14B exclusively** - the latest (Dec 2025) and highest quality model.

| Purpose    | Model                     | Rationale                                                                       |
| ---------- | ------------------------- | ------------------------------------------------------------------------------- |
| All Videos | **Cosmos-Predict2.5-14B** | Unified Text/Image/Video2World, 3.5x better quality, H200-optimized with NATTEN |

### Why Cosmos-Predict2.5 over Predict1

| Feature           | Predict1                     | Predict2.5                             |
| ----------------- | ---------------------------- | -------------------------------------- |
| Architecture      | Separate diffusion/AR models | Unified model for all modalities       |
| Quality           | Good                         | 3.5x improved, physics-aware           |
| H200 Optimization | No                           | NATTEN sparse attention (2.5x speedup) |
| Longer Videos     | Limited                      | Sliding window autoregressive mode     |

## Video Specifications

### Presentation Videos (48 total)

| Scenario              | Count | Time of Day | Duration |
| --------------------- | ----- | ----------- | -------- |
| Threat Escalation     | 12    | Night       | 15-20s   |
| Cross-Camera Tracking | 12    | Dusk        | 15-20s   |
| Household Recognition | 12    | Day         | 15-20s   |
| Vehicle + Person      | 12    | Day         | 15-20s   |

### Training Videos (40 total)

| Category                | Count | Duration | Models Exercised                    |
| ----------------------- | ----- | -------- | ----------------------------------- |
| Threat Patterns         | 10    | 30s      | threat_detector, pose, action       |
| Tracking Sequences      | 8     | 30s      | reid, depth, clothing               |
| Enrichment Stress Tests | 12    | 30s      | All 9 Model Zoo models              |
| Edge Cases              | 10    | 30s      | All models under adverse conditions |

## Directory Structure

```
data/synthetic/cosmos/
├── HANDOFF.md                    # Instructions for H200 agent
├── generation_manifest.yaml      # Master list of 88 videos
├── generation_status.json        # Progress tracking
│
├── prompts/
│   └── templates/
│       ├── base_prompt.jinja2    # Master template (~120 words)
│       ├── scenes/*.yaml         # Scene components (4 files)
│       ├── subjects/*.yaml       # Subject components (5 files)
│       ├── environments/*.yaml   # Environment components (5 files)
│       └── actions/*.yaml        # Action sequences (8+ files)
│
├── presentation/                 # Output: 48 Diffusion videos
│   ├── threat_escalation/        # 12 variations
│   ├── cross_camera/             # 12 variations
│   ├── household_recognition/    # 12 variations
│   └── vehicle_person/           # 12 variations
│
└── training/                     # Output: 40 Autoregressive videos
    ├── threat_patterns/          # 10 videos
    ├── tracking_sequences/       # 8 videos
    ├── enrichment_stress/        # 12 videos
    └── edge_cases/               # 10 videos
```

## Prompt Engineering

### Best Practices (from NVIDIA documentation)

1. **~120 words optimal** - Too short = poor quality; >300 = ignored details
2. **Single scene focus** - No shot changes or multiple angles
3. **No camera movement** - Cosmos doesn't handle pan/zoom well yet
4. **Ground in physics** - Realistic motion, lighting, spatial relationships
5. **Concrete language** - "Porch light" not "ambient illumination"

### Security Camera Aesthetic

- Fixed/static camera position
- Wide-angle lens distortion
- IR tint for night scenes
- Timestamp overlay
- Slight grain for realism
- Motion blur on fast movement

### Template Structure

```jinja2
Security camera footage from {{ scene.camera_position }}, {{ scene.setting }}
{{- " at " + environment.time_of_day if environment.time_of_day }}.
{{ environment.lighting_description }}.

{{ subject.description }} {{ subject.appearance }}.
{{ action.sequence_description }}.

{{ scene.camera_notes }}, {{ environment.quality_notes }}.
Realistic human motion, {{ generation.duration_seconds }}-second duration.
```

### Example Generated Prompt

> Security camera footage from elevated doorbell camera, suburban home front porch at night. Single porch light provides harsh overhead illumination with deep shadows. A person in dark hoodie with hood up approaches the front door from the driveway, walking with deliberate slow pace. They stop at the door, lean close to peer through the side window, then reach down to test the door handle. Their face remains obscured by the hood. Fixed camera position, wide-angle lens with slight barrel distortion, IR-tinted footage quality typical of home security systems. Realistic human motion, 15-second duration.

## Cosmos Prompt Schema

Each video is defined by a `cosmos_prompt.json`:

```json
{
  "id": "P01",
  "model": "cosmos-diffusion-14b",
  "category": "presentation",

  "scene": {
    "setting": "suburban_home_front_porch",
    "camera_position": "elevated_doorbell",
    "camera_motion": "static",
    "field_of_view": "wide_120"
  },

  "environment": {
    "time_of_day": "night",
    "lighting": "porch_light_only",
    "weather": "clear",
    "visibility": "medium"
  },

  "subjects": [
    {
      "type": "person",
      "appearance": {
        "clothing": "dark_hoodie",
        "face_visible": false,
        "build": "average_male"
      },
      "motion": {
        "entry_point": "bottom_left",
        "path": "approach_door_directly",
        "key_actions": [
          { "timestamp": 0, "action": "enters_frame_walking" },
          { "timestamp": 5, "action": "stops_at_door" },
          { "timestamp": 8, "action": "looks_through_window" },
          { "timestamp": 12, "action": "tests_door_handle" }
        ]
      }
    }
  ],

  "generation": {
    "duration_seconds": 15,
    "resolution": "1280x704",
    "fps": 24,
    "guidance_scale": 7.5,
    "num_inference_steps": 50
  },

  "prompt_text": "..."
}
```

## Expected Labels Integration

Each generated video has corresponding `expected_labels.json` for pipeline validation:

```json
{
  "detections": [{ "class": "person", "min_confidence": 0.7, "count": 1 }],
  "face": { "detected": false, "visible": false },
  "pose": {
    "posture": "standing",
    "is_suspicious": true,
    "keypoints_visible": ["left_shoulder", "right_shoulder"]
  },
  "clothing": {
    "type": "hoodie",
    "color": "dark",
    "is_suspicious": true
  },
  "risk": {
    "min_score": 60,
    "max_score": 85,
    "level": "high",
    "expected_factors": ["face_obscured", "testing_entry", "night_time"]
  }
}
```

## H200 Agent Execution

### Hardware

- NVIDIA H200 GPU instance
- Cosmos Diffusion 14B + Autoregressive 13B models
- Shell access via Cursor

### Execution Flow

1. Agent reads `HANDOFF.md` for instructions
2. Reads `generation_manifest.yaml` for video specifications
3. Uses `scripts/cosmos_prompt_generator.py` to render prompts
4. Executes Cosmos inference for each video
5. Updates `generation_status.json` with progress
6. Saves outputs with metadata and thumbnails

### Estimated Timeline

| Phase                     | Videos | Time             |
| ------------------------- | ------ | ---------------- |
| Presentation (Diffusion)  | 48     | ~4-6 hours       |
| Training (Autoregressive) | 40     | ~6-8 hours       |
| Validation & Retries      | ~5-10  | ~1-2 hours       |
| **Total**                 | **88** | **~12-16 hours** |

## Presentation Scenarios

### 1. Threat Escalation (Night)

Shows risk scoring intelligence through progressive escalation:

- P01: Normal delivery (LOW baseline)
- P02-P04: Increasingly suspicious behavior (MEDIUM)
- P05-P09: Clear threat indicators (HIGH)
- P10-P12: Critical threat actions (CRITICAL)

### 2. Cross-Camera Tracking (Dusk)

Demonstrates ReID and correlation:

- Same person tracked across driveway → door → side yard
- Tests appearance consistency across angles
- Shows tracking through occlusion

### 3. Household Recognition (Day)

Contrasts known vs unknown individuals:

- Resident arrives → LOW risk
- Unknown person same behavior → MEDIUM risk
- Demonstrates false positive reduction

### 4. Vehicle + Person Composite (Day)

Full enrichment pipeline demo:

- Vehicle detection and classification
- License plate OCR
- Person exits and approaches
- Cross-entity correlation

## Training Data Coverage

### Model Zoo Exercise Matrix

| Model              | Videos             | Scenarios                          |
| ------------------ | ------------------ | ---------------------------------- |
| Threat Detector    | T01-T10            | Weapons, tools, aggressive actions |
| Pose Estimator     | T04, T11, T19, T28 | Various postures                   |
| Demographics       | T16, T19-T20       | Visible faces                      |
| FashionCLIP        | T08, T13, T21-T22  | Clothing types                     |
| Vehicle Classifier | T10, T14, T23      | Vehicle types                      |
| Pet Classifier     | T25-T27            | Dogs, cats                         |
| Person ReID        | T11-T18            | Cross-angle tracking               |
| Depth Anything     | T18, T30           | Distance variation                 |
| Action Recognizer  | T04-T06, T15, T29  | Motion types                       |

### Edge Case Coverage

- Night/IR only (T31)
- Weather: rain (T32), fog (T33), snow (T39)
- Motion blur (T34)
- Occlusion (T35)
- Backlighting (T36)
- Multiple light sources (T37)
- Lens artifacts (T38)
- Lighting transitions (T40)

## Files to Implement

| File                                             | Purpose                  |
| ------------------------------------------------ | ------------------------ |
| `data/synthetic/cosmos/HANDOFF.md`               | H200 agent instructions  |
| `data/synthetic/cosmos/generation_manifest.yaml` | All 88 video specs       |
| `data/synthetic/cosmos/generation_status.json`   | Progress tracking        |
| `prompts/templates/base_prompt.jinja2`           | Master template          |
| `prompts/templates/scenes/*.yaml`                | 4 scene components       |
| `prompts/templates/subjects/*.yaml`              | 5 subject components     |
| `prompts/templates/environments/*.yaml`          | 5 environment components |
| `prompts/templates/actions/*.yaml`               | 8+ action components     |
| `scripts/cosmos_prompt_generator.py`             | Prompt rendering script  |

## References

- [NVIDIA Cosmos Platform](https://www.nvidia.com/en-us/ai/cosmos/)
- [Cosmos Diffusion Model Reference](https://docs.nvidia.com/cosmos/latest/predict1/diffusion/reference.html)
- [Cosmos Autoregressive Reference](https://docs.nvidia.com/cosmos/latest/predict1/autoregressive/reference.html)
- [Cosmos Cookbook Blog](https://developer.nvidia.com/blog/how-to-scale-data-generation-for-physical-ai-with-the-nvidia-cosmos-cookbook/)
- [Hugging Face: Cosmos-1.0-Diffusion-7B-Text2World](https://huggingface.co/nvidia/Cosmos-1.0-Diffusion-7B-Text2World)
