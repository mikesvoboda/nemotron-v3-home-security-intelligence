# NVIDIA Technology Inventory

> **Generated:** 2026-02-19 | **Updated:** 2026-02-19 (post-improvement implementation)
> **Audit:** 10 research agents, 5 validation agents, 5 implementation agents, ~1.5M tokens
>
> Comprehensive audit of every NVIDIA-specific technology, library, and version number used throughout the nemotron-v3-home-security-intelligence codebase.

---

## Table of Contents

- [Hardware](#hardware)
- [Container Base Images](#container-base-images)
- [NVIDIA Software Products](#nvidia-software-products)
- [NVIDIA CUDA Python Packages](#nvidia-cuda-python-packages)
- [Nemotron LLM](#nemotron-llm)
- [llama.cpp (GGML CUDA Backend)](#llamacpp-ggml-cuda-backend)
- [NVIDIA Triton Inference Server](#nvidia-triton-inference-server)
- [NVIDIA TensorRT](#nvidia-tensorrt)
- [ONNX Runtime GPU](#onnx-runtime-gpu)
- [CUDA Infrastructure Modules](#cuda-infrastructure-modules)
- [GPU Passthrough & Container Toolkit](#gpu-passthrough--container-toolkit)
- [GPU Monitoring & Observability](#gpu-monitoring--observability)
- [Prometheus GPU Metrics](#prometheus-gpu-metrics)
- [GPU Alert Rules](#gpu-alert-rules)
- [NVIDIA Inference API](#nvidia-inference-api)
- [CI/CD GPU Integration](#cicd-gpu-integration)
- [Stale References](#stale-references)

---

## Hardware

| GPU              | Architecture | Compute Capability | VRAM  | Role                                    |
| ---------------- | ------------ | ------------------ | ----- | --------------------------------------- |
| NVIDIA RTX A5500 | Ampere       | sm_86              | 24 GB | GPU 0 -- LLM only                       |
| NVIDIA RTX A400  | Ampere       | sm_86              | 4 GB  | GPU 1 -- Triton (13 models, 76.5% VRAM) |

- **Host NVIDIA Driver:** 580.119.02 (minimum required: 580 for CUDA 13.1)
- **Host CUDA Version:** 13.0
- **Both GPUs are Ampere sm_86** -- the RTX A400 was previously misidentified as Turing sm_75 in legacy docs

---

## Container Base Images

| Container           | Base Image                                                   | CUDA             | cuDNN | PyTorch      |
| ------------------- | ------------------------------------------------------------ | ---------------- | ----- | ------------ |
| ai-llm (Nemotron)   | `docker.io/nvidia/cuda:13.1.1-devel-ubuntu22.04` (builder)   | **13.1.1**       | --    | --           |
| ai-llm (Nemotron)   | `docker.io/nvidia/cuda:13.1.1-runtime-ubuntu22.04` (runtime) | **13.1.1**       | --    | --           |
| ai-gateway (Triton) | `nvcr.io/nvidia/tritonserver:26.01-py3`                      | 12.8.0 (bundled) | --    | --           |
| ai-yolo26           | `nvcr.io/nvidia/tensorrt:26.01-py3`                          | bundled          | --    | --           |
| ai-clip             | `nvcr.io/nvidia/tensorrt:26.01-py3`                          | bundled          | --    | --           |
| ai-florence         | `docker.io/pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime`    | **12.4**         | **9** | **2.6.0**    |
| ai-enrichment       | `docker.io/pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime`    | **12.4**         | **9** | **2.4.0**    |
| ai-enrichment-light | `docker.io/pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime`    | **12.4**         | **9** | **2.4.0**    |
| ai-llm (HF variant) | `docker.io/nvidia/cuda:13.1.1-runtime-ubuntu22.04`           | **13.1.1**       | --    | cu121 wheels |
| vLLM (optional)     | `docker.io/vllm/vllm-openai:cu130-nightly`                   | **13.0**         | --    | --           |
| DCGM Exporter       | `nvcr.io/nvidia/k8s/dcgm-exporter:3.3.5-3.4.0-ubuntu22.04`   | --               | --    | --           |
| YOLO26 benchmark    | `nvcr.io/nvidia/tensorrt:24.09-py3`                          | bundled          | --    | --           |

---

## NVIDIA Software Products

| Technology                             | Version                                   | Source File                                          |
| -------------------------------------- | ----------------------------------------- | ---------------------------------------------------- |
| NVIDIA Triton Inference Server         | **26.01** (v2.54.0)                       | `ai/gateway/Dockerfile` line 1                       |
| NVIDIA TensorRT                        | **10.14.x** (bundled in 26.01 containers) | `ai/yolo26/Dockerfile`, `ai/clip/Dockerfile`         |
| NVIDIA CUDA Toolkit (LLM)              | **13.1.1**                                | `ai/nemotron/Dockerfile` lines 8, 71                 |
| NVIDIA CUDA Toolkit (PyTorch services) | **12.4**                                  | `ai/florence/Dockerfile`, `ai/enrichment/Dockerfile` |
| NVIDIA cuDNN                           | **9** (images) / **9.19.0.56** (pip)      | Dockerfiles, `requirements-audit.txt`                |
| NVIDIA DCGM                            | **3.3.5** (exporter **3.4.0**)            | `docker-compose.prod.yml` line 1150                  |
| NVIDIA Container Toolkit               | detected via `nvidia-ctk`                 | `setup_lib/nvidia_toolkit.py`                        |
| NVIDIA Driver (host)                   | **580.119.02** (minimum: 580)             | `setup_lib/nvidia_detect.py`                         |
| nvidia-ml-py (NVML bindings)           | **13.590.48**                             | `requirements-audit.txt`                             |
| tritonclient[grpc]                     | **>=2.42.0**                              | `ai/gateway/requirements.txt`                        |
| onnxruntime-gpu                        | **>=1.16.0**                              | Multiple requirements files                          |
| tensorrt (Python)                      | **>=10.0.0**                              | `ai/enrichment-light/requirements.txt`               |
| tensorrt-cu12 (Python)                 | **>=10.0.0**                              | `ai/enrichment-light/requirements.txt`               |
| bitsandbytes                           | **>=0.44.0**                              | `pyproject.toml` (quantization extra)                |
| paddlepaddle-gpu                       | **>=2.6.0,<3.0.0**                        | `ai/enrichment/requirements.txt`                     |
| triton (OpenAI kernel compiler)        | **3.6.0**                                 | `requirements-audit.txt` (torch transitive)          |
| llama.cpp                              | tag **b7972**                             | `ai/nemotron/Dockerfile` line 24                     |

---

## NVIDIA CUDA Python Packages

All packages are PyTorch transitive dependencies, pinned in `requirements-audit.txt`. Platform-conditional: `x86_64` Linux only.

| Package                  | Pinned Version | Pulled By                                                            |
| ------------------------ | -------------- | -------------------------------------------------------------------- |
| nvidia-cublas-cu12       | 12.9.1.4       | torch, nvidia-cudnn-cu12, nvidia-cusolver-cu12                       |
| nvidia-cuda-cupti-cu12   | 12.9.79        | torch                                                                |
| nvidia-cuda-nvrtc-cu12   | 12.9.86        | torch                                                                |
| nvidia-cuda-runtime-cu12 | 12.9.79        | torch                                                                |
| nvidia-cudnn-cu12        | 9.19.0.56      | torch                                                                |
| nvidia-cufft-cu12        | 11.4.1.4       | torch                                                                |
| nvidia-cufile-cu12       | 1.14.1.1       | torch                                                                |
| nvidia-curand-cu12       | 10.3.10.19     | torch                                                                |
| nvidia-cusolver-cu12     | 11.7.5.82      | torch                                                                |
| nvidia-cusparse-cu12     | 12.5.10.65     | torch, nvidia-cusolver-cu12                                          |
| nvidia-cusparselt-cu12   | 0.8.1          | torch                                                                |
| nvidia-nccl-cu12         | 2.29.3         | torch                                                                |
| nvidia-nvjitlink-cu12    | 12.9.86        | torch, nvidia-cufft-cu12, nvidia-cusolver-cu12, nvidia-cusparse-cu12 |
| nvidia-nvshmem-cu12      | 3.5.19         | torch                                                                |
| nvidia-nvtx-cu12         | 12.9.79        | torch                                                                |
| nvidia-ml-py             | 13.590.48      | home-security-intelligence (direct dep)                              |

> **Note:** The backend uses **CPU-only PyTorch** (`2.9.1+cpu`) via `[tool.uv] extra-index-url`. The nvidia-\*-cu12 packages appear in the audit export but are not installed in the backend virtualenv. They are installed inside the AI containers which use CUDA PyTorch from their base images.

---

## Nemotron LLM

### Production Model

- **Model:** NVIDIA Nemotron-3-Nano-30B-A3B
- **Architecture:** Hybrid Mamba-Transformer MoE (52 layers: 23 Mamba SSM, 23 MoE FFN, 6 GQA Attention)
- **Parameters:** 30B total / 3.5B active
- **Quantization:** Q4_K_M (GGUF)
- **File:** `Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf` (~9.5 GB)
- **VRAM:** ~14.7 GB
- **HuggingFace:** `nvidia/Nemotron-3-Nano-30B-A3B-GGUF`

### Development Model

- **Model:** Nemotron Mini 4B Instruct
- **File:** `nemotron-mini-4b-instruct-q4_k_m.gguf`
- **VRAM:** ~3 GB

### Available GGUF Quantizations

| Format     | File Size   | VRAM       | Quality                              |
| ---------- | ----------- | ---------- | ------------------------------------ |
| Q8_0       | ~17 GB      | ~22 GB     | Near-lossless reference              |
| Q6_K       | ~13 GB      | ~18 GB     | Excellent                            |
| Q5_K_M     | ~11 GB      | ~16 GB     | Very good                            |
| **Q4_K_M** | **~9.5 GB** | **~14 GB** | **Production default**               |
| IQ4_XS     | ~8.5 GB     | ~13 GB     | Best quality-per-bit at 4-bit        |
| Q4_K_S     | ~9.0 GB     | ~14 GB     | Slightly smaller than Q4_K_M         |
| Q3_K_M     | ~7.5 GB     | ~12 GB     | Compact, some quality loss           |
| Q2_K_L     | ~6.0 GB     | ~10 GB     | Aggressive, significant quality loss |

### NVIDIA-Provided Quantization Formats (HuggingFace)

| Format | Size   | Repository                                      |
| ------ | ------ | ----------------------------------------------- |
| BF16   | ~60 GB | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16`    |
| FP8    | ~30 GB | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8`     |
| NVFP4  | ~18 GB | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4`   |
| AWQ    | ~17 GB | `stelterlab/NVIDIA-Nemotron-3-Nano-30B-A3B-AWQ` |

> **Note:** All vLLM-compatible formats failed on RTX A5500: NVFP4 requires H100/A100, FP8 exceeds 24 GB, AWQ has vLLM Mamba-2 bug, BF16 requires 60 GB.

---

## llama.cpp (GGML CUDA Backend)

### Build Configuration

| Setting                               | Value                                    | File                                                |
| ------------------------------------- | ---------------------------------------- | --------------------------------------------------- |
| Git tag                               | **b7972**                                | `ai/nemotron/Dockerfile` line 24                    |
| Previous tag (superseded)             | 9496bbb80                                | evaluation docs                                     |
| CUDA base image (builder)             | `nvidia/cuda:13.1.1-devel-ubuntu22.04`   | `ai/nemotron/Dockerfile` line 8                     |
| CUDA base image (runtime)             | `nvidia/cuda:13.1.1-runtime-ubuntu22.04` | `ai/nemotron/Dockerfile` line 71                    |
| CMake flag                            | `-DGGML_CUDA=ON`                         | `ai/nemotron/Dockerfile` line 60                    |
| CMake flag                            | `-DGGML_CUDA_FA_ALL_QUANTS=ON`           | `ai/nemotron/Dockerfile` line 61                    |
| CMake flag                            | `-DGGML_NATIVE=ON`                       | `ai/nemotron/Dockerfile` line 63 (added 2026-02-19) |
| CUDA_ARCHITECTURES (deployed)         | `86`                                     | `.env` line 52                                      |
| CUDA_ARCHITECTURES (.env.example)     | `89`                                     | `.env.example` line 508                             |
| CUDA_ARCHITECTURES (default if empty) | `75,80,86,89`                            | Dockerfile comments                                 |

### Runtime Flags

```bash
llama-server \
    --model ${MODEL_PATH} \
    --host 0.0.0.0 --port ${PORT} \
    --n-gpu-layers ${GPU_LAYERS} \
    --ctx-size ${CTX_SIZE} \
    --parallel ${PARALLEL} \
    --threads ${THREADS} --threads-batch ${THREADS} \
    --batch-size ${BATCH_SIZE} \
    --ubatch-size ${UBATCH_SIZE} \
    --cache-type-k ${CACHE_TYPE_K} \
    --cache-type-v ${CACHE_TYPE_V} \
    --cont-batching \
    --metrics \
    --cache-reuse 256 \
    --mlock \
    --flash-attn on \
    ${MOE_ARGS}   # --override-tensor <pattern>=CPU (when set)
```

### Runtime Environment Variables

| Variable               | Dockerfile Default | Compose Default | Description                                                                                     |
| ---------------------- | ------------------ | --------------- | ----------------------------------------------------------------------------------------------- |
| `GPU_LAYERS`           | 35                 | auto            | Layers offloaded to GPU (999 = all). `.env.example` has single definition at line 361 (`auto`). |
| `CTX_SIZE`             | 32768              | 262144          | Context window tokens                                                                           |
| `PARALLEL`             | 2                  | 8               | Concurrent inference slots                                                                      |
| `THREADS`              | 4                  | 4               | CPU threads for offloaded layers                                                                |
| `BATCH_SIZE`           | 2048               | 2048            | Prompt processing batch size                                                                    |
| `UBATCH_SIZE`          | 512                | 512             | Micro-batch size                                                                                |
| `CACHE_TYPE_K`         | q8_0               | q8_0            | KV cache key quantization                                                                       |
| `CACHE_TYPE_V`         | q8_0               | q8_0            | KV cache value quantization                                                                     |
| `FLASH_ATTENTION`      | true               | true            | Enable Flash Attention (NEM-5369)                                                               |
| `CUDA_VISIBLE_DEVICES` | --                 | `${GPU_LLM:-0}` | Restrict to GPU 0                                                                               |
| `MOE_OFFLOAD_PATTERN`  | --                 | (empty)         | MoE expert CPU offload regex                                                                    |
| `GGML_CUDA_GRAPH_OPT`  | --                 | 1               | CUDA Graph optimization for up to 35% TPS improvement (added 2026-02-19)                        |

### Remaining Optimization Opportunity

| Flag          | Expected Impact                    | Status                                                    |
| ------------- | ---------------------------------- | --------------------------------------------------------- |
| `--merge-qkv` | 5-15% speedup for attention layers | Not in CMD -- needs validation against b7972 flag support |

---

## NVIDIA Triton Inference Server

### Server Configuration

| Setting            | Value                                             |
| ------------------ | ------------------------------------------------- |
| Image              | `nvcr.io/nvidia/tritonserver:26.01-py3` (v2.54.0) |
| Gateway port       | 8090 (FastAPI, external)                          |
| gRPC port          | 8001 (internal, inference)                        |
| HTTP port          | 8000 (internal, health checks)                    |
| Metrics port       | 8002 (Prometheus scrape)                          |
| CUDA memory pool   | 256 MB on GPU 0                                   |
| Pinned memory pool | 32 MB                                             |
| Rate limiter       | `execution_count`                                 |
| Model control      | `none` (all models loaded at startup)             |

### Triton Client

| Package              | Version  | Protocol   | File                          |
| -------------------- | -------- | ---------- | ----------------------------- |
| `tritonclient[grpc]` | >=2.42.0 | Async gRPC | `ai/gateway/triton_client.py` |

### Model Repository (15 models)

| Model                     | Backend          | Instance Kind | GPU | Max Batch    | Dynamic Batching    | Priority |
| ------------------------- | ---------------- | ------------- | --- | ------------ | ------------------- | -------- |
| yolo26                    | onnxruntime      | KIND_GPU      | [0] | 0 (static=1) | No                  | 1 (high) |
| clip (SigLIP 2)           | onnxruntime      | KIND_GPU      | [0] | 8            | Yes (1,2,4 / 50ms)  | 2        |
| florence2                 | python           | KIND_GPU      | [0] | 0            | No                  | --       |
| pose (YOLOv8n)            | onnxruntime      | KIND_GPU      | [0] | 0 (static=1) | No                  | 2        |
| threat (YOLOv8n)          | onnxruntime      | KIND_GPU      | [0] | 0 (static=1) | No                  | 1 (high) |
| reid (OSNet-AIN x1.0)     | onnxruntime      | KIND_GPU      | [0] | 16           | Yes (1,4,8 / 100ms) | 2        |
| pet (ResNet-18)           | onnxruntime      | KIND_GPU      | [0] | 8            | Yes (1,4,8 / 100ms) | 3        |
| depth (Depth Anything V2) | onnxruntime      | KIND_GPU      | [0] | 0 (static=1) | No                  | 3        |
| clip_text (SigLIP 2)      | onnxruntime      | KIND_CPU (x2) | CPU | 8            | Yes (1,4,8 / 50ms)  | 3        |
| fashion_clip              | onnxruntime      | KIND_CPU (x2) | CPU | 8            | Yes (1,4,8 / 100ms) | 3        |
| vehicle (ResNet-50)       | onnxruntime      | KIND_CPU (x2) | CPU | 8            | Yes (1,4,8 / 100ms) | 3        |
| demographics_age (ViT)    | onnxruntime      | KIND_CPU (x2) | CPU | 8            | Yes (1,4,8 / 100ms) | 3        |
| demographics_gender (ViT) | onnxruntime      | KIND_CPU (x2) | CPU | 8            | Yes (1,4,8 / 100ms) | 3        |
| xclip_action              | python           | KIND_CPU      | CPU | 0            | No                  | --       |
| stgcn_action (ST-GCN++)   | onnxruntime_onnx | KIND_CPU      | CPU | 0            | No                  | --       |

**Summary:** 8 GPU models, 7 CPU models. 12 use ONNX Runtime, 2 use Python backend, 1 uses `onnxruntime_onnx` platform. **No models use TensorRT backend in Triton.**

---

## NVIDIA TensorRT

### Version

- **TensorRT 10.14.x** (bundled in `nvcr.io/nvidia/tensorrt:26.01-py3`)
- Python package: `tensorrt>=10.0.0`, `tensorrt-cu12>=10.0.0`

### Current Status

TensorRT is **NOT active in Triton** -- all 15 Triton models use ONNX Runtime or Python backend. TensorRT IS used in:

1. **Standalone YOLO26 server** (`ai-yolo26` container) -- loads `yolo26m_fp16.engine`
2. **CLIP standalone server** -- disabled by default (`CLIP_USE_TENSORRT=false`)
3. **Export pipeline** -- `ai/gateway/export/export_all.sh` can generate TensorRT engines

### Engine Files (Generated at Runtime)

| Engine           | Path                                               | Precision | Size    |
| ---------------- | -------------------------------------------------- | --------- | ------- |
| YOLO26m          | `/models/yolo26/exports/yolo26m_fp16.engine`       | FP16      | ~43 MB  |
| YOLO26m INT8     | `/models/yolo26/exports/yolo26m_int8.engine`       | INT8      | --      |
| CLIP vision      | `/models/clip-vit-l/vision_encoder_fp16.engine`    | FP16      | ~600 MB |
| Pose (YOLOv8n)   | `.../yolov8n-pose/yolov8n-pose.engine`             | FP16      | --      |
| Threat (YOLOv8n) | `.../threat-detection-yolov8n/weights/best.engine` | FP16      | --      |
| FashionSigLIP    | `/models/cache/fashion_clip/1/model.plan`          | FP16      | --      |

### Conversion Strategy

Each export script tries `trtexec` first (pre-installed in NVIDIA containers), then falls back to the `tensorrt` Python API. Default workspace: 1 GB (tuned for 4 GB RTX A400).

### TensorRT Infrastructure Code

| Module                            | Purpose                                                       |
| --------------------------------- | ------------------------------------------------------------- |
| `ai/common/tensorrt_utils.py`     | `TensorRTConverter`, `TensorRTEngine`, GPU-hash-based caching |
| `ai/common/tensorrt_inference.py` | `TensorRTInferenceBase` ABC with PyTorch fallback             |
| `ai/tensorrt_prebuild.py`         | Startup validation (SM version + TensorRT version match)      |
| `ai/clip/tensorrt_inference.py`   | CLIP-specific TensorRT inference                              |
| `ai/clip/build_engine.py`         | Build-time engine generation                                  |
| `ai/yolo26/export_tensorrt.py`    | YOLO26 TensorRT export (FP16, INT8)                           |

### TensorRT Environment Variables

| Variable                      | Default                 | Description                        |
| ----------------------------- | ----------------------- | ---------------------------------- |
| `TENSORRT_ENABLED`            | `true`                  | Global toggle                      |
| `TENSORRT_PRECISION`          | `fp16`                  | Default precision (fp32/fp16/int8) |
| `TENSORRT_CACHE_DIR`          | `models/tensorrt_cache` | Engine cache directory             |
| `TENSORRT_MAX_WORKSPACE_SIZE` | 1 GB                    | Builder workspace                  |
| `TENSORRT_VERBOSE`            | `false`                 | Verbose logging                    |
| `CLIP_USE_TENSORRT`           | `false`                 | CLIP TensorRT toggle               |
| `THREAT_USE_TENSORRT`         | `false`                 | Threat detector TensorRT toggle    |
| `POSE_USE_TENSORRT`           | `false`                 | Pose estimator TensorRT toggle     |

### Key Limitation

`TensorrtExecutionProvider` (ONNX Runtime's TensorRT EP) is **never used** in this codebase. All TensorRT usage goes through:

1. The `tensorrt` Python package directly
2. Ultralytics `model.export(format="engine")`
3. `trtexec` subprocess

---

## ONNX Runtime GPU

### CUDAExecutionProvider Usage

All GPU-accelerated ONNX models use `CUDAExecutionProvider`, not `TensorrtExecutionProvider`:

```python
providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
```

Referenced in 6+ export scripts under `ai/gateway/export/`:

- `export_depth.py`, `export_vehicle.py`, `export_pet.py`
- `export_reid.py`, `export_fashion_clip.py`, `export_demographics.py`

### Packages

| Package           | Version           | Container                      |
| ----------------- | ----------------- | ------------------------------ |
| `onnxruntime-gpu` | >=1.16.0          | ai-clip, ai-enrichment-light   |
| `onnxruntime-gpu` | >=1.19.0          | YOLO26 benchmark               |
| `onnxruntime-gpu` | latest (unpinned) | ai-gateway                     |
| `onnx`            | >=1.12.0,<2.0.0   | ai-yolo26, ai-enrichment-light |
| `onnxslim`        | >=0.1.71          | ai-yolo26, ai-enrichment-light |

---

## CUDA Infrastructure Modules

Custom Python modules in `ai/` for GPU optimization:

| Module                         | NEM Ticket | Purpose                                                       |
| ------------------------------ | ---------- | ------------------------------------------------------------- |
| `ai/cuda_graph_manager.py`     | NEM-3771   | CUDA Graph capture/replay for repeated inference              |
| `ai/cuda_streams.py`           | NEM-3772   | CUDA Stream pool for parallel preprocessing                   |
| `ai/gpu_memory_pool.py`        | NEM-3772   | Pre-allocated tensor pools, LRU eviction (512 MB default)     |
| `ai/gpu_oom_handler.py`        | NEM-4996   | OOM detection, `torch.cuda.empty_cache()`, Prometheus counter |
| `ai/flash_attention_config.py` | --         | FlashAttention-2 config (requires Ampere SM >= 8.0)           |
| `ai/torch_optimizations.py`    | --         | Backend selection: tensorrt > torch_compile > none            |
| `ai/quantization_config.py`    | NEM-3810   | BitsAndBytes 4-bit/8-bit config for HF Nemotron               |
| `ai/static_kv_cache.py`        | --         | Memory-efficient KV cache reuse                               |

### CUDA Environment Variables

| Variable                 | Default | Description         |
| ------------------------ | ------- | ------------------- |
| `CUDA_GRAPHS_DISABLE`    | `0`     | Disable CUDA graphs |
| `CUDA_STREAMS_ENABLED`   | `true`  | Enable stream pool  |
| `CUDA_STREAMS_POOL_SIZE` | `3`     | Number of streams   |
| `CUDA_STREAMS_PRIORITY`  | `0`     | Stream priority     |

---

## GPU Passthrough & Container Toolkit

### CDI (Container Device Interface)

The project uses Podman CDI for rootless GPU access:

```yaml
# ai-llm: single GPU passthrough
devices:
  - nvidia.com/gpu=${GPU_LLM:-0}

# ai-gateway: ALL GPUs passed, CUDA_VISIBLE_DEVICES restricts
devices:
  - nvidia.com/gpu=all
environment:
  - CUDA_VISIBLE_DEVICES=${GPU_AI_SERVICES:-1}
```

**Critical CDI workaround:** Using `nvidia.com/gpu=N` only creates `/dev/nvidiaN`. If N>0, CUDA fails (expects `/dev/nvidia0`). Fix: use `nvidia.com/gpu=all` + `CUDA_VISIBLE_DEVICES=N`.

### GPU Assignment Variables (.env)

| Variable               | Default | Service                         |
| ---------------------- | ------- | ------------------------------- |
| `GPU_LLM`              | 0       | Nemotron LLM (A5500 24 GB)      |
| `GPU_AI_SERVICES`      | 1       | Triton / AI Gateway (A400 4 GB) |
| `GPU_FLORENCE`         | 0       | Florence-2 (standalone)         |
| `GPU_YOLO26`           | 1       | YOLO26 (standalone)             |
| `GPU_CLIP`             | 1       | CLIP (standalone)               |
| `GPU_ENRICHMENT`       | 1       | Enrichment heavy                |
| `GPU_ENRICHMENT_LIGHT` | 1       | Enrichment light                |

### NVIDIA Container Toolkit Detection

`setup_lib/nvidia_detect.py` and `setup_lib/nvidia_toolkit.py` handle:

- GPU detection via `nvidia-smi`
- Driver version validation (minimum 580 for CUDA 13.1)
- Container Toolkit detection (`nvidia-ctk`)
- CDI spec generation: `nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml`
- Per-distro install commands (Fedora/Debian/Ubuntu/Arch)

### Docker Compose GPU Deploy Blocks

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          device_ids: ['${GPU_LLM:-0}']
          capabilities: [gpu]
```

### Persistent CUDA Cache Volumes

| Volume                | Mount                | Purpose                             |
| --------------------- | -------------------- | ----------------------------------- |
| `llama-cache`         | `/home/llama/.cache` | llama.cpp compilation cache         |
| `llama-nv-cache`      | `/home/llama/.nv`    | NVIDIA CUDA JIT kernel cache        |
| `triton-kernel-cache` | `/root/.nv`          | Triton CUDA JIT compilation cache   |
| `triton-tmp-cache`    | `/tmp`               | TensorRT temp compilation artifacts |

---

## GPU Monitoring & Observability

### NVML / nvidia-ml-py (Primary)

**Package:** `nvidia-ml-py>=12.560.30,<14.0.0` (resolved: **13.590.48**)

Installed in all AI containers and the backend. Used by:

| Service                | File                                        | NVML Calls                                                                 |
| ---------------------- | ------------------------------------------- | -------------------------------------------------------------------------- |
| `GPUMonitor`           | `backend/services/gpu_monitor.py`           | 20+ NVML calls (utilization, memory, temp, power, clocks, PCIe, ECC, etc.) |
| `GpuDetectionService`  | `backend/services/gpu_detection_service.py` | Multi-GPU detection, compute capability, UUID                              |
| `PerformanceCollector` | `backend/services/performance_collector.py` | 5-second polling, WebSocket broadcast                                      |
| `gpu_oom_handler`      | `ai/gpu_oom_handler.py`                     | `torch.cuda.memory_allocated()`                                            |

### nvidia-smi (Fallback)

Used as secondary data source when pynvml is unavailable:

```bash
nvidia-smi --query-gpu=temperature.gpu,power.draw,utilization.gpu,memory.used,memory.total,name \
  --format=csv,noheader,nounits
```

### DCGM Exporter

| Setting         | Value                                                      |
| --------------- | ---------------------------------------------------------- |
| Image           | `nvcr.io/nvidia/k8s/dcgm-exporter:3.3.5-3.4.0-ubuntu22.04` |
| Port            | 9400                                                       |
| Profile         | `gpu-rootful` (disabled by default -- requires root)       |
| Custom counters | `monitoring/dcgm/custom-counters.csv`                      |

**DCGM Counter Fields:**

| Category      | Fields                                                                                                                             |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Clocks        | `DCGM_FI_DEV_SM_CLOCK`, `DCGM_FI_DEV_MEM_CLOCK`                                                                                    |
| Temperature   | `DCGM_FI_DEV_GPU_TEMP`, `DCGM_FI_DEV_MEMORY_TEMP`                                                                                  |
| Power         | `DCGM_FI_DEV_POWER_USAGE`, `DCGM_FI_DEV_TOTAL_ENERGY_CONSUMPTION`                                                                  |
| PCIe          | `DCGM_FI_DEV_PCIE_REPLAY_COUNTER`, `DCGM_FI_PROF_PCIE_TX_BYTES`, `DCGM_FI_PROF_PCIE_RX_BYTES`                                      |
| Utilization   | `DCGM_FI_DEV_GPU_UTIL`, `DCGM_FI_DEV_MEM_COPY_UTIL`, `DCGM_FI_DEV_ENC_UTIL`, `DCGM_FI_DEV_DEC_UTIL`                                |
| Memory        | `DCGM_FI_DEV_FB_FREE`, `DCGM_FI_DEV_FB_USED`                                                                                       |
| ECC           | `DCGM_FI_DEV_ECC_SBE_VOL_TOTAL`, `DCGM_FI_DEV_ECC_DBE_VOL_TOTAL`, `DCGM_FI_DEV_ECC_SBE_AGG_TOTAL`, `DCGM_FI_DEV_ECC_DBE_AGG_TOTAL` |
| Retired Pages | `DCGM_FI_DEV_RETIRED_SBE`, `DCGM_FI_DEV_RETIRED_DBE`, `DCGM_FI_DEV_RETIRED_PENDING`                                                |
| Errors        | `DCGM_FI_DEV_XID_ERRORS`                                                                                                           |

### Triton Native Metrics

Scraped from `ai-gateway:8002/metrics`:

- `nv_gpu_utilization`, `nv_gpu_memory_used_bytes`
- `nv_inference_request_success`, `nv_inference_request_failure`
- `nv_inference_queue_duration_us`, `nv_inference_compute_infer_duration_us`

---

## Prometheus GPU Metrics

### Scrape Jobs (`monitoring/prometheus.yml`)

| Job                   | Target                                                        | Interval | Metrics Prefix |
| --------------------- | ------------------------------------------------------------- | -------- | -------------- |
| `hsi-backend-metrics` | `backend:8000/api/metrics` (native Prometheus, **preferred**) | 15s      | `hsi_*`        |
| `hsi-gpu`             | `backend:8000/api/system/gpu` (via json-exporter)             | 10s      | `hsi_gpu_*`    |
| `dcgm-exporter`       | `host.containers.internal:9400`                               | 15s      | `DCGM_FI_*`    |
| `triton-metrics`      | `ai-gateway:8002/metrics`                                     | 15s      | `nv_*`         |

### HSI GPU Metrics (from backend API via json-exporter)

| Metric                                 | Type  | Description                |
| -------------------------------------- | ----- | -------------------------- |
| `hsi_gpu_utilization`                  | gauge | GPU compute utilization %  |
| `hsi_gpu_memory_used_mb`               | gauge | VRAM used (MB)             |
| `hsi_gpu_memory_total_mb`              | gauge | Total VRAM (MB)            |
| `hsi_gpu_temperature`                  | gauge | Temperature (C)            |
| `hsi_gpu_fan_speed`                    | gauge | Fan speed 0-100%           |
| `hsi_gpu_sm_clock_mhz`                 | gauge | Current SM clock           |
| `hsi_gpu_memory_clock_mhz`             | gauge | Memory clock               |
| `hsi_gpu_sm_clock_max_mhz`             | gauge | Max SM clock               |
| `hsi_gpu_memory_clock_max_mhz`         | gauge | Max memory clock           |
| `hsi_gpu_memory_bandwidth_utilization` | gauge | Memory controller %        |
| `hsi_gpu_pstate`                       | gauge | Performance state (P0-P15) |
| `hsi_gpu_throttle_reasons`             | gauge | Throttle reason bitfield   |
| `hsi_gpu_power_limit_watts`            | gauge | Power limit (W)            |
| `hsi_gpu_compute_processes`            | gauge | Active compute processes   |
| `hsi_gpu_pcie_replay_counter`          | gauge | PCIe error counter         |
| `hsi_gpu_temp_slowdown_threshold`      | gauge | Slowdown threshold (C)     |
| `hsi_gpu_pcie_link_gen`                | gauge | PCIe generation (1-4)      |
| `hsi_gpu_pcie_link_width`              | gauge | PCIe link width            |
| `hsi_gpu_pcie_tx_throughput_kbs`       | gauge | PCIe TX (KB/s)             |
| `hsi_gpu_pcie_rx_throughput_kbs`       | gauge | PCIe RX (KB/s)             |
| `hsi_gpu_encoder_utilization`          | gauge | Video encoder %            |
| `hsi_gpu_decoder_utilization`          | gauge | Video decoder %            |
| `hsi_gpu_bar1_used_mb`                 | gauge | BAR1 memory (MB)           |
| `hsi_inference_fps`                    | gauge | Inference FPS              |

### AI Service GPU Metrics

| Metric                                | Source          | Type    |
| ------------------------------------- | --------------- | ------- |
| `yolo26_vram_bytes`                   | YOLO26 service  | gauge   |
| `yolo26_gpu_utilization_percent`      | YOLO26 service  | gauge   |
| `yolo26_gpu_memory_used_gb`           | YOLO26 service  | gauge   |
| `yolo26_gpu_temperature_celsius`      | YOLO26 service  | gauge   |
| `yolo26_gpu_power_watts`              | YOLO26 service  | gauge   |
| `ai_gpu_oom_total`                    | All AI services | counter |
| `enrichment_vram_usage_bytes`         | Enrichment      | gauge   |
| `enrichment_vram_budget_bytes`        | Enrichment      | gauge   |
| `enrichment_vram_utilization_percent` | Enrichment      | gauge   |

### Grafana Dashboard

`monitoring/grafana/dashboards/hsi-gpu-metrics.json` -- GPU dashboard with panels for utilization, VRAM, temperature, power, clocks, PCIe throughput, and memory bandwidth.

---

## GPU Alert Rules

### DCGM-Based Alerts (`monitoring/gpu-alerts.yml`)

| Alert                         | Expression               | Duration | Severity |
| ----------------------------- | ------------------------ | -------- | -------- |
| `GPUMemoryNearFull`           | VRAM > 90%               | 2m       | critical |
| `GPUMemoryHigh`               | VRAM > 80%               | 5m       | warning  |
| `GPUHighTemperature`          | temp > 85 C              | 5m       | critical |
| `GPUTemperatureElevated`      | temp > 75 C              | 10m      | warning  |
| `GPUUtilizationSaturated`     | util > 95%               | 15m      | warning  |
| `GPUUnderutilizedMemoryBound` | GPU < 30% AND MEM > 70%  | 5m       | warning  |
| `GPUMemoryBandwidthSaturated` | MEM > 90%                | 10m      | warning  |
| `GPUHighPowerUsage`           | power > 350W             | 10m      | warning  |
| `GPUClockSpeedDegraded`       | SM < 1200 AND util > 50% | 5m       | warning  |
| `DCGMExporterDown`            | exporter down            | 2m       | critical |
| `NoGPUMetrics`                | exporter up, no data     | 5m       | warning  |

### AI Pipeline GPU Alerts (`monitoring/ai-pipeline-alerts.yml`)

| Alert         | Expression                              | Duration | Severity |
| ------------- | --------------------------------------- | -------- | -------- |
| GPU OOM       | `rate(ai_gpu_oom_total[5m]) > 0`        | 5m       | critical |
| VRAM Warning  | `hsi_gpu_memory_used_mb / total > 0.9`  | 5m       | warning  |
| VRAM Critical | `hsi_gpu_memory_used_mb / total > 0.95` | 2m       | critical |

### Backend Performance Thresholds (`backend/services/performance_collector.py`)

| Metric          | Warning | Critical |
| --------------- | ------- | -------- |
| GPU temperature | 75 C    | 85 C     |
| GPU utilization | 90%     | 98%      |
| GPU VRAM        | 90%     | 95%      |
| GPU power       | 300W    | 350W     |

---

## NVIDIA Inference API

Used for media generation (not AI inference pipeline):

| Script                                    | API                                | Purpose                         |
| ----------------------------------------- | ---------------------------------- | ------------------------------- |
| `scripts/generate_architecture_images.sh` | `https://inference-api.nvidia.com` | Architecture diagram generation |
| `scripts/generate_videos.sh`              | `https://inference-api.nvidia.com` | Veo 3.1 video generation        |

Requires `NVIDIA_API_KEY` or `NVAPIKEY` environment variable.

---

## CI/CD GPU Integration

### GitHub Actions Workflows

| Workflow          | Runner                          | GPU Tests                                   |
| ----------------- | ------------------------------- | ------------------------------------------- |
| `gpu-tests.yml`   | `[self-hosted, gpu, rtx-a5500]` | `uv run pytest backend/tests/gpu/ -m "gpu"` |
| `nightly.yml`     | `[self-hosted, gpu, rtx-a5500]` | Nightly GPU test suite                      |
| `build-setup.yml` | --                              | Bundles `setup_lib.nvidia_detect`           |
| `deploy.yml`      | --                              | "NVIDIA CUDA - amd64 only" builds           |

### GPU Runner Setup (`scripts/setup-gpu-runner.sh`)

Tests GPU with multiple CUDA images: `nvidia/cuda:12.0.0`, `12.2.0`, `11.8.0` on Ubuntu 22.04. Installs `nvidia-container-toolkit` and registers runner with labels `self-hosted,linux,gpu,rtx-a5500`.

---

## Why ONNX Runtime Was Chosen Over TensorRT

TensorRT was the **original design** for 5 of the 15 Triton models. The decision to use ONNX Runtime instead was not made upfront -- it evolved through practical hardware constraints discovered during implementation.

### Decision Timeline

| Date       | Commit     | Event                                                                                                                                                                                                                   |
| ---------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-01-26 | `75d6aa35` | Triton infrastructure introduced. Original design: `tensorrt_plan` backend for yolo26, clip, pose, threat, fashion_clip.                                                                                                |
| 2026-01-26 | `a5e47aa2` | Standalone YOLO26 using TensorRT FP16 benchmarked at 5.76ms / 174 FPS on A5500.                                                                                                                                         |
| 2026-01-27 | `e1e29656` | ONNX packages added to yolo26 requirements -- A400 workspace issues surfacing.                                                                                                                                          |
| 2026-02-08 | `8c358978` | **Key decision point.** CLIP/FashionCLIP switched from `tensorrt_plan` to `onnxruntime` -- "4GB A400 too small for trtexec workspace." YOLO26 config converted from 143-line TensorRT config to ONNX Runtime.           |
| 2026-02-08 | `3710a98c` | NEM-5547: INT8 ONNX quantization attempted for YOLO26. Failed -- `ConvInteger` ops unsupported by CUDAExecutionProvider. NEM-5551: All models promoted to GPU using FP32 ONNX + CUDA EP instead. "All 15 models READY." |
| 2026-02-08 | `af227b5a` | NEM-5561-5567: Model upgrades (SigLIP 2, OSNet-AIN, ST-GCN++). ONNX Runtime on GPU confirmed as the long-term approach.                                                                                                 |
| 2026-02-13 | `18dcedeb` | NEM-5560: Rate limiter with `execution_count` mode added. YOLO26 priority=1 in instance_group. ONNX Runtime backend fully optimized.                                                                                    |

### Root Causes (4 Blocking Issues)

**1. A400 workspace memory constraint (primary blocker)**

The `trtexec` builder for CLIP and similar large models needs workspace memory that competes with the total 4GB VRAM on the RTX A400. Building TensorRT engines on a 4GB GPU with Triton + other models loaded causes OOM. Discovered during Phase 2 of migration, not anticipated in the design phase.

> Source: commit `8c358978` -- "CLIP/Fashion-CLIP: switch from TensorRT to ONNX Runtime (4GB A400 too small for trtexec workspace)."

**2. INT8 ConvInteger operator incompatibility (NEM-5547)**

`onnxruntime.quantization` inserts `ConvInteger` nodes into INT8 graphs. ONNX Runtime's `CUDAExecutionProvider` does not support `ConvInteger` -- it is a CPU-only operator. INT8 ONNX on GPU either fails to load or silently falls back to CPU. TensorRT's native INT8 path supports this, but returns to the workspace OOM problem.

> Source: commit `3710a98c` -- "yolo26: Use FP32 ONNX on GPU (INT8 ConvInteger ops unsupported by CUDA EP)." Preserved in current `config.pbtxt` line 7.

**3. Ultralytics .engine metadata wrapper incompatibility**

Pose and threat models exported via Ultralytics as `.engine` files have a metadata wrapper incompatible with Triton's `tensorrt` backend, which expects raw engine files without the Ultralytics envelope.

> Source: commit `3710a98c` -- "pose/threat: Use ONNX Runtime on GPU (not TensorRT -- Ultralytics .engine format has metadata wrapper incompatible with Triton's tensorrt backend)."

**4. Florence-2 and X-CLIP cannot be exported to TensorRT/ONNX**

Florence-2's autoregressive decoder and X-CLIP's custom cross-frame attention prevent static graph export. Both require the Python backend.

> Source: `ai/triton/model_repository/florence2/config.pbtxt` line 3, `xclip_action/config.pbtxt` line 3.

### Performance Comparison

| Backend                  | Typical Latency    | VRAM Overhead             | Build Time           | Portability    |
| ------------------------ | ------------------ | ------------------------- | -------------------- | -------------- |
| **TensorRT**             | 1x (fastest)       | High (workspace + engine) | Minutes per model    | sm_XX specific |
| **ONNX Runtime CUDA EP** | ~1.3-1.5x TensorRT | Low (ONNX file only)      | None (load directly) | Any GPU        |
| **ONNX Runtime CPU**     | ~3-5x TensorRT     | Zero GPU                  | None                 | Any CPU        |

The evaluation docs noted "near-TensorRT performance" from ONNX Runtime CUDA EP, making it an acceptable tradeoff given the A400's 4GB constraint. The standalone YOLO26 server on GPU 0 (A5500 24GB) continues to use native TensorRT where workspace is not a constraint.

### Future Path: TensorRT Execution Provider (Research Complete 2026-02-19)

Research confirmed that `TensorrtExecutionProvider` can be enabled as a **config-only change** in Triton's ONNX Runtime backend. The Triton 26.01 container already ships with TensorRT linked into the ORT backend. No model re-export needed.

**Recommended rollout (Wave 1 -- static-batch, lowest risk):**

Add this block to `threat/config.pbtxt`, `pose/config.pbtxt`, and `yolo26/config.pbtxt`:

```protobuf
optimization {
  execution_accelerators {
    gpu_execution_accelerator : [
      {
        name : "tensorrt"
        parameters { key: "precision_mode"           value: "FP16" }
        parameters { key: "max_workspace_size_bytes"  value: "268435456" }
        parameters { key: "trt_engine_cache_enable"   value: "1" }
        parameters { key: "trt_engine_cache_path"     value: "/models/cache/trt_engines" }
      }
    ]
  }
}
```

**Wave 2 (dynamic-batch, needs shape profiles):** `pet`, `reid`, `clip` -- add `trt_min_shapes`/`trt_opt_shapes`/`trt_max_shapes` parameters.

**Skip:** `depth` (hardcoded Reshape in DPT head), `florence2`/`xclip_action` (Python backend), all CPU models.

**Expected gains:** 1.5-2x inference speedup for YOLO models, ~2x for classification models. First startup slow (~5-15 min per model for TRT compilation), cached on subsequent runs.

**Rollback:** Remove the `optimization` block. ONNX files unchanged, zero-risk revert.

Other hardware paths remain viable:

- Upgrading GPU 1 to >=8GB VRAM would unblock native `trtexec` workspace
- Pre-building engines outside Triton (one-shot container) could produce raw `.plan` files

---

## Stale References

### Fixed (2026-02-19)

The following stale references were identified during the audit and corrected:

| Reference                        | Location                                        | Fix Applied                                    |
| -------------------------------- | ----------------------------------------------- | ---------------------------------------------- |
| `tritonserver:24.01-py3`         | `ai/triton/AGENTS.md` line 116                  | Updated to `26.01-py3`                         |
| `tensorrt:24.09-py3` OCI labels  | `ai/yolo26/Dockerfile` lines 26-27              | Updated to `26.01-py3`                         |
| `nvidia/cuda:13.1.0` (x4)        | `ai/nemotron/AGENTS.md` lines 12, 156, 162, 414 | Updated to `13.1.1`                            |
| `commit 9496bbb80`               | `ai/nemotron/AGENTS.md` line 157                | Updated to tag `b7972`                         |
| RTX A400 = sm_75                 | `.env.example` line 471                         | Moved A400 to sm_86 line                       |
| `pytorch/pytorch:2.4.0-cuda12.4` | `ai/clip/AGENTS.md` line 73                     | Updated to `nvcr.io/nvidia/tensorrt:26.01-py3` |
| Duplicate `GPU_LAYERS=48`        | `.env.example` line 541                         | Removed duplicate, kept `auto` at line 361     |

### Remaining (In Docs/Plans Only)

| Reference                              | Location                                              | Notes                                  |
| -------------------------------------- | ----------------------------------------------------- | -------------------------------------- |
| `tritonserver:25.01-py3`               | `docs/plans/triton-migration.md`                      | Historical plan doc, not active config |
| `tritonserver:24.09-trtllm-python-py3` | `docs/plans/2026-01-31-llm-inference-optimization.md` | TRT-LLM plan, never deployed           |

---

## VRAM Budget Summary

| Component                         | VRAM (MB) | GPU           |
| --------------------------------- | --------- | ------------- |
| Nemotron-3-Nano-30B Q4_K_M        | ~14,700   | GPU 0 (A5500) |
| KV cache (Q8_0, 32K ctx, 2 slots) | ~192      | GPU 0         |
| Triton CUDA context overhead      | ~300      | GPU 1 (A400)  |
| SigLIP 2 Base (CLIP replacement)  | ~178      | GPU 1         |
| Depth Anything V2 Tiny            | ~101      | GPU 1         |
| YOLOv8n-pose                      | ~14       | GPU 1         |
| YOLOv8n threat                    | ~12       | GPU 1         |
| ResNet-18 pet                     | ~45       | GPU 1         |
| OSNet-AIN x1.0 ReID               | ~9        | GPU 1         |
| Florence-2 Base (FP16)            | ~460      | GPU 1         |
| YOLO26m FP32 ONNX                 | ~100      | GPU 1         |
| Enrichment on-demand budget       | 6,000     | GPU 0 (heavy) |

---

## Improvements Applied (2026-02-19)

Changes implemented as a result of this audit:

### Performance Optimizations

| Change                            | File                               | Impact                                             |
| --------------------------------- | ---------------------------------- | -------------------------------------------------- |
| Added `GGML_CUDA_GRAPH_OPT=1`     | `docker-compose.prod.yml` line 180 | Up to 35% LLM token generation speedup             |
| Added `-DGGML_NATIVE=ON` to CMake | `ai/nemotron/Dockerfile` line 63   | Native CPU optimizations for MoE expert offloading |

### INT8 Quantization Infrastructure

| Change                                                                              | File                                    | Impact                                                    |
| ----------------------------------------------------------------------------------- | --------------------------------------- | --------------------------------------------------------- |
| Added `VEHICLE_QUANTIZED`, `DEMOGRAPHICS_QUANTIZED`, `QUANTIZED_MODEL_DIR` env vars | `docker-compose.prod.yml` lines 319-324 | Enables INT8 quantization for vehicle/demographics models |
| Added `/models/quantized` volume mount                                              | `docker-compose.prod.yml` line 308      | Quantized model storage                                   |
| Added quantization documentation                                                    | `ai/gateway/export/export_all.sh`       | Step-by-step INT8 deployment instructions                 |

### Documentation Fixes (7 Stale References)

| Fix                                              | File                    |
| ------------------------------------------------ | ----------------------- |
| `tritonserver:24.01-py3` -> `26.01-py3`          | `ai/triton/AGENTS.md`   |
| `cuda:13.1.0` -> `13.1.1` (x4 occurrences)       | `ai/nemotron/AGENTS.md` |
| `commit 9496bbb80` -> `tag b7972`                | `ai/nemotron/AGENTS.md` |
| `tensorrt:24.09-py3` -> `26.01-py3` (OCI labels) | `ai/yolo26/Dockerfile`  |
| RTX A400 moved from sm_75 to sm_86               | `.env.example`          |
| Base image updated to `tensorrt:26.01-py3`       | `ai/clip/AGENTS.md`     |
| Removed duplicate `GPU_LAYERS=48`                | `.env.example`          |

### Research Completed (Pending Implementation)

| Finding                                   | Recommendation                                                                       | Risk                                                       |
| ----------------------------------------- | ------------------------------------------------------------------------------------ | ---------------------------------------------------------- |
| TensorRT Execution Provider               | Config-only change in Triton config.pbtxt for 6 GPU models. 1.5-2x speedup expected. | Low (Wave 1: static-batch), Medium (Wave 2: dynamic-batch) |
| PyTorch 2.4.0 -> 2.6.0 (enrichment-light) | **GO** -- no blockers, safe to upgrade                                               | Low                                                        |
| PyTorch 2.4.0 -> 2.6.0 (enrichment-heavy) | **BLOCKED** by `paddlepaddle-gpu` CUDA library conflicts                             | High -- requires PaddlePaddle isolation or compat fix      |
