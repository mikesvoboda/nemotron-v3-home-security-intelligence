# System Endpoints

> REST API endpoints for health checks, configuration, and monitoring.

**Time to read:** ~7 min
**Prerequisites:** [API Overview](overview.md)

---

## Overview

The System API provides endpoints for monitoring system health, viewing and updating configuration, and accessing telemetry data.

**Base path:** `/api/system`

## Health Endpoints

### Basic Health Check

```
GET /api/system/health
```

Returns detailed health status of all system components.

**Response:** `200 OK` (healthy) or `503 Service Unavailable`

```json
{
  "status": "healthy",
  "services": {
    "database": {
      "status": "healthy",
      "message": "Database operational"
    },
    "redis": {
      "status": "healthy",
      "message": "Redis connected",
      "details": {
        "redis_version": "7.0.0"
      }
    },
    "ai": {
      "status": "healthy",
      "message": "AI services operational",
      "details": {
        "rtdetr": "healthy",
        "nemotron": "healthy"
      }
    }
  },
  "timestamp": "2025-01-15T14:30:00Z"
}
```

### Readiness Check

```
GET /api/system/health/ready
```

Kubernetes-style readiness probe. Checks if the system is ready to process requests.

**Response:** `200 OK` (ready) or `503 Service Unavailable`

```json
{
  "ready": true,
  "status": "ready",
  "services": { ... },
  "workers": [
    {
      "name": "detection_worker",
      "running": true,
      "message": null
    },
    {
      "name": "analysis_worker",
      "running": true,
      "message": null
    }
  ],
  "timestamp": "2025-01-15T14:30:00Z"
}
```

## GPU Monitoring

### Current GPU Stats

```
GET /api/system/gpu
```

Returns current GPU statistics.

**Response:**

```json
{
  "gpu_name": "NVIDIA RTX A5500",
  "utilization": 45.5,
  "memory_used": 7168,
  "memory_total": 24576,
  "temperature": 65.0,
  "power_usage": 120.5,
  "inference_fps": 28.3
}
```

### GPU History

```
GET /api/system/gpu/history
```

Returns GPU statistics time series for charting.

**Query Parameters:**

| Parameter | Type     | Description                           |
| --------- | -------- | ------------------------------------- |
| `since`   | datetime | Start time for history                |
| `limit`   | int      | Max samples (default: 300, max: 5000) |

## Configuration

### Get Configuration

```
GET /api/system/config
```

Returns public configuration settings.

**Response:**

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

### Update Configuration

```
PATCH /api/system/config
```

Updates configuration settings at runtime.

**Requires:** API key when `API_KEY_ENABLED=true`

**Request Body:**

```json
{
  "retention_days": 14,
  "detection_confidence_threshold": 0.6
}
```

## Statistics

### System Statistics

```
GET /api/system/stats
```

Returns aggregate system statistics.

**Response:**

```json
{
  "total_cameras": 6,
  "total_events": 1234,
  "total_detections": 5678,
  "uptime_seconds": 86400.5
}
```

### Storage Statistics

```
GET /api/system/storage
```

Returns storage usage information.

**Response:**

```json
{
  "disk_used_bytes": 107374182400,
  "disk_total_bytes": 500107862016,
  "disk_free_bytes": 392733679616,
  "disk_usage_percent": 21.47,
  "thumbnails": {
    "file_count": 1234,
    "size_bytes": 52428800
  },
  "images": {
    "file_count": 5678,
    "size_bytes": 2147483648
  },
  "clips": {
    "file_count": 100,
    "size_bytes": 1073741824
  },
  "events_count": 1234,
  "detections_count": 5678,
  "gpu_stats_count": 8640,
  "logs_count": 50000,
  "timestamp": "2025-01-15T14:30:00Z"
}
```

## Telemetry

### Pipeline Telemetry

```
GET /api/system/telemetry
```

Returns real-time pipeline metrics.

**Response:**

```json
{
  "queues": {
    "detection_queue": 5,
    "analysis_queue": 2
  },
  "latencies": {
    "watch": {
      "avg_ms": 50.5,
      "p95_ms": 120.0,
      "sample_count": 100
    },
    "detect": { ... },
    "batch": { ... },
    "analyze": { ... }
  },
  "timestamp": "2025-01-15T14:30:00Z"
}
```

### Pipeline Latency

```
GET /api/system/pipeline-latency
```

Detailed pipeline stage latencies with percentiles.

**Query Parameters:**

| Parameter        | Type | Description                         |
| ---------------- | ---- | ----------------------------------- |
| `window_minutes` | int  | Time window for stats (default: 60) |

### Pipeline Status

```
GET /api/system/pipeline
```

Combined status of all pipeline components.

## Cleanup

### Trigger Cleanup

```
POST /api/system/cleanup
```

Manually trigger data cleanup based on retention settings.

**Requires:** API key when `API_KEY_ENABLED=true`

**Query Parameters:**

| Parameter | Type    | Description                   |
| --------- | ------- | ----------------------------- |
| `dry_run` | boolean | Preview what would be deleted |

**Response:**

```json
{
  "events_deleted": 50,
  "detections_deleted": 200,
  "gpu_stats_deleted": 1000,
  "logs_deleted": 5000,
  "thumbnails_deleted": 200,
  "images_deleted": 0,
  "space_reclaimed": 104857600,
  "retention_days": 30,
  "dry_run": false,
  "timestamp": "2025-01-15T14:30:00Z"
}
```

### Cleanup Status

```
GET /api/system/cleanup/status
```

Returns automated cleanup service status.

## Severity Metadata

```
GET /api/system/severity
```

Returns severity level definitions and thresholds.

See [Risk Levels Reference](../config/risk-levels.md) for details.

## Circuit Breakers

### List Circuit Breakers

```
GET /api/system/circuit-breakers
```

Returns status of all circuit breakers protecting external services.

### Reset Circuit Breaker

```
POST /api/system/circuit-breakers/{name}/reset
```

Manually resets a circuit breaker to closed state.

**Requires:** API key when `API_KEY_ENABLED=true`

---

## Next Steps

- [Environment Variables](../config/env-reference.md) - Configuration reference
- [Troubleshooting](../troubleshooting/index.md) - Common issues
- Back to [API Overview](overview.md)
