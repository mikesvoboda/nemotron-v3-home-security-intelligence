# Home Security Intelligence

Turn "dumb" security cameras into an intelligent threat detection system — **100% local, no cloud APIs required.**

![Dashboard Tour](docs/images/dashboard-tour.gif)

<details>
<summary>📸 Static Screenshots</summary>

| Dashboard                                           | Timeline                                          | Entities                                          |
| --------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------- |
| ![Dashboard](docs/images/screenshots/dashboard.png) | ![Timeline](docs/images/screenshots/timeline.png) | ![Entities](docs/images/screenshots/entities.png) |

| Alerts                                        | Analytics                                           | AI Performance                                                |
| --------------------------------------------- | --------------------------------------------------- | ------------------------------------------------------------- |
| ![Alerts](docs/images/screenshots/alerts.png) | ![Analytics](docs/images/screenshots/analytics.png) | ![AI Performance](docs/images/screenshots/ai-performance.png) |

| Profiling                                           | Tracing                                         | Operations                                            |
| --------------------------------------------------- | ----------------------------------------------- | ----------------------------------------------------- |
| ![Profiling](docs/images/screenshots/pyroscope.png) | ![Tracing](docs/images/screenshots/tracing.png) | ![Operations](docs/images/screenshots/operations.png) |

</details>

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Node 24 LTS](https://img.shields.io/badge/node-24+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61dafb.svg)](https://react.dev/)

[![CI](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/actions/workflows/ci.yml)
[![Documentation](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/actions/workflows/docs.yml/badge.svg)](https://mikesvoboda.github.io/nemotron-v3-home-security-intelligence/)
[![codecov](https://codecov.io/gh/mikesvoboda/nemotron-v3-home-security-intelligence/graph/badge.svg)](https://codecov.io/gh/mikesvoboda/nemotron-v3-home-security-intelligence)
[![Backend Coverage](https://img.shields.io/codecov/c/github/mikesvoboda/nemotron-v3-home-security-intelligence?flag=backend-unit&label=backend%20coverage)](https://codecov.io/gh/mikesvoboda/nemotron-v3-home-security-intelligence)
[![Frontend Coverage](https://img.shields.io/codecov/c/github/mikesvoboda/nemotron-v3-home-security-intelligence?flag=frontend&label=frontend%20coverage)](https://codecov.io/gh/mikesvoboda/nemotron-v3-home-security-intelligence)

| I want to…                   | Start here                                                                                                                                                                                        |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Browse the full docs         | [**Documentation Site**](https://mikesvoboda.github.io/nemotron-v3-home-security-intelligence/)                                                                                                   |
| Run this at home             | [User Hub](docs/user/README.md)                                                                                                                                                                   |
| Deploy and maintain it       | [Operator Hub](docs/operator/README.md)                                                                                                                                                           |
| Contribute / extend the code | [Developer Hub](docs/developer/README.md)                                                                                                                                                         |
| Work on it as an AI agent    | [`AGENTS.md`](AGENTS.md) — the root instruction file (read it; `CLAUDE.md` is retired); every directory has its own `AGENTS.md`, and [`llms.txt`](llms.txt) is the condensed machine-readable map |

---

## What You Get: AI-Powered Risk Reasoning

The brain of this system is a vision-language model that assesses every event — the `ai-vlm` llama.cpp engine (VLMAnalyzer; risk reasoning — model identity is config, ledger D5. R8 retired the legacy Nemotron text-only path, 2026-09-29). It runs entirely on your hardware:

| Specification        | Value                                     | Why It Matters                                  |
| -------------------- | ----------------------------------------- | ----------------------------------------------- |
| **Weights**          | GGUF pair, host-mounted, never baked      | `VLM_MODEL_PATH` / `VLM_MMPROJ_PATH` in `.env`  |
| **VRAM Required**    | see the bring-up record — config-driven   | sized per card; `VLM_GPU_LAYERS=auto` offloads  |
| **Context Window**   | 32,768 tokens (`VLM_CTX_SIZE`)            | Split 2 ways: 16K per slot, concurrent analyses |
| **Inference Engine** | llama.cpp (`ai-vlm`, container port 8098) | Optimized C++ with CUDA acceleration            |

**Also included:**

- **Real-time dashboard** — camera grid, activity feed, risk gauge, telemetry
- **Detections → events** — time-window batching turns many frames into one explained "event"
- **Identity lookups** — re-ID, license plates and faces matched against your own registrations (DB lookups; the enrichment attribute models retired with R8)
- **Local-first** — runs on your hardware; footage stays on your network
- **First run** — the API returns 503 for everything except setup and health until you register the
  first admin in the dashboard; that's the setup guard working, not a broken install

![From Camera to Alert](docs/images/info-camera-to-event.png)

---

## Video Analytics Features

The system provides comprehensive video analytics capabilities:

### Detection and Analysis

| Feature                 | Description                                       | Documentation                                                             |
| ----------------------- | ------------------------------------------------- | ------------------------------------------------------------------------- |
| **Object Detection**    | YOLO26 detects people, vehicles, animals, objects | [Object detection](docs/guides/video-analytics.md#object-detection)       |
| **Scene Understanding** | The VLM describes and assesses each event         | [Scene understanding](docs/guides/video-analytics.md#scene-understanding) |
| **Anomaly Detection**   | Learned activity baselines flag unusual patterns  | [Anomaly detection](docs/guides/video-analytics.md#anomaly-detection)     |
| **Threat Detection**    | Weapon and dangerous item detection               | [Threat detection](docs/guides/video-analytics.md#threat-detection)       |

### Zone Intelligence

| Feature                   | Description                              | Documentation                                                              |
| ------------------------- | ---------------------------------------- | -------------------------------------------------------------------------- |
| **Detection Zones**       | Define areas for focused monitoring      | [Creating zones](docs/guides/zone-configuration.md#creating-zones)         |
| **Dwell Time Tracking**   | Monitor how long objects remain in zones | [Dwell time](docs/guides/zone-configuration.md#dwell-time-tracking)        |
| **Line Crossing**         | Detect zone entry/exit events            | [Line crossing](docs/guides/zone-configuration.md#line-crossing-detection) |
| **Household Integration** | Link zones to household members          | [Households](docs/guides/zone-configuration.md#household-integration)      |

### Person and Vehicle Identification

| Feature                    | Description                           | Documentation                                                                 |
| -------------------------- | ------------------------------------- | ----------------------------------------------------------------------------- |
| **Face Detection**         | Detect faces within person detections | [Face detection](docs/guides/face-recognition.md#face-detection)              |
| **Person Re-ID**           | Track individuals across cameras      | [Re-identification](docs/guides/face-recognition.md#person-re-identification) |
| **Demographics**           | Age and gender estimation             | [Demographics](docs/guides/face-recognition.md#demographics-analysis)         |
| **License Plates**         | Plate detection and OCR               | [License plates](docs/guides/video-analytics.md#license-plate-detection)      |
| **Vehicle Classification** | Vehicle type identification           | [Vehicle analysis](docs/guides/video-analytics.md#vehicle-analysis)           |

### Analytics and Reporting

All four live on the [Analytics API](docs/api/analytics-endpoints.md):

| Endpoint                             | Description                |
| ------------------------------------ | -------------------------- |
| `/api/analytics/detection-trends`    | Daily detection counts     |
| `/api/analytics/risk-history`        | Risk level distribution    |
| `/api/analytics/camera-uptime`       | Camera performance metrics |
| `/api/analytics/object-distribution` | Object type breakdown      |

---

## AI Model Zoo

`models.yml` is the single source of truth for every model the system downloads and loads — name, download size, VRAM footprint, and which service runs it. The tables below are drawn from it, except where a model runs inside the gateway's Triton process instead of the backend model zoo (those carry `vram_mb: 0` there, so their VRAM comes from [VRAM Requirements](docs/_includes/vram-requirements.md)).

### Always-Loaded Models

The two engines every event path talks to. The VLM runs under the `vlm` compose
profile and the backend only soft-depends on it (`docker-compose.prod.yml:127`
— a profiled service can never sit in a `depends_on`, so the backend
degrades instead of failing to boot):

| Model                                          | Purpose                            | VRAM                                                             | Where it runs                        |
| ---------------------------------------------- | ---------------------------------- | ---------------------------------------------------------------- | ------------------------------------ |
| VLM engine (GGUF pair; identity is config, D5) | Scene description + risk reasoning | see the bring-up record — config-driven                          | `ai-vlm` llama.cpp container, 8098   |
| YOLO26                                         | Primary object detection           | `vram_mb: 0` in `models.yml` (gateway-resident, not backend-zoo) | `ai-gateway` Triton, route `/yolo26` |

> Since the gateway consolidation (bc7d6101) and the R8 legacy retirement
> (2026-09-29), `ai-gateway` publishes exactly two routers on port **8090** —
> `/yolo26` and `/enrich-lt` (weapon/threat + person re-ID; `GATEWAY_MODEL_SET`
> is a closed set — an unexpected member hard-raises). The `/florence`, `/clip`
> and `/enrichment` routers, their containers and the legacy text-only LLM
> (the old `ai-llm` service) were all deleted with it.

### Object Detector

Three YOLO26 variants ship (`n`/`s`/`m`; `m` is the default). Measured end-to-end latency, RTX A5500 at 640x640, batch 1 — details and throughput curves in [YOLO26 Benchmarks](docs/benchmarks/yolo26-benchmarks.md):

| Variant | Latency (batch 1) | FPS  | Best For                     |
| ------- | ----------------- | ---- | ---------------------------- |
| YOLO26m | 138.84ms          | 7.2  | Default, best accuracy       |
| YOLO26s | 73.74ms           | 13.6 | Maximum throughput per frame |
| YOLO26n | 44.83ms           | 22.3 | Lightweight, edge deployment |

### Lookup Models

Since R8 the enrichment attribute zoo is retired — what remains answers
_identity_ questions (who/what is this face, plate, person) against your own
registrations, plus the weapon/plate detectors that feed the verdict. These
load when a detection needs them (gateway Triton or the backend model zoo) and
evict by LRU under VRAM pressure. Complete `models.yml` inventory (VRAM and
phase from the rows themselves):

| Model                    | Purpose                               | VRAM              | Phase | Notes                                                              |
| ------------------------ | ------------------------------------- | ----------------- | ----- | ------------------------------------------------------------------ |
| yolo26                   | Primary object detection              | Triton (`yolo26`) | 0     | `enabled: false` in the zoo; gateway export reads the .pt off disk |
| osnet-ain-x1-0           | Person re-ID embeddings               | ~100MB            | 1     | Triton `reid`; `preload: true`                                     |
| threat-detection-yolov8n | Weapon detection (knives, guns, bats) | ~300MB            | 1     | Triton `threat`                                                    |
| face-detector-scrfd      | Face detection (CPU onnxruntime)      | 0 (CPU)           | 3     | `low` priority; `preload: true`                                    |
| face-recognizer          | Face embeddings (CPU onnxruntime)     | 0 (CPU)           | 3     | `low` priority; `preload: true`                                    |
| yolo11-face              | Face detection on person crops        | ~200MB            | 3     | backend                                                            |
| yolo11-license-plate     | License plate detection               | ~300MB            | 3     | backend                                                            |
| fast-alpr                | Plate detection + OCR (ONNX)          | ~28MB             | 3     | library fetches at runtime                                         |
| paddleocr                | Text recognition                      | ~100MB            | 3     | superseded by fast-alpr                                            |
| yolo26-general           | General scene detection               | ~400MB            | 3     | `enabled: false` — weights not released                            |

Retired with R8 (2026-09-29): Florence, SigLIP/CLIP, pose (ViTPose /
yolov8n-pose / ST-GCN++ / X-CLIP), demographics (ViT age+gender), clothing
(FashionCLIP / SegFormer), vehicle-segment, vehicle-damage, pet, depth,
weather, violence, smoke/fire — the VLM path describes what it sees instead of
re-perceiving it with a specialist per attribute.

### Model Priority System

Every model carries a priority in `models.yml` that sets its eviction order under VRAM pressure:

- **CRITICAL**: never evicted if any VRAM can be freed (no shipped `models.yml` row is marked today — the safety model that carried it retired with R8)
- **HIGH** / **MEDIUM** / **LOW**: evicted in that order; most models ship at **medium** default (the two CPU face rows are `low`)
- `never_evict: true` pins a model outright (no live row sets it); `preload: true` loads it at startup (osnet + the two face rows)

### Downloading Models

```bash
# Download the models the setup_lib rule selects (since R8: 5 of the 10 live
# models.yml rows, 763MB of models.yml size_mb — the script header carries the
# exact re-derivation, and a guard test pins the fetch list to the rule).
# Reads only the AI_MODELS_PATH shell variable (not .env — export it to match
# setup.py's choice, below) and the target must already exist and be writable:
# setup.py sudo-creates it; otherwise sudo mkdir -p + chown first.
./ai/download_models.sh

# Custom models directory (default /export/ai_models; the containers mount this)
AI_MODELS_PATH=/path/to/models ./ai/download_models.sh
```

### VRAM Budget

Sizing is dominated by the VLM identity in `VLM_MODEL_PATH` / `VLM_MMPROJ_PATH`:
`VLM_GPU_LAYERS=auto` (default) offloads as many layers as the card allows, so
there is no fixed tier table any more. Budget the GGUF pair's layers, the
gateway's Triton process, and ~1.0GB of lookup-model headroom — the full table
lives in [VRAM Requirements](docs/_includes/vram-requirements.md). The retired
30B-LLM tiers this table published died with the legacy path in R8 (2026-09-29).

The on-demand model manager loads and unloads models based on VRAM availability using LRU eviction with priority-based ordering.

### Model Status API

```bash
curl http://localhost:8000/api/system/models
curl http://localhost:8000/api/system/models/<name>/status
```

> [!WARNING]
> Runtime state is **wrong** until the status API is repointed at the gateway. Both routes still read
> from the retired `ai-enrichment:8094` / `ai-enrichment-light:8096` services, which no longer exist in
> `docker-compose.prod.yml` (the models now run inside `ai-gateway`, routes `/enrichment` and
> `/enrich-lt`). The fetch fails soft, so `GET /api/system/models` answers 200 while reporting every
> model `loaded: false` and both services unhealthy — a phantom "all models unloaded" reading, not an
> outage. Trust `http://localhost:8090/health` and `http://localhost:8090/metrics` on the gateway
> instead. Load/unload (`POST /api/system/models/<name>/load` and `/unload`) proxy to those same dead
> hostnames, so they always fail 503; don't reach for them until the routes are rewired.

---

<details>
<summary><strong>Hardware Requirements</strong></summary>

### Minimum vs Recommended

| Component      | Minimum               | Recommended       | This Project Uses                                                                                           |
| -------------- | --------------------- | ----------------- | ----------------------------------------------------------------------------------------------------------- |
| **GPU VRAM**   | 12GB (reduced layers) | 24GB              | RTX A5500 (24GB)                                                                                            |
| **System RAM** | 32GB                  | 64GB+             | 128GB                                                                                                       |
| **Storage**    | 50GB (core models)    | 100GB+ (full zoo) | ~33GB per `models.yml` (rule selects 25 entries; script fetches 24, ~32.2GB — xclip row removed 2026-09-23) |
| **CPU**        | 8 cores               | 16+ cores         | AMD Ryzen 9                                                                                                 |

### GPU Compatibility

| VRAM     | What You Can Run                                              | Example GPUs                        |
| -------- | ------------------------------------------------------------- | ----------------------------------- |
| **24GB** | Full stack, all models loaded                                 | RTX 3090, 4090, A5000, A5500, A6000 |
| **16GB** | Nemotron (reduced layers) + YOLO26                            | RTX 4080, A4000, Tesla T4           |
| **12GB** | Nemotron (CPU offload) + YOLO26                               | RTX 3080, 4070 Ti                   |
| **8GB**  | Nemotron partially offloaded via `GPU_LAYERS` (slow) + YOLO26 | RTX 3070, 4060 Ti                   |

### Runtime Resource Usage

With all services running on RTX A5500 (24GB):

| Resource       | Usage                                                                                                          |
| -------------- | -------------------------------------------------------------------------------------------------------------- |
| **GPU Memory** | ~23 GB / 24 GB                                                                                                 |
| **System RAM** | ~49 GB (sum of `deploy.resources.limits.memory` in `docker-compose.prod.yml`; host minimum 32GB)               |
| **Containers** | 21 (19 run by default — `foscam-init` exits after its chown; `ai-llm-vllm` and `dcgm-exporter` need a profile) |
| **Open Ports** | 8444/8080 (UI HTTPS/HTTP), 8000 (API), 8090/8091 (AI gateway/Nemotron)                                         |

> [!TIP] > **Don't have 24GB VRAM?** Reduce `GPU_LAYERS` to offload some layers to CPU RAM, or use a smaller quantization. The system degrades gracefully.

</details>

---

## Quick Start

**Prerequisites:** Linux host + NVIDIA GPU + Podman with GPU passthrough (the `docker` CLI works as a shim only via the optional `podman-docker` package)

```bash
# 1. Run setup — generates .env from .env.example with your ports, paths and secrets,
#    offers to download the models, and ends by deploying the stack
python setup.py

# 2. Download AI models (~33GB per models.yml; 30-90 min on a fast connection).
#    Skip if you let setup.py do it. The script reads only the AI_MODELS_PATH shell
#    variable — not .env — so match what setup.py wrote, and the target directory
#    must already exist and be writable (setup.py sudo-creates it).
AI_MODELS_PATH=$(grep -m1 ^AI_MODELS_PATH .env | cut -d= -f2-) ./ai/download_models.sh

# 3. Start everything (you only need this if setup.py's auto-deploy was skipped —
#    reboot prompt, --defaults, or Ctrl-C; see the note below for PODMAN_SOCKET)
podman compose -f docker-compose.prod.yml up -d
```

> [!NOTE]
> This project targets **Podman**: the compose file uses Podman-specific keys
> (`userns_mode: keep-id`, `:U` mount flags, CDI `devices:`), so plain `docker compose`
> does not run it as-is. `backend` and `alloy` also hard-require `PODMAN_SOCKET` in
> `.env`; `python setup.py deploy` appends it automatically. If you skipped the deploy
> phase, enable the socket first:
>
> ```bash
> systemctl --user enable --now podman.socket
> echo "PODMAN_SOCKET=/run/user/$(id -u)/podman/podman.sock" >> .env
> ```

**Verify:**

```bash
curl http://localhost:8000/api/system/health   # Backend health
open http://localhost:8080                     # Dashboard (HTTP)
# Or: open https://localhost:8444              # Dashboard (HTTPS; enable with SSL_ENABLED=true)
```

Then open the dashboard: first run requires you to register the first admin account
(the API returns 503 for everything except setup and health until you do).

> [!TIP]
> Run **just core services**: `podman compose -f docker-compose.prod.yml up -d postgres redis backend frontend ai-gateway ai-llm`
> (Since the gateway consolidation, `ai-gateway` is the single AI entrypoint — detection/enrichment run inside it, models load on demand.)

## Operations & Monitoring

The monitoring ships in the same compose file — no separate stack to start. Monitoring URLs bind
`127.0.0.1`, so open them on the host itself (or forward an SSH tunnel); the dashboard is the
exception, bound `0.0.0.0` for tunnel access — use your firewall to fence it.

| Where        | URL                                                       | Notes                                                        |
| ------------ | --------------------------------------------------------- | ------------------------------------------------------------ |
| Dashboard    | `http://localhost:8080` / `https://localhost:8444`        | HTTPS needs `SSL_ENABLED=true`                               |
| API docs     | `http://localhost:8000/docs`                              | FastAPI Swagger UI                                           |
| Grafana      | `http://localhost:3002` or `https://<host>:8444/grafana/` | Anonymous access on by default (`GF_AUTH_ANONYMOUS_ENABLED`) |
| Prometheus   | `http://localhost:9090`                                   | Metrics and alerting rules                                   |
| Alertmanager | `http://localhost:9093`                                   | Delivered alerts                                             |
| Loki         | `http://localhost:3100`                                   | Log aggregation (queried through Grafana)                    |
| Tempo        | `http://localhost:3200`                                   | Distributed traces                                           |
| Pyroscope    | `http://localhost:4040`                                   | Continuous profiling                                         |

Port numbers come from `.env` (`GRAFANA_PORT`, `PROMETHEUS_PORT`, …). Full guide:
[Monitoring & Observability](docs/operator/monitoring.md).

### First five minutes at 2am

```bash
# What's up / what's down (this project uses Podman)
podman ps -a --format "table {{.Names}}\t{{.Status}}"
podman compose -f docker-compose.prod.yml ps

# Logs — a whole service, or one container
podman compose -f docker-compose.prod.yml logs --tail=50 backend
podman logs --tail=50 backend

# Restart one service without touching the rest
podman compose -f docker-compose.prod.yml restart backend
```

Host-run dev-mode logs land in `logs/backend.log` (`./scripts/dev.sh logs` tails it).

Health endpoints, cheapest first — `health/live` answers without touching dependencies:

| Endpoint                                       | What it tells you                |
| ---------------------------------------------- | -------------------------------- |
| `http://localhost:8000/api/system/health/live` | Backend process is alive         |
| `http://localhost:8000/api/system/health`      | Backend + dependency status      |
| `http://localhost:8000/api/system/health/full` | Every dependency, no timeouts    |
| `http://localhost:8090/health`                 | AI gateway (Triton, all routers) |
| `http://localhost:8091/health`                 | Nemotron LLM                     |

Service control and self-healing details: [Service Control](docs/operator/service-control.md).

<details>
<summary><strong>Development Setup (host-run backend + frontend)</strong></summary>

Runs backend and frontend as host processes for fast iteration; Redis and
PostgreSQL come from containers, AI containers stay as they are. Needs `uv`
(`curl -LsSf https://astral.sh/uv/install.sh | sh`), Node 24+, and Python 3.14
(`requires-python` in `pyproject.toml`) on the host.

```bash
# 1. One-time setup
python setup.py
uv sync --extra dev            # Python deps (repo-root .venv — dev.sh sources this one)
cd frontend && npm ci          # Frontend deps (CI uses npm; bun.lock exists but no bun config)

# 2. PostgreSQL — dev.sh does NOT start it, and the backend dies on boot without it
#    (init_db in the FastAPI lifespan). .env's DATABASE_URL/REDIS_URL point at the
#    container hostnames `postgres`/`redis`, so run a dev container and override:
podman run -d --name dev-postgres \
  -e POSTGRES_USER=security -e POSTGRES_DB=security \
  -e POSTGRES_PASSWORD="$(grep -m1 ^POSTGRES_PASSWORD .env | cut -d= -f2-)" \
  -p 127.0.0.1:5432:5432 docker.io/library/postgres:16-alpine
export DATABASE_URL="postgresql+asyncpg://security:$(grep -m1 ^POSTGRES_PASSWORD .env | cut -d= -f2-)@localhost:5432/security"
export REDIS_URL=redis://localhost:6379/0

# 3. Start Redis + backend (uvicorn :8000) + frontend (Vite dev server :8444, HTTPS)
./scripts/dev.sh start
./scripts/dev.sh status        # Also: stop | restart | logs
```

`dev.sh` starts Redis with the `docker` CLI; on a Podman host give it the
docker-compatible socket (`systemctl --user enable --now podman.socket` + the
`podman-docker` shim, or `export DOCKER_HOST=unix:///run/user/$UID/podman/podman.sock`)
or run a system Redis (`sudo systemctl start redis`) — otherwise `start` aborts
(`set -e`) before backend/frontend launch. `./scripts/dev.sh redis` manages just
Redis.

Open https://localhost:8444 — Vite serves HTTPS with a self-signed cert
(strictPort; accept the browser warning). It proxies `/api` and `/ws` to the
backend on port 8000. (`scripts/dev.sh` prints a 5173 URL — that echo is
wrong; the server really binds 8444 per `frontend/vite.config.ts`.)

</details>

<details>
<summary><strong>Host-run AI servers</strong></summary>

Useful when iterating on AI model code directly on the host. The host-run detector
replaces only the gateway's `/yolo26` router — the `/enrich-lt` specialists still need
the `ai-gateway` container. (The standalone `ai-yolo26` GPU image was retired 2026-09-23 —
Triton inside `ai-gateway` serves yolo26; the build recipe lives at
`archive/ai-yolo26-image/Dockerfile`. The gateway's `/florence`, `/clip` and `/enrichment`
routers were retired with R8 S3, 2026-09-29, along with the `FLORENCE_URL` / `CLIP_URL` /
`ENRICHMENT_URL` settings they fed.)

```bash
# Start the AI servers on the host (separate terminals)
./ai/start_detector.sh   # YOLO26 — reads PORT/YOLO26_PORT, defaults to 8090
# (The reasoning engine has no host-run script: the shipped llama.cpp server is the
#  ai-vlm container — start it with: podman compose -f docker-compose.prod.yml
#  --profile vlm up -d ai-vlm. The old ./ai/start_llm.sh Nemotron server was retired
#  with the legacy path in R8 S2.)

# Then point the HOST-RUN backend (dev.sh) at them. The host detector serves its
# endpoints at the root (/health, /detect), so no router suffix — and these exports
# never reach a containerized backend (compose hardcodes the AI URLs; no env_file).
export YOLO26_URL=http://localhost:8090
# The light-enrichment lane (threat + re-ID) comes from the ai-gateway container,
# published on 127.0.0.1:8090 — point its client at the router. Leave
# USE_AI_GATEWAY=false (the default): with it true the detector client ignores
# YOLO26_URL and sends detection back to the gateway.
export ENRICHMENT_LIGHT_URL=http://localhost:8090/enrich-lt
```

If instead the backend itself runs in a container, `host.docker.internal` resolves
only on macOS/Docker Desktop; on Linux Podman use `host.containers.internal` or the
host IP, and note the compose file hardcodes the AI URLs, so override them with a
compose `environment:` entry or an override file — a shell `export` is not enough.
See [AI Configuration](docs/operator/ai-configuration.md) for the per-platform hostnames.

> [!WARNING]
> Do **not** run these while `ai-gateway`/`ai-llm` containers are up — they will fight over ports 8090/8091.
> The host-run detector defaults to 8090, which is also the `ai-gateway` host port — so it
> collides with `ai-gateway`, not with the retired 8095.
> To keep `ai-gateway` up for Florence/CLIP/enrichment, run the detector on a free port instead:
> `YOLO26_PORT=8095 ./ai/start_detector.sh` with `export YOLO26_URL=http://localhost:8095`.

</details>

---

## Architecture

![System Architecture](docs/images/arch-system-overview.png)

| Layer       | Stack                         | Key Files                                         |
| ----------- | ----------------------------- | ------------------------------------------------- |
| Frontend    | React + TypeScript + Tailwind | `frontend/src/services/api.ts`                    |
| Backend     | FastAPI + SQLAlchemy + Redis  | `backend/services/`, `backend/api/`               |
| AI Services | llama.cpp + Triton + FastAPI  | `ai/gateway/` (all model routers), `ai/nemotron/` |

![Container Architecture](docs/images/architecture/container-architecture.png)

![AI Pipeline Flow](docs/images/flow-ai-pipeline.png)

**Detailed Documentation:**

| Hub                                                                  | Description                                |
| -------------------------------------------------------------------- | ------------------------------------------ |
| [Architecture Hub](docs/architecture/README.md)                      | Complete system architecture documentation |
| [Security](docs/architecture/security/README.md)                     | Input validation, data protection, OWASP   |
| [Dataflows](docs/architecture/dataflows/README.md)                   | End-to-end data traces, pipeline timing    |
| [Detection Pipeline](docs/architecture/detection-pipeline/README.md) | YOLO26 integration, image processing       |
| [AI Orchestration](docs/architecture/ai-orchestration/README.md)     | Nemotron LLM, batch processing             |

---

<details>
<summary><strong>Camera Ingestion (FTP)</strong></summary>

Cameras upload images/videos to:

```
/export/foscam/{camera_name}/
```

You can:

- Bring your own FTP server and point it at `/export/foscam`
- Run the archived vsftpd container yourself from [`archive/vsftpd/`](archive/vsftpd/) — `vsftpd.conf`, `Dockerfile`, `docker-compose-wrapper.sh`, `install-systemd.sh`. It is not wired into any compose file, and the README in that directory still points at a `docker-compose.yml` that no longer exists.

> [!NOTE]
> In production containers, the host camera path is mounted to `/cameras` and the backend uses `FOSCAM_BASE_PATH=/cameras`.

</details>

<details>
<summary><strong>Configuration</strong></summary>

**Source of truth:** [Environment Variable Reference](docs/reference/config/env-reference.md)

Common settings:

| Variable                                 | Purpose                                 | Containerized deploy                                                                                                          |
| ---------------------------------------- | --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `FOSCAM_BASE_PATH`                       | Camera upload directory (host path)     | Read from `.env` by compose (bind-mount source); inside the container it's forced to `/cameras`                               |
| `YOLO26_URL`, `FLORENCE_URL`, `CLIP_URL` | AI gateway router endpoints (port 8090) | Compose hardcodes these to `http://ai-gateway:8090/<route>`; your `.env` values are ignored (host runs only)                  |
| `NEMOTRON_URL`                           | Nemotron LLM endpoint (port 8091)       | Compose hardcodes `http://ai-llm:8091` (host runs only)                                                                       |
| `RETENTION_DAYS`                         | Event retention (days; default 30)      | **Not passed to the backend container** — add an `environment:` entry or an override file, or edits silently keep the default |
| `BATCH_WINDOW_SECONDS`                   | Detection batching window               | **Not passed to the backend container** — same caveat                                                                         |
| `API_KEY_ENABLED`                        | Enable API key auth (off by default)    | **Not passed to the backend container** — same caveat                                                                         |
| `FILE_WATCHER_POLLING`                   | Use polling (Docker mounts)             | Passed through by compose — the only knob here that works out of the box                                                      |

> [!NOTE]
> The prod compose file has **no** `env_file:` and mounts no `.env`, and `.dockerignore` excludes it —
> so the `env_file=".env"` in `backend/core/config.py` resolves to a path inside the image that
> doesn't exist. Only variables compose interpolates with `${...}`, or names in the `environment:`
> list, reach the container. Host-run dev mode (`./scripts/dev.sh`) reads `.env` directly, where all
> of these work.

</details>

<details>
<summary><strong>Security Model</strong></summary>

This MVP is designed for **single-user, trusted LAN** deployments.

- On a fresh install the API returns 503 until you register the first admin account through the dashboard
  (SetupGuardMiddleware); after that, API endpoints are open to the local network.
- Optional API keys exist behind `API_KEY_ENABLED` (off by default); admin/destructive routes carry their own guards.
- Rate limiting is **on by default**
- Do **not** expose to the public internet without hardening

See: [Admin Security Guide](docs/operator/admin/security.md)

</details>

---

## Contributing

Start with the [Developer Hub](docs/developer/README.md), then:

```bash
./scripts/validate.sh  # Full validation (lint + typecheck + tests)
```

**Issue tracking:** [Linear](https://linear.app/nemotron-v3-home-security/team/NEM/active)

---

## License

Licensed under **Apache License 2.0**. See [LICENSE](LICENSE).

## Acknowledgments

[Ultralytics YOLO](https://github.com/ultralytics/ultralytics) ·
[Nemotron](https://huggingface.co/nvidia) ·
[llama.cpp](https://github.com/ggerganov/llama.cpp) ·
[FastAPI](https://fastapi.tiangolo.com/) ·
[Tremor](https://www.tremor.so/)
