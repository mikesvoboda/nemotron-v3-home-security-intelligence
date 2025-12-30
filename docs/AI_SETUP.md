# AI Services Setup Guide

Comprehensive guide for setting up and running the AI inference services for the Nemotron v3 Home Security Intelligence system.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Environment Variables](#environment-variables)
- [Hardware Requirements](#hardware-requirements)
- [Software Prerequisites](#software-prerequisites)
- [Installation](#installation)
- [Model Downloads](#model-downloads)
- [Starting Services](#starting-services)
- [Service Management](#service-management)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Performance Tuning](#performance-tuning)
- [Monitoring](#monitoring)

## Overview

The AI pipeline consists of two independent native services running outside Docker for optimal GPU performance:

1. **RT-DETRv2 Detection Server** (Port 8090)

   - Real-time object detection from camera images
   - ONNX Runtime with CUDA acceleration
   - ~4GB VRAM usage
   - 30-50ms inference per image

2. **Nemotron LLM Server** (Port 8091)
   - Risk reasoning and natural language generation
   - llama.cpp with quantized GGUF model
   - ~3GB VRAM usage
   - 2-5 seconds per risk analysis

**Total VRAM requirement**: ~7GB (both services running)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Pipeline Services                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐         ┌──────────────────┐         │
│  │  RT-DETRv2       │         │  Nemotron LLM    │         │
│  │  Detection       │         │  Risk Analysis   │         │
│  │                  │         │                  │         │
│  │  Port: 8090      │         │  Port: 8091      │         │
│  │  VRAM: ~4GB      │         │  VRAM: ~3GB      │         │
│  │  Latency: 30-50ms│         │  Latency: 2-5s   │         │
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
    │ (FastAPI)  │              │ (FastAPI)     │
    └────────────┘              └───────────────┘
     backend/services/          backend/services/
```

## Environment Variables

The following environment variables are used by the AI services. Set these in your shell profile (e.g., `~/.bashrc` or `~/.zshrc`) or in a `.env` file at the project root.

### Required Variables

| Variable       | Description                   | Example                                   |
| -------------- | ----------------------------- | ----------------------------------------- |
| `PROJECT_ROOT` | Root directory of the project | `$HOME/github/home-security-intelligence` |

### Optional Variables

| Variable              | Description                         | Default                                                           |
| --------------------- | ----------------------------------- | ----------------------------------------------------------------- |
| `AI_RTDETR_PORT`      | Port for RT-DETRv2 detection server | `8090`                                                            |
| `AI_NEMOTRON_PORT`    | Port for Nemotron LLM server        | `8091`                                                            |
| `AI_RTDETR_LOG`       | Log file for RT-DETRv2              | `/tmp/rtdetr-detector.log`                                        |
| `AI_NEMOTRON_LOG`     | Log file for Nemotron               | `/tmp/nemotron-llm.log`                                           |
| `NEMOTRON_MODEL_PATH` | Path to Nemotron GGUF model         | `$PROJECT_ROOT/ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf` |
| `AI_SERVICE_USER`     | User to run systemd services as     | Current user                                                      |

### Setting Up Environment Variables

```bash
# Option 1: Add to shell profile (~/.bashrc or ~/.zshrc)
export PROJECT_ROOT="$HOME/github/home-security-intelligence"

# Option 2: Create .env file at project root
echo 'PROJECT_ROOT="$HOME/github/home-security-intelligence"' >> .env

# Option 3: Set for current session only
export PROJECT_ROOT="/path/to/your/project"
```

**Note:** All scripts and examples in this documentation use `$PROJECT_ROOT` to reference the project directory. Replace with your actual path if not using the environment variable.

## Hardware Requirements

### Minimum

- **GPU**: NVIDIA RTX 3060 (12GB VRAM) or equivalent
- **VRAM**: 8GB minimum (7GB used + 1GB buffer)
- **CUDA**: Version 11.8 or later
- **System RAM**: 16GB
- **Storage**: 10GB free space for models and cache

### Recommended (Tested Configuration)

- **GPU**: NVIDIA RTX A5500 (24GB VRAM)
- **VRAM**: 24GB (comfortable headroom for both services)
- **CUDA**: Version 12.x
- **System RAM**: 32GB
- **Storage**: 20GB free space

### GPU Compatibility

Works with any NVIDIA GPU supporting CUDA compute capability 7.0+:

- RTX 20xx series and newer
- RTX 30xx series (3060, 3070, 3080, 3090)
- RTX 40xx series (4060, 4070, 4080, 4090)
- RTX A-series workstation GPUs
- Tesla/V100/A100 datacenter GPUs

**Not compatible**: AMD GPUs, Intel GPUs, Apple Silicon (MPS support not implemented)

## Software Prerequisites

### Operating System

- **Linux**: Ubuntu 20.04+, Fedora 36+, or equivalent (tested on Fedora 43)
- **Windows**: WSL2 with Ubuntu recommended
- **macOS**: Not supported (requires CUDA)

### Core Dependencies

#### 1. NVIDIA Drivers and CUDA

```bash
# Check NVIDIA driver installation
nvidia-smi

# Expected output:
# +-----------------------------------------------------------------------------+
# | NVIDIA-SMI 550.54.15    Driver Version: 550.54.15    CUDA Version: 12.4   |
# +-----------------------------------------------------------------------------+
```

Install if missing:

```bash
# Ubuntu/Debian
sudo apt install nvidia-driver-550 nvidia-cuda-toolkit

# Fedora
sudo dnf install akmod-nvidia xorg-x11-drv-nvidia-cuda
```

#### 2. Python 3.10+

```bash
# Check Python version
python3 --version  # Should be 3.10 or later

# Install if missing (Ubuntu/Debian)
sudo apt install python3.10 python3-pip python3-venv

# Fedora
sudo dnf install python3.10 python3-pip
```

#### 3. llama.cpp

llama.cpp provides the `llama-server` command for running Nemotron LLM.

**Option A: Install from package manager (if available)**

```bash
# Check if already installed
which llama-server
```

**Option B: Build from source** (recommended for best performance)

```bash
# Install build dependencies
# Ubuntu/Debian
sudo apt install build-essential cmake git libcurl4-openssl-dev

# Fedora
sudo dnf install gcc-c++ cmake git libcurl-devel

# Clone llama.cpp repository
cd /tmp
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp

# Build with CUDA support
make LLAMA_CUDA=1 -j$(nproc)

# Install binary (choose one method)
# Method 1: System-wide installation
sudo install -m 755 llama-server /usr/local/bin/llama-server

# Method 2: User-local installation
mkdir -p ~/.local/bin
install -m 755 llama-server ~/.local/bin/llama-server
# Add ~/.local/bin to PATH in ~/.bashrc if not already there

# Verify installation
llama-server --version
```

Build time: ~5-10 minutes depending on CPU.

#### 4. Python Dependencies (RT-DETRv2)

```bash
cd "$PROJECT_ROOT/ai/rtdetr"

# Create and activate virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Key dependencies:

- `torch` + `torchvision` - PyTorch for deep learning
- `onnxruntime-gpu` - ONNX Runtime with CUDA
- `fastapi` + `uvicorn` - Web server
- `pillow` + `opencv-python` - Image processing
- `pynvml` - NVIDIA GPU monitoring

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/home-security-intelligence.git
cd home-security-intelligence

# Set the PROJECT_ROOT environment variable
export PROJECT_ROOT="$(pwd)"
```

### 2. Verify Prerequisites

Run the startup script with status check:

```bash
./scripts/start-ai.sh status
```

This will identify any missing prerequisites.

## Model Downloads

### Download Script

The project provides an automated download script:

```bash
cd "$PROJECT_ROOT"
./ai/download_models.sh
```

**What it downloads:**

1. **Nemotron Mini 4B Instruct (Q4_K_M)** - ~2.5GB

   - Source: HuggingFace (bartowski/nemotron-mini-4b-instruct-GGUF)
   - Format: GGUF (quantized 4-bit)
   - Location: `ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf`
   - Download time: ~5-10 minutes (depends on connection)

2. **RT-DETRv2** - ~160MB
   - Auto-downloaded on first use via Hugging Face transformers
   - Model: `PekingU/rtdetr_r50vd_coco_o365`
   - Location: Hugging Face cache (`~/.cache/huggingface/`)

### Manual Download (Alternative)

If automatic download fails:

**Nemotron model:**

```bash
cd ai/nemotron
wget https://huggingface.co/bartowski/nemotron-mini-4b-instruct-GGUF/resolve/main/nemotron-mini-4b-instruct-Q4_K_M.gguf \
  -O nemotron-mini-4b-instruct-q4_k_m.gguf
```

**RT-DETRv2 model:**

The model will be downloaded automatically by the transformers library on first inference. No manual download needed.

### Verify Downloads

```bash
# Check Nemotron model
ls -lh ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf
# Expected: ~2.5GB file

# RT-DETRv2 will show when services start
```

## Starting Services

### Unified Startup (Recommended)

Use the unified startup script to manage both services:

```bash
# Start all AI services
./scripts/start-ai.sh start

# Expected output:
# ==========================================
# Starting AI Services
# ==========================================
#
# [INFO] Checking prerequisites...
# [OK] NVIDIA GPU detected: NVIDIA RTX A5500
# [OK] CUDA available
# [OK] llama-server found: /usr/bin/llama-server
# [OK] Python found: /usr/bin/python3
# [OK] Nemotron model found (2.5G)
# [WARN] RT-DETRv2 model not found (will auto-download)
# [OK] All prerequisites satisfied
#
# [INFO] Starting RT-DETRv2 detection server...
# [OK] RT-DETRv2 detection server started successfully
#   Port: 8090
#   PID: 12345
#   Log: /tmp/rtdetr-detector.log
#   Expected VRAM: ~4GB
#
# [INFO] Starting Nemotron LLM server...
# [OK] Nemotron LLM server started successfully
#   Port: 8091
#   PID: 12346
#   Log: /tmp/nemotron-llm.log
#   Expected VRAM: ~3GB
```

First startup takes longer (~2-3 minutes) due to:

- Model loading into VRAM
- CUDA initialization
- GPU warmup inferences

### Individual Service Startup (Alternative)

Start services separately for debugging:

```bash
# RT-DETRv2 detection server
./ai/start_detector.sh

# Nemotron LLM server (in separate terminal)
./ai/start_llm.sh
```

### Background Execution

Services run as background processes and persist after terminal close.

## Service Management

### Check Status

```bash
./scripts/start-ai.sh status
```

Output shows:

- Service status (RUNNING/STOPPED)
- Process IDs
- Health check results
- GPU memory usage
- Log file locations

### Stop Services

```bash
# Stop all AI services
./scripts/start-ai.sh stop

# Graceful shutdown (10 second timeout)
# Force kill if not responding
```

### Restart Services

```bash
# Restart both services
./scripts/start-ai.sh restart

# Useful after:
# - Model updates
# - Configuration changes
# - Service crashes
```

### Health Check

```bash
# Test service health endpoints
./scripts/start-ai.sh health

# Returns:
# - HTTP health check results
# - Service response times
# - Detailed status JSON
```

## Verification

### Test RT-DETRv2 Detection

```bash
# Health check
curl http://localhost:8090/health

# Expected response:
# {
#   "status": "healthy",
#   "model_loaded": true,
#   "device": "cuda:0",
#   "cuda_available": true,
#   "vram_used_gb": 4.2
# }

# Test detection (requires test image)
cd ai/rtdetr
python example_client.py path/to/test/image.jpg
```

### Test Nemotron LLM

```bash
# Health check
curl http://localhost:8091/health

# Test completion
curl -X POST http://localhost:8091/completion \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Analyze this security event: A person was detected at the front door at 14:30.",
    "temperature": 0.7,
    "max_tokens": 200
  }'
```

### Integration Test

Test full pipeline from backend:

```bash
cd backend

# Run integration tests
pytest tests/integration/ -v -k "test_ai_pipeline"

# Run full test suite
pytest tests/ -v
```

## Troubleshooting

### RT-DETRv2 Won't Start

**Symptom**: Service fails to start or crashes immediately

**Check logs:**

```bash
tail -f /tmp/rtdetr-detector.log
```

**Common issues:**

1. **CUDA out of memory**

   ```
   RuntimeError: CUDA out of memory
   ```

   - **Solution**: Free VRAM by closing other GPU applications
   - Check VRAM: `nvidia-smi`
   - Restart services: `./scripts/start-ai.sh restart`

2. **ONNX Runtime not found**

   ```
   ModuleNotFoundError: No module named 'onnxruntime'
   ```

   - **Solution**: Install dependencies

   ```bash
   cd ai/rtdetr
   pip install -r requirements.txt
   ```

3. **Model file not found**

   ```
   FileNotFoundError: rtdetrv2_r50vd.onnx
   ```

   - **Solution**: Model will auto-download on first use
   - Wait for download to complete (check logs)

### Nemotron LLM Won't Start

**Symptom**: LLM service fails to start

**Check logs:**

```bash
tail -f /tmp/nemotron-llm.log
```

**Common issues:**

1. **llama-server not found**

   ```
   command not found: llama-server
   ```

   - **Solution**: Install llama.cpp (see Prerequisites)
   - Verify: `which llama-server`

2. **Model file not found**

   ```
   error: failed to load model
   ```

   - **Solution**: Download model

   ```bash
   ./ai/download_models.sh
   ```

3. **CUDA initialization failed**

   ```
   ggml_init_cublas: failed to initialize CUDA
   ```

   - **Solution**: Check NVIDIA drivers

   ```bash
   nvidia-smi
   sudo systemctl restart nvidia-persistenced
   ```

4. **Port already in use**

   ```
   error: bind: Address already in use
   ```

   - **Solution**: Stop existing service

   ```bash
   lsof -ti:8091 | xargs kill -9
   ./scripts/start-ai.sh restart
   ```

### Service Unhealthy

**Symptom**: Service running but health check fails

**Diagnose:**

```bash
# Check if service is responding
curl -v http://localhost:8090/health
curl -v http://localhost:8091/health

# Check process status
./scripts/start-ai.sh status

# Monitor GPU
nvidia-smi -l 1
```

**Solutions:**

- Restart services: `./scripts/start-ai.sh restart`
- Check logs for errors
- Verify CUDA availability: `python3 -c "import torch; print(torch.cuda.is_available())"`

### Slow Inference

**Symptom**: Detection or LLM responses are very slow

**Check GPU utilization:**

```bash
nvidia-smi -l 1
```

**Common causes:**

1. **CPU fallback** (GPU not being used)

   - Detection: 200-500ms instead of 30-50ms
   - LLM: 30-60 seconds instead of 2-5 seconds
   - **Solution**: Verify CUDA installation, restart services

2. **Thermal throttling**

   - GPU temperature > 85°C
   - **Solution**: Improve cooling, reduce load

3. **Concurrent load**
   - Other processes using GPU
   - **Solution**: Close unnecessary GPU applications

### Out of Memory

**Symptom**: Services crash with OOM errors

**Check VRAM usage:**

```bash
nvidia-smi
```

**Solutions:**

1. **Free VRAM**

   ```bash
   # Stop other GPU processes
   fuser -k /dev/nvidia*

   # Restart AI services
   ./scripts/start-ai.sh restart
   ```

2. **Use smaller model** (Nemotron)

   - Download Q4_K_S quantization instead of Q4_K_M (saves ~500MB)
   - Edit `ai/start_llm.sh` to use smaller model

3. **Reduce batch sizes**
   - Edit backend configuration in `backend/core/config.py`
   - Reduce `batch_window_seconds` or concurrent requests

## Performance Tuning

### RT-DETRv2 Optimization

**Adjust confidence threshold** (trade-off: precision vs. recall):

```python
# In backend/core/config.py
detection_confidence_threshold: float = 0.5  # Default
# Lower = more detections, more false positives
# Higher = fewer detections, fewer false positives
```

**Batch processing** for multiple images:

```bash
# Use batch endpoint for better throughput
POST http://localhost:8090/detect/batch
```

### Nemotron LLM Optimization

**Adjust generation parameters** (trade-off: speed vs. quality):

```bash
# In ai/start_llm.sh
--n-gpu-layers 99        # Use all GPU layers (fastest)
--parallel 2             # Concurrent requests
--ctx-size 4096          # Context window size
--cont-batching          # Continuous batching (better throughput)
```

**Temperature tuning**:

- Lower (0.3-0.5): More deterministic, consistent
- Higher (0.7-0.9): More creative, varied

**Token limits**:

```python
# In backend/services/nemotron_analyzer.py
max_tokens = 500  # Shorter = faster, longer = more detailed
```

### GPU Memory Optimization

**Monitor VRAM usage:**

```bash
watch -n 1 nvidia-smi
```

**Optimize allocation:**

1. **RT-DETRv2**: Model size is fixed, but can reduce batch size
2. **Nemotron**: Adjust `--parallel` parameter to reduce concurrent load
3. **Context size**: Reduce `--ctx-size` if not using long contexts

## Monitoring

### Real-time GPU Monitoring

```bash
# Watch GPU utilization
nvidia-smi dmon -s pucvmet

# Detailed process view
nvidia-smi -l 1

# GPU memory breakdown
nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv
```

### Service Logs

```bash
# RT-DETRv2 logs
tail -f /tmp/rtdetr-detector.log

# Nemotron LLM logs
tail -f /tmp/nemotron-llm.log

# Both logs (parallel)
tail -f /tmp/rtdetr-detector.log -f /tmp/nemotron-llm.log
```

### Backend Integration Monitoring

The backend automatically monitors AI service health:

```bash
# Check backend logs for AI service status
cd backend
tail -f logs/app.log | grep -E "rtdetr|nemotron"
```

Backend services will log:

- Connection failures
- Timeout errors
- Health check results
- Inference latencies

### Performance Metrics

Track key metrics:

```bash
# Average inference time (RT-DETRv2)
curl http://localhost:8090/metrics  # If implemented

# GPU utilization over time
nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader -l 1 >> gpu_util.log

# Memory usage tracking
nvidia-smi --query-gpu=memory.used --format=csv,noheader -l 5 >> gpu_mem.log
```

## Production Deployment

### Systemd Service Units

For production deployment, create systemd service units. Replace the placeholder values with your actual paths and username.

**Required substitutions:**

- `${AI_SERVICE_USER}`: Your system username (e.g., the output of `whoami`)
- `${PROJECT_ROOT}`: Your project root directory (see [Environment Variables](#environment-variables))

**Template files:**

```bash
# /etc/systemd/system/ai-detector.service
[Unit]
Description=RT-DETRv2 Object Detection Service
After=network.target

[Service]
Type=simple
User=${AI_SERVICE_USER}
WorkingDirectory=${PROJECT_ROOT}/ai/rtdetr
ExecStart=/usr/bin/python3 model.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# /etc/systemd/system/ai-llm.service
[Unit]
Description=Nemotron LLM Service
After=network.target

[Service]
Type=simple
User=${AI_SERVICE_USER}
ExecStart=/usr/bin/llama-server \
  --model ${PROJECT_ROOT}/ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf \
  --port 8091 \
  --ctx-size 4096 \
  --n-gpu-layers 99 \
  --host 0.0.0.0 \
  --parallel 2 \
  --cont-batching
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Creating the service files:**

```bash
# Generate service files with your actual values
export AI_SERVICE_USER="$(whoami)"
export PROJECT_ROOT="/path/to/your/project"  # Set this to your actual project path

# Create detector service
sudo tee /etc/systemd/system/ai-detector.service > /dev/null << EOF
[Unit]
Description=RT-DETRv2 Object Detection Service
After=network.target

[Service]
Type=simple
User=${AI_SERVICE_USER}
WorkingDirectory=${PROJECT_ROOT}/ai/rtdetr
ExecStart=/usr/bin/python3 model.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create LLM service
sudo tee /etc/systemd/system/ai-llm.service > /dev/null << EOF
[Unit]
Description=Nemotron LLM Service
After=network.target

[Service]
Type=simple
User=${AI_SERVICE_USER}
ExecStart=/usr/bin/llama-server --model ${PROJECT_ROOT}/ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf --port 8091 --ctx-size 4096 --n-gpu-layers 99 --host 0.0.0.0 --parallel 2 --cont-batching
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-detector ai-llm
sudo systemctl start ai-detector ai-llm
```

### Auto-start on Boot

Add to crontab (replace `${PROJECT_ROOT}` with your actual project path):

```bash
crontab -e

# Add line (substitute your actual project path):
@reboot ${PROJECT_ROOT}/scripts/start-ai.sh start

# Or use an absolute path, for example:
# @reboot $HOME/github/home-security-intelligence/scripts/start-ai.sh start
```

### High Availability

For production systems requiring high availability:

1. **Load balancing**: Run multiple instances behind nginx
2. **Health monitoring**: Use monitoring tools (Prometheus, Grafana)
3. **Automatic restart**: Configure systemd or supervisor
4. **Resource limits**: Set memory and CPU limits in systemd units

## Additional Resources

### Documentation

- **llama.cpp**: https://github.com/ggerganov/llama.cpp
- **RT-DETRv2**: https://github.com/lyuwenyu/RT-DETR
- **ONNX Runtime**: https://onnxruntime.ai/docs/
- **NVIDIA CUDA**: https://docs.nvidia.com/cuda/

### Project Documentation

- `/ai/AGENTS.md` - AI pipeline overview
- `/ai/rtdetr/README.md` - RT-DETRv2 server documentation
- `/ai/rtdetr/AGENTS.md` - RT-DETRv2 technical details
- `/ai/nemotron/AGENTS.md` - Nemotron LLM details
- `/backend/services/AGENTS.md` - Backend AI integration

### Support

For issues or questions:

1. Check troubleshooting section above
2. Review service logs
3. Consult project AGENTS.md files
4. Open GitHub issue with logs and system info

## Quick Reference

### Common Commands

```bash
# Start all AI services
./scripts/start-ai.sh start

# Stop all AI services
./scripts/start-ai.sh stop

# Check status
./scripts/start-ai.sh status

# Health check
./scripts/start-ai.sh health

# View logs
tail -f /tmp/rtdetr-detector.log
tail -f /tmp/nemotron-llm.log

# Check GPU
nvidia-smi

# Download models
./ai/download_models.sh
```

### Service Endpoints

- **RT-DETRv2**: http://localhost:8090

  - Health: `GET /health`
  - Detect: `POST /detect`
  - Batch: `POST /detect/batch`

- **Nemotron LLM**: http://localhost:8091
  - Health: `GET /health`
  - Completion: `POST /completion`
  - Chat: `POST /v1/chat/completions`

### Expected Resource Usage

| Service   | VRAM | CPU    | Latency | Throughput    |
| --------- | ---- | ------ | ------- | ------------- |
| RT-DETRv2 | ~4GB | 10-20% | 30-50ms | 20-30 img/s   |
| Nemotron  | ~3GB | 5-10%  | 2-5s    | 0.2-0.5 req/s |

### Ports

- `8090` - RT-DETRv2 detection server
- `8091` - Nemotron LLM server
- `8000` - Backend FastAPI (communicates with AI services)
- `5173` - Frontend Vite dev server (development)
