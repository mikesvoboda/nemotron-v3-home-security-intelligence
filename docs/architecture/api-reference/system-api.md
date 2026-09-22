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

**Source:** `backend/api/routes/system.py:1260-1431`

#### Response Caching

Results are cached for `HEALTH_CACHE_TTL_SECONDS` = 15 seconds, matching the
Prometheus scrape interval to avoid redundant checks.

**Source:** `backend/api/routes/system.py:341`

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

**Source:** `backend/api/routes/system.py:1465-1594`

#### Checks Performed

1. Database connectivity (critical)
2. Redis connectivity (required for queue processing)
3. Critical pipeline workers (detection, analysis) — required when
   `READINESS_REQUIRE_PIPELINE_WORKERS=true` (default)
4. Worker supervisor health (`supervisor_healthy`)

Database, Redis, and AI checks run in parallel (NEM-3892); responses are
cached for `HEALTH_CACHE_TTL_SECONDS`.

**Source:** `backend/api/routes/system.py:505, 671, 719`

#### Response

```json
{
  "ready": true,
  "status": "ready",
  "services": {
    "database": { "status": "healthy", "message": "Database operational" },
    "redis": { "status": "healthy", "message": "Redis connected" },
    "ai": { "status": "healthy", "message": "AI services operational" }
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
  ],
  "supervisor_healthy": true,
  "timestamp": "2026-01-23T12:00:00Z"
}
```

#### HTTP Status Codes

| Code | Description              |
| ---- | ------------------------ |
| 200  | Ready to receive traffic |
| 503  | Not ready or degraded    |

---

### WebSocket Health

```
GET /api/system/health/websocket
```

Check WebSocket broadcaster health.

**Source:** `backend/api/routes/system.py:1596-1675`

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

**Source:** `backend/api/schemas/health.py:316-385` (schema),
`backend/api/routes/system.py:5538-5624` (handler)

#### Response

At runtime the AI service entries report the gateway-consolidated URLs:
`yolo26` (and the other detection/enrichment models) resolve through
`http://ai-gateway:8090/yolo26` while `nemotron` points at
`http://ai-llm:8091`.

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
      "url": "http://ai-gateway:8090/yolo26",
      "response_time_ms": 45.2,
      "circuit_state": "closed",
      "error": null,
      "last_check": "2026-01-23T12:00:00Z"
    },
    {
      "name": "nemotron",
      "display_name": "Nemotron LLM",
      "status": "healthy",
      "url": "http://ai-llm:8091",
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

### Monitoring Stack Health

```
GET /api/system/monitoring/health
```

Health of the monitoring infrastructure itself: Prometheus reachability,
per-job scrape target summary, exporter status
(`redis-exporter:9121`, `json-exporter:7979`, `blackbox-exporter:9115` —
`KNOWN_EXPORTERS`, `backend/api/routes/system.py:1670-1674`), metrics
collection state, and an `issues` list.

**Source:** `backend/api/routes/system.py:1918-2016`, schema
`backend/api/schemas/system.py:2804` (`MonitoringHealthResponse`)

---

### Monitoring Targets

```
GET /api/system/monitoring/targets
```

Proxies Prometheus' `/api/v1/targets` and returns every scrape target with
`job`, `instance`, `health` (up/down), labels, `last_scrape`, `last_error`,
and `scrape_duration_seconds`, plus `total`/`up`/`down` counts and the sorted
`jobs` list. Returns 503 if Prometheus is unreachable.

**Source:** `backend/api/routes/system.py:2018-2106`, schema
`backend/api/schemas/system.py:2890` (`MonitoringTargetsResponse`)

---

## GPU Statistics

### Get GPU Stats

```
GET /api/system/gpu
```

Get current GPU utilization and memory statistics.

**Source:** `backend/api/routes/system.py:2253-2376`

#### Response

`GPUStatsResponse` (`backend/api/schemas/system.py:203-374`) — all fields are
nullable (null when telemetry is unavailable). `pstate` and `throttle_reasons`
are raw NVML integers, not strings or lists.

```json
{
  "gpu_name": "NVIDIA RTX A5500",
  "utilization": 75.5,
  "memory_used": 12000,
  "memory_total": 24000,
  "temperature": 65.0,
  "power_usage": 150.0,
  "inference_fps": 30.5,
  "fan_speed": 45,
  "sm_clock": 1800,
  "memory_bandwidth_utilization": 35.2,
  "pstate": 0,
  "throttle_reasons": 0,
  "power_limit": 230.0,
  "sm_clock_max": 1980,
  "compute_processes_count": 2,
  "pcie_replay_counter": 0,
  "temp_slowdown_threshold": 83.0,
  "memory_clock": 8001,
  "memory_clock_max": 8501,
  "pcie_link_gen": 4,
  "pcie_link_width": 16,
  "pcie_tx_throughput": 120000,
  "pcie_rx_throughput": 95000,
  "encoder_utilization": 0,
  "decoder_utilization": 0,
  "bar1_used": 256
}
```

#### Caching

Results are cached in two tiers: an in-memory L1 keyed on
`HEALTH_CACHE_TTL_SECONDS` (15s) and a Redis L2 (`CacheService` SHORT_TTL,
60s) that also feeds Prometheus cache hit/miss metrics.

**Source:** `backend/api/routes/system.py:381-431` (`GPUStatsCacheEntry`),
`2276-2291`

---

### Get GPU Stats History

```
GET /api/system/gpu/history
```

Get recent GPU stats samples as a time-series, in the standard pagination
envelope (NEM-2178): `items` (chronological `GPUStatsSample` records) plus
`pagination`.

**Source:** `backend/api/routes/system.py:2378-2459`

#### Query Parameters

| Parameter | Type         | Default | Description                            |
| --------- | ------------ | ------- | -------------------------------------- |
| `since`   | ISO datetime | none    | Lower bound for `recorded_at`          |
| `limit`   | integer      | 300     | Max samples to return (clamped 1-5000) |

---

## Configuration

### Get Configuration (deprecated)

```
GET /api/system/config
```

Get public (non-secret) configuration. Deprecated: the response carries
`Deprecation`, `Sunset: 2026-07-01`, and a `Link` header pointing at
`/api/v1/settings` as the successor.

**Source:** `backend/api/routes/system.py:2461-2566`, schema
`ConfigResponse` (`backend/api/schemas/system.py:461-539`)

#### Response

```json
{
  "app_name": "Home Security Intelligence",
  "version": "0.1.0",
  "retention_days": 30,
  "log_retention_days": 30,
  "batch_window_seconds": 90,
  "batch_idle_timeout_seconds": 30,
  "detection_confidence_threshold": 0.5,
  "fast_path_confidence_threshold": 0.9,
  "grafana_url": "http://localhost:3002",
  "debug": false
}
```

---

### Update Configuration

```
PATCH /api/system/config
```

Update system configuration (requires `verify_api_key`). Accepts a subset of
processing-related settings (see `ConfigUpdateRequest`,
`backend/api/schemas/system.py:541`); only the fields you send are changed.

**Source:** `backend/api/routes/system.py:2568-2706`. Updated values are
merged into `data/runtime.env` (`_write_runtime_env`,
`backend/api/routes/system.py:2534`) so they survive restarts.

#### Request Body

```json
{
  "batch_window_seconds": 120,
  "detection_confidence_threshold": 0.6
}
```

A separate `PATCH /api/system/anomaly-config` handler
(`backend/api/routes/system.py:2740-2835`) updates anomaly detection
thresholds (`threshold_stdev`, `min_samples`).

---

## Circuit Breakers

### Get Circuit Breaker Status

```
GET /api/system/circuit-breakers
```

Get status of all circuit breakers.

**Source:** `backend/api/routes/system.py:3795-3850`, schema
`CircuitBreakersResponse` (`backend/api/schemas/system.py:1786-1810`)

#### Response

`circuit_breakers` is a map keyed by breaker name:

```json
{
  "circuit_breakers": {
    "yolo26": {
      "name": "yolo26",
      "state": "closed",
      "failure_count": 0,
      "success_count": 1240,
      "total_calls": 1240,
      "rejected_calls": 0,
      "last_failure_time": null,
      "opened_at": null,
      "config": { "failure_threshold": 5, "recovery_timeout": 30.0 }
    },
    "nemotron": {
      "name": "nemotron",
      "state": "open",
      "failure_count": 3,
      "success_count": 410,
      "total_calls": 413,
      "rejected_calls": 12,
      "last_failure_time": 1769169300.0,
      "opened_at": 1769169300.0,
      "config": { "failure_threshold": 5, "recovery_timeout": 30.0 }
    }
  },
  "total_count": 2,
  "open_count": 1,
  "timestamp": "2026-01-23T12:00:00Z"
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

Manually reset a circuit breaker to closed state (requires `verify_api_key`).

**Source:** `backend/api/routes/system.py:3852-3935`

#### Path Parameters

| Parameter | Type   | Description          |
| --------- | ------ | -------------------- |
| `name`    | string | Circuit breaker name |

---

## Worker Management

### Get Supervisor / Worker Status

```
GET /api/system/supervisor
```

Status of the Worker Supervisor and every supervised pipeline worker. The
supervisor watches worker tasks and restarts crashed ones with exponential
backoff. `GET /api/system/supervisor/status` returns the same shape, and
`GET /api/system/supervisor/restart-history` lists past restarts
(`RestartHistoryResponse`).

**Source:** `backend/api/routes/system.py:4308-4358` (supervisor),
`4420-4464` (status), `4621-4773` (restart-history)

#### Response

```json
{
  "running": true,
  "worker_count": 3,
  "workers": [
    {
      "name": "detection_worker",
      "status": "running",
      "restart_count": 0,
      "max_restarts": 5,
      "last_started_at": "2026-01-23T09:00:00Z",
      "last_crashed_at": null,
      "error": null
    }
  ],
  "timestamp": "2026-01-23T12:00:00Z"
}
```

Worker `status` values: `running`, `stopped`, `crashed`, `restarting`,
`failed` (exceeded restart limit). Use `POST /api/system/supervisor/reset/{worker_name}`
(`system.py:4360-4418`) to clear a failed worker's backoff state.

---

## Data Models

### HealthResponse

**Source:** `backend/api/schemas/system.py:130`

| Field           | Type     | Description                                   |
| --------------- | -------- | --------------------------------------------- |
| `status`        | string   | Overall status (healthy, degraded, unhealthy) |
| `services`      | object   | Individual service statuses                   |
| `timestamp`     | datetime | Response timestamp                            |
| `recent_events` | array    | Recent health events                          |

### ReadinessResponse

**Source:** `backend/api/schemas/system.py:641-700` (the response model used
by `/api/system/health/ready`)

| Field                | Type     | Description                          |
| -------------------- | -------- | ------------------------------------ |
| `ready`              | boolean  | Overall readiness                    |
| `status`             | string   | ready / degraded / not_ready         |
| `services`           | object   | database, redis and ai check results |
| `workers`            | array    | Worker statuses                      |
| `supervisor_healthy` | boolean  | Worker supervisor health             |
| `timestamp`          | datetime | Response timestamp                   |

A second, simpler `ReadinessResponse` (`ready` + `checks` map of
`CheckResult`) lives at `backend/api/schemas/health.py:86-134` and backs the
root-level `/ready` probe.

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

The health check system uses its own lightweight circuit breaker to stop
probing services that are repeatedly failing (distinct from the AI-call
circuit breakers surfaced by `GET /api/system/circuit-breakers`).

**Source:** `backend/api/routes/system.py:169-265`

### Configuration

| Parameter           | Default | Description                     |
| ------------------- | ------- | ------------------------------- |
| `failure_threshold` | 3       | Failures before opening circuit |
| `reset_timeout`     | 30s     | Time before retrying            |

### Behavior

1. **Closed**: Normal operation, health checks executed
2. **After N failures**: Circuit opens, health checks skipped (cached error returned)
3. **After timeout**: Circuit resets to closed and lets the next check through (half-open state is implicit)
4. **On success**: Failure count resets, normal operation resumes

---

## Timeouts and Limits

| Constant                          | Value | Description                                                |
| --------------------------------- | ----- | ---------------------------------------------------------- |
| `HEALTH_CHECK_TIMEOUT_SECONDS`    | 5.0   | Health check timeout                                       |
| `HEALTH_CACHE_TTL_SECONDS`        | 15.0  | Health cache duration (matches Prometheus scrape interval) |
| `AI_HEALTH_CHECK_TIMEOUT_SECONDS` | 3.0   | AI service check timeout                                   |
| `MAX_CONCURRENT_HEALTH_CHECKS`    | 10    | Max concurrent checks                                      |

**Source:** `backend/api/routes/system.py:332, 341, 940, 944`

---

## Related Documentation

- [Health Schemas](request-response-schemas.md#health-schemas) - Schema details
- [Error Handling](error-handling.md) - Error response formats
- [Background Services](../background-services/README.md) - Worker documentation
