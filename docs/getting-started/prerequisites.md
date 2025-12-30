---
title: Prerequisites
description: Hardware and software requirements for Home Security Intelligence
source_refs:
  - pyproject.toml:5
  - frontend/package.json:32
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

| Requirement            | Minimum | Recommended |
| ---------------------- | ------- | ----------- |
| **VRAM**               | 8GB     | 12GB+       |
| **CUDA Compute**       | 7.0+    | 8.0+        |
| **Combined AI Memory** | ~6GB    | ~6GB        |

The system runs two AI models simultaneously:

- **RT-DETRv2** (object detection): ~4GB VRAM ([`ai/start_detector.sh:6-7`](../../ai/start_detector.sh:6))
- **Nemotron Mini 4B** (risk analysis): ~3GB VRAM ([`ai/start_llm.sh:6-7`](../../ai/start_llm.sh:6))

**Supported GPUs:**

- NVIDIA RTX 30-series (3060 and above)
- NVIDIA RTX 40-series (any)
- NVIDIA RTX A-series (A2000 and above)
- NVIDIA Tesla/Quadro with 8GB+ VRAM

### CPU & Memory

| Component   | Minimum | Recommended |
| ----------- | ------- | ----------- |
| **CPU**     | 4 cores | 8+ cores    |
| **RAM**     | 8GB     | 16GB+       |
| **Storage** | 50GB    | 100GB+ SSD  |

> **Note:** Storage requirements increase with camera count and retention period. Plan for ~1GB/day per active camera.

### Network

- Cameras must be able to FTP upload to the server
- Local network access (no internet required after setup)
- Default ports: 80 (web), 8000 (API), 8090 (detection), 8091 (LLM)

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

| Requirement | Version                                              |
| ----------- | ---------------------------------------------------- |
| **Python**  | 3.14+ ([`pyproject.toml:5`](../../pyproject.toml:5)) |

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

| Requirement | Version                                                            |
| ----------- | ------------------------------------------------------------------ |
| **Node.js** | 18+ ([`frontend/package.json:32`](../../frontend/package.json:32)) |
| **npm**     | 9+                                                                 |

```bash
# Verify Node version
node --version
# v18.x.x or higher
```

**Installation:**

```bash
# Ubuntu/Debian (via NodeSource)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs

# macOS (via Homebrew)
brew install node@20
```

### Container Runtime

This project uses **Podman** (not Docker) for container management.

| Runtime            | Version |
| ------------------ | ------- |
| **Podman**         | 4.0+    |
| **podman-compose** | 1.0+    |

```bash
# Verify Podman
podman --version
podman-compose --version
```

**Installation:**

```bash
# Ubuntu/Debian
sudo apt install podman podman-compose

# macOS (via Homebrew)
brew install podman podman-compose
podman machine init
podman machine start
```

### llama.cpp

Required for running the Nemotron LLM server.

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

# Podman
podman --version && podman-compose --version

# llama.cpp
which llama-server
```

Expected output:

```
NVIDIA-SMI 535.xxx  Driver Version: 535.xxx  CUDA Version: 12.x
Python 3.14.x
v20.x.x
9.x.x
podman version 4.x.x
podman-compose version 1.x.x
/usr/local/bin/llama-server
```

---

## Next Steps

Once all prerequisites are met, proceed to:

**[Installation](installation.md)** - Set up the environment and download models.
