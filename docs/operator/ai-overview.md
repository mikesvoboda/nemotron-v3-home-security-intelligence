# AI Services Overview

> Understanding the AI inference services that power object detection and risk analysis.

**Time to read:** ~5 min
**Prerequisites:** None

---

## What the AI Does

The AI pipeline transforms raw camera images into risk-scored security events using **core AI services** plus
an **enrichment layer** that adds context (attributes, captions, re-ID, and other signals).

### RT-DETRv2 Detection Server (Port 8090)

**Purpose:** Real-time object detection from camera images

- Identifies security-relevant objects: person, car, truck, dog, cat, bird, bicycle, motorcycle, bus
- Returns bounding boxes with confidence scores (0-100%)
- Processes images in 30-50ms on GPU

**Technology:**

- PyTorch + HuggingFace Transformers (GPU accelerated)
- Typical VRAM usage depends on model + runtime (plan ~3–4GB; see `ai/AGENTS.md`)

### Nemotron LLM Server (Port 8091)

**Purpose:** Risk reasoning and natural language generation

- Analyzes batched detections for context
- Assigns risk scores (0-100) based on what, when, and how
- Generates human-readable summaries and reasoning

**Technology:**

- llama.cpp server with quantized GGUF models
- Model size differs by deployment:
  - Dev/host runs often use Nemotron Mini 4B (low VRAM)
  - Production may run larger models (higher VRAM)

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
|  |  RT-DETRv2       |   |  Nemotron LLM    | |
|  |  Detection       |   |  Risk Analysis   | |
|  |                  |   |                  | |
|  |  Port: 8090      |   |  Port: 8091      | |
|  |  VRAM: ~4GB      |   |  VRAM: ~3GB      | |
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
```

## Resource Requirements

VRAM depends heavily on which services/models are enabled.

| Profile                  | Typical VRAM | Notes                                               |
| ------------------------ | ------------ | --------------------------------------------------- |
| **Minimal (dev)**        | ~8–12GB      | RT-DETRv2 + Nemotron Mini 4B                        |
| **Full AI stack (prod)** | ~22GB        | RT-DETRv2 + Nemotron + Florence + CLIP + Enrichment |

## Deployment Model

AI services can run either:

- **Fully containerized** (recommended for production): see `docker-compose.prod.yml`
- **Host-run** (useful for development): see `scripts/start-ai.sh`

**Production:** All AI services containerized in `docker-compose.prod.yml`
**Development:** AI services can run natively on host for easier debugging

## Service Endpoints

| Service    | Endpoint      | Method | Purpose                     |
| ---------- | ------------- | ------ | --------------------------- |
| RT-DETRv2  | `/health`     | GET    | Health check                |
| RT-DETRv2  | `/detect`     | POST   | Object detection (image)    |
| Nemotron   | `/health`     | GET    | Health check                |
| Nemotron   | `/completion` | POST   | Risk analysis (JSON prompt) |
| Florence-2 | `/health`     | GET    | Health check                |
| CLIP       | `/health`     | GET    | Health check                |
| Enrichment | `/health`     | GET    | Health check                |

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

[Back to Operator Hub](../operator-hub.md)
