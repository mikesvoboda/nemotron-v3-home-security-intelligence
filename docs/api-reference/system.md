---
title: System API
description: REST API endpoints for system monitoring and configuration
source_refs:
  - backend/api/routes/system.py
  - backend/api/schemas/system.py
  - backend/models/gpu_stats.py
  - backend/models/log.py
---

# System API

The System API provides endpoints for monitoring system health, GPU statistics, configuration management, telemetry, and storage metrics.

## Endpoints Overview

| Method | Endpoint                                    | Description                |
| ------ | ------------------------------------------- | -------------------------- |
| GET    | `/api/system/health`                        | Detailed health check      |
| GET    | `/health` (root level)                      | Kubernetes liveness probe  |
| GET    | `/api/system/health/ready`                  | Kubernetes readiness probe |
| GET    | `/api/system/gpu`                           | Current GPU statistics     |
| GET    | `/api/system/gpu/history`                   | GPU stats time series      |
| GET    | `/api/system/stats`                         | System statistics          |
| GET    | `/api/system/config`                        | Get configuration          |
| PATCH  | `/api/system/config`                        | Update configuration       |
| GET    | `/api/system/telemetry`                     | Pipeline telemetry         |
| GET    | `/api/system/pipeline-latency`              | Pipeline latency metrics   |
| POST   | `/api/system/cleanup`                       | Trigger data cleanup       |
| GET    | `/api/system/severity`                      | Severity definitions       |
| PUT    | `/api/system/severity`                      | Update severity thresholds |
| GET    | `/api/system/storage`                       | Storage statistics         |
| GET    | `/api/system/pipeline`                      | Pipeline status            |
| GET    | `/api/system/pipeline-latency/history`      | Pipeline latency history   |
| GET    | `/api/system/cleanup/status`                | Cleanup job status         |
| GET    | `/api/system/circuit-breakers`              | List circuit breakers      |
| POST   | `/api/system/circuit-breakers/{name}/reset` | Reset circuit breaker      |
| GET    | `/api/system/models`                        | Model Zoo registry         |
| GET    | `/api/system/models/{model_name}`           | Get specific model status  |
| GET    | `/api/system/model-zoo/status`              | Model Zoo compact status   |
| GET    | `/api/system/model-zoo/latency/history`     | Model latency time series  |

> **Note:** For detailed Model Zoo documentation, see [Model Zoo API](model-zoo.md).

---

## GET /api/system/health

Get detailed system health check.

**Source:** [`get_health`](../../backend/api/routes/system.py:665)

**Response:** `200 OK` (healthy) or `503 Service Unavailable` (degraded/unhealthy)

```json
{
  "status": "healthy",
  "services": {
    "database": {
      "status": "healthy",
      "message": "Database operational",
      "details": null
    },
    "redis": {
      "status": "healthy",
      "message": "Redis connected",
      "details": { "redis_version": "7.0.0" }
    },
    "ai": {
      "status": "healthy",
      "message": "AI services operational",
      "details": { "rtdetr": "healthy", "nemotron": "healthy" }
    }
  },
  "timestamp": "2025-12-23T10:30:00Z"
}
```

**Response Fields:**

| Field       | Type     | Description                                        |
| ----------- | -------- | -------------------------------------------------- |
| `status`    | string   | Overall status: `healthy`, `degraded`, `unhealthy` |
| `services`  | object   | Individual service status objects                  |
| `timestamp` | datetime | Health check timestamp                             |

**Service Status Values:**

| Status      | Description                               |
| ----------- | ----------------------------------------- |
| `healthy`   | Service is functioning normally           |
| `degraded`  | Service has issues but system can operate |
| `unhealthy` | Service is down or not responding         |

**Health Check Flow:**

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API
    participant DB as PostgreSQL
    participant R as Redis
    participant RT as RT-DETR
    participant NM as Nemotron

    C->>A: GET /api/system/health
    par Database Check
        A->>DB: SELECT COUNT(*) FROM cameras
        DB-->>A: OK
    and Redis Check
        A->>R: PING
        R-->>A: PONG
    and AI Services Check
        A->>RT: GET /health
        RT-->>A: OK
        A->>NM: GET /health
        NM-->>A: OK
    end
    A-->>C: 200 OK with status
```

---

## GET /health (Root Level)

Kubernetes-style liveness probe.

**Source:** [`health`](../../backend/main.py:297)

**Response:** `200 OK`

```json
{
  "status": "alive"
}
```

**Purpose:** Indicates whether the process is running. Always returns 200 if the HTTP server is responding. Used by container orchestrators to determine if the process needs to be restarted.

**Note:** This is a root-level endpoint (not under `/api/system/`). The previous `/api/system/health/live` endpoint was removed to consolidate duplicate functionality.

---

## GET /api/system/health/ready

Kubernetes-style readiness probe with detailed status.

**Source:** [`get_readiness`](../../backend/api/routes/system.py:774)

**Response:** `200 OK` (ready) or `503 Service Unavailable` (not ready)

```json
{
  "ready": true,
  "status": "ready",
  "services": {
    "database": {
      "status": "healthy",
      "message": "Database operational",
      "details": null
    },
    "redis": {
      "status": "healthy",
      "message": "Redis connected",
      "details": { "redis_version": "7.0.0" }
    },
    "ai": {
      "status": "healthy",
      "message": "AI services operational",
      "details": null
    }
  },
  "workers": [
    { "name": "gpu_monitor", "running": true, "message": null },
    { "name": "cleanup_service", "running": true, "message": null },
    { "name": "detection_worker", "running": true, "message": null },
    { "name": "analysis_worker", "running": true, "message": null }
  ],
  "timestamp": "2025-12-23T10:30:00Z"
}
```

**Response Fields:**

| Field       | Type     | Description                         |
| ----------- | -------- | ----------------------------------- |
| `ready`     | boolean  | Whether system can process requests |
| `status`    | string   | `ready`, `degraded`, or `not_ready` |
| `services`  | object   | Infrastructure service statuses     |
| `workers`   | array    | Background worker statuses          |
| `timestamp` | datetime | Check timestamp                     |

**Readiness Criteria:**

- Database must be healthy
- Redis must be healthy
- Pipeline workers (detection, analysis) must be running

---

## GET /api/system/gpu

Get current GPU statistics.

**Source:** [`get_gpu_stats`](../../backend/api/routes/system.py:893)

**Response:** `200 OK`

```json
{
  "gpu_name": "NVIDIA RTX A5500",
  "utilization": 75.5,
  "memory_used": 12000,
  "memory_total": 24000,
  "temperature": 65.0,
  "power_usage": 150.0,
  "inference_fps": 30.5
}
```

**Response Fields:**

| Field           | Type    | Description                                 |
| --------------- | ------- | ------------------------------------------- |
| `gpu_name`      | string  | GPU device name (nullable)                  |
| `utilization`   | float   | GPU utilization percentage 0-100 (nullable) |
| `memory_used`   | integer | Memory used in MB (nullable)                |
| `memory_total`  | integer | Total memory in MB (nullable)               |
| `temperature`   | float   | Temperature in Celsius (nullable)           |
| `power_usage`   | float   | Power usage in watts (nullable)             |
| `inference_fps` | float   | Inference frames per second (nullable)      |

---

## GET /api/system/gpu/history

Get GPU statistics time series for charting.

**Source:** [`get_gpu_stats_history`](../../backend/api/routes/system.py:933)

**Parameters:**

| Name    | Type     | In    | Required | Description                                     |
| ------- | -------- | ----- | -------- | ----------------------------------------------- |
| `since` | datetime | query | No       | Lower bound for recorded_at (ISO datetime)      |
| `limit` | integer  | query | No       | Max samples to return (default: 300, max: 5000) |

**Response:** `200 OK`

```json
{
  "samples": [
    {
      "recorded_at": "2025-12-23T10:00:00Z",
      "gpu_name": "NVIDIA RTX A5500",
      "utilization": 72.0,
      "memory_used": 11500,
      "memory_total": 24000,
      "temperature": 64.0,
      "power_usage": 145.0,
      "inference_fps": 28.5
    }
  ],
  "count": 1,
  "limit": 300
}
```

**Example Request:**

```bash
# Get last 100 samples
curl "http://localhost:8000/api/system/gpu/history?limit=100"

# Get samples since specific time
curl "http://localhost:8000/api/system/gpu/history?since=2025-12-23T09:00:00Z"
```

---

## GET /api/system/stats

Get system statistics.

**Source:** [`get_stats`](../../backend/api/routes/system.py:1100)

**Response:** `200 OK`

```json
{
  "total_cameras": 4,
  "total_events": 156,
  "total_detections": 892,
  "uptime_seconds": 86400.5
}
```

**Response Fields:**

| Field              | Type    | Description                   |
| ------------------ | ------- | ----------------------------- |
| `total_cameras`    | integer | Total number of cameras       |
| `total_events`     | integer | Total number of events        |
| `total_detections` | integer | Total number of detections    |
| `uptime_seconds`   | float   | Application uptime in seconds |

---

## GET /api/system/config

Get public configuration settings.

**Source:** [`get_config`](../../backend/api/routes/system.py:976)

**Response:** `200 OK`

```json
{
  "app_name": "Home Security Intelligence",
  "version": "0.1.0",
  "retention_days": 30,
  "batch_window_seconds": 90,
  "batch_idle_timeout_seconds": 30,
  "detection_confidence_threshold": 0.5
}
```

**Response Fields:**

| Field                            | Type    | Description                    |
| -------------------------------- | ------- | ------------------------------ |
| `app_name`                       | string  | Application name               |
| `version`                        | string  | Application version            |
| `retention_days`                 | integer | Data retention period (1-365)  |
| `batch_window_seconds`           | integer | Detection batch window         |
| `batch_idle_timeout_seconds`     | integer | Batch idle timeout             |
| `detection_confidence_threshold` | float   | Min confidence threshold (0-1) |

**Note:** This endpoint does NOT expose secrets like database URLs or API keys.

---

## PATCH /api/system/config

Update runtime configuration settings.

**Source:** [`patch_config`](../../backend/api/routes/system.py:1023)

**Authentication:** Required when `API_KEY_ENABLED=true` (via `X-API-Key` header)

**Request Body:**

```json
{
  "retention_days": 14,
  "batch_window_seconds": 60,
  "batch_idle_timeout_seconds": 20,
  "detection_confidence_threshold": 0.6
}
```

**Request Fields:**

| Field                            | Type    | Required | Constraints | Description              |
| -------------------------------- | ------- | -------- | ----------- | ------------------------ |
| `retention_days`                 | integer | No       | 1-365       | Data retention period    |
| `batch_window_seconds`           | integer | No       | >= 1        | Detection batch window   |
| `batch_idle_timeout_seconds`     | integer | No       | >= 1        | Batch idle timeout       |
| `detection_confidence_threshold` | float   | No       | 0.0-1.0     | Min confidence threshold |

**Response:** `200 OK`

Returns updated configuration (same format as GET).

**Errors:**

| Code | Description                 |
| ---- | --------------------------- |
| 401  | API key required or invalid |
| 422  | Validation error            |

**Example Request:**

```bash
curl -X PATCH http://localhost:8000/api/system/config \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"retention_days": 14}'
```

**Audit Log:** Creates audit entry with action `settings_changed`.

---

## GET /api/system/telemetry

Get pipeline telemetry data.

**Source:** [`get_telemetry`](../../backend/api/routes/system.py:1271)

**Response:** `200 OK`

```json
{
  "queues": {
    "detection_queue": 5,
    "analysis_queue": 2
  },
  "latencies": {
    "watch": {
      "avg_ms": 10.0,
      "min_ms": 5.0,
      "max_ms": 50.0,
      "p50_ms": 8.0,
      "p95_ms": 40.0,
      "p99_ms": 48.0,
      "sample_count": 500
    },
    "detect": {
      "avg_ms": 200.0,
      "min_ms": 100.0,
      "max_ms": 800.0,
      "p50_ms": 180.0,
      "p95_ms": 600.0,
      "p99_ms": 750.0,
      "sample_count": 500
    },
    "batch": null,
    "analyze": null
  },
  "timestamp": "2025-12-27T10:30:00Z"
}
```

**Response Fields:**

| Field                    | Type     | Description                     |
| ------------------------ | -------- | ------------------------------- |
| `queues.detection_queue` | integer  | Items in detection queue        |
| `queues.analysis_queue`  | integer  | Items in analysis queue         |
| `latencies.watch`        | object   | File watcher latency stats      |
| `latencies.detect`       | object   | Object detection latency stats  |
| `latencies.batch`        | object   | Batch aggregation latency stats |
| `latencies.analyze`      | object   | LLM analysis latency stats      |
| `timestamp`              | datetime | Telemetry snapshot timestamp    |

---

## GET /api/system/pipeline-latency

Get detailed pipeline latency metrics with percentiles.

**Source:** [`get_pipeline_latency`](../../backend/api/routes/system.py:1344)

**Parameters:**

| Name             | Type    | In    | Required | Description                         |
| ---------------- | ------- | ----- | -------- | ----------------------------------- |
| `window_minutes` | integer | query | No       | Time window for stats (default: 60) |

**Response:** `200 OK`

```json
{
  "watch_to_detect": {
    "avg_ms": 50.0,
    "min_ms": 10.0,
    "max_ms": 200.0,
    "p50_ms": 40.0,
    "p95_ms": 150.0,
    "p99_ms": 180.0,
    "sample_count": 500
  },
  "detect_to_batch": {
    "avg_ms": 100.0,
    "min_ms": 20.0,
    "max_ms": 500.0,
    "p50_ms": 80.0,
    "p95_ms": 400.0,
    "p99_ms": 480.0,
    "sample_count": 500
  },
  "batch_to_analyze": {
    "avg_ms": 5000.0,
    "min_ms": 2000.0,
    "max_ms": 15000.0,
    "p50_ms": 4500.0,
    "p95_ms": 12000.0,
    "p99_ms": 14000.0,
    "sample_count": 100
  },
  "total_pipeline": {
    "avg_ms": 35000.0,
    "min_ms": 10000.0,
    "max_ms": 120000.0,
    "p50_ms": 30000.0,
    "p95_ms": 100000.0,
    "p99_ms": 110000.0,
    "sample_count": 100
  },
  "window_minutes": 60,
  "timestamp": "2025-12-28T10:30:00Z"
}
```

---

## GET /api/system/pipeline-latency/history

Get pipeline latency history for time-series visualization and charting.

**Source:** [`get_pipeline_latency_history`](../../backend/api/routes/system.py:1548)

**Parameters:**

| Name             | Type    | In    | Required | Description                                                |
| ---------------- | ------- | ----- | -------- | ---------------------------------------------------------- |
| `since`          | integer | query | No       | Minutes of history to return (1-1440, default: 60)         |
| `bucket_seconds` | integer | query | No       | Size of each time bucket in seconds (10-3600, default: 60) |

**Response:** `200 OK`

```json
{
  "snapshots": [
    {
      "timestamp": "2025-12-28T10:00:00+00:00",
      "stages": {
        "watch_to_detect": {
          "avg_ms": 50.0,
          "p50_ms": 45.0,
          "p95_ms": 120.0,
          "p99_ms": 150.0,
          "sample_count": 15
        },
        "detect_to_batch": {
          "avg_ms": 100.0,
          "p50_ms": 80.0,
          "p95_ms": 400.0,
          "p99_ms": 480.0,
          "sample_count": 15
        },
        "batch_to_analyze": null,
        "total_pipeline": null
      }
    },
    {
      "timestamp": "2025-12-28T10:01:00+00:00",
      "stages": {
        "watch_to_detect": {
          "avg_ms": 55.0,
          "p50_ms": 50.0,
          "p95_ms": 130.0,
          "p99_ms": 160.0,
          "sample_count": 12
        },
        "detect_to_batch": null,
        "batch_to_analyze": null,
        "total_pipeline": null
      }
    }
  ],
  "window_minutes": 60,
  "bucket_seconds": 60,
  "timestamp": "2025-12-28T10:30:00Z"
}
```

**Response Fields:**

| Field            | Type     | Description                               |
| ---------------- | -------- | ----------------------------------------- |
| `snapshots`      | array    | Chronologically ordered latency snapshots |
| `window_minutes` | integer  | Time window covered by the history        |
| `bucket_seconds` | integer  | Bucket size used for aggregation          |
| `timestamp`      | datetime | When the history was retrieved            |

**Snapshot Fields:**

| Field       | Type   | Description                                                |
| ----------- | ------ | ---------------------------------------------------------- |
| `timestamp` | string | Bucket start time in ISO format                            |
| `stages`    | object | Latency stats for each pipeline stage (null if no samples) |

**Stage Statistics Fields:**

| Field          | Type    | Description                           |
| -------------- | ------- | ------------------------------------- |
| `avg_ms`       | float   | Average latency in milliseconds       |
| `p50_ms`       | float   | 50th percentile (median) latency      |
| `p95_ms`       | float   | 95th percentile latency               |
| `p99_ms`       | float   | 99th percentile latency               |
| `sample_count` | integer | Number of samples in this time bucket |

**Pipeline Stages:**

| Stage              | Description                                             |
| ------------------ | ------------------------------------------------------- |
| `watch_to_detect`  | Time from file watcher detecting image to RT-DETR start |
| `detect_to_batch`  | Time from detection completion to batch aggregation     |
| `batch_to_analyze` | Time from batch completion to Nemotron analysis start   |
| `total_pipeline`   | Total end-to-end processing time                        |

**Example Requests:**

```bash
# Get last 60 minutes with 1-minute buckets (default)
curl "http://localhost:8000/api/system/pipeline-latency/history"

# Get last 24 hours with 5-minute buckets
curl "http://localhost:8000/api/system/pipeline-latency/history?since=1440&bucket_seconds=300"

# Get last 5 minutes with 10-second buckets (high resolution)
curl "http://localhost:8000/api/system/pipeline-latency/history?since=5&bucket_seconds=10"
```

---

## GET /api/system/pipeline

Get combined status of all pipeline operations.

**Source:** [`get_pipeline_status`](../../backend/api/routes/system.py:2387)

**Response:** `200 OK`

```json
{
  "file_watcher": {
    "running": true,
    "camera_root": "/export/foscam",
    "pending_tasks": 3,
    "observer_type": "native"
  },
  "batch_aggregator": {
    "active_batches": 2,
    "batches": [
      {
        "batch_id": "abc123def456",
        "camera_id": "front_door",
        "detection_count": 5,
        "started_at": 1735500000.0,
        "age_seconds": 45.5,
        "last_activity_seconds": 10.2
      },
      {
        "batch_id": "xyz789ghi012",
        "camera_id": "backyard",
        "detection_count": 3,
        "started_at": 1735500030.0,
        "age_seconds": 15.2,
        "last_activity_seconds": 5.1
      }
    ],
    "batch_window_seconds": 90,
    "idle_timeout_seconds": 30
  },
  "degradation": {
    "mode": "normal",
    "is_degraded": false,
    "redis_healthy": true,
    "memory_queue_size": 0,
    "fallback_queues": {},
    "services": [
      {
        "name": "rtdetr",
        "status": "healthy",
        "last_check": 1735500000.0,
        "consecutive_failures": 0,
        "error_message": null
      },
      {
        "name": "nemotron",
        "status": "healthy",
        "last_check": 1735500000.0,
        "consecutive_failures": 0,
        "error_message": null
      }
    ],
    "available_features": ["detection", "analysis", "events", "media"]
  },
  "timestamp": "2025-12-30T10:30:00Z"
}
```

**Response Fields:**

| Field              | Type     | Description                                          |
| ------------------ | -------- | ---------------------------------------------------- |
| `file_watcher`     | object   | FileWatcher service status (null if not running)     |
| `batch_aggregator` | object   | BatchAggregator service status (null if unavailable) |
| `degradation`      | object   | DegradationManager status (null if not initialized)  |
| `timestamp`        | datetime | Status snapshot timestamp                            |

**FileWatcher Fields:**

| Field           | Type    | Description                                     |
| --------------- | ------- | ----------------------------------------------- |
| `running`       | boolean | Whether the file watcher is active              |
| `camera_root`   | string  | Root directory being watched for camera uploads |
| `pending_tasks` | integer | Files waiting for debounce completion           |
| `observer_type` | string  | Filesystem observer type: `native` or `polling` |

**BatchAggregator Fields:**

| Field                  | Type    | Description                                  |
| ---------------------- | ------- | -------------------------------------------- |
| `active_batches`       | integer | Number of batches currently being aggregated |
| `batches`              | array   | Details of each active batch                 |
| `batch_window_seconds` | integer | Configured batch window timeout              |
| `idle_timeout_seconds` | integer | Configured idle timeout before flush         |

**Batch Info Fields:**

| Field                   | Type    | Description                       |
| ----------------------- | ------- | --------------------------------- |
| `batch_id`              | string  | Unique batch identifier           |
| `camera_id`             | string  | Camera this batch belongs to      |
| `detection_count`       | integer | Number of detections in batch     |
| `started_at`            | float   | Batch start time (Unix timestamp) |
| `age_seconds`           | float   | Time since batch started          |
| `last_activity_seconds` | float   | Time since last activity in batch |

**DegradationManager Fields:**

| Field                | Type    | Description                                              |
| -------------------- | ------- | -------------------------------------------------------- |
| `mode`               | string  | Current mode: `normal`, `degraded`, `minimal`, `offline` |
| `is_degraded`        | boolean | Whether system is in any degraded state                  |
| `redis_healthy`      | boolean | Whether Redis connection is healthy                      |
| `memory_queue_size`  | integer | Items in in-memory fallback queue                        |
| `fallback_queues`    | object  | Count of items in disk-based fallback queues             |
| `services`           | array   | Health status of registered services                     |
| `available_features` | array   | Features available in current degradation mode           |

**Degradation Modes:**

| Mode       | Description                                           |
| ---------- | ----------------------------------------------------- |
| `normal`   | All services healthy, full functionality              |
| `degraded` | Some services impaired, reduced functionality         |
| `minimal`  | Critical services only, minimal functionality         |
| `offline`  | All external services unavailable, local caching only |

**Example Request:**

```bash
curl http://localhost:8000/api/system/pipeline
```

---

## GET /api/system/cleanup/status

Get current status of the automated cleanup service.

**Source:** [`get_cleanup_status`](../../backend/api/routes/system.py:2177)

**Response:** `200 OK`

```json
{
  "running": true,
  "retention_days": 30,
  "cleanup_time": "03:00",
  "delete_images": false,
  "next_cleanup": "2025-12-31T03:00:00Z",
  "timestamp": "2025-12-30T10:30:00Z"
}
```

**Response Fields:**

| Field            | Type     | Description                                                   |
| ---------------- | -------- | ------------------------------------------------------------- |
| `running`        | boolean  | Whether the cleanup service is currently running              |
| `retention_days` | integer  | Current retention period in days (1-365)                      |
| `cleanup_time`   | string   | Scheduled daily cleanup time in HH:MM format                  |
| `delete_images`  | boolean  | Whether original images are deleted during cleanup            |
| `next_cleanup`   | string   | ISO timestamp of next scheduled cleanup (null if not running) |
| `timestamp`      | datetime | Timestamp of status snapshot                                  |

**Example Request:**

```bash
curl http://localhost:8000/api/system/cleanup/status
```

**Notes:**

- The cleanup service runs automatically at the configured `cleanup_time` each day
- When `running` is `false`, the service is not registered or has stopped
- The `next_cleanup` field is `null` if the service is not running
- To trigger an immediate cleanup, use `POST /api/system/cleanup` instead

---

## POST /api/system/cleanup

Trigger manual data cleanup.

**Source:** [`trigger_cleanup`](../../backend/api/routes/system.py:1391)

**Authentication:** Required when `API_KEY_ENABLED=true` (via `X-API-Key` header)

**Parameters:**

| Name      | Type    | In    | Required | Description                                         |
| --------- | ------- | ----- | -------- | --------------------------------------------------- |
| `dry_run` | boolean | query | No       | Preview deletion without executing (default: false) |

**Response:** `200 OK`

```json
{
  "events_deleted": 15,
  "detections_deleted": 89,
  "gpu_stats_deleted": 2880,
  "logs_deleted": 150,
  "thumbnails_deleted": 89,
  "images_deleted": 0,
  "space_reclaimed": 524288000,
  "retention_days": 30,
  "dry_run": false,
  "timestamp": "2025-12-27T10:30:00Z"
}
```

**Response Fields:**

| Field                | Type     | Description                  |
| -------------------- | -------- | ---------------------------- |
| `events_deleted`     | integer  | Events deleted (or would be) |
| `detections_deleted` | integer  | Detections deleted           |
| `gpu_stats_deleted`  | integer  | GPU stat records deleted     |
| `logs_deleted`       | integer  | Log records deleted          |
| `thumbnails_deleted` | integer  | Thumbnail files deleted      |
| `images_deleted`     | integer  | Original images deleted      |
| `space_reclaimed`    | integer  | Bytes freed (estimated)      |
| `retention_days`     | integer  | Retention period used        |
| `dry_run`            | boolean  | Whether this was a dry run   |
| `timestamp`          | datetime | Operation timestamp          |

**Example Requests:**

```bash
# Preview what would be deleted
curl -X POST "http://localhost:8000/api/system/cleanup?dry_run=true" \
  -H "X-API-Key: your-api-key"

# Execute cleanup
curl -X POST http://localhost:8000/api/system/cleanup \
  -H "X-API-Key: your-api-key"
```

---

## GET /api/system/severity

Get severity level definitions and thresholds.

**Source:** [`get_severity_metadata`](../../backend/api/routes/system.py:1495)

**Response:** `200 OK`

```json
{
  "definitions": [
    {
      "severity": "low",
      "label": "Low",
      "description": "Routine activity, no concern",
      "color": "#22c55e",
      "priority": 3,
      "min_score": 0,
      "max_score": 29
    },
    {
      "severity": "medium",
      "label": "Medium",
      "description": "Notable activity, worth reviewing",
      "color": "#eab308",
      "priority": 2,
      "min_score": 30,
      "max_score": 59
    },
    {
      "severity": "high",
      "label": "High",
      "description": "Concerning activity, review soon",
      "color": "#f97316",
      "priority": 1,
      "min_score": 60,
      "max_score": 84
    },
    {
      "severity": "critical",
      "label": "Critical",
      "description": "Immediate attention required",
      "color": "#ef4444",
      "priority": 0,
      "min_score": 85,
      "max_score": 100
    }
  ],
  "thresholds": {
    "low_max": 29,
    "medium_max": 59,
    "high_max": 84
  }
}
```

---

## PUT /api/system/severity

Update severity threshold configuration.

**Source:** [`update_severity_thresholds`](../../backend/api/routes/system.py:1778)

**Authentication:** Required when `API_KEY_ENABLED=true` (via `X-API-Key` header)

**Request Body:**

```json
{
  "low_max": 29,
  "medium_max": 59,
  "high_max": 84
}
```

**Request Fields:**

| Field        | Type    | Required | Constraints | Description                                                      |
| ------------ | ------- | -------- | ----------- | ---------------------------------------------------------------- |
| `low_max`    | integer | Yes      | 1-98        | Maximum risk score for LOW severity (0 to low_max)               |
| `medium_max` | integer | Yes      | 2-99        | Maximum risk score for MEDIUM severity (low_max+1 to medium_max) |
| `high_max`   | integer | Yes      | 3-99        | Maximum risk score for HIGH severity (medium_max+1 to high_max)  |

**Response:** `200 OK`

Returns the updated severity metadata (same format as GET):

```json
{
  "definitions": [
    {
      "severity": "low",
      "label": "Low",
      "description": "Routine activity, no concern",
      "color": "#22c55e",
      "priority": 3,
      "min_score": 0,
      "max_score": 29
    },
    {
      "severity": "medium",
      "label": "Medium",
      "description": "Notable activity, worth reviewing",
      "color": "#eab308",
      "priority": 2,
      "min_score": 30,
      "max_score": 59
    },
    {
      "severity": "high",
      "label": "High",
      "description": "Concerning activity, review soon",
      "color": "#f97316",
      "priority": 1,
      "min_score": 60,
      "max_score": 84
    },
    {
      "severity": "critical",
      "label": "Critical",
      "description": "Immediate attention required",
      "color": "#ef4444",
      "priority": 0,
      "min_score": 85,
      "max_score": 100
    }
  ],
  "thresholds": {
    "low_max": 29,
    "medium_max": 59,
    "high_max": 84
  }
}
```

**Validation Rules:**

1. **Strict ordering:** Thresholds must be strictly ordered: `low_max < medium_max < high_max`
2. **Value ranges:** All thresholds must be between 1 and 99
3. **Contiguous ranges:** This ensures contiguous, non-overlapping ranges covering 0-100

**Severity Level Ranges:**

The thresholds define how risk scores (0-100) map to severity levels:

| Severity   | Score Range                  | Description                       |
| ---------- | ---------------------------- | --------------------------------- |
| `low`      | 0 to `low_max`               | Routine activity, no concern      |
| `medium`   | `low_max+1` to `medium_max`  | Notable activity, worth reviewing |
| `high`     | `medium_max+1` to `high_max` | Concerning activity, review soon  |
| `critical` | `high_max+1` to 100          | Immediate attention required      |

**Errors:**

| Code | Description                                                   |
| ---- | ------------------------------------------------------------- |
| 400  | Thresholds not strictly ordered (e.g., low_max >= medium_max) |
| 401  | API key required or invalid                                   |
| 422  | Validation error (values out of range)                        |

**Example Requests:**

```bash
# Update severity thresholds (default values)
curl -X PUT http://localhost:8000/api/system/severity \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"low_max": 29, "medium_max": 59, "high_max": 84}'

# Tighten thresholds (more events classified as higher severity)
curl -X PUT http://localhost:8000/api/system/severity \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"low_max": 20, "medium_max": 45, "high_max": 70}'

# Loosen thresholds (fewer events classified as high/critical)
curl -X PUT http://localhost:8000/api/system/severity \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"low_max": 40, "medium_max": 70, "high_max": 90}'
```

**Important Notes:**

- **Existing events unaffected:** Changes only affect new events. Existing events retain their original severity assignment.
- **Persistent storage:** Thresholds are persisted to the runtime environment file and survive container restarts.
- **Audit log:** Creates audit entry with action `settings_changed` recording old and new threshold values.

**Audit Log Entry:**

```json
{
  "action": "settings_changed",
  "resource_type": "severity_thresholds",
  "details": {
    "changes": {
      "low_max": { "old": 29, "new": 20 },
      "medium_max": { "old": 59, "new": 45 },
      "high_max": { "old": 84, "new": 70 }
    }
  }
}
```

---

## GET /api/system/storage

Get storage statistics and disk usage.

**Source:** [`get_storage_stats`](../../backend/api/routes/system.py:1583)

**Response:** `200 OK`

```json
{
  "disk_used_bytes": 107374182400,
  "disk_total_bytes": 536870912000,
  "disk_free_bytes": 429496729600,
  "disk_usage_percent": 20.0,
  "thumbnails": {
    "file_count": 1500,
    "size_bytes": 75000000
  },
  "images": {
    "file_count": 10000,
    "size_bytes": 5000000000
  },
  "clips": {
    "file_count": 50,
    "size_bytes": 500000000
  },
  "events_count": 156,
  "detections_count": 892,
  "gpu_stats_count": 2880,
  "logs_count": 5000,
  "timestamp": "2025-12-30T10:30:00Z"
}
```

**Response Fields:**

| Field                | Type     | Description                   |
| -------------------- | -------- | ----------------------------- |
| `disk_used_bytes`    | integer  | Total disk space used         |
| `disk_total_bytes`   | integer  | Total disk capacity           |
| `disk_free_bytes`    | integer  | Free disk space               |
| `disk_usage_percent` | float    | Disk usage percentage (0-100) |
| `thumbnails`         | object   | Thumbnail storage stats       |
| `images`             | object   | Original image storage stats  |
| `clips`              | object   | Video clip storage stats      |
| `events_count`       | integer  | Total events in database      |
| `detections_count`   | integer  | Total detections in database  |
| `gpu_stats_count`    | integer  | Total GPU stat records        |
| `logs_count`         | integer  | Total log entries             |
| `timestamp`          | datetime | Snapshot timestamp            |

---

## GET /api/system/circuit-breakers

Get status of all circuit breakers in the system.

**Source:** [`get_circuit_breakers`](../../backend/api/routes/system.py:1774)

**Response:** `200 OK`

```json
{
  "circuit_breakers": {
    "rtdetr": {
      "name": "rtdetr",
      "state": "closed",
      "failure_count": 0,
      "success_count": 10,
      "total_calls": 100,
      "rejected_calls": 0,
      "last_failure_time": null,
      "opened_at": null,
      "config": {
        "failure_threshold": 5,
        "recovery_timeout": 30.0,
        "half_open_max_calls": 3,
        "success_threshold": 2
      }
    },
    "nemotron": {
      "name": "nemotron",
      "state": "closed",
      "failure_count": 0,
      "success_count": 5,
      "total_calls": 50,
      "rejected_calls": 0,
      "last_failure_time": null,
      "opened_at": null,
      "config": {
        "failure_threshold": 5,
        "recovery_timeout": 30.0,
        "half_open_max_calls": 3,
        "success_threshold": 2
      }
    }
  },
  "total_count": 2,
  "open_count": 0,
  "timestamp": "2025-12-30T10:30:00Z"
}
```

**Response Fields:**

| Field              | Type     | Description                              |
| ------------------ | -------- | ---------------------------------------- |
| `circuit_breakers` | object   | Map of circuit breaker names to status   |
| `total_count`      | integer  | Total number of circuit breakers         |
| `open_count`       | integer  | Number of circuit breakers in OPEN state |
| `timestamp`        | datetime | Response timestamp                       |

**Circuit Breaker State Values:**

| State       | Description                                 |
| ----------- | ------------------------------------------- |
| `closed`    | Normal operation, calls pass through        |
| `open`      | Service failing, calls rejected immediately |
| `half_open` | Testing recovery, limited calls allowed     |

---

## POST /api/system/circuit-breakers/{name}/reset

Reset a specific circuit breaker to CLOSED state.

**Source:** [`reset_circuit_breaker`](../../backend/api/routes/system.py:1831)

**Authentication:** Required when `API_KEY_ENABLED=true` (via `X-API-Key` header)

**Parameters:**

| Name   | Type   | In   | Required | Description                 |
| ------ | ------ | ---- | -------- | --------------------------- |
| `name` | string | path | Yes      | Name of the circuit breaker |

**Response:** `200 OK`

```json
{
  "name": "rtdetr",
  "previous_state": "open",
  "new_state": "closed",
  "message": "Circuit breaker 'rtdetr' reset successfully from open to closed"
}
```

**Response Fields:**

| Field            | Type   | Description                         |
| ---------------- | ------ | ----------------------------------- |
| `name`           | string | Circuit breaker name                |
| `previous_state` | string | State before reset                  |
| `new_state`      | string | State after reset (always `closed`) |
| `message`        | string | Human-readable confirmation message |

**Errors:**

| Code | Description                                                    |
| ---- | -------------------------------------------------------------- |
| 400  | Invalid name (empty, too long, or contains invalid characters) |
| 401  | API key required or invalid                                    |
| 404  | Circuit breaker with specified name not found                  |

**Example Request:**

```bash
curl -X POST http://localhost:8000/api/system/circuit-breakers/rtdetr/reset \
  -H "X-API-Key: your-api-key"
```

---

## Related Documentation

- [Model Zoo API](model-zoo.md) - AI model status and latency monitoring
- [Enrichment API](enrichment.md) - Vision model analysis results
- [Events API](events.md) - Event statistics
- [Detections API](detections.md) - Detection counts
- [Cameras API](cameras.md) - Camera management
- [WebSocket API](websocket.md) - Real-time system status
