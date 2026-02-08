# Triton Inference Server Validation Report

**Date:** 2026-02-08
**Investigator:** Claude Opus 4.6 (validation agent)
**Verdict:** TRITON IS RUNNING. The pipeline mapper agent was WRONG.

---

## Executive Summary

NVIDIA Triton Inference Server **IS actively running** inside the `ai-gateway` container. All 13 models are loaded and healthy. The backend is configured to route all AI inference through the gateway. The pipeline mapper agent's claim that Triton is "dead code" is incorrect.

---

## 1. Running Containers

```
NAMES                                                       STATUS                    IMAGE
ai-gateway                                                  Up 13 minutes             localhost/ai-gateway:latest
ai-llm                                                      Up 5 minutes              localhost/ai-llm:latest
frontend                                                    Up 13 minutes             localhost/frontend:latest
backend                                                     Exited (1) 5 min ago      localhost/backend:latest
(+ 16 infrastructure containers: postgres, redis, prometheus, grafana, etc.)
```

**Key finding:** There are NO standalone AI service containers (no `ai-yolo26`, `ai-florence`, `ai-clip`, `ai-enrichment`, `ai-enrichment-light`). The gateway has replaced all five.

---

## 2. Triton Health Check - All 13 Models Loaded

```bash
$ curl http://127.0.0.1:8090/health
```

```json
{
  "status": "healthy",
  "triton_server_ready": true,
  "models": {
    "yolo26": true,
    "clip": true,
    "florence2": true,
    "vehicle": true,
    "fashion_clip": true,
    "demographics_age": true,
    "demographics_gender": true,
    "pet": true,
    "depth": true,
    "reid": true,
    "pose": true,
    "threat": true,
    "xclip_action": true
  },
  "models_loaded": 13,
  "models_total": 13
}
```

---

## 3. Architecture (Actual, Running)

```
Backend (port 8000)
   |
   +-- USE_AI_GATEWAY=true
   +-- AI_GATEWAY_URL=http://ai-gateway:8090
   |
   v
AI Gateway container (port 8090, localhost/ai-gateway:latest)
   |
   +-- FastAPI app (uvicorn, port 8090) — HTTP REST adapter layer
   |     Routes: /yolo26/*, /clip/*, /florence/*, /enrichment/*, /enrich-lt/*
   |
   +-- Triton Inference Server (inside same container)
   |     gRPC port 8001 (internal, not exposed)
   |     HTTP port 8000 (internal, not exposed)
   |     Metrics port 8002 (internal, not exposed)
   |
   +-- tritonclient.grpc.aio (Python gRPC client connecting to localhost:8001)
   |
   v
13 Triton models (ONNX + Python backends):
   GPU models (GPU 0 = NVIDIA RTX A400 4GB, device 1):
     - yolo26 (ONNX, GPU) — 78MB
     - clip (ONNX, GPU) — 1.2GB
     - florence2 (Python backend, GPU)
   CPU models:
     - demographics_age, demographics_gender, depth, fashion_clip,
       pet, pose, reid, threat, vehicle (all ONNX, CPU)
     - xclip_action (Python backend, CPU)
```

The Triton container base image is `nvcr.io/nvidia/tritonserver:25.01-py3` (Triton Server v2.54.0, CUDA 12.8.0).

---

## 4. How Triton Is Deployed (Not in docker-compose)

The gateway is deployed via `scripts/deploy-gateway.sh` using standalone `podman run` commands, NOT docker-compose. This is why the pipeline mapper missed it when checking `docker-compose.prod.yml`.

**Deploy script:** `/home/msvoboda/github/nemotron-v3-home-security-intelligence/scripts/deploy-gateway.sh`

Key deployment commands from the script:

```bash
# Phase 3: Export models (converts PyTorch/HF to ONNX/TensorRT)
podman run --rm --name ai-gateway-export \
  --entrypoint bash \
  --device "nvidia.com/gpu=${GPU_AI_SERVICES:-1}" \
  -v "/export/ai_models/model-zoo:/models/zoo:ro" \
  -v "/export/ai_models/triton:/models/cache" \
  ai-gateway \
  -c "cd /app/gateway/export && bash export_all.sh"

# Phase 6: Run gateway with GPU
podman run -d --name ai-gateway \
  --network "$NETWORK" \
  --device "nvidia.com/gpu=${GPU_AI_SERVICES:-1}" \
  -e GATEWAY_PORT=8090 \
  -v "/export/ai_models/model-zoo:/models/zoo:ro" \
  -v "/export/ai_models/triton:/models/cache" \
  -p "127.0.0.1:${AI_GATEWAY_PORT:-8090}:8090" \
  ai-gateway

# Phase 7: Backend with gateway routing enabled
podman run -d --name backend \
  -e AI_GATEWAY_URL="http://ai-gateway:8090" \
  -e USE_AI_GATEWAY=true \
  -e YOLO26_URL="http://ai-gateway:8090/yolo26" \
  -e FLORENCE_URL="http://ai-gateway:8090/florence" \
  -e CLIP_URL="http://ai-gateway:8090/clip" \
  -e ENRICHMENT_URL="http://ai-gateway:8090/enrichment" \
  -e ENRICHMENT_LIGHT_URL="http://ai-gateway:8090/enrich-lt" \
  backend
```

---

## 5. Backend Routing Verification

The backend container's environment confirms gateway routing is active:

```
AI_GATEWAY_URL=http://ai-gateway:8090
USE_AI_GATEWAY=true
YOLO26_URL=http://ai-gateway:8090/yolo26
FLORENCE_URL=http://ai-gateway:8090/florence
CLIP_URL=http://ai-gateway:8090/clip
ENRICHMENT_URL=http://ai-gateway:8090/enrichment
ENRICHMENT_LIGHT_URL=http://ai-gateway:8090/enrich-lt
```

The backend clients (`detector_client.py`, `florence_client.py`, `clip_client.py`, `enrichment_client.py`) all check `use_ai_gateway` and `ai_gateway_url` settings to route through the gateway.

---

## 6. Why the Pipeline Mapper Was Wrong

The pipeline mapper checked `docker-compose.prod.yml` for Triton/gateway references and found none. This is correct -- the gateway is NOT defined in docker-compose. However, the mapper incorrectly concluded that Triton was dead code.

The actual deployment uses `scripts/deploy-gateway.sh`, which:

1. Starts infrastructure via `podman compose -f docker-compose.prod.yml up -d` (postgres, redis, monitoring)
2. Starts AI services via standalone `podman run` commands (because Podman compose cannot pass `--device nvidia.com/gpu=X` GPU arguments)

This is a well-documented pattern in the project's CLAUDE.md memory:

> "Podman compose can't pass GPUs -- use standalone `podman run --device nvidia.com/gpu=X`"

---

## 7. Triton Container Internals

**Dockerfile:** `/home/msvoboda/github/nemotron-v3-home-security-intelligence/ai/gateway/Dockerfile`

- Base image: `nvcr.io/nvidia/tritonserver:25.01-py3`
- Installs: FastAPI, uvicorn, tritonclient[grpc], torch, transformers, ultralytics, ONNX Runtime GPU

**Entrypoint:** `/home/msvoboda/github/nemotron-v3-home-security-intelligence/ai/gateway/entrypoint.sh`

1. Links exported model cache into Triton model repository
2. Starts `tritonserver` in background (gRPC :8001, HTTP :8000, metrics :8002)
3. Waits up to 120s for Triton readiness
4. Starts FastAPI gateway via uvicorn on :8090
5. Manages both processes with SIGTERM cleanup

**Gateway code:** `/home/msvoboda/github/nemotron-v3-home-security-intelligence/ai/gateway/main.py`

- FastAPI app with adapter routers for each model family
- Connects to Triton via gRPC using `tritonclient.grpc.aio.InferenceServerClient`

**Triton client:** `/home/msvoboda/github/nemotron-v3-home-security-intelligence/ai/gateway/triton_client.py`

- Async gRPC wrapper with lazy init, timeout handling, numpy-to-Triton dtype translation

---

## 8. Model Repository and Exported Files

**Config files (in image):** `/home/msvoboda/github/nemotron-v3-home-security-intelligence/ai/triton/model_repository/`

- 13 models with `config.pbtxt` definitions
- 11 ONNX backend models, 2 Python backend models (florence2, xclip_action)
- \_yolo26 has TensorRT config but actually loads as ONNX (cache has model.onnx, not model.plan)

**Exported model files (host volume):** `/export/ai_models/triton/`

| Model               | Format | Size   | Instance |
| ------------------- | ------ | ------ | -------- |
| yolo26              | ONNX   | 78 MB  | GPU 0    |
| clip                | ONNX   | 1.2 GB | GPU 0    |
| florence2           | Python | (zoo)  | GPU 0    |
| fashion_clip        | ONNX   | 372 MB | CPU      |
| demographics_age    | ONNX   | 344 MB | CPU      |
| demographics_gender | ONNX   | 344 MB | CPU      |
| depth               | ONNX   | 101 MB | CPU      |
| vehicle             | ONNX   | 94 MB  | CPU      |
| pet                 | ONNX   | 45 MB  | CPU      |
| pose                | ONNX   | 14 MB  | CPU      |
| threat              | ONNX   | 12 MB  | CPU      |
| reid                | ONNX   | 1.5 MB | CPU      |
| xclip_action        | Python | (zoo)  | CPU      |

**Model zoo (read-only):** `/export/ai_models/model-zoo/` (mounted at `/models/zoo` in container)

---

## 9. GPU Utilization

```
GPU 0: NVIDIA RTX A5500, 23546/24564 MiB used (95.9%) — LLM (Nemotron)
GPU 1: NVIDIA RTX A400,  3129/4094 MiB used (76.4%) — Triton (yolo26, clip, florence2 on GPU)
```

---

## 10. Current Issue

The backend container has `Exited (1)` status, meaning it crashed. The gateway and Triton are healthy and serving health check requests. The gateway logs show continuous `/yolo26/health` polling from the backend's health checking system before it crashed.

---

## Conclusion

**Triton IS the active inference architecture.** It replaced 5 standalone AI containers with a single unified gateway container. The deployment uses `scripts/deploy-gateway.sh` with standalone `podman run` commands (required for GPU passthrough), not docker-compose. All 13 models are loaded and responding. The pipeline mapper's "dead code" assessment was based on checking only `docker-compose.prod.yml` and missing the standalone deployment script.
