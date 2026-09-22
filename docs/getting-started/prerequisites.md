---
title: Prerequisites
description: Hardware and software requirements for Home Security Intelligence
source_refs:
  - pyproject.toml:5
  - frontend/package.json:6-8
  - ai/start_detector.sh:6-7
  - ai/start_llm.sh:6-7
  - docker-compose.prod.yml:18-19
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

| VRAM       | What You Can Run                                                          | Example GPUs                        |
| ---------- | ------------------------------------------------------------------------- | ----------------------------------- |
| **24GB**   | Full stack, all models loaded                                             | RTX 3090, 4090, A5000, A5500, A6000 |
| **16GB**   | Nemotron (reduced layers) + YOLO26                                        | RTX 4080, A4000, Tesla T4           |
| **8–12GB** | Nemotron partially offloaded via `GPU_LAYERS` (slow), YOLO26 + embeddings | RTX 3070, 4060 Ti, RTX 3080         |

- **NVIDIA CUDA capability** 7.0 or newer (Volta and later).
- The production LLM is **Nemotron-3-Nano-30B** at Q4_K_M: a ~14.7GB GGUF file, roughly 21GB resident when fully on GPU. On smaller cards, reduce `GPU_LAYERS` to offload layers to system RAM (see [Multi-GPU guide](../development/multi-gpu.md)) — the system degrades gracefully.
- **YOLO26 + the gateway models** (Triton, on-demand loading) add several GB on top; with the full stack the measured footprint is ~23GB of a 24GB card.

**Supported GPUs:** NVIDIA RTX 30-series and newer, RTX A-series, and Tesla/Quadro cards with CUDA support. Below ~16GB set `GPU_LAYERS` below `auto` so part of the LLM spills into system RAM — analysis gets slow, but the LLM still runs (risk scoring is LLM-determined; there is no run mode without it).

### CPU & Memory

| Component   | Minimum            | Recommended           |
| ----------- | ------------------ | --------------------- |
| **CPU**     | 4 cores            | 8+ cores              |
| **RAM**     | 16GB               | 32GB+                 |
| **Storage** | 50GB (core models) | 100GB+ SSD (full zoo) |

> **Note:** The AI model zoo is ~42GB if you download everything. Storage for events grows with camera count and retention period — plan for ~1GB/day per active camera.

> **Sizing note:** `docker-compose.prod.yml` caps its 19 default services with
> `deploy.resources.limits` summing to ~25 CPUs and ~49GB memory of _ceilings_
> (ai-gateway 8 CPU/20G, ai-llm 4 CPU/12G, backend 2 CPU/10G dominate) — a busy
> full-stack box comfortably uses 32GB+, and measured steady-state usage on a
> production host is ~16GB system RAM. The minimums above are the floor for a
> core-services-only run, matching the rest of the docs.

### Network

- Cameras must be able to FTP upload to the server
- Local network access (no internet required after setup)
- Default ports (all configurable in `.env`): **8080** dashboard HTTP, **8444** dashboard HTTPS, **8000** API, **8090** AI gateway, **8091** Nemotron LLM, **5432** PostgreSQL, **6379** Redis, **3002** Grafana. Everything except the dashboard binds to `127.0.0.1` only.

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
# - Driver Version: 535+
# - CUDA Version: 12.0+
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

> **macOS Note (host-run AI only):** There is no `AI_HOST` variable — the backend reaches AI services through URL variables. If AI servers run on the host, point `YOLO26_URL`/`NEMOTRON_URL` (in `.env`) at `http://host.docker.internal:<port>` for Docker Desktop or `http://host.containers.internal:<port>` for Podman. A fully containerized deployment needs no host access at all.

### llama.cpp

Required **only** if you run the Nemotron server on the host (`./ai/start_llm.sh`, Development Mode). In Production Mode the `ai-llm` container bundles its own llama.cpp build.

```bash
# Verify llama-server is available
llama-server --version
```

**Installation:**

```bash
# Build from source (recommended for GPU support)
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make LLAMA_CUDA=1  # For NVIDIA GPU support

# Add to PATH
export PATH="$PATH:$(pwd)"
```

> **Alternative:** Pre-built binaries available at [llama.cpp releases](https://github.com/ggerganov/llama.cpp/releases).

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

# llama.cpp (only needed for host-run AI, Development Mode)
which llama-server
```

Expected output (Docker example):

```
NVIDIA-SMI 535.xxx  Driver Version: 535.xxx  CUDA Version: 12.x
Python 3.14.x
v24.x (or 22.12.x+)
10.x.x
Docker version 24.x.x
Docker Compose version v2.x.x
/usr/local/bin/llama-server
```

Expected output (Podman example):

```
NVIDIA-SMI 535.xxx  Driver Version: 535.xxx  CUDA Version: 12.x
Python 3.14.x
v24.x (or 22.12.x+)
10.x.x
podman version 4.x.x
podman-compose version 1.x.x
/usr/local/bin/llama-server
```

---

## Next Steps

Once all prerequisites are met, proceed to:

**[Installation](installation.md)** - Set up the environment and download models.
