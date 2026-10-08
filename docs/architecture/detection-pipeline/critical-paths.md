# Critical Paths and Latency Optimization

This document describes the performance-critical paths through the detection pipeline, latency targets, and optimization strategies.

## Latency Targets

| Stage                   | Target | Rationale                     |
| ----------------------- | ------ | ----------------------------- |
| File detection to queue | <500ms | User-perceived responsiveness |
| Detection inference     | <100ms | GPU batch efficiency          |
| Event broadcast         | <50ms  | Real-time UI updates          |
| Total pipeline          | <5s    | End-to-end detection to event |

## Pipeline Stages with Latency Tracking

The pipeline records latency at each stage for observability:

```
watch_to_detect --> detect_to_batch --> batch_to_analyze --> total_pipeline
```

### Stage 1: watch_to_detect

**Source:** `backend/services/file_watcher.py` (lines 827-829)

```python
duration_ms = int((time.time() - start_time) * 1000)
record_pipeline_stage_latency("watch_to_detect", float(duration_ms))
```

**Components:**

- File system event detection (watchdog)
- Debounce delay (0.5s default)
- File stability check (2.0s for FTP)
- Image validation (PIL load, off the event loop)
- Deduplication check (Redis content hash, `DedupeService.is_duplicate_and_mark`)
- Queue enqueue (Redis Streams `XADD`, or a LIST push with streams off)

### Stage 2: detect_to_batch

**Source:** `backend/services/pipeline_workers.py` (lines 526-531)

```python
duration = time.time() - start_time
observe_stage_duration("detect", duration)
record_pipeline_stage_latency("detect_to_batch", duration * 1000)
```

**Components:**

- Queue read (Redis Streams consumer group, or BRPOP)
- Payload validation
- Semaphore acquisition
- YOLO26 HTTP request
- Detection filtering
- Database insert
- Batch aggregator update

### Stage 3: batch_to_analyze

**Source:** `backend/services/pipeline_workers.py` (lines 1062-1067)

```python
duration = time.time() - start_time
duration_ms = int(duration * 1000)
record_pipeline_stage_latency("batch_to_analyze", duration_ms)
await record_stage_latency(self._redis, "analyze", duration_ms)
```

**Components:**

- Queue read (Redis Streams consumer group, or BRPOP)
- Payload validation
- Detection fetch (PostgreSQL)
- Household/zone context read
- Specialist lookups (faces, person re-ID, plates — in-process)
- Key-frame selection
- VLM assess request to `ai-vlm` (`backend/services/vlm_client.py`)
- Verdict validation (the schema arrives parsed; no text scraping)
- Event creation
- Database insert
- WebSocket broadcast

### Stage 4: total_pipeline

**Source:** `backend/services/pipeline_workers.py` (lines 1071-1080)

```python
if pipeline_start_time:  # Line 1070
    start_dt = datetime.fromisoformat(pipeline_start_time.replace("Z", "+00:00"))
    total_duration_ms = (datetime.now(UTC) - start_dt).total_seconds() * 1000
    record_pipeline_stage_latency("total_pipeline", total_duration_ms)
```

**Tracked from:** First file detection to event creation completion.

## Fast Path Optimization

For a critical detection, the analysis fast path skips the batch window and
sends the single detection straight to the analyzer.

**Source:** `backend/services/batch_aggregator.py` (gate at lines 1185-1216,
processing at 1218-1251)

### Criteria (Lines 1185-1216)

```python
def _should_use_fast_path(self, confidence: float | None, object_type: str | None) -> bool:
    if confidence is None or object_type is None:
        return False
    if confidence < self._fast_path_threshold:  # 2.0 default
        return False
    return object_type.lower() in [t.lower() for t in self._fast_path_types]
```

**Shipped criteria:** `fast_path_confidence_threshold = 2.0` (a confidence can
never reach it) and `fast_path_object_types = []` — the gate ships closed, so no
detection takes this path under the shipped config. The code path is live and
tested; setting a confidence <= 1.0 and a non-empty type list opens it. Weapon
and smoke/fire detections have their own alert bypasses that do run
(`should_bypass_batch`, lines 1294-1352).

When the gate opens, `analyze_detection_fast_path`
(`backend/services/vlm_analyzer.py:690-705`) routes the single detection through
the same `analyze_batch` gate under the id `fast_path_<id>` — one `vlm_assess`
over a one-detection batch, the same verdict invariants, one analysis path
(built by the `build_pipeline_analyzer` seam,
`backend/services/pipeline_factory.py:28-40`).

### Latency Impact

| Path         | Typical Latency | Notes                              |
| ------------ | --------------- | ---------------------------------- |
| Normal batch | 30-90s          | Wait for batch window/idle timeout |
| Fast path    | <5s             | Immediate analysis                 |

### Trade-offs

**Benefits:**

- Immediate verification and event creation for a single high-confidence detection
- Reduced time-to-event for security detections

**Costs:**

- Higher VLM load (more individual requests)
- Less context for the VLM (single detection vs batch)

## Concurrency Control

### Inference Semaphore (NEM-1463)

**Source:** `backend/services/inference_semaphore.py`

Limits concurrent AI inference operations to prevent GPU overload:

```python
# backend/core/config.py: ai_max_concurrent_inferences
# Default: 4 on standard Python, 20 on free-threaded Python
```

**Impact on latency:**

- Under load, requests queue behind the semaphore
- Trade-off between throughput and latency
- Higher limits increase parallelism but risk GPU OOM

### Detector Client Semaphore (NEM-1500)

**Source:** `backend/services/detector_client.py` (lines 204-223)

```python
@classmethod
def _get_semaphore(cls) -> asyncio.Semaphore:
    settings = get_settings()
    limit = settings.ai_max_concurrent_inferences

    if cls._request_semaphore is None or cls._semaphore_limit != limit:
        cls._request_semaphore = asyncio.Semaphore(limit)
```

## Retry and Backoff

### Exponential Backoff (NEM-1343)

The detector retries transient failures with exponential backoff:

```python
# Backoff calculation
delay = min(2**attempt, 30)  # Cap at 30 seconds
```

The schedule is `delay = min(2**attempt, 30)` — slept at line 704 — so each
retry waits 2^attempt seconds:

| Retry | Delay before it                        |
| ----- | -------------------------------------- |
| 1     | 1s                                     |
| 2     | 2s                                     |
| 3     | 4s (8s, 30s-capped with more attempts) |

The default is three attempts total (`detector_max_retries`), so the worst case
is base latency + 1s + 2s = base + 3s. The circuit breaker below trips after
five consecutive failures, bounding how long the ladder can repeat.

The analysis leg does not use a backoff ladder. `VlmClient.assess` retries a
failure where re-asking is not futile — a fast transport fault (refused
connection, `ConnectTimeout`), any other answered status (a 5xx or a plain 4xx,
except the 400 context-overflow refusal), or a schema violation on a complete
reply —
exactly once at temperature 0, the second attempt carrying its own read budget,
and raises —
the analyzer then records `verification_failed` on the event rather than
spending a second budget on it. A read or write timeout is not
retried: the request leaves unchanged, so a re-send would time out identically,
and a slow reply counts as a budget (`VlmSlowReplyError`), never as a breaker
failure. Budget refusals — a slow reply, a truncated verdict, an overflowing
prompt — raise on the first attempt, by the same rule.

## Circuit Breaker (NEM-1724)

**Source:** `backend/services/detector_client.py` (lines 336-344)

Prevents retry storms when services are unavailable:

```python
self._circuit_breaker = CircuitBreaker(
    name=f"detector_{self._detector_type}",
    config=CircuitBreakerConfig(
        failure_threshold=5,      # Opens after 5 failures
        recovery_timeout=60.0,    # 60s before retry
        half_open_max_calls=3,
        success_threshold=2,
    ),
)
```

**Latency impact:**

- When circuit is open, requests fail immediately
- Prevents cascading delays during outages

## Timeout Configuration

### Detector Timeouts

**Source:** `backend/services/detector_client.py` (lines 110-112)

```python
DETECTOR_CONNECT_TIMEOUT = 10.0   # Connection establishment
DETECTOR_READ_TIMEOUT = 60.0      # AI inference response
DETECTOR_HEALTH_TIMEOUT = 5.0     # Health check
```

### VLM Timeouts

**Source:** `backend/core/config.py` (lines 1106-1151)

```python
ai_connect_timeout: float = 10.0          # Connection establishment
ai_vlm_read_timeout: float = 25.0         # Per-read idle budget, per attempt
ai_vlm_wake_timeout_seconds: float = 90.0 # The wake-on-open ping
```

The read budget is a per-read idle budget, not an attempt deadline (httpx
resets it on every reply chunk), so each attempt carries a fresh idle window —
and a silent 25 s timeout already sits at S4's p95 <= 30 s edge (cold starts
in, connect counted on top). The client therefore never re-asks a reply that
timed out (`vlm_client.py` `VlmSlowReplyError`); the §6 temp-0 re-send follows
only re-asks that can differ (fast trip faults, any other rejected status —
5xx or a plain 4xx, not the 400 overflow —, schema violations), which cost
almost nothing when the first failure was fast. An idle budget at or above
30 s would put one silent answer past the spec.

### Defense-in-Depth (NEM-1465)

**Source:** `backend/services/detector_client.py` (budget at lines 635-637, wrapper at 663-665)

```python
# Explicit timeout as defense-in-depth (NEM-1465)
explicit_timeout = self._read_timeout + settings.ai_connect_timeout
...
async with asyncio.timeout(explicit_timeout):  # Line 665
    response = await self._http_client.post(...)
```

The httpx read timeout bounds the socket; the `asyncio.timeout()` starts inside
the class request semaphore and bounds the whole request attempt. The shared
inference semaphore is taken further out (lines 1115-1116), so a request waiting
for GPU capacity is not charged against this timeout.

## Cold Start Optimization (NEM-1670)

### Model Warmup

**Source:** `backend/services/detector_client.py` (lines 543-594)

```python
async def warmup(self) -> bool:
    """Perform model warmup by running a test inference."""
    if not self._warmup_enabled:
        return True

    was_cold = self.is_cold()
    self._is_warming = True

    result = await self.model_readiness_probe()

    if result:
        self._track_inference()
        set_model_warmth_state("yolo26", "warm")
```

**Configuration:**

```python
ai_warmup_enabled = True          # Enable warmup on startup
ai_cold_start_threshold_seconds = 300  # 5 minutes idle = cold
```

### Cold Detection

```python
def is_cold(self) -> bool:
    if self._last_inference_time is None:
        return True
    seconds_since_last = time.monotonic() - self._last_inference_time
    return seconds_since_last > self._cold_start_threshold
```

## Redis Pipelining

### Batch Timeout Checking

**Source:** `backend/services/batch_aggregator.py` (pipelines at lines 714 and 744, within `check_batch_timeouts` at 680-834)

Uses Redis pipelining to reduce RTTs from O(N \* 3) to O(2):

```python
# Phase 1: Fetch all batch IDs in parallel (single RTT)
batch_id_pipe = redis_client.pipeline()
for batch_key in batch_keys:
    batch_id_pipe.get(batch_key)
batch_ids = await batch_id_pipe.execute()

# Phase 2: Fetch all metadata in parallel (single RTT)
metadata_pipe = redis_client.pipeline()
for _batch_key, batch_id in valid_batches:
    metadata_pipe.get(f"batch:{batch_id}:started_at")
    metadata_pipe.get(f"batch:{batch_id}:last_activity")
```

### Atomic Batch Creation (NEM-2014)

**Source:** `backend/services/batch_aggregator.py` (lines 386-444)

```python
async with client.pipeline(transaction=True) as pipe:
    pipe.set(batch_key, batch_id, ex=ttl)
    pipe.set(f"batch:{batch_id}:camera_id", camera_id, ex=ttl)
    pipe.set(f"batch:{batch_id}:started_at", str(current_time), ex=ttl)
    pipe.set(f"batch:{batch_id}:last_activity", str(current_time), ex=ttl)
    await pipe.execute()
```

## Async I/O Optimization

### Thread Pool for Blocking Operations

**Source:** `backend/services/file_watcher.py` (lines 184 and 290)

```python
# Run blocking PIL operations in thread pool
return await asyncio.to_thread(_validate_image_sync, file_path)
```

### Parallel Data Fetching

**Source:** `backend/services/batch_aggregator.py` (lines 919-923)

```python
async with asyncio.TaskGroup() as tg:
    tg.create_task(fetch_detections())
    tg.create_task(fetch_started_at())
    tg.create_task(fetch_pipeline_time())
```

## HTTP Connection Pooling (NEM-1721)

**Source:** `backend/services/detector_client.py` (lines 321-327)

```python
# Persistent HTTP connection pool
self._http_client = httpx.AsyncClient(
    timeout=self._timeout,
    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
)
```

**Benefits:**

- Avoids TCP handshake overhead
- Reuses existing connections
- Prevents connection exhaustion

## Free-Threading Support (Python 3.13t/3.14t)

**Source:** `backend/services/detector_client.py` (lines 120-147)

When running on free-threaded Python (GIL disabled):

```python
def _is_free_threaded() -> bool:
    if hasattr(sys, "_is_gil_enabled"):
        return not sys._is_gil_enabled()
    return False

def _get_default_inference_limit() -> int:
    if _is_free_threaded():
        return 20  # Higher limit with true parallelism
    return 4     # Conservative limit with GIL
```

## Monitoring and Alerts

### Key Metrics to Monitor

| Metric                                        | Alert Threshold | Description               |
| --------------------------------------------- | --------------- | ------------------------- |
| `hsi_stage_duration_seconds{stage="detect"}`  | p99 > 1s        | Detection taking too long |
| `hsi_stage_duration_seconds{stage="analyze"}` | p99 > 60s       | Analysis taking too long  |
| `hsi_detection_queue_depth`                   | > 100           | Detection backlog         |
| `hsi_analysis_queue_depth`                    | > 50            | Analysis backlog          |
| `hsi_pipeline_errors_total`                   | > 10/min        | Error rate spike          |

### Latency Percentiles

Track p50, p90, p99 for each stage:

```
hsi_stage_duration_seconds_bucket{stage="detect",le="0.1"}
hsi_stage_duration_seconds_bucket{stage="detect",le="0.5"}
hsi_stage_duration_seconds_bucket{stage="detect",le="1.0"}
hsi_stage_duration_seconds_bucket{stage="detect",le="5.0"}
```

## Related Documentation

- **[FileWatcher](file-watcher.md):** Entry point optimizations
- **[Detection Queue](detection-queue.md):** Queue processing patterns
- **[Batch Aggregator](batch-aggregator.md):** Batching strategy
- **[Analysis Queue](analysis-queue.md):** VLM verification and failure handling
- **[Resilience Patterns](../resilience.md):** Circuit breakers and retries
