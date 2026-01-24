# Batch Aggregator

The BatchAggregator groups detections by camera into time-based batches before LLM analysis, optimizing GPU utilization and context coherence.

## Overview

**Source:** `backend/services/batch_aggregator.py`

The aggregator provides:

1. **Time-window batching:** Group detections within 90-second windows
2. **Idle timeout:** Close batches after 30 seconds of inactivity
3. **Size limits:** Prevent memory exhaustion from large batches
4. **Fast path:** Bypass batching for high-confidence person detections

## Class Definition

```python
class BatchAggregator:  # Line 122
    """Aggregates detections into time-based batches for analysis."""
```

### Constructor Parameters (Lines 135-161)

| Parameter      | Type               | Default | Description                    |
| -------------- | ------------------ | ------- | ------------------------------ |
| `redis_client` | `RedisClient`      | None    | Redis client for batch storage |
| `analyzer`     | `NemotronAnalyzer` | None    | For fast path analysis         |

### Configured Values (Lines 144-150)

```python
settings = get_settings()
self._batch_window = settings.batch_window_seconds        # 90s
self._idle_timeout = settings.batch_idle_timeout_seconds  # 30s
self._fast_path_threshold = settings.fast_path_confidence_threshold  # 0.9
self._fast_path_types = settings.fast_path_object_types   # ["person"]
self._batch_max_detections = settings.batch_max_detections
```

## Redis Key Structure

All batch keys have 1-hour TTL for orphan cleanup (line 133):

```python
BATCH_KEY_TTL_SECONDS = 3600  # 1 hour
```

**Key Patterns:**

| Key                                    | Purpose                                      |
| -------------------------------------- | -------------------------------------------- |
| `batch:{camera_id}:current`            | Current batch ID for camera                  |
| `batch:{batch_id}:camera_id`           | Camera ID for batch                          |
| `batch:{batch_id}:detections`          | Redis LIST of detection IDs                  |
| `batch:{batch_id}:started_at`          | Batch start timestamp                        |
| `batch:{batch_id}:last_activity`       | Last activity timestamp                      |
| `batch:{batch_id}:pipeline_start_time` | First detection timestamp (latency tracking) |
| `batch:{batch_id}:closing`             | Closing flag to prevent races                |

## Batch ID Generation

```python
def generate_batch_id() -> str:  # Line 63
    """Generate a short, unique batch identifier."""
    return f"batch-{uuid.uuid4().hex[:8]}"
    # Example: "batch-a1b2c3d4"
```

## Adding Detections

**Source:** Lines 393-547

```python
async def add_detection(
    self,
    camera_id: str,
    detection_id: int | str,
    _file_path: str,
    confidence: float | None = None,
    object_type: str | None = None,
    pipeline_start_time: str | None = None,
) -> str:
    """Add detection to batch for camera."""
```

### Fast Path Check (Lines 443-454)

```python
# Check if detection meets fast path criteria
if self._should_use_fast_path(confidence, object_type):
    logger.info("Fast path triggered for detection")
    await self._process_fast_path(camera_id, detection_id_int)
    return f"fast_path_{detection_id_int}"
```

### Batch Size Limit (Lines 468-491)

```python
if batch_id:
    current_size = await self._redis._client.llen(detections_key)

    if current_size >= self._batch_max_detections:
        logger.info("Batch reached max size, closing")
        record_batch_max_reached(camera_id)

        # Close current batch and set batch_id to None
        await self._close_batch_for_size_limit(batch_id)
        batch_id = None
```

### Atomic Batch Creation (Lines 333-391, 493-516)

```python
if not batch_id:
    # Create new batch with human-readable ID
    batch_id = generate_batch_id()

    # Atomic transaction using Redis pipeline (MULTI/EXEC)
    await self._create_batch_metadata_atomic(
        batch_key=batch_key,
        batch_id=batch_id,
        camera_id=camera_id,
        current_time=current_time,
        ttl=ttl,
        pipeline_start_time=pipeline_start_time,
    )
```

### Atomic List Append (Lines 518-535)

```python
# Add detection using atomic RPUSH operation
detections_key = f"batch:{batch_id}:detections"
detection_count = await self._atomic_list_append(detections_key, detection_id_int, ttl)

# Update last activity timestamp
await self._redis.set(f"batch:{batch_id}:last_activity", str(current_time), expire=ttl)
```

## Concurrency Control

### Per-Camera Locks (Lines 154-158, 266-280)

```python
# Per-camera locks to prevent race conditions
self._camera_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

async def _get_camera_lock(self, camera_id: str) -> asyncio.Lock:
    """Get or create a lock for the specified camera."""
    async with self._locks_lock:
        return self._camera_locks[camera_id]
```

### Global Batch Close Lock (Lines 158-159)

```python
# Global lock for batch timeout checking and closing operations
self._batch_close_lock = asyncio.Lock()
```

## Batch Timeout Checking

**Source:** Lines 549-703

The `check_batch_timeouts()` method uses Redis pipelining to efficiently check all batches:

```python
async def check_batch_timeouts(self) -> list[str]:
    """Check all active batches for timeouts and close expired ones."""

    # Phase 1: Fetch all batch IDs using pipeline (lines 584-586)
    batch_id_pipe = redis_client.pipeline()
    for batch_key in batch_keys:
        batch_id_pipe.get(batch_key)
    batch_ids = await batch_id_pipe.execute()

    # Phase 2: Fetch all metadata in parallel (lines 613-617)
    metadata_pipe = redis_client.pipeline()
    for _batch_key, batch_id in valid_batches:
        metadata_pipe.get(f"batch:{batch_id}:started_at")
        metadata_pipe.get(f"batch:{batch_id}:last_activity")
    metadata_results = await metadata_pipe.execute()

    # Check timeouts (lines 658-673)
    window_elapsed = current_time - started_at
    idle_time = current_time - last_activity

    if window_elapsed >= self._batch_window:
        should_close = True
        close_reason = "batch window exceeded"
    elif idle_time >= self._idle_timeout:
        should_close = True
        close_reason = "idle timeout exceeded"
```

## Closing Batches

**Source:** Lines 705-896

```python
async def close_batch(self, batch_id: str) -> dict[str, Any]:
    """Force close a batch and push to analysis queue."""

    # Acquire locks (lines 729-740)
    async with self._batch_close_lock:
        camera_id = await self._redis.get(f"batch:{batch_id}:camera_id")

        camera_lock = await self._get_camera_lock(camera_id)
        async with camera_lock:
            # Set closing flag with TTL (lines 743-747)
            await self._redis._client.set(
                f"batch:{batch_id}:closing",
                "1",
                ex=BATCH_CLOSING_FLAG_TTL_SECONDS,  # 5 minutes
            )

            # Fetch batch data in parallel using TaskGroup (lines 788-800)
            async with asyncio.TaskGroup() as tg:
                tg.create_task(fetch_detections())
                tg.create_task(fetch_started_at())
                tg.create_task(fetch_pipeline_time())

            # Push to analysis queue (lines 815-858)
            if detections:
                queue_item = {
                    "batch_id": batch_id,
                    "camera_id": camera_id,
                    "detection_ids": detections,
                    "timestamp": time.time(),
                    "pipeline_start_time": pipeline_start_time,
                }
                result = await self._redis.add_to_queue_safe(
                    self._analysis_queue,
                    queue_item,
                    overflow_policy=QueueOverflowPolicy.DLQ,
                )

            # Cleanup Redis keys (lines 874-882)
            await self._redis.delete(
                f"batch:{camera_id}:current",
                f"batch:{batch_id}:camera_id",
                f"batch:{batch_id}:detections",
                f"batch:{batch_id}:started_at",
                f"batch:{batch_id}:last_activity",
                f"batch:{batch_id}:pipeline_start_time",
                f"batch:{batch_id}:closing",
            )
```

## Fast Path Processing

The fast path bypasses batching for critical detections (lines 1028-1082):

### Criteria (Lines 1028-1048)

```python
def _should_use_fast_path(self, confidence: float | None, object_type: str | None) -> bool:
    """Check if detection meets fast path criteria."""
    if confidence is None or object_type is None:
        return False

    if confidence < self._fast_path_threshold:  # 0.9 default
        return False

    return object_type.lower() in [t.lower() for t in self._fast_path_types]
```

### Processing (Lines 1050-1082)

```python
async def _process_fast_path(self, camera_id: str, detection_id: int) -> None:
    """Process detection via fast path (immediate analysis)."""
    if not self._analyzer:
        from backend.services.nemotron_analyzer import NemotronAnalyzer
        self._analyzer = NemotronAnalyzer(redis_client=self._redis)

    await self._analyzer.analyze_detection_fast_path(
        camera_id=camera_id,
        detection_id=detection_id,
    )
```

## Size Limit Handling

**Source:** Lines 898-1026

When a batch reaches the max detection limit, it's closed with reason "max_size":

```python
async def _close_batch_for_size_limit(self, batch_id: str) -> dict[str, Any] | None:
    """Close a batch that has reached the max detection size limit."""

    summary = {
        "batch_id": batch_id,
        "camera_id": camera_id,
        "detection_ids": detections,
        "started_at": started_at,
        "ended_at": ended_at,
        "reason": "max_size",  # NEM-1726
    }

    result = await self._redis.add_to_queue_safe(
        self._analysis_queue,
        summary,
        overflow_policy=QueueOverflowPolicy.DLQ,
    )
```

## Memory Pressure Backpressure

**Source:** Lines 1084-1119

When GPU memory is critical, the aggregator can apply backpressure:

```python
async def should_apply_backpressure(self) -> bool:
    """Check if backpressure should be applied due to GPU memory pressure."""
    from backend.services.gpu_monitor import MemoryPressureLevel

    pressure_level = await get_memory_pressure_level()
    should_throttle = pressure_level == MemoryPressureLevel.CRITICAL

    if should_throttle:
        logger.warning("Backpressure active due to critical GPU memory pressure")

    return should_throttle
```

## WebSocket Broadcasting

The aggregator broadcasts events for real-time UI updates (lines 163-264):

### Detection New Event (Lines 163-211)

```python
async def _broadcast_detection_new(
    self, detection_id: int, batch_id: str, camera_id: str, ...
) -> None:
    """Broadcast a detection.new event via WebSocket."""
    broadcaster = await get_broadcaster(self._redis)
    detection_data = {
        "detection_id": detection_id,
        "batch_id": batch_id,
        "camera_id": camera_id,
        "label": label or "unknown",
        "confidence": confidence,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    await broadcaster.broadcast_detection_new(detection_data)
```

### Detection Batch Event (Lines 213-264)

```python
async def _broadcast_detection_batch(
    self, batch_id: str, camera_id: str, detection_ids: list[int], ...
) -> None:
    """Broadcast a detection.batch event via WebSocket."""
    batch_data = {
        "batch_id": batch_id,
        "camera_id": camera_id,
        "detection_ids": detection_ids,
        "detection_count": len(detection_ids),
        "started_at": datetime.fromtimestamp(started_at, tz=UTC).isoformat(),
        "closed_at": datetime.fromtimestamp(closed_at, tz=UTC).isoformat(),
        "close_reason": close_reason,
    }
    await broadcaster.broadcast_detection_batch(batch_data)
```

## BatchTimeoutWorker

**Source:** `backend/services/pipeline_workers.py` (lines 941-1099)

The `BatchTimeoutWorker` periodically checks for timed-out batches:

```python
class BatchTimeoutWorker:  # Line 941
    """Worker that periodically checks and closes timed-out batches."""

    def __init__(
        self,
        redis_client: RedisClient,
        batch_aggregator: BatchAggregator | None = None,
        check_interval: float = 10.0,  # Check every 10 seconds
        stop_timeout: float = 10.0,
    ):
        self._aggregator = batch_aggregator or BatchAggregator(redis_client=redis_client)
        self._check_interval = check_interval
```

### Processing Loop (Lines 1033-1099)

```python
async def _run_loop(self) -> None:
    while self._running:
        start_time = time.time()

        # Check for batch timeouts FIRST
        closed_batches = await self._aggregator.check_batch_timeouts()

        if closed_batches:
            self._stats.items_processed += len(closed_batches)
            observe_stage_duration("batch", duration)
            record_pipeline_stage_latency("detect_to_batch", duration * 1000)

        # Maintain consistent check interval
        elapsed = time.time() - start_time
        sleep_time = max(0.0, self._check_interval - elapsed)
        await asyncio.sleep(sleep_time)
```

## Configuration

| Setting                          | Default      | Description                     |
| -------------------------------- | ------------ | ------------------------------- |
| `batch_window_seconds`           | `90`         | Max time for batch to stay open |
| `batch_idle_timeout_seconds`     | `30`         | Close batch after idle period   |
| `batch_max_detections`           | `50`         | Max detections per batch        |
| `fast_path_confidence_threshold` | `0.9`        | Min confidence for fast path    |
| `fast_path_object_types`         | `["person"]` | Object types for fast path      |
| `batch_check_interval_seconds`   | `5`          | Timeout check frequency         |

## Metrics

- `hsi_batch_max_reached_total` - Batches closed due to size limit
- `hsi_pipeline_stage_duration_seconds{stage="batch"}` - Batch processing time

## Related Documentation

- **[Detection Queue](detection-queue.md):** Source of detections
- **[Analysis Queue](analysis-queue.md):** Destination for closed batches
- **[Critical Paths](critical-paths.md):** Fast path optimization
