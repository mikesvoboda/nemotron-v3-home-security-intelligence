# GPU Troubleshooting

> Solving CUDA, VRAM, and GPU-related problems.

**Time to read:** ~6 min
**Prerequisites:** NVIDIA GPU with CUDA support

---

## CUDA Not Available

### Symptoms

- Health check shows `"cuda_available": false`
- Error: `RuntimeError: CUDA not available`
- AI services running on CPU (very slow)

### Diagnosis

```bash
# Check if GPU is visible to system
nvidia-smi

# Check CUDA installation
nvcc --version

# Check PyTorch CUDA support
python3 -c "import torch; print(torch.cuda.is_available())"
```

### Solutions

**1. Install NVIDIA drivers:**

```bash
# Ubuntu/Debian
sudo apt install nvidia-driver-550 nvidia-cuda-toolkit

# Fedora
sudo dnf install akmod-nvidia xorg-x11-drv-nvidia-cuda
```

**2. Verify driver loaded:**

```bash
lsmod | grep nvidia
```

**3. For containers, ensure GPU passthrough:**

Docker Compose:

```yaml
services:
  ai-yolo26:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

Podman with CDI:

```bash
# Generate CDI spec
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml

# Verify
podman run --device nvidia.com/gpu=all nvidia/cuda:12.0-base nvidia-smi
```

---

## Out of Memory

### Symptoms

- Error: `RuntimeError: CUDA out of memory`
- Services crash during model loading
- High memory usage in `nvidia-smi`

### Diagnosis

```bash
# Check current VRAM usage
nvidia-smi

# Check what's using GPU memory
nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv
```

### Solutions

**1. Free VRAM:**

```bash
# Kill GPU processes
sudo fuser -k /dev/nvidia*

# Restart AI services
./scripts/start-ai.sh restart
```

**2. Check memory requirements:**

| Service             | Expected VRAM  |
| ------------------- | -------------- |
| YOLO26              | ~4GB           |
| Nemotron-3-Nano-30B | ~14.7GB (prod) |
| Nemotron Mini 4B    | ~3GB (dev)     |
| **Total (prod)**    | **~19GB**      |

**3. Use smaller model (Nemotron):**

Download Q4_K_S quantization instead of Q4_K_M (saves ~500MB).

**4. Close other GPU applications:**

- Browser tabs with GPU acceleration
- Desktop compositors
- Other ML applications

---

## CPU Fallback

### Symptoms

- GPU utilization at 0% in `nvidia-smi`
- Detection takes >200ms instead of 30-50ms
- LLM responses take >30s instead of 2-5s
- Health check shows `"device": "cpu"`

### Diagnosis

```bash
# Check YOLO26 health
curl http://localhost:8095/health | jq .device

# Check if GPU processes exist
nvidia-smi --query-compute-apps=pid,name --format=csv
```

### Solutions

**1. Verify CUDA in container:**

```bash
# Check container GPU access
docker exec ai-yolo26_1 nvidia-smi

# Check PyTorch CUDA
docker exec ai-yolo26_1 python3 -c "import torch; print(torch.cuda.is_available())"
```

**2. Check llama.cpp GPU support:**

```bash
# Verify llama-server has CUDA support
llama-server --version

# If built without CUDA, rebuild:
cd /tmp
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make LLAMA_CUDA=1 -j$(nproc)
sudo install -m 755 llama-server /usr/local/bin/
```

**3. Verify `--n-gpu-layers`:**

Nemotron startup should include `--n-gpu-layers 99` to load all layers on GPU.

---

## Thermal Throttling

### Symptoms

- GPU temperature >85C
- Performance degrades over time
- Fan running at maximum
- Power usage fluctuating

### Diagnosis

```bash
# Monitor temperature
watch -n 1 nvidia-smi

# Check power limits
nvidia-smi -q -d POWER
```

### Solutions

**1. Improve airflow:**

- Ensure case fans are working
- Clean dust from heatsinks
- Check GPU fan operation

**2. Adjust power limit:**

```bash
# Reduce power limit (e.g., 80% of TDP)
sudo nvidia-smi -pl 200  # Adjust value for your GPU
```

**3. Reduce inference load:**

- Increase `GPU_POLL_INTERVAL_SECONDS` to reduce monitoring overhead
- Process fewer cameras simultaneously

**4. Consider undervolting:**

For advanced users, GPU undervolting can reduce temperatures while maintaining performance.

---

## Container GPU Access

### Symptoms

- `nvidia-smi` shows no processes from containers
- Error: `Failed to initialize NVML`
- Error: `GPU device not found`

### Diagnosis

```bash
# Check if host GPU is visible
nvidia-smi

# Check container runtime
docker info | grep Runtime
podman info | grep runtime
```

### Solutions

**Docker:**

```bash
# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update
sudo apt install nvidia-container-toolkit
sudo systemctl restart docker
```

**Podman with CDI:**

```bash
# Install NVIDIA Container Toolkit
sudo dnf install nvidia-container-toolkit

# Generate CDI configuration
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml

# Verify CDI spec
cat /etc/cdi/nvidia.yaml

# Test
podman run --rm --device nvidia.com/gpu=all nvidia/cuda:12.0-base nvidia-smi
```

**Verify compose file:**

```yaml
services:
  ai-yolo26:
    # Docker
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    # OR Podman CDI
    devices:
      - nvidia.com/gpu=all
```

---

## Multiple GPUs

### Symptoms

- Wrong GPU being used
- Load not distributed as expected
- One GPU overloaded while others idle

### Diagnosis

```bash
# List all GPUs
nvidia-smi -L

# Show per-GPU utilization
nvidia-smi dmon -s pucvmet
```

### Solutions

**1. Specify GPU for service:**

```bash
# YOLO26 on GPU 0
CUDA_VISIBLE_DEVICES=0 python model.py

# Nemotron on GPU 1
CUDA_VISIBLE_DEVICES=1 llama-server ...
```

**2. In container:**

```yaml
services:
  ai-yolo26:
    environment:
      - CUDA_VISIBLE_DEVICES=0
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']
              capabilities: [gpu]
```

---

## Next Steps

- [AI Issues](ai-issues.md) - AI service-specific problems
- [Connection Issues](connection-issues.md) - Network and container issues
- [Troubleshooting Index](index.md) - Back to symptom index

---

## See Also

- [GPU Setup](../../operator/gpu-setup.md) - GPU driver and container configuration
- [AI Performance](../../operator/ai-performance.md) - Performance tuning
- [AI Overview](../../operator/ai-overview.md) - AI services architecture

---

[Back to Operator Hub](../../operator/)
