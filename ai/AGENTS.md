# AI Pipeline Directory

## Purpose

Contains AI inference services for home security monitoring. This directory houses multiple containerized HTTP servers that provide GPU-accelerated AI capabilities:

1. **RT-DETRv2** - Object detection (people, vehicles, animals)
2. **Nemotron** - LLM risk reasoning and analysis
3. **CLIP** - Entity re-identification via embeddings
4. **Florence-2** - Vision-language attribute extraction
5. **Enrichment** - Combined classification service with on-demand model loading (Model Zoo)

All services run as FastAPI HTTP servers with GPU passthrough via Docker/Podman.

## Directory Structure

```
ai/
├── AGENTS.md              # This file
├── __init__.py            # Package init
├── common/                # Shared TensorRT optimization infrastructure (NEM-3838)
│   ├── AGENTS.md          # TensorRT infrastructure documentation
│   ├── __init__.py        # Package exports
│   ├── tensorrt_utils.py  # ONNX-to-TensorRT conversion, engine management
│   ├── tensorrt_inference.py  # Base classes for TensorRT-accelerated models
│   └── tests/             # Unit tests
├── rtdetr/                # RT-DETRv2 object detection server
│   ├── AGENTS.md          # RT-DETRv2 documentation
│   ├── Dockerfile         # Container build (PyTorch + CUDA)
│   ├── model.py           # FastAPI server (HuggingFace Transformers)
│   ├── example_client.py  # Python client example
│   ├── test_model.py      # Unit tests (pytest)
│   ├── requirements.txt   # Python dependencies
│   ├── README.md          # Usage documentation
│   ├── __init__.py        # Package init (version 1.0.0)
│   └── .gitkeep           # Placeholder
├── nemotron/              # Nemotron LLM model files
│   ├── AGENTS.md          # Nemotron documentation
│   ├── Dockerfile         # Multi-stage build for llama.cpp
│   ├── config.json        # llama.cpp config reference
│   └── .gitkeep           # Placeholder (GGUF models downloaded at runtime)
├── clip/                  # CLIP embedding server
│   ├── AGENTS.md          # CLIP documentation
│   ├── Dockerfile         # Container build
│   ├── model.py           # FastAPI server for embeddings
│   └── requirements.txt   # Python dependencies
├── florence/              # Florence-2 vision-language server
│   ├── AGENTS.md          # Florence-2 documentation
│   ├── Dockerfile         # Container build
│   ├── __init__.py        # Package init
│   ├── model.py           # FastAPI server for attribute extraction
│   ├── test_model.py      # Unit tests (pytest)
│   ├── requirements.txt   # Python dependencies
│   └── tests/             # Additional tests directory
├── enrichment/            # Combined enrichment service (Model Zoo)
│   ├── AGENTS.md          # Enrichment documentation
│   ├── Dockerfile         # Container build
│   ├── __init__.py        # Package init
│   ├── model.py           # FastAPI server with /enrich endpoint
│   ├── model_manager.py   # On-demand VRAM-aware model loading
│   ├── model_registry.py  # Model configuration and registration
│   ├── vitpose.py         # ViTPose+ pose estimation (legacy)
│   ├── test_model.py      # Unit tests (pytest)
│   ├── requirements.txt   # Python dependencies
│   ├── models/            # Model implementations
│   │   ├── pose_estimator.py   # YOLOv8n-pose wrapper
│   │   ├── threat_detector.py  # Weapon detection
│   │   ├── demographics.py     # Age/gender estimation
│   │   ├── person_reid.py      # OSNet re-ID embeddings
│   │   └── action_recognizer.py # X-CLIP video actions
│   └── tests/             # Additional unit tests
├── download_models.sh     # Download AI models
├── start_detector.sh      # Start RT-DETRv2 (port 8090)
├── start_llm.sh           # Start Nemotron 4B (port 8091)
└── start_nemotron.sh      # Start Nemotron 30B with auto-recovery
```

## Service Overview

| Service    | Port | Model                | HuggingFace                                                                                       | Purpose                        |
| ---------- | ---- | -------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------ |
| RT-DETRv2  | 8090 | RT-DETRv2            | [PekingU/rtdetr_r50vd_coco_o365](https://huggingface.co/PekingU/rtdetr_r50vd_coco_o365)           | Object detection               |
| Nemotron   | 8091 | Nemotron-3-Nano-30B  | [nvidia/Nemotron-3-Nano-30B-A3B-GGUF](https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF) | Risk reasoning                 |
| Florence-2 | 8092 | Florence-2-Large     | [microsoft/Florence-2-large](https://huggingface.co/microsoft/Florence-2-large)                   | Dense captioning               |
| CLIP       | 8093 | CLIP ViT-L           | [openai/clip-vit-large-patch14](https://huggingface.co/openai/clip-vit-large-patch14)             | Entity embeddings              |
| Enrichment | 8094 | Model Zoo (9 models) | See [enrichment/AGENTS.md](enrichment/AGENTS.md)                                                  | On-demand detection enrichment |

## Model Zoo Overview

The Enrichment service implements an on-demand **Model Zoo** architecture for VRAM-efficient multi-model inference. Instead of loading all models at startup, models are loaded when needed and evicted via LRU when VRAM budget is exceeded.

### Available Models (9 total)

| Model              | VRAM   | Priority | Purpose                          | Trigger                           |
| ------------------ | ------ | -------- | -------------------------------- | --------------------------------- |
| Threat Detector    | 400 MB | CRITICAL | Weapon detection (gun, knife)    | Always checked for security       |
| Pose Estimator     | 300 MB | HIGH     | Body posture (17 COCO keypoints) | Person detected                   |
| Demographics       | 500 MB | HIGH     | Age/gender estimation            | Person with face detected         |
| FashionCLIP        | 800 MB | HIGH     | Clothing attributes              | Person detected                   |
| Vehicle Classifier | 1.5 GB | MEDIUM   | Vehicle type (11 classes)        | Vehicle detected                  |
| Pet Classifier     | 200 MB | MEDIUM   | Cat/dog classification           | Cat/dog detected                  |
| Person ReID        | 100 MB | MEDIUM   | OSNet re-ID embeddings (512-dim) | Person detected for tracking      |
| Depth Anything V2  | 150 MB | LOW      | Monocular depth estimation       | Any detection                     |
| Action Recognizer  | 1.5 GB | LOW      | X-CLIP video action recognition  | Suspicious pose + multiple frames |

### Model Priority System

Models are evicted in priority order when VRAM budget is exceeded:

- **CRITICAL** (evicted last): Threat detection - never evict if possible
- **HIGH**: Pose, demographics, clothing - important for security context
- **MEDIUM**: Vehicle, pet, re-ID - useful classification
- **LOW** (evicted first): Depth, action - expensive, load sparingly

### VRAM Budget

- Default budget: **6.8 GB** (configurable via `VRAM_BUDGET_GB`)
- Models load on-demand when `/enrich` endpoint is called
- LRU eviction with priority ordering when budget exceeded
- Automatic CUDA cache clearing on model unload

For detailed documentation, see [enrichment/AGENTS.md](enrichment/AGENTS.md).

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
┌─────────────┐      ┌───────────────────────────────────┐
│  RT-DETRv2  │─────▶│          Enrichment (8094)        │
│   (8090)    │      │    On-Demand Model Loading        │
└─────────────┘      │  ┌─────────────────────────────┐  │
      │              │  │ Threat │ Pose  │ Clothing  │  │
      │              │  │ ReID   │ Demo. │ Vehicle   │  │
      │              │  │ Action │ Pet   │ Depth     │  │
      │              │  └─────────────────────────────┘  │
      │              └───────────────────────────────────┘
      │   Detections                    │
      │                    Enriched Detections
      ▼                                 ▼
┌─────────────────────────────────────────────────────┐
│                   Nemotron (8091)                   │
│              Risk Analysis & Scoring                │
│        (Threat, Pose, Demographics Context)         │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
                   Risk Events
```

### Optional Services

- **CLIP (8093)**: Entity re-identification via 768-dim embeddings
- **Florence-2 (8092)**: Vision-language attribute extraction

## Backend Integration

The backend communicates with AI services via HTTP clients:

| Backend Service                         | AI Service | Purpose                           |
| --------------------------------------- | ---------- | --------------------------------- |
| `backend/services/detector_client.py`   | RT-DETRv2  | Send images, get detections       |
| `backend/services/nemotron_analyzer.py` | Nemotron   | Analyze batches, get risk         |
| `backend/services/enrichment_client.py` | Enrichment | Unified enrichment for detections |
| `backend/services/reid_matcher.py`      | Enrichment | Person re-ID matching             |
| `backend/services/florence_client.py`   | Florence-2 | Vision-language extraction        |
| `backend/services/clip_client.py`       | CLIP       | Embedding generation              |

## Environment Variables

### RT-DETRv2

| Variable            | Default                                        | Description              |
| ------------------- | ---------------------------------------------- | ------------------------ |
| `RTDETR_MODEL_PATH` | `/export/ai_models/rt-detrv2/rtdetr_v2_r101vd` | HuggingFace model path   |
| `RTDETR_CONFIDENCE` | `0.5`                                          | Min confidence threshold |
| `HOST`              | `0.0.0.0`                                      | Bind address             |
| `PORT`              | `8090`                                         | Server port              |

### Nemotron

**Model**: [nvidia/Nemotron-3-Nano-30B-A3B-GGUF](https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF) - NVIDIA's 30B parameter LLM optimized for reasoning tasks, quantized to GGUF format for efficient inference via llama.cpp.

| Variable     | Default                                       | Description         |
| ------------ | --------------------------------------------- | ------------------- |
| `MODEL_PATH` | `/models/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf` | GGUF model path     |
| `PORT`       | `8091`                                        | Server port         |
| `GPU_LAYERS` | `35`                                          | Layers on GPU       |
| `CTX_SIZE`   | `131072`                                      | Context window size |
| `PARALLEL`   | `1`                                           | Parallel requests   |

### Enrichment (Model Zoo)

| Variable              | Default                                  | Description                      |
| --------------------- | ---------------------------------------- | -------------------------------- |
| `VRAM_BUDGET_GB`      | `6.8`                                    | VRAM budget for on-demand models |
| `VEHICLE_MODEL_PATH`  | `/models/vehicle-segment-classification` | Vehicle classifier path          |
| `PET_MODEL_PATH`      | `/models/pet-classifier`                 | Pet classifier path              |
| `CLOTHING_MODEL_PATH` | `/models/fashion-clip`                   | FashionCLIP model path           |
| `DEPTH_MODEL_PATH`    | `/models/depth-anything-v2-small`        | Depth estimator path             |
| `POSE_MODEL_PATH`     | `/models/yolov8n-pose/yolov8n-pose.pt`   | YOLOv8n-pose model path          |
| `THREAT_MODEL_PATH`   | `/models/threat-detection`               | Threat detection model path      |
| `AGE_MODEL_PATH`      | `/models/vit-age-classifier`             | Age classifier path              |
| `REID_MODEL_PATH`     | `/models/osnet-reid`                     | OSNet ReID model path            |
| `ACTION_MODEL_PATH`   | `microsoft/xclip-base-patch32`           | X-CLIP model path                |

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

### Enrichment Context for Nemotron

The enrichment service provides structured context to Nemotron for better risk assessment:

- **Threat Detection**: `[CRITICAL] GUN DETECTED: confidence=95%`
- **Pose Analysis**: `Posture: crouching (potentially hiding)`
- **Demographics**: `Person appears to be male, age 21-35`
- **Clothing**: `Alert: dark hoodie detected`
- **Vehicle**: `Vehicle type: pickup truck (commercial)`
- **Re-ID**: `Same person seen on front_door camera 5 minutes ago`
- **Action**: `Action: loitering (suspicious)`

## Hardware Requirements

- **GPU**: NVIDIA with CUDA support (tested on RTX A5500 24GB + RTX A400 4GB)
- **Container Runtime**: Docker or Podman with NVIDIA Container Toolkit
- **Total VRAM**: ~22 GB for all services running simultaneously
  - RT-DETRv2: ~650 MB
  - Nemotron: ~21.7 GB
  - Florence-2: ~1.5 GB
  - CLIP: ~1.2 GB
  - Enrichment (Model Zoo): ~6.8 GB budget

### Multi-GPU Support

The system supports distributing AI workloads across multiple GPUs. See **[Multi-GPU Support Guide](../docs/development/multi-gpu.md)** for configuration instructions.

**Reference Multi-GPU Configuration:**

| GPU   | Model     | VRAM  | Recommended Services                      |
| ----- | --------- | ----- | ----------------------------------------- |
| GPU 0 | RTX A5500 | 24 GB | ai-llm, ai-detector, ai-florence, ai-clip |
| GPU 1 | RTX A400  | 4 GB  | ai-enrichment (with 3.5GB budget)         |

### GPU Configuration Files (Auto-Generated)

The following files are auto-generated by the GPU Configuration Service when you apply changes via the UI:

- Docker Compose override for GPU assignments (in config directory)
- Human-readable GPU assignment reference (in config directory)

**Do not edit manually.** These files may not exist until GPU configuration is applied via the UI.

### Override File Format

```yaml
# Auto-generated by GPU Config Service - DO NOT EDIT MANUALLY
services:
  ai-llm:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']
              capabilities: [gpu]
  ai-enrichment:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['1']
              capabilities: [gpu]
    environment:
      - VRAM_BUDGET_GB=3.5
```

### Using the Override File

```bash
# Start with GPU override
podman-compose -f docker-compose.prod.yml \
               -f config/docker-compose.gpu-override.yml up -d

# Restart specific service with GPU override
podman-compose -f docker-compose.prod.yml \
               -f config/docker-compose.gpu-override.yml \
               up -d --force-recreate --no-deps ai-enrichment
```

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
- GPU layers: 35
- Startup timeout: 90 seconds
- Log file: `/tmp/nemotron.log`

## Entry Points

1. **Pipeline overview**: This file
2. **Detection server**: `rtdetr/AGENTS.md` and `rtdetr/model.py`
3. **LLM server**: `nemotron/AGENTS.md`
4. **CLIP server**: `clip/AGENTS.md` and `clip/model.py`
5. **Florence server**: `florence/AGENTS.md` and `florence/model.py`
6. **Enrichment server (Model Zoo)**: `enrichment/AGENTS.md`
   - Model manager: `enrichment/model_manager.py`
   - Model registry: `enrichment/model_registry.py`
   - Model implementations: `enrichment/models/`
7. **Backend integration**: `backend/services/` directory
