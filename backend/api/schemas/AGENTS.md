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

### `system.py`

Pydantic schemas for system monitoring endpoints.

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

#### `ConfigResponse`

**Purpose:** Serialize public application configuration

**Fields:**

- `app_name: str` - Application name
- `version: str` - Application version
- `retention_days: int` - Data retention period (>= 1)
- `batch_window_seconds: int` - Batch processing window (>= 1)
- `batch_idle_timeout_seconds: int` - Batch idle timeout (>= 1)

**Security:** Only exposes non-sensitive configuration. Does NOT include database URLs, API keys, or secrets.

**Example:**

```json
{
  "app_name": "Home Security Intelligence",
  "version": "0.1.0",
  "retention_days": 30,
  "batch_window_seconds": 90,
  "batch_idle_timeout_seconds": 30
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
