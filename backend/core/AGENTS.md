# Backend Core Infrastructure Guide

## Purpose

The `backend/core/` directory contains the foundational infrastructure components for the home security intelligence system:

- **Configuration management** - Environment-based settings with Pydantic validation
- **Database layer** - SQLAlchemy 2.0 async engine with PostgreSQL and session management
- **Redis client** - Async Redis wrapper for queues, pub/sub, and caching with backpressure
- **Logging infrastructure** - Centralized structured logging with console, file, and database handlers
- **Prometheus metrics** - Observability metrics for pipeline monitoring with latency tracking
- **TLS/SSL** - Certificate management and HTTPS configuration
- **MIME type utilities** - Media file type detection and normalization

These components are designed as singletons and provide dependency injection patterns for FastAPI routes and services.

## Files Overview

```
backend/core/
├── __init__.py           # Public API exports (comprehensive re-exports)
├── config.py             # Pydantic Settings configuration
├── constants.py          # Application-wide constants (queue names, DLQ names, prefixes)
├── database.py           # SQLAlchemy async database layer
├── logging.py            # Centralized logging configuration
├── metrics.py            # Prometheus metrics definitions
├── mime_types.py         # MIME type utilities for media files
├── redis.py              # Redis async client with backpressure
├── tls.py                # TLS/SSL certificate management
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
- `QueueAddResult` - Result enum for queue operations (SUCCESS, REJECTED, SENT_TO_DLQ)
- `init_redis()` - Initialize Redis connection
- `close_redis()` - Cleanup Redis connection
- `get_redis()` - FastAPI dependency for Redis client
- `get_redis_optional()` - FastAPI dependency returning None if unavailable

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

**Exported from mime_types.py:**

- `get_mime_type()` - Get MIME type from file path
- `get_mime_type_with_default()` - Get MIME type with fallback
- `is_image_mime_type()` / `is_video_mime_type()` - Type checking
- `is_supported_mime_type()` - Check if MIME type is supported (image or video)
- `normalize_file_type()` - Normalize extension or MIME type
- `EXTENSION_TO_MIME` - Extension to MIME type mapping dict
- `DEFAULT_IMAGE_MIME` / `DEFAULT_VIDEO_MIME` - Default MIME type constants

**Exported from tls.py:**

- `TLSConfig` / `TLSMode` - Configuration dataclass and mode enum
- `TLSError`, `TLSConfigurationError`, `CertificateNotFoundError`, `CertificateValidationError` - Exception hierarchy
- `create_ssl_context()` - Create SSL context for server
- `generate_self_signed_cert()` / `generate_self_signed_certificate()` - Generate self-signed certificates
- `get_tls_config()` / `is_tls_enabled()` - Configuration helpers
- `validate_certificate()` / `validate_certificate_files()` / `get_cert_info()` - Certificate inspection
- `load_certificate_paths()` - Load cert/key paths from settings

**Usage:**

```python
from backend.core import get_settings, init_db, get_redis, get_logger, setup_logging
from backend.core import TLSConfig, TLSMode, create_ssl_context
from backend.core import get_mime_type, is_video_mime_type
```

## `constants.py` - Application Constants

### Purpose

Provides centralized constants for Redis queue names and DLQ (dead-letter queue) naming.

### Constants

**Queue Names:**

- `DETECTION_QUEUE = "detection_queue"` - Queue for incoming detection jobs
- `ANALYSIS_QUEUE = "analysis_queue"` - Queue for batched detections ready for LLM analysis

**DLQ Names:**

- `DLQ_PREFIX = "dlq:"` - Prefix for all dead-letter queues
- `DLQ_DETECTION_QUEUE = "dlq:detection_queue"` - DLQ for failed detection jobs
- `DLQ_ANALYSIS_QUEUE = "dlq:analysis_queue"` - DLQ for failed LLM analysis jobs
- `DLQ_OVERFLOW_PREFIX = "dlq:overflow:"` - Prefix for overflow DLQ queues

### Helper Functions

- `get_dlq_name(queue_name)` - Get the DLQ name for a given queue
- `get_dlq_overflow_name(queue_name)` - Get the overflow DLQ name for a given queue

**Usage:**

```python
from backend.core.constants import (
    DETECTION_QUEUE,
    ANALYSIS_QUEUE,
    DLQ_DETECTION_QUEUE,
    get_dlq_name,
)

# Queue operations (use add_to_queue_safe for proper backpressure handling)
result = await redis.add_to_queue_safe(DETECTION_QUEUE, data)
dlq_name = get_dlq_name("detection_queue")  # Returns "dlq:detection_queue"
```

## `config.py` - Configuration Management

### Purpose

Manages all application configuration using Pydantic Settings with environment variable loading.

### Key Classes

**`Settings`** - Main configuration class (Pydantic BaseSettings):

**Database Configuration:**

- `database_url: str` - SQLAlchemy URL (required, no default - must be set)
- Must use `postgresql+asyncpg://` scheme for async PostgreSQL driver
- Example: `DATABASE_URL=postgresql+asyncpg://security:password@localhost:5432/security`

**Redis Configuration:**

- `redis_url: str` - Redis connection URL (default: `redis://localhost:6379/0`)
- `redis_event_channel: str` - Pub/sub channel for events (default: `security_events`)

**Application Settings:**

- `app_name: str` - Application name (default: "Home Security Intelligence")
- `app_version: str` - Version string (default: "0.1.0")
- `debug: bool` - Debug mode flag (default: False)
- `admin_enabled: bool` - Enable admin endpoints (requires debug=True also)
- `admin_api_key: str | None` - Optional API key for admin endpoints

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

**AI Service Timeout Settings:**

- `ai_connect_timeout: float` - Connection timeout (default: 10.0s, range: 1-60)
- `ai_health_timeout: float` - Health check timeout (default: 5.0s, range: 1-30)
- `rtdetr_read_timeout: float` - RT-DETR response timeout (default: 60.0s, range: 10-300)
- `nemotron_read_timeout: float` - Nemotron response timeout (default: 120.0s, range: 30-600)

**Detection Settings:**

- `detection_confidence_threshold: float` - Minimum confidence (default: 0.5, range: 0.0-1.0)

**Fast Path Settings:**

- `fast_path_confidence_threshold: float` - High-priority threshold (default: 0.90)
- `fast_path_object_types: list[str]` - Object types for fast path (default: `["person"]`)

**GPU Monitoring Settings:**

- `gpu_poll_interval_seconds: float` - GPU stats polling interval (default: 5.0)
- `gpu_stats_history_minutes: int` - GPU stats history retention (default: 60)

**Queue Backpressure Settings:**

- `queue_max_size: int` - Maximum queue size (default: 10000)
- `queue_overflow_policy: str` - Policy when full: 'drop_oldest', 'reject', 'dlq'
- `queue_backpressure_threshold: float` - Fill ratio for warnings (default: 0.8)

**Rate Limiting Settings:**

- `rate_limit_enabled: bool` - Enable rate limiting (default: True)
- `rate_limit_requests_per_minute: int` - General limit (default: 60)
- `rate_limit_burst: int` - Burst allowance (default: 10)
- `rate_limit_media_requests_per_minute: int` - Media endpoint limit (default: 120)
- `rate_limit_websocket_connections_per_minute: int` - WebSocket limit (default: 10)
- `rate_limit_search_requests_per_minute: int` - Search endpoint limit (default: 30)

**WebSocket Settings:**

- `websocket_idle_timeout_seconds: int` - Idle timeout (default: 300s)
- `websocket_ping_interval_seconds: int` - Ping interval (default: 30s)
- `websocket_max_message_size: int` - Max message size (default: 64KB)

**Severity Threshold Settings:**

- `severity_low_max: int` - Max risk score for LOW severity (default: 29)
- `severity_medium_max: int` - Max risk score for MEDIUM (default: 59)
- `severity_high_max: int` - Max risk score for HIGH (default: 84)

**Authentication Settings:**

- `api_key_enabled: bool` - Enable API key authentication (default: False)
- `api_keys: list[str]` - List of valid API keys

**TLS/HTTPS Settings:**

- `tls_mode: str` - TLS mode: 'disabled', 'self_signed', 'provided'
- `tls_cert_path: str` - Path to certificate file
- `tls_key_path: str` - Path to private key file
- `tls_ca_path: str` - Optional CA certificate for client verification
- `tls_verify_client: bool` - Require client certificates (mTLS)
- `tls_min_version: str` - Minimum TLS version ('TLSv1.2' or 'TLSv1.3')

**Notification Settings:**

- `notification_enabled: bool` - Enable notification delivery (default: True)
- `smtp_host/port/user/password` - SMTP email configuration
- `smtp_from_address: str` - Email sender address
- `smtp_use_tls: bool` - Use TLS for SMTP (default: True)
- `default_webhook_url: str | None` - Default webhook URL for alerts
- `webhook_timeout_seconds: int` - Webhook request timeout (default: 30)
- `default_email_recipients: list[str]` - Default email recipients

**Clip Generation Settings:**

- `clips_directory: str` - Directory for event clips (default: "data/clips")
- `clip_pre_roll_seconds: int` - Pre-event time in clips (default: 5)
- `clip_post_roll_seconds: int` - Post-event time in clips (default: 5)
- `clip_generation_enabled: bool` - Enable clip generation (default: True)

**Video Processing Settings:**

- `video_frame_interval_seconds: float` - Frame extraction interval (default: 2.0)
- `video_thumbnails_dir: str` - Thumbnail directory (default: "data/thumbnails")
- `video_max_frames: int` - Max frames per video (default: 30)

**File Deduplication Settings:**

- `dedupe_ttl_seconds: int` - TTL for dedupe entries (default: 300)

**Logging Settings:**

- `log_level: str` - Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
- `log_file_path: str` - Path for rotating log file (default: `data/logs/security.log`)
- `log_file_max_bytes: int` - Maximum size of each log file (default: 10MB)
- `log_file_backup_count: int` - Number of backup log files to keep (default: 7)
- `log_db_enabled: bool` - Enable writing logs to PostgreSQL database (default: True)
- `log_db_min_level: str` - Minimum log level to write to database (default: DEBUG)
- `log_retention_days: int` - Number of days to retain logs (default: 7)

**DLQ Settings:**

- `max_requeue_iterations: int` - Max iterations for requeue-all (default: 10000)

### Configuration Loading

Settings are loaded from:

1. Environment variables (case-insensitive)
2. `.env` file in project root
3. Optional `runtime.env` file (controlled by `HSI_RUNTIME_ENV_PATH`)
4. Default values

**Model Config:**

```python
model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    case_sensitive=False,
    extra="ignore",
)
```

### Field Validators

**`validate_database_url`** - Validates database URL format:

- Ensures PostgreSQL URL is properly formatted
- Validates connection string components (user, host, port, database)
- No directory creation needed (PostgreSQL is external service)

**`validate_log_file_path`** - Ensures log directory exists:

- Creates parent directory for log files if it doesn't exist

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
- PostgreSQL connection pooling

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
2. Creates async engine with appropriate configuration:
   - PostgreSQL: Uses standard connection pool with asyncpg driver
   - Enables debug logging if `settings.debug=True`
   - Configures connection pool settings (pool size, timeout)
3. Enables foreign key constraints (native PostgreSQL support)
4. Creates async session factory with:
   - `expire_on_commit=False` - Keep objects usable after commit
   - `autocommit=False` - Manual transaction control
   - `autoflush=False` - Explicit flush control
5. Imports all models to register with metadata
6. Creates all tables via `Base.metadata.create_all()`

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

### PostgreSQL Connection Pooling

The database module is configured for PostgreSQL with asyncpg:

- Pool size: 10 base connections
- Max overflow: 20 additional connections
- Pool timeout: 30 seconds
- Connection recycling: 1800 seconds (30 minutes)
- Pre-ping: Enabled for connection validation

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

**With backpressure handling:**

- `add_to_queue_safe(queue_name, data, max_size, overflow_policy, dlq_name)` - Returns `QueueAddResult`
  - `QueueOverflowPolicy.REJECT` - Returns error, item NOT added
  - `QueueOverflowPolicy.DLQ` - Moves oldest to dead-letter queue
  - `QueueOverflowPolicy.DROP_OLDEST` - Trims with explicit warning
- `get_queue_pressure(queue_name, max_size)` - Returns `QueuePressureMetrics`

**Standard operations:**

- `get_from_queue(queue_name, timeout=0)` - BLPOP (blocking pop)
- `get_queue_length(queue_name)` - LLEN
- `peek_queue(queue_name, start=0, end=100, max_items=1000)` - LRANGE
- `clear_queue(queue_name)` - DELETE

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
- Database handler for admin UI queries and structured log storage

### Key Components

**Context Variables:**

- `_request_id: ContextVar[str | None]` - Thread-safe request ID propagation
- `get_request_id()` - Retrieve current request ID
- `set_request_id()` - Set request ID (used by RequestIDMiddleware)

**Classes:**

**`ContextFilter`** - Adds contextual information to log records (request_id).

**`CustomJsonFormatter`** - JSON formatter with ISO timestamp and structured fields.

**`DatabaseHandler`** - Custom handler writing logs to database:

- Uses synchronous database sessions
- Extracts structured metadata (camera_id, event_id, detection_id, duration_ms)
- Falls back gracefully if database is unavailable

### Functions

**`setup_logging()`** - Initialize application-wide logging:

1. Gets log level from settings
2. Clears existing handlers on root logger
3. Adds ContextFilter for request ID propagation
4. Creates console handler with plain text format
5. Creates rotating file handler (if path is accessible)
6. Creates database handler (if `log_db_enabled=True`)
7. Reduces noise from third-party libraries (uvicorn, sqlalchemy, watchdog)

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

### Pipeline Latency Tracker

`PipelineLatencyTracker` provides in-memory latency tracking with percentile calculations:

```python
from backend.core.metrics import get_pipeline_latency_tracker, record_pipeline_stage_latency

# Record latency
record_pipeline_stage_latency("watch_to_detect", 150.5)

# Get statistics
tracker = get_pipeline_latency_tracker()
stats = tracker.get_stage_stats("watch_to_detect", window_minutes=5)
# Returns: {avg_ms, min_ms, max_ms, p50_ms, p95_ms, p99_ms, sample_count}

summary = tracker.get_pipeline_summary()
# Returns stats for all stages: watch_to_detect, detect_to_batch, batch_to_analyze, total_pipeline
```

## `mime_types.py` - MIME Type Utilities

### Purpose

Provides centralized MIME type handling for media files:

### Key Constants

- `IMAGE_MIME_TYPES` - Mapping for .jpg, .jpeg, .png
- `VIDEO_MIME_TYPES` - Mapping for .mp4, .mkv, .avi, .mov
- `EXTENSION_TO_MIME` - Combined extension-to-MIME mapping
- `MIME_TO_EXTENSION` - Reverse MIME-to-extension mapping

### Functions

```python
from backend.core.mime_types import get_mime_type, is_video_mime_type, normalize_file_type

# Get MIME type from path
mime = get_mime_type("/path/to/video.mp4")  # "video/mp4"

# Check type
is_video_mime_type(mime)  # True

# Normalize mixed formats (extension or MIME)
normalize_file_type(".jpg")  # "image/jpeg"
normalize_file_type("image/png")  # "image/png"
```

## `tls.py` - TLS/SSL Configuration

### Purpose

Provides TLS certificate management for HTTPS:

### TLS Modes

```python
from backend.core.tls import TLSMode, TLSConfig

class TLSMode(str, Enum):
    DISABLED = "disabled"      # HTTP only (default)
    SELF_SIGNED = "self_signed"  # Auto-generate certificates
    PROVIDED = "provided"      # Use existing certificate files
```

### Key Functions

**Certificate Generation:**

```python
from backend.core.tls import generate_self_signed_cert

generate_self_signed_cert(
    cert_path=Path("certs/server.crt"),
    key_path=Path("certs/server.key"),
    hostname="localhost",
    san_ips=["192.168.1.100"],
    san_dns=["localhost", "myserver.local"],
    days_valid=365,
)
```

**SSL Context Creation:**

```python
from backend.core.tls import TLSConfig, TLSMode, create_ssl_context

config = TLSConfig(
    mode=TLSMode.PROVIDED,
    cert_path="/path/to/cert.pem",
    key_path="/path/to/key.pem",
    min_version=ssl.TLSVersion.TLSv1_2,
)
ssl_context = create_ssl_context(config)
```

**Certificate Validation:**

```python
from backend.core.tls import validate_certificate, get_cert_info

info = validate_certificate(Path("/path/to/cert.pem"))
# Returns: {valid, subject, issuer, not_before, not_after, serial_number, days_remaining}

# Or use get_cert_info() for currently configured certificate
cert_info = get_cert_info()
```

### Custom Exceptions

- `TLSError` - Base exception for TLS errors
- `TLSConfigurationError` - Invalid or incomplete configuration
- `CertificateNotFoundError` - Certificate file not found
- `CertificateValidationError` - Certificate parsing/validation failed

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
