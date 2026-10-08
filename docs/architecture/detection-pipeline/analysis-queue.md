# Analysis Queue Architecture

The analysis queue receives closed batches from the BatchAggregator and routes them through VLM risk verification to create security events.

## Overview

**Source Files:**

- `backend/services/pipeline_workers.py` (AnalysisQueueWorker)
- `backend/api/schemas/queue.py` (Payload validation)
- `backend/services/vlm_analyzer.py` (VlmAnalyzer)
- `backend/services/vlm_client.py` (the `vlm_assess` transport)

## Queue Structure

`USE_REDIS_STREAMS` defaults to true (`backend/core/config.py:2239-2242`), so the durable path is a Redis Stream — `analysis:stream`, read by the `analysis-workers` consumer group (`backend/services/redis_streams.py:873-875`). With the setting turned off, the same payloads ride the Redis LIST below over BRPOP.

**Queue Name:** `ANALYSIS_QUEUE = "analysis_queue"` (`backend/core/constants.py:149`)

**With prefix:** `hsi:queue:analysis_queue` (`backend/core/constants.py:242-262`, `get_prefixed_queue_name`)

**Stream key:** `analysis:stream`, DLQ key `analysis:stream:dlq` (`backend/services/redis_streams.py:873-874`)

## Queue Payload Schema

**Source:** `backend/api/schemas/queue.py` (lines 132-228)

```python
class AnalysisQueuePayload(BaseModel):
    batch_id: str = Field(..., min_length=1, max_length=128)
    camera_id: str | None = Field(
        default=None,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_-]+$",
    )
    detection_ids: list[int | str] | None = None
    pipeline_start_time: str | None = None  # For latency tracking
```

### Security Validations

**Batch ID Validation (lines 173-186):**

```python
@field_validator("batch_id")
def validate_batch_id(cls, v: str) -> str:
    # Check for null bytes
    if "\x00" in v:
        raise ValueError("batch_id cannot contain null bytes")

    # Check for newlines (logging injection)
    if "\n" in v or "\r" in v:
        raise ValueError("batch_id cannot contain newlines")
    return v
```

**Detection IDs Validation (lines 187-211):**

```python
@field_validator("detection_ids")
def validate_detection_ids(cls, v: list[int | str] | None):
    for detection_id in v:
        id_val = int(detection_id)
        if id_val < 1:
            raise ValueError("detection_ids must be positive integers")

    # DoS protection
    if len(v) > 10000:
        raise ValueError("detection_ids list too large (max 10000)")
    return v
```

## AnalysisQueueWorker

**Source:** `backend/services/pipeline_workers.py` (lines 765-1186)

### Class Definition

```python
class AnalysisQueueWorker:  # Line 765
    """Worker that consumes batches from analysis_queue and runs LLM analysis."""
```

### Constructor Parameters (Lines 778-807)

| Parameter      | Type          | Default          | Description                            |
| -------------- | ------------- | ---------------- | -------------------------------------- |
| `redis_client` | `RedisClient` | Required         | Redis client for queue operations      |
| `analyzer`     | `VlmAnalyzer` | Auto-created     | Analyzer built by the pipeline factory |
| `queue_name`   | `str`         | `ANALYSIS_QUEUE` | Queue to consume from                  |
| `poll_timeout` | `int`         | 5                | BLPOP timeout in seconds               |
| `stop_timeout` | `float`       | 30.0             | Graceful stop timeout (long for a VLM) |

The analyzer arrives through one construction seam, so no call site can pin the worker to a stale analyzer:

```python
self._analyzer = analyzer or build_pipeline_analyzer(redis_client=redis_client)  # Line 802
```

`build_pipeline_analyzer` (`backend/services/pipeline_factory.py:28-40`) is the single place an analyzer is constructed — the worker's default, the API dependency (`backend/api/dependencies.py:958-960`), the DI container (`backend/core/container.py:506-509`), and the aggregator's fast-path builder all ask it, and it returns `VlmAnalyzer`.

The FastAPI lifespan registers the worker with the `WorkerSupervisor` through `create_analysis_worker` (`backend/services/pipeline_workers.py:2140-2168`, registered as `"analysis"` at `backend/main.py:996-1001`).

### Processing Loop (Lines 888-976)

```python
async def _run_loop(self) -> None:
    """Main processing loop for the analysis queue worker."""
    use_streams = settings.use_redis_streams

    if use_streams:
        stream_service = await get_analysis_stream_service(self._redis)

    while self._running:
        if use_streams and stream_service is not None:
            # Claim stale messages from crashed consumers every 30s
            claimed = await stream_service.claim_stale_messages(consumer_name, count=5)
            for msg in claimed:
                if msg.delivery_count >= stream_service._max_delivery_count:
                    await stream_service.move_to_dlq(msg, "max_delivery_exceeded")
                else:
                    await self._process_analysis_item(msg.to_queue_dict())
                    await stream_service.acknowledge(msg.id)

            # Read from the stream with the consumer group (durable)
            messages = await stream_service.consume_batches(consumer_name, count=1, block=True)
            if not messages:
                continue
            for msg in messages:
                await self._process_analysis_item(msg.to_queue_dict())
                await stream_service.acknowledge(msg.id)
        else:
            item = await self._redis.get_from_queue(
                self._queue_name,
                timeout=self._poll_timeout,
            )
            if item is None:
                continue
            await self._process_analysis_item(item)
```

In streams mode a message is acknowledged only after `_process_analysis_item` returns, so a crash mid-batch leaves the entry pending for the stale-claim path above rather than losing it.

### Item Processing (Lines 978-1186)

```python
async def _process_analysis_item(self, item: dict[str, Any]) -> None:
    """Process a single analysis queue item."""

    # Security: Validate payload (lines 992-1009)
    try:
        validated: AnalysisQueuePayload = validate_analysis_payload(item)
        batch_id = validated.batch_id
        camera_id = validated.camera_id
        detection_ids = validated.detection_ids
        pipeline_start_time = validated.pipeline_start_time
    except ValueError as e:
        self._stats.errors += 1
        record_pipeline_error("invalid_analysis_payload")
        logger.error(f"SECURITY: Rejecting invalid payload: {e}")
        return

    # Run the verification (lines 1052-1056)
    event = await self._analyzer.analyze_batch(
        batch_id=batch_id,
        camera_id=camera_id,
        detection_ids=detection_ids,
    )

    # Record metrics (lines 1062-1067)
    duration = time.time() - start_time
    duration_ms = int(duration * 1000)
    record_pipeline_stage_latency("batch_to_analyze", duration_ms)
    await record_stage_latency(self._redis, "analyze", duration_ms)

    # Record total pipeline latency (lines 1069-1080)
    if pipeline_start_time:
        start_dt = datetime.fromisoformat(pipeline_start_time.replace("Z", "+00:00"))
        total_duration_ms = (datetime.now(UTC) - start_dt).total_seconds() * 1000
        record_pipeline_stage_latency("total_pipeline", total_duration_ms)
```

The worker broadcasts `batch.analysis_started`, `batch.analysis_completed`, and `batch.analysis_failed` around the call (lines 1029-1049, 1101-1129) — all best-effort, so a dead WebSocket never un-does a committed event.

## VlmAnalyzer

**Source:** `backend/services/vlm_analyzer.py`

### Class Definition (Line 344)

```python
class VlmAnalyzer:  # Line 344
    """One analyze_batch call == one batch -> (at most) one assess ->
    one Event (+ EventVerification) -> one broadcast (prod mode)."""
```

### Constructor Parameters (Lines 351-371)

| Parameter      | Type              | Default                  | Description                                      |
| -------------- | ----------------- | ------------------------ | ------------------------------------------------ |
| `vlm_client`   | `VlmClient`       | None                     | Built lazily on first use                        |
| `redis_client` | `Any`             | None                     | Redis for batch metadata and idempotency         |
| `severity`     | `SeverityService` | `get_severity_service()` | Derives `risk_level` from the score              |
| `replay`       | `bool`            | False                    | Eval-store mode: same pipeline, never broadcasts |

### Analysis Flow (`analyze_batch`, lines 380-656)

1. Idempotency check on the `batch_event:<id>` Redis key (line 401)
2. Resolve camera and detection ids from the queue payload, falling back to the batch keys `close_batch` wrote; refuse loudly when no detector ever closed the batch — the VLM never originates an event (lines 413-432)
3. **Session 1 (read):** detections, the zones each detection sits in, and household context (lines 439-487)
4. **Specialist lookups** over the selected key frames — the texts `faces`, `plates`, and `person_reid` (lines 489-527). These are database lookups (gallery match, plate registry, re-ID vector comparison), and the stage never raises: every failure becomes the text `unavailable` (`backend/services/vlm_specialists.py`)
5. Build the `VlmAssessContext` / `VlmAssessRequest` — one builder serving both production rows and replay rows (lines 537-549)
6. **No session across the call:** render the prompt and `await client.assess()` (lines 552-557)
7. Map a failed call to `verification_failed` (lines 558-566)
8. `apply_verdict_invariants` — the rule table (lines 255-306)
9. **Session 2 (write):** `Event`, `EventVerification`, and the event/detection junction in one transaction (lines 573-633)
10. Idempotency key set AFTER the write (line 638)
11. Broadcast LAST, best-effort (line 643)

### Verdict Invariants (`apply_verdict_invariants`)

**Source:** Lines 255-306

The table is data, pinned row by row by `test_vlm_analyzer.TestVerdictInvariants`:

| Verdict               | Score                                                                         | Level                          |
| --------------------- | ----------------------------------------------------------------------------- | ------------------------------ |
| `confirmed`           | as returned                                                                   | derived by SeverityService     |
| `uncertain`           | as returned — uncertain is not rejected                                       | derived                        |
| `rejected`            | clamped to `severity.low_max`, with the clamp visible in the stored reasoning | derived from the clamped score |
| `verification_failed` | NULL                                                                          | NULL                           |

A `verification_failed` row is written, not skipped: the event exists precisely so the UI shows "needs review". Its summary is honest text — "VLM verification failed; this event needs review." — and its score is NULL by design rather than a fabricated low value.

The level is never emitted by the model: `VlmVerdict` carries no `risk_level` field (`backend/services/vlm_verdict.py:55-101`), and `SeverityService` derives it (`backend/services/severity.py:137`).

### Failure Ladder

Transport and schema failures are retried once and then mapped — no event is dropped:

- `VlmClient.assess` makes the first attempt, then retries the same body at temperature 0 inside the same read budget (`backend/services/vlm_client.py:805-807`)
- Every raise the client documents sits in `_DEGRADABLE_ERRORS` (`backend/services/vlm_analyzer.py:89-92`): `VlmClientError` — transport, schema, truncation, context overflow, breaker-open — and `ConstrainedDecodingNotEnforced`
- The analyzer catches those, records `vlm_verification_failed`, and writes the NULL-score event. It never re-retries: a second retry would double the p95 budget a single call already fits
- Anything outside that tuple is a bug and propagates loud

### Timeout and Concurrency Configuration

**Source:** `backend/core/config.py` (lines 1093-1132) and `backend/services/vlm_client.py:265-275`

```python
ai_connect_timeout: float = 10.0           # Connection establishment
ai_vlm_read_timeout: float = 25.0          # One vlm_assess attempt's budget
ai_vlm_wake_timeout_seconds: float = 90.0  # The wake-on-open ping
```

The read budget is sized so the one retry fits inside it (p95 <= 30s including cold starts). Concurrency is bounded by the `ai-vlm` circuit breaker (`backend/services/vlm_client.py:247-250`, `failure_threshold=5`, `recovery_timeout=60.0`): while it is open, `assess` raises `VlmUnavailableError` without doing I/O (`backend/services/vlm_client.py:766-772`). The shared inference semaphore (`backend/services/inference_semaphore.py`) is held by the detector leg (`backend/services/detector_client.py:1115-1116`), not by the VLM call.

## Context Read Before the Prompt

`build_assess_context` (lines 104-166) is the field-for-field builder of the frozen `AssessInput`. It never touches an ORM object, so production rows and replay rows arrive at the same shape:

```python
VlmAssessContext(
    camera_id=camera_id,
    detections=det_rows,      # id/object_type/confidence/bbox/detected_at
    zones=zones,              # enabled zones the detections sit in
    zone_crossing=zone_crossing,
    household=household,      # zone household configs
    timestamp=timestamp,      # earliest capture time, ISO UTC
    specialist_outputs=specialist_outputs,  # faces / plates / person_reid
)
```

Zones come from the shipped geometry, `zone_service.get_zones_for_detection` (center-point membership). Household context is read by `load_household_context` (lines 309-343) and is honest-absent on any failure — a context add-on never kills the assessment.

The timestamp is a capture time: with `CAMERA_TIMEZONE` set, a row's capture time is its Foscam filename time (`backend/services/capture_time.py`); otherwise it is `detected_at`. Event rows keep `detected_at`, because alerting compares event times with "now".

## The Specialist Legs

**Source:** `backend/services/vlm_specialists.py`

Three short texts enter the prompt, computed over the batch's selected key frames (`key_frame_selector.select_key_frames`, `MAX_KEY_FRAMES = 4`) before the assess call:

| Key           | Content                                                          |
| ------------- | ---------------------------------------------------------------- |
| `faces`       | gallery match, `unknown`, `not_identifiable`, or `unavailable`   |
| `plates`      | plate text and registry state, or `unavailable`                  |
| `person_reid` | household member re-identification, or `unavailable (re-enroll)` |

Two properties matter to the pipeline: the legs run in-process, inside session 1, so they add no service hop and cannot extend the read budget; and the stage never raises into the analyzer, so a missing model or a database hiccup degrades to a text while the batch is still verified.

Replay never re-runs them — the texts a stored verdict was judged on ride the eval-store snapshot — and the VLM never originates them: they arrive as detector evidence.

## Prompt Rendering

**Source:** `backend/services/vlm_client.py` (`_render_prompt`, lines 518-554)

The client renders the prompt from the AssessContext rather than from a template file: the camera, the capture time, the zones and the crossing flag, the detection rows (each naming the attached frame it sits on), the household context, and the specialist texts, followed by the instruction to answer only with the verdict JSON object.

Two budget rules apply at the wire (`_fitted_prompt`, lines 676-742). The slot is `settings.vlm_context_window` minus the image reservation minus the verdict's output budget; and when rows have to go, truncation is visible and deterministic — the strongest detections survive and the prompt says how many rows were omitted (`hsi_prompts_truncated_total` is bumped once, at the wire).

The request ships `response_format: {"type": "json_schema", ...}` carrying the generated contract schema (`backend/ai_contract/schemas/vlm_assess.response.json`), so the shape is enforced by the engine's grammar and validated again on receipt.

## Event Creation

Both rows are written in session 2 (`backend/services/vlm_analyzer.py:573-633`):

```python
event = Event(
    batch_id=batch_id,
    camera_id=camera_id,
    started_at=start_time,
    ended_at=end_time,
    risk_score=outcome["risk_score"],      # None on verification_failed
    risk_level=outcome["risk_level"],      # derived, never model-emitted
    summary=outcome["summary"],
    reasoning=outcome["reasoning"],
    llm_prompt=f"{prompt_text}\nKEY FRAMES: {request.image_paths}",
    reviewed=False,
)

row = EventVerification(
    event_id=event.id,
    verdict=outcome["verdict"],
    scene_description=outcome["description"] or None,
    criteria=outcome["criteria"],
    key_frame_detection_ids=frame_ids,
    engine=engine,        # the served engine's own label
    model_id=model_id,
    latency_ms=latency_ms,
)
```

Paths, never bytes: `llm_prompt` stores the prompt text and the key-frame paths the model was actually shown. The WebSocket `verification` payload is rendered inside session 2 (the row is async-expunged at session exit) and published after it.

## Metrics

From the worker (`pipeline_workers.py`):

```python
record_pipeline_stage_latency("batch_to_analyze", duration_ms)
await record_stage_latency(self._redis, "analyze", duration_ms)
record_pipeline_stage_latency("total_pipeline", total_duration_ms)
```

From the analyzer and the client:

```python
record_pipeline_error("vlm_verification_failed")   # vlm_analyzer.py:561
record_pipeline_error("vlm_transport_error")        # vlm_client.py:813
record_pipeline_error("vlm_circuit_open")           # vlm_client.py:768
record_prompt_truncated()                           # vlm_client.py:780
record_model_cold_start(BREAKER_NAME)               # vlm_client.py:973
set_ai_service_degraded("ai-vlm", degraded=True)    # vlm_client.py:931
```

## Error Handling

### Batch Not Found (lines 1131-1152)

A `ValueError` — no detections, or a batch no detector closed — is logged as a skip and broadcasts `batch.analysis_failed` with `retryable: False`. It is not counted as a worker error.

```python
except ValueError as e:
    record_exception(e)
    logger.warning(f"Skipping batch: {e}")
```

### Analysis Failure (lines 1153-1186)

```python
except Exception as e:
    self._stats.errors += 1
    record_pipeline_error("analysis_batch_error")
    record_exception(e)
    logger.error(f"Failed to analyze batch: {e}")
```

Engine failures never reach this handler: the analyzer has already converted them into a `verification_failed` event. What arrives here is an infrastructure fault, and in streams mode the un-acknowledged entry stays pending for the stale-claim path.

## DLQ Handling

In streams mode the worker moves a message that has exhausted its delivery attempts to `analysis:stream:dlq` and acknowledges the original (`backend/services/pipeline_workers.py:924-931`, `backend/services/redis_streams.py:1131-1169`).

**LIST DLQ name:** `dlq:analysis_queue` (`backend/core/constants.py:173`)

## OpenTelemetry Tracing

Analysis processing is traced (lines 1013-1027):

```python
with (
    log_context(batch_id=batch_id, camera_id=camera_id, operation="analysis"),
    tracer.start_as_current_span("analysis_processing"),
):
    span_attrs = {
        "batch_id": batch_id,
        "detection_count": len(detection_ids),
        "pipeline_stage": "analysis",
    }
    add_span_attributes(**span_attrs)
```

## Configuration

| Setting                          | Default                 | Description                                   |
| -------------------------------- | ----------------------- | --------------------------------------------- |
| `ai_vlm_url`                     | `http://localhost:8098` | VLM service URL (`ai-vlm:8098` under compose) |
| `ai_vlm_read_timeout`            | `25.0`                  | Budget for one `vlm_assess` attempt           |
| `ai_connect_timeout`             | `10.0`                  | Connection establishment                      |
| `ai_vlm_wake_timeout_seconds`    | `90.0`                  | Wake-on-open ping timeout                     |
| `vlm_model_id`                   | from settings           | Provenance label when `/props` is unread      |
| `vlm_context_window`             | from settings           | The slot one assess occupies                  |
| `vlm_enforcement_probe_enabled`  | from settings           | Gate on the constrained-decoding probe        |
| `use_redis_streams`              | `true`                  | Streams with consumer groups, or LIST + BRPOP |
| `worker_supervisor_max_restarts` | from settings           | Supervisor restart budget for this worker     |

Under compose, `AI_VLM_URL` is `http://ai-vlm:8098` (`docker-compose.prod.yml:559`) and `ai-vlm` is in the default compose set — a plain `up -d` starts it (`docker-compose.prod.yml:141-270`).

## Related Documentation

- **[Batch Aggregator](batch-aggregator.md):** Source of batches
- **[Critical Paths](critical-paths.md):** Latency optimization
- **[Real-time Architecture](../real-time.md):** Event broadcasting
