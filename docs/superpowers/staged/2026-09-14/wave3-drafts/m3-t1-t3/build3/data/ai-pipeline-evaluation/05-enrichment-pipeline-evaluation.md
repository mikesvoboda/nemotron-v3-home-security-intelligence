# Enrichment Pipeline Evaluation Report

**Date:** 2026-02-08
**Scope:** Heavy (GPU 0 / A5500) and Light (GPU 1 / A400 4GB) enrichment services
**Models evaluated:** 10 enrichment models across 2 containers
**Research sources:** Context7 library resolution, Ultralytics docs, NVIDIA Triton docs, ONNX Runtime docs, Depth Anything V2/V3, ReIDMamba, X-CLIP alternatives

---

## Executive Summary

The enrichment pipeline currently runs 10 specialized models across two GPU-pinned containers (heavy on GPU 0 shared with the LLM, light on GPU 1 with 4GB VRAM). The architecture is sound but leaves significant performance on the table. The highest-impact optimizations are:

1. **Migrate all Triton-compatible models to ONNX + TensorRT via the existing Triton infrastructure** (Phase 2 of the already-planned Triton migration) -- this alone would reduce VRAM by ~40% and improve throughput by 2-5x for models that currently run raw PyTorch.
2. **Replace Depth Anything V2 Small with V2 Vits (the Tiny encoder)** -- 3x faster inference with negligible quality loss for security depth estimation use cases.
3. **Adopt INT8 quantization for Vehicle ResNet-50 and Demographics ViT** -- the quantize_models.py script already exists but is not deployed; running it would free ~1GB VRAM on the heavy service.
4. **Evaluate ReIDMamba as an OSNet replacement** -- 1/3 the parameters of TransReID with state-of-the-art accuracy, and its Mamba architecture aligns with the project's existing Nemotron hybrid Mamba-Transformer stack.
5. **Enable pipeline parallelism** within each enrichment container -- run independent models concurrently on the same frame rather than sequentially.

**Estimated aggregate impact:** 35-50% VRAM reduction, 2-4x throughput improvement, with manageable implementation effort because much of the infrastructure (Triton model repository, TensorRT export scripts, quantization scripts) already exists.

---

## Current Configuration Analysis

### Heavy Enrichment Service (ai-enrichment, port 8094, GPU 0 / A5500 24GB)

| Model                       | Architecture                  | VRAM          | Priority | Runtime              | Preloaded     |
| --------------------------- | ----------------------------- | ------------- | -------- | -------------------- | ------------- |
| Vehicle Segment Classifier  | ResNet-50                     | ~1,500 MB     | MEDIUM   | PyTorch              | Yes (default) |
| FashionSigLIP (clothing)    | SigLIP ViT                    | ~800 MB       | MEDIUM   | open_clip/PyTorch    | Yes (default) |
| Demographics (age)          | ViT                           | ~250 MB       | HIGH     | transformers/PyTorch | No            |
| Demographics (gender)       | ViT                           | ~250 MB       | HIGH     | transformers/PyTorch | No            |
| X-CLIP (action recognition) | X-CLIP Base Patch16 16-frames | ~2,000 MB     | LOW      | transformers/PyTorch | No            |
| **Total resident**          |                               | **~2,300 MB** |          |                      |               |
| **Total if all loaded**     |                               | **~4,800 MB** |          |                      |               |

**GPU 0 constraint:** The LLM (Nemotron-3-Nano-30B) consumes 95.9% of the A5500's 24GB. The VRAM_BUDGET_GB is set to 6.0, but actual available headroom after the LLM is approximately 1-2GB. This means the heavy service is perpetually in eviction mode, loading/unloading models on demand.

### Light Enrichment Service (ai-enrichment-light, port 8096, GPU 1 / A400 4GB)

| Model                    | Architecture      | VRAM                 | Priority | Runtime       | TensorRT |
| ------------------------ | ----------------- | -------------------- | -------- | ------------- | -------- |
| YOLOv8n-Pose             | Ultralytics YOLO  | ~300 MB (200 MB TRT) | HIGH     | TensorRT FP16 | Yes      |
| Threat Detection YOLOv8n | Ultralytics YOLO  | ~400 MB (300 MB TRT) | CRITICAL | TensorRT FP16 | Yes      |
| OSNet x0.25 (ReID)       | OSNet             | ~100 MB              | MEDIUM   | PyTorch       | No       |
| Pet Classifier           | ResNet-18         | ~200 MB              | MEDIUM   | PyTorch       | No       |
| Depth Anything V2 Small  | DPT-Small (ViT-S) | ~150 MB              | LOW      | PyTorch       | No       |
| **Total**                |                   | **~1,150 MB**        |          |               |          |

**GPU 1 constraint:** A400 has 4GB VRAM total. With all 5 models preloaded, utilization is ~29%. There is significant headroom (~2.85GB free). This GPU is underutilized.

### Existing Triton Infrastructure (Phase 1 complete, not yet active)

The project already has a Triton model repository at `ai/triton/model_repository/` with config.pbtxt files for all 10+ models. All are configured with `backend: "onnxruntime"` on `KIND_CPU` (except X-CLIP which uses Python backend). Dynamic batching is configured for reid (batch 1/4/8) and vehicle (batch 1/4). The Triton migration is at Phase 1 (infrastructure setup) -- Phase 2 (side-by-side deployment) has not begun.

### Backend Routing Architecture

The backend uses environment variables (`ENRICHMENT_*_SERVICE=light|heavy`) to route each model type to the correct container. The `enrichment_client.py` manages HTTP connections, circuit breakers, and retry logic. This is a clean abstraction that would survive a Triton migration with minimal changes.

---

## Recommended Optimizations

### HIGH IMPACT

---

#### 1. Complete Triton Migration (Phase 2-3) for All Enrichment Models

**What to change:** Activate the existing Triton Inference Server configuration. Export all PyTorch models to ONNX format, place them in the existing `ai/triton/model_repository/` directories. Switch from two custom FastAPI containers to a single Triton server (or two Triton servers, one per GPU).

**Current state:** All config.pbtxt files already exist. The TritonClient wrapper (`ai/triton/client.py`) is implemented and tested. The migration plan is documented. Only the actual model export and deployment steps remain.

**Expected impact:**

- **Dynamic batching** across all cameras (Triton natively batches incoming requests within a configurable queue delay window). Current per-request inference wastes GPU cycles.
- **2-3x throughput** from batching alone (NVIDIA benchmarks show 70% throughput increase with dynamic batching on A100; proportional gains expected on A400/A5500).
- **Concurrent model execution:** Triton's model scheduler can run multiple models simultaneously on the same GPU, eliminating the sequential bottleneck in the current `OnDemandModelManager`.
- **Unified monitoring:** Native Prometheus metrics at `/metrics` (port 8002) replace custom metric instrumentation.
- **Model versioning:** Built-in A/B testing for model upgrades.

**Implementation effort:** MEDIUM (2-3 days). Infrastructure exists. Main work is ONNX export for each model and integration testing.

**Risks:**

- TensorRT engine files are GPU-architecture specific (must rebuild for different GPUs).
- X-CLIP cannot be exported to ONNX/TensorRT due to custom cross-frame attention; must remain on Python backend within Triton.
- Need to validate that ONNX export preserves accuracy for all models (run validation suite).

**References:**

- [NVIDIA Triton Dynamic Batching](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/tutorials/Conceptual_Guide/Part_2-improving_resource_utilization/README.html)
- [NVIDIA Triton Optimization Guide](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/optimization.html)
- Existing project docs: `ai/triton/AGENTS.md`

---

#### 2. TensorRT for ALL Models (Not Just YOLO Pose/Threat)

**What to change:** Currently only YOLOv8n-Pose and YOLOv8n-Threat use TensorRT (FP16). Extend TensorRT conversion to: Vehicle ResNet-50, Pet ResNet-18, OSNet x0.25, Demographics ViTs, Depth Anything V2, and FashionSigLIP.

**Expected impact:**

- **2-5x speedup** per model (TensorRT optimizes computation graphs, fuses kernels, and applies precision optimizations).
- **40-60% VRAM reduction** (FP16 halves memory; INT8 quarters it).
- ResNet-50 (vehicle): FP32 1500MB -> TensorRT FP16 ~750MB -> TensorRT INT8 ~400MB.
- ViT (demographics): FP32 500MB -> TensorRT FP16 ~250MB -> TensorRT INT8 ~150MB.
- Sub-2ms latency for ResNet-50 on TensorRT FP16 (vs 10-20ms on PyTorch).

**Implementation effort:** MEDIUM. Use the ONNX Runtime TensorRT Execution Provider path: export each model to ONNX, then use `trtexec` or the Ultralytics `.export(format='engine')` to create TensorRT plans. Engine caching means the initial build is slow but subsequent loads are instant.

**Risks:**

- INT8 requires calibration datasets (100-500 representative images). The `quantize_models.py` script exists but needs calibration data.
- Depth Anything V2's DPT head has a hardcoded Reshape that breaks dynamic batching (noted in the existing Triton config). Static batch=1 is required.
- FashionSigLIP uses open_clip which may need custom export handling.

**References:**

- [ONNX Runtime TensorRT Execution Provider](https://onnxruntime.ai/docs/execution-providers/TensorRT-ExecutionProvider.html)
- [Ultralytics TensorRT Export](https://docs.ultralytics.com/modes/export/)
- [ONNX-TensorRT Optimization (40x faster)](https://github.com/umitkacar/onnx-tensorrt-optimization)

---

#### 3. Deploy INT8 Quantization for Vehicle and Demographics Models

**What to change:** Run the existing `ai/enrichment/scripts/quantize_models.py` with calibration data from security camera frames. Deploy the INT8-quantized Vehicle ResNet-50 and Demographics ViT.

**Current state:** The quantization script is fully implemented (PyTorch static PTQ), with configurable calibration batch size (32), validation against accuracy delta threshold (2%), and output directory management. Environment variables `VEHICLE_QUANTIZED` and `DEMOGRAPHICS_QUANTIZED` exist in `.env.example` but are set to `false`.

**Expected impact:**

- Vehicle ResNet-50: 1500MB -> ~400MB (73% reduction)
- Demographics ViT: 500MB -> ~150MB (70% reduction)
- Combined VRAM savings: ~1,450MB
- Inference speedup: 1.5-2x on INT8 vs FP32 (tensor cores accelerate INT8)
- This frees enough VRAM to potentially preload action_recognizer on the heavy service

**Implementation effort:** LOW (1 day). Script exists. Need calibration images (100-500 security camera frames + face crops), run quantization, validate accuracy, flip env vars.

**Risks:**

- INT8 quantization may degrade accuracy by up to 2% (the script validates this).
- Need representative calibration data -- poor calibration data leads to significant accuracy loss.
- INT8 on the A400 (Ampere architecture) is well-supported via Tensor Cores.

**References:**

- Existing script: `ai/enrichment/scripts/quantize_models.py`
- [NVIDIA INT8 Quantization Blog](https://developer.nvidia.com/blog/optimizing-llms-for-performance-and-accuracy-with-post-training-quantization/)

---

#### 4. Replace Depth Anything V2 Small with V2 Vits (Tiny Encoder)

**What to change:** Switch from `depth-anything/Depth-Anything-V2-Small-hf` (24.8M params, 518x518 input) to the ViT-S/Tiny variant for security depth estimation.

**Rationale:** For home security, depth estimation serves one purpose: determining whether a detected object is "close" (approaching the camera/door/property) or "far" (across the street). This is a coarse binary/ternary classification (near/mid/far) that does not require the fine-grained depth quality of the Small model. The Tiny encoder provides sufficient relative depth ordering at 3x faster inference.

**Additionally, consider Depth Anything V3** (released November 2025): DA3 achieves 10%+ improvement over DA2 on ETH3D benchmarks, with better edge quality and detail preservation. The DA3 Tiny variant would be the optimal choice if it fits the VRAM budget.

**Expected impact:**

- ~3x faster inference (Tiny encoder has ~5M params vs 24.8M)
- VRAM reduction from ~150MB to ~50MB
- Marginal quality loss for the security use case (relative depth ordering preserved)

**Implementation effort:** LOW (half day). Change the model path in `model_registry.py` and `depth_anything_loader.py`. The HuggingFace pipeline handles input preprocessing automatically.

**Risks:**

- Fine-grained depth detail loss (irrelevant for security proximity estimation).
- DA3 is newer and may have less community testing.

**References:**

- [Depth Anything V2 GitHub](https://github.com/DepthAnything/Depth-Anything-V2)
- [Depth Anything V3 (November 2025)](https://depth-anything-3.github.io/)
- [Video Depth Anything (CVPR 2025)](https://github.com/DepthAnything/Video-Depth-Anything)

---

#### 5. Enable Pipeline Parallelism Within Enrichment Containers

**What to change:** Currently, when a frame arrives, models are invoked sequentially (or with limited concurrency via `ENRICHMENT_SERVICE_CONCURRENCY=4`). For a single frame with a person detection, the pipeline runs: pose -> threat -> ReID -> demographics -> clothing -> depth -> action. These models are independent for a given frame and should run concurrently.

**Expected impact:**

- End-to-end enrichment latency reduction from sum(model_latencies) to max(model_latencies).
- With 7 models at ~50ms each (TensorRT), sequential = 350ms, parallel = ~50ms (7x speedup in wall-clock time).
- On GPU 1 (A400), all 5 light models are preloaded and have enough VRAM to run concurrently if batched carefully.

**Implementation effort:** MEDIUM. The `OnDemandModelManager` already supports async operations with locks. Need to ensure CUDA streams are properly separated or use Triton's built-in concurrent execution.

**Risks:**

- GPU memory fragmentation from concurrent model execution.
- CUDA stream synchronization overhead may negate gains for very small models.
- On GPU 0 (heavy service), concurrent execution could cause OOM since VRAM is already constrained.

**References:**

- [Triton Concurrent Model Execution](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/tutorials/Conceptual_Guide/Part_2-improving_resource_utilization/README.html)

---

### MEDIUM IMPACT

---

#### 6. Replace OSNet x0.25 with ReIDMamba

**What to change:** Replace the OSNet-x0.25 person re-identification model (ICCV 2019, ~100MB, 512-dim embeddings) with ReIDMamba (November 2025).

**Rationale:** ReIDMamba is a pure Mamba-based ReID framework that achieves state-of-the-art performance on 5 benchmarks while using only 1/3 the parameters of TransReID. Its Mamba architecture is conceptually aligned with the project's Nemotron-3-Nano-30B (hybrid Mamba-Transformer). Key advantages:

- **Fewer parameters:** ~1/3 of TransReID (OSNet x0.25 is already small at ~500K params, but ReIDMamba's architecture offers better feature discrimination)
- **Lower GPU memory usage and faster inference throughput** compared to transformer-based alternatives
- **State-of-the-art** on Market1501, DukeMTMC, MSMT17, and other benchmarks

**Also worth evaluating:**

- **TE-TransReID** (2025): Lightweight CNN-Transformer hybrid, rank-1 94.8% on Market1501 with 27.5M params. Better accuracy than OSNet but heavier.
- **Pose2ID** (CVPR 2025): Training-free ReID via feature centralization from poses -- could eliminate the need for a separate ReID model if pose estimation is already running.

**Expected impact:**

- Potential accuracy improvement of 5-10% on cross-camera person matching
- Similar or better inference speed
- VRAM footprint may increase slightly (ReIDMamba uses ~30-50M params vs OSNet x0.25's ~500K), but still small

**Implementation effort:** MEDIUM (2-3 days). Need to integrate the ReIDMamba model, export to ONNX, update embedding dimension if different from 512, and update the similarity threshold.

**Risks:**

- ReIDMamba is new (November 2025) with limited deployment history.
- Must validate that it works well in the security camera domain (vs standard ReID benchmarks which use curated datasets).
- Embedding dimension change would require reprocessing any stored embeddings.

**References:**

- [ReIDMamba (arXiv, Nov 2025)](https://arxiv.org/abs/2511.07948)
- [ReIDMamba GitHub](https://github.com/GuHY777/ReIDMamba)
- [Pose2ID (CVPR 2025)](https://github.com/yuanc3/Pose2ID)
- [TE-TransReID (2025)](https://www.mdpi.com/1424-8220/25/17/5461)

---

#### 7. Replace X-CLIP with EZ-CLIP or ViFi-CLIP for Action Recognition

**What to change:** Replace `microsoft/xclip-base-patch16-16-frames` (~2GB VRAM, cannot export to ONNX/TensorRT) with a lighter CLIP-based action recognition model.

**Current issues with X-CLIP:**

- **2GB VRAM** -- the single largest model in the pipeline
- **Cannot be exported to ONNX/TensorRT** due to custom cross-frame attention (documented in Triton config)
- **LOW priority** in the model registry -- loaded on-demand and frequently evicted
- Must remain on Python backend in Triton

**Alternatives evaluated:**

| Model           | VRAM   | ONNX/TRT Export                          | Key Advantage                                                           |
| --------------- | ------ | ---------------------------------------- | ----------------------------------------------------------------------- |
| **EZ-CLIP**     | ~400MB | Yes (standard CLIP + temporal prompting) | No architectural changes to CLIP; temporal adaptation via prompting     |
| **ViFi-CLIP**   | ~800MB | Partial                                  | Simple fine-tuning baseline, competitive with dedicated temporal models |
| **VLPA-CLIP**   | ~600MB | Yes                                      | Video Language Prompting and Adapting, May 2025                         |
| **Motion-CLIP** | ~500MB | Yes                                      | Explicit motion decoupling from background                              |

**Recommendation:** EZ-CLIP is the strongest candidate because:

1. It uses temporal visual prompting without altering CLIP's core architecture, making it ONNX-exportable.
2. ~400MB VRAM (80% reduction from X-CLIP's 2GB).
3. Competitive accuracy on standard action recognition benchmarks.

**Expected impact:**

- VRAM reduction from 2GB to ~400MB (80% reduction)
- Ability to export to TensorRT for 2-3x speedup
- Faster load time when invoked on-demand

**Implementation effort:** MEDIUM-HIGH (3-5 days). Need to replace the action recognizer module, update the Triton config, validate accuracy on security-relevant actions (loitering, trespassing, running, fighting).

**Risks:**

- Security-specific action labels (loitering, trespassing, hiding) may have different accuracy profiles than standard benchmarks.
- Need to validate zero-shot performance with security-relevant text prompts.

**References:**

- [EZ-CLIP (OpenReview)](https://openreview.net/forum?id=hWjPRRyiqm)
- [ViFi-CLIP](https://muzairkhattak.github.io/ViFi-CLIP/)
- [VLPA-CLIP (May 2025)](https://www.sciencedirect.com/science/article/abs/pii/S0031320325004303)

---

#### 8. Use NVIDIA Model Analyzer to Find Optimal Configurations

**What to change:** Run NVIDIA Model Analyzer (now part of NVIDIA Dynamo Triton as of March 2025) against all models on the actual A400 and A5500 hardware to determine optimal batch sizes, instance counts, and precision settings.

**Expected impact:**

- Data-driven configuration tuning (vs current guesswork for batch sizes and queue delays)
- Automated sweep of: model instance count, dynamic batch size, precision (FP32/FP16/INT8), concurrency levels
- Identifies the Pareto-optimal configurations for latency vs throughput on each specific GPU

**Implementation effort:** LOW-MEDIUM (1-2 days). Install Model Analyzer, run automated sweeps, apply recommended configurations.

**Risks:** None -- it is a read-only analysis tool.

**References:**

- [NVIDIA Triton Model Analyzer](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_analyzer.html)
- [NVIDIA Blog: Model Analyzer at Scale](https://developer.nvidia.com/blog/identifying-the-best-ai-model-serving-configurations-at-scale-with-triton-model-analyzer/)

---

#### 9. Batch Enrichment Requests Across Cameras

**What to change:** Currently, enrichment processes frames per-camera. With 4+ cameras, batch requests across cameras for the same model (e.g., batch 4 vehicle crops from 4 different cameras into a single inference call).

**How:** The existing batch processing infrastructure (90-second windows, 30-second idle timeout) already accumulates detections. During the enrichment phase, group detections by model type across all cameras, then send batched requests.

**Expected impact:**

- 2-4x throughput improvement for person-heavy scenes (multiple person crops -> batched ReID, batched pose, batched demographics)
- Better GPU utilization (small models like OSNet underutilize the GPU with batch=1)
- The Triton dynamic batching configs already define preferred batch sizes (1, 4, 8 for ReID; 1, 4 for vehicle)

**Implementation effort:** MEDIUM. Requires changes to the enrichment pipeline orchestration to group by model type before dispatching.

**Risks:**

- Added latency from waiting to accumulate batches (mitigated by Triton's `max_queue_delay_microseconds` setting).
- Memory spikes from large batches during busy periods.

---

#### 10. A400 Optimal Precision Strategy

**What to change:** Apply model-specific precision optimization for the A400's 4GB VRAM constraint.

**Recommended precision per model on A400:**

| Model             | Current       | Recommended   | VRAM Before | VRAM After  | Speedup |
| ----------------- | ------------- | ------------- | ----------- | ----------- | ------- |
| YOLOv8n-Pose      | TensorRT FP16 | TensorRT INT8 | 200 MB      | ~120 MB     | 1.3x    |
| YOLOv8n-Threat    | TensorRT FP16 | TensorRT INT8 | 300 MB      | ~180 MB     | 1.3x    |
| OSNet x0.25       | PyTorch FP32  | ONNX FP16     | 100 MB      | ~50 MB      | 1.5x    |
| Pet Classifier    | PyTorch FP32  | ONNX FP16     | 200 MB      | ~100 MB     | 1.5x    |
| Depth Anything V2 | PyTorch FP32  | ONNX FP16     | 150 MB      | ~75 MB      | 1.5x    |
| **Total**         |               |               | **~950 MB** | **~525 MB** |         |

**The A400 supports:** FP32, FP16, INT8 (via 24 Tensor Cores), and even NVFP4 (introduced 2025). INT8 for YOLO models is safe -- YOLO26 research (September 2025) shows INT8 retains nearly the same mAP as FP32. For OSNet and Pet Classifier, FP16 is the safe choice. INT8 would require careful calibration and validation.

**Expected impact:** 45% VRAM reduction on GPU 1, freeing ~425MB for future models or larger batch sizes.

**Implementation effort:** LOW-MEDIUM.

- YOLO INT8: Use Ultralytics `.export(format='engine', int8=True, data='calibration.yaml')`
- Other models: Export to ONNX, then run through `trtexec --int8` or use ONNX Runtime FP16 mode.

**References:**

- [NVIDIA RTX A400 Specs](https://www.nvidia.com/en-us/products/workstations/rtx-a400/)
- [NVIDIA NVFP4 for Low-Precision Inference (2025)](https://developer.nvidia.com/blog/introducing-nvfp4-for-efficient-and-accurate-low-precision-inference/)

---

### LOW IMPACT

---

#### 11. Replace Pet Classifier (ResNet-18) with MobileNetV3-Small

**What to change:** Replace the ResNet-18-based pet classifier (~200MB, 11.7M params) with MobileNetV3-Small (~10MB, 2.5M params) fine-tuned on Oxford-IIIT Pets or a combined cat/dog dataset.

**Rationale:** Pet classification in a security context is primarily for false-positive reduction (distinguishing a cat from a crouching intruder). This is a simple binary/few-class task that does not need ResNet-50-level capacity. MobileNetV3-Small with INT8 quantization would reduce VRAM by ~95% while maintaining >95% accuracy on cat/dog classification.

**Expected impact:**

- VRAM: 200MB -> ~10MB (95% reduction)
- Inference: 2-3x faster
- Accuracy: Comparable for cat/dog binary classification

**Implementation effort:** LOW-MEDIUM (1-2 days). Fine-tune MobileNetV3-Small on pet dataset, export to ONNX, deploy.

**Risks:** Minimal. Pet classification is already a simple task with good separation in feature space.

**References:**

- [MobileNetV3 for Edge Deployment](https://labelyourdata.com/articles/image-classification-models)

---

#### 12. Unified Pose + Action Model (Longer Term)

**What to change:** Explore replacing the separate YOLOv8n-Pose + X-CLIP action recognizer with a unified pose-action model that performs both tasks simultaneously.

**State of the art:**

- **PoseRL-Net (2025):** Integrates STGCN + attention + GRU for pose-based action recognition.
- **Pose2ID (CVPR 2025):** Training-free approach that extracts identity from pose -- could eliminate ReID model too.
- **End-to-end frameworks:** Recent research shows joint optimization of pose estimation and skeleton action recognition outperforms two-stage pipelines.

**The key insight:** Since the system already runs pose estimation (YOLOv8n-Pose with 17 COCO keypoints), action recognition could be performed directly on the pose skeleton sequence rather than requiring a separate 2GB video model (X-CLIP). A lightweight skeleton-based action classifier (STGCN or similar) operating on the pose keypoints would:

- Eliminate the 2GB X-CLIP model entirely
- Run in ~10ms on CPU (skeleton data is tiny compared to video frames)
- Be naturally compatible with the existing pose estimation output

**Expected impact:**

- Eliminate X-CLIP entirely (save 2GB VRAM)
- Combined pose+action in <100ms (vs 50ms + 200ms separately)
- Simpler pipeline with fewer models to manage

**Implementation effort:** HIGH (1-2 weeks). Requires training a skeleton-based action classifier on security-relevant actions and integrating it with the pose estimation output.

**Risks:**

- Skeleton-based action recognition has lower accuracy than appearance-based (X-CLIP) for some actions (e.g., carrying objects, clothing-based suspicious behavior).
- Need labeled training data for security-specific actions.

**References:**

- [PoseRL-Net (2025)](https://www.frontiersin.org/journals/neurorobotics/articles/10.3389/fnbot.2025.1531894/full)
- [Pose2ID (CVPR 2025)](https://github.com/yuanc3/Pose2ID)

---

#### 13. Consider ONNX Runtime Server as Lightweight Triton Alternative

**What to change:** For the light enrichment service (5 small models, A400 4GB), consider using ONNX Runtime Server instead of Triton. ONNX Runtime Server is lighter weight and natively supports the ONNX format that all light models can export to.

**Rationale:** Triton may be overkill for 5 small models on a 4GB GPU. ONNX Runtime Server provides:

- Native ONNX model serving
- HTTP/gRPC endpoints
- TensorRT Execution Provider integration
- Lower container overhead than Triton

**However:** Since Triton infrastructure already exists, the incremental benefit of ONNX Runtime Server is small. Triton provides more features (dynamic batching, model versioning, unified metrics) that justify its overhead.

**Recommendation:** Stick with Triton for both services. The unified tooling and monitoring is worth the marginal overhead.

**Implementation effort:** LOW (if chosen, just deploy ONNX Runtime Server container with model configs).

---

#### 14. Model Sharding / Swapping Strategy for GPU 0

**What to change:** Instead of the current LRU eviction in `OnDemandModelManager`, implement predictive model swapping based on detection types in the current batch.

**How:** Before processing a batch, scan all detections and pre-load only the models needed:

- Persons detected -> load demographics, clothing, ReID, pose
- Vehicles detected -> load vehicle classifier
- No faces detected -> skip demographics

The current system already does on-demand loading, but the `OnDemandModelManager` loads models reactively (when an endpoint is hit), not predictively (before the batch starts).

**Expected impact:**

- Reduced model swap latency (overlap loading with processing)
- Better VRAM utilization (only load what's needed per batch)
- Fewer evictions (predictive vs reactive)

**Implementation effort:** MEDIUM.

**Risks:** Prediction accuracy depends on YOLO26 detection quality. Misprediction wastes VRAM and time on unnecessary model loads.

---

## Architecture Assessment: Light/Heavy Split vs. Triton

### Current Architecture (2 Custom FastAPI Containers)

**Strengths:**

- Clean separation by VRAM requirements
- Dedicated GPU per service eliminates contention
- Simple routing via environment variables
- Per-model circuit breakers in backend

**Weaknesses:**

- No dynamic batching (single request per inference)
- Manual VRAM management (LRU eviction in OnDemandModelManager)
- Duplicated serving infrastructure (2 FastAPI servers, 2 sets of health checks, 2 sets of metrics)
- Sequential model execution within each container

### Recommended Architecture: 2 Triton Servers (one per GPU)

**Recommendation:** Deploy two Triton Inference Server instances, one per GPU, replacing the two custom FastAPI containers. This preserves the GPU isolation while gaining all Triton benefits.

|                  | Current                     | Recommended                                 |
| ---------------- | --------------------------- | ------------------------------------------- |
| GPU 0 (A5500)    | ai-enrichment FastAPI       | Triton Server (heavy models)                |
| GPU 1 (A400)     | ai-enrichment-light FastAPI | Triton Server (light models)                |
| Batching         | None                        | Dynamic (per-model config)                  |
| Model Management | Custom OnDemandModelManager | Triton model repository + model control API |
| Monitoring       | Custom Prometheus metrics   | Native Triton metrics                       |
| Model Format     | PyTorch (.pt, .bin)         | ONNX / TensorRT (.plan)                     |
| Concurrency      | asyncio-limited             | CUDA stream-level                           |

**Migration path:**

1. Already done: Triton config.pbtxt files, client wrapper, model repository structure
2. Next: Export all models to ONNX, validate accuracy
3. Then: Deploy Triton containers alongside existing services (dual-write)
4. Finally: Cut over routing, deprecate FastAPI services

---

## Summary: Prioritized Optimization Roadmap

| Priority | Optimization                                      | VRAM Savings | Throughput Gain | Effort      | Risk   |
| -------- | ------------------------------------------------- | ------------ | --------------- | ----------- | ------ |
| 1        | Deploy INT8 quantization (vehicle + demographics) | ~1,450 MB    | 1.5-2x          | LOW         | LOW    |
| 2        | Replace Depth Anything V2 Small with Tiny         | ~100 MB      | 3x              | LOW         | LOW    |
| 3        | TensorRT for all models on A400 (FP16/INT8)       | ~425 MB      | 2-5x            | MEDIUM      | LOW    |
| 4        | Complete Triton migration (Phase 2)               | N/A          | 2-3x (batching) | MEDIUM      | MEDIUM |
| 5        | Pipeline parallelism (concurrent models)          | N/A          | 3-7x latency    | MEDIUM      | MEDIUM |
| 6        | Cross-camera batch enrichment                     | N/A          | 2-4x            | MEDIUM      | LOW    |
| 7        | Replace X-CLIP with EZ-CLIP                       | ~1,600 MB    | 2-3x            | MEDIUM-HIGH | MEDIUM |
| 8        | Run Model Analyzer for configuration tuning       | N/A          | 10-30%          | LOW         | NONE   |
| 9        | Evaluate ReIDMamba as OSNet replacement           | ~0 MB        | Similar         | MEDIUM      | MEDIUM |
| 10       | Replace Pet Classifier with MobileNetV3           | ~190 MB      | 2-3x            | LOW-MEDIUM  | LOW    |
| 11       | A400 precision optimization (FP16 for all)        | ~425 MB      | 1.5x            | LOW         | LOW    |
| 12       | Unified pose+action model (eliminate X-CLIP)      | ~2,000 MB    | 2x              | HIGH        | HIGH   |

**Total potential VRAM savings:** ~3,600 MB (heavy) + ~525 MB (light)
**Total potential throughput gain:** 4-10x end-to-end (combining batching, TensorRT, parallelism)

---

## Appendix: Model VRAM Budget After All Optimizations

### GPU 0 (A5500 24GB) - Heavy Service

| Model                         | Current VRAM | Optimized VRAM     | Format        |
| ----------------------------- | ------------ | ------------------ | ------------- |
| Vehicle ResNet-50             | 1,500 MB     | 400 MB             | TensorRT INT8 |
| FashionSigLIP                 | 800 MB       | 400 MB             | ONNX FP16     |
| Demographics ViT (age+gender) | 500 MB       | 150 MB             | TensorRT INT8 |
| X-CLIP -> EZ-CLIP             | 2,000 MB     | 400 MB             | TensorRT FP16 |
| **Total**                     | **4,800 MB** | **1,350 MB**       |               |
| **Savings**                   |              | **3,450 MB (72%)** |               |

### GPU 1 (A400 4GB) - Light Service

| Model                  | Current VRAM | Optimized VRAM   | Format               |
| ---------------------- | ------------ | ---------------- | -------------------- |
| YOLOv8n-Pose           | 200 MB       | 120 MB           | TensorRT INT8        |
| YOLOv8n-Threat         | 300 MB       | 180 MB           | TensorRT INT8        |
| OSNet x0.25            | 100 MB       | 50 MB            | ONNX FP16            |
| Pet Classifier         | 200 MB       | 10 MB            | MobileNetV3 TRT INT8 |
| Depth Anything V2 Tiny | 150 MB       | 25 MB            | ONNX FP16            |
| **Total**              | **950 MB**   | **385 MB**       |                      |
| **Savings**            |              | **565 MB (59%)** |                      |

This leaves ~3.6GB free on the A400 -- enough to potentially move some heavy models to GPU 1 and further relieve GPU 0.
