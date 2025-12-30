# Home Security Intelligence

> Turn dumb security cameras into an intelligent threat detection system—**100% local, no cloud APIs required.**

![Dashboard](docs/images/dashboard.png)

**What it does:** Your security cameras upload images via FTP. This system watches those uploads, runs object detection (RT-DETRv2), and uses a **locally-running LLM** (Nemotron Mini 4B) to generate contextual risk assessments—not just "person detected" but _"unfamiliar person approaching back entrance at 2am, risk: high."_

### Why Local AI?

- **Privacy:** Your security footage never leaves your network
- **No subscriptions:** No monthly API fees or cloud dependencies
- **Works offline:** Full functionality without internet
- **Fast:** Sub-second inference on consumer GPUs (even older ones!)

|                |                                        |
| -------------- | -------------------------------------- |
| **Detection**  | RT-DETRv2 (30-50ms/image)              |
| **Analysis**   | Nemotron Mini 4B via llama.cpp         |
| **Storage**    | PostgreSQL + 30-day retention          |
| **Interface**  | React dashboard + REST API + WebSocket |
| **Target GPU** | NVIDIA RTX (8GB+ VRAM)                 |

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Node 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.2-61dafb.svg)](https://react.dev/)
[![Backend Coverage](https://img.shields.io/badge/backend_coverage-98%25-brightgreen.svg)]()
[![Frontend Coverage](https://img.shields.io/badge/frontend_coverage-99%25-brightgreen.svg)]()

---

## Get Running

### Prerequisites

- NVIDIA GPU with 8GB+ VRAM and CUDA 12.0+
- Docker + Docker Compose
- Python 3.14+, Node 18+
- `llama-server` on PATH ([install llama.cpp](https://github.com/ggerganov/llama.cpp))

### Quick Start

```bash
# 1. Setup environment and dependencies
./scripts/setup-hooks.sh

# 2. Download AI models (~10GB)
./ai/download_models.sh

# 3. Start AI servers (in separate terminals)
./ai/start_detector.sh    # RT-DETRv2 on :8090
./ai/start_llm.sh         # Nemotron on :8091

# 4. Start the app
docker compose up --build
```

**That's it.** Open [http://localhost:5173](http://localhost:5173) for the dashboard (development mode).

> **Production:** Use `docker compose -f docker-compose.prod.yml up -d` and access at [http://localhost](http://localhost) (port 80).

<details>
<summary>Linux networking note</summary>

The default `docker-compose.yml` uses `host.docker.internal`. On Linux, either:

- Add `--add-host=host.docker.internal:host-gateway` to your docker run
- Or set `RTDETR_URL` and `NEMOTRON_URL` explicitly in `.env`

</details>

---

## How It Works

```mermaid
flowchart LR
    subgraph Cameras
        CAM[Foscam FTP Upload]
    end

    subgraph Ingestion
        FW[FileWatcher]
        RQ1[(Redis Queue)]
    end

    subgraph Detection
        DET[RT-DETRv2<br/>Object Detection]
        DB1[(Detections + Thumbnails)]
    end

    subgraph Analysis
        BA[BatchAggregator<br/>90s windows]
        RQ2[(Redis Queue)]
        NEM[Nemotron LLM<br/>Risk Analysis]
        DB2[(Risk-scored Events)]
    end

    subgraph Interface
        WS[WebSocket]
        DASH[Dashboard]
    end

    CAM --> FW --> RQ1 --> DET --> DB1 --> BA --> RQ2 --> NEM --> DB2 --> WS --> DASH
```

<details>
<summary>Why batch detections?</summary>

A single "person walks to door" might generate 15 images over 30 seconds. Batching groups these into one event with full context, so the LLM can reason about the _sequence_ ("person approached, paused, left") rather than isolated frames.

- **Window:** 90 seconds max
- **Idle timeout:** 30 seconds of no activity closes the batch early
- **Fast path:** High-confidence critical detections (person >90%) skip batching for immediate alerts

</details>

<details>
<summary>Service ports</summary>

| Service     | Dev Port | Prod Port | Purpose                   |
| ----------- | -------- | --------- | ------------------------- |
| Frontend    | 5173     | 80        | Vite (dev) / Nginx (prod) |
| Backend API | 8000     | 8000      | FastAPI + WebSocket       |
| PostgreSQL  | 5432     | 5432      | Database                  |
| RT-DETRv2   | 8090     | 8090      | Object detection          |
| Nemotron    | 8091     | 8091      | LLM risk analysis         |
| Redis       | 6379     | 6379      | Queues + pub/sub          |

> **Note:** Production frontend runs on Nginx (port 80 inside container).
> Change with `FRONTEND_PORT` env var.

</details>

---

## Features

| Feature                 | Description                               |
| ----------------------- | ----------------------------------------- |
| **Real-time Dashboard** | Live event feed, risk gauge, camera grid  |
| **AI Risk Scoring**     | 0-100 scores with LLM-generated reasoning |
| **Event Timeline**      | Filter by camera, risk level, date range  |
| **GPU Monitoring**      | Utilization, memory, temperature tracking |
| **Thumbnail Previews**  | Auto-generated with bounding box overlays |
| **30-day Retention**    | Automatic cleanup, configurable           |

<details>
<summary>More Screenshots</summary>

**Event Timeline** — Browse and filter all security events
![Timeline](docs/images/timeline.png)

**Alerts** — High-risk events requiring attention
![Alerts](docs/images/alerts.png)

</details>

<details>
<summary>REST API endpoints</summary>

All endpoints documented at [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI)

**Cameras** — `GET/POST/PATCH/DELETE /api/cameras`

**Events** — `GET /api/events` (filterable), `GET/PATCH /api/events/{id}`

**Detections** — `GET /api/detections`, `GET /api/detections/{id}/image`

**System** — `GET /api/system/health`, `/gpu`, `/stats`, `/config`

**Media** — `GET /api/media/cameras/{id}/{path}`, `/thumbnails/{file}`

</details>

<details>
<summary>WebSocket streams</summary>

| Endpoint        | Purpose                   | Message format                             |
| --------------- | ------------------------- | ------------------------------------------ |
| `WS /ws/events` | Real-time security events | `{"type": "event", "data": {...}}`         |
| `WS /ws/system` | System status (every 5s)  | `{"type": "system_status", "data": {...}}` |

</details>

<details>
<summary>Database schema</summary>

- **cameras** — id, name, folder_path, status, timestamps
- **detections** — camera_id, object_type, confidence, bbox, thumbnail_path
- **events** — batch_id, camera_id, risk_score, risk_level, summary, reasoning
- **gpu_stats** — utilization, memory, temperature, inference_fps

Full models in `backend/models/`

</details>

---

## Configuration

Copy `.env.example` to `.env` and adjust as needed. See [docs/RUNTIME_CONFIG.md](docs/RUNTIME_CONFIG.md) for complete reference.

<details>
<summary>Environment variables</summary>

**Core**
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/security` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `FOSCAM_BASE_PATH` | `/export/foscam` | Camera upload directory |

**AI Services**
| Variable | Default | Description |
|----------|---------|-------------|
| `RTDETR_URL` | `http://localhost:8090` | Detection service |
| `NEMOTRON_URL` | `http://localhost:8091` | LLM service |
| `DETECTION_CONFIDENCE_THRESHOLD` | `0.5` | Minimum confidence (0.0-1.0) |

**Batching**
| Variable | Default | Description |
|----------|---------|-------------|
| `BATCH_WINDOW_SECONDS` | `90` | Max batch duration |
| `BATCH_IDLE_TIMEOUT_SECONDS` | `30` | Close batch after idle |
| `FAST_PATH_CONFIDENCE_THRESHOLD` | `0.90` | Skip batching threshold |
| `FAST_PATH_OBJECT_TYPES` | `["person"]` | Object types for fast path |

**Retention**
| Variable | Default | Description |
|----------|---------|-------------|
| `RETENTION_DAYS` | `30` | Days to keep events/detections |
| `LOG_RETENTION_DAYS` | `7` | Days to keep logs |

</details>

<details>
<summary>Tuning tips</summary>

**More responsive alerts?** Lower `BATCH_IDLE_TIMEOUT_SECONDS` to 15-20.

**Too many false positives?** Raise `DETECTION_CONFIDENCE_THRESHOLD` to 0.6-0.7.

**GPU memory issues?** The two AI models need ~6GB combined. Close other GPU apps or reduce batch sizes.

</details>

---

## Development

### Testing

```bash
./scripts/test-runner.sh        # Full suite with coverage
```

| Suite    | Tests | Coverage | Command                    |
| -------- | ----- | -------- | -------------------------- |
| Backend  | 335   | 98%      | `pytest backend/tests/ -v` |
| Frontend | 233   | 99%      | `cd frontend && npm test`  |

<details>
<summary>Running specific tests</summary>

```bash
# Backend
pytest backend/tests/unit/ -v                    # Unit tests only
pytest backend/tests/integration/ -v             # Integration tests only
pytest -k "test_camera" -v                       # Tests matching pattern

# Frontend
npm test -- --run src/components/                # Specific directory
npm run test:coverage                            # With coverage report
npm run test:ui                                  # Vitest UI
```

</details>

### Code Quality

Pre-commit hooks enforce standards automatically. **Never use `--no-verify`.**

```bash
pre-commit run --all-files      # Run all checks manually
```

<details>
<summary>What the hooks check</summary>

- **Python:** ruff (lint + format), mypy (types), pytest
- **Frontend:** eslint, prettier, TypeScript, vitest
- **Coverage:** 95% minimum enforced

</details>

### Project Structure

```
backend/
  api/routes/       # FastAPI endpoints
  services/         # AI pipeline (watcher, detector, analyzer)
  models/           # SQLAlchemy models
  core/             # Config, database, Redis
frontend/
  src/components/   # React components
  src/hooks/        # Custom hooks (useWebSocket, useEventStream)
  src/services/     # API client
ai/
  rtdetr/           # Detection server
  nemotron/         # LLM config
```

> **Tip:** Every directory has an `AGENTS.md` file explaining its purpose.

---

## Troubleshooting

<details>
<summary>AI servers won't start</summary>

- Verify CUDA: `nvidia-smi`
- Check GPU memory: models need ~6GB combined
- Ensure models downloaded: `./ai/download_models.sh`
- Check logs in the terminal where you started the service

</details>

<details>
<summary>Backend can't reach AI services</summary>

```bash
curl http://localhost:8090/health   # RT-DETRv2
curl http://localhost:8091/health   # Nemotron
```

On Linux, ensure Docker can reach host services (see Quick Start note).

</details>

<details>
<summary>WebSocket won't connect</summary>

- Backend running? `curl http://localhost:8000/api/system/health`
- Check browser console for CORS errors
- Verify frontend proxy config in `vite.config.ts`

</details>

<details>
<summary>Database connection issues</summary>

Ensure PostgreSQL is running and accessible. Check the connection URL and credentials.

- Native: `postgresql+asyncpg://security:security_dev_password@localhost:5432/security`
- Docker: `postgresql+asyncpg://security:security_dev_password@postgres:5432/security`
- Verify PostgreSQL is accessible: `psql -h localhost -U security -d security`

</details>

---

## Documentation

Full Documentation available in docs/README.md — Comprehensive guides for all audiences:

- **[User Guide](docs/user-guide/)** — How to use the dashboard (non-technical)
- **[Architecture](docs/architecture/)** — System design and decisions
- **[Development](docs/AI_SETUP.md)** — Setup and contributing

---

## Security

**This is designed for local/trusted network use.**

- No authentication by default (single-user assumption)
- Media endpoints have path traversal protection
- Don't expose to the internet without adding auth and hardening

---

## Contributing

Task tracking uses **bd (beads)**:

```bash
bd ready                    # Find available work
bd list --label phase-6     # Current phase
bd show <id>                # Task details
```

---

## License

Personal and educational use. Contact maintainer for commercial licensing.

---

## Acknowledgments

[RT-DETRv2](https://github.com/lyuwenyu/RT-DETR) • [Nemotron](https://huggingface.co/nvidia) • [llama.cpp](https://github.com/ggerganov/llama.cpp) • [FastAPI](https://fastapi.tiangolo.com/) • [Tremor](https://www.tremor.so/)
