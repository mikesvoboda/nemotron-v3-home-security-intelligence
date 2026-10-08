# Backend Agent Guide

## Request/Response Flow

![API Request Flow](../docs/images/architecture/request-response-flow.png)

_Sequence diagram showing typical request flow through Browser, Nginx, FastAPI, PostgreSQL, Redis, and AI services._

## Purpose

The backend is a FastAPI-based REST API server for an AI-powered home security monitoring system. It orchestrates:

- **Camera management** - Track cameras, zones, and their upload directories
- **AI detection pipeline** - File watching, YOLO26 object detection, batch aggregation, VLM risk analysis (the `ai-vlm` llama.cpp engine; model identity is config, ledger D5)
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
| API Routes          | 60    | REST endpoints organized by domain              |
| Services            | 177   | Business logic, AI pipeline, background workers |
| Models              | 54    | SQLAlchemy ORM model modules                    |
| Schemas             | 86    | Pydantic request/response schemas               |
| Middleware          | 23    | Request processing pipeline                     |
| Repositories        | 8     | Data access layer (base + 7 repositories)       |
| Core Infrastructure | 54    | Database, Redis, config, logging, etc.          |

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
├── main.py                 # FastAPI application entry point (1,800+ lines)
├── __init__.py             # Package initialization
├── Dockerfile              # Container configuration (uv-based, works with Docker/Podman)
├── .dockerignore           # Docker build exclusions
├── ai_contract/            # Generated AI-tier operation registry (plan P)
├── api/                    # REST API layer
│   ├── routes/             # 60 API route modules
│   ├── schemas/            # 86 Pydantic schema modules
│   ├── middleware/         # 23 middleware components
│   └── utils/              # API utility modules
├── config/                 # Prompt A/B rollout, experiments, shadow deployment
├── core/                   # Infrastructure (54 modules)
│   ├── websocket/          # WebSocket event infrastructure
│   └── middleware/         # Core middleware components
├── evaluation/             # VLM verdict-path evaluation (eval store, importers, S2/S3/S5 metrics, replay)
├── models/                 # SQLAlchemy ORM models (54 model modules)
├── repositories/           # Data access layer (base + 7 repositories)
├── jobs/                   # Background job modules (3 jobs)
├── services/               # Business logic and AI pipeline (177 modules)
│   ├── data/               # Service data helpers
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
- Router registration for 60 API modules:
  - `action_events` - Action event management
  - `admin` - Admin operations and cache management
  - `ai_audit` - AI pipeline audit and prompt management
  - `alertmanager` - Alertmanager integration
  - `alert_service` - Alert service operations
  - `alerts` - Alert rule CRUD and evaluation
  - `analytics` - Detection and event analytics
  - `analytics_zones` - Analytics zone configuration
  - `audit` - Security audit logging
  - `auth` - Authentication endpoints
  - `backup` - Backup management
  - `calibration` - Detection calibration settings
  - `cameras` - Camera CRUD and status
  - `cost_analytics` - AI inference cost analytics
  - `debug` - Debug endpoints for development
  - `detections` - Detection queries with filtering
  - `detector` - Detector configuration
  - `dlq` - Dead-letter queue management
  - `entities` - Entity tracking (people, vehicles)
  - `entity_recognition` - Entity recognition operations
  - `events` - Event management and review workflow
  - `exports` - Data export management
  - `face_recognition` - Face recognition management
  - `feedback` - User feedback on events
  - `gpu_config` - GPU configuration management
  - `health_ai_services` - AI service health checks
  - `heatmaps` - Heatmap generation and queries
  - `hierarchy` - Hierarchical organization
  - `household` - Household management
  - `household_matcher` - Household matching operations
  - `inbound_webhooks` - Inbound webhook handlers
  - `jobs` - Background job management
  - `llm_reasoning` - LLM reasoning inspection
  - `logs` - Log querying and frontend log ingestion
  - `media` - Secure file serving for images/videos
  - `metrics` - Prometheus metrics endpoint
  - `model_management` - AI model management
  - `mqtt_config` - MQTT configuration
  - `notification` - Notification channel management
  - `notification_preferences` - User notification preferences
  - `onvif` - ONVIF camera discovery and control
  - `outbound_webhooks` - Outbound webhook configuration
  - `plate_reads` - License plate read queries
  - `prompt_management` - LLM prompt version management
  - `queues` - Queue status and management
  - `reid` - Person re-identification
  - `rum` - Real User Monitoring data collection
  - `scheduled_reports` - Scheduled report management
  - `services` - Service management and control
  - `settings_api` - Application settings API
  - `summaries` - Event summaries
  - `system` - Health checks, GPU stats, pipeline status
  - `system_settings` - System-wide settings
  - `tracks` - Object tracking data
  - `trends` - Trend analysis
  - `webhooks` - Webhook management
  - `websocket` - Real-time event streaming
  - `zone_anomalies` - Zone anomaly detection
  - `zone_household` - Zone-household configuration
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

See `core/AGENTS.md` for detailed documentation. The core layer contains 54 modules (top-level plus the websocket and middleware subsystems) providing foundational infrastructure.

### Configuration and Settings

**`config.py`** - Pydantic Settings for configuration:

- Environment variable loading from `.env` and optional `runtime.env`
- Database URL with PostgreSQL support (required)
- Redis connection URL with queue backpressure settings
- API settings (host, port, CORS, rate limiting)
- File watching settings (Foscam base path, polling options)
- Retention and batch processing timings
- AI service endpoints (YOLO26 via `yolo26_url`, the `ai-vlm` engine via `ai_vlm_url`, plus the `ai-gateway` / `enrich-lt` routing URLs)
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
- AI request duration tracking (the only `service` label the pipeline still records is `yolo26`; the `hsi_nemotron_*` histograms stay defined because the Grafana dashboards and `monitoring/*.yml` alert rules query them — API surface, not a live engine)
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

See `models/AGENTS.md` for detailed documentation. The data layer contains 54 SQLAlchemy model modules using 2.0 `Mapped` type hints.

### Core Domain Models

- **`Camera`** - Camera entity with detections/events relationships
- **`Detection`** - Object detection results with bounding boxes and video metadata
- **`Event`** - Security events with LLM risk analysis
- **`CameraZone`** - Camera monitoring zones (`models/zone.py` re-exports it as `Zone`; import from `models/camera_zone.py`)
- **`Entity`** - Tracked entities (people, vehicles) across cameras

### Event and Detection Extensions

- **`EventDetection`** - Many-to-many relationship between events and detections
- **`EventAudit`** - Event review and audit trail
- **`EventFeedback`** - User feedback on event classification
- **`ActionEvent`** - Action event records

### AI and Analysis

- **`PromptConfig`** - LLM prompt configuration storage
- **`PromptVersion`** - Prompt versioning for A/B testing
- **`ActivityBaseline` / `ClassBaseline`** (`models/baseline.py`) - Count-based EWMA activity and per-class frequency baselines for anomaly detection
- **`SceneChange`** - Detected scene changes
- **`LLMInteraction`** - LLM interaction logging
- **`PoseResult` / `ThreatDetection` / `ActionResult`** (`models/enrichment.py`) - Per-detection specialist rows; the module's `DemographicsResult` / `ReIDEmbedding` pair is gone (R8 S4, 2026-09-30, dated DROP runbook)
- **`SmokeFireResult`** - Smoke/fire detection results
- **`ExperimentResult`** - A/B experiment results

### Zone and Area Models

- **`LineZone` / `PolygonZone`** (`models/analytics_zone.py`) - Analytics zone geometry
- **`CameraZone`** - Camera-zone associations
- **`Area`** - Area definitions
- **`ZoneAnomaly`** - Zone anomaly records
- **`ZoneActivityBaseline`** (`models/zone_baseline.py`) - Zone activity baseline data
- **`ZoneHouseholdConfig`** - Zone-household configuration
- **`HeatmapData`** (`models/heatmap.py`) - Heatmap data

### User and System

- **`User`** - User accounts
- **`UserCalibration`** - User-specific calibration settings
- **`NotificationPreferences`** - User notification preferences
- **`APIKey`** - API key management

### Alerting

- **`Alert`** - Alert rule definitions and thresholds
- **`PrometheusAlert`** - Prometheus alert records

### Monitoring

- **`GPUStats`** - GPU performance time-series data
- **`GpuConfiguration` / `GpuDevice`** (`models/gpu_config.py`) - GPU configuration settings
- **`Log`** - Structured application logs
- **`AuditLog`** (`models/audit.py`) - Security audit records

### Background Jobs

- **`Job`** - Background job definitions and state
- **`JobAttempt`** - Individual job execution attempts
- **`JobLog`** - Job execution logs
- **`JobTransition`** - Job state transition history
- **`ExportJob`** - Data export job tracking
- **`BackupJob`** - Backup job tracking
- **`ScheduledReport`** - Scheduled report definitions

### Household and Tracking

- **`Household`** (`models/household_org.py`) - Household entity
- **`HouseholdMember` / `PersonEmbedding` / `RegisteredVehicle`** (`models/household.py`) - Members, the live VLM re-ID gallery vectors, registered vehicles
- **`KnownPerson` / `FaceEmbedding`** (`models/face_identity.py`) - Face recognition identities
- **`PlateRead`** - License plate reads
- **`Track`** - Object tracking data
- **`DwellTimeRecord`** (`models/dwell_time.py`) - Dwell time records
- **`PackageEvent`** - Package detection events
- **`Summary`** - Event summaries
- **`CameraCalibration`** - Camera calibration data

### Integrations

- **`OutboundWebhook`** - Outbound webhook configuration
- **`Property`** - Property definitions

### Supporting

- **`enums.py`** - Shared enum definitions (severity levels, statuses, etc.)

## API Routes (`api/routes/`)

See `api/routes/AGENTS.md` for detailed documentation. The API layer contains 60 route modules.

### Core Domain Routes

| Route           | Prefix            | Description                                        |
| --------------- | ----------------- | -------------------------------------------------- |
| `cameras.py`    | `/api/cameras`    | Camera CRUD, status, and configuration             |
| `detections.py` | `/api/detections` | Detection queries with filtering and pagination    |
| `events.py`     | `/api/events`     | Event management, review workflow, bulk operations |
| `zones.py`      | `/api/cameras`    | Zone management for camera areas                   |
| `entities.py`   | `/api/entities`   | Entity tracking (people, vehicles)                 |
| `tracks.py`     | `/api/tracks`     | Object tracking data                               |

### AI and Analysis Routes

| Route                   | Prefix                                   | Description                               |
| ----------------------- | ---------------------------------------- | ----------------------------------------- |
| `ai_audit.py`           | `/api/ai-audit`                          | AI pipeline audit and performance metrics |
| `prompt_management.py`  | `/api/prompts`                           | LLM prompt version management             |
| `analytics.py`          | `/api/analytics`                         | Detection and event analytics             |
| `analytics_zones.py`    | `/api/analytics-zones`                   | Analytics zone configuration              |
| `calibration.py`        | `/api/calibration`                       | Detection calibration settings            |
| `cost_analytics.py`     | `/api/analytics/costs`                   | AI inference cost analytics               |
| `detector.py`           | `/system/detectors`                      | Detector configuration                    |
| `entity_recognition.py` | `/api/summaries/entities`                | Entity recognition operations             |
| `face_recognition.py`   | `/api/known-persons`, `/api/face-events` | Face recognition management               |
| `heatmaps.py`           | `/api/heatmaps`                          | Heatmap generation and queries            |
| `llm_reasoning.py`      | `/api/llm-reasoning`                     | LLM reasoning inspection                  |
| `model_management.py`   | `/api/system/models`                     | AI model management                       |
| `reid.py`               | `/api/reid`                              | Person re-identification                  |
| `summaries.py`          | `/api/summaries`                         | Event summaries                           |
| `trends.py`             | `/api/summaries/trends`                  | Trend analysis                            |

### System and Infrastructure Routes

| Route                   | Prefix                    | Description                               |
| ----------------------- | ------------------------- | ----------------------------------------- |
| `system.py`             | `/api/system`             | Health checks, GPU stats, pipeline status |
| `services.py`           | `/api/system/services`    | Service management and control            |
| `metrics.py`            | `/api/metrics`            | Prometheus metrics endpoint               |
| `dlq.py`                | `/api/dlq`                | Dead-letter queue management              |
| `admin.py`              | `/api/admin`              | Admin operations and cache management     |
| `debug.py`              | `/api/debug`              | Debug endpoints for development           |
| `gpu_config.py`         | `/api/system/gpu-config`  | GPU configuration management              |
| `health_ai_services.py` | `/api/health/ai-services` | AI service health checks                  |
| `hierarchy.py`          | `/api/v1/households`      | Household/property/area hierarchy         |
| `jobs.py`               | `/api/jobs`               | Background job management                 |
| `queues.py`             | `/api/queues`             | Queue status and management               |
| `settings_api.py`       | `/api/v1/settings`        | Application settings API                  |
| `system_settings.py`    | `/api/v1/system-settings` | System-wide settings                      |

### Media and Logging Routes

| Route        | Prefix         | Description                            |
| ------------ | -------------- | -------------------------------------- |
| `media.py`   | `/api/media`   | Secure file serving for images/videos  |
| `logs.py`    | `/api/logs`    | Log queries and frontend log ingestion |
| `rum.py`     | `/api/rum`     | Real User Monitoring data collection   |
| `exports.py` | `/api/exports` | Data export management                 |

### Notification and Alerting Routes

| Route                         | Prefix                          | Description                                       |
| ----------------------------- | ------------------------------- | ------------------------------------------------- |
| `alertmanager.py`             | `/api/v1/alertmanager`          | Alertmanager integration                          |
| `alert_service.py`            | `/api/alert-service`            | Alert service operations                          |
| `alerts.py`                   | `/api/alerts/rules`             | Alert rule CRUD and evaluation                    |
| `alerts.py`                   | `/api/alerts`                   | Alert instance queries (`alerts_instance_router`) |
| `notification.py`             | `/api/notification`             | Notification channel management                   |
| `notification_preferences.py` | `/api/notification-preferences` | User notification preferences                     |
| `scheduled_reports.py`        | `/api/scheduled-reports`        | Scheduled report management                       |

### Security and Compliance Routes

| Route         | Prefix          | Description             |
| ------------- | --------------- | ----------------------- |
| `auth.py`     | `/api/auth`     | Authentication          |
| `audit.py`    | `/api/audit`    | Security audit logging  |
| `feedback.py` | `/api/feedback` | User feedback on events |

### Household and Zone Routes

| Route                  | Prefix                           | Description                   |
| ---------------------- | -------------------------------- | ----------------------------- |
| `household.py`         | `/api/household`                 | Household management          |
| `household_matcher.py` | `/api/household-matcher`         | Household matching operations |
| `plate_reads.py`       | `/api/plate-reads`               | License plate read queries    |
| `zone_anomalies.py`    | `/api/zones/anomalies`           | Zone anomaly detection        |
| `zone_household.py`    | `/api/zones/{zone_id}/household` | Zone-household configuration  |

### Integration Routes

| Route                  | Prefix                           | Description                    |
| ---------------------- | -------------------------------- | ------------------------------ |
| `backup.py`            | `/api/backup`                    | Backup management              |
| `inbound_webhooks.py`  | `/api/webhooks/inbound`          | Inbound webhook handlers       |
| `mqtt_config.py`       | `/api/mqtt-config`               | MQTT configuration             |
| `onvif.py`             | `/api/cameras/{camera_id}/onvif` | ONVIF camera discovery/control |
| `outbound_webhooks.py` | `/api/outbound-webhooks`         | Outbound webhook configuration |
| `webhooks.py`          | `/api/webhooks`                  | Webhook management             |
| `action_events.py`     | `/api/action-events`             | Action event management        |

### Real-time Routes

| Route          | Prefix | Description                     |
| -------------- | ------ | ------------------------------- |
| `websocket.py` | `/ws`  | WebSocket real-time connections |

## API Middleware (`api/middleware/`)

The middleware layer contains 23 components for request processing:

| Middleware                  | Purpose                                           |
| --------------------------- | ------------------------------------------------- |
| `accept_header.py`          | Accept header parsing and validation              |
| `auth.py`                   | API key authentication                            |
| `baggage.py`                | Context propagation (W3C Baggage)                 |
| `body_limit.py`             | Request body size limiting                        |
| `content_negotiation.py`    | Content negotiation handling                      |
| `content_type_validator.py` | Content-Type validation                           |
| `correlation.py`            | Correlation ID for distributed tracing            |
| `deprecation.py`            | API deprecation handling                          |
| `deprecation_logger.py`     | Deprecated endpoint logging                       |
| `error_handler.py`          | Error response formatting                         |
| `etag.py`                   | ETag support for conditional requests             |
| `exception_handler.py`      | Global exception handling with RFC 7807           |
| `file_validator.py`         | File upload validation                            |
| `idempotency.py`            | Idempotency key handling                          |
| `profiling.py`              | Request profiling                                 |
| `prometheus.py`             | Prometheus metrics collection                     |
| `rate_limit.py`             | Request rate limiting                             |
| `request_id.py`             | Request ID generation and propagation             |
| `request_recorder.py`       | Request recording for debugging                   |
| `security_headers.py`       | Security headers (CSP, HSTS, etc.)                |
| `observability.py`          | Unified timing + logging + Prometheus metrics     |
| `setup_guard.py`            | Blocks API access until first admin is registered |
| `websocket_auth.py`         | WebSocket authentication                          |

## API Schemas (`api/schemas/`)

The schema layer contains 86 Pydantic schema modules for request/response validation (load-bearing examples below; full list in `api/schemas/AGENTS.md`):

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

- **`alert_repository.py`** - Alert rule queries
- **`camera_repository.py`** - Camera-specific queries
- **`detection_repository.py`** - Detection-specific queries
- **`entity_repository.py`** - Entity tracking queries
- **`event_repository.py`** - Event-specific queries
- **`summary_repository.py`** - Summary queries
- **`zone_repository.py`** - Zone queries

## Services (`services/`)

See `services/AGENTS.md` for detailed documentation. The service layer contains 177 modules (including the orchestrator and data subsystems) organized by function.

### Core AI Pipeline

| Service                  | Purpose                                                                         |
| ------------------------ | ------------------------------------------------------------------------------- |
| `file_watcher.py`        | Monitors camera directories for new uploads                                     |
| `detector_client.py`     | YOLO26 HTTP client for object detection                                         |
| `batch_aggregator.py`    | Groups detections into time-based batches                                       |
| `pipeline_factory.py`    | Builds the analyzer; `build_pipeline_analyzer` returns VlmAnalyzer              |
| `vlm_analyzer.py`        | VLM risk analysis via the `ai-vlm` engine (model identity is config, ledger D5) |
| `vlm_client.py`          | llama.cpp transport (`POST /v1/chat/completions`) + the one retry               |
| `vlm_specialists.py`     | Face / plate / re-ID text legs rendered into the VLM prompt                     |
| `thumbnail_generator.py` | Detection visualization with bounding boxes                                     |
| `dedupe.py`              | File deduplication using content hashes                                         |

R8 S2 (2026-09-29) deleted the legacy analyzer tier — `nemotron_analyzer.py`,
`nemotron_streaming.py` and `vision_extractor.py` are gone, and
`config.py` hard-raises on `pipeline_mode: legacy`, so there is no second
analysis path to document here.

### AI Model Loaders (Lazy Loading)

| Service                     | Model                                                 |
| --------------------------- | ----------------------------------------------------- |
| `osnet_loader.py`           | OSNet-AIN x1.0 person re-ID embeddings                |
| `face_recognizer_loader.py` | SCRFD face detector + ArcFace embedder (buffalo_l)    |
| `fast_alpr_loader.py`       | FastALPR end-to-end plate detection + OCR             |
| `model_loader_base.py`      | Base class for model loaders                          |
| `model_zoo.py`              | Model registry and management (registry = models.yml) |

This table once listed nineteen rows. Only its last two survive — the seventeen
above them are deleted, fifteen in R8 S2 (2026-09-29): `clip_loader.py`,
`florence_loader.py`, `florence_extractor.py`, `depth_anything_loader.py`,
`segformer_loader.py`, `vitpose_loader.py`, `yolo_world_loader.py`,
`stgcn_loader.py`, `fashion_clip_loader.py`, `pet_classifier_loader.py`,
`vehicle_classifier_loader.py`, `vehicle_damage_loader.py`,
`violence_loader.py`, `weather_loader.py` and `image_quality_loader.py`; the two
thin clients (`clip_client.py`, `florence_client.py`) went in R8 S3 the same day.
The three loaders that joined above — `osnet_loader.py`,
`face_recognizer_loader.py` and `fast_alpr_loader.py` — are the ones
`model_zoo.py`'s `_LOADER_MAP` actually binds today, which is why the old table
never listed them. The X-CLIP chain
(`xclip_loader.py`/`action_recognition_service.py`, including the
`/api/action-events` analyze route it backed) was archived 2026-09-23 to
`archive/xclip-backend-chain/`, and the models.yml rows for the deleted models
were deleted, not flipped to `enabled: false` (R8 S3 owner ruling — provenance
is git history plus the ledger).

### Detection Enrichment Pipeline

| Service               | Purpose                       |
| --------------------- | ----------------------------- |
| `context_enricher.py` | Context-aware enrichment      |
| `face_detector.py`    | Face detection                |
| `plate_detector.py`   | License plate detection       |
| `ocr_service.py`      | Optical character recognition |
| `reid_service.py`     | Person re-identification      |
| `bbox_validation.py`  | Bounding box validation       |

The heavy-perception orchestrator is gone: R8 S2 deleted
`enrichment_pipeline.py` and its `enrichment_client.py` service client. What
reaches the shipped prompt instead is `vlm_specialists.py`, which dials the
three surviving loaders directly (face via `face_recognizer_loader.py`, plate
via `fast_alpr_loader.py`, re-ID via `osnet_loader.py`). The four legs above
survive as the DI-reachable lookup services they always were — wrapped by
`ai_services.py` for the container, with `reid_service.py` behind the
entity/re-ID routes.

### Scene Analysis

| Service                    | Purpose                                                                      |
| -------------------------- | ---------------------------------------------------------------------------- |
| `scene_change_detector.py` | Scene change detection (SSIM against an in-memory baseline image per camera) |
| `baseline.py`              | Activity baseline calculation (count-based EWMA)                             |
| `zone_baseline_service.py` | Zone activity baselines                                                      |

`scene_baseline.py` (the DB-backed image baseline store) was deleted with R8 S3
on 2026-09-29; the SSIM detector keeps its baselines in process memory.

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
                               DetectorClient -> YOLO26 (/yolo26 on ai-gateway)
                                      |
                               Detection (DB)
                                      |
                    ┌─────────────────┴─────────────────┐
             ThumbnailGenerator                  BatchAggregator
                                                           |
                                                    analysis_queue
                                                           |
                                                AnalysisQueueWorker
                                                           |
                                     build_pipeline_analyzer -> VlmAnalyzer
                                                           |
                    [vlm_specialists: Face / Plate / Re-ID lookups]
                                                           |
                                      VlmAnalyzer -> ai-vlm (llama.cpp, 8098)
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

The enrichment fork that used to sit on this diagram (`EnrichmentPipeline` →
CLIP / Florence / face / plate / OCR) is gone: R8 S2 deleted the tier, so the
lookups the shipped prompt actually carries run inside `VlmAnalyzer` through
`vlm_specialists.py`, and the analyzer itself is mode-built
(`pipeline_factory.build_pipeline_analyzer`) rather than named at the call site.

### System Monitoring Flow

```
GPU stats (pynvml) -> GPUMonitor -> GPUStats (DB) -> SystemBroadcaster -> WebSocket

Health checks -> HealthMonitor -> ServiceHealthMonitor -> auto-recovery

Performance -> PerformanceCollector -> Prometheus metrics -> /api/metrics
```

### Background Services Flow

```
Scheduled cleanup -> CleanupService -> Delete old records -> Remove files

Scene analysis -> SceneChangeDetector -> SSIM vs in-memory baseline image -> SceneChangeResult

Activity anomaly -> BaselineService (count-based EWMA per camera/hour)
                   -> ActivityBaseline / ClassBaseline
                   -> ZoneActivityBaseline (zone_baseline_service)

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
├── unit/                  # 27,901 collected unit tests
│   ├── api/               # API route tests
│   ├── core/              # Core infrastructure tests
│   ├── models/            # Model tests
│   ├── services/          # Service tests
│   └── repositories/      # Repository tests
└── integration/           # 4,059 collected integration tests (4 shards)
    ├── api/               # API integration tests
    ├── websocket/         # WebSocket tests
    ├── services/          # Service integration tests
    └── models/            # Model integration tests
```

Both counts are `pytest --collect-only -q` totals on the 2026-09-30 tree, not
run-time pass counts.

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

**Coverage Requirements** (owner ruling A7.1, 2026-09-19):

| Test Type | Number | Role                                                                  |
| --------- | ------ | --------------------------------------------------------------------- |
| Unit      | 85%    | `pyproject.toml` fail_under — PR diff baseline, not an absolute floor |
| Combined  | 80%    | The executed absolute floor (`validate.sh --fail-under=80`)           |

## Environment Variables

Key environment variables (loaded via `.env` file):

```bash
# Database and Redis
DATABASE_URL=postgresql+asyncpg://security:password@localhost:5432/security
REDIS_URL=redis://localhost:6379/0

# Camera configuration
FOSCAM_BASE_PATH=/export/foscam

# AI service endpoints - the ai-gateway container on port 8090 serves ONLY
# /yolo26 and /enrich-lt (R8 S3 pruned the /florence /clip /enrichment router
# mounts on 2026-09-29). The shipped LLM engine is the separate `ai-vlm`
# llama.cpp container, host loopback port 8098 (default compose set).
# Values below match .env.example.
USE_AI_GATEWAY=true
AI_GATEWAY_URL=http://ai-gateway:8090
YOLO26_URL=http://localhost:8090/yolo26
AI_VLM_URL=http://localhost:8098

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

| Path                                | Purpose                                          |
| ----------------------------------- | ------------------------------------------------ |
| `/backend/ai_contract/AGENTS.md`    | AI-tier operation registry (generated)           |
| `/backend/api/AGENTS.md`            | API layer overview                               |
| `/backend/api/routes/AGENTS.md`     | API endpoints (60 routes)                        |
| `/backend/api/schemas/AGENTS.md`    | Pydantic schemas (86 modules)                    |
| `/backend/api/middleware/AGENTS.md` | Middleware components (23 modules)               |
| `/backend/api/utils/AGENTS.md`      | API utility modules                              |
| `/backend/core/AGENTS.md`           | Core infrastructure (54 modules)                 |
| `/backend/config/AGENTS.md`         | Prompt A/B rollout and experiments               |
| `/backend/core/websocket/AGENTS.md` | WebSocket event infrastructure                   |
| `/backend/evaluation/AGENTS.md`     | VLM verdict-path evaluation and replay           |
| `/backend/jobs/AGENTS.md`           | Background job modules                           |
| `/backend/models/AGENTS.md`         | Database models (54 models)                      |
| `/backend/repositories/AGENTS.md`   | Repository pattern (base + 7 repos)              |
| `/backend/services/AGENTS.md`       | Service layer (177 modules)                      |
| `/backend/tests/AGENTS.md`          | Test infrastructure                              |
| `/backend/examples/AGENTS.md`       | Example scripts (Redis usage)                    |
| `/backend/scripts/AGENTS.md`        | Utility scripts (VRAM benchmarking)              |
| `/backend/data/`                    | Runtime data directory (no AGENTS.md - data dir) |

### Project-Level Documentation

| Path                         | Purpose                        |
| ---------------------------- | ------------------------------ |
| `/AGENTS.md`                 | Project-wide instructions      |
| `/docs/developer/testing.md` | Comprehensive testing patterns |
| `/docs/ROADMAP.md`           | Post-MVP enhancements          |
