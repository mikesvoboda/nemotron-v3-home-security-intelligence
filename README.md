# Home Security Intelligence

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.2-61dafb.svg)](https://react.dev/)

An AI-powered home security monitoring dashboard that turns **camera uploads** into **structured detections** and **contextual risk-scored events**.

This project is designed for a **single-user, local deployment** (no auth by default) and targets a hybrid setup:

- **Docker** for the web app + backend services
- **Native GPU processes** for AI inference (RT-DETRv2 + Nemotron via `llama.cpp`)

---

## Table of Contents

- [Key Features](#key-features)
- [What it does](#what-it-does-intent)
- [Architecture](#architecture-high-level)
- [What's implemented](#whats-implemented-today-repo-reality)
- [Quickstart](#quickstart-local-dev)
- [Configuration](#configuration)
- [Testing](#testing)
- [Deployment](#deployment)
- [Repo map](#repo-map-where-to-look)
- [Contributing](#contributing--work-tracking)
- [Security & Privacy](#security--privacy-notes)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Key Features

- **Intelligent Object Detection** - RT-DETRv2 identifies people, vehicles, and animals in real-time
- **AI Risk Analysis** - Nemotron LLM generates contextual risk scores (0-100) with reasoning
- **Event Batching** - Groups detections into meaningful 90-second events for better context
- **Real-time Dashboard** - Live WebSocket updates for events and system status
- **GPU Monitoring** - Track NVIDIA GPU utilization, memory, and temperature
- **Event Timeline** - Searchable history with filtering by camera, risk level, and date
- **Thumbnail Previews** - Auto-generated thumbnails with bounding box overlays
- **RESTful API** - Full FastAPI backend with auto-generated OpenAPI docs
- **Configurable Retention** - Automatic cleanup of old events (default: 30 days)
- **Path Safety** - Built-in traversal protection for media serving

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

**API Documentation:**

- **Interactive docs**: `http://localhost:8000/docs` (Swagger UI)
- **ReDoc**: `http://localhost:8000/redoc` (alternative documentation)
- **OpenAPI spec**: `http://localhost:8000/openapi.json`

**Service Ports:**

- **Frontend**: `http://localhost:5173` (Vite dev server)
- **Backend API**: `http://localhost:8000` (FastAPI/uvicorn)
- **Swagger UI**: `http://localhost:8000/docs`

### AI pipeline services

Core pipeline building blocks exist in `backend/services/` (watcher, detector client, batcher, analyzer, thumbnail generator).

**Note:** the “background worker” processes that continuously consume Redis queues are not bundled as a single one-command daemon yet; today you typically run the API + AI servers, and wire/operate the pipeline workers as needed during development.

---

## Quickstart (local dev)

### Prerequisites

- **Docker** + Docker Compose (v20.10+ recommended)
- **Python 3.11+** (project uses `.venv`; see `./scripts/setup-hooks.sh`)
- **Node.js 18+** and npm (for the frontend)
- **llama.cpp** installed locally so `llama-server` is on your `PATH`
- **NVIDIA GPU** with CUDA support (recommended: RTX series, 8GB+ VRAM)
- **CUDA Toolkit 12.0+** (for GPU inference)
- **~10GB disk space** for AI models and data storage

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

- **Frontend**: `http://localhost:5173` (Vite dev server)
- **Backend**: `http://localhost:8000` (FastAPI)

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

### Run all tests with coverage

```bash
./scripts/test-runner.sh
```

This runs:

- Backend tests (pytest) with 95% coverage requirement
- Frontend tests (vitest) with 95% coverage requirement
- Integration tests for APIs and WebSockets

### Quick validation (lint + typecheck + tests)

```bash
./scripts/validate.sh
```

### Backend tests only

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v --cov=. --cov-report=term-missing
```

### Frontend tests only

```bash
cd frontend
npm test                    # Run tests in watch mode
npm run test:coverage      # Run tests with coverage report
npm run test:ui            # Open Vitest UI
```

### Pre-commit hooks

The project uses pre-commit hooks to enforce code quality:

- Python: ruff (linting + formatting), mypy (type checking), pytest
- Frontend: eslint, prettier, vitest

**Important:** Never bypass hooks with `--no-verify`

---

## Deployment

### Production deployment (hybrid approach)

The recommended production setup uses:

- **Docker** for the web stack (frontend, backend, Redis)
- **Native processes** for GPU workloads (RT-DETRv2, Nemotron)

**Why hybrid?**

- GPU acceleration works best with native CUDA
- Containers simplify web service management
- Minimal operational overhead for single-user deployment

### Steps for production

1. **Clone and configure**

   ```bash
   git clone <repo-url>
   cd nemotron-v3-home-security-intelligence
   cp .env.example .env
   # Edit .env with your camera paths and settings
   ```

2. **Download AI models**

   ```bash
   ./ai/download_models.sh
   ```

3. **Start AI servers (in screen/tmux or systemd)**

   ```bash
   ./ai/start_detector.sh &
   ./ai/start_llm.sh &
   ```

4. **Start the web stack**

   ```bash
   docker compose up -d
   ```

5. **Verify**
   - Frontend: `http://your-server:5173` (Vite dev server)
   - Backend health: `http://your-server:8000/api/system/health`

### Storage and retention

- Database: `backend/data/security.db` (SQLite)
- Media files: mounted from `CAMERA_ROOT` (read-only)
- Thumbnails: `backend/data/thumbnails/`
- Retention: 30 days (configurable via `RETENTION_DAYS`)

### Monitoring

Check system health via:

- API: `GET /api/system/health` - service status
- API: `GET /api/system/gpu` - GPU metrics
- API: `GET /api/system/stats` - database statistics
- WebSocket: `WS /ws/system` - real-time system updates

---

## Repo map (where to look)

- **Backend API**: `backend/api/routes/`
- **Backend services (pipeline)**: `backend/services/`
- **DB models**: `backend/models/`
- **Frontend app**: `frontend/src/`
- **Design spec / plans**: `docs/plans/`
- **Post-MVP ideas**: `docs/ROADMAP.md`
- **AGENTS.md files**: Every directory has an `AGENTS.md` for navigation

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
- Camera feeds and security data are sensitive; ensure proper network isolation and access controls.

---

## Troubleshooting

### AI servers won't start

**Issue:** `llama-server` or detector service fails to start

**Solutions:**

- Verify CUDA installation: `nvidia-smi`
- Check GPU memory availability
- Ensure models are downloaded: `./ai/download_models.sh`
- Review logs in terminal where services were started

### Backend can't connect to AI services

**Issue:** Backend shows detector/LLM connection errors

**Solutions:**

- Verify AI servers are running: `curl http://localhost:8001/health` and `curl http://localhost:8002/health`
- On Linux, check `docker-compose.yml` uses correct host networking
- Ensure ports 8001 and 8002 are not blocked by firewall

### Database locked errors

**Issue:** SQLite database lock errors

**Solutions:**

- Ensure only one backend instance is running
- Check file permissions on `backend/data/security.db`
- Restart the backend service

### WebSocket connection fails

**Issue:** Frontend can't establish WebSocket connection

**Solutions:**

- Verify backend is running: `http://localhost:8000/api/system/health`
- Check browser console for CORS or connection errors
- Ensure `VITE_WS_URL` is correctly set in frontend environment

### Models take too long to download

**Issue:** `download_models.sh` is slow or fails

**Solutions:**

- Check internet connection and Hugging Face availability
- Models are ~5-10GB; ensure adequate bandwidth
- Resume interrupted downloads by re-running the script

---

## License

This project is provided as-is for personal and educational use.

**No official license has been specified yet.** Please contact the project maintainer for licensing questions or commercial use inquiries.

---

## Acknowledgments

- **RT-DETRv2** - Object detection by PaddlePaddle team
- **Nemotron** - LLM by NVIDIA
- **llama.cpp** - Efficient LLM inference
- **FastAPI** - Modern Python web framework
- **React + Tremor** - Frontend UI components
