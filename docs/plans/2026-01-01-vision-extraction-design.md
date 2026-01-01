# Comprehensive Vision Extraction Design

**Date:** 2026-01-01
**Status:** Draft

## Overview

Maximize information extraction from security camera feeds to enrich Nemotron LLM risk analysis. Extends the existing Model Zoo architecture with vision-language models for comprehensive attribute extraction, behavior analysis, re-identification, and scene understanding.

## Goals

1. **Object Attributes** - Extract vehicle color/type/make/commercial markings, person clothing/bags/uniforms
2. **Behavior Analysis** - Pose estimation, action recognition, trajectory patterns (post-hoc)
3. **Re-Identification** - Session-based entity tracking across cameras (24-hour TTL)
4. **Scene Understanding** - Unusual objects, scene changes, environmental context

## Model Architecture

### Always Loaded

| Model        | VRAM   | Purpose                                 |
| ------------ | ------ | --------------------------------------- |
| RT-DETRv2    | 650MB  | Object detection with confidence scores |
| Nemotron LLM | 21.7GB | Risk analysis                           |

### On-Demand Model Zoo

| Model                    | VRAM   | Purpose                             |
| ------------------------ | ------ | ----------------------------------- |
| Florence-2-large (4-bit) | ~1.2GB | Attributes, behavior, scene queries |
| CLIP ViT-L               | ~800MB | Re-identification embeddings        |
| YOLO11-license-plate     | ~300MB | License plate detection             |
| YOLO11-face              | ~200MB | Face detection                      |
| PaddleOCR                | ~100MB | Text recognition                    |

**Loading strategy:** Models load sequentially, never concurrently. Max ~1.2GB on-demand VRAM.

## Extraction Pipeline

```
RT-DETRv2 (always loaded)
    │
    ▼ Detections with confidence
    │
Florence-2 (on-demand)
    │
    ▼ Attributes, behavior, scene context
    │
CLIP ViT-L (on-demand)
    │
    ▼ Re-identification embeddings
    │
YOLO11-plate → PaddleOCR (on-demand)
    │
    ▼ License plate text
    │
YOLO11-face (on-demand)
    │
    ▼ Face detections
    │
Nemotron LLM (always loaded)
    │
    ▼ Risk assessment with full context
```

## Florence-2 Extraction Queries

### Vehicle Queries

```python
VEHICLE_QUERIES = [
    "<CAPTION>",                              # Full description
    "What color is this vehicle?",            # "white", "red", "black"
    "What type of vehicle is this?",          # "sedan", "SUV", "pickup"
    "Is this a commercial vehicle?",          # "yes, delivery van" / "no"
    "What company logo or text is visible?",  # "FedEx", "HVAC Services"
]
```

### Person Queries

```python
PERSON_QUERIES = [
    "<CAPTION>",                              # Full description
    "What is this person wearing?",           # "blue jacket, dark pants"
    "Is this person carrying anything?",      # "backpack", "package", "nothing"
    "Does this person appear to be a delivery worker or service worker?",
    "What is this person doing?",             # "walking", "standing", "crouching"
]
```

### Scene Queries

```python
SCENE_QUERIES = [
    "<CAPTION>",                              # General scene description
    "Are there any unusual objects in this scene?",
    "What time of day does this appear to be?",
    "Is anyone using tools or equipment?",
]

UNUSUAL_OBJECT_QUERIES = [
    "Are there any tools visible? (ladder, crowbar, bolt cutters, etc.)",
    "Are there any abandoned bags or packages?",
    "Is there anything unusual or out of place in this scene?",
]

ENVIRONMENT_QUERIES = [
    "What time of day does this appear to be based on lighting?",
    "Is there a flashlight or artificial light source visible?",
    "What are the weather conditions?",
]
```

## Data Structures

### Attribute Extraction

```python
@dataclass
class VehicleAttributes:
    color: str | None           # "white", "red", "black"
    vehicle_type: str | None    # "sedan", "SUV", "pickup", "van"
    is_commercial: bool
    commercial_text: str | None # "FedEx", "Joe's Plumbing"
    caption: str                # Full description

@dataclass
class PersonAttributes:
    clothing: str | None        # "blue jacket, dark pants"
    carrying: str | None        # "backpack", "package", "nothing"
    is_service_worker: bool
    action: str | None          # "walking", "standing", "crouching"
    caption: str

@dataclass
class SceneAnalysis:
    unusual_objects: list[str]  # ["ladder against fence"]
    tools_detected: list[str]   # ["ladder", "crowbar"]
    abandoned_items: list[str]  # ["package near door"]
    scene_description: str

@dataclass
class EnvironmentContext:
    time_of_day: str            # "day", "dusk", "night"
    artificial_light: bool      # Flashlight at night = suspicious
    weather: str | None
```

### Re-Identification

```python
@dataclass
class EntityEmbedding:
    entity_type: str              # "person" or "vehicle"
    embedding: list[float]        # 768-dim vector from CLIP ViT-L
    camera_id: str
    timestamp: datetime
    detection_id: str
    attributes: dict              # From Florence-2
```

**Redis Storage (session-based):**

```
Key: entity_embeddings:{date}
TTL: 24 hours

Structure:
{
    "persons": [
        {"embedding": [...], "camera": "front", "time": "14:32", "clothing": "blue jacket"},
    ],
    "vehicles": [
        {"embedding": [...], "camera": "front", "time": "14:30", "color": "white", "plate": "ABC123"},
    ]
}
```

**Matching:**

```python
SIMILARITY_THRESHOLD = 0.85  # Cosine similarity

def find_matching_entities(new_embedding, stored_embeddings):
    matches = []
    for stored in stored_embeddings:
        similarity = cosine_similarity(new_embedding, stored.embedding)
        if similarity >= SIMILARITY_THRESHOLD:
            matches.append({
                "entity": stored,
                "similarity": similarity,
                "time_gap": new_timestamp - stored.timestamp,
            })
    return matches
```

### Scene Change Detection (CPU-based, no ML)

```python
from skimage.metrics import structural_similarity as ssim

class SceneChangeDetector:
    def __init__(self):
        self._baselines: dict[str, np.ndarray] = {}

    def detect_changes(self, camera_id: str, current_frame: np.ndarray) -> dict:
        if camera_id not in self._baselines:
            self._baselines[camera_id] = current_frame
            return {"change_detected": False}

        similarity = ssim(self._baselines[camera_id], current_frame)
        return {
            "change_detected": similarity < 0.90,
            "similarity_score": similarity,
        }
```

## Enhanced Nemotron Prompt

```python
ENHANCED_RISK_ANALYSIS_PROMPT = """<|im_start|>system
You are a home security risk analyzer. Provide detailed reasoning. Output valid JSON only.<|im_end|>
<|im_start|>user
Analyze this security event and provide a risk assessment.

## Camera & Time
Camera: {camera_name}
Time: {timestamp}
Day: {day_of_week}
Lighting: {time_of_day}

## Detections
{detections_with_attributes}

## Re-Identification
{reid_context}

## Zone Analysis
{zone_analysis}

## Baseline Comparison
{baseline_comparison}
Deviation score: {deviation_score}

## Cross-Camera Activity
{cross_camera_summary}

## Scene Analysis
{scene_analysis}

## Risk Factors to Consider
- entry_point detections: Higher concern
- Unknown persons/vehicles: Note if not seen before
- Re-identified entities: Track movement patterns
- Service workers: Usually lower risk (delivery, utility)
- Unusual objects: Tools, abandoned items increase risk
- Time context: Late night + artificial light = concerning
- Behavioral cues: Crouching, loitering, repeated passes

## Risk Levels
- low (0-29): Normal activity
- medium (30-59): Notable, worth reviewing
- high (60-84): Suspicious, recommend alert
- critical (85-100): Immediate threat

Output JSON:
{{"risk_score": N, "risk_level": "level", "summary": "text", "reasoning": "detailed explanation", "entities": [{{"type": "person|vehicle", "description": "text", "threat_level": "low|medium|high"}}], "recommended_action": "text"}}<|im_end|>
<|im_start|>assistant
"""
```

## Implementation Plan

### Phase 1: Florence-2 Integration

1. Download Florence-2-large model to Model Zoo
2. Add Florence-2 to ModelConfig registry
3. Create VisionExtractor service with Florence-2 queries
4. Implement attribute extraction for vehicles and persons
5. Implement scene analysis queries

### Phase 2: Re-Identification

1. Download CLIP ViT-L model to Model Zoo
2. Add CLIP to ModelConfig registry
3. Create ReIdentificationService with embedding generation
4. Implement Redis storage for session-based embeddings
5. Implement cosine similarity matching
6. Add re-id context formatting for prompt

### Phase 3: Scene Understanding

1. Implement SceneChangeDetector (CPU-based SSIM)
2. Add unusual object detection queries
3. Add environment context queries
4. Integrate scene analysis into pipeline

### Phase 4: Pipeline Integration

1. Update EnrichmentPipeline to orchestrate all extractors
2. Update NemotronAnalyzer to use enhanced prompt
3. Add formatting functions for all context types
4. Add configuration toggles for each extraction type

### Phase 5: Testing

1. Unit tests for VisionExtractor
2. Unit tests for ReIdentificationService
3. Unit tests for SceneChangeDetector
4. Integration tests for full pipeline
5. Benchmark VRAM usage and timing

## VRAM Budget

| Phase         | Models Loaded | VRAM Used |
| ------------- | ------------- | --------- |
| Detection     | RT-DETRv2     | 650MB     |
| Attributes    | Florence-2    | 1.2GB     |
| Re-ID         | CLIP ViT-L    | 800MB     |
| License Plate | YOLO11 + OCR  | 400MB     |
| Face          | YOLO11-face   | 200MB     |
| Analysis      | Nemotron      | 21.7GB    |

Max on-demand: 1.2GB (Florence-2)
Total always-loaded: 22.35GB
Available headroom: ~1.6GB

## Performance Estimates

- Florence-2 queries: ~2-3 seconds per batch
- CLIP embedding generation: ~0.5 seconds per entity
- Scene change detection: ~50ms (CPU)
- Total pipeline addition: ~5-8 seconds per batch

## Success Criteria

- All vehicle attributes extracted (color, type, commercial)
- All person attributes extracted (clothing, carrying, action)
- Re-identification matches entities across cameras with >85% accuracy
- Scene changes detected within 2 frames
- Unusual objects flagged when present
- VRAM stays within budget
- Pipeline adds <10 seconds to batch processing
