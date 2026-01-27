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
| [Troubleshooting](troubleshooting/)         | Symptom-based problem solving              |
| [API Reference](../developer/api/README.md) | REST and WebSocket API documentation       |
| [Risk Levels](config/risk-levels.md)        | Risk score ranges and severity definitions |

---

## Service Ports

| Service     | Port | Protocol | Description                                                        |
| ----------- | ---- | -------- | ------------------------------------------------------------------ |
| Frontend    | 5173 | HTTP     | Vite dev server (development) or host port in production (default) |
| Frontend    | 80   | HTTP     | Nginx inside production container (mapped via FRONTEND_PORT)       |
| Backend API | 8000 | HTTP/WS  | FastAPI REST + WebSocket                                           |
| YOLO26      | 8090 | HTTP     | Object detection service                                           |
| Nemotron    | 8091 | HTTP     | LLM risk analysis service                                          |
| Florence-2  | 8092 | HTTP     | Vision extraction service (optional)                               |
| CLIP        | 8093 | HTTP     | Re-identification service (optional)                               |
| Enrichment  | 8094 | HTTP     | Enrichment HTTP service (optional)                                 |
| PostgreSQL  | 5432 | TCP      | Database                                                           |
| Redis       | 6379 | TCP      | Cache, queues, pub/sub                                             |

---

## Environment Variables {#environment}

Complete reference: [Environment Variable Reference](config/env-reference.md)

### Quick Reference - Essential Variables

| Variable       | Required | Default                    | Description               |
| -------------- | -------- | -------------------------- | ------------------------- |
| `DATABASE_URL` | **Yes**  | -                          | PostgreSQL connection URL |
| `REDIS_URL`    | No       | `redis://localhost:6379/0` | Redis connection URL      |
| `YOLO26_URL`   | No       | `http://localhost:8095`    | YOLO26 service URL        |
| `NEMOTRON_URL` | No       | `http://localhost:8091`    | Nemotron LLM service URL  |

### Database Configuration

```bash
# Format
DATABASE_URL=postgresql+asyncpg://user:password@host:port/database  # pragma: allowlist secret

# Local development
DATABASE_URL=postgresql+asyncpg://security:password@localhost:5432/security  # pragma: allowlist secret

# Docker container (use service name)
DATABASE_URL=postgresql+asyncpg://security:password@postgres:5432/security  # pragma: allowlist secret
```

> **Important:** There is no default `DATABASE_URL`. Run `./setup.sh` to generate a `.env` file with secure credentials.

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

| Variable         | Default                 | Description                           |
| ---------------- | ----------------------- | ------------------------------------- |
| `YOLO26_URL`     | `http://localhost:8095` | YOLO26 object detection service       |
| `NEMOTRON_URL`   | `http://localhost:8091` | Nemotron LLM service                  |
| `FLORENCE_URL`   | `http://localhost:8092` | Florence-2 vision-language (optional) |
| `CLIP_URL`       | `http://localhost:8093` | CLIP embedding service (optional)     |
| `ENRICHMENT_URL` | `http://localhost:8094` | Enrichment service (optional)         |

> **Warning:** Use HTTPS in production to prevent MITM attacks.

### AI Service Timeouts

| Variable                | Default | Range   | Description                |
| ----------------------- | ------- | ------- | -------------------------- |
| `AI_CONNECT_TIMEOUT`    | `10.0`  | 1-60s   | Connection timeout         |
| `AI_HEALTH_TIMEOUT`     | `5.0`   | 1-30s   | Health check timeout       |
| `YOLO26_READ_TIMEOUT`   | `60.0`  | 10-300s | Detection response timeout |
| `NEMOTRON_READ_TIMEOUT` | `120.0` | 30-600s | LLM response timeout       |

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

| Variable            | Default                 | Description                      |
| ------------------- | ----------------------- | -------------------------------- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend API URL                  |
| `VITE_WS_BASE_URL`  | `ws://localhost:8000`   | WebSocket URL                    |
| `FRONTEND_PORT`     | `5173`                  | Host port for frontend container |

For complete environment variable documentation, see [Environment Variable Reference](config/env-reference.md).

---

## AI Service Deployment Modes

### Development Mode (Host-run AI)

AI services run directly on the host while the backend runs in a container:

```bash
# macOS with Docker Desktop (default)
YOLO26_URL=http://host.docker.internal:8095
NEMOTRON_URL=http://host.docker.internal:8091

# macOS with Podman
export AI_HOST=host.containers.internal
podman-compose up -d

# Linux
# Use host IP or add --add-host=host.docker.internal:host-gateway
```

### Production Mode (Fully Containerized)

All services including AI run in containers:

```bash
# Uses container network names (set in docker-compose.prod.yml)
YOLO26_URL=http://ai-yolo26:8095
NEMOTRON_URL=http://ai-llm:8091
```

### Quick Reference: AI_HOST by Platform

| Platform | Runtime | Development (host AI)            | Production (container AI)   |
| -------- | ------- | -------------------------------- | --------------------------- |
| macOS    | Docker  | `host.docker.internal` (default) | N/A (use Linux for GPU)     |
| macOS    | Podman  | `host.containers.internal`       | N/A (use Linux for GPU)     |
| Linux    | Docker  | Host IP or `host-gateway`        | `ai-yolo26`, `ai-llm`, etc. |
| Linux    | Podman  | Host IP or `host-gateway`        | `ai-yolo26`, `ai-llm`, etc. |
| Windows  | Docker  | `host.docker.internal`           | N/A (use Linux for GPU)     |

---

## Glossary

Key terms used throughout the documentation. Full glossary: [Glossary](glossary.md)

### Core Concepts

| Term           | Definition                                                                                                                      |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Detection**  | A single object instance identified by YOLO26 in an image. Contains object type, confidence score, bounding box, and timestamp. |
| **Event**      | A security incident containing one or more detections, analyzed by Nemotron for risk assessment.                                |
| **Batch**      | A collection of detections from a single camera grouped within a time window for analysis.                                      |
| **Risk Score** | A numeric value from 0-100 assigned by Nemotron indicating the threat level of an event.                                        |
| **Risk Level** | Categorical classification: Low (0-29), Medium (30-59), High (60-84), Critical (85-100).                                        |

### AI Components

| Term           | Definition                                                                              |
| -------------- | --------------------------------------------------------------------------------------- |
| **YOLO26**     | Real-time object detection model using transformer architecture for accurate detection. |
| **Nemotron**   | NVIDIA's LLM family. Production uses Nemotron-3-Nano-30B-A3B; development uses Mini 4B. |
| **Florence-2** | Vision-language model for extracting visual attributes (optional enrichment).           |
| **CLIP**       | Model for generating image embeddings enabling re-identification across camera frames.  |
| **Inference**  | The process of running an AI model on input data to produce predictions.                |

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

Quick symptom reference. Full guide: [Troubleshooting Hub](troubleshooting/)

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

| Symptom                     | Likely Cause             | Quick Fix                     |
| --------------------------- | ------------------------ | ----------------------------- |
| Dashboard shows no events   | File watcher or AI down  | Restart backend               |
| Risk gauge stuck at 0       | Nemotron unavailable     | Start Nemotron LLM            |
| Camera shows offline        | FTP or folder path issue | Check FTP and folder config   |
| AI not responding           | Services not started     | `./scripts/start-ai.sh start` |
| WebSocket disconnected      | Backend down             | Restart backend               |
| "Connection refused" errors | Service not running      | Start the service             |
| CORS errors in browser      | URL mismatch             | Update `CORS_ORIGINS`         |

### Detailed Troubleshooting Guides

- [Troubleshooting Index](troubleshooting/) - Start here for any issue
- [AI Issues](troubleshooting/ai-issues.md) - YOLO26, Nemotron, pipeline problems
- [Connection Issues](troubleshooting/connection-issues.md) - Network, containers, WebSocket
- [Database Issues](troubleshooting/database-issues.md) - PostgreSQL connection, migrations
- [GPU Issues](troubleshooting/gpu-issues.md) - CUDA, VRAM, thermal issues

---

## Configuration Files

| File                      | Purpose                                  |
| ------------------------- | ---------------------------------------- |
| `.env`                    | Local environment overrides (not in git) |
| `.env.example`            | Template with documented defaults        |
| `data/runtime.env`        | Runtime overrides (loaded after .env)    |
| `docker-compose.yml`      | Development Docker configuration         |
| `docker-compose.prod.yml` | Production Docker configuration          |

### Loading Order

1. Default values from `backend/core/config.py`
2. `.env` file (if exists)
3. `data/runtime.env` file (if exists)
4. Environment variables override all

---

## Validation

Test your configuration:

```bash
# Check backend config loads correctly
cd backend
python -c "from core.config import get_settings; s = get_settings(); print(s.model_dump_json(indent=2))"

# Test service connectivity
curl http://localhost:8000/api/system/health     # Backend
curl http://localhost:8095/health                # YOLO26
curl http://localhost:8091/health                # Nemotron
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

- [Troubleshooting Index](troubleshooting/) - Quick symptom lookup
- [AI Issues](troubleshooting/ai-issues.md) - AI service problems
- [Connection Issues](troubleshooting/connection-issues.md) - Network and connectivity
- [Database Issues](troubleshooting/database-issues.md) - PostgreSQL problems
- [GPU Issues](troubleshooting/gpu-issues.md) - GPU and CUDA issues

---

## Related Documentation

- [Operator Hub](../operator/README.md) - System administration guides
- [Developer Hub](../developer/README.md) - Development guides
- [User Hub](../user/README.md) - End-user documentation
- [Architecture](../architecture/) - Technical architecture decisions

---

[Back to Documentation](../AGENTS.md) | [Operator Hub](../operator/README.md) | [Developer Hub](../developer/README.md)
