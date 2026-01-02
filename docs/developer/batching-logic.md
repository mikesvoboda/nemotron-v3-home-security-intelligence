# Batching Logic

> How detections are grouped before LLM analysis.

**Time to read:** ~8 min
**Prerequisites:** [Detection Service](detection-service.md)

---

![How Batch Aggregation Works](../images/flow-batch-aggregator.png)

---

## Why We Batch

1. **Better LLM Context**: A "person approaching door" event might span 30 seconds across 15 images. Analyzing together gives full context.

2. **Reduced Noise**: Individual frame detections can be noisy. Batching smooths false positives.

3. **Efficiency**: One LLM call for 10 detections is more efficient than 10 separate calls.

4. **Meaningful Events**: Users want "Person at front door for 45 seconds" not "15 separate person detections."

---

## Source Files

- `/backend/services/batch_aggregator.py` - Batch management
- `/backend/services/pipeline_workers.py` - BatchTimeoutWorker

---

## Batch Lifecycle

```
No Active Batch
      |
      | First detection arrives
      v
  Batch Active (collecting)
      |
      +-- Detection added --> Update last_activity
      |
      +-- Window timeout (90s from start) --> Close
      |
      +-- Idle timeout (30s no activity) --> Close
      |
      +-- Force close (API call) --> Close
      v
  Batch Closed
      |
      | Push to analysis_queue
      | Cleanup Redis keys
      v
  Event Created
```

---

## Timing Parameters

| Parameter      | Default | Environment Variable         |
| -------------- | ------- | ---------------------------- |
| Window timeout | 90s     | `BATCH_WINDOW_SECONDS`       |
| Idle timeout   | 30s     | `BATCH_IDLE_TIMEOUT_SECONDS` |
| Check interval | 10s     | (hardcoded)                  |

---

## Redis Key Structure

All batch keys have a 1-hour TTL for orphan cleanup:

```
batch:{camera_id}:current       -> batch_id (string)
batch:{batch_id}:camera_id      -> camera_id (string)
batch:{batch_id}:detections     -> ["det_1", "det_2", ...] (JSON array)
batch:{batch_id}:started_at     -> 1703764800.123 (Unix timestamp)
batch:{batch_id}:last_activity  -> 1703764845.456 (Unix timestamp)
```

---

## Adding a Detection

When `add_detection()` is called:

1. Check if batch exists for camera
2. If no batch: Create new with UUID, set started_at and last_activity
3. If batch exists: Append detection_id, update last_activity
4. Check for fast-path eligibility

```python
async def add_detection(
    self,
    camera_id: str,
    detection_id: int,
    confidence: float,
    object_type: str
) -> str | None:
    """Add detection to batch. Returns batch_id or fast_path_id."""
    # Fast path check
    if self._is_fast_path_eligible(confidence, object_type):
        return await self._process_fast_path(detection_id)

    # Get or create batch
    batch_id = await self._get_or_create_batch(camera_id)

    # Add detection to batch
    await self._add_to_batch(batch_id, detection_id)

    return batch_id
```

---

## Fast Path

High-confidence detections of critical object types bypass batching:

### Eligibility Criteria

```python
def _is_fast_path_eligible(self, confidence: float, object_type: str) -> bool:
    return (
        confidence >= self.fast_path_confidence_threshold
        and object_type in self.fast_path_object_types
    )
```

**Default configuration:**

- Confidence threshold: 0.90
- Object types: `["person"]`

### Fast Path Flow

```
Detection arrives
      |
      v
confidence >= 0.90 AND object_type == "person"?
      |
      +-- Yes --> FAST PATH
      |             |
      |             v
      |       Immediate LLM analysis
      |             |
      |             v
      |       Create Event (is_fast_path=true)
      |             |
      |             v
      |       WebSocket broadcast
      |
      +-- No --> Normal batching
```

**Latency:** Fast path events complete in ~3-6 seconds vs. 30-90 seconds for normal path.

---

## Batch Timeout Check

The `BatchTimeoutWorker` runs every 10 seconds:

```python
async def check_batch_timeouts(self):
    """Check all active batches for timeout conditions."""
    now = time.time()

    for camera_id in await self._get_active_cameras():
        batch_id = await self._get_current_batch(camera_id)
        if not batch_id:
            continue

        started_at = await self._get_batch_started_at(batch_id)
        last_activity = await self._get_batch_last_activity(batch_id)

        # Window timeout: 90s from batch start
        if now - started_at >= self.batch_window_seconds:
            await self._close_batch(batch_id, "window_timeout")

        # Idle timeout: 30s since last detection
        elif now - last_activity >= self.batch_idle_timeout_seconds:
            await self._close_batch(batch_id, "idle_timeout")
```

---

## Closing a Batch

When a batch closes:

1. Get all detection IDs from Redis
2. Push job to `analysis_queue`
3. Clear Redis keys
4. Log batch closure reason

```python
async def _close_batch(self, batch_id: str, reason: str):
    """Close batch and queue for analysis."""
    camera_id = await self._get_batch_camera_id(batch_id)
    detection_ids = await self._get_batch_detection_ids(batch_id)

    job = {
        "batch_id": batch_id,
        "camera_id": camera_id,
        "detection_ids": detection_ids,
        "timestamp": time.time(),
        "close_reason": reason
    }

    await self.redis.lpush("analysis_queue", json.dumps(job))
    await self._cleanup_batch_keys(batch_id, camera_id)
```

---

## Analysis Queue Format

```json
{
  "batch_id": "a3f9c8b2d1e4f5g6h7i8j9k0",
  "camera_id": "front_door",
  "detection_ids": ["1", "2", "3", "4", "5"],
  "timestamp": 1703764890.123,
  "close_reason": "idle_timeout"
}
```

---

## Configuration

| Variable                         | Default    | Description            |
| -------------------------------- | ---------- | ---------------------- |
| `BATCH_WINDOW_SECONDS`           | 90         | Maximum batch duration |
| `BATCH_IDLE_TIMEOUT_SECONDS`     | 30         | Close if no activity   |
| `FAST_PATH_CONFIDENCE_THRESHOLD` | 0.90       | Fast path threshold    |
| `FAST_PATH_OBJECT_TYPES`         | ["person"] | Fast path object types |

---

## Next Steps

- [Risk Analysis](risk-analysis.md) - LLM processing and scoring
- [Pipeline Overview](pipeline-overview.md) - Full pipeline flow

---

## See Also

- [AI Performance](../operator/ai-performance.md) - Tuning batch timing parameters
- [Environment Variable Reference](../reference/config/env-reference.md) - Batch configuration variables
- [Data Model](data-model.md) - How batches become events
- [Detection Service](detection-service.md) - What creates detections

---

[Back to Developer Hub](../developer-hub.md)
