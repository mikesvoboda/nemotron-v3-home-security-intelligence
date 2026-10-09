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
│   └── websocket/          # WebSocket event infrastructure (9 modules)
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
- Authentication gate (`AuthMiddleware`): login session or API key required when `EXPOSE_LAN=true`
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
  - `inbound_webhooks` - Inbound webhook receivers (all four answer 501 per UR-12)
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
| `inbound_webhooks.py`  | `/api/webhooks/inbound`          | Inbound webhook receivers, 501 |
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

Generic `Repository[T]` (`base.py`) plus seven per-domain subclasses. Every method is
discoverable by reading the class; what is NOT is the transaction semantics (W3.1 batch 7
recovered these from the deleted satellite guide — they had been re-derived three times):

- **A repository never commits.** `create()`/`update()`/`delete()`/`save()`/`merge()` only
  `flush()`; the commit belongs to `core/database.py`'s `get_session()`, which does
  `yield session` then `await session.commit()` on clean exit. Two same-session writers
  cannot see each other's rows mid-request, and an early "rollback won" is an illusion —
  what got undone was the whole `get_session` commit. Test note: `pyproject.toml:544` runs
  pytest `-n 8 --dist=worksteal -p randomly`, so every test's session is its own and order
  is shuffled — anything relying on one test's flush being visible in another is broken
  already.
- **`list_paginated()` caps your `limit` SILENTLY** via `get_max_limit()` (settings
  `PAGINATION_MAX_LIMIT`, fallback `MAX_LIMIT` = 1000): the cap is
  `capped_limit = min(limit, max_limit)`. A short page is not the end of the table.
- **`save()` is a PostgreSQL upsert, and explicit NULL means CLEAR.** It emits
  `insert … on_conflict_do_update` over all non-PK columns (NEM-4473: a column set on the
  instance — even to `None`, when it is present in `__dict__` — rides the UPDATE, so
  clearing a field is what `save()` DOES, not something it loses). On `IntegrityError`
  (unique constraints outside the PK) it falls back to `session.merge()`. `merge()` runs
  inside `begin_nested()` — a savepoint, so its failure rolls back the merge alone.
- **Alert rules: an EMPTY `camera_ids` list means ALL cameras.** A rule applies when
  `camera_ids` is NULL, `== []`, or contains the camera (`alert_repository.py:383-392`).
  "No cameras selected" and "every camera" are the same row. Alert methods also accept the
  enum OR its string value and normalize internally.
- **Embedding search is app-level cosine over JSONB — there is no pgvector index here.**
  `find_by_embedding` compares in Python and applies a PROVENANCE SKIP:
  `_provenance_matches` returns False for a missing `model_id` or the
  `vector_provenance.LEGACY_MODEL_ID` sentinel — the docstring says the match is SKIPPED,
  not scored 0.0, so legacy rows are invisible to searches, not last-ranked. The
  write-side guard is F11: `models/entity.py`'s `from_detection` (via `set_embedding`)
  raises when an embedding arrives without `model_id` (the retired literal would mislabel
  the bytes); a probe that passes no `model_id` compares against nothing.
- **`get_detections_for_entity` ignores its `limit`/`offset`** — both parameters carry
  `# noqa: ARG002`, reserved for future use — and `get_camera_counts` pulls every
  matching entity into Python to group: pagination you pass there does nothing, and the
  count query is not a GROUP BY.
- **Named methods can over-promise.** `camera_repository.py`'s `get_cameras_with_stats`
  fetches NO stats — its body is `select(Camera).order_by(Camera.name)` and its own
  docstring says event/detection counts must come from separate aggregate queries (the
  collections are deliberately not eager-loaded).
- **`event_repository.py` lazy-load landmine:** the `eager_load_camera=True` kwarg exists
  only on some methods. The default False path leaves `event.camera` unloaded, and touching
  it in async code raises `MissingGreenlet` — an await inside a template/format, not at the
  query. `zone_repository.py` names `Zone`/`ZoneType` as aliases of `CameraZone`/
  `CameraZoneType` (:25-27); `get_by_type()` is GLOBAL — the camera-scoped method is
  `get_by_camera_and_type()`.

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

| Path                                | Purpose                                                                      |
| ----------------------------------- | ---------------------------------------------------------------------------- |
| `/backend/ai_contract/AGENTS.md`    | AI-tier operation registry (generated)                                       |
| `/backend/api/AGENTS.md`            | API layer overview                                                           |
| `/backend/api/routes/AGENTS.md`     | API endpoints (60 routes)                                                    |
| `/backend/api/schemas/AGENTS.md`    | Pydantic schemas (86 modules)                                                |
| `/backend/api/middleware/AGENTS.md` | Middleware components (23 modules)                                           |
| `/backend/core/AGENTS.md`           | Core infrastructure (54 modules)                                             |
| `/backend/models/AGENTS.md`         | Database models (54 models)                                                  |
| `/backend/services/AGENTS.md`       | Service layer (177 modules)                                                  |
| this file, "The test tree" appendix | Test infrastructure (W3.1 pruned the per-directory guides)                   |
| this file, "Batch 7" appendix below | Repositories · jobs · config · examples · scripts (W3.1 pruned their guides) |
| `/backend/data/`                    | Runtime data directory (no AGENTS.md - data dir)                             |

### Project-Level Documentation

| Path                         | Purpose                        |
| ---------------------------- | ------------------------------ |
| `/AGENTS.md`                 | Project-wide instructions      |
| `/docs/developer/testing.md` | Comprehensive testing patterns |
| `/docs/ROADMAP.md`           | Post-MVP enhancements          |

## The test tree (W3.1 appendix, batch 6)

The per-directory guides under `backend/tests/` are deleted (45 files). This section carries
their non-discoverable rules — every line below was re-verified against the code at this commit,
and where a guide contradicted the code the code's value is printed. The old parent guide at
backend/tests/AGENTS.md was a zero-byte file: five sibling guides cited it as "the overview"
and it said nothing — the shared machinery is stated here directly instead.

### Shared machinery

- `backend/tests/conftest.py` is the shared root: `ENVIRONMENT=test`, autouse
  `reset_settings_cache`, `unique_id(prefix)` for parallel-safe ids, stale-test-database cleanup.
  The `session` / `isolated_db_session` fixtures live in `backend/tests/integration/conftest.py`
  (`session` wraps `isolated_db_session`); a unit test requesting `session` will not resolve it.
- Two error envelopes ship and keep shipping: legacy `{"detail": "..."}` and structured
  `{"error": {"code", "message", "errors": [...]}}` (RFC 7807 handlers in
  `backend/api/exception_handlers.py`). Tests go through `get_error_message()` / `has_error()`
  in `backend/tests/integration/test_helpers.py` — never hand-parse, so a contract change is a
  one-file fix. Trap: `backend/tests/unit/integration/` holds _unit_ tests of those
  _integration-tree_ helpers — moving `test_helpers.py` breaks a directory nothing predicts.

### Runner canon

- Run tests with `uv run pytest`. `pyproject.toml` `addopts` silently adds
  `-n 8 --dist=worksteal -p randomly --strict-markers -m 'not gpu'` with `timeout = 5`; a bare
  invocation outside the repo config runs a different suite. `asyncio_mode = "auto"` — the
  `@pytest.mark.asyncio` decorator is not needed (several guides said "always"; false).
- The 5s timeout times setup and teardown too (`timeout_func_only = false`, set explicitly after
  an owner ruling — see the pyproject comment): never sleep for real
  in a test — inject a fake clock/sleep. See the pre-import rationale in
  `backend/tests/unit/synthbench/conftest.py` (first test on each worker paid a 2.3s import
  inside its budget).
- Hypothesis profiles are registered **in code** in `backend/tests/conftest.py` and selected by
  `HYPOTHESIS_PROFILE`; the `[tool.hypothesis.profiles.*]` tables in `pyproject.toml` are read
  by nothing — do not "fix" a profile by editing them.
- Settings are cached process-wide: env-mutating tests need the cache cleared (`reset_settings_cache`
  is autouse; the manual escape hatch is `get_settings.cache_clear()`) and the app must be
  imported **after** env setup or fixtures silently use stale settings.

### What CI collects (the guides were silent; verified at this commit)

- `.github/workflows/nightly-full-gate.yml` collects `backend/tests/unit`, `backend/tests/contracts`
  and `backend/tests/security`, and `--ignore`s `load`, `benchmarks`, `e2e`, `chaos`.
  `.github/workflows/benchmarks.yml` runs `backend/tests/benchmarks/` via pytest-benchmark,
  failing on >20% mean regression from a saved baseline. NO workflow collects
  `backend/tests/gpu/` (the old gpu workflow was deleted); `-m 'not gpu'` excludes gpu-marked
  nodes everywhere, including the gpu tests inside `backend/tests/e2e/test_gpu_pipeline.py`.
- Skip-not-fail suites lie green: gpu (no hardware → all skip) and `backend/tests/benchmarks/` (optional
  `memray`/`big-o` absent → skipif) can pass while measuring nothing. Judge by skip counts.
- There are TWO `test_performance.py` files: `backend/tests/benchmarks/` (pytest-benchmark
  regression tracking) and `backend/tests/load/` (feature-SLO checks whose memory assertions are
  `frame_count × ~100KB` **arithmetic** and whose p99 is hand-rolled over 100 samples — the
  verdict rides on stated assumptions, not measurements).

### Unit tier (`backend/tests/unit/`)

- `mock_session`, `clean_env`, `sample_detections`, `temp_camera_root` are NOT global fixtures —
  each is defined locally in dozens of files. Copy the fixture; do not request it.
- Mocked-session contract: `session.add` is a **sync** MagicMock while
  `commit`/`flush`/`refresh`/`execute` are AsyncMock; result stubs chain through
  `execute.return_value` → `scalars().all()`. `get_by_id` on a missing row returns None (it
  calls `session.get` — mock that, not `execute().scalar_one_or_none()`).
- Patch in the module's OWN namespace (`patch("backend.api.routes.cameras.get_db")` — the route
  module imported the symbol); for FastAPI DI the shipped idiom is
  `app.dependency_overrides[get_db]` keyed by `backend.core.database.get_db`.
- Route tests live in TWO sibling directories, `backend/tests/unit/routes/` and
  `backend/tests/unit/api/routes/`, with no tree rule for which takes a new test — and
  `test_events_routes.py` exists in BOTH. New test → join the endpoint's existing siblings.
- Same-name-different-suite traps: `backend/tests/unit/middleware/` covers
  `backend/core/logging.py`, while `backend/tests/unit/api/middleware/` covers
  `backend/api/middleware/*`; `backend/tests/unit/integration/` is unit tests, not the
  integration tier.
- Retired surfaces stay absent **by test**: `test_enrichment_transformers_retired.py` locks the
  dead-twin `backend.api.helpers` package out of existence; `test_materialized_views_retired.py` locks the
  phantom materialized-view admin surface. A red here means something resurrected a dead
  module — delete it, never re-create the surface to go green.
- NEM-5558 deleted `RequestTimingMiddleware`/`RequestLoggingMiddleware` (modules AND tests);
  their coverage re-homed to `TestRequestLogFormatting` in
  `backend/tests/unit/api/middleware/test_observability.py`. Chain-order, `X-Response-Time`
  and slow-request logging are pinned ONLY by `backend/tests/integration/test_middleware_chain.py`
  — a unit-only run proves nothing about ordering.
- Correlation IDs: a client-supplied `X-Correlation-ID` is echoed **verbatim, unvalidated**
  (`backend/api/middleware/request_id.py`) — do not "improve" this; the UUID check applies only
  to generated IDs, and the contextvar set/reset around the request is the leak guard. This
  suite is the sole pin for several wire specs (RFC 8594 Sunset, W3C Baggage, ETag,
  Idempotency-Key replay, rate-limit **proxy trust**, upload magic-numbers).
- Secret-looking fixture literals need a trailing `# pragma: allowlist secret` or the
  detect-secrets hook blocks the commit with no hint why (repo-wide convention — the
  pragmas live in `backend/tests/security/conftest.py`, the root conftest, and more).
- Source-text guards (`backend/tests/unit/frontend/` and the R8 siblings in the unit root):
  pins, not greps — assert on LIVE forms only (import specifiers, JSX elements, `data-testid`)
  with **comments stripped** so a retirement docblock cannot fail the file, and every scan
  carries its own non-vacuity witness (the import-resolution pin requires >2000 resolved
  specifiers; an empty scan would pass a naive check).
- `backend/config/` singletons: autouse-reset ALL of them before and after every test — the
  `reset_*` functions there (four today) — or A/B state leaks across tests. Two validation
  messages are pinned by substring (`"between 0.0 and 1.0"`, `"must be positive"`): rewording
  the ValueError breaks tests. Camera→PromptVersion assignment is hash-deterministic; swapping
  the hash silently re-aims the distribution band a 1000-camera test asserts.
- `backend/tests/unit/synthbench/`: `gpu_window()` in `synthbench/generate/window.py` **stops
  real GPU containers by default** — tests must inject `before_restore`. These tests live here,
  not under `synthbench/`, because CI collects `backend/tests/unit/` — do not "tidy" them into
  the lane. In the spikes tier, `synthbench/spikes/p1_bakeoff/measure.py` and
  `synthbench/spikes/p1_bakeoff/cases.py` must stay Python 3.12-parseable (they run inside the
  renderer image; `backend/tests/unit/synthbench/spikes/test_p1_py312.py` enforces it).

### Integration tier (`backend/tests/integration/`)

- Real Postgres (testcontainers **or** local service) plus a real Redis container for the DB
  suites, with per-worker isolation: each xdist worker owns database `security_test_gw<N>`, and
  Redis DB index gw0–gw14 → 0–14 with **master → 15** — a 16th worker would collide. Tests that
  do not need real Redis use the `mock_redis` double instead; both patterns coexist on purpose.
- The `client` fixture DELETEs all tables before AND after each test (DELETE, not TRUNCATE —
  it avoids table locks) in a dynamically computed FK-safe topological order (parents last — do
  not hardcode a table list). Standalone `db_session` does NOT clean up: request
  `isolated_db_session` when a test skips `client`.
- Cascade tests must issue an explicit `delete(Camera)` statement — an ORM
  `session.delete(obj)` never reaches the DB-level `ON DELETE CASCADE`, so the assertion would
  pass for the wrong reason.
- Deadlock handling catches `(OperationalError, DBAPIError)` together (deadlock surfaces as the
  subclass); `session.expire_all()` is required between two reads that must observe committed
  state, or the identity map returns a cached row and isolation tests report false stability.
- `setup_explain_logging()` takes `engine.sync_engine` — the event hooks are sync-only, so the
  async engine attaches nothing and the test passes while measuring nothing.

### Contracts tier (`backend/tests/contracts/`)

- **No xfail / skip / importorskip anywhere in the tier** (goal rule): a ruling-blocked finding
  becomes a characterization test, and an absence assertion is a GREEN GUARD — never "fix" one
  by adding a skip.
- **Never respx**: the fake provider is a real ASGI app
  (`backend/ai_contract/fake/app.py`) and every hop is `httpx.ASGITransport`.
- `backend/tests/contracts/ai_providers/golden/` is GENERATED by `scripts/gen-ai-contract.py` — regenerate, never hand-edit; the
  `api-types-check` CI job fails on drift. Conformance tests import the golden payloads
  verbatim instead of hand-writing dicts.

### Host-bound tiers (where the guides were most stale — code values printed)

- `backend/tests/gpu/`: explicit invocation only (`uv run pytest backend/tests/gpu/ -v -m gpu`).
  Everything SKIPS (never fails) when the services/hardware are absent. Default URLs in
  `backend/tests/gpu/test_detector_integration.py`: `YOLO26_URL` → `http://localhost:8090`
  (one guide printed 8095 — the code says 8090) and `NEMOTRON_URL` → `http://localhost:8091`;
  the localhost defaults only work when pytest runs ON the GPU host. There is no
  `--ignore-missing-gpu` pytest flag — a guide invented it.
- `backend/tests/chaos/`: NO fault-injection framework exists (the old one was deleted) — files
  inject `unittest.mock` side-effects around the real resilience singletons, and every module
  autouse-resets `reset_circuit_breaker_registry()` / `reset_degradation_manager()`.
  `test_worker_chaos.py` forces `use_redis_streams=False` via its autouse fixture: do NOT
  re-enable Streams against the LIST-only mock — an empty `xreadgroup` reply hits the
  consumer's un-slept `continue` and HANGS. The directory is excluded from every gate by the
  pre-approved conditional in `scripts/validate.sh` (R-T7-POISON-CASCADE); one guide claimed it
  now runs green under xdist — the recorded hang says otherwise.
- `backend/tests/e2e/`: real business logic + real Postgres; ONLY the external AI HTTP services
  and Redis are mocked. httpx mock responses: `.json()` must be a **MagicMock**, not an
  AsyncMock, or the run drowns in "coroutine was never awaited".
- `backend/tests/security/`: dir-local `conftest.py` supplies `security_client` and the key
  fixtures. Auth contract: API keys are SHA-256 digested and compared with
  `hmac.compare_digest` (constant-time), and a key never appears in an error response. The
  keyless-path truth is `OPEN_PATHS` in `backend/api/middleware/auth.py` — read it; a guide's
  five-path list is already stale. `EXPOSE_LAN` is deliberately NOT covered here: it is pinned
  in `backend/tests/unit/api/middleware/` and, across every mounted route, by
  `backend/tests/unit/api/test_expose_lan_routes.py`.
- `backend/tests/fixtures/compose-render.env` is the minimal FAKE env that makes
  `docker-compose.prod.yml` render on any box (exactly two hard-required `${VAR:?}` vars) so
  the O1.3 evidence test `backend/tests/unit/core/test_compose_render_lists_ai_vlm.py` is
  reproducible — it is test evidence, never a deployment env.

## The backend satellites (W3.1 appendix, batch 7)

The remaining per-directory guides under `backend/` are deleted (11 files). This section carries
the non-discoverable rules for the six whose nearest boundary is this file; the other five live
where their code does — `services/orchestrator/` → "Container orchestration types" in
`backend/services/AGENTS.md`, `api/utils/` → the sparse-fieldsets section in
`backend/api/AGENTS.md`, `core/websocket/` → its section in `backend/core/AGENTS.md` (the
`core/middleware` guide documented a directory containing only the guide — nothing to route),
`ai_contract/fake/` → the FakeProvider section in `backend/ai_contract/AGENTS.md`. Every line
below was re-verified against the code at this commit.

### `backend/repositories/` — the data-access layer

- Nine files: `__init__.py`, `base.py`, seven repository modules — the old "base + 7 repos" was
  accurate; the wrinkle is `alert_repository.py`, which defines BOTH `AlertRepository` and
  `AlertRuleRepository` (eight repository classes).
- `Repository[T: Base]` needs the `model_class` class attribute. Fourteen base methods — the
  old guide's table missed `list_paginated`, `create_many`, `delete_by_id`, `merge`, `save`.
- `save()` is a PostgreSQL `INSERT ... ON CONFLICT DO UPDATE` upsert inside a savepoint, and
  `merge()` re-attaches DETACHED entities, also savepoint-wrapped (NEM-2566). The race-safe
  upsert is `save()` — never an exists-check plus create.
- Repositories flush, never commit: `get_session()` in `backend/core/database.py` commits on a
  clean block exit and rolls back on exception, so two repositories sharing one
  `async with get_session()` ARE one transaction.
- `EntityRepository.find_by_embedding` is application-layer cosine similarity over JSONB-stored
  vectors — there is no pgvector; the deleted guide's suggestion to add it is aspirational. Its
  F11 provenance guard (`_provenance_matches`) SKIPS rather than scores: a stored embedding is
  comparable only when its `model` names the probe's weights, and a row that never named its
  producer — or a probe with no `model_id` — compares against nothing. The retired behavior
  ran foreign rows through `_cosine_similarity`'s silent dimension pass and reported "no
  match" for what was really "no comparison possible".
- Tests use the root `conftest.py`'s `isolated_db` fixture; see the test-tree appendix above.

### `backend/jobs/` — three singleton jobs

- Every module pairs a `get_*()` with a `reset_*()` singleton; the reset exists for tests.
  All three `get_*()`s are FIRST-CALL-WINS (`if _singleton is None:`) — arguments passed to a
  later call are silently ignored while an earlier instance lives. A test that constructs
  via `get_summary_job_scheduler(interval_minutes=1)` pins the interval for everything
  later in the process unless it calls the `reset_*()` first.
- `OrphanCleanupJob` is safe by DEFAULT — `dry_run=True`, 24 h minimum age, a 10 GB per-run
  deletion cap, known image/video patterns only — but **its scheduler is not**:
  `OrphanCleanupScheduler` runs the SAME job with `dry_run=False`
  (`orphan_cleanup_job.py:132` default True vs `:339` the scheduler's False), so anything
  that starts the scheduler deletes for real. Nothing in production does —
  `get_orphan_cleanup_scheduler()` and the class have zero non-test callers; only the job's
  own defaults are live-reviewed. The settings trio: `orphan_cleanup_enabled`,
  `orphan_cleanup_scan_interval_hours`, `orphan_cleanup_age_threshold_hours`.
- `SummaryJob` runs EVERY 60 MINUTES — `backend/main.py:1082` constructs the scheduler with
  `interval_minutes=60` (the deleted guide's "every 5 minutes" matches no code — and the
  scheduler's own `__init__` docstring STILL says "Default: 5 minutes" while
  `DEFAULT_INTERVAL_MINUTES` = 60; trust the constant, which is where the deleted guide's
  number probably came from). 180-second per-run timeout (`DEFAULT_TIMEOUT_SECONDS` = 180,
  not the guide's 60). It invalidates `summaries:latest`, `summaries:hourly`,
  `summaries:daily` — but cache-invalidation and the WebSocket broadcast are each gated on a
  constructor-injected client (`summary_job.py:227` `if self._redis_client is not None`,
  `:235` `if self._broadcaster is not None`). Production gets both (`main.py` passes
  `redis_client` + `broadcaster`; the scheduler builds a fresh job per run and forwards
  them), so a bare `SummaryJob()` in a test or ad-hoc script runs the whole summary and
  invalidates NOTHING, silently.
- `TimeoutCheckerJob` polls every 30 s and is **NOT WIRED**: zero non-test references to it
  exist outside `backend/jobs/` and `backend/main.py` never imports it, so no job timeout is
  ever checked in the running app. Its singleton pair exists for tests; wiring it is a code
  change. (The deleted guide's startup/shutdown example was fiction. This row repeated it until
  the batch-7 reader audit caught the omission.)

### `backend/config/` — the prompt-A/B stack is UNWIRED

- Measured at this commit: nothing outside `backend/config/` imports it — no route, no service,
  no `backend/main.py`. The rollout/shadow/experiment classes are complete, tested, and
  DORMANT. Do not assume a prompt experiment is running because this package exists.
- Camera→group assignment uses the builtin `hash()` (`backend/config/prompt_experiment.py:125`),
  which Python randomizes per process via PYTHONHASHSEED — and the repo pins PYTHONHASHSEED
  nowhere. The code comment claiming the assignment is "deterministic" is FALSE across
  restarts: group membership is stable within one process only.
- `get_rollout_manager()` is NOT a lazy singleton — it returns `None` until
  `configure_rollout_manager()` has run. The deleted guide's usage snippet AttributeErrors.
- Auto-rollback defaults: latency +50 %, FP rate +5 %, error rate +5 %, at 100 FEEDBACK
  submissions per arm (`prompt_ab_rollout.py:571-572` gates on `total_feedback_count` only —
  recording analyses never satisfies the gate, so an analysis-only experiment reports
  "Insufficient samples" forever and cannot roll back)
  (`backend/config/prompt_experiment.py:90`, `backend/config/ab_rollout_production.py:73-83`);
  the production profile is a 50/50 split for 48 hours (`backend/config/ab_rollout_production.py:62-66`).
  `PromptExperiment.traffic_split` defaults to 0.1.

### `backend/examples/` — one runnable file

- `redis_example.py` is the entire directory (plus an empty `__init__.py`). It is a live smoke
  demo against a real Redis (`python -m backend.examples.redis_example`), not doc snippets. The
  client contracts it exercises — `health_check()` never raising, the BLPOP 5-second floor —
  are pinned in `backend/core/AGENTS.md`.

### `backend/scripts/` — three assets, one of them runtime code

- `sliding_window_rate_limit.lua` is the app's only Lua asset and it is LOAD-BEARING RUNTIME
  CODE: `backend/api/middleware/rate_limit.py` reads it at import time via `_LUA_SCRIPT_PATH`.
  Never prune it with the "examples-ish" sweep.
- `init_schema.py` creates tables straight from the SQLAlchemy models, BYPASSING Alembic; the
  NEM-4482 guard refuses to run against production without `--force`.
- `benchmark_vram.py` measures SERIAL deltas from one baseline — load one model, then unload it
  (`del`, `gc.collect()`, `torch.cuda.empty_cache()`). Its report's "Total VRAM (all models)"
  is a sum of independent measurements, NOT a simultaneous footprint. The deleted guide's
  sample-output model names were synthetic and name no registry entry.

### `backend/evaluation/` — the VLM verdict-path evaluation

- The band table's DEFINITION OF RECORD is the frontend's `RISK_THRESHOLDS`
  (`frontend/src/utils/risk.ts:80`): low 0-29, medium 30-59, high 60-84, critical 85-100.
  `levels.py`'s own docstring: the moment it re-spells the table it has created a second
  definition — three places, one truth, with `test_levels.py` AST-pinning `levels.py` to the
  TS source.
- Out-of-range scores are NOT clamped, on purpose: an out-of-range score is a bug and must stay
  visible.
- The Wilson interval hand-codes z = 1.959963984540054 and deliberately does not import scipy
  (`backend/evaluation/s_metrics.py`); intervals are checked against HAND-COMPUTED values.
- Corpus items share scenarios, so per-item Wilson assumes an independence they do not have:
  use the scenario-cluster bootstrap (`DEFAULT_RESAMPLES` = 10 000, fixed `DEFAULT_SEED` =
  20261006); the paired comparison is `cluster_bootstrap_diff`, never `mcnemar_exact` alone;
  an empty population is never 0 % — it is the full-width `[0.0, 100.0]` band; and
  `noise_floor` refuses to quote a noise figure from a single run.
- A gen-2 eval-store build INSIDE the repo checkout is refused outright
  (`backend/evaluation/eval_store.py:742-748`) — the store is off-repo by ruling D10/F6.
