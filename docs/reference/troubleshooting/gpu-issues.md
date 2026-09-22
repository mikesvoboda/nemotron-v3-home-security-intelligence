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

The production services (`ai-gateway`, `ai-llm`) already declare GPU access in
`docker-compose.prod.yml` — Podman CDI device passthrough plus a `deploy.resources`
reservation. This is the shape to copy for any new GPU service:

```yaml
services:
  ai-gateway:
    # Podman CDI (rootless GPU access) — all GPUs, then CUDA_VISIBLE_DEVICES selects
    devices:
      - nvidia.com/gpu=all
    environment:
      - CUDA_VISIBLE_DEVICES=${GPU_AI_SERVICES:-1}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['${GPU_AI_SERVICES:-1}']
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

# Restart AI services (containerized production stack)
docker compose -f docker-compose.prod.yml restart ai-gateway ai-llm

# Host-run services started with the ./ai/start_*.sh helpers
pkill -f model.py && ./ai/start_detector.sh
```

**2. Check memory requirements:**

| Service (container)                     | Expected VRAM  |
| --------------------------------------- | -------------- |
| YOLO26 (ai-gateway, TensorRT)           | ~2GB           |
| Florence-2 (ai-gateway)                 | ~1.5GB         |
| SigLIP 2 embeddings (ai-gateway)        | ~0.2GB         |
| Nemotron-3-Nano-30B (ai-llm)            | ~14.7GB (prod) |
| Nemotron Mini 4B (host-run dev scripts) | ~3GB (dev)     |
| **Total (prod)**                        | **~19GB**      |

See the VRAM table in [Operator Hub](../../operator/README.md) (GPU tier guidance:
8-12GB minimum, 16GB recommended, 24GB+ optimal).

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
# Production: the gateway health endpoint reports model readiness, not the device
curl http://localhost:8090/health | jq
curl http://localhost:8090/yolo26/health | jq .model_loaded

# Host-run standalone server (./ai/start_detector.sh) reports the torch device
curl http://localhost:8090/health | jq .device

# Check if GPU processes exist
nvidia-smi --query-compute-apps=pid,name --format=csv
```

> The `device` field only exists on the standalone host-run server
> (`ai/yolo26/model.py`, which returns `cuda:0` or `cpu`). The Triton-backed gateway
> router (`ai/gateway/adapters/yolo26.py`) returns only `status`, `model` and
> `model_loaded`.

### Solutions

**1. Verify CUDA in container:**

```bash
# Check container GPU access
docker compose -f docker-compose.prod.yml exec ai-gateway nvidia-smi

# Check PyTorch CUDA
docker compose -f docker-compose.prod.yml exec ai-gateway python3 -c "import torch; print(torch.cuda.is_available())"
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

**3. Verify GPU layer offload:**

- **Containerized `ai-llm`:** `docker-compose.prod.yml` passes `GPU_LAYERS=${GPU_LAYERS:-auto}`
  (llama.cpp auto-fits layers to free VRAM). Force full offload with `GPU_LAYERS=99` in `.env`.
- **Host-run `./ai/start_llm.sh`:** hardcoded `--n-gpu-layers 99` (all layers on GPU).
- **Host-run `./ai/start_nemotron.sh`:** `NEMOTRON_GPU_LAYERS` (default 35).

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

`ai-gateway` and `ai-llm` in `docker-compose.prod.yml` already combine both mechanisms —
the CDI `devices:` entry for Podman rootless, and the `deploy.resources` reservation for
Docker:

```yaml
services:
  ai-gateway:
    # Podman CDI
    devices:
      - nvidia.com/gpu=all
    # Docker
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['${GPU_AI_SERVICES:-1}']
              capabilities: [gpu]
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

The compose file parameterizes GPU selection with `GPU_AI_SERVICES` (ai-gateway,
default 1) and `GPU_LLM` (ai-llm, default 0). To change assignments, set them in `.env`
rather than editing the compose file:

```bash
# .env — put the Triton gateway on GPU 0 instead of the default GPU 1
GPU_AI_SERVICES=0
GPU_LLM=1
```

The resulting pattern in `docker-compose.prod.yml`:

```yaml
services:
  ai-gateway:
    environment:
      - CUDA_VISIBLE_DEVICES=${GPU_AI_SERVICES:-1}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['${GPU_AI_SERVICES:-1}']
              capabilities: [gpu]
```

---

## Triton CUDA Init Failure (Rootless Podman)

If ai-gateway (Triton) fails with `cudaGetDeviceCount() err=3` while ai-llm works:

- **Symptom:** Triton models UNAVAILABLE, `cudaErrorInitializationError`
- **Cause:** CUDA Runtime API vs Driver API — Triton uses Runtime API which may require nvidia-cap in rootless
- **Quick fix:** Run ai-gateway with rootful Podman: `sudo podman compose -f docker-compose.prod.yml up -d ai-gateway`

See: [Triton Rootless CUDA](triton-rootless-cuda.md) for full diagnosis and solutions.

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

[Back to Operator Hub](../../operator/README.md)
