# Combined Enrichment Service

## Purpose

HTTP server hosting multiple classification models for enriching RT-DETRv2 detections with additional attributes. Consolidates vehicle, pet, clothing, depth, and pose analysis into a single containerized service to reduce VRAM fragmentation and simplify deployment.

## Port and Resources

- **Port**: 8094 (configurable via `PORT`)
- **Expected VRAM**: ~2.65 GB total (per model.py docstring)

| Model                  | VRAM    | Purpose                         |
| ---------------------- | ------- | ------------------------------- |
| Vehicle Classification | ~1.5 GB | Vehicle type (car, truck, etc.) |
| Pet Classifier         | ~200 MB | Cat/dog classification          |
| FashionCLIP            | ~800 MB | Clothing attributes             |
| Depth Anything V2      | ~150 MB | Distance estimation             |

**Note**: ViTPose+ Small is loaded on-demand via `vitpose.py` module.

## Directory Contents

```
ai/enrichment/
├── AGENTS.md          # This file
├── Dockerfile         # Container build (PyTorch + CUDA 12.4)
├── model.py           # FastAPI server with all classifiers
├── vitpose.py         # ViTPose+ pose analyzer module
└── requirements.txt   # Python dependencies
```

## Key Files

### `model.py` (Main Server)

FastAPI server hosting all classification models.

**Classifier Classes:**

| Class                | Model          | Purpose                           |
| -------------------- | -------------- | --------------------------------- |
| `VehicleClassifier`  | ResNet-50      | Vehicle type classification       |
| `PetClassifier`      | ResNet-18      | Cat/dog classification            |
| `ClothingClassifier` | FashionCLIP    | Zero-shot clothing classification |
| `DepthEstimator`     | Depth Anything | Monocular depth estimation        |

**Vehicle Classes:**

```python
VEHICLE_SEGMENT_CLASSES = [
    "articulated_truck", "background", "bicycle", "bus", "car",
    "motorcycle", "non_motorized_vehicle", "pedestrian",
    "pickup_truck", "single_unit_truck", "work_van"
]
```

**Clothing Prompts (Security-Focused):**

```python
SECURITY_CLOTHING_PROMPTS = [
    "person wearing dark hoodie",
    "person wearing face mask",
    "person wearing ski mask or balaclava",
    "delivery uniform", "Amazon delivery vest", "FedEx uniform",
    "UPS uniform", "USPS postal worker uniform",
    "casual clothing", "business attire or suit", ...
]
```

### `vitpose.py` (Pose Analyzer)

ViTPose+ Small human pose estimation module.

**Class: `PoseAnalyzer`**

```python
def load_model(self) -> None:
    """Load ViTPose+ via VitPoseForPoseEstimation.from_pretrained()"""

def analyze(self, image: Image.Image, min_confidence: float = 0.3) -> dict:
    """Returns keypoints, posture classification, and security alerts"""
```

**COCO Keypoints (17):**

```python
COCO_KEYPOINT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle"
]
```

**Posture Classifications:**

- `standing`, `walking`, `running`, `sitting`, `crouching`, `lying_down`, `unknown`

**Security Alerts:**

- `crouching` - Potential hiding/break-in behavior
- `lying_down` - Possible medical emergency
- `hands_raised` - Potential surrender/robbery scenario
- `fighting_stance` - Aggressive posture

### `Dockerfile`

Container build configuration:

- **Base image**: `pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime`
- **Non-root user**: `enrichment` for security
- **Health check**: 180s start period (loading all models)
- **HuggingFace cache**: `/cache/huggingface`

### `requirements.txt`

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6
transformers>=4.35.0
open_clip_torch>=2.24.0    # FashionCLIP
pillow>=10.0.0
numpy>=1.24.0
pydantic>=2.4.0
nvidia-ml-py>=12.560.30    # GPU monitoring
safetensors>=0.4.0
```

**Note**: torch and torchvision come from the base Docker image (pytorch/pytorch:2.4.0-cuda12.4).

## API Endpoints

### GET /health

Returns health status of all models.

```json
{
  "status": "healthy",
  "models": [
    {
      "name": "vehicle-segment-classification",
      "loaded": true,
      "vram_mb": 1500
    },
    { "name": "pet-classifier", "loaded": true, "vram_mb": 200 },
    { "name": "fashion-clip", "loaded": true, "vram_mb": 800 },
    { "name": "depth-anything-v2-small", "loaded": true, "vram_mb": 150 }
  ],
  "total_vram_used_gb": 6.0,
  "device": "cuda:0",
  "cuda_available": true
}
```

### POST /vehicle-classify

Classify vehicle type from cropped image.

**Request:**

```json
{
  "image": "<base64>",
  "bbox": [x1, y1, x2, y2]  // optional crop
}
```

**Response:**

```json
{
  "vehicle_type": "pickup_truck",
  "display_name": "pickup truck",
  "confidence": 0.92,
  "is_commercial": false,
  "all_scores": { "pickup_truck": 0.92, "car": 0.05, "work_van": 0.02 },
  "inference_time_ms": 45.2
}
```

### POST /pet-classify

Classify pet type (cat/dog).

**Request:**

```json
{
  "image": "<base64>",
  "bbox": [x1, y1, x2, y2]  // optional crop
}
```

**Response:**

```json
{
  "pet_type": "dog",
  "breed": "unknown",
  "confidence": 0.98,
  "is_household_pet": true,
  "inference_time_ms": 22.1
}
```

### POST /clothing-classify

Classify clothing using FashionCLIP zero-shot classification.

**Request:**

```json
{
  "image": "<base64>",
  "bbox": [x1, y1, x2, y2]  // optional crop
}
```

**Response:**

```json
{
  "clothing_type": "hoodie",
  "color": "dark",
  "style": "suspicious",
  "confidence": 0.85,
  "top_category": "person wearing dark hoodie",
  "description": "Alert: dark hoodie",
  "is_suspicious": true,
  "is_service_uniform": false,
  "inference_time_ms": 68.4
}
```

### POST /depth-estimate

Estimate depth map for entire image.

**Request:**

```json
{ "image": "<base64>" }
```

**Response:**

```json
{
  "depth_map_base64": "<base64-png>",
  "min_depth": 0.0,
  "max_depth": 1.0,
  "mean_depth": 0.45,
  "inference_time_ms": 85.3
}
```

### POST /object-distance

Estimate distance to object at bounding box.

**Request:**

```json
{
  "image": "<base64>",
  "bbox": [100, 150, 300, 400],
  "method": "center" // or "mean", "median", "min"
}
```

**Response:**

```json
{
  "estimated_distance_m": 3.5,
  "relative_depth": 0.35,
  "proximity_label": "close",
  "inference_time_ms": 90.2
}
```

### POST /pose-analyze

Analyze human pose keypoints.

**Request:**

```json
{
  "image": "<base64>",
  "bbox": [x1, y1, x2, y2],  // optional crop
  "min_confidence": 0.3
}
```

**Response:**

```json
{
  "keypoints": [
    {"name": "nose", "x": 0.5, "y": 0.1, "confidence": 0.95},
    {"name": "left_shoulder", "x": 0.4, "y": 0.25, "confidence": 0.92},
    ...
  ],
  "posture": "standing",
  "alerts": [],
  "inference_time_ms": 35.6
}
```

## Environment Variables

| Variable              | Default                                  | Description             |
| --------------------- | ---------------------------------------- | ----------------------- |
| `HOST`                | `0.0.0.0`                                | Bind address            |
| `PORT`                | `8094`                                   | Listen port             |
| `VEHICLE_MODEL_PATH`  | `/models/vehicle-segment-classification` | Vehicle classifier path |
| `PET_MODEL_PATH`      | `/models/pet-classifier`                 | Pet classifier path     |
| `CLOTHING_MODEL_PATH` | `/models/fashion-clip`                   | FashionCLIP model path  |
| `DEPTH_MODEL_PATH`    | `/models/depth-anything-v2-small`        | Depth estimator path    |
| `VITPOSE_MODEL_PATH`  | `/models/vitpose-plus-small`             | ViTPose+ model path     |
| `HF_HOME`             | `/cache/huggingface`                     | HuggingFace cache dir   |

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
```

Or via `EnrichmentPipeline`:

```python
from backend.services.enrichment_pipeline import EnrichmentPipeline

pipeline = EnrichmentPipeline(use_enrichment_service=True)
result = await pipeline.enrich_batch(detections, images, camera_id)
```

## Starting the Server

### Container (Production)

```bash
docker compose -f docker-compose.prod.yml up ai-enrichment
```

### Native (Development)

```bash
cd ai/enrichment && python model.py
```

## Testing

```bash
# Health check
curl http://localhost:8094/health

# Vehicle classification (with base64 image)
curl -X POST http://localhost:8094/vehicle-classify \
  -H "Content-Type: application/json" \
  -d '{"image": "'$(base64 -w0 vehicle.jpg)'"}'

# Clothing classification
curl -X POST http://localhost:8094/clothing-classify \
  -H "Content-Type: application/json" \
  -d '{"image": "'$(base64 -w0 person.jpg)'"}'
```

## Entry Points

1. **Main server**: `model.py` - All classifiers and endpoints
2. **Pose analyzer**: `vitpose.py` - ViTPose+ module
3. **Dockerfile**: Container build configuration
4. **Backend client**: `backend/services/enrichment_client.py`
5. **Backend pipeline**: `backend/services/enrichment_pipeline.py`
