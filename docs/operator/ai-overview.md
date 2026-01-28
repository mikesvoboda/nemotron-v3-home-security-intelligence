# AI Services Overview

> Understanding the AI inference services that power object detection and risk analysis.

**Time to read:** ~5 min
**Prerequisites:** None

---

## What the AI Does

The AI pipeline transforms raw camera images into risk-scored security events using **core AI services** plus
an **enrichment layer** that adds context (attributes, captions, re-ID, and other signals).

### YOLO26 Detection Server (Port 8095)

**Purpose:** Real-time object detection from camera images

- Identifies security-relevant objects: person, car, truck, dog, cat, bird, bicycle, motorcycle, bus
- Returns bounding boxes with confidence scores (0-100%)
- Processes images in 30-50ms on GPU

**Technology:**

- PyTorch + HuggingFace Transformers (GPU accelerated)
- Typical VRAM usage depends on model + runtime (plan ~3-4GB; see `ai/AGENTS.md`)

### NVIDIA Nemotron LLM Server (Port 8091)

**Purpose:** Risk reasoning and natural language generation

- Analyzes batched detections for context
- Assigns risk scores (0-100) based on what, when, and how
- Generates human-readable summaries and reasoning

**Technology:**

- llama.cpp server with NVIDIA Nemotron GGUF models
- ChatML format with `<|im_start|>` / `<|im_end|>` message delimiters
- Model options by deployment:

| Deployment      | Model                                                                                        | VRAM     | Context |
| --------------- | -------------------------------------------------------------------------------------------- | -------- | ------- |
| **Production**  | [NVIDIA Nemotron-3-Nano-30B-A3B](https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF) | ~14.7 GB | 128K    |
| **Development** | [Nemotron Mini 4B Instruct](https://huggingface.co/bartowski/nemotron-mini-4b-instruct-GGUF) | ~3 GB    | 4K      |

The production 30B model with 128K context enables:

- Analyzing all detections across extended time windows (hours of activity)
- Rich historical baseline comparisons
- Cross-camera activity correlation in a single prompt

## Enrichment Services (Ports 8092–8094)

In production deployments, the system can run additional AI services:

- **Florence-2 (8092)**: vision-language extraction (captions/attributes)
- **CLIP (8093)**: embeddings and re-identification support
- **Enrichment service (8094)**: vehicle/pet/clothing/etc. helpers

These services feed into the backend’s enrichment pipeline and ultimately improve the context sent to the LLM.

> [!NOTE]
> The backend also has a “model zoo” that can run additional enrichment steps on demand (and/or delegate to
> `ai-enrichment` depending on configuration).

## Architecture Diagram

```
+----------------------------------------------+
|              AI Pipeline Services             |
+----------------------------------------------+
|                                              |
|  +------------------+   +------------------+ |
|  |  YOLO26       |   |  NVIDIA Nemotron | |
|  |  Detection       |   |  Risk Analysis   | |
|  |                  |   |                  | |
|  |  Port: 8095      |   |  Port: 8091      | |
|  |  VRAM: ~4GB      |   |  VRAM: 3-15GB*   | |
|  |  Latency: 30-50ms|   |  Latency: 2-5s   | |
|  +------------------+   +------------------+ |
|         ^                       ^            |
|         |                       |            |
|         | POST /detect          | POST       |
|         | (multipart)           | /completion|
+----------------------------------------------+
          |                       |
    +-----+------+         +------+------+
    | Detector   |         | Nemotron    |
    | Client     |         | Analyzer    |
    | (FastAPI)  |         | (FastAPI)   |
    +------------+         +-------------+

* Nemotron VRAM: ~3GB (4B dev) or ~14.7GB (30B production)
```

## Resource Requirements

VRAM depends heavily on which services/models are enabled.

| Profile                  | Typical VRAM | Notes                                                 |
| ------------------------ | ------------ | ----------------------------------------------------- |
| **Minimal (dev)**        | ~8-12GB      | YOLO26 (~4GB) + Nemotron Mini 4B (~3GB)               |
| **Full AI stack (prod)** | ~22-24GB     | YOLO26 + Nemotron 30B (~14.7GB) + Enrichment services |

**Production Breakdown (24GB GPU):**

- YOLO26: ~4GB
- NVIDIA Nemotron-3-Nano-30B-A3B (Q4_K_M): ~14.7GB
- Florence-2 / CLIP / Enrichment: ~4-5GB shared

## Deployment Model

AI services can run either:

- **Fully containerized** (recommended for production): see `docker-compose.prod.yml`
- **Host-run** (useful for development): see `scripts/start-ai.sh`

**Production:** All AI services containerized in `docker-compose.prod.yml`
**Development:** AI services can run natively on host for easier debugging

## Service Endpoints

| Service         | Endpoint      | Method | Purpose                              |
| --------------- | ------------- | ------ | ------------------------------------ |
| YOLO26          | `/health`     | GET    | Health check                         |
| YOLO26          | `/detect`     | POST   | Object detection (image)             |
| NVIDIA Nemotron | `/health`     | GET    | Health check                         |
| NVIDIA Nemotron | `/completion` | POST   | Risk analysis (ChatML prompt + JSON) |
| Florence-2      | `/health`     | GET    | Health check                         |
| CLIP            | `/health`     | GET    | Health check                         |
| Enrichment      | `/health`     | GET    | Health check                         |

---

## Next Steps

- [AI Installation](ai-installation.md) - Set up prerequisites and dependencies
- [AI Configuration](ai-configuration.md) - Configure environment variables
- [AI Services](ai-services.md) - Starting, stopping, verifying services

---

## See Also

- [GPU Setup](gpu-setup.md) - GPU drivers and container access
- [Pipeline Overview](../developer/pipeline-overview.md) - How images flow through AI services
- [Risk Levels Reference](../reference/config/risk-levels.md) - How risk scores are interpreted
- [AI Troubleshooting](ai-troubleshooting.md) - Common issues and solutions

---

[Back to Operator Hub](./)
