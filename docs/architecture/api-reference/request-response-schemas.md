# Request/Response Schemas

This document provides detailed documentation for all Pydantic schemas used in the NEM home security monitoring API.

## Overview

All API schemas are defined using Pydantic v2 and are located in `backend/api/schemas/`. Schemas provide:

- Request validation
- Response serialization
- OpenAPI documentation generation

## Common Patterns

### Pagination Envelope

All list endpoints use a standardized pagination envelope.

**Source:** `backend/api/schemas/pagination.py`

```json
{
  "items": [...],
  "pagination": {
    "total": 100,
    "limit": 50,
    "offset": 0,
    "cursor": null,
    "next_cursor": "eyJpZCI6IDUwfQ==",
    "has_more": true
  }
}
```

#### PaginationMeta

| Field         | Type    | Description                |
| ------------- | ------- | -------------------------- |
| `total`       | integer | Total items matching query |
| `limit`       | integer | Maximum items per page     |
| `offset`      | integer | Number of items skipped    |
| `cursor`      | string  | Current pagination cursor  |
| `next_cursor` | string  | Cursor for next page       |
| `has_more`    | boolean | Whether more results exist |

---

### Cursor-Based Pagination

Cursors are base64-encoded JSON containing:

```json
{
  "id": 50,
  "created_at": "2026-01-23T12:00:00Z"
}
```

**Source:** `backend/api/pagination.py`

---

### Sparse Fieldsets

Many list endpoints support the `fields` query parameter to request only specific fields.

```
GET /api/events?fields=id,camera_id,risk_score,summary
```

Invalid field requests return HTTP 400.

---

## Event Schemas

### EventResponse

**Source:** `backend/api/schemas/events.py:61-125`

```json
{
  "id": 1,
  "camera_id": "front_door",
  "started_at": "2026-01-23T12:00:00Z",
  "ended_at": "2026-01-23T12:02:30Z",
  "risk_score": 75,
  "risk_level": "medium",
  "summary": "Person detected near front entrance",
  "reasoning": "Person approaching entrance during daytime, no suspicious behavior",
  "llm_prompt": "<|im_start|>system\nYou are a home security risk analyzer...",
  "reviewed": false,
  "notes": null,
  "snooze_until": null,
  "detection_count": 5,
  "detection_ids": [1, 2, 3, 4, 5],
  "thumbnail_url": "/api/detections/1/image",
  "enrichment_status": {...},
  "deleted_at": null
}
```

| Field               | Type     | Required | Description                    |
| ------------------- | -------- | -------- | ------------------------------ |
| `id`                | integer  | Yes      | Event ID                       |
| `camera_id`         | string   | Yes      | Normalized camera ID           |
| `started_at`        | datetime | Yes      | Event start timestamp          |
| `ended_at`          | datetime | No       | Event end timestamp            |
| `risk_score`        | integer  | No       | Risk score (0-100)             |
| `risk_level`        | string   | No       | low, medium, high, critical    |
| `summary`           | string   | No       | LLM-generated summary          |
| `reasoning`         | string   | No       | LLM reasoning                  |
| `llm_prompt`        | string   | No       | Full prompt sent to LLM        |
| `reviewed`          | boolean  | No       | Review status (default: false) |
| `notes`             | string   | No       | User notes                     |
| `snooze_until`      | datetime | No       | Alert snooze timestamp         |
| `detection_count`   | integer  | No       | Number of detections           |
| `detection_ids`     | array    | No       | List of detection IDs          |
| `thumbnail_url`     | string   | No       | URL to thumbnail               |
| `enrichment_status` | object   | No       | Enrichment pipeline status     |
| `deleted_at`        | datetime | No       | Soft-delete timestamp          |

---

### EventUpdate

**Source:** `backend/api/schemas/events.py:127-144`

```json
{
  "reviewed": true,
  "notes": "Verified - delivery person",
  "snooze_until": "2026-01-24T12:00:00Z"
}
```

| Field          | Type     | Required | Description      |
| -------------- | -------- | -------- | ---------------- |
| `reviewed`     | boolean  | No       | Mark as reviewed |
| `notes`        | string   | No       | User notes       |
| `snooze_until` | datetime | No       | Snooze timestamp |

---

### EnrichmentStatusResponse

**Source:** `backend/api/schemas/events.py:27-58`

```json
{
  "status": "partial",
  "successful_models": ["violence", "weather", "face"],
  "failed_models": ["clothing"],
  "errors": { "clothing": "Model not loaded" },
  "success_rate": 0.75
}
```

| Field               | Type   | Description                    |
| ------------------- | ------ | ------------------------------ |
| `status`            | string | full, partial, failed, skipped |
| `successful_models` | array  | Models that succeeded          |
| `failed_models`     | array  | Models that failed             |
| `errors`            | object | Model to error mapping         |
| `success_rate`      | float  | Success rate (0.0-1.0)         |

---

### EventStatsResponse

**Source:** `backend/api/schemas/events.py:243-284`

```json
{
  "total_events": 44,
  "events_by_risk_level": {
    "critical": 2,
    "high": 5,
    "medium": 12,
    "low": 25
  },
  "risk_distribution": [{ "risk_level": "critical", "count": 2 }],
  "events_by_camera": [
    { "camera_id": "front_door", "camera_name": "Front Door", "event_count": 30 }
  ]
}
```

---

### TimelineSummaryResponse

**Source:** `backend/api/schemas/events.py:310-349`

```json
{
  "buckets": [
    {
      "timestamp": "2026-01-15T06:00:00Z",
      "event_count": 5,
      "max_risk_score": 45
    }
  ],
  "total_events": 17,
  "start_date": "2026-01-15T06:00:00Z",
  "end_date": "2026-01-15T08:00:00Z"
}
```

---

## Camera Schemas

### CameraResponse

**Source:** `backend/api/schemas/camera.py:184-208`

```json
{
  "id": "front_door",
  "name": "Front Door Camera",
  "folder_path": "/export/foscam/front_door",
  "status": "online",
  "created_at": "2026-01-01T10:00:00Z",
  "last_seen_at": "2026-01-23T12:00:00Z"
}
```

| Field          | Type     | Description                     |
| -------------- | -------- | ------------------------------- |
| `id`           | string   | Normalized camera ID            |
| `name`         | string   | Camera name                     |
| `folder_path`  | string   | File system path                |
| `status`       | string   | online, offline, error, unknown |
| `created_at`   | datetime | Creation timestamp              |
| `last_seen_at` | datetime | Last activity timestamp         |

---

### CameraCreate

**Source:** `backend/api/schemas/camera.py:96-136`

```json
{
  "name": "Front Door Camera",
  "folder_path": "/export/foscam/front_door",
  "status": "online"
}
```

| Field         | Type   | Required | Validation                     |
| ------------- | ------ | -------- | ------------------------------ |
| `name`        | string | Yes      | 1-255 chars, no control chars  |
| `folder_path` | string | Yes      | 1-500 chars, no path traversal |
| `status`      | string | No       | Default: online                |

---

### CameraUpdate

**Source:** `backend/api/schemas/camera.py:139-181`

All fields are optional for partial updates.

```json
{
  "name": "Front Door Camera - Updated",
  "status": "offline"
}
```

---

### CameraPathValidationResponse

**Source:** `backend/api/schemas/camera.py:314-356`

```json
{
  "base_path": "/export/foscam",
  "total_cameras": 6,
  "valid_count": 4,
  "invalid_count": 2,
  "valid_cameras": [...],
  "invalid_cameras": [
    {
      "id": "garage",
      "name": "Garage Camera",
      "folder_path": "/export/foscam/garage",
      "status": "offline",
      "resolved_path": "/export/foscam/garage",
      "issues": ["directory does not exist"]
    }
  ]
}
```

---

## Detection Schemas

### DetectionResponse

**Source:** `backend/api/schemas/detections.py:142-214`

```json
{
  "id": 1,
  "camera_id": "front_door",
  "file_path": "/export/foscam/front_door/20260123_120000.jpg",
  "file_type": "image/jpeg",
  "detected_at": "2026-01-23T12:00:00Z",
  "object_type": "person",
  "confidence": 0.95,
  "bbox_x": 100,
  "bbox_y": 150,
  "bbox_width": 200,
  "bbox_height": 400,
  "thumbnail_path": "/data/thumbnails/1_thumb.jpg",
  "media_type": "image",
  "duration": null,
  "video_codec": null,
  "video_width": null,
  "video_height": null,
  "enrichment_data": {...}
}
```

---

### EnrichmentDataSchema

**Source:** `backend/api/schemas/detections.py:94-139`

```json
{
  "vehicle": {
    "vehicle_type": "sedan",
    "vehicle_color": "blue",
    "has_damage": false,
    "is_commercial": false
  },
  "person": {
    "clothing_description": "dark jacket, blue jeans",
    "action": "walking",
    "carrying": ["backpack"],
    "is_suspicious": false
  },
  "pet": {
    "pet_type": "dog",
    "breed": "golden retriever"
  },
  "weather": "sunny",
  "errors": []
}
```

---

### VehicleEnrichmentData

**Source:** `backend/api/schemas/detections.py:17-41`

| Field           | Type    | Default | Description            |
| --------------- | ------- | ------- | ---------------------- |
| `vehicle_type`  | string  | null    | sedan, suv, truck, van |
| `vehicle_color` | string  | null    | Primary color          |
| `has_damage`    | boolean | false   | Damage detected        |
| `is_commercial` | boolean | false   | Commercial vehicle     |

---

### PersonEnrichmentData

**Source:** `backend/api/schemas/detections.py:44-70`

| Field                  | Type    | Default | Description          |
| ---------------------- | ------- | ------- | -------------------- |
| `clothing_description` | string  | null    | Clothing description |
| `action`               | string  | null    | Detected action      |
| `carrying`             | array   | []      | Items being carried  |
| `is_suspicious`        | boolean | false   | Suspicious flag      |

---

### PetEnrichmentData

**Source:** `backend/api/schemas/detections.py:73-91`

| Field      | Type   | Default | Description    |
| ---------- | ------ | ------- | -------------- |
| `pet_type` | string | null    | dog, cat       |
| `breed`    | string | null    | Detected breed |

---

### DetectionStatsResponse

**Source:** `backend/api/schemas/detections.py:290-342`

```json
{
  "total_detections": 107,
  "detections_by_class": {
    "person": 23,
    "car": 20
  },
  "object_class_distribution": [{ "object_class": "person", "count": 23 }],
  "average_confidence": 0.87,
  "trends": [{ "timestamp": 1737504000000, "detection_count": 10 }]
}
```

**Note:** `trends.timestamp` is Unix epoch milliseconds for Grafana compatibility.

---

### DetectionSearchResult

**Source:** `backend/api/schemas/detections.py:348-376`

| Field             | Type     | Description              |
| ----------------- | -------- | ------------------------ |
| `id`              | integer  | Detection ID             |
| `camera_id`       | string   | Camera ID                |
| `object_type`     | string   | Detected object type     |
| `confidence`      | float    | Detection confidence     |
| `detected_at`     | datetime | Detection timestamp      |
| `file_path`       | string   | Source file path         |
| `thumbnail_path`  | string   | Thumbnail path           |
| `relevance_score` | float    | Search relevance (0-1)   |
| `labels`          | array    | Searchable labels        |
| `bbox_*`          | integer  | Bounding box coordinates |
| `enrichment_data` | object   | Enrichment data          |

---

## Health Schemas

### LivenessResponse

**Source:** `backend/api/schemas/health.py:22-46`

```json
{
  "status": "alive"
}
```

---

### ReadinessResponse

**Source:** `backend/api/schemas/health.py:86-134`

```json
{
  "ready": true,
  "checks": {
    "database": {
      "status": "healthy",
      "latency_ms": 2.5,
      "error": null
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 1.2,
      "error": null
    }
  }
}
```

---

### CheckResult

**Source:** `backend/api/schemas/health.py:49-83`

| Field        | Type   | Description                  |
| ------------ | ------ | ---------------------------- |
| `status`     | string | healthy, unhealthy, degraded |
| `latency_ms` | float  | Check latency (ms)           |
| `error`      | string | Error message                |

---

### FullHealthResponse

**Source:** `backend/api/schemas/health.py:316-385`

```json
{
  "status": "healthy",
  "ready": true,
  "message": "All systems operational",
  "postgres": {...},
  "redis": {...},
  "ai_services": [...],
  "circuit_breakers": {...},
  "workers": [...],
  "timestamp": "2026-01-23T12:00:00Z",
  "version": "0.1.0"
}
```

---

### AIServiceHealthStatus

**Source:** `backend/api/schemas/health.py:201-234`

| Field              | Type     | Description             |
| ------------------ | -------- | ----------------------- |
| `name`             | string   | Service identifier      |
| `display_name`     | string   | Human-readable name     |
| `status`           | string   | Health state            |
| `url`              | string   | Service URL             |
| `response_time_ms` | float    | Response time           |
| `circuit_state`    | string   | closed, open, half_open |
| `error`            | string   | Error message           |
| `last_check`       | datetime | Last check timestamp    |

---

### CircuitBreakerSummary

**Source:** `backend/api/schemas/health.py:262-292`

```json
{
  "total": 5,
  "closed": 4,
  "open": 1,
  "half_open": 0,
  "breakers": {
    "rtdetr": "closed",
    "nemotron": "closed",
    "florence": "open"
  }
}
```

---

### WorkerHealthStatus

**Source:** `backend/api/schemas/health.py:295-313`

| Field      | Type    | Description                    |
| ---------- | ------- | ------------------------------ |
| `name`     | string  | Worker name                    |
| `running`  | boolean | Running status                 |
| `critical` | boolean | Whether critical for operation |

---

## Bulk Operation Schemas

### BulkOperationResponse

**Source:** `backend/api/schemas/bulk.py`

```json
{
  "total": 10,
  "succeeded": 8,
  "failed": 2,
  "skipped": 0,
  "results": [
    {
      "index": 0,
      "status": "success",
      "id": 123,
      "error": null
    },
    {
      "index": 1,
      "status": "failed",
      "id": null,
      "error": "Camera not found"
    }
  ]
}
```

### BulkOperationStatus Enum

- `success` - Operation succeeded
- `failed` - Operation failed
- `skipped` - Operation skipped

---

## Validation Rules

### Date Range Validation

**Source:** `backend/api/validators.py`

- `start_date` must be before `end_date`
- End dates are normalized to end-of-day for date-only inputs
- Maximum range: 90 days (configurable per endpoint)

### Camera Name Validation

**Source:** `backend/api/schemas/camera.py:66-93`

- 1-255 characters
- No control characters (null, tab, newline)
- Leading/trailing whitespace stripped

### Folder Path Validation

**Source:** `backend/api/schemas/camera.py:36-63`

- 1-500 characters
- No path traversal (`..`)
- Forbidden characters: `< > : " | ? *`

### Confidence Score Validation

- Range: 0.0 to 1.0
- Validated at Pydantic level with `ge=0.0, le=1.0`

---

## Related Documentation

- [Events API](events-api.md) - Event endpoints
- [Cameras API](cameras-api.md) - Camera endpoints
- [Detections API](detections-api.md) - Detection endpoints
- [System API](system-api.md) - System endpoints
- [Error Handling](error-handling.md) - Error response formats
