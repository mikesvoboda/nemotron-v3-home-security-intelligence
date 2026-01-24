# Cameras API

The Cameras API provides endpoints for managing security cameras in the NEM home security monitoring system, including CRUD operations, media serving, baseline analytics, and scene change detection.

**Source:** `backend/api/routes/cameras.py`

## Overview

Cameras are the primary data source in the system. Each camera:

- Has a configured folder path for image/video uploads
- Tracks online/offline status
- Maintains activity baselines for anomaly detection
- Detects scene changes (tampering, angle changes)

## Endpoints

### List Cameras

```
GET /api/cameras
```

List all cameras with optional filtering and sparse fieldsets.

**Source:** `backend/api/routes/cameras.py:106-221`

#### Query Parameters

| Parameter | Type   | Default | Description                                               |
| --------- | ------ | ------- | --------------------------------------------------------- |
| `status`  | string | null    | Filter by camera status (online, offline, error, unknown) |
| `fields`  | string | null    | Comma-separated fields for sparse fieldsets               |

#### Valid Sparse Fields

```
id, name, folder_path, status, created_at, last_seen_at
```

**Source:** `backend/api/routes/cameras.py:76-85`

#### Response

```json
{
  "items": [
    {
      "id": "front_door",
      "name": "Front Door Camera",
      "folder_path": "/export/foscam/front_door",
      "status": "online",
      "created_at": "2026-01-01T10:00:00Z",
      "last_seen_at": "2026-01-23T12:00:00Z"
    }
  ],
  "pagination": {
    "total": 6,
    "limit": 1000,
    "offset": 0,
    "next_cursor": null,
    "has_more": false
  }
}
```

**Source:** `backend/api/schemas/camera.py:211-243`

#### Caching

Results are cached in Redis with cache-aside pattern. Cache key includes status filter.

**Source:** `backend/api/routes/cameras.py:148-171`

---

### Create Camera

```
POST /api/cameras
```

Create a new camera.

**Source:** `backend/api/routes/cameras.py:362-453`

#### Request Body

```json
{
  "name": "Front Door Camera",
  "folder_path": "/export/foscam/front_door",
  "status": "online"
}
```

**Source:** `backend/api/schemas/camera.py:96-136`

#### Validation Rules

**Name Validation:**

- Minimum 1 character, maximum 255 characters
- Control characters are rejected (null, tab, newline)
- Leading/trailing whitespace is stripped

**Folder Path Validation:**

- Minimum 1 character, maximum 500 characters
- Path traversal (`..`) is rejected
- Forbidden characters: `< > : " | ? *` and control characters

**Source:** `backend/api/schemas/camera.py:36-93`

#### Response

```json
{
  "id": "front_door",
  "name": "Front Door Camera",
  "folder_path": "/export/foscam/front_door",
  "status": "online",
  "created_at": "2026-01-23T12:00:00Z",
  "last_seen_at": null
}
```

#### HTTP Status Codes

| Code | Description                                   |
| ---- | --------------------------------------------- |
| 201  | Created                                       |
| 409  | Conflict - name or folder_path already exists |
| 422  | Validation error                              |

---

### Get Camera

```
GET /api/cameras/{camera_id}
```

Get a specific camera by ID.

**Source:** `backend/api/routes/cameras.py:342-359`

#### Path Parameters

| Parameter   | Type   | Description                               |
| ----------- | ------ | ----------------------------------------- |
| `camera_id` | string | Normalized camera ID (e.g., "front_door") |

#### HTTP Status Codes

| Code | Description      |
| ---- | ---------------- |
| 200  | Success          |
| 404  | Camera not found |

---

### Update Camera

```
PATCH /api/cameras/{camera_id}
```

Update an existing camera. All fields are optional.

**Source:** `backend/api/routes/cameras.py:456-532`

#### Request Body

```json
{
  "name": "Front Door Camera - Updated",
  "status": "offline"
}
```

**Source:** `backend/api/schemas/camera.py:139-181`

#### HTTP Status Codes

| Code | Description      |
| ---- | ---------------- |
| 200  | Success          |
| 404  | Camera not found |
| 422  | Validation error |

---

### Delete Camera

```
DELETE /api/cameras/{camera_id}
```

Delete a camera. This cascades to all related detections and events.

**Source:** `backend/api/routes/cameras.py:535-589`

#### HTTP Status Codes

| Code | Description          |
| ---- | -------------------- |
| 204  | Success (no content) |
| 404  | Camera not found     |

---

## Soft Delete and Recovery

### List Deleted Cameras

```
GET /api/cameras/deleted
```

List soft-deleted cameras for the "trash" view.

**Source:** `backend/api/routes/cameras.py:231-282`

#### Response

```json
{
  "items": [
    {
      "id": "old_camera",
      "name": "Old Camera",
      "folder_path": "/export/foscam/old_camera",
      "status": "offline",
      "created_at": "2025-06-01T10:00:00Z",
      "last_seen_at": "2025-12-01T10:00:00Z"
    }
  ],
  "pagination": {
    "total": 1,
    "limit": 1000,
    "offset": 0,
    "has_more": false
  }
}
```

**Source:** `backend/api/schemas/camera.py:246-280`

---

### Restore Camera

```
POST /api/cameras/{camera_id}/restore
```

Restore a soft-deleted camera.

**Source:** `backend/api/routes/cameras.py:285-339`

#### HTTP Status Codes

| Code | Description           |
| ---- | --------------------- |
| 200  | Success               |
| 400  | Camera is not deleted |
| 404  | Camera not found      |

---

## Media Endpoints

### Get Camera Snapshot

```
GET /api/cameras/{camera_id}/snapshot
```

Return the latest image for a camera. Supports fallback to video frame extraction.

**Source:** `backend/api/routes/cameras.py:799-909`

#### Authentication

This endpoint is exempt from API key authentication for direct browser access via `<img>` tags.

#### Rate Limiting

Media tier: 30 requests/minute

**Source:** `backend/api/routes/cameras.py:72-73`

#### Response

Returns image file with appropriate Content-Type header.

**Supported Image Types:**

- `.jpg`, `.jpeg` - image/jpeg
- `.png` - image/png
- `.gif` - image/gif

**Source:** `backend/api/routes/cameras.py:88-93`

#### Fallback Behavior

If no image files are found, the endpoint extracts a frame from the most recent video file.

**Supported Video Types:** `.mkv`, `.mp4`, `.avi`, `.mov`, `.webm`

**Source:** `backend/api/routes/cameras.py:96`

#### HTTP Status Codes

| Code | Description                  |
| ---- | ---------------------------- |
| 200  | Success                      |
| 404  | Camera or snapshot not found |
| 429  | Rate limit exceeded          |

---

## Validation Endpoints

### Validate Camera Paths

```
GET /api/cameras/validation/paths
```

Validate all camera folder paths against the configured base path.

**Source:** `backend/api/routes/cameras.py:912-996`

#### Response

```json
{
  "base_path": "/export/foscam",
  "total_cameras": 6,
  "valid_count": 4,
  "invalid_count": 2,
  "valid_cameras": [
    {
      "id": "front_door",
      "name": "Front Door Camera",
      "folder_path": "/export/foscam/front_door",
      "status": "online",
      "resolved_path": null,
      "issues": null
    }
  ],
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

**Source:** `backend/api/schemas/camera.py:314-356`

---

## Baseline Analytics

### Get Camera Baseline Summary

```
GET /api/cameras/{camera_id}/baseline
```

Get comprehensive baseline activity data for a camera.

**Source:** `backend/api/routes/cameras.py:999-1048`

#### Response

```json
{
  "camera_id": "front_door",
  "camera_name": "Front Door Camera",
  "baseline_established": "2026-01-01T00:00:00Z",
  "data_points": 168,
  "hourly_patterns": {...},
  "daily_patterns": {...},
  "object_baselines": {...},
  "current_deviation": 0.15
}
```

---

### Get Baseline Anomalies

```
GET /api/cameras/{camera_id}/baseline/anomalies
```

Get recent anomaly events for a camera.

**Source:** `backend/api/routes/cameras.py:1051-1086`

#### Query Parameters

| Parameter | Type    | Default | Description                        |
| --------- | ------- | ------- | ---------------------------------- |
| `days`    | integer | 7       | Number of days to look back (1-90) |

#### Response

```json
{
  "camera_id": "front_door",
  "anomalies": [...],
  "count": 5,
  "period_days": 7
}
```

---

### Get Activity Baseline

```
GET /api/cameras/{camera_id}/baseline/activity
```

Get raw activity baseline data (24 hours x 7 days heatmap).

**Source:** `backend/api/routes/cameras.py:1089-1160`

#### Response

```json
{
  "camera_id": "front_door",
  "entries": [
    {
      "hour": 8,
      "day_of_week": 1,
      "avg_count": 12.5,
      "sample_count": 30,
      "is_peak": true
    }
  ],
  "total_samples": 5040,
  "peak_hour": 8,
  "peak_day": 1,
  "learning_complete": true,
  "min_samples_required": 30
}
```

---

### Get Class Baseline

```
GET /api/cameras/{camera_id}/baseline/classes
```

Get object class frequency baseline data.

**Source:** `backend/api/routes/cameras.py:1163-1222`

#### Response

```json
{
  "camera_id": "front_door",
  "entries": [
    {
      "object_class": "person",
      "hour": 8,
      "frequency": 0.85,
      "sample_count": 150
    }
  ],
  "unique_classes": ["person", "car", "dog"],
  "total_samples": 5040,
  "most_common_class": "person"
}
```

---

## Scene Change Detection

### List Scene Changes

```
GET /api/cameras/{camera_id}/scene-changes
```

Get scene changes for a camera with cursor-based pagination.

**Source:** `backend/api/routes/cameras.py:1225-1319`

#### Query Parameters

| Parameter      | Type     | Default | Description                               |
| -------------- | -------- | ------- | ----------------------------------------- |
| `acknowledged` | boolean  | null    | Filter by acknowledgement status          |
| `limit`        | integer  | 50      | Maximum results (1-100)                   |
| `cursor`       | datetime | null    | Pagination cursor (detected_at timestamp) |

#### Response

```json
{
  "camera_id": "front_door",
  "scene_changes": [
    {
      "id": 1,
      "detected_at": "2026-01-23T12:00:00Z",
      "change_type": "angle_change",
      "similarity_score": 0.65,
      "acknowledged": false,
      "acknowledged_at": null,
      "file_path": "/export/foscam/front_door/scene_change_001.jpg"
    }
  ],
  "total_changes": 1,
  "next_cursor": null,
  "has_more": false
}
```

---

### Acknowledge Scene Change

```
POST /api/cameras/{camera_id}/scene-changes/{scene_change_id}/acknowledge
```

Mark a scene change as acknowledged.

**Source:** `backend/api/routes/cameras.py:1322-1421`

#### Idempotency

If already acknowledged, returns existing data without modification.

**Source:** `backend/api/routes/cameras.py:1376-1381`

#### Response

```json
{
  "id": 1,
  "acknowledged": true,
  "acknowledged_at": "2026-01-23T14:00:00Z"
}
```

#### HTTP Status Codes

| Code | Description                      |
| ---- | -------------------------------- |
| 200  | Success                          |
| 404  | Camera or scene change not found |

---

## Data Models

### CameraResponse

**Source:** `backend/api/schemas/camera.py:184-208`

| Field          | Type     | Description                                     |
| -------------- | -------- | ----------------------------------------------- |
| `id`           | string   | Normalized camera ID                            |
| `name`         | string   | Camera name                                     |
| `folder_path`  | string   | File system path for uploads                    |
| `status`       | string   | Camera status (online, offline, error, unknown) |
| `created_at`   | datetime | Creation timestamp                              |
| `last_seen_at` | datetime | Last activity timestamp                         |

### CameraCreate

**Source:** `backend/api/schemas/camera.py:96-136`

| Field         | Type   | Required | Description                      |
| ------------- | ------ | -------- | -------------------------------- |
| `name`        | string | Yes      | Camera name (1-255 chars)        |
| `folder_path` | string | Yes      | File system path (1-500 chars)   |
| `status`      | string | No       | Initial status (default: online) |

### CameraUpdate

**Source:** `backend/api/schemas/camera.py:139-181`

| Field         | Type   | Required | Description     |
| ------------- | ------ | -------- | --------------- |
| `name`        | string | No       | New camera name |
| `folder_path` | string | No       | New folder path |
| `status`      | string | No       | New status      |

### CameraStatus Enum

**Source:** `backend/models/enums.py`

- `online` - Camera is active and processing
- `offline` - Camera is not active
- `error` - Camera has an error condition
- `unknown` - Camera status is unknown

---

## Cache Invalidation

Camera list cache is invalidated on:

- Camera creation (`backend/api/routes/cameras.py:448-451`)
- Camera update (`backend/api/routes/cameras.py:525-529`)
- Camera deletion (`backend/api/routes/cameras.py:585-589`)
- Camera restoration (`backend/api/routes/cameras.py:334-337`)

---

## Related Documentation

- [Events API](events-api.md) - Security events from cameras
- [Detections API](detections-api.md) - Object detections from cameras
- [Error Handling](error-handling.md) - Error response formats
