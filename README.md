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
[![Node 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61dafb.svg)](https://react.dev/)
[![Backend Coverage](https://img.shields.io/badge/backend_coverage-98%25-brightgreen.svg)]()
[![Frontend Coverage](https://img.shields.io/badge/frontend_coverage-99%25-brightgreen.svg)]()

---

## What It Does

- **Camera uploads** (FTP) **->** **AI detection** (RT-DETRv2) **->** **Risk scoring** (Nemotron LLM)
- **100% local**: Your footage never leaves your network
- **Real-time dashboard**: Live events, risk gauge, camera grid

---

## Quick Start (60 seconds)

```bash
# 1. Setup environment and dependencies
./scripts/setup-hooks.sh

# 2. Download AI models (~10GB)
./ai/download_models.sh

# 3. Start AI servers (separate terminals)
./ai/start_detector.sh    # RT-DETRv2 on :8090
./ai/start_llm.sh         # Nemotron on :8091

# 4. Launch the app
podman-compose -f docker-compose.prod.yml up -d
```

**Open [http://localhost](http://localhost)** -- that's it.

> **macOS with Podman?** Set `export AI_HOST=host.containers.internal` first.

---

## Key Features

| Feature                 | Description                               | Docs                                                |
| ----------------------- | ----------------------------------------- | --------------------------------------------------- |
| **AI Risk Scoring**     | 0-100 scores with LLM-generated reasoning | [Architecture](docs/architecture/ai-pipeline.md)    |
| **Real-time Dashboard** | Live event feed, risk gauge, camera grid  | [User Guide](docs/user-guide/dashboard-overview.md) |
| **Event Timeline**      | Filter by camera, risk level, date range  | [User Guide](docs/user-guide/event-timeline.md)     |

---

## Tech Stack

|                |                                |
| -------------- | ------------------------------ |
| **Detection**  | RT-DETRv2 (30-50ms/image)      |
| **Analysis**   | Nemotron Mini 4B via llama.cpp |
| **Storage**    | PostgreSQL + 30-day retention  |
| **Interface**  | React + Tailwind + Tremor      |
| **Target GPU** | NVIDIA RTX (8GB+ VRAM)         |

---

## Documentation

> **[Full Documentation](docs/README.md)** -- Comprehensive guides for all audiences.

| Audience            | Start Here                                                                                                                                                       |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Getting Started** | [Prerequisites](docs/getting-started/prerequisites.md) -> [Installation](docs/getting-started/installation.md) -> [First Run](docs/getting-started/first-run.md) |
| **End Users**       | [Dashboard Overview](docs/user-guide/dashboard-overview.md)                                                                                                      |
| **Administrators**  | [Configuration](docs/admin-guide/configuration.md)                                                                                                               |
| **Developers**      | [Architecture Overview](docs/architecture/overview.md)                                                                                                           |

---

## Security

**Designed for local/trusted network use.** No authentication by default (single-user assumption).

Do not expose to the internet without adding authentication and hardening.

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

[RT-DETRv2](https://github.com/lyuwenyu/RT-DETR) | [Nemotron](https://huggingface.co/nvidia) | [llama.cpp](https://github.com/ggerganov/llama.cpp) | [FastAPI](https://fastapi.tiangolo.com/) | [Tremor](https://www.tremor.so/)
