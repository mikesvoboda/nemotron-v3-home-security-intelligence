# Triton Inference Server Migration Plan

## Overview

This document describes the migration from direct PyTorch/TensorRT inference to NVIDIA Triton Inference Server for object detection models (RT-DETR and YOLO26).

## Why Triton?

### Current Architecture Issues

| Issue                   | Impact                                      |
| ----------------------- | ------------------------------------------- |
| No automatic batching   | Suboptimal GPU utilization under load       |
| Separate AI services    | Resource duplication, complex orchestration |
| Manual model management | No versioning, no A/B testing               |
| Custom health/metrics   | Inconsistent observability                  |
| Cold start latency      | First request slow after idle               |

### Triton Benefits

| Feature             | Benefit                                 |
| ------------------- | --------------------------------------- |
| Dynamic batching    | Up to 5x throughput improvement         |
| Model repository    | Centralized, versioned model management |
| Native metrics      | Prometheus-compatible, detailed latency |
| Warmup support      | Configurable model pre-loading          |
| Resource isolation  | Per-model memory and compute quotas     |
| Multi-model serving | Single server, multiple models          |
| gRPC + HTTP         | Flexible protocol options               |

## Architecture Comparison

### Before (Current)

```
┌─────────────┐
│   Backend   │
└──────┬──────┘
       │
  ┌────┴────┐
  ▼         ▼
┌─────┐  ┌──────┐
│RTDETR│  │YOLO26│
│FastAPI│  │FastAPI│
│8090   │  │8095   │
└───────┘  └───────┘
   GPU        GPU
```

Each AI service:

- Runs FastAPI + PyTorch
- Manages own model loading
- Handles own health checks
- No request batching

### After (With Triton)

```
┌─────────────┐
│   Backend   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Triton    │
│   Server    │
│ 8000/8001   │
├─────────────┤
│ ┌────────┐  │
│ │ RT-DETR │  │
│ └────────┘  │
│ ┌────────┐  │
│ │ YOLO26 │  │
│ └────────┘  │
└─────────────┘
      GPU
```

Single Triton server:

- Manages all models
- Automatic batching
- Unified metrics
- Model versioning

## Migration Phases

### Phase 1: Infrastructure (Current)

**Goal**: Create Triton infrastructure without disrupting existing services.

**Deliverables**:

- [x] Model repository structure (`ai/triton/model_repository/`)
- [x] Model configurations (`config.pbtxt` files)
- [x] Triton client wrapper (`ai/triton/client.py`)
- [x] Docker Compose service (profile-gated)
- [x] Unit tests for client

**Status**: Complete

### Phase 2: Model Conversion

**Goal**: Convert existing models to Triton-compatible TensorRT format.

**Tasks**:

1. **RT-DETR Conversion**

   ```bash
   # Export to ONNX (if not already)
   python ai/rtdetr/export_onnx.py --output rtdetr.onnx

   # Convert to TensorRT
   trtexec --onnx=rtdetr.onnx \
           --saveEngine=ai/triton/model_repository/rtdetr/1/model.plan \
           --fp16 \
           --minShapes=images:1x3x640x640 \
           --optShapes=images:4x3x640x640 \
           --maxShapes=images:8x3x640x640 \
           --workspace=4096
   ```

2. **YOLO26 Conversion**

   ```bash
   # Use Ultralytics export
   yolo export model=yolo26m.pt format=engine device=0 half=True

   # Copy to Triton repository
   cp yolo26m.engine ai/triton/model_repository/yolo26/1/model.plan
   ```

3. **Validation**
   - Verify model outputs match current implementation
   - Compare latency and throughput
   - Test batch inference

**Estimated Time**: 2-3 days

### Phase 3: Integration Testing

**Goal**: Validate Triton client works correctly with real Triton server.

**Tasks**:

1. **Local Testing**

   ```bash
   # Start Triton server
   docker compose -f docker-compose.prod.yml --profile triton up -d triton

   # Run integration tests
   TRITON_ENABLED=true pytest ai/triton/tests/test_integration.py -v
   ```

2. **Performance Testing**

   ```bash
   # Use Triton's perf_analyzer
   perf_analyzer -m rtdetr \
                 -u localhost:8097 \
                 --concurrency-range 1:16 \
                 --shape images:1,3,640,640
   ```

3. **Comparison Testing**
   - A/B test with current implementation
   - Measure latency at p50, p95, p99
   - Verify detection accuracy unchanged

**Estimated Time**: 2-3 days

### Phase 4: Backend Integration

**Goal**: Update backend to use Triton client when enabled.

**Tasks**:

1. **Configuration**

   - Add Triton settings to backend config
   - Support fallback to direct services

2. **Detector Client Update**

   ```python
   # backend/services/detector_client.py

   async def _detect_with_triton(self, image_data: bytes) -> list[Detection]:
       """Use Triton for inference when enabled."""
       from ai.triton import TritonClient

       client = self._get_triton_client()
       result = await client.detect(image_data, model=self._detector_type)

       return [
           Detection(
               object_type=det.class_name,
               confidence=det.confidence,
               bbox_x=det.bbox.x,
               bbox_y=det.bbox.y,
               bbox_width=det.bbox.width,
               bbox_height=det.bbox.height,
           )
           for det in result.detections
       ]
   ```

3. **Testing**
   - Unit tests with mocked Triton client
   - Integration tests with real Triton server

**Estimated Time**: 3-4 days

### Phase 5: Gradual Rollout

**Goal**: Safely roll out Triton in production.

**Rollout Strategy**:

1. **Canary (10% traffic)**

   - Deploy Triton alongside existing services
   - Route 10% of traffic via feature flag
   - Monitor error rates and latency

2. **Incremental (25%, 50%, 75%)**

   - Increase traffic percentage
   - Monitor for regression
   - Rollback if issues detected

3. **Full Rollout (100%)**
   - All traffic through Triton
   - Existing services as fallback

**Monitoring**:

```yaml
# Grafana alert rules
- alert: TritonHighLatency
  expr: histogram_quantile(0.95, rate(nv_inference_exec_duration_us[5m])) > 200000
  for: 5m
  labels:
    severity: warning

- alert: TritonHighErrorRate
  expr: rate(nv_inference_request_failure[5m]) / rate(nv_inference_request_success[5m]) > 0.01
  for: 5m
  labels:
    severity: critical
```

**Estimated Time**: 1-2 weeks

### Phase 6: Deprecation

**Goal**: Remove legacy AI services after successful migration.

**Tasks**:

1. Remove direct AI service containers
2. Update documentation
3. Archive old code (keep for reference)
4. Update CI/CD pipelines

**Estimated Time**: 1-2 days

## Configuration Reference

### Environment Variables

| Variable                      | Default          | Description               |
| ----------------------------- | ---------------- | ------------------------- |
| `TRITON_ENABLED`              | `false`          | Enable Triton inference   |
| `TRITON_URL`                  | `localhost:8001` | gRPC endpoint             |
| `TRITON_HTTP_URL`             | `localhost:8000` | HTTP endpoint             |
| `TRITON_PROTOCOL`             | `grpc`           | Protocol (grpc/http)      |
| `TRITON_TIMEOUT`              | `60`             | Request timeout (seconds) |
| `TRITON_MODEL`                | `rtdetr`         | Default model             |
| `TRITON_MAX_RETRIES`          | `3`              | Max retry attempts        |
| `TRITON_CONFIDENCE_THRESHOLD` | `0.5`            | Detection threshold       |

### Docker Compose

Enable Triton with:

```bash
# Start with Triton profile
docker compose -f docker-compose.prod.yml --profile triton up -d

# Or set in .env
TRITON_ENABLED=true
```

## Performance Expectations

### Latency (p95)

| Scenario       | Current | With Triton | Improvement |
| -------------- | ------- | ----------- | ----------- |
| Single request | 50ms    | 45ms        | ~10%        |
| 4 concurrent   | 200ms   | 55ms        | ~73%        |
| 8 concurrent   | 400ms   | 70ms        | ~82%        |

### Throughput

| Scenario   | Current  | With Triton | Improvement |
| ---------- | -------- | ----------- | ----------- |
| Sequential | 20 req/s | 22 req/s    | ~10%        |
| Concurrent | 25 req/s | 115 req/s   | ~360%       |

_Note: Actual results depend on GPU, batch sizes, and workload patterns._

## Rollback Plan

If issues occur during migration:

1. **Immediate**: Set `TRITON_ENABLED=false` to fall back to direct services
2. **Container**: Stop Triton container, existing services continue working
3. **Full Rollback**: Remove Triton profile, restart without changes

## Success Criteria

- [ ] No increase in detection latency (p95)
- [ ] Detection accuracy unchanged (< 0.1% variance)
- [ ] Error rate < 0.1% under normal load
- [ ] GPU utilization improved under concurrent load
- [ ] All existing tests pass
- [ ] Prometheus metrics available

## Timeline Summary

| Phase               | Duration  | Dependencies   |
| ------------------- | --------- | -------------- |
| Infrastructure      | Complete  | -              |
| Model Conversion    | 2-3 days  | TensorRT tools |
| Integration Testing | 2-3 days  | Phase 2        |
| Backend Integration | 3-4 days  | Phase 3        |
| Gradual Rollout     | 1-2 weeks | Phase 4        |
| Deprecation         | 1-2 days  | Phase 5        |

**Total Estimated Time**: 4-6 weeks

## References

- [NVIDIA Triton Inference Server](https://github.com/triton-inference-server/server)
- [Triton Model Configuration](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_configuration.html)
- [Dynamic Batching](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_configuration.html#dynamic-batching)
- [Performance Analyzer](https://github.com/triton-inference-server/client/tree/main/src/c%2B%2B/perf_analyzer)
