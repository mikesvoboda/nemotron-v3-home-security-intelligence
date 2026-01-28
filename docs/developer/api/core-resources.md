# Core Resources API

This guide covers the fundamental data resources in the Home Security Intelligence system: cameras, events, detections, zones, entities, and analytics.

## Entity Relationships

The core data model follows a hierarchical structure where cameras produce detections, which are aggregated into events by the AI pipeline.

```mermaid
%%{init: {
  'theme': 'dark',
  'themeVariables': {
    'primaryColor': '#3B82F6',
    'primaryTextColor': '#FFFFFF',
    'primaryBorderColor': '#60A5FA',
    'secondaryColor': '#A855F7',
    'tertiaryColor': '#009688',
    'background': '#121212',
    'mainBkg': '#1a1a2e',
    'lineColor': '#666666'
  }
}}%%
erDiagram
    CAMERA ||--o{ DETECTION : produces
    CAMERA ||--o{ EVENT : generates
    CAMERA ||--o{ ZONE : contains
    EVENT ||--o{ DETECTION : groups
    DETECTION ||--o| ENTITY : "tracked as"

    CAMERA {
        string id PK
        string name
        string folder_path
        string status
        datetime last_seen_at
    }

    DETECTION {
        int id PK
        string camera_id FK
        string object_type
        float confidence
        datetime detected_at
        string thumbnail_path
    }

    EVENT {
        int id PK
        string camera_id FK
        int risk_score
        string risk_level
        text summary
        text reasoning
        json detection_ids
    }

    ZONE {
        string id PK
        string camera_id FK
        string name
        string zone_type
        json coordinates
    }

    ENTITY {
        string id PK
        string entity_type
        datetime first_seen
        datetime last_seen
        json cameras_seen
    }
```

**Data Flow:**

1. **Camera** uploads images via FTP to its configured `folder_path`
2. **Detection** records are created when YOLO26 identifies objects in images
3. **Events** aggregate multiple detections within time windows (90s) and include LLM-generated risk assessments
4. **Zones** define regions of interest within camera views for targeted detection
5. **Entities** track persons/vehicles across cameras using CLIP-based re-identification

---

## Cameras

Cameras represent physical security devices that upload images to configured folder paths.

### Endpoints

| Method | Endpoint                                                  | Description               |
| ------ | --------------------------------------------------------- | ------------------------- |
| GET    | `/api/cameras`                                            | List all cameras          |
| GET    | `/api/cameras/{camera_id}`                                | Get camera by ID          |
| POST   | `/api/cameras`                                            | Create new camera         |
| PATCH  | `/api/cameras/{camera_id}`                                | Update camera             |
| DELETE | `/api/cameras/{camera_id}`                                | Delete camera             |
| GET    | `/api/cameras/deleted`                                    | List soft-deleted cameras |
| POST   | `/api/cameras/{camera_id}/restore`                        | Restore deleted camera    |
| GET    | `/api/cameras/{camera_id}/snapshot`                       | Get latest snapshot       |
| GET    | `/api/cameras/validation/paths`                           | Validate folder paths     |
| GET    | `/api/cameras/{camera_id}/baseline`                       | Get baseline summary      |
| GET    | `/api/cameras/{camera_id}/baseline/activity`              | Get activity heatmap data |
| GET    | `/api/cameras/{camera_id}/baseline/anomalies`             | Get recent anomalies      |
| GET    | `/api/cameras/{camera_id}/baseline/classes`               | Get class frequency data  |
| GET    | `/api/cameras/{camera_id}/scene-changes`                  | List scene changes        |
| POST   | `/api/cameras/{camera_id}/scene-changes/{id}/acknowledge` | Acknowledge scene change  |

### List Cameras

```bash
GET /api/cameras?status=online
```

**Parameters:**

| Name   | Type   | Description                                                                                                                    |
| ------ | ------ | ------------------------------------------------------------------------------------------------------------------------------ |
| status | string | Filter: `online`, `offline`, `error`                                                                                           |
| fields | string | Comma-separated list of fields for sparse response. Valid: `id`, `name`, `folder_path`, `status`, `created_at`, `last_seen_at` |

**Response:**

```json
{
  "cameras": [
    {
      "id": "front_door",
      "name": "Front Door Camera",
      "folder_path": "/export/foscam/front_door",
      "status": "online",
      "created_at": "2025-12-23T10:00:00Z",
      "last_seen_at": "2025-12-23T12:00:00Z"
    }
  ],
  "count": 1
}
```

### Create Camera

```bash
POST /api/cameras
Content-Type: application/json

{
  "name": "Front Door Camera",
  "folder_path": "/export/foscam/front_door",
  "status": "online"
}
```

The camera `id` is auto-generated from the name (lowercase, underscored).

### Get Camera Snapshot

```bash
GET /api/cameras/front_door/snapshot
```

Returns binary image data with appropriate `Content-Type` header.

### Baseline Activity

Get activity patterns for anomaly detection:

```bash
GET /api/cameras/front_door/baseline
```

**Response:**

```json
{
  "camera_id": "front_door",
  "baseline_established": "2026-01-01T00:00:00Z",
  "data_points": 720,
  "hourly_patterns": {
    "0": { "avg_detections": 0.5, "std_dev": 0.3, "sample_count": 30 },
    "17": { "avg_detections": 5.2, "std_dev": 1.1, "sample_count": 30 }
  },
  "current_deviation": {
    "score": 1.8,
    "interpretation": "slightly_above_normal",
    "contributing_factors": ["person_count_elevated"]
  }
}
```

### Scene Change Detection

Monitor camera tampering or angle changes:

```bash
GET /api/cameras/front_door/scene-changes?acknowledged=false
```

**Parameters:**

| Name         | Type     | Description                               |
| ------------ | -------- | ----------------------------------------- |
| acknowledged | boolean  | Filter by acknowledgement status          |
| limit        | integer  | Max results (1-100, default: 50)          |
| cursor       | datetime | Pagination cursor (detected_at timestamp) |

**Change Types:** `view_blocked`, `angle_changed`, `view_tampered`, `unknown`

### Soft-Deleted Cameras

List cameras that have been soft-deleted for trash view:

```bash
GET /api/cameras/deleted
```

**Response:**

```json
{
  "cameras": [
    {
      "id": "old_camera",
      "name": "Old Camera",
      "folder_path": "/export/foscam/old_camera",
      "status": "offline",
      "deleted_at": "2026-01-10T15:30:00Z"
    }
  ],
  "count": 1
}
```

### Restore Camera

Restore a soft-deleted camera:

```bash
POST /api/cameras/old_camera/restore
```

**Response:** Returns the restored camera object.

**Errors:**

- `404` - Camera not found
- `400` - Camera is not deleted (nothing to restore)

### Activity Heatmap Data

Get raw activity baseline data for weekly heatmap visualization:

```bash
GET /api/cameras/front_door/baseline/activity
```

Returns up to 168 entries (24 hours x 7 days) representing the full weekly activity heatmap.

**Response:**

```json
{
  "camera_id": "front_door",
  "entries": [
    {
      "hour": 0,
      "day_of_week": 0,
      "avg_count": 0.5,
      "sample_count": 30
    },
    {
      "hour": 17,
      "day_of_week": 1,
      "avg_count": 5.2,
      "sample_count": 30
    }
  ]
}
```

### Class Frequency Baseline

Get baseline entries grouped by object class and hour:

```bash
GET /api/cameras/front_door/baseline/classes
```

**Response:**

```json
{
  "camera_id": "front_door",
  "entries": [
    {
      "object_class": "person",
      "hour": 17,
      "avg_count": 3.5,
      "sample_count": 30
    },
    {
      "object_class": "car",
      "hour": 8,
      "avg_count": 2.1,
      "sample_count": 30
    }
  ]
}
```

---

## Events

Events are aggregated from detections within time windows and contain LLM-generated risk assessments.

### Event Retrieval Flow

The following diagram illustrates the typical API flow for fetching events with filters, including how the backend processes pagination and joins detection data.

```mermaid
%%{init: {'theme': 'dark'}}%%
sequenceDiagram
    participant Client as Frontend Client
    participant API as FastAPI Backend
    participant DB as PostgreSQL
    participant Cache as Redis Cache

    Client->>API: GET /api/events?camera_id=front_door&risk_level=high&limit=50
    API->>API: Validate query parameters

    alt Cache hit for query
        API->>Cache: Check cached result
        Cache-->>API: Return cached events
    else Cache miss
        API->>DB: SELECT events WHERE camera_id AND risk_level
        Note right of DB: Uses idx_events_camera_id<br/>and idx_events_risk_score
        DB-->>API: Event records with count
        API->>Cache: Store result (5min TTL)
    end

    API->>DB: SELECT detections WHERE id IN (detection_ids)
    Note right of DB: Fetches detection details<br/>for each event
    DB-->>API: Detection records

    API->>API: Assemble response with pagination
    API-->>Client: JSON {events, count, limit, offset}

    opt Client requests event details
        Client->>API: GET /api/events/{event_id}
        API->>DB: SELECT event, detections, enrichments
        DB-->>API: Full event data
        API-->>Client: JSON with full event details
    end
```

### Endpoints

| Method | Endpoint                                | Description                        |
| ------ | --------------------------------------- | ---------------------------------- |
| GET    | `/api/events`                           | List events with filtering         |
| GET    | `/api/events/stats`                     | Get event statistics               |
| GET    | `/api/events/search`                    | Full-text search                   |
| GET    | `/api/events/export`                    | Export as CSV/Excel                |
| POST   | `/api/events/export`                    | Start background export job        |
| GET    | `/api/events/deleted`                   | List soft-deleted events           |
| POST   | `/api/events/bulk`                      | Bulk create events                 |
| PATCH  | `/api/events/bulk`                      | Bulk update events                 |
| DELETE | `/api/events/bulk`                      | Bulk delete events                 |
| GET    | `/api/events/analyze/{batch_id}/stream` | Stream LLM analysis progress (SSE) |
| GET    | `/api/events/{event_id}`                | Get event by ID                    |
| PATCH  | `/api/events/{event_id}`                | Update event (review)              |
| DELETE | `/api/events/{event_id}`                | Soft delete event                  |
| POST   | `/api/events/{event_id}/restore`        | Restore soft-deleted event         |
| GET    | `/api/events/{event_id}/detections`     | Get detections for event           |
| GET    | `/api/events/{event_id}/enrichments`    | Get enrichment data                |
| GET    | `/api/events/{event_id}/clip`           | Get video clip info                |
| POST   | `/api/events/{event_id}/clip/generate`  | Generate video clip                |

### List Events

```bash
GET /api/events?camera_id=front_door&risk_level=high&limit=50
```

**Parameters:**

| Name        | Type     | Description                                                                                                                                                                                                         |
| ----------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| camera_id   | string   | Filter by camera ID                                                                                                                                                                                                 |
| risk_level  | string   | `low`, `medium`, `high`, `critical`                                                                                                                                                                                 |
| start_date  | datetime | Filter events after date                                                                                                                                                                                            |
| end_date    | datetime | Filter events before date                                                                                                                                                                                           |
| reviewed    | boolean  | Filter by reviewed status                                                                                                                                                                                           |
| object_type | string   | Filter by object: `person`, `vehicle`                                                                                                                                                                               |
| limit       | integer  | Max results (1-100, default: 50)                                                                                                                                                                                    |
| offset      | integer  | Results to skip (deprecated, use cursor)                                                                                                                                                                            |
| cursor      | string   | Pagination cursor from previous response                                                                                                                                                                            |
| fields      | string   | Comma-separated fields for sparse response. Valid: `id`, `camera_id`, `started_at`, `ended_at`, `risk_score`, `risk_level`, `summary`, `reasoning`, `reviewed`, `detection_count`, `detection_ids`, `thumbnail_url` |

**Response:**

```json
{
  "events": [
    {
      "id": 1,
      "camera_id": "front_door",
      "started_at": "2025-12-23T12:00:00Z",
      "ended_at": "2025-12-23T12:02:30Z",
      "risk_score": 75,
      "risk_level": "medium",
      "summary": "Person detected near front entrance",
      "reasoning": "Person approaching entrance during daytime",
      "reviewed": false,
      "detection_count": 5,
      "detection_ids": [1, 2, 3, 4, 5]
    }
  ],
  "count": 1,
  "limit": 50,
  "offset": 0
}
```

### Full-Text Search

```bash
GET /api/events/search?q=suspicious+person&severity=high,critical
```

**Search Syntax:**

| Syntax            | Description  | Example               |
| ----------------- | ------------ | --------------------- |
| `word1 word2`     | Implicit AND | `person vehicle`      |
| `"phrase"`        | Exact phrase | `"suspicious person"` |
| `word1 OR word2`  | Boolean OR   | `person OR animal`    |
| `word1 NOT word2` | Boolean NOT  | `person NOT cat`      |

### Update Event (Review)

```bash
PATCH /api/events/1
Content-Type: application/json

{
  "reviewed": true,
  "notes": "Verified - delivery person"
}
```

### Generate Video Clip

```bash
POST /api/events/123/clip/generate
Content-Type: application/json

{
  "start_offset_seconds": -15,
  "end_offset_seconds": 30,
  "force": false
}
```

### Delete Event

Soft delete an event with optional cascade to related detections:

```bash
DELETE /api/events/123?cascade=true
```

**Parameters:**

| Name    | Type    | Description                                       |
| ------- | ------- | ------------------------------------------------- |
| cascade | boolean | Cascade soft delete to detections (default: true) |

**Errors:**

- `404` - Event not found
- `409` - Event already deleted

### Restore Event

Restore a soft-deleted event with optional cascade:

```bash
POST /api/events/123/restore?cascade=true
```

**Parameters:**

| Name    | Type    | Description                                           |
| ------- | ------- | ----------------------------------------------------- |
| cascade | boolean | Cascade restore to related detections (default: true) |

### Soft-Deleted Events

List events that have been soft-deleted:

```bash
GET /api/events/deleted
```

Returns events ordered by `deleted_at` descending (most recently deleted first).

### Bulk Operations

Create, update, or delete multiple events in a single request. All bulk operations support partial success and return HTTP 207 Multi-Status.

**Bulk Create:**

```bash
POST /api/events/bulk
Content-Type: application/json

{
  "events": [
    {
      "camera_id": "front_door",
      "started_at": "2026-01-10T12:00:00Z",
      "risk_score": 50,
      "summary": "Person detected"
    }
  ]
}
```

**Bulk Update:**

```bash
PATCH /api/events/bulk
Content-Type: application/json

{
  "updates": [
    { "id": 1, "reviewed": true },
    { "id": 2, "reviewed": true }
  ]
}
```

**Bulk Delete:**

```bash
DELETE /api/events/bulk
Content-Type: application/json

{
  "ids": [1, 2, 3],
  "soft_delete": true,
  "cascade": true
}
```

**Response (207 Multi-Status):**

```json
{
  "total": 3,
  "succeeded": 2,
  "failed": 1,
  "results": [
    { "id": 1, "status": 200 },
    { "id": 2, "status": 200 },
    { "id": 3, "status": 404, "error": "Not found" }
  ]
}
```

### Stream LLM Analysis

Stream LLM analysis progress via Server-Sent Events:

```bash
GET /api/events/analyze/batch_abc123/stream?camera_id=front_door
```

**Parameters:**

| Name          | Type   | Description                   |
| ------------- | ------ | ----------------------------- |
| camera_id     | string | Camera ID for the batch       |
| detection_ids | string | Comma-separated detection IDs |

**SSE Event Types:**

| Event Type | Description                                |
| ---------- | ------------------------------------------ |
| `progress` | Partial LLM response with accumulated_text |
| `complete` | Final event with risk assessment           |
| `error`    | Error with error_code and recoverable flag |

**Example SSE Stream:**

```text
data: {"event_type": "progress", "content": "Based on", "accumulated_text": "Based on"}

data: {"event_type": "progress", "content": " the", "accumulated_text": "Based on the"}

data: {"event_type": "complete", "event_id": 123, "risk_score": 75, "risk_level": "medium"}
```

### Export Events

Export events as CSV or Excel. Supports content negotiation via Accept header.

**CSV Export (default):**

```bash
GET /api/events/export?camera_id=front_door
Accept: text/csv
```

**Excel Export:**

```bash
GET /api/events/export?camera_id=front_door
Accept: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
```

**Background Export Job:**

For large exports, start a background job:

```bash
POST /api/events/export
Content-Type: application/json

{
  "format": "xlsx",
  "camera_id": "front_door",
  "start_date": "2026-01-01T00:00:00Z"
}
```

Returns job ID for tracking via `GET /api/jobs/{job_id}`.

---

## Detections

Detections represent individual objects identified by YOLO26 in camera images.

### Endpoints

| Method | Endpoint                                         | Description                   |
| ------ | ------------------------------------------------ | ----------------------------- |
| GET    | `/api/detections`                                | List detections               |
| GET    | `/api/detections/labels`                         | Get unique labels with counts |
| GET    | `/api/detections/search`                         | Full-text search              |
| GET    | `/api/detections/stats`                          | Get detection statistics      |
| GET    | `/api/detections/export`                         | Export as CSV/JSON            |
| POST   | `/api/detections/bulk`                           | Bulk create detections        |
| PATCH  | `/api/detections/bulk`                           | Bulk update detections        |
| DELETE | `/api/detections/bulk`                           | Bulk delete detections        |
| GET    | `/api/detections/{detection_id}`                 | Get detection by ID           |
| GET    | `/api/detections/{detection_id}/image`           | Get image with bounding box   |
| GET    | `/api/detections/{detection_id}/thumbnail`       | Get cropped thumbnail         |
| GET    | `/api/detections/{detection_id}/enrichment`      | Get enrichment data           |
| GET    | `/api/detections/{detection_id}/video`           | Stream video                  |
| GET    | `/api/detections/{detection_id}/video/thumbnail` | Get video thumbnail           |

### List Detections

```bash
GET /api/detections?camera_id=front_door&object_type=person&min_confidence=0.8
```

**Parameters:**

| Name           | Type     | Description                                                                                                                                                                                                                                                                                              |
| -------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| camera_id      | string   | Filter by camera ID                                                                                                                                                                                                                                                                                      |
| object_type    | string   | Filter: `person`, `car`, `dog`, etc.                                                                                                                                                                                                                                                                     |
| start_date     | datetime | Filter after date                                                                                                                                                                                                                                                                                        |
| end_date       | datetime | Filter before date                                                                                                                                                                                                                                                                                       |
| min_confidence | float    | Minimum confidence (0.0-1.0)                                                                                                                                                                                                                                                                             |
| limit          | integer  | Max results (1-100, default: 50)                                                                                                                                                                                                                                                                         |
| offset         | integer  | Results to skip (deprecated, use cursor)                                                                                                                                                                                                                                                                 |
| cursor         | string   | Pagination cursor from previous response                                                                                                                                                                                                                                                                 |
| fields         | string   | Comma-separated fields for sparse response. Valid: `id`, `camera_id`, `file_path`, `file_type`, `detected_at`, `object_type`, `confidence`, `bbox_x`, `bbox_y`, `bbox_width`, `bbox_height`, `thumbnail_path`, `media_type`, `duration`, `video_codec`, `video_width`, `video_height`, `enrichment_data` |

**Response:**

```json
{
  "detections": [
    {
      "id": 1,
      "camera_id": "front_door",
      "file_path": "/export/foscam/front_door/20251223_120000.jpg",
      "file_type": "image/jpeg",
      "detected_at": "2025-12-23T12:00:00Z",
      "object_type": "person",
      "confidence": 0.95,
      "bbox_x": 100,
      "bbox_y": 150,
      "bbox_width": 200,
      "bbox_height": 400,
      "thumbnail_path": "/data/thumbnails/1_thumb.jpg",
      "media_type": "image"
    }
  ],
  "count": 1,
  "limit": 50,
  "offset": 0
}
```

### Object Types

Common objects detected by YOLO26:

| Type         | Description  |
| ------------ | ------------ |
| `person`     | Human being  |
| `car`        | Automobile   |
| `truck`      | Truck or van |
| `motorcycle` | Motorcycle   |
| `bicycle`    | Bicycle      |
| `dog`        | Dog          |
| `cat`        | Cat          |

### Video Streaming

Supports HTTP Range requests for seeking:

```bash
GET /api/detections/1/video
Range: bytes=0-1048575
```

Returns `206 Partial Content` with `Content-Range` header.

### Detection Image

Get detection image with bounding box overlay:

```bash
GET /api/detections/1/image
```

**Parameters:**

| Name | Type    | Description                                                |
| ---- | ------- | ---------------------------------------------------------- |
| full | boolean | Return full-size original without overlay (default: false) |

### Cropped Thumbnail

Get cropped thumbnail image focused on the detected object:

```bash
GET /api/detections/1/thumbnail
```

Returns JPEG/PNG image cropped to the bounding box area.

### Detection Labels

Get all unique detection labels with counts:

```bash
GET /api/detections/labels
```

**Response:**

```json
{
  "labels": [
    { "label": "person", "count": 450 },
    { "label": "car", "count": 180 },
    { "label": "dog", "count": 60 }
  ]
}
```

### Search Detections

Full-text search across detections:

```bash
GET /api/detections/search?q=person&labels=person,vehicle&min_confidence=0.8
```

**Parameters:**

| Name           | Type     | Description                       |
| -------------- | -------- | --------------------------------- |
| q              | string   | Search query (required)           |
| labels         | array    | Filter by label types             |
| min_confidence | float    | Minimum confidence (0.0-1.0)      |
| camera_id      | string   | Filter by camera ID               |
| start_date     | datetime | Filter after date                 |
| end_date       | datetime | Filter before date                |
| limit          | integer  | Max results (1-1000, default: 50) |
| offset         | integer  | Results to skip (default: 0)      |

### Detection Statistics

Get aggregate detection statistics:

```bash
GET /api/detections/stats
```

**Response:**

```json
{
  "total_count": 690,
  "avg_confidence": 0.87,
  "class_distribution": [
    { "object_type": "person", "count": 450 },
    { "object_type": "car", "count": 180 },
    { "object_type": "dog", "count": 60 }
  ]
}
```

### Bulk Operations

Create, update, or delete multiple detections. All operations support partial success and return HTTP 207 Multi-Status.

**Bulk Create:**

```bash
POST /api/detections/bulk
Content-Type: application/json

{
  "detections": [
    {
      "camera_id": "front_door",
      "file_path": "/export/foscam/front_door/image.jpg",
      "object_type": "person",
      "confidence": 0.95,
      "bbox_x": 100,
      "bbox_y": 150,
      "bbox_width": 200,
      "bbox_height": 400
    }
  ]
}
```

**Bulk Update:**

```bash
PATCH /api/detections/bulk
Content-Type: application/json

{
  "updates": [
    { "id": 1, "object_type": "person" },
    { "id": 2, "object_type": "car" }
  ]
}
```

**Bulk Delete:**

```bash
DELETE /api/detections/bulk
Content-Type: application/json

{
  "ids": [1, 2, 3]
}
```

Note: Detection deletion is always hard delete (soft-delete not supported for raw data).

### Export Detections

Export detections as CSV or JSON file for external analysis. Supports content negotiation via HTTP Accept header.

```bash
GET /api/detections/export?camera_id=front_door&object_type=person
Accept: text/csv
```

**Parameters:**

| Name           | Type     | Description                            |
| -------------- | -------- | -------------------------------------- |
| camera_id      | string   | Filter by camera ID                    |
| object_type    | string   | Filter: `person`, `car`, `dog`, etc.   |
| start_date     | datetime | Filter after date                      |
| end_date       | datetime | Filter before date                     |
| min_confidence | float    | Minimum confidence threshold (0.0-1.0) |

**Content Negotiation:**

| Accept Header        | Format | Description             |
| -------------------- | ------ | ----------------------- |
| `text/csv` (default) | CSV    | Comma-separated values  |
| `application/csv`    | CSV    | Alternative CSV request |
| `application/json`   | JSON   | JSON array format       |

**CSV Response:**

```csv
detection_id,camera_name,detected_at,object_type,confidence,bbox_x,bbox_y,bbox_width,bbox_height,file_path,thumbnail_path,media_type
12345,Front Door Camera,2026-01-15T10:30:00Z,person,0.95,100,150,200,400,/export/foscam/front_door/image.jpg,/data/thumbnails/12345_thumb.jpg,image
```

**JSON Response:**

```json
[
  {
    "detection_id": 12345,
    "camera_name": "Front Door Camera",
    "detected_at": "2026-01-15T10:30:00Z",
    "object_type": "person",
    "confidence": 0.95,
    "bbox_x": 100,
    "bbox_y": 150,
    "bbox_width": 200,
    "bbox_height": 400,
    "file_path": "/export/foscam/front_door/image.jpg",
    "thumbnail_path": "/data/thumbnails/12345_thumb.jpg",
    "media_type": "image"
  }
]
```

**Export Fields:**

| Field            | Type     | Description                          |
| ---------------- | -------- | ------------------------------------ |
| `detection_id`   | integer  | Unique detection identifier          |
| `camera_name`    | string   | Human-readable camera name           |
| `detected_at`    | datetime | ISO 8601 timestamp                   |
| `object_type`    | string   | Detected object type                 |
| `confidence`     | float    | Detection confidence score (0.0-1.0) |
| `bbox_x`         | integer  | Bounding box X coordinate            |
| `bbox_y`         | integer  | Bounding box Y coordinate            |
| `bbox_width`     | integer  | Bounding box width                   |
| `bbox_height`    | integer  | Bounding box height                  |
| `file_path`      | string   | Path to source image                 |
| `thumbnail_path` | string   | Path to thumbnail (may be null)      |
| `media_type`     | string   | `image` or `video`                   |

**Rate Limiting:**

Export endpoint is rate-limited to 10 requests per minute per client IP to prevent abuse.

**Errors:**

- `400` - Invalid date range (start_date after end_date)
- `429` - Rate limit exceeded

---

## Zones

Zones define areas of interest within camera views for targeted detection and alerting.

### Sparse Fieldsets

**Note:** The zones API does **not** support sparse fieldsets (`?fields=` parameter) unlike cameras, events, and detections endpoints. Zone responses are compact by design (typically 7-8 fields per zone), making field filtering unnecessary. The full zone object is always returned.

### Zone Configuration Architecture

Zones enable fine-grained detection filtering and contextual risk assessment. The following diagram shows how zones integrate with cameras and affect detection processing.

```mermaid
%%{init: {
  'theme': 'dark',
  'themeVariables': {
    'primaryColor': '#3B82F6',
    'primaryTextColor': '#FFFFFF',
    'primaryBorderColor': '#60A5FA',
    'secondaryColor': '#A855F7',
    'tertiaryColor': '#009688',
    'background': '#121212',
    'mainBkg': '#1a1a2e',
    'lineColor': '#666666'
  }
}}%%
flowchart TB
    subgraph Camera["Camera View (front_door)"]
        direction TB
        IMG[Camera Image<br/>1920x1080]
    end

    subgraph Zones["Defined Zones"]
        direction LR
        Z1[Zone: Front Door<br/>type: entry_point<br/>priority: 1<br/>color: #3B82F6]
        Z2[Zone: Driveway<br/>type: driveway<br/>priority: 2<br/>color: #FFB800]
        Z3[Zone: Sidewalk<br/>type: walkway<br/>priority: 3<br/>color: #64748B]
    end

    subgraph Processing["Detection Processing"]
        direction TB
        DET[Detection<br/>bbox: x,y,w,h]
        CHECK{Detection in Zone?}
        CONTEXT[Add Zone Context<br/>to LLM Prompt]
        ALERT[Trigger Alert Rule<br/>if zone_ids match]
    end

    IMG --> Z1
    IMG --> Z2
    IMG --> Z3

    Z1 --> DET
    Z2 --> DET
    Z3 --> DET

    DET --> CHECK
    CHECK -->|Yes| CONTEXT
    CHECK -->|Yes| ALERT
    CHECK -->|No| SKIP[Standard Processing]

    style Z1 fill:#3B82F6
    style Z2 fill:#FFB800,color:#000000
    style Z3 fill:#64748B
```

**Zone Types and Use Cases:**

| Zone Type     | Typical Use                     | Risk Impact                   |
| ------------- | ------------------------------- | ----------------------------- |
| `entry_point` | Doors, gates, windows           | Higher risk for unknowns      |
| `restricted`  | Private areas, off-limits zones | Maximum risk elevation        |
| `driveway`    | Vehicle areas, parking          | Vehicle-focused alerts        |
| `walkway`     | Sidewalks, common paths         | Lower risk (expected traffic) |
| `perimeter`   | Property boundaries             | Boundary breach detection     |
| `other`       | General purpose zones           | User-defined behavior         |

### Endpoints

| Method | Endpoint                                   | Description |
| ------ | ------------------------------------------ | ----------- |
| GET    | `/api/cameras/{camera_id}/zones`           | List zones  |
| POST   | `/api/cameras/{camera_id}/zones`           | Create zone |
| GET    | `/api/cameras/{camera_id}/zones/{zone_id}` | Get zone    |
| PUT    | `/api/cameras/{camera_id}/zones/{zone_id}` | Update zone |
| DELETE | `/api/cameras/{camera_id}/zones/{zone_id}` | Delete zone |

### List Zones

```bash
GET /api/cameras/front_door/zones?enabled=true
```

**Parameters:**

| Name    | Type    | Description                         |
| ------- | ------- | ----------------------------------- |
| enabled | boolean | Filter by enabled status (optional) |

**Response:**

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "camera_id": "front_door",
      "name": "Front Door",
      "zone_type": "entry_point",
      "coordinates": [
        [0.1, 0.2],
        [0.3, 0.2],
        [0.3, 0.8],
        [0.1, 0.8]
      ],
      "shape": "rectangle",
      "color": "#3B82F6",
      "enabled": true,
      "priority": 1
    }
  ],
  "pagination": {
    "total": 1,
    "limit": 1,
    "offset": 0,
    "has_more": false
  }
}
```

### Create Zone

```bash
POST /api/cameras/front_door/zones
Content-Type: application/json

{
  "name": "Front Door",
  "zone_type": "entry_point",
  "coordinates": [
    [0.1, 0.2],
    [0.3, 0.2],
    [0.3, 0.8],
    [0.1, 0.8]
  ],
  "shape": "rectangle",
  "color": "#3B82F6",
  "enabled": true,
  "priority": 1
}
```

**Zone Types:**

| Type          | Description               |
| ------------- | ------------------------- |
| `entry_point` | Entry/exit points (doors) |
| `restricted`  | Restricted areas          |
| `driveway`    | Driveway or parking       |
| `walkway`     | Sidewalks and paths       |
| `perimeter`   | Property boundary         |
| `other`       | General purpose           |

**Coordinate System:**

Coordinates are normalized (0.0-1.0):

- `(0.0, 0.0)` = top-left corner
- `(1.0, 1.0)` = bottom-right corner

---

## Entities

Entities track persons and vehicles across cameras using CLIP-based re-identification.

### Endpoints

| Method | Endpoint                               | Description                          |
| ------ | -------------------------------------- | ------------------------------------ |
| GET    | `/api/entities`                        | List tracked entities                |
| GET    | `/api/entities/matches/{detection_id}` | Find matching entities for detection |
| GET    | `/api/entities/{entity_id}`            | Get entity details                   |
| GET    | `/api/entities/{entity_id}/history`    | Get appearance timeline              |

### List Entities

```bash
GET /api/entities?entity_type=person&camera_id=front_door
```

**Parameters:**

| Name        | Type     | Description                       |
| ----------- | -------- | --------------------------------- |
| entity_type | string   | Filter: `person` or `vehicle`     |
| camera_id   | string   | Filter by camera ID               |
| since       | datetime | Filter entities seen since time   |
| limit       | integer  | Max results (1-1000, default: 50) |
| offset      | integer  | Results to skip (default: 0)      |

**Response:**

```json
{
  "entities": [
    {
      "id": "entity_abc123",
      "entity_type": "person",
      "first_seen": "2025-12-23T10:00:00Z",
      "last_seen": "2025-12-23T14:30:00Z",
      "appearance_count": 5,
      "cameras_seen": ["front_door", "backyard", "driveway"],
      "thumbnail_url": "/api/detections/123/image"
    }
  ],
  "count": 1,
  "limit": 50,
  "offset": 0
}
```

### Get Entity Details

```bash
GET /api/entities/entity_abc123
```

Returns entity with full appearance history including:

- Detection IDs
- Camera locations
- Timestamps
- Similarity scores
- Attributes (clothing, carrying items)

### Find Entity Matches

Find entities matching a specific detection's embedding:

```bash
GET /api/entities/matches/123?entity_type=person&threshold=0.85
```

**Parameters:**

| Name        | Type   | Description                                             |
| ----------- | ------ | ------------------------------------------------------- |
| entity_type | string | Type to search: `person` or `vehicle` (default: person) |
| threshold   | float  | Minimum cosine similarity (default: 0.85)               |

**Response:**

```json
{
  "detection_id": "123",
  "matches": [
    {
      "entity_id": "entity_abc123",
      "similarity": 0.92,
      "camera_id": "backyard",
      "detected_at": "2026-01-10T14:30:00Z",
      "thumbnail_url": "/api/detections/456/image"
    }
  ],
  "match_count": 1
}
```

**Errors:**

- `404` - Detection not found or no embedding stored
- `503` - Redis service unavailable

### Re-identification Architecture

- **Algorithm:** CLIP ViT-L 768-dimensional embeddings
- **Storage:** Redis with 24-hour TTL
- **Matching:** Cosine similarity (default threshold: 0.85)
- **Scope:** Today's and yesterday's embeddings

---

## Analytics

Analytics endpoints provide aggregated data for dashboards and reports.

### Endpoints

| Method | Endpoint                             | Description             |
| ------ | ------------------------------------ | ----------------------- |
| GET    | `/api/analytics/detection-trends`    | Daily detection counts  |
| GET    | `/api/analytics/risk-history`        | Risk score distribution |
| GET    | `/api/analytics/camera-uptime`       | Uptime per camera       |
| GET    | `/api/analytics/object-distribution` | Counts by object type   |

All analytics endpoints require `start_date` and `end_date` parameters (ISO date format: YYYY-MM-DD).

### Detection Trends

Get detection counts aggregated by day:

```bash
GET /api/analytics/detection-trends?start_date=2025-12-01&end_date=2025-12-31
```

**Parameters (required):**

| Name       | Type | Description            |
| ---------- | ---- | ---------------------- |
| start_date | date | Start date (inclusive) |
| end_date   | date | End date (inclusive)   |

**Response:**

```json
{
  "data_points": [
    { "date": "2025-12-01", "count": 45 },
    { "date": "2025-12-02", "count": 32 }
  ],
  "total_detections": 77,
  "start_date": "2025-12-01",
  "end_date": "2025-12-02"
}
```

### Risk History

```bash
GET /api/analytics/risk-history?start_date=2025-12-01&end_date=2025-12-31
```

**Response:**

```json
{
  "data_points": [
    {
      "date": "2025-12-01",
      "low": 10,
      "medium": 5,
      "high": 2,
      "critical": 0
    }
  ],
  "start_date": "2025-12-01",
  "end_date": "2025-12-31"
}
```

### Camera Uptime

Uptime is calculated as days with at least one detection:

```bash
GET /api/analytics/camera-uptime?start_date=2025-12-01&end_date=2025-12-31
```

**Response:**

```json
{
  "cameras": [
    {
      "camera_id": "front_door",
      "camera_name": "Front Door Camera",
      "uptime_percentage": 95.5,
      "detection_count": 1250
    }
  ],
  "start_date": "2025-12-01",
  "end_date": "2025-12-31"
}
```

### Object Distribution

```bash
GET /api/analytics/object-distribution?start_date=2025-12-01&end_date=2025-12-31
```

**Response:**

```json
{
  "object_types": [
    { "object_type": "person", "count": 450, "percentage": 65.2 },
    { "object_type": "car", "count": 180, "percentage": 26.1 },
    { "object_type": "dog", "count": 60, "percentage": 8.7 }
  ],
  "total_detections": 690,
  "start_date": "2025-12-01",
  "end_date": "2025-12-31"
}
```

---

## Related Documentation

- [AI Pipeline API](ai-pipeline.md) - Enrichment and batch processing
- [System Operations API](system-ops.md) - Health and configuration
- [Real-time API](realtime.md) - WebSocket streams
