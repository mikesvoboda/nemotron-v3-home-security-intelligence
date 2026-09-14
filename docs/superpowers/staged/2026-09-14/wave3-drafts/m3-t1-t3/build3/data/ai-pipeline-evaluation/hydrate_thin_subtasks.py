#!/usr/bin/env python3
"""Hydrate 12 thin Linear subtasks with exact implementation details."""

import sys

sys.path.insert(0, "/home/msvoboda/.claude/skills/linear-python")

from linear_client import LinearClient

client = LinearClient()

updates = [
    {
        "id": "NEM-5539",
        "description": r"""**Impact:** HIGH (+35% token gen) | **Effort:** 5min | **Source:** LLM Eval (Report 01)

## Change
Add `GGML_CUDA_GRAPH_OPT=1` environment variable to the ai-llm container.

**Dependency:** Requires NEM-5544 (llama.cpp commit update) first — CUDA graphs may not exist in pinned commit 9496bbb80.

## Exact Location
`scripts/deploy-gateway.sh` lines 110-124, the ai-llm `podman run` command:

```bash
podman run -d \
  --name ai-llm \
  --network "$NETWORK" \
  --device "nvidia.com/gpu=${GPU_LLM:-0}" \
  --security-opt label=disable \
  -e PORT="${LLM_PORT:-8091}" \
  -e CUDA_VISIBLE_DEVICES=0 \
  -e GPU_LAYERS="${GPU_LAYERS:-48}" \
  -e CTX_SIZE="${CTX_SIZE:-32768}" \
  -e PARALLEL="${PARALLEL:-2}" \
  -e GGML_CUDA_GRAPH_OPT=1 \          # <-- ADD THIS LINE
  -v "/export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km:/models:ro,z" \
  -p "127.0.0.1:${LLM_PORT:-8091}:${LLM_PORT:-8091}" \
  ai-llm 2>&1 | tail -1
```

Insert `-e GGML_CUDA_GRAPH_OPT=1` after the PARALLEL env var (line ~120).

## How It Works
CUDA graphs capture the GPU execution graph and replay it, eliminating CPU-side kernel launch overhead. Particularly effective for batch-size-1 token generation (the dominant workload for security event analysis).

## Verification
```bash
podman exec ai-llm env | grep GGML_CUDA_GRAPH
# Should output: GGML_CUDA_GRAPH_OPT=1
```

## References
- [NVIDIA Blog: Optimizing llama.cpp with CUDA Graphs](https://developer.nvidia.com/blog/optimizing-llama-cpp-ai-inference-with-cuda-graphs/)
""",
    },
    {
        "id": "NEM-5540",
        "description": r"""**Impact:** HIGH (30-50% TTFT reduction) | **Effort:** 5min | **Source:** LLM Eval (Report 01)

## Change
Add `--cache-reuse 256` flag to the llama-server CMD in the Dockerfile.

## Exact Location
`ai/nemotron/Dockerfile` lines 104-124, the CMD definition:

```dockerfile
CMD ["sh", "-c", "FLASH_ARGS=''; \
    if [ \"${FLASH_ATTENTION}\" = 'true' ]; then FLASH_ARGS='--flash-attn on'; fi; \
    MOE_ARGS=''; \
    if [ -n \"${MOE_OFFLOAD_PATTERN}\" ]; then MOE_ARGS=\"--override-tensor ${MOE_OFFLOAD_PATTERN}=CPU\"; fi; \
    llama-server \
    --model ${MODEL_PATH} \
    --host 0.0.0.0 \
    --port ${PORT} \
    --n-gpu-layers ${GPU_LAYERS} \
    --ctx-size ${CTX_SIZE} \
    --parallel ${PARALLEL} \
    --threads ${THREADS} \
    --threads-batch ${THREADS} \
    --batch-size ${BATCH_SIZE} \
    --ubatch-size ${UBATCH_SIZE} \
    --cache-type-k ${CACHE_TYPE_K} \
    --cache-type-v ${CACHE_TYPE_V} \
    --cont-batching \
    --metrics \
    --cache-reuse 256 \
    ${FLASH_ARGS} \
    ${MOE_ARGS}"]
```

Add `--cache-reuse 256 \` on a new line after `--metrics \` (line 125) and before `${FLASH_ARGS}`.

## How It Works
With 2 parallel slots and the shared ~3K token system prompt:
- Without `--cache-reuse`: slot reassignment requires re-processing entire prompt
- With `--cache-reuse 256`: server uses KV shifting to retain the shared prefix, only processing new event data tokens

Note: `cache_prompt: true` is already correctly sent in API body from `nemotron_analyzer.py` line 3993. `--cache-reuse` is the server-side complement.

## Verification
Check llama-server startup logs for `cache_reuse` parameter confirmation.
""",
    },
    {
        "id": "NEM-5541",
        "description": r"""**Impact:** HIGH (5-15% speedup if layers were on CPU) | **Effort:** 1min | **Source:** LLM Eval (Report 01)

## Problem: Three different defaults across four files

| File | Line | Current Value | Used When |
|------|------|--------------|-----------|
| `.env` | 55 | `GPU_LAYERS=48` | Source of truth for compose and deploy script |
| `docker-compose.prod.yml` | 218 | `${GPU_LAYERS:-999}` | Compose mode (fallback=999 if .env unset) |
| `ai/nemotron/Dockerfile` | 66 | `ENV GPU_LAYERS=35` | Only if no runtime -e override |
| `scripts/deploy-gateway.sh` | 119 | `${GPU_LAYERS:-48}` | Gateway deploy mode (fallback=48) |

## What Actually Wins at Runtime
- **Compose mode:** `.env` value (48) overrides compose default (999), so 48 layers on GPU
- **Gateway deploy mode:** `.env` value (48) used, fallback is also 48

**Result:** 48 of 53 layers on GPU. 5 layers unnecessarily on CPU.

## VRAM Budget Analysis
The A5500 has ample headroom for all 53 layers:
- Model weights (Q4_K_M): ~9.5GB
- KV cache (6 attn layers, 32K ctx, q8_0): ~192MB
- Compute buffers: ~1-2GB
- **Total: ~11-12GB out of 24GB**

## Fix
```bash
# .env line 55 — change from:
GPU_LAYERS=48
# to:
GPU_LAYERS=999
```

Also update `scripts/deploy-gateway.sh` line 119 fallback:
```bash
# From:
-e GPU_LAYERS="${GPU_LAYERS:-48}" \
# To:
-e GPU_LAYERS="${GPU_LAYERS:-999}" \
```

## Verification
```bash
podman exec ai-llm env | grep GPU_LAYERS
# Should show: GPU_LAYERS=999
nvidia-smi  # Monitor VRAM usage — should still be well within 24GB
```
""",
    },
    {
        "id": "NEM-5546",
        "description": r"""**Impact:** HIGH (documentation fix, TensorRT may be suboptimal) | **Effort:** 30min | **Source:** YOLO Eval (Report 02)

## Problem
`ai/yolo26/build_engine.py` lines 9-12 incorrectly maps A400 to Turing (sm_75):

```python
# Current (WRONG):
TensorRT engines are GPU-architecture-specific. The CUDA_COMPUTE_CAP build arg
controls which GPU architecture the engine targets:
  - sm_75: RTX 2080 / T4 / A400        # <-- A400 is NOT Turing
  - sm_86: RTX 3090 / A5500
```

RTX A400 is **Ampere architecture (sm_86)**, same generation as A5500.

## Fix
Update `ai/yolo26/build_engine.py` lines 9-12:
```python
# Corrected:
  - sm_75: RTX 2080 / T4 (Turing)
  - sm_86: RTX 3090 / A5500 / A400 (Ampere)
  - sm_89: RTX 4090 / L4 (Ada Lovelace)
```

## Runtime Impact
The code auto-detects compute capability via `torch.cuda.get_device_properties()` at build time, so the TensorRT engine should be built correctly regardless of comments. However, verify:

```bash
# Confirm actual compute capability
nvidia-smi --query-gpu=compute_cap --format=csv,noheader
# Expected: 8.6 for A400, 8.6 for A5500
```

Search for any hardcoded sm_75 values that might affect the build:
```bash
grep -rn "sm_75\|compute_75\|7.5" ai/yolo26/ ai/clip/ ai/gateway/
```

## Files to Check
- `ai/yolo26/build_engine.py` (lines 9-12) — primary fix
- `ai/clip/build_engine.py` — check for same issue
- `ai/gateway/export/` — check export scripts
""",
    },
    {
        "id": "NEM-5548",
        "description": r"""**Impact:** HIGH (300ms → 100ms enrichment latency) | **Effort:** 4-6h | **Source:** Backend Eval (Report 04) + Enrichment Eval (Report 05)

## Problem
In-process models in `enrichment_pipeline.py` run sequentially via `model_manager.load()` but are independent per frame.

## Existing Async Utilities (ready to use)
`backend/core/async_utils.py` provides:

```python
from backend.core.async_utils import AsyncTaskGroup, bounded_gather

# Option 1: Structured concurrency
async with AsyncTaskGroup() as tg:
    tg.create_task(operation_a())
    tg.create_task(operation_b())

# Option 2: Bounded concurrency
results = await bounded_gather(
    [operation(i) for i in range(100)],
    limit=10,
)
```

## Implementation

### Step 1: Find sequential model calls in enrichment_pipeline.py
Search for the pattern where models are called one after another in `_enrich_single_detection_unified` or similar methods. The calls look like:

```python
# Current (sequential):
pose_result = await self._run_pose_estimation(detection)
depth_result = await self._run_depth_estimation(detection)
clothing_result = await self._run_clothing_classification(detection)
vehicle_result = await self._run_vehicle_classification(detection)
```

### Step 2: Convert to parallel using bounded_gather
```python
# New (parallel with VRAM-aware concurrency limit):
results = await bounded_gather(
    [
        self._run_pose_estimation(detection),
        self._run_depth_estimation(detection),
        self._run_clothing_classification(detection),
    ],
    limit=3,  # Limit concurrent GPU model loads to avoid VRAM OOM
)
pose_result, depth_result, clothing_result = results
```

### Step 3: Separate GPU vs CPU models
GPU models (need serialization for VRAM safety):
- vitpose, depth_anything, fashion_clip, xclip (if on GPU)

CPU models (can run truly parallel):
- vehicle, pet, segformer, violence, weather, image_quality

```python
# Run CPU models in parallel (no VRAM concern)
cpu_results = await bounded_gather(cpu_model_tasks, limit=5)

# Run GPU models with tighter limit
gpu_results = await bounded_gather(gpu_model_tasks, limit=2)
```

## Files to Modify
- `backend/services/enrichment_pipeline.py` — main orchestration
- Import `bounded_gather` from `backend/core/async_utils`

## Verification
- Measure enrichment latency before/after
- Monitor VRAM usage during concurrent GPU model loads
- Ensure all enrichment fields still populated correctly
""",
    },
    {
        "id": "NEM-5552",
        "description": r"""**Impact:** MEDIUM (3x faster inference) | **Effort:** 2h | **Source:** Enrichment Eval (Report 05)

## Change
Replace Depth Anything V2 Small with V2 Tiny encoder.

## Current Configuration

**Model Zoo** (`backend/services/model_zoo.py` line ~18):
```python
"depth-anything-v2-small": ModelConfig(...)  # Monocular depth estimation
```

**Loader** (`backend/services/depth_anything_loader.py` line 11):
```python
# HuggingFace: depth-anything/Depth-Anything-V2-Small-hf
```

**Triton config** (`ai/triton/model_repository/depth/config.pbtxt`):
```pbtxt
# Depth Estimation - ONNX Runtime (Depth Anything V2 Small / DPT-Small)
# Input: preprocessed image (B, 3, 518, 518) FP32
# Output: depth map (B, 1, 518, 518) FP32
```

## HuggingFace Model IDs
- Current: `depth-anything/Depth-Anything-V2-Small-hf`
- Target: `depth-anything/Depth-Anything-V2-Tiny-hf`

## Implementation Steps

### 1. Download Tiny model
```bash
huggingface-cli download depth-anything/Depth-Anything-V2-Tiny-hf \
  --local-dir /export/ai_models/model-zoo/depth-anything-v2-tiny
```

### 2. Export to ONNX
```python
from transformers import AutoModelForDepthEstimation
model = AutoModelForDepthEstimation.from_pretrained("depth-anything/Depth-Anything-V2-Tiny-hf")
# Export using torch.onnx.export or optimum
```

### 3. Update references
- `model_zoo.py`: Change model name/path from "small" to "tiny"
- `depth_anything_loader.py`: Update HuggingFace model ID
- `ai/triton/model_repository/depth/config.pbtxt`: Update comments (dims stay same: 518x518)
- Place exported ONNX in `/export/ai_models/triton/depth/1/model.onnx`

## Notes
- Tiny uses **same 518x518 input resolution** as Small — Triton config dims unchanged
- Both produce same output format (depth map)
- For security use case (near/mid/far categorization), Tiny quality is sufficient
""",
    },
    {
        "id": "NEM-5553",
        "description": r"""**Impact:** MEDIUM (per-model Triton metrics in Grafana) | **Effort:** 1h | **Source:** Monitoring Eval (Report 06)

## Problem
Triton has built-in Prometheus metrics at port 8002 inside the ai-gateway container, but the port is not exposed and not scraped.

## Current State

**Triton already starts with metrics enabled** (`ai/gateway/entrypoint.sh` lines 75-86):
```bash
tritonserver \
    --model-repository="${TRITON_MODEL_REPO}" \
    --metrics-port="${TRITON_METRICS_PORT}" \  # Port 8002 (line 14)
    ...
```

**Port is NOT exposed** in `scripts/deploy-gateway.sh` lines 98-108 (only 8090 is mapped).

## Implementation Steps

### 1. Expose port 8002 in deploy-gateway.sh
Add after line 107 (the AI_GATEWAY_PORT mapping):
```bash
-p "127.0.0.1:${AI_GATEWAY_METRICS_PORT:-8002}:8002" \
```

### 2. Add Prometheus scrape target
Add to `monitoring/prometheus.yml` after the ai-llm-metrics job (~line 92):
```yaml
  - job_name: 'triton-metrics'
    metrics_path: /metrics
    scrape_interval: 15s
    scrape_timeout: 10s
    static_configs:
      - targets:
          - 'ai-gateway:8002'
    labels:
      service: triton
      component: inference-server
```

### 3. (Optional) Create Grafana dashboard
Triton exposes rich metrics:
- `nv_inference_request_success` / `nv_inference_request_failure` per model
- `nv_inference_queue_duration_us` — queue wait time
- `nv_inference_compute_infer_duration_us` — actual inference time
- `nv_gpu_utilization` — GPU utilization
- `nv_inference_count` — total inference count per model

## Verification
```bash
curl -s http://localhost:8002/metrics | head -20
# Should show Triton metrics with nv_inference_* prefixes
```
""",
    },
    {
        "id": "NEM-5554",
        "description": r"""**Impact:** HIGH (fixes garbage output) | **Effort:** 2-4h | **Source:** Florence Eval (Report 03)

## Problem
Florence-2 Triton Python backend returns garbage output because post-processing doesn't properly handle task-specific parsing.

## Exact Location
`ai/triton/model_repository/florence2/1/model.py` lines 388-406:

```python
# Current (incomplete post-processing):
task_type = TASKS_ANSWER_POST_PROCESSING_TYPE.get(prompt, "pure_text")
parsed = self.post_processor(
    text=generated_text,
    image_size=(image.width, image.height),
    parse_tasks=task_type,
)

if task_type in parsed:
    result = parsed[task_type]
    if task_type == "pure_text":
        result = result.replace("<s>", "").replace("</s>", "").strip()
    return result

# Fallback: returns cleaned text — LOSES STRUCTURED DATA
return generated_text.replace("<s>", "").replace("</s>", "").strip()
```

## What's Missing
For structured tasks (OD, OCR, phrase grounding), Florence-2 outputs `<loc_...>` tokens that need to be parsed into bounding boxes. The fallback at line 406 strips these tokens and returns plain text, losing all spatial information.

## Reference Implementation
The standalone server `ai/florence/model.py` handles this correctly (lines ~634-643). It calls `processor.post_process_generation()` with:
- The generated text
- The original task prompt
- The image size (width, height)

This returns properly structured data (bboxes, labels, etc.) depending on the task type.

## Fix
Replicate the standalone server's post-processing in the Triton Python backend. Ensure:
1. `<MORE_DETAILED_CAPTION>` → returns rich text description
2. `<OD>` → returns parsed bounding boxes with labels
3. `<OCR_WITH_REGION>` → returns text regions with coordinates
4. `<CAPTION_TO_PHRASE_GROUNDING>` → returns grounded phrase results

## Status
Being actively worked on by another agent. Track to completion.
""",
    },
    {
        "id": "NEM-5555",
        "description": r"""**Impact:** HIGH (enables classify/similarity endpoints) | **Effort:** 4-8h | **Source:** Florence Eval (Report 03)

## Problem
CLIP text encoder is NOT deployed to Triton. Gateway adapter falls back to lazy-loading open_clip on CPU (often fails), then returns zero embeddings.

## Current Fallback Code
`ai/gateway/adapters/clip.py` lines 60-100:

```python
def _ensure_text_encoder() -> bool:
    Lazy-init the open_clip text encoder and tokenizer.
    global _text_model, _text_tokenizer, _text_encoder_failed
    if _text_encoder_failed:
        return False
    try:
        import open_clip
        logger.info("Loading open_clip ViT-L-14 text encoder (CPU)...")
        model, _, _ = open_clip.create_model_and_transforms("ViT-L-14", pretrained="openai")
        model = model.eval().cpu()
        tokenizer = open_clip.get_tokenizer("ViT-L-14")
        _text_model = model
        _text_tokenizer = tokenizer
        return True
    except Exception:
        _text_encoder_failed = True
        logger.warning("Failed to load open_clip text encoder. "
                       "classify/similarity will return placeholder results.")
```

When this fails, `/clip/classify`, `/clip/similarity`, and `/clip/batch-similarity` all return zero/placeholder embeddings.

## Implementation Steps

### 1. Export CLIP text encoder to ONNX
```python
from transformers import CLIPTextModel, CLIPTokenizer
import torch

model = CLIPTextModel.from_pretrained("openai/clip-vit-large-patch14")
tokenizer = CLIPTokenizer.from_pretrained("openai/clip-vit-large-patch14")

dummy_input = tokenizer("sample text", return_tensors="pt", padding="max_length", max_length=77)
torch.onnx.export(
    model,
    (dummy_input["input_ids"], dummy_input["attention_mask"]),
    "/export/ai_models/triton/clip_text/1/model.onnx",
    input_names=["input_ids", "attention_mask"],
    output_names=["text_embeds"],
    dynamic_axes={"input_ids": {0: "batch"}, "attention_mask": {0: "batch"}},
    opset_version=14,
)
```

### 2. Create Triton config
`ai/triton/model_repository/clip_text/config.pbtxt`:
```pbtxt
name: "clip_text"
backend: "onnxruntime"
max_batch_size: 8
input [
  { name: "input_ids", data_type: TYPE_INT64, dims: [77] },
  { name: "attention_mask", data_type: TYPE_INT64, dims: [77] }
]
output [
  { name: "text_embeds", data_type: TYPE_FP32, dims: [768] }
]
instance_group [{ count: 1, kind: KIND_CPU }]
dynamic_batching { max_queue_delay_microseconds: 50000 }
```

### 3. Update gateway adapter
Replace `_ensure_text_encoder()` fallback in `ai/gateway/adapters/clip.py` with Triton gRPC call to `clip_text` model.

### 4. Verification
```bash
curl -X POST http://localhost:8090/clip/classify \
  -F "image=@test_image.jpg" \
  -F "labels=person,vehicle,animal"
# Should return non-zero similarity scores
```
""",
    },
    {
        "id": "NEM-5556",
        "description": r"""**Impact:** MEDIUM (40-50% latency + 80% transfer reduction) | **Effort:** 4-6h | **Source:** Florence Eval (Report 03)

## Two Changes

### Change 1: Batch Florence-2 queries
**Current:** One HTTP call per detection in `backend/services/florence_client.py`
**Proposed:** Batch multiple detections in a single request

#### Backend client changes (`florence_client.py`):
```python
async def batch_extract(self, items: list[dict]) -> list[dict]:
    Batch multiple detection crops in one request.
    payload = {"detections": [
        {"image": self._encode_image(item["crop"]), "prompt": item.get("prompt", "<MORE_DETAILED_CAPTION>")}
        for item in items
    ]}
    response = await self._http_client.post(f"{self.base_url}/batch-extract", json=payload)
    return response.json()["results"]
```

#### Gateway adapter changes (`ai/gateway/adapters/florence.py`):
Add a `/batch-extract` endpoint that processes multiple image+prompt pairs in one call.

### Change 2: Switch PNG to JPEG encoding
**Current:** PNG base64 encoding (large payloads)
**Proposed:** JPEG at quality=85 (70% smaller)

Find the image encoding function in `florence_client.py` (likely `_encode_image` or similar):
```python
# Current (PNG):
buffer = io.BytesIO()
image.save(buffer, format="PNG")
b64 = base64.b64encode(buffer.getvalue()).decode()

# New (JPEG):
buffer = io.BytesIO()
image.save(buffer, format="JPEG", quality=85)
b64 = base64.b64encode(buffer.getvalue()).decode()
```

**Savings:** ~50KB PNG → ~15KB JPEG per crop at quality=85.

## Files to Modify
- `backend/services/florence_client.py` — add batch method + JPEG encoding
- `ai/gateway/adapters/florence.py` — add /batch-extract endpoint
""",
    },
    {
        "id": "NEM-5558",
        "description": r"""**Impact:** MEDIUM (2-5ms per request) | **Effort:** 2-4h | **Source:** Backend Eval (Report 04)

## Problem
16 middleware layers in `backend/main.py` lines 1130-1189. Every request traverses all of them.

## Current Stack (outermost to innermost, from main.py):
```python
app.add_middleware(SetupGuardMiddleware)
app.add_middleware(ContentTypeValidationMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(BaggageMiddleware)
app.add_middleware(ProfilingMiddleware)
app.add_middleware(PrometheusMiddleware)
app.add_middleware(RequestTimingMiddleware)
if request_logging_enabled:
    app.add_middleware(RequestLoggingMiddleware)
if request_recording_enabled:
    app.add_middleware(RequestRecorderMiddleware)
app.add_middleware(DeprecationMiddleware, config=_get_deprecation_config())
app.add_middleware(DeprecationLoggerMiddleware)
app.add_middleware(CORSMiddleware, ...)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(GZipMiddleware)
app.add_middleware(IdempotencyMiddleware)
```

Middleware directory: `backend/api/middleware/` (25 files total)

## Actions

### 1. Remove DeprecationMiddleware + DeprecationLoggerMiddleware
`backend/api/middleware/deprecation.py` — config returns empty `_endpoints` dict (line ~133). Zero deprecated endpoints registered. Safe to remove both.

### 2. Merge observability middleware
Combine these three into a single `ObservabilityMiddleware`:
- `backend/api/middleware/timing.py` (RequestTimingMiddleware)
- `backend/api/middleware/request_logging.py` (RequestLoggingMiddleware)
- `backend/api/middleware/prometheus.py` (PrometheusMiddleware)

This saves 2 async call boundaries per request.

### 3. Add health endpoint short-circuit
Add early return in the outermost middleware for `/health`, `/ready`, `/metrics` to bypass the full 16-layer stack:
```python
if scope["path"] in {"/health", "/api/system/health/ready", "/metrics"}:
    return await self.app(scope, receive, send)  # Skip remaining middleware
```

## Files to Modify
- `backend/main.py` lines 1130-1189 — middleware registration
- `backend/api/middleware/deprecation.py` — remove or stub
- `backend/api/middleware/deprecation_logger.py` — remove or stub
- `backend/api/middleware/timing.py` + `request_logging.py` + `prometheus.py` — merge into one

## Verification
- Run full test suite after changes
- Benchmark request latency on /health endpoint before/after
- Ensure Prometheus metrics still recorded correctly
""",
    },
    {
        "id": "NEM-5559",
        "description": r"""**Impact:** LOW (cleanup) | **Effort:** 5min | **Source:** Monitoring Eval (Report 06)

## Problem
Two Prometheus scrape jobs scrape the same target `ai-llm:8091`.

## Duplicate Jobs in `monitoring/prometheus.yml`

**Job 1 (lines 81-92) — KEEP:**
```yaml
  - job_name: 'ai-llm-metrics'
    metrics_path: /metrics
    scrape_interval: 15s
    scrape_timeout: 10s
    static_configs:
      - targets:
          - 'ai-llm:8091'
        labels:
          service: nemotron
          model_type: llm
    honor_labels: true
```

**Job 2 (lines 274-286) — REMOVE:**
```yaml
  - job_name: 'llama-cpp-metrics'
    metrics_path: /metrics
    scrape_interval: 15s
    scrape_timeout: 10s
    static_configs:
      - targets:
          - 'ai-llm:8091'
    relabel_configs:
      - target_label: service
        replacement: 'nemotron-llm'
      - target_label: ai_model
        replacement: 'nemotron-3-nano-30b'
```

## Fix
Delete lines 274-286 from `monitoring/prometheus.yml`. Keep `ai-llm-metrics` (lines 81-92) as the canonical job — it has `honor_labels: true` which preserves native metric labels.

## Verification
```bash
curl -s localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job | test("llm|llama"))'
# Should show only one target, not two
```
""",
    },
]

print(  # noqa: T201 # noqa: T201 # noqa: T201
    f"Hydrating {len(updates)} subtasks...\n"
)

for update in updates:
    internal_id = client._resolve_issue_id(update["id"])
    escaped_desc = (
        update["description"].replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    )

    mutation = f'''
    mutation {{
        issueUpdate(id: "{internal_id}", input: {{
            description: "{escaped_desc}"
        }}) {{
            success
            issue {{ identifier title }}
        }}
    }}
    '''
    try:
        result = client._query(mutation)
        issue = result["issueUpdate"]["issue"]
        print(  # noqa: T201 # noqa: T201
            f"  Updated {issue['identifier']}: {issue['title'][:65]}"
        )
    except Exception as e:
        print(  # noqa: T201 # noqa: T201
            f"  FAILED {update['id']}: {e}"
        )

print(  # noqa: T201 # noqa: T201 # noqa: T201
    f"\nDone! All {len(updates)} subtasks hydrated."
)
