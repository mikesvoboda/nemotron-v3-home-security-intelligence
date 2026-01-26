# Triton Inference Server Integration

## Purpose

This directory contains the NVIDIA Triton Inference Server integration for the AI pipeline. Triton provides production-grade model serving with features like dynamic batching, model versioning, and multi-model serving on a single server.

## Benefits Over Direct Inference

| Feature            | Current (FastAPI + PyTorch) | With Triton                |
| ------------------ | --------------------------- | -------------------------- |
| Batching           | Manual, single request      | Automatic dynamic batching |
| Model Loading      | Per-service, duplicated     | Shared model repository    |
| GPU Utilization    | Suboptimal                  | Optimized scheduler        |
| Model Versioning   | File-based, manual          | Built-in A/B testing       |
| Multi-Model        | Separate containers         | Single server              |
| Monitoring         | Custom metrics              | Native Prometheus metrics  |
| Resource Isolation | Container-level             | Model-level quotas         |

## Directory Structure

```
ai/triton/
  AGENTS.md                 # This file
  __init__.py               # Package exports
  client.py                 # Triton client wrapper
  tests/                    # Unit tests
    __init__.py
    conftest.py             # Test fixtures
    test_client.py          # Client tests
  model_repository/         # Triton model repository
    yolo26/                 # YOLO26 object detection
      config.pbtxt          # Model configuration
      1/                    # Version 1
        model.plan          # TensorRT engine (generated)
    yolo26/                 # YOLO26 object detection
      config.pbtxt          # Model configuration
      1/                    # Version 1
        model.plan          # TensorRT engine (generated)
```

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

Each model has a `config.pbtxt` file defining:

- Input/output tensor shapes and types
- Dynamic batching parameters
- GPU allocation
- Optimization settings
- Warmup configuration

Example configuration:

```protobuf
name: "yolo26"
platform: "tensorrt_plan"
max_batch_size: 8

dynamic_batching {
  preferred_batch_size: [ 2, 4, 8 ]
  max_queue_delay_microseconds: 100000
}
```

## Environment Variables

| Variable                      | Default          | Description             |
| ----------------------------- | ---------------- | ----------------------- |
| `TRITON_ENABLED`              | `false`          | Enable Triton inference |
| `TRITON_URL`                  | `localhost:8001` | Triton gRPC endpoint    |
| `TRITON_HTTP_URL`             | `localhost:8000` | Triton HTTP endpoint    |
| `TRITON_PROTOCOL`             | `grpc`           | Protocol (grpc or http) |
| `TRITON_TIMEOUT`              | `60`             | Request timeout seconds |
| `TRITON_MODEL`                | `yolo26`         | Default model           |
| `TRITON_MAX_RETRIES`          | `3`              | Max retry attempts      |
| `TRITON_CONFIDENCE_THRESHOLD` | `0.5`            | Detection threshold     |

## Docker Compose Integration

The Triton server is configured in `docker-compose.prod.yml`:

```yaml
services:
  triton:
    image: nvcr.io/nvidia/tritonserver:24.01-py3
    ports:
      - '8000:8000' # HTTP
      - '8001:8001' # gRPC
      - '8002:8002' # Metrics
    volumes:
      - ./ai/triton/model_repository:/models:ro
    command: tritonserver --model-repository=/models --strict-model-config=false
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

## Model Preparation

### YOLO26

1. Export to ONNX:

```bash
python -c "
from transformers import AutoModelForObjectDetection
import torch

model = AutoModelForObjectDetection.from_pretrained('PekingU/yolo26_r50vd_coco_o365')
dummy_input = torch.randn(1, 3, 640, 640)
torch.onnx.export(model, dummy_input, 'yolo26.onnx', opset_version=17)
"
```

2. Convert to TensorRT:

```bash
trtexec --onnx=yolo26.onnx \
        --saveEngine=ai/triton/model_repository/yolo26/1/model.plan \
        --fp16 \
        --minShapes=images:1x3x640x640 \
        --optShapes=images:4x3x640x640 \
        --maxShapes=images:8x3x640x640
```

### YOLO26

1. Export using Ultralytics:

```bash
yolo export model=yolo26m.pt format=engine device=0 half=True
```

2. Copy engine:

```bash
cp yolo26m.engine ai/triton/model_repository/yolo26/1/model.plan
```

## Dynamic Batching

Triton automatically batches incoming requests for optimal GPU utilization:

```
Time -->

Request 1 ─┐
Request 2 ─┼─> [Batch of 3] -> GPU Inference -> Results
Request 3 ─┘

Queue delay: max 100ms to accumulate batch
Preferred batch sizes: 2, 4, 8
```

Benefits:

- Higher throughput under load
- Better GPU utilization
- Transparent to clients

## Monitoring

Triton exposes Prometheus metrics at `/metrics` (port 8002):

Key metrics:

- `nv_inference_request_success`: Successful inference count
- `nv_inference_request_failure`: Failed inference count
- `nv_inference_exec_count`: Total executions per model
- `nv_inference_queue_duration_us`: Queue wait time
- `nv_inference_compute_infer_duration_us`: Inference latency

Example Prometheus scrape config:

```yaml
scrape_configs:
  - job_name: 'triton'
    static_configs:
      - targets: ['triton:8002']
```

## Migration Strategy

The migration to Triton is designed to be gradual:

1. **Phase 1 (Current)**: Infrastructure setup

   - Create model repository structure
   - Implement Triton client wrapper
   - Add docker-compose configuration

2. **Phase 2**: Side-by-side deployment

   - Deploy Triton alongside existing services
   - Enable via `TRITON_ENABLED=true`
   - Compare latency and throughput

3. **Phase 3**: Gradual rollout

   - Route percentage of traffic to Triton
   - Monitor metrics and errors
   - Adjust batching parameters

4. **Phase 4**: Full migration
   - Deprecate direct inference services
   - Route all traffic through Triton
   - Remove legacy code

## Testing

### Unit Tests

```bash
uv run pytest ai/triton/tests/ -v
```

### Integration Tests (requires running Triton)

```bash
# Start Triton server
docker compose -f docker-compose.prod.yml up -d triton

# Run integration tests
uv run pytest ai/triton/tests/test_integration.py -v --run-integration
```

### Load Tests

```bash
# Using Triton's perf_analyzer
perf_analyzer -m yolo26 \
              -u localhost:8001 \
              --concurrency-range 1:8 \
              --shape images:1,3,640,640
```

## Troubleshooting

### Model Loading Fails

```bash
# Check Triton logs
docker compose -f docker-compose.prod.yml logs triton

# Verify model repository structure
ls -la ai/triton/model_repository/*/
```

### gRPC Connection Errors

```bash
# Test connectivity
grpcurl -plaintext localhost:8001 inference.GRPCInferenceService/ServerLive

# Check firewall/network
nc -zv localhost 8001
```

### Performance Issues

```bash
# Enable verbose logging
TRITON_VERBOSE=true

# Check GPU utilization
nvidia-smi -l 1

# Analyze batching behavior
perf_analyzer -m yolo26 --percentile=95
```

## Entry Points

1. **Client usage**: Import from `ai.triton` package
2. **Configuration**: Modify `config.pbtxt` files
3. **Testing**: `ai/triton/tests/` directory
4. **Deployment**: `docker-compose.prod.yml` triton service

## Related Files

- `backend/services/detector_client.py`: Backend client (to be updated for Triton)
- `docker-compose.prod.yml`: Container orchestration
- `docs/plans/triton-migration.md`: Migration plan documentation
