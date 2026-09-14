# Analysis Queue Architecture

The analysis queue receives closed batches from the BatchAggregator and routes them through LLM risk analysis to create security events.

## Overview

**Source Files:**

- `backend/services/pipeline_workers.py` (AnalysisQueueWorker)
- `backend/api/schemas/queue.py` (Payload validation)
- `backend/services/nemotron_analyzer.py` (NemotronAnalyzer)

## Queue Structure

The analysis queue uses a Redis LIST data structure with LPUSH/BRPOP pattern.

**Queue Name:** `ANALYSIS_QUEUE = "analysis_queue"` (constants.py:149)

**With prefix:** `hsi:queue:analysis_queue` (constants.py:260-261)

## Queue Payload Schema

**Source:** `backend/api/schemas/queue.py` (lines 107-187)

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

**Batch ID Validation (lines 148-160):**

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

**Detection IDs Validation (lines 162-187):**

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

**Source:** `backend/services/pipeline_workers.py` (lines 691-939)

### Class Definition

```python
class AnalysisQueueWorker:  # Line 691
    """Worker that consumes batches from analysis_queue and runs LLM analysis."""
```

### Constructor Parameters (Lines 703-728)

| Parameter      | Type               | Default          | Description                            |
| -------------- | ------------------ | ---------------- | -------------------------------------- |
| `redis_client` | `RedisClient`      | Required         | Redis client for queue operations      |
| `analyzer`     | `NemotronAnalyzer` | Auto-created     | Nemotron analyzer instance             |
| `queue_name`   | `str`              | `ANALYSIS_QUEUE` | Queue to consume from                  |
| `poll_timeout` | `int`              | 5                | BLPOP timeout in seconds               |
| `stop_timeout` | `float`            | 30.0             | Graceful stop timeout (longer for LLM) |

### Processing Loop (Lines 784-822)

```python
async def _run_loop(self) -> None:
    """Main processing loop for the analysis queue worker."""
    while self._running:
        # Pop item from queue with timeout
        item = await self._redis.get_from_queue(
            self._queue_name,
            timeout=self._poll_timeout,
        )

        if item is None:
            continue

        await self._process_analysis_item(item)
```

### Item Processing (Lines 824-938)

```python
async def _process_analysis_item(self, item: dict[str, Any]) -> None:
    """Process a single analysis queue item."""

    # Security: Validate payload (lines 838-854)
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

    # Run LLM analysis (lines 877-881)
    event = await self._analyzer.analyze_batch(
        batch_id=batch_id,
        camera_id=camera_id,
        detection_ids=detection_ids,
    )

    # Record metrics (lines 887-916)
    duration = time.time() - start_time
    record_pipeline_stage_latency("batch_to_analyze", duration * 1000)
    await record_stage_latency(self._redis, "analyze", duration * 1000)

    # Record total pipeline latency
    if pipeline_start_time:
        start_dt = datetime.fromisoformat(pipeline_start_time.replace("Z", "+00:00"))
        total_duration_ms = (datetime.now(UTC) - start_dt).total_seconds() * 1000
        record_pipeline_stage_latency("total_pipeline", total_duration_ms)
```

## NemotronAnalyzer

**Source:** `backend/services/nemotron_analyzer.py`

### Class Definition (Lines 135-236)

```python
class NemotronAnalyzer:  # Line 135
    """Analyzes detection batches using Nemotron LLM for risk assessment."""
```

### Analysis Flow (Lines 1-28)

The documented analysis flow:

1. Fetch batch detections from Redis/database
2. Enrich context with zones, baselines, and cross-camera activity
3. Run enrichment pipeline for license plates, faces, OCR (optional)
4. Format prompt with enriched detection details
5. Acquire shared AI inference semaphore (NEM-1463)
6. POST to llama.cpp completion endpoint (with retry)
7. Release semaphore
8. Parse JSON response
9. Create Event with risk assessment
10. Store Event in database
11. Broadcast via WebSocket

### Constructor Parameters (Lines 156-236)

| Parameter                 | Type                    | Default           | Description                   |
| ------------------------- | ----------------------- | ----------------- | ----------------------------- |
| `redis_client`            | `RedisClient`           | None              | Redis for caching             |
| `context_enricher`        | `ContextEnricher`       | Global singleton  | Zone/baseline enrichment      |
| `enrichment_pipeline`     | `EnrichmentPipeline`    | Global singleton  | License plate/face extraction |
| `use_enriched_context`    | `bool`                  | True              | Enable context enrichment     |
| `use_enrichment_pipeline` | `bool`                  | True              | Enable enrichment pipeline    |
| `max_retries`             | `int`                   | From settings (3) | Max LLM retry attempts        |
| `service_facade`          | `AnalyzerServiceFacade` | Global singleton  | Service access facade         |

### Timeout Configuration (Lines 127-132)

```python
NEMOTRON_CONNECT_TIMEOUT = 10.0   # Connection establishment
NEMOTRON_READ_TIMEOUT = 120.0     # LLM response (complex inference)
NEMOTRON_HEALTH_TIMEOUT = 5.0     # Health check
```

### Concurrency Control (Lines 19-22)

```
Concurrency Control (NEM-1463):
    Uses a shared asyncio.Semaphore to limit concurrent AI inference operations.
    This prevents GPU/AI service overload under high traffic. The limit is
    configurable via AI_MAX_CONCURRENT_INFERENCES setting (default: 4).
```

### Retry Logic (Lines 24-27)

```
Retry Logic (NEM-1343):
    - Configurable max retries via NEMOTRON_MAX_RETRIES setting (default: 3)
    - Exponential backoff: 2^attempt seconds between retries (capped at 30s)
    - Only retries transient failures (connection, timeout, HTTP 5xx)
```

## Context Enrichment

The analyzer enriches detection context before prompting (from docstring lines 2-9):

### Zone Enrichment

Maps detections to defined security zones for context:

```python
# Example enriched context
{
    "zone": "front_yard",
    "zone_type": "perimeter",
    "sensitivity": "high"
}
```

### Baseline Deviation

Compares current activity to historical baselines:

```python
# Example deviation data
{
    "person_count": 3,
    "baseline_avg": 1.2,
    "deviation_sigma": 1.5
}
```

### Cross-Camera Activity

Correlates activity across cameras:

```python
# Example cross-camera data
{
    "cameras_with_activity": ["front_door", "driveway"],
    "tracking_id": "person_123"
}
```

## Enrichment Pipeline

Optional enrichment extracts additional data (from docstring lines 3-4):

### License Plate OCR

Extracts license plate text from vehicle detections.

### Face Detection

Identifies faces in person detections.

### Text OCR

Extracts visible text from the scene.

## Prompt Templates

**Source:** `backend/services/prompts.py`

Multiple prompt templates are available (lines 96-114):

```python
from backend.services.prompts import (
    ENRICHED_RISK_ANALYSIS_PROMPT,
    FULL_ENRICHED_RISK_ANALYSIS_PROMPT,
    MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
    RISK_ANALYSIS_PROMPT,
    VISION_ENHANCED_RISK_ANALYSIS_PROMPT,
)
```

### Prompt Formatting Functions

```python
format_detections_with_all_enrichment()
format_action_recognition_context()
format_camera_health_context()
format_clothing_analysis_context()
format_depth_context()
format_household_context()
format_image_quality_context()
format_pet_classification_context()
format_pose_analysis_context()
format_vehicle_classification_context()
format_vehicle_damage_context()
format_violence_context()
format_weather_context()
```

## A/B Testing Support

**Source:** Lines 238-331

The analyzer supports prompt A/B testing:

```python
def set_ab_test_config(self, config: ABTestConfig) -> None:  # Line 242
    """Configure A/B testing for prompt versions."""
    self._ab_config = config
    self._ab_tester = PromptABTester(config)

async def get_prompt_version(self) -> tuple[int, bool]:  # Line 260
    """Get the prompt version to use for this request."""
    if self._ab_tester is not None:
        return self._ab_tester.select_prompt_version()
    return (1, False)  # Default version
```

### Shadow Analysis (Lines 348-399)

Run both prompt versions but return V1 results:

```python
async def run_shadow_analysis(self, camera_id: str, context: str):
    """Run shadow mode with both V1 and V2 prompts."""
    # Run V1 (control)
    v1_result = await self._call_llm_with_version(context, prompt_version=V1)

    # In shadow mode, also run V2 (treatment)
    if config.shadow_mode:
        v2_result = await self._call_llm_with_version(context, prompt_version=V2)
        score_diff = abs(v1_result["risk_score"] - v2_result["risk_score"])

    return {
        "primary_result": v1_result,
        "shadow_result": v2_result,
        "score_diff": score_diff,
    }
```

## Event Creation

After analysis, an Event is created and broadcast:

```python
# Create Event with risk assessment
event = Event(
    camera_id=camera_id,
    risk_score=parsed_response["risk_score"],
    summary=parsed_response["summary"],
    analysis=parsed_response["analysis"],
    detections=detections,
    created_at=datetime.now(UTC),
)

# Store in database
session.add(event)
await session.commit()

# Broadcast via WebSocket
await broadcaster.broadcast_event(event)
```

## Metrics

### Analysis Duration

```python
observe_ai_request_duration("nemotron", ai_duration)
observe_stage_duration("analyze", duration)
```

### Risk Score Distribution

```python
observe_risk_score(event.risk_score)
```

### Event Counters

```python
record_event_created()
record_event_by_camera(camera_id)
record_event_by_risk_level(risk_level)
```

### Token Usage

```python
record_nemotron_tokens(prompt_tokens, completion_tokens)
```

### Prompt Version Tracking

```python
record_prompt_template_used(template_name)
record_prompt_latency(f"v{prompt_version}", latency_seconds)
```

## Error Handling

### Batch Not Found (Line 927-930)

```python
except ValueError as e:
    # Batch not found or no detections
    record_exception(e)
    logger.warning(f"Skipping batch: {e}")
```

### Analysis Failure (Lines 931-938)

```python
except Exception as e:
    self._stats.errors += 1
    record_pipeline_error("analysis_batch_error")
    record_exception(e)
    logger.error(f"Failed to analyze batch: {e}")
```

## DLQ Handling

Failed analysis jobs are sent to the dead-letter queue:

**DLQ Name:** `dlq:analysis_queue` (constants.py:174)

## OpenTelemetry Tracing

Analysis processing is traced (lines 859-871):

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

| Setting                           | Default                                     | Description                |
| --------------------------------- | ------------------------------------------- | -------------------------- |
| `nemotron_url`                    | `http://localhost:8091/v1/chat/completions` | LLM server URL             |
| `nemotron_max_retries`            | `3`                                         | Max retry attempts         |
| `nemotron_read_timeout`           | `120.0`                                     | Response timeout (seconds) |
| `ai_max_concurrent_inferences`    | `4`                                         | Concurrent inference limit |
| `ai_warmup_enabled`               | `true`                                      | Enable model warmup        |
| `ai_cold_start_threshold_seconds` | `300`                                       | Cold model threshold       |

## Related Documentation

- **[Batch Aggregator](batch-aggregator.md):** Source of batches
- **[Critical Paths](critical-paths.md):** Latency optimization
- **[Real-time Architecture](../real-time.md):** Event broadcasting
