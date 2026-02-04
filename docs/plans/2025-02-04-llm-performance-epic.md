# LLM Inference Performance Optimization Epic

**Created:** 2025-02-04
**Status:** Draft
**Approach:** Benchmark-First Exploration

## Objective

Systematically benchmark and optimize the Nemotron inference stack to:

- Reduce latency (current P50: 39.6s)
- Increase throughput (current: ~2 req/min)
- Fit full AI pipeline on single RTX A5500 (24GB)
- Maintain quality (≥95% of current 30B model)

## Background

### Current Stack

| Model                  | VRAM          | Current GPU |
| ---------------------- | ------------- | ----------- |
| Nemotron 30B (Q4_K_M)  | ~14.7 GB      | A5500       |
| Florence-2             | ~3 GB         | A5500       |
| YOLO26                 | ~2 GB         | A400        |
| CLIP                   | ~0.8 GB       | A400        |
| Enrichment (Model Zoo) | ~5-6 GB       | On-demand   |
| **Total**              | **~25-27 GB** | Split       |

### Pain Points

1. **Latency** - 39.6s P50 too slow for real-time alerting
2. **Throughput** - Can't keep up with detection volume
3. **Resource efficiency** - Stack split across two GPUs
4. **User experience** - Dashboard sluggish waiting for risk scores

### Constraints

- Primary hardware: RTX A5500 (24GB) - goal is single-GPU deployment
- Secondary hardware: RTX A400 (4GB) - fallback if needed
- No rush on timeline - do it right
- Synthetic test data available at `data/synthetic/`

---

## Phase 1: Benchmark Infrastructure

**Goal:** Build measurement foundation before any optimizations.

### Metrics to Track

| Dimension      | Metrics                                          | How Measured                  |
| -------------- | ------------------------------------------------ | ----------------------------- |
| **Latency**    | P50, P95, P99, time-to-first-token               | Request timestamps            |
| **Throughput** | Requests/min, tokens/sec                         | Sustained load test           |
| **VRAM**       | Peak usage, steady-state                         | `nvidia-smi` polling          |
| **Quality**    | Accuracy vs ground truth, risk score correlation | Synthetic test set comparison |

### Test Scenarios

1. **Single request latency** - One request at a time, measure response time
2. **Sustained load** - Continuous requests at expected detection rate
3. **Burst handling** - Simulate camera event storm (10+ simultaneous detections)
4. **Cold start** - Time from container start to first inference

### Test Dataset

Pull from `data/synthetic/` to create a fixed evaluation set:

- 100 events across risk levels (70 low, 20 medium, 8 high, 2 critical)
- Mix of prompt complexity (basic → fully enriched)
- Store expected outputs for quality comparison

### Deliverables

| Deliverable       | Location                                             |
| ----------------- | ---------------------------------------------------- |
| Benchmark runner  | `scripts/benchmark/run_benchmark.py`                 |
| Test dataset      | `data/benchmark/evaluation-set/`                     |
| Metrics collector | `scripts/benchmark/metrics.py`                       |
| Baseline report   | `results/benchmarks/baseline-30b-q4km-llamacpp.json` |
| Comparison tool   | `scripts/benchmark/compare.py`                       |

### Exit Criteria

- Benchmark suite runs end-to-end
- Baseline captured for current setup
- Comparison tool generates markdown tables

---

## Phase 2: Model Exploration

**Goal:** Determine if smaller models can match 30B quality.

### Models to Test

| Model                              | Parameters | Expected VRAM     | Why Test                  |
| ---------------------------------- | ---------- | ----------------- | ------------------------- |
| **Nemotron-3-Nano-30B** (baseline) | 30B        | ~14.7 GB (Q4_K_M) | Current production        |
| **Nemotron-Nano-9B-V2**            | 9B         | ~5-6 GB (Q4_K_M)  | Latest nano, good balance |
| **Nemotron-Nano-8B-V1**            | 8B         | ~4-5 GB (Q4_K_M)  | Smaller alternative       |
| **Nemotron-Nano-4B-V1.1**          | 4B         | ~2.5 GB (Q4_K_M)  | Minimum viable            |

### Test Matrix

Each model tested with:

- Same 100-event synthetic dataset
- Same prompt templates (all 5 tiers)
- Same generation parameters (temp=0.7, top_p=0.95)

### Quality Evaluation Criteria

For each response, score:

1. **Risk score accuracy** - Delta from ground truth (±5 acceptable, ±10 marginal)
2. **Risk level match** - Exact match on low/medium/high/critical
3. **JSON validity** - Parseable, schema-compliant
4. **Reasoning quality** - Manual spot-check of 10 samples per model

### Decision Framework

```
If 9B quality ≥ 95% of 30B quality:
  → Consider 9B (saves ~9GB VRAM)

If 8B quality ≥ 90% of 30B quality:
  → Consider 8B for "easy" cases (quality-adaptive routing)

If 4B quality ≥ 85% of 30B quality:
  → Consider speculative decoding (4B draft + 30B verify)
```

### Deliverables

| Deliverable       | Location                           |
| ----------------- | ---------------------------------- |
| Downloaded models | `/export/ai_models/nemotron/`      |
| Benchmark results | `results/benchmarks/model-*.json`  |
| Comparison report | `docs/reports/model-comparison.md` |

### Exit Criteria

- All models benchmarked
- Quality comparison documented with data
- Model recommendation made

---

## Phase 3: Quantization Exploration

**Goal:** Find optimal VRAM/quality tradeoff through quantization.

### Quantization Formats to Test

For the 30B model (and winning smaller model):

| Format                | Bits            | Expected VRAM | Quality Impact   |
| --------------------- | --------------- | ------------- | ---------------- |
| **Q4_K_M** (baseline) | 4-bit           | ~14.7 GB      | Baseline         |
| **Q4_K_S**            | 4-bit (small)   | ~13.5 GB      | Minimal          |
| **Q3_K_M**            | 3-bit           | ~11 GB        | Moderate         |
| **Q3_K_S**            | 3-bit (small)   | ~10 GB        | Noticeable       |
| **Q2_K**              | 2-bit           | ~8 GB         | Significant      |
| **IQ3_M**             | 3-bit (i-quant) | ~10.5 GB      | Better than Q3_K |
| **IQ2_M**             | 2-bit (i-quant) | ~7.5 GB       | Better than Q2_K |

### Quality vs VRAM Tradeoff Analysis

For each quantization level, measure:

1. **Risk score MAE** (mean absolute error vs Q4_K_M baseline)
2. **Risk level accuracy** (% exact match)
3. **Reasoning coherence** (manual review of edge cases)
4. **VRAM saved** (GB freed for other models)

### Key Question

```
Can we find a quantization that:
  - Saves 3-5 GB VRAM (enough to fit full stack on A5500)
  - Maintains ≥95% quality vs Q4_K_M
  - Doesn't increase latency significantly
```

### Combining with Smaller Models

- If 9B @ Q4_K_M ≈ 30B @ Q3_K_M quality → Prefer 9B
- If 30B @ Q3_K_M > 9B @ Q4_K_M quality → Keep 30B with tighter quantization

### Deliverables

| Deliverable       | Location                                  |
| ----------------- | ----------------------------------------- |
| Quantized models  | `/export/ai_models/nemotron/`             |
| Benchmark results | `results/benchmarks/quant-*.json`         |
| Tradeoff curves   | `docs/reports/quantization-comparison.md` |

### Exit Criteria

- All quantization levels benchmarked
- Quality/VRAM tradeoff curve documented
- Quantization selection made

---

## Phase 4: Engine Exploration

**Goal:** Evaluate inference backends for throughput and latency.

### Engines to Test

| Engine                   | Key Feature                         | VRAM Overhead | Complexity |
| ------------------------ | ----------------------------------- | ------------- | ---------- |
| **llama.cpp** (baseline) | CPU offload, GGUF quantization      | Lowest        | Low        |
| **vLLM**                 | PagedAttention, continuous batching | Medium        | Medium     |
| **TensorRT-LLM**         | NVIDIA-optimized kernels            | Medium        | High       |

### Performance Targets

| Metric      | llama.cpp Baseline | vLLM Target | TRT-LLM Target |
| ----------- | ------------------ | ----------- | -------------- |
| P50 Latency | 39.6s              | <10s        | <5s            |
| Throughput  | ~2 req/min         | ~10 req/min | ~25 req/min    |
| VRAM        | ~14.7 GB           | ~15-16 GB   | ~15-16 GB      |
| Cold start  | ~120s              | ~60s        | ~90s           |

### vLLM-Specific Tests

- **Continuous batching** - Throughput improvement under load
- **PagedAttention** - Memory efficiency for larger context
- **Prefix caching** - Latency improvement from shared system prompt

### Engine Selection Criteria

```
If vLLM throughput ≥ 5x llama.cpp AND fits in 24GB:
  → Migrate to vLLM

If TRT-LLM throughput ≥ 2x vLLM AND complexity is acceptable:
  → Consider TRT-LLM for Phase 2

If llama.cpp + tuning gets close enough:
  → Stay with llama.cpp (simplicity wins)
```

### Deliverables

| Deliverable       | Location                            |
| ----------------- | ----------------------------------- |
| vLLM container    | `ai/vllm/`                          |
| Benchmark results | `results/benchmarks/engine-*.json`  |
| Comparison report | `docs/reports/engine-comparison.md` |

### Exit Criteria

- vLLM benchmarked against llama.cpp
- TensorRT-LLM feasibility assessed
- Engine recommendation made

---

## Phase 5: Batching and Scheduling Optimizations

**Goal:** Maximize throughput through request handling improvements.

### Current State

- 90-second batch windows, 30-second idle timeout
- `PARALLEL=1` (single inference slot)
- Semaphore-based concurrency control (`AI_MAX_CONCURRENT_INFERENCES=4`)
- Priority queue exists but limited use

### Optimizations to Test

| Optimization            | What It Does                                | Expected Impact         |
| ----------------------- | ------------------------------------------- | ----------------------- |
| **Increase PARALLEL**   | Multiple concurrent inference slots         | 2-3x throughput         |
| **Dynamic batching**    | Coalesce requests arriving within window    | Better GPU utilization  |
| **Priority scheduling** | High-risk detections skip queue             | Critical alerts faster  |
| **Request coalescing**  | Merge similar detections into single prompt | Reduce total inferences |
| **Adaptive timeouts**   | Shorter timeout at high queue depth         | Prevent backlog spiral  |

### Priority Queue Enhancement

```
Priority Levels:
  P0 (Critical): Weapon detected, unknown person at night
  P1 (High):     Unknown vehicle, person in restricted zone
  P2 (Normal):   Standard detections
  P3 (Low):      Known faces, expected delivery times

P0 requests preempt P3 in queue.
```

### Request Coalescing Rules

When multiple detections arrive in same batch window:

- Same camera + same object type → Merge into single analysis
- Cross-camera same person (ReID match) → Single unified analysis
- Reduces inference count by estimated 20-40%

### Deliverables

| Deliverable                | Location                                |
| -------------------------- | --------------------------------------- |
| Priority queue enhancement | `backend/services/nemotron_analyzer.py` |
| Request coalescing logic   | `backend/services/batch_coalescer.py`   |
| Throughput benchmarks      | `results/benchmarks/batching-*.json`    |

### Exit Criteria

- Priority scheduling implemented and tested
- Request coalescing implemented and tested
- Throughput gains measured under load

---

## Phase 6: Integration and Validation

**Goal:** Combine winning optimizations and validate end-to-end.

### Tasks

1. **Combine configurations** - Merge best model, quantization, engine, batching settings
2. **Full regression test** - Run complete benchmark suite
3. **VRAM validation** - Confirm full stack fits on A5500
4. **Load testing** - Sustained throughput under realistic conditions
5. **Documentation** - Update deployment guides

### Deliverables

| Deliverable              | Location                                    |
| ------------------------ | ------------------------------------------- |
| Final configuration      | `docker-compose.prod.yml`                   |
| Deployment guide updates | `docs/deployment/`                          |
| Final benchmark report   | `docs/reports/final-optimization-report.md` |

### Exit Criteria

- All success criteria met (see below)
- Documentation updated
- Configuration committed and tested

---

## Success Criteria

### Overall Epic Success

Achieve measurable improvement in **at least 3 of 4 dimensions**:

| Dimension             | Current           | Target              | Stretch          |
| --------------------- | ----------------- | ------------------- | ---------------- |
| **P50 Latency**       | 39.6s             | <15s                | <5s              |
| **Throughput**        | ~2 req/min        | >8 req/min          | >20 req/min      |
| **VRAM (full stack)** | ~25-27 GB (split) | <24 GB (A5500 only) | <20 GB           |
| **Quality**           | Baseline          | ≥95% of baseline    | ≥98% of baseline |

### Phase Exit Criteria Summary

| Phase       | Exit Condition                                                 |
| ----------- | -------------------------------------------------------------- |
| **Phase 1** | Benchmark suite runs, baseline captured, comparison tool works |
| **Phase 2** | All models benchmarked, recommendation documented with data    |
| **Phase 3** | Quantization/quality tradeoff curve documented, selection made |
| **Phase 4** | Engine comparison complete, migration path documented          |
| **Phase 5** | Batching optimizations tested, throughput gains measured       |
| **Phase 6** | Final config deployed, all targets validated, docs updated     |

---

## Decision Points

### After Phase 2 (Models)

```
If no smaller model meets 95% quality threshold:
  → Continue with 30B, focus on quantization/engine
```

### After Phase 3 (Quantization)

```
If aggressive quantization hurts quality too much:
  → Accept current VRAM footprint, focus on engine/batching
```

### After Phase 4 (Engine)

```
If vLLM doesn't fit or perform better:
  → Stay with llama.cpp, maximize its configuration
```

### Fallback Position

If we can't hit single-GPU target:

- Document optimal A5500 + A400 split configuration
- Prioritize latency and throughput over single-GPU goal

---

## Risks and Mitigations

| Risk                                   | Mitigation                                             |
| -------------------------------------- | ------------------------------------------------------ |
| Smaller models underperform            | Keep 30B as fallback, explore quality-adaptive routing |
| vLLM doesn't fit in 24GB               | Test with smaller models, or stay with llama.cpp       |
| Benchmarks don't reflect real workload | Include burst scenarios, use real prompt templates     |
| Scope creep                            | Strict phase gates, decision checkpoints               |

---

## References

- Current LLM optimization plan: `docs/plans/2026-01-31-llm-inference-optimization.md`
- Triton migration plan: `docs/plans/triton-migration.md`
- Model reference: `docs/reference/models.md`
- NIM research: Conducted 2025-02-04 (8 parallel research agents)
