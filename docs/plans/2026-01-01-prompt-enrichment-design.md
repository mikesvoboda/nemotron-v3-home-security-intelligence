# Nemotron Prompt Enrichment Design

**Date:** 2026-01-01
**Status:** Draft

## Overview

Enhance the Nemotron LLM risk analysis by enriching detection context with zone information, baseline deviation data, cross-camera correlation, and additional model outputs (license plates, faces, OCR text).

## Current State

The current prompt sends minimal context to Nemotron:

- Camera name
- Time window
- List of detections with class/confidence/bbox

This results in generic risk assessments that don't account for:

- Where detections occurred (driveway vs yard vs entry point)
- Whether activity is normal for this time/location
- Patterns across multiple cameras
- Detailed object identification (license plates, faces)

## Architecture

### Phase 1: Context Enrichment (Prompt-Only)

Enrich prompts with data already available in the database:

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Batch           │────▶│ ContextEnricher  │────▶│ Enhanced Prompt │
│ (detections)    │     │ Service          │     │ to Nemotron     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
              ┌─────────┐ ┌─────────┐ ┌─────────┐
              │ Zones   │ │Baselines│ │ Recent  │
              │ DB      │ │ DB      │ │ Events  │
              └─────────┘ └─────────┘ └─────────┘
```

#### ContextEnricher Service

```python
@dataclass
class EnrichedContext:
    camera_name: str
    zones: list[ZoneContext]
    baselines: BaselineContext
    recent_events: list[RecentEvent]
    cross_camera: list[CrossCameraActivity]

class ContextEnricher:
    async def enrich(self, batch: Batch) -> EnrichedContext:
        zones = await self._get_zone_context(batch)
        baselines = await self._get_baseline_deviation(batch)
        recent = await self._get_recent_events(batch.camera_id)
        cross_camera = await self._get_cross_camera_activity(batch)
        return EnrichedContext(...)
```

#### Zone Context

Map detections to zones defined in the database:

| Zone Type   | Risk Weight | Description                 |
| ----------- | ----------- | --------------------------- |
| entry_point | High        | Doors, gates, access points |
| driveway    | Medium      | Vehicle areas               |
| sidewalk    | Low         | Public foot traffic         |
| yard        | Medium      | Property perimeter          |

#### Baseline Deviation

Compare current activity to historical norms:

```python
class BaselineContext:
    hour_of_day: int
    day_of_week: str
    expected_detections: dict[str, float]  # class -> avg count
    current_detections: dict[str, int]     # class -> actual count
    deviation_score: float                  # 0-1 how unusual
```

### Phase 2: Model Zoo (On-Demand Loading)

Add secondary models that load on-demand during batch processing to extract additional context, then unload to free VRAM.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Batch Processing                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌─────────────┐    ┌──────────────┐            │
│  │ RT-DETRv2│───▶│ Model Zoo   │───▶│ Nemotron LLM │            │
│  │ (always) │    │ (on-demand) │    │ (always)     │            │
│  └──────────┘    └─────────────┘    └──────────────┘            │
│                         │                                        │
│         ┌───────────────┼───────────────┐                        │
│         ▼               ▼               ▼                        │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐                    │
│   │ YOLO11   │   │ YOLO11   │   │ PaddleOCR│                    │
│   │ License  │   │ Face     │   │ Text     │                    │
│   └──────────┘   └──────────┘   └──────────┘                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Model Configuration

```python
@dataclass
class ModelConfig:
    name: str                    # "yolo11-license-plate"
    path: str                    # HuggingFace or local path
    category: str                # "detection", "recognition", "ocr"
    vram_mb: int                 # Estimated VRAM usage
    load_fn: Callable           # Function to load model
    enabled: bool = True        # Can be disabled via config
    available: bool = False     # Set True after successful load

MODEL_ZOO = {
    "yolo11-license-plate": ModelConfig(
        name="yolo11-license-plate",
        path="keremberke/yolov11-license-plate-detection",
        category="detection",
        vram_mb=300,
        load_fn=load_yolo_model,
    ),
    "yolo11-face": ModelConfig(
        name="yolo11-face",
        path="keremberke/yolov11n-face-detection",
        category="detection",
        vram_mb=200,
        load_fn=load_yolo_model,
    ),
    "paddleocr": ModelConfig(
        name="paddleocr",
        path="PaddlePaddle/PaddleOCR",
        category="ocr",
        vram_mb=100,
        load_fn=load_paddle_ocr,
    ),
    # Future: YOLO26 when released
    "yolo26-general": ModelConfig(
        name="yolo26-general",
        path="ultralytics/yolo26",  # TBD
        category="detection",
        vram_mb=400,
        load_fn=load_yolo_model,
        enabled=False,  # Enable when available
    ),
}
```

#### ModelManager

```python
class ModelManager:
    def __init__(self):
        self._loaded_models: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def load(self, model_name: str):
        """Load model, yield for use, then unload."""
        config = MODEL_ZOO[model_name]

        async with self._lock:
            if model_name not in self._loaded_models:
                logger.info(f"Loading {model_name} (~{config.vram_mb}MB)")
                model = await config.load_fn(config.path)
                self._loaded_models[model_name] = model

        try:
            yield self._loaded_models[model_name]
        finally:
            async with self._lock:
                if model_name in self._loaded_models:
                    logger.info(f"Unloading {model_name}")
                    del self._loaded_models[model_name]
                    torch.cuda.empty_cache()
```

#### Enrichment Pipeline

```python
class EnrichmentPipeline:
    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager

    async def enrich_batch(
        self,
        detections: list[Detection],
        images: list[Image]
    ) -> EnrichmentResult:
        result = EnrichmentResult()

        # Check for vehicles -> run license plate detection
        vehicles = [d for d in detections if d.class_name in VEHICLE_CLASSES]
        if vehicles:
            async with self.model_manager.load("yolo11-license-plate") as model:
                result.license_plates = await self._detect_plates(model, vehicles, images)

            # OCR on detected plates
            if result.license_plates:
                async with self.model_manager.load("paddleocr") as ocr:
                    result.plate_text = await self._read_plates(ocr, result.license_plates)

        # Check for persons -> run face detection
        persons = [d for d in detections if d.class_name == "person"]
        if persons:
            async with self.model_manager.load("yolo11-face") as model:
                result.faces = await self._detect_faces(model, persons, images)

        return result
```

### Enhanced Prompt Template

```python
RISK_ANALYSIS_PROMPT = """<|im_start|>system
You are a home security risk analyzer. Output valid JSON only.<|im_end|>
<|im_start|>user
Analyze these detections and output a JSON risk assessment.

## Camera Context
Camera: {camera_name}
Time: {start_time} to {end_time}
Day: {day_of_week}

## Zone Analysis
{zone_analysis}

## Baseline Comparison
Expected activity for {hour}:00 on {day_of_week}:
{baseline_comparison}

Deviation score: {deviation_score} (0=normal, 1=highly unusual)

## Cross-Camera Activity
{cross_camera_summary}

## Detections
{detections_list}

## Additional Context
{enrichment_context}

## Risk Interpretation Guide
- entry_point detections: Higher concern, especially unknown persons
- Baseline deviation > 0.5: Unusual activity pattern
- Cross-camera correlation: May indicate coordinated movement
- License plates: Note any unrecognized vehicles
- Time of day: Late night activity more concerning

## Risk Levels
- low (0-29): Normal activity, no action needed
- medium (30-59): Notable activity, worth reviewing
- high (60-84): Suspicious activity, recommend alert
- critical (85-100): Immediate threat, urgent action

Output format: {{"risk_score": N, "risk_level": "level", "summary": "text", "reasoning": "text", "recommended_action": "text"}}<|im_end|>
<|im_start|>assistant
"""
```

## VRAM Budget

| Component       | VRAM (MB) | Status        |
| --------------- | --------- | ------------- |
| Nemotron LLM    | 21,700    | Always loaded |
| RT-DETRv2       | 650       | Always loaded |
| **Available**   | **1,650** | For Model Zoo |
| YOLO11-License  | 300       | On-demand     |
| YOLO11-Face     | 200       | On-demand     |
| PaddleOCR       | 100       | On-demand     |
| YOLO26 (future) | 400       | On-demand     |

Models load sequentially, never concurrently, to stay within budget.

## Implementation Plan

### Phase 1: Context Enrichment

1. Create `ContextEnricher` service
2. Implement zone mapping for detections
3. Implement baseline deviation calculation
4. Add cross-camera correlation query
5. Update prompt template with context sections
6. Update `NemotronAnalyzer` to use enriched context

### Phase 2: Model Zoo

1. Create `ModelConfig` and `MODEL_ZOO` registry
2. Implement `ModelManager` with context manager
3. Create `EnrichmentPipeline` service
4. Add license plate detection + OCR
5. Add face detection
6. Integrate enrichment into batch processing
7. Add YOLO26 when released

### Phase 3: Testing & Tuning

1. Unit tests for each component
2. Integration tests for full pipeline
3. Tune prompt based on LLM output quality
4. Benchmark VRAM usage and loading times
5. Add model availability checks and fallbacks

## Success Criteria

- Risk assessments include zone-specific reasoning
- Unusual activity patterns are flagged with deviation scores
- License plates and faces are detected when present
- VRAM stays within budget during enrichment
- Model loading adds <2s to batch processing time
- JSON parse success rate remains >99%

## Future Enhancements

- **Entity tracking**: Track same person/vehicle across cameras over time
- **Known entity database**: Store recognized plates/faces with labels
- **Configurable model selection**: Enable/disable models per camera
- **Streaming enrichment**: Process enrichment while waiting for Nemotron
- **YOLO26 integration**: Drop-in replacement when released
