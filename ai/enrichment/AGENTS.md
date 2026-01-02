# ai/enrichment - Combined Enrichment Service

HTTP server hosting multiple classification models for detection enrichment.

## Purpose

Provides vehicle type classification, pet classification, clothing
classification, and action recognition as a single containerized service to
reduce VRAM fragmentation and simplify deployment.

## Port

- **8094** (configurable via `PORT` environment variable)

## Expected VRAM

- ~6GB total (with all models loaded)
  - Vehicle Segment Classification (ResNet-50): ~1.5GB
  - Pet Classifier (ResNet-18): ~200MB
  - FashionCLIP: ~800MB
  - X-CLIP Action Classifier: ~2GB
  - ViTPose+ Small: ~1.5GB

## Key Files

| File               | Purpose                                        |
| ------------------ | ---------------------------------------------- |
| `model.py`         | FastAPI app with all classifiers and endpoints |
| `vitpose.py`       | ViTPose+ pose analyzer module                  |
| `Dockerfile`       | Container build definition                     |
| `requirements.txt` | Python dependencies                            |

## Models Hosted

### 1. Vehicle Segment Classification (ResNet-50)

- **Classes:** articulated_truck, bicycle, bus, car, motorcycle, pickup_truck, etc.
- **Model path:** `/models/vehicle-segment-classification`
- **Endpoint:** `POST /vehicle-classify`

### 2. Pet Classifier (ResNet-18)

- **Classes:** cat, dog
- **Model path:** `/models/pet-classifier`
- **Endpoint:** `POST /pet-classify`

### 3. FashionCLIP

- **Zero-shot clothing classification**
- **Security-focused prompts:** dark hoodie, face mask, service uniforms, etc.
- **Model path:** `/models/fashion-clip`
- **Endpoint:** `POST /clothing-classify`

### 4. X-CLIP Action Classifier

- **Temporal action recognition from video frames**
- **Security-focused actions:** loitering, running away, suspicious behavior, etc.
- **Model path:** `/models/xclip-base`
- **Endpoint:** `POST /action-classify`

### 5. ViTPose+ Small (Human Pose Estimation)

- **17 COCO keypoints detection**
- **Posture classification:** standing, walking, sitting, crouching, lying_down, running
- **Security alerts:** crouching (hiding), lying_down (medical emergency), hands_raised (robbery), fighting_stance
- **Model path:** `/models/vitpose-plus-small`
- **Endpoint:** `POST /pose-analyze`

## API Endpoints

### GET /health

Health check with model status and VRAM usage.

Response:

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
    { "name": "xclip-action", "loaded": true, "vram_mb": 2000 },
    { "name": "vitpose-plus-small", "loaded": true, "vram_mb": 1500 }
  ],
  "total_vram_used_gb": 6.0,
  "device": "cuda:0",
  "cuda_available": true
}
```

### POST /vehicle-classify

Classify vehicle type and attributes.

Request:

```json
{
  "image": "<base64>",
  "bbox": [x1, y1, x2, y2]  // optional
}
```

Response:

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

Request:

```json
{
  "image": "<base64>",
  "bbox": [x1, y1, x2, y2]  // optional
}
```

Response:

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

Classify clothing attributes using FashionCLIP.

Request:

```json
{
  "image": "<base64>",
  "bbox": [x1, y1, x2, y2]  // optional
}
```

Response:

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

### POST /action-classify

Classify action from a sequence of video frames using X-CLIP.

Request:

```json
{
  "frames": ["<base64_frame1>", "<base64_frame2>", ...],  // 8 frames optimal
  "labels": ["custom action 1", "custom action 2"]  // optional, defaults to security prompts
}
```

Response:

```json
{
  "action": "a person loitering",
  "confidence": 0.78,
  "is_suspicious": true,
  "risk_weight": 0.7,
  "all_scores": {
    "a person loitering": 0.78,
    "a person walking normally": 0.12,
    "a person looking around suspiciously": 0.05
  },
  "inference_time_ms": 245.6
}
```

Security Action Categories:

- **Suspicious:** loitering, running away, looking around suspiciously, trying door handle, checking windows, hiding near bushes, taking photos, vandalizing, breaking in
- **Normal:** walking normally, delivering package, knocking on door, ringing doorbell, leaving package

### POST /pose-analyze

Analyze human pose keypoints using ViTPose+.

Request:

```json
{
  "image": "<base64>",
  "bbox": [x1, y1, x2, y2],  // optional - crop to person
  "min_confidence": 0.3  // optional - keypoint confidence threshold
}
```

Response:

```json
{
  "keypoints": [
    { "name": "nose", "x": 0.5, "y": 0.1, "confidence": 0.95 },
    { "name": "left_shoulder", "x": 0.4, "y": 0.25, "confidence": 0.92 },
    ...
  ],
  "posture": "standing",
  "alerts": [],
  "inference_time_ms": 35.6
}
```

Posture Classifications:

- **Normal:** standing, walking, running
- **Concerning:** sitting, crouching, lying_down
- **Unknown:** insufficient keypoints detected

Security Alerts:

- **crouching:** Potential hiding or break-in behavior
- **lying_down:** Possible medical emergency or unconscious person
- **hands_raised:** Potential surrender or robbery scenario
- **fighting_stance:** Aggressive posture with arms extended

## Environment Variables

| Variable              | Default                                  | Description              |
| --------------------- | ---------------------------------------- | ------------------------ |
| `HOST`                | `0.0.0.0`                                | Bind address             |
| `PORT`                | `8094`                                   | Listen port              |
| `VEHICLE_MODEL_PATH`  | `/models/vehicle-segment-classification` | Vehicle classifier path  |
| `PET_MODEL_PATH`      | `/models/pet-classifier`                 | Pet classifier path      |
| `CLOTHING_MODEL_PATH` | `/models/fashion-clip`                   | FashionCLIP model path   |
| `ACTION_MODEL_PATH`   | `/models/xclip-base`                     | X-CLIP action model path |
| `VITPOSE_MODEL_PATH`  | `/models/vitpose-plus-small`             | ViTPose+ model path      |
| `HF_HOME`             | `/cache/huggingface`                     | HuggingFace cache dir    |

## Backend Integration

The backend can use this service via `EnrichmentClient`:

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
print(f"Pet: {pet.pet_type} ({pet.confidence:.0%})")

# Classify clothing
clothing = await client.classify_clothing(person_image)
print(f"Clothing: {clothing.description}")

# Classify action from video frames
frames = [frame1, frame2, frame3, ...]  # PIL Images
action = await client.classify_action(frames)
print(f"Action: {action.action} (suspicious: {action.is_suspicious})")

# Analyze pose
pose = await client.analyze_pose(person_image)
print(f"Posture: {pose.posture}")
if pose.has_security_alerts():
    print(f"Alerts: {pose.alerts}")
```

Or via `EnrichmentPipeline` with `use_enrichment_service=True`:

```python
from backend.services.enrichment_pipeline import EnrichmentPipeline

pipeline = EnrichmentPipeline(use_enrichment_service=True)
result = await pipeline.enrich_batch(detections, images, camera_id)
```

## Docker Compose

See `docker-compose.prod.yml` for the `ai-enrichment` service definition.

Volumes mount model directories from `/export/ai_models/model-zoo/`.

## Testing

```bash
# Build and start
podman-compose -f docker-compose.prod.yml build ai-enrichment
podman-compose -f docker-compose.prod.yml up -d ai-enrichment

# Health check
curl http://localhost:8094/health

# Test classification (requires base64 image)
curl -X POST http://localhost:8094/vehicle-classify \
  -H "Content-Type: application/json" \
  -d '{"image": "<base64_encoded_image>"}'
```

## Related Files

- `backend/services/enrichment_client.py` - HTTP client
- `backend/services/enrichment_pipeline.py` - Pipeline integration
- `backend/core/config.py` - `enrichment_url` setting
- `docker-compose.prod.yml` - Service definition
