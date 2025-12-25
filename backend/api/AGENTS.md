# Backend API Package

## Purpose

The `backend/api/` package contains the FastAPI REST API layer for the home security monitoring system. It provides HTTP endpoints for managing cameras, events, detections, system monitoring, media serving, and real-time WebSocket communication.

## Directory Structure

```
backend/api/
├── __init__.py          # Package initialization
├── routes/              # API route handlers (endpoints)
├── schemas/             # Pydantic schemas for request/response validation
└── middleware/          # HTTP middleware components (auth, etc.)
```

## Key Components

### Routes (`routes/`)

Contains FastAPI routers that define HTTP endpoints:

- **cameras.py** - Camera CRUD operations and snapshot serving
- **events.py** - Security event management, queries, and statistics
- **detections.py** - Object detection listing and thumbnail serving
- **logs.py** - System and frontend log management
- **websocket.py** - WebSocket endpoints for real-time updates
- **system.py** - System health, GPU stats, configuration
- **media.py** - Secure file serving for images/videos

### Schemas (`schemas/`)

Contains Pydantic models for request/response validation:

- **camera.py** - Camera data validation schemas
- **events.py** - Event request/response and statistics schemas
- **detections.py** - Detection response schemas
- **logs.py** - Log entry and statistics schemas
- **system.py** - System monitoring and config schemas
- **media.py** - Media error response schemas

### Middleware (`middleware/`)

HTTP middleware for cross-cutting concerns:

- **auth.py** - API key authentication (optional, configurable)

## Architecture Overview

This API layer follows a clean architecture pattern:

1. **Middleware** - Authentication, request logging, error handling
2. **Routes** - Handle HTTP requests, call services, return responses
3. **Schemas** - Validate incoming data and serialize outgoing data
4. **Services** - Business logic (AI pipeline, broadcasting, monitoring)
5. **Database** - SQLAlchemy async sessions via dependency injection
6. **Redis** - Redis client via dependency injection for pub/sub

## Common Patterns

### Dependency Injection

All routes use FastAPI's dependency injection for:

- Database sessions: `db: AsyncSession = Depends(get_db)`
- Redis client: `redis: RedisClient = Depends(get_redis)`
- Settings: `get_settings()`

### Error Handling

- **401 Unauthorized** - Missing or invalid API key
- **404 Not Found** - Resource doesn't exist
- **403 Forbidden** - Access denied (path traversal, invalid file types)
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

## Real-Time Communication

### WebSocket Endpoints

- **`/ws/events`** - Real-time security event notifications
- **`/ws/system`** - System status updates (GPU, cameras, health)

Both use broadcaster pattern for efficient multi-client messaging.

## Security Considerations

### Authentication Middleware

Optional API key authentication (disabled by default for development):

- Configurable via `API_KEY_ENABLED` environment variable
- SHA-256 hashed API keys for validation
- Header or query parameter authentication
- Exempt paths: health checks, docs, root

### Media Endpoint Security

The `/api/media/*` endpoints implement strict security controls:

- Path traversal prevention (blocks `..` and absolute paths)
- File type whitelist (only images and videos)
- Base path validation (ensures files are within allowed directories)
- Resolved path checking (prevents symlink escapes)

## Integration Points

### External Dependencies

- **FastAPI** - Web framework
- **SQLAlchemy** - ORM for database access
- **Pydantic** - Data validation
- **Redis** - Pub/sub for WebSocket broadcasting

### Internal Dependencies

- `backend.core.database` - Database session management
- `backend.core.redis` - Redis client
- `backend.core.config` - Application settings
- `backend.models.*` - SQLAlchemy models
- `backend.services.*` - Business logic services

### Service Layer Integration

Routes delegate to services for:

- **EventBroadcaster** - WebSocket event streaming
- **SystemBroadcaster** - WebSocket system status streaming
- **ThumbnailGenerator** - Detection image generation
- **GPUMonitor** - GPU metrics collection

## API Endpoints Overview

### Cameras

- `GET /api/cameras` - List cameras with optional status filter
- `GET /api/cameras/{id}` - Get specific camera
- `GET /api/cameras/{id}/snapshot` - Get latest snapshot image
- `POST /api/cameras` - Create new camera
- `PATCH /api/cameras/{id}` - Update camera
- `DELETE /api/cameras/{id}` - Delete camera (cascades)

### Events

- `GET /api/events` - List events with filters (risk level, date, reviewed, object_type)
- `GET /api/events/stats` - Get aggregated event statistics by risk level and camera
- `GET /api/events/{id}` - Get specific event with notes
- `PATCH /api/events/{id}` - Update event (reviewed status and notes)
- `GET /api/events/{id}/detections` - Get detections for event

### Logs

- `GET /api/logs` - List logs with filters (level, component, source, date, search)
- `GET /api/logs/stats` - Get log statistics for dashboard (counts by level/component)
- `GET /api/logs/{id}` - Get specific log entry
- `POST /api/logs/frontend` - Submit frontend log entry

### Detections

- `GET /api/detections` - List detections with filters (camera, object type, confidence)
- `GET /api/detections/{id}` - Get specific detection
- `GET /api/detections/{id}/image` - Get detection thumbnail with bounding box

### System

- `GET /api/system/health` - System health check
- `GET /api/system/gpu` - Current GPU stats
- `GET /api/system/gpu/history` - GPU stats time series
- `GET /api/system/stats` - System statistics (counts, uptime)
- `GET /api/system/config` - Public configuration
- `PATCH /api/system/config` - Update configuration

### Media

- `GET /api/media/cameras/{camera_id}/{filename}` - Serve camera media
- `GET /api/media/thumbnails/{filename}` - Serve detection thumbnails

### WebSocket

- `WS /ws/events` - Real-time event stream
- `WS /ws/system` - Real-time system status stream

## Testing Approach

When testing the API layer:

1. **Unit Tests** - Test individual route handlers with mocked dependencies
2. **Integration Tests** - Test full request/response cycle with test database
3. **WebSocket Tests** - Test connection lifecycle and message broadcasting
4. **Security Tests** - Test authentication, path traversal prevention
5. **Validation Tests** - Test Pydantic schema validation

See `backend/tests/unit/` and `backend/tests/integration/` for examples.
