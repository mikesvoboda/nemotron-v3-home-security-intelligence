# Backend Core Infrastructure Guide

## Purpose

The `backend/core/` directory contains the foundational infrastructure components for the home security intelligence system:

- **Configuration management** - Environment-based settings with Pydantic validation
- **Database layer** - SQLAlchemy 2.0 async engine and session management
- **Redis client** - Async Redis wrapper for queues, pub/sub, and caching
- **Logging infrastructure** - Centralized structured logging with console, file, and SQLite handlers
- **Prometheus metrics** - Observability metrics for pipeline monitoring

These components are designed as singletons and provide dependency injection patterns for FastAPI routes and services.

## Files Overview

```
backend/core/
├── __init__.py           # Public API exports
├── config.py             # Pydantic Settings configuration
├── database.py           # SQLAlchemy async database layer
├── logging.py            # Centralized logging configuration
├── metrics.py            # Prometheus metrics definitions
├── redis.py              # Redis async client wrapper
├── README.md             # General documentation
├── README_REDIS.md       # Detailed Redis documentation
└── REDIS_QUICKSTART.md   # Redis usage quick reference
```

## `__init__.py` - Public Exports

The `__init__.py` file provides a clean public API for the core module:

**Exported from config.py:**

- `Settings` - Pydantic settings class
- `get_settings()` - Get cached settings instance

**Exported from database.py:**

- `Base` - SQLAlchemy declarative base
- `init_db()` - Initialize database engine and create tables
- `close_db()` - Cleanup database connections
- `get_db()` - FastAPI dependency for database sessions
- `get_session()` - Context manager for manual session usage
- `get_engine()` - Access global async engine
- `get_session_factory()` - Access session factory

**Exported from redis.py:**

- `RedisClient` - Redis client wrapper class
- `init_redis()` - Initialize Redis connection
- `close_redis()` - Cleanup Redis connection
- `get_redis()` - FastAPI dependency for Redis client

**Exported from logging.py:**

- `get_logger()` - Get a configured logger instance
- `get_request_id()` - Get current request ID from context
- `set_request_id()` - Set request ID in context
- `setup_logging()` - Initialize application-wide logging
- `sanitize_error()` - Sanitize error messages for logging

**Exported from metrics.py:**

- `get_metrics_response()` - Generate Prometheus metrics response
- `observe_stage_duration()` - Record pipeline stage duration
- `observe_ai_request_duration()` - Record AI service request duration
- `record_detection_processed()` - Increment detection counter
- `record_event_created()` - Increment event counter
- `record_pipeline_error()` - Increment error counter
- `set_queue_depth()` - Update queue depth gauge

**Usage:**

```python
from backend.core import get_settings, init_db, get_redis, get_logger, setup_logging
```

## `config.py` - Configuration Management

### Purpose

Manages all application configuration using Pydantic Settings with environment variable loading.

### Key Classes

**`Settings`** - Main configuration class (Pydantic BaseSettings):

**Database Configuration:**

- `database_url: str` - SQLAlchemy URL (default: `sqlite+aiosqlite:///./data/security.db`)
- Auto-creates data directory for SQLite files

**Redis Configuration:**

- `redis_url: str` - Redis connection URL (default: `redis://localhost:6379/0`)
- `redis_event_channel: str` - Pub/sub channel for events (default: `security_events`)

**Application Settings:**

- `app_name: str` - Application name
- `app_version: str` - Version string
- `debug: bool` - Debug mode flag (default: False)

**API Settings:**

- `api_host: str` - Host to bind to (default: `0.0.0.0`)
- `api_port: int` - Port to listen on (default: 8000)
- `cors_origins: list[str]` - Allowed CORS origins

**File Watching Settings:**

- `foscam_base_path: str` - Base path for camera uploads (default: `/export/foscam`)

**Retention Settings:**

- `retention_days: int` - Days to retain events/detections (default: 30)

**Batch Processing Settings:**

- `batch_window_seconds: int` - Time window for batching detections (default: 90)
- `batch_idle_timeout_seconds: int` - Idle timeout before processing batch (default: 30)

**AI Service Endpoints:**

- `rtdetr_url: str` - RT-DETRv2 detection service URL (default: `http://localhost:8090`)
- `nemotron_url: str` - Nemotron reasoning service URL (default: `http://localhost:8091`)

**Detection Settings:**

- `detection_confidence_threshold: float` - Minimum confidence (default: 0.5, range: 0.0-1.0)

**Fast Path Settings:**

- `fast_path_confidence_threshold: float` - High-priority threshold (default: 0.90)
- `fast_path_object_types: list[str]` - Object types for fast path (default: `["person"]`)

**GPU Monitoring Settings:**

- `gpu_poll_interval_seconds: float` - GPU stats polling interval (default: 5.0)
- `gpu_stats_history_minutes: int` - GPU stats history retention (default: 60)

**Authentication Settings:**

- `api_key_enabled: bool` - Enable API key authentication (default: False)
- `api_keys: list[str]` - List of valid API keys

**File Deduplication Settings:**

- `dedupe_ttl_seconds: int` - TTL for dedupe entries (default: 300)

**Logging Settings:**

- `log_level: str` - Logging level (default: INFO)
- `log_file_path: str` - Path for rotating log file
- `log_file_max_bytes: int` - Maximum log file size (default: 10MB)
- `log_file_backup_count: int` - Number of backup files (default: 7)
- `log_db_enabled: bool` - Enable SQLite logging (default: True)
- `log_db_min_level: str` - Minimum level for DB logging (default: DEBUG)
- `log_retention_days: int` - Log retention days (default: 7)

**DLQ Settings:**

- `max_requeue_iterations: int` - Max iterations for requeue-all (default: 10000)

### Configuration Loading

Settings are loaded from:

1. Environment variables (case-insensitive)
2. `.env` file in project root
3. Optional `runtime.env` file (controlled by `HSI_RUNTIME_ENV_PATH`)
4. Default values

### Singleton Pattern

```python
@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    runtime_env_path = os.getenv("HSI_RUNTIME_ENV_PATH", "./data/runtime.env")
    return Settings(_env_file=(".env", runtime_env_path))
```

## `database.py` - SQLAlchemy Async Layer

### Purpose

Provides async database connectivity using SQLAlchemy 2.0 with:

- Async engine creation and pooling
- Session factory for creating async sessions
- FastAPI dependency injection
- Context manager patterns
- SQLite-specific optimizations

### Key Components

**`Base`** - Declarative base class for ORM models.

**Global State:**

```python
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None
```

### Functions

**`init_db() -> None`** - Initialize database:

1. Gets settings via `get_settings()`
2. Creates async engine with SQLite-specific configuration
3. Enables SQLite pragmas via event listener:
   - `foreign_keys=ON` - Enable foreign key constraints
   - `journal_mode=WAL` - Write-ahead logging for concurrency
   - `busy_timeout=30000` - 30 second timeout
   - `synchronous=NORMAL` - Balance safety/speed
4. Creates async session factory
5. Creates all tables via `Base.metadata.create_all()`

**`close_db() -> None`** - Cleanup database connections.

**`get_engine() -> AsyncEngine`** - Access global engine.

**`get_session_factory() -> async_sessionmaker[AsyncSession]`** - Access session factory.

**`get_session() -> AsyncGenerator[AsyncSession, None]`** - Context manager for services:

```python
async with get_session() as session:
    result = await session.execute(select(Camera))
    # Auto-commit on success, rollback on exception
```

**`get_db() -> AsyncGenerator[AsyncSession, None]`** - FastAPI dependency:

```python
@router.get("/cameras")
async def list_cameras(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Camera))
    return result.scalars().all()
```

### SQLite-Specific Optimizations

- Uses `NullPool` for SQLite to avoid connection reuse issues
- Enables WAL journal mode for better concurrent access
- Sets busy timeout to 30 seconds
- Uses `check_same_thread=False` for async compatibility

## `redis.py` - Redis Async Client

### Purpose

Provides async Redis connectivity with:

- Connection pooling and retry logic
- Queue operations (FIFO lists)
- Pub/Sub messaging
- Cache operations
- JSON serialization/deserialization
- Health monitoring

### Key Class: `RedisClient`

**Initialization:**

```python
client = RedisClient(redis_url="redis://localhost:6379/0")
await client.connect()
```

**Connection pooling:**

- Max 10 connections
- UTF-8 encoding with `decode_responses=True`
- 5-second connection timeout
- Keep-alive enabled
- 30-second health check interval

**Retry logic:**

- 3 connection attempts
- Exponential backoff with jitter
- Configurable base delay (1s) and max delay (30s)

### Queue Operations

**`add_to_queue(queue_name, data, max_size=10000)`** - RPUSH with automatic trimming
**`get_from_queue(queue_name, timeout=0)`** - BLPOP (blocking pop)
**`get_queue_length(queue_name)`** - LLEN
**`peek_queue(queue_name, start=0, end=100, max_items=1000)`** - LRANGE
**`clear_queue(queue_name)`** - DELETE

### Pub/Sub Operations

**`publish(channel, message)`** - Publish with JSON serialization
**`subscribe(*channels)`** - Subscribe to channels
**`unsubscribe(*channels)`** - Unsubscribe from channels
**`listen(pubsub)`** - Async generator for messages

### Cache Operations

**`get(key)`** - GET with JSON deserialization
**`set(key, value, expire=None)`** - SET with optional TTL
**`delete(*keys)`** - DEL
**`exists(*keys)`** - EXISTS

### Health Check

**`health_check()`** - Returns status dict with connected state and Redis version.

### Global Singleton Pattern

```python
async def init_redis() -> RedisClient:
    """Initialize Redis for app startup."""

async def close_redis() -> None:
    """Close Redis for app shutdown."""

async def get_redis() -> AsyncGenerator[RedisClient, None]:
    """FastAPI dependency for Redis."""
```

## `logging.py` - Centralized Logging

### Purpose

Provides unified logging infrastructure with multiple outputs:

- Console handler with plain text format for development
- File handler with rotating logs for production grep/tail
- SQLite handler for admin UI queries and structured log storage

### Key Components

**Context Variables:**

- `_request_id: ContextVar[str | None]` - Thread-safe request ID propagation
- `get_request_id()` - Retrieve current request ID
- `set_request_id()` - Set request ID (used by RequestIDMiddleware)

**Classes:**

**`ContextFilter`** - Adds contextual information to log records (request_id).

**`CustomJsonFormatter`** - JSON formatter with ISO timestamp and structured fields.

**`SQLiteHandler`** - Custom handler writing logs to database:

- Uses synchronous database sessions
- Extracts structured metadata (camera_id, event_id, detection_id, duration_ms)
- Falls back gracefully if database is unavailable

### Functions

**`setup_logging()`** - Initialize application-wide logging:

1. Gets log level from settings
2. Clears existing handlers on root logger
3. Adds ContextFilter for request ID propagation
4. Creates console handler with plain text format
5. Creates rotating file handler
6. Creates SQLite handler (if enabled)
7. Reduces noise from third-party libraries

**`get_logger(name: str)`** - Get a configured logger:

```python
from backend.core import get_logger

logger = get_logger(__name__)
logger.info("Detection processed", extra={
    "camera_id": "front_door",
    "detection_id": 123,
    "duration_ms": 45
})
```

**`sanitize_error(error, max_length=500)`** - Sanitize error messages:

- Removes credential patterns (password, secret, token, api_key, Bearer)
- Simplifies file paths to just filenames
- Truncates long messages

## `metrics.py` - Prometheus Metrics

### Purpose

Defines Prometheus metrics for observability:

### Metrics Defined

**Queue Depth Gauges:**

- `hsi_detection_queue_depth` - Images waiting in detection queue
- `hsi_analysis_queue_depth` - Batches waiting in analysis queue

**Stage Duration Histograms:**

- `hsi_stage_duration_seconds` - Duration by stage (detect, batch, analyze)

**Counters:**

- `hsi_events_created_total` - Total security events created
- `hsi_detections_processed_total` - Total detections processed
- `hsi_pipeline_errors_total` - Pipeline errors by type

**AI Request Duration:**

- `hsi_ai_request_duration_seconds` - AI service request duration by service

### Helper Functions

```python
set_queue_depth("detection", 10)
observe_stage_duration("detect", 0.5)
record_event_created()
record_detection_processed(count=5)
observe_ai_request_duration("rtdetr", 0.25)
record_pipeline_error("connection_error")
get_metrics_response()  # Returns Prometheus exposition format
```

## Dependency Injection Patterns

### FastAPI Route Dependencies

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core import get_db, get_redis
from backend.core.redis import RedisClient

router = APIRouter()

@router.get("/example")
async def example_route(
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    # Database operations
    result = await db.execute(select(Camera))
    cameras = result.scalars().all()

    # Redis operations
    await redis.publish("updates", {"type": "example"})

    return {"cameras": len(cameras)}
```

### Service Dependencies

Services can use context managers directly:

```python
from backend.core import get_session, init_redis

async def my_background_task():
    # Database
    async with get_session() as session:
        result = await session.execute(select(Event))
        events = result.scalars().all()

    # Redis
    redis = await init_redis()
    await redis.publish("channel", {"events": len(events)})
```

## Testing

Core modules have comprehensive unit tests in `backend/tests/unit/`:

- `test_config.py` - Settings loading and validation
- `test_database.py` - Database initialization, sessions, transactions
- `test_redis.py` - Redis operations, serialization, error handling
- `test_logging.py` - Logging setup, handlers, context propagation

Run with:

```bash
pytest backend/tests/unit/ -v
```

## Related Documentation

- `/backend/AGENTS.md` - Backend architecture overview
- `/backend/models/AGENTS.md` - Database model documentation
- `/backend/services/AGENTS.md` - Service layer documentation
