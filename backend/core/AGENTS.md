# Backend Core Infrastructure Guide

## Purpose

The `backend/core/` directory contains the foundational infrastructure components for the home security intelligence system:

- **Configuration management** - Environment-based settings with validation
- **Database layer** - SQLAlchemy 2.0 async engine and session management
- **Redis client** - Async Redis wrapper for queues, pub/sub, and caching
- **Logging infrastructure** - Centralized structured logging with console, file, and SQLite handlers

These components are designed as singletons and provide dependency injection patterns for FastAPI routes and services.

## Files Overview

```
backend/core/
├── __init__.py       # Public API exports
├── config.py         # Pydantic Settings configuration
├── database.py       # SQLAlchemy async database layer
├── logging.py        # Centralized logging configuration
└── redis.py          # Redis async client wrapper
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

**Application Settings:**

- `app_name: str` - Application name
- `app_version: str` - Version string
- `debug: bool` - Debug mode flag (default: False)

**API Settings:**

- `api_host: str` - Host to bind to (default: `0.0.0.0`)
- `api_port: int` - Port to listen on (default: 8000)
- `cors_origins: list[str]` - Allowed CORS origins (default: localhost:3000 and localhost:5173)

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

- `fast_path_confidence_threshold: float` - Confidence threshold for fast path high-priority analysis (default: 0.90, range: 0.0-1.0)
- `fast_path_object_types: list[str]` - Object types that trigger fast path analysis (default: ["person"])

**GPU Monitoring Settings:**

- `gpu_poll_interval_seconds: float` - GPU stats polling interval in seconds (default: 5.0, range: 1.0-60.0)
- `gpu_stats_history_minutes: int` - Minutes of GPU stats history to retain in memory (default: 60, range: 1-1440)

**Authentication Settings:**

- `api_key_enabled: bool` - Enable API key authentication (default: False)
- `api_keys: list[str]` - List of valid API keys (plain text, hashed on startup)

**Logging Settings:**

- `log_level: str` - Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
- `log_file_path: str` - Path for rotating log file (default: `data/logs/security.log`)
- `log_file_max_bytes: int` - Maximum size of each log file (default: 10MB)
- `log_file_backup_count: int` - Number of backup log files to keep (default: 7)
- `log_db_enabled: bool` - Enable writing logs to SQLite database (default: True)
- `log_db_min_level: str` - Minimum log level to write to database (default: DEBUG)
- `log_retention_days: int` - Number of days to retain logs (default: 7)

### Configuration Loading

Settings are loaded from:

1. Environment variables (case-insensitive)
2. `.env` file in project root
3. Default values

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

**`validate_database_url`** - Ensures SQLite data directory exists:

- Extracts path from SQLite URL
- Creates parent directory if it doesn't exist
- Handles both `sqlite:///` and `sqlite://` formats
- Skips validation for in-memory databases (`:memory:`)

**`validate_log_file_path`** - Ensures log directory exists:

- Creates parent directory for log files if it doesn't exist

### Singleton Pattern

```python
@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

The `@lru_cache` decorator ensures only one Settings instance is created per process.

**Usage:**

```python
from backend.core import get_settings

settings = get_settings()
print(f"Database: {settings.database_url}")
print(f"Redis: {settings.redis_url}")
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

**`Base`** - Declarative base class:

```python
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass
```

All ORM models inherit from this base.

**Global State:**

```python
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None
```

Singleton pattern for engine and session factory.

### Functions

**`init_db() -> None`** - Initialize database:

1. Gets settings via `get_settings()`
2. Creates async engine with appropriate configuration:
   - SQLite: Uses `NullPool` to avoid connection reuse issues
   - Sets `check_same_thread=False` for async SQLite
   - Enables debug logging if `settings.debug=True`
3. Enables SQLite foreign keys via event listener
4. Creates async session factory with:
   - `expire_on_commit=False` - Keep objects usable after commit
   - `autocommit=False` - Manual transaction control
   - `autoflush=False` - Explicit flush control
5. Imports all models to register with metadata
6. Creates all tables via `Base.metadata.create_all()`

**Called during:** Application startup (lifespan context manager in main.py)

**`close_db() -> None`** - Cleanup database:

1. Disposes of async engine
2. Clears global state
3. Releases all connections

**Called during:** Application shutdown

**`get_engine() -> AsyncEngine`** - Access global engine:

- Returns the global async engine instance
- Raises `RuntimeError` if database not initialized
- Used when direct engine access is needed (rare)

**`get_session_factory() -> async_sessionmaker[AsyncSession]`** - Access session factory:

- Returns the global session factory
- Raises `RuntimeError` if database not initialized
- Used internally by session creation functions

**`get_session() -> AsyncGenerator[AsyncSession, None]`** - Context manager pattern:

```python
async with get_session() as session:
    result = await session.execute(select(Model))
    models = result.scalars().all()
    # Auto-commit on success, rollback on exception
```

**Features:**

- Async context manager (yields AsyncSession)
- Auto-commit on successful exit
- Auto-rollback on exception
- Proper session cleanup

**Use in:** Services, background tasks, scripts

**`get_db() -> AsyncGenerator[AsyncSession, None]`** - FastAPI dependency:

```python
@router.get("/items")
async def list_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item))
    return result.scalars().all()
```

**Features:**

- Designed for FastAPI dependency injection
- Auto-commit on success, rollback on exception
- Ensures session is closed in finally block

**Use in:** API route handlers

### SQLite-Specific Optimizations

**Foreign Keys:**

```python
@event.listens_for(_engine.sync_engine, "connect")
def enable_foreign_keys(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
```

Enables foreign key constraints for each SQLite connection.

**Connection Pooling:**

- Uses `NullPool` for SQLite to avoid connection reuse issues
- Each query gets a fresh connection
- Prevents "database is locked" errors in async context

### Async Patterns

**Query execution:**

```python
result = await session.execute(select(Camera))
cameras = result.scalars().all()
```

**Adding records:**

```python
camera = Camera(id="cam1", name="Front Door")
session.add(camera)
await session.commit()
await session.refresh(camera)
```

**Updates:**

```python
camera.status = "offline"
await session.commit()
```

**Deletes:**

```python
await session.delete(camera)
await session.commit()
```

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
- Exponential backoff (1s \* attempt number)
- Logs warnings on failure
- Raises exception after all retries exhausted

### Queue Operations

**`add_to_queue(queue_name: str, data: Any) -> int`** - RPUSH:

- Adds item to end of queue (Redis list)
- Auto-serializes data to JSON
- Returns queue length after operation

**`get_from_queue(queue_name: str, timeout: int = 0) -> Any | None`** - BLPOP:

- Blocking pop from front of queue
- `timeout=0` means block indefinitely
- Auto-deserializes JSON response
- Returns None on timeout

**`get_queue_length(queue_name: str) -> int`** - LLEN:

- Returns number of items in queue

**`peek_queue(queue_name: str, start: int = 0, end: int = 100, max_items: int = 1000) -> list[Any]`** - LRANGE:

- View queue items without removing
- Default `end=100` prevents expensive full-queue fetches
- `end=-1` returns all items up to `max_items` cap
- `max_items` provides hard cap on items returned (default 1000)
- Returns list of deserialized items

**`clear_queue(queue_name: str) -> bool`** - DELETE:

- Removes entire queue
- Returns True if queue existed

**Example usage:**

```python
# Producer
await redis.add_to_queue("detection_queue", {
    "camera_id": "cam1",
    "file_path": "/path/to/image.jpg",
    "timestamp": "2025-01-15T10:30:00"
})

# Consumer
while True:
    item = await redis.get_from_queue("detection_queue", timeout=5)
    if item:
        process_detection(item)
```

### Pub/Sub Operations

**`publish(channel: str, message: Any) -> int`** - PUBLISH:

- Broadcasts message to channel subscribers
- Auto-serializes to JSON
- Returns number of subscribers that received message

**`subscribe(*channels: str) -> PubSub`** - SUBSCRIBE:

- Subscribe to one or more channels
- Returns PubSub instance for receiving messages

**`unsubscribe(*channels: str) -> None`** - UNSUBSCRIBE:

- Unsubscribe from channels

**`listen(pubsub: PubSub) -> AsyncGenerator[dict, None]`** - Message iterator:

- Async generator yielding messages
- Auto-deserializes JSON data
- Filters for message type (ignores subscribe confirmations)

**Example usage:**

```python
# Publisher
await redis.publish("events", {
    "type": "event_created",
    "event_id": 123,
    "risk_score": 75
})

# Subscriber
pubsub = await redis.subscribe("events", "alerts")
async for message in redis.listen(pubsub):
    channel = message["channel"]
    data = message["data"]
    handle_message(channel, data)
```

### Cache Operations

**`get(key: str) -> Any | None`** - GET:

- Retrieve value from cache
- Auto-deserializes JSON
- Returns None if key doesn't exist

**`set(key: str, value: Any, expire: int | None = None) -> bool`** - SET:

- Store value in cache
- Auto-serializes to JSON
- Optional expiration time in seconds
- Returns True on success

**`delete(*keys: str) -> int`** - DEL:

- Delete one or more keys
- Returns number of keys deleted

**`exists(*keys: str) -> int`** - EXISTS:

- Check if keys exist
- Returns count of existing keys

**Example usage:**

```python
# Cache camera metadata
await redis.set("camera:cam1:metadata", {
    "name": "Front Door",
    "status": "online"
}, expire=300)

# Retrieve from cache
metadata = await redis.get("camera:cam1:metadata")

# Check existence
if await redis.exists("camera:cam1:metadata"):
    print("Cache hit")
```

### Health Check

**`health_check() -> dict[str, Any]`**:

- Pings Redis server
- Retrieves server info
- Returns health status dictionary:
  ```python
  {
      "status": "healthy",  # or "unhealthy"
      "connected": True,
      "redis_version": "7.0.0"
  }
  ```

### Connection Management

**`connect() -> None`**:

- Establishes connection with retry logic
- Must be called before any operations
- Idempotent (safe to call multiple times)

**`disconnect() -> None`**:

- Closes pub/sub connections
- Closes Redis client
- Disconnects connection pool
- Cleans up resources

### Global Singleton Pattern

```python
_redis_client: RedisClient | None = None

async def init_redis() -> RedisClient:
    """Initialize Redis for app startup."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
        await _redis_client.connect()
    return _redis_client

async def close_redis() -> None:
    """Close Redis for app shutdown."""
    global _redis_client
    if _redis_client:
        await _redis_client.disconnect()
        _redis_client = None

async def get_redis() -> AsyncGenerator[RedisClient, None]:
    """FastAPI dependency for Redis."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
        await _redis_client.connect()
    yield _redis_client
```

**Usage in FastAPI:**

```python
@router.post("/items")
async def create_item(
    item: Item,
    redis: RedisClient = Depends(get_redis)
):
    await redis.add_to_queue("items_queue", item.dict())
    return {"status": "queued"}
```

### Error Handling

All Redis operations handle:

- `ConnectionError` - Network/connection issues
- `TimeoutError` - Operation timeout
- `json.JSONDecodeError` - Invalid JSON (falls back to raw string)

Operations log errors and either:

- Return None/False/0 for failures
- Raise exceptions for critical errors

### JSON Serialization

**Automatic serialization:**

- All queue, pub/sub, and cache operations auto-serialize Python objects to JSON
- Strings are passed through unchanged
- Complex objects (dicts, lists) are converted via `json.dumps()`

**Automatic deserialization:**

- Retrieved values are parsed via `json.loads()`
- Falls back to raw string if JSON parsing fails
- Preserves type information (dict stays dict, list stays list)

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

**`ContextFilter`** - Logging filter that adds contextual information:

- Adds `request_id` to all log records
- Enables log correlation across async operations

**`CustomJsonFormatter`** - JSON formatter with structured fields:

- ISO timestamp in UTC
- Level, component, and message fields
- Request ID when available
- Inherits from `python-json-logger.JsonFormatter`

**`SQLiteHandler`** - Custom handler writing logs to database:

- Uses synchronous database sessions (avoids blocking async context)
- Extracts structured metadata (camera_id, event_id, detection_id, duration_ms)
- Falls back gracefully if database is unavailable
- Creates `Log` model entries in the `logs` table
- Configurable minimum log level

### Functions

**`setup_logging() -> None`** - Initialize application-wide logging:

1. Gets log level from settings
2. Clears existing handlers on root logger
3. Adds ContextFilter for request ID propagation
4. Creates console handler with plain text format
5. Creates rotating file handler (if path is accessible)
6. Creates SQLite handler (if `log_db_enabled=True`)
7. Reduces noise from third-party libraries (uvicorn, sqlalchemy, watchdog)

**Called during:** Application startup in lifespan context manager (before database init)

**`get_logger(name: str) -> logging.Logger`** - Get a configured logger:

```python
from backend.core import get_logger

logger = get_logger(__name__)
logger.info("Operation completed", extra={"camera_id": "front_door"})
```

### Log Record Structure

When writing to SQLite, logs include:

- `timestamp` - UTC datetime
- `level` - Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `component` - Logger name (typically `__name__`)
- `message` - Formatted log message
- `camera_id` - Camera reference (if in extra)
- `event_id` - Event reference (if in extra)
- `request_id` - Request correlation ID (from context)
- `detection_id` - Detection reference (if in extra)
- `duration_ms` - Operation duration (if in extra)
- `extra` - JSON object with additional context
- `source` - Always "backend" for backend logs

### Usage Patterns

**Basic logging:**

```python
from backend.core import get_logger

logger = get_logger(__name__)
logger.info("Processing started")
logger.warning("Slow operation detected")
logger.error("Failed to process", exc_info=True)
```

**Structured logging with context:**

```python
logger.info(
    "Detection processed",
    extra={
        "camera_id": camera_id,
        "detection_id": detection.id,
        "duration_ms": 150
    }
)
```

**Request ID propagation:**

```python
from backend.core import get_request_id

request_id = get_request_id()  # Available in any async context
logger.info(f"Request {request_id}: Processing")
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

Services can inject dependencies via constructor:

```python
class MyService:
    def __init__(self, redis_client: RedisClient | None = None):
        self._redis = redis_client

    async def process(self):
        if self._redis:
            await self._redis.add_to_queue("queue", data)
```

Or use context managers directly:

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

## Common Patterns

### Application Lifecycle

**Startup (in main.py):**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize logging first (before any other initialization)
    setup_logging()

    # Startup
    await init_db()
    await init_redis()

    yield

    # Shutdown
    await close_db()
    await close_redis()
```

### Transaction Management

**Auto-commit pattern:**

```python
async with get_session() as session:
    camera = Camera(id="cam1", name="Front Door")
    session.add(camera)
    # Commits automatically on context exit
```

**Manual control:**

```python
async with get_session() as session:
    camera = Camera(id="cam1", name="Front Door")
    session.add(camera)
    await session.flush()  # Write to DB but don't commit
    # ... more operations
    # Commits at context exit
```

**Error handling:**

```python
try:
    async with get_session() as session:
        # ... operations that might fail
        pass
except Exception as e:
    # Session automatically rolled back
    logger.error(f"Database error: {e}")
```

### Settings Access

```python
from backend.core import get_settings

def my_function():
    settings = get_settings()

    # Access configuration
    db_url = settings.database_url
    redis_url = settings.redis_url
    confidence = settings.detection_confidence_threshold

    # Use settings
    if settings.debug:
        print(f"Debug mode enabled")
```

## Type Hints

All core modules use modern Python type hints:

```python
from collections.abc import AsyncGenerator
from typing import Any

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    ...

async def add_to_queue(queue_name: str, data: Any) -> int:
    ...
```

## Logging

All modules use the centralized logging infrastructure from `logging.py`:

```python
from backend.core import get_logger

logger = get_logger(__name__)
logger.info("Redis connected successfully")
logger.warning("Database connection attempt failed")
logger.error("Critical error", exc_info=True)

# With structured context
logger.info("Detection processed", extra={
    "camera_id": "front_door",
    "detection_id": 123,
    "duration_ms": 45
})
```

See the `logging.py` section above for detailed documentation.

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
