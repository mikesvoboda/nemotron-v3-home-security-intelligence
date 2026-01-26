# Backend Agent Guide

## Request/Response Flow

![API Request Flow](../docs/images/architecture/request-response-flow.png)

_Sequence diagram showing typical request flow through Browser, Nginx, FastAPI, PostgreSQL, Redis, and AI services._

## Purpose

The backend is a FastAPI-based REST API server for an AI-powered home security monitoring system. It orchestrates:

- **Camera management** - Track cameras, zones, and their upload directories
- **AI detection pipeline** - File watching, YOLO26 object detection, batch aggregation, Nemotron risk analysis
- **Data persistence** - PostgreSQL database for structured data (cameras, detections, events, GPU stats, logs)
- **Real-time capabilities** - Redis for queues, pub/sub, and caching with backpressure handling
- **Media serving** - Secure file serving with path traversal protection
- **System monitoring** - Health checks, GPU stats, and system statistics
- **Observability** - Prometheus metrics, structured logging, dead-letter queues
- **Alerting** - Alert rules with severity-based thresholds and notification channels
- **TLS/HTTPS** - Optional TLS support with self-signed certificate generation
- **Audit logging** - Security-sensitive operation tracking for compliance

## Architecture Summary

| Component           | Count | Description                                     |
| ------------------- | ----- | ----------------------------------------------- |
| API Routes          | 34    | REST endpoints organized by domain              |
| Services            | 124   | Business logic, AI pipeline, background workers |
| Models              | 35    | SQLAlchemy ORM models                           |
| Schemas             | 49    | Pydantic request/response schemas               |
| Middleware          | 20    | Request processing pipeline                     |
| Repositories        | 9     | Data access abstraction layer                   |
| Core Infrastructure | 28    | Database, Redis, config, logging, etc.          |

## Running the Backend

```bash
# Development (from project root)
source .venv/bin/activate
python -m backend.main

# Or with uvicorn directly
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Production (via Podman)
podman-compose -f docker-compose.prod.yml up -d backend
```

## Directory Structure

```
backend/
├── main.py                 # FastAPI application entry point (600+ lines)
├── __init__.py             # Package initialization
├── Dockerfile              # Container configuration (uv-based, works with Docker/Podman)
├── .dockerignore           # Docker build exclusions
├── alembic.ini             # Alembic configuration
├── alembic/                # Database migrations (Alembic)
├── api/                    # REST API layer
│   ├── routes/             # 34 API route modules
│   ├── schemas/            # 49 Pydantic schema modules
│   ├── middleware/         # 20 middleware components
│   ├── helpers/            # API helper modules
│   └── utils/              # API utility modules
├── core/                   # Infrastructure (28 modules)
│   ├── websocket/          # WebSocket event infrastructure
│   └── middleware/         # Core middleware components
├── models/                 # SQLAlchemy ORM models (35 models)
├── repositories/           # Data access layer (9 repositories)
├── jobs/                   # Background job modules (3 jobs)
├── services/               # Business logic and AI pipeline (124 modules)
│   └── orchestrator/       # Service orchestration subsystem
├── tests/                  # Unit and integration tests
├── data/                   # Runtime data (sample images, thumbnails)
├── examples/               # Example scripts (Redis usage)
└── scripts/                # Utility scripts (VRAM benchmarking)
```

**Note:** Python dependencies are managed via `uv` (pyproject.toml/uv.lock) at the project root level, not per-directory requirements.txt files.

## Key Files

### Application Entry Point

**`main.py`** - FastAPI application with:

- Lifespan context manager for startup/shutdown
- CORS middleware configuration
- Authentication middleware (optional API key validation via `AuthMiddleware`)
- Request ID middleware for log correlation (`RequestIDMiddleware`)
- Health check endpoints (`/`, `/health`)
- Router registration for 27 API modules:
  - `admin` - Admin operations and cache management
  - `ai_audit` - AI pipeline audit and prompt management
  - `alerts` - Alert rule CRUD and evaluation
  - `analytics` - Detection and event analytics
  - `audit` - Security audit logging
  - `calibration` - Detection calibration settings
  - `cameras` - Camera CRUD and status
  - `debug` - Debug endpoints for development
  - `detections` - Detection queries with filtering
  - `dlq` - Dead-letter queue management
  - `entities` - Entity tracking (people, vehicles)
  - `events` - Event management and review workflow
  - `exports` - Data export management
  - `feedback` - User feedback on events
  - `jobs` - Background job management
  - `logs` - Log querying and frontend log ingestion
  - `media` - Secure file serving for images/videos
  - `metrics` - Prometheus metrics endpoint
  - `notification` - Notification channel management
  - `notification_preferences` - User notification preferences
  - `queues` - Queue status and management
  - `rum` - Real User Monitoring data collection
  - `services` - Service management and control
  - `system` - Health checks, GPU stats, pipeline status
  - `websocket` - Real-time event streaming
  - `zones` - Zone management for camera areas
- Database and Redis initialization
- Service initialization:
  - `FileWatcher` - Monitors camera directories for new uploads
  - `PipelineWorkerManager` - Detection queue, analysis queue, batch timeout workers
  - `GPUMonitor` - NVIDIA GPU statistics monitoring
  - `CleanupService` - Data retention and disk cleanup
  - `SystemBroadcaster` - Periodic system status broadcasting
  - `EventBroadcaster` - WebSocket event distribution
  - `PerformanceCollector` - AI service performance metrics collection
  - `ServiceHealthMonitor` - Auto-recovery monitoring for AI services

### Package Configuration

**`__init__.py`** - Simple package docstring for the backend module.

## Core Infrastructure (`core/`)

See `core/AGENTS.md` for detailed documentation. The core layer contains 28 modules providing foundational infrastructure.

### Configuration and Settings

**`config.py`** - Pydantic Settings for configuration:

- Environment variable loading from `.env` and optional `runtime.env`
- Database URL with PostgreSQL support (required)
- Redis connection URL with queue backpressure settings
- API settings (host, port, CORS, rate limiting)
- File watching settings (Foscam base path, polling options)
- Retention and batch processing timings
- AI service endpoints (YOLO26, Nemotron)
- Detection and fast path thresholds
- Logging configuration (file, database, rotation)
- TLS/HTTPS settings (mode-based: disabled, self_signed, provided)
- Notification settings (SMTP, webhooks)
- Severity threshold configuration
- Cached singleton pattern via `@lru_cache`

**`constants.py`** - Application-wide constants and magic values.

### Data Layer

**`database.py`** - SQLAlchemy 2.0 async database layer:

- `Base` - Declarative base for all models
- `init_db()` / `close_db()` - Lifecycle management
- `get_db()` - FastAPI dependency for database sessions
- `get_session()` - Async context manager for services
- PostgreSQL connection pooling with asyncpg driver

**`redis.py`** - Redis async client wrapper:

- `RedisClient` class with connection pooling
- Queue operations with backpressure handling:
  - `add_to_queue_safe()` - Queue add with overflow policies (REJECT, DLQ, DROP_OLDEST)
  - `get_queue_pressure()` - Queue health metrics
- Pub/Sub operations (publish, subscribe, listen)
- Cache operations (get, set, delete, exists, expire)
- Retry logic with exponential backoff and jitter

**`container.py`** - Dependency injection container for service resolution.

**`dependencies.py`** - FastAPI dependency injection utilities.

### Resilience and Error Handling

**`circuit_breaker.py`** - Circuit breaker pattern for fault tolerance:

- State management (CLOSED, OPEN, HALF_OPEN)
- Configurable failure thresholds and recovery timeouts
- Async context manager support

**`websocket_circuit_breaker.py`** - WebSocket-specific circuit breaker.

**`retry.py`** - Retry logic with exponential backoff and jitter.

**`exceptions.py`** - Custom exception hierarchy for the application.

**`error_context.py`** - Error context enrichment for debugging.

### Observability

**`logging.py`** - Centralized logging infrastructure:

- Console, file, and SQLite handlers
- Request ID context propagation
- Structured logging with camera_id, event_id, detection_id, duration_ms
- Error message sanitization (`sanitize_error`)

**`metrics.py`** - Prometheus metrics:

- Queue depth gauges (detection, analysis)
- Stage duration histograms (detect, batch, analyze)
- Event/detection counters
- AI request duration tracking (rtdetr, nemotron)
- Error counters by type
- `PipelineLatencyTracker` - In-memory latency tracking with percentile calculations

**`telemetry.py`** - Distributed tracing and telemetry collection.

**`profiling.py`** - Performance profiling utilities.

**`query_explain.py`** - SQL query analysis and EXPLAIN plan utilities.

### Async Utilities

**`async_context.py`** - Async context management utilities.

**`async_utils.py`** - Common async helper functions.

### Security

**`tls.py`** - TLS/SSL configuration and certificate management:

- `TLSMode` enum: DISABLED, SELF_SIGNED, PROVIDED
- `TLSConfig` dataclass for configuration
- Self-signed certificate generation with SANs
- SSL context creation for uvicorn
- Certificate validation and info extraction

**`sanitization.py`** - Input sanitization for security.

**`url_validation.py`** - URL validation and safety checks.

### Utilities

**`mime_types.py`** - MIME type utilities:

- Image and video MIME type mappings
- Extension-to-MIME conversion
- File type normalization

**`json_utils.py`** - JSON serialization utilities.

**`time_utils.py`** - Time and datetime utilities.

**`protocols.py`** - Protocol definitions for type checking.

**`docker_client.py`** - Docker/Podman client abstraction.

## Database Models (`models/`)

See `models/AGENTS.md` for detailed documentation. The data layer contains 25 SQLAlchemy models using 2.0 `Mapped` type hints.

### Core Domain Models

- **`Camera`** - Camera entity with detections/events relationships
- **`Detection`** - Object detection results with bounding boxes and video metadata
- **`Event`** - Security events with LLM risk analysis
- **`Zone`** - Camera monitoring zones/areas
- **`Entity`** - Tracked entities (people, vehicles) across cameras

### Event and Detection Extensions

- **`EventDetection`** - Many-to-many relationship between events and detections
- **`EventAudit`** - Event review and audit trail
- **`EventFeedback`** - User feedback on event classification

### AI and Analysis

- **`PromptConfig`** - LLM prompt configuration storage
- **`PromptVersion`** - Prompt versioning for A/B testing
- **`Baseline`** - Scene baseline for anomaly detection
- **`SceneChange`** - Detected scene changes

### User and System

- **`UserCalibration`** - User-specific calibration settings
- **`NotificationPreferences`** - User notification preferences

### Alerting

- **`Alert`** - Alert rule definitions and thresholds

### Monitoring

- **`GPUStats`** - GPU performance time-series data
- **`Log`** - Structured application logs
- **`Audit`** - Security audit records

### Background Jobs

- **`Job`** - Background job definitions and state
- **`JobAttempt`** - Individual job execution attempts
- **`JobLog`** - Job execution logs
- **`JobTransition`** - Job state transition history
- **`ExportJob`** - Data export job tracking

### Supporting

- **`enums.py`** - Shared enum definitions (severity levels, statuses, etc.)

## API Routes (`api/routes/`)

See `api/routes/AGENTS.md` for detailed documentation. The API layer contains 28 route modules.

### Core Domain Routes

| Route           | Prefix            | Description                                        |
| --------------- | ----------------- | -------------------------------------------------- |
| `cameras.py`    | `/api/cameras`    | Camera CRUD, status, and configuration             |
| `detections.py` | `/api/detections` | Detection queries with filtering and pagination    |
| `events.py`     | `/api/events`     | Event management, review workflow, bulk operations |
| `zones.py`      | `/api/cameras`    | Zone management for camera areas                   |
| `entities.py`   | `/api/entities`   | Entity tracking (people, vehicles)                 |

### AI and Analysis Routes

| Route                  | Prefix                  | Description                               |
| ---------------------- | ----------------------- | ----------------------------------------- |
| `ai_audit.py`          | `/api/ai-audit`         | AI pipeline audit and performance metrics |
| `prompt_management.py` | `/api/ai-audit/prompts` | LLM prompt version management             |
| `analytics.py`         | `/api/analytics`        | Detection and event analytics             |
| `calibration.py`       | `/api/calibration`      | Detection calibration settings            |

### System and Infrastructure Routes

| Route         | Prefix                 | Description                               |
| ------------- | ---------------------- | ----------------------------------------- |
| `system.py`   | `/api/system`          | Health checks, GPU stats, pipeline status |
| `services.py` | `/api/system/services` | Service management and control            |
| `metrics.py`  | `/api`                 | Prometheus metrics endpoint               |
| `dlq.py`      | `/api/dlq`             | Dead-letter queue management              |
| `admin.py`    | `/api/admin`           | Admin operations and cache management     |
| `debug.py`    | `/api/debug`           | Debug endpoints for development           |
| `jobs.py`     | `/api/jobs`            | Background job management                 |
| `queues.py`   | `/api/queues`          | Queue status and management               |

### Media and Logging Routes

| Route        | Prefix         | Description                            |
| ------------ | -------------- | -------------------------------------- |
| `media.py`   | `/api/media`   | Secure file serving for images/videos  |
| `logs.py`    | `/api/logs`    | Log queries and frontend log ingestion |
| `rum.py`     | `/api/rum`     | Real User Monitoring data collection   |
| `exports.py` | `/api/exports` | Data export management                 |

### Notification and Alerting Routes

| Route                         | Prefix                          | Description                     |
| ----------------------------- | ------------------------------- | ------------------------------- |
| `alerts.py`                   | `/api/alerts/rules`             | Alert rule CRUD and evaluation  |
| `notification.py`             | `/api/notification`             | Notification channel management |
| `notification_preferences.py` | `/api/notification-preferences` | User notification preferences   |

### Security and Compliance Routes

| Route         | Prefix          | Description             |
| ------------- | --------------- | ----------------------- |
| `audit.py`    | `/api/audit`    | Security audit logging  |
| `feedback.py` | `/api/feedback` | User feedback on events |

### Real-time Routes

| Route          | Prefix | Description                     |
| -------------- | ------ | ------------------------------- |
| `websocket.py` | `/ws`  | WebSocket real-time connections |

## API Middleware (`api/middleware/`)

The middleware layer contains 20 components for request processing:

| Middleware                  | Purpose                                 |
| --------------------------- | --------------------------------------- |
| `accept_header.py`          | Accept header parsing and validation    |
| `auth.py`                   | API key authentication                  |
| `body_limit.py`             | Request body size limiting              |
| `content_negotiation.py`    | Content negotiation handling            |
| `content_type_validator.py` | Content-Type validation                 |
| `correlation.py`            | Correlation ID for distributed tracing  |
| `deprecation.py`            | API deprecation handling                |
| `deprecation_logger.py`     | Deprecated endpoint logging             |
| `error_handler.py`          | Error response formatting               |
| `exception_handler.py`      | Global exception handling with RFC 7807 |
| `file_validator.py`         | File upload validation                  |
| `idempotency.py`            | Idempotency key handling                |
| `rate_limit.py`             | Request rate limiting                   |
| `request_id.py`             | Request ID generation and propagation   |
| `request_logging.py`        | Request/response logging                |
| `request_recorder.py`       | Request recording for debugging         |
| `request_timing.py`         | Request duration metrics                |
| `security_headers.py`       | Security headers (CSP, HSTS, etc.)      |
| `websocket_auth.py`         | WebSocket authentication                |

## API Schemas (`api/schemas/`)

The schema layer contains 43 Pydantic models for request/response validation:

- **Domain schemas:** `camera.py`, `detections.py`, `events.py`, `zone.py`, `entities.py`
- **AI schemas:** `ai_audit.py`, `llm.py`, `llm_response.py`, `enrichment.py`, `enrichment_data.py`
- **System schemas:** `system.py`, `health.py`, `services.py`, `queue.py`, `queue_status.py`, `performance.py`
- **Notification schemas:** `notification.py`, `notification_preferences.py`, `alerts.py`
- **Media schemas:** `media.py`, `clips.py`, `streaming.py`
- **Error handling:** `errors.py`, `problem_details.py` (RFC 7807)
- **Background jobs:** `jobs.py`, `export.py`
- **Feedback:** `feedback.py`
- **Documentation:** `openapi_docs.py`
- **Utilities:** `bulk.py`, `hateoas.py`, `search.py`, `baseline.py`, `calibration.py`, `pagination.py`

## Repositories (`repositories/`)

The repository layer provides data access abstraction with a generic base class:

- **`base.py`** - Generic `Repository[T]` base class with:

  - `get_by_id()` - Retrieve by primary key
  - `get_all()` - Retrieve all entities
  - `list_paginated()` - Paginated queries with skip/limit
  - `count()` - Count entities
  - `create()` / `update()` / `delete()` - CRUD operations
  - `merge()` - Upsert operations
  - `save()` - Persist changes

- **`camera_repository.py`** - Camera-specific queries
- **`detection_repository.py`** - Detection-specific queries
- **`entity_repository.py`** - Entity tracking queries
- **`event_repository.py`** - Event-specific queries

## Services (`services/`)

See `services/AGENTS.md` for detailed documentation. The service layer contains 89 modules organized by function.

### Core AI Pipeline

| Service                  | Purpose                                     |
| ------------------------ | ------------------------------------------- |
| `file_watcher.py`        | Monitors camera directories for new uploads |
| `detector_client.py`     | YOLO26 HTTP client for object detection     |
| `batch_aggregator.py`    | Groups detections into time-based batches   |
| `nemotron_analyzer.py`   | LLM risk analysis via llama.cpp             |
| `nemotron_streaming.py`  | Streaming LLM responses                     |
| `thumbnail_generator.py` | Detection visualization with bounding boxes |
| `dedupe.py`              | File deduplication using content hashes     |
| `vision_extractor.py`    | Visual feature extraction                   |

### AI Model Loaders (Lazy Loading)

| Service                        | Model                         |
| ------------------------------ | ----------------------------- |
| `clip_loader.py`               | CLIP embeddings               |
| `clip_client.py`               | CLIP client interface         |
| `florence_loader.py`           | Florence-2 vision-language    |
| `florence_client.py`           | Florence client interface     |
| `florence_extractor.py`        | Florence feature extraction   |
| `depth_anything_loader.py`     | Depth estimation              |
| `segformer_loader.py`          | Semantic segmentation         |
| `vitpose_loader.py`            | Pose estimation               |
| `yolo_world_loader.py`         | YOLO-World detection          |
| `xclip_loader.py`              | X-CLIP video understanding    |
| `fashion_clip_loader.py`       | Fashion-specific CLIP         |
| `pet_classifier_loader.py`     | Pet/animal classification     |
| `vehicle_classifier_loader.py` | Vehicle classification        |
| `vehicle_damage_loader.py`     | Vehicle damage detection      |
| `violence_loader.py`           | Violence detection            |
| `weather_loader.py`            | Weather classification        |
| `image_quality_loader.py`      | Image quality assessment      |
| `model_loader_base.py`         | Base class for model loaders  |
| `model_zoo.py`                 | Model registry and management |

### Detection Enrichment Pipeline

| Service                  | Purpose                            |
| ------------------------ | ---------------------------------- |
| `enrichment_pipeline.py` | Detection enrichment orchestration |
| `enrichment_client.py`   | Enrichment service client          |
| `context_enricher.py`    | Context-aware enrichment           |
| `face_detector.py`       | Face detection                     |
| `plate_detector.py`      | License plate detection            |
| `ocr_service.py`         | Optical character recognition      |
| `reid_service.py`        | Person re-identification           |
| `bbox_validation.py`     | Bounding box validation            |

### Scene Analysis

| Service                    | Purpose                   |
| -------------------------- | ------------------------- |
| `scene_baseline.py`        | Scene baseline management |
| `scene_change_detector.py` | Scene change detection    |
| `baseline.py`              | Baseline calculation      |

### Pipeline Workers

| Service                   | Purpose                                                                                                                       |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `pipeline_workers.py`     | Background workers (DetectionQueueWorker, AnalysisQueueWorker, BatchTimeoutWorker, QueueMetricsWorker, PipelineWorkerManager) |
| `evaluation_queue.py`     | Evaluation queue management                                                                                                   |
| `background_evaluator.py` | Background evaluation processing                                                                                              |
| `batch_fetch.py`          | Batch data fetching                                                                                                           |

### Broadcasting and Real-time

| Service                 | Purpose                                        |
| ----------------------- | ---------------------------------------------- |
| `event_broadcaster.py`  | WebSocket event distribution via Redis pub/sub |
| `system_broadcaster.py` | Periodic system status broadcasting            |

### Video Processing

| Service              | Purpose                               |
| -------------------- | ------------------------------------- |
| `video_processor.py` | Video processing and frame extraction |
| `clip_generator.py`  | Video clip generation                 |

### Background Services

| Service                          | Purpose                                      |
| -------------------------------- | -------------------------------------------- |
| `gpu_monitor.py`                 | NVIDIA GPU statistics monitoring             |
| `cleanup_service.py`             | Data retention and disk cleanup              |
| `health_monitor.py`              | Service health monitoring with auto-recovery |
| `health_monitor_orchestrator.py` | Health monitor coordination                  |
| `performance_collector.py`       | AI service performance metrics               |

### Alerting and Notifications

| Service                  | Purpose                      |
| ------------------------ | ---------------------------- |
| `alert_engine.py`        | Alert rule evaluation engine |
| `alert_dedup.py`         | Alert deduplication          |
| `notification.py`        | Notification dispatch        |
| `notification_filter.py` | Notification filtering rules |
| `severity.py`            | Severity calculation         |

### Prompt Management

| Service                     | Purpose                        |
| --------------------------- | ------------------------------ |
| `prompts.py`                | LLM prompt templates           |
| `prompt_parser.py`          | Prompt parsing                 |
| `prompt_sanitizer.py`       | Prompt input sanitization      |
| `prompt_storage.py`         | Prompt persistence             |
| `prompt_version_service.py` | Prompt versioning              |
| `prompt_service.py`         | Prompt service facade          |
| `typed_prompt_config.py`    | Type-safe prompt configuration |
| `token_counter.py`          | Token counting for prompts     |

### Resilience and Fault Tolerance

| Service                  | Purpose                             |
| ------------------------ | ----------------------------------- |
| `circuit_breaker.py`     | Circuit breaker pattern             |
| `retry_handler.py`       | Exponential backoff and DLQ support |
| `ai_fallback.py`         | AI service fallback strategies      |
| `degradation_manager.py` | Graceful degradation                |
| `inference_semaphore.py` | Inference concurrency control       |

### Service Management

| Service                     | Purpose                                                |
| --------------------------- | ------------------------------------------------------ |
| `service_managers.py`       | Strategy pattern for service management (Shell/Docker) |
| `service_registry.py`       | Service registration and discovery                     |
| `managed_service.py`        | Managed service base class                             |
| `lifecycle_manager.py`      | Service lifecycle management                           |
| `container_discovery.py`    | Container discovery                                    |
| `container_orchestrator.py` | Container orchestration                                |

### Data Access

| Service            | Purpose                       |
| ------------------ | ----------------------------- |
| `search.py`        | Full-text and semantic search |
| `cache_service.py` | Caching layer                 |
| `zone_service.py`  | Zone management               |

### Audit and Compliance

| Service                             | Purpose                    |
| ----------------------------------- | -------------------------- |
| `audit.py`                          | Audit service              |
| `audit_logger.py`                   | Audit logging              |
| `pipeline_quality_audit_service.py` | Pipeline quality auditing  |
| `cost_tracker.py`                   | AI inference cost tracking |

### Calibration

| Service          | Purpose               |
| ---------------- | --------------------- |
| `calibration.py` | Detection calibration |

### Database Management

| Service                | Purpose            |
| ---------------------- | ------------------ |
| `partition_manager.py` | Table partitioning |

### Orchestrator Subsystem (`services/orchestrator/`)

| Module        | Purpose                  |
| ------------- | ------------------------ |
| `__init__.py` | Orchestrator exports     |
| `enums.py`    | Orchestrator enums       |
| `models.py`   | Orchestrator data models |
| `registry.py` | Service registry         |

## Data Flow

### Detection Pipeline

```
Camera uploads -> FileWatcher -> detection_queue (Redis)
                                      |
                              DetectionQueueWorker
                                      |
                               DetectorClient -> YOLO26
                                      |
                               Detection (DB)
                                      |
                    ┌─────────────────┼─────────────────┐
                    |                 |                 |
           ThumbnailGenerator   BatchAggregator   EnrichmentPipeline
                                      |                 |
                               analysis_queue     [CLIP, Florence,
                                      |            Face, Plate, OCR]
                                      |
                          AnalysisQueueWorker
                                      |
                             NemotronAnalyzer -> Nemotron LLM
                                      |
                                 Event (DB)
                                      |
                    ┌─────────────────┼─────────────────┐
                    |                 |                 |
             AlertEngine     EventBroadcaster   NotificationService
                    |          (Redis pub/sub)         |
              Alert (DB)              |           [Email, Webhook]
                             WebSocket clients
```

### System Monitoring Flow

```
GPU stats (pynvml) -> GPUMonitor -> GPUStats (DB) -> SystemBroadcaster -> WebSocket

Health checks -> HealthMonitor -> ServiceHealthMonitor -> auto-recovery

Performance -> PerformanceCollector -> Prometheus metrics -> /api/metrics
```

### Background Services Flow

```
Scheduled cleanup -> CleanupService -> Delete old records -> Remove files

Scene analysis -> SceneChangeDetector -> SceneBaseline -> Anomaly detection

Cost tracking -> CostTracker -> Usage metrics -> /api/ai-audit
```

### Logging Flow

```
Backend operations -> get_logger() -> SQLiteHandler -> Log (DB)
                                   -> RotatingFileHandler -> security.log
                                   -> StreamHandler -> console

Frontend logs -> POST /api/logs/frontend -> Log (DB)

RUM events -> POST /api/rum -> Performance metrics (DB)
```

### Error Handling Flow

```
Failed jobs -> RetryHandler (exponential backoff)
                    |
           ┌───────┴───────┐
           |               |
      Retry (N times)   DLQ (Redis)
                           |
                   /api/dlq/* endpoints
                           |
                   Manual review/replay
```

### Resilience Patterns

```
AI Service Request -> CircuitBreaker -> InferenceSemaphore -> AI Service
                           |                   |
                    [OPEN: fallback]    [Rate limiting]
                           |
                    AIFallback -> DegradationManager
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
    result = await redis.add_to_queue_safe("my_queue", {"data": "value"})
    if not result.success:
        raise HTTPException(status_code=503, detail="Queue full")
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

Test structure mirrors source code with comprehensive coverage:

```
backend/tests/
├── unit/                  # 8,229 unit tests
│   ├── api/               # API route tests
│   ├── core/              # Core infrastructure tests
│   ├── models/            # Model tests
│   ├── services/          # Service tests
│   └── repositories/      # Repository tests
└── integration/           # 1,556 integration tests (4 shards)
    ├── api/               # API integration tests
    ├── websocket/         # WebSocket tests
    ├── services/          # Service integration tests
    └── models/            # Model integration tests
```

**Running Tests:**

```bash
# Unit tests (parallel, ~10s)
uv run pytest backend/tests/unit/ -n auto --dist=worksteal

# Integration tests (serial, ~70s)
uv run pytest backend/tests/integration/ -n0

# Full test suite with coverage
uv run pytest backend/tests/ --cov=backend --cov-report=term-missing

# Specific test file
uv run pytest backend/tests/unit/api/routes/test_cameras.py -v
```

**Coverage Requirements:**

| Test Type | Minimum |
| --------- | ------- |
| Unit      | 85%     |
| Combined  | 95%     |

## Environment Variables

Key environment variables (loaded via `.env` file):

```bash
# Database and Redis
DATABASE_URL=postgresql+asyncpg://security:password@localhost:5432/security
REDIS_URL=redis://localhost:6379/0

# Camera configuration
FOSCAM_BASE_PATH=/export/foscam

# AI service endpoints
YOLO26_URL=http://localhost:8090
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
LOG_LEVEL=WARNING
LOG_DB_ENABLED=true

# TLS (optional)
TLS_MODE=disabled  # or self_signed, provided
TLS_CERT_PATH=/path/to/cert.pem
TLS_KEY_PATH=/path/to/key.pem

# Rate limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
```

## Health Endpoints

The backend provides three health endpoints for different use cases:

| Endpoint                 | Purpose                                     | Returns               |
| ------------------------ | ------------------------------------------- | --------------------- |
| `GET /`                  | Basic status check                          | `{"status": "ok"}`    |
| `GET /health`            | Liveness probe (Kubernetes/Docker)          | `{"status": "alive"}` |
| `GET /ready`             | Readiness probe (checks DB, Redis, workers) | HTTP 200 or 503       |
| `GET /api/system/health` | Detailed health with service breakdown      | Full status object    |

## Related Documentation

### Backend Subdirectories

| Path                                | Purpose                            |
| ----------------------------------- | ---------------------------------- |
| `/backend/alembic/AGENTS.md`        | Database migration documentation   |
| `/backend/api/routes/AGENTS.md`     | API endpoints (28 routes)          |
| `/backend/api/schemas/AGENTS.md`    | Pydantic schemas (43 schemas)      |
| `/backend/api/middleware/AGENTS.md` | Middleware components (20 modules) |
| `/backend/api/utils/AGENTS.md`      | API utility modules                |
| `/backend/core/AGENTS.md`           | Core infrastructure (28 modules)   |
| `/backend/core/websocket/AGENTS.md` | WebSocket event infrastructure     |
| `/backend/jobs/AGENTS.md`           | Background job modules             |
| `/backend/models/AGENTS.md`         | Database models (25 models)        |
| `/backend/repositories/AGENTS.md`   | Repository pattern (5 repos)       |
| `/backend/services/AGENTS.md`       | Service layer (89 modules)         |
| `/backend/tests/AGENTS.md`          | Test infrastructure                |
| `/backend/data/AGENTS.md`           | Runtime data directory             |

### Project-Level Documentation

| Path                                | Purpose                        |
| ----------------------------------- | ------------------------------ |
| `/CLAUDE.md`                        | Project-wide instructions      |
| `/docs/development/testing.md`      | Comprehensive testing patterns |
| `/docs/TEST_PERFORMANCE_METRICS.md` | Test performance baselines     |
| `/docs/ROADMAP.md`                  | Post-MVP enhancements          |
