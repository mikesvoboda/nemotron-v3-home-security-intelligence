# Health Check Strategy

This document defines the health check strategy for the Nemotron v3 Home Security Intelligence system. It covers Service Level Objectives (SLOs), health check endpoints, circuit breaker integration, and recovery procedures.

**Implements:** NEM-1582

## Table of Contents

- [Overview](#overview)
- [Health Check Architecture](#health-check-architecture)
- [Service Level Objectives (SLOs)](#service-level-objectives-slos)
- [Health Check Endpoints](#health-check-endpoints)
- [Service Dependencies](#service-dependencies)
- [Circuit Breaker Integration](#circuit-breaker-integration)
- [Recovery Procedures](#recovery-procedures)
- [Monitoring and Alerting](#monitoring-and-alerting)

## Overview

The system implements a comprehensive health check strategy that enables:

1. **Kubernetes/Docker orchestration** - Liveness and readiness probes for container health
2. **Load balancer routing** - Traffic routing based on service health
3. **Graceful degradation** - Continued operation with reduced functionality when non-critical services fail
4. **Circuit breaker protection** - Prevention of cascade failures across services
5. **Real-time visibility** - WebSocket broadcasting of health state changes

## Health Check Architecture

```
                                    +-------------------+
                                    |   Load Balancer   |
                                    |  (Health Checks)  |
                                    +--------+----------+
                                             |
                                             v
+------------------+              +----------+----------+              +------------------+
|   PostgreSQL     |<-------------|      Backend        |------------->|      Redis       |
|  (Critical)      |              |   /health/full      |              |   (Critical)     |
+------------------+              +----------+----------+              +------------------+
                                             |
                    +------------------------+------------------------+
                    |                        |                        |
                    v                        v                        v
         +------------------+     +------------------+     +------------------+
         |   RT-DETR        |     |    Nemotron      |     |    Florence      |
         |   (Critical)     |     |   (Critical)     |     |  (Non-Critical)  |
         +------------------+     +------------------+     +------------------+
                    |                        |                        |
                    v                        v                        v
         +------------------+     +------------------+
         |      CLIP        |     |   Enrichment     |
         |  (Non-Critical)  |     |  (Non-Critical)  |
         +------------------+     +------------------+
```

## Service Level Objectives (SLOs)

### Critical Services

Critical services must be healthy for the system to be considered ready for traffic.

| Service    | Target Availability | Max Response Time | Recovery Time Objective |
| ---------- | ------------------- | ----------------- | ----------------------- |
| PostgreSQL | 99.9%               | 100ms             | 60s                     |
| Redis      | 99.9%               | 50ms              | 30s                     |
| RT-DETR    | 99.5%               | 5000ms            | 60s                     |
| Nemotron   | 99.5%               | 10000ms           | 120s                    |

### Non-Critical Services

Non-critical services can fail without blocking system readiness. The system operates in degraded mode.

| Service    | Target Availability | Max Response Time | Recovery Time Objective |
| ---------- | ------------------- | ----------------- | ----------------------- |
| Florence   | 95.0%               | 5000ms            | 120s                    |
| CLIP       | 95.0%               | 3000ms            | 120s                    |
| Enrichment | 95.0%               | 5000ms            | 180s                    |

### Background Workers

| Worker          | Critical | Expected Status | Recovery Action |
| --------------- | -------- | --------------- | --------------- |
| file_watcher    | Yes      | Running         | Auto-restart    |
| cleanup_service | No       | Running         | Manual restart  |

## Health Check Endpoints

### Liveness Probe

**Endpoint:** `GET /health`

Simple liveness check that returns "alive" if the process is running.

```json
{
  "status": "alive"
}
```

**Use Cases:**

- Kubernetes liveness probe
- Docker HEALTHCHECK
- Process monitoring

### Readiness Probe

**Endpoint:** `GET /api/system/health/ready`

Readiness check for infrastructure services (database, Redis).

```json
{
  "ready": true,
  "checks": {
    "database": {
      "status": "healthy",
      "latency_ms": 2.5
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 1.2
    }
  }
}
```

**HTTP Status Codes:**

- `200 OK` - System is ready
- `503 Service Unavailable` - System is not ready

### Full Health Check

**Endpoint:** `GET /api/system/health/full`

Comprehensive health check including all services and circuit breakers.

```json
{
  "status": "healthy",
  "ready": true,
  "message": "All systems operational",
  "postgres": {
    "name": "postgres",
    "status": "healthy",
    "message": "Database operational"
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
      "name": "rtdetr",
      "display_name": "RT-DETRv2 Object Detection",
      "status": "healthy",
      "url": "http://ai-detector:8090",
      "response_time_ms": 45.2,
      "circuit_state": "closed",
      "last_check": "2026-01-08T10:30:00Z"
    }
  ],
  "circuit_breakers": {
    "total": 5,
    "open": 0,
    "half_open": 0,
    "closed": 5,
    "breakers": {
      "rtdetr": "closed",
      "nemotron": "closed"
    }
  },
  "workers": [
    {
      "name": "file_watcher",
      "running": true,
      "critical": true
    }
  ],
  "timestamp": "2026-01-08T10:30:00Z",
  "version": "0.1.0"
}
```

**HTTP Status Codes:**

- `200 OK` - System is healthy or degraded
- `503 Service Unavailable` - Critical services are unhealthy

### Status Values

| Status      | Description                   | HTTP Code |
| ----------- | ----------------------------- | --------- |
| `healthy`   | All services operational      | 200       |
| `degraded`  | Non-critical services failing | 200       |
| `unhealthy` | Critical services failing     | 503       |

## Service Dependencies

### Startup Order

The system uses Docker Compose health-based `depends_on` for proper startup ordering:

```yaml
backend:
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
    ai-detector:
      condition: service_healthy
    ai-llm:
      condition: service_healthy
```

### Expected Startup Times

| Service    | Expected Startup Time | Notes                    |
| ---------- | --------------------- | ------------------------ |
| PostgreSQL | ~10s                  | Database initialization  |
| Redis      | ~5s                   | Memory allocation        |
| RT-DETR    | ~60s                  | GPU model loading        |
| Nemotron   | ~120s                 | Large LLM loading        |
| Florence   | ~60s                  | Vision model loading     |
| CLIP       | ~60s                  | Embedding model loading  |
| Enrichment | ~180s                 | Multiple models loading  |
| Backend    | ~30s                  | After dependencies ready |
| Frontend   | ~40s                  | After backend ready      |

### Grace Period Configuration

Health check start periods allow for model loading:

```yaml
healthcheck:
  test: ['CMD', 'curl', '-f', 'http://localhost:8090/health']
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 60s # Wait for model loading
```

## Circuit Breaker Integration

### Circuit Breaker States

| State       | Description      | Behavior                  |
| ----------- | ---------------- | ------------------------- |
| `closed`    | Normal operation | Requests pass through     |
| `open`      | Service failing  | Requests fail immediately |
| `half_open` | Testing recovery | Limited requests allowed  |

### Configuration

Default circuit breaker configuration:

```python
CircuitBreakerConfig(
    failure_threshold=5,      # Failures before opening
    recovery_timeout=30.0,    # Seconds before half-open
    half_open_max_calls=3,    # Test calls in half-open
    success_threshold=2,      # Successes to close
)
```

### WebSocket Broadcasting

Circuit breaker state changes are broadcast via WebSocket:

```json
{
  "type": "circuit_breaker_update",
  "data": {
    "timestamp": "2026-01-08T10:30:00Z",
    "summary": {
      "total": 5,
      "open": 1,
      "half_open": 0,
      "closed": 4
    },
    "breakers": {
      "rtdetr": "open",
      "nemotron": "closed"
    }
  }
}
```

### Frontend Integration

Use the `useFullHealthQuery` hook to monitor health and circuit breaker states:

```typescript
const { aiServices, circuitBreakers, isReady, statusMessage } = useFullHealthQuery({
  refetchInterval: 30000, // Poll every 30 seconds
});

// Display degradation warning
if (circuitBreakers?.open > 0) {
  showWarning(`${circuitBreakers.open} services are unavailable`);
}
```

## Recovery Procedures

### PostgreSQL Recovery

**Symptoms:**

- `/health/full` shows postgres status as `unhealthy`
- Database connection errors in logs

**Recovery Steps:**

1. Check PostgreSQL logs: `docker logs postgres`
2. Verify disk space: `df -h`
3. Check connection limits: `SELECT count(*) FROM pg_stat_activity`
4. Restart if needed: `docker restart postgres`
5. Monitor `/health/ready` until healthy

### Redis Recovery

**Symptoms:**

- `/health/full` shows redis status as `unhealthy`
- Cache connection errors in logs

**Recovery Steps:**

1. Check Redis logs: `docker logs redis`
2. Verify memory usage: `redis-cli INFO memory`
3. Check for memory pressure: `free -m`
4. Restart if needed: `docker restart redis`
5. Monitor `/health/ready` until healthy

### AI Service Recovery

**Symptoms:**

- Circuit breaker in `open` state
- AI service health check failing
- GPU memory errors in logs

**Recovery Steps:**

1. Check service logs: `docker logs ai-detector`
2. Verify GPU availability: `nvidia-smi`
3. Check for OOM errors in dmesg
4. Restart service: `docker restart ai-detector`
5. Wait for `start_period` (60-180s depending on service)
6. Monitor circuit breaker state via `/health/full`

### Complete System Recovery

For full system issues:

```bash
# Stop all services
docker compose -f docker-compose.prod.yml down

# Clear any stuck state
docker system prune -f

# Start services in order
docker compose -f docker-compose.prod.yml up -d postgres redis
sleep 15

docker compose -f docker-compose.prod.yml up -d ai-detector ai-llm
sleep 120

docker compose -f docker-compose.prod.yml up -d backend frontend
```

## Monitoring and Alerting

### Prometheus Metrics

The system exposes Prometheus metrics for monitoring:

```
# Circuit breaker state (0=closed, 1=open, 2=half_open)
circuit_breaker_state{service="rtdetr"} 0

# Health check latency
health_check_latency_seconds{service="postgres"} 0.002

# Service availability
service_available{service="rtdetr"} 1
```

### Alerting Rules

Example Prometheus alerting rules:

```yaml
groups:
  - name: health_alerts
    rules:
      - alert: CriticalServiceUnhealthy
        expr: service_available{critical="true"} == 0
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: 'Critical service {{ $labels.service }} is unhealthy'

      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state > 0
        for: 60s
        labels:
          severity: warning
        annotations:
          summary: 'Circuit breaker {{ $labels.service }} is not closed'
```

### Grafana Dashboard

The system provides a Grafana dashboard at `http://localhost:3002` with:

- Service health overview
- Circuit breaker states
- Health check latency trends
- Recovery event timeline

## Best Practices

1. **Check `/health/full` before deployments** - Ensure all services are healthy
2. **Monitor circuit breaker states** - Open circuits indicate persistent issues
3. **Set appropriate timeouts** - Avoid blocking on slow services
4. **Use graceful degradation** - Design features to work without non-critical services
5. **Log health check failures** - Enable debugging of transient issues
6. **Implement retry with backoff** - Avoid thundering herd on recovery
