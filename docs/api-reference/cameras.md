---
title: Cameras API
description: REST API endpoints for camera management
source_refs:
  - backend/api/routes/cameras.py
  - backend/api/schemas/camera.py
  - backend/models/camera.py
---

# Cameras API

The Cameras API provides CRUD operations for managing security cameras in the system. Each camera represents a physical device that uploads images to a configured folder path.

## Endpoints Overview

| Method | Endpoint                            | Description               |
| ------ | ----------------------------------- | ------------------------- |
| GET    | `/api/cameras`                      | List all cameras          |
| GET    | `/api/cameras/{camera_id}`          | Get camera by ID          |
| POST   | `/api/cameras`                      | Create new camera         |
| PATCH  | `/api/cameras/{camera_id}`          | Update camera             |
| DELETE | `/api/cameras/{camera_id}`          | Delete camera             |
| GET    | `/api/cameras/{camera_id}/snapshot` | Get latest snapshot image |

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

| Code | Description                                               |
| ---- | --------------------------------------------------------- |
| 403  | Camera folder_path is outside configured foscam_base_path |
| 404  | Camera not found                                          |
| 404  | Camera folder does not exist                              |
| 404  | No snapshot images found for camera                       |

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

## Related Documentation

- [Events API](events.md) - Events are linked to cameras
- [Detections API](detections.md) - Detections are linked to cameras
- [System API](system.md) - System stats include camera counts
