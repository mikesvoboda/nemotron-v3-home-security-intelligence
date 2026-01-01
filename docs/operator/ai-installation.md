# AI Services Installation

> Install prerequisites and dependencies for AI inference services.

**Time to read:** ~10 min
**Prerequisites:** [AI Overview](ai-overview.md)

---

## Hardware Requirements

### Minimum

- **GPU**: NVIDIA RTX 3060 (8GB+ VRAM) or equivalent
- **VRAM**: 8GB minimum (~7GB used + buffer)
- **CUDA**: Version 11.8 or later
- **System RAM**: 16GB
- **Storage**: 10GB free space for models and cache

### Recommended (Tested Configuration)

- **GPU**: NVIDIA RTX A5500 (24GB VRAM)
- **VRAM**: 12GB+ (comfortable headroom)
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

**Not compatible**: AMD GPUs, Intel GPUs, Apple Silicon

---

## Software Prerequisites

### Operating System

| OS      | Supported Versions                           |
| ------- | -------------------------------------------- |
| Linux   | Ubuntu 20.04+, Fedora 36+ (tested on Fed 43) |
| Windows | WSL2 with Ubuntu                             |
| macOS   | Not supported (requires CUDA)                |

### 1. NVIDIA Drivers and CUDA

```bash
# Check NVIDIA driver installation
nvidia-smi

# Expected output includes:
# Driver Version: 550.54.15
# CUDA Version: 12.4
```

**Install if missing:**

```bash
# Ubuntu/Debian
sudo apt install nvidia-driver-550 nvidia-cuda-toolkit

# Fedora
sudo dnf install akmod-nvidia xorg-x11-drv-nvidia-cuda
```

### 2. Python 3.10+

```bash
# Check Python version
python3 --version  # Should be 3.10 or later

# Ubuntu/Debian
sudo apt install python3.10 python3-pip python3-venv

# Fedora
sudo dnf install python3.10 python3-pip
```

### 3. llama.cpp (for Nemotron)

llama.cpp provides the `llama-server` command for running the LLM.

**Option A: Check if installed**

```bash
which llama-server
```

**Option B: Build from source** (recommended for best performance)

```bash
# Install build dependencies
# Ubuntu/Debian
sudo apt install build-essential cmake git libcurl4-openssl-dev

# Fedora
sudo dnf install gcc-c++ cmake git libcurl-devel

# Clone and build
cd /tmp
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make LLAMA_CUDA=1 -j$(nproc)

# Install binary (choose one)
# System-wide
sudo install -m 755 llama-server /usr/local/bin/llama-server

# User-local
mkdir -p ~/.local/bin
install -m 755 llama-server ~/.local/bin/llama-server

# Verify
llama-server --version
```

Build time: ~5-10 minutes depending on CPU.

### 4. Python Dependencies (RT-DETRv2)

```bash
cd $PROJECT_ROOT/ai/rtdetr

# Create virtual environment (recommended)
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

---

## Model Downloads

### Automated Download

```bash
cd $PROJECT_ROOT
./ai/download_models.sh
```

**Downloads:**

1. **Nemotron Mini 4B Instruct (Q4_K_M)** - ~2.5GB

   - Source: HuggingFace (bartowski/nemotron-mini-4b-instruct-GGUF)
   - Location: `ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf`
   - Download time: ~5-10 minutes

2. **RT-DETRv2** - ~160MB
   - Auto-downloaded on first use via HuggingFace transformers
   - Location: `~/.cache/huggingface/`

### Manual Download (if automatic fails)

**Nemotron model:**

```bash
cd ai/nemotron
wget https://huggingface.co/bartowski/nemotron-mini-4b-instruct-GGUF/resolve/main/nemotron-mini-4b-instruct-Q4_K_M.gguf \
  -O nemotron-mini-4b-instruct-q4_k_m.gguf
```

### Verify Downloads

```bash
# Check Nemotron model
ls -lh ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf
# Expected: ~2.5GB file

# RT-DETRv2 downloads automatically on first inference
```

---

## Verification

Run the startup script with status check:

```bash
./scripts/start-ai.sh status
```

This identifies any missing prerequisites.

---

## Next Steps

- [AI Configuration](ai-configuration.md) - Configure environment variables
- [AI Services](ai-services.md) - Start and verify services
- [AI Troubleshooting](ai-troubleshooting.md) - Common issues and solutions

---

## See Also

- [GPU Setup](gpu-setup.md) - Detailed GPU driver and container configuration
- [GPU Troubleshooting](../reference/troubleshooting/gpu-issues.md) - CUDA and VRAM problems
- [AI Overview](ai-overview.md) - Architecture and capabilities

---

[Back to Operator Hub](../operator-hub.md)
