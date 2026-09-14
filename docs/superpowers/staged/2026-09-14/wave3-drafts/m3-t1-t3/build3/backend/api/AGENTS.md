# Backend API Package

## Purpose

The `backend/api/` package contains the FastAPI REST API layer for the home security monitoring system. It provides HTTP endpoints for managing cameras, events, detections, system monitoring, media serving, dead-letter queue management, Prometheus metrics, and real-time WebSocket communication.

## Directory Structure

```
backend/api/
├── __init__.py              # Package initialization
├── AGENTS.md                # This file
├── dependencies.py          # Reusable utility functions for entity existence checks
├── exception_handlers.py    # Global exception handlers for standardized error responses
├── pagination.py            # Pagination utilities for list endpoints
├── validators.py            # Request validation helpers
├── helpers/                 # Helper modules for API transformations
├── routes/                  # 28 API route handlers (endpoints)
├── schemas/                 # 43 Pydantic schemas for request/response validation
├── middleware/              # 20 HTTP middleware components
└── utils/                   # API utility modules
```

## Key Files

### `__init__.py`

Package initialization. Contains a simple docstring: "API package for routes and websocket handlers."

### `dependencies.py`

Reusable utility functions for entity existence checks. These functions abstract the repeated
pattern of querying for an entity by ID and raising a 404 if not found:

| Function               | Purpose                                         |
| ---------------------- | ----------------------------------------------- |
| `get_camera_or_404`    | Get camera by ID or raise HTTPException(404)    |
| `get_event_or_404`     | Get event by ID or raise HTTPException(404)     |
| `get_detection_or_404` | Get detection by ID or raise HTTPException(404) |

Usage pattern (modern Annotated style - NEM-3742):

```python
from backend.api.dependencies import DbSession, get_camera_or_404

@router.get("/{camera_id}")
async def get_camera(camera_id: str, db: DbSession) -> Camera:
    return await get_camera_or_404(camera_id, db)
```

**Annotated Dependency Type Aliases (NEM-3742):**

| Type Alias           | Description                                    |
| -------------------- | ---------------------------------------------- |
| `DbSession`          | Database session for write operations          |
| `ReadDbSession`      | Read-only session (uses replica if configured) |
| `RedisDep`           | Redis client dependency                        |
| `CacheDep`           | CacheService dependency                        |
| `BaselineServiceDep` | BaselineService dependency                     |
| `JobTrackerDep`      | JobTracker dependency                          |
| `ClipGeneratorDep`   | ClipGenerator dependency                       |

Legacy pattern (still supported):

```python
from fastapi import Depends
from backend.core.database import get_db

@router.get("/{camera_id}")
async def get_camera(camera_id: str, db: AsyncSession = Depends(get_db)) -> Camera:
    return await get_camera_or_404(camera_id, db)
```

### `pagination.py`

Pagination utilities for list endpoints:

- Standard pagination parameters (limit, offset)
- Cursor-based pagination support
- Page size limits and defaults

### `validators.py`

Request validation helpers:

- Custom field validators
- Common validation patterns
- Request data sanitization

### `exception_handlers.py`

Global exception handlers for standardized error responses across the API. Converts all
exceptions to a consistent JSON format with proper logging, request tracing, and error
sanitization.

**Key Features:**

- Standardized error response format with error codes, messages, and request IDs
- Automatic error logging with appropriate severity levels
- Error message sanitization to prevent information leakage
- Integration with request tracing (X-Request-ID headers)
- Support for custom exception types (SecurityIntelligenceError, CircuitBreakerOpenError, etc.)

**Exception Handlers:**

| Handler                                   | Exception Type            | Purpose                            |
| ----------------------------------------- | ------------------------- | ---------------------------------- |
| `security_intelligence_exception_handler` | SecurityIntelligenceError | Application-specific errors        |
| `http_exception_handler`                  | HTTPException             | Standard HTTP exceptions           |
| `validation_exception_handler`            | RequestValidationError    | Request validation errors          |
| `pydantic_validation_handler`             | PydanticValidationError   | Response serialization errors      |
| `circuit_breaker_exception_handler`       | CircuitBreakerOpenError   | Circuit breaker open errors        |
| `rate_limit_exception_handler`            | RateLimitError            | Rate limit exceeded errors         |
| `external_service_exception_handler`      | ExternalServiceError      | External service failures          |
| `generic_exception_handler`               | Exception                 | Catch-all for unhandled exceptions |

**Error Response Format:**

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "request_id": "a1b2c3d4",
    "timestamp": "2025-01-07T10:30:00Z",
    "details": {}
  }
}
```

Registration in main.py:

```python
from backend.api.exception_handlers import register_exception_handlers

app = FastAPI()
register_exception_handlers(app)
```

## Key Components

### Helpers (`helpers/`)

Helper modules for API data transformations and processing:

| File                         | Purpose                                                     |
| ---------------------------- | ----------------------------------------------------------- |
| `enrichment_transformers.py` | Transform enrichment JSONB data to structured API responses |

**`enrichment_transformers.py`:**

Provides helper classes for transforming raw enrichment data from the database (JSONB format)
into structured API response format using an extractor pattern.

**Key Classes:**

| Class                     | Purpose                                          |
| ------------------------- | ------------------------------------------------ |
| `EnrichmentTransformer`   | Main transformer orchestrating all extractors    |
| `BaseEnrichmentExtractor` | Abstract base class for enrichment extractors    |
| `LicensePlateExtractor`   | Extract license plate data                       |
| `FaceExtractor`           | Extract face detection data                      |
| `ViolenceExtractor`       | Extract violence detection data                  |
| `VehicleExtractor`        | Extract vehicle classification and damage data   |
| `ClothingExtractor`       | Extract clothing classification and segmentation |
| `ImageQualityExtractor`   | Extract image quality assessment data            |
| `PetExtractor`            | Extract pet classification data                  |

**Key Functions:**

| Function                     | Purpose                                          |
| ---------------------------- | ------------------------------------------------ |
| `transform_enrichment_data`  | Main entry point for enrichment transformation   |
| `get_enrichment_transformer` | Get the default transformer singleton            |
| `sanitize_errors`            | Sanitize error messages to remove sensitive data |

Usage pattern:

```python
from backend.api.helpers.enrichment_transformers import transform_enrichment_data

enrichment_response = transform_enrichment_data(
    detection_id=detection.id,
    enrichment_data=detection.enrichment_data,
    detected_at=detection.detected_at,
)
```

**Design Highlights:**

- Validates enrichment data schema before transformation (NEM-1351)
- Uses extractor pattern to reduce code duplication (NEM-1349)
- Breaks down transformation into smaller, focused helper classes (NEM-1307)
- Sanitizes error messages to prevent information leakage in API responses

### Routes (`routes/`)

Contains FastAPI routers that define HTTP endpoints (28 route files):

| File                          | Purpose                                                |
| ----------------------------- | ------------------------------------------------------ |
| `admin.py`                    | Development-only seed data endpoints (DEBUG mode)      |
| `ai_audit.py`                 | AI pipeline audit, quality scoring, recommendations    |
| `alerts.py`                   | Alert rules CRUD and rule testing                      |
| `analytics.py`                | Detection trends, risk history, camera uptime, objects |
| `audit.py`                    | Audit log listing and statistics                       |
| `calibration.py`              | Camera calibration endpoints                           |
| `cameras.py`                  | Camera CRUD operations and snapshot serving            |
| `debug.py`                    | Debug endpoints for runtime diagnostics (DEBUG mode)   |
| `detections.py`               | Object detection listing and thumbnail serving         |
| `dlq.py`                      | Dead-letter queue inspection and management            |
| `entities.py`                 | Entity re-identification tracking across cameras       |
| `events.py`                   | Security event management, queries, and statistics     |
| `exports.py`                  | Data export management and download                    |
| `feedback.py`                 | User feedback on events and detections                 |
| `jobs.py`                     | Background job management and monitoring               |
| `logs.py`                     | System and frontend log management                     |
| `media.py`                    | Secure file serving for images/videos                  |
| `metrics.py`                  | Prometheus metrics endpoint                            |
| `notification.py`             | Notification configuration and test endpoints          |
| `notification_preferences.py` | Global notification preferences and quiet hours        |
| `prompt_management.py`        | Prompt configuration with versioning and testing       |
| `queues.py`                   | Queue status and management                            |
| `rum.py`                      | Real User Monitoring - Core Web Vitals ingestion       |
| `services.py`                 | Container orchestrator service management              |
| `system.py`                   | System health, GPU stats, configuration, telemetry     |
| `websocket.py`                | WebSocket endpoints for real-time updates              |
| `zones.py`                    | Camera zone management (nested under cameras)          |

### Schemas (`schemas/`)

Contains Pydantic models for request/response validation (43 schema files):

| File                          | Purpose                                                    |
| ----------------------------- | ---------------------------------------------------------- |
| `ai_audit.py`                 | AI pipeline audit response schemas                         |
| `alerts.py`                   | Alert rules and alerts CRUD schemas                        |
| `analytics.py`                | Detection trends, risk history, uptime, object dist.       |
| `audit.py`                    | Audit log entry and statistics schemas                     |
| `baseline.py`                 | Camera baseline activity and anomaly detection schemas     |
| `bulk.py`                     | Bulk create/update/delete operations with 207 Multi-Status |
| `calibration.py`              | Camera calibration schemas                                 |
| `camera.py`                   | Camera data validation schemas                             |
| `clips.py`                    | Event clip generation schemas                              |
| `detections.py`               | Detection response and enrichment data schemas             |
| `dlq.py`                      | Dead-letter queue schemas                                  |
| `enrichment.py`               | Structured enrichment API response schemas                 |
| `enrichment_data.py`          | Enrichment JSONB field validation schemas                  |
| `entities.py`                 | Entity re-identification schemas                           |
| `errors.py`                   | Standardized error response schemas (RFC 7807 compatible)  |
| `events.py`                   | Event request/response and statistics schemas              |
| `export.py`                   | Data export request/response schemas                       |
| `feedback.py`                 | User feedback schemas                                      |
| `hateoas.py`                  | HATEOAS hypermedia links for API discoverability           |
| `health.py`                   | Health check schemas (liveness, readiness, full health)    |
| `jobs.py`                     | Background job schemas                                     |
| `llm.py`                      | LLM response validation with entity/flag schemas           |
| `llm_response.py`             | Simpler LLM response validation (risk score/level)         |
| `logs.py`                     | Log entry and statistics schemas                           |
| `media.py`                    | Media error response schemas                               |
| `notification.py`             | Notification delivery and configuration schemas            |
| `notification_preferences.py` | Notification preferences and quiet hours schemas           |
| `openapi_docs.py`             | OpenAPI documentation customization schemas                |
| `pagination.py`               | Pagination response schemas                                |
| `performance.py`              | System performance metrics schemas (GPU, AI, host)         |
| `problem_details.py`          | RFC 7807 Problem Details for standardized errors           |
| `prompt_management.py`        | Prompt configuration and versioning schemas                |
| `queue.py`                    | Queue message payload validation (security-focused)        |
| `queue_status.py`             | Queue status response schemas                              |
| `rum.py`                      | Real User Monitoring (Core Web Vitals) schemas             |
| `scene_change.py`             | Scene change detection schemas                             |
| `search.py`                   | Event full-text search schemas                             |
| `services.py`                 | Container orchestrator service schemas                     |
| `streaming.py`                | SSE streaming event schemas (progress, complete, error)    |
| `system.py`                   | System monitoring, config, health, and telemetry schemas   |
| `websocket.py`                | WebSocket message validation schemas                       |
| `zone.py`                     | Camera zone management schemas                             |

### Middleware (`middleware/`)

HTTP middleware for cross-cutting concerns (20 middleware files):

| File                        | Purpose                                                |
| --------------------------- | ------------------------------------------------------ |
| `accept_header.py`          | Accept header parsing and validation                   |
| `auth.py`                   | API key authentication (HTTP and WebSocket)            |
| `body_limit.py`             | Request body size limits for DoS protection            |
| `content_negotiation.py`    | Content negotiation handling                           |
| `content_type_validator.py` | Content-Type header validation for request bodies      |
| `correlation.py`            | Correlation ID propagation to outgoing requests        |
| `deprecation.py`            | API deprecation handling                               |
| `deprecation_logger.py`     | Deprecated endpoint logging                            |
| `error_handler.py`          | Error response formatting                              |
| `exception_handler.py`      | Exception handling utilities with data minimization    |
| `file_validator.py`         | File magic number validation for upload security       |
| `idempotency.py`            | Idempotency key handling                               |
| `rate_limit.py`             | Redis-based sliding window rate limiting               |
| `request_id.py`             | Request ID generation and propagation for tracing      |
| `request_logging.py`        | Structured HTTP request/response logging               |
| `request_recorder.py`       | Request recording for replay debugging (NEM-1646)      |
| `request_timing.py`         | Request timing and slow request logging                |
| `security_headers.py`       | Security headers (CSP, X-Frame-Options, etc.)          |
| `websocket_auth.py`         | WebSocket token authentication (separate from API key) |

## Architecture Overview

This API layer follows a clean architecture pattern:

1. **Middleware** - Authentication, request ID propagation, rate limiting, error handling
2. **Routes** - Handle HTTP requests, call services, return responses
3. **Schemas** - Validate incoming data and serialize outgoing data
4. **Services** - Business logic (AI pipeline, broadcasting, monitoring, alerts)
5. **Database** - SQLAlchemy async sessions via dependency injection
6. **Redis** - Redis client via dependency injection for pub/sub, queues, and rate limiting

## Common Patterns

### Dependency Injection

All routes use FastAPI's dependency injection for:

- Database sessions: `db: AsyncSession = Depends(get_db)`
- Redis client: `redis: RedisClient = Depends(get_redis)`
- Settings: `get_settings()`

### Error Handling

- **401 Unauthorized** - Missing or invalid API key
- **403 Forbidden** - Access denied (path traversal, invalid file types, debug-only endpoints)
- **404 Not Found** - Resource doesn't exist
- **422 Unprocessable Entity** - Validation errors (automatic via Pydantic)
- **429 Too Many Requests** - Rate limit exceeded
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
- **Detection** - Object detections from YOLO26v2
- **Event** - Security events with risk scores
- **GPUStats** - GPU performance metrics
- **Log** - System and frontend logs
- **AlertRule** - Alert rule definitions
- **Alert** - Triggered alerts
- **AuditLog** - Security audit trail
- **Zone** - Camera detection zones

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
- `GET /health` (root level) - Liveness probe (always returns "alive")
- `GET /api/system/health/ready` - Readiness probe (checks all dependencies)
- `GET /api/system/gpu` - Current GPU stats
- `GET /api/system/gpu/history` - GPU stats time series
- `GET /api/system/stats` - System statistics (counts, uptime)
- `GET /api/system/config` - Public configuration
- `PATCH /api/system/config` - Update configuration (requires API key)
- `GET /api/system/telemetry` - Pipeline queue depths and latency stats
- `GET /api/system/pipeline-latency` - Pipeline stage transition latencies with percentiles
- `POST /api/system/cleanup` - Trigger manual data cleanup (requires API key, supports dry_run)
- `GET /api/system/severity` - Severity level definitions and thresholds
- `GET /api/system/storage` - Storage statistics and disk usage

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

### Alert Rules (`/api/alerts/rules`)

- `GET /api/alerts/rules` - List alert rules with filtering
- `POST /api/alerts/rules` - Create new alert rule
- `GET /api/alerts/rules/{id}` - Get specific alert rule
- `PUT /api/alerts/rules/{id}` - Update alert rule
- `DELETE /api/alerts/rules/{id}` - Delete alert rule
- `POST /api/alerts/rules/{id}/test` - Test rule against historical events

### Audit (`/api/audit`)

- `GET /api/audit` - List audit logs with filtering
- `GET /api/audit/stats` - Get audit log statistics
- `GET /api/audit/{id}` - Get specific audit log entry

### Zones (`/api/cameras/{camera_id}/zones`)

- `GET /api/cameras/{id}/zones` - List zones for camera
- `POST /api/cameras/{id}/zones` - Create zone for camera
- `GET /api/cameras/{id}/zones/{zone_id}` - Get specific zone
- `PUT /api/cameras/{id}/zones/{zone_id}` - Update zone
- `DELETE /api/cameras/{id}/zones/{zone_id}` - Delete zone

### Notification (`/api/notification`)

- `GET /api/notification/config` - Get notification configuration status
- `POST /api/notification/test` - Test notification channel delivery

### Admin (DEBUG mode only) (`/api/admin`)

- `POST /api/admin/seed/cameras` - Seed test cameras
- `POST /api/admin/seed/events` - Seed test events and detections
- `DELETE /api/admin/seed/clear` - Clear all seeded data

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
- **AlertRuleEngine** - Alert rule evaluation and testing
- **AuditService** - Audit log recording and querying

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
