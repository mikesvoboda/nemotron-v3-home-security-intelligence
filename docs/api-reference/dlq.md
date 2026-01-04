---
title: Dead Letter Queue API Reference
description: API for managing failed AI pipeline jobs in the dead letter queue
source_refs:
  - backend/api/routes/dlq.py
  - backend/api/schemas/dlq.py
  - backend/services/retry_handler.py
  - backend/core/constants.py
---

# Dead Letter Queue (DLQ) API Reference

The Dead Letter Queue (DLQ) API provides endpoints for inspecting and managing jobs that have failed processing in the AI pipeline. When detection or analysis jobs exhaust their retry attempts, they are moved to a DLQ for later investigation and potential reprocessing.

## Overview

### What is the DLQ?

The DLQ is a holding area for failed AI pipeline jobs. Jobs end up in the DLQ when:

1. **Detection failures** - RT-DETR object detection service is unavailable or times out
2. **Analysis failures** - Nemotron LLM analysis fails after exhausting retries
3. **Transient errors** - Network issues, resource exhaustion, or temporary service degradation

### DLQ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  File Watcher   │────▶│ detection_queue │────▶│  RT-DETR        │
└─────────────────┘     └─────────────────┘     │  Detector       │
                                │               └─────────────────┘
                                │ (on failure after retries)
                                ▼
                        ┌─────────────────┐
                        │ dlq:detection_  │
                        │ queue           │
                        └─────────────────┘

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Batch           │────▶│ analysis_queue  │────▶│  Nemotron       │
│ Aggregator      │     └─────────────────┘     │  LLM            │
└─────────────────┘             │               └─────────────────┘
                                │ (on failure after retries)
                                ▼
                        ┌─────────────────┐
                        │ dlq:analysis_   │
                        │ queue           │
                        └─────────────────┘
```

### Queue Names

| Queue Name            | Description                            |
| --------------------- | -------------------------------------- |
| `dlq:detection_queue` | Failed detection jobs (image analysis) |
| `dlq:analysis_queue`  | Failed LLM analysis jobs (batches)     |

### Retry Behavior

Before a job reaches the DLQ, the system attempts to process it multiple times with exponential backoff:

- **Default max retries:** 3 attempts
- **Base delay:** 1 second
- **Max delay:** 30 seconds
- **Exponential base:** 2.0 (delays: ~1s, ~2s, ~4s)
- **Jitter:** Enabled (0-25% random variance)

Only after all retries are exhausted does a job move to the DLQ.

## Authentication

Destructive operations (requeue, clear) require API key authentication when `API_KEY_ENABLED=true`:

**HTTP Header (preferred):**

```
X-API-Key: your-api-key
```

**Query Parameter (fallback):**

```
?api_key=your-api-key
```

Read-only operations (stats, list jobs) do not require authentication.

## Endpoints

### Get DLQ Statistics

Returns aggregate counts across all dead letter queues.

```http
GET /api/dlq/stats
```

#### Response

```json
{
  "detection_queue_count": 2,
  "analysis_queue_count": 1,
  "total_count": 3
}
```

#### Response Fields

| Field                   | Type    | Description                     |
| ----------------------- | ------- | ------------------------------- |
| `detection_queue_count` | integer | Number of jobs in detection DLQ |
| `analysis_queue_count`  | integer | Number of jobs in analysis DLQ  |
| `total_count`           | integer | Total jobs across all DLQs      |

#### Example

```bash
curl http://localhost:8000/api/dlq/stats
```

---

### List DLQ Jobs

Returns jobs in a specific DLQ without removing them. Supports pagination for large queues.

```http
GET /api/dlq/jobs/{queue_name}
```

#### Path Parameters

| Parameter    | Type   | Required | Description                                             |
| ------------ | ------ | -------- | ------------------------------------------------------- |
| `queue_name` | string | Yes      | DLQ name: `dlq:detection_queue` or `dlq:analysis_queue` |

#### Query Parameters

| Parameter | Type    | Default | Max  | Description                      |
| --------- | ------- | ------- | ---- | -------------------------------- |
| `start`   | integer | 0       | -    | Start index (0-based)            |
| `limit`   | integer | 100     | 1000 | Maximum number of jobs to return |

#### Response

```json
{
  "queue_name": "dlq:detection_queue",
  "jobs": [
    {
      "original_job": {
        "camera_id": "front_door",
        "file_path": "/export/foscam/front_door/image_001.jpg",
        "timestamp": "2025-12-23T10:30:00.000000"
      },
      "error": "Connection refused: detector service unavailable",
      "attempt_count": 3,
      "first_failed_at": "2025-12-23T10:30:05.000000",
      "last_failed_at": "2025-12-23T10:30:15.000000",
      "queue_name": "detection_queue"
    }
  ],
  "count": 1
}
```

#### Response Fields

| Field        | Type    | Description                     |
| ------------ | ------- | ------------------------------- |
| `queue_name` | string  | Name of the DLQ                 |
| `jobs`       | array   | List of failed jobs             |
| `count`      | integer | Number of jobs in this response |

#### Job Object Fields

| Field             | Type    | Description                                 |
| ----------------- | ------- | ------------------------------------------- |
| `original_job`    | object  | Original job payload that failed            |
| `error`           | string  | Error message from the last failure attempt |
| `attempt_count`   | integer | Number of processing attempts made          |
| `first_failed_at` | string  | ISO timestamp of the first failure          |
| `last_failed_at`  | string  | ISO timestamp of the last failure           |
| `queue_name`      | string  | Original queue where the job came from      |

#### Example

```bash
# List first 10 jobs in detection DLQ
curl "http://localhost:8000/api/dlq/jobs/dlq:detection_queue?limit=10"

# Paginate through jobs
curl "http://localhost:8000/api/dlq/jobs/dlq:analysis_queue?start=100&limit=50"
```

---

### Requeue Single Job

Removes the oldest job from a DLQ and adds it back to its original processing queue for retry.

```http
POST /api/dlq/requeue/{queue_name}
```

**Requires authentication when API_KEY_ENABLED=true**

#### Path Parameters

| Parameter    | Type   | Required | Description                                             |
| ------------ | ------ | -------- | ------------------------------------------------------- |
| `queue_name` | string | Yes      | DLQ name: `dlq:detection_queue` or `dlq:analysis_queue` |

#### Response (Success)

```json
{
  "success": true,
  "message": "Job requeued from dlq:detection_queue to detection_queue",
  "job": null
}
```

#### Response (Empty Queue)

```json
{
  "success": false,
  "message": "No jobs to requeue from dlq:detection_queue",
  "job": null
}
```

#### Response Fields

| Field     | Type    | Description                                  |
| --------- | ------- | -------------------------------------------- |
| `success` | boolean | Whether the requeue operation succeeded      |
| `message` | string  | Status message describing the result         |
| `job`     | object  | The requeued job data (null in current impl) |

#### Example

```bash
curl -X POST http://localhost:8000/api/dlq/requeue/dlq:detection_queue \
  -H "X-API-Key: your-api-key"
```

---

### Requeue All Jobs

Removes all jobs from a DLQ and adds them back to their original processing queue for retry. Limited to prevent resource exhaustion.

```http
POST /api/dlq/requeue-all/{queue_name}
```

**Requires authentication when API_KEY_ENABLED=true**

#### Path Parameters

| Parameter    | Type   | Required | Description                                             |
| ------------ | ------ | -------- | ------------------------------------------------------- |
| `queue_name` | string | Yes      | DLQ name: `dlq:detection_queue` or `dlq:analysis_queue` |

#### Response (Success)

```json
{
  "success": true,
  "message": "Requeued 15 jobs from dlq:detection_queue to detection_queue",
  "job": null
}
```

#### Response (Hit Limit)

```json
{
  "success": true,
  "message": "Requeued 1000 jobs from dlq:detection_queue to detection_queue (hit limit of 1000)",
  "job": null
}
```

#### Response (Empty Queue)

```json
{
  "success": false,
  "message": "No jobs to requeue from dlq:detection_queue",
  "job": null
}
```

#### Configuration

The maximum number of jobs requeued in a single call is controlled by:

- **Setting:** `max_requeue_iterations`
- **Default:** 1000

This limit prevents resource exhaustion when requeuing large backlogs.

#### Example

```bash
curl -X POST http://localhost:8000/api/dlq/requeue-all/dlq:analysis_queue \
  -H "X-API-Key: your-api-key"
```

---

### Clear DLQ

Permanently removes all jobs from a dead letter queue.

```http
DELETE /api/dlq/{queue_name}
```

**Requires authentication when API_KEY_ENABLED=true**

**WARNING:** This operation permanently deletes all jobs. Use with caution.

#### Path Parameters

| Parameter    | Type   | Required | Description                                             |
| ------------ | ------ | -------- | ------------------------------------------------------- |
| `queue_name` | string | Yes      | DLQ name: `dlq:detection_queue` or `dlq:analysis_queue` |

#### Response (Success)

```json
{
  "success": true,
  "message": "Cleared 5 jobs from dlq:detection_queue",
  "queue_name": "dlq:detection_queue"
}
```

#### Response (Failure)

```json
{
  "success": false,
  "message": "Failed to clear dlq:detection_queue",
  "queue_name": "dlq:detection_queue"
}
```

#### Response Fields

| Field        | Type    | Description                               |
| ------------ | ------- | ----------------------------------------- |
| `success`    | boolean | Whether the clear operation succeeded     |
| `message`    | string  | Status message with count of cleared jobs |
| `queue_name` | string  | Name of the cleared queue                 |

#### Example

```bash
curl -X DELETE http://localhost:8000/api/dlq/dlq:detection_queue \
  -H "X-API-Key: your-api-key"
```

## Common Failure Reasons

### Detection Queue Failures

| Error                                      | Cause                                    | Resolution                                    |
| ------------------------------------------ | ---------------------------------------- | --------------------------------------------- |
| `Connection refused: detector unavailable` | RT-DETR service is down                  | Check AI container health, restart if needed  |
| `Timeout waiting for detection`            | RT-DETR overloaded or slow               | Check GPU utilization, consider scaling       |
| `File not found`                           | Image file was deleted before processing | Check file watcher timing, retention settings |
| `Invalid image format`                     | Corrupted or unsupported image           | Check camera feed, may need manual review     |

### Analysis Queue Failures

| Error                                 | Cause                             | Resolution                                   |
| ------------------------------------- | --------------------------------- | -------------------------------------------- |
| `Connection refused: LLM unavailable` | Nemotron service is down          | Check AI container health, restart if needed |
| `Timeout waiting for analysis`        | LLM overloaded or slow            | Check GPU VRAM, reduce batch size            |
| `Context length exceeded`             | Too many detections in batch      | Reduce batch window or max detections        |
| `Model loading failed`                | VRAM exhausted or model corrupted | Restart AI services, check GPU memory        |

## Circuit Breaker Protection

The DLQ system includes circuit breaker protection to prevent cascading failures when the DLQ itself becomes unavailable (e.g., Redis full or failing).

### Circuit Breaker States

| State       | Behavior                                                       |
| ----------- | -------------------------------------------------------------- |
| `CLOSED`    | Normal operation, DLQ writes proceed                           |
| `OPEN`      | DLQ failing, writes are skipped to prevent resource exhaustion |
| `HALF_OPEN` | Testing recovery, limited writes allowed                       |

### Configuration

Circuit breaker settings are controlled via environment variables:

| Variable                                  | Default | Description                           |
| ----------------------------------------- | ------- | ------------------------------------- |
| `DLQ_CIRCUIT_BREAKER_FAILURE_THRESHOLD`   | 5       | Failures before opening circuit       |
| `DLQ_CIRCUIT_BREAKER_RECOVERY_TIMEOUT`    | 60      | Seconds before attempting recovery    |
| `DLQ_CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS` | 3       | Test calls allowed in half-open state |
| `DLQ_CIRCUIT_BREAKER_SUCCESS_THRESHOLD`   | 2       | Successes needed to close circuit     |

### Monitoring

The circuit breaker status is available via the system health endpoint:

```http
GET /api/system/circuit-breakers
```

When the DLQ circuit breaker is open, jobs that would normally go to the DLQ are logged with `CRITICAL DATA LOSS` severity for audit purposes.

## Operational Workflows

### Investigating DLQ Jobs

```bash
# 1. Check DLQ statistics
curl http://localhost:8000/api/dlq/stats

# 2. List failed jobs to investigate
curl "http://localhost:8000/api/dlq/jobs/dlq:detection_queue?limit=10"

# 3. Review error messages and timestamps
# Look for patterns: same camera, same error, clustered times
```

### Recovering After Service Outage

```bash
# 1. Verify services are healthy
curl http://localhost:8000/api/system/health

# 2. Check DLQ size
curl http://localhost:8000/api/dlq/stats

# 3. Requeue all jobs for retry
curl -X POST http://localhost:8000/api/dlq/requeue-all/dlq:detection_queue \
  -H "X-API-Key: your-api-key"

curl -X POST http://localhost:8000/api/dlq/requeue-all/dlq:analysis_queue \
  -H "X-API-Key: your-api-key"

# 4. Monitor for new failures
watch -n 5 'curl -s http://localhost:8000/api/dlq/stats'
```

### Clearing Stale Jobs

```bash
# Review jobs first - ensure they're truly stale
curl "http://localhost:8000/api/dlq/jobs/dlq:detection_queue"

# If jobs are from deleted cameras or old files, clear them
curl -X DELETE http://localhost:8000/api/dlq/dlq:detection_queue \
  -H "X-API-Key: your-api-key"
```

## Related Documentation

- [System API](system.md) - Health checks and circuit breaker status
- [WebSocket API](websocket.md) - Real-time system status updates
- [Architecture: AI Pipeline](../architecture/ai-pipeline.md) - Pipeline design and flow
- [Architecture: Resilience](../architecture/resilience.md) - Retry and circuit breaker patterns
