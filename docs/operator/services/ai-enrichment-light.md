# Enrichment Light (`/enrich-lt`) — inside ai-gateway

> [!IMPORTANT] > `ai-enrichment-light` is **no longer a standalone container**. The lightweight models
> (pose, threat, person ReID, pet, depth) run as Triton models inside the single
> `ai-gateway` container and are served by the **`/enrich-lt` router** on the gateway's
> port (`${AI_GATEWAY_PORT:-8090}`). The old service and its port 8096 no longer exist;
> the `ai/enrichment-light/` directory survives only as the legacy server image that CI
> still builds. The heavy counterparts live on the `/enrichment` router in the same
> container.

## Overview

| Property          | Value                                                                                                                                                              |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Container**     | `ai-gateway` (Triton + FastAPI)                                                                                                                                    |
| **Router**        | `/enrich-lt` on port 8090                                                                                                                                          |
| **Source**        | `ai/gateway/adapters/enrichment_light.py`                                                                                                                          |
| **GPU**           | `GPU_AI_SERVICES` (gateway-wide, default 1)                                                                                                                        |
| **Model weights** | `${AI_MODELS_PATH:-/export/ai_models}/model-zoo/` (manifest: `models.yml`)                                                                                         |
| **Preload list**  | `ENRICHMENT_LIGHT_PRELOAD_MODELS` env var — values use the _config_ names: `pose_estimator`, `threat_detector`, `person_reid`, `pet_classifier`, `depth_estimator` |

## Models Hosted

Triton model names in parentheses — this is what health checks and metrics use:

| Model (`triton_name`)           | VRAM (est.) | Purpose                    | Security Value                                  |
| ------------------------------- | ----------- | -------------------------- | ----------------------------------------------- |
| **YOLOv8n-pose** (`pose`)       | ~300MB      | Human pose estimation      | Detect suspicious postures (crouching, running) |
| **Threat Detector** (`threat`)  | ~400MB      | Weapon detection           | Identify knives, guns, bats, etc.               |
| **OSNet** (`reid`)              | ~100MB      | Person re-identification   | Track individuals across cameras                |
| **Pet Classifier** (`pet`)      | ~200MB      | Cat/dog classification     | Reduce false positives from pets                |
| **Depth Anything V2** (`depth`) | ~150MB      | Monocular depth estimation | Distance context for detections                 |

These run inside the gateway's shared VRAM budget (~4GB base, ~6GB peak) — there is no
separate 4GB-GPU budget any more. Triton runs with `--model-control-mode=none`
(`ai/gateway/entrypoint.sh`), so every model in the repository is loaded at startup.

## API Endpoints

All paths are prefixed with `/enrich-lt` on the gateway: `POST
http://<gateway>:8090/enrich-lt/<endpoint>`.

The image-carrying endpoints (`/pose-analyze`, `/threat-detect`, `/person-reid`,
`/pet-classify`) take a JSON body with a base64 image **plus a `bbox`** (crop region) —
`{"image_base64": "...", "bbox": {"x": 0, "y": 0, "width": 100, "height": 200}}` (a
`[x1, y1, x2, y2]` list also works). Only `/depth-estimate` takes the full image
(`{"image_base64": "..."}`).

### Health Check

```bash
curl -s http://localhost:8090/enrich-lt/health | jq
```

**Response** (per-model Triton readiness):

```json
{
  "status": "healthy",
  "models": {
    "pose": true,
    "threat": true,
    "reid": true,
    "pet": true,
    "depth": true
  }
}
```

`status` is `"degraded"` when any model is not ready.

### Pose Analysis

```http
POST /enrich-lt/pose-analyze
Content-Type: application/json

{ "image_base64": "<base64-crop>", "bbox": { "x": 100, "y": 80, "width": 120, "height": 300 } }
```

Returns `keypoints`, a derived `posture` (e.g. `standing`, `crouching`), `alerts`, and
`inference_time_ms`.

### Threat Detection

```http
POST /enrich-lt/threat-detect
```

Returns `threats_detected[]` (class, confidence, bbox), `is_threat`, `max_confidence`.

### Person Re-identification

```http
POST /enrich-lt/person-reid
```

Returns the embedding vector and `inference_time_ms`.

### Pet Classification

```http
POST /enrich-lt/pet-classify
```

Returns `pet_type`, `confidence`, and household-pet matching.

### Depth Estimation

```http
POST /enrich-lt/depth-estimate
Content-Type: application/json

{ "image_base64": "<base64-full-image>" }
```

Returns normalized depth statistics (min/max/mean) for the frame.

### Prometheus Metrics

```bash
curl -s http://localhost:8090/metrics      # gateway + merged Triton metrics
curl -s http://localhost:8002/metrics      # Triton native (per-model)
```

Gateway-level metrics emitted per call: `hsi_ai_inference_duration_seconds{service,
endpoint}` (histogram) and `hsi_ai_inference_errors_total{service, endpoint}` (counter);
Triton adds `nv_inference_*` per model. Prometheus scrapes both via the `triton-metrics`
job. The retired `enrichment_light_*` metrics no longer exist.

## Configuration

### Tier Routing (which service handles which model)

```bash
# .env — route a model to the light or heavy router
ENRICHMENT_POSE_SERVICE=light      # Default: light
ENRICHMENT_THREAT_SERVICE=light    # Default: light
ENRICHMENT_REID_SERVICE=light      # Default: light
ENRICHMENT_PET_SERVICE=light       # Default: light
ENRICHMENT_DEPTH_SERVICE=light     # Default: light
```

The backend's `enrichment_client.py` resolves each model's URL from these values
against `ENRICHMENT_LIGHT_URL` (`http://ai-gateway:8090/enrich-lt` in compose) or
`ENRICHMENT_URL` (`…/enrichment`).

### Preload

```bash
# Models loaded eagerly at gateway startup instead of on demand (comma-separated)
ENRICHMENT_LIGHT_PRELOAD_MODELS=pose_estimator,threat_detector,person_reid,pet_classifier,depth_estimator
```

### Quantization / device overrides

Per-model quantization toggles (`VEHICLE_QUANTIZED`, `DEMOGRAPHICS_QUANTIZED`) and the
`device_env_var` entries in `models.yml` (e.g. `POSE_DEVICE`) are applied by
`ai/gateway/entrypoint.sh` and `patch_triton_configs.py` at container start — see
[GPU Setup](../gpu-setup.md).

## Backend Integration

```python
# backend/services/enrichment_client.py (simplified)
light_url = settings.enrichment_light_url          # ENRICHMENT_LIGHT_URL
if settings.enrichment_pose_service == "light":
    await client.post(f"{light_url}/pose-analyze", json={...})
else:
    await client.post(f"{settings.enrichment_url}/pose-analyze", json={...})
```

## Health Checks (compose)

The router has no separate healthcheck — container health is the gateway's aggregate
check:

```yaml
# ai-gateway (docker-compose.prod.yml)
healthcheck:
  test: ['CMD', 'curl', '-f', 'http://localhost:8090/health']
  start_period: 180s # Triton initialises 14 models (comment in compose still says 13, stale since NEM-5563)
```

`/health` reports `healthy` only when Triton's server is ready **and** every model is
ready.

## Light vs Heavy Enrichment (both on :8090)

| Aspect        | `/enrich-lt`                           | `/enrichment`                                                          |
| ------------- | -------------------------------------- | ---------------------------------------------------------------------- |
| **Models**    | pose, threat, reid, pet, depth         | vehicle, clothing, demographics, action (+ pose/pet/depth also served) |
| **Character** | Small, efficient                       | Larger transformers                                                    |
| **GPU**       | shared gateway GPU (`GPU_AI_SERVICES`) | shared gateway GPU                                                     |

## Troubleshooting

```bash
# Which models are ready?
curl -s http://localhost:8090/enrich-lt/health | jq

# Triton's view of one model
podman exec ai-gateway curl -s http://localhost:8002/v2/models/pose | jq '.state,.ready'

# Model-load failures show up first in the gateway log
podman logs ai-gateway 2>&1 | grep -iE "pose|threat|reid|pet|depth|error"

# Weights present on the host?
ls /export/ai_models/model-zoo/   # yolov8n-pose/, osnet-ain-x1-0/, threat-detection*/, pet-classifier/, depth-anything-v2-tiny/
```

If a model reports `degraded`, run `./ai/download_models.sh` (manifest `models.yml`) and
restart the gateway: `podman compose -f docker-compose.prod.yml restart ai-gateway`.

## Related Documentation

- [AI Orchestration Overview](../../architecture/ai-orchestration/README.md)
- [Model Zoo](../../architecture/ai-orchestration/model-zoo.md)
- [GPU Memory Limits](../../deployment/gpu-memory-limits.md)
- [Enrichment Pipeline](../../architecture/ai-orchestration/enrichment-pipeline.md)
