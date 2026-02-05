# Session Notes: NIM Research and LLM Performance Epic

**Date:** 2025-02-04
**Branch:** `msvoboda/dos13`

## Summary

Comprehensive research session on NVIDIA NIMs for potential deployment, followed by design and creation of an LLM inference performance optimization epic.

## Key Findings: NVIDIA NIM Feasibility

### Critical Constraint

**NIM does NOT support CPU layer offloading** - it requires the entire model to fit in GPU VRAM. This is a dealbreaker for memory-constrained deployments.

### Hardware Comparison

| Scenario                 | llama.cpp (current) | NVIDIA NIM       |
| ------------------------ | ------------------- | ---------------- |
| Nemotron 30B on 24GB GPU | ✅ Works (~14.7GB)  | ❌ Needs ~30GB   |
| CPU layer offloading     | ✅ Supported        | ❌ Not supported |
| Quantization options     | Q2-Q8, IQ variants  | FP8, BF16 only   |
| Licensing                | Free (MIT)          | $4,500/GPU/year  |

### NIM Features Already in Codebase

- `nvext.guided_json` structured generation
- `nvext.guided_choice` constrained outputs
- OpenAI-compatible API endpoints
- Chain-of-thought reasoning (`<think>` blocks)

### Recommendation

**Stay with llama.cpp** for production. NIM only viable with 48GB+ VRAM or smaller models.

## Epic Created: LLM Inference Performance Optimization

**Linear Epic:** [NEM-5441](https://linear.app/nemotron-v3-home-security/issue/NEM-5441)

### Phases (Updated Scope)

| Phase | Focus                     | Status            |
| ----- | ------------------------- | ----------------- |
| 1     | Benchmark Infrastructure  | Ready             |
| 2     | Quantization Exploration  | Models downloaded |
| 3     | Engine Exploration (vLLM) | Planned           |
| 4     | Batching & Scheduling     | Planned           |
| 5     | Integration & Validation  | Planned           |

**Note:** Model comparison phase (9B/8B/4B) was removed - focusing on quantization of the same 30B model instead.

### Success Criteria

- P50 Latency: <15s (from 39.6s)
- Throughput: >8 req/min (from ~2)
- VRAM: <24GB for full stack on A5500
- Quality: ≥95% of Q4_K_M baseline

## Models Downloaded

All quantizations for Nemotron-3-Nano-30B-A3B:

| Quantization | File Size | Location                                                   |
| ------------ | --------- | ---------------------------------------------------------- |
| Q4_K_M       | 23 GB     | `/export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km/` |
| Q4_K_S       | 21 GB     | `/export/ai_models/nemotron/quantization-benchmarks/`      |
| Q3_K_M       | 19 GB     | `/export/ai_models/nemotron/quantization-benchmarks/`      |
| Q3_K_S       | 17 GB     | `/export/ai_models/nemotron/quantization-benchmarks/`      |
| Q2_K_L       | 17 GB     | `/export/ai_models/nemotron/quantization-benchmarks/`      |

## Linear Tasks Status

### Research Tasks (Completed)

- ✅ NEM-5442: [Research] Phase 1: Benchmark Infrastructure
- ✅ NEM-5447: [Research] Phase 2: Model Comparison (scope changed)
- ✅ NEM-5452: [Research] Phase 3: Quantization Exploration
- ✅ NEM-5457: [Research] Phase 4: vLLM Engine Evaluation
- ✅ NEM-5462: [Research] Phase 5: Batching and Scheduling
- ✅ NEM-5467: [Research] Phase 6: Integration and Validation

### Canceled Tasks (Scope Change)

- ❌ NEM-5448: [TDD] Phase 2: Model Comparison
- ❌ NEM-5449: [Implement] Phase 2: Model Comparison
- ❌ NEM-5450: [Validate] Phase 2: Model Comparison
- ❌ NEM-5451: [Simplify] Phase 2: Model Comparison

### Ready to Start

- 🔓 NEM-5443: [TDD] Phase 1: Benchmark Infrastructure

## Commits Made

1. `440cc706` - docs: add LLM inference performance optimization epic
2. `8a79af47` - docs: add Linear epic design JSON for LLM performance optimization
3. `64f9910f` - docs: update LLM performance epic - remove model comparison phase

## Files Created/Modified

### Created

- `docs/plans/2025-02-04-llm-performance-epic.md` - Epic design document
- `docs/plans/llm-performance-epic-design.json` - Linear epic design JSON
- `docs/session-notes/2025-02-04-nim-research-and-performance-epic.md` - This file

### Model Files Downloaded

- `/export/ai_models/nemotron/quantization-benchmarks/Nemotron-3-Nano-30B-A3B-Q4_K_S.gguf`
- `/export/ai_models/nemotron/quantization-benchmarks/Nemotron-3-Nano-30B-A3B-Q3_K_M.gguf`
- `/export/ai_models/nemotron/quantization-benchmarks/Nemotron-3-Nano-30B-A3B-Q3_K_S.gguf`
- `/export/ai_models/nemotron/quantization-benchmarks/Nemotron-3-Nano-30B-A3B-Q2_K_L.gguf`

## Next Steps

1. Start **NEM-5443** - Write tests for benchmark infrastructure
2. Implement benchmark runner (`scripts/benchmark/run_benchmark.py`)
3. Create evaluation dataset from `data/synthetic/`
4. Capture baseline metrics for Q4_K_M
5. Begin quantization benchmarking

## Research Agents Used

8 parallel research agents explored:

1. NIM supported models
2. NIM deployment architecture
3. NIM vs llama.cpp comparison
4. Current Nemotron setup analysis
5. Nemotron Nano NIM features
6. NIM advanced inference features
7. NIM API and integration patterns
8. NeMo ecosystem capabilities
