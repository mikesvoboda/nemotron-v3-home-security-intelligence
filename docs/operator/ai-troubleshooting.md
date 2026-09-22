# AI Services Troubleshooting

> Diagnose and fix common AI service issues.

**Time to read:** ~10 min
**Prerequisites:** [AI Services Management](ai-services.md)

---

## Quick Diagnostics

Production AI is two containers: `ai-gateway` (:8090, Triton + routers) and `ai-llm`
(:8091, llama.cpp). There is no `scripts/start-ai.sh`.

```bash
# Container status
podman ps -a --filter name=ai-gateway --filter name=ai-llm

# Aggregate gateway health (healthy only when Triton + all models are ready)
curl -s http://localhost:8090/health | jq

# Per-router health
curl -s http://localhost:8090/yolo26/health | jq
curl -s http://localhost:8090/florence/health | jq
curl -s http://localhost:8090/clip/health | jq
curl -s http://localhost:8090/enrichment/health | jq
curl -s http://localhost:8090/enrich-lt/health | jq

# LLM health
curl -s http://localhost:8091/health | jq

# GPU availability
nvidia-smi

# Recent logs
podman logs --tail=100 ai-gateway 2>&1 | tail -50
podman logs --tail=100 ai-llm 2>&1 | tail -50
```

Host-run dev services (started via `ai/start_detector.sh`, `ai/start_llm.sh`,
`ai/start_nemotron.sh`) log to the terminal, except `start_nemotron.sh` which writes
`/tmp/nemotron.log`.

---

## Gateway / Triton Issues

### Gateway Never Becomes Healthy

```bash
podman logs ai-gateway 2>&1 | grep -iE "error|failed|model"
```

Common causes:

- **Model weights missing** — Triton loads every model in `/models/zoo` at startup
  (`--model-control-mode=none`). Run `./ai/download_models.sh` (manifest: `models.yml`),
  then restart the gateway.
- **`start_period` not elapsed** — Triton initialises 13+ models; the compose healthcheck
  allows 180s before it counts failures.
- **GPU not visible** — check the CDI spec exists (`ls /etc/cdi/nvidia.yaml`) and
  `CUDA_VISIBLE_DEVICES=${GPU_AI_SERVICES:-1}` points at a real card; verify with
  `podman exec ai-gateway nvidia-smi`.

### One Router Reports Degraded

```bash
curl -s http://localhost:8090/enrich-lt/health | jq   # per-model ready flags
podman exec ai-gateway curl -s http://localhost:8002/v2/models/pose | jq '.state,.ready'
```

### Restart the Gateway

```bash
podman compose -f docker-compose.prod.yml restart ai-gateway
```

---

## YOLO26 Issues

### Standalone Host-Run Server Fails to Start

```bash
tail -f /tmp/yolo26-detector.log 2>/dev/null || # logs go to the terminal (ai/start_detector.sh)
uv sync --extra dev      # ModuleNotFoundError: No module named 'transformers'
```

If `YOLO26_MODEL_PATH` points at a missing TensorRT engine, the server falls back per
`YOLO26_AUTO_REBUILD` (rebuild from `YOLO26_PT_MODEL_PATH`) and then to PyTorch — see the
startup messages in its log.

**CUDA out of memory:**

```
RuntimeError: CUDA out of memory
```

1. Close other GPU applications; check VRAM: `nvidia-smi`
2. Restart the gateway: `podman compose -f docker-compose.prod.yml restart ai-gateway`

---

## Nemotron LLM Issues

### Service Won't Start

```bash
podman logs ai-llm 2>&1 | tail -50
```

**llama-server not found (host-run only):** the `ai-llm` image builds llama.cpp inside the
image; for `ai/start_nemotron.sh` on the host, set `LLAMA_SERVER_PATH` or install it —
see [AI Installation](ai-installation.md).

**Model file not found:**

```
error: failed to load model
```

```bash
./ai/download_models.sh   # fetches the Nemotron-3-Nano-30B GGUF listed in models.yml
```

**CUDA initialization failed:**

```
ggml_init_cublas: failed to initialize CUDA
```

```bash
nvidia-smi
sudo systemctl restart nvidia-persistenced
```

**Port already in use:**

```
error: bind: Address already in use
```

```bash
lsof -ti:8091 | xargs kill -9
podman compose -f docker-compose.prod.yml restart ai-llm
```

### LLM Slow to Answer

The Nano 30B model takes minutes to load (compose `start_period` 300s). Watch it:

```bash
podman compose -f docker-compose.prod.yml logs -f ai-llm
```

---

## Service Unhealthy

### Diagnosis

```bash
# Check if services are responding
curl -v http://localhost:8090/health
curl -v http://localhost:8091/health

# Container state + restart counts
podman inspect -f '{{.State.Status}} {{.RestartCount}}' ai-gateway ai-llm

# Monitor GPU
nvidia-smi -l 1
```

### Solutions

1. Restart containers:
   `podman compose -f docker-compose.prod.yml restart ai-gateway ai-llm`
2. Check logs for errors: `podman compose -f docker-compose.prod.yml logs --tail=100 ai-gateway`
3. Verify CUDA (host-run only): `python3 -c "import torch; print(torch.cuda.is_available())"`

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
# Verify CUDA is being used (host-run server)
python3 -c "import torch; print(torch.cuda.is_available())"
# Gateway: confirm Triton model instances are on GPU
podman exec ai-gateway nvidia-smi
```

**Thermal throttling:**

```bash
nvidia-smi --query-gpu=temperature.gpu --format=csv
```

If > 85C, improve cooling or reduce load.

**Concurrent load:** other processes using the GPU — check
`nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv`.

---

## Out of Memory (OOM)

### Symptoms

Services crash with OOM errors (`CUDA out of memory` in gateway/llm logs).

### Solutions

**1. Free VRAM:**

```bash
# Restart AI containers (fuser -k kills *all* GPU processes — avoid on shared hosts)
podman compose -f docker-compose.prod.yml restart ai-gateway ai-llm
```

**2. Shrink the LLM footprint:** `GPU_LAYERS` defaults to `auto` (all layers on GPU);
lowering it (e.g. `GPU_LAYERS=25`) offloads fewer layers to VRAM — see
[AI Configuration](ai-configuration.md). Or run the gateway on the second GPU
(`GPU_AI_SERVICES=1`, already the default split).

**3. Reduce concurrent load:** the backend caps parallel AI calls with
`AI_MAX_CONCURRENT_INFERENCES` (config.py default 4 on the standard build).

---

## Connection Issues

### Backend Can't Reach AI Services

**Symptoms:**

```
httpx.ConnectError: [Errno 111] Connection refused
```

**Check:**

1. Are the AI containers up and healthy? `podman ps -a` (the gateway needs ~3 min for
   Triton to load all models)
2. Is the URL correct in `.env` / compose env (`AI_GATEWAY_URL`, `YOLO26_URL`,
   `NEMOTRON_URL`)? In the compose stack these are `http://ai-gateway:8090/...` and
   `http://ai-llm:8091` — the legacy per-model hostnames (`ai-yolo26`, `ai-florence`,
   `ai-clip`, `ai-enrichment`) no longer exist.
3. Is there a firewall blocking the ports? (The gateway and LLM bind `127.0.0.1` on the
   host by default — cross-host access needs a proxy/tunnel.)

**Docker/Podman networking:**

The correct URL depends on your deployment mode (production compose DNS vs host-run AI vs
"backend container + host AI"). Start here:

- [Deployment Modes & AI Networking](deployment-modes.md) (decision table + copy/paste
  `.env` snippets)

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

### Gateway Common Log Messages

| Message                        | Meaning            | Action                             |
| ------------------------------ | ------------------ | ---------------------------------- |
| `successfully loaded 'yolo26'` | Triton model ready | None                               |
| `CUDA out of memory`           | Not enough VRAM    | Free VRAM / move LLM to GPU 0      |
| `model … unavailable`          | Weights missing    | `./ai/download_models.sh`, restart |
| `address already in use`       | Port conflict      | Check who holds 8090/8002          |

### Nemotron Common Log Messages

| Message                        | Meaning            | Action                |
| ------------------------------ | ------------------ | --------------------- |
| `model loaded`                 | Service ready      | None                  |
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

# Service status
podman ps -a

# Health checks
curl -s http://localhost:8090/health 2>&1
curl -s http://localhost:8091/health 2>&1

# Recent logs
podman logs --tail=100 ai-gateway 2>&1
podman logs --tail=100 ai-llm 2>&1
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

[Back to Operator Hub](README.md)
