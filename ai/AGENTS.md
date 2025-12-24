# AI Pipeline Directory

## Purpose

This directory contains the AI inference services that power the home security monitoring system. It includes object detection via RT-DETRv2 and risk reasoning via Nemotron LLM, both running as independent HTTP services.

## Directory Structure

```
ai/
├── rtdetr/              # RT-DETRv2 object detection server
├── nemotron/            # Nemotron LLM model files
├── download_models.sh   # Download AI models script
├── start_detector.sh    # Start RT-DETRv2 server
└── start_llm.sh         # Start Nemotron LLM server
```

## Key Files

### `download_models.sh`

Downloads required AI models:

- **Nemotron Mini 4B Instruct** (Q4_K_M quantized GGUF) - ~2.5GB
  - Source: HuggingFace (bartowski/nemotron-mini-4b-instruct-GGUF)
  - Purpose: LLM-based risk reasoning and natural language generation
- **RT-DETRv2** - ~160MB
  - Auto-downloaded by transformers library on first use
  - Model: PekingU/rtdetr_r50vd_coco_o365

### `start_detector.sh`

Starts the RT-DETRv2 object detection server:

- **Port**: 8001
- **VRAM**: ~4GB
- **Purpose**: Detects security-relevant objects in camera images
- Runs `python ai/rtdetr/model.py`

### `start_llm.sh`

Starts the Nemotron LLM server via llama.cpp:

- **Port**: 8090
- **VRAM**: ~3GB (Q4_K_M quantization)
- **Context**: 4096 tokens
- **Parallelism**: 2 concurrent requests
- **GPU layers**: 99 (all layers on GPU)
- Uses `llama-server` command from llama.cpp

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AI Pipeline                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐         ┌──────────────────┐         │
│  │  RT-DETRv2       │         │  Nemotron LLM    │         │
│  │  Detection       │         │  Reasoning       │         │
│  │  Port: 8001      │         │  Port: 8090      │         │
│  │  VRAM: ~4GB      │         │  VRAM: ~3GB      │         │
│  └──────────────────┘         └──────────────────┘         │
│         ▲                             ▲                     │
│         │                             │                     │
│         │ HTTP POST /detect           │ HTTP POST          │
│         │ (multipart/form-data)       │ /completion        │
│         │                             │ (JSON)             │
└─────────┼─────────────────────────────┼──────────────────────┘
          │                             │
          │                             │
    ┌─────┴──────┐              ┌──────┴────────┐
    │ Detector   │              │ Nemotron      │
    │ Client     │              │ Analyzer      │
    │ Service    │              │ Service       │
    └────────────┘              └───────────────┘
     (backend)                   (backend)
```

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
cd /home/msvoboda/github/nemotron-v3-home-security-intelligence
./ai/download_models.sh
```

### 2. Start Detection Server

```bash
./ai/start_detector.sh
```

Server runs at: `http://localhost:8001`

### 3. Start LLM Server

```bash
./ai/start_llm.sh
```

Server runs at: `http://localhost:8090`

**Note**: Ensure `llama-server` from llama.cpp is installed and available in PATH before starting the LLM service.

## Hardware Requirements

- **GPU**: NVIDIA RTX A5500 (24GB VRAM)
- **CUDA**: Required for GPU acceleration
- **Total VRAM Usage**: ~7GB (4GB detector + 3GB LLM)
- **Inference Performance**:
  - RT-DETRv2: 30-50ms per image
  - Nemotron: ~2-5 seconds per risk analysis

## Development Notes

- Both services run as independent HTTP servers (not in Docker)
- Services must be started manually before running the backend
- Health check endpoints available at `/health` on both services
- Use `example_client.py` in rtdetr/ for testing detection API
- Backend automatically falls back if services are unavailable
