---
title: Zones API
description: REST API endpoints for camera zone management
source_refs:
  - backend/api/routes/zones.py
  - backend/api/schemas/zone.py
  - backend/models/zone.py
---

# Zones API

The Zones API provides endpoints for managing detection zones within camera views. Zones allow you to define areas of interest (entry points, restricted areas, etc.) for more targeted detection and alerting.

## Endpoints Overview

| Method | Endpoint                                   | Description       |
| ------ | ------------------------------------------ | ----------------- |
| GET    | `/api/cameras/{camera_id}/zones`           | List zones        |
| POST   | `/api/cameras/{camera_id}/zones`           | Create zone       |
| GET    | `/api/cameras/{camera_id}/zones/{zone_id}` | Get specific zone |
| PUT    | `/api/cameras/{camera_id}/zones/{zone_id}` | Update zone       |
| DELETE | `/api/cameras/{camera_id}/zones/{zone_id}` | Delete zone       |

---

## GET /api/cameras/{camera_id}/zones

List all zones for a specific camera.

**Source:** [`list_zones`](../../backend/api/routes/zones.py:76)

**Parameters:**

| Name        | Type    | In    | Required | Description                       |
| ----------- | ------- | ----- | -------- | --------------------------------- |
| `camera_id` | string  | path  | Yes      | UUID of the camera                |
| `enabled`   | boolean | query | No       | Filter by enabled/disabled status |

**Response:** `200 OK`

```json
{
  "zones": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "camera_id": "456e7890-e89b-12d3-a456-426614174000",
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
      "priority": 1,
      "created_at": "2025-12-23T10:00:00Z",
      "updated_at": "2025-12-23T12:00:00Z"
    }
  ],
  "count": 1
}
```

**Response Fields:**

| Field   | Type    | Description           |
| ------- | ------- | --------------------- |
| `zones` | array   | List of zone objects  |
| `count` | integer | Total number of zones |

**Errors:**

| Code | Description                        |
| ---- | ---------------------------------- |
| 404  | Camera with specified ID not found |

**Example Request:**

```bash
# List all zones for a camera
curl http://localhost:8000/api/cameras/456e7890-e89b-12d3-a456-426614174000/zones

# Filter by enabled status
curl "http://localhost:8000/api/cameras/456e7890-e89b-12d3-a456-426614174000/zones?enabled=true"
```

---

## POST /api/cameras/{camera_id}/zones

Create a new zone for a camera.

**Source:** [`create_zone`](../../backend/api/routes/zones.py:110)

**Parameters:**

| Name        | Type   | In   | Required | Description        |
| ----------- | ------ | ---- | -------- | ------------------ |
| `camera_id` | string | path | Yes      | UUID of the camera |

**Request Body:**

```json
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

**Request Fields:**

| Field         | Type    | Required | Constraints             | Description                                 |
| ------------- | ------- | -------- | ----------------------- | ------------------------------------------- |
| `name`        | string  | Yes      | 1-255 chars             | Zone name                                   |
| `zone_type`   | string  | No       | See Zone Types          | Type of zone (default: `other`)             |
| `coordinates` | array   | Yes      | Min 3 points, 0-1 range | Array of normalized [x, y] points           |
| `shape`       | string  | No       | See Zone Shapes         | Shape of the zone (default: `rectangle`)    |
| `color`       | string  | No       | Hex format (#RRGGBB)    | Color for UI display (default: `#3B82F6`)   |
| `enabled`     | boolean | No       | -                       | Whether zone is active (default: `true`)    |
| `priority`    | integer | No       | 0-100                   | Priority for overlapping zones (default: 0) |

**Response:** `201 Created`

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "camera_id": "456e7890-e89b-12d3-a456-426614174000",
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
  "priority": 1,
  "created_at": "2025-12-23T10:00:00Z",
  "updated_at": "2025-12-23T10:00:00Z"
}
```

**Errors:**

| Code | Description                                  |
| ---- | -------------------------------------------- |
| 404  | Camera with specified ID not found           |
| 422  | Validation error (invalid coordinates, etc.) |

**Example Request:**

```bash
curl -X POST http://localhost:8000/api/cameras/456e7890-e89b-12d3-a456-426614174000/zones \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Front Door",
    "zone_type": "entry_point",
    "coordinates": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
    "priority": 1
  }'
```

---

## GET /api/cameras/{camera_id}/zones/{zone_id}

Get a specific zone by ID.

**Source:** [`get_zone`](../../backend/api/routes/zones.py:153)

**Parameters:**

| Name        | Type   | In   | Required | Description        |
| ----------- | ------ | ---- | -------- | ------------------ |
| `camera_id` | string | path | Yes      | UUID of the camera |
| `zone_id`   | string | path | Yes      | UUID of the zone   |

**Response:** `200 OK`

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "camera_id": "456e7890-e89b-12d3-a456-426614174000",
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
  "priority": 1,
  "created_at": "2025-12-23T10:00:00Z",
  "updated_at": "2025-12-23T12:00:00Z"
}
```

**Errors:**

| Code | Description                             |
| ---- | --------------------------------------- |
| 404  | Camera not found                        |
| 404  | Zone not found for the specified camera |

**Example Request:**

```bash
curl http://localhost:8000/api/cameras/456e7890-e89b-12d3-a456-426614174000/zones/123e4567-e89b-12d3-a456-426614174000
```

---

## PUT /api/cameras/{camera_id}/zones/{zone_id}

Update an existing zone. Only provided fields are updated.

**Source:** [`update_zone`](../../backend/api/routes/zones.py:178)

**Parameters:**

| Name        | Type   | In   | Required | Description        |
| ----------- | ------ | ---- | -------- | ------------------ |
| `camera_id` | string | path | Yes      | UUID of the camera |
| `zone_id`   | string | path | Yes      | UUID of the zone   |

**Request Body:**

```json
{
  "name": "Front Door - Updated",
  "enabled": false
}
```

**Request Fields:**

| Field         | Type    | Required | Constraints             | Description                       |
| ------------- | ------- | -------- | ----------------------- | --------------------------------- |
| `name`        | string  | No       | 1-255 chars             | Zone name                         |
| `zone_type`   | string  | No       | See Zone Types          | Type of zone                      |
| `coordinates` | array   | No       | Min 3 points, 0-1 range | Array of normalized [x, y] points |
| `shape`       | string  | No       | See Zone Shapes         | Shape of the zone                 |
| `color`       | string  | No       | Hex format (#RRGGBB)    | Color for UI display              |
| `enabled`     | boolean | No       | -                       | Whether zone is active            |
| `priority`    | integer | No       | 0-100                   | Priority for overlapping zones    |

**Response:** `200 OK`

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "camera_id": "456e7890-e89b-12d3-a456-426614174000",
  "name": "Front Door - Updated",
  "zone_type": "entry_point",
  "coordinates": [
    [0.1, 0.2],
    [0.3, 0.2],
    [0.3, 0.8],
    [0.1, 0.8]
  ],
  "shape": "rectangle",
  "color": "#3B82F6",
  "enabled": false,
  "priority": 1,
  "created_at": "2025-12-23T10:00:00Z",
  "updated_at": "2025-12-23T14:00:00Z"
}
```

**Errors:**

| Code | Description                                  |
| ---- | -------------------------------------------- |
| 404  | Camera not found                             |
| 404  | Zone not found for the specified camera      |
| 422  | Validation error (invalid coordinates, etc.) |

**Example Request:**

```bash
curl -X PUT http://localhost:8000/api/cameras/456e7890-e89b-12d3-a456-426614174000/zones/123e4567-e89b-12d3-a456-426614174000 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Front Door - Updated",
    "enabled": false
  }'
```

---

## DELETE /api/cameras/{camera_id}/zones/{zone_id}

Delete a zone.

**Source:** [`delete_zone`](../../backend/api/routes/zones.py:215)

**Parameters:**

| Name        | Type   | In   | Required | Description        |
| ----------- | ------ | ---- | -------- | ------------------ |
| `camera_id` | string | path | Yes      | UUID of the camera |
| `zone_id`   | string | path | Yes      | UUID of the zone   |

**Response:** `204 No Content`

No response body.

**Errors:**

| Code | Description                             |
| ---- | --------------------------------------- |
| 404  | Camera not found                        |
| 404  | Zone not found for the specified camera |

**Example Request:**

```bash
curl -X DELETE http://localhost:8000/api/cameras/456e7890-e89b-12d3-a456-426614174000/zones/123e4567-e89b-12d3-a456-426614174000
```

---

## Zone Types

| Type          | Description                               |
| ------------- | ----------------------------------------- |
| `entry_point` | Entry/exit points (doors, gates)          |
| `restricted`  | Restricted areas requiring extra alerting |
| `driveway`    | Driveway or parking areas                 |
| `walkway`     | Sidewalks and walking paths               |
| `perimeter`   | Property boundary or fence line           |
| `other`       | General purpose zone                      |

---

## Zone Shapes

| Shape       | Description                      |
| ----------- | -------------------------------- |
| `rectangle` | Four-point rectangular region    |
| `polygon`   | Arbitrary polygon with 3+ points |

---

## Coordinate System

Coordinates are specified as normalized values in the range 0.0 to 1.0, where:

- `(0.0, 0.0)` = top-left corner of the image
- `(1.0, 1.0)` = bottom-right corner of the image

This allows zones to be resolution-independent and work with any camera resolution.

**Coordinate Validation:**

- Minimum 3 points required for a valid polygon
- All points must be within 0-1 range
- No duplicate consecutive points allowed
- Polygon must have positive area (not degenerate)
- Polygon edges must not self-intersect

---

## Data Models

### ZoneResponse

Full zone response model.

**Source:** [`ZoneResponse`](../../backend/api/schemas/zone.py:240)

| Field         | Type     | Description                            |
| ------------- | -------- | -------------------------------------- |
| `id`          | string   | Zone UUID                              |
| `camera_id`   | string   | Camera ID this zone belongs to         |
| `name`        | string   | Zone name                              |
| `zone_type`   | string   | Type of zone                           |
| `coordinates` | array    | Array of normalized [x, y] points      |
| `shape`       | string   | Shape of the zone                      |
| `color`       | string   | Hex color for UI display               |
| `enabled`     | boolean  | Whether zone is active                 |
| `priority`    | integer  | Priority for overlapping zones (0-100) |
| `created_at`  | datetime | Timestamp when zone was created        |
| `updated_at`  | datetime | Timestamp when zone was last updated   |

### ZoneCreate

Request model for creating a zone.

**Source:** [`ZoneCreate`](../../backend/api/schemas/zone.py:153)

| Field         | Type    | Required | Constraints             | Description                    |
| ------------- | ------- | -------- | ----------------------- | ------------------------------ |
| `name`        | string  | Yes      | 1-255 chars             | Zone name                      |
| `zone_type`   | string  | No       | See Zone Types          | Type of zone                   |
| `coordinates` | array   | Yes      | Min 3 points, 0-1 range | Array of [x, y] points         |
| `shape`       | string  | No       | See Zone Shapes         | Shape of the zone              |
| `color`       | string  | No       | Hex format (#RRGGBB)    | Color for UI display           |
| `enabled`     | boolean | No       | -                       | Whether zone is active         |
| `priority`    | integer | No       | 0-100                   | Priority for overlapping zones |

### ZoneUpdate

Request model for updating a zone.

**Source:** [`ZoneUpdate`](../../backend/api/schemas/zone.py:198)

| Field         | Type    | Required | Constraints             | Description                    |
| ------------- | ------- | -------- | ----------------------- | ------------------------------ |
| `name`        | string  | No       | 1-255 chars             | Zone name                      |
| `zone_type`   | string  | No       | See Zone Types          | Type of zone                   |
| `coordinates` | array   | No       | Min 3 points, 0-1 range | Array of [x, y] points         |
| `shape`       | string  | No       | See Zone Shapes         | Shape of the zone              |
| `color`       | string  | No       | Hex format (#RRGGBB)    | Color for UI display           |
| `enabled`     | boolean | No       | -                       | Whether zone is active         |
| `priority`    | integer | No       | 0-100                   | Priority for overlapping zones |

---

## Related Documentation

- [Cameras API](cameras.md) - Parent camera management
- [Events API](events.md) - Events linked to zones
- [Detections API](detections.md) - Detections within zones
