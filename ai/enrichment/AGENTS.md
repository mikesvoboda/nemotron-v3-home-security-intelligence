# ai/enrichment - Combined Enrichment Service

HTTP server hosting multiple classification models for detection enrichment.

## Purpose

Provides vehicle type classification, pet classification, and clothing
classification as a single containerized service to reduce VRAM fragmentation
and simplify deployment.

## Port

- **8094** (configurable via `PORT` environment variable)

## Expected VRAM

- ~2.5GB total
  - Vehicle Segment Classification (ResNet-50): ~1.5GB
  - Pet Classifier (ResNet-18): ~200MB
  - FashionCLIP: ~800MB

## Key Files

| File               | Purpose                                        |
| ------------------ | ---------------------------------------------- |
| `model.py`         | FastAPI app with all classifiers and endpoints |
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
    { "name": "fashion-clip", "loaded": true, "vram_mb": 800 }
  ],
  "total_vram_used_gb": 2.5,
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

## Environment Variables

| Variable              | Default                                  | Description             |
| --------------------- | ---------------------------------------- | ----------------------- |
| `HOST`                | `0.0.0.0`                                | Bind address            |
| `PORT`                | `8094`                                   | Listen port             |
| `VEHICLE_MODEL_PATH`  | `/models/vehicle-segment-classification` | Vehicle classifier path |
| `PET_MODEL_PATH`      | `/models/pet-classifier`                 | Pet classifier path     |
| `CLOTHING_MODEL_PATH` | `/models/fashion-clip`                   | FashionCLIP model path  |
| `HF_HOME`             | `/cache/huggingface`                     | HuggingFace cache dir   |

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
