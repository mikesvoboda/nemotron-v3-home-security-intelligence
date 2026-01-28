# AI Services Troubleshooting

> Diagnose and fix common AI service issues.

**Time to read:** ~10 min
**Prerequisites:** [AI Services Management](ai-services.md)

---

## Quick Diagnostics

Run these commands first to identify the issue:

```bash
# Check if services are running
./scripts/start-ai.sh status

# Test service health endpoints
curl http://localhost:8095/health   # YOLO26
curl http://localhost:8091/health   # Nemotron
curl http://localhost:8092/health   # Florence-2 (optional)
curl http://localhost:8093/health   # CLIP (optional)
curl http://localhost:8094/health   # Enrichment (optional)

# Check GPU availability
nvidia-smi

# View recent logs
tail -100 /tmp/yolo26-detector.log
tail -100 /tmp/nemotron-llm.log
```

---

## YOLO26 Issues

### Service Won't Start

**Check logs:**

```bash
tail -f /tmp/yolo26-detector.log
```

**CUDA out of memory:**

```
RuntimeError: CUDA out of memory
```

**Solution:**

1. Close other GPU applications
2. Check VRAM usage: `nvidia-smi`
3. Restart services: `./scripts/start-ai.sh restart`

**Python dependency not found (YOLO26):**

```
ModuleNotFoundError: No module named 'transformers'
```

**Solution:**

```bash
cd "$PROJECT_ROOT"
uv sync --extra dev
```

**Model file not found:**

```
ImportError / ModuleNotFoundError in `ai/yolo26/model.py`
```

**Solution:** Model auto-downloads on first use. Wait for download to complete (check logs).

---

## Nemotron LLM Issues

### Service Won't Start

**Check logs:**

```bash
tail -f /tmp/nemotron-llm.log
```

**llama-server not found:**

```
command not found: llama-server
```

**Solution:** Install llama.cpp. See [AI Installation](ai-installation.md).

**Model file not found:**

```
error: failed to load model
```

**Solution:**

```bash
./ai/download_models.sh
```

**CUDA initialization failed:**

```
ggml_init_cublas: failed to initialize CUDA
```

**Solution:**

```bash
nvidia-smi
sudo systemctl restart nvidia-persistenced
```

**Port already in use:**

```
error: bind: Address already in use
```

**Solution:**

```bash
lsof -ti:8091 | xargs kill -9
./scripts/start-ai.sh restart
```

---

## Service Unhealthy

### Symptoms

Service running but health check fails.

### Diagnosis

```bash
# Check if service is responding
curl -v http://localhost:8095/health
curl -v http://localhost:8091/health

# Check process status
./scripts/start-ai.sh status

# Monitor GPU
nvidia-smi -l 1
```

### Solutions

1. Restart services: `./scripts/start-ai.sh restart`
2. Check logs for errors
3. Verify CUDA: `python3 -c "import torch; print(torch.cuda.is_available())"`

---

## Slow Inference

### Symptoms

- Detection: 200-500ms instead of 30-50ms
- LLM: 30-60 seconds instead of 2-5 seconds

### Check GPU Utilization

```bash
nvidia-smi -l 1
```

### Common Causes

**CPU fallback (GPU not being used):**

```bash
# Verify CUDA is being used
python3 -c "import torch; print(torch.cuda.is_available())"
```

Solution: Verify CUDA installation, restart services.

**Thermal throttling:**

```bash
# Check GPU temperature
nvidia-smi --query-gpu=temperature.gpu --format=csv
```

If > 85C, improve cooling or reduce load.

**Concurrent load:**

Other processes using GPU. Close unnecessary GPU applications.

---

## Out of Memory (OOM)

### Symptoms

Services crash with OOM errors.

### Check VRAM Usage

```bash
nvidia-smi
```

### Solutions

**1. Free VRAM:**

```bash
# Stop other GPU processes
fuser -k /dev/nvidia*

# Restart AI services
./scripts/start-ai.sh restart
```

**2. Use smaller model:**

Download Q4_K_S quantization instead of Q4_K_M (saves ~500MB). Edit `ai/start_llm.sh` to use smaller model.

**3. Reduce batch sizes:**

Edit backend configuration in `backend/core/config.py`. Reduce `batch_window_seconds` or concurrent requests.

---

## Connection Issues

### Backend Can't Reach AI Services

**Symptoms:**

```
httpx.ConnectError: [Errno 111] Connection refused
```

**Check:**

1. Are AI services running? `./scripts/start-ai.sh status`
2. Is the URL correct in `.env`?
3. Is there a firewall blocking the ports?

**Docker/Podman networking:**

The correct URL depends on your deployment mode (production compose DNS vs host-run AI vs “backend container + host AI”).

Start here:

- [Deployment Modes & AI Networking](deployment-modes.md) (decision table + copy/paste `.env` snippets)

### From Container Can't Reach Host

```bash
# Docker - verify host.docker.internal resolves
docker exec <container> getent hosts host.docker.internal

# Podman - verify host.containers.internal resolves
podman exec <container> getent hosts host.containers.internal
```

If not resolving, use host IP directly.

---

## Log Analysis

### YOLO26 Common Log Messages

| Message                     | Meaning         | Action             |
| --------------------------- | --------------- | ------------------ |
| `Model loaded successfully` | Service ready   | None               |
| `CUDA out of memory`        | Not enough VRAM | Free VRAM          |
| `Connection refused`        | Port conflict   | Check port usage   |
| `Failed to load image`      | Invalid image   | Check image format |

### Nemotron Common Log Messages

| Message                        | Meaning            | Action                |
| ------------------------------ | ------------------ | --------------------- |
| `Model loaded`                 | Service ready      | None                  |
| `ggml_cuda_init: failed`       | CUDA not available | Check NVIDIA drivers  |
| `bind: Address already in use` | Port conflict      | Kill existing process |
| `context length exceeded`      | Prompt too long    | Reduce context size   |

---

## Getting Help

When reporting issues, collect:

```bash
# System info
nvidia-smi
python3 --version
llama-server --version

# Service status
./scripts/start-ai.sh status

# Health checks
curl http://localhost:8095/health 2>&1
curl http://localhost:8091/health 2>&1

# Recent logs
tail -100 /tmp/yolo26-detector.log
tail -100 /tmp/nemotron-llm.log
```

---

## Next Steps

- [AI Performance](ai-performance.md) - Optimize performance
- [AI TLS](ai-tls.md) - Secure communications

---

## See Also

- [AI Issues (Reference)](../reference/troubleshooting/ai-issues.md) - More detailed AI troubleshooting
- [GPU Troubleshooting](../reference/troubleshooting/gpu-issues.md) - CUDA and VRAM issues
- [Connection Troubleshooting](../reference/troubleshooting/connection-issues.md) - Network problems
- [Troubleshooting Index](../reference/troubleshooting/index.md) - Full symptom reference

---

[Back to Operator Hub](./)
