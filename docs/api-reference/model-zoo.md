---
title: Model Zoo API
description: REST API endpoints for Model Zoo status and latency monitoring
source_refs:
  - backend/api/routes/system.py
  - backend/api/schemas/system.py
  - backend/services/model_zoo.py
---

# Model Zoo API

The Model Zoo API provides endpoints for monitoring the status and performance of AI models used in the enrichment pipeline. The Model Zoo contains 18+ vision models that are loaded on-demand during batch processing to extract additional context from detections.

## Overview

The Model Zoo system manages a collection of specialized AI models that enhance detection results:

- **License plate detection and OCR** - Identify and read vehicle plates
- **Face detection** - Detect faces for person tracking
- **Vehicle classification** - Detailed vehicle type identification
- **Clothing analysis** - Fashion classification and segmentation
- **Violence detection** - Safety monitoring
- **Pose estimation** - Human activity recognition
- **Depth estimation** - Distance context for detections
- **Pet classification** - False positive reduction

**VRAM Budget**: The Model Zoo has a dedicated VRAM budget of 1650 MB, separate from the RT-DETRv2 detector (~650 MB) and Nemotron LLM (~21,700 MB) allocations.

**Loading Strategy**: Models are loaded sequentially (one at a time) to prevent VRAM fragmentation and ensure stable operation.

## Endpoints Overview

| Method | Endpoint                                | Description                              |
| ------ | --------------------------------------- | ---------------------------------------- |
| GET    | `/api/system/models`                    | Get Model Zoo registry with all models   |
| GET    | `/api/system/models/{model_name}`       | Get status of a specific model           |
| GET    | `/api/system/model-zoo/status`          | Get compact status for UI display        |
| GET    | `/api/system/model-zoo/latency/history` | Get latency history for a specific model |

---

## GET /api/system/models

Get the current status of all models in the Model Zoo.

**Source:** [`get_models`](../../backend/api/routes/system.py:2523)

**Response:** `200 OK`

```json
{
  "vram_budget_mb": 1650,
  "vram_used_mb": 300,
  "vram_available_mb": 1350,
  "models": [
    {
      "name": "yolo11-license-plate",
      "display_name": "YOLO11 License Plate",
      "vram_mb": 300,
      "status": "loaded",
      "category": "detection",
      "enabled": true,
      "available": true,
      "path": "/models/model-zoo/yolo11-license-plate/license-plate-finetune-v1n.pt",
      "load_count": 1
    },
    {
      "name": "yolo11-face",
      "display_name": "YOLO11 Face Detection",
      "vram_mb": 200,
      "status": "unloaded",
      "category": "detection",
      "enabled": true,
      "available": false,
      "path": "/models/model-zoo/yolo11-face-detection/model.pt",
      "load_count": 0
    }
  ],
  "loading_strategy": "sequential",
  "max_concurrent_models": 1
}
```

**Response Fields:**

| Field                   | Type    | Description                                            |
| ----------------------- | ------- | ------------------------------------------------------ |
| `vram_budget_mb`        | integer | Total VRAM budget for Model Zoo (excludes core models) |
| `vram_used_mb`          | integer | Currently used VRAM by loaded models                   |
| `vram_available_mb`     | integer | Available VRAM for loading additional models           |
| `models`                | array   | List of all models in the registry                     |
| `loading_strategy`      | string  | Model loading strategy (always "sequential")           |
| `max_concurrent_models` | integer | Maximum models loaded at once (always 1)               |

**Model Status Values:**

| Status     | Description                                   |
| ---------- | --------------------------------------------- |
| `loaded`   | Model is currently loaded in GPU memory       |
| `unloaded` | Model is not loaded but available for loading |
| `disabled` | Model is disabled and will not be loaded      |
| `loading`  | Model is currently being loaded               |
| `error`    | Model failed to load due to an error          |

**Model Categories:**

| Category             | Models                                                                                                   |
| -------------------- | -------------------------------------------------------------------------------------------------------- |
| `detection`          | yolo11-license-plate, yolo11-face, yolo-world-s, vehicle-damage-detection                                |
| `classification`     | violence-detection, weather-classification, fashion-clip, vehicle-segment-classification, pet-classifier |
| `segmentation`       | segformer-b2-clothes                                                                                     |
| `pose`               | vitpose-small                                                                                            |
| `depth-estimation`   | depth-anything-v2-small                                                                                  |
| `embedding`          | clip-vit-l                                                                                               |
| `ocr`                | paddleocr                                                                                                |
| `action-recognition` | xclip-base                                                                                               |

**Example Request:**

```bash
curl http://localhost:8000/api/system/models
```

---

## GET /api/system/models/{model_name}

Get detailed status information for a specific model.

**Source:** [`get_model`](../../backend/api/routes/system.py:2581)

**Parameters:**

| Name         | Type   | In   | Required | Description                                     |
| ------------ | ------ | ---- | -------- | ----------------------------------------------- |
| `model_name` | string | path | Yes      | Model identifier (e.g., `yolo11-license-plate`) |

**Response:** `200 OK`

```json
{
  "name": "yolo11-license-plate",
  "display_name": "YOLO11 License Plate",
  "vram_mb": 300,
  "status": "unloaded",
  "category": "detection",
  "enabled": true,
  "available": false,
  "path": "/models/model-zoo/yolo11-license-plate/license-plate-finetune-v1n.pt",
  "load_count": 0
}
```

**Response Fields:**

| Field          | Type    | Description                                              |
| -------------- | ------- | -------------------------------------------------------- |
| `name`         | string  | Unique model identifier                                  |
| `display_name` | string  | Human-readable display name                              |
| `vram_mb`      | integer | Estimated VRAM usage in megabytes when loaded            |
| `status`       | string  | Current loading status                                   |
| `category`     | string  | Model category (detection, classification, etc.)         |
| `enabled`      | boolean | Whether the model is enabled for use                     |
| `available`    | boolean | Whether model has been successfully loaded at least once |
| `path`         | string  | HuggingFace repo path or local file path                 |
| `load_count`   | integer | Current reference count (0 if not loaded)                |

**Errors:**

| Code | Description                 |
| ---- | --------------------------- |
| 404  | Model not found in registry |

**Example Request:**

```bash
curl http://localhost:8000/api/system/models/yolo11-license-plate
```

---

## GET /api/system/model-zoo/status

Get compact status information for all Model Zoo models, optimized for UI display.

**Source:** [`get_model_zoo_status`](../../backend/api/routes/system.py:2664)

**Response:** `200 OK`

```json
{
  "models": [
    {
      "name": "yolo11-license-plate",
      "display_name": "YOLO11 License Plate",
      "category": "Detection",
      "status": "unloaded",
      "vram_mb": 300,
      "last_used_at": null,
      "enabled": true
    },
    {
      "name": "violence-detection",
      "display_name": "Violence Detection",
      "category": "Classification",
      "status": "loaded",
      "vram_mb": 500,
      "last_used_at": "2026-01-04T10:30:00Z",
      "enabled": true
    },
    {
      "name": "florence-2-large",
      "display_name": "Florence 2 Large",
      "category": "Other",
      "status": "disabled",
      "vram_mb": 1200,
      "last_used_at": null,
      "enabled": false
    }
  ],
  "total_models": 18,
  "loaded_count": 1,
  "disabled_count": 3,
  "vram_budget_mb": 1650,
  "vram_used_mb": 500,
  "timestamp": "2026-01-04T10:30:00Z"
}
```

**Response Fields:**

| Field            | Type     | Description                                    |
| ---------------- | -------- | ---------------------------------------------- |
| `models`         | array    | List of all Model Zoo models with their status |
| `total_models`   | integer  | Total number of models in the registry         |
| `loaded_count`   | integer  | Number of currently loaded models              |
| `disabled_count` | integer  | Number of disabled models                      |
| `vram_budget_mb` | integer  | Total VRAM budget for Model Zoo                |
| `vram_used_mb`   | integer  | Currently used VRAM                            |
| `timestamp`      | datetime | Timestamp of status snapshot                   |

**Model Item Fields:**

| Field          | Type     | Description                                   |
| -------------- | -------- | --------------------------------------------- |
| `name`         | string   | Model identifier                              |
| `display_name` | string   | Human-readable display name                   |
| `category`     | string   | UI category (Detection, Classification, etc.) |
| `status`       | string   | Current status: loaded, unloaded, disabled    |
| `vram_mb`      | integer  | VRAM usage when loaded                        |
| `last_used_at` | datetime | Last usage timestamp (null if never used)     |
| `enabled`      | boolean  | Whether the model is enabled                  |

**UI Categories (sorted order):**

1. Detection
2. Classification
3. Segmentation
4. Pose
5. Depth
6. Embedding
7. OCR
8. Action Recognition
9. Other (disabled models appear last)

**Example Request:**

```bash
curl http://localhost:8000/api/system/model-zoo/status
```

---

## GET /api/system/model-zoo/latency/history

Get latency history for a specific Model Zoo model. Returns time-series data for charting.

**Source:** [`get_model_zoo_latency_history`](../../backend/api/routes/system.py:2743)

**Parameters:**

| Name             | Type    | In    | Required | Description                                        |
| ---------------- | ------- | ----- | -------- | -------------------------------------------------- |
| `model`          | string  | query | Yes      | Model name (e.g., `yolo11-license-plate`)          |
| `since`          | integer | query | No       | Minutes of history to return (1-1440, default: 60) |
| `bucket_seconds` | integer | query | No       | Bucket size in seconds (10-3600, default: 60)      |

**Response:** `200 OK`

```json
{
  "model_name": "yolo11-license-plate",
  "display_name": "YOLO11 License Plate",
  "snapshots": [
    {
      "timestamp": "2026-01-04T10:00:00+00:00",
      "stats": {
        "avg_ms": 45.0,
        "p50_ms": 42.0,
        "p95_ms": 68.0,
        "sample_count": 15
      }
    },
    {
      "timestamp": "2026-01-04T10:01:00+00:00",
      "stats": {
        "avg_ms": 48.0,
        "p50_ms": 45.0,
        "p95_ms": 72.0,
        "sample_count": 12
      }
    },
    {
      "timestamp": "2026-01-04T10:02:00+00:00",
      "stats": null
    }
  ],
  "window_minutes": 60,
  "bucket_seconds": 60,
  "has_data": true,
  "timestamp": "2026-01-04T10:30:00Z"
}
```

**Response Fields:**

| Field            | Type     | Description                                    |
| ---------------- | -------- | ---------------------------------------------- |
| `model_name`     | string   | Model identifier                               |
| `display_name`   | string   | Human-readable display name                    |
| `snapshots`      | array    | Chronologically ordered latency snapshots      |
| `window_minutes` | integer  | Time window covered by the history             |
| `bucket_seconds` | integer  | Bucket size used for aggregation               |
| `has_data`       | boolean  | Whether any latency data exists for this model |
| `timestamp`      | datetime | Timestamp when history was retrieved           |

**Snapshot Stats Fields:**

| Field          | Type    | Description                           |
| -------------- | ------- | ------------------------------------- |
| `avg_ms`       | float   | Average latency in milliseconds       |
| `p50_ms`       | float   | 50th percentile (median) latency      |
| `p95_ms`       | float   | 95th percentile latency               |
| `sample_count` | integer | Number of samples in this time bucket |

**Note:** If `stats` is `null` for a snapshot, no inference data was collected during that time bucket.

**Errors:**

| Code | Description                 |
| ---- | --------------------------- |
| 404  | Model not found in registry |

**Example Requests:**

```bash
# Get last hour of latency data with 1-minute buckets
curl "http://localhost:8000/api/system/model-zoo/latency/history?model=yolo11-license-plate"

# Get last 24 hours with 5-minute buckets
curl "http://localhost:8000/api/system/model-zoo/latency/history?model=violence-detection&since=1440&bucket_seconds=300"

# Get last 15 minutes with 30-second buckets
curl "http://localhost:8000/api/system/model-zoo/latency/history?model=fashion-clip&since=15&bucket_seconds=30"
```

---

## Available Models

The Model Zoo includes the following models:

### Detection Models

| Model                      | VRAM    | Description                                       |
| -------------------------- | ------- | ------------------------------------------------- |
| `yolo11-license-plate`     | 300 MB  | License plate detection on vehicles               |
| `yolo11-face`              | 200 MB  | Face detection on persons                         |
| `yolo-world-s`             | 1500 MB | Open-vocabulary zero-shot detection               |
| `vehicle-damage-detection` | 2000 MB | Vehicle damage segmentation (cracks, dents, etc.) |

### Classification Models

| Model                            | VRAM    | Description                                         |
| -------------------------------- | ------- | --------------------------------------------------- |
| `violence-detection`             | 500 MB  | Binary violence classification                      |
| `weather-classification`         | 200 MB  | Weather condition classification (5 classes)        |
| `fashion-clip`                   | 500 MB  | Zero-shot clothing classification                   |
| `vehicle-segment-classification` | 1500 MB | Detailed vehicle type classification (11 types)     |
| `pet-classifier`                 | 200 MB  | Cat/dog classification for false positive reduction |

### Other Models

| Model                     | VRAM    | Category           | Description                           |
| ------------------------- | ------- | ------------------ | ------------------------------------- |
| `segformer-b2-clothes`    | 1500 MB | Segmentation       | Clothing segmentation (18 categories) |
| `vitpose-small`           | 1500 MB | Pose               | Human pose keypoint detection         |
| `depth-anything-v2-small` | 150 MB  | Depth Estimation   | Monocular depth estimation            |
| `clip-vit-l`              | 800 MB  | Embedding          | CLIP embeddings for re-identification |
| `paddleocr`               | 100 MB  | OCR                | Text extraction from detected plates  |
| `xclip-base`              | 2000 MB | Action Recognition | Temporal action recognition           |

### Disabled Models

| Model              | VRAM    | Reason                                         |
| ------------------ | ------- | ---------------------------------------------- |
| `florence-2-large` | 1200 MB | Now runs as dedicated ai-florence HTTP service |
| `brisque-quality`  | 0 MB    | Incompatible with NumPy 2.0                    |
| `yolo26-general`   | 400 MB  | Not yet released                               |

---

## Integration Patterns

### Monitoring Model Status

```python
import requests

# Get overall Model Zoo status
response = requests.get("http://localhost:8000/api/system/model-zoo/status")
status = response.json()

print(f"Loaded models: {status['loaded_count']}/{status['total_models']}")
print(f"VRAM usage: {status['vram_used_mb']}/{status['vram_budget_mb']} MB")

# Check which models are currently loaded
for model in status['models']:
    if model['status'] == 'loaded':
        print(f"  - {model['display_name']} ({model['vram_mb']} MB)")
```

### Latency Monitoring Dashboard

```javascript
// Fetch latency history for visualization
async function fetchModelLatency(modelName, windowMinutes = 60) {
  const response = await fetch(
    `/api/system/model-zoo/latency/history?model=${modelName}&since=${windowMinutes}`
  );
  const data = await response.json();

  // Filter snapshots with data
  const validSnapshots = data.snapshots.filter((s) => s.stats !== null);

  return {
    labels: validSnapshots.map((s) => new Date(s.timestamp)),
    avgLatency: validSnapshots.map((s) => s.stats.avg_ms),
    p95Latency: validSnapshots.map((s) => s.stats.p95_ms),
  };
}
```

---

## Related Documentation

- [Enrichment API](enrichment.md) - Results from Model Zoo processing
- [System API](system.md) - Overall system health and configuration
- [AI Performance](../../docs/operator/ai-performance.md) - Performance tuning guide
