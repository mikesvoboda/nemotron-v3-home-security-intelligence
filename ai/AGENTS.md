# AI Pipeline Directory

## Purpose

Contains AI inference services for home security monitoring. This directory houses multiple containerized HTTP servers that provide GPU-accelerated AI capabilities:

1. **RT-DETRv2** - Object detection (people, vehicles, animals)
2. **Nemotron** - LLM risk reasoning and analysis
3. **CLIP** - Entity re-identification via embeddings
4. **Florence-2** - Vision-language attribute extraction
5. **Enrichment** - Combined classification service (vehicle, pet, clothing, depth, pose)

All services run as FastAPI HTTP servers with GPU passthrough via Docker/Podman.

## Directory Structure

```
ai/
├── AGENTS.md              # This file
├── rtdetr/                # RT-DETRv2 object detection server
│   ├── AGENTS.md          # RT-DETRv2 documentation
│   ├── Dockerfile         # Container build (PyTorch + CUDA)
│   ├── model.py           # FastAPI server (HuggingFace Transformers)
│   ├── example_client.py  # Python client example
│   ├── test_model.py      # Unit tests (pytest)
│   ├── requirements.txt   # Python dependencies
│   ├── README.md          # Usage documentation
│   └── __init__.py        # Package init (version 1.0.0)
├── nemotron/              # Nemotron LLM model files
│   ├── AGENTS.md          # Nemotron documentation
│   ├── Dockerfile         # Multi-stage build for llama.cpp
│   └── config.json        # llama.cpp config reference
├── clip/                  # CLIP embedding server
│   ├── AGENTS.md          # CLIP documentation
│   ├── Dockerfile         # Container build
│   ├── model.py           # FastAPI server for embeddings
│   └── requirements.txt   # Python dependencies
├── florence/              # Florence-2 vision-language server
│   ├── AGENTS.md          # Florence-2 documentation
│   ├── Dockerfile         # Container build
│   ├── model.py           # FastAPI server for attribute extraction
│   └── requirements.txt   # Python dependencies
├── enrichment/            # Combined enrichment service
│   ├── AGENTS.md          # Enrichment documentation
│   ├── Dockerfile         # Container build
│   ├── model.py           # FastAPI server with multiple classifiers
│   ├── vitpose.py         # ViTPose+ pose estimation module
│   └── requirements.txt   # Python dependencies
├── download_models.sh     # Download AI models
├── start_detector.sh      # Start RT-DETRv2 (port 8090)
├── start_llm.sh           # Start Nemotron 4B (port 8091)
└── start_nemotron.sh      # Start Nemotron 30B with auto-recovery
```

## Service Overview

| Service    | Port | VRAM     | Framework           | Purpose                         |
| ---------- | ---- | -------- | ------------------- | ------------------------------- |
| RT-DETRv2  | 8090 | ~650 MiB | HuggingFace         | Object detection                |
| Nemotron   | 8091 | ~14.7 GB | llama.cpp           | Risk reasoning                  |
| Florence-2 | 8092 | ~1.2 GB  | HuggingFace         | Vision-language captions        |
| CLIP       | 8093 | ~800 MB  | HuggingFace         | Entity re-identification        |
| Enrichment | 8094 | ~6 GB    | PyTorch/HuggingFace | Vehicle/pet/clothing/depth/pose |

## Quick Start

### Production (Docker/Podman Containers)

```bash
# Start all services including AI containers
docker compose -f docker-compose.prod.yml up -d

# Or with Podman
podman-compose -f docker-compose.prod.yml up -d

# Verify AI containers are running
docker ps --filter name=ai-
```

### Development (Native)

Shell scripts for native execution (useful for debugging):

```bash
# 1. Download models (first time only)
./ai/download_models.sh

# 2. Start individual services
./ai/start_detector.sh     # RT-DETRv2 on 8090
./ai/start_llm.sh          # Nemotron 4B on 8091
./ai/start_nemotron.sh     # Nemotron 30B on 8091 (alternative)
```

## Architecture

```
Camera Images
      │
      ▼
┌─────────────┐      ┌─────────────┐
│  RT-DETRv2  │─────▶│  Enrichment │
│   (8090)    │      │   (8094)    │
└─────────────┘      └─────────────┘
      │                    │
      │   Detections       │  Classified Detections
      ▼                    ▼
┌─────────────────────────────────┐
│         Nemotron (8091)         │
│     Risk Analysis & Scoring     │
└─────────────────────────────────┘
                │
                ▼
          Risk Events
```

### Optional Services

- **CLIP (8093)**: Entity re-identification via 768-dim embeddings
- **Florence-2 (8092)**: Vision-language attribute extraction

## Backend Integration

The backend communicates with AI services via HTTP clients:

| Backend Service                         | AI Service | Purpose                     |
| --------------------------------------- | ---------- | --------------------------- |
| `backend/services/detector_client.py`   | RT-DETRv2  | Send images, get detections |
| `backend/services/nemotron_analyzer.py` | Nemotron   | Analyze batches, get risk   |
| `backend/services/enrichment_client.py` | Enrichment | Classify detections         |

## Environment Variables

### RT-DETRv2

| Variable            | Default                                        | Description              |
| ------------------- | ---------------------------------------------- | ------------------------ |
| `RTDETR_MODEL_PATH` | `/export/ai_models/rt-detrv2/rtdetr_v2_r101vd` | HuggingFace model path   |
| `RTDETR_CONFIDENCE` | `0.5`                                          | Min confidence threshold |
| `HOST`              | `0.0.0.0`                                      | Bind address             |
| `PORT`              | `8090`                                         | Server port              |

### Nemotron

| Variable     | Default                                       | Description         |
| ------------ | --------------------------------------------- | ------------------- |
| `MODEL_PATH` | `/models/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf` | GGUF model path     |
| `PORT`       | `8091`                                        | Server port         |
| `GPU_LAYERS` | `30`                                          | Layers on GPU       |
| `CTX_SIZE`   | `131072`                                      | Context window size |
| `PARALLEL`   | `1`                                           | Parallel requests   |

### Enrichment

| Variable              | Default                                  | Description             |
| --------------------- | ---------------------------------------- | ----------------------- |
| `VEHICLE_MODEL_PATH`  | `/models/vehicle-segment-classification` | Vehicle classifier path |
| `PET_MODEL_PATH`      | `/models/pet-classifier`                 | Pet classifier path     |
| `CLOTHING_MODEL_PATH` | `/models/fashion-clip`                   | FashionCLIP model path  |
| `DEPTH_MODEL_PATH`    | `/models/depth-anything-v2-small`        | Depth estimator path    |
| `VITPOSE_MODEL_PATH`  | `/models/vitpose-plus-small`             | ViTPose+ model path     |

## Security-Relevant Classes

RT-DETRv2 filters detections to these classes only:

```python
SECURITY_CLASSES = {"person", "car", "truck", "dog", "cat", "bird", "bicycle", "motorcycle", "bus"}
```

## Risk Scoring (Nemotron)

| Score Range | Level    | Description                 |
| ----------- | -------- | --------------------------- |
| 0-29        | Low      | Normal activity             |
| 30-59       | Medium   | Unusual but not threatening |
| 60-84       | High     | Suspicious activity         |
| 85-100      | Critical | Potential security threat   |

## Hardware Requirements

- **GPU**: NVIDIA with CUDA support (tested on RTX A5500 24GB)
- **Container Runtime**: Docker or Podman with NVIDIA Container Toolkit
- **Total VRAM**: ~22 GB for all services running simultaneously

## Startup Scripts

### `download_models.sh`

Downloads or locates models:

- Nemotron: HuggingFace (bartowski/nemotron-mini-4b-instruct-GGUF)
- RT-DETRv2: HuggingFace models auto-download

### `start_detector.sh`

Runs RT-DETRv2 server (`python model.py`) on port 8090.

### `start_llm.sh`

Simple llama-server startup for 4B model:

- Context: 4096 tokens
- GPU layers: 99

### `start_nemotron.sh`

Advanced startup for 30B model with auto-recovery:

- Context: 12288 tokens
- GPU layers: 45
- Startup timeout: 90 seconds
- Log file: `/tmp/nemotron.log`

## Entry Points

1. **Pipeline overview**: This file
2. **Detection server**: `rtdetr/AGENTS.md` and `rtdetr/model.py`
3. **LLM server**: `nemotron/AGENTS.md`
4. **CLIP server**: `clip/AGENTS.md` and `clip/model.py`
5. **Florence server**: `florence/AGENTS.md` and `florence/model.py`
6. **Enrichment server**: `enrichment/AGENTS.md` and `enrichment/model.py`
7. **Backend integration**: `backend/services/` directory
