# Backend Services Directory

## Purpose

This directory contains the core business logic and background services for the AI-powered home security monitoring system. Services orchestrate the complete detection pipeline from file monitoring through AI analysis to event creation, along with context enrichment, re-identification, and model zoo management.

## Architecture Overview

The services implement a multi-stage async pipeline with real-time broadcasting and background maintenance:

```
File Upload -> Detection -> Batching -> Specialists -> Analysis -> Event Creation -> Broadcasting
   (1)          (2)         (3)            (4)           (5)          (6)              (7)

                     Monitoring Services (Parallel)
                     ├── GPUMonitor (polls GPU stats)
                     ├── SystemBroadcaster (system status)
                     ├── HealthMonitor (service recovery)
                     ├── CleanupService (retention policy)
                     ├── PerformanceCollector (metrics aggregation)
                     └── BackgroundEvaluator (AI audit evaluation)
```

### Service Categories

1. **Core AI Pipeline** - File watching, detection, batching, VLM analysis, streaming
2. **VLM Analysis Path** - `vlm_client` (the `vlm_assess` transport), `vlm_analyzer` (the analysis entry point), `vlm_verdict` (contract models), `vlm_specialists` (faces/plates/person-re-ID texts)
3. **AI Services** - DI wrappers for face/plate detection services
4. **Context Enrichment** - Zone detection, baseline tracking, re-identification
5. **Person Re-identification** - OSNet-AIN x1.0 embedding clustering, hybrid storage bridge
6. **Model Zoo** - On-demand model loading for the lookup legs (plates, faces, embeddings, OCR)
7. **Model Loaders** - Individual model loading functions for Model Zoo
8. **Model Loader Base** - Abstract base class for model loaders
9. **Pipeline Workers** - Background queue consumers and managers
10. **Background Services** - GPU monitoring, cleanup, health checks, worker supervision
11. **Container Orchestrator** - Container discovery, lifecycle management
12. **Infrastructure** - Circuit breakers, retry handlers, degradation, fallback
13. **Alerting** - Alert rules, deduplication, notifications, filtering, CRUD
14. **Audit** - Security audit logging, AI pipeline auditing
15. **Prompt Management** - LLM prompt templates, storage, versioning, type-safety
16. **Utility** - Search, severity mapping, token counting, batch fetching, cost tracking
17. **Data Management** - Partition management for time-series tables
18. **Camera Services** - Camera status updates with concurrency control
19. **Event Services** - Event CRUD, cascade soft delete, export generation
20. **File Services** - Scheduled deletion, cleanup, orphan scanning
21. **Job Services** - Job lifecycle, status tracking, timeout handling, history
22. **Calibration Services** - Adaptive threshold adjustment from feedback
23. **Queue Status** - Queue depth and health monitoring
24. **Transcoding** - Video transcoding with caching and NVENC support
25. **WebSocket** - Centralized event emission service
26. **Monitoring** - Prometheus/Grafana stack validation

## Service Files Overview

### Core AI Pipeline Services

| Service                  | Purpose                                                                     | Exported via `__init__.py` |
| ------------------------ | --------------------------------------------------------------------------- | -------------------------- |
| `file_watcher.py`        | Monitor camera directories for media uploads                                | Yes                        |
| `dedupe.py`              | Prevent duplicate file processing                                           | Yes                        |
| `detector_client.py`     | Send images to YOLO26v2 for detection                                       | Yes                        |
| `batch_aggregator.py`    | Group detections into time-based batches                                    | Yes                        |
| `capture_time.py`        | Foscam filename → capture time for the VLM's time context (CAMERA_TIMEZONE) | No (import directly)       |
| `vlm_analyzer.py`        | The shipped analysis entry point: one `vlm_assess` call per batch           | No (import directly)       |
| `vlm_client.py`          | The ONLY backend caller of the llama.cpp VLM server                         | No (import directly)       |
| `vlm_verdict.py`         | `vlm_assess` contract models (schema source of truth)                       | No (import directly)       |
| `vlm_specialists.py`     | faces/plates/person_reid texts fed into the verdict                         | No (import directly)       |
| `thumbnail_generator.py` | Generate preview images with bounding boxes                                 | Yes                        |
| `video_processor.py`     | Extract video metadata and thumbnails                                       | No (import directly)       |
| `event_broadcaster.py`   | Distribute events via WebSocket                                             | Yes                        |

### Context Enrichment Services

| Service                    | Purpose                                          | Exported via `__init__.py` |
| -------------------------- | ------------------------------------------------ | -------------------------- |
| `context_enricher.py`      | Aggregate context from zones, baselines, reid    | Yes                        |
| `zone_service.py`          | Zone detection and context generation            | Yes                        |
| `baseline.py`              | Activity baseline tracking for anomaly detection | Yes                        |
| `scene_change_detector.py` | SSIM-based scene change detection                | Yes                        |
| `reid_service.py`          | Person re-identification across cameras          | Yes                        |
| `reid_matcher.py`          | Person re-ID matching across detections          | No (import directly)       |
| `bbox_validation.py`       | Bounding box validation utilities                | No (import directly)       |

### Model Zoo Services

| Service        | Purpose                                      | Exported via `__init__.py` |
| -------------- | -------------------------------------------- | -------------------------- |
| `model_zoo.py` | Registry and manager for on-demand AI models | Yes                        |

### Model Loader Services

The zoo's loader set is what `model_zoo.py`'s `_LOADER_MAP` binds — one generic
YOLO loader plus the resident specialist loaders:

| Service                     | Purpose                                                             | Exported via `__init__.py` |
| --------------------------- | ------------------------------------------------------------------- | -------------------------- |
| `osnet_loader.py`           | Load OSNet-AIN x1.0 person re-ID embeddings                         | No (import directly)       |
| `face_recognizer_loader.py` | Load the SCRFD face detector + ArcFace recognizer (CPU onnxruntime) | No (import directly)       |
| `fast_alpr_loader.py`       | Load the FastALPR plate reader                                      | No (import directly)       |

The YOLO rows (`yolo26-general`, `yolo11-face`, `yolo11-license-plate`) load
through `load_yolo_model` and the OCR row through `load_paddle_ocr`, both
defined inside `model_zoo.py` itself.

### Model Loader Base

| Service                | Purpose                                       | Exported via `__init__.py` |
| ---------------------- | --------------------------------------------- | -------------------------- |
| `model_loader_base.py` | Abstract base class for all Model Zoo loaders | No (import directly)       |

### Specialized Detection Services

| Service                        | Purpose                                     | Exported via `__init__.py` |
| ------------------------------ | ------------------------------------------- | -------------------------- |
| `plate_detector.py`            | License plate detection and OCR             | Yes                        |
| `face_detector.py`             | Face detection for person re-identification | Yes                        |
| `ocr_service.py`               | OCR text extraction from detected regions   | Yes                        |
| `smoke_fire_consecutive.py`    | Consecutive smoke/fire detection tracking   | No (import directly)       |
| `threat_monitor_service.py`    | Weapon detection immediate alert generation | No (import directly)       |
| `depth_calibration_service.py` | Depth-to-distance calibration for cameras   | No (import directly)       |

### Pipeline Workers

| Service               | Purpose                              | Exported via `__init__.py` |
| --------------------- | ------------------------------------ | -------------------------- |
| `pipeline_workers.py` | Background queue workers and manager | No (import directly)       |

### Background Services

| Service                          | Purpose                                       | Exported via `__init__.py` |
| -------------------------------- | --------------------------------------------- | -------------------------- |
| `gpu_monitor.py`                 | Poll NVIDIA GPU metrics                       | Yes                        |
| `cleanup_service.py`             | Enforce data retention policies               | Yes                        |
| `health_monitor.py`              | Monitor service health with auto-recovery     | No (import directly)       |
| `health_monitor_orchestrator.py` | Container orchestrator health monitoring loop | No (import directly)       |
| `health_event_emitter.py`        | WebSocket health status event emission        | No (import directly)       |
| `health_service_registry.py`     | DI registry for health monitoring (NEM-2611)  | No (import directly)       |
| `system_broadcaster.py`          | Broadcast system health status                | No (import directly)       |
| `performance_collector.py`       | Collect system performance metrics            | No (import directly)       |
| `background_evaluator.py`        | Run AI audit evaluations when GPU is idle     | Yes                        |
| `worker_supervisor.py`           | Auto-recovery for crashed worker tasks        | No (import directly)       |

### Container Orchestrator Services

| Service                     | Purpose                                             | Exported via `__init__.py` |
| --------------------------- | --------------------------------------------------- | -------------------------- |
| `container_discovery.py`    | Discover Docker containers by name pattern          | No (import directly)       |
| `lifecycle_manager.py`      | Self-healing restart logic with exponential backoff | No (import directly)       |
| `container_orchestrator.py` | Coordinate discovery, health, lifecycle, broadcast  | No (import directly)       |

### Infrastructure Services

| Service                  | Purpose                                            | Exported via `__init__.py` |
| ------------------------ | -------------------------------------------------- | -------------------------- |
| `retry_handler.py`       | Exponential backoff and DLQ support                | Yes                        |
| `service_managers.py`    | Strategy pattern for service management            | No (import directly)       |
| `circuit_breaker.py`     | Circuit breaker for service resilience             | Yes                        |
| `degradation_manager.py` | Graceful degradation management                    | Yes                        |
| `cache_service.py`       | Redis caching utilities                            | Yes                        |
| `service_registry.py`    | Service registry with Redis persistence            | No (import directly)       |
| `inference_semaphore.py` | Shared semaphore for AI inference                  | No (import directly)       |
| `managed_service.py`     | Canonical ManagedService and ServiceRegistry types | Yes                        |
| `ai_fallback.py`         | AI service fallback strategies for degradation     | No (import directly)       |

### Alerting Services

| Service                  | Purpose                                  | Exported via `__init__.py` |
| ------------------------ | ---------------------------------------- | -------------------------- |
| `alert_engine.py`        | Evaluate alert rules against events      | Yes                        |
| `alert_dedup.py`         | Alert deduplication logic                | Yes                        |
| `alert_service.py`       | Alert CRUD with WebSocket events         | No (import directly)       |
| `notification.py`        | Multi-channel notification delivery      | Yes                        |
| `notification_filter.py` | Filter notifications by user preferences | No (import directly)       |

### Audit Services

| Service                             | Purpose                                      | Exported via `__init__.py` |
| ----------------------------------- | -------------------------------------------- | -------------------------- |
| `audit.py`                          | Audit logging for security-sensitive actions | Yes                        |
| `audit_logger.py`                   | High-level security audit logging interface  | No (import directly)       |
| `pipeline_quality_audit_service.py` | AI pipeline audit and self-evaluation        | Yes                        |

### Prompt Management Services

| Service                     | Purpose                                               | Exported via `__init__.py` |
| --------------------------- | ----------------------------------------------------- | -------------------------- |
| `prompts.py`                | LLM prompt templates                                  | No (import directly)       |
| `prompt_sanitizer.py`       | Prompt injection prevention for LLM inputs (NEM-1722) | No (import directly)       |
| `prompt_service.py`         | CRUD operations for AI prompt configs                 | No (import directly)       |
| `prompt_storage.py`         | File-based prompt storage with versioning             | No (import directly)       |
| `prompt_version_service.py` | Prompt version history and restoration                | No (import directly)       |
| `prompt_parser.py`          | Parse and modify prompts with suggestions             | No (import directly)       |
| `typed_prompt_config.py`    | Type-safe prompt configuration with generics          | No (import directly)       |

### Utility Services

| Service             | Purpose                                                 | Exported via `__init__.py` |
| ------------------- | ------------------------------------------------------- | -------------------------- |
| `search.py`         | Full-text search for events                             | Yes                        |
| `severity.py`       | Severity level mapping and configuration                | Yes                        |
| `clip_generator.py` | Video clip generation for events                        | Yes                        |
| `token_counter.py`  | LLM prompt token counting and context window validation | No (import directly)       |
| `batch_fetch.py`    | Batch fetch detections (avoid N+1)                      | No (import directly)       |
| `cost_tracker.py`   | LLM inference cost tracking and budget controls         | Yes                        |

### Data Management Services

| Service                | Purpose                         | Exported via `__init__.py` |
| ---------------------- | ------------------------------- | -------------------------- |
| `partition_manager.py` | PostgreSQL partition management | Yes                        |

### Evaluation Services

| Service               | Purpose                                 | Exported via `__init__.py` |
| --------------------- | --------------------------------------- | -------------------------- |
| `evaluation_queue.py` | Priority queue for AI audit evaluations | Yes                        |

### Camera Services

| Service                    | Purpose                                              | Exported via `__init__.py` |
| -------------------------- | ---------------------------------------------------- | -------------------------- |
| `camera_service.py`        | Camera status with optimistic concurrency (NEM-2030) | No (import directly)       |
| `camera_status_service.py` | Camera status changes with WebSocket broadcasting    | No (import directly)       |

### RTSP/ONVIF Camera Services

| Service              | Purpose                                                   | Exported via `__init__.py` |
| -------------------- | --------------------------------------------------------- | -------------------------- |
| `stream_manager.py`  | RTSP stream lifecycle, Redis health tracking (NEM-4197)   | No (import directly)       |
| `frame_extractor.py` | Motion detection (MOG2), frame saving, detection queueing | No (import directly)       |
| `onvif_service.py`   | ONVIF device discovery, PTZ control, preset management    | No (import directly)       |

### Entity Re-identification Services

| Service                        | Purpose                                             | Exported via `__init__.py` |
| ------------------------------ | --------------------------------------------------- | -------------------------- |
| `entity_clustering_service.py` | Embedding similarity for entity matching (NEM-2497) | No (import directly)       |
| `hybrid_entity_storage.py`     | Redis/PostgreSQL hybrid storage bridge (NEM-2498)   | No (import directly)       |

### Event Services

| Service             | Purpose                                        | Exported via `__init__.py` |
| ------------------- | ---------------------------------------------- | -------------------------- |
| `event_service.py`  | Event CRUD with cascade soft delete (NEM-1956) | No (import directly)       |
| `export_service.py` | CSV/Excel/JSON export generation (NEM-1989)    | No (import directly)       |

### File Services

| Service                     | Purpose                                              | Exported via `__init__.py` |
| --------------------------- | ---------------------------------------------------- | -------------------------- |
| `file_service.py`           | Scheduled file deletion with Redis queue (NEM-1988)  | No (import directly)       |
| `file_cleanup_service.py`   | Cascade file deletion for events (NEM-2384)          | No (import directly)       |
| `orphan_cleanup_service.py` | Cleanup orphaned files without DB records (NEM-2260) | No (import directly)       |
| `orphan_scanner_service.py` | Scan for orphaned files on disk (NEM-2387)           | No (import directly)       |

### Job Services

| Service                    | Purpose                                        | Exported via `__init__.py` |
| -------------------------- | ---------------------------------------------- | -------------------------- |
| `job_tracker.py`           | Job lifecycle management with WebSocket events | No (import directly)       |
| `job_service.py`           | Job CRUD service layer (NEM-2389, NEM-2390)    | No (import directly)       |
| `job_status.py`            | Redis-backed job status tracking               | No (import directly)       |
| `job_timeout_service.py`   | Job timeout detection and handling             | No (import directly)       |
| `job_history_service.py`   | Job execution history retrieval                | No (import directly)       |
| `job_search_service.py`    | Job search and filtering                       | No (import directly)       |
| `job_progress_reporter.py` | WebSocket job progress emission (NEM-2380)     | No (import directly)       |

### Calibration Services

| Service                  | Purpose                                     | Exported via `__init__.py` |
| ------------------------ | ------------------------------------------- | -------------------------- |
| `calibration_service.py` | Adaptive threshold adjustment from feedback | No (import directly)       |

### Queue Status Services

| Service                   | Purpose                           | Exported via `__init__.py` |
| ------------------------- | --------------------------------- | -------------------------- |
| `queue_status_service.py` | Queue depth and health monitoring | No (import directly)       |

### Transcoding Services

| Service                  | Purpose                                   | Exported via `__init__.py` |
| ------------------------ | ----------------------------------------- | -------------------------- |
| `transcoding.py`         | Video transcoding to H.264/MP4 (NEM-2681) | No (import directly)       |
| `transcoding_service.py` | Transcoding with caching (NEM-2682)       | No (import directly)       |
| `transcode_cache.py`     | Disk cache for transcoded videos with LRU | No (import directly)       |

### WebSocket Services

| Service                | Purpose                              | Exported via `__init__.py` |
| ---------------------- | ------------------------------------ | -------------------------- |
| `websocket_emitter.py` | Centralized WebSocket event emission | No (import directly)       |

### AI Services

| Service          | Purpose                               | Exported via `__init__.py` |
| ---------------- | ------------------------------------- | -------------------------- |
| `ai_services.py` | AI service wrappers for DI (NEM-2030) | No (import directly)       |

### Monitoring Services

| Service                         | Purpose                                    | Exported via `__init__.py` |
| ------------------------------- | ------------------------------------------ | -------------------------- |
| `monitoring_stack_validator.py` | Prometheus/Grafana stack health validation | No (import directly)       |

## Detailed Service Documentation

### file_watcher.py

**Purpose:** Monitors Foscam camera upload directories and queues images and videos for processing.

**Key Features:**

- Watchdog-based filesystem monitoring (recursive)
- Supports both images (.jpg, .jpeg, .png) and videos (.mp4, .mkv, .avi, .mov)
- Debounce logic (0.5s default) to wait for complete file writes
- Image integrity validation using PIL
- Integrates with DedupeService for content-hash based deduplication
- Supports both native filesystem events (inotify/FSEvents) and polling mode

**Observer Selection:**

- Default: Native backend (inotify on Linux, FSEvents on macOS)
- Polling mode: Enabled via `FILE_WATCHER_POLLING` env var or `settings.file_watcher_polling`
- Use polling for Docker Desktop, NFS/SMB mounts where inotify events don't propagate

**Camera ID Contract:**

```
Upload path: /export/foscam/Front Door/image.jpg
-> folder_name: "Front Door"
-> camera_id: "front_door" (normalized)
```

**Public API:**

- `FileWatcher(camera_root, redis_client, debounce_delay, queue_name, dedupe_service)`
- `async start()` - Begin monitoring camera directories
- `async stop()` - Gracefully shutdown
- `is_image_file(path)`, `is_video_file(path)`, `is_supported_media_file(path)`

### detector_client.py

**Purpose:** HTTP client for YOLO26v2 object detection service.

**Key Features:**

- Async HTTP client using httpx
- Confidence threshold filtering
- Direct database persistence (creates Detection records)
- 30-second timeout for detection requests
- Prometheus metrics for AI request duration

**Public API:**

- `DetectorClient()` - Initialize with settings
- `async health_check()` - Check if detector is reachable
- `async detect_objects(image_path, camera_id, session)` - Detect and store

### batch_aggregator.py

**Purpose:** Groups detections into time-based batches for efficient VLM analysis.

**Batching Rules:**

- **Window timeout:** 90 seconds from batch start (configurable)
- **Idle timeout:** 30 seconds since last detection (configurable)
- **One batch per camera:** Each camera has max 1 active batch at a time
- **Fast path:** The high-confidence bypass exists in the code but is DISABLED by config (`fast_path_confidence_threshold` defaults to the impossible 2.0 and `fast_path_object_types` to `[]`); when it does fire it routes the single detection through `VlmAnalyzer.analyze_detection_fast_path`, which runs the SAME batch gate as a one-detection batch

**Redis Keys (all keys have 1-hour TTL for orphan cleanup):**

```
batch:{camera_id}:current         -> current batch ID
batch:{batch_id}:camera_id        -> camera ID
batch:{batch_id}:detections       -> LIST of detection IDs (RPUSH for atomic append)
batch:{batch_id}:started_at       -> Unix timestamp
batch:{batch_id}:last_activity    -> Unix timestamp
```

**Concurrency:** Uses per-camera locks plus global lock for batch operations. Detection list updates use Redis RPUSH for atomic append in distributed environments.

**Public API:**

- `BatchAggregator(redis_client, analyzer)`
- `async add_detection(camera_id, detection_id, file_path, confidence, object_type)`
- `async check_batch_timeouts()` - Close expired batches
- `async close_batch(batch_id)` - Force close and push to analysis queue

### vlm_analyzer.py

**Purpose:** The shipped analysis entry point — one `vlm_assess` call per closed batch, its constrained verdict turned into an Event plus its EventVerification row. Built by `pipeline_factory.build_pipeline_analyzer()`, never by naming a mode at the call site.

**Analysis Flow (spec §6 ladder):**

1. Idempotency check first (the `batch_event:<id>` Redis key, same TTL as its replay twin)
2. Resolve batch identity from the queue payload, falling back to the Redis keys `close_batch` wrote; a batch with no camera from EITHER source raises loudly with zero writes (the VLM never originates an event)
3. Session 1 (READ): camera/detections/zones/household — NO session is held across the VLM call
4. The specialist stage (`vlm_specialists.py`) computes the three short lines — `faces`, `plates`, `person_reid` — over the batch's selected key frames; a specialist failure always degrades to the text "unavailable" and never fails the batch
5. ONE constrained call through `vlm_client` (transport retry at temperature 0 lives THERE; this module never re-retries)
6. Apply the verdict invariants: rejected clamps the score to `SeverityService.low_max`, uncertain keeps its score, the risk level is ALWAYS derived by `SeverityService` (the model never emits one), and a verification failure scores NULL with the event row still written ("needs review")
7. Session 2 (WRITE): Event and EventVerification in the SAME transaction, the idempotency key AFTER the write
8. Broadcast LAST, best-effort — a broadcast failure never un-does the committed event

**Public API:**

- `VlmAnalyzer(vlm_client, redis_client, severity=..., replay=...)`
- `async analyze_batch(batch_id, camera_id, detection_ids, *, specialist_inputs)` - Analyze one closed batch and create the Event (`specialist_inputs` is replay's carrier; production never passes it)
- `async analyze_detection_fast_path(camera_id, detection_id)` - The aggregator's bypass, routed through the same batch gate
- `async analyze_batch_streaming(batch_id, ...)` - The SSE re-analyze route's generator: one progress update, then the terminal update the Event's own stored values justify

### vlm_client.py

**Purpose:** The ONLY thing in the backend that dials the llama.cpp VLM server (`AI_VLM_URL`, compose `http://ai-vlm:8098`). `vlm_analyzer` consumes this; nobody else should.

**Key features:**

- Chat request with up to 4 base64 image parts + structured context; `response_format` carries the NESTED `json_schema` wrapper the enforcement probe proved ENFORCED at the pin
- The wire schema is the GENERATED contract schema with grammar-unsafe constraints stripped (`minLength`/`minimum`/`maximum` — the grammar guarantees shape, `VlmVerdict` post-validation owns bounds)
- Read budget `settings.ai_vlm_read_timeout` (default 25 s); ONE transport retry at temperature 0, and only when the first attempt failed fast
- Transport failures feed `get_circuit_breaker("ai-vlm")`; when it OPENS, DegradationManager is told ai-vlm is unhealthy
- Error types: `VlmClientError` and the subclasses `VlmTransportError`, `VlmSchemaError` (+ `VlmTruncatedError`), `VlmContextOverflowError`, `VlmUnavailableError`, `VlmImageError`
- `async wake_ai_vlm()` - bring a scale-to-zero engine back

### vlm_verdict.py

**Purpose:** The `vlm_assess` contract models — the schema the client sends, the golden payload, and the shape snapshot all derive from this module (drift doctrine: the contract is GENERATED by `scripts/gen-ai-contract.py` under `VLM_OPS`, never hand-transcribed). `risk_level` is NOT a field: `SeverityService` derives it from `risk_score`. Import closure is pydantic-only (the generator imports this module by name).

### vlm_specialists.py

**Purpose:** The specialist stage — `collect_face_text`, `collect_plate_text`, `collect_reid_text` produce one short line each (`faces`, `plates`, `person_reid`) into AssessInput before `vlm_assess`. Three rules dominate: never block the verdict (degrade to "unavailable", never "unknown"); four face outcomes (match / unknown / not_identifiable / unavailable) with the quality gate deciding unknown-vs-not-identifiable; and the one-embedding-space rule (person re-ID scores only same-`model_id` gallery rows via the resident OSNet handle).

### event_broadcaster.py

**Purpose:** Distributes security events to frontend clients via WebSocket.

**Channel:** `security_events` (Redis pub/sub)

**Message Format:**

```json
{
  "type": "event",
  "data": {
    "id": "uuid",
    "camera_id": "front_door",
    "risk_score": 75,
    "summary": "Person detected at front door",
    "created_at": "2024-01-15T10:30:00Z",
    "detections": [...]
  }
}
```

**Key Features:**

- WebSocket broadcast to all connected clients
- Redis pub/sub for horizontal scaling
- Automatic reconnection handling
- Message queuing during disconnection

**Public API:**

- `EventBroadcaster(redis_client)`
- `async broadcast_event(event)` - Broadcast event to all clients
- `CHANNEL_NAME` - Canonical channel name ("security_events")

### context_enricher.py

**Purpose:** Aggregates contextual information from multiple sources for LLM prompts.

**Context Sources:**

- Zone information (from zone_service)
- Activity baselines (from baseline)
- Cross-camera activity (recent detections on other cameras)

**Where it runs:** the shipped VLM path does not call this module — `vlm_analyzer` reads zones and household directly. Its one non-test consumer is `pipeline_quality_audit_service`, whose audit rows may carry an `EnrichedContext`, and `get_context_enricher()` is a DI provider (`backend/core/dependencies.py`).

**Key Classes:**

- `EnrichedContext` - Dataclass holding all enrichment data
- `ContextEnricher` - Service class for context aggregation

**Public API:**

- `ContextEnricher(cross_camera_window, image_width, image_height)`
- `async enrich(batch_id, camera_id, detection_ids, *, session)` - Get context for a batch (opens its own session when none is passed)
- `get_context_enricher()` - Get global singleton
- `reset_context_enricher()` - Reset singleton (for testing)

### model_zoo.py

**Purpose:** Registry and manager for on-demand AI model loading with VRAM optimization.

**Runtime surface (the rows `models.yml` ships today):**

| Model name               | Loader bound in `_LOADER_MAP`                          | zoo-enabled | preload | VRAM (MB) | Purpose                                                  |
| ------------------------ | ------------------------------------------------------ | ----------- | ------- | --------- | -------------------------------------------------------- |
| yolo26                   | — (loaded by the serving container, not in-process)    | false       | false   | 0         | Primary object detection — the backend calls it via HTTP |
| osnet-ain-x1-0           | `osnet_loader.load_osnet_model`                        | true        | true    | 100       | Person re-ID embeddings (512-d, OSNet-AIN)               |
| face-detector-scrfd      | `face_recognizer_loader.load_face_detector`            | true        | true    | 0         | SCRFD face detection (CPU onnxruntime, sha256-pinned)    |
| face-recognizer          | `face_recognizer_loader.load_face_recognizer`          | true        | true    | 0         | ArcFace face embedding (CPU onnxruntime, sha256-pinned)  |
| threat-detection-yolov8n | — (`service: both`, the gateway `threat` Triton model) | true        | false   | 300       | Threat/weapon detection                                  |
| yolo11-face              | `load_yolo_model`                                      | true        | false   | 200       | Face detection (DB-lookup leg)                           |
| yolo11-license-plate     | `load_yolo_model`                                      | true        | false   | 300       | License plate detection (DB-lookup leg)                  |
| fast-alpr                | `fast_alpr_loader.load_fast_alpr`                      | true        | false   | 28        | End-to-end plate detection + OCR                         |
| paddleocr                | `load_paddle_ocr`                                      | true        | false   | 100       | Text extraction from plates                              |
| yolo26-general           | `load_yolo_model`                                      | false       | false   | 400       | General detection variant, disabled                      |

`_LOADER_MAP` also still binds `yolov8n-pose` to `load_yolo_model`; that row
left `models.yml` in R8 S3, so the binding is unreachable — a name with no
row never reaches the zoo.

**VRAM budget:**

- ai-vlm: the always-loaded perception engine (`VLM_MODEL_SLOTS`), resident in its own container
- YOLO26v2: 650 MB (always loaded)
- Models load sequentially, never concurrently

**Key Classes:**

- `ModelConfig` - Configuration for a Model Zoo model
- `ModelManager` - Manager for on-demand model loading with reference counting

**Public API:**

```python
manager = get_model_manager()

async with manager.load("yolo11-face") as model:
    results = model.predict(image)
# Model automatically unloaded and CUDA cache cleared

# Utility functions
get_model_config(name)  # Get config for model
get_enabled_models()  # List enabled models
get_available_models()  # List verified working models
get_total_vram_if_loaded(names)  # Calculate VRAM usage
```

### reid_service.py

**Purpose:** Person re-identification across cameras using OSNet-AIN x1.0 embeddings (512-d; full swap, ledger item 20). Vehicles have no embedding producer in the shipped mode — vehicle identity rides plate match; a vehicle re-ID model is a named follow-up.

**Features:**

- Generate embeddings from person crops via the resident OSNet zoo handle (`osnet_loader.get_reid_handle()`; no weights resident ⇒ `ReIDUnavailableError`, never a zero vector)
- Provenance on every stored vector: `model_id` belt derived from the models.yml sha pin (F11), grammar `osnet-ain-x1-0@osnet_ain_x1_0_msmt17@8a07e8da3894` (`<name>@<weights>@<sha256 prefix 12>`); Redis keys partition by it so a search cannot read another space's rows
- Pre-swap rows decode to the `legacy-unknown-provenance` sentinel and are never scored — mismatch or unprovenanced answers `unavailable (re-enroll)`; drop and re-enroll, no backfill
- The VLM `person_reid` specialist leg (`vlm_specialists.py`) is real: it probes person crops with this resident handle and scores only same-`model_id` gallery rows
- A client-computed vector cannot be trusted to share this space, so `POST /api/household-matcher/match-person` (send a pre-computed embedding) is retired — it answers 410 Gone (D-1)
- Store embeddings in Redis with 24-hour TTL
- Match entities across camera views using cosine similarity (threshold default 0.7, OSNet-space, PROVISIONAL)
- Rate limiting via asyncio.Semaphore (configurable max concurrent requests)
- Timeout and retry logic with exponential backoff (retries never re-try an availability refusal)
- Batch similarity computation for performance (NEM-1071)
- Bounding box validation with clamping (NEM-1073)

**Redis Storage:**

```
entity_embeddings:{model_id}:{date} -> {
    "persons": [{entity_type, embedding, model_id, camera_id, timestamp, detection_id, attributes}, ...],
    "vehicles": [...]   # list exists; no vehicle embedding producer writes it in the shipped mode
}
TTL: 24 hours (86400 seconds)
```

**Key Classes:**

- `EntityEmbedding` - Embedding data for detected entity (carries `model_id`; pre-swap rows decode to the `legacy-unknown-provenance` sentinel and are never scored)
- `EntityMatch` - Match result with similarity score
- `ReIdentificationService` - Main service class

**Public API:**

- `ReIdentificationService(max_concurrent_requests, embedding_timeout, max_retries, hybrid_storage)`
- `async generate_embedding(image, bbox) -> (vector, model_id)` - Extract via the resident OSNet handle
- `async store_embedding(redis, embedding)` - Store in Redis (partitioned by the entry's model_id)
- `async find_matching_entities(redis, embedding, entity_type, threshold, model_id)` - Find matches (reads only the probe's own partition)
- `get_reid_service()` - Get global singleton

**Prompt Formatting:**

- `format_entity_match(match)` - Format single match for prompt
- `format_reid_context(matches_by_entity, entity_type)` - Format all matches
- `format_full_reid_context(person_matches, vehicle_matches)` - Complete context
- `format_reid_summary(person_matches, vehicle_matches)` - Brief summary

### reid_matcher.py

**Purpose:** Person re-identification matching service for tracking individuals across detections and time.

**Related to:** NEM-3043 - Implement Re-ID Matching Service

**Features:**

- Cosine similarity matching for person embeddings
- Configurable similarity threshold (default: 0.7)
- Time-window based search (default: 24 hours)
- Embedding hash for quick lookup
- Uses embeddings from Detection model's `enrichment_data.reid_embedding`

**Key Classes:**

- `ReIDMatch` - Match result with detection_id, similarity, timestamp, camera_id
- `ReIDMatcher` - Main service class for matching embeddings

**Public API:**

```python
from backend.services.reid_matcher import ReIDMatcher

async with get_session() as session:
    matcher = ReIDMatcher(session, similarity_threshold=0.7)

    # Find matches for an embedding
    matches = await matcher.find_matches(
        embedding=[0.1, 0.2, ...],  # 512-dim from OSNet
        time_window_hours=24,
        max_results=10,
        exclude_detection_id=current_detection_id,
    )

    # Check if this is a known person
    is_known, best_match = await matcher.is_known_person(
        embedding=[0.1, 0.2, ...],
        time_window_hours=24,
    )
```

**Embedding Source:**

Embeddings are stored in the Detection model:

```python
Detection.enrichment_data = {
    "reid_embedding": {
        "vector": [0.1, 0.2, ...],      # 512-dim from OSNet-AIN x1.0
        "hash": "abc123...",             # First 16 chars of SHA-256
        "model": "osnet_ain_x1_0",
    },
    ...
}
```

A bare vector list under the same key is also read. This matcher is a same-space lookup with no `model_id` guard of its own; the provenance-checked person comparison (mismatch or unprovenanced ⇒ `unavailable (re-enroll)`) lives in `household_matcher.compare_person_vectors`.

**Integration with the gateway `reid` model:**

The primary producer is `reid_service`, computing through the resident OSNet zoo handle. The gateway's OSNet pass — the Triton `reid` model behind `/enrich-lt/person-reid` (`http://ai-gateway:8090/enrich-lt/person-reid`) — is the same models.yml-pinned weights, so its vectors live in the one space and carry the same `model_id`; where both run, the resident pipeline's cached vector wins.

### scene_change_detector.py

**Purpose:** CPU-based scene change detection using Structural Similarity Index (SSIM).

**Features:**

- Compares current frames against stored baselines
- Detects significant visual changes (>10% difference by default)
- Per-camera baseline management
- Configurable similarity threshold and resize dimensions

**Key Classes:**

- `SceneChangeResult` - Detection result with similarity score and is_first_frame flag
- `SceneChangeDetector` - Main detector class

**Public API:**

- `SceneChangeDetector(similarity_threshold=0.90, resize_width=640)`
- `detect_changes(camera_id, frame)` - Compare frame to baseline
- `update_baseline(camera_id, frame)` - Set new baseline
- `reset_baseline(camera_id)` - Remove baseline
- `reset_all_baselines()` - Clear all baselines
- `get_scene_change_detector()` - Get global singleton

### pipeline_quality_audit_service.py

**Purpose:** AI pipeline auditing with self-evaluation via `POST {AI_VLM_URL}/completion` (the shipped verdict engine answers the evaluation calls). The module's own name is its filename — the class is `PipelineQualityAuditService`, reached through `get_audit_service()`.

**Features:**

- Create audit records with model contribution flags
- Self-evaluation modes:
  1. **Self-critique** - The model critiques its own response
  2. **Rubric scoring** - Quality dimension scoring (1-5 scale)
  3. **Consistency check** - Re-analyze and compare risk scores
  4. **Prompt improvement** - Suggest prompt enhancements
- Aggregate statistics and model leaderboard

**Tracked contribution flags** (`MODEL_NAMES`, read off an `EnrichmentResultLike`, which the shipped path passes as `None`):
yolo26, florence, clip, violence, clothing, vehicle, pet, weather, image_quality, zones, baseline, cross_camera

**Quality Dimensions:**

- context_usage - Did analysis reference all relevant enrichment data?
- reasoning_coherence - Is reasoning logical and well-structured?
- risk_justification - Does evidence support the risk score?
- actionability - Is summary useful for homeowner?

**Public API:**

- `AuditService()`
- `create_partial_audit(event_id, llm_prompt, enriched_context, enrichment_result)`
- `async persist_record(audit, session)` - Save to database
- `async run_full_evaluation(audit, event, session)` - Run all 4 evaluation modes
- `async get_stats(session, days, camera_id)` - Aggregate statistics
- `async get_leaderboard(session, days)` - Model contribution ranking
- `async get_recommendations(session, days)` - Prompt improvements
- `get_audit_service()` - Get global singleton

### gpu_monitor.py

**Purpose:** NVIDIA GPU statistics monitoring with multiple fallback strategies.

**Fallback Order:**

1. pynvml (direct NVML bindings - fastest)
2. nvidia-smi subprocess (works when nvidia-smi in PATH)
3. AI container health endpoints (YOLO26v2 reports VRAM)
4. Mock data (for development without GPU)

**Public API:**

- `GPUMonitor(poll_interval, history_minutes, broadcaster, http_timeout)`
- `async start()` - Start polling loop
- `async stop()` - Stop polling
- `async poll_once()` - Single poll
- `get_latest_stats()` - Get most recent stats
- `get_history(minutes)` - Get stats history

### cleanup_service.py

**Purpose:** Automated data retention and disk space management.

**Features:**

- Delete events older than retention period
- Cascade delete associated detections
- Remove GPU stats older than retention period
- Clean up thumbnail files for deleted detections
- Clean up log entries older than log_retention_days
- Optional cleanup of original image files
- Transaction-safe with rollback support

**Key Classes:**

- `CleanupStats` - Statistics for cleanup operation (events, detections, gpu_stats, logs, thumbnails, images, space_reclaimed)
- `CleanupService` - Main cleanup service

**Public API:**

- `CleanupService(session)`
- `async cleanup(dry_run=False)` - Run cleanup
- `async get_stats()` - Get cleanup statistics

### health_monitor_orchestrator.py

**Purpose:** Health monitoring loop for the container orchestrator.

**Features:**

- Periodic health checks for all enabled services (default: every 30 seconds)
- HTTP health endpoint checks for the AI containers `container_discovery` surfaces (`ai-gateway`, `ai-llm-vllm`)
- Command-based health checks for infrastructure (PostgreSQL, Redis)
- Container running status as fallback health check
- Grace period support for recently started containers
- Failure tracking with automatic status updates
- Callback support for health change notifications

**Note:** This is separate from `health_monitor.py` (ServiceHealthMonitor) which uses ServiceManager/ServiceConfig for AI service restart scripts. This module uses DockerClient for container management through Docker API.

**Key Classes:**

- `ManagedService` - Dataclass holding state and config for a managed container
- `ServiceRegistry` - Registry for managed services with lookup and update methods
- `HealthMonitor` - Main health monitoring loop class

**Health Check Priority:**

1. HTTP health check - If `health_endpoint` is set (e.g., `/health`)
2. Command health check - If `health_cmd` is set (e.g., `pg_isready -U security`)
3. Container running check - Fallback if neither is defined

**Grace Period:**

Services are not health-checked during their startup grace period (default: 60s for AI services, 10s for PostgreSQL). This allows time for the service to initialize.

**Public API:**

```python
from backend.services.health_monitor_orchestrator import (
    HealthMonitor,
    ManagedService,
    ServiceRegistry,
    check_http_health,
    check_cmd_health,
)

# Create registry and register services
registry = ServiceRegistry()
service = ManagedService(
    name="ai-gateway",
    container_id="abc123",
    image="ghcr.io/.../ai-gateway:latest",
    port=8090,
    health_endpoint="/health",
    category=ServiceCategory.AI,
)
registry.register(service)

# Create and start health monitor
async with DockerClient() as docker:
    monitor = HealthMonitor(
        registry=registry,
        docker_client=docker,
        settings=orchestrator_settings,
        on_health_change=my_callback,  # Optional callback
    )
    await monitor.start()
    # ... monitor runs in background
    await monitor.stop()

# Check individual service health
healthy = await check_http_health("localhost", 8090, "/health")
healthy = await check_cmd_health(docker_client, "container_id", "pg_isready")
```

### alert_engine.py

**Purpose:** Core engine for evaluating alert rules against events.

**Features:**

- AND logic within rules (all conditions must match)
- Condition types: risk_threshold, object_types, camera_ids, zone_ids, min_confidence, schedule
- Cooldown periods using dedup_key
- Creates Alert records for triggered rules

**Public API:**

- `AlertRuleEngine(session, redis_client)`
- `async evaluate_event(event, detections, current_time)` - Evaluate all rules
- `async create_alerts_for_event(event, triggered_rules)` - Create Alert records
- `async test_rule_against_events(rule, events)` - Test rule configuration

### circuit_breaker.py

**Purpose:** Circuit breaker pattern for external service protection. This is the canonical implementation - all modules should import from here rather than from `backend.core.circuit_breaker`.

**States:**

| State     | Code | Description      | Behavior                   |
| --------- | ---- | ---------------- | -------------------------- |
| CLOSED    | 0    | Normal operation | Calls pass through         |
| OPEN      | 1    | Circuit tripped  | Calls rejected immediately |
| HALF_OPEN | 2    | Recovery testing | Limited calls allowed      |

**State Transitions:**

```
CLOSED ─(failures >= threshold)──> OPEN
   ↑                                  │
   │                                  │ (recovery_timeout elapsed)
   │                                  ↓
   └──(success_threshold met)── HALF_OPEN ──(any failure)──> OPEN
```

**Key Features:**

- Configurable failure thresholds and recovery timeouts
- Half-open state for gradual recovery testing
- Excluded exceptions that don't count as failures
- Thread-safe async implementation
- Registry for managing multiple circuit breakers
- Prometheus metrics integration (both legacy and hsi\_-prefixed)
- Protected call wrapper and async context manager

**Configuration Options:**

| Parameter           | Default | Description                                  |
| ------------------- | ------- | -------------------------------------------- |
| failure_threshold   | 5       | Failures before opening circuit              |
| recovery_timeout    | 30.0s   | Seconds before transitioning to half-open    |
| half_open_max_calls | 3       | Maximum calls allowed in half-open state     |
| success_threshold   | 2       | Successes needed in half-open to close       |
| excluded_exceptions | ()      | Exception types that don't count as failures |

**Prometheus Metrics:**

| Metric                            | Type    | Labels            | Description                    |
| --------------------------------- | ------- | ----------------- | ------------------------------ |
| `circuit_breaker_state`           | Gauge   | service           | Current state (0/1/2)          |
| `circuit_breaker_failures_total`  | Counter | service           | Total failures recorded        |
| `circuit_breaker_state_changes`   | Counter | service, from, to | State transitions              |
| `circuit_breaker_calls_total`     | Counter | service, result   | Calls by result (success/fail) |
| `circuit_breaker_rejected_total`  | Counter | service           | Calls rejected when open       |
| `hsi_circuit_breaker_state`       | Gauge   | service           | HSI-prefixed state (Grafana)   |
| `hsi_circuit_breaker_trips_total` | Counter | service           | Times circuit has tripped      |

**Public API:**

```python
from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerOpenError,
    CircuitOpenError,
    CircuitState,
    CircuitBreakerRegistry,
    get_circuit_breaker,
    reset_circuit_breaker_registry,
)

# Method 1: Create with config
config = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=30.0,
    half_open_max_calls=3,
    success_threshold=2,
)
breaker = CircuitBreaker(name="ai_service", config=config)

# Method 2: Use global registry
breaker = get_circuit_breaker("ai_service", config)

# Execute through circuit breaker
try:
    result = await breaker.call(async_operation, arg1, arg2)
except CircuitBreakerError as e:
    # Handle service unavailable
    logger.warning(f"Circuit open for {e.service_name}")

# Async context manager
async with breaker:
    result = await async_operation()

# Protected call wrapper
result = await breaker.protected_call(lambda: client.fetch_data())

# Context manager with retry info
try:
    async with breaker.protect():
        result = await risky_operation()
except CircuitOpenError as e:
    # Return 503 with Retry-After header
    raise HTTPException(
        status_code=503, headers={"Retry-After": str(int(e.recovery_time_remaining))}
    )

# Manual control
breaker.reset()  # Reset to CLOSED
breaker.force_open()  # Force to OPEN (for maintenance)

# Get status
status = breaker.get_status()
metrics = breaker.get_metrics()
```

**Troubleshooting:**

| Issue                        | Check                                                   |
| ---------------------------- | ------------------------------------------------------- |
| Circuit stuck open           | Check `recovery_timeout` and service health             |
| Too many failures triggering | Increase `failure_threshold` or add excluded exceptions |
| Half-open not recovering     | Verify `success_threshold` and service stability        |
| Metrics not showing          | Ensure Prometheus scraping `/metrics` endpoint          |

### retry_handler.py

**Purpose:** Retry logic with exponential backoff and dead-letter queue support.

**DLQ Queues:**

- `dlq:detection_queue` - Failed detection jobs
- `dlq:analysis_queue` - Failed LLM analysis jobs

**Key Features:**

- Configurable max retries, base delay, max delay
- Exponential backoff with optional jitter
- Moves failed jobs to DLQ after exhausting retries
- DLQ inspection and management

**Public API:**

- `RetryHandler(redis_client, config)`
- `async with_retry(operation, job_data, queue_name)` - Execute with retries
- `async get_dlq_stats()` - Get DLQ statistics
- `async get_dlq_jobs(dlq_name)` - Inspect DLQ contents
- `async requeue_dlq_job(dlq_name)` - Move job back to processing

### service_registry.py

**Purpose:** Service registry with Redis persistence for Container Orchestrator.

**Key Features:**

- In-memory storage for fast access during health checks
- Redis persistence for state recovery across backend restarts
- Thread-safe concurrent access via RLock
- Redis key pattern: `orchestrator:service:{name}:state`

**ManagedService Dataclass:**

- `name` - Service identifier (e.g., "postgres", "ai-yolo26")
- `display_name` - Human-readable name (e.g., "PostgreSQL", "YOLO26v2")
- `container_id` - Docker container ID or None
- `image` - Container image (e.g., "postgres:16-alpine")
- `port` - Primary service port
- `health_endpoint` - HTTP health check path or None
- `health_cmd` - Docker exec health command or None
- `category` - ServiceCategory (infrastructure, ai, monitoring)
- `status` - ServiceStatus (running, stopped, unhealthy, etc.)
- `enabled` - Whether auto-restart is enabled
- `failure_count` - Consecutive health check failures
- `restart_count` - Total restarts since backend boot
- `max_failures` - Disable service after N consecutive failures (default 5)
- `restart_backoff_base` - Base delay for exponential backoff (default 5.0s)
- `restart_backoff_max` - Maximum backoff delay (default 300.0s)
- `startup_grace_period` - Seconds before counting health failures (default 60)

**Public API:**

```python
from backend.services.service_registry import (
    ServiceRegistry,
    ManagedService,
    get_service_registry,
    reset_service_registry,
)

# Get global singleton
registry = get_service_registry()

# Registration
registry.register(service)
registry.unregister(name)
registry.get(name) -> ManagedService | None
registry.get_all() -> list[ManagedService]
registry.get_by_category(category) -> list[ManagedService]
registry.get_enabled() -> list[ManagedService]

# State updates
registry.update_status(name, status)
registry.increment_failure(name) -> int  # returns new count
registry.reset_failures(name)
registry.record_restart(name)
registry.set_enabled(name, enabled)

# Redis persistence
await registry.persist_state(name)
await registry.load_state(name)
await registry.load_all_state()
await registry.clear_state(name)
```

**Redis State Schema:**

```json
{
  "enabled": true,
  "failure_count": 2,
  "last_failure_at": "2026-01-05T10:30:00+00:00",
  "last_restart_at": "2026-01-05T10:29:00+00:00",
  "restart_count": 5,
  "status": "running"
}
```

### performance_collector.py

**Purpose:** Collects system performance metrics from all components.

**Metrics Sources:**

| Source     | Method                                     | Metrics                               |
| ---------- | ------------------------------------------ | ------------------------------------- |
| GPU        | pynvml or HTTP fallback                    | Utilization, VRAM, temperature, power |
| YOLO26v2   | HTTP `/health` endpoint                    | Status, VRAM, model name, device      |
| ai-vlm     | HTTP `/slots` endpoint (`ai_vlm_url`)      | Status, active/total slots, context   |
| PostgreSQL | SQL queries (pg_stat_activity)             | Connections, cache hit ratio, txns    |
| Redis      | redis-py INFO command                      | Clients, memory, hit ratio, blocked   |
| Host       | psutil                                     | CPU%, RAM GB, disk GB                 |
| Containers | HTTP health endpoints (ai-yolo26, ai-vlm…) | Status, health for each container     |
| Inference  | PipelineLatencyTracker                     | YOLO26/analysis/pipeline latencies    |

The ai-vlm leg carries the class name `NemotronMetrics` and the method name
`collect_nemotron_metrics` — llama.cpp serves the `/slots` contract at
`ai_vlm_url`, and the names keep the LLM-era label. The latency leg likewise
labels the `batch_to_analyze` stage stats `nemotron_latency_ms`.

**Alert Thresholds:**

- GPU temperature: warning 75C, critical 85C
- GPU utilization: warning 90%, critical 98%
- GPU VRAM: warning 90%, critical 95%
- PostgreSQL connections: warning 80%, critical 95%
- PostgreSQL cache hit: warning <90%, critical <80%
- Redis memory: warning 100MB, critical 500MB
- Host CPU: warning 80%, critical 95%
- Host RAM: warning 85%, critical 95%
- Host disk: warning 80%, critical 90%

**Public API:**

```python
from backend.services.performance_collector import PerformanceCollector

collector = PerformanceCollector()
metrics = await collector.collect_all()  # Returns PerformanceUpdate schema
await collector.close()
```

### container_discovery.py

**Purpose:** Discovers Docker containers by name pattern and creates ManagedService objects with proper configuration for the container orchestrator.

**Key Features:**

- Pattern-based container name matching (e.g., "postgres" matches "security-postgres-1")
- Pre-configured service definitions for infrastructure, AI, and monitoring services
- Category-based discovery filtering (infrastructure, AI, monitoring)
- Automatic configuration assignment from matched patterns
- Supports both HTTP health endpoints and Docker exec health commands

**Pre-configured Service Categories:**

| Category       | Services                                                                                                                             | Restart Policy        |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------ | --------------------- |
| Infrastructure | PostgreSQL (:5432), Redis (:6379), backend, go2rtc, frontend                                                                         | Critical - aggressive |
| AI             | `ai-gateway` (the one AI container in compose; the detection/specialist models all ride it), `ai-llm-vllm` (optional `vllm` profile) | Standard backoff      |
| Monitoring     | Prometheus, Grafana, Alertmanager, Loki, Pyroscope, Alloy, Tempo, Redis/JSON/Blackbox/Node/DCGM Exporters, cAdvisor                  | Lenient               |

The orchestrator's `RETIRED_LLM_SERVICES` guard refuses to manage a stale
pre-R8 `ai-llm` container if one survives on the host.

**Key Classes:**

- `ServiceConfig` - Configuration dataclass for service patterns (port, health check, limits)
- `ManagedService` - Represents a discovered container with config values
- `ContainerDiscoveryService` - Main service for container discovery

**Public API:**

```python
from backend.services.container_discovery import (
    ContainerDiscoveryService,
    ServiceConfig,
    ManagedService,
    ALL_CONFIGS,
    INFRASTRUCTURE_CONFIGS,
    AI_CONFIGS,
    MONITORING_CONFIGS,
)

# Create discovery service
service = ContainerDiscoveryService(docker_client)

# Discover all containers matching known patterns
all_services = await service.discover_all()

# Discover by category
ai_services = await service.discover_by_category(ServiceCategory.AI)

# Get config for a service name
config = service.get_config("postgres")

# Match container name against patterns (returns config key or None)
config_key = service.match_container_name("security-postgres-1")  # Returns "postgres"
```

### lifecycle_manager.py

**Purpose:** Self-healing restart logic with exponential backoff for the container orchestrator.

**Key Features:**

- Exponential backoff calculation: base \* 2^failure_count, capped at max
- Category-specific defaults for Infrastructure, AI, and Monitoring services
- Automatic disabling of services after max_failures consecutive failures
- Callbacks for restart and disabled events
- State persistence to Redis for durability across backend restarts

**Self-Healing Decision Tree:**

```
Container Missing/Stopped/Unhealthy
            |
            v
    +-------------------+
    | failure_count >=  |--Yes--> Mark DISABLED, alert, skip
    | max_failures?     |
    +-------------------+
            | No
            v
    +-------------------+
    | Backoff elapsed?  |--No---> Skip this cycle
    | (exponential)     |
    +-------------------+
            | Yes
            v
    +-------------------+
    | Restart container |
    | Increment counts  |
    | Record timestamp  |
    +-------------------+
```

**Backoff Calculation:**

```python
# Exponential backoff: 5s, 10s, 20s, 40s, 80s, 160s, 300s (cap)
def calculate_backoff(failure_count, base=5.0, max_backoff=300.0):
    return min(base * (2**failure_count), max_backoff)
```

**Category-Specific Defaults:**

| Category       | max_failures | backoff_base | backoff_max |
| -------------- | ------------ | ------------ | ----------- |
| Infrastructure | 10           | 2.0s         | 60s         |
| AI             | 5            | 5.0s         | 300s        |
| Monitoring     | 3            | 10.0s        | 600s        |

**Key Classes:**

- `ManagedService` - Dataclass representing a managed container with lifecycle tracking
- `ServiceRegistry` - Registry for managing ManagedService instances with Redis persistence
- `LifecycleManager` - Main orchestration class for self-healing restart logic

**Public API:**

```python
from backend.services.lifecycle_manager import (
    LifecycleManager,
    ManagedService,
    ServiceRegistry,
    calculate_backoff,
)

# Create lifecycle manager with dependencies
manager = LifecycleManager(
    registry=registry,
    docker_client=docker_client,
    on_restart=my_restart_callback,
    on_disabled=my_disabled_callback,
)

# Backoff calculation
backoff = manager.calculate_backoff(service)
should_restart = manager.should_restart(service)
remaining = manager.backoff_remaining(service)

# Lifecycle actions
await manager.restart_service(service)
await manager.start_service(service)
await manager.stop_service(service)
await manager.enable_service("ai-yolo26")  # Reset failures and enable
await manager.disable_service("ai-yolo26")

# Self-healing handlers
await manager.handle_unhealthy(service)
await manager.handle_stopped(service)
await manager.handle_missing(service)
```

**ServiceRegistry API:**

```python
registry = ServiceRegistry(redis_client=redis)

# Register a service
registry.register(service)

# Get service(s)
service = registry.get("ai-yolo26")
all_services = registry.get_all()
enabled = registry.get_enabled_services()

# Update tracking
registry.record_restart("ai-yolo26")
new_count = registry.increment_failure("ai-yolo26")
registry.reset_failures("ai-yolo26")
registry.update_status("ai-yolo26", ContainerServiceStatus.RUNNING)
registry.set_enabled("ai-yolo26", False)

# Persistence
await registry.persist_state("ai-yolo26")
await registry.load_state()
```

### container_orchestrator.py

**Purpose:** Coordinates container discovery, health monitoring, lifecycle management, and real-time WebSocket broadcasting of service status changes.

**Key Features:**

- Service discovery using container name patterns
- Health monitoring with configurable intervals
- Self-healing restart logic with exponential backoff
- WebSocket broadcast of service status changes
- Integration with HealthMonitor and LifecycleManager components

**Public API:**

```python
from backend.services.container_orchestrator import (
    ContainerOrchestrator,
    create_service_status_event,
)

# Create orchestrator with broadcast function
orchestrator = ContainerOrchestrator(
    docker_client=docker_client,
    redis_client=redis_client,
    settings=settings,
    broadcast_fn=event_broadcaster.broadcast_service_status,
)

# Start orchestrator (discovery + monitoring)
await orchestrator.start()

# Query services
all_services = orchestrator.get_all_services()
service = orchestrator.get_service("ai-yolo26")

# Manual control
await orchestrator.restart_service("ai-yolo26")
await orchestrator.enable_service("ai-yolo26")
await orchestrator.disable_service("ai-yolo26")
await orchestrator.start_service("ai-yolo26")

# Stop orchestrator
await orchestrator.stop()
```

**Broadcasts service status events when:**

- Service discovered on startup
- Health check passes after failure (recovery)
- Health check fails
- Container restart initiated
- Container restart succeeded
- Container restart failed
- Service disabled (max failures)
- Service manually enabled
- Service manually disabled
- Service manually restarted

### prompt_parser.py

**Purpose:** Prompt parsing utilities for smart insertion of suggestions.

**Key Features:**

- Parse system prompts to identify optimal insertion points
- Detect variable style patterns (curly/angle/dollar)
- Generate insertion text matching detected style
- Validate prompt syntax (unclosed brackets, duplicate variables)
- Apply suggestions to prompts programmatically

**Public API:**

```python
from backend.services.prompt_parser import (
    find_insertion_point,
    detect_variable_style,
    generate_insertion_text,
    validate_prompt_syntax,
    apply_suggestion_to_prompt,
)

# Find where to insert a suggestion
insert_idx, insert_type = find_insertion_point(
    prompt, target_section="Camera & Time Context", insertion_point="append"
)

# Detect variable style in prompt
style = detect_variable_style(prompt)  # {'format': 'curly', 'label_style': 'colon', ...}

# Generate insertion text
new_text = generate_insertion_text("Time Since Last Event", "time_since_last_event", style)

# Validate prompt syntax
warnings = validate_prompt_syntax(prompt)

# Apply suggestion to prompt (convenience function)
modified_prompt = apply_suggestion_to_prompt(
    prompt,
    target_section="Camera & Time Context",
    insertion_point="append",
    proposed_label="Time Since Last Event",
    proposed_variable="time_since_last_event",
)
```

### batch_fetch.py

**Purpose:** Batch fetching service for detections to avoid N+1 query problems.

**Key Features:**

- Deduplicate input IDs
- Split IDs into configurable batch sizes (default 250, max 1000)
- Execute batched queries with IN clauses
- Aggregate results efficiently
- Optional ordering by detected_at timestamp

**Configuration:**

- `MIN_BATCH_SIZE`: 1
- `DEFAULT_BATCH_SIZE`: 250 (balanced between query count and IN clause size)
- `MAX_BATCH_SIZE`: 1000 (PostgreSQL handles IN clauses well up to ~1000 items)

**Public API:**

```python
from backend.services.batch_fetch import (
    batch_fetch_detections,
    batch_fetch_detections_by_ids,
    batch_fetch_file_paths,
)

async with get_session() as session:
    # Fetch as list
    detections = await batch_fetch_detections(session, detection_ids)

    # Fetch as dict for O(1) lookup
    detection_map = await batch_fetch_detections_by_ids(session, detection_ids)
    detection = detection_map.get(123)

    # Fetch only file paths (optimized)
    paths = await batch_fetch_file_paths(session, detection_ids)
```

### inference_semaphore.py

**Purpose:** Shared semaphore for AI inference concurrency control.

**Key Features:**

- Limits concurrent AI inference operations across all services
- Prevents GPU/AI service overload under high traffic
- Configurable via `AI_MAX_CONCURRENT_INFERENCES` env var (default: 4)
- Global singleton pattern for shared resource management

**Benefits:**

- Prevents GPU OOM errors under high load
- Ensures predictable latency by preventing request pileup
- Allows graceful degradation instead of service crashes
- Shared limit ensures total AI load stays bounded

**Public API:**

```python
from backend.services.inference_semaphore import get_inference_semaphore

async def detect_objects(...):
    semaphore = get_inference_semaphore()
    async with semaphore:
        # Perform AI inference (this block limited to N concurrent operations)
        result = await ai_client.detect(...)
    return result
```

### partition_manager.py

**Purpose:** PostgreSQL native partition management for high-volume time-series tables.

**Key Features:**

- Automatic partition creation for current and future months
- Configurable partition intervals (monthly, weekly)
- Automatic cleanup of old partitions beyond retention period
- Partition statistics and monitoring
- Idempotent partition creation (safe to run multiple times)

**Partitioned Tables:**

| Table      | Partition Column | Interval | Retention |
| ---------- | ---------------- | -------- | --------- |
| detections | detected_at      | monthly  | 12 months |
| events     | started_at       | monthly  | 12 months |
| logs       | timestamp        | monthly  | 6 months  |
| gpu_stats  | recorded_at      | weekly   | 3 months  |

**Partition Naming Convention:**

- Monthly: `{table}_y{year}m{month:02d}` (e.g., `detections_y2026m01`)
- Weekly: `{table}_y{year}w{week:02d}` (e.g., `gpu_stats_y2026w01`)

**Public API:**

```python
from backend.services.partition_manager import PartitionManager

manager = PartitionManager()
await manager.ensure_partitions()  # Create missing partitions
await manager.cleanup_old_partitions()  # Remove expired partitions
stats = await manager.get_partition_stats()  # Get partition info
result = await manager.run_maintenance()  # Full maintenance (create + cleanup)
```

### degradation_manager.py

**Purpose:** Graceful degradation management for system resilience during partial outages.

**Key Features:**

- Track health states of the services that get registered — `main.py` registers `ai-vlm` (critical=False) whose status arrives by breaker push from `vlm_client`, not by polling; Redis health drives the fallback-queue machinery below
- Fallback to disk-based queues when Redis is down
- In-memory queue fallback when Redis unavailable
- Automatic recovery detection
- Integration with circuit breakers
- Job queueing for later processing
- Configurable health check timeouts

**Degradation Modes:**

| Mode     | Description               | Available Features        |
| -------- | ------------------------- | ------------------------- |
| NORMAL   | All services healthy      | Full functionality        |
| DEGRADED | Some services unavailable | events, media (read-only) |
| MINIMAL  | Critical services down    | media only                |
| OFFLINE  | All services down         | Queueing only             |

**Fallback Queue Hierarchy:**

1. **Redis queue** - Primary storage for jobs
2. **Disk fallback** - JSON files on disk when Redis is down
3. **Memory queue** - In-memory deque when disk is unavailable (max 1000 items)

**Redis Keys:**

```
degraded:jobs      -> LIST of queued jobs
```

**Disk Fallback Storage:**

```
~/.cache/hsi_fallback/{queue_name}/{timestamp}_{counter}.json
```

**Public API:**

```python
from backend.services.degradation_manager import (
    DegradationManager,
    DegradationMode,
    DegradationServiceStatus,
    get_degradation_manager,
    reset_degradation_manager,
    FallbackQueue,
)

# Get global singleton
manager = get_degradation_manager(redis_client=redis)

# Register services for monitoring
manager.register_service(
    name="ai_detector",
    health_check=detector.health_check,
    critical=True,
)

# Check service health
if manager.is_service_healthy("yolo26"):
    # Proceed with AI analysis
    pass

# Queue with automatic fallback
await manager.queue_with_fallback("detection_queue", item)

# Determine if job should be queued
if manager.should_queue_job("detection"):
    await manager.queue_job_for_later("detection", job_data)
else:
    await process_job(job_data)

# Drain fallback queue when recovered
drained_count = await manager.drain_fallback_queue("detection_queue")

# Get status
status = manager.get_status()
# Returns: {"mode": "degraded", "redis_healthy": False, "memory_queue_size": 5, ...}

# Start/stop background health checks
await manager.start()
await manager.stop()
```

**Troubleshooting:**

| Issue                    | Check                                                  |
| ------------------------ | ------------------------------------------------------ |
| Stuck in DEGRADED mode   | Verify service health via `manager.get_status()`       |
| Jobs not processing      | Check `await manager.get_pending_job_count()`          |
| Fallback queue growing   | Ensure Redis is healthy, call `drain_fallback_queue()` |
| Health checks timing out | Adjust `health_check_timeout` in settings              |

### health_service_registry.py

**Purpose:** Centralized dependency injection registry for health monitoring services.

**Key Features:**

- Replaces global state pattern with proper dependency injection (NEM-2611)
- Tracks background workers and health monitors
- Circuit breaker for external health checks
- FastAPI dependency support for route handlers
- Worker status aggregation for health endpoints

**Tracked Services:**

| Service                  | Purpose                    | Critical |
| ------------------------ | -------------------------- | -------- |
| `gpu_monitor`            | GPU resource monitoring    | No       |
| `cleanup_service`        | Data cleanup service       | No       |
| `system_broadcaster`     | WebSocket system status    | No       |
| `file_watcher`           | File system monitoring     | Yes      |
| `pipeline_manager`       | Detection/analysis workers | Yes      |
| `batch_aggregator`       | Batch processing           | No       |
| `degradation_manager`    | Service degradation        | No       |
| `service_health_monitor` | Auto-recovery monitoring   | No       |
| `performance_collector`  | Performance metrics        | No       |
| `health_event_emitter`   | WebSocket health events    | No       |

**Circuit Breaker for Health Checks:**

The registry includes a `HealthCircuitBreaker` to prevent health checks from blocking on slow services:

- Failure threshold: 3 consecutive failures before opening
- Reset timeout: 30 seconds before retrying
- States: CLOSED (normal), OPEN (skip checks, return cached error)

**Public API:**

```python
from backend.services.health_service_registry import (
    HealthServiceRegistry,
    WorkerStatus,
    HealthCircuitBreaker,
    get_health_registry,
    get_health_registry_optional,
)


# FastAPI dependency
@app.get("/health")
async def get_health(
    registry: HealthServiceRegistry = Depends(get_health_registry),
):
    statuses = registry.get_worker_statuses()
    return {"workers": [s.__dict__ for s in statuses]}


# Get registry from DI container
container = get_container()
registry = await container.get_async("health_service_registry")

# Check critical workers
if registry.are_critical_pipeline_workers_healthy():
    # Detection and analysis workers are running
    pass

# Get pipeline status
pipeline_status = registry.get_pipeline_status()

# Register services (during startup)
registry.register_gpu_monitor(gpu_monitor)
registry.register_pipeline_manager(pipeline_manager)
registry.register_degradation_manager(degradation_manager)

# Get worker statuses
statuses: list[WorkerStatus] = registry.get_worker_statuses()
for status in statuses:
    print(f"{status.name}: {'running' if status.running else status.message}")

# Circuit breaker usage
cb = registry.circuit_breaker
if not cb.is_open("ai_service"):
    try:
        result = await check_ai_health()
        cb.record_success("ai_service")
    except Exception as e:
        cb.record_failure("ai_service", str(e))
```

### health_event_emitter.py

**Purpose:** WebSocket health event broadcasting with change detection.

**Key Features:**

- Tracks health state for each system component
- Emits WebSocket events only on status changes (prevents spam)
- Aggregates component health into overall system status
- Critical components (database, redis) impact overall health more heavily
- Thread-safe singleton pattern

**Health Components Monitored:**

| Component  | Check Method                | Critical |
| ---------- | --------------------------- | -------- |
| database   | PostgreSQL connection/query | Yes      |
| redis      | Redis connection/memory     | Yes      |
| ai_service | ai-vlm + YOLO26v2 health    | No       |
| gpu        | CUDA availability/memory    | No       |
| storage    | Disk space for /export      | No       |

**Health Status Values:**

| Status    | Priority | Description                    |
| --------- | -------- | ------------------------------ |
| UNHEALTHY | 0        | Component is failing           |
| DEGRADED  | 1        | Component is partially working |
| UNKNOWN   | 2        | Status not yet determined      |
| HEALTHY   | 3        | Component is working normally  |

**Event Types Emitted:**

- `system.health_changed` - When health status changes
- `system.error` - When a system-level error occurs

**WebSocket Payload Examples:**

```json
{
  "type": "system.health_changed",
  "data": {
    "health": "degraded",
    "previous_health": "healthy",
    "components": {
      "database": "healthy",
      "redis": "healthy",
      "ai_service": "unhealthy",
      "gpu": "healthy"
    },
    "changed_component": "ai_service",
    "component_previous_status": "healthy",
    "component_new_status": "unhealthy",
    "timestamp": "2026-01-18T10:30:00+00:00"
  }
}
```

**Public API:**

```python
from backend.services.health_event_emitter import (
    HealthEventEmitter,
    HealthStatus,
    ErrorSeverity,
    get_health_event_emitter,
    emit_system_error,
    reset_health_event_emitter,
)

# Get singleton emitter
emitter = get_health_event_emitter()

# Set WebSocket emitter (during startup)
emitter.set_emitter(websocket_emitter_service)

# Check and emit health changes (returns True if status changed)
changed = await emitter.check_and_emit(
    component="database",
    new_status="unhealthy",
    details={"error": "Connection refused"},
)

# Update multiple components at once
changed_components = await emitter.update_all_components(
    statuses={"database": "healthy", "redis": "degraded"},
    details={"redis": {"memory_mb": 450}},
)

# Emit system error
await emit_system_error(
    error_code="AI_SERVICE_CRASH",
    message="ai-vlm service crashed unexpectedly",
    severity="high",
    details={"exit_code": 137},
    recoverable=True,
)

# Get current status
overall = emitter.get_overall_status()
component_statuses = emitter.get_all_component_statuses()
```

**Overall Status Calculation:**

1. If any critical component (database, redis) is UNHEALTHY -> overall is UNHEALTHY
2. Otherwise, take the worst status across all components

### orphan_cleanup_service.py

**Purpose:** Periodic cleanup of orphaned files (files on disk without database records).

**Key Features:**

- Configurable scan interval (default: 24 hours)
- Configurable age threshold before deletion (default: 24 hours)
- Integration with job tracking system for progress monitoring
- WebSocket notification on cleanup completion
- Safe deletion with file age verification
- Multiple file naming pattern recognition

**File Extensions Scanned:**

- `.mp4`, `.webm`, `.mkv`, `.avi`

**Event ID Extraction Patterns:**

| Pattern           | Example          | Extracted ID |
| ----------------- | ---------------- | ------------ |
| `event_<id>`      | `event_123.mp4`  | 123          |
| `clip_event_<id>` | `clip_event_456` | 456          |
| `<id>_clip`       | `789_clip.webm`  | 789          |
| Numeric filename  | `123.mp4`        | 123          |

**Orphan Detection Logic:**

1. Extract event ID from filename
2. Check if event exists in database
3. If event exists, check if file is referenced in `clip_path`
4. If not referenced, file is an orphan

**Safety Measures:**

- Files must be older than `age_threshold_hours` before deletion
- Files without extractable event IDs are checked against all clip_paths
- On database error, file is NOT deleted (safe default)

**Public API:**

```python
from backend.services.orphan_cleanup_service import (
    OrphanedFileCleanupService,
    OrphanedFileCleanupStats,
    get_orphan_cleanup_service,
    reset_orphan_cleanup_service,
    JOB_TYPE_ORPHAN_CLEANUP,
)

# Get singleton service
service = get_orphan_cleanup_service(
    scan_interval_hours=24,
    age_threshold_hours=24,
    clips_directory="/path/to/clips",
    enabled=True,
    job_tracker=job_tracker,
    broadcast_callback=my_broadcast_fn,
)

# Start background cleanup loop
await service.start()

# Run cleanup manually
stats = await service.run_cleanup()
print(f"Scanned: {stats.files_scanned}")
print(f"Orphans found: {stats.orphans_found}")
print(f"Deleted: {stats.files_deleted}")
print(f"Space reclaimed: {stats.space_reclaimed} bytes")
print(f"Skipped (too young): {stats.files_skipped_young}")

# Get service status
status = service.get_status()
# Returns: {"running": True, "enabled": True, "scan_interval_hours": 24, ...}

# Stop service
await service.stop()

# Use as async context manager
async with service:
    # Service runs in background
    pass  # Automatically stopped on exit
```

**Job Tracker Integration:**

When `job_tracker` is provided:

- Creates job with type `orphan_cleanup`
- Updates progress as files are scanned (0-90%)
- Completes job with cleanup statistics
- Fails job on critical errors

**Troubleshooting:**

| Issue                   | Check                                                   |
| ----------------------- | ------------------------------------------------------- |
| Files not being deleted | Verify files are older than `age_threshold_hours`       |
| Wrong files deleted     | Check event ID extraction patterns in logs              |
| Service not running     | Check `enabled` setting and `service.get_status()`      |
| High disk usage         | Decrease `age_threshold_hours` or `scan_interval_hours` |

### evaluation_queue.py

**Purpose:** Priority queue for AI audit evaluations backed by Redis.

**Key Features:**

- Redis sorted set (ZSET) for priority-based ordering
- Higher priority events (higher risk scores) are evaluated first
- Persists across restarts (Redis-backed)
- Supports queue status and management

**Redis Storage:**

- Key: `evaluation:pending` (sorted set)
- Members: event IDs (as strings)
- Scores: priorities (higher = evaluated first)

**Public API:**

```python
from backend.services.evaluation_queue import get_evaluation_queue

queue = get_evaluation_queue(redis_client)

await queue.enqueue(event_id, priority=risk_score)  # Add to queue
event_id = await queue.dequeue()  # Get highest priority event
size = await queue.get_size()  # Get queue size
pending = await queue.get_pending_events(limit=100)  # List pending events
removed = await queue.remove(event_id)  # Remove specific event
is_queued = await queue.is_queued(event_id)  # Check if event is queued
```

### background_evaluator.py

**Purpose:** Background service that runs AI audit evaluations automatically when GPU is idle.

**Key Features:**

- Monitors GPU utilization and only processes when idle
- Detection and analysis queues take priority over evaluation
- Higher risk events are evaluated first (priority queue)
- Configurable idle threshold (default: 20%) and duration requirements (default: 5s)

**Processing Flow:**

1. Check if detection/analysis queues are empty
2. Check if GPU has been idle for required duration
3. Dequeue highest priority event from evaluation queue
4. Run full AI audit evaluation (4 LLM calls)
5. Repeat or wait based on queue status

**Configuration:**

- `gpu_idle_threshold`: GPU utilization % below which GPU is idle (default: 20%)
- `idle_duration_required`: Seconds GPU must be idle before processing (default: 5s)
- `poll_interval`: How often to check for work (default: 5s)
- `enabled`: Whether background evaluation is enabled (default: True)

**Public API:**

```python
from backend.services.background_evaluator import get_background_evaluator

evaluator = get_background_evaluator(
    redis_client=redis_client,
    gpu_monitor=gpu_monitor,
    evaluation_queue=evaluation_queue,
    audit_service=audit_service,
)

await evaluator.start()  # Start background loop
is_idle = await evaluator.is_gpu_idle()  # Check GPU idle status
can_process = await evaluator.can_process_evaluation()  # Check if can process
processed = await evaluator.process_one()  # Process one evaluation manually
await evaluator.stop()  # Stop background loop
```

### token_counter.py

**Purpose:** Token counting service for LLM context window management.

**Key Features:**

- Tiktoken-based token counting with configurable encoding
- Context utilization tracking with warning thresholds
- Intelligent truncation of enrichment data by priority
- Prometheus metrics for context utilization monitoring

**Configuration:**

- `encoding_name`: Tiktoken encoding (default: from settings, usually "cl100k_base")
- `context_window`: Max context window (default: `settings.nemotron_context_window` — a per-slot budget of 32,768 tokens, derived from llama.cpp's `CTX_SIZE` // `llama_slot_count`; the field keeps its legacy name and the shipped engine is ai-vlm)
- `max_output_tokens`: Tokens reserved for output (default: 1,536)
- `warning_threshold`: Utilization threshold for warnings (default: 0.85 = 85%)

**Truncation Priority (lowest priority truncated first):**

1. `depth_context` - Depth estimation (lowest priority)
2. `pose_analysis` - Human pose estimation
3. `action_recognition` - Action recognition
4. `pet_classification_context` - Pet classification
5. `image_quality_context` - Image quality assessment
6. `weather_context` - Weather classification
7. `vehicle_damage_context` - Vehicle damage detection
8. `vehicle_classification_context` - Vehicle type classification
9. `clothing_analysis_context` - Clothing analysis
10. `violence_context` - Violence detection
11. `reid_context` - Re-identification matches
12. `cross_camera_summary` - Cross-camera activity
13. `baseline_comparison` - Baseline anomaly detection
14. `zone_analysis` - Zone context
15. `detections_with_all_attributes` - Core detection data (high priority)
16. `scene_analysis` - Scene analysis (highest priority)

**Public API:**

```python
from backend.services.token_counter import (
    get_token_counter,
    count_prompt_tokens,
    validate_prompt_tokens,
)

counter = get_token_counter()

# Count tokens
token_count = counter.count_tokens(prompt_text)
token_count = count_prompt_tokens(prompt_text)  # Convenience function

# Validate prompt fits in context window
result = counter.validate_prompt(prompt, max_output_tokens=1536)
result = validate_prompt_tokens(prompt, max_output_tokens=1536)  # Convenience function
if not result.is_valid:
    # Handle truncation
    truncated = counter.truncate_enrichment_data(prompt, max_tokens)

# Truncate to fit
truncated_text = counter.truncate_to_fit(text, max_tokens, suffix="...[truncated]")

# Estimate enrichment token counts
token_counts = counter.estimate_enrichment_tokens(
    {
        "zone_analysis": zone_text,
        "reid_context": reid_text,
    }
)

# Get context budget
budget = (
    counter.get_context_budget()
)  # Returns dict with context_window, max_output_tokens, available_for_prompt
```

### clip_generator.py

**Purpose:** Event clip generator service for creating video clips around detected events.

**Key Features:**

- Extract clips from existing video files using ffmpeg
- Generate video from image sequences (MP4/GIF)
- Configurable pre/post roll seconds (default: 5s each)
- Store clips in configurable directory
- Associate clips with Event records

**Output Format:**

- File: `{clips_directory}/{event_id}_clip.mp4` or `{event_id}_clip.gif`
- Codec: libx264 (H.264) for MP4
- Audio: copy (if present) or none

**Security:**

- All user inputs are validated before use in subprocess calls
- Uses subprocess with list arguments (never shell=True)
- Paths are validated to prevent command-line option injection

**Public API:**

```python
from backend.services.clip_generator import get_clip_generator

generator = get_clip_generator()

# Generate clip from video
clip_path = await generator.generate_clip_from_video(
    event, video_path="/path/to/video.mp4", pre_seconds=5, post_seconds=5
)

# Generate clip from images
clip_path = await generator.generate_clip_from_images(
    event,
    image_paths=["/path/to/img1.jpg", "/path/to/img2.jpg"],
    fps=2,
    output_format="mp4",  # or "gif"
)

# Generate clip automatically (chooses best method)
clip_path = await generator.generate_clip_for_event(
    event,
    video_path="/path/to/video.mp4",  # Optional
    image_paths=[...],  # Optional
    fps=2,
)

# Query clips
clip_path = generator.get_clip_path(event_id)  # Returns Path or None
deleted = generator.delete_clip(event_id)  # Returns bool
```

### ai_fallback.py

**Purpose:** AI service fallback strategies for graceful degradation when AI services become unavailable. The module is kept-and-DEAD: zero shipped importers (ledgered as flagged-not-deleted; its final deletion is a dead-code slice's to make).

**Key Features:**

- Per-service fallback strategies for the one member the enum still names: `AIService.YOLO26`
- Cached risk score retrieval for fallback values
- Default value generation based on object types
- Health-based routing and degradation level tracking
- WebSocket status broadcasting for status changes
- Integration with circuit breakers

**Degradation Levels:**

- `NORMAL` - All services healthy
- `DEGRADED` - Non-critical services down
- `MINIMAL` - Critical services partially available
- `OFFLINE` - All AI services down

**Key Classes:**

- `AIService` - Enum of AI service identifiers (`yolo26` is the only member — an enum member naming a service no deployment can boot is the decorative-config class this repo refuses)
- `DegradationLevel` - System degradation levels
- `ServiceState` - State information for a single AI service
- `FallbackRiskAnalysis` - Fallback risk analysis result when the analyzer is unavailable
- `RiskScoreCache` - Cache for risk score patterns
- `AIFallbackService` - Main service class

**Public API:**

```python
from backend.services.ai_fallback import (
    AIFallbackService,
    AIService,
    DegradationLevel,
    get_ai_fallback_service,
    reset_ai_fallback_service,
)

service = get_ai_fallback_service()
await service.start()

# Check service availability
if service.is_service_available(AIService.YOLO26):
    result = await detector.detect(detection)
else:
    result = service.get_fallback_risk_analysis(
        camera_name="front_door", object_types=["person", "vehicle"]
    )

# Get degradation status
status = service.get_degradation_status()
level = service.get_degradation_level()
features = service.get_available_features()

# Convenience checks
if service.should_skip_detection():
    pass  # YOLO26v2 unavailable

await service.stop()
```

### managed_service.py

**Purpose:** Canonical ManagedService and ServiceRegistry definitions for the Container Orchestrator system.

**Key Features:**

- Single authoritative definitions used throughout container orchestration
- Redis persistence for state recovery across backend restarts
- Thread-safe concurrent access via RLock
- Factory methods for creating services from configs
- Serialization/deserialization for JSON and Redis storage

**Key Classes:**

- `ServiceConfig` - Configuration for service patterns used in discovery
- `ManagedService` - Container service managed by the orchestrator
- `ServiceRegistry` - Registry with optional Redis persistence

**ManagedService Fields:**

- Identity: name, display_name, container_id, image, port
- Health: health_endpoint, health_cmd
- Classification: category (infrastructure, ai, monitoring)
- Runtime: status, enabled
- Tracking: failure_count, last_failure_at, restart_count, last_restart_at
- Limits: max_failures, restart_backoff_base, restart_backoff_max, startup_grace_period

**Public API:**

```python
from backend.services.managed_service import (
    ManagedService,
    ServiceConfig,
    ServiceRegistry,
    get_service_registry,
    reset_service_registry,
)
from backend.api.schemas.services import ServiceCategory, ContainerServiceStatus

# Create a managed service
service = ManagedService(
    name="ai-gateway",
    display_name="AI Gateway (Triton)",
    container_id="abc123",
    image="ghcr.io/.../ai-gateway:latest",
    port=8090,
    health_endpoint="/health",
    category=ServiceCategory.AI,
    status=ContainerServiceStatus.RUNNING,
)

# Get global registry
registry = await get_service_registry()

# Register and manage services
registry.register(service)
registry.update_status("ai-yolo26", ContainerServiceStatus.UNHEALTHY)
registry.increment_failure("ai-yolo26")
registry.record_restart("ai-yolo26")

# Persist to Redis
await registry.persist_state("ai-yolo26")
await registry.load_state("ai-yolo26")
```

### model_loader_base.py

**Purpose:** Abstract base class for Model Zoo loaders.

**Key Features:**

- The consistent interface every loader class implements (the zoo's current load functions are plain async functions bound by name in `model_zoo.py`'s `_LOADER_MAP`; nothing in the shipped tree subclasses this base today — it is the contract a class-form loader implements)
- Generic type parameter for model instance types
- Required properties: model_name, vram_mb
- Required methods: load(device), unload()

**Abstract Interface:**

```python
class ModelLoaderBase(ABC, Generic[T]):
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Unique model identifier (e.g., 'osnet-ain-x1-0')."""
        ...

    @property
    @abstractmethod
    def vram_mb(self) -> int:
        """Estimated VRAM usage in megabytes."""
        ...

    @abstractmethod
    async def load(self, device: str = "cuda") -> T:
        """Load model and return instance."""
        ...

    @abstractmethod
    async def unload(self) -> None:
        """Unload model and free GPU memory."""
        ...
```

**Usage Example:**

```python
from backend.services.model_loader_base import ModelLoaderBase


class OsnetLoader(ModelLoaderBase[dict]):  # illustrative shape, not a shipped class
    @property
    def model_name(self) -> str:
        return "osnet-ain-x1-0"

    @property
    def vram_mb(self) -> int:
        return 100

    async def load(self, device: str = "cuda") -> dict: ...

    async def unload(self) -> None:
        del self._model
        torch.cuda.empty_cache()
```

### typed_prompt_config.py

**Purpose:** Type-safe prompt configuration with Python generics and Pydantic validation.

**Key Features:**

- Compile-time type checking via mypy
- Runtime validation via Pydantic
- Model-specific parameter types
- Generic template with type constraints
- Factory functions for template creation

**The module is self-contained: no shipped module imports it.** Its parameter
registry still names the retired attribute zoo (`florence2`, `yolo_world`,
`xclip`, `fashion_clip`) alongside the LLM-era `nemotron` key — the key is a
lookup string, not a claim that a Nemotron service exists.

**Parameter Types:**

| Type                      | Purpose                        | Required Fields                                  |
| ------------------------- | ------------------------------ | ------------------------------------------------ |
| `NemotronPromptParams`    | Nemotron risk analysis         | camera_name, timestamp, day_of_week, time_of_day |
| `Florence2PromptParams`   | Florence-2 VQA                 | queries                                          |
| `YoloWorldPromptParams`   | YOLO-World detection           | classes, confidence_threshold                    |
| `XClipPromptParams`       | X-CLIP action recognition      | action_classes                                   |
| `FashionClipPromptParams` | Fashion-CLIP clothing analysis | clothing_categories, suspicious_indicators       |

**Public API:**

```python
from backend.services.typed_prompt_config import (
    TypedPromptTemplate,
    NemotronPromptParams,
    create_typed_template,
    get_typed_params,
    get_param_type_for_model,
)

# Create typed template
template = TypedPromptTemplate[NemotronPromptParams](
    model_name="nemotron",
    template_string="Camera: {camera_name}\nTime: {timestamp}",
    param_type=NemotronPromptParams,
)

# Or use factory
template = create_typed_template("nemotron", "Camera: {camera_name}")

# Validate and render
params = NemotronPromptParams(
    camera_name="Front Door",
    timestamp="2024-01-15T10:30:00",
    day_of_week="Monday",
    time_of_day="morning",
)
rendered = template.render(params)

# Parse raw data into typed params
params = get_typed_params("nemotron", raw_dict)
```

### service_managers.py

**Purpose:** Strategy pattern for service management with health checks and restarts.

**Key Features:**

- Abstract ServiceManager base class
- ShellServiceManager for script-based restarts
- DockerServiceManager for container restarts
- HTTP health checks for AI services
- Redis health via redis-cli ping
- Security: Command allowlist and container name validation

**Security Measures:**

- Restart commands validated against `ALLOWED_RESTART_SCRIPTS` allowlist
- Container names validated against Docker naming regex
- Commands executed with `shell=False` to prevent injection
- Maximum container name length of 128 characters

**Key Classes:**

- `ServiceConfig` - Configuration for a managed service
- `ServiceManager` - Abstract base class
- `ShellServiceManager` - Restart via shell scripts
- `DockerServiceManager` - Restart via docker restart

**Public API:**

```python
from backend.services.service_managers import (
    ServiceConfig,
    ShellServiceManager,
    DockerServiceManager,
    validate_restart_command,
    validate_container_name,
)

# Create config
config = ServiceConfig(
    name="ai-gateway",
    health_url="http://localhost:8090/health",
    restart_cmd="ai/start_detector.sh",  # Must be in ALLOWED_RESTART_SCRIPTS
    health_timeout=5.0,
    max_retries=3,
    backoff_base=5.0,
)

# Use shell manager
manager = ShellServiceManager(subprocess_timeout=60.0)
healthy = await manager.check_health(config)
if not healthy:
    success = await manager.restart(config)

# Use Docker manager
docker_manager = DockerServiceManager()
healthy = await docker_manager.check_health(config)
if not healthy:
    success = await docker_manager.restart(config)

# Validate commands (allowlist: ai/start_detector.sh; container restarts of any
# valid container name)
is_valid = validate_restart_command(
    "ai/start_detector.sh"
)  # host-run dev stand-in; prod detection is served by Triton inside ai-gateway
is_valid = validate_restart_command("docker restart ai-gateway-1")  # prod detection host
is_valid = validate_container_name("ai-gateway-1")
```

### notification_filter.py

**Purpose:** Filter notifications based on user preferences, camera settings, and quiet hours.

**Key Features:**

- Global notification preference checking
- Per-camera notification settings
- Risk level filtering (critical, high, medium, low)
- Quiet hours periods with day-of-week support
- Handles periods spanning midnight

**Filtering Logic:**

1. Check if global notifications enabled
2. Check if risk level is in enabled filters
3. Check per-camera settings (if provided)
4. Check quiet hours periods (if provided)

**Risk Level Thresholds:**

- CRITICAL: score >= 80
- HIGH: score >= 60
- MEDIUM: score >= 40
- LOW: score < 40

**Public API:**

```python
from backend.services.notification_filter import NotificationFilterService
from backend.models.notification_preferences import (
    NotificationPreferences,
    CameraNotificationSetting,
    QuietHoursPeriod,
)
from datetime import UTC, datetime, time

filter_service = NotificationFilterService()

# Check if notification should be sent
should_send = filter_service.should_notify(
    risk_score=75,
    camera_id="front_door",
    timestamp=datetime.now(UTC),
    global_prefs=NotificationPreferences(
        enabled=True,
        risk_filters=["critical", "high"],
    ),
    camera_setting=CameraNotificationSetting(
        enabled=True,
        risk_threshold=50,
    ),
    quiet_periods=[
        QuietHoursPeriod(
            start_time=time(22, 0),
            end_time=time(6, 0),
            days=["monday", "tuesday", "wednesday", "thursday", "friday"],
        ),
    ],
)

# Check if in quiet period
is_quiet = filter_service.is_quiet_period(
    timestamp=datetime.now(UTC),
    period=quiet_period,
)
```

### cost_tracker.py

**Purpose:** LLM inference cost tracking and budget controls.

**Key Features:**

- Token usage tracking per LLM request (input/output)
- GPU-time tracking per model inference
- Cost estimation based on cloud equivalents
- Daily/monthly budget limits with alerts
- Prometheus metrics for monitoring
- Redis persistence for usage records

**Cloud Pricing Models:**

- AWS GPU instances (p4d, p3, g5)
- GCP GPU instances (a2, n1)
- Azure GPU instances (NC, ND)

**Public API:**

```python
from backend.services.cost_tracker import (
    CostTracker,
    CostModel,
    get_cost_tracker,
    reset_cost_tracker,
)

tracker = get_cost_tracker()

# Track LLM usage
tracker.track_llm_usage(
    input_tokens=1500,
    output_tokens=500,
    model="nemotron",
    duration_seconds=2.5,
    camera_id="front_door",
)

# Track detection model usage
tracker.track_detection_usage(
    model="yolo26",
    duration_seconds=0.15,
    images_processed=1,
)

# Check budget status
status = await tracker.get_budget_status()
if status.daily_exceeded:
    logger.warning("Daily budget exceeded!")

# Get usage summary
daily = await tracker.get_daily_usage()
monthly = await tracker.get_monthly_usage()
```

### audit_logger.py

**Purpose:** High-level security audit logging interface for common security events.

**Key Features:**

- Simplified API for logging security events
- Rate limit violation logging
- Content-Type validation failure logging
- File magic number validation logging
- Configuration change tracking
- Sensitive operation logging

**Logged Events:**

- Rate limit exceeded
- Content-Type validation failure
- File magic validation failure
- Configuration changes
- Export operations
- Cleanup operations

**Public API:**

```python
from backend.services.audit_logger import audit_logger

# Log rate limit exceeded
await audit_logger.log_rate_limit_exceeded(
    db=db,
    request=request,
    tier="default",
    current_count=65,
    limit=60,
)

# Log configuration change
await audit_logger.log_config_change(
    db=db,
    request=request,
    setting_name="batch_window_seconds",
    old_value=90,
    new_value=120,
)

# Log sensitive operation
await audit_logger.log_sensitive_operation(
    db=db,
    request=request,
    operation="export_events",
    details={"format": "csv", "count": 1000},
)
```

### stream_manager.py

**Purpose:** Manages RTSP stream connections for live camera feeds with automatic reconnection and health tracking.

**Related Issue:** NEM-4197

**Key Features:**

- RTSP stream connection using TCP transport (reliable, no UDP)
- Exponential backoff for reconnection (5s, 10s, 20s, 40s, max 60s)
- Health tracking via Redis hash keys
- Async-compatible design with event loop integration
- Graceful shutdown handling
- Support for multiple concurrent streams

**Redis Schema:**

```
hsi:stream:health:{camera_id}  -> Hash with fields:
  - status: "connecting" | "connected" | "reconnecting"
  - connection_time: ISO timestamp
  - fps: "25.0"
  - retry_count: "0"
  - last_error: error message (if any)
```

**Public API:**

```python
from backend.services.stream_manager import StreamManager

# Use as async context manager
async with StreamManager(redis_client=redis) as manager:
    await manager.add_stream("camera1", "rtsp://192.168.1.100:554/stream")
    health = await manager.get_stream_health("camera1")
    print(health["status"])  # "connected"
    await manager.remove_stream("camera1")

# Or manual lifecycle
manager = StreamManager(redis_client=redis)
await manager.start()
await manager.add_stream("camera1", "rtsp://...")
# ... use stream ...
await manager.stop()
```

**Key Classes:**

- `StreamManager` - Main service class for managing RTSP streams

### frame_extractor.py

**Purpose:** Extracts frames from RTSP streams, performs motion detection using MOG2 background subtraction, and queues detected motion frames for the AI pipeline.

**Key Features:**

- 1 FPS extraction for detection (configurable)
- MOG2 background subtraction for motion detection
- Per-camera background models for accurate motion detection
- Only saves frames when motion is detected (bandwidth optimization)
- Saves to `/tmp/claude/rtsp_frames/{camera_id}/{timestamp}.jpg`
- Queues to detection_queue with DetectionQueuePayload format

**Motion Sensitivity:**

The `motion_sensitivity` parameter (0.0 to 1.0) controls detection threshold:

- 0.0 = lowest sensitivity (requires large motion to trigger)
- 0.5 = balanced sensitivity (default)
- 1.0 = highest sensitivity (triggers on small motion)

**Public API:**

```python
from backend.services.frame_extractor import FrameExtractor

extractor = FrameExtractor(
    redis_client=redis, motion_sensitivity=0.7, frame_save_dir="/tmp/claude/rtsp_frames"
)

# Process a frame (main entry point)
file_path = await extractor.extract_frame(
    camera_id="front_door",
    frame=np_frame,  # numpy array (BGR format)
    timestamp=datetime.now(),
)

if file_path:
    print(f"Motion detected! Frame saved to {file_path}")

# Individual operations
has_motion = extractor.detect_motion(frame, camera_id="front_door")
file_path = extractor.save_frame("front_door", frame, timestamp)
await extractor.queue_detection("front_door", file_path, timestamp)
```

**Key Classes:**

- `FrameExtractor` - Main service class for frame extraction and motion detection
- `_MOG2Wrapper` - Wrapper around cv2.BackgroundSubtractorMOG2 for testability

### onvif_service.py

**Purpose:** ONVIF device management including discovery, capability retrieval, RTSP URL extraction, and PTZ control operations.

**Related Issues:** NEM-4207, NEM-4388

**Key Features:**

- WS-Discovery for ONVIF device scanning
- RTSP URL extraction from media profiles
- Manufacturer/model detection from ONVIF scopes
- Capability detection (video, PTZ, events)
- PTZ command execution (pan, tilt, zoom, stop)
- PTZ preset navigation

**Discovery Output:**

```python
{
    "device_url": "http://192.168.1.100:80/onvif/device_service",
    "ip": "192.168.1.100",
    "port": 80,
    "manufacturer": "Hikvision",
    "model": "DS-2CD2385G1",
    "rtsp_urls": [
        {"profile": "mainStream", "url": "rtsp://192.168.1.100:554/Streaming/Channels/101"}
    ],
    "capabilities": {"video": True, "ptz": True, "events": False},
}
```

**Public API:**

```python
from backend.services.onvif_service import OnvifService

service = OnvifService(session=db_session, redis=redis_client)

# Discover devices on network
devices = await service.discover_devices(subnet="192.168.1.0/24", timeout=10)

# Get device capabilities for a configured camera
capabilities = await service.get_capabilities(camera_id="front_door")

# Execute PTZ command
await service.execute_ptz_command(
    camera_id="front_door",
    command="pan",  # pan, tilt, zoom, stop
    value=0.5,  # -1.0 to 1.0
    speed=0.3,  # 0.0 to 1.0
)

# Get PTZ presets
presets = await service.get_presets(camera_id="front_door")

# Navigate to preset
await service.goto_preset(camera_id="front_door", preset_token="preset_1")

# Extract RTSP URL from device
rtsp_url = await service.get_rtsp_url_from_device(
    device_url="http://192.168.1.100:80/onvif/device_service",
    username="admin",
    password="secret",  # pragma: allowlist secret
)
```

**Dependencies:**

- `wsdiscovery` - WS-Discovery protocol for device scanning
- `onvif-zeep` - ONVIF protocol implementation

**Key Classes:**

- `OnvifService` - Main service class for ONVIF operations

## Data Flow Between Services

### Complete Pipeline Flow

```
1. FileWatcher
   | Detects new image or video files
   | Validates media file integrity
   | Checks for duplicates via DedupeService
   | Queues to Redis: detection_queue

2. [DetectionQueueWorker]
   | Consumes from: detection_queue
   | For images: Calls DetectorClient.detect_objects()
   | For videos: Calls VideoProcessor.extract_thumbnail() then DetectorClient
   | Stores: Detection records in PostgreSQL

3. [DetectionQueueWorker]
   | Calls: BatchAggregator.add_detection(confidence, object_type)
   |---> [Fast Path] Disabled by config (threshold 2.0); if ever re-enabled:
   |     | Calls: VlmAnalyzer.analyze_detection_fast_path() — the same batch
   |     | gate on a one-detection batch; Event with is_fast_path=True
   |
   └---> [Normal Path] Otherwise:
         | Updates Redis batch keys

4. [BatchTimeoutWorker]
   | Calls: BatchAggregator.check_batch_timeouts()
   | Queues to Redis: analysis_queue

5. [AnalysisQueueWorker]
   | Consumes from: analysis_queue
   | Calls: VlmAnalyzer.analyze_batch() (built by build_pipeline_analyzer)
   |   inside the analyzer: the vlm_specialists texts (faces/plates/person_reid),
   |   then ONE vlm_client vlm_assess call, then the verdict invariants
   | Stores: Event + EventVerification rows in PostgreSQL (one transaction)

6. [VlmAnalyzer] (tail of analyze_batch)
   | Calls: EventBroadcaster.broadcast_event() (LAST, best-effort)
   | Publishes: Redis pub/sub channel "security_events"
   | Audit: the ai_audit routes create the partial audit on demand
   |   (service.create_partial_audit) — analysis itself does not enqueue
   |   evaluation: EvaluationQueue.enqueue() has no production caller, so
   |   evaluation:pending only ever fills through test fixtures

7. [AlertRuleEngine] (After Event Creation)
   | Evaluates: Each rule's conditions against event
   | Creates: Alert records for triggered rules
   | Calls: NotificationService.send_alert()

8. [BackgroundEvaluator] (When GPU Idle)
   | Checks: GPU idle and queues empty
   | Dequeues: Highest priority event from evaluation queue
   | Calls: AuditService.run_full_evaluation()
   | Updates: EventAudit record with quality scores
```

### Specialist Stage (inside analyze_batch)

```
vlm_specialists (faces / plates / person_reid), over the batch's selected key frames
│
├── faces:         face_detector.detect() on the key frames, then the
│                  gallery match via face_recognizer (ArcFace) — four
│                  outcomes: match / unknown / not_identifiable / unavailable
├── plates:        plate_detector.detect() + ocr_service.extract(), then a
│                  registered-vehicle DB match
└── person_reid:   reid_service.generate_embedding() through the resident
                   OSNet-AIN x1.0 handle (512-d + model_id), scored only
                   against same-model_id gallery rows

Every leg degrades to the text "unavailable" — a specialist never fails a
batch, and the VLM never originates these lines (the snapshot is their only
carrier; replay reads what production stored).
```

### Background Services (Parallel)

```
GPUMonitor (Continuous Polling)
   | Every poll_interval seconds
   | Reads: pynvml GPU metrics (or fallback)
   | Stores: GPUStats records in PostgreSQL
   | Broadcasts: WebSocket to SystemBroadcaster (optional)

SystemBroadcaster (Periodic Broadcasting)
   | Every 5 seconds
   | Queries: Latest GPUStats, Camera counts, Redis queue lengths
   | Checks: Database + Redis health
   | Broadcasts: WebSocket system_status to all connected clients

PerformanceCollector (Periodic Collection)
   | Every 5 seconds
   | Collects: GPU, AI models, PostgreSQL, Redis, host, containers
   | Calculates: Alert thresholds (warning/critical)
   | Returns: PerformanceUpdate schema for WebSocket broadcast

CleanupService (Daily Scheduled)
   | Once per day at cleanup_time (default: 03:00)
   | Deletes: Events, Detections, GPUStats older than retention_days
   | Deletes: Logs older than log_retention_days
   | Removes: Thumbnail files (and optionally original images)

PartitionManager (Periodic Maintenance)
   | Once per day (recommended)
   | Creates: Missing partitions for current and future months
   | Removes: Expired partitions beyond retention period
   | Logs: Partition statistics and counts

ServiceHealthMonitor (Periodic Health Checks)
   | Every check_interval seconds (default: 15s)
   | Checks: HTTP health endpoint for the one configured service (yolo26 —
   |   the gateway's aggregated /health when USE_AI_GATEWAY is on)
   | Checks: Redis via redis-cli ping
   | Restarts: Failed services with exponential backoff
   | Broadcasts: Service status changes via WebSocket

BackgroundEvaluator (GPU Idle Processing)
   | Every poll_interval seconds (default: 5s)
   | Checks: GPU idle and detection/analysis queues empty
   | Dequeues: Highest priority event from evaluation queue
   | Runs: Full AI audit evaluation (4 LLM calls)
   | Updates: EventAudit records with quality scores
```

### Redis Queue Structure

**detection_queue:**

```json
{
  "camera_id": "front_door",
  "file_path": "/export/foscam/front_door/image_001.jpg",
  "timestamp": "2024-01-15T10:30:00.000000",
  "media_type": "image",
  "file_hash": "abc123..."
}
```

**analysis_queue:**

```json
{
  "batch_id": "batch_uuid",
  "camera_id": "front_door",
  "detection_ids": [1, 2, 3]
}
```

**evaluation:pending (sorted set):**

```
Member: "123" (event_id as string)
Score: 75 (priority, usually risk_score)
```

## Import Patterns

```python
# For exported services (via __init__.py)
from backend.services import (
    FileWatcher,
    DetectorClient,
    BatchAggregator,
    ThumbnailGenerator,
    EventBroadcaster,
    GPUMonitor,
    CleanupService,
    CircuitBreaker,
    RetryHandler,
    BackgroundEvaluator,
    EvaluationQueue,
    PartitionManager,
    ManagedService,
    ServiceConfig,
    ServiceRegistry,
    CostTracker,
)

# For context enrichment (import directly)
from backend.services.context_enricher import ContextEnricher, get_context_enricher
from backend.services.reid_service import ReIdentificationService, get_reid_service
from backend.services.scene_change_detector import SceneChangeDetector, get_scene_change_detector

# For the VLM analysis path (import directly)
from backend.services.vlm_analyzer import VlmAnalyzer
from backend.services.vlm_client import VlmClient
from backend.services.vlm_verdict import VlmVerdict
from backend.services.pipeline_factory import build_pipeline_analyzer

# For Model Zoo (import directly)
from backend.services.model_zoo import ModelManager, get_model_manager, get_model_config
from backend.services.model_loader_base import ModelLoaderBase

# For AI fallback (import directly; the module is kept-and-DEAD)
from backend.services.ai_fallback import AIFallbackService, get_ai_fallback_service

# For SSE streaming: the event models live in backend.api.schemas.streaming
# and the generator is VlmAnalyzer.analyze_batch_streaming (the route in
# backend/api/routes/events.py consumes it — there is no service-level
# streaming module)

# For workers and background services (import directly)
from backend.services.pipeline_workers import PipelineWorkerManager
from backend.services.health_monitor import ServiceHealthMonitor
from backend.services.performance_collector import PerformanceCollector
from backend.services.pipeline_quality_audit_service import (
    PipelineQualityAuditService,
    get_audit_service,
)

# For container orchestrator (import directly)
from backend.services.container_orchestrator import ContainerOrchestrator
from backend.services.container_discovery import ContainerDiscoveryService
from backend.services.lifecycle_manager import LifecycleManager
from backend.services.managed_service import get_service_registry

# For service management (import directly)
from backend.services.service_managers import (
    ServiceManager,
    ShellServiceManager,
    DockerServiceManager,
)

# For notifications (import directly)
from backend.services.notification_filter import NotificationFilterService

# For typed prompts (import directly)
from backend.services.typed_prompt_config import (
    TypedPromptTemplate,
    NemotronPromptParams,
    create_typed_template,
)

# For utilities (import directly)
from backend.services.token_counter import get_token_counter, count_prompt_tokens
from backend.services.batch_fetch import batch_fetch_detections, batch_fetch_detections_by_ids
from backend.services.prompt_parser import apply_suggestion_to_prompt
from backend.services.inference_semaphore import get_inference_semaphore
from backend.services.cost_tracker import get_cost_tracker
from backend.services.audit_logger import audit_logger
```

## Testing Considerations

### Mocking AI Services

```python
# Mock Model Zoo for tests
from backend.services.model_zoo import reset_model_zoo, reset_model_manager

reset_model_zoo()
reset_model_manager()
```

### Singleton Reset Functions

Most services provide `reset_*()` functions for test isolation:

- `reset_model_zoo()`, `reset_model_manager()`
- `reset_reid_service()`, `reset_dedupe_service()`
- `reset_context_enricher()`
- `reset_scene_change_detector()`, `reset_audit_service()`
- `reset_background_evaluator()`, `reset_evaluation_queue()`
- `reset_token_counter()`, `reset_clip_generator()`
- `reset_inference_semaphore()`
- `reset_ai_fallback_service()`, `reset_service_registry()`
- `reset_cost_tracker()`

### Integration Test Patterns

```python
@pytest.mark.asyncio
async def test_reid_service():
    # Reset the singleton
    reset_reid_service()

    service = get_reid_service()

    # With no pinned weights resident the producer refuses — it never
    # answers with a zero vector (F11).
    with pytest.raises(ReIDUnavailableError):
        await service.generate_embedding(image, bbox)
```

### Bounding Box Testing

```python
from backend.services.bbox_validation import (
    is_valid_bbox,
    clamp_bbox_to_image,
    InvalidBoundingBoxError,
)

# Test invalid bboxes
assert not is_valid_bbox((0, 0, 0, 0))  # Zero dimensions
assert not is_valid_bbox((100, 100, 50, 50))  # Inverted

# Test clamping
clamped = clamp_bbox_to_image((10, 10, 200, 200), 100, 100)
assert clamped == (10, 10, 100, 100)
```

## Dependencies

### External Services

- **ai-gateway** (host port `AI_GATEWAY_PORT` 8090, metrics 8002) - Triton-based gateway serving the `yolo26` router (`/yolo26`: detect, detect/batch, segment) and the resident threat + re-ID specialists (`/enrich-lt`: threat-detect, person-reid) behind one container
- **ai-vlm** (host port `AI_VLM_PORT` 8098, container port 8098) - the verdict engine the backend dials at `AI_VLM_URL` (compose default `http://ai-vlm:8098`, default compose set); llama.cpp + mmproj serving `vlm_assess`, which owns the analysis stage
- **Redis** (`REDIS_PORT` 6379) - Queue and cache storage
- **PostgreSQL** (`POSTGRES_PORT` 5432) - Persistent storage
- **ffmpeg/ffprobe** - Video processing

### Python Packages

- `watchdog` - Filesystem monitoring
- `httpx` - Async HTTP client
- `PIL/Pillow` - Image processing
- `sqlalchemy[asyncio]` - Database ORM
- `redis` - Redis client
- `pynvml` - NVIDIA GPU monitoring (optional)
- `numpy` - Numerical operations
- `scikit-image` - SSIM computation
- `transformers` - Model loading (HuggingFace)
- `torch` - PyTorch for model inference
- `tiktoken` - Token counting for LLMs

## Related Documentation

- `/backend/AGENTS.md` - Backend architecture overview
- `/backend/models/AGENTS.md` - Database model documentation
- `/backend/api/routes/AGENTS.md` - API endpoint documentation
- `/backend/api/schemas/AGENTS.md` - Pydantic schema documentation
- `/backend/core/AGENTS.md` - Core infrastructure documentation
- `/ai/AGENTS.md` - AI pipeline overview
- `/ai/yolo26/AGENTS.md` - YOLO26v2 detection server
- `/ai/gateway/AGENTS.md` - The Triton gateway the detection and specialist calls ride
