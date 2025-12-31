# Backend Services Directory

## Purpose

This directory contains the core business logic and background services for the AI-powered home security monitoring system. Services orchestrate the complete detection pipeline from file monitoring through AI analysis to event creation.

## Architecture Overview

The services implement a multi-stage async pipeline with real-time broadcasting and background maintenance:

```
File Upload -> Detection -> Batching -> Analysis -> Event Creation -> Broadcasting
   (1)          (2)         (3)         (4)         (5)              (6)

                     Monitoring Services (Parallel)
                     ├── GPUMonitor (polls GPU stats)
                     ├── SystemBroadcaster (system status)
                     ├── HealthMonitor (service recovery)
                     └── CleanupService (retention policy)
```

### Core AI Pipeline Services

1. **FileWatcher** - Monitors camera directories for new image and video uploads
2. **DedupeService** - Prevents duplicate file processing via content hashing
3. **DetectorClient** - Sends images to RT-DETRv2 for object detection
4. **BatchAggregator** - Groups detections into time-based batches
5. **NemotronAnalyzer** - Analyzes batches with LLM for risk scoring
6. **ThumbnailGenerator** - Creates preview images with bounding boxes
7. **VideoProcessor** - Extracts metadata and thumbnails from video files using ffmpeg
8. **EventBroadcaster** - Distributes events via WebSocket to frontend

### Pipeline Workers

- **DetectionQueueWorker** - Consumes from detection_queue, runs detection
- **AnalysisQueueWorker** - Consumes from analysis_queue, runs LLM analysis
- **BatchTimeoutWorker** - Periodically checks and closes timed-out batches
- **QueueMetricsWorker** - Updates Prometheus metrics for queue depths
- **PipelineWorkerManager** - Unified lifecycle management for all workers

### Background Services

- **GPUMonitor** - Polls NVIDIA GPU metrics and stores statistics
- **SystemBroadcaster** - Aggregates and broadcasts system health status
- **CleanupService** - Enforces data retention policies and frees disk space
- **ServiceHealthMonitor** - Monitors external service health with auto-recovery

### Infrastructure Services

- **RetryHandler** - Exponential backoff and dead-letter queue support
- **ServiceManager** - Strategy pattern for service restarts (Shell/Docker)
- **CircuitBreaker** - Circuit breaker pattern for service resilience
- **DegradationManager** - Graceful degradation during service outages

## Service Files Overview

| Service                    | Purpose                                          | Type           | Exported via `__init__.py` |
| -------------------------- | ------------------------------------------------ | -------------- | -------------------------- |
| `file_watcher.py`          | Monitor camera directories for media uploads     | Core Pipeline  | Yes                        |
| `dedupe.py`                | Prevent duplicate file processing                | Core Pipeline  | Yes                        |
| `detector_client.py`       | Send images to RT-DETRv2 for detection           | Core Pipeline  | Yes                        |
| `batch_aggregator.py`      | Group detections into time-based batches         | Core Pipeline  | Yes                        |
| `nemotron_analyzer.py`     | LLM-based risk analysis via llama.cpp            | Core Pipeline  | Yes                        |
| `thumbnail_generator.py`   | Generate preview images with bounding boxes      | Core Pipeline  | Yes                        |
| `video_processor.py`       | Extract video metadata and thumbnails            | Core Pipeline  | No (import directly)       |
| `pipeline_workers.py`      | Background queue workers and manager             | Workers        | No (import directly)       |
| `event_broadcaster.py`     | Distribute events via WebSocket                  | Broadcasting   | Yes                        |
| `system_broadcaster.py`    | Broadcast system health status                   | Broadcasting   | No (import directly)       |
| `gpu_monitor.py`           | Poll NVIDIA GPU metrics                          | Background     | Yes                        |
| `cleanup_service.py`       | Enforce data retention policies                  | Background     | Yes                        |
| `health_monitor.py`        | Monitor service health with auto-recovery        | Background     | No (import directly)       |
| `retry_handler.py`         | Exponential backoff and DLQ support              | Infrastructure | Yes                        |
| `service_managers.py`      | Strategy pattern for service management          | Infrastructure | No (import directly)       |
| `circuit_breaker.py`       | Circuit breaker for service resilience           | Infrastructure | Yes                        |
| `degradation_manager.py`   | Graceful degradation management                  | Infrastructure | Yes                        |
| `prompts.py`               | LLM prompt templates                             | Utility        | No (import directly)       |
| `alert_engine.py`          | Evaluate alert rules against events              | Alerting       | Yes                        |
| `alert_dedup.py`           | Alert deduplication logic                        | Alerting       | Yes                        |
| `notification.py`          | Multi-channel notification delivery              | Alerting       | Yes                        |
| `search.py`                | Full-text search for events                      | Query          | Yes                        |
| `severity.py`              | Severity level mapping and configuration         | Utility        | Yes                        |
| `zone_service.py`          | Zone detection and context generation            | Core Pipeline  | Yes                        |
| `baseline.py`              | Activity baseline tracking for anomaly detection | Core Pipeline  | Yes                        |
| `audit.py`                 | Audit logging for security-sensitive actions     | Infrastructure | Yes                        |
| `clip_generator.py`        | Video clip generation for events                 | Core Pipeline  | Yes                        |
| `performance_collector.py` | Collect system performance metrics               | Background     | No (import directly)       |

**Import Pattern:**

```python
# For exported services (most common)
from backend.services import FileWatcher, DetectorClient, NemotronAnalyzer

# For non-exported services (import directly)
from backend.services.video_processor import VideoProcessor
from backend.services.pipeline_workers import PipelineWorkerManager
from backend.services.health_monitor import ServiceHealthMonitor
from backend.services.performance_collector import PerformanceCollector
```

## Service Files

### file_watcher.py

**Purpose:** Monitors Foscam camera upload directories and queues images and videos for processing.

**Key Features:**

- Watchdog-based filesystem monitoring (recursive)
- Supports both images (.jpg, .jpeg, .png) and videos (.mp4, .mkv, .avi, .mov)
- Debounce logic (0.5s default) to wait for complete file writes
- Image integrity validation using PIL (checks for corruption, zero-byte files)
- Video validation (file exists, minimum size check of 1KB)
- Async-compatible design with thread-safe event loop scheduling
- Camera ID derived from folder name via `normalize_camera_id()`
- Integrates with DedupeService for content-hash based deduplication
- Supports both native filesystem events (inotify/FSEvents) and polling mode

**Observer Selection:**

- Default: Native backend (inotify on Linux, FSEvents on macOS)
- Polling mode: Enabled via `FILE_WATCHER_POLLING` env var or `settings.file_watcher_polling`
- Use polling for Docker Desktop, NFS/SMB mounts where inotify events don't propagate

**Supported File Types:**

- **Images:** `.jpg`, `.jpeg`, `.png`
- **Videos:** `.mp4`, `.mkv`, `.avi`, `.mov`

**Public API (exported from `backend.services`):**

- `FileWatcher(camera_root, redis_client, debounce_delay, queue_name, dedupe_service)` - Initialize watcher
- `async start()` - Begin monitoring camera directories
- `async stop()` - Gracefully shutdown (cancels pending tasks)
- `is_image_file(path)` - Validate image extension (module-level function)
- `is_valid_image(path)` - Validate image integrity with PIL (module-level function)

**Additional module-level functions (not exported):**

- `is_video_file(path)` - Validate video extension
- `is_supported_media_file(path)` - Validate any supported media extension
- `get_media_type(path)` - Returns "image", "video", or None
- `is_valid_video(path)` - Validate video file exists and has content (>1KB)
- `is_valid_media_file(path)` - Validate either image or video

**Camera ID Contract:**

```
Upload path: /export/foscam/Front Door/image.jpg
-> folder_name: "Front Door"
-> camera_id: "front_door" (normalized)
```

Auto-creates Camera record if `auto_create_cameras` is enabled (default: True).

**Data Flow:**

1. Watchdog detects file creation/modification event
2. Checks if file has supported media extension (image or video)
3. Schedules async task via `asyncio.run_coroutine_threadsafe()`
4. Debounces by cancelling/recreating pending task on each event
5. After debounce delay, validates media and extracts camera ID
6. Checks for duplicates via DedupeService (SHA256 content hash)
7. Queues to Redis `detection_queue` with `{camera_id, file_path, timestamp, media_type, file_hash}`

**Error Handling:**

- Warns on invalid/corrupted media files (skips processing)
- Logs errors for queue failures
- Creates camera root directory if missing
- Skips duplicate files based on content hash
- Uses QueueOverflowPolicy for queue capacity management

### dedupe.py

**Purpose:** Provides file deduplication to prevent duplicate processing using content hashes.

**Key Features:**

- SHA256 content hash of image files for idempotency
- Redis as primary dedupe cache with configurable TTL (default 5 minutes)
- Database fallback when Redis is unavailable
- Fail-open design for availability (processes if dedupe unavailable)
- Thread-safe and async-compatible

**Public API:**

- `compute_file_hash(file_path)` - Compute SHA256 hash of file content
- `DedupeService(redis_client, ttl_seconds)` - Initialize service
- `async is_duplicate(file_path, file_hash)` - Check if file was already processed
- `async mark_processed(file_path, file_hash)` - Mark file as processed
- `async is_duplicate_and_mark(file_path)` - Atomic check-and-mark operation
- `async clear_hash(file_hash)` - Clear hash from cache (for testing/reprocessing)
- `get_dedupe_service(redis_client)` - Get/create global singleton
- `reset_dedupe_service()` - Reset singleton (for testing)

**Redis Keys:**

```
dedupe:{sha256_hash}  -> file_path (with TTL)
```

**Error Handling:**

- Redis unavailable: Fails open (allows processing)
- File read errors: Returns False (don't process corrupted files)
- Empty files: Logs warning, returns None hash

### detector_client.py

**Purpose:** HTTP client for RT-DETRv2 object detection service.

**Key Features:**

- Async HTTP client using httpx
- Confidence threshold filtering (default from config)
- Direct database persistence (creates Detection records)
- 30-second timeout for detection requests
- Prometheus metrics for AI request duration and pipeline errors

**Public API:**

- `DetectorClient()` - Initialize with settings
- `async health_check()` - Check if detector is reachable
- `async detect_objects(image_path, camera_id, session)` - Detect and store

**Data Flow:**

1. Read image file as bytes
2. POST to `{rtdetr_url}/detect` with multipart/form-data
3. Parse JSON response: `{"detections": [{"class": "person", "confidence": 0.95, "bbox": [x,y,w,h]}, ...]}`
4. Filter detections by confidence threshold
5. Create Detection model instances with bbox coordinates
6. Commit to database, return Detection list

**Error Handling:**

- Returns empty list `[]` on all errors
- Logs detailed error messages for debugging
- Records pipeline error metrics

### batch_aggregator.py

**Purpose:** Groups detections into time-based batches for efficient LLM analysis.

**Batching Rules:**

- **Window timeout:** 90 seconds from batch start (configurable)
- **Idle timeout:** 30 seconds since last detection (configurable)
- **One batch per camera:** Each camera has max 1 active batch at a time
- **Fast path:** High-confidence critical detections bypass batching for immediate analysis

**Redis Keys:**

```
batch:{camera_id}:current         -> current batch ID (string)
batch:{batch_id}:camera_id        -> camera ID (string)
batch:{batch_id}:detections       -> JSON array of detection IDs
batch:{batch_id}:started_at       -> Unix timestamp (float)
batch:{batch_id}:last_activity    -> Unix timestamp (float)
```

**Public API:**

- `BatchAggregator(redis_client, analyzer)` - Initialize with Redis and optional analyzer for fast path
- `async add_detection(camera_id, detection_id, file_path, confidence, object_type)` - Add to batch
- `async check_batch_timeouts()` - Close expired batches, returns closed batch IDs
- `async close_batch(batch_id)` - Force close and push to analysis queue

### nemotron_analyzer.py

**Purpose:** LLM-based risk analysis using Nemotron via llama.cpp server.

**Key Features:**

- Fetches batch detections from database
- Formats structured prompt with detection details
- Calls llama.cpp `/completion` endpoint
- Parses JSON from LLM response (handles extra text)
- Creates Event records with risk scores
- Broadcasts via WebSocket (optional)

**Public API:**

- `NemotronAnalyzer(redis_client)` - Initialize with Redis
- `async analyze_batch(batch_id)` - Analyze batch and create Event
- `async analyze_detection_fast_path(camera_id, detection_id)` - Analyze single detection immediately
- `async health_check()` - Check if LLM server is reachable

### thumbnail_generator.py

**Purpose:** Generate thumbnail previews with bounding boxes for detection visualization.

**Key Features:**

- Draws colored bounding boxes based on object type
- Adds text labels with confidence scores
- Resizes to 320x240 with aspect ratio preservation
- Saves as optimized JPEG (quality 85)

**Color Scheme:**

```python
person:            red (#E74856)
car/truck:         blue (#3B82F6)
dog/cat:           green (#76B900)
bicycle/motorcycle: yellow (#FFB800)
bird:              purple (#A855F7)
default:           white (#FFFFFF)
```

**Public API:**

- `ThumbnailGenerator(output_dir)` - Initialize with output directory
- `generate_thumbnail(image_path, detections, output_size, detection_id)` - Create thumbnail
- `draw_bounding_boxes(image, detections)` - Draw boxes on image
- `get_output_path(detection_id)` - Get thumbnail path
- `delete_thumbnail(detection_id)` - Remove thumbnail file

### video_processor.py

**Purpose:** Extract metadata and thumbnails from video files using ffmpeg.

**Key Features:**

- Uses ffmpeg/ffprobe subprocess for reliable cross-platform video processing
- Extracts video metadata (duration, codec, resolution)
- Generates thumbnail frames at configurable timestamps
- Smart thumbnail extraction (avoids black frames at start)
- Async-compatible subprocess execution via `asyncio.to_thread`
- No Python video library dependencies (uses system ffmpeg)

**Supported Formats:**

- MP4 (.mp4)
- Matroska (.mkv)
- AVI (.avi)
- QuickTime (.mov)

**Public API:**

- `VideoProcessor(output_dir)` - Initialize with output directory (default: "data/thumbnails")
- `async get_video_metadata(video_path)` - Extract video metadata
- `async extract_thumbnail(video_path, output_path, timestamp, size)` - Extract frame as thumbnail
- `async extract_thumbnail_for_detection(video_path, detection_id, size)` - Convenience method
- `get_output_path(detection_id)` - Get thumbnail path for detection
- `delete_thumbnail(detection_id)` - Remove thumbnail file

**Metadata Returned:**

```python
{
    "duration": float,        # Video duration in seconds
    "video_codec": str,       # Codec name (e.g., "h264", "hevc")
    "video_width": int,       # Video width in pixels
    "video_height": int,      # Video height in pixels
    "file_type": str          # MIME type (e.g., "video/mp4")
}
```

**Thumbnail Extraction:**

- Default size: 320x240 pixels
- Smart timestamp selection: `min(1 second, 10% of duration)`
- Maintains aspect ratio with black padding
- Output naming: `{detection_id}_video_thumb.jpg`

**Error Handling:**

- Raises `VideoProcessingError` for metadata extraction failures
- Logs warning if ffmpeg/ffprobe not found in PATH
- Returns `None` from thumbnail extraction on failure
- Handles subprocess timeouts (30 second limit)

**Dependencies:**

- Requires `ffmpeg` and `ffprobe` in system PATH
- Install: `brew install ffmpeg` (macOS) or `apt install ffmpeg` (Linux)

### pipeline_workers.py

**Purpose:** Background worker processes for continuous detection and analysis processing.

**Worker Classes:**

- `DetectionQueueWorker` - Consumes from detection_queue, runs RT-DETRv2 detection
- `AnalysisQueueWorker` - Consumes from analysis_queue, runs Nemotron LLM analysis
- `BatchTimeoutWorker` - Periodically checks and closes timed-out batches
- `QueueMetricsWorker` - Updates Prometheus metrics for queue depths
- `PipelineWorkerManager` - Unified lifecycle management for all workers

### retry_handler.py

**Purpose:** Retry logic with exponential backoff and dead-letter queue support.

**DLQ Structure:**

```
dlq:detection_queue  - Failed detection jobs
dlq:analysis_queue   - Failed LLM analysis jobs
```

### service_managers.py

**Purpose:** Strategy pattern for managing external services (Redis, RT-DETRv2, Nemotron).

- `ShellServiceManager` - Shell script restarts (dev)
- `DockerServiceManager` - Docker container restarts (prod)

### health_monitor.py

**Purpose:** Monitors service health and orchestrates automatic recovery with exponential backoff.

**Key Features:**

- Periodic health checks for all configured services (Redis, RT-DETRv2, Nemotron)
- Automatic restart with exponential backoff on failure
- Configurable max retries before giving up
- WebSocket broadcast of service status changes
- Graceful shutdown support

**Status Values:**

- `healthy` - Service responding normally
- `unhealthy` - Health check failed
- `restarting` - Restart in progress
- `restart_failed` - Restart attempt failed
- `failed` - Max retries exceeded, giving up

**Public API (import directly):**

```python
from backend.services.health_monitor import ServiceHealthMonitor

monitor = ServiceHealthMonitor(
    manager=service_manager,
    services=[redis_config, rtdetr_config, nemotron_config],
    broadcaster=event_broadcaster,
    check_interval=15.0  # seconds
)
await monitor.start()
await monitor.stop()
```

### cleanup_service.py

**Purpose:** Automated data retention and disk space management service.

### event_broadcaster.py

**Purpose:** Real-time event distribution via WebSocket using Redis pub/sub backbone.

**Key Features:**

- Publishes events to Redis pub/sub channel `security_events`
- WebSocket clients subscribe to receive real-time updates
- Message envelope format for type discrimination

**Message Format:**

```json
{
  "type": "event",
  "data": {
    "event_id": 123,
    "camera_id": "front_door",
    "risk_score": 65,
    "risk_level": "high",
    "summary": "Person detected near entrance",
    "started_at": "2024-01-15T10:30:00.000000",
    "ended_at": "2024-01-15T10:31:00.000000"
  }
}
```

**Public API:**

- `EventBroadcaster(redis_client)` - Initialize with Redis client
- `async broadcast_event(event)` - Publish event to security_events channel
- `CHANNEL_NAME = "security_events"` - Canonical channel name constant

### gpu_monitor.py

**Purpose:** NVIDIA GPU statistics monitoring using pynvml.

### system_broadcaster.py

**Purpose:** WebSocket broadcaster for comprehensive system status updates.

### prompts.py

**Purpose:** Centralized prompt templates for LLM analysis.

### alert_engine.py

**Purpose:** Core engine for evaluating alert rules against events and detections.

**Key Features:**

- Loads and evaluates all enabled AlertRule records
- Uses AND logic within rules (all conditions must match)
- Supports multiple condition types: risk_threshold, object_types, camera_ids, zone_ids, min_confidence, schedule
- Respects cooldown periods using dedup_key
- Creates Alert records for triggered rules

**Public API:**

- `AlertRuleEngine(session, redis_client)` - Initialize with database session
- `async evaluate_event(event, detections, current_time)` - Evaluate all rules against event
- `async create_alerts_for_event(event, triggered_rules)` - Create Alert records
- `async test_rule_against_events(rule, events)` - Test rule configuration

### circuit_breaker.py

**Purpose:** Circuit breaker pattern implementation for external service protection.

**States:**

- CLOSED: Normal operation, calls pass through
- OPEN: Circuit tripped, calls rejected immediately
- HALF_OPEN: Recovery testing, limited calls allowed

**Key Features:**

- Configurable failure thresholds and recovery timeouts
- Half-open state for gradual recovery testing
- Excluded exceptions that don't count as failures
- Thread-safe async implementation
- Registry for managing multiple circuit breakers

**Public API:**

- `CircuitBreaker(name, config)` - Create circuit breaker
- `async call(operation, *args, **kwargs)` - Execute through circuit breaker
- `get_circuit_breaker(name, config)` - Get from global registry
- Supports async context manager: `async with breaker: ...`

### retry_handler.py

**Purpose:** Retry logic with exponential backoff and dead-letter queue (DLQ) support.

**Key Features:**

- Configurable max retries, base delay, max delay
- Exponential backoff with optional jitter
- Moves failed jobs to DLQ after exhausting retries
- DLQ inspection and management

**DLQ Queues:**

- `dlq:detection_queue` - Failed detection jobs
- `dlq:analysis_queue` - Failed LLM analysis jobs

**Public API:**

- `RetryHandler(redis_client, config)` - Initialize handler
- `async with_retry(operation, job_data, queue_name)` - Execute with retries
- `async get_dlq_stats()` - Get DLQ statistics
- `async get_dlq_jobs(dlq_name)` - Inspect DLQ contents
- `async requeue_dlq_job(dlq_name)` - Move job back to processing

### severity.py

**Purpose:** Configurable severity level mapping and utilities.

**Key Features:**

- Maps risk scores (0-100) to severity levels (LOW/MEDIUM/HIGH/CRITICAL)
- Configurable thresholds via settings
- Severity comparison functions (gt, gte, lt, lte)
- Color mapping for UI display

**Default Thresholds:**

- LOW: 0-29
- MEDIUM: 30-59
- HIGH: 60-84
- CRITICAL: 85-100

### search.py

**Purpose:** Full-text search for events using PostgreSQL TSVECTOR.

**Key Features:**

- Searches across summary, reasoning, object_types
- Supports filtering by camera, risk level, date range
- Pagination with total count

**Public API:**

- `async search_events(session, query, filters, page, page_size)` - Execute search
- `async update_event_object_types(session, event, detection_ids)` - Update cached types
- `async refresh_event_search_vector(session, event_id)` - Refresh TSVECTOR

### zone_service.py

**Purpose:** Zone detection and context generation for detections.

**Key Features:**

- Determines which zones contain a detection (point-in-polygon)
- Generates context strings for LLM prompts
- Supports priority-based zone resolution for overlapping zones

**Public API:**

- `point_in_zone(x, y, zone)` - Check if point is in zone
- `detection_in_zone(detection, zone)` - Check if detection bbox center is in zone
- `get_zones_for_detection(session, detection)` - Get all matching zones
- `get_highest_priority_zone(session, detection)` - Get primary zone
- `zones_to_context(zones)` - Generate context string for LLM

### audit.py

**Purpose:** Audit logging for security-sensitive operations.

**Key Features:**

- Records who, what, when, where for sensitive actions
- Captures client IP and user agent
- Supports success/failure status tracking

**Auditable Actions:**

- Event review/dismissal
- Settings changes
- Media exports
- Alert rule CRUD
- Camera CRUD
- API key management

**Public API:**

- `AuditService(session)` - Initialize with database session
- `async log_action(action, resource_type, resource_id, actor, ...)` - Record action
- `audit_service` - Global singleton accessor

### clip_generator.py

**Purpose:** Generate video clips for security events using ffmpeg.

**Key Features:**

- Creates clips from detection images for an event
- Configurable output format and quality
- Async subprocess execution

**Public API:**

- `ClipGenerator(output_dir)` - Initialize with output directory
- `async generate_clip(event_id, image_paths)` - Create video clip
- `get_clip_path(event_id)` - Get output path for event

### performance_collector.py

**Purpose:** Collects system performance metrics from all components for the System Performance Dashboard.

**Key Features:**

- Aggregates metrics from GPU, AI models, databases, host system, and containers
- Uses pynvml for direct GPU metrics or falls back to AI container health endpoints
- Collects PostgreSQL metrics (connections, cache hit ratio, transactions)
- Collects Redis metrics (clients, memory, hit ratio)
- Host metrics via psutil (CPU, RAM, disk)
- Alert threshold checking with warning and critical levels
- Metrics broadcast via WebSocket every 5 seconds

**Metrics Sources:**

| Source     | Method                         | Metrics                               |
| ---------- | ------------------------------ | ------------------------------------- |
| GPU        | pynvml or HTTP fallback        | Utilization, VRAM, temperature, power |
| RT-DETRv2  | HTTP `/health` endpoint        | Status, VRAM, model name, device      |
| Nemotron   | HTTP `/slots` endpoint         | Status, active/total slots, context   |
| PostgreSQL | SQL queries (pg_stat_activity) | Connections, cache hit ratio, txns    |
| Redis      | redis-py INFO command          | Clients, memory, hit ratio, blocked   |
| Host       | psutil                         | CPU%, RAM GB, disk GB                 |
| Containers | HTTP health endpoints          | Status, health for each container     |
| Inference  | PipelineLatencyTracker         | RT-DETR/Nemotron/pipeline latencies   |

**Alert Thresholds:**

- GPU temperature: warning 75C, critical 85C
- GPU utilization: warning 90%, critical 98%
- GPU VRAM: warning 90%, critical 95%
- PostgreSQL connections: warning 80%, critical 95%
- PostgreSQL cache hit: warning below 90%, critical below 80%
- Redis memory: warning 100MB, critical 500MB
- Host CPU: warning 80%, critical 95%
- Host RAM: warning 85%, critical 95%
- Host disk: warning 80%, critical 90%

**Public API (import directly):**

```python
from backend.services.performance_collector import PerformanceCollector

collector = PerformanceCollector()
metrics = await collector.collect_all()  # Returns PerformanceUpdate schema
await collector.close()
```

## Data Flow Between Services

### Complete Pipeline Flow

```
1. FileWatcher
   | Detects new image or video files
   | Validates media file integrity
   | Checks for duplicates via DedupeService
   | Queues to Redis: detection_queue (with media_type)

2. [DetectionQueueWorker]
   | Consumes from: detection_queue
   | Calls: DedupeService.is_duplicate_and_mark()
   | For images: Calls DetectorClient.detect_objects()
   | For videos: Calls VideoProcessor.extract_thumbnail() then DetectorClient
   | Stores: Detection records in PostgreSQL

3. [DetectionQueueWorker]
   | Calls: BatchAggregator.add_detection(confidence, object_type)
   |---> [Fast Path] If high-confidence critical detection:
   |     | Calls: NemotronAnalyzer.analyze_detection_fast_path()
   |     | Creates: Event with is_fast_path=True
   |
   └---> [Normal Path] Otherwise:
         | Updates Redis batch keys

4. [BatchTimeoutWorker]
   | Calls: BatchAggregator.check_batch_timeouts()
   | Queues to Redis: analysis_queue

5. [AnalysisQueueWorker]
   | Consumes from: analysis_queue
   | Calls: NemotronAnalyzer.analyze_batch()
   | Stores: Event records in PostgreSQL

6. [NemotronAnalyzer]
   | Calls: EventBroadcaster.broadcast_event()
   | Publishes: Redis pub/sub channel "security_events"
   | Broadcasts: WebSocket to all connected clients

7. [AlertRuleEngine] (After Event Creation)
   | Loads: All enabled AlertRule records
   | Evaluates: Each rule's conditions against event
   | Creates: Alert records for triggered rules
   | Calls: NotificationService.send_alert()
   | Delivers: Notifications via configured channels

8. [On Demand]
   | Calls: ThumbnailGenerator.generate_thumbnail()
   | Stores: Thumbnail files in data/thumbnails/
```

**Background Services (Parallel):**

```
GPUMonitor (Continuous Polling)
   | Every poll_interval seconds (default from settings)
   | Reads: pynvml GPU metrics
   | Stores: GPUStats records in PostgreSQL
   | Appends: In-memory circular buffer (max 1000)
   | Broadcasts: WebSocket to SystemBroadcaster (optional)

SystemBroadcaster (Periodic Broadcasting)
   | Every 5 seconds (configurable)
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
   | Logs: CleanupStats (records deleted, space reclaimed)

ServiceHealthMonitor (Periodic Health Checks)
   | Every check_interval seconds (default: 15s)
   | Checks: HTTP health endpoints for RT-DETRv2, Nemotron
   | Checks: Redis via redis-cli ping
   | Restarts: Failed services with exponential backoff
   | Broadcasts: Service status changes via WebSocket

QueueMetricsWorker (Periodic Metrics)
   | Every update_interval seconds (default: 5s)
   | Queries: Redis queue lengths
   | Updates: Prometheus gauge metrics
```

### Redis Queue Structure

**detection_queue (image):**

```json
{
  "camera_id": "front_door",
  "file_path": "/export/foscam/front_door/image_001.jpg",
  "timestamp": "2024-01-15T10:30:00.000000",
  "media_type": "image",
  "file_hash": "abc123..."
}
```

**detection_queue (video):**

```json
{
  "camera_id": "front_door",
  "file_path": "/export/foscam/front_door/video_001.mp4",
  "timestamp": "2024-01-15T10:30:00.000000",
  "media_type": "video",
  "file_hash": "def456..."
}
```

## Dependencies

### External Services

- **RT-DETRv2 HTTP server** (port 8090) - Object detection
- **llama.cpp server** (port 8080) - LLM inference
- **Redis** - Queue and cache storage
- **PostgreSQL** - Persistent storage (via SQLAlchemy async)
- **ffmpeg/ffprobe** - Video processing (system binaries)

### Python Packages

- `watchdog` - Filesystem monitoring
- `httpx` - Async HTTP client
- `PIL/Pillow` - Image processing
- `sqlalchemy[asyncio]` - Database ORM
- `redis` - Redis client
- `pynvml` - NVIDIA GPU monitoring (optional)
- `fastapi` - WebSocket support

## Related Documentation

- `/backend/AGENTS.md` - Backend architecture overview
- `/backend/models/AGENTS.md` - Database model documentation
- `/backend/api/routes/AGENTS.md` - API endpoint documentation
- `/backend/core/AGENTS.md` - Core infrastructure documentation
- `/backend/examples/AGENTS.md` - Example code and usage patterns
