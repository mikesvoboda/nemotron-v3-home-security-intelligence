# ruff: noqa: T201
#!/usr/bin/env python3
"""Create Linear epic and subtasks from AI Pipeline Evaluation synthesis report."""

import sys

sys.path.insert(0, "/home/msvoboda/.claude/skills/linear-python")

from linear_client import LinearClient

client = LinearClient()

# --- Create the parent epic ---
epic = client.create_issue(
    title="AI Pipeline Optimization Phase 2",
    description="""## Overview

End-to-end evaluation of the AI pipeline identified **33 optimization opportunities** across 6 technology areas. This epic tracks implementation across 6 sprints.

**Research investment:** 9 agents, ~874K tokens, 8 detailed reports in `data/ai-pipeline-evaluation/`

## Architecture (Current)

```
Backend (port 8000) ──HTTP──> AI Gateway (port 8090) ──gRPC──> Triton v2.54.0 (port 8001)
                                   ├── /yolo26/*     → yolo26 (ONNX, GPU)
                                   ├── /florence/*    → florence2 (Python backend, GPU)
                                   ├── /clip/*        → clip (ONNX, GPU)
                                   ├── /enrichment/*  → vehicle, fashion_clip, demographics, xclip
                                   └── /enrich-lt/*   → pose, threat, reid, pet, depth

ai-llm (port 8091) ── Standalone llama.cpp (GPU 0, A5500 24GB)
```

- **GPU 0 (A5500 24GB):** LLM at 95.9% VRAM
- **GPU 1 (A400 4GB):** Triton with 13 models (3 GPU, 10 CPU) at 76.4% VRAM
- Backend also loads 11 models in-process via `model_manager.load()`

## Aggregate Impact Estimates

- **LLM throughput**: +40-70% token generation, +30-50% TTFT
- **YOLO detection**: +100% with INT8 quantization
- **Enrichment latency**: 3-7x reduction (parallelism + Triton batching + TensorRT)
- **Monitoring memory**: -5.5GB from Tempo migration
- **VRAM savings**: INT8 quantization for enrichment models

## Sprint Structure

1. **Critical Fixes & Quick Wins** — httpx anti-pattern, LLM flags, Redis, vehicle threshold
2. **LLM & Detection Optimization** — llama.cpp update, YOLO INT8, architecture fix
3. **Triton & Enrichment Optimization** — parallelism, dynamic batching, INT8, TensorRT
4. **Florence-2 & CLIP Fixes** — post-processing, text encoder, batching
5. **Monitoring Modernization** — Tempo migration, version upgrades, middleware cleanup
6. **Strategic Model Upgrades** — Triton tuning, model replacements, dead code cleanup

## Source Reports

All in `data/ai-pipeline-evaluation/`:
- `SYNTHESIS-REPORT.md` — Consolidated findings (v2, corrected)
- `00-triton-validation.md` — Architecture validation
- `01-llama-cpp-llm-evaluation.md` through `06-monitoring-infrastructure-evaluation.md`
""",
    priority=2,  # High
    status="backlog",
)

epic_id = epic["issue"]["identifier"]
print(f"Created epic: {epic_id} — {epic['issue']['url']}")

# --- Sprint 1: Critical Fixes & Quick Wins ---
subtasks = [
    # Sprint 1
    {
        "title": "[Sprint 1] Fix NemotronAnalyzer httpx connection pooling anti-pattern",
        "priority": 1,  # Urgent
        "description": """**Impact:** CRITICAL | **Effort:** 1h | **Source:** Backend Eval (Report 04)

## Problem
`nemotron_analyzer.py` creates a new `httpx.AsyncClient` per request at 5+ locations (lines 400, 983, 1375, 3504, 4072). This destroys connection pooling and adds ~50-100ms per LLM call. All other AI clients (DetectorClient, CLIPClient, FlorenceClient, EnrichmentClient) correctly use persistent clients.

## Fix
Replace per-request `async with httpx.AsyncClient() as client:` with a persistent client initialized once and reused, matching the pattern used by other AI service clients (NEM-1721).

## Verification
- Grep for `httpx.AsyncClient` in nemotron_analyzer.py — should only appear once (initialization)
- Benchmark LLM call latency before/after
""",
    },
    {
        "title": "[Sprint 1] Enable CUDA Graphs for llama.cpp (`GGML_CUDA_GRAPH_OPT=1`)",
        "priority": 2,  # High
        "description": """**Impact:** HIGH (+35% token gen) | **Effort:** 5min | **Source:** LLM Eval (Report 01)

## Change
Add `GGML_CUDA_GRAPH_OPT=1` environment variable to ai-llm container in `scripts/deploy-gateway.sh`.

## Dependency
Requires llama.cpp commit update first (item #7) — CUDA graphs may not exist in current pinned commit 9496bbb80.

## References
- [NVIDIA Blog: Optimizing llama.cpp with CUDA Graphs](https://developer.nvidia.com/blog/optimizing-llama-cpp-ai-inference-with-cuda-graphs/)
""",
    },
    {
        "title": "[Sprint 1] Add `--cache-reuse 256` to llama-server CMD",
        "priority": 2,  # High
        "description": """**Impact:** HIGH (30-50% TTFT reduction) | **Effort:** 5min | **Source:** LLM Eval (Report 01)

## Change
Add `--cache-reuse 256` flag to the llama-server CMD in `ai/nemotron/Dockerfile`.

## Why
Enables KV shifting for prompt prefix reuse across slot reassignments. The ~3K token system prompt is shared across all security analysis requests. This reduces Time-To-First-Token by 30-50%.

Note: `cache_prompt: true` is already correctly sent in the API request body from `nemotron_analyzer.py` line 3993. `--cache-reuse` is the server-side complement.
""",
    },
    {
        "title": "[Sprint 1] Fix GPU_LAYERS .env inconsistency (48 vs 999)",
        "priority": 2,  # High
        "description": """**Impact:** HIGH | **Effort:** 1min | **Source:** LLM Eval (Report 01)

## Problem
`.env` sets `GPU_LAYERS=48` but `docker-compose.prod.yml` defaults to `${GPU_LAYERS:-999}`. The compose override wins at runtime. Verify the actual runtime value and set `.env` to 999 to match intent (all layers on GPU).

## Verification
```bash
podman exec ai-llm env | grep GPU_LAYERS
```
""",
    },
    {
        "title": "[Sprint 1] Fix Redis eviction policy (`allkeys-lru` → `volatile-lru`)",
        "priority": 2,  # High
        "description": """**Impact:** HIGH (data loss prevention) | **Effort:** 5min | **Source:** Backend Eval (Report 04)

## Problem
Redis at 450MB with `allkeys-lru` will silently evict Stream entries and DLQ data under memory pressure. Streams and DLQ should never be evicted.

## Fix
Change `--maxmemory-policy allkeys-lru` to `--maxmemory-policy volatile-lru` in docker-compose.prod.yml Redis command. This only evicts keys with TTL set, protecting Streams/DLQ.

## Alternative
Increase `--maxmemory` from 450mb to 512mb or 640mb as additional buffer.
""",
    },
    {
        "title": "[Sprint 1] Fix vehicle detection threshold (0.70 → 0.40-0.50)",
        "priority": 3,  # Medium
        "description": """**Impact:** MEDIUM (vehicles being missed) | **Effort:** 30min | **Source:** YOLO Eval (Report 02)

## Problem
Vehicle detection confidence threshold of 0.70 is too aggressive for security monitoring. Vehicles are being missed in detections.

## Fix
Lower threshold to 0.40-0.50 range for security camera use cases where recall matters more than precision.

## Location
Check Triton gateway YOLO adapter and backend configuration for where this threshold is applied.
""",
    },
    # Sprint 2
    {
        "title": "[Sprint 2] Update llama.cpp pinned commit (6 months stale)",
        "priority": 2,  # High
        "description": """**Impact:** HIGH (20-40% cumulative improvement) | **Effort:** 2-4h | **Source:** LLM Eval (Report 01)

## Problem
Current pinned commit `9496bbb80` in `ai/nemotron/Dockerfile` line 23 is approximately 6 months behind HEAD.

## Missing Features
- CUDA graph support (GGML_CUDA_GRAPH_OPT)
- QKV merging (--merge-qkv)
- Improved Flash Attention kernels
- Better Mamba/hybrid model backends
- --cache-reuse flag
- Speculative decoding in server mode

## Change
Update to a recent stable commit or tagged release (e.g., b5200+). Rebuild and validate:
1. Model loads correctly
2. Health endpoint responds
3. Inference quality unchanged (run test prompts)
4. VRAM usage within bounds

## Also add these flags after update
- `--merge-qkv` (fuses Q/K/V attention projections, 5-15% speedup)
- `--mlock` (prevents model weight page swapping)

## Build flags to add
```cmake
cmake -B build \\
    -DGGML_CUDA=ON \\
    -DGGML_CUDA_FA_ALL_QUANTS=ON \\
    -DGGML_NATIVE=ON \\
    -DCMAKE_BUILD_TYPE=Release
```
""",
    },
    {
        "title": "[Sprint 2] Replace Jaeger + Elasticsearch with Grafana Tempo",
        "priority": 2,  # High
        "description": """**Impact:** HIGH (-5.5GB memory) | **Effort:** 4-8h | **Source:** Monitoring Eval (Report 06)

## Problem
Elasticsearch uses 6GB memory limit + 2GB heap solely for Jaeger trace storage. This is excessive for a single-node system.

## Change
Replace both `jaeger` and `elasticsearch` services with `grafana/tempo` in monolithic mode:
- Tempo runs in ~1GB memory (vs 6.5GB for ES+Jaeger)
- Native Grafana integration with TraceQL query support
- Local filesystem storage (no separate database)
- OTLP-native (direct from Alloy/backend)

## Migration Steps
1. Add Tempo service to docker-compose.prod.yml
2. Configure Grafana Tempo datasource in provisioning
3. Update Alloy config to send traces to Tempo instead of Jaeger
4. Update backend OTEL_EXPORTER_OTLP_ENDPOINT to point to Tempo
5. Remove jaeger and elasticsearch services
6. Remove elasticsearch_data volume

## Saves
~5.5GB RAM, 2 fewer containers, simpler architecture.
""",
    },
    {
        "title": "[Sprint 2] Fix YOLO A400 GPU architecture (sm_86 not sm_75)",
        "priority": 2,  # High
        "description": """**Impact:** HIGH (suboptimal TensorRT engine) | **Effort:** 30min | **Source:** YOLO Eval (Report 02)

## Problem
`build_engine.py` documents RTX A400 as Turing sm_75, but it is actually Ampere sm_86. This means TensorRT may be building engines for the wrong compute capability.

## Fix
Update the GPU architecture constant/documentation in build_engine.py. Rebuild TensorRT engine targeting sm_86.

## Verification
```bash
nvidia-smi --query-gpu=compute_cap --format=csv,noheader
```
""",
    },
    {
        "title": "[Sprint 2] Enable INT8 quantization for YOLO26 in Triton",
        "priority": 2,  # High
        "description": """**Impact:** HIGH (~2x speedup) | **Effort:** 2-4h | **Source:** YOLO Eval (Report 02)

## Problem
YOLO26 runs as ONNX FP32/FP16 on GPU. INT8 would give ~2x speedup on A400.

## Prerequisites
- Calibration dataset from actual security camera images (100-500 representative frames)
- INT8 export infrastructure already exists in the codebase

## Steps
1. Collect calibration images from `/export/foscam/` directories
2. Run INT8 calibration using existing export_tensorrt.py
3. Update Triton model config to load INT8 engine
4. Validate detection accuracy hasn't degraded significantly
""",
    },
    # Sprint 3
    {
        "title": "[Sprint 3] Parallelize backend enrichment model calls",
        "priority": 2,  # High
        "description": """**Impact:** HIGH (300ms → 100ms latency) | **Effort:** 4-6h | **Source:** Backend Eval (Report 04) + Enrichment Eval (Report 05)

## Problem
In-process models in `enrichment_pipeline.py` run sequentially but are independent per frame. `AsyncTaskGroup` and `bounded_gather` already exist in `async_utils.py` but aren't used for enrichment.

## Fix
Use `asyncio.TaskGroup` to run independent enrichment model calls concurrently:
- vitpose, depth, fashion_clip, vehicle, xclip, violence, weather, segformer, pet, vehicle_damage, image_quality
- Latency becomes max(single_model) instead of sum(all_models)

## Constraint
Models share GPU VRAM, so concurrent GPU execution may need semaphore-based serialization. CPU-only models can run truly parallel.
""",
    },
    {
        "title": "[Sprint 3] Optimize Triton dynamic batching for all 13 models",
        "priority": 2,  # High
        "description": """**Impact:** HIGH (2-3x throughput) | **Effort:** 2-4h | **Source:** Enrichment Eval (Report 05)

## Problem
Dynamic batching is only configured for `reid` (batch 1/4/8) and `vehicle` (batch 1/4) in Triton config.pbtxt files. The other 11 models have no batching configured.

## Fix
Add `dynamic_batching { max_queue_delay_microseconds: 100000 }` to all 13 model config.pbtxt files with appropriate preferred_batch_sizes.

## Location
`ai/triton/model_repository/*/config.pbtxt`
""",
    },
    {
        "title": "[Sprint 3] Deploy INT8 quantization for enrichment ONNX models",
        "priority": 2,  # High
        "description": """**Impact:** HIGH (-1,450MB VRAM) | **Effort:** 2-4h | **Source:** Enrichment Eval (Report 05)

## Problem
`ai/enrichment/scripts/quantize_models.py` exists and is fully implemented but never deployed. Environment flags `VEHICLE_QUANTIZED=false`, `DEMOGRAPHICS_QUANTIZED=false` in `.env.example`.

## Fix
1. Run quantize_models.py to generate INT8 ONNX models
2. Update Triton model configs to load quantized versions
3. Set VEHICLE_QUANTIZED=true, DEMOGRAPHICS_QUANTIZED=true
4. Validate accuracy on representative security camera data

## Expected savings
Vehicle ResNet-50 + Demographics ViTs → ~1,450MB VRAM reduction on heavy service.
""",
    },
    {
        "title": "[Sprint 3] Evaluate TensorRT conversion for CPU ONNX models",
        "priority": 3,  # Medium
        "description": """**Impact:** HIGH (2-5x per model) | **Effort:** 8-16h | **Source:** Enrichment Eval (Report 05)

## Problem
10 of 13 Triton models run as ONNX on CPU. These could potentially run on GPU with TensorRT or use optimized ONNX Runtime with TensorRT EP.

## Models to evaluate
fashion_clip (372MB), demographics_age (344MB), demographics_gender (344MB), depth (101MB), vehicle (94MB), pet (45MB), pose (14MB), threat (12MB), reid (1.5MB), xclip_action (Python)

## Consideration
A400 has 4GB VRAM with 3 GPU models already using ~2.4GB. Available headroom is ~1.6GB. Only small models (pose, threat, reid, pet, depth = ~373MB total) could fit on GPU.

## Approach
1. Profile CPU inference latency for each model
2. Identify bottleneck models
3. Convert highest-impact models to TensorRT
4. Monitor GPU VRAM utilization
""",
    },
    {
        "title": "[Sprint 3] Replace Depth Anything V2 Small with Tiny",
        "priority": 3,  # Medium
        "description": """**Impact:** MEDIUM (3x faster) | **Effort:** 2h | **Source:** Enrichment Eval (Report 05)

## Problem
Depth Anything V2 Small is overkill for security depth estimation (near/mid/far categorization). The Tiny variant provides 3x faster inference with negligible quality loss for coarse depth ordering.

## Change
1. Download Depth Anything V2 Tiny model
2. Export to ONNX
3. Update Triton model config and in-process loader
4. Validate depth quality on security camera samples
""",
    },
    {
        "title": "[Sprint 3] Expose Triton native Prometheus metrics",
        "priority": 3,  # Medium
        "description": """**Impact:** MEDIUM | **Effort:** 1h | **Source:** Monitoring Eval (Report 06)

## Problem
Triton has built-in Prometheus metrics at port 8002 but they're not exposed outside the ai-gateway container or scraped by Prometheus.

## Fix
1. Expose port 8002 in ai-gateway container (deploy-gateway.sh)
2. Add Prometheus scrape target for Triton metrics
3. Create Grafana dashboard for per-model inference latency, queue depth, batch sizes
""",
    },
    # Sprint 4
    {
        "title": "[Sprint 4] Fix Florence-2 Triton Python backend post-processing",
        "priority": 2,  # High
        "description": """**Impact:** HIGH (fixes garbage output) | **Effort:** 2-4h | **Source:** Florence Eval (Report 03)

## Problem
Florence-2 Triton Python backend not calling `processor.post_process_generation()` with task prompt and image size, resulting in garbage output. The standalone server (`ai/florence/model.py` lines 634-643) does this correctly.

## Status
Actively being worked on by another agent. Track to completion.

## Fix
Ensure Triton Python backend in `ai/triton/model_repository/florence2/1/model.py` calls post_process_generation with the original task prompt and image dimensions.
""",
    },
    {
        "title": "[Sprint 4] Deploy CLIP text encoder to Triton",
        "priority": 2,  # High
        "description": """**Impact:** HIGH (enables classify/similarity) | **Effort:** 4-8h | **Source:** Florence Eval (Report 03)

## Problem
Gateway adapter (`ai/gateway/adapters/clip.py` lines 160-206) falls back to returning zero embeddings when `clip_text` Triton model is unavailable. This makes classify/similarity/batch-similarity endpoints non-functional through the gateway.

## Fix
1. Export CLIP text encoder to ONNX
2. Create `clip_text` model config in Triton model repository
3. Deploy text encoder model alongside vision encoder
4. Update gateway adapter to use the Triton text model instead of fallback
""",
    },
    {
        "title": "[Sprint 4] Batch Florence-2 queries per entity + switch to JPEG",
        "priority": 3,  # Medium
        "description": """**Impact:** MEDIUM (40-50% latency reduction + 80% less transfer) | **Effort:** 4-6h | **Source:** Florence Eval (Report 03)

## Changes
1. **Batch queries**: Currently one HTTP call per detection. Batch multiple detections in a single request for 40-50% latency reduction.
2. **JPEG encoding**: Switch base64 image encoding from PNG to JPEG. 10x payload reduction, ~80% less network transfer time.

## Location
Backend: `florence_client.py` and gateway: `ai/gateway/adapters/florence.py`
""",
    },
    # Sprint 5
    {
        "title": "[Sprint 5] Upgrade monitoring stack versions",
        "priority": 3,  # Medium
        "description": """**Impact:** MEDIUM | **Effort:** 4-8h | **Source:** Monitoring Eval (Report 06)

## Current → Target Versions
- Grafana: 10.2.3 → 12.3 (2 major versions behind)
- Prometheus: 2.48.0 → 3.1 (1 major version behind, native OTLP)
- Loki: 2.9.4 → 3.5 (native OTLP log endpoint, bloom filters)
- Alloy: 1.0.0 → 1.9+ (18 minor releases behind, **may fix privileged mode SELinux issue**)

## Priority
Alloy upgrade is highest priority — may eliminate the privileged mode security workaround.

## Approach
Upgrade one at a time, validate after each:
1. Alloy (test SELinux fix)
2. Grafana (test dashboards still work)
3. Loki (test log queries)
4. Prometheus (test metrics/alerts)
""",
    },
    {
        "title": "[Sprint 5] Merge/remove unused middleware layers",
        "priority": 3,  # Medium
        "description": """**Impact:** MEDIUM | **Effort:** 2-4h | **Source:** Backend Eval (Report 04)

## Problem
16 middleware layers, every request traverses all of them. `DeprecationMiddleware` and `DeprecationLoggerMiddleware` are active but have zero registered endpoints.

## Fix
1. Remove DeprecationMiddleware and DeprecationLoggerMiddleware (0 registered endpoints)
2. Merge Timing + Logging + Prometheus middleware into one layer (saves 2 async call boundaries per request)
3. Audit remaining middleware for unused layers
""",
    },
    {
        "title": "[Sprint 5] Remove duplicate Prometheus scrape job",
        "priority": 4,  # Low
        "description": """**Impact:** LOW | **Effort:** 5min | **Source:** Monitoring Eval (Report 06)

## Problem
`llama-cpp-metrics` scrape job duplicates `ai-llm-metrics`, both scraping `ai-llm:8091`.

## Fix
Remove the duplicate job from `monitoring/prometheus.yml`.
""",
    },
    # Sprint 6
    {
        "title": "[Sprint 6] Optimize Triton model concurrency and priority settings",
        "priority": 3,  # Medium
        "description": """**Impact:** HIGH | **Effort:** 1-2 weeks | **Source:** Enrichment Eval (Report 05)

## Task
Tune Triton instance groups, model priority, and rate limiters per model for optimal GPU/CPU utilization.

## Areas to tune
- Instance count per model (currently 1 for all)
- Model priority (YOLO26 should be highest — it's in the critical path)
- Rate limiter for GPU models to prevent VRAM contention
- Sequence batching for Florence-2 and X-CLIP (Python backends)
""",
    },
    {
        "title": "[Sprint 6] Evaluate SigLIP 2 as CLIP replacement",
        "priority": 3,  # Medium
        "description": """**Impact:** MEDIUM | **Effort:** 8-16h | **Source:** Florence Eval (Report 03)

## Rationale
SigLIP 2 offers better accuracy at 5x fewer parameters than CLIP ViT-L. Would reduce VRAM and improve embedding quality for re-identification.

## Tasks
1. Benchmark SigLIP 2 vs CLIP ViT-L on security camera embeddings
2. Test re-identification accuracy with SigLIP embeddings
3. Export to ONNX/TensorRT
4. If better, migrate Triton model config
""",
    },
    {
        "title": "[Sprint 6] Evaluate ReIDMamba as OSNet replacement",
        "priority": 3,  # Medium
        "description": """**Impact:** MEDIUM | **Effort:** 8-16h | **Source:** Enrichment Eval (Report 05)

## Rationale
ReIDMamba has 1/3 the parameters of TransReID, SOTA on 5 ReID benchmarks, and its Mamba architecture aligns with the Nemotron hybrid Mamba-Transformer stack.

## Tasks
1. Download and benchmark ReIDMamba
2. Compare ReID accuracy vs OSNet x0.25 on security camera data
3. Export to ONNX for Triton
4. If better, update model_zoo and Triton config
""",
    },
    {
        "title": "[Sprint 6] Evaluate EZ-CLIP as X-CLIP replacement for action recognition",
        "priority": 3,  # Medium
        "description": """**Impact:** MEDIUM (80% VRAM reduction) | **Effort:** 8-16h | **Source:** Enrichment Eval (Report 05)

## Rationale
X-CLIP requires ~2GB VRAM and cannot be exported to ONNX (custom cross-frame attention). EZ-CLIP at ~400MB is ONNX-exportable with competitive accuracy.

## Tasks
1. Benchmark EZ-CLIP action recognition on security scenarios
2. Export to ONNX
3. Compare accuracy vs X-CLIP on key actions (loitering, fighting, breaking in)
4. If viable, deploy to Triton (replacing Python backend with ONNX backend)
""",
    },
    {
        "title": "[Sprint 6] Evaluate migrating backend in-process models to Triton",
        "priority": 3,  # Medium
        "description": """**Impact:** MEDIUM | **Effort:** 2-4 weeks | **Source:** Enrichment Eval (Report 05) + Loader Audit

## Background
Backend currently loads 11 models in-process via `model_manager.load()` in `enrichment_pipeline.py`. These could potentially be served through Triton instead, unifying the inference path.

## In-process models (11 active)
vitpose, depth, fashion_clip, vehicle, xclip, violence, weather, segformer, pet, vehicle_damage, image_quality

## Trade-offs
**Pro:** Unified inference, dynamic batching, better GPU utilization, reduced backend memory
**Con:** Added network hop, more complex debugging, need to handle model_manager fallback

## Decision needed
Is the benefit of unified Triton inference worth the migration effort and added complexity?
""",
    },
    {
        "title": "[Sprint 6] Track: Evolve HTTP→gRPC gateway to direct gRPC",
        "priority": 4,  # Low
        "description": """**Impact:** MEDIUM | **Effort:** 2-4 weeks | **Source:** Backend Eval (Report 04)

## Current
Backend → HTTP → FastAPI Gateway → gRPC → Triton

## Future
Backend → gRPC → Triton (direct, eliminates a hop)

## Status
The HTTP→gRPC gateway is already implemented and working. This is a future optimization to eliminate the intermediate FastAPI translation layer. Track for later evaluation.
""",
    },
    {
        "title": "[Sprint 6] Clean up dead code (standalone servers, dead loaders)",
        "priority": 4,  # Low
        "description": """**Impact:** LOW | **Effort:** 4-8h | **Source:** Pipeline Map + Loader Audit

## Dead standalone AI servers (superseded by Triton)
- `ai/yolo26/model.py`
- `ai/florence/model.py`
- `ai/clip/model.py`
- `ai/enrichment/model.py`
- `ai/enrichment-light/model.py`

## Dead loader files (never called in pipeline)
- `backend/services/age_classifier_loader.py`
- `backend/services/gender_classifier_loader.py`
- `backend/services/osnet_loader.py`
- `backend/services/threat_detection_loader.py`
- `backend/services/yolo_world_loader.py`

## Special case
- `backend/services/smoke_fire_loader.py` — marked CRITICAL/preload but never called via model_manager.load()

## Approach
Archive or remove dead files. Keep standalone servers as reference if needed for fallback architecture.
""",
    },
]

# Create all subtasks
print(f"\nCreating {len(subtasks)} subtasks under {epic_id}...\n")

for i, task in enumerate(subtasks, 1):
    result = client.create_subtask(
        parent_identifier=epic_id,
        title=task["title"],
        description=task["description"],
        priority=task["priority"],
        status="backlog",
    )
    issue = result["issue"]
    print(f"  [{i:2d}/{len(subtasks)}] {issue['identifier']}: {task['title'][:70]}")

print(f"\nDone! Created epic {epic_id} with {len(subtasks)} subtasks.")
print(f"View at: {epic['issue']['url']}")
