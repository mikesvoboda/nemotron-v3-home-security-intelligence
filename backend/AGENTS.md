# Backend Agent Guide

## Purpose

The backend is a FastAPI-based REST API server for an AI-powered home security monitoring system. It orchestrates:

- **Camera management** - Track cameras and their upload directories
- **AI detection pipeline** - File watching, RT-DETRv2 object detection, batch aggregation, Nemotron risk analysis
- **Data persistence** - PostgreSQL database for structured data (cameras, detections, events, GPU stats, logs)
- **Real-time capabilities** - Redis for queues, pub/sub, and caching
- **Media serving** - Secure file serving with path traversal protection
- **System monitoring** - Health checks, GPU stats, and system statistics
- **Observability** - Prometheus metrics, structured logging, dead-letter queues

## Directory Structure

```
backend/
├── main.py                 # FastAPI application entry point
├── __init__.py             # Package initialization
├── requirements.txt        # Python dependencies
├── requirements-prod.txt   # Production dependencies
├── Dockerfile              # Development Docker configuration
├── Dockerfile.prod         # Production Docker configuration
├── .dockerignore           # Docker build exclusions
├── api/                    # REST API routes, schemas, and middleware
├── core/                   # Infrastructure (database, Redis, config, logging, metrics)
├── models/                 # SQLAlchemy ORM models
├── services/               # Business logic and AI pipeline
├── tests/                  # Unit and integration tests
├── data/                   # Runtime data (sample images, SQLite DB location)
└── examples/               # Example scripts and configurations
```

## Key Files

### Application Entry Point

**`main.py`** - FastAPI application with:

- Lifespan context manager for startup/shutdown
- CORS middleware configuration
- Authentication middleware (optional API key validation via `AuthMiddleware`)
- Request ID middleware for log correlation (`RequestIDMiddleware`)
- Health check endpoints (`/`, `/health`)
- Router registration for all API modules:
  - `admin` - Admin operations
  - `cameras` - Camera CRUD
  - `detections` - Detection management
  - `dlq` - Dead-letter queue management
  - `events` - Event management
  - `logs` - Log querying and frontend log ingestion
  - `media` - Secure file serving
  - `metrics` - Prometheus metrics endpoint
  - `system` - System health and status
  - `websocket` - Real-time event streaming
- Database and Redis initialization
- Service initialization:
  - `FileWatcher` - Monitors camera directories for new uploads
  - `PipelineWorkerManager` - Detection queue, analysis queue, batch timeout workers
  - `GPUMonitor` - NVIDIA GPU statistics monitoring
  - `CleanupService` - Data retention and disk cleanup
  - `SystemBroadcaster` - Periodic system status broadcasting
  - `EventBroadcaster` - WebSocket event distribution

### Package Configuration

**`__init__.py`** - Simple package docstring for the backend module.

**`requirements.txt`** - Development dependencies including FastAPI, SQLAlchemy, Redis, httpx, Pillow, pynvml, prometheus-client, and testing libraries.

**`requirements-prod.txt`** - Production-optimized dependencies with gunicorn.

## Core Infrastructure (`core/`)

See `core/AGENTS.md` for detailed documentation.

**`config.py`** - Pydantic Settings for configuration:

- Environment variable loading from `.env` and optional `runtime.env`
- Database URL with PostgreSQL support
- Redis connection URL
- API settings (host, port, CORS)
- File watching settings (Foscam base path)
- Retention and batch processing timings
- AI service endpoints (RT-DETR, Nemotron)
- Detection and fast path thresholds
- Logging configuration
- Cached singleton pattern via `@lru_cache`

**`database.py`** - SQLAlchemy 2.0 async database layer:

- `Base` - Declarative base for all models
- `init_db()` / `close_db()` - Lifecycle management
- `get_db()` - FastAPI dependency for database sessions
- `get_session()` - Async context manager for services
- SQLite-specific optimizations (NullPool, WAL mode, foreign keys)

**`redis.py`** - Redis async client wrapper:

- `RedisClient` class with connection pooling
- Queue operations (RPUSH, BLPOP, LLEN, LRANGE, peek_queue, clear_queue)
- Pub/Sub operations (publish, subscribe, listen)
- Cache operations (get, set, delete, exists)
- Retry logic with exponential backoff

**`logging.py`** - Centralized logging infrastructure:

- Console, file, and SQLite handlers
- Request ID context propagation
- Structured logging with camera_id, event_id, detection_id, duration_ms
- Error message sanitization (`sanitize_error`)

**`metrics.py`** - Prometheus metrics:

- Queue depth gauges
- Stage duration histograms
- Event/detection counters
- AI request duration tracking
- Error counters by type

## Database Models (`models/`)

See `models/AGENTS.md` for detailed documentation.

All models use SQLAlchemy 2.0 `Mapped` type hints:

- **`Camera`** - Camera entity with detections/events relationships
- **`Detection`** - Object detection results with bounding boxes and video metadata
- **`Event`** - Security events with LLM risk analysis
- **`GPUStats`** - GPU performance time-series data
- **`Log`** - Structured application logs
- **`APIKey`** - API key authentication records

## API Routes (`api/routes/`)

See `api/routes/AGENTS.md` for detailed documentation.

- **`cameras.py`** - Camera CRUD operations
- **`detections.py`** - Detection queries with filtering
- **`events.py`** - Event management and review workflow
- **`media.py`** - Secure file serving for images/videos
- **`system.py`** - Health checks, GPU stats, pipeline status
- **`websocket.py`** - WebSocket real-time connections
- **`logs.py`** - Log queries and frontend log ingestion
- **`dlq.py`** - Dead-letter queue management
- **`metrics.py`** - Prometheus metrics endpoint
- **`admin.py`** - Admin operations

## Services (`services/`)

See `services/AGENTS.md` for detailed documentation.

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

## Data Flow

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

Scheduled cleanup -> CleanupService -> Delete old records -> Remove files

Backend operations -> get_logger() -> SQLiteHandler -> Log (DB)
                                   -> RotatingFileHandler -> security.log
                                   -> StreamHandler -> console

Frontend logs -> POST /api/logs/frontend -> Log (DB)

Failed jobs -> RetryHandler (with backoff) -> DLQ (Redis) -> /api/dlq/* endpoints
```

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
FAST_PATH_CONFIDENCE_THRESHOLD=0.90
FAST_PATH_OBJECT_TYPES=["person"]

# Batch processing
BATCH_WINDOW_SECONDS=90
BATCH_IDLE_TIMEOUT_SECONDS=30

# Data retention
RETENTION_DAYS=30

# Authentication (optional)
API_KEY_ENABLED=false

# Logging
LOG_LEVEL=INFO
LOG_DB_ENABLED=true
```

## Related Documentation

- `/backend/core/AGENTS.md` - Core infrastructure documentation
- `/backend/models/AGENTS.md` - Database model documentation
- `/backend/services/AGENTS.md` - Service layer documentation
- `/backend/api/routes/AGENTS.md` - API endpoint documentation
- `/backend/tests/AGENTS.md` - Test infrastructure documentation
- `/backend/data/AGENTS.md` - Runtime data directory documentation
