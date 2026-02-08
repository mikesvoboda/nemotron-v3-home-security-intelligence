# Triton Inference Server Migration Plan

> **Date:** 2026-02-08
> **Status:** Approved Design
> **Author:** Mike Svoboda + Claude Opus 4.6

## Problem Statement

The AI pipeline runs 5 separate containers on GPU 1 (RTX A400 4GB), each with its own PyTorch CUDA runtime. The duplicate CUDA contexts consume ~2.4 GB of overhead, leaving only 360 MiB free on a 4 GB card. This prevents on-demand models from loading and limits enrichment coverage.

| Container | Model VRAM | CUDA Overhead | Total |
|-----------|-----------|---------------|-------|
| ai-yolo26 | 5 MiB | ~170 MiB | ~175 MiB |
| ai-clip | 834 MiB | ~384 MiB | ~1,218 MiB |
| ai-florence | 460 MiB | ~930 MiB | ~1,390 MiB |
| ai-enrichment | 760 MiB | ~170 MiB | ~930 MiB |
| ai-enrichment-light | 0 MiB | 0 MiB | 0 MiB |
| **Total** | | | **~3,713 MiB / 4,094 MiB** |

## Solution: Single Triton Container + AI Gateway

Consolidate all GPU 1 models into a single NVIDIA Triton Inference Server with one shared CUDA context. A lightweight FastAPI gateway translates between the existing backend REST APIs and Triton's gRPC protocol.

### Projected VRAM After Migration

| Backend | Models | VRAM |
|---------|--------|------|
| TensorRT | yolo26, clip, pose, threat, fashion-clip | ~500 MiB |
| ONNX Runtime | vehicle, demographics (age+gender), pet, depth, reid | ~350 MiB |
| Python (shared PyTorch) | florence-2, xclip-action | ~860 MiB |
| Triton server overhead | (single CUDA context) | ~300 MiB |
| **Total** | **13 models** | **~2,010 MiB / 4,094 MiB** |

**All models stay resident in memory.** No on-demand loading needed. ~2 GB free headroom for inference buffers.

## Architecture

```
                    ┌─────────────────────────────────┐
                    │          Backend (8001)          │
                    │                                  │
                    │  AI_GATEWAY_URL=http://gw:8090   │
                    │                                  │
                    │  detector_client  → /yolo26/*    │
                    │  clip_client      → /clip/*      │
                    │  florence_client   → /florence/*  │
                    │  enrichment_client → /enrichment/*│
                    │  enrich_light_cli → /enrich-lt/* │
                    └──────────┬──────────────────────┘
                               │ HTTP (existing REST APIs)
                               ▼
              ┌───────────────────────────────────────┐
              │       AI Gateway (FastAPI, CPU)        │
              │            Port 8090                   │
              │                                        │
              │  /yolo26/detect   → triton:yolo26      │
              │  /clip/embed      → triton:clip        │
              │  /florence/extract → triton:florence2   │
              │  /enrichment/*    → triton:various     │
              │  /enrich-lt/*     → triton:various     │
              │  /health          → aggregated health  │
              │  /metrics         → prometheus export  │
              └──────────┬────────────────────────────┘
                         │ gRPC (localhost:8001)
                         ▼
              ┌───────────────────────────────────────┐
              │     Triton Inference Server            │
              │     GPU 1 (RTX A400 4GB)              │
              │                                        │
              │  TensorRT:  yolo26, clip, pose,        │
              │             threat, fashion_clip        │
              │  ONNX RT:   vehicle, demographics_age, │
              │             demographics_gender, pet,   │
              │             depth, reid                 │
              │  Python:    florence2, xclip_action     │
              │                                        │
              │  All 13 models resident in memory       │
              └───────────────────────────────────────┘
```

### Component Responsibilities

1. **Backend** — Unchanged. All 5 HTTP clients keep their existing APIs, circuit breakers, retry logic. Single env var `AI_GATEWAY_URL` replaces 5 individual `*_URL` vars. Each client prepends its service prefix (`/clip/embed`, `/florence/extract`, etc.).

2. **AI Gateway** — Thin FastAPI process on CPU (no GPU). Receives REST calls, translates to Triton gRPC, reformats responses. ~200 lines per model adapter. Runs in same container as Triton. Exposes per-model Prometheus metrics and aggregated health endpoint.

3. **Triton Inference Server** — Hosts all 13 models on GPU 1 in a single CUDA context. Three backends: TensorRT (5 models), ONNX Runtime (6 models), Python (2 models).

## Model Repository Structure

```
ai/triton/model_repository/
├── yolo26/
│   ├── config.pbtxt              # TensorRT, FP16
│   └── 1/model.plan
├── clip/
│   ├── config.pbtxt              # TensorRT, FP16
│   └── 1/model.plan
├── pose/
│   ├── config.pbtxt              # TensorRT, FP16
│   └── 1/model.plan
├── threat/
│   ├── config.pbtxt              # TensorRT, FP16
│   └── 1/model.plan
├── fashion_clip/
│   ├── config.pbtxt              # TensorRT, FP16
│   └── 1/model.plan
├── vehicle/
│   ├── config.pbtxt              # ONNX Runtime
│   └── 1/model.onnx
├── demographics_age/
│   ├── config.pbtxt              # ONNX Runtime
│   └── 1/model.onnx
├── demographics_gender/
│   ├── config.pbtxt              # ONNX Runtime
│   └── 1/model.onnx
├── pet/
│   ├── config.pbtxt              # ONNX Runtime
│   └── 1/model.onnx
├── depth/
│   ├── config.pbtxt              # ONNX Runtime
│   └── 1/model.onnx
├── reid/
│   ├── config.pbtxt              # ONNX Runtime
│   └── 1/model.onnx
├── florence2/
│   ├── config.pbtxt              # Python backend
│   └── 1/model.py
└── xclip_action/
    ├── config.pbtxt              # Python backend
    └── 1/model.py
```

### Model Backend Selection Rationale

| Model | Backend | Why |
|-------|---------|-----|
| yolo26, clip, pose, threat, fashion-clip | **TensorRT** | Standard architectures, max efficiency, 50-90% VRAM reduction |
| vehicle, demographics, pet, depth, reid | **ONNX Runtime** | Simple models, straightforward export, good efficiency |
| florence2 | **Python** | `trust_remote_code=True`, autoregressive decoder, custom post-processing |
| xclip_action | **Python** | `trust_remote_code=True`, custom cross-frame temporal attention |

Florence-2 and X-CLIP cannot be exported to TensorRT/ONNX due to custom HuggingFace model code and autoregressive generation. They share a single PyTorch runtime in Triton's Python backend.

## AI Gateway Design

### File Structure

```
ai/gateway/
├── Dockerfile
├── requirements.txt          # fastapi, tritonclient[grpc], uvicorn, pillow
├── main.py                   # App, routing, health, metrics
├── triton_client.py          # Shared gRPC client pool
├── adapters/
│   ├── yolo26.py             # /yolo26/detect, /yolo26/segment
│   ├── clip.py               # /clip/embed, /clip/classify, etc.
│   ├── florence.py           # /florence/extract, /florence/ocr, etc.
│   ├── enrichment.py         # /enrichment/enrich, /enrichment/vehicle, etc.
│   └── enrichment_light.py   # /enrich-lt/pose, /enrich-lt/threat, etc.
└── utils.py                  # base64 decode, image resize, numpy conversion
```

### Adapter Pattern

Each adapter translates REST → Triton gRPC → REST:

```python
@router.post("/embed")
async def embed(request: EmbedRequest) -> EmbedResponse:
    start = time.monotonic()
    image = decode_base64_image(request.image)
    tensor = preprocess_clip(image)                   # (1, 3, 224, 224) FP16
    result = await triton.infer(
        model_name="clip",
        inputs={"image": tensor},
        outputs=["embedding"],
    )
    embedding = l2_normalize(result["embedding"][0].tolist())
    return {"embedding": embedding, "inference_time_ms": (time.monotonic() - start) * 1000}
```

### Backend Client Changes

Single env var replaces 5:

```env
AI_GATEWAY_URL=http://ai-gateway:8090
```

Each client prepends its prefix:

```python
# clip_client.py
self.base_url = f"{settings.ai_gateway_url}/clip"

# florence_client.py
self.base_url = f"{settings.ai_gateway_url}/florence"
```

## Observability

### Per-Model Metrics (Triton native)

Triton exposes Prometheus metrics at `:8002/metrics` with per-model granularity:

```prometheus
nv_inference_request_success{model="clip",version="1"} 1547
nv_inference_request_success{model="yolo26",version="1"} 3201
nv_inference_compute_infer_duration_us{model="clip",version="1"} 12400
nv_inference_queue_duration_us{model="clip",version="1"} 150
nv_gpu_utilization{gpu_uuid="..."} 0.45
nv_gpu_memory_used_bytes{gpu_uuid="..."} 2105000000
```

### Gateway Application Metrics

```prometheus
hsi_ai_inference_duration_seconds{service="clip",endpoint="embed"}
hsi_ai_inference_duration_seconds{service="florence",endpoint="ocr"}
hsi_ai_inference_errors_total{service="enrichment",endpoint="vehicle"}
hsi_circuit_breaker_state{service="clip",endpoint="embed"}
```

### Health Checking (3 layers)

| Layer | Endpoint | What It Checks |
|-------|----------|---------------|
| Triton native | `GET :8000/v2/health/ready` | Server ready, all models loaded |
| Triton per-model | `GET :8000/v2/models/{name}/ready` | Individual model status |
| Gateway aggregated | `GET :8090/health` | All models + gateway (matches current backend format) |

## Container & Deployment

### Single Container (Gateway + Triton)

```dockerfile
FROM nvcr.io/nvidia/tritonserver:25.01-py3

RUN pip install --no-cache-dir fastapi uvicorn tritonclient[grpc] pillow numpy prometheus-client

COPY ai/gateway/ /app/gateway/
COPY ai/triton/model_repository/ /models/repository/
COPY ai/gateway/entrypoint.sh /entrypoint.sh

ENV TRITON_MODEL_REPOSITORY=/models/repository
ENV GATEWAY_PORT=8090

EXPOSE 8090
ENTRYPOINT ["/entrypoint.sh"]
```

### Launch Command (replaces 5 containers)

```bash
podman run -d \
  --name ai-gateway \
  --network security-net \
  --device nvidia.com/gpu=1 \
  --security-opt label=disable \
  -v /export/ai_models/model-zoo:/models/zoo:ro \
  -v /export/ai_models/triton:/models/cache \
  -p 127.0.0.1:8090:8090 \
  ai-gateway
```

### .env Changes

```env
# Remove
YOLO26_PORT=8095
CLIP_PORT=8093
FLORENCE_PORT=8092
ENRICHMENT_PORT=8094
ENRICHMENT_LIGHT_PORT=8096

# Add
AI_GATEWAY_PORT=8090
AI_GATEWAY_URL=http://ai-gateway:8090
```

## Model Export Pipeline

Export scripts convert HuggingFace/PyTorch models to Triton-compatible formats:

```
ai/gateway/export/
├── export_clip.py            # HF → ONNX → TensorRT FP16
├── export_fashion_clip.py    # HF → ONNX → TensorRT FP16
├── export_vehicle.py         # HF → ONNX
├── export_demographics.py    # HF → ONNX (age + gender)
├── export_pet.py             # HF → ONNX
├── export_depth.py           # HF → ONNX
├── export_reid.py            # PyTorch → ONNX
└── export_all.sh             # Runs all exports, caches results
```

YOLO26 TensorRT engine already exists. Pose and threat TensorRT engines export via Ultralytics `.export(format='engine')`. Exported files are cached in a persistent volume and reused across deploys.

## Migration Phases

### Phase 1: Model Export Pipeline

Build export scripts, convert all models, validate outputs match PyTorch originals.

**Tasks:**
- Write 7 export scripts (CLIP, fashion-CLIP, vehicle, demographics, pet, depth, reid)
- Copy existing YOLO26 TensorRT engine
- Export pose/threat via Ultralytics TensorRT
- Write Python backend `model.py` for Florence-2 and X-CLIP
- Write `config.pbtxt` for all 13 models
- Validate: load each in standalone Triton, compare outputs (cosine sim > 0.999, IoU > 0.99)

**Deliverable:** Fully populated `ai/triton/model_repository/`

**Risk:** None — no runtime changes, purely offline work.

### Phase 2: Gateway + Triton Container

Build gateway adapters and Triton container. Deploy alongside existing services on a different port.

**Tasks:**
- Write `ai/gateway/main.py` (health, metrics, routing)
- Write 5 adapter files (yolo26, clip, florence, enrichment, enrichment-light)
- Write `triton_client.py` (gRPC connection pool)
- Write `Dockerfile` and `entrypoint.sh`
- Deploy on port 8090, test with seed script via env override

**Validation:**
```bash
AI_GATEWAY_URL=http://localhost:8090 uv run python scripts/seed-events.py --validate
```

**Deliverable:** Working `ai-gateway` container, verified equivalent to current 5-service deployment.

**Risk:** Low — old services still running, gateway runs in parallel.

### Phase 3: Backend Client Migration

Update 5 backend clients to support `AI_GATEWAY_URL`. Feature-flagged with `USE_AI_GATEWAY` toggle.

**Tasks:**
- Add `AI_GATEWAY_URL` to backend settings
- Update each client's `__init__` (1 line each)
- Add `USE_AI_GATEWAY=true/false` toggle
- Test both modes with seed + validation

**Deliverable:** Backend supports both old and new modes.

**Risk:** Minimal — toggle provides instant rollback.

### Phase 4: Cutover & Cleanup

Switch to gateway as default, remove old containers and code.

**Tasks:**
- Set `USE_AI_GATEWAY=true` as default
- Stop 5 old AI containers
- Update redeploy script, docker-compose, CLAUDE.md, AGENTS.md, .env.example
- Archive old Dockerfiles to `ai/legacy/`

**Deliverable:** Single `ai-gateway` container replaces 5 AI containers.

### Rollback Safety

| Phase | Rollback |
|-------|----------|
| Phase 1 | No impact — nothing running changed |
| Phase 2 | Delete gateway container, old services unaffected |
| Phase 3 | Set `USE_AI_GATEWAY=false`, instant rollback |
| Phase 4 | Re-deploy old containers from cached images |

## Success Criteria

- [ ] All 13 models loaded and healthy in single Triton container
- [ ] GPU 1 VRAM usage < 2.5 GB (vs current 3.7 GB)
- [ ] Per-model Prometheus metrics available
- [ ] Detection/enrichment accuracy unchanged (< 0.1% variance)
- [ ] Inference latency within 10% of current (TensorRT models should be faster)
- [ ] Seed script validation passes with equivalent results
- [ ] Backend circuit breakers and health checks functional
- [ ] Single `AI_GATEWAY_URL` env var replaces 5 service URLs
