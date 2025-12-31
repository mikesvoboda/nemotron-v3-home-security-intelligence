# Home Security Intelligence

> Turn dumb security cameras into an intelligent threat detection system -- **100% local, no cloud APIs required.**

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
[![Backend Coverage](https://img.shields.io/badge/backend_coverage-%E2%89%A595%25-brightgreen.svg)]()
[![Frontend Coverage](https://img.shields.io/badge/frontend_coverage-%E2%89%A589%25-brightgreen.svg)]()

---

## What It Does

- **Camera uploads** (FTP) **->** **AI detection** (RT-DETRv2) **->** **Risk scoring** (Nemotron LLM)
- **100% local**: Your footage never leaves your network
- **Real-time dashboard**: Live events, risk gauge, camera grid

---

## Documentation

> **Pick your path based on what you want to do:**

| I want to...                  | Go here                                |
| ----------------------------- | -------------------------------------- |
| **Run this at home**          | [User Hub](docs/user-hub.md)           |
| **Deploy and maintain this**  | [Operator Hub](docs/operator-hub.md)   |
| **Contribute or extend this** | [Developer Hub](docs/developer-hub.md) |

---

## Quick Start

Choose your deployment path:

### Option A: Production (Recommended)

All services run in containers, including GPU-accelerated AI. Requires NVIDIA GPU with `nvidia-container-toolkit`.

```bash
# 1. Setup environment
./scripts/setup-hooks.sh

# 2. Download AI models (~10GB)
./ai/download_models.sh

# 3. Launch everything (AI + backend + frontend)
docker compose -f docker-compose.prod.yml up -d
# OR with Podman:
# podman-compose -f docker-compose.prod.yml up -d
```

**Open [http://localhost:5173](http://localhost:5173)** -- that's it.

### Option B: Development (Host AI)

AI servers run natively on the host for faster iteration. Backend and frontend run in containers.

```bash
# 1. Setup environment
./scripts/setup-hooks.sh

# 2. Download AI models (~10GB)
./ai/download_models.sh

# 3. Start AI servers on host (separate terminals)
./ai/start_detector.sh    # RT-DETRv2 on :8090
./ai/start_llm.sh         # Nemotron on :8091

# 4. Set AI host for container networking (if needed)
export AI_HOST=host.docker.internal     # Docker on Linux/macOS
# OR
export AI_HOST=host.containers.internal # Podman on macOS

# 5. Launch app containers (no AI services)
docker compose up -d
# OR with Podman:
# podman-compose up -d
```

**Open [http://localhost:5173](http://localhost:5173)**

> **Note:** Do NOT mix host AI servers with `docker-compose.prod.yml` -- this causes port conflicts on 8090/8091.

For detailed deployment guidance, see the [Operator Hub](docs/operator-hub.md).

---

## Key Features

| Feature                 | Description                               |
| ----------------------- | ----------------------------------------- |
| **AI Risk Scoring**     | 0-100 scores with LLM-generated reasoning |
| **Real-time Dashboard** | Live event feed, risk gauge, camera grid  |
| **Event Timeline**      | Filter by camera, risk level, date range  |

---

## Tech Stack

|                |                                            |
| -------------- | ------------------------------------------ |
| **Detection**  | RT-DETRv2 (30-50ms/image)                  |
| **Analysis**   | Nemotron via llama.cpp (4B dev / 30B prod) |
| **Storage**    | PostgreSQL + 30-day retention              |
| **Interface**  | React + Tailwind + Tremor                  |
| **Target GPU** | NVIDIA RTX (8GB+ VRAM)                     |

---

## Security

**Designed for local/trusted network use.** No authentication by default (single-user assumption).

Do not expose to the internet without adding authentication and hardening.

---

## Contributing

See the [Developer Hub](docs/developer-hub.md) for architecture, testing, and contribution guidelines.

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

[RT-DETRv2](https://github.com/lyuwenyu/RT-DETR) | [Nemotron](https://huggingface.co/nvidia) | [llama.cpp](https://github.com/ggerganov/llama.cpp) | [FastAPI](https://fastapi.tiangolo.com/) | [Tremor](https://www.tremor.so/)
