# Service Dependencies Map

This document describes the service dependency hierarchy, startup order requirements, communication protocols, and health check dependencies for the Home Security Intelligence system.

## Table of Contents

1. [Service Dependency Diagram](#service-dependency-diagram)
2. [Startup Order](#startup-order)
3. [Communication Protocols](#communication-protocols)
4. [Health Check Dependencies](#health-check-dependencies)
5. [Failure Impact Analysis](#failure-impact-analysis)
6. [Recovery Procedures](#recovery-procedures)

---

## Service Dependency Diagram

### Architecture Overview

![Service Dependencies Architecture](images/architecture/service-dependencies.png)

_Complete microservices topology showing all 9 services, their connections, and the GPU hardware layer._

### Mermaid Diagram

```mermaid
graph TB
    subgraph "External"
        Cameras[Camera FTP Uploads]
        Browser[Web Browser]
    end

    subgraph "Application Layer"
        Frontend[Frontend<br/>React + Nginx<br/>:5173]
        Backend[Backend<br/>FastAPI<br/>:8000]
    end

    subgraph "Data Layer"
        Postgres[PostgreSQL<br/>:5432]
        Redis[Redis<br/>:6379]
    end

    subgraph "AI Layer"
        RTDetr[RT-DETRv2<br/>:8090]
        Nemotron[Nemotron<br/>:8091]
        Florence[Florence-2<br/>:8092]
        Clip[CLIP<br/>:8093]
        Enrichment[Enrichment<br/>:8094]
    end

    subgraph "Hardware"
        GPU[NVIDIA GPU<br/>RTX A5500]
    end

    Browser -->|HTTP/WS| Frontend
    Frontend -->|HTTP/WS| Backend
    Cameras -->|Files| Backend
    Backend -->|SQL| Postgres
    Backend -->|Redis Protocol| Redis
    Backend -->|HTTP| RTDetr
    Backend -->|HTTP| Nemotron
    Backend -->|HTTP| Florence
    Backend -->|HTTP| Clip
    Backend -->|HTTP| Enrichment
    Backend -->|pynvml| GPU
    RTDetr -->|CUDA| GPU
    Nemotron -->|CUDA| GPU
    Florence -->|CUDA| GPU
    Clip -->|CUDA| GPU
    Enrichment -->|CUDA| GPU

    style Frontend fill:#61dafb
    style Backend fill:#009485
    style Postgres fill:#336791
    style Redis fill:#dc382d
    style RTDetr fill:#76b900
    style Nemotron fill:#76b900
    style Florence fill:#76b900
    style Clip fill:#76b900
    style Enrichment fill:#76b900
    style GPU fill:#76b900
```

---

## Startup Order

Services must start in this specific order to ensure proper dependency resolution.

### Phase 1: Data Infrastructure (0-15 seconds)

**Start simultaneously:**

1. **PostgreSQL** (Priority 1)

   - Port: 5432
   - Health check: `pg_isready`
   - Startup time: ~10-15 seconds
   - Dependencies: None

2. **Redis** (Priority 1)
   - Port: 6379
   - Health check: `redis-cli ping`
   - Startup time: ~5-10 seconds
   - Dependencies: None

**Why first:** Backend and all other services require database and Redis to be available before starting.

### Phase 2: AI Services (60-180 seconds)

**Start after Phase 1 completes:**

3. **RT-DETRv2** (Priority 2)

   - Port: 8090
   - Health check: `GET /health`
   - Startup time: ~60-90 seconds (model download/load)
   - Dependencies: GPU
   - Critical: Yes

4. **Nemotron** (Priority 2)

   - Port: 8091
   - Health check: `GET /health`
   - Startup time: ~90-120 seconds (model load into VRAM)
   - Dependencies: GPU
   - Critical: Yes

5. **Florence-2** (Priority 3, Optional)

   - Port: 8092
   - Health check: `GET /health`
   - Startup time: ~60 seconds
   - Dependencies: GPU
   - Critical: No (graceful degradation)

6. **CLIP** (Priority 3, Optional)

   - Port: 8093
   - Health check: `GET /health`
   - Startup time: ~60 seconds
   - Dependencies: GPU
   - Critical: No (graceful degradation)

7. **Enrichment** (Priority 3, Optional)
   - Port: 8094
   - Health check: `GET /health`
   - Startup time: ~120-180 seconds (multiple models)
   - Dependencies: GPU
   - Critical: No (graceful degradation)

**Why second:** AI services take longest to start (model loading). Backend can start while AI services are still initializing, but detection/analysis queues will wait for AI services to be ready.

**Note:** Backend does NOT wait for AI services in `docker-compose.prod.yml` dependencies. The health monitor detects when AI services become available and auto-resumes processing.

### Phase 3: Application Layer (30-60 seconds)

**Start after Phase 1 completes (can overlap with Phase 2):**

8. **Backend** (Priority 2)
   - Port: 8000
   - Health check: `GET /api/system/health/ready`
   - Startup time: ~30-60 seconds
   - Dependencies: PostgreSQL (required), Redis (required), AI services (optional)
   - Critical: Yes

**Backend startup sequence:**

1. Load configuration from .env
2. Connect to PostgreSQL (required, startup fails if unavailable)
3. Connect to Redis (required, startup fails if unavailable)
4. Run database migrations (Alembic)
5. Initialize background services:
   - FileWatcher (monitors camera directories)
   - PipelineWorkerManager (detection/analysis queues)
   - GPUMonitor (polls GPU stats)
   - CleanupService (scheduled retention)
   - EventBroadcaster (WebSocket distribution)
   - SystemBroadcaster (status updates)
   - PerformanceCollector (metrics)
   - ServiceHealthMonitor (AI service recovery)
6. Start FastAPI server
7. Health check passes when all critical dependencies ready

### Phase 4: Frontend (10-20 seconds)

**Start after Backend is healthy:**

9. **Frontend** (Priority 3)
   - Port: 5173 (or FRONTEND_PORT)
   - Health check: `GET /` (nginx)
   - Startup time: ~10-20 seconds
   - Dependencies: Backend (required)
   - Critical: Yes (for user access)

**Why last:** Frontend requires backend API to be available for initial data load and WebSocket connection.

---

## Communication Protocols

### Frontend ↔ Backend

**Protocol:** HTTP + WebSocket

| Type      | Direction          | Port | Purpose                       |
| --------- | ------------------ | ---- | ----------------------------- |
| HTTP GET  | Frontend → Backend | 8000 | API queries (cameras, events) |
| HTTP POST | Frontend → Backend | 8000 | API mutations (update camera) |
| WebSocket | Bidirectional      | 8000 | Real-time events, GPU stats   |

**Endpoints:**

- REST API: `http://backend:8000/api/*`
- WebSocket: `ws://backend:8000/api/ws`

**In production:** Nginx proxies `/api` and `/ws` to backend, so frontend uses relative URLs.

**Health dependency:** Frontend cannot function without backend. Shows error page if backend unreachable.

### Backend ↔ PostgreSQL

**Protocol:** PostgreSQL Wire Protocol (asyncpg driver)

| Operation       | Direction       | Port | Purpose                     |
| --------------- | --------------- | ---- | --------------------------- |
| SQL Queries     | Backend → DB    | 5432 | CRUD operations             |
| Transactions    | Bidirectional   | 5432 | Atomic operations           |
| Connection Pool | Backend manages | 5432 | Async connection management |

**Connection string:**

```
postgresql+asyncpg://security:$POSTGRES_PASSWORD@postgres:5432/security
```

**Health dependency:** Backend CANNOT start without PostgreSQL. Fails fast on startup if DB unreachable.

### Backend ↔ Redis

**Protocol:** Redis Protocol (redis-py async)

| Operation | Direction        | Port | Purpose                     |
| --------- | ---------------- | ---- | --------------------------- |
| Queue Ops | Backend → Redis  | 6379 | Detection/analysis queues   |
| Pub/Sub   | Backend ↔ Redis | 6379 | Event broadcasting          |
| Cache     | Backend ↔ Redis | 6379 | File deduplication, metrics |
| Streams   | Backend → Redis  | 6379 | Dead-letter queue (DLQ)     |

**Connection string:**

```
redis://redis:6379/0
```

**Health dependency:** Backend CANNOT start without Redis. Fails fast on startup if Redis unreachable.

### Backend ↔ RT-DETRv2

**Protocol:** HTTP (FastAPI)

| Endpoint      | Method | Purpose          | Response Time |
| ------------- | ------ | ---------------- | ------------- |
| `/health`     | GET    | Health check     | < 2 sec       |
| `/detect`     | POST   | Object detection | 5-30 sec      |
| `/model-info` | GET    | Model metadata   | < 1 sec       |

**Request format:**

```json
POST /detect
{
  "image_path": "/path/to/image.jpg",
  "confidence_threshold": 0.5
}
```

**Response format:**

```json
{
  "detections": [
    {
      "label": "person",
      "confidence": 0.95,
      "bbox": [100, 200, 300, 400]
    }
  ],
  "inference_time_ms": 250
}
```

**Health dependency:** Backend gracefully degrades if RT-DETRv2 unavailable. Detection queue pauses, health monitor retries until service recovers.

**Timeout:** `RTDETR_READ_TIMEOUT` (default: 60 seconds)

### Backend ↔ Nemotron

**Protocol:** HTTP (llama.cpp server completion API)

| Endpoint      | Method | Purpose           | Response Time |
| ------------- | ------ | ----------------- | ------------- |
| `/health`     | GET    | Health check      | < 2 sec       |
| `/completion` | POST   | LLM risk analysis | 30-120 sec    |

**Request format:**

```json
POST /completion
{
  "prompt": "<analysis prompt>",
  "temperature": 0.1,
  "max_tokens": 500
}
```

**Response format:**

```json
{
  "content": "<LLM response>",
  "stop_reason": "stop",
  "tokens_predicted": 250
}
```

**Health dependency:** Backend gracefully degrades if Nemotron unavailable. Analysis queue pauses, events created without risk scores until service recovers.

**Timeout:** `NEMOTRON_READ_TIMEOUT` (default: 120 seconds)

### Backend ↔ Optional AI Services

Florence-2, CLIP, and Enrichment follow the same pattern as RT-DETRv2:

- **Protocol:** HTTP (FastAPI)
- **Health check:** `GET /health`
- **Inference endpoint:** Varies by service
- **Dependency:** Optional, graceful degradation

**If unavailable:** Backend continues operating, enrichment data omitted from events.

### Backend ↔ GPU

**Protocol:** pynvml (NVIDIA Management Library Python bindings)

| Operation        | Direction     | Purpose            |
| ---------------- | ------------- | ------------------ |
| `nvmlInit()`     | Backend → GPU | Initialize library |
| `nvmlDeviceGet*` | Backend ← GPU | Query GPU stats    |

**Data polled:**

- GPU utilization (%)
- VRAM usage (MB)
- GPU temperature (°C)
- Power consumption (W)

**Polling interval:** `GPU_POLL_INTERVAL_SECONDS` (default: 5 seconds)

**Health dependency:** Backend tolerates GPU monitoring failures (logs warning, continues operating).

---

## Health Check Dependencies

### Backend Health Check Logic

The backend `/api/system/health/ready` endpoint checks:

```python
{
  "status": "ready",  # or "degraded" or "unavailable"
  "database": "connected",
  "redis": "connected",
  "workers": {
    "file_watcher": "running",
    "pipeline_workers": "running",
    "gpu_monitor": "running",
    "cleanup_service": "running"
  },
  "services": {
    "rtdetr": "healthy",      # or "unhealthy" (non-critical)
    "nemotron": "healthy",    # or "unhealthy" (non-critical)
    "florence": "healthy",    # optional
    "clip": "healthy",        # optional
    "enrichment": "healthy"   # optional
  },
  "gpu": {
    "available": true,
    "devices": 1
  }
}
```

**Health status determination:**

| Condition          | Status      | Impact                  |
| ------------------ | ----------- | ----------------------- |
| All checks pass    | ready       | Fully operational       |
| DB or Redis down   | unavailable | Backend cannot start    |
| AI services down   | degraded    | Queue processing pauses |
| GPU not accessible | degraded    | AI services won't work  |
| Workers crashed    | degraded    | Partial functionality   |

### Docker Compose Health Check Configuration

From `docker-compose.prod.yml`:

```yaml
# PostgreSQL
healthcheck:
  test: ['CMD-SHELL', 'pg_isready -U security -d security']
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 10s

# Redis
healthcheck:
  test: ['CMD', 'redis-cli', 'ping']
  interval: 10s
  timeout: 5s
  retries: 3

# Backend
healthcheck:
  test: ['CMD', 'python', '-c', "import httpx; r = httpx.get('http://localhost:8000/api/system/health/ready'); exit(0 if r.status_code == 200 else 1)"]
  interval: 10s
  timeout: 5s
  retries: 3
  start_period: 30s
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy

# Frontend
healthcheck:
  test: ['CMD', 'wget', '--no-verbose', '--tries=1', '--spider', 'http://localhost:8080']
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
  depends_on:
    backend:
      condition: service_healthy
```

**Startup order enforced by `depends_on` with `condition: service_healthy`:**

1. PostgreSQL and Redis start first
2. Backend waits for PostgreSQL and Redis to be healthy
3. Frontend waits for Backend to be healthy

**AI services intentionally NOT in `depends_on`:** Backend uses health monitor to detect when AI services become available, allowing backend to start while AI services are still loading models.

---

## Failure Impact Analysis

### PostgreSQL Failure

**Symptoms:**

- Backend fails to start (if down during startup)
- API returns 500 errors (if fails after startup)
- Data cannot be persisted

**Impact:**

- **Severity:** Critical
- **Scope:** Complete system outage
- **User Impact:** Dashboard unusable

**Mitigation:**

- Backend fails fast on startup (no silent failures)
- Database connection pooling with retry logic
- Health check detects failure immediately

**Recovery:** See `docs/DEPLOYMENT_TROUBLESHOOTING.md` > Database Issues

### Redis Failure

**Symptoms:**

- Backend fails to start (if down during startup)
- Queue processing stops (if fails after startup)
- WebSocket events not delivered

**Impact:**

- **Severity:** Critical
- **Scope:** Pipeline processing stops, real-time updates fail
- **User Impact:** No new detections, dashboard shows stale data

**Mitigation:**

- Backend fails fast on startup
- Queue operations with backpressure and DLQ
- Health check detects failure immediately

**Recovery:** See `docs/DEPLOYMENT_TROUBLESHOOTING.md` > Redis Issues

### RT-DETRv2 Failure

**Symptoms:**

- Detection queue grows
- Health endpoint shows `rtdetr: unhealthy`
- No new detections created

**Impact:**

- **Severity:** High
- **Scope:** Object detection pipeline stops
- **User Impact:** New camera uploads not processed

**Mitigation:**

- Backend gracefully degrades (continues operating)
- Health monitor auto-retries every 30 seconds
- Queue processing resumes when service recovers
- Detection queue uses backpressure to prevent overflow

**Recovery:**

1. Health monitor detects failure
2. Queue processing pauses
3. Service restarts (manual or auto)
4. Health monitor detects recovery
5. Queue processing resumes automatically

### Nemotron Failure

**Symptoms:**

- Analysis queue grows
- Health endpoint shows `nemotron: unhealthy`
- Events created without risk scores

**Impact:**

- **Severity:** Medium
- **Scope:** Risk analysis stops, events lack scores
- **User Impact:** Events visible but not prioritized

**Mitigation:**

- Backend gracefully degrades
- Events still created (risk_score = null)
- Health monitor auto-retries
- Analysis queue uses backpressure

**Recovery:**
Same as RT-DETRv2, queue processing resumes when service recovers.

### Frontend Failure

**Symptoms:**

- Port 5173 not responding
- Browser shows connection refused

**Impact:**

- **Severity:** High
- **Scope:** User interface unavailable
- **User Impact:** Cannot access dashboard

**Mitigation:**

- Backend continues processing (independent of frontend)
- Data still persisted and available via API
- Nginx serves static files (fast restart)

**Recovery:**

```bash
docker compose -f docker-compose.prod.yml restart frontend
```

### GPU Failure

**Symptoms:**

- AI services crash or fail to start
- `nvidia-smi` shows errors
- VRAM allocation errors

**Impact:**

- **Severity:** Critical (for AI services)
- **Scope:** All AI inference stops
- **User Impact:** No detections or analysis

**Mitigation:**

- AI services restart on crash (Docker restart policy)
- Backend detects AI service failures via health monitor
- Queue processing pauses until GPU recovers

**Recovery:** See `docs/DEPLOYMENT_TROUBLESHOOTING.md` > GPU Issues

---

## Recovery Procedures

### Automatic Recovery

**ServiceHealthMonitor** (backend service) provides automatic recovery:

1. **Detection:** Polls AI service health endpoints every 30 seconds
2. **Action:** If service unhealthy, pauses queue processing
3. **Retry:** Continues polling until service recovers
4. **Resume:** Automatically resumes queue processing when healthy

**No manual intervention required** for temporary AI service failures.

### Manual Recovery

**Individual service restart:**

```bash
docker compose -f docker-compose.prod.yml restart <service-name>
```

**Complete system restart (ordered):**

```bash
# Stop all services
docker compose -f docker-compose.prod.yml down

# Start in phases
docker compose -f docker-compose.prod.yml up -d postgres redis
sleep 15
docker compose -f docker-compose.prod.yml up -d ai-detector ai-llm ai-florence ai-clip ai-enrichment
sleep 90
docker compose -f docker-compose.prod.yml up -d backend
sleep 30
docker compose -f docker-compose.prod.yml up -d frontend
```

### Dependency Chain Recovery

If multiple services fail, recover in this order:

1. **PostgreSQL** (required for all services)
2. **Redis** (required for backend)
3. **AI Services** (backend will auto-detect when ready)
4. **Backend** (required for frontend)
5. **Frontend**

**Example:** If both PostgreSQL and backend are down:

```bash
# Start PostgreSQL first
docker compose -f docker-compose.prod.yml up -d postgres

# Wait for healthy
until docker compose -f docker-compose.prod.yml exec postgres pg_isready -U security; do sleep 1; done

# Then start backend
docker compose -f docker-compose.prod.yml up -d backend
```

---

## Service Interdependencies Summary

| Service    | Hard Dependencies | Soft Dependencies | Can Start Without | Auto-Recovers  |
| ---------- | ----------------- | ----------------- | ----------------- | -------------- |
| PostgreSQL | None              | None              | All               | N/A            |
| Redis      | None              | None              | All               | N/A            |
| RT-DETRv2  | GPU               | None              | Backend, Frontend | No             |
| Nemotron   | GPU               | None              | Backend, Frontend | No             |
| Florence   | GPU               | None              | Backend, Frontend | No             |
| CLIP       | GPU               | None              | Backend, Frontend | No             |
| Enrichment | GPU               | None              | Backend, Frontend | No             |
| Backend    | PostgreSQL, Redis | AI Services, GPU  | Frontend          | AI via monitor |
| Frontend   | Backend           | None              | None              | No             |

**Hard Dependencies:** Service cannot start without these.
**Soft Dependencies:** Service degrades gracefully if unavailable.
**Can Start Without:** Other services can start even if this service is down.
**Auto-Recovers:** Service automatically resumes when dependencies recover.

---

## Monitoring Dependencies

Use these commands to check dependency health:

```bash
# Check all service health
docker compose -f docker-compose.prod.yml ps

# Check backend view of dependencies
curl http://localhost:8000/api/system/health/ready | jq .

# Check individual service health
curl http://localhost:8090/health  # RT-DETRv2
curl http://localhost:8091/health  # Nemotron

# Check database connectivity
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U security

# Check Redis connectivity
docker compose -f docker-compose.prod.yml exec redis redis-cli ping

# Check GPU availability
docker compose -f docker-compose.prod.yml exec backend nvidia-smi
```

---

## Related Documentation

- `docs/DEPLOYMENT_RUNBOOK.md` - Service startup procedures
- `docs/DEPLOYMENT_TROUBLESHOOTING.md` - Failure diagnosis and recovery
- `docs/DOCKER_DEPLOYMENT.md` - Container architecture
- `docs/RUNTIME_CONFIG.md` - Service configuration reference
- `docs/operator/deployment-modes.md` - AI service connectivity modes
