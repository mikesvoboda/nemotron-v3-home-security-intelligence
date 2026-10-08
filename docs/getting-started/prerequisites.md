---
title: Prerequisites
description: Hardware and software requirements for Home Security Intelligence
source_refs:
  - pyproject.toml:5
  - frontend/package.json:6-8
  - ai/start_detector.sh:6-7
  - docker-compose.prod.yml:162-163
  - setup_lib/nvidia_detect.py:38
---

# Prerequisites

Before installing Home Security Intelligence, ensure your system meets the following requirements.

<!-- Nano Banana Pro Prompt:
"Technical illustration of GPU server hardware with NVIDIA graphics card,
dark background #121212, NVIDIA green #76B900 accent lighting,
clean minimalist style, vertical 2:3 aspect ratio,
no text overlays"
-->

---

## Hardware Requirements

### GPU (Required)

How much VRAM you need depends on which models you want running:

Two containers hold GPU memory, and each has its own knob:

| Card  | What Fits                                                               | Example GPUs                        |
| ----- | ----------------------------------------------------------------------- | ----------------------------------- |
| 24 GB | `ai-vlm` with its whole model on GPU, plus `ai-gateway` on its own card | RTX 3090, 4090, A5000, A5500, A6000 |
| 16 GB | `ai-vlm` on one card with the gateway on the other, tighter KV budget   | RTX 4080, A4000                     |
| 8 GB  | `ai-vlm` partly in system RAM and a slower verdict on the same card     | RTX 3070, 4060 Ti                   |

- **NVIDIA CUDA capability** 7.0 or newer (Volta and later), on a **driver 580 or newer** — `setup.py` stops below that floor because the `ai-vlm` image is built on CUDA 13.1 (`setup_lib/nvidia_detect.py:38`).
- The shipped weight pair is `Qwen3VL-8B-Instruct-Q4_K_M.gguf` (5,027,784,800 B) plus its `mmproj-…-Q8_0.gguf` projector (752,289,728 B), and identity is config — swap `VLM_MODEL_PATH` / `VLM_MMPROJ_PATH` and the footprint changes with your choice (`docker-compose.prod.yml:232-233`).
- The other thing the serve reserves is the KV cache pool: **4 608 MiB** of f16 cache for the shipped `VLM_CTX_SIZE=32768` × `VLM_PARALLEL=2` geometry, and the default `q8_0` key/value types run that pool at about half. Lower `VLM_CTX_SIZE` or `VLM_PARALLEL` to shrink it (see [VRAM Budget](../reference/nvidia-technology-inventory.md#vram-budget)).
- `ai-gateway` runs Triton with FP32 ONNX models and declares a 256 MB CUDA memory pool at startup (`ai/gateway/entrypoint.sh:153`).
- `VLM_GPU_LAYERS` (compose passes it as `GPU_LAYERS`) defaults to `auto`, which fits layers to the free VRAM the serve finds; a fixed count in `.env` overrides that fit.
- The face, plate and person-re-ID lookups are CPU ONNX and cost no VRAM either way.

**Supported GPUs:** NVIDIA RTX 30-series and newer, RTX A-series, and Tesla/Quadro cards with CUDA support. Risk scoring is what the VLM produces — there is no run mode without it, so on a small card expect a slower verdict (`GPU_LAYERS` set below `auto` spills layers into system RAM) rather than a degraded mode.

### CPU & Memory

| Component   | Minimum            | Recommended           |
| ----------- | ------------------ | --------------------- |
| **CPU**     | 4 cores            | 8+ cores              |
| **RAM**     | 16GB               | 32GB+                 |
| **Storage** | 50GB (core models) | 100GB+ SSD (full zoo) |

> **Note:** `models.yml` carries ten rows, and the `setup_lib` download rule selects five artifacts from it — `yolo26`, `osnet-ain-x1-0`, `threat-detection-yolov8n`, `yolo11-face` and `yolo11-license-plate`, ~1.5 GB together. The rest of the inventory arrives another way: the face leg's two ONNX files are unpacked from `buffalo_l.zip` by hand, `fast-alpr` and `paddleocr` fetch at runtime, and the VLM weights are host-mounted (see [Models Reference](../reference/models.md#model-download)). Storage for events grows with camera count and retention period — plan for ~1GB/day per active camera.

> **Sizing note:** `docker-compose.prod.yml` declares 21 services and caps 19 of
> them with `deploy.resources.limits`; the 18 of those that start with a plain
> `up -d` sum to ~26 CPUs and ~47 GB of _ceilings_ (`ai-gateway` 8 CPU/20G, `ai-vlm`
> 4 CPU/10G and `backend` 2 CPU/10G dominate). Those are host RAM ceilings, not
> reservations and not VRAM. The minimums above are the floor for a core-services
> run; the monitoring stack (`prometheus`, `loki`, `grafana`, `tempo`,
> `pyroscope` and the exporters) accounts for most of the rest.

### Network

- Cameras must be able to FTP upload to the server
- Local network access (no internet required after setup)
- Default ports (all configurable in `.env`): **8080** dashboard HTTP, **8444** dashboard HTTPS, **8000** API, **8090** AI gateway, **8098** `ai-vlm`, **5432** PostgreSQL, **6379** Redis, **3002** Grafana. Everything except the dashboard binds to `127.0.0.1` only.

---

## Software Requirements

### Operating System

| OS          | Version       | Status                 |
| ----------- | ------------- | ---------------------- |
| **Ubuntu**  | 22.04 LTS     | Fully Supported        |
| **Debian**  | 12+           | Supported              |
| **macOS**   | 13+ (Ventura) | Supported (via Podman) |
| **Windows** | WSL2          | Experimental           |

### NVIDIA Drivers & CUDA

```bash
# Verify NVIDIA driver
nvidia-smi

# Required output should show:
# - Driver Version: 580+  (setup.py refuses to proceed below this)
# - CUDA Version: 13.x
```

**Installation guides:**

- Ubuntu: [NVIDIA CUDA Installation Guide](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/)
- macOS: CUDA not available; use [MPS backend](https://developer.apple.com/metal/pytorch/)

### Python

| Requirement | Version                                                                                                                         |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Python**  | 3.14+ ([`pyproject.toml:5`](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/blob/main/pyproject.toml#L5)) |

```bash
# Verify Python version
python3 --version
# Python 3.14.x
```

**Installation:**

```bash
# Ubuntu/Debian
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.14 python3.14-venv python3.14-dev

# macOS (via Homebrew)
brew install python@3.14
```

### Node.js

| Requirement | Version                                                                                                                                                     |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Node.js** | 24 LTS (22.12+ accepted) ([`frontend/package.json`](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/blob/main/frontend/package.json)) |
| **npm**     | 10+                                                                                                                                                         |

> **Note:** Vite 7 requires Node.js 24 LTS, 22.12+ accepted for native ESM support. Node.js 18 is NOT supported.

```bash
# Verify Node version
node --version
# v24.x LTS
```

**Installation:**

```bash
# Ubuntu/Debian (via NodeSource)
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt install nodejs

# macOS (via Homebrew)
brew install node@24
```

### Container Runtime

This project supports **both Docker and Podman**. Choose whichever is available on your system.

| Runtime            | Version | License                          |
| ------------------ | ------- | -------------------------------- |
| **Docker Engine**  | 20.10+  | Free (Linux)                     |
| **Docker Desktop** | 4.0+    | Paid (commercial >250 employees) |
| **Podman**         | 4.0+    | Free (Apache 2.0)                |
| **docker-compose** | 2.0+    | Included with Docker             |
| **podman-compose** | 1.0+    | Separate install                 |

```bash
# Verify Docker
docker --version
docker compose version

# OR verify Podman
podman --version
podman-compose --version
```

**Installation:**

<details>
<summary><strong>Docker Installation</strong></summary>

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install docker.io docker-compose-v2
sudo usermod -aG docker $USER  # Log out and back in

# macOS (Docker Desktop)
# Download from https://www.docker.com/products/docker-desktop
```

</details>

<details>
<summary><strong>Podman Installation</strong></summary>

```bash
# Ubuntu/Debian
sudo apt install podman podman-compose

# Fedora/RHEL
sudo dnf install podman podman-compose

# macOS (via Homebrew)
brew install podman podman-compose
podman machine init
podman machine start
```

</details>

> **macOS Note (host-run AI only):** There is no `AI_HOST` variable — the backend reaches AI services through URL variables. Only the detector has a host-run server to start (`./ai/start_detector.sh`); if it runs on the host, point `YOLO26_URL` (in `.env`) at `http://host.docker.internal:8090/yolo26` for Docker Desktop or `http://host.containers.internal:8090/yolo26` for Podman. A fully containerized deployment needs no host access at all.

### llama.cpp

Nothing on the host needs llama.cpp: the `ai-vlm` container builds `llama-server` from source with `-DGGML_CUDA=ON` (`ai/vlm/Dockerfile:74-76`) and runs it on the GGUF pair you mount. Bring the library only if you want to run a serve by hand outside compose.

```bash
# The shipped serve answers on its own health endpoint (no profile flag needed)
docker compose -f docker-compose.prod.yml exec -T ai-vlm \
  curl -s localhost:8098/health
```

---

## Verification Checklist

Run these commands to verify all prerequisites:

```bash
# GPU
nvidia-smi | head -5

# Python
python3 --version

# Node.js
node --version && npm --version

# Container runtime (choose one)
docker --version && docker compose version   # Docker
# OR
podman --version && podman-compose --version  # Podman

```

Expected output (Docker example):

```
NVIDIA-SMI 580.xxx  Driver Version: 580.xxx  CUDA Version: 13.x
Python 3.14.x
v24.x (or 22.12.x+)
10.x.x
Docker version 24.x.x
Docker Compose version v2.x.x
```

Expected output (Podman example):

```
NVIDIA-SMI 580.xxx  Driver Version: 580.xxx  CUDA Version: 13.x
Python 3.14.x
v24.x (or 22.12.x+)
10.x.x
podman version 4.x.x
podman-compose version 1.x.x
```

---

## Next Steps

Once all prerequisites are met, proceed to:

**[Installation](installation.md)** - Set up the environment and download models.
