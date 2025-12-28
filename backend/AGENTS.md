# Backend Agent Guide

## Purpose

The backend is a FastAPI-based REST API server for an AI-powered home security monitoring system. It orchestrates:

- **Camera management** - Track cameras and their upload directories
- **AI detection pipeline** - File watching, RT-DETRv2 object detection, batch aggregation, Nemotron risk analysis
- **Data persistence** - PostgreSQL database for structured data (cameras, detections, events, GPU stats)
- **Real-time capabilities** - Redis for queues, pub/sub, and caching
- **Media serving** - Secure file serving with path traversal protection
- **System monitoring** - Health checks, GPU stats, and system statistics
- **Observability** - Prometheus metrics, structured logging, dead-letter queues

## Directory Structure

```
backend/
├── main.py                 # FastAPI application entry point
├── core/                   # Infrastructure (database, Redis, config, metrics)
├── api/                    # REST API routes, schemas, and middleware
├── models/                 # SQLAlchemy ORM models
├── services/               # Business logic and AI pipeline
├── tests/                  # Unit and integration tests
└── data/                   # Runtime data (SQLite DB, thumbnails)
```

## Key Files

### Application Entry Point

**`main.py`** - FastAPI application with:

- Lifespan context manager for startup/shutdown
- CORS middleware configuration
- Authentication middleware (optional API key validation)
- Request ID middleware for log correlation
- Health check endpoints (`/`, `/health`)
- Router registration (cameras, detections, dlq, events, logs, media, metrics, system, websocket)
- Database and Redis initialization
- Service initialization (FileWatcher, PipelineWorkerManager, GPUMonitor, CleanupService, SystemBroadcaster)

### Core Infrastructure (`core/`)

**`config.py`** - Pydantic Settings for configuration:

- Environment variable loading from `.env`
- Database URL with PostgreSQL support
- Redis connection URL
- API settings (host, port, CORS)
- File watching settings (Foscam base path)
- Retention and batch processing timings
- AI service endpoints (RT-DETR, Nemotron)
- Detection confidence thresholds
- Fast path settings for high-priority detections
- Cached singleton pattern via `@lru_cache`

**`database.py`** - SQLAlchemy 2.0 async database layer:

- `Base` - Declarative base for all models
- `init_db()` - Initialize engine, create tables, enable SQLite foreign keys
- `close_db()` - Cleanup on shutdown
- `get_db()` - FastAPI dependency for database sessions
- `get_session()` - Async context manager for manual session usage
- `get_engine()` - Access global async engine
- Uses NullPool for SQLite to avoid connection reuse issues
- Auto-commit/rollback on success/error

**`redis.py`** - Redis async client wrapper:

- `RedisClient` class with connection pooling
- Retry logic with exponential backoff (3 retries, 1s base delay)
- Queue operations (RPUSH, BLPOP, LLEN, LRANGE, peek_queue, clear_queue)
- Pub/Sub operations (publish, subscribe, listen)
- Cache operations (get, set, delete, exists)
- JSON serialization/deserialization for all operations
- Health check with server info
- Global singleton instance pattern
- `init_redis()` / `close_redis()` for app lifecycle
- `get_redis()` - FastAPI dependency

**`logging.py`** - Centralized logging infrastructure:

- `setup_logging()` - Initialize console, file, and SQLite handlers
- `get_logger(name)` - Get configured logger instance
- `get_request_id()` / `set_request_id()` - Request ID context propagation
- `ContextFilter` - Adds request_id to log records
- `CustomJsonFormatter` - JSON formatting with structured fields
- `SQLiteHandler` - Custom handler writing logs to database
- Rotating file handler with configurable size and backup count
- Structured logging with camera_id, event_id, detection_id, duration_ms
- Reduces noise from third-party libraries (uvicorn, sqlalchemy, watchdog)

**`metrics.py`** - Prometheus metrics for observability:

- Pipeline stage duration histograms (detect, batch, analyze)
- Queue depth gauges (detection_queue, analysis_queue)
- Error counters by type
- `get_metrics_response()` - Returns metrics in Prometheus exposition format

### Database Models (`models/`)

All models inherit from `Base` (defined in `camera.py`) and use SQLAlchemy 2.0 `Mapped` type hints.

**`camera.py`** - Camera tracking:

- `id` (str, primary key) - Camera UUID
- `name` (str) - Human-readable camera name
- `folder_path` (str) - Filesystem path to camera upload directory
- `status` (str) - "online", "offline", "error"
- `created_at`, `last_seen_at` (datetime)
- Relationships: `detections`, `events` with cascade delete

**`detection.py`** - Object detection results:

- `id` (int, auto-increment)
- `camera_id` (foreign key to cameras)
- `file_path` (str) - Path to original image
- `detected_at` (datetime)
- `object_type` (str) - Class label (person, car, dog, etc.)
- `confidence` (float) - Detection confidence 0.0-1.0
- `bbox_x`, `bbox_y`, `bbox_width`, `bbox_height` (int) - Bounding box coordinates
- `thumbnail_path` (str) - Path to thumbnail with boxes drawn
- Indexes on camera_id, detected_at, and composite (camera_id, detected_at)

**`event.py`** - Security event aggregations:

- `id` (int, auto-increment)
- `batch_id` (str) - UUID linking to detection batch
- `camera_id` (foreign key to cameras)
- `started_at`, `ended_at` (datetime) - Event time window
- `risk_score` (int) - LLM-assigned risk score 0-100
- `risk_level` (str) - "low", "medium", "high", "critical"
- `summary` (text) - Natural language summary from LLM
- `reasoning` (text) - LLM explanation
- `detection_ids` (text) - JSON array of detection IDs
- `reviewed` (bool) - User review flag
- `notes` (text) - User notes
- `is_fast_path` (bool) - Whether event used fast path analysis
- Indexes on camera_id, started_at, risk_score, reviewed, batch_id

**`gpu_stats.py`** - GPU performance metrics:

- `id` (int, auto-increment)
- `recorded_at` (datetime)
- `gpu_utilization` (float) - Percentage 0-100
- `memory_used`, `memory_total` (int) - Bytes
- `temperature` (float) - Celsius
- `inference_fps` (float) - Frames per second
- Index on recorded_at for time-series queries

**`log.py`** - Structured application logs:

- `id` (int, auto-increment)
- `timestamp` (datetime) - Log entry timestamp
- `level` (str) - Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `component` (str) - Logger name (module `__name__`)
- `message` (text) - Formatted log message
- `camera_id`, `event_id`, `detection_id` (nullable) - Structured references
- `request_id` (str, nullable) - Request correlation ID
- `duration_ms` (int, nullable) - Operation duration
- `extra` (JSON, nullable) - Additional structured context
- `source` (str) - "backend" or "frontend"
- `user_agent` (text, nullable) - Browser user agent for frontend logs
- Indexes on timestamp, level, component, camera_id, source

**`api_key.py`** - API key authentication:

- `id` (int, auto-increment)
- `key_hash` (str, unique) - SHA-256 hash of API key
- `name` (str) - Human-readable key name
- `created_at` (datetime)
- `is_active` (bool) - Active status flag

### API Routes (`api/routes/`)

**`cameras.py`** - Camera CRUD operations:

- `GET /api/cameras` - List cameras with optional status filter
- `GET /api/cameras/{camera_id}` - Get single camera
- `POST /api/cameras` - Create camera (auto-generates UUID)
- `PATCH /api/cameras/{camera_id}` - Update camera fields
- `DELETE /api/cameras/{camera_id}` - Delete camera (cascade to detections/events)
- All use async SQLAlchemy sessions via `Depends(get_db)`

**`media.py`** - Secure file serving:

- `GET /api/media/cameras/{camera_id}/{filename:path}` - Serve camera images/videos
- `GET /api/media/thumbnails/{filename}` - Serve detection thumbnails
- Path traversal protection (validates `..` and absolute paths)
- Whitelist file extensions (.jpg, .jpeg, .png, .gif, .mp4, .avi, .webm)
- Resolves and validates paths are within allowed directories
- Returns `FileResponse` with appropriate content-type headers

**`system.py`** - System monitoring:

- `GET /api/system/health` - Comprehensive health check (database, Redis, AI services)
- `GET /api/system/gpu` - Latest GPU statistics
- `GET /api/system/config` - Public configuration settings
- `GET /api/system/stats` - Aggregate counts (cameras, events, detections, uptime)
- `GET /api/system/pipeline` - Pipeline worker status
- Helper functions: `check_database_health()`, `check_redis_health()`, `check_ai_services_health()`

**`detections.py`** - Detection CRUD operations:

- `GET /api/detections` - List detections with pagination and filtering
- `GET /api/detections/{detection_id}` - Get single detection
- Query parameters: camera_id, object_type, min_confidence, limit, offset
- Returns detection data with bounding boxes and thumbnails

**`events.py`** - Event CRUD operations:

- `GET /api/events` - List events with pagination and filtering
- `GET /api/events/{event_id}` - Get single event with full details
- `PATCH /api/events/{event_id}` - Update event (mark reviewed, add notes)
- Query parameters: camera_id, min_risk_score, reviewed, limit, offset
- Returns aggregated event data with risk assessment

**`websocket.py`** - WebSocket real-time connections:

- `WS /api/ws` - WebSocket endpoint for real-time event streaming
- Broadcasts security events to all connected clients
- Integrates with EventBroadcaster service
- Redis pub/sub backbone for multi-instance support
- Automatic connection cleanup on disconnect

**`logs.py`** - Log management API:

- `GET /api/logs` - List logs with filtering and pagination
- `GET /api/logs/stats` - Get log statistics for dashboard
- `GET /api/logs/{log_id}` - Get single log entry by ID
- `POST /api/logs/frontend` - Receive and store frontend logs

**`dlq.py`** - Dead-letter queue management:

- `GET /api/dlq/stats` - Get DLQ statistics (counts for each queue)
- `GET /api/dlq/jobs/{queue_name}` - List jobs in a specific DLQ
- `POST /api/dlq/requeue/{queue_name}` - Requeue oldest job from DLQ
- `POST /api/dlq/requeue-all/{queue_name}` - Requeue all jobs from DLQ
- `DELETE /api/dlq/{queue_name}` - Clear all jobs from a DLQ

**`metrics.py`** - Prometheus metrics endpoint:

- `GET /api/metrics` - Return all metrics in Prometheus exposition format
- No authentication required for Prometheus scraping

### API Middleware (`api/middleware/`)

**`auth.py`** - API key authentication middleware:

- `AuthMiddleware` - Optional API key validation
- Enabled when `api_key_enabled=True` in settings
- Validates API keys against hashed values in database
- Skips authentication for health check endpoints

**`request_id.py`** - Request ID middleware:

- `RequestIDMiddleware` - Generates and propagates request IDs
- Accepts `X-Request-ID` header or generates new UUID (8 chars)
- Sets request ID in context via `set_request_id()`
- Adds `X-Request-ID` to response headers
- Enables log correlation across async operations

### Services (`services/`)

See `services/AGENTS.md` for detailed service documentation.

**Core AI Pipeline:**

- `file_watcher.py` - Monitors camera directories for new uploads
- `detector_client.py` - RT-DETRv2 HTTP client for object detection
- `batch_aggregator.py` - Groups detections into time-based batches
- `nemotron_analyzer.py` - LLM risk analysis via llama.cpp
- `thumbnail_generator.py` - Detection visualization with bounding boxes
- `dedupe.py` - File deduplication using content hashes

**Pipeline Workers:**

- `pipeline_workers.py` - Background worker processes (DetectionQueueWorker, AnalysisQueueWorker, BatchTimeoutWorker, QueueMetricsWorker, PipelineWorkerManager)

**Broadcasting:**

- `event_broadcaster.py` - WebSocket event distribution via Redis pub/sub
- `system_broadcaster.py` - Periodic system status broadcasting

**Background Services:**

- `gpu_monitor.py` - NVIDIA GPU statistics monitoring
- `cleanup_service.py` - Data retention and disk cleanup
- `health_monitor.py` - Service health monitoring with auto-recovery

**Infrastructure:**

- `retry_handler.py` - Exponential backoff and dead-letter queue support
- `service_managers.py` - Strategy pattern for service management (Shell/Docker)
- `prompts.py` - LLM prompt templates

## Configuration Patterns

### Settings Access

```python
from backend.core import get_settings

settings = get_settings()  # Cached singleton
database_url = settings.database_url
redis_url = settings.redis_url
```

### Database Session Usage

**In API routes (dependency injection):**

```python
@router.get("/cameras")
async def list_cameras(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Camera))
    return result.scalars().all()
```

**In services (context manager):**

```python
from backend.core import get_session

async with get_session() as session:
    result = await session.execute(select(Camera))
    cameras = result.scalars().all()
    # Auto-commit on success, rollback on exception
```

### Redis Client Usage

**As dependency:**

```python
async def my_route(redis: RedisClient = Depends(get_redis)):
    await redis.add_to_queue("my_queue", {"data": "value"})
```

**Direct access:**

```python
from backend.core.redis import init_redis

redis = await init_redis()
await redis.publish("events", {"type": "update"})
```

## Async/Await Patterns

All database and Redis operations are **fully async**:

- Database: Uses `sqlalchemy.ext.asyncio` (AsyncEngine, AsyncSession)
- Redis: Uses `redis.asyncio` client
- HTTP clients: Uses `httpx.AsyncClient`
- File watching: Uses `asyncio` for debouncing and task scheduling

**Key async patterns:**

1. **Database queries** - Always await:

   ```python
   result = await db.execute(select(Camera))
   camera = result.scalar_one_or_none()
   await db.commit()
   ```

2. **Redis operations** - Always await:

   ```python
   await redis.add_to_queue("queue", data)
   item = await redis.get_from_queue("queue", timeout=5)
   await redis.publish("channel", message)
   ```

3. **Context managers** - Use `async with`:

   ```python
   async with get_session() as session:
       # ... database operations
   ```

4. **HTTP requests** - Use async client:
   ```python
   async with httpx.AsyncClient() as client:
       response = await client.post(url, json=data)
   ```

## Dependencies and Relationships

### Module Import Graph

```
main.py
  ├── core (config, database, redis, logging, metrics)
  ├── api.routes (cameras, detections, dlq, events, logs, media, metrics, system, websocket)
  ├── api.middleware (auth, request_id)
  ├── models (Camera, Detection, Event, GPUStats, Log, APIKey)
  └── services (FileWatcher, PipelineWorkerManager, GPUMonitor, CleanupService, broadcasters)

api.routes
  ├── core (database, redis, config)
  ├── models (ORM classes)
  ├── api.schemas (Pydantic request/response models)
  └── services (retry_handler for DLQ routes)

services
  ├── core (config, database, redis, logging, metrics)
  ├── models (ORM classes)
  └── other services (for composition)
```

### External Service Dependencies

- **RT-DETRv2** (`rtdetr_url`) - Object detection service
- **Nemotron** (`nemotron_url`) - LLM risk analysis via llama.cpp
- **Redis** (`redis_url`) - Queue and pub/sub infrastructure
- **SQLite** (`database_url`) - Persistent storage

### Data Flow

```
Camera uploads -> FileWatcher -> detection_queue (Redis)
                                      |
                              DetectionQueueWorker
                                      |
                               DetectorClient -> RT-DETRv2
                                      |
                               Detection (DB) -> BatchAggregator
                                      |               |
                         ThumbnailGenerator   analysis_queue (Redis)
                                                      |
                                          AnalysisQueueWorker
                                                      |
                                             NemotronAnalyzer -> Nemotron LLM
                                                      |
                                                 Event (DB)
                                                      |
                                           EventBroadcaster (Redis pub/sub)
                                                      |
                                             WebSocket clients

GPU stats (pynvml) -> GPUMonitor -> GPUStats (DB) -> SystemBroadcaster -> WebSocket
                                        |
                                  In-memory buffer

Scheduled cleanup -> CleanupService -> Delete old records -> Remove files

Backend operations -> get_logger() -> SQLiteHandler -> Log (DB)
                                   -> RotatingFileHandler -> security.log
                                   -> StreamHandler -> console

Frontend logs -> POST /api/logs/frontend -> Log (DB)

Failed jobs -> RetryHandler (with backoff) -> DLQ (Redis) -> /api/dlq/* endpoints
```

## Testing

Test structure mirrors source code:

```
backend/tests/
├── unit/                  # Unit tests for individual modules
│   ├── test_config.py
│   ├── test_database.py
│   ├── test_redis.py
│   └── test_models.py
└── integration/           # Integration tests for API endpoints
```

Run tests with `pytest`:

```bash
pytest backend/tests/ -v
```

## Environment Variables

Key environment variables (loaded via `.env` file):

```bash
# Database and Redis
DATABASE_URL=sqlite+aiosqlite:///./data/security.db
REDIS_URL=redis://localhost:6379/0

# Camera configuration
FOSCAM_BASE_PATH=/export/foscam

# AI service endpoints
RTDETR_URL=http://localhost:8090
NEMOTRON_URL=http://localhost:8091

# Detection settings
DETECTION_CONFIDENCE_THRESHOLD=0.5

# Fast path settings
FAST_PATH_CONFIDENCE_THRESHOLD=0.90
FAST_PATH_OBJECT_TYPES=["person"]

# Batch processing
BATCH_WINDOW_SECONDS=90
BATCH_IDLE_TIMEOUT_SECONDS=30

# Data retention
RETENTION_DAYS=30

# GPU monitoring
GPU_POLL_INTERVAL_SECONDS=5.0
GPU_STATS_HISTORY_MINUTES=60

# Authentication (optional)
API_KEY_ENABLED=false
API_KEYS=[]

# Logging
LOG_LEVEL=INFO
LOG_FILE_PATH=data/logs/security.log
LOG_FILE_MAX_BYTES=10485760
LOG_FILE_BACKUP_COUNT=7
LOG_DB_ENABLED=true
LOG_DB_MIN_LEVEL=DEBUG
LOG_RETENTION_DAYS=7

# Development
DEBUG=false
```

## Common Patterns

### Error Handling

Services use comprehensive error handling with logging:

```python
try:
    # Operation
    result = await some_operation()
except SpecificError as e:
    logger.error(f"Specific error: {e}", exc_info=True)
    # Handle or raise
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    # Handle gracefully
```

### Logging

All modules use the centralized logging infrastructure from `backend/core/logging.py`:

```python
from backend.core import get_logger

logger = get_logger(__name__)
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message", exc_info=True)

# With structured context for database logging
logger.info("Detection processed", extra={
    "camera_id": "front_door",
    "detection_id": 123,
    "duration_ms": 45
})
```

Logs are written to:

1. Console (stdout) - Plain text for development
2. Rotating file (`data/logs/security.log`) - Plain text for grep/tail
3. SQLite database (`logs` table) - Structured logs for admin UI queries

### Type Hints

Full type hints using modern Python syntax:

```python
from collections.abc import AsyncGenerator

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    ...

def process_data(items: list[dict[str, Any]]) -> int:
    ...
```

## Deployment Notes

- **Hybrid deployment**: Backend runs in Docker, AI models run natively for GPU access
- **Database**: SQLite with foreign keys enabled, NullPool for async compatibility
- **Redis**: Optional (system continues without it, some features unavailable)
- **GPU**: NVIDIA RTX A5500 (24GB) for RT-DETRv2 and Nemotron models
- **File storage**: Foscam cameras upload to `/export/foscam/{camera_name}/`
- **Retention**: 30-day automatic cleanup (configurable)

## Related Documentation

- `/backend/models/AGENTS.md` - Database model documentation
- `/backend/services/AGENTS.md` - Service layer documentation
- `/backend/api/routes/AGENTS.md` - API endpoint documentation
- `/backend/core/AGENTS.md` - Core infrastructure documentation
- `/backend/tests/AGENTS.md` - Test infrastructure documentation
