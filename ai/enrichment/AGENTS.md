# AI Enrichment Service

![Context Enrichment Pipeline](../../docs/images/architecture/enrichment-pipeline.png)

_Fan-out enrichment pipeline showing parallel model inference for detection context._

## Purpose

Combined enrichment service providing on-demand model loading for comprehensive detection analysis. Consolidates vehicle, pet, clothing, depth, pose, threat detection, demographics, and re-identification into a single containerized service with VRAM-aware model management. (Action recognition retired here with NEM-5563 — it runs as Triton `stgcn_action` on the ai-gateway.)

## Architecture

- **On-Demand Loading**: Models loaded when needed, evicted via LRU when VRAM budget is exceeded
- **VRAM Budget**: Configurable via `VRAM_BUDGET_GB` environment variable (default: 6.0GB)
- **Priority System**: CRITICAL > HIGH > MEDIUM > LOW (lower priority models evicted first)
- **Thread-Safe**: All model loading/unloading protected by asyncio locks

## Port and Resources

- **Port**: 8094 (configurable via `PORT`)
- **Total VRAM Budget**: ~6.0 GB (configurable)

| Model                  | VRAM    | Priority | Purpose                                 |
| ---------------------- | ------- | -------- | --------------------------------------- |
| Threat Detector        | ~400 MB | CRITICAL | Weapon detection (gun, knife)           |
| Pose Estimator         | ~300 MB | HIGH     | Body posture analysis                   |
| Demographics           | ~500 MB | HIGH     | Age/gender estimation                   |
| FashionSigLIP          | ~800 MB | MEDIUM   | Clothing attributes (57% more accurate) |
| Vehicle Classification | ~1.5 GB | MEDIUM   | Vehicle type (car, truck, etc.)         |
| Pet Classifier         | ~200 MB | MEDIUM   | Cat/dog classification                  |
| Person ReID            | ~100 MB | MEDIUM   | OSNet re-ID embeddings                  |
| Plate OCR              | ~500 MB | MEDIUM   | License plate text recognition          |
| Depth Anything V2      | ~150 MB | LOW      | Distance estimation                     |
| YOLO26 Detector        | ~100 MB | LOW      | Secondary object detection (opt.)       |

The Action Recognizer row (X-CLIP, ~1.5-2 GB) was retired with NEM-5563:
action recognition now runs as Triton `stgcn_action` on the ai-gateway
(`/action-classify`); the X-CLIP class itself lives in
`archive/ai-enrichment/action_recognizer.py`.

## Directory Contents

```
ai/enrichment/
├── AGENTS.md              # This file
├── Dockerfile             # Container build (PyTorch + CUDA 12.4)
├── __init__.py            # Package init
├── model.py               # Main FastAPI server with /enrich endpoint
├── model_manager.py       # On-demand VRAM-aware model loading
├── model_registry.py      # Model configuration and registration
├── vitpose.py             # ViTPose+ pose analyzer module (legacy)
├── requirements.txt       # Python dependencies
├── models/                # Model implementations
│   ├── __init__.py        # Model exports
│   ├── pose_estimator.py  # YOLOv8n-pose wrapper (TensorRT support)
│   ├── threat_detector.py # Weapon detection
│   ├── demographics.py    # Age/gender estimation
│   ├── person_reid.py     # OSNet re-ID embeddings
│   ├── plate_ocr.py       # PaddleOCR license plate text (NEM-5372)
│   └── yolo26_detector.py # YOLO26 secondary detector
├── utils/                 # Utility modules (NEM-3719)
│   ├── AGENTS.md          # Utils documentation
│   ├── __init__.py        # Package exports
│   └── video_processing.py # ByteTrack tracking, annotators, heatmaps
├── scripts/               # Utility scripts
│   └── export_pose_tensorrt.py  # Export pose model to TensorRT
├── tests/                 # Unit tests
│   ├── conftest.py        # Test fixtures
│   ├── test_model_manager.py     # Model manager unit tests
│   ├── test_pose_estimator.py    # Pose estimation tests
│   ├── test_demographics.py      # Demographics tests
│   ├── test_plate_ocr.py         # Plate OCR tests (NEM-5372)
│   ├── test_video_processing.py  # Video processing utilities tests
│   └── test_yolo26_detector.py   # YOLO26 detector tests
└── test_model.py          # Integration tests
```

## Key Files

### Core Service

#### `model.py` (Main Server)

FastAPI server hosting all classification models with unified `/enrich` endpoint.

**Classifier Classes:**

| Class                | Model                   | VRAM    | Purpose                                               |
| -------------------- | ----------------------- | ------- | ----------------------------------------------------- |
| `VehicleClassifier`  | ViT-base-patch16-224    | ~1.5 GB | Vehicle type classification                           |
| `PetClassifier`      | ResNet-18               | ~200 MB | Cat/dog classification                                |
| `ClothingClassifier` | FashionSigLIP           | ~800 MB | Zero-shot clothing classification (57% more accurate) |
| `DepthEstimator`     | Depth Anything V2 Small | ~150 MB | Monocular depth estimation                            |

**Vehicle Classes:**

```python
VEHICLE_SEGMENT_CLASSES = [
    "articulated_truck",
    "background",
    "bicycle",
    "bus",
    "car",
    "motorcycle",
    "non_motorized_vehicle",
    "pedestrian",
    "pickup_truck",
    "single_unit_truck",
    "work_van",
]
```

**Security Features:**

- Image magic bytes validation (prevents non-image uploads)
- Path traversal protection for model paths (NEM-1098)
- Size limits enforced (10MB max)
- Base64 decoding with error handling

#### `model_manager.py` (On-Demand Model Manager)

VRAM-aware model manager implementing LRU eviction with priority ordering.

**Key Features:**

- Configurable VRAM budget (default: 6.0GB)
- Priority-based eviction (CRITICAL models evicted last)
- Async-safe with asyncio locks
- Automatic CUDA cache clearing on unload

**Public API:**

```python
manager = OnDemandModelManager(vram_budget_gb=6.0)
manager.register_model(
    ModelConfig(
        name="vehicle",
        vram_mb=1500,
        priority=ModelPriority.MEDIUM,
        loader_fn=lambda: VehicleClassifier(...).load_model(),
        unloader_fn=lambda m: _unload_model(m),
    )
)

# Get model (loads if necessary, evicts LRU if needed)
model = await manager.get_model("vehicle")

# Check status
status = manager.get_status()
```

#### `model_registry.py` (Model Registration)

Defines model configurations and the `create_model_registry()` factory function.

**Available Models (9 total):**

| Model Name         | VRAM   | Priority | Trigger Conditions           |
| ------------------ | ------ | -------- | ---------------------------- |
| fashion_clip       | 800 MB | MEDIUM   | Person detected              |
| vehicle_classifier | 1.5 GB | MEDIUM   | Vehicle detected             |
| pet_classifier     | 200 MB | MEDIUM   | Cat/dog detected             |
| depth_estimator    | 100 MB | LOW      | Any detection                |
| pose_estimator     | 300 MB | HIGH     | Person detected              |
| threat_detector    | 400 MB | CRITICAL | Always checked for security  |
| demographics       | 500 MB | HIGH     | Person with face detected    |
| person_reid        | 100 MB | MEDIUM   | Person detected for tracking |
| yolo26_detector    | 100 MB | LOW      | Optional secondary detection |

The X-CLIP `action_recognizer` (1.5–2 GB, LOW) row was removed with the
NEM-5563 retirement — action recognition now runs as Triton `stgcn_action`
behind the ai-gateway's `/action-classify` adapter.

### Model Implementations

#### `models/pose_estimator.py` (YOLOv8n-pose)

Human pose estimation with 17 COCO keypoints.

**Features:**

- Detects 17 COCO keypoints (nose, eyes, ears, shoulders, elbows, wrists, hips, knees, ankles)
- Classifies body posture (standing, crouching, running, reaching_up, etc.)
- Flags suspicious poses for security analysis
- **TensorRT acceleration** for 2-3x speedup (NEM-3838)

**TensorRT Acceleration:**

Enable TensorRT for faster pose estimation inference:

```bash
# Set environment variable
export POSE_USE_TENSORRT=true

# Or export model manually with the script
python ai/enrichment/scripts/export_pose_tensorrt.py --model /models/yolov8n-pose.pt

# Benchmark PyTorch vs TensorRT
python ai/enrichment/scripts/export_pose_tensorrt.py --benchmark
```

TensorRT engines are GPU-architecture specific. Rebuild for each target GPU.

**Posture Classifications:**

- `standing`, `walking`, `running`, `sitting`, `crouching`, `lying_down`, `reaching_up`, `unknown`

**Suspicious Poses:**

- `crouching` - Potential hiding/break-in behavior
- `crawling` - Unusual movement
- `hiding` - Concealment attempt
- `reaching_up` - Potential climbing/entry

#### `models/threat_detector.py` (Weapon Detection)

CRITICAL priority weapon detection for security applications.

**Threat Classes:**

| Class   | Severity |
| ------- | -------- |
| gun     | CRITICAL |
| rifle   | CRITICAL |
| pistol  | CRITICAL |
| knife   | HIGH     |
| bat     | MEDIUM   |
| crowbar | MEDIUM   |

**Output Format:**

```python
ThreatResult(
    threats=[ThreatDetection(threat_type="knife", confidence=0.85, bbox=[...], severity="high")],
    has_threat=True,
    max_severity="high",
    inference_time_ms=45.2,
)
```

#### `models/demographics.py` (Age/Gender Estimation)

ViT-based age and gender classification from face crops.

**Age Ranges:**

```python
AGE_RANGES = ["0-10", "11-20", "21-35", "36-50", "51-65", "65+"]
```

**Privacy Note:** Demographics are used for identification context only and should not be stored long-term.

#### `models/person_reid.py` (OSNet Re-ID)

Person re-identification embeddings for tracking across cameras.

**Features:**

- 512-dimensional normalized embeddings
- Cosine similarity computation
- Configurable matching threshold (default: 0.7)
- Embedding hash for quick lookup

**Input Dimensions:** 256x128 (OSNet standard)

#### Action recognition — RETIRED (NEM-5563)

The X-CLIP `ActionRecognizer` no longer lives in this package; the retired
class is in `archive/ai-enrichment/action_recognizer.py`. Action
recognition now runs skeleton-based: the ai-gateway's `/action-classify`
adapter drives Triton `stgcn_action` over gateway-computed pose keypoints
(`ai/gateway/adapters/enrichment.py`), and the backend pipeline uses
`_recognize_actions_from_skeleton()`. The legacy `/enrich` wire contract
still ACCEPTS `frames` / an `action_recognition` option but ignores both,
and `EnrichmentResponse.action` stays `None`.

#### `models/plate_ocr.py` (PaddleOCR License Plate Text - NEM-5372)

License plate text recognition using PaddleOCR with specialized preprocessing for plate images.

**Features:**

- Automatic angle correction for tilted plates
- CLAHE-based enhancement for low-light conditions
- Motion blur detection and image quality assessment
- Alphanumeric character filtering
- Confidence-weighted text extraction
- GPU acceleration support (via paddlepaddle-gpu)

**Output Format:**

```python
PlateOCRResult(
    plate_text="ABC123",  # Filtered alphanumeric text
    raw_text="ABC 123",  # Original OCR output
    ocr_confidence=0.95,  # Aggregate confidence (0-1)
    char_confidences=[...],  # Per-character confidence
    image_quality_score=0.85,  # Quality assessment (0-1)
    is_enhanced=False,  # Whether CLAHE was applied
    is_blurry=False,  # Motion blur detected
)
```

**Environment Variables:**

| Variable            | Default | Description                           |
| ------------------- | ------- | ------------------------------------- |
| `PLATE_OCR_USE_GPU` | auto    | Enable GPU acceleration (auto-detect) |
| `PLATE_OCR_LANG`    | `en`    | OCR language (en, ch, etc.)           |

**Dependencies:** Requires `paddleocr` and `paddlepaddle-gpu` packages (see requirements.txt).

#### `models/yolo26_detector.py` (YOLO26 Object Detection)

Optional secondary object detector using YOLO26 (Ultralytics).

**Use Cases:**

- Fine-grained object detection complementing YOLO26v2
- Domain-specific detection tasks with custom models
- Detection validation and cross-checking

**Model Variants:**

- `yolo26n`: Nano (~3.5MB, fastest)
- `yolo26s`: Small (~11MB)
- `yolo26m`: Medium (~25MB, recommended) - ~100MB VRAM
- `yolo26l`: Large (~45MB)
- `yolo26x`: Extra-large (~98MB, most accurate)

**Features:**

- Supports batch inference (NEM-3377)
- 80 COCO classes by default
- Configurable confidence threshold
- Class filtering support

### `vitpose.py` (Legacy Pose Analyzer)

Original ViTPose+ Small implementation. Kept for backwards compatibility with `/pose-analyze` endpoint.

## API Endpoints

### GET /health

Returns health status of all models and VRAM usage.

```json
{
  "status": "healthy",
  "models": [
    {"name": "vehicle-segment-classification", "loaded": true, "vram_mb": 1500},
    {"name": "pet-classifier", "loaded": true, "vram_mb": 200},
    ...
  ],
  "total_vram_used_gb": 6.0,
  "device": "cuda:0",
  "cuda_available": true
}
```

### GET /models/status

Returns current model loading status from the OnDemandModelManager.

```json
{
  "vram_budget_mb": 6963.2,
  "vram_used_mb": 2500,
  "vram_available_mb": 4463.2,
  "vram_utilization_percent": 35.9,
  "loaded_models": [
    {"name": "vehicle_classifier", "vram_mb": 1500, "priority": "MEDIUM", "last_used": "..."}
  ],
  "registered_models": [...],
  "pending_loads": []
}
```

### POST /models/preload

Manually preload a model into VRAM.

```json
{ "model_name": "pose_estimator" }
```

### POST /models/unload

Manually unload a model from VRAM.

```json
{ "model_name": "person_reid" }
```

### POST /enrich

Unified enrichment endpoint for detections. Automatically loads required models.

**Request:**

```json
{
  "image": "<base64>",
  "detection_type": "person",
  "bbox": [100, 150, 300, 400],
  "is_suspicious": false,
  "frames": ["<base64>", "<base64>", ...]  // Accepted, ignored since NEM-5563 (action retired here)
}
```

**Response:**

```json
{
  "pose": {"keypoints": [...], "posture": "standing", "is_suspicious": false},
  "clothing": {"type": "casual", "is_suspicious": false},
  "demographics": {"age_range": "21-35", "gender": "male"},
  "threat": {"has_threat": false, "max_severity": "none"},
  "depth": {"estimated_distance_m": 3.5},
  "reid": {"embedding": [...], "embedding_hash": "abc123..."},
  "action": null,
  "inference_time_ms": 245.6
}
```

### POST /vehicle-classify

Classify vehicle type from cropped image.

### POST /pet-classify

Classify pet type (cat/dog).

### POST /clothing-classify

Classify clothing using FashionSigLIP zero-shot classification (57% more accurate than FashionCLIP).

### POST /depth-estimate

Estimate depth map for entire image.

### POST /object-distance

Estimate distance to object at bounding box.

### POST /pose-analyze

Analyze human pose keypoints (legacy ViTPose+ endpoint).

### POST /demographics

Estimate age range and gender for a person crop.

### POST /action-classify — RETIRED HERE

Removed with the xclip cleanup (NEM-5563): this route 404s by design.
Action classification from multi-frame clips is served by Triton
`stgcn_action` through the ai-gateway's `/enrichment/action-classify`
adapter (`ai/gateway/adapters/enrichment.py`).

### GET /readiness, GET /models/registry, GET /metrics

Readiness probe (loads without failing until all CRITICAL models are warm),
the full model registry (names, VRAM, priority, loaded state), and Prometheus
metrics.

## Environment Variables

| Variable                                       | Default                                                                                                    | Description                              |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| `HOST`                                         | `0.0.0.0`                                                                                                  | Bind address                             |
| `PORT`                                         | `8094`                                                                                                     | Listen port                              |
| `VRAM_BUDGET_GB`                               | `6.8`                                                                                                      | VRAM budget for on-demand models         |
| `VEHICLE_MODEL_PATH`                           | `/models/vehicle-segment-classification`                                                                   | Vehicle classifier path                  |
| `PET_MODEL_PATH`                               | `/models/pet-classifier`                                                                                   | Pet classifier path                      |
| `CLOTHING_MODEL_PATH`                          | `/models/fashion-clip`                                                                                     | FashionCLIP/FashionSigLIP model path     |
| `DEPTH_MODEL_PATH`                             | `/models/depth-anything-v2-tiny`                                                                           | Depth estimator path                     |
| `POSE_MODEL_PATH`                              | `/models/yolov8n-pose/yolov8n-pose.pt` (registry) / `/models/vitpose-plus-small` (`model.py` server entry) | Pose model path - two defaults, see note |
| `POSE_USE_TENSORRT`                            | `false`                                                                                                    | Enable TensorRT for pose (2-3x faster)   |
| `POSE_TENSORRT_ENGINE_PATH`                    | (auto)                                                                                                     | Custom TensorRT engine path              |
| `POSE_TENSORRT_FP16`                           | `true`                                                                                                     | Use FP16 precision for TensorRT          |
| `THREAT_MODEL_PATH`                            | `/models/threat-detection-yolov8n` (`model.py`; registry uses its `weights/best.pt`)                       | Threat detection model path              |
| `AGE_MODEL_PATH`                               | `/models/vit-age-classifier`                                                                               | Age classifier path                      |
| `GENDER_MODEL_PATH`                            | (unset - derived from age model setup)                                                                     | Gender classifier path                   |
| `REID_MODEL_PATH`                              | `/models/osnet-ain-x1-0/osnet_ain_x1_0_msmt17.pth`                                                         | OSNet ReID model path                    |
| `ACTION_MODEL_PATH`                            | (retired — no reader since NEM-5563)                                                                       | Former X-CLIP model path                 |
| `YOLO26_ENRICHMENT_MODEL_PATH`                 | `/models/yolo26m.pt`                                                                                       | YOLO26 detector model path               |
| `PET_DEVICE` / `REID_DEVICE`                   | cuda:0 (cpu fallback)                                                                                      | Force pet / re-ID model onto CPU         |
| `VEHICLE_QUANTIZED` / `DEMOGRAPHICS_QUANTIZED` | `false`                                                                                                    | Use INT8 copies (NEM-5533)               |

Note: `VITPOSE_MODEL_PATH` does not exist anywhere in the code - the
ViTPose path comes from `POSE_MODEL_PATH` (see the two-default note above).
`model.py` (standalone server) and `model_registry.py` (Model Zoo) each read
`POSE_MODEL_PATH` with different defaults.
| `HF_HOME` | `/cache/huggingface` | HuggingFace cache dir |

## Model Links

| Model                      | HuggingFace URL                                                                                                                                 | Description                                                                                                                                                                                                                                      |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| FashionSigLIP              | [Marqo/marqo-fashionSigLIP](https://huggingface.co/Marqo/marqo-fashionSigLIP)                                                                   | Zero-shot clothing classification (57% more accurate)                                                                                                                                                                                            |
| Vehicle Segment Classifier | [lxyuan/vit-base-patch16-224-vehicle-segment-classification](https://huggingface.co/lxyuan/vit-base-patch16-224-vehicle-segment-classification) | Vehicle type classification (ViT)                                                                                                                                                                                                                |
| Pet Classifier (ResNet-18) | [microsoft/resnet-18](https://huggingface.co/microsoft/resnet-18)                                                                               | Cat/dog classification                                                                                                                                                                                                                           |
| Depth Anything V2 Small    | [depth-anything/Depth-Anything-V2-Small-hf](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf)                                   | Monocular depth estimation                                                                                                                                                                                                                       |
| ViTPose+ Small             | [usyd-community/vitpose-plus-small](https://huggingface.co/usyd-community/vitpose-plus-small)                                                   | Human pose estimation (17 keypoints)                                                                                                                                                                                                             |
| YOLOv8n-pose               | [ultralytics/yolov8n-pose](https://docs.ultralytics.com/tasks/pose/)                                                                            | Human pose estimation (17 keypoints)                                                                                                                                                                                                             |
| Threat Detection           | [Subh775/Threat-Detection-YOLOv8n](https://huggingface.co/Subh775/Threat-Detection-YOLOv8n)                                                     | Weapon detection                                                                                                                                                                                                                                 |
| Age Classifier             | [nateraw/vit-age-classifier](https://huggingface.co/nateraw/vit-age-classifier)                                                                 | Age range estimation                                                                                                                                                                                                                             |
| OSNet                      | [torchreid/osnet_x0_25](https://github.com/KaiyangZhou/deep-person-reid)                                                                        | Person re-identification                                                                                                                                                                                                                         |
| X-CLIP (retired)           | [microsoft/xclip-base-patch32](https://huggingface.co/microsoft/xclip-base-patch32)                                                             | Video action recognition — retired NEM-5563; no reader remains (backend `xclip_loader.py`/`action_recognition_service.py` archived to `archive/xclip-backend-chain/` 2026-09-23, download row dropped from `ai/download_models.sh` the same day) |
| YOLO26                     | [ultralytics](https://docs.ultralytics.com/models/)                                                                                             | Secondary object detection                                                                                                                                                                                                                       |

## Backend Integration

Called by `backend/services/enrichment_client.py`:

```python
from backend.services.enrichment_client import get_enrichment_client

client = get_enrichment_client()

# Health check
health = await client.check_health()

# Classify vehicle
result = await client.classify_vehicle(image, bbox=(x1, y1, x2, y2))
print(f"Vehicle: {result.display_name} ({result.confidence:.0%})")

# Classify pet
pet = await client.classify_pet(animal_image)

# Classify clothing
clothing = await client.classify_clothing(person_image)
if clothing.is_suspicious:
    print(f"Alert: {clothing.description}")

# Analyze pose
pose = await client.analyze_pose(person_image)
if pose.alerts:
    print(f"Pose alerts: {pose.alerts}")

# Unified enrichment
enrichment = await client.enrich(
    image=person_image,
    detection_type="person",
    bbox=(x1, y1, x2, y2),
    is_suspicious=True,
)
```

Or via `EnrichmentPipeline`:

```python
from backend.services.enrichment_pipeline import EnrichmentPipeline

pipeline = EnrichmentPipeline(use_enrichment_service=True)
result = await pipeline.enrich_batch(detections, images, camera_id)
```

## Starting the Server

### Production (served by ai-gateway)

enrichment runs inside the `ai-gateway` container (Triton + FastAPI on port 8090, router prefix `/enrichment`) - there is no standalone `ai-enrichment` compose service:

```bash
podman compose -f docker-compose.prod.yml up -d ai-gateway
```

### Native (Development)

```bash
cd ai/enrichment && python model.py
```

## Testing

```bash
# Run unit tests
cd ai/enrichment && pytest tests/ -v

# Health check
curl http://localhost:8094/health

# Model status
curl http://localhost:8094/models/status

# Vehicle classification (with base64 image)
curl -X POST http://localhost:8094/vehicle-classify \
  -H "Content-Type: application/json" \
  -d '{"image": "'$(base64 -w0 vehicle.jpg)'"}'

# Unified enrichment
curl -X POST http://localhost:8094/enrich \
  -H "Content-Type: application/json" \
  -d '{"image": "'$(base64 -w0 person.jpg)'", "detection_type": "person"}'
```

## Entry Points

1. **Main service**: `model.py:app` - FastAPI application
2. **Model loading**: `model_manager.py:OnDemandModelManager` - VRAM-aware model management
3. **Registration**: `model_registry.py:create_model_registry()` - Model configuration factory
4. **Pose estimation**: `models/pose_estimator.py:PoseEstimator` - YOLOv8n-pose wrapper
5. **Threat detection**: `models/threat_detector.py:ThreatDetector` - Weapon detection
6. **Demographics**: `models/demographics.py:DemographicsEstimator` - Age/gender estimation
7. **Re-ID**: `models/person_reid.py:PersonReID` - OSNet embedding extraction
8. **Plate OCR**: `models/plate_ocr.py:PlateOCR` - PaddleOCR license plate text (NEM-5372)
9. **YOLO26 detection**: `models/yolo26_detector.py:YOLO26Detector` - Secondary object detection
10. **Backend client**: `backend/services/enrichment_client.py` - HTTP client
11. **Backend pipeline**: `backend/services/enrichment_pipeline.py` - Orchestration

## Related Documentation

For comprehensive feature documentation:

- [Video Analytics Guide](../../docs/guides/video-analytics.md) - Complete AI pipeline overview
- [Zone Configuration Guide](../../docs/guides/zone-configuration.md) - Detection zone setup and intelligence
- [Face Recognition Guide](../../docs/guides/face-recognition.md) - Face detection and person re-identification
- [Analytics API Reference](../../docs/api/analytics-endpoints.md) - Analytics endpoints documentation

## Integration with Video Analytics Features

This enrichment service powers the following video analytics capabilities:

| Feature                 | Service Component                                                                     | Documentation                                                                      |
| ----------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| **Scene Understanding** | `/enrich` endpoint with Florence-2                                                    | [Video Analytics](../../docs/guides/video-analytics.md#scene-understanding)        |
| **Person Analysis**     | Pose, demographics, clothing, re-ID                                                   | [Video Analytics](../../docs/guides/video-analytics.md#person-analysis)            |
| **Face Detection**      | Demographics + backend `face_detector.py`                                             | [Face Recognition](../../docs/guides/face-recognition.md)                          |
| **Person Re-ID**        | `PersonReID` model                                                                    | [Face Recognition](../../docs/guides/face-recognition.md#person-re-identification) |
| **Vehicle Analysis**    | Vehicle classifier + plate detector                                                   | [Video Analytics](../../docs/guides/video-analytics.md#vehicle-analysis)           |
| **License Plate OCR**   | `PlateOCR` model with PaddleOCR                                                       | [Video Analytics](../../docs/guides/video-analytics.md#vehicle-analysis)           |
| **Threat Detection**    | `ThreatDetector` model (CRITICAL priority)                                            | [Video Analytics](../../docs/guides/video-analytics.md#threat-detection)           |
| **Action Recognition**  | RETIRED here (NEM-5563) — Triton `stgcn_action` via the ai-gateway `/action-classify` | [Video Analytics](../../docs/guides/video-analytics.md#person-analysis)            |
