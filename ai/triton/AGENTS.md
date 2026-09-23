# Triton Inference Server Integration

## Purpose

This directory contains the NVIDIA Triton Inference Server integration: the
model repository (one directory per model, each with a `config.pbtxt`) and a
standalone async client wrapper (`client.py`).

**How Triton actually runs in production**: it is not a standalone compose
service. It runs _inside_ the `ai-gateway` container
(`docker-compose.prod.yml`, service `ai-gateway`, built from
`ai/gateway/Dockerfile`, base image
`nvcr.io/nvidia/tritonserver:26.01-py3`). The gateway's `entrypoint.sh`
starts `tritonserver` (gRPC `localhost:8001`, HTTP `localhost:8000`, metrics
`localhost:8002`) plus the FastAPI gateway on 8090; only 8090 and the metrics
port 8002 are published from the container. The backend reaches it through the
gateway (`USE_AI_GATEWAY=true`), not through `client.py` — `ai.triton`
currently has no production consumer (there is an explicit guard asserting that
in `backend/tests/contracts/ai_providers/test_conformance_vocabulary.py`).

## Benefits Over Direct Inference

| Feature            | Direct Inference (legacy per-service containers) | With Triton                |
| ------------------ | ------------------------------------------------ | -------------------------- |
| Batching           | Manual, single request                           | Automatic dynamic batching |
| Model Loading      | Per-service, duplicated                          | Shared model repository    |
| GPU Utilization    | Suboptimal                                       | Optimized scheduler        |
| Model Versioning   | File-based, manual                               | Built-in A/B testing       |
| Multi-Model        | Separate containers                              | Single server              |
| Monitoring         | Custom metrics                                   | Native Prometheus metrics  |
| Resource Isolation | Container-level                                  | Model-level quotas         |

## Directory Structure

```
ai/triton/
  AGENTS.md                 # This file
  __init__.py               # Package exports
  client.py                 # Triton client wrapper (standalone; see Purpose)
  tests/                    # Unit tests
    AGENTS.md
    __init__.py
    conftest.py             # Test fixtures
    test_client.py          # Client tests
  model_repository/         # Triton model repository (baked into the ai-gateway image at /models/repository)
    yolo26/                 # config.pbtxt + 1/model.onnx (14 model dirs; see Model Repository below)
    clip/
    clip_text/
    demographics_age/
    demographics_gender/
    depth/
    fashion_clip/
    florence2/
    pet/
    pose/
    reid/
    stgcn_action/           # config only — not loaded until its weights are exported
    threat/
    vehicle/
```

Model weight files (`model.onnx`, `.plan`, model-data) are **not** in git. At
runtime, the gateway entrypoint symlinks each `<name>/1/` version directory
from the mounted model cache (`${AI_MODELS_PATH}/triton` → container
`/models/cache`) into the baked-in repository. Export scripts that produce
those files live in `ai/gateway/export/`.

## Components

### TritonClient (`client.py`)

High-level async client for Triton Inference Server:

```python
from ai.triton import TritonClient, TritonConfig

# Create client from environment
config = TritonConfig.from_env()
client = TritonClient(config)

# Check health
if await client.is_healthy():
    # Run detection
    result = await client.detect(image_bytes)
    for det in result.detections:
        print(f"{det.class_name}: {det.confidence:.2f}")

# Cleanup
await client.close()
```

Features:

- gRPC and HTTP protocol support
- Automatic retry with exponential backoff
- Health checks and model status queries
- Batch inference support
- Statistics collection

### Model Configurations

Each model has a `config.pbtxt` file defining input/output tensor shapes and
types, batching, backend and optimization settings. Example (from
`model_repository/clip/config.pbtxt`):

```protobuf
name: "clip"
backend: "onnxruntime"
max_batch_size: 8

dynamic_batching {
  preferred_batch_size: [ 1, 2, 4 ]
  max_queue_delay_microseconds: 50000
}
```

## Environment Variables

`client.py` (`TritonConfig.from_env`) reads these; none are set in
`.env.example` — production uses the gateway's in-container defaults
(`ai/gateway/Dockerfile`):

| Variable                      | Default          | Description                             |
| ----------------------------- | ---------------- | --------------------------------------- |
| `TRITON_ENABLED`              | `false`          | Client opt-in switch (`client.py` only) |
| `TRITON_URL`                  | `localhost:8001` | Triton gRPC endpoint                    |
| `TRITON_HTTP_URL`             | `localhost:8000` | Triton HTTP endpoint                    |
| `TRITON_PROTOCOL`             | `grpc`           | Protocol (grpc or http)                 |
| `TRITON_TIMEOUT`              | `60`             | Request timeout seconds                 |
| `TRITON_MODEL`                | `yolo26`         | Default model                           |
| `TRITON_MAX_RETRIES`          | `3`              | Max retry attempts                      |
| `TRITON_CONFIDENCE_THRESHOLD` | `0.5`            | Detection threshold                     |
| `TRITON_VERBOSE`              | `false`          | Verbose logging                         |

The gateway container instead uses `TRITON_GRPC_URL` (`localhost:8001`),
`TRITON_HTTP_URL` (`http://localhost:8000`) and
`TRITON_MODEL_REPOSITORY` (`/models/repository`).

## Docker Compose Integration (ai-gateway)

There is no standalone `triton` service. The relevant excerpt from
`docker-compose.prod.yml` (service `ai-gateway`):

```yaml
ai-gateway:
  build:
    context: .
    dockerfile: ai/gateway/Dockerfile # FROM nvcr.io/nvidia/tritonserver:26.01-py3
  ports:
    - '127.0.0.1:${AI_GATEWAY_PORT:-8090}:8090' # FastAPI gateway
    - '127.0.0.1:${AI_GATEWAY_METRICS_PORT:-8002}:8002' # Triton metrics
  volumes:
    - ${AI_MODELS_PATH:-/export/ai_models}/triton:/models/cache
    - triton-kernel-cache:/root/.nv
    - triton-tmp-cache:/tmp
  environment:
    - CUDA_VISIBLE_DEVICES=${GPU_AI_SERVICES:-1}
  healthcheck:
    test: ['CMD', 'curl', '-f', 'http://localhost:8090/health']
    start_period: 180s # Triton loads 14 models — allow 3 minutes
```

(The gateway container is named `ai-gateway`; internal Triton HTTP/gRPC ports
8000/8001 are not published to the host.)

## Model Repository

`model_repository/` ships 14 model directories. 12 are loadable at startup
(config + an exported version dir linked from the model cache) and the
`yolo26` / `stgcn_action` configs have no exported weights by default. The
compose healthcheck comments used to say "13 models" — stale since
`xclip_action` was retired with NEM-5563 (its config/python `model.py` now
live under `archive/triton-model-repository/`) — and were corrected to 14 in
the gateway-consolidation follow-up:

| Model               | Backend     | max_batch_size  |
| ------------------- | ----------- | --------------- |
| yolo26              | onnxruntime | 0 (static 1)    |
| clip / clip_text    | onnxruntime | 8               |
| fashion_clip        | onnxruntime | 8               |
| vehicle             | onnxruntime | 8               |
| demographics_age    | onnxruntime | 8               |
| demographics_gender | onnxruntime | 8               |
| pet                 | onnxruntime | 8               |
| reid                | onnxruntime | 16              |
| depth               | onnxruntime | 0 (static 1)    |
| pose                | onnxruntime | 0 (static 1)    |
| threat              | onnxruntime | 0 (static 1)    |
| florence2           | python      | 0               |
| stgcn_action        | onnxruntime | 0 (config only) |

`florence2` is the only Triton Python-backend model left; `xclip_action`
(python, zero-shot video action recognition) was superseded by the
skeleton-based `stgcn_action` pipeline, whose per-frame pose stage the gateway
drives itself (`ai/gateway/adapters/enrichment.py` `_infer_action`).

## Model Preparation

Exports live in `ai/gateway/export/` (`export_all.sh` plus per-model scripts),
not ad-hoc one-liners. They write to the Triton model cache so the gateway
entrypoint can link them into the repository. Example (YOLO26,
`export_yolo26.py`):

```bash
python ai/gateway/export/export_yolo26.py \
    --model-path /models/zoo/yolo26/yolo26m.pt \
    --output-path /models/cache/yolo26/1/model.onnx
```

Modes: `--onnx` (default ONNX path), `--int8` (quantized ONNX), `--tensorrt`
(FP16 `.engine`). The default yolo26 serving path is FP32 ONNX on GPU via the
onnxruntime CUDA execution provider (`config.pbtxt` header notes INT8 ONNX was
incompatible with the CUDA EP).

## Dynamic Batching

Models with `max_batch_size > 0` use Triton dynamic batching, e.g.
`preferred_batch_size: [1, 2, 4]` with a 50 ms max queue delay
(`max_queue_delay_microseconds: 50000`) in the clip/vehicle/pet/etc configs.
Static-batch models (yolo26, pose, threat, depth) process one request per
inference. Batched models give higher throughput and better GPU utilization
under load; batching is transparent to clients.

## Monitoring

Triton metrics are scraped by Prometheus (job `triton-metrics` in
`monitoring/prometheus.yml`) from `ai-gateway:8002/metrics`:

```yaml
- job_name: 'triton-metrics'
  metrics_path: /metrics
  static_configs:
    - targets: ['ai-gateway:8002']
```

Key metrics:

- `nv_inference_request_success` / `nv_inference_request_failure`
- `nv_inference_exec_count`
- `nv_inference_queue_duration_us`
- `nv_inference_compute_infer_duration_us`

## Deployment Status

Triton serving through the gateway is the production path (see
`docker-compose.prod.yml` and `ai/gateway/AGENTS.md`). The legacy
per-service containers (`ai-yolo26`, `ai-florence`, `ai-clip`, `ai-enrichment`,
`ai-enrichment-light`) are dev-only options, not compose services.
`ai/triton/client.py` is the standalone client wrapper kept for direct gRPC
access; production traffic goes through the gateway's HTTP routers instead.

## Testing

### Unit Tests

```bash
uv run pytest ai/triton/tests/ -v
```

### Against a Running Gateway/Triton

```bash
# Start the gateway (Triton runs inside it)
podman compose -f docker-compose.prod.yml up -d ai-gateway

# Health: gateway HTTP on 8090; Triton gRPC is container-internal (8001)
curl -s localhost:${AI_GATEWAY_PORT:-8090}/health | jq
```

### Load Tests

```bash
# Using Triton's perf_analyzer from a host that can reach the container network
perf_analyzer -m yolo26 \
              -u <gateway-host>:8001 \
              --protocol grpc \
              --shape images:1,3,640,640
```

## Troubleshooting

### Model Loading Fails

```bash
# Check gateway/Triton logs
podman logs ai-gateway | grep -i triton

# Verify linked model files in the cache volume
ls -la ${AI_MODELS_PATH:-/export/ai_models}/triton/*/1/
```

### gRPC Connection Errors

```bash
# gRPC 8001 is container-internal; test from inside the container
podman exec ai-gateway grpcurl -plaintext localhost:8001 inference.GRPCInferenceService/ServerLive
```

### Performance Issues

```bash
# Enable verbose client logging (client.py)
TRITON_VERBOSE=true

# Check GPU utilization
nvidia-smi -l 1

# Analyze batching behavior
perf_analyzer -m yolo26 --percentile=95
```

## Entry Points

1. **Client usage**: Import from `ai.triton` package
2. **Configuration**: Modify `config.pbtxt` files (then rebuild the gateway image or remount configs)
3. **Testing**: `ai/triton/tests/` directory
4. **Deployment**: `ai/gateway/Dockerfile` + `docker-compose.prod.yml` service `ai-gateway`

## Related Files

- `ai/gateway/AGENTS.md`: the gateway that runs Triton and exposes it on 8090
- `ai/gateway/export/`: model export scripts
- `backend/services/detector_client.py`: backend HTTP detector client (talks to the gateway's `/yolo26` router, not to gRPC)
- `docs/plans/triton-migration.md`: migration plan documentation
