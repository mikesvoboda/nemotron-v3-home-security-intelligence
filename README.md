# Home Security Intelligence

Turn “dumb” security cameras into an intelligent threat detection system — **100% local, no cloud APIs required.**

<!-- Nano Banana Pro Prompt:
"Technical illustration of AI-powered home security concept,
neural network analyzing security camera feeds with green detection overlays,
dark background #121212, NVIDIA green #76B900 accent lighting,
clean minimalist style, vertical 2:3 aspect ratio,
no text overlays"
-->

![Dashboard](docs/images/dashboard.png)

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Node 20.19+](https://img.shields.io/badge/node-20.19+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61dafb.svg)](https://react.dev/)

## What you get

- **Real-time dashboard**: camera grid, activity feed, risk gauge, telemetry
- **Detections → events (not noise)**: time-window batching turns many frames into one explained “event”
- **AI model zoo enrichment**: optional captions, re-ID, plate/OCR, faces, clothing/vehicle/pet context, image quality/tamper signals
- **Local-first**: runs on your hardware; footage stays on your network

## How it works (at a glance)

![From Camera to Alert](docs/images/info-camera-to-event.png)

### AI Pipeline

![AI Pipeline Flow](docs/images/flow-ai-pipeline.png)

## Documentation (pick your path)

| I want to…                   | Start here                             |
| ---------------------------- | -------------------------------------- |
| Run this at home             | [User Hub](docs/user-hub.md)           |
| Deploy and maintain it       | [Operator Hub](docs/operator-hub.md)   |
| Contribute / extend the code | [Developer Hub](docs/developer-hub.md) |

If you just need the authoritative env/ports reference, go straight to
[Runtime Configuration](docs/RUNTIME_CONFIG.md).

## AI services and model zoo (what's actually in this repo)

This project ships a **multi-service AI stack** (`ai/`) plus a backend "model zoo" used for enrichment.

### What the system detects

![Detection Types](docs/images/info-detection-types.png)

### Model zoo enrichment

![Model Zoo](docs/images/arch-model-zoo.png)

### AI services (containerized HTTP)

| Service                                | Default port | Purpose                                          | Typical usage |
| -------------------------------------- | ------------ | ------------------------------------------------ | ------------- |
| RT-DETRv2 (`ai/rtdetr`)                | 8090         | Object detection (people/vehicles/animals)       | Core          |
| Nemotron via llama.cpp (`ai/nemotron`) | 8091         | Risk reasoning + scoring (0–100)                 | Core          |
| Florence-2 (`ai/florence`)             | 8092         | Vision-language extraction (captions/attributes) | Enrichment    |
| CLIP (`ai/clip`)                       | 8093         | Embeddings + re-identification support           | Enrichment    |
| Enrichment service (`ai/enrichment`)   | 8094         | Vehicle/pet/clothing/depth/pose (remote helper)  | Enrichment    |

> [!NOTE]
> In production, `docker-compose.prod.yml` defines **all** of these services (not just RT-DETR/Nemotron).

### Backend enrichment (lazy-loaded “model zoo”)

The backend also includes an `EnrichmentPipeline` that can load/run additional models on demand (or call the
`ai-enrichment` HTTP service in containerized deployments). Examples include license plates + OCR, faces,
vehicle damage/type, clothing segmentation, pet classification, violence detection, and image quality checks.

## Quick Start

> [!TIP]
> If you’re unsure which option to choose, start with **Option A**.

### Option A: Production (fully containerized, GPU)

Runs **frontend + backend + PostgreSQL + Redis + AI services** in containers (RT-DETR, Nemotron, and model-zoo
enrichment services like Florence/CLIP/Enrichment).

**Prereqs:** Linux host + NVIDIA GPU + container GPU passthrough. Model files/paths are documented in
[AI Setup](docs/AI_SETUP.md).

```bash
# 1) Create local config
cp .env.example .env

# 2) Download AI models (first run)
./ai/download_models.sh

# 3) Start everything (Docker)
docker compose -f docker-compose.prod.yml up -d

# OR Podman
# podman-compose -f docker-compose.prod.yml up -d
```

- Open the dashboard: `http://localhost:5173`
- Verify backend health:

```bash
curl http://localhost:8000/api/system/health
```

> [!TIP]
> Want to run **just the core** AI services? You can start a subset of services:
>
> ```bash
> docker compose -f docker-compose.prod.yml up -d postgres redis backend frontend ai-detector ai-llm
> ```

### Option B: Development (host-run AI + app containers)

Useful when iterating on AI services, or when GPU passthrough is inconvenient.

```bash
# 1) Create local config
cp .env.example .env

# 2) Download AI models (first run)
./ai/download_models.sh

# 3) Start AI on the host
./scripts/start-ai.sh start

# (Alternatively, start in separate terminals)
# ./ai/start_detector.sh   # RT-DETRv2 on :8090
# ./ai/start_llm.sh        # Nemotron on :8091

# 4) If needed, set AI_HOST for container → host networking
# Docker Desktop typically uses: host.docker.internal
export AI_HOST=host.docker.internal
# Podman on macOS uses: host.containers.internal
# export AI_HOST=host.containers.internal

# 5) Start app stack (no container AI services)
docker compose up -d
```

- Open the dashboard: `http://localhost:5173`

> [!WARNING]
> Do **not** mix host-run AI services with `docker-compose.prod.yml` (port conflicts on 8090/8091).

## Cameras: how ingestion works (FTP)

Cameras upload images/videos to:

```
/export/foscam/{camera_name}/
```

You can:

- Bring your own FTP server and point it at `/export/foscam`
- Use the included FTP container: see [`vsftpd/README.md`](vsftpd/README.md)

> [!NOTE]
> In production containers, the host camera path is mounted to `/cameras` and the backend uses
> `FOSCAM_BASE_PATH=/cameras` (see `docker-compose.prod.yml`).

## Configuration (where to look first)

**Source of truth:** [docs/RUNTIME_CONFIG.md](docs/RUNTIME_CONFIG.md)

Common things you’ll configure:

- `FOSCAM_BASE_PATH` (where camera uploads land)
- `RTDETR_URL`, `NEMOTRON_URL` (core AI endpoints)
- `FLORENCE_URL`, `CLIP_URL`, `ENRICHMENT_URL` (enrichment AI endpoints)
- `RETENTION_DAYS`, `BATCH_WINDOW_SECONDS`, `BATCH_IDLE_TIMEOUT_SECONDS`
- `FILE_WATCHER_POLLING=true` (recommended on Docker Desktop volume mounts)
- `VISION_EXTRACTION_ENABLED`, `REID_ENABLED`, `SCENE_CHANGE_ENABLED` (enrichment feature toggles)
- `API_KEY_ENABLED` (turn on API key auth for exposed deployments)

## Architecture (1-minute tour)

![System Architecture](docs/images/arch-system-overview.png)

- **Frontend** (`frontend/`): React + TypeScript + Tailwind + Tremor
  - REST client + WS URL builder: `frontend/src/services/api.ts`
  - Realtime hooks: `frontend/src/hooks/`
- **Backend** (`backend/`): FastAPI + async SQLAlchemy + Redis
  - Pipeline orchestration: `backend/services/`
  - HTTP/WebSocket API: `backend/api/routes/`
  - Models: `backend/models/`
- **AI services** (`ai/`): containerized FastAPI/llama.cpp servers
  - RT-DETRv2 detection (`ai/rtdetr/`, default port **8090**)
  - Nemotron risk reasoning via llama.cpp (`ai/nemotron/`, default port **8091**)
  - Florence-2 VLM extraction (`ai/florence/`, default port **8092**)
  - CLIP embeddings / re-ID support (`ai/clip/`, default port **8093**)
  - Enrichment service helper (`ai/enrichment/`, default port **8094**)

See [AI Setup](docs/AI_SETUP.md) and the authoritative ports/env in
[docs/RUNTIME_CONFIG.md](docs/RUNTIME_CONFIG.md).

## Security model (read this before exposing it)

This MVP is designed for **single-user, trusted LAN** deployments.

- Authentication is **off by default**
- Rate limiting is **on by default**
- Do **not** expose it to the public internet without hardening

Start here:

- [Admin Security Guide](docs/admin-guide/security.md)

## Contributing

Start with the [Developer Hub](docs/developer-hub.md).

```bash
# Full validation (lint + typecheck + tests)
./scripts/validate.sh
```

This project uses **bd (beads)** for task tracking:

```bash
bd ready
bd show <id>
bd update <id> --status in_progress
```

## License

Licensed under the **Apache License 2.0**. See [LICENSE](LICENSE).

## Acknowledgments

[RT-DETRv2](https://github.com/lyuwenyu/RT-DETR) ·
[Nemotron](https://huggingface.co/nvidia) ·
[llama.cpp](https://github.com/ggerganov/llama.cpp) ·
[FastAPI](https://fastapi.tiangolo.com/) ·
[Tremor](https://www.tremor.so/)
