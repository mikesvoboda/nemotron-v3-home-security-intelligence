# AI Pipeline Directory

## Purpose

Contains AI inference services for home security monitoring: object detection (RT-DETRv2) and risk reasoning (Nemotron LLM). Both run as containerized HTTP servers with GPU passthrough via Podman.

## Deployment

Both AI services run in **Podman containers** with NVIDIA GPU passthrough:

| Container       | Image                           | Port | GPU VRAM |
| --------------- | ------------------------------- | ---- | -------- |
| `ai-detector_1` | localhost/...ai-detector:latest | 8090 | ~650 MiB |
| `ai-llm_1`      | localhost/...ai-llm:latest      | 8091 | ~14.7 GB |

```bash
# View running AI containers
podman ps --filter name=ai-

# Check container logs
podman logs nemotron-v3-home-security-intelligence_ai-detector_1
podman logs nemotron-v3-home-security-intelligence_ai-llm_1

# Check GPU usage
nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv
```

## Directory Structure

```
ai/
├── AGENTS.md              # This file
├── rtdetr/                # RT-DETRv2 object detection server
│   ├── AGENTS.md          # RT-DETRv2 documentation
│   ├── Dockerfile         # Container build configuration
│   ├── model.py           # FastAPI server (HuggingFace Transformers)
│   ├── example_client.py  # Python client example
│   ├── test_model.py      # Unit tests (some outdated)
│   ├── requirements.txt   # Python dependencies
│   ├── README.md          # Usage documentation
│   └── __init__.py        # Package init (version 1.0.0)
├── nemotron/              # Nemotron LLM model files
│   ├── AGENTS.md          # Nemotron documentation
│   ├── Dockerfile         # Container build configuration
│   ├── config.json        # llama.cpp config reference
│   └── .gitkeep           # Placeholder (GGUF models not in git)
├── download_models.sh     # Download AI models
├── start_detector.sh      # Start RT-DETRv2 (port 8090)
├── start_llm.sh           # Start Nemotron 4B (port 8091)
└── start_nemotron.sh      # Start Nemotron 30B with auto-recovery
```

## Quick Start

### Production (Recommended - Podman Containers)

```bash
# Start all services including AI containers
podman-compose -f docker-compose.prod.yml up -d

# Verify AI containers are running
podman ps --filter name=ai-
```

### Development (Native - Legacy)

Shell scripts for native execution (useful for debugging):

```bash
# 1. Download models (first time only)
./ai/download_models.sh

# 2. Start RT-DETRv2 detection server
./ai/start_detector.sh

# 3. Start Nemotron LLM server
./ai/start_llm.sh          # Simple (4B model)
./ai/start_nemotron.sh     # Advanced (30B model)
```

## Services

### RT-DETRv2 (Object Detection)

- **Port**: 8090
- **VRAM**: ~3-4GB
- **Framework**: HuggingFace Transformers (PyTorch)
- **Default Model**: `/export/ai_models/rt-detrv2/rtdetr_v2_r101vd`
- **Endpoints**: `GET /health`, `POST /detect`, `POST /detect/batch`

**Environment Variables**:

- `RTDETR_MODEL_PATH`: HuggingFace model path
- `RTDETR_CONFIDENCE`: Min confidence (default: 0.5)
- `HOST`: Bind address (default: 0.0.0.0)
- `PORT`: Server port (default: 8090)

**Security-Relevant Classes** (all others filtered):

```
person, car, truck, dog, cat, bird, bicycle, motorcycle, bus
```

### Nemotron LLM (Risk Reasoning)

- **Port**: 8091
- **VRAM**: ~3GB (4B) or ~16GB (30B)
- **Framework**: llama.cpp
- **Endpoints**: `GET /health`, `POST /completion`, `POST /v1/chat/completions`

**Environment Variables**:

- `NEMOTRON_MODEL_PATH`: GGUF model path
- `NEMOTRON_PORT`: Server port (default: 8091)
- `NEMOTRON_CONTEXT_SIZE`: Context window (default: 4096 or 12288)
- `NEMOTRON_GPU_LAYERS`: GPU layers (default: 99 or 45)

**Risk Scoring**:

- 0-25: Low (normal activity)
- 26-50: Medium (unusual)
- 51-75: High (suspicious)
- 76-100: Critical (threat)

## Architecture

```
Camera Images → RT-DETRv2 (8090) → Detections → Nemotron (8091) → Risk Events
                   ↑                                  ↑
                   │                                  │
           detector_client.py              nemotron_analyzer.py
                (backend)                       (backend)
```

## Backend Integration

### Detector Client (`backend/services/detector_client.py`)

- Sends images to RT-DETRv2
- Stores Detection records in database

### Nemotron Analyzer (`backend/services/nemotron_analyzer.py`)

- Analyzes detection batches
- Creates Event records with risk scores

## Hardware Requirements

- **GPU**: NVIDIA with CUDA support (tested on RTX A5500 24GB)
- **Container Runtime**: Podman with NVIDIA Container Toolkit (CDI)
- **VRAM** (actual measured usage):
  - RT-DETRv2: ~650 MiB
  - Nemotron 30B (Q4_K_M): ~14.7 GB
- **Performance**:
  - RT-DETRv2: 30-50ms/image
  - Nemotron: 2-5s/analysis

## Startup Scripts

### `download_models.sh`

Downloads or locates models:

- Nemotron: HuggingFace (bartowski/nemotron-mini-4b-instruct-GGUF)
- RT-DETRv2: Optional ONNX (legacy, HuggingFace models auto-download)

### `start_detector.sh`

Runs `python model.py` from rtdetr/. Checks for ONNX model path (legacy) but actual code uses HuggingFace.

### `start_llm.sh`

Simple llama-server startup for 4B model:

- Context: 4096 tokens
- GPU layers: 99

### `start_nemotron.sh`

Advanced startup for 30B model:

- Auto-recovery and health monitoring
- Multiple model/binary search paths
- 90-second startup timeout
- Log file: `/tmp/nemotron.log`

## Known Issues

1. **start_detector.sh references ONNX**: Script checks for ONNX model but code uses HuggingFace Transformers
2. **test_model.py outdated**: Some tests reference deprecated ONNX API
3. **README.md outdated**: References ONNX Runtime

## Entry Points

1. **Pipeline overview**: This file
2. **Detection server**: `rtdetr/AGENTS.md` and `rtdetr/model.py`
3. **LLM server**: `nemotron/AGENTS.md`
4. **Backend integration**: `backend/services/detector_client.py` and `nemotron_analyzer.py`
