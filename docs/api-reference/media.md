---
title: Media API
description: REST API endpoints for serving media files (images, videos, thumbnails)
source_refs:
  - backend/api/routes/media.py
  - backend/api/schemas/media.py
---

# Media API

The Media API provides secure endpoints for serving media files including camera images, detection thumbnails, video clips, and detection-associated images. All endpoints include security protections against path traversal attacks and rate limiting.

## Endpoints Overview

| Method | Endpoint                                    | Description                          |
| ------ | ------------------------------------------- | ------------------------------------ |
| GET    | `/api/media/cameras/{camera_id}/{filename}` | Serve camera image or video          |
| GET    | `/api/media/thumbnails/{filename}`          | Serve detection thumbnail            |
| GET    | `/api/media/detections/{detection_id}`      | Serve image for a detection          |
| GET    | `/api/media/clips/{filename}`               | Serve event video clip               |
| GET    | `/api/media/{path}`                         | Compatibility route (legacy support) |

---

## Security Features

All Media API endpoints include the following security protections:

### Path Traversal Protection

Requests containing `..` or absolute paths starting with `/` are rejected with a `403 Forbidden` response.

### File Type Allowlist

Only the following file types are served:

| Extension | Content-Type      |
| --------- | ----------------- |
| `.jpg`    | `image/jpeg`      |
| `.jpeg`   | `image/jpeg`      |
| `.png`    | `image/png`       |
| `.gif`    | `image/gif`       |
| `.mp4`    | `video/mp4`       |
| `.avi`    | `video/x-msvideo` |
| `.webm`   | `video/webm`      |

### Rate Limiting

All media endpoints are protected by rate limiting (MEDIA tier). Excessive requests will receive a `429 Too Many Requests` response.

### Directory Containment

All resolved file paths are verified to remain within their configured base directories.

---

## GET /api/media/cameras/{camera_id}/{filename}

Serve camera images or videos from Foscam storage.

**Source:** [`serve_camera_file`](../../backend/api/routes/media.py:207)

**Parameters:**

| Name        | Type   | In   | Required | Description                                |
| ----------- | ------ | ---- | -------- | ------------------------------------------ |
| `camera_id` | string | path | Yes      | Camera identifier (directory name)         |
| `filename`  | string | path | Yes      | File to serve (can include subdirectories) |

**Response:** `200 OK`

Binary file data with appropriate `Content-Type` header based on file extension.

**Response Headers:**

| Header         | Description                       |
| -------------- | --------------------------------- |
| `Content-Type` | MIME type based on file extension |
| `filename`     | Original filename for download    |

**Errors:**

| Code | Description                                        |
| ---- | -------------------------------------------------- |
| 403  | Invalid camera identifier (path traversal attempt) |
| 403  | Path traversal detected in filename                |
| 403  | File type not allowed                              |
| 404  | File not found                                     |
| 429  | Too many requests (rate limited)                   |

**Example Request:**

```bash
# Get a camera image
curl -o image.jpg http://localhost:8000/api/media/cameras/front_door/2025/01/04/image_001.jpg

# Get a camera video
curl -o video.mp4 http://localhost:8000/api/media/cameras/backyard/2025/01/04/clip.mp4

# View in browser
# http://localhost:8000/api/media/cameras/front_door/snapshot.jpg
```

---

## GET /api/media/thumbnails/{filename}

Serve detection thumbnail images stored in the backend data directory.

**Source:** [`serve_thumbnail`](../../backend/api/routes/media.py:259)

**Parameters:**

| Name       | Type   | In   | Required | Description        |
| ---------- | ------ | ---- | -------- | ------------------ |
| `filename` | string | path | Yes      | Thumbnail filename |

**Response:** `200 OK`

Binary image data with appropriate `Content-Type` header.

**Response Headers:**

| Header         | Description                       |
| -------------- | --------------------------------- |
| `Content-Type` | MIME type based on file extension |
| `filename`     | Original filename for download    |

**Errors:**

| Code | Description                         |
| ---- | ----------------------------------- |
| 403  | Path traversal detected in filename |
| 403  | File type not allowed               |
| 404  | Thumbnail file not found            |
| 429  | Too many requests (rate limited)    |

**Example Request:**

```bash
# Download thumbnail
curl -o thumb.jpg http://localhost:8000/api/media/thumbnails/detection_123_thumb.jpg

# View in browser
# http://localhost:8000/api/media/thumbnails/detection_123_thumb.jpg
```

**Storage Location:**

Thumbnails are stored in `backend/data/thumbnails/`.

---

## GET /api/media/detections/{detection_id}

Serve the source image associated with a detection record. This endpoint looks up the detection in the database and serves the original image file.

**Source:** [`serve_detection_image`](../../backend/api/routes/media.py:299)

**Parameters:**

| Name           | Type    | In   | Required | Description             |
| -------------- | ------- | ---- | -------- | ----------------------- |
| `detection_id` | integer | path | Yes      | Detection ID to look up |

**Response:** `200 OK`

Binary image data with appropriate `Content-Type` header.

**Response Headers:**

| Header         | Description                       |
| -------------- | --------------------------------- |
| `Content-Type` | MIME type based on file extension |
| `filename`     | Original filename for download    |

**Errors:**

| Code | Description                      |
| ---- | -------------------------------- |
| 403  | File outside allowed directory   |
| 403  | File type not allowed            |
| 404  | Detection not found in database  |
| 404  | Detection has no associated file |
| 404  | File not found on disk           |
| 429  | Too many requests (rate limited) |

**Example Request:**

```bash
# Download detection image
curl -o detection.jpg http://localhost:8000/api/media/detections/123

# View in browser
# http://localhost:8000/api/media/detections/123
```

**Implementation Notes:**

- The endpoint looks up the detection record to find the associated `file_path`
- Supports both absolute and relative file paths in the database
- Includes fallback logic for seeded test data paths

---

## GET /api/media/clips/{filename}

Serve event video clips generated by the ClipGenerator service.

**Source:** [`serve_clip`](../../backend/api/routes/media.py:398)

**Parameters:**

| Name       | Type   | In   | Required | Description                          |
| ---------- | ------ | ---- | -------- | ------------------------------------ |
| `filename` | string | path | Yes      | Clip filename (e.g., `123_clip.mp4`) |

**Response:** `200 OK`

Binary video data with appropriate `Content-Type` header.

**Response Headers:**

| Header         | Description                       |
| -------------- | --------------------------------- |
| `Content-Type` | MIME type based on file extension |
| `filename`     | Original filename for download    |

**Errors:**

| Code | Description                         |
| ---- | ----------------------------------- |
| 403  | Path traversal detected in filename |
| 403  | File type not allowed               |
| 404  | Clip file not found                 |
| 429  | Too many requests (rate limited)    |

**Example Request:**

```bash
# Download video clip
curl -o clip.mp4 http://localhost:8000/api/media/clips/123_clip.mp4

# Stream in browser
# http://localhost:8000/api/media/clips/123_clip.mp4
```

**Storage Location:**

Clips are stored in the directory configured by the ClipGenerator service.

---

## GET /api/media/{path}

Compatibility route for serving media using design-spec-style paths. This endpoint routes requests to the appropriate specialized endpoint.

**Source:** [`serve_media_compat`](../../backend/api/routes/media.py:121)

**Parameters:**

| Name   | Type   | In   | Required | Description                |
| ------ | ------ | ---- | -------- | -------------------------- |
| `path` | string | path | Yes      | Full path including prefix |

**Supported Path Prefixes:**

| Path Pattern                     | Routes To                                   |
| -------------------------------- | ------------------------------------------- |
| `cameras/{camera_id}/{filename}` | `/api/media/cameras/{camera_id}/{filename}` |
| `thumbnails/{filename}`          | `/api/media/thumbnails/{filename}`          |
| `detections/{id}`                | `/api/media/detections/{id}`                |
| `clips/{filename}`               | `/api/media/clips/{filename}`               |

**Response:** `200 OK`

Binary file data with appropriate `Content-Type` header (same as the target endpoint).

**Errors:**

| Code | Description                                               |
| ---- | --------------------------------------------------------- |
| 403  | Path traversal or access denied (same as target endpoint) |
| 404  | Unsupported path prefix                                   |
| 404  | File not found (same as target endpoint)                  |
| 404  | Invalid detection ID (non-numeric)                        |
| 429  | Too many requests (rate limited)                          |
| 500  | Database connection unavailable (detections only)         |

**Example Requests:**

```bash
# Camera file via compatibility route
curl -o image.jpg http://localhost:8000/api/media/cameras/front_door/image.jpg

# Thumbnail via compatibility route
curl -o thumb.jpg http://localhost:8000/api/media/thumbnails/detection_123.jpg

# Detection image via compatibility route
curl -o detection.jpg http://localhost:8000/api/media/detections/123

# Clip via compatibility route
curl -o clip.mp4 http://localhost:8000/api/media/clips/123_clip.mp4
```

---

## Error Response Format

All error responses use the `MediaErrorResponse` schema:

**Source:** [`MediaErrorResponse`](../../backend/api/schemas/media.py:6)

```json
{
  "error": "Error message describing what went wrong",
  "path": "The path that was attempted to be accessed"
}
```

**Fields:**

| Field   | Type   | Description                       |
| ------- | ------ | --------------------------------- |
| `error` | string | Human-readable error message      |
| `path`  | string | The path that triggered the error |

**Example Error Responses:**

```json
// 403 - Path traversal detected
{
  "error": "Path traversal detected",
  "path": "../../../etc/passwd"
}

// 403 - File type not allowed
{
  "error": "File type not allowed: .exe",
  "path": "cameras/front_door/malware.exe"
}

// 404 - File not found
{
  "error": "File not found",
  "path": "cameras/front_door/nonexistent.jpg"
}

// 404 - Detection not found
{
  "error": "Detection not found",
  "path": "detections/99999"
}

// 404 - Unsupported path
{
  "error": "Unsupported media path (expected cameras/..., thumbnails/..., detections/..., or clips/...)",
  "path": "invalid/path"
}
```

---

## Usage Examples

### Displaying Detection Images in Frontend

```typescript
// Get detection thumbnail
const thumbnailUrl = `/api/media/thumbnails/detection_${detectionId}_thumb.jpg`;

// Get full detection image
const imageUrl = `/api/media/detections/${detectionId}`;

// Use in React component
<img src={thumbnailUrl} alt="Detection thumbnail" />
```

### Streaming Video Clips

```html
<!-- HTML5 video player -->
<video controls>
  <source src="/api/media/clips/123_clip.mp4" type="video/mp4" />
  Your browser does not support video playback.
</video>
```

### Camera Feed Images

```typescript
// Get latest camera snapshot (use Cameras API)
const snapshotUrl = `/api/cameras/${cameraId}/snapshot`;

// Get specific camera image (use Media API)
const imageUrl = `/api/media/cameras/${cameraId}/${imagePath}`;
```

---

## Related Documentation

- [Cameras API](cameras.md) - Camera management and snapshots
- [Detections API](detections.md) - Detection queries and metadata
- [Events API](events.md) - Events with associated media
