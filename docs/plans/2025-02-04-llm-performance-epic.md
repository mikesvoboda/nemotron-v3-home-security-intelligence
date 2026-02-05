# LLM Inference Performance Optimization Epic

**Created:** 2025-02-04
**Status:** Active
**Updated:** 2025-02-04 - Removed model comparison phase, focusing on quantization
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

## Phase 2: Quantization Exploration

**Goal:** Find optimal VRAM/quality tradeoff through quantization of the Nemotron-3-Nano-30B-A3B model.

### Quantization Formats to Test

All quantizations use the same Nemotron-3-Nano-30B-A3B architecture:

| Format                | Bits          | File Size | Expected VRAM | Quality Impact |
| --------------------- | ------------- | --------- | ------------- | -------------- |
| **Q4_K_M** (baseline) | 4-bit         | ~23 GB    | ~14.7 GB      | Baseline       |
| **Q4_K_S**            | 4-bit (small) | ~22 GB    | ~13.5 GB      | Minimal        |
| **Q3_K_M**            | 3-bit         | ~20 GB    | ~11 GB        | Moderate       |
| **Q3_K_S**            | 3-bit (small) | ~18 GB    | ~10 GB        | Noticeable     |
| **Q2_K_L**            | 2-bit (large) | ~18 GB    | ~9 GB         | Significant    |

### Model Locations

| Quantization | Path                                                       |
| ------------ | ---------------------------------------------------------- |
| Q4_K_M       | `/export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km/` |
| Q4_K_S       | `/export/ai_models/nemotron/quantization-benchmarks/`      |
| Q3_K_M       | `/export/ai_models/nemotron/quantization-benchmarks/`      |
| Q3_K_S       | `/export/ai_models/nemotron/quantization-benchmarks/`      |
| Q2_K_L       | `/export/ai_models/nemotron/quantization-benchmarks/`      |

### Quality vs VRAM Tradeoff Analysis

For each quantization level, measure:

1. **Risk score MAE** (mean absolute error vs Q4_K_M baseline)
2. **Risk level accuracy** (% exact match)
3. **Reasoning coherence** (manual review of edge cases)
4. **VRAM saved** (GB freed for other models)
5. **Inference latency** (any performance degradation?)

### Key Question

```
Can we find a quantization that:
  - Saves 3-5 GB VRAM (enough to fit full stack on A5500)
  - Maintains ≥95% quality vs Q4_K_M
  - Doesn't increase latency significantly
```

### Decision Framework

```
If Q4_K_S quality ≥ 98% AND saves ~1GB:
  → Use Q4_K_S (minimal quality loss)

If Q3_K_M quality ≥ 95% AND saves ~4GB:
  → Use Q3_K_M (fit full stack on A5500)

If Q3_K_S quality ≥ 90% AND saves ~5GB:
  → Use Q3_K_S (aggressive but acceptable)

If Q2_K_L quality < 85%:
  → Q2_K too aggressive, stop at Q3_K_S
```

### Deliverables

| Deliverable       | Location                                  |
| ----------------- | ----------------------------------------- |
| Quantized models  | `/export/ai_models/nemotron/`             |
| Benchmark results | `results/benchmarks/quant-*.json`         |
| Tradeoff curves   | `docs/reports/quantization-comparison.md` |

### Exit Criteria

- All 5 quantization levels benchmarked
- Quality/VRAM tradeoff curve documented
- Optimal quantization selected based on 95% quality threshold

---

## Phase 3: Engine Exploration

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

## Phase 4: Batching and Scheduling Optimizations

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

## Phase 5: Integration and Validation

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
| **Phase 2** | Quantization/quality tradeoff curve documented, selection made |
| **Phase 3** | Engine comparison complete, migration path documented          |
| **Phase 4** | Batching optimizations tested, throughput gains measured       |
| **Phase 5** | Final config deployed, all targets validated, docs updated     |

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
