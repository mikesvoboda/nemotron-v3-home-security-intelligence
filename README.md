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

[![CI](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/mikesvoboda/nemotron-v3-home-security-intelligence/graph/badge.svg)](https://codecov.io/gh/mikesvoboda/nemotron-v3-home-security-intelligence)
[![Backend Coverage](https://img.shields.io/codecov/c/github/mikesvoboda/nemotron-v3-home-security-intelligence?flag=backend-unit&label=backend%20coverage)](https://codecov.io/gh/mikesvoboda/nemotron-v3-home-security-intelligence)
[![Frontend Coverage](https://img.shields.io/codecov/c/github/mikesvoboda/nemotron-v3-home-security-intelligence?flag=frontend&label=frontend%20coverage)](https://codecov.io/gh/mikesvoboda/nemotron-v3-home-security-intelligence)

## Powered by NVIDIA Nemotron

This project showcases **[NVIDIA Nemotron-3-Nano-30B-A3B](https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF)** for intelligent security risk analysis.

- **Model**: Nemotron-3-Nano-30B-A3B (Q4_K_M quantization)
- **Context Window**: 131,072 tokens (128K)
- **VRAM**: ~14.7 GB
- **Purpose**: Analyzes security detections and provides nuanced risk scoring with detailed reasoning

## Why This Matters: AI on Your Hardware

**Millions of people own NVIDIA GPUs that can run advanced AI models locally.** This project proves you don't need cloud APIs or data center hardware to build intelligent systems.

### Nemotron v3 Nano: Big Model, Small Footprint

The brain of this system is [NVIDIA's Nemotron-3-Nano](https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF) — a 30 billion parameter reasoning model that fits on a single workstation GPU:

| Specification        | Value                  | Why It Matters                                       |
| -------------------- | ---------------------- | ---------------------------------------------------- |
| **Parameters**       | 30B (A3B architecture) | State-of-the-art reasoning in a dense model          |
| **Quantization**     | Q4_K_M (4-bit)         | Reduces memory by ~4x with minimal quality loss      |
| **VRAM Required**    | ~18GB                  | Fits on RTX 3090, 4090, A5000, A5500, A6000          |
| **Context Window**   | 128K tokens            | Analyze hours of security context in a single prompt |
| **Inference Engine** | llama.cpp              | Optimized C++ with CUDA acceleration                 |

### Configuration

```yaml
# docker-compose.prod.yml
ai-llm:
  environment:
    - GPU_LAYERS=35 # Offload 35 layers to GPU (adjust for your VRAM)
    - CTX_SIZE=131072 # Full 128K context window
  volumes:
    - /path/to/nemotron-3-nano-30b-a3b-q4km:/models:ro
```

The llama.cpp server runs with:

- `--cont-batching` — Continuous batching for throughput
- `--parallel 1` — Single-slot for dedicated inference
- `--metrics` — Prometheus-compatible monitoring

### What This Enables

With 128K context, Nemotron can reason about:

- **All detections in a time window** — not just the latest frame
- **Historical baselines** — "Is this normal for 3am on a Tuesday?"
- **Cross-camera correlation** — "Same person seen at front door, then garage"
- **Rich enrichment data** — clothing, vehicles, behavior, scene descriptions

All processed locally, with your footage never leaving your network.

> [!TIP] > **Don't have 24GB VRAM?** Reduce `GPU_LAYERS` to offload some layers to CPU RAM, or use a smaller quantization. The system degrades gracefully.

---

## AI Models

| Model               | Purpose                  | HuggingFace                                                                                                   |
| ------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------- |
| Nemotron-3-Nano-30B | Risk reasoning           | [nvidia/Nemotron-3-Nano-30B-A3B-GGUF](https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF)             |
| RT-DETRv2           | Object detection         | [PekingU/rtdetr_r50vd_coco_o365](https://huggingface.co/PekingU/rtdetr_r50vd_coco_o365)                       |
| Florence-2-Large    | Dense captioning         | [microsoft/Florence-2-large](https://huggingface.co/microsoft/Florence-2-large)                               |
| CLIP ViT-L          | Entity re-identification | [openai/clip-vit-large-patch14](https://huggingface.co/openai/clip-vit-large-patch14)                         |
| FashionCLIP         | Clothing analysis        | [patrickjohncyh/fashion-clip](https://huggingface.co/patrickjohncyh/fashion-clip)                             |
| Depth Anything V2   | Depth estimation         | [depth-anything/Depth-Anything-V2-Small-hf](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf) |

---

## System Requirements

### Hardware

| Component      | Minimum               | Recommended       | This Project Uses |
| -------------- | --------------------- | ----------------- | ----------------- |
| **GPU VRAM**   | 12GB (reduced layers) | 24GB              | RTX A5500 (24GB)  |
| **System RAM** | 32GB                  | 64GB+             | 128GB             |
| **Storage**    | 50GB (core models)    | 100GB+ (full zoo) | ~42GB models      |
| **CPU**        | 8 cores               | 16+ cores         | AMD Ryzen 9       |

### GPU Compatibility

Any NVIDIA GPU with sufficient VRAM and CUDA support:

| VRAM     | What You Can Run                    | Example GPUs                        |
| -------- | ----------------------------------- | ----------------------------------- |
| **24GB** | Full stack, all models loaded       | RTX 3090, 4090, A5000, A5500, A6000 |
| **16GB** | Nemotron (reduced layers) + RT-DETR | RTX 4080, A4000, Tesla T4           |
| **12GB** | Nemotron (CPU offload) + RT-DETR    | RTX 3080, 4070 Ti                   |
| **8GB**  | RT-DETR only, no LLM                | RTX 3070, 4060 Ti                   |

### Model Storage Requirements

**Core AI Models (~23GB):**

| Model                      | Size   | Purpose              |
| -------------------------- | ------ | -------------------- |
| Nemotron-3-Nano-30B Q4_K_M | 23 GB  | Risk reasoning (LLM) |
| RT-DETRv2                  | 165 MB | Object detection     |

**Enrichment Model Zoo (~19GB total):**

| Model                  | Size   | Purpose                        |
| ---------------------- | ------ | ------------------------------ |
| CLIP ViT-L             | 6.4 GB | Embeddings / re-identification |
| Fashion-CLIP           | 3.5 GB | Clothing classification        |
| Florence-2-Large       | 3.0 GB | Vision-language captions       |
| Weather Classification | 2.4 GB | Weather/visibility context     |
| X-CLIP Base            | 1.5 GB | Action recognition             |
| Violence Detection     | 656 MB | Violence classifier            |
| YOLO License Plate     | 656 MB | License plate detection        |
| Segformer Clothes      | 523 MB | Clothing segmentation          |
| ViTPose Small          | 127 MB | Pose estimation                |
| Vehicle Damage         | 120 MB | Damage detection               |
| Depth Anything V2      | 95 MB  | Depth estimation               |
| Vehicle Segment        | 91 MB  | Vehicle type classification    |
| Pet Classifier         | 86 MB  | Cat/dog detection              |
| YOLO Face              | 41 MB  | Face detection                 |
| YOLO World             | 25 MB  | Open-vocabulary detection      |
| PaddleOCR              | 12 MB  | Text recognition               |
| OSNet Re-ID            | 2.9 MB | Person re-identification       |

### Container Architecture (9 Services)

![Container Architecture](docs/images/architecture/container-architecture.png)

_Docker/Podman deployment showing all containers with memory allocations, GPU services, and volume mounts._

### Runtime Resource Usage

With all services running on RTX A5500 (24GB):

| Resource       | Usage                                 |
| -------------- | ------------------------------------- |
| **GPU Memory** | ~23 GB / 24 GB                        |
| **System RAM** | ~16 GB                                |
| **Containers** | 9                                     |
| **Open Ports** | 5173 (UI), 8000 (API), 8090-8094 (AI) |

---

## What you get

- **Real-time dashboard**: camera grid, activity feed, risk gauge, telemetry
- **Detections → events (not noise)**: time-window batching turns many frames into one explained "event"
- **AI model zoo enrichment**: optional captions, re-ID, plate/OCR, faces, clothing/vehicle/pet context, image quality/tamper signals
- **Local-first**: runs on your hardware; footage stays on your network

## How it works (at a glance)

![From Camera to Alert](docs/images/info-camera-to-event.png)

### AI Pipeline

![AI Pipeline Flow](docs/images/flow-ai-pipeline.png)

## Documentation (pick your path)

| I want to…                   | Start here                                |
| ---------------------------- | ----------------------------------------- |
| Run this at home             | [User Hub](docs/user/README.md)           |
| Deploy and maintain it       | [Operator Hub](docs/docs/operator/)       |
| Contribute / extend the code | [Developer Hub](docs/developer/README.md) |

If you just need the authoritative env/ports reference, go straight to
[Environment Variable Reference](docs/reference/config/env-reference.md).

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
[AI Installation](docs/operator/ai-installation.md).

```bash
# 1) Run interactive setup (generates .env and docker-compose.override.yml)
./setup.sh              # Quick mode - accept defaults with Enter
# OR
./setup.sh --guided     # Guided mode - step-by-step with explanations

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
# 1) Run interactive setup (generates .env and docker-compose.override.yml)
./setup.sh              # Quick mode - accept defaults with Enter

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

**Source of truth:** [Environment Variable Reference](docs/reference/config/env-reference.md)

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

See [AI Overview](docs/operator/ai-overview.md) and the authoritative ports/env in the
[Environment Variable Reference](docs/reference/config/env-reference.md).

## Security model (read this before exposing it)

This MVP is designed for **single-user, trusted LAN** deployments.

- Authentication is **off by default**
- Rate limiting is **on by default**
- Do **not** expose it to the public internet without hardening

Start here:

- [Admin Security Guide](docs/admin-guide/security.md)

## Contributing

Start with the [Developer Hub](docs/developer/README.md).

```bash
# Full validation (lint + typecheck + tests)
./scripts/validate.sh
```

This project uses **[Linear](https://linear.app/nemotron-v3-home-security)** for task tracking:

- [Active Issues](https://linear.app/nemotron-v3-home-security/team/NEM/active)
- [Project Board](https://linear.app/nemotron-v3-home-security/team/NEM/board)

## License

Licensed under the **Apache License 2.0**. See [LICENSE](LICENSE).

## Acknowledgments

[RT-DETRv2](https://github.com/lyuwenyu/RT-DETR) ·
[Nemotron](https://huggingface.co/nvidia) ·
[llama.cpp](https://github.com/ggerganov/llama.cpp) ·
[FastAPI](https://fastapi.tiangolo.com/) ·
[Tremor](https://www.tremor.so/)
