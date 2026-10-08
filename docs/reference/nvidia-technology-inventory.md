# NVIDIA Technology Inventory

> Every NVIDIA-specific technology, library and version number in the
> nemotron-v3-home-security-intelligence codebase, measured against this working
> tree on 2026-10-02. The shipped stack is one Triton gateway and one llama.cpp
> VLM serve: two AI services, three Triton model directories, three in-process
> ONNX lookup legs.
>
> Each row names the file the value comes from. A row whose source file is
> missing from the tree is marked.

---

## Table of Contents

- [Hardware](#hardware)
- [Container Base Images](#container-base-images)
- [NVIDIA Software Products](#nvidia-software-products)
- [NVIDIA CUDA Python Packages](#nvidia-cuda-python-packages)
- [llama.cpp VLM Serve](#llamacpp-vlm-serve)
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

---

## Hardware

The two hosts the AI images are built for:

| Target host              | Architecture | Compute capability | Driver in code                                                   | Runs                           |
| ------------------------ | ------------ | ------------------ | ---------------------------------------------------------------- | ------------------------------ |
| NVIDIA GB300 (aarch64)   | Blackwell    | sm_103 (CC 10.3)   | 610.57.04 recorded in `ai/vlm/Dockerfile:57`                     | `CUDA_ARCHITECTURES=103` build |
| NVIDIA RTX A5500 (24 GB) | Ampere       | sm_86              | `MINIMUM_DRIVER_VERSION = 580` (`setup_lib/nvidia_detect.py:38`) | `CUDA_ARCHITECTURES=86` build  |

- **Driver floor:** 580, for CUDA 13.x (`setup_lib/nvidia_detect.py:38`, with the
  `nvidia-driver-565` purge guard at `:48-58`).
- **One Dockerfile, two hosts:** `docker-compose.prod.yml:153-160` passes
  `CUDA_ARCHITECTURES: ${CUDA_ARCHITECTURES:-}` into the `ai/vlm` build context;
  `ai/vlm/Dockerfile:59-60` states the same contract — GB300 dev passes `103`,
  the A5500 bring-up passes `86`, unchanged.
- **GPU 1 sizing:** the export helpers are tuned against a 4 GB card on the
  second slot — `ai/gateway/export/README.md:75` (`--workspace-gb` default of
  1 GB "tuned for the 4 GB RTX A400 on GPU 1") and
  `ai/gateway/export/export_yolo_pose.py:172`.

---

## Container Base Images

| Container          | Base Image                                                 | Source                         |
| ------------------ | ---------------------------------------------------------- | ------------------------------ |
| `ai-vlm` (builder) | `docker.io/nvidia/cuda:13.3.1-devel-ubuntu22.04`           | `ai/vlm/Dockerfile:19`         |
| `ai-vlm` (runtime) | `docker.io/nvidia/cuda:13.3.1-runtime-ubuntu22.04`         | `ai/vlm/Dockerfile:86`         |
| `ai-gateway`       | `nvcr.io/nvidia/tritonserver:26.01-py3`                    | `ai/gateway/Dockerfile:1`      |
| `ai-llm-vllm`      | `docker.io/vllm/vllm-openai:cu130-nightly`                 | `docker-compose.prod.yml:291`  |
| `dcgm-exporter`    | `nvcr.io/nvidia/k8s/dcgm-exporter:3.3.5-3.4.0-ubuntu22.04` | `docker-compose.prod.yml:1375` |

| Service         | Compose profile | Publishes                             | `deploy` limits          | GPU device                                                          |
| --------------- | --------------- | ------------------------------------- | ------------------------ | ------------------------------------------------------------------- |
| `ai-gateway`    | none (default)  | `127.0.0.1:8090`, `127.0.0.1:8002`    | 8 CPU / 20G, reserve 10G | `nvidia.com/gpu=all` + `CUDA_VISIBLE_DEVICES=${GPU_AI_SERVICES:-1}` |
| `ai-vlm`        | none (default)  | `127.0.0.1:${AI_VLM_PORT:-8098}:8098` | 4 CPU / 10G, reserve 4G  | `nvidia.com/gpu=${GPU_LLM:-0}`                                      |
| `ai-llm-vllm`   | `vllm`          | 8097                                  | --                       | `${GPU_LLM:-0}`                                                     |
| `dcgm-exporter` | `gpu-rootful`   | 9400                                  | --                       | --                                                                  |

`ai-vlm` is in the default compose set (UR-18; until then it sat behind a
profile that had to be named explicitly), so a plain bring-up starts it:

```bash
podman compose -f docker-compose.prod.yml up -d ai-gateway ai-vlm
```

Weights are host-mounted, never baked:
`${AI_MODELS_PATH:-/export/ai_models}/vlm:/models:ro`
(`docker-compose.prod.yml:170`).

---

## NVIDIA Software Products

| Technology                         | Version                                        | Source File                                           |
| ---------------------------------- | ---------------------------------------------- | ----------------------------------------------------- |
| NVIDIA Triton Inference Server     | **26.01**                                      | `ai/gateway/Dockerfile:1`                             |
| NVIDIA TensorRT                    | bundled in the `nvcr.io/nvidia/*:26.0x` images | `ai/common/tensorrt_utils.py` (runtime version check) |
| NVIDIA CUDA Toolkit (`ai-vlm`)     | **13.3.1**                                     | `ai/vlm/Dockerfile:19,86`                             |
| NVIDIA CUDA Toolkit (`ai-gateway`) | bundled in `tritonserver:26.01-py3`            | `ai/gateway/Dockerfile:1`                             |
| NVIDIA DCGM                        | **3.3.5** (exporter **3.4.0**)                 | `docker-compose.prod.yml:1375`                        |
| NVIDIA Container Toolkit           | detected via `nvidia-ctk`                      | `setup_lib/nvidia_toolkit.py`                         |
| NVIDIA driver (host floor)         | **580** minimum for CUDA 13.x                  | `setup_lib/nvidia_detect.py:38`                       |
| nvidia-ml-py (NVML bindings)       | `>=12.560.30,<14.0.0`                          | `pyproject.toml:24`                                   |
| tritonclient[grpc]                 | `>=2.42.0`                                     | `ai/gateway/requirements.txt`                         |
| llama.cpp                          | tag **b7972**                                  | `ai/vlm/Dockerfile:46`                                |
| bitsandbytes                       | `>=0.44.0` (quantization extra)                | `pyproject.toml:175`                                  |
| onnxruntime (CPU, `face` extra)    | `>=1.16` — `CPUExecutionProvider` only         | `pyproject.toml:196-200`                              |
| PyTorch (backend)                  | **2.14.0+cpu**                                 | `uv.lock:25`                                          |
| PyTorch (AI containers)            | CUDA builds from the NGC / devel base images   | base images above                                     |

`ai/gateway/requirements.txt` is seven lines — `fastapi`,
`uvicorn[standard]`, `tritonclient[grpc]`, `pillow`, `numpy`,
`prometheus-client`, `httpx`. It declares no CUDA, ONNX Runtime or TensorRT
package: the NGC Triton image ships all three, and the gateway only ever calls
Triton over gRPC.

---

## NVIDIA CUDA Python Packages

The backend resolves **CPU-only PyTorch**: `torch 2.14.0+cpu` from
`download.pytorch.org/whl/cpu` (`uv.lock:25`; macOS resolves the plain `2.14.0`
wheel at `:24`). Consequences, both measured in this tree:

- `uv.lock` contains exactly one `nvidia-*` package — `nvidia-ml-py`, declared
  `>=12.560.30,<14.0.0` at `uv.lock:1559`, resolved block at `uv.lock:2807`.
- No `nvidia-*-cu12` runtime package and no `triton` kernel compiler appears in
  the lock at all. The CUDA runtime libraries live inside the AI containers, in
  their base images.

`nvidia-ml-py` is the one CUDA-adjacent package the host Python environment
carries: `pyproject.toml:24`. It is the NVML binding behind the GPU monitor and
detection services (see GPU Monitoring).

---

## llama.cpp VLM Serve

`ai-vlm` is a single-stage llama.cpp serve of a vision-language model — the
shipped pair is `Qwen3VL-8B-Instruct-Q4_K_M.gguf` plus
`mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf`. Both names come from compose defaults,
not from the image: `MODEL_PATH` and `MMPROJ_PATH` at
`docker-compose.prod.yml:184-185`. The event path POSTs
`/v1/chat/completions` to `http://ai-vlm:8098`
(`backend/core/config.py:1042` `ai_vlm_url`).

### Build Configuration

| Setting             | Value                                                                   | Source                    |
| ------------------- | ----------------------------------------------------------------------- | ------------------------- |
| Source pin          | `ARG LLAMA_CPP_REF=b7972`                                               | `ai/vlm/Dockerfile:46`    |
| CUDA base (builder) | `nvidia/cuda:13.3.1-devel-ubuntu22.04`                                  | `ai/vlm/Dockerfile:19`    |
| CUDA base (runtime) | `nvidia/cuda:13.3.1-runtime-ubuntu22.04`                                | `ai/vlm/Dockerfile:86`    |
| CMake flags         | `-DGGML_CUDA=ON`, `-DGGML_CUDA_FA_ALL_QUANTS=ON`, `-DGGML_NATIVE=ON`    | `ai/vlm/Dockerfile:74-76` |
| Target arch         | `ARG CUDA_ARCHITECTURES=""` → `-DCMAKE_CUDA_ARCHITECTURES=<n>` when set | `ai/vlm/Dockerfile:64-69` |
| Built artifact      | `llama-server` + its `.so*` set                                         | `ai/vlm/Dockerfile:97-98` |

`GGML_NATIVE=ON` is safe alongside an explicit `CMAKE_CUDA_ARCHITECTURES`
(`ai/vlm/Dockerfile:61-62`); an unset `CUDA_ARCHITECTURES` leaves the arch
choice to the compiler default.

### Runtime Flags

The image `CMD` is one shell line that assembles optional flags only when the
matching variable is non-empty (`ai/vlm/Dockerfile:141-171`):

```bash
llama-server \
    --model ${MODEL_PATH} \
    ${MM_ARGS}         # --mmproj ${MMPROJ_PATH}, only when MMPROJ_PATH is set
    ${ALIAS_ARGS}      # --alias ${MODEL_ALIAS}, only when set
    ${SLEEP_ARGS}      # --sleep-idle-seconds ${SLEEP_IDLE_SECONDS}, only when set
    ${KV_ARGS}         # --cache-type-k / --cache-type-v, only when set
    --host 0.0.0.0 --port ${PORT} \
    --n-gpu-layers ${GPU_LAYERS} \
    --ctx-size ${CTX_SIZE} \
    --parallel ${PARALLEL} \
    --threads ${THREADS} --threads-batch ${THREADS} \
    --batch-size ${BATCH_SIZE} \
    --ubatch-size ${UBATCH_SIZE} \
    --cont-batching \
    --metrics \
    --cache-reuse 256 \
    --jinja \
    ${FLASH_ARGS}      # --flash-attn on when FLASH_ATTENTION=true
```

**The multimodal projector gate.** `MM_ARGS` is built inside
`if [ -n "${MMPROJ_PATH}" ]` (`ai/vlm/Dockerfile:143-144`), and `ENV MMPROJ_PATH=`
is deliberately empty at build time (`:104-107`). A container that reaches
runtime without a readable projector therefore starts, serves and passes both
healthchecks while answering text-only. `ai/vlm/Dockerfile:141-144` is the
first place to read when verdicts look like the model never saw the stills.

### Runtime Variables

| Variable                     | Image default (`ENV`)    | Compose default (`${VAR:-…}`)                  | Source                                                  |
| ---------------------------- | ------------------------ | ---------------------------------------------- | ------------------------------------------------------- |
| `PORT`                       | 8098                     | `PORT=8098` (container side, fixed)            | `ai/vlm/Dockerfile:123` / `docker-compose.prod.yml:181` |
| `MODEL_PATH`                 | `/models/vlm/model.gguf` | `/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf`      | `ai/vlm/Dockerfile:103` / `:180`                        |
| `MMPROJ_PATH`                | empty                    | `/models/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf` | `ai/vlm/Dockerfile:107` / `:181`                        |
| `MODEL_ALIAS`                | empty                    | `Qwen3VL-8B` (from `VLM_MODEL_ALIAS`)          | `ai/vlm/Dockerfile:111` / `:182`                        |
| `GPU_LAYERS`                 | 99                       | `auto` (from `VLM_GPU_LAYERS`)                 | `ai/vlm/Dockerfile:124` / `:188`                        |
| `CTX_SIZE`                   | 8192                     | 32768 (from `VLM_CTX_SIZE`)                    | `ai/vlm/Dockerfile:125` / `:207`                        |
| `PARALLEL`                   | 1                        | 2 (from `VLM_PARALLEL`)                        | `ai/vlm/Dockerfile:126` / `:208`                        |
| `THREADS`                    | 8                        | 4 (from `VLM_THREADS`)                         | `ai/vlm/Dockerfile:128` / `:209`                        |
| `BATCH_SIZE`                 | 2048                     | 2048 (from `VLM_BATCH_SIZE`)                   | `ai/vlm/Dockerfile:129` / `:210`                        |
| `UBATCH_SIZE`                | 512                      | 512 (from `VLM_UBATCH_SIZE`)                   | `ai/vlm/Dockerfile:130` / `:211`                        |
| `CACHE_TYPE_K` / `_V`        | empty (f16)              | `q8_0` / `q8_0`                                | `ai/vlm/Dockerfile:119-120` / `:224-225`                |
| `FLASH_ATTENTION`            | true                     | true (from `VLM_FLASH_ATTENTION`)              | `ai/vlm/Dockerfile:127` / `:226`                        |
| `SLEEP_IDLE_SECONDS`         | empty (never)            | 300 (from `VLM_SLEEP_IDLE_SECONDS`)            | `ai/vlm/Dockerfile:115` / `:241`                        |
| `LLAMA_ARG_IMAGE_MAX_TOKENS` | unset                    | 1280 (literal)                                 | `docker-compose.prod.yml:194`                           |
| `CUDA_VISIBLE_DEVICES`       | unset                    | `${GPU_LLM:-0}`                                | `docker-compose.prod.yml:180`                           |

Per-slot context is `CTX_SIZE / PARALLEL` = 32768 / 2 = 16 384 tokens, and each
still is capped at 1 280 vision tokens (`LLAMA_ARG_IMAGE_MAX_TOKENS`,
`docker-compose.prod.yml:189-194`). The client fits the prompt to the slot
rather than trusting that arithmetic — see the erratum block at
`docker-compose.prod.yml:201-209`.

`SLEEP_IDLE_SECONDS=300` is the residency mechanism: llama.cpp releases the
weights to CPU RAM after 300 idle seconds, so an idle night yields the VRAM to
other residents and a burst of camera traffic keeps the serve warm. The caller's
wake budget is `AI_VLM_WAKE_TIMEOUT_SECONDS`.

**Healthcheck.** Both the image and compose probe the same URL with the same
grace: `curl -f http://localhost:8098/health`, `--start-period=120s`
(`ai/vlm/Dockerfile:138-139`, `docker-compose.prod.yml:242-255`).

---

## NVIDIA Triton Inference Server

### Server Configuration

`ai/gateway/entrypoint.sh` starts Triton in the background, waits for
`/v2/health/ready`, then starts the FastAPI gateway in the same container
(`:142-200`).

| Setting            | Value                                            | Source                         |
| ------------------ | ------------------------------------------------ | ------------------------------ |
| Image              | `nvcr.io/nvidia/tritonserver:26.01-py3`          | `ai/gateway/Dockerfile:1`      |
| Gateway port       | 8090 (FastAPI, published to localhost)           | `ai/gateway/entrypoint.sh:11`  |
| HTTP port          | 8000 (internal: readiness, metrics proxy)        | `ai/gateway/entrypoint.sh:12`  |
| gRPC port          | 8001 (internal: inference)                       | `ai/gateway/entrypoint.sh:13`  |
| Metrics port       | 8002 (Prometheus scrape, published)              | `ai/gateway/entrypoint.sh:14`  |
| Model control      | `none` (models load only by presence)            | `ai/gateway/entrypoint.sh:147` |
| Rate limiter       | `execution_count`                                | `ai/gateway/entrypoint.sh:151` |
| Pinned memory pool | 32 MB (`33554432`)                               | `ai/gateway/entrypoint.sh:152` |
| CUDA memory pool   | 256 MB on device 0 (`0:268435456`)               | `ai/gateway/entrypoint.sh:153` |
| Model repository   | `${TRITON_MODEL_REPOSITORY:-/models/repository}` | `ai/gateway/entrypoint.sh:10`  |

The gateway publishes 8090 and 8002 to `127.0.0.1`; Triton's own 8000/8001 are
never published (`docker-compose.prod.yml:368-370`).

### Startup sequence

Four steps run before Triton starts, each in `ai/gateway/entrypoint.sh`:

1. **Device export** — reads `device_env_var`/`device` from `models.yml` and
   exports them (`:52-72`).
2. **Config patch** — `ai/gateway/patch_triton_configs.py` rewrites each
   `config.pbtxt` `instance_group` from the `triton_kind` field in **`models.yml`
   at the repo root**, before Triton scans (`:84-90`). `models.yml` is the
   single source of truth for CPU↔GPU moves.
3. **Weight linking** — symlinks `${MODEL_CACHE_DIR:-/models/cache}/<model>/1`
   into the repository so the baked `config.pbtxt` and the volume's weights meet
   (`:99-115`).
4. **Residency prune** — `python3 -m ai.gateway.residency` moves every model
   outside the active set to `${TRITON_MODEL_REPO}.retired` (`:118-131`). This
   step has no `|| true`: a failed prune stops the container rather than let
   Triton scan a retired model.

### Residency

`GATEWAY_MODEL_SET` selects the model directories that stay in the repository
(`docker-compose.prod.yml:392`, shipped default `vlm`). `ai/gateway/residency.py`
is the whole control surface: `VLM_MODEL_BASE = ("yolo26", "reid")` at `:60`,
plus `threat` when `GATEWAY_ENABLE_THREAT=true` (compose default `false`,
`docker-compose.prod.yml:393`). `get_model_set()` accepts the name `vlm` and
raises otherwise (`ai/gateway/residency.py:60-90`), so the entrypoint's own
`<unset: residency will refuse>` echo at `:130` is a stop, not a warning.

### Model Repository (3 models)

`ai/triton/model_repository/` contains exactly `yolo26`, `reid` and `threat`.
All three declare `backend: "onnxruntime"` and one `KIND_GPU` instance group
with a `global` rate-limiter resource. **No model uses a TensorRT backend.**

| Model    | Backend     | Input           | Output       | Max Batch    | Dynamic Batching         | Priority | Source         |
| -------- | ----------- | --------------- | ------------ | ------------ | ------------------------ | -------- | -------------- |
| `yolo26` | onnxruntime | `[1,3,640,640]` | `[1,300,6]`  | 0 (static=1) | No                       | 1 (high) | `config.pbtxt` |
| `reid`   | onnxruntime | `[3,256,128]`   | `[512]`      | 16           | preferred 1,4,8 / 100 ms | 2        | `config.pbtxt` |
| `threat` | onnxruntime | `[1,3,640,640]` | `[1,8,8400]` | 0 (static=1) | No                       | 1 (high) | `config.pbtxt` |

`yolo26` returns post-NMS detections (`x1,y1,x2,y2,score,class`, 300 slots, 80
COCO classes); `threat` returns the raw YOLO tensor (`4 box + 4 class scores` ×
8 400 anchors); `reid` returns an L2-normalised 512-d embedding from a
256×128 person crop. Only `yolo26` and `reid` are resident unless threat is
opted in.

### Mounted model paths

| Mount                                                                 | Purpose                                               |
| --------------------------------------------------------------------- | ----------------------------------------------------- |
| `${AI_MODELS_PATH:-/export/ai_models}/model-zoo:/models/zoo:ro`       | zoo weights and exports                               |
| `${AI_MODELS_PATH:-/export/ai_models}/triton:/models/cache`           | version dirs the entrypoint links into the repository |
| `${AI_MODELS_PATH:-/export/ai_models}/quantized:/models/quantized:ro` | INT8 weight store                                     |
| `triton-kernel-cache:/root/.nv`                                       | CUDA JIT compilation cache                            |
| `triton-tmp-cache:/tmp`                                               | compilation temp artifacts                            |
| `${HF_CACHE_PATH}:/root/.cache/huggingface`                           | HF cache with `HF_HUB_OFFLINE=1`                      |

(`docker-compose.prod.yml:371-380`.)

### Triton Client

| Package              | Version  | Protocol   | Source                                                                |
| -------------------- | -------- | ---------- | --------------------------------------------------------------------- |
| `tritonclient[grpc]` | >=2.42.0 | async gRPC | `ai/gateway/requirements.txt`; `ai/gateway/triton_client.py:24,61-65` |

`TRITON_GRPC_URL` defaults to `localhost:8001` — same container, gRPC port
(`ai/gateway/triton_client.py:24`). `ai/gateway/main.py:276-277` mounts exactly
two routers: `/yolo26` and `/enrich-lt`, backed by the two adapters in
`ai/gateway/adapters/`.

---

## NVIDIA TensorRT

### Version and status

TensorRT is **not active in Triton** — all three repository models use the
ONNX Runtime backend. TensorRT ships inside the NGC images and reaches the tree
through three paths:

1. **Host-side engine prep** — `ai/yolo26/build_engine.py` builds an FP16 engine
   on the host, driven by `scripts/prebuild-tensorrt-engines.sh` (whose own
   header marks the container route deprecated in favour of
   `ai/gateway/export/export_all.sh`).
2. **Engine placement** — `ai/gateway/export/copy_yolo26_engine.py` copies
   `/models/zoo/yolo26/exports/yolo26m_fp16.engine` to
   `/models/cache/yolo26/1/model.plan`, the Triton-expected path.
3. **Optional export format** — `ai/gateway/export/export_yolo26.py` defaults to
   ONNX (which is what the `onnxruntime` backend loads) and takes `--tensorrt`
   when an engine is wanted.

Engines are GPU-architecture-specific: an engine built on one card fails to load
on another (`ai/gateway/export/copy_yolo26_engine.py:17-22`).

### Infrastructure code

| Module                            | Purpose                                                                          |
| --------------------------------- | -------------------------------------------------------------------------------- |
| `ai/common/tensorrt_utils.py`     | `TensorRTConverter`, `TensorRTEngine`, GPU-hash-based caching                    |
| `ai/common/tensorrt_inference.py` | `TensorRTInferenceBase` ABC with a PyTorch fallback                              |
| `ai/tensorrt_prebuild.py`         | startup validation (SM version + TensorRT version match)                         |
| `ai/yolo26/build_engine.py`       | host-side engine build                                                           |
| `ai/yolo26/model.py`              | host-run detector; `_prebuild_yolo26_engine` under `YOLO26_PREBUILD_ENGINE=true` |
| `ai/torch_optimizations.py`       | backend selection: `tensorrt` > `torch_compile` > none                           |

### Configuration

| Variable                      | Default                 | Reader                        |
| ----------------------------- | ----------------------- | ----------------------------- |
| `TENSORRT_ENABLED`            | `true`                  | `ai/common/tensorrt_utils.py` |
| `TENSORRT_PRECISION`          | `fp16`                  | `ai/common/tensorrt_utils.py` |
| `TENSORRT_CACHE_DIR`          | `models/tensorrt_cache` | `ai/common/tensorrt_utils.py` |
| `TENSORRT_MAX_WORKSPACE_SIZE` | 1 GB                    | `ai/common/tensorrt_utils.py` |
| `TENSORRT_VERBOSE`            | `false`                 | `ai/common/tensorrt_utils.py` |

No `tensorrt` Python package is declared in `pyproject.toml` or in
`ai/gateway/requirements.txt`; the symbols above run where the NGC image
provides the library.

### Key limitation

`TensorrtExecutionProvider` (ONNX Runtime's TensorRT EP) is not used by the
shipped inference path — no file under `backend/` or `ai/` selects it. The one
place it is constructed is the benchmark harness, behind a flag that defaults to
off: `scripts/benchmark_yolo26_gpu.py:441,462,1172,1191`. It is a measurement
arm, not a deployment option.

---

## ONNX Runtime GPU

### CUDAExecutionProvider usage

The Triton `onnxruntime` backend runs each model with the CUDA provider inside
the gateway container; the model configs say so in their headers
(`ai/triton/model_repository/yolo26/config.pbtxt:6-8`).

In the host Python environment, `export` helpers select providers directly:

```python
providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
```

Six scripts under `ai/gateway/export/` do this —
`export_reid.py`, `export_depth.py`, `export_vehicle.py`, `export_pet.py`,
`export_fashion_clip.py`, `export_demographics.py` — of which only
`export_reid.py` corresponds to a model in the repository. The remaining five
are export tooling for models the repository does not carry.

The backend's identity lookups are deliberately CPU-only: `pyproject.toml:196-200`
declares `onnxruntime>=1.16` under the `face` extra with the comment
`CPUExecutionProvider only (deliberately no GPU provider)`, so the
face-recognizer loader stays out of the VRAM budget.

### Packages

| Package              | Version  | Where                                                         |
| -------------------- | -------- | ------------------------------------------------------------- |
| `onnxruntime`        | >=1.16   | host Python, `face` extra, CPU EP only — `pyproject.toml:200` |
| ONNX Runtime         | bundled  | Triton `onnxruntime` backend in `tritonserver:26.01-py3`      |
| `tritonclient[grpc]` | >=2.42.0 | `ai-gateway` — `ai/gateway/requirements.txt`                  |

---

## CUDA Infrastructure Modules

Custom GPU-optimization modules in `ai/`. Each is confirmed to exist in this
tree; the "Reader" column names the file that reads its configuration.

| Module                         | NEM ticket | Purpose                                                       | Reader (env var)                                  |
| ------------------------------ | ---------- | ------------------------------------------------------------- | ------------------------------------------------- |
| `ai/cuda_graph_manager.py`     | NEM-3771   | CUDA Graph capture/replay for repeated inference              | `CUDA_GRAPHS_DISABLE`                             |
| `ai/cuda_streams.py`           | NEM-3772   | CUDA stream pool for parallel preprocessing                   | `CUDA_STREAMS_ENABLED`, `_POOL_SIZE`, `_PRIORITY` |
| `ai/gpu_memory_pool.py`        | NEM-3772   | Pre-allocated tensor pools, LRU eviction                      | --                                                |
| `ai/gpu_oom_handler.py`        | NEM-4996   | OOM detection, `torch.cuda.empty_cache()`, Prometheus counter | --                                                |
| `ai/flash_attention_config.py` | --         | FlashAttention-2 config (Ampere SM >= 8.0)                    | --                                                |
| `ai/torch_optimizations.py`    | --         | backend selection: tensorrt > torch_compile > none            | --                                                |
| `ai/quantization_config.py`    | NEM-3810   | BitsAndBytes 4-bit/8-bit config for HF models                 | bitsandbytes extra, `pyproject.toml:175`          |
| `ai/static_kv_cache.py`        | --         | memory-efficient KV cache reuse                               | --                                                |
| `ai/compile_utils.py`          | --         | compile warmup helpers                                        | --                                                |
| `ai/warmup_utils.py`           | --         | warmup helpers                                                | --                                                |
| `ai/hub_cache_config.py`       | --         | HF hub cache configuration                                    | --                                                |

> `ai/gpu_oom_handler.py` defines the `ai_gpu_oom_total` counter; nothing in the
> gateway topology exports it over `/metrics`, which is why the alert that keyed
> on it was deleted (`monitoring/ai-pipeline-alerts.yml:33-40`).

### CUDA environment variables

| Variable                 | Default | Source                     |
| ------------------------ | ------- | -------------------------- |
| `CUDA_GRAPHS_DISABLE`    | `0`     | `ai/cuda_graph_manager.py` |
| `CUDA_STREAMS_ENABLED`   | `true`  | `ai/cuda_streams.py`       |
| `CUDA_STREAMS_POOL_SIZE` | `3`     | `ai/cuda_streams.py`       |
| `CUDA_STREAMS_PRIORITY`  | `0`     | `ai/cuda_streams.py`       |

---

## GPU Passthrough & Container Toolkit

### CDI (Container Device Interface)

Rootless GPU access goes through Podman CDI. The two AI services use two
different device forms, on purpose:

```yaml
# ai-vlm: one GPU, named
devices:
  - nvidia.com/gpu=${GPU_LLM:-0}

# ai-gateway: ALL GPUs passed, CUDA_VISIBLE_DEVICES restricts
devices:
  - nvidia.com/gpu=all
environment:
  - CUDA_VISIBLE_DEVICES=${GPU_AI_SERVICES:-1}
```

(`docker-compose.prod.yml:162-163,175` and `:361-362,392`.)

**The CDI constraint the gateway works around:** `nvidia.com/gpu=N` creates only
`/dev/nvidiaN`, and CUDA expects `/dev/nvidia0` for its first visible device, so
a card numbered above 0 fails. The gateway passes `nvidia.com/gpu=all` and lets
`CUDA_VISIBLE_DEVICES` pick the card — the reason is written out at
`docker-compose.prod.yml:362-365`.

### GPU assignment variables

| Variable          | Default | Service                                               | Source                                |
| ----------------- | ------- | ----------------------------------------------------- | ------------------------------------- |
| `GPU_LLM`         | 0       | `ai-vlm` (also its `deploy` reservation)              | `docker-compose.prod.yml:163,179,269` |
| `GPU_AI_SERVICES` | 1       | `ai-gateway` / Triton (also its `deploy` reservation) | `docker-compose.prod.yml:398,423`     |

Those are the only two GPU selectors the compose file reads.

### NVIDIA Container Toolkit detection

`setup_lib/nvidia_detect.py` and `setup_lib/nvidia_toolkit.py` handle:

- GPU detection via `nvidia-smi`
- driver validation against `MINIMUM_DRIVER_VERSION = 580` (`setup_lib/nvidia_detect.py:38`)
- Container Toolkit detection (`nvidia-ctk`)
- CDI spec generation: `nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml`
- per-distro install commands, and an apt repair step that purges `nvidia`
  packages rather than letting `--fix-broken` reinstall a driver below 580
  (`setup_lib/nvidia_detect.py:45-58`)

### Persistent CUDA cache volumes

| Volume                | Mount                      | Consumed by                       | Source                                |
| --------------------- | -------------------------- | --------------------------------- | ------------------------------------- |
| `llama-cache`         | `/home/llama/.cache`       | `ai-vlm`                          | `docker-compose.prod.yml:175`         |
| `llama-nv-cache`      | `/home/llama/.nv`          | `ai-vlm`                          | `docker-compose.prod.yml:176`         |
| `triton-kernel-cache` | `/root/.nv`                | `ai-gateway`                      | `docker-compose.prod.yml:376`         |
| `triton-tmp-cache`    | `/tmp`                     | `ai-gateway`                      | `docker-compose.prod.yml:378`         |
| `hf_cache`            | `/root/.cache/huggingface` | `ai-gateway` (`HF_HUB_OFFLINE=1`) | `docker-compose.prod.yml:380,399-400` |

`ai-vlm` also gets `tmpfs: /tmp` (`docker-compose.prod.yml:148-149`) rather than a
named volume.

---

## GPU Monitoring & Observability

### NVML / nvidia-ml-py (primary)

**Package:** `nvidia-ml-py>=12.560.30,<14.0.0` (`pyproject.toml:24`; lock entry
`uv.lock:2807`).

| Consumer               | File                                        | What it reads                                           |
| ---------------------- | ------------------------------------------- | ------------------------------------------------------- |
| `GPUMonitor`           | `backend/services/gpu_monitor.py`           | utilization, memory, temp, power, clocks, PCIe, ECC     |
| `GpuDetectionService`  | `backend/services/gpu_detection_service.py` | multi-GPU detection, compute capability, UUID           |
| `PerformanceCollector` | `backend/services/performance_collector.py` | 5-second polling, WebSocket broadcast, threshold alerts |

### nvidia-smi (fallback)

```bash
nvidia-smi --query-gpu=temperature.gpu,power.draw,utilization.gpu,memory.used,memory.total,name \
  --format=csv,noheader,nounits
```

### DCGM Exporter

| Setting         | Value                                                                 |
| --------------- | --------------------------------------------------------------------- |
| Image           | `nvcr.io/nvidia/k8s/dcgm-exporter:3.3.5-3.4.0-ubuntu22.04`            |
| Port            | 9400                                                                  |
| Profile         | `gpu-rootful` — `DCGM nv-hostengine` needs host root                  |
| Custom counters | `monitoring/dcgm/custom-counters.csv` (79 lines)                      |
| Scrape target   | `host.containers.internal`:9400 (`monitoring/prometheus.yml:523-527`) |

`monitoring/prometheus.yml:520-522` records that the exporter runs as a rootful
systemd unit (`monitoring/dcgm/dcgm-exporter.service`) with `--net=host` so
rootless Prometheus can reach it.

**DCGM counter fields** (`monitoring/dcgm/custom-counters.csv`):

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

### Triton native metrics

Scraped from `ai-gateway:8002/metrics` (`monitoring/prometheus.yml:112-121`):

- `nv_gpu_utilization`, `nv_gpu_memory_used_bytes`
- `nv_inference_request_success`, `nv_inference_request_failure`
- `nv_inference_request_duration_us`, `nv_inference_queue_duration_us`,
  `nv_inference_compute_infer_duration_us`

The gateway also serves its own Prometheus text at `/metrics`, merging Triton
native metrics with gateway-level counters
(`ai/gateway/main.py:20,318-320`).

### llama.cpp metrics

`llama-server` runs with `--metrics` (`ai/vlm/Dockerfile:168`) on the fixed
container port 8098, and Prometheus scrapes `ai-vlm:8098/metrics`.

---

## Prometheus GPU Metrics

### Scrape jobs (`monitoring/prometheus.yml`)

| Job                   | Target                                                        | Interval | Prefix      | Line |
| --------------------- | ------------------------------------------------------------- | -------- | ----------- | ---- |
| `hsi-backend-metrics` | `backend:8000` `/api/metrics`                                 | 15s      | `hsi_*`     | 61   |
| `ai-vlm-metrics`      | `ai-vlm:8098` `/metrics`                                      | 15s      | llama.cpp   | 90   |
| `triton-metrics`      | `ai-gateway:8002` `/metrics`                                  | 15s      | `nv_*`      | 112  |
| `ai-gateway-metrics`  | `ai-gateway:8090` `/metrics`                                  | 15s      | gateway     | 138  |
| `hsi-gpu`             | `http://backend:8000/api/system/gpu` (json-exporter `/probe`) | 10s      | `hsi_gpu_*` | 233  |
| `dcgm-exporter`       | `host.containers.internal`:9400                               | 15s      | `DCGM_FI_*` | 523  |

**Not every scrape job in this file resolves.** The `blackbox-http-health` job
still targets `ai-gateway:8090/clip/health`, `/florence/health` and
`/enrichment/health` (`monitoring/prometheus.yml:430,436,442`) on a gateway that
mounts only `/yolo26` and `/enrich-lt` (`ai/gateway/main.py:276-277`), so
`probe_success` is pinned 0 for those three targets while the live probes at
`:412`, `:418`, `:424` and `:448` behave.

### HSI GPU metrics (backend API via json-exporter)

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

### AI service metrics with no scrape target

| Metric                                | Defined at              | State              |
| ------------------------------------- | ----------------------- | ------------------ |
| `ai_gpu_oom_total`                    | `ai/gpu_oom_handler.py` | counter, no target |
| `enrichment_vram_usage_bytes`         | enrichment code         | gauge, no target   |
| `enrichment_vram_budget_bytes`        | enrichment code         | gauge, no target   |
| `enrichment_vram_utilization_percent` | enrichment code         | gauge, no target   |
| `yolo26_*`                            | `ai/yolo26/metrics.py`  | gauges, no target  |

`monitoring/prometheus.yml:161` (`# Removed targets:`) records that Triton's
native `nv_*` metrics are the replacement for the deleted scrape jobs. A metric
that is defined in code but has no `/metrics` handler and no job is not a signal
— the `GPUOOMCritical` alert that keyed on `ai_gpu_oom_total` was deleted for
exactly this reason (`monitoring/ai-pipeline-alerts.yml:33-40`).

### Grafana dashboards

`monitoring/grafana/dashboards/hsi-gpu-metrics.json` — utilization, VRAM,
temperature, power, clocks, PCIe throughput, memory bandwidth.

Every other dashboard in that directory keys on series an exporter produces;
`scripts/audit_grafana_queries.py` re-derives the empty-series census
(`docs/guides/metrics-coverage.md` holds the current reading).

---

## GPU Alert Rules

### DCGM-based alerts (`monitoring/gpu-alerts.yml`, 11 alerts)

| Alert                         | Expression               | Duration | Severity | Line |
| ----------------------------- | ------------------------ | -------- | -------- | ---- |
| `GPUMemoryNearFull`           | VRAM > 90%               | 2m       | critical | 33   |
| `GPUMemoryHigh`               | VRAM > 80%               | 5m       | warning  | 47   |
| `GPUHighTemperature`          | temp > 85 C              | 5m       | critical | 64   |
| `GPUTemperatureElevated`      | temp > 75 C              | 10m      | warning  | 77   |
| `GPUUtilizationSaturated`     | util > 95%               | 15m      | warning  | 94   |
| `GPUUnderutilizedMemoryBound` | GPU < 30% AND MEM > 70%  | 5m       | warning  | 107  |
| `GPUMemoryBandwidthSaturated` | MEM > 90%                | 10m      | warning  | 126  |
| `GPUHighPowerUsage`           | power > 350W             | 10m      | warning  | 143  |
| `GPUClockSpeedDegraded`       | SM < 1200 AND util > 50% | 5m       | warning  | 160  |
| `DCGMExporterDown`            | exporter down            | 2m       | critical | 179  |
| `NoGPUMetrics`                | exporter up, no data     | 5m       | warning  | 192  |

### AI pipeline alerts (`monitoring/ai-pipeline-alerts.yml`)

The GPU rules that actually reference the shipped topology:

| Alert                  | Expression                                                                                                  | Duration | Severity | Line |
| ---------------------- | ----------------------------------------------------------------------------------------------------------- | -------- | -------- | ---- |
| `GPUInferenceFailures` | `sum(rate(nv_inference_request_failure[5m])) / (sum(rate(nv_inference_request_success[5m])) + 0.001) > 0.1` | 5m       | critical | 49   |
| `GPUMemoryHigh`        | `hsi_gpu_memory_used_mb / total > 0.9`                                                                      | 5m       | warning  | 67   |
| `GPUMemoryCritical`    | `hsi_gpu_memory_used_mb / total > 0.95`                                                                     | 2m       | critical | 80   |

The same file also carries the ai-vlm verification-leg alerts, keyed on the
metrics the VLM path actually writes: `PromptTruncationHigh` `:108`
(`hsi_prompts_truncated_total`), `VlmVerificationFailures` `:145`
(`hsi_pipeline_errors_total{error_type="vlm_verification_failed"}`),
`VlmRequestErrors` `:169` (the `vlm_transport_error|vlm_http_error|vlm_schema_invalid`
attempt classes), `VlmServiceUnhealthy` `:192` (`hsi_ai_service_degraded`), and
`VlmSpecialistLegsUnavailable` `:213` (`hsi_specialist_unavailable_total`).

### Backend performance thresholds (`backend/services/performance_collector.py:39-42`)

| Metric          | Warning | Critical |
| --------------- | ------- | -------- |
| GPU temperature | 75 C    | 85 C     |
| GPU utilization | 90%     | 98%      |
| GPU VRAM        | 90%     | 95%      |
| GPU power       | 300W    | 350W     |

---

## VRAM Budget

Two GPU-resident workloads and three CPU lookup legs. The compose `memory`
limits are host RAM, not VRAM; nothing in this tree advertises a VRAM budget for
the GPU-resident pair, so the rows below are what the code actually sizes.

| Component                                                       | Footprint                                   | Source                            |
| --------------------------------------------------------------- | ------------------------------------------- | --------------------------------- |
| `Qwen3VL-8B-Instruct-Q4_K_M.gguf` weights                       | 5,027,784,800 B                             | `docker-compose.prod.yml:232-233` |
| `mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf` weights                  | 752,289,728 B                               | `docker-compose.prod.yml:232-233` |
| KV pool, 32 768 ctx × 2 slots, f16                              | 4 608 MiB (measured, llama.cpp's own line)  | `docker-compose.prod.yml:215-226` |
| KV pool, same geometry, `CACHE_TYPE_K/V=q8_0` (shipped default) | half the f16 pool                           | `docker-compose.prod.yml:227-228` |
| Triton CUDA context + three ONNX models                         | 256 MB CUDA memory pool declared at startup | `ai/gateway/entrypoint.sh:153`    |
| Face detection + recognition, person re-ID, plate OCR           | CPU (ONNX `CPUExecutionProvider` only)      | `pyproject.toml:196-200`          |

The `q8_0` KV default is the shipped relief for this pool: the pool is a
function of the architecture and the ctx/slot numbers, not of the weights' size
(`docker-compose.prod.yml:215-226`).

`models.yml` at the repo root carries the per-model `vram_mb` field the backend
model zoo reads; `GPU_LAYERS=auto` lets llama.cpp fit the VLM to whatever VRAM
is free (`docker-compose.prod.yml:188`).

---

## NVIDIA Inference API

Used for media generation, not the event pipeline:

| Script                                    | Endpoint / tool                                                                                        | Purpose                         |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------- |
| `scripts/generate_videos.sh`              | `https://inference-api.nvidia.com` (`scripts/generate_videos.py:41`)                                   | Veo 3.1 video generation        |
| `scripts/synthetic/media_generator.py`    | same host (`:96`)                                                                                      | synthetic media generation      |
| `scripts/generate_architecture_images.sh` | the local `nvidia-image-gen` skill (`$HOME/.claude/skills/nvidia-image-gen/scripts/generate_image.py`) | architecture diagram generation |

The shell helpers point users to **`https://build.nvidia.com`** for keys.
Requires `NVIDIA_API_KEY` or `NVAPIKEY`.

---

## CI/CD GPU Integration

### GitHub Actions workflows

| Workflow          | GPU relevance                           |
| ----------------- | --------------------------------------- |
| `build-setup.yml` | bundles `setup_lib.nvidia_detect`       |
| `deploy.yml`      | "NVIDIA CUDA — amd64 only" image builds |

There is **no GPU CI job** in `.github/workflows/`. `.github/workflows/nightly.yml:12` records
that the `extended-benchmarks` job (self-hosted gpu, rtx-a5500) was removed on
2026-09-15 while the runner is offline, with an in-file note to restore it from
git history when the box returns. `backend/tests/gpu/` and
`scripts/setup-gpu-runner.sh` still exist locally; they simply have no scheduled
job.

### GPU runner setup (`scripts/setup-gpu-runner.sh`)

Probes the host against three CUDA base images — `nvidia/cuda:12.0.0-base-ubuntu22.04`,
`12.2.0-base-ubuntu22.04`, `11.8.0-base-ubuntu22.04` (`:70-72`) — installs
`nvidia-container-toolkit`, and registers the runner with labels
`self-hosted,linux,gpu,rtx-a5500`.

---

## Why ONNX Runtime, Not TensorRT

Both shipped Triton inference models and the resident re-ID model run
`backend: "onnxruntime"` on GPU, and none of the three uses a TensorRT backend.
The reasons are recorded in the files themselves, where they were discovered:

1. **INT8 `ConvInteger` is CPU-only in ONNX Runtime.** The quantized YOLO26
   export inserted `ConvInteger` nodes the CUDA EP cannot run, so the config
   states it chose FP32 ONNX on GPU instead
   (`ai/triton/model_repository/yolo26/config.pbtxt:7-8`, NEM-5547 / NEM-5551).
2. **Builder workspace on a small second card.** The export helpers default
   `--workspace-gb` to 1 GB because that is what fits alongside other residents
   on a 4 GB GPU 1 (`ai/gateway/export/README.md:75`); the same constraint is in
   `ai/gateway/export/export_yolo_pose.py:172`. Engine builds compete for that workspace.
3. **Ultralytics `.engine` files are wrapped.** Triton's `tensorrt` backend
   expects a raw serialized plan; the Ultralytics export carries a metadata
   envelope, which is why engine output goes through the explicit
   `copy_yolo26_engine.py` placement step rather than a Triton TensorRT config.

The measured comparison the benchmark harness still runs today is the CUDA EP
against the TensorRT EP, flag-gated and off by default
(`scripts/benchmark_yolo26_gpu.py:441,447,462,1172,1191`).

| Backend                  | Relative latency   | VRAM overhead             | Portability    |
| ------------------------ | ------------------ | ------------------------- | -------------- |
| **TensorRT**             | 1x (fastest)       | high (workspace + engine) | sm_XX specific |
| **ONNX Runtime CUDA EP** | ~1.3-1.5x TensorRT | low (ONNX file only)      | any GPU        |
| **ONNX Runtime CPU EP**  | ~3-5x TensorRT     | none                      | any CPU        |

Paths that stay open: `--tensorrt` on `export_yolo26.py` for an engine build,
the host-side `build_engine.py` + `copy_yolo26_engine.py` placement pair, and a
larger second card to unblock a bigger builder workspace.
