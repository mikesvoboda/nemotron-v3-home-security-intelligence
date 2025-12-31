# AI Services Overview

> Understanding the AI inference services that power object detection and risk analysis.

**Time to read:** ~5 min
**Prerequisites:** None

---

## What the AI Does

The AI pipeline transforms raw camera images into risk-scored security events through two specialized services:

### RT-DETRv2 Detection Server (Port 8090)

**Purpose:** Real-time object detection from camera images

- Identifies security-relevant objects: person, car, truck, dog, cat, bird, bicycle, motorcycle, bus
- Returns bounding boxes with confidence scores (0-100%)
- Processes images in 30-50ms on GPU

**Technology:**

- ONNX Runtime with CUDA acceleration
- ~4GB VRAM usage
- HuggingFace Transformers model

### Nemotron LLM Server (Port 8091)

**Purpose:** Risk reasoning and natural language generation

- Analyzes batched detections for context
- Assigns risk scores (0-100) based on what, when, and how
- Generates human-readable summaries and reasoning

**Technology:**

- llama.cpp with quantized GGUF model
- Nemotron Mini 4B Q4_K_M quantization
- ~3GB VRAM usage
- 2-5 seconds per risk analysis

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

| Resource       | Minimum | Recommended |
| -------------- | ------- | ----------- |
| **Total VRAM** | ~7GB    | 12GB+       |
| **RT-DETRv2**  | ~4GB    | ~4GB        |
| **Nemotron**   | ~3GB    | ~3GB        |
| **CUDA**       | 11.8+   | 12.x        |

## Deployment Model

Both services run in **OCI containers** (Docker or Podman) with NVIDIA GPU passthrough via Container Device Interface (CDI).

**Production:** All AI services containerized in `docker-compose.prod.yml`
**Development:** AI services can run natively on host for easier debugging

## Service Endpoints

| Service   | Endpoint      | Method | Purpose                     |
| --------- | ------------- | ------ | --------------------------- |
| RT-DETRv2 | `/health`     | GET    | Health check                |
| RT-DETRv2 | `/detect`     | POST   | Object detection (image)    |
| Nemotron  | `/health`     | GET    | Health check                |
| Nemotron  | `/completion` | POST   | Risk analysis (JSON prompt) |

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
