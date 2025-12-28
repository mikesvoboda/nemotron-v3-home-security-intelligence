# Backend API Package

## Purpose

The `backend/api/` package contains the FastAPI REST API layer for the home security monitoring system. It provides HTTP endpoints for managing cameras, events, detections, system monitoring, media serving, dead-letter queue management, Prometheus metrics, and real-time WebSocket communication.

## Directory Structure

```
backend/api/
├── __init__.py          # Package initialization
├── AGENTS.md            # This file
├── routes/              # API route handlers (endpoints)
├── schemas/             # Pydantic schemas for request/response validation
└── middleware/          # HTTP middleware components (auth, request ID)
```

## Key Files

### `__init__.py`

Package initialization. Contains a simple docstring: "API package for routes and websocket handlers."

## Key Components

### Routes (`routes/`)

Contains FastAPI routers that define HTTP endpoints:

| File | Purpose |
|------|---------|
| `cameras.py` | Camera CRUD operations and snapshot serving |
| `events.py` | Security event management, queries, and statistics |
| `detections.py` | Object detection listing and thumbnail serving |
| `logs.py` | System and frontend log management |
| `websocket.py` | WebSocket endpoints for real-time updates |
| `system.py` | System health, GPU stats, configuration, telemetry |
| `media.py` | Secure file serving for images/videos |
| `dlq.py` | Dead-letter queue inspection and management |
| `metrics.py` | Prometheus metrics endpoint |

### Schemas (`schemas/`)

Contains Pydantic models for request/response validation:

| File | Purpose |
|------|---------|
| `camera.py` | Camera data validation schemas |
| `events.py` | Event request/response and statistics schemas |
| `detections.py` | Detection response schemas |
| `logs.py` | Log entry and statistics schemas |
| `system.py` | System monitoring, config, health, and telemetry schemas |
| `media.py` | Media error response schemas |
| `dlq.py` | Dead-letter queue schemas |

### Middleware (`middleware/`)

HTTP middleware for cross-cutting concerns:

| File | Purpose |
|------|---------|
| `auth.py` | API key authentication (HTTP and WebSocket) |
| `request_id.py` | Request ID generation and propagation for tracing |

## Architecture Overview

This API layer follows a clean architecture pattern:

1. **Middleware** - Authentication, request ID propagation, error handling
2. **Routes** - Handle HTTP requests, call services, return responses
3. **Schemas** - Validate incoming data and serialize outgoing data
4. **Services** - Business logic (AI pipeline, broadcasting, monitoring)
5. **Database** - SQLAlchemy async sessions via dependency injection
6. **Redis** - Redis client via dependency injection for pub/sub and queues

## Common Patterns

### Dependency Injection

All routes use FastAPI's dependency injection for:

- Database sessions: `db: AsyncSession = Depends(get_db)`
- Redis client: `redis: RedisClient = Depends(get_redis)`
- Settings: `get_settings()`

### Error Handling

- **401 Unauthorized** - Missing or invalid API key
- **403 Forbidden** - Access denied (path traversal, invalid file types)
- **404 Not Found** - Resource doesn't exist
- **422 Unprocessable Entity** - Validation errors (automatic via Pydantic)
- **500 Internal Server Error** - Unexpected errors

### Response Models

All endpoints specify response models via `response_model` parameter for automatic validation and OpenAPI documentation generation.

### Pagination Pattern

List endpoints support pagination with consistent query parameters:

- `limit: int` - Maximum results (default: 50, max: 1000)
- `offset: int` - Skip N results (default: 0)
- Response includes: `count`, `limit`, `offset`

## Database Models Used

The API interacts with these SQLAlchemy models:

- **Camera** - Camera configuration and status
- **Detection** - Object detections from RT-DETRv2
- **Event** - Security events with risk scores
- **GPUStats** - GPU performance metrics
- **Log** - System and frontend logs

## Real-Time Communication

### WebSocket Endpoints

- **`/ws/events`** - Real-time security event notifications
- **`/ws/system`** - System status updates (GPU, cameras, health)

Both use broadcaster pattern for efficient multi-client messaging. WebSocket authentication uses the same API key validation as HTTP endpoints, provided via query parameter or `Sec-WebSocket-Protocol` header.

## Security Considerations

### Authentication Middleware

Optional API key authentication (configurable via environment):

- Configurable via `API_KEY_ENABLED` environment variable
- SHA-256 hashed API keys for validation
- Header (`X-API-Key`) or query parameter (`api_key`) authentication
- Exempt paths: health checks, docs, root
- WebSocket authentication via query param or protocol header

### Media Endpoint Security

The `/api/media/*` endpoints implement strict security controls:

- Path traversal prevention (blocks `..` and absolute paths)
- File type whitelist (only images and videos)
- Base path validation (ensures files are within allowed directories)
- Resolved path checking (prevents symlink escapes)

## API Endpoints Overview

### Cameras (`/api/cameras`)

- `GET /api/cameras` - List cameras with optional status filter
- `GET /api/cameras/{id}` - Get specific camera
- `GET /api/cameras/{id}/snapshot` - Get latest snapshot image
- `POST /api/cameras` - Create new camera
- `PATCH /api/cameras/{id}` - Update camera
- `DELETE /api/cameras/{id}` - Delete camera (cascades)

### Events (`/api/events`)

- `GET /api/events` - List events with filters (risk level, date, reviewed, object_type)
- `GET /api/events/stats` - Get aggregated event statistics by risk level and camera
- `GET /api/events/{id}` - Get specific event with notes
- `PATCH /api/events/{id}` - Update event (reviewed status and notes)
- `GET /api/events/{id}/detections` - Get detections for event

### Logs (`/api/logs`)

- `GET /api/logs` - List logs with filters (level, component, source, date, search)
- `GET /api/logs/stats` - Get log statistics for dashboard (counts by level/component)
- `GET /api/logs/{id}` - Get specific log entry
- `POST /api/logs/frontend` - Submit frontend log entry

### Detections (`/api/detections`)

- `GET /api/detections` - List detections with filters (camera, object type, confidence)
- `GET /api/detections/{id}` - Get specific detection
- `GET /api/detections/{id}/image` - Get detection thumbnail with bounding box

### System (`/api/system`)

- `GET /api/system/health` - Detailed system health check
- `GET /api/system/health/live` - Liveness probe (always returns "alive")
- `GET /api/system/health/ready` - Readiness probe (checks all dependencies)
- `GET /api/system/gpu` - Current GPU stats
- `GET /api/system/gpu/history` - GPU stats time series
- `GET /api/system/stats` - System statistics (counts, uptime)
- `GET /api/system/config` - Public configuration
- `PATCH /api/system/config` - Update configuration
- `GET /api/system/telemetry` - Pipeline queue depths and latency stats

### Media (`/api/media`)

- `GET /api/media/cameras/{camera_id}/{filename}` - Serve camera media
- `GET /api/media/thumbnails/{filename}` - Serve detection thumbnails
- `GET /api/media/{path}` - Compatibility route for legacy paths

### Dead-Letter Queue (`/api/dlq`)

- `GET /api/dlq/stats` - Get DLQ statistics
- `GET /api/dlq/jobs/{queue_name}` - List jobs in a specific DLQ
- `POST /api/dlq/requeue/{queue_name}` - Requeue single job from DLQ
- `POST /api/dlq/requeue-all/{queue_name}` - Requeue all jobs from DLQ
- `DELETE /api/dlq/{queue_name}` - Clear all jobs from DLQ

### Metrics (`/api/metrics`)

- `GET /api/metrics` - Prometheus metrics in exposition format

### WebSocket

- `WS /ws/events` - Real-time event stream
- `WS /ws/system` - Real-time system status stream

## Integration Points

### External Dependencies

- **FastAPI** - Web framework
- **SQLAlchemy** - ORM for database access
- **Pydantic** - Data validation
- **Redis** - Pub/sub for WebSocket broadcasting and job queues

### Internal Dependencies

- `backend.core.database` - Database session management
- `backend.core.redis` - Redis client
- `backend.core.config` - Application settings
- `backend.core.metrics` - Prometheus metrics registry
- `backend.core.logging` - Structured logging with request ID context
- `backend.models.*` - SQLAlchemy models
- `backend.services.*` - Business logic services

### Service Layer Integration

Routes delegate to services for:

- **EventBroadcaster** - WebSocket event streaming
- **SystemBroadcaster** - WebSocket system status streaming
- **ThumbnailGenerator** - Detection image generation
- **GPUMonitor** - GPU metrics collection
- **RetryHandler** - Dead-letter queue management

## Entry Points for Understanding the Code

1. **Start with routes**: Each route file is self-contained with clear HTTP endpoint definitions
2. **Follow the schemas**: Schemas define the API contract and are well-documented
3. **Check middleware**: Understand cross-cutting concerns like auth and request ID
4. **Trace to services**: Routes call services in `backend/services/` for business logic

## Testing Approach

When testing the API layer:

1. **Unit Tests** - Test individual route handlers with mocked dependencies
2. **Integration Tests** - Test full request/response cycle with test database
3. **WebSocket Tests** - Test connection lifecycle and message broadcasting
4. **Security Tests** - Test authentication, path traversal prevention
5. **Validation Tests** - Test Pydantic schema validation

See `backend/tests/unit/` and `backend/tests/integration/` for examples.
