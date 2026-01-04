# API Routes

## Purpose

The `backend/api/routes/` directory contains FastAPI router modules that define HTTP endpoints for the home security monitoring system. Each file groups related endpoints by resource type (cameras, events, detections, system, media, WebSocket, DLQ, metrics).

## Files

### `__init__.py`

Package initialization with public exports:

- `alerts_router` - Alert rules API router
- `audit_router` - Audit logs API router
- `logs_router` - Logs API router
- `zones_router` - Camera zones API router

Note: Other routers (cameras, events, detections, system, media, websocket, dlq, metrics, notification, admin) are imported directly via FastAPI app.include_router() in main.py.

### `cameras.py`

Camera management CRUD endpoints and snapshot serving.

**Router prefix:** `/api/cameras`

**Endpoints:**

| Method | Path                                | Purpose                                         |
| ------ | ----------------------------------- | ----------------------------------------------- |
| GET    | `/api/cameras`                      | List all cameras with optional status filter    |
| GET    | `/api/cameras/{camera_id}`          | Get a specific camera by ID                     |
| GET    | `/api/cameras/{camera_id}/snapshot` | Get latest snapshot image                       |
| POST   | `/api/cameras`                      | Create a new camera                             |
| PATCH  | `/api/cameras/{camera_id}`          | Update an existing camera                       |
| DELETE | `/api/cameras/{camera_id}`          | Delete a camera (cascades to detections/events) |

**Key Features:**

- UUID generation for new cameras
- Partial updates via PATCH (only updates provided fields)
- Cascade deletion of related data
- Latest snapshot serving from camera folder (finds most recently modified image)
- Path traversal protection for snapshot serving

### `events.py`

Security event management, querying, and statistics.

**Router prefix:** `/api/events`

**Endpoints:**

| Method | Path                                | Purpose                                |
| ------ | ----------------------------------- | -------------------------------------- |
| GET    | `/api/events`                       | List events with filtering/pagination  |
| GET    | `/api/events/stats`                 | Get aggregated event statistics        |
| GET    | `/api/events/{event_id}`            | Get specific event by ID               |
| PATCH  | `/api/events/{event_id}`            | Update event (reviewed status & notes) |
| GET    | `/api/events/{event_id}/detections` | Get detections for event               |

**Query Parameters (List):**

- `camera_id` - Filter by camera ID (e.g., "front_door")
- `risk_level` - Filter by risk level (low, medium, high, critical)
- `start_date` / `end_date` - Date range filter (ISO format)
- `reviewed` - Filter by reviewed status
- `object_type` - Filter by detected object type
- `limit` / `offset` - Pagination (default: 50, max: 1000)

**Key Features:**

- Object type filtering via detection join
- Detection count calculation from JSON array detection_ids
- Aggregated statistics by risk level and camera
- User notes support

### `detections.py`

Object detection listing and thumbnail image serving.

**Router prefix:** `/api/detections`

**Endpoints:**

| Method | Path                                   | Purpose                                   |
| ------ | -------------------------------------- | ----------------------------------------- |
| GET    | `/api/detections`                      | List detections with filtering/pagination |
| GET    | `/api/detections/{detection_id}`       | Get specific detection by ID              |
| GET    | `/api/detections/{detection_id}/image` | Get thumbnail with bounding box           |

**Query Parameters (List):**

- `camera_id` - Filter by camera ID (e.g., "front_door")
- `object_type` - Filter by object type (person, car, etc.)
- `start_date` / `end_date` - Date range filter
- `min_confidence` - Minimum confidence (0.0-1.0)
- `limit` / `offset` - Pagination

**Key Features:**

- On-the-fly thumbnail generation if not cached
- Bounding box overlay on images
- Image caching with 1-hour cache headers
- Integration with ThumbnailGenerator service

### `logs.py`

System and frontend log management.

**Router prefix:** `/api/logs`

**Endpoints:**

| Method | Path                 | Purpose                             |
| ------ | -------------------- | ----------------------------------- |
| GET    | `/api/logs`          | List logs with filtering/pagination |
| GET    | `/api/logs/stats`    | Get log statistics for dashboard    |
| GET    | `/api/logs/{log_id}` | Get specific log entry by ID        |
| POST   | `/api/logs/frontend` | Submit frontend log entry           |

**Query Parameters (List):**

- `level` - Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `component` - Filter by component/module name
- `camera_id` - Filter by associated camera ID (e.g., "front_door")
- `source` - Filter by source (backend, frontend)
- `search` - Search in message text (case-insensitive)
- `start_date` / `end_date` - Date range filter
- `limit` / `offset` - Pagination (default: 100)

**Key Features:**

- Dashboard statistics (today's counts by level and component)
- Frontend log ingestion with automatic user agent capture
- Top component identification

### `websocket.py`

WebSocket endpoints for real-time communication.

**Router prefix:** None (WebSocket endpoints)

**Endpoints:**

| Method | Path         | Purpose                         |
| ------ | ------------ | ------------------------------- |
| WS     | `/ws/events` | Real-time security event stream |
| WS     | `/ws/system` | Real-time system status stream  |

**Event Stream (`/ws/events`):**

- Broadcasts security events as they are analyzed
- Message format: `{"type": "event", "data": {...}}`
- Uses EventBroadcaster service

**System Stream (`/ws/system`):**

- Broadcasts system status updates every 5 seconds
- Message format: `{"type": "system_status", "data": {...}}`
- Uses SystemBroadcaster service

**Authentication:**
When API key auth is enabled, provide key via:

- Query parameter: `ws://host/ws/events?api_key=YOUR_KEY`
- Sec-WebSocket-Protocol header: `api-key.YOUR_KEY`

**Connection Lifecycle:**

1. Client connects and is authenticated (if enabled)
2. Connection registered with broadcaster
3. Client receives broadcast messages
4. Ping/pong keep-alive support
5. Graceful disconnect and cleanup

### `system.py`

System monitoring, health checks, GPU stats, configuration, and telemetry.

**Router prefix:** `/api/system`

**Endpoints:**

| Method | Path                           | Purpose                                          |
| ------ | ------------------------------ | ------------------------------------------------ |
| GET    | `/api/system/health`           | Detailed system health check                     |
| GET    | `/health` (root level)         | Liveness probe (always returns "alive")          |
| GET    | `/api/system/health/ready`     | Readiness probe (checks all dependencies)        |
| GET    | `/api/system/gpu`              | Current GPU statistics                           |
| GET    | `/api/system/gpu/history`      | GPU stats time series                            |
| GET    | `/api/system/stats`            | System statistics (counts, uptime)               |
| GET    | `/api/system/config`           | Public configuration settings                    |
| PATCH  | `/api/system/config`           | Update configuration settings (API key required) |
| GET    | `/api/system/telemetry`        | Pipeline queue depths and latency stats          |
| GET    | `/api/system/pipeline-latency` | Pipeline stage transition latencies              |
| POST   | `/api/system/cleanup`          | Trigger manual cleanup (API key required)        |
| GET    | `/api/system/severity`         | Severity level definitions and thresholds        |
| GET    | `/api/system/storage`          | Storage statistics and disk usage                |

**Health Status Logic:**

- `healthy` - All services operational
- `degraded` - Some non-critical services down
- `unhealthy` - Critical services (database) down

**Readiness Logic:**

- `ready` - Database and Redis healthy
- `degraded` - Database up but Redis down
- `not_ready` - Database down

**Worker Status Tracking:**

- GPU monitor, cleanup service, system broadcaster, file watcher
- Workers registered via `register_workers()` at startup

**Telemetry:**

- Queue depths for detection and analysis queues
- Per-stage latency statistics (watch, detect, batch, analyze)
- Percentile calculations (p50, p95, p99)

**Key Features:**

- Multi-service health checks with timeout protection (5 seconds)
- Circuit breaker pattern for AI service health checks
- Runtime configuration updates persisted to env file
- Application uptime tracking
- Kubernetes-style liveness/readiness probes
- Pipeline latency tracking with percentiles (p50, p95, p99)
- Manual cleanup with dry_run mode for verification
- Severity taxonomy and thresholds for frontend consistency
- Storage stats with disk usage and per-category breakdown

### `media.py`

Secure media file serving for camera images and detection thumbnails.

**Router prefix:** `/api/media`

**Endpoints:**

| Method | Path                                        | Purpose                              |
| ------ | ------------------------------------------- | ------------------------------------ |
| GET    | `/api/media/cameras/{camera_id}/{filename}` | Serve camera images/videos           |
| GET    | `/api/media/thumbnails/{filename}`          | Serve detection thumbnails           |
| GET    | `/api/media/{path}`                         | Compatibility route for legacy paths |

**Allowed File Types:**

- Images: `.jpg`, `.jpeg`, `.png`, `.gif`
- Videos: `.mp4`, `.mkv`, `.avi`, `.mov`

**Security Features:**

- Path traversal prevention (blocks `..` and `/` prefixes)
- File type whitelist enforcement
- Base path validation (resolved path must be within allowed directory)
- Descriptive error responses via `MediaErrorResponse`

**Base Paths:**

- Camera files: `{foscam_base_path}/{camera_id}/`
- Thumbnails: `backend/data/thumbnails/`

### `dlq.py`

Dead-letter queue (DLQ) inspection and management.

**Router prefix:** `/api/dlq`

**Endpoints:**

| Method | Path                                | Purpose                     |
| ------ | ----------------------------------- | --------------------------- |
| GET    | `/api/dlq/stats`                    | Get DLQ statistics          |
| GET    | `/api/dlq/jobs/{queue_name}`        | List jobs in a specific DLQ |
| POST   | `/api/dlq/requeue/{queue_name}`     | Requeue oldest job from DLQ |
| POST   | `/api/dlq/requeue-all/{queue_name}` | Requeue all jobs from DLQ   |
| DELETE | `/api/dlq/{queue_name}`             | Clear all jobs from DLQ     |

**Queue Names:**

- `dlq:detection_queue` - Failed detection jobs
- `dlq:analysis_queue` - Failed analysis jobs

**Key Features:**

- View failed job payloads and error messages
- Retry failed jobs by moving back to processing queue
- Bulk requeue with iteration limit (10,000 max)
- Clear DLQ contents

### `metrics.py`

Prometheus metrics endpoint for observability.

**Router prefix:** `/api`

**Endpoints:**

| Method | Path           | Purpose                                        |
| ------ | -------------- | ---------------------------------------------- |
| GET    | `/api/metrics` | Return Prometheus metrics in exposition format |

**Key Features:**

- No authentication required (for Prometheus scraping)
- Standard Prometheus text format
- Integrates with `backend.core.metrics`

### `alerts.py`

Alert rules management with CRUD operations and rule testing.

**Router prefix:** `/api/alerts/rules`

**Endpoints:**

| Method | Path                               | Purpose                             |
| ------ | ---------------------------------- | ----------------------------------- |
| GET    | `/api/alerts/rules`                | List alert rules with filtering     |
| POST   | `/api/alerts/rules`                | Create new alert rule               |
| GET    | `/api/alerts/rules/{rule_id}`      | Get specific alert rule             |
| PUT    | `/api/alerts/rules/{rule_id}`      | Update alert rule                   |
| DELETE | `/api/alerts/rules/{rule_id}`      | Delete alert rule                   |
| POST   | `/api/alerts/rules/{rule_id}/test` | Test rule against historical events |

**Query Parameters (List):**

- `enabled` - Filter by enabled status
- `severity` - Filter by severity level (low, medium, high, critical)
- `limit` / `offset` - Pagination

**Key Features:**

- Rule conditions: risk threshold, object types, camera IDs, zone IDs, min confidence
- Schedule-based rules with timezone support (time-of-day filtering)
- Deduplication with cooldown windows
- Channel-based notification routing
- Rule testing against historical events to validate configuration

### `audit.py`

Audit log management for security and compliance tracking.

**Router prefix:** `/api/audit`

**Endpoints:**

| Method | Path                    | Purpose                      |
| ------ | ----------------------- | ---------------------------- |
| GET    | `/api/audit`            | List audit logs with filters |
| GET    | `/api/audit/stats`      | Get audit log statistics     |
| GET    | `/api/audit/{audit_id}` | Get specific audit log entry |

**Query Parameters (List):**

- `action` - Filter by action type
- `resource_type` - Filter by resource type (event, alert, rule, camera, settings)
- `resource_id` - Filter by specific resource ID
- `actor` - Filter by actor (user or system)
- `status` - Filter by status (success/failure)
- `start_date` / `end_date` - Date range filter
- `limit` / `offset` - Pagination

**Key Features:**

- Tracks security-sensitive operations
- Statistics aggregation by action, resource type, and status
- Recent actors tracking

### `zones.py`

Camera zone management (nested under cameras resource).

**Router prefix:** `/api/cameras`

**Endpoints:**

| Method | Path                                       | Purpose               |
| ------ | ------------------------------------------ | --------------------- |
| GET    | `/api/cameras/{camera_id}/zones`           | List zones for camera |
| POST   | `/api/cameras/{camera_id}/zones`           | Create zone           |
| GET    | `/api/cameras/{camera_id}/zones/{zone_id}` | Get specific zone     |
| PUT    | `/api/cameras/{camera_id}/zones/{zone_id}` | Update zone           |
| DELETE | `/api/cameras/{camera_id}/zones/{zone_id}` | Delete zone           |

**Query Parameters (List):**

- `enabled` - Filter by enabled status

**Key Features:**

- Polygon coordinates in normalized 0-1 range
- Zone types: entry_point, exit_point, restricted, monitored, other
- Shape support: rectangle, polygon
- Priority-based overlapping zones
- Color customization for UI display

### `notification.py`

Notification configuration and testing endpoints.

**Router prefix:** `/api/notification`

**Endpoints:**

| Method | Path                       | Purpose                            |
| ------ | -------------------------- | ---------------------------------- |
| GET    | `/api/notification/config` | Get notification configuration     |
| POST   | `/api/notification/test`   | Test notification channel delivery |

**Key Features:**

- Shows which notification channels are configured (email, webhook, push)
- Returns SMTP and webhook settings (without sensitive data)
- Test endpoint sends mock alerts to verify channel configuration
- Supports email, webhook, and push notification channels
- Integrates with AuditService for logging test actions

### `admin.py`

Development-only admin endpoints for seeding test data.

**Router prefix:** `/api/admin`

**Endpoints:**

| Method | Path                      | Purpose                         |
| ------ | ------------------------- | ------------------------------- |
| POST   | `/api/admin/seed/cameras` | Seed test cameras               |
| POST   | `/api/admin/seed/events`  | Seed mock events and detections |
| DELETE | `/api/admin/seed/clear`   | Clear all seeded data           |

**Key Features:**

- Only available when `DEBUG=true` in environment
- Predefined sample cameras (Front Door, Backyard, Garage, etc.)
- Mock events with realistic risk levels and summaries
- Weighted risk distribution (50% low, 35% medium, 15% high)
- Auto-generates detections with random bounding boxes

### `ai_audit.py`

AI pipeline audit management for model performance, quality scoring, and recommendations.

**Router prefix:** `/api/ai-audit`

**Endpoints:**

| Method | Path                                       | Purpose                                            |
| ------ | ------------------------------------------ | -------------------------------------------------- |
| GET    | `/api/ai-audit/events/{event_id}`          | Get audit info for a specific event                |
| POST   | `/api/ai-audit/events/{event_id}/evaluate` | Trigger full evaluation for an event               |
| GET    | `/api/ai-audit/stats`                      | Get aggregate AI audit statistics                  |
| GET    | `/api/ai-audit/leaderboard`                | Get model leaderboard by contribution rate         |
| GET    | `/api/ai-audit/recommendations`            | Get aggregated prompt improvement recommendations  |
| POST   | `/api/ai-audit/batch`                      | Trigger batch audit processing for multiple events |

**Query Parameters:**

- `days` - Number of days to include (1-90, default 7)
- `camera_id` - Filter by camera ID (stats endpoint)
- `force` - Force re-evaluation even if already evaluated (evaluate endpoint)
- `min_risk_score` - Minimum risk score filter (batch endpoint)
- `limit` - Maximum events to process (batch endpoint)

**Key Features:**

- Model contribution tracking (RT-DETR, Florence, CLIP, violence, clothing, vehicle, pet, weather, etc.)
- Quality scoring (context usage, reasoning coherence, risk justification, consistency)
- Prompt improvement suggestions (missing context, confusing sections, unused data, format suggestions)
- Model leaderboard with quality correlation
- Batch evaluation for historical events

### `entities.py`

Entity re-identification tracking across multiple cameras using CLIP embeddings.

**Router prefix:** `/api/entities`

**Endpoints:**

| Method | Path                                | Purpose                               |
| ------ | ----------------------------------- | ------------------------------------- |
| GET    | `/api/entities`                     | List tracked entities with filtering  |
| GET    | `/api/entities/{entity_id}`         | Get detailed info for an entity       |
| GET    | `/api/entities/{entity_id}/history` | Get appearance timeline for an entity |

**Query Parameters (List):**

- `entity_type` - Filter by type ('person' or 'vehicle')
- `camera_id` - Filter by camera ID
- `since` - Filter entities seen since this timestamp
- `limit` / `offset` - Pagination (default: 50, max: 1000)

**Key Features:**

- Cross-camera entity tracking using CLIP embeddings stored in Redis
- Appearance history with timestamps and camera locations
- Thumbnail URLs for each entity appearance
- Entity summaries with appearance counts and cameras seen
- Graceful degradation when Redis is unavailable

### `prompt_management.py`

Prompt configuration management for AI models with versioning, testing, and import/export.

**Router prefix:** `/api/ai-audit/prompts`

**Endpoints:**

| Method | Path                                         | Purpose                                 |
| ------ | -------------------------------------------- | --------------------------------------- |
| GET    | `/api/ai-audit/prompts`                      | Get all prompt configurations           |
| GET    | `/api/ai-audit/prompts/export`               | Export all prompts as JSON              |
| GET    | `/api/ai-audit/prompts/history`              | Get prompt version history              |
| POST   | `/api/ai-audit/prompts/test`                 | Test a modified prompt against an event |
| POST   | `/api/ai-audit/prompts/import`               | Import prompt configurations            |
| POST   | `/api/ai-audit/prompts/import/preview`       | Preview import changes without applying |
| POST   | `/api/ai-audit/prompts/history/{version_id}` | Restore a specific prompt version       |
| GET    | `/api/ai-audit/prompts/{model}`              | Get prompt for a specific model         |
| PUT    | `/api/ai-audit/prompts/{model}`              | Update prompt for a specific model      |

**Supported Models:**

- `nemotron` - System prompt for risk analysis
- `florence2` - Scene analysis queries
- `yolo_world` - Custom object classes and confidence threshold
- `xclip` - Action recognition classes
- `fashion_clip` - Clothing categories

**Key Features:**

- Full version history with change descriptions
- Export/import for backup and sharing configurations
- Import preview with diff computation
- A/B testing prompts against events or images
- Restore previous versions while preserving history

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

- `get_latest_gpu_stats(db)` - Fetch most recent GPU stats from database
- `check_database_health(db)` - Test database connectivity with timeout
- `check_redis_health(redis)` - Test Redis connectivity with timeout
- `check_ai_services_health()` - AI service health check (placeholder)
- `register_workers(...)` - Register background workers for readiness monitoring
- `record_stage_latency(redis, stage, latency_ms)` - Record pipeline latency sample
- `get_latency_stats(redis)` - Calculate latency statistics from Redis

### `media.py` Helpers

- `_validate_and_resolve_path(base_path, requested_path)` - Secure path validation
  - Prevents path traversal
  - Validates file exists
  - Checks file type is allowed
  - Returns resolved absolute path

### `dlq.py` Helpers

- `_get_target_queue(dlq_name)` - Get target queue for requeuing

## Integration Points

### Database Models

- `Camera` - Camera configuration
- `Detection` - Object detections
- `Event` - Security events
- `GPUStats` - GPU metrics
- `Log` - System and frontend logs
- `AlertRule` - Alert rule definitions
- `Alert` - Triggered alerts
- `AuditLog` - Security audit trail
- `Zone` - Camera detection zones

### External Services

- SQLAlchemy async engine
- Redis for health checks, queues, and pub/sub
- File system for media serving

### Configuration

Uses `backend.core.config.Settings` for:

- Foscam base path
- Application name/version
- Batch processing settings
- Retention policies

### Service Integration

- `EventBroadcaster` - WebSocket event broadcasting
- `SystemBroadcaster` - WebSocket system status broadcasting
- `ThumbnailGenerator` - Detection thumbnail generation
- `RetryHandler` - Dead-letter queue operations
- `AlertRuleEngine` - Alert rule evaluation and testing
- `AuditService` - Audit log recording and querying

## Testing Considerations

When testing routes:

1. Use `AsyncClient` for async endpoints
2. Mock database dependencies with test fixtures
3. Test error cases (404, 403, 429, validation errors)
4. Verify cascade deletes for cameras
5. Test path traversal prevention for media endpoints
6. Verify health check logic for degraded states
7. Test WebSocket connection lifecycle
8. Test DLQ operations with mock Redis
9. Test alert rule conditions and schedule evaluation
10. Test zone coordinate validation (0-1 range)
11. Test admin endpoints require DEBUG mode
