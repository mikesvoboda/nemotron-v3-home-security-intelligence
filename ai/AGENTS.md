# AI Pipeline Directory

## Purpose

This directory contains the AI inference services that power the home security monitoring system. It includes object detection via RT-DETRv2 and risk reasoning via Nemotron LLM, both running as independent HTTP services.

## Directory Structure

```
ai/
├── AGENTS.md              # This file - AI pipeline overview
├── rtdetr/                # RT-DETRv2 object detection server
│   ├── AGENTS.md          # RT-DETRv2 documentation
│   ├── model.py           # FastAPI inference server
│   ├── example_client.py  # Python client example
│   ├── test_model.py      # Unit tests
│   ├── requirements.txt   # Python dependencies
│   └── README.md          # Usage documentation
├── nemotron/              # Nemotron LLM model files and config
│   ├── AGENTS.md          # Nemotron documentation
│   ├── config.json        # llama.cpp server config reference
│   └── *.gguf             # Model file (downloaded, not in git)
├── download_models.sh     # Download AI models script
├── start_detector.sh      # Start RT-DETRv2 server
├── start_llm.sh           # Start Nemotron LLM server (simple)
└── start_nemotron.sh      # Start Nemotron server (advanced, with auto-recovery)
```

## Key Files

### `download_models.sh`

Downloads or locates required AI models:

- **Nemotron Mini 4B Instruct** (Q4_K_M quantized GGUF) - ~2.5GB
  - Source: HuggingFace (bartowski/nemotron-mini-4b-instruct-GGUF)
  - Purpose: LLM-based risk reasoning and natural language generation
  - Search paths: `NEMOTRON_GGUF_PATH`, `NEMOTRON_MODELS_DIR`, `/export/ai_models/nemotron`
- **RT-DETRv2** (optional ONNX file for legacy support)
  - Model: `rtdetrv2_r50vd.onnx`
  - Search paths: `RTDETR_ONNX_PATH`, `RTDETR_MODELS_DIR`, `/export/ai_models/rt-detrv2`
  - Note: The current `model.py` uses HuggingFace Transformers which auto-downloads models

### `start_detector.sh`

Starts the RT-DETRv2 object detection server:

- **Port**: 8090 (configurable via `RTDETR_PORT`)
- **VRAM**: ~4GB (uses HuggingFace Transformers)
- **Purpose**: Detects security-relevant objects in camera images
- Runs `python ai/rtdetr/model.py`
- **Environment**: `MODEL_PATH` for ONNX model path (legacy), `RTDETR_MODEL_PATH` for HuggingFace model

### `start_llm.sh`

Simple startup script for Nemotron LLM server via llama.cpp:

- **Port**: 8091 (configurable via `NEMOTRON_PORT`)
- **VRAM**: ~3GB (Q4_K_M quantization)
- **Context**: 4096 tokens
- **Parallelism**: 2 concurrent requests
- **GPU layers**: 99 (all layers on GPU)
- Uses `llama-server` command from llama.cpp

### `start_nemotron.sh`

Advanced startup script with auto-recovery support:

- **Port**: 8091 (configurable via `NEMOTRON_PORT`)
- **Host**: 127.0.0.1 (configurable via `NEMOTRON_HOST`)
- **VRAM**: ~16GB (supports larger Nemotron-3-Nano-30B-A3B model)
- **Context**: 12288 tokens (configurable via `NEMOTRON_CONTEXT_SIZE`)
- **GPU layers**: 45 (configurable via `NEMOTRON_GPU_LAYERS`)
- **Startup timeout**: 90 seconds (for large model loading)
- **Log file**: `/tmp/nemotron.log`
- Features:
  - Multiple model path search locations
  - Multiple llama-server binary search locations
  - Health check before starting (skips if already running)
  - Background process with nohup
  - Startup health monitoring with timeout

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AI Pipeline                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐         ┌──────────────────┐         │
│  │  RT-DETRv2       │         │  Nemotron LLM    │         │
│  │  Detection       │         │  Reasoning       │         │
│  │  Port: 8090      │         │  Port: 8091      │         │
│  │  VRAM: ~4GB      │         │  VRAM: ~3-16GB   │         │
│  │  HuggingFace     │         │  llama.cpp       │         │
│  └──────────────────┘         └──────────────────┘         │
│         ▲                             ▲                     │
│         │                             │                     │
│         │ HTTP POST /detect           │ HTTP POST          │
│         │ (multipart/form-data)       │ /completion        │
│         │                             │ (JSON)             │
└─────────┼─────────────────────────────┼─────────────────────┘
          │                             │
          │                             │
    ┌─────┴──────┐              ┌──────┴────────┐
    │ Detector   │              │ Nemotron      │
    │ Client     │              │ Analyzer      │
    │ Service    │              │ Service       │
    └────────────┘              └───────────────┘
     (backend)                   (backend)
```

## How the AI Models are Used

### RT-DETRv2 (Object Detection)

RT-DETRv2 (Real-Time Detection Transformer v2) analyzes camera images to detect security-relevant objects:

1. **Input**: Camera images from Foscam FTP uploads (`/export/foscam/{camera_name}/`)
2. **Processing**: The file watcher service detects new images and sends them to RT-DETRv2
3. **Detection**: RT-DETRv2 identifies objects with bounding boxes and confidence scores
4. **Filtering**: Only security-relevant classes are returned (person, car, truck, dog, cat, bird, bicycle, motorcycle, bus)
5. **Output**: Detection records stored in database with coordinates and timestamps

**Security-Relevant Classes**: person, car, truck, dog, cat, bird, bicycle, motorcycle, bus

### Nemotron (Risk Reasoning)

Nemotron Mini 4B Instruct performs AI-powered risk analysis on batches of detections:

1. **Input**: Batches of detection data aggregated over 90-second time windows
2. **Analysis**: LLM evaluates the context, timing, and patterns of detected objects
3. **Risk Scoring**: Generates a 0-100 risk score based on the analysis
4. **Classification**: Assigns risk level (low/medium/high/critical)
5. **Output**: Event records with risk scores, summaries, and reasoning

**Risk Scoring Guidelines**:

- 0-25 (low): Normal activity, no concern
- 26-50 (medium): Unusual but not threatening
- 51-75 (high): Suspicious activity requiring attention
- 76-100 (critical): Potential security threat, immediate action needed

## Backend Integration

The backend services integrate with these AI servers:

### Detector Client (`backend/services/detector_client.py`)

- Sends camera images to RT-DETRv2 detection server
- Receives bounding boxes and object classifications
- Filters by confidence threshold (default 0.5)
- Stores Detection records in database

### Nemotron Analyzer (`backend/services/nemotron_analyzer.py`)

- Analyzes batches of detections using Nemotron LLM
- Generates risk scores (0-100) and risk levels (low/medium/high/critical)
- Produces natural language summaries and reasoning
- Creates Event records with risk assessments

## Starting the Services

### 1. Download Models (First Time Only)

```bash
cd /path/to/home_security_intelligence
./ai/download_models.sh
```

### 2. Start Detection Server

```bash
./ai/start_detector.sh
```

Server runs at: `http://localhost:8090`

### 3. Start LLM Server

```bash
# Simple startup
./ai/start_llm.sh

# Or advanced startup with auto-recovery
./ai/start_nemotron.sh
```

Server runs at: `http://localhost:8091`

**Note**: Ensure `llama-server` from llama.cpp is installed and available in PATH before starting the LLM service.

## Hardware Requirements

- **GPU**: NVIDIA RTX A5500 (24GB VRAM) or similar
- **CUDA**: Required for GPU acceleration
- **Total VRAM Usage**: ~7-20GB depending on model configuration
  - RT-DETRv2: ~4GB
  - Nemotron Mini 4B: ~3GB
  - Nemotron 30B A3B: ~16GB
- **Inference Performance**:
  - RT-DETRv2: 30-50ms per image
  - Nemotron: ~2-5 seconds per risk analysis

## Development Notes

- Both services run as independent HTTP servers (not in Docker)
- Services must be started manually before running the backend
- Health check endpoints available at `/health` on both services
- Use `example_client.py` in rtdetr/ for testing detection API
- Backend automatically falls back if services are unavailable

## Entry Points for Understanding the Code

1. **Start here**: Read this file for pipeline overview
2. **Object Detection**: `ai/rtdetr/AGENTS.md` and `ai/rtdetr/model.py`
3. **Risk Reasoning**: `ai/nemotron/AGENTS.md` and backend's `nemotron_analyzer.py`
4. **Model Setup**: `ai/download_models.sh` for model acquisition
5. **Service Startup**: `ai/start_detector.sh` and `ai/start_nemotron.sh`
