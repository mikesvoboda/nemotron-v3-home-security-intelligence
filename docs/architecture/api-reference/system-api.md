# System API

The System API provides endpoints for health monitoring, system configuration, GPU statistics, and operational management in the NEM home security monitoring system.

**Source:** `backend/api/routes/system.py`

## Overview

The System API provides:

- Health check endpoints for Kubernetes probes
- GPU and system statistics
- Configuration management
- Circuit breaker status
- Worker monitoring

## Health Check Endpoints

### Detailed Health Check

```
GET /api/system/health
```

Get detailed system health check including database, Redis, and AI services.

**Source:** `backend/api/routes/system.py:1049-1181`

#### Response Caching

Results are cached for 5 seconds to reduce load from frequent health probes.

**Source:** `backend/api/routes/system.py:308`

#### Response

```json
{
  "status": "healthy",
  "services": {
    "database": {
      "status": "healthy",
      "message": "Database operational",
      "details": {
        "pool": {
          "size": 5,
          "overflow": 0,
          "checkedin": 4,
          "checkedout": 1,
          "total_connections": 5
        }
      }
    },
    "redis": {
      "status": "healthy",
      "message": "Redis connected",
      "details": {
        "redis_version": "7.4.0"
      }
    },
    "ai": {
      "status": "healthy",
      "message": "AI services operational",
      "details": {
        "yolo26": "healthy",
        "nemotron": "healthy"
      }
    }
  },
  "timestamp": "2026-01-23T12:00:00Z",
  "recent_events": [
    {
      "timestamp": "2026-01-23T11:55:00Z",
      "service": "redis",
      "event_type": "recovery",
      "message": "Redis connection restored"
    }
  ]
}
```

#### Health Status Values

| Status      | Description                                              |
| ----------- | -------------------------------------------------------- |
| `healthy`   | All services operational                                 |
| `degraded`  | Some services unhealthy but core functionality available |
| `unhealthy` | Critical services down                                   |

#### HTTP Status Codes

| Code | Description           |
| ---- | --------------------- |
| 200  | Healthy               |
| 503  | Degraded or unhealthy |

---

### Readiness Probe

```
GET /api/system/health/ready
```

Kubernetes-style readiness probe with detailed information.

**Source:** `backend/api/routes/system.py:1188-1328`

#### Checks Performed

1. Database connectivity (critical)
2. Redis connectivity (required for queue processing)
3. Critical pipeline workers (detection, analysis)
4. Worker supervisor health

**Source:** `backend/api/routes/system.py:564-596`

#### Response

```json
{
  "ready": true,
  "status": "ready",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "pipeline_workers": "healthy",
    "supervisor": "healthy"
  },
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
    },
    {
      "name": "batch_aggregator",
      "running": true,
      "message": null
    }
  ]
}
```

#### HTTP Status Codes

| Code | Description              |
| ---- | ------------------------ |
| 200  | Ready to receive traffic |
| 503  | Not ready                |

---

### WebSocket Health

```
GET /api/system/health/websocket
```

Check WebSocket broadcaster health.

**Source:** `backend/api/routes/system.py:1331-1394`

#### Response

```json
{
  "status": "healthy",
  "connected_clients": 5,
  "broadcaster_running": true,
  "last_broadcast": "2026-01-23T12:00:00Z"
}
```

---

### Full Health Check

```
GET /api/system/health/full
```

Comprehensive health check including all AI services and circuit breakers.

**Source:** `backend/api/schemas/health.py:316-385`

#### Response

```json
{
  "status": "healthy",
  "ready": true,
  "message": "All systems operational",
  "postgres": {
    "name": "postgres",
    "status": "healthy",
    "message": "Database operational",
    "details": null
  },
  "redis": {
    "name": "redis",
    "status": "healthy",
    "message": "Redis connected",
    "details": {
      "redis_version": "7.4.0"
    }
  },
  "ai_services": [
    {
      "name": "yolo26",
      "display_name": "YOLO26 Object Detection",
      "status": "healthy",
      "url": "http://ai-yolo26:8095",
      "response_time_ms": 45.2,
      "circuit_state": "closed",
      "error": null,
      "last_check": "2026-01-23T12:00:00Z"
    },
    {
      "name": "nemotron",
      "display_name": "Nemotron LLM",
      "status": "healthy",
      "url": "http://nemotron:8080",
      "response_time_ms": 120.5,
      "circuit_state": "closed",
      "error": null,
      "last_check": "2026-01-23T12:00:00Z"
    }
  ],
  "circuit_breakers": {
    "total": 5,
    "closed": 5,
    "open": 0,
    "half_open": 0,
    "breakers": {
      "yolo26": "closed",
      "nemotron": "closed",
      "florence": "closed",
      "clip": "closed",
      "enrichment": "closed"
    }
  },
  "workers": [
    {
      "name": "file_watcher",
      "running": true,
      "critical": true
    }
  ],
  "timestamp": "2026-01-23T12:00:00Z",
  "version": "0.1.0"
}
```

**Source:** `backend/api/schemas/health.py:316-385`

---

## Monitoring Endpoints

### Prometheus-Style Health

```
GET /api/system/monitoring/health
```

Prometheus-compatible health endpoint for monitoring integrations.

#### Response

```json
{
  "status": "up",
  "checks": {
    "database": "up",
    "redis": "up",
    "ai_services": "up"
  }
}
```

---

### Monitoring Targets

```
GET /api/system/monitoring/targets
```

Get monitoring target information for service discovery.

#### Response

```json
{
  "targets": [
    {
      "name": "backend",
      "url": "http://backend:8000",
      "health_endpoint": "/api/system/health"
    },
    {
      "name": "yolo26",
      "url": "http://ai-yolo26:8095",
      "health_endpoint": "/health"
    }
  ]
}
```

---

## GPU Statistics

### Get GPU Stats

```
GET /api/system/gpu/stats
```

Get current GPU utilization and memory statistics.

**Source:** `backend/api/routes/system.py:634-683`

#### Response

```json
{
  "recorded_at": "2026-01-23T12:00:00Z",
  "gpu_name": "NVIDIA GeForce RTX 4090",
  "utilization": 45.5,
  "memory_used": 8192,
  "memory_total": 24576,
  "temperature": 65,
  "power_usage": 250,
  "inference_fps": 30.5,
  "fan_speed": 45,
  "sm_clock": 2520,
  "memory_bandwidth_utilization": 35.2,
  "pstate": "P0",
  "throttle_reasons": [],
  "power_limit": 450,
  "sm_clock_max": 2520,
  "compute_processes_count": 3,
  "pcie_replay_counter": 0,
  "temp_slowdown_threshold": 83,
  "memory_clock": 10501,
  "memory_clock_max": 10501,
  "pcie_link_gen": 4,
  "pcie_link_width": 16,
  "pcie_tx_throughput": 1024,
  "pcie_rx_throughput": 512,
  "encoder_utilization": 0,
  "decoder_utilization": 15,
  "bar1_used": 256
}
```

#### Caching

Results are cached for 5 seconds.

**Source:** `backend/api/routes/system.py:347-356`

---

### Get GPU Stats History

```
GET /api/system/gpu/stats/history
```

Get historical GPU statistics.

#### Query Parameters

| Parameter  | Type    | Default | Description                            |
| ---------- | ------- | ------- | -------------------------------------- |
| `hours`    | integer | 24      | Number of hours to retrieve (1-168)    |
| `interval` | string  | "5m"    | Aggregation interval (1m, 5m, 15m, 1h) |

---

## Configuration

### Get Configuration

```
GET /api/system/config
```

Get current system configuration.

#### Response

```json
{
  "batch_timeout_seconds": 90,
  "batch_idle_timeout_seconds": 30,
  "retention_days": 30,
  "detection_confidence_threshold": 0.5,
  "risk_score_thresholds": {
    "low": 0,
    "medium": 30,
    "high": 60,
    "critical": 80
  }
}
```

---

### Update Configuration

```
PATCH /api/system/config
```

Update system configuration.

#### Request Body

```json
{
  "batch_timeout_seconds": 120,
  "detection_confidence_threshold": 0.6
}
```

---

## Circuit Breakers

### Get Circuit Breaker Status

```
GET /api/system/circuit-breakers
```

Get status of all circuit breakers.

#### Response

```json
{
  "breakers": [
    {
      "name": "yolo26",
      "state": "closed",
      "failure_count": 0,
      "last_failure": null,
      "last_success": "2026-01-23T12:00:00Z"
    },
    {
      "name": "nemotron",
      "state": "open",
      "failure_count": 3,
      "last_failure": "2026-01-23T11:55:00Z",
      "last_success": "2026-01-23T11:50:00Z",
      "reset_at": "2026-01-23T12:00:30Z"
    }
  ]
}
```

#### Circuit Breaker States

| State       | Description                                |
| ----------- | ------------------------------------------ |
| `closed`    | Normal operation, requests pass through    |
| `open`      | Service failing, requests fail immediately |
| `half_open` | Testing recovery, limited requests allowed |

**Source:** `backend/api/schemas/health.py:187-198`

---

### Reset Circuit Breaker

```
POST /api/system/circuit-breakers/{name}/reset
```

Manually reset a circuit breaker to closed state.

#### Path Parameters

| Parameter | Type   | Description          |
| --------- | ------ | -------------------- |
| `name`    | string | Circuit breaker name |

---

## Worker Management

### Get Worker Status

```
GET /api/system/workers
```

Get status of all background workers.

#### Response

```json
{
  "workers": [
    {
      "name": "gpu_monitor",
      "running": true,
      "message": null
    },
    {
      "name": "cleanup_service",
      "running": true,
      "message": null
    },
    {
      "name": "file_watcher",
      "running": true,
      "message": null
    },
    {
      "name": "detection_worker",
      "running": true,
      "message": null
    },
    {
      "name": "analysis_worker",
      "running": true,
      "message": null
    },
    {
      "name": "batch_aggregator",
      "running": true,
      "message": null
    }
  ]
}
```

**Source:** `backend/api/routes/system.py:445-561`

---

## Data Models

### HealthResponse

| Field           | Type     | Description                                   |
| --------------- | -------- | --------------------------------------------- |
| `status`        | string   | Overall status (healthy, degraded, unhealthy) |
| `services`      | object   | Individual service statuses                   |
| `timestamp`     | datetime | Response timestamp                            |
| `recent_events` | array    | Recent health events                          |

### ReadinessResponse

**Source:** `backend/api/schemas/health.py:86-134`

| Field    | Type    | Description              |
| -------- | ------- | ------------------------ |
| `ready`  | boolean | Overall readiness        |
| `checks` | object  | Individual check results |

### CheckResult

**Source:** `backend/api/schemas/health.py:49-83`

| Field        | Type   | Description                     |
| ------------ | ------ | ------------------------------- |
| `status`     | string | healthy, unhealthy, or degraded |
| `latency_ms` | float  | Check latency in milliseconds   |
| `error`      | string | Error message if unhealthy      |

### ServiceHealthState Enum

**Source:** `backend/api/schemas/health.py:171-184`

- `healthy` - Service is fully operational
- `unhealthy` - Service is down or critical issues
- `degraded` - Partially operational
- `unknown` - Status cannot be determined

### CircuitState Enum

**Source:** `backend/api/schemas/health.py:187-198`

- `closed` - Normal operation
- `open` - Service failing, requests blocked
- `half_open` - Testing recovery

### AIServiceHealthStatus

**Source:** `backend/api/schemas/health.py:201-234`

| Field              | Type     | Description           |
| ------------------ | -------- | --------------------- |
| `name`             | string   | Service identifier    |
| `display_name`     | string   | Human-readable name   |
| `status`           | string   | Health state          |
| `url`              | string   | Service URL           |
| `response_time_ms` | float    | Response time         |
| `circuit_state`    | string   | Circuit breaker state |
| `error`            | string   | Error message         |
| `last_check`       | datetime | Last check timestamp  |

### InfrastructureHealthStatus

**Source:** `backend/api/schemas/health.py:237-259`

| Field     | Type   | Description        |
| --------- | ------ | ------------------ |
| `name`    | string | Service name       |
| `status`  | string | Health state       |
| `message` | string | Status message     |
| `details` | object | Additional details |

### WorkerHealthStatus

**Source:** `backend/api/schemas/health.py:295-313`

| Field      | Type    | Description                |
| ---------- | ------- | -------------------------- |
| `name`     | string  | Worker name                |
| `running`  | boolean | Running status             |
| `critical` | boolean | Whether worker is critical |

---

## Circuit Breaker Implementation

The health check system uses circuit breakers to prevent cascading failures.

**Source:** `backend/api/routes/system.py:158-254`

### Configuration

| Parameter           | Default | Description                     |
| ------------------- | ------- | ------------------------------- |
| `failure_threshold` | 3       | Failures before opening circuit |
| `reset_timeout`     | 30s     | Time before retrying            |

### Behavior

1. **Closed**: Normal operation, health checks executed
2. **After N failures**: Circuit opens, health checks skipped
3. **After timeout**: Circuit becomes half-open, allows one request
4. **On success**: Circuit closes, normal operation resumes

---

## Timeouts and Limits

| Constant                          | Value | Description              |
| --------------------------------- | ----- | ------------------------ |
| `HEALTH_CHECK_TIMEOUT_SECONDS`    | 5.0   | Health check timeout     |
| `HEALTH_CACHE_TTL_SECONDS`        | 5.0   | Health cache duration    |
| `AI_HEALTH_CHECK_TIMEOUT_SECONDS` | 3.0   | AI service check timeout |
| `MAX_CONCURRENT_HEALTH_CHECKS`    | 10    | Max concurrent checks    |

**Source:** `backend/api/routes/system.py:297-298, 308, 820-824`

---

## Related Documentation

- [Health Schemas](request-response-schemas.md#health-schemas) - Schema details
- [Error Handling](error-handling.md) - Error response formats
- [Background Services](../background-services/) - Worker documentation
