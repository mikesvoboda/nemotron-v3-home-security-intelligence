# Reference Hub

> Authoritative reference documentation for the Home Security Intelligence system. Lookup-style information for APIs, configuration, and troubleshooting.

**Target Audiences:** Developers, Operators, Support, All Users

---

## Quick Navigation

| Section                                     | What You'll Find                           |
| ------------------------------------------- | ------------------------------------------ |
| [Environment Variables](#environment)       | All configuration options with defaults    |
| [Service Ports](#service-ports)             | Port assignments for all services          |
| [Glossary](#glossary)                       | Definitions of key terms                   |
| [Troubleshooting](troubleshooting/index.md) | Symptom-based problem solving              |
| [API Reference](../developer/api/README.md) | REST and WebSocket API documentation       |
| [Risk Levels](config/risk-levels.md)        | Risk score ranges and severity definitions |

---

## Service Ports

| Service        | Port | Protocol | Description                                                        |
| -------------- | ---- | -------- | ------------------------------------------------------------------ |
| Frontend HTTP  | 8080 | HTTP     | nginx in the `frontend` container, host port `FRONTEND_HTTP_PORT`  |
| Frontend HTTPS | 8444 | HTTPS    | nginx in the `frontend` container, host port `FRONTEND_HTTPS_PORT` |
| Backend API    | 8000 | HTTP/WS  | FastAPI REST + WebSocket (`API_PORT`)                              |
| `ai-gateway`   | 8090 | HTTP     | Triton gateway: `/yolo26` detection + `/enrich-lt` readiness       |
| `ai-vlm`       | 8098 | HTTP     | llama.cpp reasoning serve, in the default compose set              |
| PostgreSQL     | 5432 | TCP      | Database (`POSTGRES_PORT`)                                         |
| Redis          | 6379 | TCP      | Cache, queues, pub/sub (`REDIS_PORT`)                              |
| Grafana        | 3002 | HTTP     | Dashboards at the `/grafana/` sub-path (`GRAFANA_PORT`)            |
| Prometheus     | 9090 | HTTP     | Metrics (`PROMETHEUS_PORT`)                                        |
| Tempo          | 3200 | HTTP     | Distributed tracing query API (`TEMPO_PORT`; OTLP gRPC on 4317)    |

> **Frontend Port Details:**
>
> - **Production containers:** nginx serves the built React app on container ports 8080 (HTTP) and 8443 (HTTPS), mapped to host ports `FRONTEND_HTTP_PORT` (default 8080) and `FRONTEND_HTTPS_PORT` (default 8444) in `docker-compose.prod.yml`
> - **Local development:** `npm run dev` in `frontend/` runs the Vite dev server on **https://localhost:8444** (set in `frontend/vite.config.ts`); `FRONTEND_PORT=5173` is left over from the Vite dev default and is not referenced by `docker-compose.prod.yml`
> - **SSL:** Enabled by default in production with auto-generated self-signed certificates. See [SSL/HTTPS Configuration](../developer/ssl-https.md)
> - Compose maps AI, database and monitoring ports to `127.0.0.1` only — they are reachable from the host, not from your LAN.

---

## Environment Variables {#environment}

Complete reference: [Environment Variable Reference](config/env-reference.md)

### Quick Reference - Essential Variables

| Variable       | Required | Default                    | Description                  |
| -------------- | -------- | -------------------------- | ---------------------------- |
| `DATABASE_URL` | **Yes**  | -                          | PostgreSQL connection URL    |
| `REDIS_URL`    | No       | `redis://localhost:6379/0` | Redis connection URL         |
| `YOLO26_URL`   | No       | see note below             | YOLO26 service URL           |
| `AI_VLM_URL`   | No       | `http://localhost:8098`    | `ai-vlm` reasoning serve URL |

> `YOLO26_URL` has two sources of truth: the backend default (`backend/core/config.py`) is `http://ai-gateway:8090/yolo26` for containerized deployments, while `.env.example` ships `http://localhost:8090/yolo26` for host-run development. Set it explicitly to match where your gateway runs.

### Database Configuration

```bash
# Format
DATABASE_URL=postgresql+asyncpg://user:password@host:port/database  # pragma: allowlist secret

# Local development
DATABASE_URL=postgresql+asyncpg://security:password@localhost:5432/security  # pragma: allowlist secret

# Docker container (use service name)
DATABASE_URL=postgresql+asyncpg://security:password@postgres:5432/security  # pragma: allowlist secret
```

> **Important:** There is no default `DATABASE_URL`. Run `python setup.py` to generate a `.env` file with secure credentials.

### Redis Configuration

```bash
# Format
REDIS_URL=redis://[password@]host:port[/database]

# Local development
REDIS_URL=redis://localhost:6379/0

# Docker container
REDIS_URL=redis://redis:6379/0
```

### AI Service URLs

Detection goes through the AI **gateway** (Triton); reasoning is a direct dial to `ai-vlm`.

| Variable         | Default (`.env.example`)       | Compose value                   | Description                                                           |
| ---------------- | ------------------------------ | ------------------------------- | --------------------------------------------------------------------- |
| `YOLO26_URL`     | `http://localhost:8090/yolo26` | `http://ai-gateway:8090/yolo26` | Object detection                                                      |
| `AI_VLM_URL`     | `http://localhost:8098`        | `http://ai-vlm:8098`            | llama.cpp reasoning serve                                             |
| `AI_GATEWAY_URL` | `http://ai-gateway:8090`       | `http://ai-gateway:8090`        | Gateway base for `{AI_GATEWAY_URL}/yolo26` when `USE_AI_GATEWAY=true` |

With `USE_AI_GATEWAY=true` (what compose sets) the detector dials `{AI_GATEWAY_URL}/yolo26`; with it `false` the backend's own default, `http://ai-gateway:8090/yolo26`, is the dial.

> **Warning:** Use HTTPS in production to prevent MITM attacks.

### AI Service Timeouts

| Variable              | Default | Range  | Description                                              |
| --------------------- | ------- | ------ | -------------------------------------------------------- |
| `AI_CONNECT_TIMEOUT`  | `10.0`  | 1-60s  | Connection timeout                                       |
| `AI_HEALTH_TIMEOUT`   | `5.0`   | 1-30s  | Health check timeout                                     |
| `YOLO26_READ_TIMEOUT` | `30.0`  | 5-120s | Detection response timeout                               |
| `AI_VLM_READ_TIMEOUT` | `25.0`  | 5-300s | One verdict attempt; its single retry shares this budget |

### Batch Processing

| Variable                     | Default | Description                             |
| ---------------------------- | ------- | --------------------------------------- |
| `BATCH_WINDOW_SECONDS`       | `90`    | Max time window for grouping detections |
| `BATCH_IDLE_TIMEOUT_SECONDS` | `30`    | Close batch after inactivity            |

### Retention

| Variable             | Default | Description                        |
| -------------------- | ------- | ---------------------------------- |
| `RETENTION_DAYS`     | `30`    | Days to keep events and detections |
| `LOG_RETENTION_DAYS` | `7`     | Days to keep log entries           |

### Camera Integration

| Variable           | Default          | Description                       |
| ------------------ | ---------------- | --------------------------------- |
| `FOSCAM_BASE_PATH` | `/export/foscam` | Base directory for camera uploads |

Camera images are expected at: `{FOSCAM_BASE_PATH}/{camera_name}/`

### Frontend

| Variable              | Default                 | Description                            |
| --------------------- | ----------------------- | -------------------------------------- |
| `VITE_API_BASE_URL`   | `http://localhost:8000` | Backend API URL                        |
| `VITE_WS_BASE_URL`    | `ws://localhost:8000`   | WebSocket URL                          |
| `FRONTEND_HTTP_PORT`  | `8080`                  | Host port for frontend container HTTP  |
| `FRONTEND_HTTPS_PORT` | `8444`                  | Host port for frontend container HTTPS |

For complete environment variable documentation, see [Environment Variable Reference](config/env-reference.md).

---

## AI Service Deployment Modes

### Development Mode (Host-run AI)

AI services run directly on the host while the backend runs in a container:

```bash
# macOS with Docker Desktop (default)
YOLO26_URL=http://host.docker.internal:8090/yolo26
AI_VLM_URL=http://host.docker.internal:8098

# macOS with Podman
export AI_HOST=host.containers.internal
podman-compose up -d

# Linux
# Use host IP or add --add-host=host.docker.internal:host-gateway
```

Only the detector has a host-run server to point at: `./ai/start_detector.sh`
(`ai/yolo26/model.py`). It binds :8090, the same port `ai-gateway` publishes, so run
it with the gateway down or set `YOLO26_PORT`.

### Production Mode (Fully Containerized)

Both AI services run in containers — the Triton gateway (`ai-gateway`) and the
reasoning serve (`ai-vlm`, in the default compose set — a plain `up -d` starts it):

```bash
# Set by docker-compose.prod.yml for the backend
YOLO26_URL=http://ai-gateway:8090/yolo26
USE_AI_GATEWAY=true
AI_GATEWAY_URL=http://ai-gateway:8090
AI_VLM_URL=http://ai-vlm:8098
```

### Quick Reference: AI_HOST by Platform

| Platform | Runtime | Development (host AI)            | Production (container AI) |
| -------- | ------- | -------------------------------- | ------------------------- |
| macOS    | Docker  | `host.docker.internal` (default) | N/A (use Linux for GPU)   |
| macOS    | Podman  | `host.containers.internal`       | N/A (use Linux for GPU)   |
| Linux    | Docker  | Host IP or `host-gateway`        | `ai-gateway`, `ai-vlm`    |
| Linux    | Podman  | Host IP or `host-gateway`        | `ai-gateway`, `ai-vlm`    |
| Windows  | Docker  | `host.docker.internal`           | N/A (use Linux for GPU)   |

---

## Glossary

Key terms used throughout the documentation. Full glossary: [Glossary](glossary.md)

### Core Concepts

| Term           | Definition                                                                                                                      |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Detection**  | A single object instance identified by YOLO26 in an image. Contains object type, confidence score, bounding box, and timestamp. |
| **Event**      | A security incident containing one or more detections, scored by the `ai-vlm` reasoning serve.                                  |
| **Batch**      | A collection of detections from a single camera grouped within a time window for analysis.                                      |
| **Risk Score** | A numeric value from 0-100 indicating the threat level of an event; `null` means the scorer failed and the event needs review.  |
| **Risk Level** | Categorical classification: Low (0-29), Medium (30-59), High (60-84), Critical (85-100).                                        |

### AI Components

| Term                  | Definition                                                                                                                       |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| **YOLO26**            | Real-time object detection model using transformer architecture, served by Triton inside `ai-gateway`.                           |
| **`ai-vlm`**          | The llama.cpp serve that turns a batch's stills and lookup text into a risk verdict.                                             |
| **Specialist lookup** | An in-process face, license-plate or person-re-ID match against your own registrations; `unavailable` is a class, never a score. |
| **Inference**         | The process of running an AI model on input data to produce predictions.                                                         |

### System Components

| Term                  | Definition                                                                                     |
| --------------------- | ---------------------------------------------------------------------------------------------- |
| **Pipeline**          | End-to-end processing flow: File Watcher -> Detection -> Batch Aggregator -> Analysis -> Event |
| **File Watcher**      | Service that monitors camera directories for new image uploads.                                |
| **Batch Aggregator**  | Service that groups detections into batches based on camera and time proximity.                |
| **Circuit Breaker**   | Fault tolerance pattern that temporarily disables calls to a failing service.                  |
| **Dead Letter Queue** | Queue where failed messages are stored for investigation and reprocessing.                     |

---

## Troubleshooting

Quick symptom reference. Full guide: [Troubleshooting Hub](troubleshooting/index.md)

### Quick Self-Check

```bash
# 1. System health
curl -s http://localhost:8000/api/system/health | jq .

# 2. Service status
docker compose -f docker-compose.prod.yml ps

# 3. GPU status
nvidia-smi

# 4. Recent logs
docker compose -f docker-compose.prod.yml logs --tail=50 backend
```

### Common Issues Quick Reference

| Symptom                     | Likely Cause             | Quick Fix                                                           |
| --------------------------- | ------------------------ | ------------------------------------------------------------------- |
| Dashboard shows no events   | File watcher or AI down  | Restart backend                                                     |
| Risk gauge stuck at 0       | `ai-vlm` not running     | `docker compose -f docker-compose.prod.yml up -d ai-vlm`            |
| Camera shows offline        | FTP or folder path issue | Check FTP and folder config                                         |
| AI not responding           | Services not started     | `docker compose -f docker-compose.prod.yml up -d ai-gateway ai-vlm` |
| WebSocket disconnected      | Backend down             | Restart backend                                                     |
| "Connection refused" errors | Service not running      | Start the service                                                   |
| CORS errors in browser      | URL mismatch             | Update `CORS_ORIGINS`                                               |

### Detailed Troubleshooting Guides

- [Troubleshooting Index](troubleshooting/index.md) - Start here for any issue
- [AI Issues](troubleshooting/ai-issues.md) - `ai-gateway`, `ai-vlm`, pipeline problems
- [Connection Issues](troubleshooting/connection-issues.md) - Network, containers, WebSocket
- [Database Issues](troubleshooting/database-issues.md) - PostgreSQL connection, schema
- [GPU Issues](troubleshooting/gpu-issues.md) - CUDA, VRAM, thermal issues
- [Triton Rootless CUDA](troubleshooting/triton-rootless-cuda.md) - Gateway CUDA init failure under rootless Podman

---

## Configuration Files

| File                      | Purpose                                  |
| ------------------------- | ---------------------------------------- |
| `.env`                    | Local environment overrides (not in git) |
| `.env.example`            | Template with documented defaults        |
| `data/runtime.env`        | Runtime overrides (loaded after .env)    |
| `docker-compose.prod.yml` | Production Docker configuration          |
| `docker-compose.ci.yml`   | CI pipeline configuration                |
| `docker-compose.test.yml` | Test harness configuration               |

### Loading Order

1. Default values from `backend/core/config.py`
2. `.env` file (if exists)
3. `data/runtime.env` file (if exists; path overridable via `HSI_RUNTIME_ENV_PATH`)
4. Environment variables override all

---

## Validation

Test your configuration:

```bash
# Check backend config loads correctly (run from the repo root)
uv run python -c "from backend.core.config import get_settings; s = get_settings(); print(s.model_dump_json(indent=2))"

# Test service connectivity
curl http://localhost:8000/api/system/health     # Backend
curl http://localhost:8090/yolo26/health         # YOLO26 (AI gateway router)
curl http://localhost:8098/health                # ai-vlm (check `podman ps` first)
redis-cli ping                                   # Redis
```

---

## Subdirectories

### API Documentation

REST and WebSocket API endpoint reference. Full API documentation is located in the [Developer API Guide](../developer/api/README.md).

- [API Overview](../developer/api/README.md) - API conventions and authentication
- [Core Resources](../developer/api/core-resources.md) - Cameras, events, detections, zones, entities, analytics
- [AI Pipeline](../developer/api/ai-pipeline.md) - Enrichment, batches, AI audit, dead letter queue
- [System Operations](../developer/api/system-ops.md) - Health, config, alerts, logs, notifications
- [Real-time](../developer/api/realtime.md) - WebSocket streams for events and system status
- [WebSocket Contracts](../developer/api/websocket-contracts.md) - Detailed WebSocket message formats

### config/

Configuration reference documentation.

- [Environment Variables](config/env-reference.md) - Complete variable reference
- [Risk Levels](config/risk-levels.md) - Risk score ranges and severity

### troubleshooting/

Symptom-based problem-solving guides.

- [Troubleshooting Index](troubleshooting/index.md) - Quick symptom lookup
- [AI Issues](troubleshooting/ai-issues.md) - AI service problems
- [Connection Issues](troubleshooting/connection-issues.md) - Network and connectivity
- [Database Issues](troubleshooting/database-issues.md) - PostgreSQL problems
- [GPU Issues](troubleshooting/gpu-issues.md) - GPU and CUDA issues
- [Triton Rootless CUDA](troubleshooting/triton-rootless-cuda.md) - Gateway CUDA init failure under rootless Podman

---

## Related Documentation

- [Operator Hub](../operator/README.md) - System administration guides
- [Developer Hub](../developer/README.md) - Development guides
- [User Hub](../user/README.md) - End-user documentation
- [Architecture](../architecture/README.md) - Technical architecture decisions

---

[Back to Documentation](../AGENTS.md) | [Operator Hub](../operator/README.md) | [Developer Hub](../developer/README.md)
