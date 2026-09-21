# AI Gateway Directory

## Purpose

Single FastAPI service (port 8090) that fronts NVIDIA Triton Inference Server, preserving the exact HTTP APIs of the five legacy AI containers (YOLO26, CLIP, Florence-2, enrichment, enrichment-light). The backend switches to it with a URL change — see `USE_AI_GATEWAY=true` and `*_URL=http://ai-gateway:8090/...` in `docker-compose.prod.yml`. Compose service name: `ai-gateway`.

```
Backend (8000) -> AI Gateway (8090, FastAPI) -> Triton (8001 gRPC, same container, GPU)
```

## Key Files

| File                       | Purpose                                                              |
| -------------------------- | -------------------------------------------------------------------- |
| `main.py`                  | FastAPI app; mounts adapter routers under `/yolo26`, `/clip`, `/florence`, `/enrichment`, `/enrich-lt`; `/health` + `/metrics` |
| `triton_client.py`         | Async gRPC client wrapper (pooling, timeout, numpy <-> InferInput)   |
| `utils.py`                 | Shared image decode/preprocess helpers (base64, letterbox, normalize)|
| `adapters/`                | One router module per legacy service (see `adapters/AGENTS.md`)      |
| `export/`                  | Model export pipeline (see `export/AGENTS.md`)                       |
| `entrypoint.sh`            | Starts Triton, waits ready, then uvicorn; SIGTERM cleanup            |
| `patch_triton_configs.py`  | Rewrites `config.pbtxt` instance_group from models.yml before boot   |
| `Dockerfile`               | Based on `nvcr.io/nvidia/tritonserver:26.01-py3`                     |
| `tests/`                   | Unit tests (see `tests/AGENTS.md`)                                   |

## Environment Variables

| Variable                | Default            | Description                    |
| ----------------------- | ------------------ | ------------------------------ |
| `GATEWAY_PORT`          | `8090`             | FastAPI port                   |
| `TRITON_GRPC_URL`       | `localhost:8001`   | Triton gRPC endpoint           |
| `TRITON_HTTP_URL`       | `http://localhost:8000` | Triton native HTTP       |
| `TRITON_METRICS_URL`    | `http://localhost:8002` | Triton metrics         |
| `TRITON_TIMEOUT_S`      | `30`               | Inference timeout              |
| `MODELS_YAML_PATH`      | `/app/models.yml`  | GPU/CPU assignment source      |

## Patterns / Gotchas

- **Triton runs in the same container** as the gateway; `entrypoint.sh` supervises both.
- **`models.yml` is the single source of truth** for per-model GPU vs CPU placement — edit it, not individual `config.pbtxt` files (`patch_triton_configs.py` rewrites those at boot).
- Adapters must keep the legacy wire format byte-compatible so backend clients need no code change.
- Florence-2 uses Triton's **Python backend** (autoregressive decoder can't export to ONNX/TensorRT).

## Related

- `../AGENTS.md` (pipeline overview), `../triton/AGENTS.md`, `docs/plans/triton-migration.md`
