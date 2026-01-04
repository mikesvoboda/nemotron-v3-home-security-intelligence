# Detection Endpoints

> REST API endpoints for accessing object detection results.

**Time to read:** ~4 min
**Prerequisites:** [API Overview](overview.md)

---

## Overview

Detections are individual object detections from the RT-DETRv2 model. Multiple detections may be grouped into a single Event for analysis.

**Base path:** `/api/detections`

## Endpoints

### List Detections

```
GET /api/detections
```

Returns detections with filtering and pagination.

**Query Parameters:**

| Parameter        | Type     | Description                                  |
| ---------------- | -------- | -------------------------------------------- |
| `camera_id`      | string   | Filter by camera ID (e.g., "front_door")     |
| `object_type`    | string   | Filter by type: `person`, `car`, `dog`, etc. |
| `start_date`     | datetime | ISO 8601 date/time (detections after this)   |
| `end_date`       | datetime | ISO 8601 date/time (detections before this)  |
| `min_confidence` | float    | Minimum confidence score (0.0-1.0)           |
| `limit`          | int      | Max results (default: 50, max: 1000)         |
| `offset`         | int      | Pagination offset                            |

**Response:** `200 OK`

```json
{
  "detections": [
    {
      "id": 1,
      "camera_id": "front_door",
      "detected_at": "2025-01-15T14:30:15Z",
      "object_type": "person",
      "confidence": 0.95,
      "bbox_x": 120,
      "bbox_y": 80,
      "bbox_width": 150,
      "bbox_height": 300,
      "file_path": "/export/foscam/front_door/image.jpg",
      "thumbnail_path": "/data/thumbnails/det_1.jpg",
      "media_type": "image"
    }
  ],
  "count": 156,
  "limit": 50,
  "offset": 0
}
```

### Get Detection

```
GET /api/detections/{detection_id}
```

Returns a single detection by ID.

**Response:** `200 OK` or `404 Not Found`

### Get Detection Image

```
GET /api/detections/{detection_id}/image
```

Returns the detection thumbnail with bounding box overlay.

- If thumbnail exists, returns cached version
- If not, generates thumbnail on-the-fly

**Response:** JPEG image or `404 Not Found`

**Headers:**

- `Cache-Control: public, max-age=3600`

### Stream Detection Video

```
GET /api/detections/{detection_id}/video
```

Streams video for video-based detections. Supports HTTP Range requests for seeking.

**Headers:**

- `Range: bytes=0-1023` (optional, for partial content)

**Response:**

- `200 OK` - Full video content
- `206 Partial Content` - Range request satisfied
- `400 Bad Request` - Detection is not a video
- `416 Range Not Satisfiable` - Invalid range

### Get Video Thumbnail

```
GET /api/detections/{detection_id}/video/thumbnail
```

Returns a thumbnail frame from a video detection.

**Response:** JPEG image or `404 Not Found`

## Object Types

The RT-DETRv2 model can detect COCO dataset classes. Common security-relevant types:

| Type         | Description  |
| ------------ | ------------ |
| `person`     | Human figure |
| `car`        | Automobile   |
| `truck`      | Truck or van |
| `motorcycle` | Motorcycle   |
| `bicycle`    | Bicycle      |
| `dog`        | Dog          |
| `cat`        | Cat          |

## Bounding Box Coordinates

Bounding boxes use pixel coordinates relative to the original image:

| Field         | Description            |
| ------------- | ---------------------- |
| `bbox_x`      | Left edge X coordinate |
| `bbox_y`      | Top edge Y coordinate  |
| `bbox_width`  | Box width in pixels    |
| `bbox_height` | Box height in pixels   |

## Confidence Scores

- Range: 0.0 to 1.0
- Default threshold: 0.5 (configurable via `DETECTION_CONFIDENCE_THRESHOLD`)
- Higher confidence = more certain detection

---

## Next Steps

- [Events API](events.md) - View grouped events
- [System API](system.md) - Monitor AI service health
- Back to [API Overview](overview.md)
