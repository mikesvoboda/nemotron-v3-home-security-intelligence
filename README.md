# Home Security Intelligence

An AI-powered home security monitoring dashboard that turns **camera uploads** into **structured detections** and **contextual risk-scored events**.

This project is designed for a **single-user, local deployment** (no auth by default) and targets a hybrid setup:
- **Docker** for the web app + backend services
- **Native GPU processes** for AI inference (RT-DETRv2 + Nemotron via `llama.cpp`)

---

## What it does (intent)

Foscam cameras FTP-upload images/videos to a folder structure like:

- `/export/foscam/{camera_name}/...`

The system then:
- Detects objects (people/vehicles/animals) with **RT-DETRv2**
- Batches detections into short time windows (for more context)
- Uses **Nemotron** to generate:
  - a **risk score** (0–100)
  - a **risk level** (low/medium/high/critical)
  - a short **summary** + reasoning
- Stores results in SQLite and streams updates to the dashboard via WebSockets

---

## Architecture (high level)

**Data flow**

- **Camera uploads** → filesystem
- **File watcher** → Redis queue (`detection_queue`)
- **Detector worker** → RT-DETRv2 → `detections` table (+ thumbnails)
- **Batch aggregator** → Redis (`analysis_queue`)
- **Analyzer worker** → Nemotron/llama.cpp → `events` table
- **Backend** broadcasts → WebSocket → **Frontend UI**

**Key technologies**

- **Frontend**: React + TypeScript + Tailwind + Tremor
- **Backend**: FastAPI + SQLAlchemy (async) + SQLite + Redis
- **AI**:
  - RT-DETRv2 detection server (HTTP, port `8001`)
  - Nemotron LLM via `llama-server` (HTTP, port `8002`)

---

## What’s implemented today (repo reality)

### Backend API (FastAPI, port 8000)

- **REST**
  - `GET /api/system/health`, `GET /api/system/gpu`, `GET /api/system/config`, `GET /api/system/stats`
  - `GET/POST/PATCH/DELETE /api/cameras`
  - `GET /api/events` (+ filters/pagination), `GET/PATCH /api/events/{id}`, `GET /api/events/{id}/detections`
  - `GET /api/detections` (+ filters/pagination), `GET /api/detections/{id}`, `GET /api/detections/{id}/image` (bbox overlay)
  - `GET /api/media/cameras/{camera_id}/{filename:path}` and `GET /api/media/thumbnails/{filename}` (with traversal protection)
- **WebSocket**
  - `WS /ws/events` (event stream)
  - `WS /ws/system` (system status stream)

FastAPI docs: `http://localhost:8000/docs`

### AI pipeline services

Core pipeline building blocks exist in `backend/services/` (watcher, detector client, batcher, analyzer, thumbnail generator).

**Note:** the “background worker” processes that continuously consume Redis queues are not bundled as a single one-command daemon yet; today you typically run the API + AI servers, and wire/operate the pipeline workers as needed during development.

---

## Quickstart (local dev)

### Prerequisites

- **Docker** + Docker Compose
- **Python** (project uses `.venv`; see `./scripts/setup-hooks.sh`)
- **Node.js** (for the frontend)
- **llama.cpp** installed locally so `llama-server` is on your `PATH`
- (Optional) NVIDIA GPU + CUDA for fast inference

### 1) One-time setup

```bash
./scripts/setup-hooks.sh
```

### 2) Download AI model(s)

```bash
./ai/download_models.sh
```

### 3) Start AI servers (native)

In separate terminals:

```bash
./ai/start_detector.sh
```

```bash
./ai/start_llm.sh
```

### 4) Start the app stack (Docker)

```bash
docker compose up --build
```

- **Frontend**: `http://localhost:3000`
- **Backend**: `http://localhost:8000`

**macOS note:** `docker-compose.yml` uses `host.docker.internal` for `DETECTOR_URL` / `LLM_URL`. On Linux you may need to adjust this (e.g., `--add-host=host.docker.internal:host-gateway` or set the URLs explicitly).

---

## Configuration

- Copy `.env.example` → `.env` (if you want local overrides)
- Docker Compose also supplies environment variables for the backend container, including:
  - `DATABASE_URL` (SQLite file under `backend/data/`)
  - `REDIS_URL`
  - `DETECTOR_URL` (RT-DETRv2)
  - `LLM_URL` (Nemotron / llama.cpp)
  - `CAMERA_ROOT` (camera mount inside the container; defaults to `/cameras`)

---

## Testing

Run everything (tests + coverage):

```bash
./scripts/test-runner.sh
```

Quick validation (lint + typecheck + tests):

```bash
./scripts/validate.sh
```

---

## Repo map (where to look)

- **Backend API**: `backend/api/routes/`
- **Backend services (pipeline)**: `backend/services/`
- **DB models**: `backend/models/`
- **Frontend app**: `frontend/src/`
- **Design spec / plans**: `docs/plans/`
- **Post-MVP ideas**: `docs/ROADMAP.md`

---

## Contributing / work tracking

This repo uses **bd (beads)** for task tracking:

```bash
bd ready
bd list --label phase-5
bd show <id>
```

---

## Security & privacy notes

- This is intended for **local** use; do not expose it publicly without adding authentication and hardening.
- Media serving endpoints include **path traversal protection** and file type allowlists, but you should still run behind a trusted network boundary.


