# Camera Endpoints

> REST API endpoints for camera management.

**Time to read:** ~4 min
**Prerequisites:** [API Overview](overview.md)

---

## Overview

The Camera API provides CRUD operations for managing security cameras. Cameras represent physical camera devices that upload images via FTP.

**Base path:** `/api/cameras`

## Endpoints

### List Cameras

```
GET /api/cameras
```

Returns all cameras, optionally filtered by status.

**Query Parameters:**

| Parameter | Type   | Description                                    |
| --------- | ------ | ---------------------------------------------- |
| `status`  | string | Filter by status: `online`, `offline`, `error` |

**Response:** `200 OK`

```json
{
  "cameras": [
    {
      "id": "uuid-string",
      "name": "Front Door",
      "folder_path": "/export/foscam/front_door",
      "status": "online",
      "created_at": "2025-01-15T10:00:00Z",
      "updated_at": "2025-01-15T10:00:00Z"
    }
  ],
  "count": 1
}
```

### Get Camera

```
GET /api/cameras/{camera_id}
```

Returns a single camera by ID.

**Response:** `200 OK` or `404 Not Found`

### Create Camera

```
POST /api/cameras
```

Creates a new camera.

**Request Body:**

```json
{
  "name": "Back Yard",
  "folder_path": "/export/foscam/back_yard",
  "status": "online"
}
```

**Response:** `201 Created`

### Update Camera

```
PATCH /api/cameras/{camera_id}
```

Updates an existing camera. All fields are optional.

**Request Body:**

```json
{
  "name": "Back Yard (Updated)",
  "status": "offline"
}
```

**Response:** `200 OK` or `404 Not Found`

### Delete Camera

```
DELETE /api/cameras/{camera_id}
```

Deletes a camera and all associated events/detections.

**Response:** `204 No Content` or `404 Not Found`

### Get Camera Snapshot

```
GET /api/cameras/{camera_id}/snapshot
```

Returns the most recent image from the camera's folder.

**Response:** Image file (JPEG/PNG) or `404 Not Found`

## Camera Status Values

| Status    | Description                                        |
| --------- | -------------------------------------------------- |
| `online`  | Camera is operational and uploading images         |
| `offline` | Camera is not uploading (intentional or scheduled) |
| `error`   | Camera has a problem (connectivity, hardware)      |

## Folder Path Configuration

The `folder_path` must be within the configured `FOSCAM_BASE_PATH`:

- Default: `/export/foscam`
- Camera paths are validated to prevent directory traversal

---

## Next Steps

- [Events API](events.md) - Access events from cameras
- [Detections API](detections.md) - Access detection details
- Back to [API Overview](overview.md)
