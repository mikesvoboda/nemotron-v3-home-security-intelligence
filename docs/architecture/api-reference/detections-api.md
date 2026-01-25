# Detections API

The Detections API provides endpoints for accessing object detection data and associated media in the NEM home security monitoring system.

**Source:** `backend/api/routes/detections.py`

## Overview

Detections are individual object detections from the RT-DETR AI model. Each detection:

- Contains bounding box coordinates
- Has a confidence score (0-1)
- May include enrichment data from additional AI models
- Is associated with a camera and optionally an event

## Endpoints

### List Detections

```
GET /api/detections
```

List detections with optional filtering and cursor-based pagination.

**Source:** `backend/api/routes/detections.py:172-360`

#### Query Parameters

| Parameter        | Type     | Default | Description                                 |
| ---------------- | -------- | ------- | ------------------------------------------- |
| `camera_id`      | string   | null    | Filter by camera ID                         |
| `object_type`    | string   | null    | Filter by object type (person, car, etc.)   |
| `start_date`     | datetime | null    | Filter detections after this date           |
| `end_date`       | datetime | null    | Filter detections before this date          |
| `min_confidence` | float    | null    | Minimum confidence score (0-1)              |
| `limit`          | integer  | 50      | Maximum results (1-100)                     |
| `offset`         | integer  | 0       | Results to skip (deprecated, use cursor)    |
| `cursor`         | string   | null    | Pagination cursor from previous response    |
| `fields`         | string   | null    | Comma-separated fields for sparse fieldsets |

#### Valid Sparse Fields

```
id, camera_id, file_path, file_type, detected_at, object_type, confidence,
bbox_x, bbox_y, bbox_width, bbox_height, thumbnail_path, media_type,
duration, video_codec, video_width, video_height, enrichment_data
```

**Source:** `backend/api/routes/detections.py:79-101`

#### Response

```json
{
  "items": [
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
      "enrichment_data": {
        "vehicle": null,
        "person": {
          "clothing_description": "dark jacket, blue jeans",
          "action": "walking",
          "carrying": ["backpack"],
          "is_suspicious": false
        },
        "pet": null,
        "weather": "sunny",
        "errors": []
      }
    }
  ],
  "pagination": {
    "total": 1000,
    "limit": 50,
    "offset": 0,
    "next_cursor": "eyJpZCI6IDUwLCAiY3JlYXRlZF9hdCI6ICIyMDI2LTAxLTIzVDEyOjAwOjAwWiJ9", // pragma: allowlist secret
    "has_more": true
  },
  "deprecation_warning": null
}
```

**Source:** `backend/api/schemas/detections.py:217-259`

#### HTTP Status Codes

| Code | Description                           |
| ---- | ------------------------------------- |
| 200  | Success                               |
| 400  | Invalid date range, cursor, or fields |
| 422  | Validation error                      |

---

### Get Detection Statistics

```
GET /api/detections/stats
```

Get aggregate detection statistics including class distribution and trends.

**Source:** `backend/api/routes/detections.py:363-502`

#### Query Parameters

| Parameter   | Type   | Default | Description                 |
| ----------- | ------ | ------- | --------------------------- |
| `camera_id` | string | null    | Filter statistics by camera |

#### Response

```json
{
  "total_detections": 107,
  "detections_by_class": {
    "person": 23,
    "car": 20,
    "truck": 6,
    "bicycle": 1
  },
  "object_class_distribution": [
    { "object_class": "person", "count": 23 },
    { "object_class": "car", "count": 20 },
    { "object_class": "truck", "count": 6 },
    { "object_class": "bicycle", "count": 1 }
  ],
  "average_confidence": 0.87,
  "trends": [
    { "timestamp": 1737504000000, "detection_count": 10 },
    { "timestamp": 1737590400000, "detection_count": 15 }
  ]
}
```

**Source:** `backend/api/schemas/detections.py:290-342`

**Note:** The `trends` array contains Unix epoch milliseconds for Grafana JSON datasource compatibility.

---

### Search Detections

```
GET /api/detections/search
```

Full-text search across detections using PostgreSQL text search.

**Source:** `backend/api/routes/detections.py:505-576`

#### Query Parameters

| Parameter        | Type     | Default  | Description                    |
| ---------------- | -------- | -------- | ------------------------------ |
| `q`              | string   | required | Search query (min 1 character) |
| `labels`         | array    | null     | Filter by detection labels     |
| `min_confidence` | float    | null     | Minimum confidence (0-1)       |
| `camera_id`      | string   | null     | Filter by camera               |
| `start_date`     | datetime | null     | Filter after date              |
| `end_date`       | datetime | null     | Filter before date             |
| `limit`          | integer  | 50       | Maximum results (1-1000)       |
| `offset`         | integer  | 0        | Results to skip                |

#### Response

```json
{
  "results": [
    {
      "id": 1,
      "camera_id": "front_door",
      "object_type": "person",
      "confidence": 0.95,
      "detected_at": "2026-01-23T12:00:00Z",
      "file_path": "/export/foscam/front_door/20260123_120000.jpg",
      "thumbnail_path": "/data/thumbnails/1_thumb.jpg",
      "relevance_score": 0.95,
      "labels": ["outdoor", "daytime"],
      "bbox_x": 100,
      "bbox_y": 150,
      "bbox_width": 200,
      "bbox_height": 400,
      "enrichment_data": {...}
    }
  ],
  "total_count": 50,
  "limit": 50,
  "offset": 0
}
```

**Source:** `backend/api/schemas/detections.py:348-376`

---

### Get Detection Labels

```
GET /api/detections/labels
```

Get all unique detection labels with counts.

**Source:** `backend/api/routes/detections.py:579-588`

#### Response

```json
{
  "labels": [
    { "label": "outdoor", "count": 500 },
    { "label": "daytime", "count": 450 },
    { "label": "person_visible", "count": 300 }
  ]
}
```

**Source:** `backend/api/schemas/detections.py:378-388`

---

### Get Single Detection

```
GET /api/detections/{detection_id}
```

Get detailed information about a specific detection.

**Source:** `backend/api/routes/detections.py:591-608`

#### Path Parameters

| Parameter      | Type    | Description  |
| -------------- | ------- | ------------ |
| `detection_id` | integer | Detection ID |

#### HTTP Status Codes

| Code | Description         |
| ---- | ------------------- |
| 200  | Success             |
| 404  | Detection not found |

---

## Media Endpoints

All media endpoints are exempt from API key authentication and have rate limiting.

### Get Detection Thumbnail

```
GET /api/detections/{detection_id}/thumbnail
```

Serve the cropped thumbnail image with bounding box overlay.

**Source:** `backend/api/routes/detections.py:611-720`

#### Rate Limiting

Media tier: 30 requests/minute

**Source:** `backend/api/routes/detections.py:166`

#### Response

Returns JPEG or PNG image file.

#### On-Demand Generation

If thumbnail does not exist, it is generated on-the-fly from the source media.

**Source:** `backend/api/routes/detections.py:661-700`

#### HTTP Status Codes

| Code | Description                      |
| ---- | -------------------------------- |
| 200  | Success                          |
| 404  | Detection or thumbnail not found |
| 429  | Rate limit exceeded              |
| 500  | Thumbnail generation failed      |

---

### Get Detection Image

```
GET /api/detections/{detection_id}/image
```

Get detection image with bounding box overlay, or full-size original.

**Source:** `backend/api/routes/detections.py:1185-1313`

#### Query Parameters

| Parameter | Type    | Default | Description                                    |
| --------- | ------- | ------- | ---------------------------------------------- |
| `full`    | boolean | false   | Return full-size original instead of thumbnail |

#### Rate Limiting

Media tier: 30 requests/minute

#### Response

Returns JPEG image with 1-hour cache control header.

#### HTTP Status Codes

| Code | Description                  |
| ---- | ---------------------------- |
| 200  | Success                      |
| 404  | Detection or image not found |
| 429  | Rate limit exceeded          |
| 500  | Image generation failed      |

---

### Get Detection Enrichment

```
GET /api/detections/{detection_id}/enrichment
```

Get structured enrichment data for a detection.

**Source:** `backend/api/routes/detections.py:993-1026`

#### Response

```json
{
  "detection_id": 1,
  "enriched_at": "2026-01-23T12:00:00Z",
  "license_plate": {
    "detected": true,
    "text": "ABC123",
    "confidence": 0.92,
    "ocr_confidence": 0.88
  },
  "face": {
    "detected": true,
    "count": 1,
    "confidence": 0.85
  },
  "vehicle": {
    "type": "sedan",
    "color": null,
    "confidence": 0.91,
    "is_commercial": false,
    "damage_detected": false,
    "damage_types": null
  },
  "clothing": {
    "upper": "dark jacket",
    "lower": "blue jeans",
    "is_suspicious": false,
    "is_service_uniform": false,
    "has_face_covered": false,
    "has_bag": true,
    "clothing_items": ["jacket", "jeans"]
  },
  "violence": {
    "detected": false,
    "score": 0.05,
    "confidence": 0.95
  },
  "weather": null,
  "pose": {
    "posture": "standing",
    "alerts": [],
    "keypoint_count": 17,
    "confidence": 0.88
  },
  "depth": null,
  "image_quality": {
    "score": 0.85,
    "is_blurry": false,
    "is_low_quality": false,
    "quality_issues": []
  },
  "pet": null,
  "processing_time_ms": 1250,
  "errors": []
}
```

**Note:** Error messages are sanitized to remove sensitive internal details.

**Source:** `backend/api/routes/detections.py:128-161`

---

### Stream Detection Video

```
GET /api/detections/{detection_id}/video
```

Stream detection video with HTTP Range request support and automatic transcoding.

**Source:** `backend/api/routes/detections.py:1361-1508`

#### Headers

| Header  | Description                                                  |
| ------- | ------------------------------------------------------------ |
| `Range` | HTTP Range header for partial content (e.g., "bytes=0-1023") |

#### Rate Limiting

Media tier: 30 requests/minute

#### Transcoding

Videos are automatically transcoded to browser-compatible H.264/MP4 format. Transcoded videos are cached.

**Source:** `backend/api/routes/detections.py:1429-1438`

#### Response

- **200 OK**: Full video content
- **206 Partial Content**: Range request response

#### HTTP Status Codes

| Code | Description                     |
| ---- | ------------------------------- |
| 200  | Full content                    |
| 206  | Partial content (range request) |
| 400  | Detection is not a video        |
| 404  | Detection or video not found    |
| 416  | Range not satisfiable           |
| 429  | Rate limit exceeded             |
| 500  | Transcoding failed              |

---

### Get Video Thumbnail

```
GET /api/detections/{detection_id}/video/thumbnail
```

Get thumbnail frame from a video detection.

**Source:** `backend/api/routes/detections.py:1511-1624`

#### Rate Limiting

Media tier: 30 requests/minute

#### Response

Returns JPEG thumbnail image.

#### HTTP Status Codes

| Code | Description                  |
| ---- | ---------------------------- |
| 200  | Success                      |
| 400  | Detection is not a video     |
| 404  | Detection or video not found |
| 429  | Rate limit exceeded          |
| 500  | Thumbnail generation failed  |

---

## Bulk Operations

All bulk endpoints have rate limiting: 10 requests/minute with burst of 2.

**Source:** `backend/api/routes/detections.py:1635`

### Bulk Create Detections

```
POST /api/detections/bulk
```

Create multiple detections in a single request.

**Source:** `backend/api/routes/detections.py:1638-1762`

#### Request Body

```json
{
  "detections": [
    {
      "camera_id": "front_door",
      "object_type": "person",
      "confidence": 0.95,
      "detected_at": "2026-01-23T12:00:00Z",
      "file_path": "/export/foscam/front_door/img.jpg",
      "bbox_x": 100,
      "bbox_y": 150,
      "bbox_width": 200,
      "bbox_height": 400
    }
  ]
}
```

#### Response

Returns HTTP 207 Multi-Status with per-item results.

```json
{
  "total": 2,
  "succeeded": 1,
  "failed": 1,
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
      "error": "Camera not found: invalid_camera"
    }
  ]
}
```

---

### Bulk Update Detections

```
PATCH /api/detections/bulk
```

Update multiple detections in a single request.

**Source:** `backend/api/routes/detections.py:1765-1881`

#### Request Body

```json
{
  "detections": [
    {
      "id": 1,
      "object_type": "car",
      "confidence": 0.98
    }
  ]
}
```

---

### Bulk Delete Detections

```
DELETE /api/detections/bulk
```

Delete multiple detections in a single request.

**Source:** `backend/api/routes/detections.py:1884-1997`

**Note:** Detection deletion is always hard delete (no soft-delete support).

#### Request Body

```json
{
  "detection_ids": [1, 2, 3, 4, 5]
}
```

---

## Data Models

### DetectionResponse

**Source:** `backend/api/schemas/detections.py:142-214`

| Field             | Type     | Description                    |
| ----------------- | -------- | ------------------------------ |
| `id`              | integer  | Detection ID                   |
| `camera_id`       | string   | Normalized camera ID           |
| `file_path`       | string   | Path to source image/video     |
| `file_type`       | string   | MIME type of source file       |
| `detected_at`     | datetime | Detection timestamp            |
| `object_type`     | string   | Detected object type           |
| `confidence`      | float    | Detection confidence (0-1)     |
| `bbox_x`          | integer  | Bounding box X coordinate      |
| `bbox_y`          | integer  | Bounding box Y coordinate      |
| `bbox_width`      | integer  | Bounding box width             |
| `bbox_height`     | integer  | Bounding box height            |
| `thumbnail_path`  | string   | Path to thumbnail image        |
| `media_type`      | string   | Media type: 'image' or 'video' |
| `duration`        | float    | Video duration in seconds      |
| `video_codec`     | string   | Video codec (e.g., h264)       |
| `video_width`     | integer  | Video resolution width         |
| `video_height`    | integer  | Video resolution height        |
| `enrichment_data` | object   | AI enrichment data             |

### EnrichmentDataSchema

**Source:** `backend/api/schemas/detections.py:94-139`

| Field     | Type   | Description                 |
| --------- | ------ | --------------------------- |
| `vehicle` | object | Vehicle classification data |
| `person`  | object | Person enrichment data      |
| `pet`     | object | Pet classification data     |
| `weather` | string | Weather condition           |
| `errors`  | array  | Enrichment errors           |

### VehicleEnrichmentData

**Source:** `backend/api/schemas/detections.py:17-41`

| Field           | Type    | Description                   |
| --------------- | ------- | ----------------------------- |
| `vehicle_type`  | string  | Type (sedan, suv, truck, van) |
| `vehicle_color` | string  | Primary color                 |
| `has_damage`    | boolean | Damage detected               |
| `is_commercial` | boolean | Commercial/delivery vehicle   |

### PersonEnrichmentData

**Source:** `backend/api/schemas/detections.py:44-70`

| Field                  | Type    | Description                |
| ---------------------- | ------- | -------------------------- |
| `clothing_description` | string  | Description of clothing    |
| `action`               | string  | Detected action            |
| `carrying`             | array   | Items being carried        |
| `is_suspicious`        | boolean | Suspicious appearance flag |

### PetEnrichmentData

**Source:** `backend/api/schemas/detections.py:73-91`

| Field      | Type   | Description            |
| ---------- | ------ | ---------------------- |
| `pet_type` | string | Type of pet (dog, cat) |
| `breed`    | string | Detected breed         |

---

## Related Documentation

- [Events API](events-api.md) - Security events containing detections
- [Cameras API](cameras-api.md) - Camera management
- [Error Handling](error-handling.md) - Error response formats
- [Request/Response Schemas](request-response-schemas.md) - Schema details
