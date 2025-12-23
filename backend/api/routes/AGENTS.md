# API Routes

## Purpose

The `backend/api/routes/` directory contains FastAPI router modules that define HTTP endpoints for the home security monitoring system. Each file groups related endpoints by resource type.

## Files

### `__init__.py`

Package initialization file. Simple docstring: "API route handlers."

### `cameras.py`

Camera management CRUD endpoints.

### `system.py`

System monitoring, health checks, and configuration endpoints.

### `media.py`

Secure media file serving for camera images and detection thumbnails.

## API Endpoints

### Camera Management (`cameras.py`)

Router prefix: `/api/cameras`

| Method | Path                       | Purpose                                         | Request Body   | Response             | Status Codes |
| ------ | -------------------------- | ----------------------------------------------- | -------------- | -------------------- | ------------ |
| GET    | `/api/cameras`             | List all cameras with optional status filter    | None           | `CameraListResponse` | 200          |
| GET    | `/api/cameras/{camera_id}` | Get a specific camera by UUID                   | None           | `CameraResponse`     | 200, 404     |
| POST   | `/api/cameras`             | Create a new camera                             | `CameraCreate` | `CameraResponse`     | 201          |
| PATCH  | `/api/cameras/{camera_id}` | Update an existing camera                       | `CameraUpdate` | `CameraResponse`     | 200, 404     |
| DELETE | `/api/cameras/{camera_id}` | Delete a camera (cascades to detections/events) | None           | None                 | 204, 404     |

**Query Parameters:**

- `GET /api/cameras?status={online|offline|error}` - Filter cameras by status

**Key Features:**

- UUID generation for new cameras
- Partial updates via PATCH (only updates provided fields)
- Cascade deletion of related data
- SQLAlchemy async operations

---

### System Monitoring (`system.py`)

Router prefix: `/api/system`

| Method | Path                 | Purpose                                                | Request Body | Response              | Status Codes |
| ------ | -------------------- | ------------------------------------------------------ | ------------ | --------------------- | ------------ |
| GET    | `/api/system/health` | Get system health check (database, Redis, AI services) | None         | `HealthResponse`      | 200          |
| GET    | `/api/system/gpu`    | Get current GPU statistics                             | None         | `GPUStatsResponse`    | 200          |
| GET    | `/api/system/config` | Get public configuration settings                      | None         | `ConfigResponse`      | 200          |
| GET    | `/api/system/stats`  | Get system statistics (counts, uptime)                 | None         | `SystemStatsResponse` | 200          |

**Key Features:**

- Multi-service health checks with degraded/unhealthy states
- Latest GPU stats from database (returns null if unavailable)
- Public-only config (no secrets exposed)
- Application uptime tracking
- Aggregate statistics (camera/event/detection counts)

**Health Status Logic:**

- `healthy` - All services operational
- `degraded` - Some non-critical services down
- `unhealthy` - Critical services (database) down

---

### Media Serving (`media.py`)

Router prefix: `/api/media`

| Method | Path                                             | Purpose                    | Request Body | Response       | Status Codes  |
| ------ | ------------------------------------------------ | -------------------------- | ------------ | -------------- | ------------- |
| GET    | `/api/media/cameras/{camera_id}/{filename:path}` | Serve camera images/videos | None         | `FileResponse` | 200, 403, 404 |
| GET    | `/api/media/thumbnails/{filename}`               | Serve detection thumbnails | None         | `FileResponse` | 200, 403, 404 |

**Allowed File Types:**

- Images: `.jpg`, `.jpeg`, `.png`, `.gif`
- Videos: `.mp4`, `.avi`, `.webm`

**Security Features:**

- Path traversal prevention (blocks `..` and `/` prefixes)
- File type whitelist enforcement
- Base path validation (resolved path must be within allowed directory)
- Descriptive error responses via `MediaErrorResponse`

**Base Paths:**

- Camera files: `{foscam_base_path}/{camera_id}/`
- Thumbnails: `backend/data/thumbnails/`

## Common Patterns

### Async Database Access

All routes use async SQLAlchemy sessions:

```python
db: AsyncSession = Depends(get_db)
result = await db.execute(select(Model).where(...))
item = result.scalar_one_or_none()
```

### Error Handling

```python
if not resource:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Resource with id {id} not found",
    )
```

### Response Models

Every endpoint declares its response model:

```python
@router.get("", response_model=ResponseSchema)
async def endpoint(...) -> ResponseType:
    ...
```

### Dependency Injection

Routes use FastAPI dependencies for:

- `db: AsyncSession = Depends(get_db)` - Database session
- `redis: RedisClient = Depends(get_redis)` - Redis client
- `get_settings()` - Configuration settings

## Helper Functions

### `system.py` Helpers

- **`get_latest_gpu_stats(db)`** - Fetch most recent GPU stats from database
- **`check_database_health(db)`** - Test database connectivity
- **`check_redis_health(redis)`** - Test Redis connectivity
- **`check_ai_services_health()`** - Placeholder for AI service checks

### `media.py` Helpers

- **`_validate_and_resolve_path(base_path, requested_path)`** - Secure path validation
  - Prevents path traversal
  - Validates file exists
  - Checks file type is allowed
  - Returns resolved absolute path

## Integration Points

### Database Models

- `Camera` - Camera configuration
- `Detection` - Object detections
- `Event` - Security events
- `GPUStats` - GPU metrics

### External Services

- SQLAlchemy async engine
- Redis for health checks
- File system for media serving

### Configuration

Uses `backend.core.config.Settings` for:

- Foscam base path
- Application name/version
- Batch processing settings
- Retention policies

## Testing Considerations

When testing routes:

1. Use `AsyncClient` for async endpoints
2. Mock database dependencies with test fixtures
3. Test error cases (404, 403, validation errors)
4. Verify cascade deletes for cameras
5. Test path traversal prevention for media endpoints
6. Verify health check logic for degraded states
