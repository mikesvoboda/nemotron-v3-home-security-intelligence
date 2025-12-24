# API Schemas

## Purpose

The `backend/api/schemas/` directory contains Pydantic models for request/response validation. These schemas ensure type safety, automatic validation, and OpenAPI documentation generation.

## Files

### `__init__.py`

Package initialization with public exports:

- `CameraCreate`
- `CameraListResponse`
- `CameraResponse`
- `CameraUpdate`

### `camera.py`

Pydantic schemas for camera management endpoints.

### `events.py`

Pydantic schemas for event management endpoints.

### `detections.py`

Pydantic schemas for detection listing endpoints.

### `system.py`

Pydantic schemas for system monitoring and configuration endpoints.

### `media.py`

Pydantic schemas for media serving error responses.

## Schema Definitions

### Camera Schemas (`camera.py`)

#### `CameraCreate`

**Purpose:** Validate data for creating a new camera

**Fields:**

- `name: str` - Camera name (1-255 chars, required)
- `folder_path: str` - File system path (1-500 chars, required)
- `status: str` - Status (default: "online")

**Example:**

```json
{
  "name": "Front Door Camera",
  "folder_path": "/export/foscam/front_door",
  "status": "online"
}
```

---

#### `CameraUpdate`

**Purpose:** Validate data for updating an existing camera (partial updates)

**Fields:**

- `name: str | None` - Camera name (1-255 chars, optional)
- `folder_path: str | None` - File system path (1-500 chars, optional)
- `status: str | None` - Status (optional)

**Example:**

```json
{
  "name": "Front Door Camera - Updated",
  "status": "offline"
}
```

**Note:** All fields are optional - only provided fields are updated.

---

#### `CameraResponse`

**Purpose:** Serialize camera data in API responses

**Fields:**

- `id: str` - Camera UUID
- `name: str` - Camera name
- `folder_path: str` - File system path
- `status: str` - Status (online, offline, error)
- `created_at: datetime` - Creation timestamp
- `last_seen_at: datetime | None` - Last activity timestamp

**Config:**

- `from_attributes=True` - Enable ORM mode for SQLAlchemy models

**Example:**

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

---

#### `CameraListResponse`

**Purpose:** Serialize list of cameras with metadata

**Fields:**

- `cameras: list[CameraResponse]` - List of camera objects
- `count: int` - Total number of cameras

**Example:**

```json
{
  "cameras": [...],
  "count": 1
}
```

---

### Event Schemas (`events.py`)

#### `EventResponse`

**Purpose:** Serialize event data in API responses

**Fields:**

- `id: int` - Event ID
- `camera_id: str` - Camera UUID
- `started_at: datetime` - Event start timestamp
- `ended_at: datetime | None` - Event end timestamp (optional)
- `risk_score: int | None` - Risk score 0-100 (optional)
- `risk_level: str | None` - Risk level: low, medium, high, critical (optional)
- `summary: str | None` - LLM-generated event summary (optional)
- `reviewed: bool` - Whether event has been reviewed (default: False)
- `detection_count: int` - Number of detections in this event (default: 0)

**Config:**

- `from_attributes=True` - Enable ORM mode for SQLAlchemy models

**Example:**

```json
{
  "id": 1,
  "camera_id": "123e4567-e89b-12d3-a456-426614174000",
  "started_at": "2025-12-23T12:00:00Z",
  "ended_at": "2025-12-23T12:02:30Z",
  "risk_score": 75,
  "risk_level": "medium",
  "summary": "Person detected near front entrance",
  "reviewed": false,
  "detection_count": 5
}
```

---

#### `EventUpdate`

**Purpose:** Validate data for updating an event (mark as reviewed)

**Fields:**

- `reviewed: bool` - Mark event as reviewed or not reviewed (required)

**Example:**

```json
{
  "reviewed": true
}
```

---

#### `EventListResponse`

**Purpose:** Serialize list of events with pagination metadata

**Fields:**

- `events: list[EventResponse]` - List of event objects
- `count: int` - Total number of events matching filters
- `limit: int` - Maximum number of results returned
- `offset: int` - Number of results skipped

**Example:**

```json
{
  "events": [...],
  "count": 1,
  "limit": 50,
  "offset": 0
}
```

---

### Detection Schemas (`detections.py`)

#### `DetectionResponse`

**Purpose:** Serialize detection data in API responses

**Fields:**

- `id: int` - Detection ID
- `camera_id: str` - Camera UUID
- `file_path: str` - Path to source image file
- `file_type: str | None` - MIME type of source file (optional)
- `detected_at: datetime` - Timestamp when detection was made
- `object_type: str | None` - Type of detected object: person, car, etc. (optional)
- `confidence: float | None` - Detection confidence score 0-1 (optional)
- `bbox_x: int | None` - Bounding box X coordinate (optional)
- `bbox_y: int | None` - Bounding box Y coordinate (optional)
- `bbox_width: int | None` - Bounding box width (optional)
- `bbox_height: int | None` - Bounding box height (optional)
- `thumbnail_path: str | None` - Path to thumbnail image with bbox overlay (optional)

**Config:**

- `from_attributes=True` - Enable ORM mode for SQLAlchemy models

**Example:**

```json
{
  "id": 1,
  "camera_id": "123e4567-e89b-12d3-a456-426614174000",
  "file_path": "/export/foscam/front_door/20251223_120000.jpg",
  "file_type": "image/jpeg",
  "detected_at": "2025-12-23T12:00:00Z",
  "object_type": "person",
  "confidence": 0.95,
  "bbox_x": 100,
  "bbox_y": 150,
  "bbox_width": 200,
  "bbox_height": 400,
  "thumbnail_path": "/data/thumbnails/1_thumb.jpg"
}
```

---

#### `DetectionListResponse`

**Purpose:** Serialize list of detections with pagination metadata

**Fields:**

- `detections: list[DetectionResponse]` - List of detection objects
- `count: int` - Total number of detections matching filters
- `limit: int` - Maximum number of results returned
- `offset: int` - Number of results skipped

**Example:**

```json
{
  "detections": [...],
  "count": 1,
  "limit": 50,
  "offset": 0
}
```

---

### System Schemas (`system.py`)

#### `ServiceStatus`

**Purpose:** Represent status of individual system services

**Fields:**

- `status: str` - Service health: "healthy", "unhealthy", or "not_initialized"
- `message: str | None` - Optional status message or error details
- `details: dict[str, str] | None` - Additional service-specific details

---

#### `HealthResponse`

**Purpose:** Serialize complete system health check

**Fields:**

- `status: str` - Overall status: "healthy", "degraded", or "unhealthy"
- `services: dict[str, ServiceStatus]` - Status of database, redis, ai
- `timestamp: datetime` - Health check timestamp

**Example:**

```json
{
  "status": "healthy",
  "services": {
    "database": {
      "status": "healthy",
      "message": "Database operational",
      "details": null
    },
    "redis": {
      "status": "healthy",
      "message": "Redis connected",
      "details": { "redis_version": "7.0.0" }
    },
    "ai": {
      "status": "healthy",
      "message": "AI services operational",
      "details": null
    }
  },
  "timestamp": "2025-12-23T10:30:00"
}
```

---

#### `GPUStatsResponse`

**Purpose:** Serialize GPU performance metrics

**Fields:**

- `utilization: float | None` - GPU utilization % (0-100)
- `memory_used: int | None` - GPU memory used (MB, >= 0)
- `memory_total: int | None` - Total GPU memory (MB, >= 0)
- `temperature: float | None` - GPU temperature (Celsius)
- `inference_fps: float | None` - Inference frames per second (>= 0)

**Note:** All fields are nullable - returns null if no GPU data available.

**Example:**

```json
{
  "utilization": 75.5,
  "memory_used": 12000,
  "memory_total": 24000,
  "temperature": 65.0,
  "inference_fps": 30.5
}
```

---

#### `GPUStatsSample`

**Purpose:** Single time-series sample of GPU statistics

**Fields:**

- `recorded_at: datetime` - When the GPU sample was recorded (UTC)
- `utilization: float | None` - GPU utilization % (0-100)
- `memory_used: int | None` - GPU memory used (MB, >= 0)
- `memory_total: int | None` - Total GPU memory (MB, >= 0)
- `temperature: float | None` - GPU temperature (Celsius)
- `inference_fps: float | None` - Inference frames per second (>= 0)

**Config:**

- `from_attributes=True` - Enable ORM mode for SQLAlchemy models

**Example:**

```json
{
  "recorded_at": "2025-12-23T12:00:00Z",
  "utilization": 75.5,
  "memory_used": 12000,
  "memory_total": 24000,
  "temperature": 65.0,
  "inference_fps": 30.5
}
```

---

#### `GPUStatsHistoryResponse`

**Purpose:** Serialize GPU stats time series data

**Fields:**

- `samples: list[GPUStatsSample]` - GPU stats samples in chronological order
- `count: int` - Number of samples returned (>= 0)
- `limit: int` - Applied limit (>= 1)

**Example:**

```json
{
  "samples": [...],
  "count": 100,
  "limit": 100
}
```

---

#### `ConfigResponse`

**Purpose:** Serialize public application configuration

**Fields:**

- `app_name: str` - Application name
- `version: str` - Application version
- `retention_days: int` - Data retention period (>= 1)
- `batch_window_seconds: int` - Batch processing window (>= 1)
- `batch_idle_timeout_seconds: int` - Batch idle timeout (>= 1)
- `detection_confidence_threshold: float` - Minimum confidence threshold (0.0-1.0)

**Security:** Only exposes non-sensitive configuration. Does NOT include database URLs, API keys, or secrets.

**Example:**

```json
{
  "app_name": "Home Security Intelligence",
  "version": "0.1.0",
  "retention_days": 30,
  "batch_window_seconds": 90,
  "batch_idle_timeout_seconds": 30,
  "detection_confidence_threshold": 0.5
}
```

---

#### `ConfigUpdateRequest`

**Purpose:** Validate data for updating configuration (PATCH)

**Fields:**

- `retention_days: int | None` - Data retention period (>= 1, optional)
- `batch_window_seconds: int | None` - Batch processing window (>= 1, optional)
- `batch_idle_timeout_seconds: int | None` - Batch idle timeout (>= 1, optional)
- `detection_confidence_threshold: float | None` - Minimum confidence (0.0-1.0, optional)

**Note:** All fields are optional - only provided fields are updated.

**Example:**

```json
{
  "retention_days": 45,
  "detection_confidence_threshold": 0.6
}
```

---

#### `SystemStatsResponse`

**Purpose:** Serialize system-wide statistics

**Fields:**

- `total_cameras: int` - Total cameras in system (>= 0)
- `total_events: int` - Total events recorded (>= 0)
- `total_detections: int` - Total detections recorded (>= 0)
- `uptime_seconds: float` - Application uptime (>= 0)

**Example:**

```json
{
  "total_cameras": 4,
  "total_events": 156,
  "total_detections": 892,
  "uptime_seconds": 86400.5
}
```

---

### Media Schemas (`media.py`)

#### `MediaErrorResponse`

**Purpose:** Serialize error responses for media access failures

**Fields:**

- `error: str` - Error message describing what went wrong
- `path: str` - The path that was attempted to be accessed

**Example:**

```json
{
  "error": "Path traversal detected",
  "path": "../../../etc/passwd"
}
```

**Usage:** Used in 403 and 404 responses from media endpoints.

## Common Patterns

### Field Validation

Pydantic provides automatic validation:

- `Field(..., min_length=1, max_length=255)` - String length constraints
- `Field(..., ge=0, le=100)` - Numeric range constraints
- `str | None` - Optional fields (nullable)

### Configuration

All schemas use `model_config` for:

- `from_attributes=True` - Enable SQLAlchemy ORM mode
- `json_schema_extra` - Provide example data for OpenAPI docs

### Examples in OpenAPI

Every schema includes example JSON in `json_schema_extra` for automatic API documentation generation.

## Request/Response Patterns

### Create Pattern

- Request: `*Create` schema (all required fields)
- Response: `*Response` schema (includes generated ID and timestamps)

### Update Pattern

- Request: `*Update` schema (all optional fields for partial updates)
- Response: `*Response` schema (full updated object)

### List Pattern

- Response: `*ListResponse` schema (array + count)

### Error Pattern

- Response: `*ErrorResponse` schema (error + context)

## Validation Features

### Automatic Validation

FastAPI automatically validates:

- Required vs optional fields
- Field types
- String lengths
- Numeric ranges
- Date/datetime formats

### Validation Errors

Returns 422 Unprocessable Entity with detailed error information:

```json
{
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## Integration with SQLAlchemy

Schemas use `from_attributes=True` to serialize SQLAlchemy models:

```python
# SQLAlchemy model to Pydantic schema
camera = await db.get(Camera, camera_id)
return CameraResponse.model_validate(camera)
```

## Testing Considerations

When testing with schemas:

1. Test required field validation
2. Test field length/range constraints
3. Test optional field handling (None values)
4. Verify example JSON is valid
5. Test ORM mode with actual SQLAlchemy models
6. Verify partial updates exclude unset fields
