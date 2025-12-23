# Backend Services Directory

## Purpose

This directory contains the core business logic and background services for the AI-powered home security monitoring system. Services orchestrate the complete detection pipeline from file monitoring through AI analysis to event creation.

## Architecture Overview

The services implement a multi-stage async pipeline:

```
File Upload → Detection → Batching → Analysis → Event Creation
   (1)          (2)         (3)         (4)         (5)
```

1. **FileWatcher** monitors camera directories for new uploads
2. **DetectorClient** sends images to RT-DETRv2 for object detection
3. **BatchAggregator** groups detections into time-based batches
4. **NemotronAnalyzer** analyzes batches with LLM for risk scoring
5. **ThumbnailGenerator** creates preview images with bounding boxes

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

**Redis Keys:**

```
batch:{camera_id}:current         → current batch ID (string)
batch:{batch_id}:camera_id        → camera ID (string)
batch:{batch_id}:detections       → JSON array of detection IDs
batch:{batch_id}:started_at       → Unix timestamp (float)
batch:{batch_id}:last_activity    → Unix timestamp (float)
```

**Public API:**

- `BatchAggregator(redis_client)` - Initialize with Redis
- `async add_detection(camera_id, detection_id, file_path)` - Add to batch, returns batch_id
- `async check_batch_timeouts()` - Close expired batches, returns closed batch IDs
- `async close_batch(batch_id)` - Force close and push to analysis queue

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
- `async health_check()` - Check if LLM server is reachable

**Data Flow:**

1. Fetch batch metadata from Redis (`batch:{batch_id}:camera_id`, `batch:{batch_id}:detections`)
2. Query database for Detection records and Camera name
3. Format prompt with camera, time window, detection list (see `prompts.py`)
4. POST to `{nemotron_url}/completion` with `{prompt, temperature: 0.7, max_tokens: 500}`
5. Extract JSON from completion text using regex pattern
6. Validate risk data (score 0-100, level in [low, medium, high, critical])
7. Create Event record with risk assessment
8. Broadcast to WebSocket channel `events` (if available)

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

### prompts.py

**Purpose:** Centralized prompt templates for LLM analysis.

**Contents:**

- `RISK_ANALYSIS_PROMPT` - Template for Nemotron risk assessment
  - Variables: `{camera_name}`, `{start_time}`, `{end_time}`, `{detections_list}`
  - Specifies JSON response format
  - Includes risk level guidelines

## Data Flow Between Services

### Complete Pipeline Flow

```
1. FileWatcher
   ↓ Queues to Redis: detection_queue

2. [Background Worker]
   ↓ Consumes from: detection_queue
   ↓ Calls: DetectorClient.detect_objects()
   ↓ Stores: Detection records in SQLite

3. [Background Worker]
   ↓ Calls: BatchAggregator.add_detection()
   ↓ Updates Redis batch keys

4. [Periodic Task]
   ↓ Calls: BatchAggregator.check_batch_timeouts()
   ↓ Queues to Redis: analysis_queue

5. [Background Worker]
   ↓ Consumes from: analysis_queue
   ↓ Calls: NemotronAnalyzer.analyze_batch()
   ↓ Stores: Event records in SQLite
   ↓ Publishes: WebSocket events channel

6. [On Demand]
   ↓ Calls: ThumbnailGenerator.generate_thumbnail()
   ↓ Stores: Thumbnail files in data/thumbnails/
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

## Testing Considerations

All services include comprehensive error handling for testing:

- Mock Redis client by passing `redis_client=None` or mock instance
- Mock HTTP responses for DetectorClient and NemotronAnalyzer
- Mock filesystem events for FileWatcher
- Use in-memory PIL images for ThumbnailGenerator tests

See `backend/tests/unit/services/` for test examples.
