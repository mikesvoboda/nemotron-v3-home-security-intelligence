# GPU Troubleshooting

> Solving CUDA, VRAM, and GPU-related problems.

**Time to read:** ~6 min
**Prerequisites:** NVIDIA GPU with CUDA support

Two containers hold GPU memory: `ai-gateway` (Triton — the YOLO26 detector and the
resident specialists) and `ai-vlm` (llama.cpp, behind the `vlm` compose profile).
Which card each one lands on is decided by `GPU_AI_SERVICES` and `GPU_LLM` in `.env`.
The face, plate, and person-re-ID lookups run in the backend process on CPU.

---

## CUDA Not Available

### Symptoms

- `nvidia-smi` on the host shows the card, but no process from either AI container
- `GET http://localhost:8090/health` returns `"status": "degraded"` with
  `triton_server_ready: false` or every model in `models` false
- The container probe below returns `err=3, count=0`

### Diagnosis

```bash
# Check if GPU is visible to the system
nvidia-smi

# Check the CUDA driver on the host
nvidia-smi --query-gpu=driver_version --format=csv,noheader

# Probe CUDA from inside the gateway container — this is the check that matters.
# The host's Python environment runs a CPU-only torch wheel, so a host
# torch.cuda.is_available() is false even on a perfectly healthy GPU.
docker compose -f docker-compose.prod.yml exec -T ai-gateway python3 -c "
import ctypes
lib = ctypes.CDLL('libcudart.so')
count = ctypes.c_int()
print('err=', lib.cudaGetDeviceCount(ctypes.byref(count)), 'count=', count.value)
"
```

### Solutions

**1. Install NVIDIA drivers.** The setup script refuses to proceed below driver
580 (`setup_lib/nvidia_detect.py:38`), so install a driver at or above that floor:

```bash
# Ubuntu/Debian — the graphics-driver PPA tracks the current production branch
sudo add-apt-repository ppa:graphics-drivers/ppa
sudo apt update
sudo apt install nvidia-driver-580-server

# Fedora
sudo dnf install akmod-nvidia xorg-x11-drv-nvidia-cuda
```

**2. Verify driver loaded:**

```bash
lsmod | grep nvidia
```

**3. For containers, ensure GPU passthrough:**

Docker Compose:

Both AI services already declare GPU access in `docker-compose.prod.yml` — a Podman
CDI device entry plus a `deploy.resources` reservation. This is the shape to copy for
any new GPU service:

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

`ai-vlm` uses the same two mechanisms and a single-card selector —
`devices: nvidia.com/gpu=${GPU_LLM:-0}` with `device_ids: ['${GPU_LLM:-0}']`
(`docker-compose.prod.yml:157-158`, `:264`). The gateway passes `all` deliberately:
a single `nvidia.com/gpu=N` with N>0 creates only `/dev/nvidiaN`, which the CUDA
Runtime cannot use, so the gateway takes every card and narrows Triton with
`CUDA_VISIBLE_DEVICES` instead.

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
# Restart the AI services (drops loaded models and re-initialises CUDA)
docker compose -f docker-compose.prod.yml restart ai-gateway
docker compose -f docker-compose.prod.yml --profile vlm restart ai-vlm

# A host-run standalone detector, if you started one
pkill -f "ai/yolo26/model.py"
```

**2. Know what the two GPU workloads actually cost:**

| What                                                        | Footprint                                                   |
| ----------------------------------------------------------- | ----------------------------------------------------------- |
| `ai-vlm` GGUF weights (Q4_K_M + Q8_0 projector)             | ~5.03GB + ~0.75GB                                           |
| `ai-vlm` KV pool (32 768 ctx × 2 slots, `q8_0` keys/values) | about half the 4 608 MiB an f16 pool of that geometry needs |
| `ai-gateway` Triton CUDA context + resident ONNX models     | 256 MB pool declared at startup                             |
| Face, plate and person-re-ID lookups                        | CPU only                                                    |

The KV pool scales with the context and slot counts, not with the weights, so
`VLM_CTX_SIZE` and `VLM_PARALLEL` are the levers on it. The shipped
`CACHE_TYPE_K`/`CACHE_TYPE_V=q8_0` is what halves that pool against an f16 default.
Measured figures and their sources are in
[VRAM Budget](../nvidia-technology-inventory.md#vram-budget).

The compose `memory:` limits are host RAM, not VRAM.

**3. Free the KV pool sooner:**

`ai-vlm` releases its VRAM to the host after `VLM_SLEEP_IDLE_SECONDS` (compose
default 300) of idleness. Lower that value on a shared card, or drop
`VLM_PARALLEL` to 1 to halve the pool the serve holds while it is awake.

**4. Close other GPU applications:**

- Browser tabs with GPU acceleration
- Desktop compositors
- Other ML applications

---

## CPU Fallback

### Symptoms

- GPU utilization at 0% in `nvidia-smi` while events are being processed
- Detection latency an order of magnitude above the served baseline
- Verdicts that take tens of seconds
- `ai-vlm` answers, but each answer is slow and the card is idle

### Diagnosis

```bash
# The gateway reports model readiness, not a device string
curl http://localhost:8090/health | jq
curl http://localhost:8090/yolo26/health | jq .model_loaded

# Which processes actually hold GPU memory
nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv

# The serve's own view of its offload
docker compose -f docker-compose.prod.yml --profile vlm logs ai-vlm 2>&1 | grep -iE "offload|CUDA|BLAS"
```

> Neither production service publishes a `"device"` field. `ai-gateway`'s router
> returns `status`, `model` and `model_loaded`
> (`ai/gateway/adapters/yolo26.py:511-520`); the aggregate at `/health` returns
> `status`, `triton_server_ready` and a per-model readiness map. The only server in
> this tree that answers with a `device` is the host-run `ai/yolo26/model.py`, which
> reports `cuda:0` or `cpu`.

### Solutions

**1. Verify CUDA inside the gateway container:**

```bash
# Container sees the card at all?
docker compose -f docker-compose.prod.yml exec -T ai-gateway nvidia-smi

# CUDA Runtime initializes?
docker compose -f docker-compose.prod.yml exec -T ai-gateway python3 -c "
import ctypes
lib = ctypes.CDLL('libcudart.so')
count = ctypes.c_int()
print('err=', lib.cudaGetDeviceCount(ctypes.byref(count)), 'count=', count.value)
"
```

`err=3` with `count=0` while `nvidia-smi` works is the rootless-Podman class — see
[Triton Rootless CUDA](triton-rootless-cuda.md).

**2. Check the llama.cpp CUDA build:**

The shipped `ai-vlm` image builds `llama-server` from source with `-DGGML_CUDA=ON`
(`ai/vlm/Dockerfile:74-76`), so the image is CUDA-capable by construction. A
CPU-only serve is a device-passthrough problem, not a build problem:

```bash
docker compose -f docker-compose.prod.yml --profile vlm exec -T ai-vlm nvidia-smi
docker compose -f docker-compose.prod.yml --profile vlm exec -T ai-vlm \
  ls /dev/nvidia0
```

If the device is missing inside the container, the CDI spec is the thing to
regenerate, not the image.

**3. Verify GPU layer offload:**

The compose file passes `GPU_LAYERS=${VLM_GPU_LAYERS:-auto}`
(`docker-compose.prod.yml:183`), so llama.cpp fits layers to the free VRAM it finds.
The image's own default is `99` (`ai/vlm/Dockerfile:124`). If a fixed count was set in
`.env` it overrides the auto-fit — check the value before blaming the card:

```bash
docker compose -f docker-compose.prod.yml --profile vlm exec -T ai-vlm env | grep GPU_LAYERS
```

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

`ai-gateway` and `ai-vlm` in `docker-compose.prod.yml` already combine both mechanisms —
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
# Host-run standalone detector on GPU 0
CUDA_VISIBLE_DEVICES=0 ./ai/start_detector.sh
```

**2. In container:**

The compose file parameterizes GPU selection with two variables: `GPU_AI_SERVICES`
(`ai-gateway`, default 1) and `GPU_LLM` (`ai-vlm`, default 0). To change assignments,
set them in `.env` rather than editing the compose file:

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

If ai-gateway (Triton) fails with `cudaGetDeviceCount() err=3` while `ai-vlm` runs
on the same card:

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
