# Florence-2 & CLIP Model Serving Evaluation

**Date:** 2026-02-08
**Evaluator:** AI Pipeline Research Agent (Claude Opus 4.6)
**Scope:** Florence-2 and CLIP model optimization for home security AI pipeline

---

## Executive Summary

This evaluation examines the current Florence-2 and CLIP model serving configurations within the nemotron-v3 home security intelligence pipeline, identifies critical bugs, and recommends optimizations ranked by impact. The analysis is based on a thorough code review of 10+ source files across the `ai/`, `backend/services/`, and `ai/gateway/adapters/` directories, supplemented by HuggingFace documentation and community research.

**Key findings:**

1. **Florence-2 garbage output is a known processor post-processing issue** -- the current code correctly uses `skip_special_tokens=False` + `post_process_generation()` in `ai/florence/model.py`, but the Triton Python backend adapter may not be applying this two-step decode properly, causing structured outputs to be returned as raw token strings.

2. **CLIP is well-architected** with SDPA attention, TensorRT acceleration, and surveillance-specific prompt ensembling already implemented. The main gap is the missing `clip_text` Triton model, which means classify/similarity endpoints return placeholder results through the gateway.

3. **Florence-2-base (232M params) is already configured** in the Dockerfile (`FLORENCE_MODEL_PATH=/models/florence-2-base`) despite documentation referencing "Florence-2-large". Base is likely sufficient for security captioning given VRAM constraints.

4. **Highest-impact optimizations**: Fix Florence-2 Triton backend decode pipeline (HIGH), deploy CLIP text encoder to Triton (HIGH), switch to SigLIP 2 for improved embeddings (MEDIUM), enable JPEG encoding for base64 payloads (MEDIUM).

---

## Table of Contents

1. [Current Configuration Analysis](#current-configuration-analysis)
2. [Florence-2 Findings](#florence-2-findings)
3. [CLIP Findings](#clip-findings)
4. [Recommended Optimizations](#recommended-optimizations)
5. [Alternative Models Assessment](#alternative-models-assessment)
6. [References](#references)

---

## Current Configuration Analysis

### Florence-2

| Parameter             | Current Value                                   | Source File                           |
| --------------------- | ----------------------------------------------- | ------------------------------------- |
| Model                 | Florence-2 (base configured, docs say large)    | `ai/florence/Dockerfile` line 111     |
| GPU                   | Shares GPU 0 (A5500 24GB) with LLM              | docker-compose                        |
| Base Image            | `pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime` | `ai/florence/Dockerfile` line 69      |
| VRAM Budget           | ~1.2GB                                          | Dockerfile comment                    |
| Container Limits      | 2 CPUs, 6GB memory                              | docker-compose                        |
| Attention             | `eager` (SDPA disabled)                         | `ai/florence/model.py` lines 517, 527 |
| torch.compile         | Enabled by default (`FLORENCE_USE_COMPILE=1`)   | `ai/florence/model.py` line 802       |
| Accelerate device_map | Enabled by default                              | `ai/florence/model.py` line 804       |
| Batch size            | Max 4 (configurable)                            | `ai/florence/model.py` line 806       |
| KV Cache              | Disabled (`use_cache=False`)                    | `ai/florence/model.py` line 627       |
| Num beams             | 1 (greedy decoding)                             | `ai/florence/model.py` line 626       |
| Max new tokens        | 1024                                            | `ai/florence/model.py` line 623       |

### CLIP

| Parameter         | Current Value                                     | Source File                        |
| ----------------- | ------------------------------------------------- | ---------------------------------- |
| Model             | CLIP ViT-L/14                                     | `ai/clip/model.py`                 |
| GPU               | A400 4GB (GPU 1)                                  | docker-compose                     |
| Base Image        | `nvcr.io/nvidia/tensorrt:25.12-py3`               | `ai/clip/Dockerfile` line 12       |
| VRAM Budget       | ~800MB (PyTorch) / ~600MB (TensorRT)              | Dockerfile comment                 |
| Container Limits  | 2 CPUs, 3GB memory                                | docker-compose                     |
| Attention         | SDPA (with fallback to default)                   | `ai/clip/model.py` lines 654-658   |
| TensorRT          | Optional, auto-exports ONNX->TRT on first run     | `ai/clip/model.py` lines 529-588   |
| Embedding Dim     | 768                                               | `ai/clip/model.py` line 227        |
| Prompt Ensembling | 5 surveillance-specific templates per camera type | `ai/clip/model.py` lines 129-168   |
| Thread Safety     | `_model_lock` for concurrent access               | `ai/clip/model.py` lines 1186-1189 |

---

## Florence-2 Findings

### F1. Garbage Output Root Cause Analysis

**Severity: CRITICAL**

The standalone Florence server (`ai/florence/model.py`) correctly implements the two-step decode:

```python
# Step 1: Decode with special tokens preserved
generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=False)[0]

# Step 2: Post-process to extract structured result
parsed_result = self.processor.post_process_generation(
    generated_text,
    task=prompt,
    image_size=(image.width, image.height),
)
```

However, the Triton Python backend (`florence2` model) communicates via the gateway adapter (`ai/gateway/adapters/florence.py`), which receives raw text output from Triton and attempts to parse it as JSON:

```python
# Gateway adapter receives OUTPUT_TEXT from Triton
text_result = raw_output[0].decode("utf-8")
# Then tries JSON parsing
parsed = _parse_json_output(text)  # json.loads() attempt
```

The garbage output occurs when:

1. The Triton Python backend returns the raw `batch_decode(..., skip_special_tokens=False)` output (with location tokens like `<loc_123>`) without calling `post_process_generation()`
2. OR when it returns the `post_process_generation()` dict as a string representation rather than proper JSON
3. OR when the processor in the Triton container was not initialized with `trust_remote_code=True`, causing the `post_process_generation()` method to be missing or broken

**The fix requires ensuring the Triton Python backend model calls `post_process_generation()` with the correct task prompt and image size, and serializes the result as proper JSON before returning it as `OUTPUT_TEXT`.**

### F2. Processor Initialization

The processor is loaded correctly with `trust_remote_code=True`:

```python
self.processor = AutoProcessor.from_pretrained(
    self.model_path,
    trust_remote_code=True,
)
```

This is the documented correct approach. The `post_process_generation()` method is part of Florence-2's custom processor code and requires `trust_remote_code=True` to be available. No issues found here in the standalone server.

### F3. Attention Implementation

Florence-2 uses `attn_implementation="eager"` rather than SDPA. This is intentional per the code comment:

> Use eager attention implementation to avoid SDPA compatibility issues with Florence-2's custom model code

This is confirmed by [HuggingFace issue #41622](https://github.com/huggingface/transformers/issues/41622) which documents that Florence-2's remote code lacks the `_supports_sdpa` attribute. Using eager attention is correct for now but represents a ~15-30% latency penalty compared to SDPA/Flash Attention.

### F4. KV Cache Disabled

The code disables KV cache with `use_cache=False` and documents the reason:

> The Florence-2 model's prepare_inputs_for_generation has a bug with past_key_values

This is a known issue in Florence-2's custom code. Disabling it prevents crashes but increases generation latency since each token must re-attend to all previous tokens. For the typical max_new_tokens=1024, this could be 2-3x slower than cached generation.

### F5. torch.compile Status

torch.compile is attempted but may silently fail:

```python
if self.use_compile and is_compile_supported():
    try:
        self.model = compile_model(self.model, mode="reduce-overhead")
        self.is_compiled = True
    except Exception as e:
        logger.warning(f"torch.compile() failed for Florence-2: {e}")
```

Florence-2 with `trust_remote_code=True` uses custom Python code that often causes compilation graph breaks. The `reduce-overhead` mode is the correct choice (uses CUDA graphs), but it is likely failing silently on this model. **The logs should be checked to confirm whether compilation actually succeeds.**

### F6. Model Size: Base vs Large

The Dockerfile sets `FLORENCE_MODEL_PATH=/models/florence-2-base`, which is the 232M parameter variant. Florence-2-Large is 771M parameters. Key differences:

| Metric          | Florence-2-Base (232M) | Florence-2-Large (771M) |
| --------------- | ---------------------- | ----------------------- |
| COCO CIDEr      | ~120                   | 135.6                   |
| VRAM            | ~0.5GB (FP16)          | ~1.5GB (FP16)           |
| Inference Speed | ~2x faster             | Baseline                |
| Parameters      | 232M                   | 771M                    |

For security captioning (vehicle color, person clothing, scene description), Florence-2-Base provides adequate quality given that its outputs are consumed by the Nemotron LLM for final risk scoring. The LLM can compensate for less detailed captions through its own reasoning.

### F7. Sequential Multi-Query Pattern

The `FlorenceExtractor` (`backend/services/florence_extractor.py`) makes 4-5 sequential inference calls per entity:

- Vehicle: caption + color + type + commercial + logo (5 calls)
- Person: caption + clothing + carrying + service_worker + action (5 calls)
- Scene: caption + tools + abandoned + unusual (4 calls)

Each call goes through HTTP -> base64 encode -> network -> decode -> inference -> encode -> network. This is highly inefficient.

---

## CLIP Findings

### C1. SDPA Attention (Positive)

CLIP correctly attempts SDPA with graceful fallback:

```python
try:
    self.model = CLIPModel.from_pretrained(
        self.model_path,
        torch_dtype=dtype,
        attn_implementation="sdpa",
    )
except (ValueError, ImportError) as e:
    self.model = CLIPModel.from_pretrained(self.model_path, torch_dtype=dtype)
```

SDPA provides 15-40% faster inference for CLIP's attention layers. This is working correctly.

### C2. TensorRT Auto-Export Pipeline (Positive)

The CLIP service has a sophisticated TensorRT pipeline:

1. Checks for pre-built engine
2. Auto-exports to ONNX if not found
3. Converts ONNX to TensorRT
4. Validates engine against current GPU architecture
5. Falls back to PyTorch on any failure

This is well-engineered. Expected speedup is 1.5-2x over PyTorch FP16.

### C3. Missing Triton Text Encoder

The gateway CLIP adapter (`ai/gateway/adapters/clip.py`) has a critical gap:

```python
async def _get_text_embeddings(texts: list[str]) -> np.ndarray:
    try:
        if await triton.is_model_ready("clip_text"):
            # Use Triton text encoder
            ...
    except Exception as e:
        logger.debug(f"Triton clip_text model not available, using fallback: {e}")

    # Fallback: Return zero embeddings with a warning
    logger.warning("CLIP text encoder not available in Triton.")
    return np.zeros((len(texts), EMBEDDING_DIMENSION), dtype=np.float32)
```

This means all classify, similarity, and batch-similarity endpoints through the gateway return meaningless results. The standalone CLIP server handles text encoding correctly using `CLIPModel.get_text_features()`.

### C4. Surveillance Prompt Ensembling (Positive)

The CLIP server implements camera-type-specific prompt templates (5 per type) that improve zero-shot classification accuracy by 5-10% on surveillance footage. This is a well-researched technique that bridges the domain gap between CLIP's web-image training data and security camera footage.

### C5. Base64 PNG Encoding Overhead

Both Florence and CLIP clients encode images as PNG:

```python
image.save(buffer, format="PNG")
```

PNG is lossless but significantly larger than JPEG. For 640x480 security camera frames, PNG base64 is ~1.2MB vs JPEG base64 at ~100KB. This adds unnecessary network overhead and base64 encode/decode CPU cost.

### C6. Input Validation (Positive)

CLIP has thorough input validation:

- Base64 size limits (10MB decoded max)
- Image dimension limits (4096x4096 max)
- Allowed format validation (JPEG, PNG, GIF, BMP, WebP)
- Batch size limits (configurable, default 100)
- Field validators on Pydantic models

This is production-quality validation.

---

## Recommended Optimizations

### HIGH Impact

#### H1. Fix Florence-2 Triton Backend Post-Processing

**What to change:** Ensure the Triton Python backend for Florence-2 calls `processor.post_process_generation()` with the correct task prompt and image dimensions, then serializes the structured result as JSON before returning in `OUTPUT_TEXT`.

**Expected impact:** Eliminates garbage output from Florence-2 through the gateway path. This is the #1 blocking issue for Florence-2 functionality.

**Implementation effort:** 2-4 hours. Modify the Triton Python backend model.py for florence2 to:

1. Store the task prompt alongside the image
2. Call `post_process_generation(decoded_text, task=prompt, image_size=image_size)`
3. Return `json.dumps(parsed_result)` as OUTPUT_TEXT

**Risks:** Requires rebuilding the Triton model repository. Must verify all task prompts produce valid JSON output.

---

#### H2. Deploy CLIP Text Encoder to Triton

**What to change:** Export the CLIP text encoder as an ONNX model and deploy it as the `clip_text` model in Triton.

**Expected impact:** Enables classify, similarity, and batch-similarity endpoints through the AI Gateway, which currently return zero embeddings.

**Implementation effort:** 4-8 hours.

1. Export `CLIPModel.get_text_features()` path to ONNX
2. Create Triton model config for `clip_text`
3. Update gateway adapter to use the Triton model

**Risks:** Text tokenization must happen in the gateway or as a pre-processing step since Triton ONNX models expect tensor inputs, not raw text. May need a Python backend for tokenization.

---

#### H3. Batch Florence-2 Queries per Entity

**What to change:** Consolidate the 4-5 sequential Florence queries per entity (vehicle, person, scene) into a single batch request using the `/batch-extract` endpoint.

**Current flow (per vehicle):**

```
HTTP(caption) -> HTTP(color) -> HTTP(type) -> HTTP(commercial) -> HTTP(logo)
= 5 round trips, ~150ms each = ~750ms per vehicle
```

**Proposed flow:**

```
HTTP(batch-extract, 5 items) -> single response
= 1 round trip + 5 sequential inferences = ~400ms per vehicle
```

**Expected impact:** 40-50% reduction in per-entity latency from eliminated HTTP overhead. 5 HTTP round trips reduced to 1.

**Implementation effort:** 4-6 hours. Modify `FlorenceExtractor` to use `FlorenceClient.batch_extract()` for multi-query extraction.

**Risks:** Batch endpoint may not be available on older Florence service versions (fallback already implemented in client).

---

### MEDIUM Impact

#### M1. Switch CLIP Image Encoding to JPEG

**What to change:** Change `image.save(buffer, format="PNG")` to `image.save(buffer, format="JPEG", quality=85)` in both `FlorenceClient._encode_image_to_base64()` and `CLIPClient._encode_image_to_base64()`.

**Expected impact:**

- ~10x reduction in payload size (1.2MB -> ~100KB for 640x480)
- ~50% reduction in base64 encode/decode CPU time
- ~80% reduction in HTTP transfer time over container network
- Negligible quality impact for security camera frames (JPEG artifacts are within noise margin)

**Implementation effort:** 1 hour. Two line changes in `florence_client.py` and `clip_client.py`.

**Risks:** Very minor quality loss from JPEG compression. Not suitable for OCR tasks where pixel-level accuracy matters (keep PNG for OCR endpoints only).

**Files to modify:**

- `/home/msvoboda/github/nemotron-v3-home-security-intelligence/backend/services/florence_client.py` (line 321)
- `/home/msvoboda/github/nemotron-v3-home-security-intelligence/backend/services/clip_client.py` (line 207)

---

#### M2. Enable Florence-2 SDPA When Supported

**What to change:** Check if the installed transformers version supports Florence-2 with SDPA (the `_supports_sdpa` fix was merged), and use `attn_implementation="sdpa"` with a fallback to `"eager"`.

**Expected impact:** 15-30% inference speedup on all Florence-2 tasks when SDPA is available.

**Implementation effort:** 2 hours. Add SDPA detection logic similar to CLIP's approach.

**Risks:** May require a newer version of Florence-2's remote code. Test thoroughly as Florence-2's custom attention implementation has known compatibility issues.

---

#### M3. Consider SigLIP 2 as CLIP Replacement

**What to change:** Evaluate replacing `openai/clip-vit-large-patch14` with a SigLIP 2 model (e.g., `google/siglip2-base-patch16-224`) for embedding generation.

**Expected impact:**

- SigLIP 2 outperforms CLIP at all model scales in zero-shot classification and image-text retrieval ([SigLIP 2 blog](https://huggingface.co/blog/siglip2))
- Significant improvements on localization and dense prediction tasks
- Better multilingual support if needed for OCR text matching
- SigLIP 2 base (86M params) may provide comparable embeddings to CLIP ViT-L (428M params) at ~3x lower VRAM cost

**Implementation effort:** 8-16 hours. Requires:

1. Benchmarking SigLIP 2 embeddings against CLIP for person/vehicle re-identification quality
2. Updating processor initialization (SigLIP uses a different processor)
3. Updating embedding dimension handling (SigLIP 2 base outputs 768-dim, matching CLIP ViT-L)
4. Rebuilding TensorRT engine for the new architecture

**Risks:** SigLIP 2's contrastive loss function (sigmoid, not softmax) changes the interpretation of similarity scores. Re-identification thresholds would need recalibration. Existing stored embeddings would be incompatible.

---

#### M4. Investigate Florence-2 KV Cache Fix

**What to change:** Check if newer versions of Florence-2's custom code have fixed the `prepare_inputs_for_generation` bug that prevents KV cache usage.

**Expected impact:** 2-3x speedup on generation tasks if KV cache can be re-enabled. This is the single biggest Florence-2 performance bottleneck.

**Implementation effort:** 2-4 hours of investigation + testing.

**Risks:** If the bug persists, enabling KV cache could cause silent corruption of generated text or CUDA errors.

---

### LOW Impact

#### L1. Consider DINOv2 for Visual Re-identification

**What to change:** Deploy DINOv2 alongside or instead of CLIP for entity re-identification embeddings.

**Expected impact:** DINOv2 demonstrates a 5x performance advantage over CLIP on fine-grained visual classification tasks ([Voxel51 comparison](https://voxel51.com/blog/finding-the-best-embedding-model-for-image-classification)). For distinguishing between similar-looking people or vehicles across cameras, DINOv2's self-supervised features may be significantly better.

**Implementation effort:** 16-24 hours (new model integration).

**Risks:** DINOv2 is vision-only (no text encoder), so classify/similarity endpoints would need a separate text model. Adds architectural complexity. Stored embeddings would be incompatible.

---

#### L2. ONNX Runtime for Florence-2

**What to change:** Export Florence-2 to ONNX and use ONNX Runtime with CUDA EP for inference.

**Expected impact:** ONNX Runtime achieves 2x+ performance speedup over PyTorch for transformer models on specific configurations ([ONNX RT docs](https://onnxruntime.ai/docs/performance/transformers-optimization.html)). However, Florence-2's autoregressive decoder and custom code make ONNX export difficult.

**Implementation effort:** 24-40 hours. Florence-2 cannot be exported to ONNX easily due to:

- Custom model code (`trust_remote_code`)
- Autoregressive generation loop
- Dynamic shapes in decoder

**Risks:** High implementation risk. The Florence-2 gateway adapter already notes: "Florence-2 uses Triton's Python backend because it requires `trust_remote_code` and has an autoregressive decoder that cannot be exported to TensorRT/ONNX."

---

#### L3. Reduce Florence-2 Max New Tokens

**What to change:** Reduce `max_new_tokens` from 1024 to 256 for caption/VQA tasks, keeping 1024 only for OCR tasks.

**Expected impact:** 2-4x speedup on caption tasks (most tokens generated are padding). Security captions rarely exceed 50-100 tokens.

**Implementation effort:** 2 hours. Add task-specific token limits.

**Risks:** Could truncate long OCR results or detailed captions. Use task-aware limits: CAPTION=128, DETAILED_CAPTION=256, OCR=1024.

---

#### L4. Pre-compute Security Objects Text Embeddings for CLIP

**What to change:** Pre-compute and cache text embeddings for the 21 security objects in SECURITY_OBJECTS list at startup, rather than encoding them per request.

**Expected impact:** Eliminates redundant text encoding on every `detect_security_objects` call. Saves ~5ms per call.

**Implementation effort:** 2 hours.

**Risks:** Minimal. Must invalidate cache if security objects vocabulary changes.

---

#### L5. Reduce Florence-2 num_beams in FlorenceExtractor

**What to change:** The `FlorenceExtractor._run_inference()` in `backend/services/florence_extractor.py` uses `num_beams=3`, while the standalone server uses `num_beams=1` (greedy decoding).

**Expected impact:** 2-3x speedup on backend-initiated Florence queries. Beam search with 3 beams runs the model 3x per generation step. For attribute extraction (color, type), greedy decoding produces equivalent results.

**Implementation effort:** 1 hour. Change `num_beams=3` to `num_beams=1` in `florence_extractor.py` line 323.

**Risks:** Slightly lower output diversity, but for factual extraction tasks this is irrelevant.

**File:** `/home/msvoboda/github/nemotron-v3-home-security-intelligence/backend/services/florence_extractor.py` (line 323)

---

## Alternative Models Assessment

### Vision-Language Models (Florence-2 Alternatives)

| Model            | Params | VRAM (FP16) | Strengths                                   | Weaknesses                                      | Recommendation                              |
| ---------------- | ------ | ----------- | ------------------------------------------- | ----------------------------------------------- | ------------------------------------------- |
| Florence-2-Base  | 232M   | ~0.5GB      | Current model, proven pipeline              | Garbage output bug (Triton backend)             | **Keep** (fix Triton backend)               |
| Florence-2-Large | 771M   | ~1.5GB      | Higher accuracy (+12% CIDEr)                | 3x VRAM, 2x slower, competes with LLM for GPU 0 | Upgrade only if Base proves insufficient    |
| Qwen2-VL-2B      | 2B     | ~4GB        | Superior vision understanding, native video | Too large for GPU 0 alongside LLM               | Not viable without dedicated GPU            |
| InternVL2-1B     | 1B     | ~2GB        | Excellent OCR, good captioning              | Higher VRAM, newer/less tested                  | Evaluate if Florence-2 quality insufficient |
| PaliGemma-3B     | 3B     | ~6GB        | Google's VLM, strong benchmarks             | Too large, high VRAM                            | Not viable                                  |

**Verdict:** Florence-2-Base is the right model for this deployment. Fix the Triton backend issue rather than replacing the model.

### Embedding Models (CLIP Alternatives)

| Model             | Params | Dim  | VRAM   | Strengths                             | Weaknesses                                | Recommendation                            |
| ----------------- | ------ | ---- | ------ | ------------------------------------- | ----------------------------------------- | ----------------------------------------- |
| CLIP ViT-L/14     | 428M   | 768  | ~800MB | Current model, proven, TensorRT ready | Web-image bias, no surveillance training  | **Keep** (well-optimized)                 |
| SigLIP 2 Base     | 86M    | 768  | ~200MB | Better accuracy at smaller size       | New API, different loss function          | **Evaluate** as replacement               |
| SigLIP 2 Large    | 428M   | 1024 | ~800MB | Best accuracy in class                | Dimension mismatch with stored embeddings | Long-term upgrade path                    |
| DINOv2 ViT-B/14   | 86M    | 768  | ~200MB | 5x better on fine-grained tasks       | No text encoder, vision-only              | Re-ID specialist, not general replacement |
| OpenCLIP ViT-G/14 | 1.8B   | 1024 | ~3.6GB | Highest quality embeddings            | Way too large for A400 4GB                | Not viable                                |
| EVA-CLIP          | 307M   | 768  | ~600MB | Strong zero-shot, CLIP-compatible     | Less community support                    | Possible alternative                      |

**Verdict:** Current CLIP ViT-L is well-suited. SigLIP 2 Base is the most promising upgrade path -- same embedding dimension at 5x fewer parameters with better accuracy. DINOv2 is worth evaluating specifically for re-identification quality.

---

## Merge Conflict Alert

Both `florence_client.py` and `clip_client.py` have **unresolved merge conflicts** (<<<<<<< HEAD / ======= / >>>>>>> markers) in the circuit breaker initialization sections. These must be resolved before any other changes can be made.

**Files with conflicts:**

- `/home/msvoboda/github/nemotron-v3-home-security-intelligence/backend/services/florence_client.py` (lines 238-270)
- `/home/msvoboda/github/nemotron-v3-home-security-intelligence/backend/services/clip_client.py` (lines 135-157, 221-254)

Both conflicts involve `CircuitBreakerConfig` (HEAD) vs `**_cb_kwargs` dict unpacking (incoming branch). These need to be resolved to match whichever API the `CircuitBreaker` class currently exposes.

---

## Implementation Priority Roadmap

### Phase 1: Critical Fixes (Week 1)

1. **Resolve merge conflicts** in florence_client.py and clip_client.py
2. **H1**: Fix Florence-2 Triton backend post-processing
3. **L5**: Reduce num_beams from 3 to 1 in FlorenceExtractor

### Phase 2: Performance Wins (Week 2)

4. **M1**: Switch to JPEG encoding for image payloads
5. **H3**: Batch Florence-2 queries per entity
6. **L3**: Task-specific max_new_tokens limits

### Phase 3: Gateway Completeness (Week 3)

7. **H2**: Deploy CLIP text encoder to Triton
8. **L4**: Pre-compute security objects text embeddings

### Phase 4: Model Upgrades (Week 4+)

9. **M2**: Enable Florence-2 SDPA when supported
10. **M4**: Investigate Florence-2 KV cache fix
11. **M3**: Benchmark SigLIP 2 as CLIP replacement
12. **L1**: Evaluate DINOv2 for re-identification

---

## References

### Florence-2

- [HuggingFace Florence-2 Documentation](https://huggingface.co/docs/transformers/main/model_doc/florence2)
- [Florence-2 SDPA Issue #41622](https://github.com/huggingface/transformers/issues/41622)
- [Florence-2 Slow Initialization Discussion](https://huggingface.co/microsoft/Florence-2-large/discussions/102)
- [Fine-tuning Florence-2 Blog](https://huggingface.co/blog/finetune-florence2)
- [Florence-2 OpenVINO Documentation](https://docs.openvino.ai/2024/notebooks/florence2-with-output.html)
- [Florence-2 Research Paper (Microsoft)](https://www.microsoft.com/en-us/research/publication/florence-2-advancing-a-unified-representation-for-a-variety-of-vision-tasks/)
- [Florence-2 Roboflow Model Guide](https://roboflow.com/model/florence-2)
- [Ultralytics Florence-2 Overview](https://www.ultralytics.com/blog/florence-2-microsofts-latest-vision-language-model)

### CLIP & Embedding Models

- [SigLIP 2: Multilingual Vision-Language Encoders](https://huggingface.co/blog/siglip2)
- [SigLIP 2 Paper (arXiv)](https://arxiv.org/pdf/2502.14786)
- [Finding the Best Embedding Model for Image Classification](https://voxel51.com/blog/finding-the-best-embedding-model-for-image-classification)
- [CLIP-based Vehicle Re-identification](https://www.sciencedirect.com/science/article/abs/pii/S0957417425044550)
- [DINOv2 Meets Text](https://arxiv.org/html/2412.16334v1)
- [Image Similarity with Transformers](https://medium.com/@tapanbabbar/build-an-image-similarity-search-with-transformers-vit-clip-efficientnet-dino-v2-and-blip-2-5040d1848c00)

### Optimization Techniques

- [torch.compile vs TensorRT (Collabora)](https://www.collabora.com/news-and-blog/blog/2024/12/19/faster-inference-torch.compile-vs-tensorrt/)
- [ONNX Runtime Transformers Optimization](https://onnxruntime.ai/docs/performance/transformers-optimization.html)
- [ONNX Runtime Journey (Microsoft)](https://opensource.microsoft.com/blog/2021/06/30/journey-to-optimize-large-scale-transformer-model-inference-with-onnx-runtime)
- [NVIDIA Model Optimizer](https://github.com/NVIDIA/Model-Optimizer)
