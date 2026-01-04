---
title: Cameras API
description: REST API endpoints for camera management, baseline activity, and scene change detection
source_refs:
  - backend/api/routes/cameras.py
  - backend/api/schemas/camera.py
  - backend/api/schemas/baseline.py
  - backend/api/schemas/scene_change.py
  - backend/models/camera.py
  - backend/models/scene_change.py
  - backend/services/baseline.py
---

# Cameras API

The Cameras API provides CRUD operations for managing security cameras in the system. Each camera represents a physical device that uploads images to a configured folder path.

In addition to basic camera management, this API includes:

- **Baseline Activity Tracking**: Monitor activity patterns and detect anomalies based on historical behavior
- **Scene Change Detection**: Detect camera tampering, angle changes, or blocked views with acknowledgement workflow

## Endpoints Overview

| Method | Endpoint                                                  | Description                  |
| ------ | --------------------------------------------------------- | ---------------------------- |
| GET    | `/api/cameras`                                            | List all cameras             |
| GET    | `/api/cameras/{camera_id}`                                | Get camera by ID             |
| POST   | `/api/cameras`                                            | Create new camera            |
| PATCH  | `/api/cameras/{camera_id}`                                | Update camera                |
| DELETE | `/api/cameras/{camera_id}`                                | Delete camera                |
| GET    | `/api/cameras/{camera_id}/snapshot`                       | Get latest snapshot image    |
| GET    | `/api/cameras/validation/paths`                           | Validate camera folder paths |
| GET    | `/api/cameras/{camera_id}/baseline`                       | Get baseline activity data   |
| GET    | `/api/cameras/{camera_id}/baseline/anomalies`             | Get recent anomaly events    |
| GET    | `/api/cameras/{camera_id}/scene-changes`                  | List scene changes           |
| POST   | `/api/cameras/{camera_id}/scene-changes/{id}/acknowledge` | Acknowledge a scene change   |

---

## GET /api/cameras

List all cameras with optional status filter.

**Source:** [`list_cameras`](../../backend/api/routes/cameras.py:35)

**Parameters:**

| Name     | Type   | In    | Required | Description                                           |
| -------- | ------ | ----- | -------- | ----------------------------------------------------- |
| `status` | string | query | No       | Filter by camera status: `online`, `offline`, `error` |

**Response:** `200 OK`

```json
{
  "cameras": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
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

**Response Fields:**

| Field     | Type    | Description             |
| --------- | ------- | ----------------------- |
| `cameras` | array   | List of camera objects  |
| `count`   | integer | Total number of cameras |

**Example Request:**

```bash
# List all cameras
curl http://localhost:8000/api/cameras

# Filter by status
curl "http://localhost:8000/api/cameras?status=online"
```

---

## GET /api/cameras/{camera_id}

Get a specific camera by its UUID.

**Source:** [`get_camera`](../../backend/api/routes/cameras.py:64)

**Parameters:**

| Name        | Type   | In   | Required | Description        |
| ----------- | ------ | ---- | -------- | ------------------ |
| `camera_id` | string | path | Yes      | UUID of the camera |

**Response:** `200 OK`

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Front Door Camera",
  "folder_path": "/export/foscam/front_door",
  "status": "online",
  "created_at": "2025-12-23T10:00:00Z",
  "last_seen_at": "2025-12-23T12:00:00Z"
}
```

**Response Fields:**

| Field          | Type   | Description                                    |
| -------------- | ------ | ---------------------------------------------- |
| `id`           | string | Camera UUID                                    |
| `name`         | string | Camera display name                            |
| `folder_path`  | string | Filesystem path for camera uploads             |
| `status`       | string | Current status: `online`, `offline`, `error`   |
| `created_at`   | string | ISO 8601 creation timestamp                    |
| `last_seen_at` | string | ISO 8601 timestamp of last activity (nullable) |

**Errors:**

| Code | Description                        |
| ---- | ---------------------------------- |
| 404  | Camera with specified ID not found |

**Example Request:**

```bash
curl http://localhost:8000/api/cameras/123e4567-e89b-12d3-a456-426614174000
```

---

## POST /api/cameras

Create a new camera.

**Source:** [`create_camera`](../../backend/api/routes/cameras.py:94)

**Request Body:**

```json
{
  "name": "Front Door Camera",
  "folder_path": "/export/foscam/front_door",
  "status": "online"
}
```

**Request Fields:**

| Field         | Type   | Required | Description                                           |
| ------------- | ------ | -------- | ----------------------------------------------------- |
| `name`        | string | Yes      | Camera name (1-255 characters)                        |
| `folder_path` | string | Yes      | Filesystem path for camera uploads (1-500 characters) |
| `status`      | string | No       | Initial status, default: `online`                     |

**Response:** `201 Created`

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Front Door Camera",
  "folder_path": "/export/foscam/front_door",
  "status": "online",
  "created_at": "2025-12-23T10:00:00Z",
  "last_seen_at": null
}
```

**Errors:**

| Code | Description                             |
| ---- | --------------------------------------- |
| 422  | Validation error - invalid field values |

**Example Request:**

```bash
curl -X POST http://localhost:8000/api/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Front Door Camera",
    "folder_path": "/export/foscam/front_door",
    "status": "online"
  }'
```

**Audit Log:**

This operation creates an audit log entry with action `camera_created`.

---

## PATCH /api/cameras/{camera_id}

Update an existing camera. Only provided fields are updated.

**Source:** [`update_camera`](../../backend/api/routes/cameras.py:141)

**Parameters:**

| Name        | Type   | In   | Required | Description        |
| ----------- | ------ | ---- | -------- | ------------------ |
| `camera_id` | string | path | Yes      | UUID of the camera |

**Request Body:**

```json
{
  "name": "Front Door Camera - Updated",
  "status": "offline"
}
```

**Request Fields:**

| Field         | Type   | Required | Description                                           |
| ------------- | ------ | -------- | ----------------------------------------------------- |
| `name`        | string | No       | Camera name (1-255 characters)                        |
| `folder_path` | string | No       | Filesystem path for camera uploads (1-500 characters) |
| `status`      | string | No       | Camera status                                         |

**Response:** `200 OK`

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Front Door Camera - Updated",
  "folder_path": "/export/foscam/front_door",
  "status": "offline",
  "created_at": "2025-12-23T10:00:00Z",
  "last_seen_at": "2025-12-23T12:00:00Z"
}
```

**Errors:**

| Code | Description                             |
| ---- | --------------------------------------- |
| 404  | Camera with specified ID not found      |
| 422  | Validation error - invalid field values |

**Example Request:**

```bash
curl -X PATCH http://localhost:8000/api/cameras/123e4567-e89b-12d3-a456-426614174000 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "offline"
  }'
```

**Audit Log:**

This operation creates an audit log entry with action `camera_updated`, including old and new values for changed fields.

---

## DELETE /api/cameras/{camera_id}

Delete a camera. This operation cascades to delete all related detections and events.

**Source:** [`delete_camera`](../../backend/api/routes/cameras.py:209)

**Parameters:**

| Name        | Type   | In   | Required | Description        |
| ----------- | ------ | ---- | -------- | ------------------ |
| `camera_id` | string | path | Yes      | UUID of the camera |

**Response:** `204 No Content`

No response body.

**Errors:**

| Code | Description                        |
| ---- | ---------------------------------- |
| 404  | Camera with specified ID not found |

**Example Request:**

```bash
curl -X DELETE http://localhost:8000/api/cameras/123e4567-e89b-12d3-a456-426614174000
```

**Audit Log:**

This operation creates an audit log entry with action `camera_deleted`.

**Warning:** This operation is destructive. All detections and events associated with the camera will also be deleted.

---

## GET /api/cameras/{camera_id}/snapshot

Get the latest snapshot image from a camera. Returns the most recently modified image file from the camera's configured folder path.

**Source:** [`get_camera_snapshot`](../../backend/api/routes/cameras.py:257)

**Parameters:**

| Name        | Type   | In   | Required | Description        |
| ----------- | ------ | ---- | -------- | ------------------ |
| `camera_id` | string | path | Yes      | UUID of the camera |

**Response:** `200 OK`

Binary image data with appropriate `Content-Type` header:

- `image/jpeg` for `.jpg`/`.jpeg` files
- `image/png` for `.png` files
- `image/gif` for `.gif` files

**Response Headers:**

| Header                | Description                             |
| --------------------- | --------------------------------------- |
| `Content-Type`        | MIME type of the image                  |
| `Content-Disposition` | `attachment; filename="image_name.jpg"` |

**Errors:**

| Code | Description                                       |
| ---- | ------------------------------------------------- |
| 404  | Camera not found                                  |
| 404  | Camera folder does not exist                      |
| 404  | No snapshot images found for camera               |
| 404  | No snapshot available (folder path misconfigured) |

**Example Request:**

```bash
# Download snapshot
curl -o snapshot.jpg http://localhost:8000/api/cameras/123e4567-e89b-12d3-a456-426614174000/snapshot

# View in browser (open URL directly)
# http://localhost:8000/api/cameras/123e4567-e89b-12d3-a456-426614174000/snapshot
```

**Security Note:**

The endpoint validates that the camera's folder path is within the configured `foscam_base_path` to prevent directory traversal attacks.

---

## GET /api/cameras/validation/paths

Validate all camera folder paths against the configured base path. Use this endpoint to diagnose cameras that show "No snapshot available" errors.

**Source:** [`validate_camera_paths`](../../backend/api/routes/cameras.py:524)

**Parameters:**

None.

**Response:** `200 OK`

```json
{
  "base_path": "/export/foscam",
  "total_cameras": 4,
  "valid_count": 3,
  "invalid_count": 1,
  "valid_cameras": [
    {
      "id": "front_door",
      "name": "Front Door",
      "folder_path": "/export/foscam/front_door",
      "status": "online"
    }
  ],
  "invalid_cameras": [
    {
      "id": "garage",
      "name": "Garage Camera",
      "folder_path": "/old/path/garage",
      "status": "error",
      "resolved_path": "/old/path/garage",
      "issues": ["folder_path not under base_path (/export/foscam)", "directory does not exist"]
    }
  ]
}
```

**Response Fields:**

| Field             | Type    | Description                                           |
| ----------------- | ------- | ----------------------------------------------------- |
| `base_path`       | string  | Configured FOSCAM_BASE_PATH                           |
| `total_cameras`   | integer | Total number of cameras in database                   |
| `valid_count`     | integer | Number of cameras with valid paths                    |
| `invalid_count`   | integer | Number of cameras with invalid paths                  |
| `valid_cameras`   | array   | List of cameras with valid folder paths               |
| `invalid_cameras` | array   | List of cameras with issues (includes `issues` array) |

**Example Request:**

```bash
curl http://localhost:8000/api/cameras/validation/paths
```

**Use Cases:**

- Diagnose why camera snapshots are not loading
- Verify folder paths after environment changes (Docker vs native)
- Identify cameras needing folder path updates

---

## GET /api/cameras/{camera_id}/baseline

Get baseline activity data for a camera. Returns comprehensive baseline statistics used for anomaly detection.

**Source:** [`get_camera_baseline`](../../backend/api/routes/cameras.py:597)

**Parameters:**

| Name        | Type   | In   | Required | Description      |
| ----------- | ------ | ---- | -------- | ---------------- |
| `camera_id` | string | path | Yes      | ID of the camera |

**Response:** `200 OK`

```json
{
  "camera_id": "front_door",
  "camera_name": "Front Door",
  "baseline_established": "2026-01-01T00:00:00Z",
  "data_points": 720,
  "hourly_patterns": {
    "0": { "avg_detections": 0.5, "std_dev": 0.3, "sample_count": 30 },
    "8": { "avg_detections": 3.2, "std_dev": 0.8, "sample_count": 30 },
    "17": { "avg_detections": 5.2, "std_dev": 1.1, "sample_count": 30 }
  },
  "daily_patterns": {
    "monday": { "avg_detections": 45.0, "peak_hour": 17, "total_samples": 168 },
    "saturday": { "avg_detections": 32.0, "peak_hour": 14, "total_samples": 168 }
  },
  "object_baselines": {
    "person": { "avg_hourly": 2.3, "peak_hour": 17, "total_detections": 550 },
    "vehicle": { "avg_hourly": 0.8, "peak_hour": 8, "total_detections": 192 }
  },
  "current_deviation": {
    "score": 1.8,
    "interpretation": "slightly_above_normal",
    "contributing_factors": ["person_count_elevated"]
  }
}
```

**Response Fields:**

| Field                  | Type     | Description                                                 |
| ---------------------- | -------- | ----------------------------------------------------------- |
| `camera_id`            | string   | Camera ID                                                   |
| `camera_name`          | string   | Human-readable camera name                                  |
| `baseline_established` | datetime | When baseline data collection started (null if no data)     |
| `data_points`          | integer  | Total number of data points in baseline                     |
| `hourly_patterns`      | object   | Activity patterns by hour (0-23)                            |
| `daily_patterns`       | object   | Activity patterns by day of week                            |
| `object_baselines`     | object   | Baseline statistics by object type                          |
| `current_deviation`    | object   | Current deviation from baseline (null if insufficient data) |

**Hourly Pattern Fields:**

| Field            | Type    | Description                                   |
| ---------------- | ------- | --------------------------------------------- |
| `avg_detections` | float   | Average number of detections during this hour |
| `std_dev`        | float   | Standard deviation of detection count         |
| `sample_count`   | integer | Number of samples used for calculation        |

**Daily Pattern Fields:**

| Field            | Type    | Description                               |
| ---------------- | ------- | ----------------------------------------- |
| `avg_detections` | float   | Average number of detections for this day |
| `peak_hour`      | integer | Hour with most activity (0-23)            |
| `total_samples`  | integer | Total samples for this day                |

**Object Baseline Fields:**

| Field              | Type    | Description                                    |
| ------------------ | ------- | ---------------------------------------------- |
| `avg_hourly`       | float   | Average hourly detection count for this object |
| `peak_hour`        | integer | Hour with most detections of this type (0-23)  |
| `total_detections` | integer | Total detections in the baseline period        |

**Current Deviation Fields:**

| Field                  | Type   | Description                                |
| ---------------------- | ------ | ------------------------------------------ |
| `score`                | float  | Deviation score (z-score, can be negative) |
| `interpretation`       | string | Human-readable interpretation              |
| `contributing_factors` | array  | Factors contributing to current deviation  |

**Interpretation Values:**

- `far_below_normal` - Activity is significantly below baseline (z < -2.0)
- `below_normal` - Activity is below baseline (-2.0 <= z < -1.0)
- `normal` - Activity matches baseline (-1.0 <= z < 1.0)
- `slightly_above_normal` - Activity slightly elevated (1.0 <= z < 2.0)
- `above_normal` - Activity elevated (2.0 <= z < 3.0)
- `far_above_normal` - Activity significantly elevated (z >= 3.0)

**Errors:**

| Code | Description                        |
| ---- | ---------------------------------- |
| 404  | Camera with specified ID not found |

**Example Request:**

```bash
curl http://localhost:8000/api/cameras/front_door/baseline
```

**Use Cases:**

- Display camera activity patterns on dashboard
- Understand typical activity levels for each camera
- Monitor current deviation for anomaly alerts
- Identify peak activity hours for security planning

---

## GET /api/cameras/{camera_id}/baseline/anomalies

Get recent anomaly events for a camera. Anomalies are detections that significantly deviate from established baseline activity patterns.

**Source:** [`get_camera_baseline_anomalies`](../../backend/api/routes/cameras.py:658)

**Parameters:**

| Name        | Type    | In    | Required | Description                                    |
| ----------- | ------- | ----- | -------- | ---------------------------------------------- |
| `camera_id` | string  | path  | Yes      | ID of the camera                               |
| `days`      | integer | query | No       | Number of days to look back (1-90, default: 7) |

**Response:** `200 OK`

```json
{
  "camera_id": "front_door",
  "anomalies": [
    {
      "timestamp": "2026-01-03T02:30:00Z",
      "detection_class": "vehicle",
      "anomaly_score": 0.95,
      "expected_frequency": 0.1,
      "observed_frequency": 5.0,
      "reason": "Vehicle detected at 2:30 AM when rarely seen at this hour"
    }
  ],
  "count": 1,
  "period_days": 7
}
```

**Response Fields:**

| Field         | Type    | Description                          |
| ------------- | ------- | ------------------------------------ |
| `camera_id`   | string  | Camera ID                            |
| `anomalies`   | array   | List of anomaly events               |
| `count`       | integer | Total number of anomalies returned   |
| `period_days` | integer | Number of days covered by this query |

**Anomaly Event Fields:**

| Field                | Type     | Description                                       |
| -------------------- | -------- | ------------------------------------------------- |
| `timestamp`          | datetime | When the anomaly was detected                     |
| `detection_class`    | string   | Object class that triggered the anomaly           |
| `anomaly_score`      | float    | Anomaly score (0.0-1.0, higher is more anomalous) |
| `expected_frequency` | float    | Expected frequency for this class at this time    |
| `observed_frequency` | float    | Observed frequency that triggered the anomaly     |
| `reason`             | string   | Human-readable explanation                        |

**Errors:**

| Code | Description                        |
| ---- | ---------------------------------- |
| 404  | Camera with specified ID not found |

**Example Request:**

```bash
# Get anomalies from the last 7 days (default)
curl http://localhost:8000/api/cameras/front_door/baseline/anomalies

# Get anomalies from the last 30 days
curl "http://localhost:8000/api/cameras/front_door/baseline/anomalies?days=30"
```

**Use Cases:**

- Review unusual activity that may indicate security concerns
- Monitor for late-night vehicle/person activity
- Identify patterns that deviate from normal behavior
- Generate alerts for security dashboard

---

## GET /api/cameras/{camera_id}/scene-changes

Get scene changes for a camera. Scene changes indicate potential camera tampering, angle changes, or blocked views that may require attention.

**Source:** [`get_camera_scene_changes`](../../backend/api/routes/cameras.py:703)

**Parameters:**

| Name           | Type    | In    | Required | Description                                   |
| -------------- | ------- | ----- | -------- | --------------------------------------------- |
| `camera_id`    | string  | path  | Yes      | ID of the camera                              |
| `acknowledged` | boolean | query | No       | Filter by acknowledgement status (null = all) |
| `limit`        | integer | query | No       | Maximum results (1-1000, default: 50)         |
| `offset`       | integer | query | No       | Number of results to skip (default: 0)        |

**Response:** `200 OK`

```json
{
  "camera_id": "front_door",
  "scene_changes": [
    {
      "id": 1,
      "detected_at": "2026-01-03T10:30:00Z",
      "change_type": "view_blocked",
      "similarity_score": 0.23,
      "acknowledged": false,
      "acknowledged_at": null,
      "file_path": "/export/foscam/front_door/image.jpg"
    },
    {
      "id": 2,
      "detected_at": "2026-01-02T14:15:00Z",
      "change_type": "angle_changed",
      "similarity_score": 0.45,
      "acknowledged": true,
      "acknowledged_at": "2026-01-02T15:00:00Z",
      "file_path": null
    }
  ],
  "total_changes": 2
}
```

**Response Fields:**

| Field           | Type    | Description                   |
| --------------- | ------- | ----------------------------- |
| `camera_id`     | string  | Camera ID                     |
| `scene_changes` | array   | List of scene change events   |
| `total_changes` | integer | Total number of scene changes |

**Scene Change Fields:**

| Field              | Type     | Description                                         |
| ------------------ | -------- | --------------------------------------------------- |
| `id`               | integer  | Unique scene change ID                              |
| `detected_at`      | datetime | When the scene change was detected                  |
| `change_type`      | string   | Type of change detected                             |
| `similarity_score` | float    | SSIM similarity score (0-1, lower = more different) |
| `acknowledged`     | boolean  | Whether the change has been reviewed                |
| `acknowledged_at`  | datetime | When the change was acknowledged (nullable)         |
| `file_path`        | string   | Path to the triggering image (nullable)             |

**Change Types:**

| Value           | Description                                            |
| --------------- | ------------------------------------------------------ |
| `view_blocked`  | Camera view appears blocked or covered                 |
| `angle_changed` | Camera angle has shifted from baseline position        |
| `view_tampered` | Camera view appears to be intentionally manipulated    |
| `unknown`       | Scene change detected but type could not be determined |

**Errors:**

| Code | Description                        |
| ---- | ---------------------------------- |
| 404  | Camera with specified ID not found |

**Example Requests:**

```bash
# Get all scene changes
curl http://localhost:8000/api/cameras/front_door/scene-changes

# Get only unacknowledged scene changes
curl "http://localhost:8000/api/cameras/front_door/scene-changes?acknowledged=false"

# Paginate results
curl "http://localhost:8000/api/cameras/front_door/scene-changes?limit=10&offset=0"
```

**Use Cases:**

- Monitor for camera tampering attempts
- Alert operators when camera angles shift
- Track blocked or obstructed camera views
- Review and acknowledge resolved scene change alerts

---

## POST /api/cameras/{camera_id}/scene-changes/{scene_change_id}/acknowledge

Acknowledge a scene change alert. Marks a scene change as reviewed to indicate it has been addressed or is a known condition.

**Source:** [`acknowledge_scene_change`](../../backend/api/routes/cameras.py:781)

**Parameters:**

| Name              | Type    | In   | Required | Description                           |
| ----------------- | ------- | ---- | -------- | ------------------------------------- |
| `camera_id`       | string  | path | Yes      | ID of the camera                      |
| `scene_change_id` | integer | path | Yes      | ID of the scene change to acknowledge |

**Request Body:**

None required.

**Response:** `200 OK`

```json
{
  "id": 1,
  "acknowledged": true,
  "acknowledged_at": "2026-01-03T11:00:00Z"
}
```

**Response Fields:**

| Field             | Type     | Description                          |
| ----------------- | -------- | ------------------------------------ |
| `id`              | integer  | Scene change ID                      |
| `acknowledged`    | boolean  | Acknowledgement status (always true) |
| `acknowledged_at` | datetime | When the change was acknowledged     |

**Errors:**

| Code | Description                                              |
| ---- | -------------------------------------------------------- |
| 404  | Camera with specified ID not found                       |
| 404  | Scene change with specified ID not found for this camera |

**Example Request:**

```bash
curl -X POST http://localhost:8000/api/cameras/front_door/scene-changes/1/acknowledge
```

**Audit Log:**

This operation creates an audit log entry with action `event_reviewed`.

**Use Cases:**

- Mark a scene change as reviewed after investigation
- Clear alerts from the security dashboard
- Track which scene changes have been addressed
- Maintain audit trail of operator acknowledgements

---

## Data Models

### Camera

Full camera response model.

**Source:** [`CameraResponse`](../../backend/api/schemas/camera.py:47)

| Field          | Type     | Description                                  |
| -------------- | -------- | -------------------------------------------- |
| `id`           | string   | Camera UUID                                  |
| `name`         | string   | Camera display name                          |
| `folder_path`  | string   | Filesystem path for camera uploads           |
| `status`       | string   | Current status: `online`, `offline`, `error` |
| `created_at`   | datetime | When the camera was created                  |
| `last_seen_at` | datetime | Last time camera was active (nullable)       |

### CameraCreate

Request model for creating a camera.

**Source:** [`CameraCreate`](../../backend/api/schemas/camera.py:8)

| Field         | Type   | Required | Constraints | Description                        |
| ------------- | ------ | -------- | ----------- | ---------------------------------- |
| `name`        | string | Yes      | 1-255 chars | Camera name                        |
| `folder_path` | string | Yes      | 1-500 chars | Filesystem path                    |
| `status`      | string | No       | -           | Initial status (default: `online`) |

### CameraUpdate

Request model for updating a camera.

**Source:** [`CameraUpdate`](../../backend/api/schemas/camera.py:28)

| Field         | Type   | Required | Constraints | Description     |
| ------------- | ------ | -------- | ----------- | --------------- |
| `name`        | string | No       | 1-255 chars | Camera name     |
| `folder_path` | string | No       | 1-500 chars | Filesystem path |
| `status`      | string | No       | -           | Camera status   |

### CameraListResponse

Response model for camera list.

**Source:** [`CameraListResponse`](../../backend/api/schemas/camera.py:72)

| Field     | Type          | Description             |
| --------- | ------------- | ----------------------- |
| `cameras` | array[Camera] | List of camera objects  |
| `count`   | integer       | Total number of cameras |

---

### BaselineSummaryResponse

Response model for camera baseline data.

**Source:** [`BaselineSummaryResponse`](../../backend/api/schemas/baseline.py:143)

| Field                  | Type                   | Description                                |
| ---------------------- | ---------------------- | ------------------------------------------ |
| `camera_id`            | string                 | Camera ID                                  |
| `camera_name`          | string                 | Human-readable camera name                 |
| `baseline_established` | datetime (nullable)    | When baseline data collection started      |
| `data_points`          | integer                | Total number of data points in baseline    |
| `hourly_patterns`      | object[HourlyPattern]  | Activity patterns by hour (0-23)           |
| `daily_patterns`       | object[DailyPattern]   | Activity patterns by day of week           |
| `object_baselines`     | object[ObjectBaseline] | Baseline statistics by object type         |
| `current_deviation`    | CurrentDeviation       | Current deviation from baseline (nullable) |

### HourlyPattern

Activity pattern for a specific hour of the day.

**Source:** [`HourlyPattern`](../../backend/api/schemas/baseline.py:24)

| Field            | Type    | Description                                   |
| ---------------- | ------- | --------------------------------------------- |
| `avg_detections` | float   | Average number of detections during this hour |
| `std_dev`        | float   | Standard deviation of detection count         |
| `sample_count`   | integer | Number of samples used for calculation        |

### DailyPattern

Activity pattern for a specific day of the week.

**Source:** [`DailyPattern`](../../backend/api/schemas/baseline.py:54)

| Field            | Type    | Description                               |
| ---------------- | ------- | ----------------------------------------- |
| `avg_detections` | float   | Average number of detections for this day |
| `peak_hour`      | integer | Hour with most activity (0-23)            |
| `total_samples`  | integer | Total samples for this day                |

### ObjectBaseline

Baseline statistics for a specific detected object class.

**Source:** [`ObjectBaseline`](../../backend/api/schemas/baseline.py:85)

| Field              | Type    | Description                                    |
| ------------------ | ------- | ---------------------------------------------- |
| `avg_hourly`       | float   | Average hourly detection count for this object |
| `peak_hour`        | integer | Hour with most detections of this type (0-23)  |
| `total_detections` | integer | Total detections in the baseline period        |

### CurrentDeviation

Current activity deviation from established baseline.

**Source:** [`CurrentDeviation`](../../backend/api/schemas/baseline.py:116)

| Field                  | Type   | Description                                              |
| ---------------------- | ------ | -------------------------------------------------------- |
| `score`                | float  | Deviation score (z-score, standard deviations from mean) |
| `interpretation`       | string | Human-readable interpretation (see values below)         |
| `contributing_factors` | array  | Factors contributing to current deviation                |

**Interpretation Enum Values:**

| Value                   | Description            |
| ----------------------- | ---------------------- |
| `far_below_normal`      | z-score < -2.0         |
| `below_normal`          | -2.0 <= z-score < -1.0 |
| `normal`                | -1.0 <= z-score < 1.0  |
| `slightly_above_normal` | 1.0 <= z-score < 2.0   |
| `above_normal`          | 2.0 <= z-score < 3.0   |
| `far_above_normal`      | z-score >= 3.0         |

### AnomalyListResponse

Response model for camera anomaly list.

**Source:** [`AnomalyListResponse`](../../backend/api/schemas/baseline.py:260)

| Field         | Type                | Description                          |
| ------------- | ------------------- | ------------------------------------ |
| `camera_id`   | string              | Camera ID                            |
| `anomalies`   | array[AnomalyEvent] | List of recent anomaly events        |
| `count`       | integer             | Total number of anomalies returned   |
| `period_days` | integer             | Number of days covered by this query |

### AnomalyEvent

A single anomaly event detected for a camera.

**Source:** [`AnomalyEvent`](../../backend/api/schemas/baseline.py:214)

| Field                | Type     | Description                                       |
| -------------------- | -------- | ------------------------------------------------- |
| `timestamp`          | datetime | When the anomaly was detected                     |
| `detection_class`    | string   | Object class that triggered the anomaly           |
| `anomaly_score`      | float    | Anomaly score (0.0-1.0, higher is more anomalous) |
| `expected_frequency` | float    | Expected frequency for this class at this time    |
| `observed_frequency` | float    | Observed frequency that triggered the anomaly     |
| `reason`             | string   | Human-readable explanation                        |

### SceneChangeListResponse

Response model for listing scene changes.

**Source:** [`SceneChangeListResponse`](../../backend/api/schemas/scene_change.py:66)

| Field           | Type                       | Description                   |
| --------------- | -------------------------- | ----------------------------- |
| `camera_id`     | string                     | Camera ID                     |
| `scene_changes` | array[SceneChangeResponse] | List of scene changes         |
| `total_changes` | integer                    | Total number of scene changes |

### SceneChangeResponse

Response model for a single scene change event.

**Source:** [`SceneChangeResponse`](../../backend/api/schemas/scene_change.py:22)

| Field              | Type                | Description                                         |
| ------------------ | ------------------- | --------------------------------------------------- |
| `id`               | integer             | Unique scene change ID                              |
| `detected_at`      | datetime            | When the scene change was detected                  |
| `change_type`      | string              | Type of change (see enum values below)              |
| `similarity_score` | float               | SSIM similarity score (0-1, lower = more different) |
| `acknowledged`     | boolean             | Whether the change has been acknowledged            |
| `acknowledged_at`  | datetime (nullable) | When the change was acknowledged                    |
| `file_path`        | string (nullable)   | Path to the triggering image                        |

**SceneChangeType Enum Values:**

| Value           | Description                                   |
| --------------- | --------------------------------------------- |
| `view_blocked`  | Camera view appears blocked or covered        |
| `angle_changed` | Camera angle has shifted from baseline        |
| `view_tampered` | Camera view appears intentionally manipulated |
| `unknown`       | Scene change type could not be determined     |

### SceneChangeAcknowledgeResponse

Response model for acknowledging a scene change.

**Source:** [`SceneChangeAcknowledgeResponse`](../../backend/api/schemas/scene_change.py:99)

| Field             | Type     | Description                          |
| ----------------- | -------- | ------------------------------------ |
| `id`              | integer  | Scene change ID                      |
| `acknowledged`    | boolean  | Acknowledgement status (always true) |
| `acknowledged_at` | datetime | When the change was acknowledged     |

---

## Related Documentation

- [Events API](events.md) - Events are linked to cameras
- [Detections API](detections.md) - Detections are linked to cameras
- [System API](system.md) - System stats include camera counts
- [Baseline Service](../../backend/services/baseline.py) - Baseline calculation logic
- [Scene Change Detector](../../backend/services/scene_change_detector.py) - Scene change detection logic
