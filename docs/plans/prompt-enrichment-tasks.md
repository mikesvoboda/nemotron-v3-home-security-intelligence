# Prompt Enrichment Implementation Tasks

## Phase 1: Context Enrichment

### Create ContextEnricher service with dataclasses

Create `backend/services/context_enricher.py` with the ContextEnricher service.

**Dataclasses to create:**

- `ZoneContext`: zone_id, zone_name, zone_type (ZoneType enum), detections_in_zone (count)
- `BaselineContext`: hour_of_day, day_of_week, expected_detections (dict[str, float]), current_detections (dict[str, int]), deviation_score (float 0-1)
- `RecentEvent`: event_id, timestamp, risk_level, summary
- `CrossCameraActivity`: camera_name, detection_class, count, time_window_seconds
- `EnrichedContext`: camera_name, zones (list[ZoneContext]), baselines (BaselineContext), recent_events (list[RecentEvent]), cross_camera (list[CrossCameraActivity])

**ContextEnricher class:**

- Constructor takes AsyncSession
- `async def enrich(self, batch: Batch) -> EnrichedContext` - main entry point
- Private methods: `_get_zone_context`, `_get_baseline_deviation`, `_get_recent_events`, `_get_cross_camera_activity`

**Reference files:**

- `backend/models/zone.py` - Zone model with ZoneType enum
- `backend/models/baseline.py` - ActivityBaseline and ClassBaseline models
- `backend/models/event.py` - Event model
- `backend/services/batch_aggregator.py` - Batch dataclass

**Tests:** Create `backend/tests/unit/test_context_enricher.py`

---

### Implement zone mapping for detections

Add `_get_zone_context` method to ContextEnricher that maps detections to zones.

**Implementation:**

1. Query zones for the camera from database (Zone model, filter by camera_id and enabled=True)
2. For each detection in the batch, check if its bbox center point falls within any zone polygon
3. Use point-in-polygon algorithm (ray casting) - create helper function `point_in_polygon(x, y, coordinates) -> bool`
4. Bbox center: `center_x = (bbox.x1 + bbox.x2) / 2`, `center_y = (bbox.y1 + bbox.y2) / 2`
5. Zone coordinates are normalized 0-1, bbox coordinates may need normalization based on image dimensions
6. Return list of ZoneContext with detection counts per zone

**Helper function location:** `backend/services/geometry.py` or inline in context_enricher.py

**Tests:** Test point_in_polygon with rectangle and polygon shapes, test zone mapping with mock detections

---

### Implement baseline deviation calculation

Add `_get_baseline_deviation` method to ContextEnricher.

**Implementation:**

1. Get current hour and day_of_week from batch timestamp
2. Query ActivityBaseline for camera_id, hour, day_of_week to get avg_count
3. Query ClassBaseline for each detection_class in the batch to get expected frequencies
4. Count actual detections by class in the batch
5. Calculate deviation_score: `abs(actual - expected) / max(expected, 1)` averaged across classes
6. Clamp deviation_score to 0-1 range

**Fallback:** If no baseline data exists (new camera), return deviation_score=0.5 (neutral) with empty expected_detections

**Reference:** `backend/models/baseline.py` - ActivityBaseline.avg_count, ClassBaseline.frequency

**Tests:** Test with existing baselines, test fallback for missing baselines, test deviation calculation

---

### Add cross-camera correlation query

Add `_get_cross_camera_activity` method to ContextEnricher.

**Implementation:**

1. Get list of all cameras except current one
2. Query recent detections (last 5 minutes) from Detection model grouped by camera and class
3. Return list of CrossCameraActivity showing what was detected on other cameras
4. Time window configurable via constant CROSS_CAMERA_WINDOW_SECONDS = 300

**Query pattern:**

```python
SELECT camera_id, class_name, COUNT(*) as count
FROM detections
WHERE timestamp > (now - 5 minutes)
  AND camera_id != current_camera_id
GROUP BY camera_id, class_name
```

**Reference:** `backend/models/detection.py` - Detection model with camera_id, class_name, timestamp

**Tests:** Test with detections on multiple cameras, test empty result when no other activity

---

### Create enhanced prompt template

Update `backend/services/prompts.py` with the enhanced prompt template.

**New template variables:**

- `{day_of_week}` - e.g., "Monday"
- `{hour}` - e.g., "14"
- `{zone_analysis}` - formatted zone context
- `{baseline_comparison}` - formatted baseline data
- `{deviation_score}` - float 0-1
- `{cross_camera_summary}` - formatted cross-camera activity
- `{enrichment_context}` - model zoo results (license plates, faces) - empty for Phase 1

**Add helper functions:**

- `format_zone_analysis(zones: list[ZoneContext]) -> str`
- `format_baseline_comparison(baseline: BaselineContext) -> str`
- `format_cross_camera(cross_camera: list[CrossCameraActivity]) -> str`

**Keep existing template as RISK_ANALYSIS_PROMPT_SIMPLE for fallback**

**Reference:** Design doc `docs/plans/2026-01-01-prompt-enrichment-design.md` lines 225-270

---

### Integrate ContextEnricher into NemotronAnalyzer

Update `backend/services/nemotron_analyzer.py` to use ContextEnricher.

**Changes:**

1. Add ContextEnricher as dependency (inject in constructor or create in analyze_batch)
2. In `analyze_batch`, call `enricher.enrich(batch)` to get EnrichedContext
3. Update prompt formatting to use enhanced template with context variables
4. Handle case where enrichment fails gracefully (log warning, use simple prompt)

**Location:** `backend/services/nemotron_analyzer.py` around line 480-530

**Config:** Add `ENABLE_CONTEXT_ENRICHMENT` env var (default True) to allow disabling

**Tests:** Update existing NemotronAnalyzer tests to mock ContextEnricher

---

## Phase 2: Model Zoo

### Create ModelConfig and MODEL_ZOO registry

Create `backend/services/model_zoo.py` with model configuration.

**ModelConfig dataclass:**

```python
@dataclass
class ModelConfig:
    name: str                    # "yolo11-license-plate"
    path: str                    # Local path to model
    category: str                # "detection", "ocr"
    vram_mb: int                 # Estimated VRAM usage
    enabled: bool = True         # Can be disabled via env var
```

**MODEL_ZOO dict:**

```python
MODEL_ZOO = {
    "yolo11-license-plate": ModelConfig(
        name="yolo11-license-plate",
        path="/export/ai_models/model-zoo/yolo11-license-plate/license-plate-finetune-v1s.pt",
        category="detection",
        vram_mb=300,
    ),
    "yolo11-face": ModelConfig(
        name="yolo11-face",
        path="/export/ai_models/model-zoo/yolo11-face-detection/model.pt",
        category="detection",
        vram_mb=200,
    ),
    "paddleocr": ModelConfig(
        name="paddleocr",
        path="/export/ai_models/model-zoo/paddleocr",
        category="ocr",
        vram_mb=100,
    ),
}
```

**Environment variables:** `MODEL_ZOO_LICENSE_PLATE_ENABLED`, `MODEL_ZOO_FACE_ENABLED`, `MODEL_ZOO_OCR_ENABLED`

**Tests:** Test ModelConfig creation, test env var overrides

---

### Implement ModelManager with context manager

Add ModelManager class to `backend/services/model_zoo.py`.

**Implementation:**

```python
class ModelManager:
    def __init__(self):
        self._loaded_models: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def load(self, model_name: str):
        """Load model, yield for use, then unload to free VRAM."""
        # Load model if not cached
        # yield model
        # Unload and call torch.cuda.empty_cache()
```

**Model loading functions:**

- `_load_yolo_model(path: str)` - use ultralytics YOLO class
- `_load_paddleocr(path: str)` - use PaddleOCR with custom model paths

**Dependencies to add:** `ultralytics`, `paddleocr` in pyproject.toml

**Logging:** Log model load/unload with timing and VRAM estimate

**Tests:** Test load/unload cycle, test concurrent access with lock, test VRAM cleanup

---

### Create EnrichmentPipeline service

Create `backend/services/enrichment_pipeline.py` with the orchestration logic.

**EnrichmentResult dataclass:**

```python
@dataclass
class LicensePlateResult:
    bbox: tuple[float, float, float, float]
    confidence: float
    plate_text: str | None  # From OCR

@dataclass
class FaceResult:
    bbox: tuple[float, float, float, float]
    confidence: float

@dataclass
class EnrichmentResult:
    license_plates: list[LicensePlateResult] = field(default_factory=list)
    faces: list[FaceResult] = field(default_factory=list)
```

**EnrichmentPipeline class:**

- Constructor takes ModelManager
- `async def enrich_batch(self, detections: list[Detection], image_paths: list[str]) -> EnrichmentResult`
- Check for vehicle detections -> run license plate model -> run OCR on plates
- Check for person detections -> run face model

**Vehicle classes:** car, truck, bus, motorcycle (from COCO)

**Tests:** Test with mock models, test conditional enrichment based on detection classes

---

### Implement license plate detection

Add license plate detection to EnrichmentPipeline.

**Implementation:**

1. Filter detections for vehicle classes
2. For each vehicle detection, crop the image region (with padding)
3. Load yolo11-license-plate model via ModelManager
4. Run inference on cropped regions
5. Return list of LicensePlateResult with bbox (relative to original image) and confidence

**Image handling:**

- Use PIL or cv2 to load and crop images
- Bbox coordinates: convert from detection bbox to absolute pixels, crop with 10% padding
- Convert plate bbox back to absolute coordinates in original image

**Reference:** Model at `/export/ai_models/model-zoo/yolo11-license-plate/license-plate-finetune-v1s.pt`

**Tests:** Test with sample vehicle images, test empty result for non-vehicle detections

---

### Implement PaddleOCR text recognition

Add OCR to EnrichmentPipeline for reading license plates.

**Implementation:**

1. For each detected license plate, crop the plate region from image
2. Load PaddleOCR via ModelManager
3. Run OCR on plate crops
4. Update LicensePlateResult.plate_text with recognized text

**PaddleOCR initialization:**

```python
from paddleocr import PaddleOCR
ocr = PaddleOCR(
    det_model_dir="/export/ai_models/model-zoo/paddleocr/en_PP-OCRv3_det_infer",
    rec_model_dir="/export/ai_models/model-zoo/paddleocr/en_PP-OCRv3_rec_infer",
    cls_model_dir="/export/ai_models/model-zoo/paddleocr/ch_ppocr_mobile_v2.0_cls_infer",
    use_angle_cls=True,
    use_gpu=True,
)
```

**Post-processing:** Clean OCR text (uppercase, remove spaces, validate plate format)

**Tests:** Test with sample plate images, test OCR accuracy

---

### Implement face detection

Add face detection to EnrichmentPipeline.

**Implementation:**

1. Filter detections for "person" class
2. For each person detection, crop the upper portion (head region ~top 30% of bbox)
3. Load yolo11-face model via ModelManager
4. Run inference on cropped regions
5. Return list of FaceResult with bbox and confidence

**Reference:** Model at `/export/ai_models/model-zoo/yolo11-face-detection/model.pt`

**Tests:** Test with sample person images, test empty result for non-person detections

---

### Integrate enrichment into batch processing

Connect EnrichmentPipeline to NemotronAnalyzer.

**Changes to NemotronAnalyzer:**

1. Add ModelManager and EnrichmentPipeline as dependencies
2. Before calling LLM, run enrichment pipeline on batch
3. Format enrichment results into `{enrichment_context}` for prompt
4. Add config `ENABLE_MODEL_ZOO_ENRICHMENT` (default False until tested)

**Format enrichment context:**

```
License plates detected: ABC123 (confidence: 0.92), XYZ789 (confidence: 0.87)
Faces detected: 2 faces in frame
```

**Error handling:** If enrichment fails, log warning and continue with empty enrichment_context

**Tests:** Integration test with full pipeline

---

## Phase 3: Testing

### Unit tests for ContextEnricher

Create comprehensive unit tests for `backend/tests/unit/test_context_enricher.py`.

**Test cases:**

- test_zone_context_with_detections_in_zones
- test_zone_context_with_no_zones_defined
- test_zone_context_point_in_polygon_rectangle
- test_zone_context_point_in_polygon_complex
- test_baseline_deviation_normal_activity
- test_baseline_deviation_unusual_activity
- test_baseline_deviation_no_baseline_data
- test_recent_events_query
- test_cross_camera_activity_with_multiple_cameras
- test_cross_camera_activity_no_other_activity
- test_enrich_full_context

**Fixtures:** Mock database session, sample zones, sample baselines, sample detections

---

### Unit tests for ModelManager

Create tests for `backend/tests/unit/test_model_zoo.py`.

**Test cases:**

- test_model_config_creation
- test_model_zoo_registry
- test_model_manager_load_unload
- test_model_manager_concurrent_access
- test_model_manager_disabled_model
- test_load_yolo_model (mock ultralytics)
- test_load_paddleocr (mock paddleocr)

**Mocking:** Mock torch.cuda.empty_cache, mock model classes

---

### Integration tests for enrichment pipeline

Create `backend/tests/integration/test_enrichment_pipeline.py`.

**Test cases:**

- test_license_plate_detection_on_vehicle_image
- test_ocr_on_license_plate
- test_face_detection_on_person_image
- test_full_enrichment_pipeline
- test_enrichment_with_no_relevant_detections
- test_enrichment_graceful_failure

**Test images:** Add sample images to `backend/tests/fixtures/` (vehicle with plate, person with face)

**Note:** These tests require GPU and models - mark with `@pytest.mark.slow` and `@pytest.mark.gpu`

---

### Benchmark VRAM usage and loading times

Create benchmark script `scripts/benchmark_model_zoo.py`.

**Measurements:**

- Time to load each model
- VRAM usage after loading each model (nvidia-smi)
- Time for inference on sample image
- Time to unload and VRAM recovery
- Total pipeline time for typical batch

**Output:** Write results to `docs/benchmarks/model-zoo-benchmark.md`

**Run criteria:** Must stay under 1.5GB VRAM for all Model Zoo models combined
