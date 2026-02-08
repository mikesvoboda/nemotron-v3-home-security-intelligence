# AI Pipeline End-to-End Evaluation: Consolidated Synthesis Report

**Date:** 2026-02-08
**Agents Dispatched:** 9 (6 technology evaluators + 1 pipeline mapper + 1 Triton validator + 1 loader auditor)
**Reports Generated:** 8 detailed evaluation reports + this synthesis
**Revision:** v2 — corrected after Triton validation and loader audit

---

## Active Pipeline Architecture (Validated)

The pipeline mapper initially reported 6 standalone FastAPI microservices. **This was incorrect.** Subsequent validation confirmed the architecture has migrated to **Triton Inference Server + HTTP-to-gRPC gateway**.

### What's ACTUALLY Running

```
Backend (port 8000) ──HTTP──> AI Gateway (port 8090) ──gRPC──> Triton (port 8001 internal)
                                   │
                                   ├── /yolo26/*     → Triton: yolo26 (ONNX, GPU)
                                   ├── /florence/*    → Triton: florence2 (Python backend, GPU)
                                   ├── /clip/*        → Triton: clip (ONNX, GPU)
                                   ├── /enrichment/*  → Triton: vehicle, fashion_clip, demographics, xclip
                                   └── /enrich-lt/*   → Triton: pose, threat, reid, pet, depth

ai-llm (port 8091) ── Standalone llama.cpp server (GPU 0, A5500)
```

| Container      | Port | GPU                | Technology                                                  |
| -------------- | ---- | ------------------ | ----------------------------------------------------------- |
| **ai-gateway** | 8090 | GPU 1 (A400 4GB)   | Triton v2.54.0 + FastAPI gateway (13 models: 3 GPU, 10 CPU) |
| **ai-llm**     | 8091 | GPU 0 (A5500 24GB) | llama.cpp (Nemotron-3-Nano-30B Q4_K_M)                      |

**Key details:**

- `USE_AI_GATEWAY=true` — backend routes ALL AI calls through gateway
- Deployed via `scripts/deploy-gateway.sh` (standalone `podman run`, NOT docker-compose — required for GPU passthrough)
- Triton gRPC on internal :8001, FastAPI HTTP adapter on :8090
- 11 ONNX backend models, 2 Python backend models (florence2, xclip_action)
- Backend also loads **11 models in-process** via `model_manager.load()` for enrichment pipeline

### Dual Model Loading Architecture

The backend runs a **hybrid architecture** with both HTTP-to-Triton and in-process model loading:

| Path                                           | Models                                                                                                                    | Used For                                                      |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| **HTTP → Gateway → Triton**                    | yolo26, florence2, clip, all enrichment models                                                                            | Primary detection + captioning + embeddings                   |
| **In-process (model_manager)**                 | 11 models: vitpose, depth, fashion_clip, vehicle, xclip, violence, weather, segformer, pet, vehicle_damage, image_quality | Backend enrichment pipeline (`enrichment_pipeline.py`)        |
| **Hybrid (HTTP primary, in-process fallback)** | CLIP, Florence-2                                                                                                          | CLIP: HTTP primary; Florence: HTTP only (in-process disabled) |

### Dead Code (confirmed)

| Category              | Items                                                                                                                              | Status                                                              |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Standalone AI servers | `ai/yolo26/model.py`, `ai/florence/model.py`, `ai/clip/model.py`, `ai/enrichment/model.py`, `ai/enrichment-light/model.py`         | **Superseded** by Triton gateway — these are the OLD architecture   |
| Dead loaders          | `age_classifier_loader.py`, `gender_classifier_loader.py`, `osnet_loader.py`, `threat_detection_loader.py`, `yolo_world_loader.py` | **Never called** in pipeline — models exist but unused              |
| Special case          | `smoke_fire_loader.py`                                                                                                             | Marked CRITICAL/preload but never called via `model_manager.load()` |

### In-Flight Work (handled by other agents)

- **Merge conflicts** (14 files) — another agent resolving
- **Florence-2 garbage output** — actively being fixed

---

## Priority-Ranked Optimization Recommendations

### TIER 1: CRITICAL / Quick Wins (Do First)

| #   | Optimization                                                   | Source       | Impact   | Effort | Details                                                                                                                                                                              |
| --- | -------------------------------------------------------------- | ------------ | -------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | **Fix NemotronAnalyzer httpx anti-pattern**                    | Backend Eval | CRITICAL | 1h     | Creates new `httpx.AsyncClient` per request at 5+ locations (lines 400, 983, 1375, 3504, 4072). Adds ~50-100ms per LLM call. All other clients use persistent connections correctly. |
| 2   | **Enable CUDA Graphs** (`GGML_CUDA_GRAPH_OPT=1`)               | LLM Eval     | HIGH     | 5min   | Single env var in deploy script. Up to 35% faster token generation. Requires llama.cpp commit update first.                                                                          |
| 3   | **Add `--cache-reuse 256`** to llama-server CMD                | LLM Eval     | HIGH     | 5min   | Enables KV shifting for ~3K shared system prompt. 30-50% TTFT reduction.                                                                                                             |
| 4   | **Fix GPU_LAYERS inconsistency** in .env                       | LLM Eval     | HIGH     | 1min   | .env says 48 but compose defaults to 999. Verify actual runtime value and fix.                                                                                                       |
| 5   | **Fix Redis eviction policy** (`allkeys-lru` → `volatile-lru`) | Backend Eval | HIGH     | 5min   | Current policy silently evicts Stream/DLQ data under memory pressure.                                                                                                                |
| 6   | **Fix vehicle detection threshold** (0.70 too aggressive)      | YOLO Eval    | MEDIUM   | 30min  | Vehicles being missed. Lower to 0.40-0.50 for security monitoring.                                                                                                                   |

### TIER 2: HIGH Impact Optimizations

| #   | Optimization                                               | Source                         | Impact | Effort | Details                                                                                                                      |
| --- | ---------------------------------------------------------- | ------------------------------ | ------ | ------ | ---------------------------------------------------------------------------------------------------------------------------- |
| 7   | **Update llama.cpp commit** (9496bbb80 is ~6 months stale) | LLM Eval                       | HIGH   | 2-4h   | Missing CUDA graphs, QKV merging, improved Flash Attention, Mamba optimizations. Estimated 20-40% cumulative improvement.    |
| 8   | **Add `--merge-qkv`** to llama-server CMD                  | LLM Eval                       | MEDIUM | 5min   | Fuses Q/K/V attention projections. 5-15% generation speedup (modest — only 6/52 attention layers).                           |
| 9   | **Replace Jaeger + Elasticsearch with Grafana Tempo**      | Monitoring Eval                | HIGH   | 4-8h   | Saves ~5.5GB memory (ES alone is 6GB). Tempo monolithic mode runs in 1GB. Native Grafana integration.                        |
| 10  | **Fix YOLO A400 GPU architecture** in build_engine.py      | YOLO Eval                      | HIGH   | 30min  | RTX A400 is Ampere sm_86, documented as Turing sm_75. Wrong compute capability = suboptimal TensorRT engine.                 |
| 11  | **Enable INT8 quantization for YOLO26 in Triton**          | YOLO Eval                      | HIGH   | 2-4h   | Currently ONNX on GPU. INT8 calibration with security camera data could give ~2x speedup on A400.                            |
| 12  | **Parallelize enrichment model calls** in backend          | Backend Eval + Enrichment Eval | HIGH   | 4-6h   | In-process models run sequentially but are independent per frame. `AsyncTaskGroup` already exists. Latency: ~300ms → ~100ms. |
| 13  | **Optimize Triton dynamic batching config**                | Enrichment Eval                | HIGH   | 2-4h   | Triton has dynamic batching configured for only reid and vehicle. Enable for all 13 models with tuned queue delays.          |
| 14  | **Deploy INT8 quantization for enrichment ONNX models**    | Enrichment Eval                | HIGH   | 2-4h   | `quantize_models.py` exists but never deployed. Vehicle ResNet-50 + demographics ViTs → ~1,450MB VRAM savings.               |
| 15  | **Convert remaining CPU models to TensorRT**               | Enrichment Eval                | HIGH   | 8-16h  | 10 CPU ONNX models could run with TensorRT on GPU or optimized ONNX Runtime. 2-5x speedup per model.                         |

### TIER 3: MEDIUM Impact / Larger Efforts

| #   | Optimization                                               | Source          | Impact | Effort | Details                                                                                                                                         |
| --- | ---------------------------------------------------------- | --------------- | ------ | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| 16  | **Upgrade monitoring stack versions**                      | Monitoring Eval | MEDIUM | 4-8h   | Grafana 10.2→12.3, Prometheus 2.48→3.1, Loki 2.9→3.5, Alloy 1.0→1.9. Alloy upgrade may fix privileged mode SELinux issue.                       |
| 17  | **Fix Florence-2 Triton Python backend post-processing**   | Florence Eval   | HIGH   | 2-4h   | Garbage output — Triton backend not calling `processor.post_process_generation()`. Being actively worked on.                                    |
| 18  | **Deploy CLIP text encoder to Triton**                     | Florence Eval   | HIGH   | 4-8h   | Gateway adapter falls back to zero embeddings when `clip_text` model unavailable. Classify/similarity endpoints non-functional through gateway. |
| 19  | **Batch Florence-2 queries per entity**                    | Florence Eval   | MEDIUM | 4-6h   | Currently one HTTP call per detection. Batching = 40-50% latency reduction.                                                                     |
| 20  | **Switch Florence-2 base64 encoding from PNG to JPEG**     | Florence Eval   | MEDIUM | 1h     | 10x payload reduction, ~80% less transfer time.                                                                                                 |
| 21  | **Merge/remove unused middleware**                         | Backend Eval    | MEDIUM | 2-4h   | 16 middleware layers, DeprecationMiddleware has 0 registered endpoints. Merge Timing+Logging+Prometheus into one.                               |
| 22  | **Replace Depth Anything V2 Small with Tiny**              | Enrichment Eval | MEDIUM | 2h     | 3x faster inference, negligible quality loss for near/mid/far security depth estimation.                                                        |
| 23  | **Remove duplicate Prometheus scrape job**                 | Monitoring Eval | LOW    | 5min   | `llama-cpp-metrics` duplicates `ai-llm-metrics`, both scraping `ai-llm:8091`.                                                                   |
| 24  | **Add `--mlock`** to llama-server CMD                      | LLM Eval        | MEDIUM | 5min   | Prevents model weight page swapping for consistent latency.                                                                                     |
| 25  | **Add build flags** to llama.cpp Dockerfile                | LLM Eval        | MEDIUM | 30min  | `GGML_CUDA_FA_ALL_QUANTS=ON` and `GGML_NATIVE=ON` for better Flash Attention kernel coverage.                                                   |
| 26  | **Expose Triton native metrics** (port 8002) to Prometheus | Monitoring Eval | MEDIUM | 1h     | Triton has built-in Prometheus metrics but they're not exposed outside the container. Add scrape target.                                        |

### TIER 4: Strategic / Future Investment

| #   | Optimization                                           | Source                         | Impact | Effort    | Details                                                                                                                          |
| --- | ------------------------------------------------------ | ------------------------------ | ------ | --------- | -------------------------------------------------------------------------------------------------------------------------------- |
| 27  | **Optimize Triton model concurrency settings**         | Enrichment Eval                | HIGH   | 1-2 weeks | Tune instance groups, model priority, rate limiters per model for optimal GPU/CPU utilization.                                   |
| 28  | **Evaluate SigLIP 2** as CLIP replacement              | Florence Eval                  | MEDIUM | 8-16h     | Better accuracy at 5x fewer parameters.                                                                                          |
| 29  | **Replace OSNet x0.25 with ReIDMamba**                 | Enrichment Eval                | MEDIUM | 8-16h     | 1/3 parameters of TransReID, SOTA on 5 ReID benchmarks. Mamba architecture aligns with Nemotron stack.                           |
| 30  | **Replace X-CLIP with EZ-CLIP** for action recognition | Enrichment Eval                | MEDIUM | 8-16h     | 80% VRAM reduction (~2GB → ~400MB), ONNX-exportable (X-CLIP cannot be exported).                                                 |
| 31  | **Migrate backend in-process models to Triton**        | Enrichment Eval + Loader Audit | MEDIUM | 2-4 weeks | 11 models loaded via model_manager could be served through Triton instead, unifying the inference path.                          |
| 32  | **Evolve HTTP→gRPC gateway to direct gRPC**            | Backend Eval                   | MEDIUM | 2-4 weeks | Current architecture: Backend→HTTP→Gateway→gRPC→Triton. Direct gRPC from backend eliminates a hop. Track as future optimization. |
| 33  | **Clean up dead code**                                 | Pipeline Map + Loader Audit    | LOW    | 4-8h      | Standalone servers (`ai/*/model.py`), 5 dead loaders, disabled Florence in-process loader.                                       |

---

## Aggregate Impact Estimates

### Performance

- **LLM throughput**: +40-70% token generation, +30-50% TTFT (items 1-4, 7-8, 24-25)
- **YOLO detection**: +100% with INT8, +immediate fix for vehicle detection (items 10-11, 6)
- **Enrichment latency**: 3-7x reduction from parallelism + Triton batching + TensorRT (items 12-15, 22)
- **Florence-2**: Fix garbage output + 40-50% latency reduction (items 17, 19-20)
- **Gateway**: Triton dynamic batching across all models (item 13)

### Memory

- **Monitoring stack**: -5.5GB from Tempo migration (item 9)
- **Triton VRAM GPU 1**: INT8 quantization for ONNX models (item 14)
- **Backend RAM**: Reduced from 6GB if in-process models migrate to Triton (item 31)

### Reliability

- **Redis eviction**: Stream/DLQ data loss risk eliminated (item 5)
- **httpx connection reuse**: -50-100ms per LLM call, prevents connection exhaustion (item 1)
- **CLIP text encoder**: Classify/similarity endpoints currently non-functional through gateway (item 18)

---

## Recommended Linear Epic Structure

### Epic: AI Pipeline Optimization Phase 2

#### Sprint 1: Critical Fixes & Quick Wins (Items 1-6)

- Fix NemotronAnalyzer httpx connection pooling (CRITICAL)
- LLM quick wins: GPU_LAYERS, --cache-reuse, CUDA graphs env var
- Fix Redis eviction policy
- Fix vehicle detection threshold

#### Sprint 2: LLM & Detection Optimization (Items 7-11)

- Update llama.cpp commit + add --merge-qkv, --mlock, build flags
- Fix YOLO A400 architecture misidentification (sm_86, not sm_75)
- Enable YOLO INT8 quantization in Triton with calibration data

#### Sprint 3: Triton & Enrichment Optimization (Items 12-15, 22, 26)

- Parallelize backend enrichment model execution
- Optimize Triton dynamic batching for all 13 models
- Deploy INT8 quantization for enrichment ONNX models
- Evaluate TensorRT conversion for CPU ONNX models
- Swap Depth Anything V2 Small → Tiny
- Expose Triton native Prometheus metrics

#### Sprint 4: Florence-2 & CLIP Fixes (Items 17-20)

- Fix Florence-2 Triton Python backend post-processing (in progress)
- Deploy CLIP text encoder to Triton
- Batch Florence-2 queries + switch to JPEG encoding

#### Sprint 5: Monitoring Modernization (Items 9, 16, 21, 23)

- Replace Jaeger + Elasticsearch with Grafana Tempo
- Upgrade Grafana, Prometheus, Loki, Alloy versions
- Merge/remove unused middleware
- Remove duplicate Prometheus scrape job

#### Sprint 6: Strategic Model Upgrades (Items 27-33)

- Tune Triton concurrency and model priority settings
- Evaluate SigLIP 2, ReIDMamba, EZ-CLIP replacements
- Evaluate migrating in-process models to Triton
- Track direct gRPC evolution (HTTP→gRPC gateway already in place)
- Clean up dead code (standalone servers, dead loaders)

---

## What's Already Well-Done

- **Triton + Gateway architecture**: HTTP→gRPC translation layer avoids major backend refactor while getting Triton benefits. Smart incremental migration.
- **13/13 Triton models healthy**: All models loaded and returning READY status
- **Database pooling**: asyncpg pool_size=20, max_overflow=30, pool_pre_ping, LIFO, connection warming
- **Redis architecture**: Dedicated pools by workload (cache/queue/pubsub/ratelimit), Zstd compression
- **Circuit breakers**: 10 per-endpoint breakers with configurable thresholds and Prometheus metrics
- **LLM config**: Flash attention, KV cache quantization, continuous batching, Q4_K_M quantization choice
- **Security hardening**: no-new-privileges, cap_drop ALL, 127.0.0.1 binding across all services
- **Profiling**: Pyroscope + py-spy for Python, eBPF for llama.cpp C++
- **Graceful shutdown**: 30s queue drain timeout in backend
- **Deploy automation**: `scripts/deploy-gateway.sh` handles GPU passthrough that Podman compose cannot

---

## Source Reports

All detailed reports are in `data/ai-pipeline-evaluation/`:

| File                                         | Focus                                    | Tokens           |
| -------------------------------------------- | ---------------------------------------- | ---------------- |
| `00-triton-validation.md`                    | Triton + gateway validation (CORRECTIVE) | 68K              |
| `00-loader-audit.md`                         | Backend loader file audit                | 90K              |
| `01-llama-cpp-llm-evaluation.md`             | LLM inference optimization               | 78K              |
| `02-yolo-tensorrt-evaluation.md`             | Object detection pipeline                | 89K              |
| `03-florence2-clip-evaluation.md`            | Vision-language models                   | 162K             |
| `04-fastapi-backend-evaluation.md`           | Backend architecture                     | 124K             |
| `05-enrichment-pipeline-evaluation.md`       | Multi-model enrichment                   | 81K              |
| `06-monitoring-infrastructure-evaluation.md` | Observability & containers               | 92K              |
| **Total research investment**                | **9 agents**                             | **~874K tokens** |

---

## Corrections Log (v2)

| Original Claim                       | Correction                                                   | Source           |
| ------------------------------------ | ------------------------------------------------------------ | ---------------- |
| "6 standalone FastAPI microservices" | **1 Triton gateway + 1 LLM container**                       | Triton validator |
| "ai/triton/ is dead code"            | **Triton IS the active architecture** (13/13 models healthy) | Triton validator |
| "ai/gateway/ has 0 imports"          | **Gateway is the active HTTP→gRPC layer** (port 8090)        | Triton validator |
| "19 redundant loader files"          | **11 active, 2 hybrid, 5 dead, 1 special case**              | Loader auditor   |
| "Merge conflicts are Tier 1"         | **Removed** — another agent handling                         | User input       |
| "gRPC is a 2-4 week refactor"        | **Already implemented** via HTTP→gRPC gateway                | User input       |
| "Florence-2 in Tier 3"               | **Keep tracking** — actively being fixed                     | User input       |
| "Standalone AI servers are active"   | **These are the OLD architecture** (superseded by Triton)    | Triton validator |
