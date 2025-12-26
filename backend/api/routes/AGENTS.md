# API Routes

## Purpose

The `backend/api/routes/` directory contains FastAPI router modules that define HTTP endpoints for the home security monitoring system. Each file groups related endpoints by resource type (cameras, events, detections, system, media, WebSocket).

## Files

### `__init__.py`

Package initialization file. Simple docstring: "API route handlers."

### `cameras.py`

Camera management CRUD endpoints and snapshot serving.

**Key Features:**

- Full CRUD operations for cameras
- Status filtering
- Latest snapshot image serving
- UUID generation for new cameras
- Cascade deletion of related data

### `events.py`

Security event management, querying, and statistics.

**Key Features:**

- List events with filtering (risk level, date range, reviewed status, object type)
- Get aggregated event statistics by risk level and camera
- Get specific event details with detection count and notes
- Mark events as reviewed and add notes (PATCH)
- Get detections associated with an event
- Pagination support

### `detections.py`

Object detection listing and thumbnail image serving.

**Key Features:**

- List detections with advanced filtering (camera, object type, confidence, date)
- Get specific detection details
- Serve detection thumbnail images with bounding boxes
- On-the-fly thumbnail generation if not cached
- Pagination support

### `websocket.py`

WebSocket endpoints for real-time communication.

**Key Features:**

- `/ws/events` - Real-time security event notifications
- `/ws/system` - System status updates (GPU, cameras, health)
- Connection lifecycle management
- Ping/pong keep-alive support
- Integration with broadcaster services

### `logs.py`

System and frontend log management.

**Key Features:**

- List logs with filtering (level, component, camera, source, date, text search)
- Get log statistics for dashboard (counts by level, component)
- Get individual log entries by ID
- Receive and store frontend logs
- Pagination support

### `system.py`

System monitoring, health checks, GPU stats, and configuration.

**Key Features:**

- Multi-service health checks (database, Redis, AI)
- Current and historical GPU statistics
- System-wide statistics (camera/event/detection counts, uptime)
- Public configuration retrieval
- Configuration updates (PATCH)

### `media.py`

Secure media file serving for camera images and detection thumbnails.

**Key Features:**

- Path traversal prevention
- File type whitelist enforcement
- Secure path resolution
- Base path validation

## API Endpoints

### Camera Management (`cameras.py`)

Router prefix: `/api/cameras`

| Method | Path                                | Purpose                                         | Request Body   | Response             | Status Codes |
| ------ | ----------------------------------- | ----------------------------------------------- | -------------- | -------------------- | ------------ |
| GET    | `/api/cameras`                      | List all cameras with optional status filter    | None           | `CameraListResponse` | 200          |
| GET    | `/api/cameras/{camera_id}`          | Get a specific camera by UUID                   | None           | `CameraResponse`     | 200, 404     |
| GET    | `/api/cameras/{camera_id}/snapshot` | Get latest snapshot image                       | None           | `FileResponse`       | 200, 404     |
| POST   | `/api/cameras`                      | Create a new camera                             | `CameraCreate` | `CameraResponse`     | 201          |
| PATCH  | `/api/cameras/{camera_id}`          | Update an existing camera                       | `CameraUpdate` | `CameraResponse`     | 200, 404     |
| DELETE | `/api/cameras/{camera_id}`          | Delete a camera (cascades to detections/events) | None           | None                 | 204, 404     |

**Query Parameters:**

- `GET /api/cameras?status={online|offline|error}` - Filter cameras by status

**Key Features:**

- UUID generation for new cameras
- Partial updates via PATCH (only updates provided fields)
- Cascade deletion of related data
- Latest snapshot serving from camera folder
- SQLAlchemy async operations

---

### Events Management (`events.py`)

Router prefix: `/api/events`

| Method | Path                                | Purpose                                | Request Body  | Response                | Status Codes |
| ------ | ----------------------------------- | -------------------------------------- | ------------- | ----------------------- | ------------ |
| GET    | `/api/events`                       | List events with filtering/pagination  | None          | `EventListResponse`     | 200          |
| GET    | `/api/events/stats`                 | Get aggregated event statistics        | None          | `EventStatsResponse`    | 200          |
| GET    | `/api/events/{event_id}`            | Get specific event by ID               | None          | `EventResponse`         | 200, 404     |
| PATCH  | `/api/events/{event_id}`            | Update event (reviewed status & notes) | `EventUpdate` | `EventResponse`         | 200, 404     |
| GET    | `/api/events/{event_id}/detections` | Get detections for event               | None          | `DetectionListResponse` | 200, 404     |

**Query Parameters (List):**

- `camera_id: str` - Filter by camera UUID
- `risk_level: str` - Filter by risk level (low, medium, high, critical)
- `start_date: datetime` - Filter by start date (ISO format)
- `end_date: datetime` - Filter by end date (ISO format)
- `reviewed: bool` - Filter by reviewed status
- `object_type: str` - Filter by detected object type (person, vehicle, animal, etc.)
- `limit: int` - Max results (1-1000, default: 50)
- `offset: int` - Skip N results (default: 0)

**Query Parameters (Stats):**

- `start_date: datetime` - Filter by start date (ISO format)
- `end_date: datetime` - Filter by end date (ISO format)

**Key Features:**

- Advanced filtering by risk, date, camera, reviewed status, object type
- Aggregated statistics by risk level and camera
- Automatic detection count calculation
- Parse comma-separated detection_ids
- User notes support for events
- Chronological ordering within events
- Pagination support

---

### Detections Management (`detections.py`)

Router prefix: `/api/detections`

| Method | Path                                   | Purpose                                   | Request Body | Response                | Status Codes  |
| ------ | -------------------------------------- | ----------------------------------------- | ------------ | ----------------------- | ------------- |
| GET    | `/api/detections`                      | List detections with filtering/pagination | None         | `DetectionListResponse` | 200           |
| GET    | `/api/detections/{detection_id}`       | Get specific detection by ID              | None         | `DetectionResponse`     | 200, 404      |
| GET    | `/api/detections/{detection_id}/image` | Get thumbnail with bounding box           | None         | JPEG image              | 200, 404, 500 |

**Query Parameters (List):**

- `camera_id: str` - Filter by camera UUID
- `object_type: str` - Filter by object type (person, car, etc.)
- `start_date: datetime` - Filter by start date (ISO format)
- `end_date: datetime` - Filter by end date (ISO format)
- `min_confidence: float` - Minimum confidence (0.0-1.0)
- `limit: int` - Max results (1-1000, default: 50)
- `offset: int` - Skip N results (default: 0)

**Key Features:**

- Advanced filtering by camera, object type, confidence, date
- On-the-fly thumbnail generation if not cached
- Bounding box overlay on images
- Image caching with 1-hour cache headers
- Pagination support
- Integration with ThumbnailGenerator service

---

### WebSocket Communication (`websocket.py`)

Router prefix: None (WebSocket endpoints)

| Method | Path         | Purpose                         | Message Format                             |
| ------ | ------------ | ------------------------------- | ------------------------------------------ |
| WS     | `/ws/events` | Real-time security event stream | `{"type": "event", "data": {...}}`         |
| WS     | `/ws/system` | Real-time system status stream  | `{"type": "system_status", "data": {...}}` |

**Event Stream (`/ws/events`):**

- Broadcasts security events as they're analyzed
- Message includes: event ID, camera info, risk score/level, summary, timestamp
- Supports ping/pong keep-alive
- Uses EventBroadcaster service

**System Stream (`/ws/system`):**

- Broadcasts system status updates every 5 seconds
- Message includes: GPU stats, camera counts, queue status, health
- Supports ping/pong keep-alive
- Uses SystemBroadcaster service

**Connection Lifecycle:**

1. Client connects (handshake)
2. Connection registered with broadcaster
3. Client receives broadcast messages
4. Client can send ping for keep-alive
5. Graceful disconnect and cleanup

---

### System Monitoring (`system.py`)

Router prefix: `/api/system`

| Method | Path                      | Purpose                                                | Request Body          | Response                  | Status Codes |
| ------ | ------------------------- | ------------------------------------------------------ | --------------------- | ------------------------- | ------------ |
| GET    | `/api/system/health`      | Get system health check (database, Redis, AI services) | None                  | `HealthResponse`          | 200          |
| GET    | `/api/system/gpu`         | Get current GPU statistics                             | None                  | `GPUStatsResponse`        | 200          |
| GET    | `/api/system/gpu/history` | Get GPU stats time series                              | None                  | `GPUStatsHistoryResponse` | 200          |
| GET    | `/api/system/stats`       | Get system statistics (counts, uptime)                 | None                  | `SystemStatsResponse`     | 200          |
| GET    | `/api/system/config`      | Get public configuration settings                      | None                  | `ConfigResponse`          | 200          |
| PATCH  | `/api/system/config`      | Update configuration settings                          | `ConfigUpdateRequest` | `ConfigResponse`          | 200          |

**Query Parameters (GPU History):**

- `limit: int` - Max samples (1-1000, default: 100)

**Key Features:**

- Multi-service health checks with degraded/unhealthy states
- Latest GPU stats from database (returns null if unavailable)
- GPU stats time series for graphing
- Public-only config (no secrets exposed)
- Configuration updates for processing parameters
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

---

### Logs Management (`logs.py`)

Router prefix: `/api/logs`

| Method | Path                 | Purpose                             | Request Body        | Response                | Status Codes |
| ------ | -------------------- | ----------------------------------- | ------------------- | ----------------------- | ------------ |
| GET    | `/api/logs`          | List logs with filtering/pagination | None                | `LogsResponse`          | 200          |
| GET    | `/api/logs/stats`    | Get log statistics for dashboard    | None                | `LogStats`              | 200          |
| GET    | `/api/logs/{log_id}` | Get specific log entry by ID        | None                | `LogEntry`              | 200, 404     |
| POST   | `/api/logs/frontend` | Submit frontend log entry           | `FrontendLogCreate` | `{"status": "created"}` | 201          |

**Query Parameters (List):**

- `level: str` - Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `component: str` - Filter by component/module name
- `camera_id: str` - Filter by associated camera UUID
- `source: str` - Filter by source (backend, frontend)
- `search: str` - Search in message text (case-insensitive)
- `start_date: datetime` - Filter from date (ISO format)
- `end_date: datetime` - Filter to date (ISO format)
- `limit: int` - Max results (1-1000, default: 100)
- `offset: int` - Skip N results (default: 0)

**Key Features:**

- Advanced filtering by level, component, source, date, text search
- Dashboard statistics (counts by level and component)
- Frontend log ingestion with automatic user agent capture
- Today-based statistics for dashboard widgets
- Pagination support
- Chronological ordering (newest first)

**Stats Response Fields:**

- `total_today: int` - Total logs today
- `errors_today: int` - Error count today
- `warnings_today: int` - Warning count today
- `by_component: dict` - Counts grouped by component
- `by_level: dict` - Counts grouped by level
- `top_component: str | None` - Most active component

---

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
- `Log` - System and frontend logs

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
