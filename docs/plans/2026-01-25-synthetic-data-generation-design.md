# Synthetic Data Generation & A/B Testing Design

**Date:** 2026-01-25
**Status:** Draft
**Author:** Claude + User

## Overview

A synthetic data generation platform for testing the Home Security Intelligence AI pipeline. Uses NVIDIA's inference API (Gemini for images, Veo 3.1 for videos) to generate realistic security camera footage with known ground truth labels for automated A/B comparison testing.

## Goals

1. **Regression testing** - Verify pipeline produces consistent results after code changes
2. **Edge case coverage** - Generate rare/dangerous scenarios (intruders, weapons, break-ins)
3. **Performance benchmarking** - Stress test throughput with high-volume varied data
4. **Ground truth dataset** - Build labeled dataset where generation spec = expected output

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLI Entry Point                              │
│          ./scripts/synthetic_data.py --scenario loitering           │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Scenario Spec Generator                         │
│  • Loads scenario template (JSON)                                   │
│  • Randomizes parameters within constraints                         │
│  • Outputs: scenario_spec.json + expected_labels.json               │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Prompt Generator                               │
│  • Converts structured spec → natural language prompt               │
│  • Applies camera-style modifiers (fisheye, IR, timestamp overlay)  │
│  • Outputs: generation_prompt.txt                                   │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                              ▼
         ┌──────────────────┐           ┌──────────────────┐
         │  Gemini Image    │           │    Veo Video     │
         │  (high volume)   │           │  (temporal tests)│
         └──────────────────┘           └──────────────────┘
                    │                              │
                    └──────────────┬──────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    File Watcher Simulation                           │
│  • Drops media into /export/foscam/synthetic_{run_id}/              │
│  • Waits for pipeline processing                                    │
│  • Polls API for results                                            │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Comparison Engine                               │
│  • Compares API results vs expected_labels.json                     │
│  • Outputs: results/{timestamp}_report.json                         │
└─────────────────────────────────────────────────────────────────────┘
```

## Scenario Spec Schema

```json
{
  "id": "uuid-auto-generated",
  "category": "suspicious_activity",
  "name": "loitering_at_night",

  "scene": {
    "location": "front_porch",
    "camera_type": "doorbell",
    "camera_effects": ["fisheye_distortion", "ir_night_vision"],
    "timestamp_overlay": true
  },

  "environment": {
    "time_of_day": "night",
    "lighting": "low_ambient_streetlight",
    "weather": "clear",
    "season": "winter"
  },

  "subjects": [
    {
      "type": "person",
      "appearance": { "clothing": "dark_hoodie", "face_visible": false },
      "action": "loitering",
      "position": "near_door",
      "duration_sec": 45,
      "behavior_notes": "looking around nervously, checking windows"
    }
  ],

  "expected_outputs": {
    "detections": [{ "class": "person", "min_confidence": 0.75, "count": 1 }],
    "risk_assessment": {
      "level": "medium",
      "min_score": 40,
      "max_score": 70,
      "expected_factors": ["loitering", "nighttime", "obscured_face"]
    },
    "actions": ["loitering", "looking_around"],
    "threat_indicators": ["suspicious_behavior"]
  },

  "generation": {
    "format": "video",
    "count": 3
  }
}
```

## Scenario Categories

### Normal Activity (`scenarios/normal/`)

| Template           | Description                      | Key Variations                               |
| ------------------ | -------------------------------- | -------------------------------------------- |
| `resident_arrival` | Person approaching/entering home | time of day, vehicle present, carrying items |
| `delivery_driver`  | Package delivery at door         | uniform type, package size, duration at door |
| `pet_activity`     | Dog/cat in yard or at door       | animal type, size, behavior                  |
| `vehicle_parking`  | Car arriving/leaving driveway    | vehicle type, speed, occupants               |
| `yard_maintenance` | Lawn care, gardening             | equipment, duration, multiple workers        |

### Suspicious Activity (`scenarios/suspicious/`)

| Template     | Description                      | Key Variations                              |
| ------------ | -------------------------------- | ------------------------------------------- |
| `loitering`  | Person lingering without purpose | duration, time of day, face visibility      |
| `prowling`   | Checking doors/windows           | path taken, tools visible, clothing         |
| `casing`     | Observing property from distance | vehicle vs on foot, duration, return visits |
| `tailgating` | Following resident through gate  | distance, timing, interaction               |

### Active Threats (`scenarios/threats/`)

| Template           | Description                 | Key Variations                        |
| ------------------ | --------------------------- | ------------------------------------- |
| `break_in_attempt` | Forced entry on door/window | tool type, success/failure, time      |
| `package_theft`    | Taking package from porch   | speed, disguise, vehicle nearby       |
| `vandalism`        | Property damage             | target, method, group size            |
| `weapon_visible`   | Person with visible weapon  | weapon type, brandishing vs concealed |

### Environmental Variations (`scenarios/environmental/`)

Applied as modifiers to any base scenario:

- **Time:** dawn, day, dusk, night, midnight
- **Weather:** clear, rain, snow, fog, wind
- **Lighting:** bright_sun, overcast, shadows, headlights, flashlight

## Models Tested (24+ Models)

### Core Services (Always Loaded)

| Model        | Purpose                  | VRAM    |
| ------------ | ------------------------ | ------- |
| YOLO26       | Primary object detection | 650 MB  |
| Nemotron 30B | LLM risk analysis        | 14.7 GB |

### Model Zoo (On-Demand)

| Model                          | Purpose                        | VRAM       |
| ------------------------------ | ------------------------------ | ---------- |
| yolo11-license-plate           | License plate detection        | ~300 MB    |
| yolo11-face                    | Face detection                 | ~300 MB    |
| paddleocr                      | OCR text extraction            | ~500 MB    |
| clip-vit-l                     | Re-identification embeddings   | 800 MB     |
| florence-2-large               | Vision-language queries        | 1.2 GB     |
| yolo-world-s                   | Open-vocabulary detection      | ~400 MB    |
| vitpose-small                  | Pose keypoint detection        | ~200 MB    |
| depth-anything-v2-small        | Depth estimation               | 150 MB     |
| violence-detection             | Violence classification        | ~200 MB    |
| weather-classification         | Weather conditions (5 classes) | ~200 MB    |
| segformer-b2-clothes           | Clothing segmentation          | ~300 MB    |
| xclip-base                     | Temporal action recognition    | 1.5 GB     |
| fashion-clip                   | Clothing classification        | 800 MB     |
| brisque-quality                | Image quality assessment       | 0 MB (CPU) |
| vehicle-segment-classification | Vehicle type (11 types)        | 1.5 GB     |
| pet-classifier                 | Cat/dog classification         | 200 MB     |
| osnet-x0-25                    | Person re-ID embeddings        | 100 MB     |
| threat-detection-yolov8n       | Weapon detection               | 300 MB     |
| vit-age-classifier             | Age estimation                 | 200 MB     |
| vit-gender-classifier          | Gender classification          | 200 MB     |
| yolov8n-pose                   | Alternative pose model         | 200 MB     |
| vehicle-damage                 | Vehicle damage detection       | ~300 MB    |

### Florence-2 Tasks

| Task                      | Output                  |
| ------------------------- | ----------------------- |
| Caption generation        | Scene description       |
| Dense region captioning   | Per-region descriptions |
| OCR with regions          | Text + bounding boxes   |
| Visual Q&A                | Custom queries          |
| Open vocabulary detection | Custom object classes   |

## Expected Outputs Schema

```json
{
  "detections": [
    { "class": "person", "min_confidence": 0.75, "count": 1 },
    { "class": "car", "min_confidence": 0.8, "count": 1 }
  ],

  "license_plate": {
    "detected": true,
    "text_pattern": "^[A-Z0-9]{5,8}$"
  },

  "face": {
    "detected": true,
    "count": 1,
    "visible": true
  },

  "ocr": {
    "expected_text": ["FEDEX", "AMAZON"],
    "min_confidence": 0.7
  },

  "pose": {
    "posture": "crouching",
    "is_suspicious": true,
    "keypoints_visible": ["left_shoulder", "right_shoulder", "left_hip"]
  },

  "action": {
    "action": "loitering",
    "is_suspicious": true
  },

  "demographics": {
    "age_range": "21-35",
    "gender": "male"
  },

  "clothing": {
    "type": "hoodie",
    "color": "dark",
    "is_suspicious": true
  },

  "clothing_segmentation": {
    "segments": ["upper_body", "lower_body", "headwear"]
  },

  "threats": {
    "has_threat": true,
    "types": ["knife"],
    "max_severity": "critical"
  },

  "violence": {
    "detected": false,
    "confidence_threshold": 0.5
  },

  "weather": {
    "condition": "rain/storm",
    "affects_visibility": true
  },

  "vehicle": {
    "type": "van",
    "color": "white"
  },

  "vehicle_damage": {
    "detected": false
  },

  "pet": {
    "type": "dog",
    "is_known_pet": true
  },

  "depth": {
    "subject_distance_m": [2.0, 5.0]
  },

  "reid": {
    "same_person_as": "previous_frame",
    "similarity_threshold": 0.7
  },

  "image_quality": {
    "min_brisque_score": 0,
    "max_brisque_score": 50
  },

  "florence_caption": {
    "must_contain": ["person", "door", "night"],
    "must_not_contain": ["indoor"]
  },

  "risk": {
    "min_score": 60,
    "max_score": 85,
    "level": "high",
    "expected_factors": ["weapon_visible", "nighttime", "loitering"]
  }
}
```

## CLI Interface

```bash
# Commands
./scripts/synthetic_data.py generate   # Generate synthetic media
./scripts/synthetic_data.py test       # Run A/B comparison tests
./scripts/synthetic_data.py list       # List scenario templates
./scripts/synthetic_data.py validate   # Validate scenario spec

# Generate examples
./scripts/synthetic_data.py generate --scenario loitering --count 5
./scripts/synthetic_data.py generate --scenario break_in_attempt \
    --time night --weather rain --count 3
./scripts/synthetic_data.py generate --scenario package_theft \
    --format video --count 2
./scripts/synthetic_data.py generate --spec ./custom_scenario.json

# Test examples
./scripts/synthetic_data.py test --run-id 20260125_143022
./scripts/synthetic_data.py test --run-id 20260125_143022 \
    --models threat_detector,pose_estimator
./scripts/synthetic_data.py test --all
```

## Output Structure

```
data/synthetic/
├── suspicious_activity/
│   └── loitering_20260125_143022/
│       ├── scenario_spec.json      # Input spec
│       ├── generation_prompt.txt   # Prompt sent to Veo/Gemini
│       ├── expected_labels.json    # Ground truth for comparison
│       ├── media/
│       │   ├── 001.mp4
│       │   ├── 002.mp4
│       │   └── 003.mp4
│       └── metadata.json           # Generation metadata
└── results/
    └── 20260125_143022_report.json # Test results
```

## Comparison Engine

### Field Comparison Methods

| Field Type       | Comparison Method                       |
| ---------------- | --------------------------------------- |
| `count`          | Exact match or within ±1 tolerance      |
| `min_confidence` | Actual ≥ expected                       |
| `class`          | Exact string match                      |
| `is_suspicious`  | Boolean exact match                     |
| `score range`    | min ≤ actual ≤ max                      |
| `text_pattern`   | Regex match                             |
| `must_contain`   | All keywords present (case-insensitive) |
| `enum values`    | Exact match from allowed set            |
| `distance range` | Within [min, max] meters                |

### Report Format

```json
{
  "run_id": "20260125_143022",
  "scenario": "loitering",
  "generated_at": "2026-01-25T14:30:22Z",
  "tested_at": "2026-01-25T14:35:47Z",
  "summary": {
    "total_samples": 5,
    "passed": 4,
    "failed": 1,
    "pass_rate": 0.8,
    "models_tested": 12,
    "avg_inference_time_ms": 1847
  },
  "model_results": {
    "rt_detrv2": { "passed": 5, "failed": 0, "accuracy": 1.0 },
    "threat_detector": { "passed": 5, "failed": 0, "accuracy": 1.0 },
    "pose_estimator": { "passed": 4, "failed": 1, "accuracy": 0.8 },
    "nemotron_risk": { "passed": 5, "failed": 0, "accuracy": 1.0 }
  },
  "failures": [
    {
      "sample": "003.mp4",
      "model": "pose_estimator",
      "expected": { "posture": "crouching", "is_suspicious": true },
      "actual": { "posture": "standing", "is_suspicious": false },
      "diff": {
        "posture": { "expected": "crouching", "actual": "standing" },
        "is_suspicious": { "expected": true, "actual": false }
      }
    }
  ]
}
```

## Prompt Generation

### Base Template

```python
SECURITY_CAMERA_PROMPT = """
Security camera footage from a {camera_type} camera mounted at {location}.
{time_description}. {weather_description}.
{camera_effects_description}

Scene: {scene_description}

{subject_descriptions}

{action_description}

Style: Realistic security camera footage, {resolution} quality,
slight motion blur, {lighting_style} lighting.
{timestamp_overlay}
"""
```

### Camera Effect Modifiers

| Effect                  | Prompt Addition                                                |
| ----------------------- | -------------------------------------------------------------- |
| `fisheye_distortion`    | "Wide-angle fisheye lens with barrel distortion at edges"      |
| `ir_night_vision`       | "Infrared night vision mode, grayscale with slight green tint" |
| `timestamp_overlay`     | "White timestamp text in bottom-right corner"                  |
| `motion_blur`           | "Slight motion blur on moving subjects"                        |
| `compression_artifacts` | "Mild JPEG compression artifacts typical of security footage"  |

## Pipeline Integration

1. **Generate media** via Veo/Gemini APIs
2. **Drop files** into `/export/foscam/synthetic_{run_id}/`
3. **File watcher** detects and processes through real pipeline
4. **Poll API** with timeout for results:
   ```python
   camera_name = f"synthetic_test_{uuid4().hex[:8]}"
   # Drop files into /export/foscam/{camera_name}/
   for _ in range(max_retries):
       results = api.get(f"/api/detections?camera={camera_name}")
       if len(results) >= expected_count:
           break
       sleep(poll_interval)
   ```
5. **Compare** pipeline output against expected labels

## File Structure

```
scripts/synthetic_data.py          # Main CLI tool
scripts/synthetic/
├── __init__.py
├── prompt_generator.py            # Spec → prompt conversion
├── media_generator.py             # Veo/Gemini API calls
├── comparison_engine.py           # A/B testing logic
├── report_generator.py            # JSON report creation
└── scenarios/                     # Template library
    ├── __init__.py
    ├── normal/
    │   ├── resident_arrival.json
    │   ├── delivery_driver.json
    │   ├── pet_activity.json
    │   └── vehicle_parking.json
    ├── suspicious/
    │   ├── loitering.json
    │   ├── prowling.json
    │   └── casing.json
    ├── threats/
    │   ├── break_in_attempt.json
    │   ├── package_theft.json
    │   └── weapon_visible.json
    └── environmental/
        ├── time_modifiers.json
        └── weather_modifiers.json
```

## Limitations

- **Veo video duration:** 8 seconds max per generation (extension not supported via NVIDIA API)
- **Resolution:** 720p for videos, 1080p for images
- **API rate limits:** May need throttling for large batch generation
- **Model variance:** Expected outputs use ranges, not exact values

## Future Enhancements

- CI/CD integration for automated regression testing
- Pre-generated dataset caching for faster test runs
- Dashboard visualization of test trends over time
- Automatic scenario generation from real incident reports
