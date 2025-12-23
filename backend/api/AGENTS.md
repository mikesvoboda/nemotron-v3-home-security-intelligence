# Backend API Package

## Purpose

The `backend/api/` package contains the FastAPI REST API layer for the home security monitoring system. It provides HTTP endpoints for managing cameras, system monitoring, and serving media files.

## Directory Structure

```
backend/api/
├── __init__.py          # Package initialization
├── routes/              # API route handlers (endpoints)
└── schemas/             # Pydantic schemas for request/response validation
```

## Key Components

### Routes (`routes/`)

Contains FastAPI routers that define HTTP endpoints:

- **cameras.py** - Camera CRUD operations
- **system.py** - System health, GPU stats, configuration
- **media.py** - Secure file serving for images/videos

### Schemas (`schemas/`)

Contains Pydantic models for request/response validation:

- **camera.py** - Camera data validation schemas
- **system.py** - System monitoring response schemas
- **media.py** - Media error response schemas

## Architecture Overview

This API layer follows a clean architecture pattern:

1. **Routes** - Handle HTTP requests, call service layer (future), return responses
2. **Schemas** - Validate incoming data and serialize outgoing data
3. **Database** - Uses SQLAlchemy async sessions via dependency injection
4. **Redis** - Uses Redis client via dependency injection for caching/pub-sub

## Common Patterns

### Dependency Injection

All routes use FastAPI's dependency injection for:

- Database sessions: `db: AsyncSession = Depends(get_db)`
- Redis client: `redis: RedisClient = Depends(get_redis)`
- Settings: `get_settings()`

### Error Handling

- **404 Not Found** - Resource doesn't exist
- **403 Forbidden** - Access denied (path traversal, invalid file types)
- **422 Unprocessable Entity** - Validation errors (automatic via Pydantic)
- **500 Internal Server Error** - Unexpected errors

### Response Models

All endpoints specify response models via `response_model` parameter for automatic validation and OpenAPI documentation generation.

## Database Models Used

The API interacts with these SQLAlchemy models:

- **Camera** - Camera configuration and status
- **Detection** - Object detections from RT-DETR
- **Event** - Security events with risk scores
- **GPUStats** - GPU performance metrics

## Security Considerations

### Media Endpoint

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
- **Redis** - Caching and pub/sub

### Internal Dependencies

- `backend.core.database` - Database session management
- `backend.core.redis` - Redis client
- `backend.core.config` - Application settings
- `backend.models.*` - SQLAlchemy models

## Future Enhancements

- Service layer to separate business logic from routes
- WebSocket endpoints for real-time updates
- Authentication/authorization (currently single-user)
- Rate limiting
- Request logging middleware
