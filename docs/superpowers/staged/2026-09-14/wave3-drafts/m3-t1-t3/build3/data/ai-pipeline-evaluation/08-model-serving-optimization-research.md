# Model Serving Optimization Research

**Date:** 2026-02-08
**Hardware Context:** NVIDIA RTX A400 (4 GB VRAM, GPU 1) + RTX A5500 (24 GB VRAM, GPU 0, shared with 30B LLM at 95.9% utilization)
**Current Setup:** 13 Triton models (3 GPU, 10 CPU), ONNX Runtime backend, Nemotron-3-Nano-30B-A3B via llama.cpp

---

## Table of Contents

1. [Model Compression Techniques (2025-2026 SOTA)](#1-model-compression-techniques)
2. [Multi-Model Serving Optimization on Triton](#2-multi-model-serving-optimization-on-triton)
3. [ONNX Runtime vs TensorRT vs OpenVINO](#3-onnx-runtime-vs-tensorrt-vs-openvino)
4. [Emerging Serving Frameworks](#4-emerging-serving-frameworks)
5. [Model Cascading / Early Exit](#5-model-cascading--early-exit)
6. [Prioritized Implementation Roadmap](#6-prioritized-implementation-roadmap)

---

## Current Model Inventory

| Model               | Backend     | Device | Architecture                  | Size (approx)  | Input Shape   | Purpose                        |
| ------------------- | ----------- | ------ | ----------------------------- | -------------- | ------------- | ------------------------------ |
| yolo26              | onnxruntime | GPU 0  | YOLOv8-variant                | ~50 MB         | 1x3x640x640   | Primary object detection       |
| clip                | onnxruntime | GPU 0  | ViT-L/14                      | ~1159 MB       | Bx3x224x224   | Scene/object embedding         |
| florence2           | python      | GPU 0  | Encoder-decoder               | ~460 MB (FP16) | base64 string | Vision-language captioning     |
| reid                | onnxruntime | CPU    | OSNet-x0.25                   | ~100 MB        | Bx3x256x128   | Person re-identification       |
| pose                | onnxruntime | CPU    | YOLOv8n-pose                  | ~12 MB         | 1x3x640x640   | Pose estimation (17 keypoints) |
| threat              | onnxruntime | CPU    | YOLOv8n                       | ~12 MB         | 1x3x640x640   | Weapon/threat detection        |
| vehicle             | onnxruntime | CPU    | ResNet-50                     | ~100 MB        | Bx3x224x224   | Vehicle segment classification |
| depth               | onnxruntime | CPU    | DPT-Small (Depth Anything V2) | ~100 MB        | 1x3x518x518   | Depth estimation               |
| demographics_age    | onnxruntime | CPU    | ViT                           | ~340 MB        | Bx3x224x224   | Age range classification       |
| demographics_gender | onnxruntime | CPU    | ViT                           | ~340 MB        | Bx3x224x224   | Gender classification          |
| pet                 | onnxruntime | CPU    | ResNet-18                     | ~45 MB         | Bx3x224x224   | Cat/dog classification         |
| fashion_clip        | onnxruntime | CPU    | SigLIP (vision encoder)       | ~354 MB        | Bx3x224x224   | Clothing classification        |
| xclip_action        | python      | CPU    | X-CLIP-base-patch32           | ~400 MB        | base64 frames | Action recognition             |

**GPU 0 total model VRAM:** ~1,669 MB (yolo26 + clip + florence2), leaving headroom on A400's 4 GB
**CPU models total RAM:** ~1,803 MB

---

## 1. Model Compression Techniques

### 1.1 ONNX Quantization (INT8 / INT4 / Mixed Precision)

**What it is:** Post-training quantization (PTQ) reduces model weights and activations from FP32 to lower precision (INT8, INT4, or mixed). ONNX Runtime supports this natively via `onnxruntime.quantization` APIs. INT8 halves model size; INT4 quarters it. Mixed precision keeps sensitive layers at higher precision while quantizing the rest.

**Quality/Speed Tradeoff for Vision Models:**

| Precision                 | Memory Savings | Typical Accuracy Drop | Latency Change      | Hardware Required         |
| ------------------------- | -------------- | --------------------- | ------------------- | ------------------------- |
| FP32 (baseline)           | 0%             | 0%                    | Baseline            | Any                       |
| FP16                      | 50%            | <0.5%                 | 10-30% faster (GPU) | GPU with FP16 support     |
| INT8 (dynamic)            | 75%            | 1-3%                  | 20-40% faster (CPU) | CPU with VNNI/AVX-512     |
| INT8 (static, calibrated) | 75%            | 0.5-2%                | 30-50% faster       | CPU/GPU with INT8 support |
| INT4 (weight-only)        | 87.5%          | 2-5%                  | Variable            | Requires specific kernels |

**Key findings from 2025-2026 research:**

- ONNX Runtime on GPU only supports S8S8 quantization format; hardware with Tensor Core INT8 (like T4, A100) achieves best results. The RTX A400 (Ada Lovelace) does support INT8 Tensor Cores.
- For CPU models, U8S8 with QDQ (Quantize-DeQuantize) format is recommended as the default that balances performance and accuracy.
- INT4 types (introduced in ONNX opset 21) require ONNX Runtime 1.20+. The `GatherBlockQuantized` operator enables block-wise INT4 quantization.
- Per-node calibration reduces memory during the quantization process itself, critical for large models.
- A 2025 paper on "Selective Quantization Tuning for ONNX Models" shows that selectively quantizing only resilient layers preserves accuracy while maximizing compression.

**Expected Impact on Our Setup:**

| Model               | Current Precision | Recommended        | VRAM/RAM Savings | Accuracy Risk                        |
| ------------------- | ----------------- | ------------------ | ---------------- | ------------------------------------ |
| yolo26              | FP32              | INT8 static (GPU)  | ~25 MB saved     | Low (YOLO is robust to quantization) |
| clip                | FP32              | FP16 (GPU)         | ~580 MB saved    | Very low                             |
| florence2           | FP16              | Already FP16       | None             | N/A                                  |
| reid                | FP32              | INT8 dynamic (CPU) | ~50 MB saved     | Low                                  |
| pose                | FP32              | INT8 dynamic (CPU) | ~6 MB saved      | Low                                  |
| threat              | FP32              | INT8 dynamic (CPU) | ~6 MB saved      | Low                                  |
| vehicle             | FP32              | INT8 static (CPU)  | ~50 MB saved     | Low                                  |
| depth               | FP32              | INT8 static (CPU)  | ~50 MB saved     | Medium (depth maps sensitive)        |
| demographics_age    | FP32              | INT8 dynamic (CPU) | ~170 MB saved    | Low-Medium                           |
| demographics_gender | FP32              | INT8 dynamic (CPU) | ~170 MB saved    | Low-Medium                           |
| fashion_clip        | FP32              | INT8 dynamic (CPU) | ~177 MB saved    | Low                                  |

**Implementation effort:** Low-Medium. ONNX Runtime provides `quantize_dynamic()` (no calibration data needed) and `quantize_static()` (requires calibration dataset of ~100-500 representative images). Dynamic quantization can be applied in a single script; static requires a calibration pipeline.

**Applies to our setup:** Yes, directly. All ONNX models can be quantized. The largest win is converting CLIP to FP16 on GPU (saves ~580 MB VRAM on the A400) and INT8 quantizing CPU models for latency improvement.

### 1.2 Knowledge Distillation

**What it is:** Training a smaller "student" model to mimic a larger "teacher" model's outputs, producing a compact model with near-teacher accuracy.

**Relevant distilled models for our use case:**

| Teacher Model            | Distilled Student        | Size Reduction | Accuracy Retention | Status                                      |
| ------------------------ | ------------------------ | -------------- | ------------------ | ------------------------------------------- |
| CLIP ViT-L/14 (1.16 GB)  | CLIP ViT-B/16 (~600 MB)  | ~48%           | ~95% on zero-shot  | Available on HuggingFace                    |
| CLIP ViT-L/14            | MobileCLIP-S2 (~130 MB)  | ~89%           | ~90% on zero-shot  | Apple, 2024                                 |
| Florence-2-base (460 MB) | VL2Lite (CVPR 2025)      | ~60-70%        | Task-dependent     | Research stage                              |
| YOLOv8m/YOLO26           | YOLOv8n                  | ~80%           | ~85-90% mAP        | Already using nano variants for pose/threat |
| OSNet-x1.0 (ReID)        | OSNet-x0.25 (~100 MB)    | ~75%           | ~95% rank-1        | Already using x0.25                         |
| ResNet-50 (vehicle)      | ResNet-18 or MobileNetV3 | ~75%           | ~92-95%            | Available, easy swap                        |
| ViT-base (demographics)  | ViT-tiny/MobileViT       | ~75%           | ~90-93%            | Available on HuggingFace                    |

**Key 2025-2026 findings:**

- LKD-YOLOv8 integrates masked generative distillation (MGD) into the YOLO framework for infrared detection on edge platforms -- directly applicable to our threat detection model.
- VL2Lite (CVPR 2025) demonstrates task-specific knowledge distillation from large VLMs to lightweight models, relevant for Florence-2 replacement.
- MoVE-KD (CVPR 2025) proposes knowledge distillation for VLMs with mixture of visual encoders, potentially useful for combining CLIP and Florence-2 into a single lighter model.

**Expected impact:** Replacing CLIP ViT-L/14 with MobileCLIP-S2 would free ~1 GB on GPU 0, though at the cost of some zero-shot accuracy. Replacing vehicle ResNet-50 with MobileNetV3-small would cut CPU inference time by ~3x.

**Implementation effort:** Medium. Requires model evaluation, re-export to ONNX, and validation against security-specific benchmarks.

**Applies to our setup:** Yes, particularly for CLIP (largest GPU model) and vehicle classifier (CPU bottleneck).

### 1.3 Pruning

**What it is:** Removing redundant parameters (weights, attention heads, or entire layers) from a model while preserving accuracy. Structured pruning removes entire neurons/channels/heads (hardware-friendly, real speedup); unstructured pruning zeros individual weights (higher compression but no speedup without sparse hardware).

**2025-2026 state of the art:**

| Technique                        | Target               | Speedup                 | Accuracy Loss | Hardware Compatibility |
| -------------------------------- | -------------------- | ----------------------- | ------------- | ---------------------- |
| Structured channel pruning (CNN) | ResNet, YOLO         | 1.5-3x                  | 1-3%          | Universal              |
| Block-structured pruning (ViT)   | ViT, DeiT            | 1.8-3.9x                | 1-4%          | GPU-friendly           |
| FBP-ViT (ICMR 2025)              | ViT (MSA/MLP blocks) | 2-4x                    | 1-3%          | Universal              |
| Dynamic token pruning (ViT)      | ViT                  | 1.5-2x                  | <1%           | Universal              |
| LPViT semi-structured (2024)     | ViT                  | 1.4x (GPU), 1.8x (edge) | 1-2%          | N:M sparsity hardware  |
| UPDP unified depth pruning       | CNN + ViT            | 1.3-2x                  | 1-3%          | Universal              |

**Key findings:**

- For ViTs (demographics_age, demographics_gender, CLIP): FBP-ViT's fine-grained block pruning selectively removes MSA or MLP blocks with minimal accuracy loss. This is directly applicable.
- For CNNs (vehicle ResNet-50, pet ResNet-18): Standard structured channel pruning is mature and well-supported by ONNX export. PyTorch's `torch.nn.utils.prune` can prune 30-50% of channels with <2% accuracy loss.
- Dynamic token pruning for ViTs: Automatically adjusts pruning rate based on input complexity. Security-relevant frames (with people/vehicles) would retain more tokens; empty frames get aggressively pruned.

**Expected impact:**

- Pruning demographics ViTs by 40-50% (block pruning): ~2x CPU speedup, ~170 MB RAM saved per model.
- Pruning vehicle ResNet-50 by 30%: ~1.3x CPU speedup, ~30 MB RAM saved.
- Dynamic token pruning on CLIP ViT-L/14: 1.5-2x speedup with <1% embedding quality loss.

**Implementation effort:** Medium-High. Requires fine-tuning after pruning (even a few epochs) to recover accuracy. Need calibration data.

**Applies to our setup:** Yes, especially for the CPU-bound ViT models where inference latency matters.

### 1.4 Neural Architecture Search (NAS)

**What it is:** Automated search for optimal model architectures that meet specific constraints (latency, memory, accuracy). Hardware-aware NAS profiles real-device performance during search.

**2025-2026 developments relevant to security/surveillance:**

- **YOLO26** (Roboflow, 2026): Already NAS-influenced, brings faster CPU inference, small-object accuracy, and edge optimization. This is already our primary detector.
- **EfficientDet-Lite** / **EfficientNet-Lite**: NAS-designed object detectors and classifiers optimized for edge deployment. Could replace ResNet-based classifiers.
- **Early Exiting Neural Networks (EENN)**: Recent NAS work automates the placement of early exit branches in existing architectures, allowing dynamic termination based on input complexity. A 2025 paper on "Hardware-aware Neural Architecture Search of Early Exiting Networks on Edge Accelerators" is directly relevant.
- **MobileNetV4** (2024-2025): NAS-optimized for mobile/edge, with hardware-aware design targeting multiple platforms including NVIDIA GPUs.

**Expected impact:** Swapping vehicle classifier from ResNet-50 to a NAS-optimized MobileNetV4-small could yield 3-5x speedup with <3% accuracy loss.

**Implementation effort:** Low (if using pre-trained NAS models) to Very High (if running custom NAS).

**Applies to our setup:** Yes, using pre-trained NAS models as drop-in replacements for our classifiers.

---

## 2. Multi-Model Serving Optimization on Triton

### 2.1 GPU Memory Sharing via Rate Limiter

**What it is:** Triton's rate limiter manages scheduling across all loaded models to prevent GPU memory oversubscription. It operates cross-model, allowing prioritization and resource-aware scheduling.

**How it works:**

- Each model instance declares its GPU memory requirement as a "resource."
- The rate limiter ensures that the total active GPU memory across all instances does not exceed the available budget.
- This allows models to effectively share GPU memory by time-multiplexing -- only active models consume GPU memory; others stay dormant.

**Configuration for our A400 (4 GB):**

```
# Start Triton with rate limiter
tritonserver --model-repository=/models \
  --rate-limit=execution_count \
  --rate-limit-resource=gpu_memory:0:3800  # 3.8 GB budget on GPU 0

# In yolo26 config.pbtxt:
instance_group [
  {
    count: 1
    kind: KIND_GPU
    gpus: [ 0 ]
    rate_limiter {
      resources [
        { name: "gpu_memory" count: 50 }  # ~50 MB
      ]
    }
  }
]

# In clip config.pbtxt:
instance_group [
  {
    count: 1
    kind: KIND_GPU
    gpus: [ 0 ]
    rate_limiter {
      resources [
        { name: "gpu_memory" count: 1200 }  # ~1200 MB
      ]
      priority: 2  # Lower priority than YOLO (higher number = lower priority)
    }
  }
]

# In florence2 config.pbtxt:
instance_group [
  {
    count: 1
    kind: KIND_GPU
    gpus: [ 0 ]
    rate_limiter {
      resources [
        { name: "gpu_memory" count: 460 }  # ~460 MB
      ]
      priority: 3  # Lowest priority among GPU models
    }
  }
]
```

**Priority system:** An instance with priority 2 gets half the scheduling chances of priority 1. For our pipeline: YOLO (priority 1, always-on detector) > CLIP (priority 2, per-event embedding) > Florence-2 (priority 3, detailed captioning).

**Expected impact:** Better GPU utilization. Prevents OOM when multiple GPU models process simultaneously. Critical for the A400 where 3 models compete for 4 GB.

**Implementation effort:** Low. Config-only changes.

**Applies to our setup:** Yes, directly. This is the most impactful low-effort optimization for GPU memory management.

### 2.2 Dynamic Model Loading/Unloading

**What it is:** Triton can load and unload models on-demand using its Model Management API, freeing GPU/CPU memory when models are not in use.

**Three control modes:**

| Mode           | Behavior                                      | Use Case                        |
| -------------- | --------------------------------------------- | ------------------------------- |
| NONE (default) | All models loaded at startup, no changes      | Production (predictable memory) |
| POLL           | Monitors model repository, auto-loads/unloads | Development                     |
| EXPLICIT       | Models loaded/unloaded only via API calls     | Dynamic resource management     |

**EXPLICIT mode for our pipeline:**

```bash
# Start Triton with explicit control
tritonserver --model-repository=/models --model-control-mode=explicit \
  --load-model=yolo26 --load-model=clip  # Only load always-needed models

# Load florence2 on-demand when captioning is needed
curl -X POST localhost:8000/v2/repository/models/florence2/load

# Unload after processing batch
curl -X POST localhost:8000/v2/repository/models/florence2/unload
```

**Expected impact:** Could free ~460 MB GPU memory when Florence-2 is not actively processing. Since Florence-2 is used only for detailed event captioning (not every frame), this would give YOLO and CLIP more breathing room on the A400.

**Implementation effort:** Medium. Requires backend orchestration logic to load/unload models before/after batch processing. Load time adds latency (several seconds for large models).

**Applies to our setup:** Yes, particularly for Florence-2. Not recommended for YOLO (always-on) or CLIP (frequent use).

### 2.3 Instance Groups Optimization

**What it is:** Configuring the number of model instances and their device placement for optimal throughput.

**Current vs recommended configuration:**

| Model               | Current  | Recommended                 | Rationale                                       |
| ------------------- | -------- | --------------------------- | ----------------------------------------------- |
| yolo26              | 1x GPU:0 | 1x GPU:0                    | Single detector, one-at-a-time frames           |
| clip                | 1x GPU:0 | 1x GPU:0                    | Dynamic batching handles throughput             |
| florence2           | 1x GPU:0 | 1x GPU:0                    | Autoregressive, no parallelism benefit          |
| reid                | 1x CPU   | 2x CPU                      | High batch traffic (multiple persons per frame) |
| pose                | 1x CPU   | 1x CPU                      | One frame at a time                             |
| threat              | 1x CPU   | 1x CPU                      | One frame at a time                             |
| vehicle             | 1x CPU   | 1x CPU                      | Low traffic                                     |
| depth               | 1x CPU   | 1x CPU                      | One frame at a time                             |
| demographics_age    | 1x CPU   | 1x CPU                      | Low traffic                                     |
| demographics_gender | 1x CPU   | 1x CPU                      | Low traffic                                     |
| pet                 | 1x CPU   | 1x CPU                      | Very low traffic                                |
| fashion_clip        | 1x CPU   | 1x CPU (with thread tuning) | Already has intra_op=4                          |
| xclip_action        | 1x CPU   | 1x CPU                      | Heavy, one clip at a time                       |

**Key insight:** For CPU models, increasing instance count trades memory for throughput. Since most CPU models are small (<100 MB), we could add a second instance for reid (which processes multiple person crops per frame).

**Implementation effort:** Very Low. Config change only.

### 2.4 CUDA MPS (Multi-Process Service)

**What it is:** CUDA MPS allows multiple CUDA processes to share a single GPU context, enabling concurrent kernel execution on different SMs. Without MPS, GPU processes are time-sliced; with MPS, they can run truly concurrently.

**Benefits for our setup:**

- yolo26, clip, and florence2 all share GPU 0. Without MPS, they are serialized via context switching.
- With MPS, small kernels from YOLO and CLIP could overlap, improving utilization from ~20% per-process to potentially ~60%.
- 50% cost reduction potential with only 7.5% performance impact (based on benchmarks).

**Limitations:**

- RTX A400 supports MPS (compute capability 8.9, Ada Lovelace).
- Memory isolation is reduced -- one model's OOM could crash all processes.
- Triton does not natively use MPS. MPS must be configured at the CUDA driver level (`nvidia-cuda-mps-control`), and Triton runs atop it.
- The A400's 4 GB is the real constraint. MPS improves compute sharing but does not increase available memory.

**Configuration:**

```bash
# Start MPS daemon before launching Triton
nvidia-cuda-mps-control -d

# Set memory limits per client
export CUDA_MPS_PINNED_DEVICE_MEM_LIMIT="0=3800MB"

# Launch Triton normally -- it will use MPS automatically
tritonserver --model-repository=/models
```

**Expected impact:** Marginal for our setup. The bottleneck on A400 is VRAM capacity, not compute utilization. MPS would help most if multiple GPU models received concurrent requests, but our pipeline is largely sequential (detect -> embed -> caption).

**Implementation effort:** Low. System-level daemon configuration.

**Applies to our setup:** Limited benefit. The sequential nature of our pipeline and VRAM constraint mean MPS provides minimal improvement. Would be more valuable if we had a larger GPU with underutilized compute.

### 2.5 Model Parallelism (GPU+CPU Splitting)

**What it is:** Splitting a single model across GPU and CPU, where compute-heavy layers run on GPU and less intensive layers run on CPU.

**Relevance to our models:**

- CLIP ViT-L/14 is the largest GPU model (~1.16 GB). Splitting it (e.g., first 12 layers on GPU, last 12 on CPU) could halve GPU memory usage.
- Florence-2 already runs via Python backend, making custom layer placement possible with PyTorch's `device_map`.

**Practical considerations:**

- ONNX Runtime supports multi-device execution through execution providers, but layer-level splitting requires custom session configuration.
- The CPU-GPU data transfer overhead may negate latency benefits for small models.
- More practical for CLIP than for YOLO (YOLO's entire forward pass is fast and benefits from staying on GPU).

**Expected impact:** Could save ~580 MB on GPU 0 by offloading half of CLIP to CPU, at the cost of ~2x inference latency for CLIP.

**Implementation effort:** High. Requires careful profiling, custom ONNX graph partitioning, and validation.

**Applies to our setup:** Potentially useful for CLIP if VRAM is the critical constraint. Not recommended for YOLO or Florence-2.

---

## 3. ONNX Runtime vs TensorRT vs OpenVINO

### 3.1 Framework Comparison for Our Models

#### GPU Models (3 models on A400)

| Framework                            | Strengths                             | Weaknesses                                                        | Fit for A400                         |
| ------------------------------------ | ------------------------------------- | ----------------------------------------------------------------- | ------------------------------------ |
| **ONNX Runtime + CUDA EP** (current) | Easy setup, good perf, dynamic shapes | ~10-30% slower than TRT                                           | Good -- currently working            |
| **ONNX Runtime + TRT EP**            | Near-TRT performance through ORT      | TRT engine building needs VRAM workspace                          | Risky on 4 GB A400                   |
| **TensorRT (native)**                | Best latency/throughput on NVIDIA     | Engine build requires workspace memory; A400 may OOM during build | Risky -- explicitly why we chose ORT |
| **ONNX Runtime + OpenVINO EP**       | N/A for GPU models on NVIDIA          | Intel-focused                                                     | Not applicable                       |

**Recommendation for GPU models:** Stay with ONNX Runtime + CUDA EP. The A400's 4 GB does not have enough workspace for TensorRT engine building (as noted in the yolo26 config). Consider TensorRT only if models are quantized to INT8 first (smaller engines, less workspace needed).

**Workaround for TRT:** Pre-build TRT engines on the A5500 (24 GB) and transfer to A400. TRT engines are GPU-architecture-specific but both are Ada Lovelace, so this may work if compute capabilities match.

#### CPU Models (10 models)

| Framework                           | Strengths                                | Weaknesses                           | Fit for CPU            |
| ----------------------------------- | ---------------------------------------- | ------------------------------------ | ---------------------- |
| **ONNX Runtime + CPU EP** (current) | Cross-platform, good default             | Not Intel-optimized                  | Good baseline          |
| **ONNX Runtime + OpenVINO EP**      | Best Intel CPU performance, VNNI/AVX-512 | Requires Intel CPU, separate package | Excellent if Intel CPU |
| **OpenVINO (native)**               | Maximum Intel optimization, INT8 auto    | Intel-only ecosystem                 | Excellent if Intel CPU |
| **ONNX Runtime + XNNPACK EP**       | ARM/mobile optimized                     | Not relevant for server              | Not applicable         |

**Key finding:** OpenVINO consistently outperforms default ONNX Runtime CPU EP on Intel hardware:

- YOLO models: 1.3-2x faster with OpenVINO (per Ultralytics benchmarks)
- ViT models: 1.5-2x faster with OpenVINO INT8 (per Intel benchmarks)
- ResNet models: 1.2-1.5x faster with OpenVINO

**Recommendation for CPU models:** If the host CPU is Intel (check with `lscpu`), switch to ONNX Runtime with OpenVINO Execution Provider. This is a drop-in replacement that works within Triton's `onnxruntime` backend:

```
# In config.pbtxt, add:
parameters {
  key: "execution_provider"
  value: { string_value: "openvino" }
}
```

The Triton ONNX Runtime backend supports OpenVINO EP natively. No model re-export needed.

### 3.2 ONNX Runtime Graph Optimization Levels

**What it is:** ONNX Runtime applies graph-level optimizations before inference:

| Level               | Optimizations                                   | Overhead       | Recommended              |
| ------------------- | ----------------------------------------------- | -------------- | ------------------------ |
| ORT_DISABLE_ALL     | None                                            | None           | Never                    |
| ORT_ENABLE_BASIC    | Constant folding, redundant node elimination    | Low            | Minimum                  |
| ORT_ENABLE_EXTENDED | + Complex fusions (attention, GELU, layer norm) | Medium         | Default for transformers |
| ORT_ENABLE_ALL      | + Layout optimizations (NCHW -> NCHWc for CPU)  | Higher startup | Best for CPU production  |

**Key insight:** Layout optimizations (only in ORT_ENABLE_ALL) are CPU-specific and can provide 10-30% speedup but require hardware compatibility. The optimized model should be saved offline to avoid repeated optimization at startup.

**Recommendation:** Use ORT_ENABLE_ALL with offline optimization for all CPU models. Pre-optimize ONNX models once, save the optimized versions, and load those at Triton startup (reduces startup time from ~30s to ~5s for all models).

```python
# Offline optimization script
import onnxruntime as ort
sess_options = ort.SessionOptions()
sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
sess_options.optimized_model_filepath = "model_optimized.onnx"
session = ort.InferenceSession("model.onnx", sess_options)
```

### 3.3 Hybrid Strategy Recommendation

| Model               | Current EP  | Recommended EP                          | Expected Speedup |
| ------------------- | ----------- | --------------------------------------- | ---------------- |
| yolo26              | CUDA        | CUDA (stay)                             | --               |
| clip                | CUDA        | CUDA (stay), or TRT if engine pre-built | 0-20%            |
| florence2           | Python/CUDA | Python/CUDA (stay)                      | --               |
| reid                | CPU         | OpenVINO (if Intel)                     | 1.3-2x           |
| pose                | CPU         | OpenVINO (if Intel)                     | 1.5-2x           |
| threat              | CPU         | OpenVINO (if Intel)                     | 1.5-2x           |
| vehicle             | CPU         | OpenVINO (if Intel)                     | 1.2-1.5x         |
| depth               | CPU         | OpenVINO (if Intel)                     | 1.3-1.8x         |
| demographics_age    | CPU         | OpenVINO (if Intel)                     | 1.5-2x           |
| demographics_gender | CPU         | OpenVINO (if Intel)                     | 1.5-2x           |
| pet                 | CPU         | OpenVINO (if Intel)                     | 1.2-1.5x         |
| fashion_clip        | CPU         | OpenVINO (if Intel)                     | 1.5-2x           |
| xclip_action        | Python/CPU  | Python/CPU (stay)                       | --               |

---

## 4. Emerging Serving Frameworks

### 4.1 NVIDIA Dynamo (Successor to Triton)

**What it is:** Announced at GTC 2025 (March 2025), NVIDIA Dynamo is a low-latency, modular open-source inference framework purpose-built for generative AI. As of March 18, 2025, NVIDIA Triton Inference Server has been integrated into the Dynamo platform as "Dynamo Triton."

**Key innovations:**

- **Disaggregated serving:** Separates prefill and decode phases of LLMs onto different GPUs, optimizing each independently.
- **Dynamic GPU scheduling:** Adds, removes, and reallocates GPUs in response to fluctuating workloads.
- **LLM-aware request routing:** Routes queries to specific GPUs that minimize computation.
- **Accelerated async data transfer:** Offloads inference data to cheaper memory/storage.

**Performance claims:**

- 2x performance for Llama models on Hopper GPUs.
- 30x throughput improvement for DeepSeek-R1 on GB200 NVL72.
- Supports PyTorch, SGLang, TensorRT-LLM, and vLLM.

**Applies to our setup:** Limited. Dynamo is designed for large-scale multi-GPU LLM inference (100s of GPUs). Our single-node, 2-GPU setup does not benefit from distributed scheduling. Triton (as part of Dynamo) remains the right choice for multi-model vision serving.

**Recommendation:** Monitor Dynamo development. When Dynamo Triton replaces standalone Triton in NVIDIA containers, migrate naturally. No active migration needed.

### 4.2 BentoML

**What it is:** An open-source framework for serving ML models with automatic adaptive batching, async serving, and efficient resource utilization. Known for fast cold starts (sub-second) and developer-friendly Python API.

**Comparison with Triton for our use case:**

| Feature                      | Triton                         | BentoML                        |
| ---------------------------- | ------------------------------ | ------------------------------ |
| Raw GPU inference throughput | Higher (2-3x for transformers) | Lower                          |
| CPU model serving            | Good                           | Good (with better autoscaling) |
| Multi-model pipeline         | Ensemble/BLS                   | Python DAGs                    |
| Dynamic batching             | Yes                            | Yes (adaptive)                 |
| Cold start time              | 10-30s                         | Sub-second                     |
| Model format support         | ONNX, TRT, TF, PyTorch, Python | Any Python-callable            |
| GPU memory management        | Rate limiter, instance groups  | Basic                          |
| Complexity                   | Higher                         | Lower                          |

**Applies to our setup:** Not recommended as a replacement. Triton's GPU inference throughput advantage and tight ONNX/TRT integration are critical for our VRAM-constrained setup. BentoML would be a step backward for GPU model performance.

**Recommendation:** Do not migrate.

### 4.3 Ray Serve

**What it is:** A scalable model serving library built on Ray, ideal for distributed AI applications with built-in autoscaling.

**Key advantage:** Ray Serve can wrap Triton as a backend while adding pipeline orchestration, autoscaling, and complex routing logic.

**Applies to our setup:** Overkill for single-node deployment. Ray Serve shines with distributed multi-node scaling. Our pipeline's sequential nature (detect -> classify -> embed -> caption) is well-served by Triton's ensemble/BLS without Ray's overhead.

**Recommendation:** Do not adopt. Consider only if scaling to multiple camera servers.

### 4.4 TensorRT-LLM for Nemotron

**What it is:** NVIDIA's optimized inference runtime for LLMs, with specific support for hybrid Mamba-Transformer architectures like Nemotron-H.

**Key findings (2025-2026):**

- TensorRT-LLM explicitly supports Nemotron-H models with paged heterogeneous KV head caching, batched streaming, and support for "linear" or "no-op" attention/FFN blocks in FP8.
- NVIDIA Nemotron Nano 2 (September 2025) is specifically optimized for TensorRT-LLM with efficient hybrid Mamba-Transformer inference.
- Nemotron-3-Nano-30B-A3B (our model) can be served via TensorRT-LLM alongside llama.cpp and vLLM.

**Expected impact:**

- FP8 quantization of attention layers could reduce LLM VRAM from ~22 GB to ~12-15 GB, freeing 7-10 GB on the A5500.
- Paged KV caching is optimized for the 6 attention layers (vs 46 Mamba layers), reducing memory fragmentation.
- Batched streaming improves throughput for concurrent requests.

**Concerns:**

- TensorRT-LLM has a larger memory footprint than llama.cpp during engine build.
- Engine building for 30B parameters requires significant temporary VRAM.
- llama.cpp's `--cache-prompt` is already efficient for our single-user scenario.

**Applies to our setup:** Potentially high impact but high risk. The A5500's 24 GB is already 95.9% utilized by llama.cpp. TensorRT-LLM could either improve this (FP8 = less VRAM) or make it worse (engine overhead). Requires careful benchmarking.

**Recommendation:** Benchmark TensorRT-LLM with FP8 quantization on the A5500. If VRAM usage drops below 18 GB, the freed memory could allow promoting some CPU models (CLIP? reid?) to GPU.

### 4.5 llama.cpp for Mamba-Transformer Hybrids

**What it is:** The current serving backend for Nemotron-3-Nano-30B-A3B.

**2025-2026 status:**

- llama.cpp supports hybrid Mamba-Transformer architectures (confirmed via Nemotron-3 model cards).
- Hardware-aware speculative decoding algorithms have been developed to accelerate Mamba inference.
- The hybrid architecture (6 attention + 46 Mamba layers) enables constant-memory inference for the Mamba layers, meaning KV cache only grows for the 6 attention layers.

**Current optimizations already applied:**

- `--cache-prompt` added to Dockerfile (not yet deployed per session notes).
- CTX_SIZE=32768 with PARALLEL=2 = 16K per slot.
- KV cache only for 6 attention layers (~192 MB).

**Potential additional optimizations:**

- Flash attention for the 6 attention layers (if not already enabled).
- FP8 quantization of attention weights (requires CUDA compute capability 8.9+ -- A5500 is 8.6, so FP8 is NOT natively supported on A5500's Ada Lovelace architecture. A5500 is actually Ampere, compute 8.6).
- Q4_K_M or Q5_K_M quantization of the full model (already likely in use given 22 GB fits in 24 GB).

**Applies to our setup:** Already in use. Deploy the `--cache-prompt` flag. Consider speculative decoding if a smaller draft model is available.

---

## 5. Model Cascading / Early Exit

### 5.1 Intelligent Model Cascading for Security Pipeline

**What it is:** Running models selectively based on the output of upstream models. Not every frame needs every model -- only relevant enrichment models should run based on what YOLO detects.

**Proposed cascade architecture:**

```
Frame Input
    |
    v
[YOLO26 Detection] (always runs)
    |
    +--> No detections? --> SKIP all enrichment (save 100% enrichment cost)
    |
    +--> Person detected?
    |       +--> [Pose Estimation] (threat assessment)
    |       +--> [ReID] (person tracking)
    |       +--> [Demographics] (age/gender)
    |       +--> [Fashion CLIP] (clothing description)
    |       +--> [Threat Detection] (weapon scan)
    |
    +--> Vehicle detected?
    |       +--> [Vehicle Classifier] (type identification)
    |
    +--> Animal detected?
    |       +--> [Pet Classifier] (cat/dog)
    |
    +--> Any detection?
            +--> [CLIP Embedding] (scene understanding)
            +--> [Depth Estimation] (spatial context)
            +--> [Florence-2 Captioning] (natural language description)
            +--> [X-CLIP Action] (if multi-frame buffer available)
```

**Expected savings per frame type:**

| Frame Content    | Models Run    | Models Skipped | Compute Saved |
| ---------------- | ------------- | -------------- | ------------- |
| Empty frame      | 1 (YOLO only) | 12             | ~92%          |
| Person only      | 7             | 5              | ~42%          |
| Vehicle only     | 5             | 7              | ~58%          |
| Person + Vehicle | 10            | 2              | ~17%          |
| Animal only      | 5             | 7              | ~58%          |

**Key insight from research:** In a typical home security scenario, 80-95% of frames contain no detections. Cascading would eliminate enrichment processing for the vast majority of frames.

**Implementation effort:** Medium. Requires modifying the enrichment pipeline (gateway/backend) to check YOLO outputs before dispatching to enrichment models. The current 90-second batch window naturally aligns with this -- batch only frames with detections.

**Applies to our setup:** Yes, this is the single highest-impact optimization. If 90% of frames are empty, cascading saves 90% of CPU model compute.

### 5.2 Confidence-Based Deferral (Gatekeeper Pattern)

**What it is:** Based on the NeurIPS 2025 "Gatekeeper" paper, a smaller model handles easy cases confidently while deferring hard cases to a larger model. Applied to our pipeline: lightweight classifiers handle obvious detections; uncertain cases escalate to Florence-2 or the LLM.

**Application to our pipeline:**

| Stage                 | Small Model (fast)          | Large Model (accurate)      | Deferral Criterion                        |
| --------------------- | --------------------------- | --------------------------- | ----------------------------------------- |
| Object classification | YOLO class label            | Florence-2 captioning       | YOLO confidence < 0.5                     |
| Person description    | Fashion CLIP + Demographics | LLM (Nemotron)              | Embedding distance > threshold            |
| Threat assessment     | Threat detector             | Pose + LLM reasoning        | Threat score in ambiguous range (0.3-0.7) |
| Scene understanding   | CLIP embedding cosine sim   | Florence-2 detailed caption | Low cosine sim to known scenes            |

**Expected impact:**

- Florence-2 invocations reduced by 60-80% (only called for ambiguous detections).
- LLM invocations could be reduced by 30-50% for obvious events (clear person walking vs. ambiguous shadow).
- GPU time on A400 freed for higher-priority YOLO processing.

**Research backing:** The Gatekeeper approach achieves LLM-level accuracy with up to 98% cost savings in cascaded inference. While those numbers are for text LLMs, the principle applies to our vision pipeline.

**Implementation effort:** Medium-High. Requires:

1. Defining confidence thresholds for each cascade stage.
2. Modifying the enrichment gateway to route requests based on upstream confidence.
3. Tuning thresholds on representative security data.

**Applies to our setup:** Yes, very high impact. The Florence-2 and LLM stages are the most expensive; reducing their invocation rate directly frees GPU time.

### 5.3 Adaptive Inference / Frame Skipping

**What it is:** Not every frame needs to be processed. Adaptive inference adjusts the processing rate based on scene activity.

**Strategies:**

| Strategy                | Description                                          | Latency Impact           | Compute Savings |
| ----------------------- | ---------------------------------------------------- | ------------------------ | --------------- |
| Temporal frame skipping | Process every Nth frame when scene is static         | +N frame latency         | 50-90%          |
| Motion-based triggering | Only process frames with significant pixel delta     | Minimal (motion = fast)  | 70-95%          |
| Key-frame detection     | Process I-frames and frames with high motion vectors | Depends on GOP structure | 60-80%          |
| Background subtraction  | Lightweight CPU pre-filter before YOLO               | +5-10ms                  | 50-80%          |

**Recommended approach for home security:**

1. **Background subtraction pre-filter:** Run OpenCV `BackgroundSubtractorMOG2` (CPU, <5ms) on every frame.
2. **Motion threshold:** Only send frames with >2% changed pixels to YOLO.
3. **Burst mode:** When motion is detected, process at full framerate for 10 seconds, then drop to 1 FPS.

**Expected impact:** For a typical home camera, 90%+ of frames are static. This alone could reduce YOLO invocations from 15 FPS to ~1-2 FPS during quiet periods, proportionally reducing all downstream model invocations.

**Implementation effort:** Low-Medium. Background subtraction is a mature OpenCV technique. Integrate at the camera ingestion layer (go2rtc or backend).

**Applies to our setup:** Yes, extremely high impact. This is complementary to model cascading and reduces the load on both GPU and CPU.

### 5.4 Triton BLS/Ensemble for Pipeline Orchestration

**What it is:** Triton Business Logic Scripting (BLS) allows implementing the cascade logic directly within Triton, using Python to control which models run based on upstream outputs.

**Ensemble vs BLS:**

| Feature        | Ensemble                             | BLS                           |
| -------------- | ------------------------------------ | ----------------------------- |
| Pipeline type  | Fixed DAG                            | Dynamic (conditionals, loops) |
| Model skipping | Not possible                         | Possible                      |
| Custom logic   | No                                   | Python code                   |
| Performance    | Slightly faster (no Python overhead) | Slightly slower               |
| Flexibility    | Low                                  | High                          |

**BLS is the right choice for our pipeline** because we need conditional model execution (cascading).

**Example BLS implementation:**

```python
# In a BLS model's execute():
import triton_python_backend_utils as pb_utils

def execute(self, requests):
    for request in requests:
        # Step 1: Always run YOLO
        yolo_request = pb_utils.InferenceRequest(
            model_name="yolo26", inputs=[...])
        yolo_response = yolo_request.exec()
        detections = parse_yolo_output(yolo_response)

        # Step 2: Cascade based on detections
        if has_person(detections):
            reid_request = pb_utils.InferenceRequest(
                model_name="reid", inputs=[...])
            # ... etc
        if has_vehicle(detections):
            vehicle_request = pb_utils.InferenceRequest(
                model_name="vehicle", inputs=[...])
```

**Expected impact:** Formalizes the cascade logic within Triton, eliminating network round-trips between the backend and individual models. Could reduce per-event processing latency by 20-40% compared to the current HTTP-based gateway routing.

**Implementation effort:** High. Requires rewriting the enrichment pipeline as a Triton BLS model. But this is the architecturally cleanest solution.

**Applies to our setup:** Yes, this is the recommended long-term architecture (as already proposed in the NVIDIA architecture proposal from the session notes).

---

## 6. Prioritized Implementation Roadmap

Sorted by impact-to-effort ratio, with specific applicability to our A400/A5500 + Triton setup.

### Tier 1: Quick Wins (1-3 days each, high impact)

| #   | Optimization                                 | Expected Impact                                | Effort   | Risk     |
| --- | -------------------------------------------- | ---------------------------------------------- | -------- | -------- |
| 1   | **Model cascading in enrichment gateway**    | 80-90% compute reduction for empty frames      | 2-3 days | Low      |
| 2   | **Triton rate limiter configuration**        | Prevent OOM, better GPU scheduling             | 1 day    | Very Low |
| 3   | **CLIP FP16 conversion**                     | ~580 MB VRAM saved on A400                     | 1 day    | Very Low |
| 4   | **Deploy `--cache-prompt` for llama.cpp**    | 20-40% faster LLM for repeated prompts         | 1 hour   | Very Low |
| 5   | **INT8 dynamic quantization of CPU models**  | 20-40% faster CPU inference, ~600 MB RAM saved | 1-2 days | Low      |
| 6   | **ORT_ENABLE_ALL with offline optimization** | 10-30% CPU model speedup, faster startup       | 1 day    | Very Low |

### Tier 2: Medium Effort, High Impact (1-2 weeks each)

| #   | Optimization                                                        | Expected Impact                      | Effort   | Risk   |
| --- | ------------------------------------------------------------------- | ------------------------------------ | -------- | ------ |
| 7   | **OpenVINO EP for CPU models** (if Intel CPU)                       | 1.3-2x CPU inference speedup         | 3-5 days | Low    |
| 8   | **Adaptive frame processing** (background subtraction)              | 50-90% reduction in YOLO invocations | 3-5 days | Low    |
| 9   | **Confidence-based deferral** (skip Florence-2/LLM for clear cases) | 60-80% fewer Florence-2 calls        | 1 week   | Medium |
| 10  | **Dynamic Florence-2 loading/unloading**                            | ~460 MB VRAM freed when idle         | 3-5 days | Medium |
| 11  | **INT8 static quantization with calibration** for YOLO + CLIP       | 10-20% faster GPU inference          | 1 week   | Medium |

### Tier 3: High Effort, Strategic (2-4 weeks each)

| #   | Optimization                                                    | Expected Impact                    | Effort    | Risk        |
| --- | --------------------------------------------------------------- | ---------------------------------- | --------- | ----------- |
| 12  | **Triton BLS pipeline** (replace HTTP gateway)                  | 20-40% latency reduction per event | 2-3 weeks | Medium      |
| 13  | **Knowledge distillation** (replace CLIP ViT-L with MobileCLIP) | ~1 GB VRAM freed                   | 2 weeks   | Medium-High |
| 14  | **TensorRT-LLM evaluation** for Nemotron                        | Potential 7-10 GB VRAM freed       | 2-3 weeks | High        |
| 15  | **Structured pruning** of ViT models (demographics)             | 1.5-2x CPU speedup                 | 2 weeks   | Medium      |

### Tier 4: Long-term / Experimental

| #   | Optimization                                             | Expected Impact           | Effort    | Risk   |
| --- | -------------------------------------------------------- | ------------------------- | --------- | ------ |
| 16  | **NAS model replacements** (MobileNetV4 for vehicle/pet) | 3-5x CPU speedup          | 3-4 weeks | Medium |
| 17  | **CLIP model parallelism** (split across GPU+CPU)        | ~580 MB VRAM freed        | 2-3 weeks | High   |
| 18  | **Custom early exit networks** via NAS                   | Dynamic compute per-input | 4+ weeks  | High   |
| 19  | **Migrate to Dynamo Triton** (when production-ready)     | Future-proofing           | TBD       | TBD    |

### Cumulative Impact Projection

| After Tier | GPU VRAM Freed (A400) | CPU Speedup | Compute Reduction     | Latency Improvement |
| ---------- | --------------------- | ----------- | --------------------- | ------------------- |
| Tier 1     | ~580 MB               | 20-40%      | 80-90% (empty frames) | 20-40%              |
| Tier 1+2   | ~1040 MB              | 2-3x        | 90-95% (empty frames) | 40-60%              |
| Tier 1+2+3 | ~2040 MB              | 3-5x        | 95%+ (empty frames)   | 50-70%              |

---

## References

### ONNX Runtime Quantization

- [ONNX Runtime Quantization Documentation](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)
- [ONNX Model Quantization (NVIDIA Model Optimizer)](https://deepwiki.com/NVIDIA/Model-Optimizer/4.1-onnx-model-quantization)
- [Selective Quantization Tuning for ONNX Models (arXiv, 2025)](https://arxiv.org/html/2507.12196v1)
- [ONNX 1.21 INT4 Types](https://onnx.ai/onnx/technical/int4.html)
- [Graph Optimizations in ONNX Runtime](https://onnxruntime.ai/docs/performance/model-optimizations/graph-optimizations.html)

### TensorRT

- [NVIDIA TensorRT SDK](https://developer.nvidia.com/tensorrt)
- [End-to-End AI: CUDA and TensorRT EPs in ONNX Runtime](https://developer.nvidia.com/blog/end-to-end-ai-for-nvidia-based-pcs-cuda-and-tensorrt-execution-providers-in-onnx-runtime/)

### OpenVINO

- [OpenVINO Execution Provider for ONNX Runtime](https://onnxruntime.ai/docs/execution-providers/OpenVINO-ExecutionProvider.html)
- [OpenVINO Performance Benchmarks](https://docs.openvino.ai/2025/about-openvino/performance-benchmarks.html)
- [OpenVINO 2025.4 Release Notes](https://www.intel.com/content/www/us/en/developer/articles/release-notes/openvino/2025-4.html)
- [Intel OpenVINO Export (Ultralytics)](https://docs.ultralytics.com/integrations/openvino/)

### Triton Inference Server

- [Triton Optimization Guide](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/optimization.html)
- [Triton Rate Limiter](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/rate_limiter.html)
- [Triton Model Management](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_management.html)
- [Triton Model Configuration](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_configuration.html)
- [Triton Ensemble Models](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/ensemble_models.html)
- [Serving ML Pipelines with Triton Ensembles (NVIDIA Blog)](https://developer.nvidia.com/blog/serving-ml-model-pipelines-on-nvidia-triton-inference-server-with-ensemble-models/)
- [Triton Model Analyzer](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_analyzer.html)

### NVIDIA Dynamo

- [NVIDIA Dynamo Framework](https://developer.nvidia.com/dynamo)
- [NVIDIA Dynamo Announcement (GTC 2025)](https://nvidianews.nvidia.com/news/nvidia-dynamo-open-source-library-accelerates-and-scales-ai-reasoning-models)
- [NVIDIA Dynamo Blog Post](https://developer.nvidia.com/blog/introducing-nvidia-dynamo-a-low-latency-distributed-inference-framework-for-scaling-reasoning-ai-models/)

### CUDA MPS

- [CUDA Multi-Process Service Overview](https://docs.nvidia.com/deploy/mps/index.html)
- [When to Use MPS](https://docs.nvidia.com/deploy/mps/when-to-use-mps.html)
- [MPS vs Dedicated GPU for LLM Inference (Pebble)](https://www.gopebble.com/case-studies/nvidia-mps-vs-dedicated-gpu-allocation-for-llm-inference)

### Knowledge Distillation

- [VL2Lite: Task-Specific KD from Large VLMs (CVPR 2025)](https://openaccess.thecvf.com/content/CVPR2025/papers/Jang_VL2Lite_Task-Specific_Knowledge_Distillation_from_Large_Vision-Language_Models_to_Lightweight_CVPR_2025_paper.pdf)
- [LKD-YOLOv8: Lightweight KD for Infrared Detection (MDPI, 2025)](https://www.mdpi.com/1424-8220/25/13/4054)
- [MoVE-KD: KD for VLMs with Mixture of Visual Encoders (CVPR 2025)](https://openaccess.thecvf.com/content/CVPR2025/papers/Cao_MoVE-KD_Knowledge_Distillation_for_VLMs_with_Mixture_of_Visual_Encoders_CVPR_2025_paper.pdf)

### Pruning

- [Vision Transformers on the Edge: Compression Survey (2025)](https://arxiv.org/html/2503.02891v1)
- [LPViT: Low-Power Semi-structured Pruning for ViT](https://arxiv.org/html/2407.02068v2)
- [FBP-ViT: Fine-grained Block Pruning for Vision Transformers (ICMR 2025)](https://dl.acm.org/doi/10.1145/3731715.3733341)
- [UPDP: Unified Progressive Depth Pruner for CNN and ViT](https://arxiv.org/html/2401.06426v1)

### Model Cascading / Adaptive Inference

- [Gatekeeper: Improving Model Cascades Through Confidence Tuning (NeurIPS 2025)](https://arxiv.org/abs/2502.19335)
- [Understanding and Optimizing Multi-Stage AI Inference Pipelines (MIT CSAIL, 2025)](https://people.csail.mit.edu/suvinay/pubs/2025.hermes.arxiv.pdf)
- [Hardware-aware NAS for Early Exiting Networks (2025)](https://arxiv.org/html/2512.04705v1)

### Nemotron / Mamba-Transformer

- [Nemotron-H: Hybrid Mamba-Transformer LLMs](https://research.nvidia.com/labs/adlr/nemotronh/)
- [The Mamba in the Llama: Distilling and Accelerating Hybrid Models (NeurIPS 2024)](https://arxiv.org/abs/2408.15237)
- [Hybrid Models as First-Class Citizens in vLLM (PyTorch Blog)](https://pytorch.org/blog/hybrid-models-as-first-class-citizens-in-vllm/)
- [NVIDIA Nemotron Nano 2 Technical Report (September 2025)](https://arxiv.org/abs/2508.14444)

### Framework Comparisons

- [Accelerating Deep Learning Inference: Comparative Analysis (MDPI Electronics, 2025)](https://www.mdpi.com/2079-9292/14/15/2977)
- [BentoML vs Ray Serve vs Triton (2026)](https://www.index.dev/skill-vs-skill/ai-bentoml-vs-ray-serve-vs-triton)
- [Top 10 AI Model Serving Frameworks 2025](https://www.devopsschool.com/blog/top-10-ai-model-serving-frameworks-tools-in-2025-features-pros-cons-comparison/)
- [Running Vision Models: VRAM Requirements and Optimization (2026)](https://dasroot.net/posts/2026/01/running-vision-models-vram-requirements/)
