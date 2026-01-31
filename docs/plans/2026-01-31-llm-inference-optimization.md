# LLM Inference Optimization Design

**Issue:** NEM-4536
**Status:** Planning
**Author:** AI Engineering Team
**Date:** 2026-01-31

## Executive Summary

This document outlines the optimization strategy for the Nemotron LLM inference pipeline, addressing the current 39.6s average latency bottleneck. The recommended approach involves migrating to vLLM for continuous batching and evaluating TensorRT-LLM for 2-3x performance improvements.

## Current State

### Performance Metrics

| Metric              | Current Value | Target      |
| ------------------- | ------------- | ----------- |
| Average latency     | 39.6s         | <10s        |
| P95 latency         | ~60s          | <15s        |
| P99 latency         | ~90s          | <30s        |
| Throughput          | ~2 req/min    | 10+ req/min |
| Context utilization | 1.5%          | >50%        |

### Architecture

```
                     Current Architecture

+-------------+      +-----------------+      +------------------+
|  Detection  | ---> |  Analysis Queue | ---> |  llama.cpp       |
|  Pipeline   |      |  (110 backlog)  |      |  Nemotron Server |
+-------------+      +-----------------+      +------------------+
                                                     |
                                              [39.6s avg latency]
                                                     |
                                                     v
                                              +------------------+
                                              |  Risk Assessment |
                                              |  JSON Response   |
                                              +------------------+
```

### Root Causes

1. **Sequential processing**: llama.cpp processes one request at a time
2. **No continuous batching**: New requests wait for current request to complete
3. **Cold start overhead**: Model loads slowly after idle periods
4. **Context inefficiency**: Only using 1.5% of available context window
5. **Queue backlog**: 110 items in detection queue indicates demand outpaces capacity

## Proposed Solutions

### Phase 1: vLLM Migration (Recommended First Step)

**Benefits:**

- Continuous batching: Process multiple requests simultaneously
- PagedAttention: Efficient GPU memory management
- 5-24x throughput improvement for batch scenarios
- Drop-in OpenAI-compatible API

**Implementation:**

```yaml
# docker-compose.vllm.yml
services:
  nemotron-vllm:
    image: vllm/vllm-openai:latest
    command: >
      --model nvidia/Nemotron-Mini-4B-Instruct
      --tensor-parallel-size 1
      --max-model-len 8192
      --gpu-memory-utilization 0.9
      --enable-chunked-prefill
      --max-num-batched-tokens 8192
      --max-num-seqs 32
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    ports:
      - '8000:8000'
```

**Code Changes:**

```python
# backend/core/config.py
class Settings(BaseSettings):
    # vLLM settings
    llm_backend: str = "vllm"  # "llamacpp" | "vllm" | "tensorrt"
    vllm_url: str = "http://nemotron-vllm:8000/v1"
    vllm_max_concurrent: int = 32  # Leverage batching

# backend/services/nemotron_analyzer.py
async def _call_llm_vllm(self, prompt: str) -> dict:
    """Call vLLM OpenAI-compatible endpoint."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{self._vllm_url}/chat/completions",
            json={
                "model": "nvidia/Nemotron-Mini-4B-Instruct",
                "messages": [
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 512,
                "temperature": 0.3,
            }
        )
        return response.json()
```

**Expected Results:**

- Latency: 39.6s -> 8-12s (3-5x improvement)
- Throughput: 2 req/min -> 10-15 req/min
- Queue backlog: 110 -> <10 items

### Phase 2: TensorRT-LLM Optimization

**Benefits:**

- 2-3x speedup over standard PyTorch/vLLM
- Quantization support (INT8, FP8) for memory efficiency
- Optimized CUDA kernels
- Inflight batching (continuous batching optimized for NVIDIA GPUs)

**Implementation:**

```yaml
# docker-compose.tensorrt.yml
services:
  nemotron-trt:
    image: nvcr.io/nvidia/tritonserver:24.09-trtllm-python-py3
    volumes:
      - ./engines:/engines
    command: >
      tritonserver --model-repository=/models
      --http-port=8000
      --grpc-port=8001
```

**Engine Build Process:**

```bash
# Build TensorRT-LLM engine from Nemotron model
trtllm-build \
    --checkpoint_dir /models/nemotron-mini-4b \
    --output_dir /engines/nemotron-mini-4b-trt \
    --gemm_plugin float16 \
    --gpt_attention_plugin float16 \
    --max_batch_size 32 \
    --max_input_len 4096 \
    --max_output_len 512 \
    --use_inflight_batching
```

**Expected Results:**

- Latency: 8-12s -> 3-5s (additional 2-3x improvement)
- Throughput: 10-15 req/min -> 25-40 req/min

### Phase 3: Prompt Optimization (Implemented)

**Already Implemented (NEM-4541):**

- LRU caching for static prompt sections
- `get_cached_system_prompt()` - System prompt with reasoning
- `get_cached_scoring_reference()` - Scoring reference table
- `get_cached_non_risk_factors()` - Non-risk factors guidance

**Future Optimizations:**

- Prompt compression for context-heavy inputs
- Template precompilation
- Semantic deduplication of repeated context

### Phase 4: Queue Optimization (Implemented)

**Already Implemented (NEM-4537):**

- Priority queue using Redis sorted sets
- `add_to_priority_queue()` - ZADD with priority scoring
- `get_from_priority_queue()` - ZPOPMAX for highest priority
- `calculate_detection_priority()` - Priority scoring based on confidence

**Priority Scoring:**

```python
def calculate_priority(confidence: float, is_high_risk: bool) -> float:
    priority = confidence * 100.0  # 0-100 base
    if is_high_risk:
        priority += 10.0  # Bonus for weapons, suspicious items
    return priority
```

## Migration Plan

### Week 1-2: vLLM Integration

1. Add vLLM container to docker-compose
2. Implement vLLM backend in NemotronAnalyzer
3. Add feature flag for backend selection
4. Deploy to staging and benchmark
5. Gradual rollout (10% -> 50% -> 100%)

### Week 3-4: TensorRT-LLM Evaluation

1. Build TensorRT-LLM engine for Nemotron
2. Benchmark against vLLM baseline
3. Evaluate accuracy/latency tradeoffs
4. Decision point: adopt TRT-LLM or stay with vLLM

### Week 5-6: Production Hardening

1. Monitoring and alerting integration
2. Graceful degradation (fallback to llama.cpp)
3. Auto-scaling based on queue depth
4. Documentation and runbooks

## Risk Assessment

| Risk                     | Impact | Mitigation                      |
| ------------------------ | ------ | ------------------------------- |
| vLLM API incompatibility | High   | Maintain llama.cpp fallback     |
| TRT-LLM accuracy drift   | Medium | A/B testing validation          |
| GPU memory exhaustion    | High   | Memory utilization caps         |
| Cold start regression    | Medium | Warm-up on container start      |
| Breaking API changes     | Low    | Pin versions, integration tests |

## Success Metrics

| Metric          | Baseline | Phase 1 Target | Phase 2 Target |
| --------------- | -------- | -------------- | -------------- |
| P50 latency     | 39.6s    | <10s           | <5s            |
| P95 latency     | 60s      | <15s           | <8s            |
| Throughput      | 2/min    | 10/min         | 25/min         |
| Queue backlog   | 110      | <20            | <5             |
| GPU utilization | 30%      | 70%            | 85%            |

## Cost Analysis

### Hardware Requirements

| Backend      | GPU Memory | Recommendation |
| ------------ | ---------- | -------------- |
| llama.cpp    | 4-8GB      | RTX 3060/4060  |
| vLLM         | 8-12GB     | RTX 3080/4070  |
| TensorRT-LLM | 8-16GB     | RTX 4080/A4000 |

### Cloud Cost Comparison (per month)

| Option              | Instance    | Cost | Throughput |
| ------------------- | ----------- | ---- | ---------- |
| Current (llama.cpp) | g4dn.xlarge | $380 | 2/min      |
| vLLM                | g4dn.xlarge | $380 | 10/min     |
| TensorRT-LLM        | g5.xlarge   | $560 | 25/min     |

**ROI Analysis:** vLLM provides 5x throughput improvement at no additional infrastructure cost. TensorRT-LLM provides further gains but may require GPU upgrade.

## Alternatives Considered

### 1. Horizontal Scaling (Rejected)

- **Approach**: Multiple llama.cpp instances behind load balancer
- **Pros**: Simple to implement
- **Cons**: Linear cost scaling, no batching benefits, complex state management
- **Decision**: Rejected - vLLM provides better cost/performance ratio

### 2. Model Distillation (Deferred)

- **Approach**: Fine-tune smaller model (2B params) for security analysis
- **Pros**: Faster inference, lower memory
- **Cons**: Requires training pipeline, potential accuracy loss
- **Decision**: Deferred to Phase 3 if needed after vLLM optimization

### 3. Speculative Decoding (Future)

- **Approach**: Use draft model to accelerate generation
- **Pros**: 2-3x speedup with no accuracy loss
- **Cons**: Requires additional small model, complex implementation
- **Decision**: Future consideration after TensorRT-LLM evaluation

## References

- [vLLM Documentation](https://docs.vllm.ai/)
- [TensorRT-LLM Documentation](https://nvidia.github.io/TensorRT-LLM/)
- [PagedAttention Paper](https://arxiv.org/abs/2309.06180)
- [Continuous Batching for LLM Inference](https://www.anyscale.com/blog/continuous-batching-llm-inference)
- [NVIDIA NIM Inference Microservices](https://developer.nvidia.com/nim)

## Appendix: Benchmark Scripts

```bash
# Latency benchmark
./scripts/benchmark_llm_latency.py \
    --backend vllm \
    --requests 100 \
    --concurrency 10 \
    --output results/vllm_latency.json

# Throughput benchmark
./scripts/benchmark_llm_throughput.py \
    --backend tensorrt \
    --duration 300 \
    --output results/tensorrt_throughput.json
```

## Changelog

| Date       | Author         | Change        |
| ---------- | -------------- | ------------- |
| 2026-01-31 | AI Engineering | Initial draft |
