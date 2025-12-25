# Backend Services Directory

## Purpose

This directory contains the core business logic and background services for the AI-powered home security monitoring system. Services orchestrate the complete detection pipeline from file monitoring through AI analysis to event creation.

## Architecture Overview

The services implement a multi-stage async pipeline with real-time broadcasting and background maintenance:

```
File Upload → Detection → Batching → Analysis → Event Creation → Broadcasting
   (1)          (2)         (3)         (4)         (5)              (6)

                     Monitoring Services (Parallel)
                     ├── GPUMonitor (polls GPU stats)
                     ├── SystemBroadcaster (system status)
                     └── CleanupService (retention policy)
```

### Core AI Pipeline Services

1. **FileWatcher** - Monitors camera directories for new uploads
2. **DetectorClient** - Sends images to RT-DETRv2 for object detection
3. **BatchAggregator** - Groups detections into time-based batches
4. **NemotronAnalyzer** - Analyzes batches with LLM for risk scoring
5. **ThumbnailGenerator** - Creates preview images with bounding boxes
6. **EventBroadcaster** - Distributes events via WebSocket to frontend

### Background Services

- **GPUMonitor** - Polls NVIDIA GPU metrics and stores statistics
- **SystemBroadcaster** - Aggregates and broadcasts system health status
- **CleanupService** - Enforces data retention policies and frees disk space

## Service Files Overview

| Service                  | Purpose                                     | Type          | Dependencies                         |
| ------------------------ | ------------------------------------------- | ------------- | ------------------------------------ |
| `file_watcher.py`        | Monitor camera directories for new uploads  | Core Pipeline | watchdog, Redis                      |
| `detector_client.py`     | Send images to RT-DETRv2 for detection      | Core Pipeline | httpx, SQLAlchemy                    |
| `batch_aggregator.py`    | Group detections into time-based batches    | Core Pipeline | Redis                                |
| `nemotron_analyzer.py`   | LLM-based risk analysis via llama.cpp       | Core Pipeline | httpx, SQLAlchemy, Redis             |
| `thumbnail_generator.py` | Generate preview images with bounding boxes | Core Pipeline | PIL/Pillow                           |
| `event_broadcaster.py`   | Distribute events via WebSocket             | Broadcasting  | Redis, FastAPI WebSocket             |
| `gpu_monitor.py`         | Poll NVIDIA GPU metrics                     | Background    | pynvml, SQLAlchemy                   |
| `system_broadcaster.py`  | Broadcast system health status              | Broadcasting  | SQLAlchemy, Redis, FastAPI WebSocket |
| `cleanup_service.py`     | Enforce data retention policies             | Background    | SQLAlchemy                           |
| `prompts.py`             | LLM prompt templates                        | Utility       | -                                    |

## Service Files

### file_watcher.py

**Purpose:** Monitors Foscam camera upload directories and queues images for processing.

**Key Features:**

- Watchdog-based filesystem monitoring (recursive)
- Debounce logic (0.5s default) to wait for complete file writes
- Image integrity validation using PIL (checks for corruption, zero-byte files)
- Async-compatible design with thread-safe event loop scheduling
- Extracts camera ID from path structure: `/export/foscam/{camera_id}/`

**Public API:**

- `FileWatcher(camera_root, redis_client, debounce_delay, queue_name)` - Initialize watcher
- `async start()` - Begin monitoring camera directories
- `async stop()` - Gracefully shutdown (cancels pending tasks)
- `is_image_file(path)` - Validate image extension (.jpg, .jpeg, .png)
- `is_valid_image(path)` - Validate image integrity with PIL

**Data Flow:**

1. Watchdog detects file creation/modification event
2. Schedules async task via `asyncio.run_coroutine_threadsafe()`
3. Debounces by cancelling/recreating pending task on each event
4. After debounce delay, validates image and extracts camera ID
5. Queues to Redis `detection_queue` with `{camera_id, file_path, timestamp}`

**Error Handling:**

- Warns on invalid/corrupted images (skips processing)
- Logs errors for queue failures
- Creates camera root directory if missing

### detector_client.py

**Purpose:** HTTP client for RT-DETRv2 object detection service.

**Key Features:**

- Async HTTP client using httpx
- Confidence threshold filtering (default from config)
- Direct database persistence (creates Detection records)
- 30-second timeout for detection requests

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

- Returns empty list `[]` on all errors:
  - Connection errors (service unreachable)
  - Timeouts (30s exceeded)
  - HTTP errors (non-200 status)
  - Invalid JSON response
  - Missing image files
- Logs detailed error messages for debugging

### batch_aggregator.py

**Purpose:** Groups detections into time-based batches for efficient LLM analysis.

**Batching Rules:**

- **Window timeout:** 90 seconds from batch start (configurable)
- **Idle timeout:** 30 seconds since last detection (configurable)
- **One batch per camera:** Each camera has max 1 active batch at a time
- **Fast path:** High-confidence critical detections bypass batching for immediate analysis

**Redis Keys:**

```
batch:{camera_id}:current         → current batch ID (string)
batch:{batch_id}:camera_id        → camera ID (string)
batch:{batch_id}:detections       → JSON array of detection IDs
batch:{batch_id}:started_at       → Unix timestamp (float)
batch:{batch_id}:last_activity    → Unix timestamp (float)
```

**Public API:**

- `BatchAggregator(redis_client, analyzer)` - Initialize with Redis and optional analyzer for fast path
- `async add_detection(camera_id, detection_id, file_path, confidence, object_type)` - Add to batch, returns batch_id; triggers fast path if criteria met
- `async check_batch_timeouts()` - Close expired batches, returns closed batch IDs
- `async close_batch(batch_id)` - Force close and push to analysis queue

**Fast Path:**

High-priority detections can bypass normal batching for immediate analysis:
- Triggered when confidence >= `fast_path_confidence_threshold` (from settings)
- AND object_type is in `fast_path_object_types` list (from settings)
- Immediately calls `NemotronAnalyzer.analyze_detection_fast_path()`
- Returns `fast_path_{detection_id}` as batch ID

**Data Flow:**

1. Check for existing batch for camera (`batch:{camera_id}:current`)
2. If none exists, create new batch with UUID
3. Add detection ID to batch's detection list
4. Update `last_activity` timestamp
5. On timeout/close: push to `analysis_queue` with `{batch_id, camera_id, detection_ids, timestamp}`
6. Clean up all Redis keys for closed batch

**Error Handling:**

- Raises `RuntimeError` if Redis client not initialized
- Raises `ValueError` if batch not found during close
- Logs warnings for batches missing timestamps
- Continues processing other batches if one fails during timeout check

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
- `async analyze_detection_fast_path(camera_id, detection_id)` - Analyze single detection immediately (bypasses batching)
- `async health_check()` - Check if LLM server is reachable

**Data Flow:**

1. Fetch batch metadata from Redis (`batch:{batch_id}:camera_id`, `batch:{batch_id}:detections`)
2. Query database for Detection records and Camera name
3. Format prompt with camera, time window, detection list (see `prompts.py`)
4. POST to `{nemotron_url}/completion` with `{prompt, temperature: 0.7, max_tokens: 500}`
5. Extract JSON from completion text using regex pattern
6. Validate risk data (score 0-100, level in [low, medium, high, critical])
7. Create Event record with risk assessment (includes `is_fast_path` flag for fast path events)
8. Broadcast to WebSocket channel `events` (if available)

**Fast Path Analysis:**

For single high-priority detections:
1. Convert detection_id to int
2. Query database for Detection record and Camera name
3. Format prompt with single detection
4. Call LLM for risk analysis
5. Create Event with `is_fast_path=True`
6. Broadcast via WebSocket

**Error Handling:**

- Fallback risk data on LLM failure:
  - `risk_score: 50`
  - `risk_level: "medium"`
  - `summary: "Analysis unavailable - LLM service error"`
- Raises `ValueError` if batch not found or has no detections
- Raises `RuntimeError` if Redis client not initialized
- Continues event creation even if WebSocket broadcast fails
- Validates and normalizes all risk data fields

**LLM Response Format:**

```json
{
  "risk_score": 65,
  "risk_level": "high",
  "summary": "Unknown person detected at night",
  "reasoning": "Single person detection at 2:15 AM is unusual..."
}
```

### thumbnail_generator.py

**Purpose:** Generate thumbnail previews with bounding boxes for detection visualization.

**Key Features:**

- Draws colored bounding boxes based on object type
- Adds text labels with confidence scores
- Resizes to 320x240 with aspect ratio preservation
- Saves as optimized JPEG (quality 85)
- No external service dependencies (pure PIL/Pillow)

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

**Data Flow:**

1. Load original image with PIL
2. Convert to RGB if needed
3. Draw bounding boxes (3px line width)
4. Add text labels above boxes (white text on colored background)
5. Resize to target size with black padding (maintains aspect ratio)
6. Save as `{detection_id}_thumb.jpg` in output directory

**Error Handling:**

- Returns `None` on failure (logs error)
- Skips detections with incomplete bbox coordinates
- Falls back to default PIL font if TrueType fonts unavailable
- Handles FileNotFoundError, PermissionError gracefully

**Detection Dict Format:**

```python
{
    "object_type": "person",
    "confidence": 0.95,
    "bbox_x": 100,
    "bbox_y": 150,
    "bbox_width": 200,
    "bbox_height": 400
}
```

### cleanup_service.py

**Purpose:** Automated data retention and disk space management service.

**Key Features:**

- Scheduled daily cleanup at configurable time (default: 03:00)
- Enforces retention policy (default: 30 days)
- Cascade deletion: Events, Detections, GPU Stats, Logs
- File cleanup: Thumbnails and optionally original images
- Transaction-safe with rollback support
- Detailed statistics on cleanup operations

**Public API:**

- `CleanupService(cleanup_time, retention_days, thumbnail_dir, delete_images)` - Initialize
- `async start()` - Start scheduled cleanup loop
- `async stop()` - Stop cleanup and cancel tasks
- `async run_cleanup()` - Execute cleanup operation manually
- `get_cleanup_stats()` - Get service status and next cleanup time

**Cleanup Process:**

1. Calculate cutoff date (now - retention_days)
2. Query detections older than cutoff (collect file paths)
3. Delete old detections from database
4. Delete old events from database (cascade)
5. Delete old GPU stats from database
6. Commit database transaction
7. Delete old logs from database (uses `log_retention_days` from settings)
8. Delete thumbnail files from disk
9. Delete original image files (if enabled)

**CleanupStats:**

```python
{
    "events_deleted": int,        # Events removed
    "detections_deleted": int,    # Detections removed
    "gpu_stats_deleted": int,     # GPU stat records removed
    "logs_deleted": int,          # Log records removed
    "thumbnails_deleted": int,    # Thumbnail files removed
    "images_deleted": int,        # Original images removed
    "space_reclaimed": int        # Disk space freed (bytes)
}
```

**Error Handling:**

- Validates cleanup_time format (HH:MM 24-hour)
- Rolls back database transaction on failure
- Continues loop even if single cleanup fails
- Logs warnings for missing files
- Graceful cancellation with CancelledError handling

### event_broadcaster.py

**Purpose:** Real-time event distribution via WebSocket using Redis pub/sub backbone.

**Key Features:**

- Manages WebSocket connection lifecycle
- Bridges Redis pub/sub to WebSocket clients
- Supports multiple backend instances (via Redis)
- Automatic cleanup of disconnected clients
- Idempotent start/stop operations

**Public API:**

- `EventBroadcaster(redis_client)` - Initialize with Redis client
- `async start()` - Start listening on Redis pub/sub channel
- `async stop()` - Stop listener and disconnect all clients
- `async connect(websocket)` - Register new WebSocket connection
- `async disconnect(websocket)` - Unregister WebSocket connection
- `async broadcast_event(event_data)` - Publish event to Redis channel

**Redis Channel:**

- Channel name: `security_events`
- Message format: `{"type": "event", "data": {...}}`

**Data Flow:**

1. Event created → `broadcast_event()` publishes to Redis
2. Redis pub/sub broadcasts to all backend instances
3. `_listen_for_events()` receives message from Redis
4. `_send_to_all_clients()` sends to all WebSocket connections
5. Frontend receives real-time update

**Error Handling:**

- Removes failed connections automatically
- Continues listening after individual message failures
- Restarts listener task if error occurs
- Graceful shutdown with task cancellation

**Factory Functions:**

- `get_broadcaster(redis_client)` - Get/create global singleton
- `stop_broadcaster()` - Stop and cleanup global instance

### gpu_monitor.py

**Purpose:** NVIDIA GPU statistics monitoring using pynvml.

**Key Features:**

- Async polling at configurable intervals (default from settings)
- Graceful handling of missing GPU or driver
- In-memory circular buffer for quick access
- Database persistence for historical analysis
- Mock data mode when GPU unavailable
- Optional WebSocket broadcasting

**Public API:**

- `GPUMonitor(poll_interval, history_minutes, broadcaster)` - Initialize
- `async start()` - Start GPU monitoring loop
- `async stop()` - Stop monitoring and cleanup NVML
- `get_current_stats()` - Get current GPU stats (real or mock)
- `get_stats_history(minutes)` - Get in-memory stats history
- `async get_stats_from_db(minutes, limit)` - Query database for stats

**GPU Metrics Collected:**

```python
{
    "gpu_name": str,              # GPU model name
    "gpu_utilization": float,     # GPU usage percentage (0-100)
    "memory_used": int,           # Memory used in MB
    "memory_total": int,          # Total memory in MB
    "temperature": float,         # Temperature in Celsius
    "power_usage": float,         # Power usage in Watts
    "recorded_at": datetime       # Timestamp
}
```

**Data Flow:**

1. Poll GPU metrics via pynvml every `poll_interval` seconds
2. Append to in-memory circular buffer (max 1000 entries)
3. Store in database (GPUStats table)
4. Broadcast via WebSocket (if broadcaster provided)

**Error Handling:**

- Falls back to mock data if pynvml unavailable
- Returns None for metrics that fail to read
- Continues polling even if single iteration fails
- Safely shuts down NVML on stop
- Logs all errors with context

**Mock Mode:**

Activated when:

- pynvml not installed
- No NVIDIA GPU present
- NVML initialization fails
- Driver not available

### system_broadcaster.py

**Purpose:** WebSocket broadcaster for comprehensive system status updates.

**Key Features:**

- Periodic broadcasting of system metrics (default: 5s interval)
- Aggregates data from multiple sources (GPU, cameras, queues, health)
- Sends initial status immediately on connection
- Automatic cleanup of failed connections
- Graceful error handling per metric category

**Public API:**

- `SystemBroadcaster()` - Initialize broadcaster
- `async connect(websocket)` - Add WebSocket connection
- `async disconnect(websocket)` - Remove WebSocket connection
- `async broadcast_status(status_data)` - Send status to all clients
- `async start_broadcasting(interval)` - Start periodic broadcasts
- `async stop_broadcasting()` - Stop periodic broadcasts

**System Status Structure:**

```python
{
    "type": "system_status",
    "data": {
        "gpu": {
            "utilization": float,      # GPU usage %
            "memory_used": int,        # Memory MB
            "memory_total": int,       # Total memory MB
            "temperature": float,      # Temperature C
            "inference_fps": float     # Inference FPS
        },
        "cameras": {
            "active": int,             # Online cameras
            "total": int               # Total cameras
        },
        "queue": {
            "pending": int,            # Detection queue length
            "processing": int          # Analysis queue length
        },
        "health": str                  # "healthy", "degraded", "unhealthy"
    },
    "timestamp": str                   # ISO format
}
```

**Data Sources:**

1. **GPU Stats:** Latest record from GPUStats table
2. **Camera Stats:** Count queries on Camera table
3. **Queue Stats:** Redis queue length queries
4. **Health Status:** Database + Redis connectivity checks

**Error Handling:**

- Returns null values if GPU stats unavailable
- Returns zero counts if database query fails
- Returns zero counts if Redis unavailable
- Falls back to "unhealthy" if health check fails
- Continues broadcasting even if one metric fails
- Removes disconnected clients automatically

**Factory Function:**

- `get_system_broadcaster()` - Get/create global singleton

### prompts.py

**Purpose:** Centralized prompt templates for LLM analysis.

**Contents:**

- `RISK_ANALYSIS_PROMPT` - Template for Nemotron risk assessment
  - Variables: `{camera_name}`, `{start_time}`, `{end_time}`, `{detections_list}`
  - Specifies JSON response format
  - Includes risk level guidelines

## Data Flow Between Services

### Complete Pipeline Flow

**Core AI Pipeline:**

```
1. FileWatcher
   ↓ Queues to Redis: detection_queue

2. [Background Worker]
   ↓ Consumes from: detection_queue
   ↓ Calls: DetectorClient.detect_objects()
   ↓ Stores: Detection records in SQLite

3. [Background Worker]
   ↓ Calls: BatchAggregator.add_detection(confidence, object_type)
   ├─→ [Fast Path] If high-confidence critical detection:
   │   ↓ Calls: NemotronAnalyzer.analyze_detection_fast_path()
   │   ↓ Creates: Event with is_fast_path=True
   │   ↓ Broadcasts: WebSocket immediately
   │
   └─→ [Normal Path] Otherwise:
       ↓ Updates Redis batch keys

4. [Periodic Task]
   ↓ Calls: BatchAggregator.check_batch_timeouts()
   ↓ Queues to Redis: analysis_queue

5. [Background Worker]
   ↓ Consumes from: analysis_queue
   ↓ Calls: NemotronAnalyzer.analyze_batch()
   ↓ Stores: Event records in SQLite

6. [Background Worker]
   ↓ Calls: EventBroadcaster.broadcast_event()
   ↓ Publishes: Redis pub/sub channel "security_events"
   ↓ Broadcasts: WebSocket to all connected clients

7. [On Demand]
   ↓ Calls: ThumbnailGenerator.generate_thumbnail()
   ↓ Stores: Thumbnail files in data/thumbnails/
```

**Background Services (Parallel):**

```
GPUMonitor (Continuous Polling)
   ↓ Every poll_interval seconds (default from settings)
   ↓ Reads: pynvml GPU metrics
   ↓ Stores: GPUStats records in SQLite
   ↓ Appends: In-memory circular buffer (max 1000)
   ↓ Broadcasts: WebSocket to SystemBroadcaster (optional)

SystemBroadcaster (Periodic Broadcasting)
   ↓ Every 5 seconds (configurable)
   ↓ Queries: Latest GPUStats, Camera counts, Redis queue lengths
   ↓ Checks: Database + Redis health
   ↓ Broadcasts: WebSocket system_status to all connected clients

CleanupService (Daily Scheduled)
   ↓ Once per day at cleanup_time (default: 03:00)
   ↓ Deletes: Events, Detections, GPUStats older than retention_days
   ↓ Deletes: Logs older than log_retention_days
   ↓ Removes: Thumbnail files (and optionally original images)
   ↓ Logs: CleanupStats (records deleted, space reclaimed)
```

### Redis Queue Structure

**detection_queue:**

```json
{
  "camera_id": "front_door",
  "file_path": "/export/foscam/front_door/image_001.jpg",
  "timestamp": "2024-01-15T10:30:00.000000"
}
```

**analysis_queue:**

```json
{
  "batch_id": "a3f9c8b2d1e4",
  "camera_id": "front_door",
  "detection_ids": ["det_001", "det_002", "det_003"],
  "timestamp": 1705317000.123
}
```

## Async Patterns Used

### Thread-Safe Event Loop Scheduling

**FileWatcher** bridges synchronous Watchdog callbacks to async processing:

```python
# In watchdog thread:
asyncio.run_coroutine_threadsafe(
    self.watcher._schedule_file_processing(file_path),
    self.watcher._loop,
)
```

### Debounce with Task Cancellation

**FileWatcher** cancels pending tasks when new events arrive:

```python
if file_path in self._pending_tasks:
    self._pending_tasks[file_path].cancel()

task = asyncio.create_task(self._debounced_process(file_path))
self._pending_tasks[file_path] = task
```

### Context Manager Database Sessions

**NemotronAnalyzer** uses async context managers for database access:

```python
async with get_session() as session:
    # Query database
    result = await session.execute(select(Detection).where(...))
```

### HTTP Client Resource Management

**DetectorClient** and **NemotronAnalyzer** use async context managers for HTTP:

```python
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.post(url, files=files)
```

## Error Handling and Fallbacks

### Graceful Degradation

1. **DetectorClient:** Returns empty list on all errors (no crashes)
2. **NemotronAnalyzer:** Falls back to default risk score (50, medium) on LLM failure
3. **ThumbnailGenerator:** Returns `None` on failure (allows processing to continue)
4. **FileWatcher:** Skips invalid images, logs warnings (doesn't stop monitoring)

### Idempotent Operations

- **FileWatcher.start()** can be called multiple times safely
- **BatchAggregator** creates new batch if none exists (no race conditions)

### Resource Cleanup

- **FileWatcher.stop()** cancels all pending tasks with timeout
- Redis keys are cleaned up after batch close
- Database sessions are automatically committed/rolled back via async context managers

## Configuration

All services use `backend.core.config.get_settings()` for configuration:

- `foscam_base_path` - Camera upload directory
- `rtdetr_url` - RT-DETRv2 service endpoint
- `nemotron_url` - Nemotron llama.cpp server endpoint
- `detection_confidence_threshold` - Minimum confidence for detections
- `batch_window_seconds` - Maximum batch duration (default: 90s)
- `batch_idle_timeout_seconds` - Idle timeout before closing batch (default: 30s)
- `fast_path_confidence_threshold` - Minimum confidence for fast path (bypasses batching)
- `fast_path_object_types` - Object types eligible for fast path (e.g., ["person"])
- `gpu_poll_interval_seconds` - GPU monitoring poll interval
- `gpu_stats_history_minutes` - GPU stats in-memory history retention
- `retention_days` - Data retention period for cleanup service
- `log_retention_days` - Log retention period for cleanup service

## Dependencies

### External Services

- **RT-DETRv2 HTTP server** (port 8001) - Object detection
- **llama.cpp server** (port 8080) - LLM inference
- **Redis** - Queue and cache storage
- **SQLite** - Persistent storage (via SQLAlchemy async)

### Python Packages

- `watchdog` - Filesystem monitoring
- `httpx` - Async HTTP client
- `PIL/Pillow` - Image processing
- `sqlalchemy[asyncio]` - Database ORM
- `redis` - Redis client
- `pynvml` - NVIDIA GPU monitoring (optional)
- `fastapi` - WebSocket support

## WebSocket Broadcasting Architecture

The system uses two distinct WebSocket channels for different data streams:

### Event Channel (EventBroadcaster)

- **Purpose:** Real-time security event notifications
- **Channel:** `security_events` (Redis pub/sub)
- **Data:** Individual security events with risk scores
- **Trigger:** Event creation after batch analysis
- **Pattern:** Publish to Redis → All instances listen → Broadcast to WebSocket clients

**Message Structure:**

```python
{
    "type": "event",
    "data": {
        "id": 1,
        "camera_id": "cam-123",
        "risk_score": 75,
        "risk_level": "high",
        "summary": "Person detected",
        "started_at": "2024-01-15T10:30:00",
        # ... other event fields
    }
}
```

### System Status Channel (SystemBroadcaster)

- **Purpose:** Periodic system health and metrics
- **Interval:** Every 5 seconds (configurable)
- **Data:** Aggregated system status (GPU, cameras, queues, health)
- **Trigger:** Periodic broadcast loop
- **Pattern:** Query all sources → Aggregate → Broadcast to WebSocket clients

**Message Structure:**

```python
{
    "type": "system_status",
    "data": {
        "gpu": {...},
        "cameras": {...},
        "queue": {...},
        "health": "healthy"
    },
    "timestamp": "2024-01-15T10:30:00.000Z"
}
```

### Multi-Instance Support

Both broadcasters support horizontal scaling via Redis:

1. **EventBroadcaster** - Uses Redis pub/sub to share events across instances
2. **SystemBroadcaster** - Each instance broadcasts independently (no shared state needed)

## Testing Considerations

All services include comprehensive error handling for testing:

### Core Services

- Mock Redis client by passing `redis_client=None` or mock instance
- Mock HTTP responses for DetectorClient and NemotronAnalyzer
- Mock filesystem events for FileWatcher
- Use in-memory PIL images for ThumbnailGenerator tests

### Broadcasting Services

- Mock WebSocket connections for EventBroadcaster and SystemBroadcaster
- Test connection lifecycle (connect/disconnect/error handling)
- Verify message formatting and delivery
- Test automatic cleanup of failed connections

### Background Services

- Mock pynvml for GPUMonitor (test with and without GPU)
- Mock database queries for SystemBroadcaster
- Test CleanupService with in-memory database or test fixtures
- Verify task cancellation and graceful shutdown

See `backend/tests/unit/` and `backend/tests/integration/` for test examples.
