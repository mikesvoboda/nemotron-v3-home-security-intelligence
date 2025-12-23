# Backend Agent Guide

## Purpose

The backend is a FastAPI-based REST API server for an AI-powered home security monitoring system. It orchestrates:

- **Camera management** - Track cameras and their upload directories
- **AI detection pipeline** - File watching, RT-DETRv2 object detection, batch aggregation, Nemotron risk analysis
- **Data persistence** - SQLite database for structured data (cameras, detections, events, GPU stats)
- **Real-time capabilities** - Redis for queues, pub/sub, and caching
- **Media serving** - Secure file serving with path traversal protection
- **System monitoring** - Health checks, GPU stats, and system statistics

## Directory Structure

```
backend/
├── main.py                 # FastAPI application entry point
├── core/                   # Infrastructure (database, Redis, config)
├── api/                    # REST API routes and schemas
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
- Health check endpoints (`/`, `/health`)
- Router registration (cameras, media, system)
- Database and Redis initialization

### Core Infrastructure (`core/`)

**`config.py`** - Pydantic Settings for configuration:

- Environment variable loading from `.env`
- Database URL with SQLite support
- Redis connection URL
- API settings (host, port, CORS)
- File watching settings (Foscam base path)
- Retention and batch processing timings
- AI service endpoints (RT-DETR, Nemotron)
- Detection confidence thresholds
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
- Queue operations (RPUSH, BLPOP, LLEN, LRANGE)
- Pub/Sub operations (publish, subscribe, listen)
- Cache operations (get, set, delete, exists)
- JSON serialization/deserialization for all operations
- Health check with server info
- Global singleton instance pattern
- `init_redis()` / `close_redis()` for app lifecycle
- `get_redis()` - FastAPI dependency

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
- Indexes on camera_id, started_at, risk_score, reviewed, batch_id

**`gpu_stats.py`** - GPU performance metrics:

- `id` (int, auto-increment)
- `recorded_at` (datetime)
- `gpu_utilization` (float) - Percentage 0-100
- `memory_used`, `memory_total` (int) - Bytes
- `temperature` (float) - Celsius
- `inference_fps` (float) - Frames per second
- Index on recorded_at for time-series queries

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
- Helper functions: `check_database_health()`, `check_redis_health()`, `check_ai_services_health()`

### Services (`services/`)

**`file_watcher.py`** - Filesystem monitoring service:

- Watches Foscam camera directories for new image uploads
- Uses `watchdog` library for file system events
- Debounce logic (0.5s delay) to wait for file writes to complete
- Image validation (PIL verify, non-zero size)
- Extracts camera ID from path structure
- Queues detections to Redis `detection_queue`
- Async-compatible with thread-safe event loop scheduling
- `start()` / `stop()` lifecycle management

**`detector_client.py`** - RT-DETRv2 HTTP client:

- Sends images to RT-DETRv2 service via `POST /detect`
- Filters detections by confidence threshold (from settings)
- Creates `Detection` models in database
- HTTP client with 30s timeout
- Error handling for connection errors, timeouts, HTTP errors
- `health_check()` method for service availability
- Returns list of `Detection` instances

**`batch_aggregator.py`** - Detection batching service:

- Groups detections from same camera into time-based batches
- **Batch window**: 90 seconds from batch start
- **Idle timeout**: 30 seconds since last detection
- Redis keys pattern:
  - `batch:{camera_id}:current` - Active batch ID for camera
  - `batch:{batch_id}:camera_id` - Camera for batch
  - `batch:{batch_id}:detections` - JSON array of detection IDs
  - `batch:{batch_id}:started_at` - Unix timestamp (float)
  - `batch:{batch_id}:last_activity` - Unix timestamp (float)
- `add_detection()` - Add to active batch or create new one
- `check_batch_timeouts()` - Scan all batches, close expired ones
- `close_batch()` - Push to `analysis_queue` and cleanup Redis keys

**`nemotron_analyzer.py`** - LLM risk analysis service:

- Consumes from `analysis_queue` (populated by batch aggregator)
- Fetches detection details from database
- Formats prompt with camera name, time window, detection list
- Calls llama.cpp server (`POST /completion`) with Nemotron model
- Parses JSON response from LLM (extracts from markdown if needed)
- Validates risk data (score 0-100, valid level)
- Creates `Event` record with risk assessment
- Broadcasts event via Redis pub/sub (optional)
- Fallback risk data on LLM errors
- `health_check()` method for LLM service availability

**`thumbnail_generator.py`** - Detection visualization:

- Generates thumbnail images with bounding boxes
- PIL/Pillow for image manipulation
- Color-coded boxes by object type (person=red, car=blue, dog=green, etc.)
- Draws labels with object type and confidence
- Resizes to 320x240 with aspect ratio preservation and padding
- Saves as JPEG (quality 85) to `data/thumbnails/`
- Filename pattern: `{detection_id}_thumb.jpg`
- Font loading with fallback to default PIL font

**`prompts.py`** - LLM prompt templates:

- `RISK_ANALYSIS_PROMPT` - Template for Nemotron risk assessment
- Formats camera name, time window, and detection list
- Instructs LLM to return JSON with risk_score, risk_level, summary, reasoning

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
  ├── core (config, database, redis)
  ├── api.routes (cameras, media, system)
  └── models (Camera, Detection, Event, GPUStats)

api.routes
  ├── core (database, redis, config)
  ├── models (ORM classes)
  └── api.schemas (Pydantic request/response models)

services
  ├── core (config, database, redis)
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
Camera uploads → FileWatcher → detection_queue (Redis)
                                      ↓
                              DetectorClient → RT-DETRv2
                                      ↓
                               Detection (DB) → BatchAggregator
                                                      ↓
                                              analysis_queue (Redis)
                                                      ↓
                                             NemotronAnalyzer → Nemotron LLM
                                                      ↓
                                                 Event (DB)
                                                      ↓
                                             WebSocket broadcast
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
DATABASE_URL=sqlite+aiosqlite:///./data/security.db
REDIS_URL=redis://localhost:6379/0
FOSCAM_BASE_PATH=/export/foscam
RTDETR_URL=http://localhost:8001
NEMOTRON_URL=http://localhost:8002
DETECTION_CONFIDENCE_THRESHOLD=0.5
BATCH_WINDOW_SECONDS=90
BATCH_IDLE_TIMEOUT_SECONDS=30
RETENTION_DAYS=30
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

All modules use Python's `logging` module:

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message", exc_info=True)
```

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
