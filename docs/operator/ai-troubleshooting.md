# AI Services Troubleshooting

> Diagnose and fix common AI service issues.

**Time to read:** ~10 min
**Prerequisites:** [AI Services Management](ai-services.md)

---

## Quick Diagnostics

Production AI is two containers: `ai-gateway` (:8090, Triton + routers) and `ai-vlm`
(:8098, llama.cpp behind the compose profile `vlm`). There is no `scripts/start-ai.sh`.

```bash
# Container status — note whether ai-vlm is ABSENT (profile never applied) or STOPPED
podman ps -a --filter name=ai-gateway --filter name=ai-vlm

# Aggregate gateway health (healthy only when Triton + all models are ready)
curl -s http://localhost:8090/health | jq

# Per-router health (the gateway mounts exactly two routers)
curl -s http://localhost:8090/yolo26/health | jq
curl -s http://localhost:8090/enrich-lt/health | jq

# VLM health — proves the serve is up, NOT that it can see images
curl -s http://localhost:8098/health | jq
curl -s http://localhost:8098/props | jq

# GPU availability
nvidia-smi

# Recent logs
podman logs --tail=100 ai-gateway 2>&1 | tail -50
podman logs --tail=100 ai-vlm 2>&1 | tail -50
```

The one host-run script in the tree is `ai/start_detector.sh`, which logs to the terminal.

### The query that ends most of these

Diagnose from `events`, never from `alerts` — **no event auto-creates an Alert on this
path**, so a stalled pipeline and a healthy-but-unnotified one both show zero alert rows:

```sql
SELECT verdict, count(*), max(created_at)
FROM events e JOIN event_verifications ev ON ev.event_id = e.id
GROUP BY verdict ORDER BY max(created_at) DESC;
```

| Signature                                             | What it means                                                           |
| ----------------------------------------------------- | ----------------------------------------------------------------------- |
| A run of `verification_failed` with NULL `risk_score` | The VLM is unreachable (below) or blind (below) — not an empty camera   |
| Events landing, `risk_score` populated                | The path works. Specialist lines may still be degraded — see next table |
| No events at all                                      | Upstream of AI: FileWatcher / camera drop / Redis. Not an AI failure    |

And the specialist census:

```bash
curl -s http://localhost:8000/metrics | grep hsi_specialist_unavailable_total
```

---

## ai-vlm Is Not Running

`ai-vlm` is the only shipped AI service behind a compose profile, so **`up -d` without
`--profile vlm` does not start it** — and podman-compose drops a service whose profile is
inactive _before_ it resolves the names on your command line. The failure is quiet:

```bash
# Wrong: reports success, starts nothing
podman compose -f docker-compose.prod.yml up -d ai-vlm

# Right
podman compose -f docker-compose.prod.yml --profile vlm up -d ai-vlm
```

### restart-all.sh will re-create this for you

`scripts/restart-all.sh` names both AI services (`AI_SERVICES="ai-gateway ai-vlm"`) but
passes a profile only for the monitoring group. Restarting "AI" through it therefore
restarts the gateway, cannot start the VLM, and **reports success**:

```bash
# Verify after any restart-all run, do not trust its summary:
podman ps -a --filter name=ai-vlm
```

Use the explicit command instead of the script for the AI group.

### Confirm the compose-level hole is closed

The backend's dev default for `AI_VLM_URL` is `http://localhost:8098`, which inside a
container is the container itself. `docker-compose.prod.yml` threads
`AI_VLM_URL=${AI_VLM_URL:-http://ai-vlm:8098}` to prevent exactly that. Check what the
running container actually holds:

```bash
podman exec backend printenv AI_VLM_URL
podman exec backend curl -fsS http://ai-vlm:8098/health
```

---

## The VLM Answers But Cannot See

A projector-less `llama-server` starts happily, answers `200` on `/health`, and passes
both the compose healthcheck and the image's own `HEALTHCHECK`. Every `vlm_assess` call
then degrades silently against a text-only server while events keep landing.

```bash
# 1. Are BOTH weights present where compose mounts them?
ls -l "${AI_MODELS_PATH:-/export/ai_models}/vlm/"

# 2. What does the container think its paths are?
podman exec ai-vlm sh -c 'echo "MODEL_PATH=$MODEL_PATH"; echo "MMPROJ_PATH=$MMPROJ_PATH"'

# 3. Did llama-server actually load a projector?
podman logs ai-vlm 2>&1 | grep -i mmproj
```

An empty `MMPROJ_PATH`, or a path that does not exist inside the container, is the bug.
The Dockerfile builds the projector argument conditionally on `[ -n "$MMPROJ_PATH" ]`.

Two fetch hazards worth checking before you debug anything deeper:

- **Wrong projector variant.** The repo also ships an **F16** mmproj. Taking it yields a
  serve that starts and a file matching no known pin. The shipped identity is the **Q8_0**
  projector.
- **File mode.** Weights fetched into the models root commonly land **mode 640**; `ai/vlm`
  runs as uid 1000 and dies with `Permission denied` on a file the host operator can read
  fine. `chmod 644` both files.

Nothing in this repo can tell you the weights are missing — the model check reads the
**env string**, so a fabricated env naming nonexistent files still passes. Verify on disk.

---

## Gateway / Triton Issues

### Gateway Never Becomes Healthy

```bash
podman logs ai-gateway 2>&1 | grep -iE "error|failed|model"
```

Common causes:

- **Model weights missing** — Triton loads every model in its repository at startup
  (`--model-control-mode=none`; residency prunes the repository to `yolo26` + `reid`,
  plus `threat` when `GATEWAY_ENABLE_THREAT=true`). Run `./ai/download_models.sh`
  (manifest: `models.yml`), then restart the gateway.
- **`start_period` not elapsed** — the compose healthcheck allows 180s before it counts
  failures.
- **GPU not visible** — check the CDI spec exists (`ls /etc/cdi/nvidia.yaml`) and
  `CUDA_VISIBLE_DEVICES=${GPU_AI_SERVICES:-1}` points at a real card; verify with
  `podman exec ai-gateway nvidia-smi`.

### One Router Reports Degraded

```bash
curl -s http://localhost:8090/enrich-lt/health | jq
# Triton's own control API is container-internal on 8000 (metrics on 8002):
podman exec ai-gateway curl -s http://localhost:8000/v2/models/reid | jq '.state,.ready'
```

### Restart the Gateway

```bash
podman compose -f docker-compose.prod.yml restart ai-gateway
```

---

## YOLO26 Issues

### Standalone Host-Run Server Fails to Start

```bash
uv sync --extra dev      # ModuleNotFoundError: No module named 'transformers'
```

The script logs to the terminal; it defaults to port 8090, which **is** the gateway's
host port — run it with `ai-gateway` down or set `YOLO26_PORT`.

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

## Specialist Legs Read `unavailable`

The `faces` and `person_reid` lines are **residency-gated**, and residency ships off.
`get_reid_handle()` and `get_face_leg_handles()` are membership reads that never trigger
a load — by design. The handle exists only if the boot preload sweep put it there, and
that sweep is gated on `BACKEND_MODEL_PRELOAD`, which ships **`false`**; `setup.py`
writes `true` only when it detects **>= 24 GB** VRAM.

```bash
podman exec backend printenv BACKEND_MODEL_PRELOAD
curl -s http://localhost:8000/metrics | grep hsi_specialist_unavailable_total
```

Non-zero and unbroken since boot ⇒ that leg has **never** run. The fix is host-specific:
on a >= 24 GB card, set `BACKEND_MODEL_PRELOAD=true` in the host `.env`. Note the shipped
default is pinned by a gate test, so changing the **default** is a gate edit — set it in
your `.env`.

This degradation is honest, not silent garbage: the unavailable line reports
`"unavailable: specialist did not run"`, increments the counter with a bounded reason code
(`weights_absent`, `package_absent`, `space_mismatch`, …), logs with `exc_info`, and keeps
`not_identifiable` distinct from `unknown` so a degraded leg can never masquerade as an
empty result.

The plate leg is the exception — `fast_alpr_loader` loads on demand.

---

## VLM Issues

### Service Won't Start

```bash
podman compose -f docker-compose.prod.yml --profile vlm logs ai-vlm 2>&1 | tail -50
```

**`failed to load model`** — the GGUF pair is missing, misnamed, unreadable (mode 640), or
the wrong variant. See [The VLM Answers But Cannot See](#the-vlm-answers-but-cannot-see).
`./ai/download_models.sh` does **not** fetch these weights — nothing in this repo does.
Place them per [AI Installation](ai-installation.md#2-operator-placed-the-vlm-gguf-pair).

**`ggml_init_cublas: failed to initialize CUDA`**

```bash
nvidia-smi
sudo systemctl restart nvidia-persistenced
```

**`bind: Address already in use`**

```bash
lsof -ti:8098 | xargs kill -9
podman compose -f docker-compose.prod.yml --profile vlm up -d ai-vlm
```

### Slow to Answer / Waking From Sleep

Cold load is covered by the `start_period` of 120s (mirrored from the image's own
`HEALTHCHECK --start-period=120s`). A service reported `unhealthy` inside that window is
early, not broken.

After `VLM_SLEEP_IDLE_SECONDS` (default 300) idle, the weights drop to CPU RAM. The next
request pays a RAM→VRAM copy of the whole pair. The client's wake ping is budgeted at
`AI_VLM_WAKE_TIMEOUT_SECONDS=90.0` and a failed wake is **swallowed**, not retried — so
the first verdict after a quiet night can read like an outage.

Set `VLM_SLEEP_IDLE_SECONDS=` (empty) to disable sleeping and hold the VRAM permanently.

### The Enforcement Probe Refuses to Trust the Serve

`VLM_ENFORCEMENT_PROBE_ENABLED=true` runs one JSON-schema probe per endpoint+build before
the first verdict is trusted, and asserts the build string from `/props` against
`VLM_REQUIRED_BUILD`. A NOT-ENFORCED verdict **fails closed by design**.

```bash
curl -s http://localhost:8098/props | jq
```

If you rebuilt llama.cpp from a different source, the build string no longer matches the
pinned `b7972`. Update `VLM_REQUIRED_BUILD` to the build you actually ship — do not blank
it in production, since an empty value skips the assertion and lets a stale proof launder
onto an unknown build.

---

## Service Unhealthy

### Diagnosis

```bash
# Check if services are responding
curl -v http://localhost:8090/health
curl -v http://localhost:8098/health

# Container state + restart counts
podman inspect -f '{{.State.Status}} {{.RestartCount}}' ai-gateway ai-vlm

# Monitor GPU
nvidia-smi -l 1
```

### Solutions

1. Restart containers:
   `podman compose -f docker-compose.prod.yml restart ai-gateway` then
   `podman compose -f docker-compose.prod.yml --profile vlm up -d --force-recreate ai-vlm`
2. Check logs for errors: `podman compose -f docker-compose.prod.yml logs --tail=100 ai-gateway`
3. Verify CUDA (host-run only): `python3 -c "import torch; print(torch.cuda.is_available())"`

---

## Slow Inference

### Symptoms

- Detection: 200-500ms instead of 30-50ms
- Verdict: 30-60 seconds instead of single-digit seconds

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

**Prompt overflow:** a full batch is not small — detections arrive at roughly 61 tokens a
row and `batch_max_detections` is 500. The client **fits** the prompt to the served slot
(`VLM_CTX_SIZE / VLM_PARALLEL`, shipped 16,384) and drops the weakest rows, saying so in
the prompt. If verdicts are slow _and_ the reasoning mentions dropped rows, that is the
fitter working, not a fault.

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

Services crash with OOM errors (`CUDA out of memory` in gateway/vlm logs).

### Solutions

**1. Free VRAM:**

```bash
# Restart AI containers (fuser -k kills *all* GPU processes — avoid on shared hosts)
podman compose -f docker-compose.prod.yml restart ai-gateway
podman compose -f docker-compose.prod.yml --profile vlm up -d --force-recreate ai-vlm
```

**2. Let the VLM release its VRAM when idle:** lower `VLM_SLEEP_IDLE_SECONDS` so the
weights return to CPU RAM between bursts, or drop to the measured 4B pair via
`VLM_MODEL_PATH` + `VLM_MMPROJ_PATH` + `VLM_MODEL_ID`.

**3. Trim the KV pool:** the shipped `CACHE_TYPE_K`/`CACHE_TYPE_V` are already `q8_0`
(half the f16 pool). `VLM_CTX_SIZE`/`VLM_PARALLEL` set the pool size, and the backend
reads the same pair for its prompt budget — change the pair, never one side of it.

**4. Reduce concurrent load:** the backend caps parallel AI calls with
`AI_MAX_CONCURRENT_INFERENCES` (`backend/core/config.py`).

---

## Connection Issues

### Backend Can't Reach AI Services

**Symptoms:**

```
httpx.ConnectError: [Errno 111] Connection refused
```

**Check:**

1. Are the AI containers up and healthy? `podman ps -a` (the gateway needs ~3 min for
   Triton to load its models; `ai-vlm` needs its profile to exist at all)
2. Is the URL correct in `.env` / compose env (`AI_GATEWAY_URL`, `YOLO26_URL`,
   `AI_VLM_URL`)? In the compose stack these are `http://ai-gateway:8090/...` and
   `http://ai-vlm:8098`.
3. Is there a firewall blocking the ports? (Both AI services bind `127.0.0.1` on the
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
| `CUDA out of memory`           | Not enough VRAM    | Free VRAM / move the VLM to GPU 0  |
| `model … unavailable`          | Weights missing    | `./ai/download_models.sh`, restart |
| `address already in use`       | Port conflict      | Check who holds 8090/8002          |

### ai-vlm Common Log Messages

| Message                               | Meaning                     | Action                                                                |
| ------------------------------------- | --------------------------- | --------------------------------------------------------------------- |
| `model loaded`                        | Serve ready                 | Still prove the projector — see above                                 |
| no `mmproj` line at all               | Text-only serve             | Set `VLM_MMPROJ_PATH` to a real file                                  |
| `ggml_cuda_init: failed`              | CUDA not available          | Check NVIDIA drivers                                                  |
| `Permission denied` reading a `.gguf` | Weights landed mode 640     | `chmod 644` both files                                                |
| `bind: Address already in use`        | Port conflict               | Kill the process holding 8098                                         |
| `context length exceeded`             | Prompt larger than the slot | The fitter should prevent this; check `VLM_CTX_SIZE` / `VLM_PARALLEL` |

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
curl -s http://localhost:8098/health 2>&1
curl -s http://localhost:8098/props  2>&1

# Specialist census
curl -s http://localhost:8000/metrics | grep hsi_specialist_unavailable_total

# Recent logs
podman logs --tail=100 ai-gateway 2>&1
podman logs --tail=100 ai-vlm 2>&1
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
- [AI pipeline: current state](../architecture/ai-pipeline-current-state.md) - The measured path, including the four silent-failure surfaces

---

[Back to Operator Hub](README.md)
