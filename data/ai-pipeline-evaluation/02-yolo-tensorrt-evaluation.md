# YOLO26 + TensorRT Optimization Evaluation

**Date:** 2026-02-08
**Evaluator:** AI Pipeline Research Agent
**Scope:** YOLO26m object detection with TensorRT acceleration on NVIDIA A400 (4GB VRAM)

---

## Executive Summary

The current YOLO26m + TensorRT FP16 setup is architecturally sound and already leverages several best practices (TensorRT acceleration, NMS-free decoder, class-specific thresholds, auto-rebuild on version mismatch). However, there are **7 high-impact and 5 medium-impact optimizations** that can improve throughput by 20-60%, reduce VRAM usage, fix the known vehicle detection threshold issue, and modernize the container base image.

The most impactful changes are:

1. **INT8 quantization** -- YOLO26's architecture is specifically designed for quantization robustness, making INT8 a near-free performance win (~20% latency reduction, 50% model size reduction)
2. **Lowering vehicle thresholds** from 0.70 to 0.55-0.60 -- the current thresholds are too aggressive and miss legitimate vehicle detections
3. **Upgrading the TensorRT base image** from 26.01 to 25.12+ -- gains from TensorRT 10.14.x optimizations
4. **Dynamic batch inference** for multi-camera frame processing -- currently batch detection is sequential, not truly batched at the GPU level
5. **Reducing workspace size** from 4GB to 2GB -- the A400 only has 4GB total; a 4GB workspace competes with the model itself

**Key architectural advantage already in place:** YOLO26's NMS-free decoder eliminates a major post-processing bottleneck and simplifies TensorRT deployment. This is a significant win over YOLOv8/v11 that the project is already benefiting from.

---

## Current Configuration Analysis

### Hardware

| Component          | Value              | Notes                                                   |
| ------------------ | ------------------ | ------------------------------------------------------- |
| GPU                | NVIDIA RTX A400    | 4GB GDDR6, Ampere architecture                          |
| Compute Capability | sm_86 (Ampere)     | NOT sm_75/Turing as noted in `build_engine.py` comments |
| CUDA Cores         | 768                |                                                         |
| Tensor Cores       | 24 (3rd gen)       | Full INT8/FP16 support                                  |
| VRAM               | 4GB GDDR6          | Tight constraint; model + workspace must fit            |
| Container CPU      | 2 cores            | Via docker-compose resource limits                      |
| Container Memory   | 4GB (2GB reserved) | Matching GPU VRAM                                       |

**Critical finding:** The `build_engine.py` comment lists "sm_75: RTX 2080 / T4 / A400" -- this is incorrect. The RTX A400 is an **Ampere GPU (sm_86)**, not Turing (sm_75). The T4 is indeed sm_75. This mismatch in documentation could cause confusion but does not affect runtime behavior since compute capability is auto-detected.

### Software Stack

| Component   | Current                             | Latest Available                                          | Gap                                                                |
| ----------- | ----------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------ |
| Base Image  | `nvcr.io/nvidia/tensorrt:26.01-py3` | `nvcr.io/nvidia/tensorrt:25.12-py3` (calendar versioning) | The `26.01` tag maps to the January 2026 release. This is current. |
| TensorRT    | 10.14.x (bundled)                   | 10.14.1.48                                                | Current                                                            |
| Ultralytics | >=8.4.0                             | 8.4.x+ (YOLO26 support)                                   | Current                                                            |
| PyTorch     | >=2.0.0                             | 2.x (bundled in NGC)                                      | Current                                                            |

**Analysis:** The base image `tensorrt:26.01-py3` is the January 2026 NGC container release, which is **current**. The labels in the Dockerfile reference `24.09-py3` in the `org.opencontainers.image.base.name` and `base.digest` labels, which are stale/incorrect -- these should be updated to `26.01-py3`.

### Model Configuration

| Setting            | Value                                               | Assessment                                                      |
| ------------------ | --------------------------------------------------- | --------------------------------------------------------------- |
| Model              | YOLO26m                                             | Good choice for security (medium model balances speed/accuracy) |
| Precision          | FP16                                                | Suboptimal -- INT8 is viable and recommended                    |
| Image Size         | 640x640                                             | Standard, appropriate                                           |
| Workspace          | 4GB                                                 | Too large for 4GB GPU -- competes with model                    |
| Dynamic Batch      | False (build_engine.py) / True (export_tensorrt.py) | Inconsistent across scripts                                     |
| Global Confidence  | 0.50                                                | Reasonable                                                      |
| Vehicle Thresholds | 0.70                                                | **Too aggressive** -- known issue                               |
| Person Threshold   | 0.45                                                | Good -- favors recall                                           |
| Batch Processing   | Sequential per-image                                | Not truly batched at GPU level                                  |
| CUDA Cache Clear   | Every detection                                     | Aggressive; may hurt throughput                                 |
| Warmup             | 3 iterations                                        | Adequate                                                        |

### NMS Configuration

YOLO26 is **NMS-free by design**, using an end-to-end decoder that produces final predictions directly. This is a major advantage:

- Eliminates NMS post-processing latency (typically 1-5ms saved)
- Simplifies TensorRT export (no custom NMS plugin needed)
- Better quantization compatibility (no NMS operations to handle)

The codebase still processes boxes from `result.boxes` but YOLO26 boxes are already deduplicated by the model's native decoder.

---

## Recommended Optimizations

### 1. INT8 Quantization [HIGH IMPACT]

**What to change:** Switch from FP16 to INT8 TensorRT engine.

**Current state:** The `export_tensorrt.py` script already supports INT8 export with calibration data, but production uses FP16 (`yolo26m_fp16.engine`).

**Expected impact:**

- **~20% latency reduction** (INT8 inference is faster on Ampere Tensor Cores)
- **~50% model size reduction** (smaller engine file, less VRAM)
- **~2x theoretical throughput** improvement (INT8 Tensor Core ops are 2x faster than FP16)
- Minimal accuracy loss -- YOLO26 was specifically designed for quantization robustness: "INT8 exports of YOLO26 retain nearly the same mAP as FP32 versions" (Ultralytics documentation)

**Why this works well on A400:**

- RTX A400 has 3rd-gen Tensor Cores with native INT8 support
- With only 4GB VRAM, reducing model memory footprint is critical
- YOLO26's removal of DFL and NMS-free decoder means no custom ops that are hard to quantize

**Implementation effort:** MEDIUM

- Calibration dataset needed (200-500 representative security camera images)
- The `export_tensorrt.py` script already handles INT8 export
- Use `--extract-frames` flag to build calibration set from recorded video
- Need calibration YAML config file

**Risks:**

- Marginal accuracy loss (typically <1% mAP for YOLO26 INT8 vs FP16)
- Calibration data must be representative of actual deployment conditions (lighting, camera angles)
- One-time calibration process takes longer than FP16 export

**Implementation steps:**

```bash
# 1. Create calibration dataset from security camera recordings
python export_tensorrt.py --int8 \
  --data config/yolo26_calibration.yaml \
  --extract-frames \
  --model /export/ai_models/model-zoo/yolo26/yolo26m.pt \
  --output /export/ai_models/model-zoo/yolo26/exports/

# 2. Benchmark INT8 vs FP16
python export_tensorrt.py --benchmark /export/ai_models/model-zoo/yolo26/exports/yolo26m_int8.engine

# 3. Validate accuracy
python export_tensorrt.py --validate /export/ai_models/model-zoo/yolo26/exports/yolo26m_int8.engine \
  --data config/yolo26_calibration.yaml
```

**References:**

- [Ultralytics TensorRT Export](https://docs.ultralytics.com/integrations/tensorrt/)
- [Ultralytics Model Quantization](https://www.ultralytics.com/glossary/model-quantization)
- [YOLO26 Architecture Paper](https://arxiv.org/html/2509.25164v3)

---

### 2. Lower Vehicle Detection Thresholds [HIGH IMPACT]

**What to change:** Reduce car/truck/bus thresholds from 0.70 to 0.55-0.60.

**Current state:**

```python
_DEFAULT_CLASS_CONFIDENCE_THRESHOLDS = {
    "car": 0.70,      # Too aggressive
    "truck": 0.70,    # Too aggressive
    "bus": 0.70,      # Too aggressive
    ...
}
```

**Expected impact:**

- **Significantly improved vehicle detection recall** -- currently missing legitimate vehicles at 0.70
- This is a **known issue** flagged in the AI pipeline remediation session
- The enrichment pipeline already filters false positives downstream, so lower thresholds are safe

**Recommended thresholds:**

```python
_DEFAULT_CLASS_CONFIDENCE_THRESHOLDS = {
    "person": 0.45,       # Keep -- good recall-oriented threshold
    "car": 0.55,          # Lowered from 0.70 -- catch more real vehicles
    "truck": 0.55,        # Lowered from 0.70
    "bus": 0.55,          # Lowered from 0.70
    "motorcycle": 0.55,   # Lowered from 0.65
    "bicycle": 0.55,      # Lowered from 0.65
    "dog": 0.50,          # Slightly lowered for better pet detection
    "cat": 0.50,          # Slightly lowered for better pet detection
    "bird": 0.50,         # Slightly lowered
}
```

**Implementation effort:** LOW -- single config change, can also be done via `YOLO26_CLASS_THRESHOLDS` env var without code change.

**Risks:**

- More false positives for vehicles (shadows, reflections), but the enrichment pipeline handles these
- Can be tuned incrementally via the `YOLO26_CLASS_THRESHOLDS` environment variable

**Quick fix via environment variable:**

```bash
YOLO26_CLASS_THRESHOLDS='{"car": 0.55, "truck": 0.55, "bus": 0.55, "motorcycle": 0.55, "bicycle": 0.55}'
```

---

### 3. Reduce TensorRT Workspace Size [HIGH IMPACT]

**What to change:** Reduce workspace from 4GB to 2GB in both `build_engine.py` and `rebuild_tensorrt_engine()`.

**Current state:** Both `build_engine.py` (line 67: `workspace: int = 4`) and `rebuild_tensorrt_engine()` (line 506: `workspace=4`) use 4GB workspace.

**Expected impact:**

- **Prevents potential OOM during engine build** -- 4GB workspace on a 4GB GPU leaves no room for the model, CUDA context, or framework overhead
- The TensorRT workspace is temporary memory used during engine optimization; it does not need to match total VRAM
- For a YOLO26m model (~5MB engine), 2GB workspace is more than sufficient

**Implementation effort:** LOW -- change `workspace=4` to `workspace=2` in two locations.

**Risks:**

- Theoretically could miss some optimization opportunities, but for YOLO-sized models, 2GB is ample
- TensorRT workspace is only used during engine building, not inference

**References:**

- [TensorRT Best Practices - Workspace Size](https://docs.nvidia.com/deeplearning/tensorrt/latest/performance/best-practices.html)

---

### 4. True Batch Inference for Multi-Camera Processing [HIGH IMPACT]

**What to change:** Implement GPU-level batch inference instead of sequential per-image processing.

**Current state:** `detect_batch()` in `model.py` (line 1440-1481) calls `self.detect(image)` sequentially in a loop. This means each image goes through the full inference pipeline separately -- no GPU parallelism.

**Expected impact:**

- **2-4x throughput improvement** when processing multiple camera frames
- Better GPU utilization (batch execution saturates Tensor Cores)
- Reduced per-frame overhead (single kernel launch for N frames)

**Implementation approach:**

```python
def detect_batch(self, images: list[Image.Image]) -> tuple[list[list[dict]], float]:
    """True batch inference using Ultralytics batch prediction."""
    start_time = time.perf_counter()

    # Preprocess all images
    rgb_images = [img.convert("RGB") if img.mode != "RGB" else img for img in images]

    # Single batch inference call
    results = self.model.predict(
        source=rgb_images,
        conf=self.confidence_threshold,
        verbose=False,
        device=self.device,
    )

    # Process results per image
    all_detections = []
    for result in results:
        detections = self._process_result(result)
        all_detections.append(detections)

    total_time_ms = (time.perf_counter() - start_time) * 1000
    return all_detections, total_time_ms
```

**Prerequisites:**

- TensorRT engine must be built with `dynamic=True` for variable batch sizes
- Current `build_engine.py` uses `dynamic=False` -- this must change
- Need to verify A400 VRAM can handle batch size > 1 with YOLO26m

**Implementation effort:** MEDIUM -- requires engine rebuild with dynamic shapes and code changes to `detect_batch()`.

**Risks:**

- VRAM pressure with larger batch sizes on 4GB GPU -- need to test batch size 2 and 4
- Dynamic shape engines may have slightly higher per-frame latency (optimization profiles less specialized)
- Requires rebuilding TensorRT engine

**References:**

- [Ultralytics Dynamic Batching Issue](https://github.com/ultralytics/ultralytics/issues/20662)
- [TensorRT Dynamic Batching](https://forums.developer.nvidia.com/t/tensorrt-use-dynamic-batch-or-specified-batch/232835)

---

### 5. Enable Dynamic Shapes with Optimization Profiles [HIGH IMPACT]

**What to change:** Build TensorRT engine with explicit batch mode and optimization profiles.

**Current state:**

- `build_engine.py` uses `dynamic=False`
- `export_tensorrt.py` uses `dynamic=True`
- There is no optimization profile configuration
- TensorRT 10.x has deprecated implicit batch mode; explicit batch is the default

**Expected impact:**

- Required prerequisite for true batch inference (Recommendation #4)
- Optimization profiles allow TensorRT to optimize for common batch sizes (1, 2, 4)
- Better handling of variable-size camera input

**Recommended optimization profile:**

```python
# When building via Ultralytics export:
model.export(
    format="engine",
    imgsz=640,
    half=True,        # or int8=True
    dynamic=True,     # Enable dynamic shapes
    batch=4,          # Max batch size
    workspace=2,      # Reduced for A400
    simplify=True,
)
```

**Implementation effort:** LOW-MEDIUM -- change export parameters, rebuild engine.

**Risks:**

- Dynamic engines are ~5-10% slower for single-image inference than static engines
- Must ensure max batch size fits in VRAM

**References:**

- [TensorRT Explicit Batch Mode](https://docs.nvidia.com/deeplearning/tensorrt/latest/performance/best-practices.html)

---

### 6. Reduce CUDA Cache Clear Frequency [HIGH IMPACT]

**What to change:** Change `YOLO26_CACHE_CLEAR_FREQUENCY` from 1 (every detection) to 10-50.

**Current state:** `torch.cuda.empty_cache()` is called after **every single detection** (line 1337-1340). This is extremely aggressive.

**Expected impact:**

- **5-15% throughput improvement** -- `empty_cache()` is not free; it synchronizes the GPU and returns all cached memory to the CUDA allocator
- Reduced GPU synchronization overhead
- The A400 has only 4GB, so some cache management is needed, but every-detection is excessive

**Why current setting is problematic:**

- `torch.cuda.empty_cache()` forces a device synchronization, which blocks the CPU until all GPU operations complete
- For a small model like YOLO26m (~5MB engine, ~500MB inference), VRAM fragmentation is minimal
- The pre-inference memory guard at line 1366-1371 already handles low-memory situations

**Recommended setting:**

```bash
YOLO26_CACHE_CLEAR_FREQUENCY=20  # Clear every 20 detections
```

**Implementation effort:** LOW -- environment variable change only.

**Risks:**

- Slightly higher peak VRAM usage between cache clears
- Monitor for OOM errors; adjust frequency if needed

---

### 7. Upgrade Dockerfile Labels [HIGH IMPACT - Correctness]

**What to change:** Fix stale OCI labels in the Dockerfile.

**Current state (lines 26-27):**

```dockerfile
LABEL org.opencontainers.image.base.name="nvcr.io/nvidia/tensorrt:24.09-py3"
LABEL org.opencontainers.image.base.digest="nvcr.io/nvidia/tensorrt:24.09-py3"
```

**Actual base image (line 16):**

```dockerfile
FROM nvcr.io/nvidia/tensorrt:26.01-py3 AS tensorrt_base
```

**Expected impact:** Correctness only -- prevents confusion about which TensorRT version is actually in use.

**Implementation effort:** TRIVIAL

**Risks:** None

---

### 8. Fix build_engine.py GPU Architecture Documentation [MEDIUM IMPACT]

**What to change:** Correct the compute capability mapping in `build_engine.py` comments.

**Current (incorrect):**

```
- sm_75: RTX 2080 / T4 / A400
- sm_86: RTX 3090 / A5500
```

**Correct:**

```
- sm_75: RTX 2080 / T4
- sm_86: RTX 3090 / A5500 / RTX A400
```

The RTX A400 is an **Ampere** GPU (sm_86), not Turing (sm_75). This is important because:

- sm_86 has 3rd-gen Tensor Cores with INT8 support
- sm_75 has 2nd-gen Tensor Cores with more limited INT8 support
- Engine built for sm_75 will not be optimal on sm_86

**Implementation effort:** TRIVIAL

**Risks:** None

**References:**

- [NVIDIA CUDA GPU Compute Capabilities](https://developer.nvidia.com/cuda/gpus)
- [RTX A400 Specifications](https://www.nvidia.com/en-us/products/workstations/rtx-a400/)

---

### 9. Consider NVIDIA DeepStream for Multi-Camera Pipeline [MEDIUM IMPACT]

**What to change:** Evaluate NVIDIA DeepStream SDK for multi-camera stream processing.

**Current state:** The backend sends individual images to the YOLO26 HTTP endpoint. Each camera frame is processed as an independent HTTP request.

**Expected impact:**

- DeepStream handles hardware-accelerated decode, batch inference, and tracking natively
- Zero-copy GPU processing (frames stay on GPU from decode through inference)
- Built-in multi-stream batching (multiple camera feeds processed in a single inference call)
- Up to **5-10x throughput improvement** for multi-camera deployments

**However, this is a major architectural change:**

- Requires replacing the current HTTP-based inference API
- DeepStream has a steep learning curve
- The current simple HTTP architecture is easier to maintain and debug
- A400 may not support DeepStream features well (designed for Jetson/T4/A100)

**Implementation effort:** HIGH -- major architecture change.

**Risks:**

- Complete API redesign needed
- DeepStream adds significant complexity
- May not be well-supported on desktop Ampere GPUs
- Current architecture is simpler and easier to maintain

**Recommendation:** Consider for future scaling if camera count exceeds 8-10. For current deployment, the HTTP-based approach with true batch inference (Recommendation #4) is more appropriate.

**References:**

- [DeepStream SDK](https://developer.nvidia.com/deepstream-sdk)
- [Ultralytics YOLO26 on DeepStream](https://docs.ultralytics.com/guides/deepstream-nvidia-jetson/)

---

### 10. ONNX Runtime with TensorRT EP as Alternative [MEDIUM IMPACT]

**What to change:** Evaluate ONNX Runtime with TensorRT execution provider as an alternative to native TensorRT.

**Current state:** Native TensorRT via Ultralytics export.

**Expected impact:**

- ONNX Runtime provides automatic fallback to CUDA EP for unsupported operations
- Easier model versioning and portability
- However, **native TensorRT generally provides better performance** for fully-supported models

**Analysis:**
For YOLO26, which is a well-supported model architecture, native TensorRT (as currently used) is the better choice:

- All YOLO26 operations are supported by TensorRT
- No fallback to CUDA EP needed
- Native TensorRT gives better optimization (whole-graph optimization vs subgraph)
- The Ultralytics export pipeline handles the complexity

**Recommendation:** **Keep native TensorRT.** ONNX Runtime + TensorRT EP is better suited for models with custom ops that TensorRT doesn't support. YOLO26 is fully TensorRT-compatible.

**Implementation effort:** MEDIUM (if pursued)

**Risks:**

- Potential performance regression vs native TensorRT
- Additional dependency

**References:**

- [ONNX Runtime TensorRT EP](https://onnxruntime.ai/docs/execution-providers/TensorRT-ExecutionProvider.html)
- [NVIDIA TensorRT vs ONNX Runtime Comparison](https://github.com/microsoft/onnxruntime/issues/12083)

---

### 11. Temporal Confidence Filtering [MEDIUM IMPACT]

**What to change:** Implement multi-frame consistency for marginal detections.

**Current state:** There is a TODO in `model.py` (lines 215-220) for temporal confidence filtering:

```python
# TODO(NEM-future): Temporal confidence filtering / multi-frame consistency.
# For MARGINAL-tier detections (confidence < 0.60), require confirmation across
# N consecutive frames before accepting.
```

**Expected impact:**

- Reduces false positives for marginal detections without lowering recall
- Particularly effective for vehicle shadows/reflections that don't persist across frames
- Enables lower per-frame thresholds (more recall) while maintaining precision through temporal consistency

**Implementation effort:** MEDIUM -- requires frame-level tracking state per camera.

**Risks:**

- Adds latency (must wait for N frames)
- Increases memory usage (tracking state per camera)
- May miss fast-moving objects that only appear in 1-2 frames

---

### 12. Explore YOLO26 Model Size Variants [MEDIUM IMPACT]

**What to change:** Evaluate whether YOLO26n (nano) or YOLO26s (small) would be sufficient.

**Current state:** YOLO26m (medium, ~5MB TensorRT engine, ~2GB VRAM inference).

**Performance comparison (from YOLO26 benchmarks):**

| Model   | mAP@50 | Latency | Parameters | VRAM   |
| ------- | ------ | ------- | ---------- | ------ |
| YOLO26n | ~39.5% | Fastest | Smallest   | ~0.5GB |
| YOLO26s | ~47%   | Fast    | Small      | ~1GB   |
| YOLO26m | ~53%   | Medium  | Medium     | ~2GB   |
| YOLO26l | ~55%   | Slower  | Large      | ~3GB   |

**Analysis for 4GB A400:**

- YOLO26m uses ~2GB of 4GB -- leaving only 2GB for CUDA context, workspace, and overhead
- YOLO26s would use ~1GB, leaving 3GB -- much more headroom
- For security monitoring, the 9-class filtered subset means the full COCO mAP difference is less impactful
- YOLO26n provides **43% faster CPU inference** than YOLO11n

**Recommendation:** Test YOLO26s as a potential improvement -- the VRAM savings would enable larger batch sizes (Recommendation #4) and more aggressive caching.

**Implementation effort:** LOW -- just swap the model file.

**Risks:**

- Lower mAP may miss small objects or low-contrast detections
- Need validation on actual security camera footage before switching

---

## Summary Table

| #   | Optimization                 | Impact                          | Effort     | Risk                         | Priority |
| --- | ---------------------------- | ------------------------------- | ---------- | ---------------------------- | -------- |
| 1   | INT8 Quantization            | HIGH (~20% faster, 50% smaller) | MEDIUM     | LOW (YOLO26 designed for it) | P0       |
| 2   | Lower Vehicle Thresholds     | HIGH (fixes known bug)          | LOW        | LOW (enrichment filters FPs) | P0       |
| 3   | Reduce Workspace to 2GB      | HIGH (prevents OOM on build)    | LOW        | VERY LOW                     | P0       |
| 4   | True Batch Inference         | HIGH (2-4x throughput)          | MEDIUM     | MEDIUM (VRAM pressure)       | P1       |
| 5   | Dynamic Shapes / Profiles    | HIGH (enables batching)         | LOW-MEDIUM | LOW                          | P1       |
| 6   | Reduce Cache Clear Frequency | HIGH (5-15% throughput)         | LOW        | LOW                          | P0       |
| 7   | Fix Dockerfile Labels        | HIGH (correctness)              | TRIVIAL    | NONE                         | P0       |
| 8   | Fix GPU Architecture Docs    | MEDIUM (correctness)            | TRIVIAL    | NONE                         | P0       |
| 9   | DeepStream Multi-Camera      | MEDIUM (5-10x throughput)       | HIGH       | HIGH (architecture change)   | P3       |
| 10  | ONNX Runtime + TensorRT EP   | MEDIUM                          | MEDIUM     | MEDIUM (regression risk)     | SKIP     |
| 11  | Temporal Confidence Filter   | MEDIUM (fewer FPs)              | MEDIUM     | LOW                          | P2       |
| 12  | YOLO26s Model Variant        | MEDIUM (VRAM savings)           | LOW        | MEDIUM (accuracy)            | P2       |

---

## Answers to Specific Questions

### 1. FP16 vs INT8 -- What speedup can INT8 give on A400?

INT8 on the RTX A400 (Ampere sm_86) can provide:

- **~20% latency reduction** per inference
- **~50% model size reduction**
- **~2x theoretical Tensor Core throughput** (INT8 ops are 2x faster than FP16 on 3rd-gen Tensor Cores)
- YOLO26 specifically designed for quantization robustness -- "nearly the same mAP as FP32"

The A400 has 24 third-generation Tensor Cores with native INT8 support. This is the single highest-impact optimization available.

### 2. Dynamic batching for multiple camera frames?

**Yes, but not currently implemented.** The `detect_batch()` method processes images sequentially. True batch inference requires:

- TensorRT engine built with `dynamic=True`
- Using `model.predict(source=[img1, img2, ...])` instead of per-image calls
- Careful VRAM management on 4GB GPU (batch size 2-4 recommended)

### 3. Optimal NMS configuration for security cameras?

**Not applicable.** YOLO26 is NMS-free by design -- it uses an end-to-end decoder that produces final predictions without NMS. This is a significant architectural advantage that the project is already benefiting from. No NMS tuning needed.

### 4. Explicit batch mode vs implicit batch mode?

**Explicit batch is required.** TensorRT 10.x has deprecated implicit batch mode. The Ultralytics export uses explicit batch by default. No action needed -- the current approach is correct.

### 5. Newer YOLO variants for security scenarios?

YOLO26 **is the newest** (released September 2025). It outperforms YOLO11 and YOLOv8 on the accuracy-vs-latency Pareto front. Key advantages for security:

- NMS-free decoder (simpler, faster, better TensorRT compatibility)
- Quantization robustness (designed for INT8 deployment)
- Small-Target-Aware Label Assignment (STAL) -- important for distant security camera subjects
- 43% faster CPU inference than YOLO11n

**No upgrade needed** -- YOLO26 is the best available option.

### 6. Multi-stream inference?

Currently not possible with the HTTP-based architecture. Two paths:

- **Short term:** True batch inference via Ultralytics (Recommendation #4) -- batch frames from multiple cameras
- **Long term:** NVIDIA DeepStream for native multi-stream pipelines (Recommendation #9) -- major architectural change

### 7. Is `nvcr.io/nvidia/tensorrt:26.01-py3` the latest?

**Yes.** The `26.01` tag is the January 2026 NGC release, containing TensorRT 10.14.x. This is current. The Dockerfile OCI labels referencing `24.09-py3` are stale and should be updated.

### 8. TensorRT builder optimizations?

Key recommendations:

- **Workspace size:** Reduce from 4GB to 2GB (Recommendation #3) -- A400 cannot support 4GB workspace + model
- **Precision:** Switch to INT8 (Recommendation #1)
- **Simplify:** Already enabled (`simplify=True`) -- good
- **Dynamic shapes:** Enable for batch inference (Recommendation #5)

### 9. Optimal model size/precision for 4GB GPU?

| Combination  | VRAM Usage | Feasibility                                |
| ------------ | ---------- | ------------------------------------------ |
| YOLO26m FP16 | ~2GB       | Current, works well                        |
| YOLO26m INT8 | ~1.2GB     | **Recommended** -- frees VRAM for batching |
| YOLO26s INT8 | ~0.6GB     | Best for multi-batch processing            |
| YOLO26l FP16 | ~3GB       | Too tight for 4GB GPU                      |

**Recommendation:** YOLO26m INT8 is the sweet spot -- strong accuracy with significant VRAM savings. If batch inference is critical, consider YOLO26s INT8.

### 10. ONNX Runtime + TensorRT EP vs native TensorRT?

**Keep native TensorRT.** YOLO26 is fully supported by TensorRT with no unsupported operations. Native TensorRT provides better whole-graph optimization. ONNX Runtime + TensorRT EP adds unnecessary complexity and potential performance regression for this use case.

---

## Implementation Roadmap

### Phase 1: Quick Wins (1-2 hours)

- [ ] Fix vehicle thresholds via `YOLO26_CLASS_THRESHOLDS` env var
- [ ] Reduce CUDA cache clear frequency to 20
- [ ] Fix Dockerfile OCI labels
- [ ] Fix `build_engine.py` GPU architecture documentation

### Phase 2: INT8 Quantization (4-8 hours)

- [ ] Create calibration dataset from security camera recordings
- [ ] Build INT8 TensorRT engine
- [ ] Benchmark INT8 vs FP16 (latency, throughput, accuracy)
- [ ] Deploy INT8 engine if accuracy is acceptable

### Phase 3: Batch Inference (8-16 hours)

- [ ] Rebuild TensorRT engine with `dynamic=True`, `batch=4`, `workspace=2`
- [ ] Refactor `detect_batch()` for true GPU-batched inference
- [ ] Test with 2-4 camera frames batched
- [ ] Monitor VRAM usage under batch load

### Phase 4: Advanced Optimizations (future)

- [ ] Implement temporal confidence filtering
- [ ] Evaluate YOLO26s for VRAM savings
- [ ] Consider DeepStream for high camera count deployments

---

## Sources

- [Ultralytics TensorRT Export Documentation](https://docs.ultralytics.com/integrations/tensorrt/)
- [Ultralytics Model Quantization](https://www.ultralytics.com/glossary/model-quantization)
- [YOLO26 Architecture Paper](https://arxiv.org/html/2509.25164v3)
- [YOLO26 NMS-Free Analysis](https://arxiv.org/html/2601.12882v1)
- [Ultralytics YOLO Evolution Overview](https://arxiv.org/html/2510.09653v1)
- [NVIDIA TensorRT Best Practices](https://docs.nvidia.com/deeplearning/tensorrt/latest/performance/best-practices.html)
- [NVIDIA TensorRT Container Release Notes](https://docs.nvidia.com/deeplearning/frameworks/container-release-notes/index.html)
- [NVIDIA RTX A400 Specifications](https://www.nvidia.com/en-us/products/workstations/rtx-a400/)
- [NVIDIA CUDA GPU Compute Capabilities](https://developer.nvidia.com/cuda/gpus)
- [RTX A400 Datasheet (Lenovo)](https://lenovopress.lenovo.com/lp2171-thinksystem-nvidia-rtx-a400-4gb-pcie-gen4-active-gpu)
- [YOLO11 vs YOLOv8 Comparison](https://docs.ultralytics.com/compare/yolo11-vs-yolov8/)
- [Ultralytics YOLO Model Comparisons](https://docs.ultralytics.com/compare/)
- [NVIDIA DeepStream SDK](https://developer.nvidia.com/deepstream-sdk)
- [Ultralytics YOLO26 on DeepStream](https://docs.ultralytics.com/guides/deepstream-nvidia-jetson/)
- [ONNX Runtime TensorRT Execution Provider](https://onnxruntime.ai/docs/execution-providers/TensorRT-ExecutionProvider.html)
- [Ultralytics Dynamic Batching Discussion](https://github.com/ultralytics/ultralytics/issues/20662)
- [Integrating Ultralytics YOLO with TensorRT](https://www.ultralytics.com/blog/optimizing-ultralytics-yolo-models-with-the-tensorrt-integration)
- [TensorRT Dynamic vs Specified Batch](https://forums.developer.nvidia.com/t/tensorrt-use-dynamic-batch-or-specified-batch/232835)
- [YOLO26 Roboflow Analysis](https://blog.roboflow.com/yolo26/)
- [YOLO26 LearnOpenCV](https://learnopencv.com/yolov26-real-time-deployment/)
