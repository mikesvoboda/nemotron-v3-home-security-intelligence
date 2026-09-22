# AI Pipeline Directory

## Purpose

Contains AI inference services for home security monitoring. What actually
runs in production (`docker-compose.prod.yml` builds exactly two AI images):

| Compose service | Port                 | What it is                                                                                                                                                                  |
| --------------- | -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ai-llm`        | 8091                 | Nemotron LLM via llama.cpp (this directory's `nemotron/Dockerfile`)                                                                                                         |
| `ai-gateway`    | 8090 (+8002 metrics) | FastAPI facade over Triton in one container; serves the legacy YOLO26 / CLIP / Florence-2 / enrichment / enrichment-light HTTP APIs through Triton (`ai/gateway/AGENTS.md`) |

The remaining capability modules are standalone FastAPI servers you can run
natively for development/debugging - they are **not** compose services in
production:

1. **YOLO26** (`yolo26/`, default port 8095) - Object detection
2. **CLIP** (`clip/`, default port 8093) - Entity embeddings
3. **Florence-2** (`florence/`, default port 8092) - Vision-language attributes
4. **Enrichment** (`enrichment/`, default port 8094) - Model Zoo
5. **Enrichment-light** (`enrichment-light/`, default port 8096)
6. **Triton client + model repository** (`triton/`, NEM-3769) - the gRPC
   server Triton itself runs inside the ai-gateway container

The backend reaches AI through HTTP clients in `backend/services/`. With
`USE_AI_GATEWAY=true` + `AI_GATEWAY_URL` (the production default), those
clients base-URL-swap to `http://ai-gateway:8090/<service-prefix>`; otherwise
they hit the standalone ports directly (`backend/core/config.py`
`use_ai_gateway` / `ai_gateway_url`).

## Directory Structure

```
ai/
├── AGENTS.md              # This file
├── __init__.py            # Package init
├── cuda_streams.py        # CUDA streams for parallel preprocessing (NEM-3770)
├── compile_utils.py       # torch.compile() utilities (NEM-3773)
├── batch_utils.py         # Batch processing utilities (NEM-3377)
├── torch_optimizations.py # General PyTorch optimization utilities
├── cpu_offloading.py      # CPU offloading utilities
├── cuda_graph_manager.py  # CUDA graph management
├── flash_attention_config.py # FlashAttention configuration
├── gpu_memory_pool.py     # GPU memory pool management
├── hub_cache_config.py    # HuggingFace hub cache configuration
├── quantization_config.py # Quantization configuration
├── static_kv_cache.py     # Static KV cache for inference
├── warmup_utils.py        # Model warmup utilities
├── shared/                # Shared utilities (gpu_profiler.py) - see shared/AGENTS.md
├── common/                # Shared TensorRT optimization infrastructure (NEM-3838)
│   ├── AGENTS.md          # TensorRT infrastructure documentation
│   ├── __init__.py        # Package exports
│   ├── tensorrt_utils.py  # ONNX-to-TensorRT conversion, engine management
│   ├── tensorrt_inference.py  # Base classes for TensorRT-accelerated models
│   └── tests/             # Unit tests
│       └── __init__.py    # Package init
├── yolo26/                # YOLO26 detection server - port 8095 (see yolo26/AGENTS.md)
├── nemotron/              # Nemotron LLM container build (compose service ai-llm)
│   ├── AGENTS.md          # Nemotron documentation
│   ├── Dockerfile         # Multi-stage build for llama.cpp
│   ├── Dockerfile.hf      # Optional HF-transformers variant (model_hf.py)
│   ├── model_hf.py        # Transformers-based server (alternative to llama.cpp)
│   ├── config.json        # llama.cpp config reference
│   └── .gitkeep           # Placeholder (GGUF models downloaded at runtime)
├── clip/                  # CLIP embedding server
│   ├── AGENTS.md          # CLIP documentation
│   ├── Dockerfile         # Container build
│   ├── model.py           # FastAPI server for embeddings
│   └── requirements.txt   # Python dependencies
├── florence/              # Florence-2 vision-language server
│   ├── AGENTS.md          # Florence-2 documentation
│   ├── Dockerfile         # Container build
│   ├── __init__.py        # Package init
│   ├── model.py           # FastAPI server for attribute extraction
│   ├── test_model.py      # Unit tests (pytest)
│   ├── requirements.txt   # Python dependencies
│   └── tests/             # Additional tests directory
├── enrichment/            # Combined enrichment service (Model Zoo) - standalone default port 8094
├── enrichment-light/      # Lightweight enrichment service - standalone default port 8096
│   ├── AGENTS.md          # Enrichment-light documentation
│   ├── Dockerfile         # Container build
│   ├── model.py           # FastAPI server (pose, threat, reid, pet, depth)
│   ├── security.py        # Env-var/model-path validation (NEM-4513)
│   ├── requirements.txt   # Python dependencies
│   ├── models/            # Model implementations (person_reid, pose_estimator, threat_detector)
│   └── tests/             # Model-loading unit tests
├── gateway/               # AI Gateway: FastAPI facade over Triton (port 8090)
│   ├── AGENTS.md          # Gateway documentation
│   ├── main.py            # Routers for yolo26/clip/florence/enrichment/enrich-lt
│   ├── adapters/          # REST-to-gRPC adapter modules
│   ├── export/            # ONNX/TensorRT model export pipeline
│   └── tests/             # Gateway unit tests (mocked Triton)
├── triton/                # Triton client + model repository (NEM-3769)
├── tests/                 # AI-level optimization tests (cuda streams, etc.)
├── download_models.sh     # Download AI models
├── start_detector.sh      # Start YOLO26 standalone (YOLO26_PORT, default 8090; the model server itself defaults PORT=8095)
├── start_llm.sh           # Start Nemotron 4B (port 8091)
└── start_nemotron.sh      # Start Nemotron 30B with auto-recovery
```

## Model Zoo Overview

The Enrichment service (`ai/enrichment/`, and its Triton mirror in
`ai/gateway`) implements an on-demand **Model Zoo** architecture for
VRAM-efficient multi-model inference. Instead of loading all models at
startup, models are loaded when needed and evicted via LRU when the VRAM
budget is exceeded. Figures below are from `enrichment/model_registry.py`.

### Available Models (10 registry entries)

| Registry key         | VRAM (default)        | Priority | Purpose                          | Trigger                           |
| -------------------- | --------------------- | -------- | -------------------------------- | --------------------------------- |
| `threat_detector`    | 400 MB                | CRITICAL | Weapon detection (gun, knife)    | Always checked for security       |
| `pose_estimator`     | 300 MB                | HIGH     | Body posture (17 COCO keypoints) | Person detected                   |
| `demographics`       | 500 MB (150 MB INT8)  | HIGH     | Age/gender estimation            | Person with face detected         |
| `fashion_clip`       | 800 MB                | MEDIUM   | Clothing attributes              | Person detected                   |
| `vehicle_classifier` | 1500 MB (400 MB INT8) | MEDIUM   | Vehicle type                     | Vehicle detected                  |
| `pet_classifier`     | 200 MB (0 if CPU)     | MEDIUM   | Cat/dog classification           | Cat/dog detected                  |
| `person_reid`        | 100 MB (0 if CPU)     | MEDIUM   | OSNet re-ID embeddings           | Person detected for tracking      |
| `depth_estimator`    | 100 MB                | LOW      | Monocular depth estimation       | Any detection                     |
| `action_recognizer`  | 2000 MB               | LOW      | X-CLIP video action recognition  | Suspicious pose + multiple frames |
| `yolo26_detector`    | 100 MB (0 if CPU)     | LOW      | Optional secondary detector      | Enrichment-side detection         |

INT8 sizes apply when `VEHICLE_QUANTIZED` / `DEMOGRAPHICS_QUANTIZED` are
`true` (NEM-5533; see the ai-gateway env in `docker-compose.prod.yml`).

### Model Priority System

Models are evicted in priority order when the VRAM budget is exceeded:

- **CRITICAL** (evicted last): Threat detection - never evict if possible
- **HIGH**: Pose, demographics, clothing - important for security context
- **MEDIUM**: Vehicle, pet, re-ID - useful classification
- **LOW** (evicted first): Depth, action, secondary detection

### VRAM Budget

- Default budget: **6.8 GB** (`OnDemandModelManager(vram_budget_gb=6.8)` in
  `model_manager.py`; `enrichment/model.py` reads `VRAM_BUDGET_GB`, default
  `6.8`)
- Models load on-demand when `/enrich` endpoint is called
- LRU eviction with priority ordering when budget exceeded
- Automatic CUDA cache clearing on model unload

For detailed documentation, see [enrichment/AGENTS.md](enrichment/AGENTS.md).

## Quick Start

### Production (Docker/Podman Containers)

```bash
# Start everything (AI in production = ai-llm + ai-gateway)
podman compose -f docker-compose.prod.yml up -d

# Verify AI containers are running
podman ps --filter name=ai-
```

### Development (Native)

Shell scripts for native execution (useful for debugging a standalone server
outside the gateway):

```bash
# 1. Download models (first time only)
./ai/download_models.sh

# 2. Start individual services
./ai/start_detector.sh     # YOLO26 server on 8090 (YOLO26_PORT/PORT overridable)
./ai/start_llm.sh          # llama-server, small nemotron-mini 4B default
                           #   (NEMOTRON_MODEL_PATH overrides; --ctx-size 4096,
                           #    --n-gpu-layers 99, --parallel 2, ~3GB VRAM)
./ai/start_nemotron.sh     # Nemotron-3-Nano-30B Q4_K_M with auto-recovery
                           #   (-ngl 35, -c 12288, --parallel 2, log /tmp/nemotron.log,
                           #    90s startup timeout)
```

Note `start_llm.sh` and `start_nemotron.sh` both default to port 8091 - run
only one at a time.

## Architecture

```
Camera Images
      |
      v
+------------------------------------------------------------------+
|  ai-gateway container (8090)                                     |
|  FastAPI routers (/yolo26, /clip, /florence, /enrichment,        |
|  /enrich-lt) -> Triton (gRPC 8001, same container, GPU)          |
|  Model Zoo models load on demand inside Triton                   |
+------------------------------------------------------------------+
      |   Detections + Enriched Detections
      v
+-----------------------------------------------------+
|              ai-llm container (8091)                |
|              Nemotron risk analysis                 |
|        (Threat, Pose, Demographics Context)         |
+-----------------------------------------------------+
                        |
                        v
                   Risk Events
```

In native development mode the same flow runs with the standalone servers:
YOLO26 on 8095, enrichment on 8094, CLIP on 8093, Florence-2 on 8092.

### Also Available (standalone dev servers)

- **CLIP (8093)**: Entity embeddings
- **Florence-2 (8092)**: Vision-language attribute extraction
- **Enrichment-light (8096)**: pose, threat, reid, pet, depth subset

## Backend Integration

AI clients live in `backend/services/`:

| Backend Service                         | Talks to                                        | Purpose                                               |
| --------------------------------------- | ----------------------------------------------- | ----------------------------------------------------- |
| `backend/services/detector_client.py`   | YOLO26 API (gateway `/yolo26` or :8095)         | Send images, get detections                           |
| `backend/services/nemotron_analyzer.py` | ai-llm directly (`settings.nemotron_url`)       | Analyze batches, get risk                             |
| `backend/services/enrichment_client.py` | Enrichment API (gateway `/enrichment` or :8094) | Unified enrichment for detections                     |
| `backend/services/florence_client.py`   | Florence-2 API (gateway `/florence` or :8092)   | Vision-language extraction                            |
| `backend/services/clip_client.py`       | CLIP API (gateway `/clip` or :8093)             | Embedding generation                                  |
| `backend/services/reid_matcher.py`      | nothing over HTTP                               | Matches re-ID embeddings already stored on detections |

The gateway swap is `use_ai_gateway` + `ai_gateway_url` in
`backend/core/config.py` (env `USE_AI_GATEWAY`, `AI_GATEWAY_URL`);
`reid_matcher.py` is DB-side matching, not an AI service client.

## Environment Variables

### YOLO26

| Variable            | Default                                      | Description              |
| ------------------- | -------------------------------------------- | ------------------------ |
| `YOLO26_MODEL_PATH` | `/models/yolo26/exports/yolo26m_fp16.engine` | TensorRT engine path     |
| `YOLO26_CONFIDENCE` | `0.5`                                        | Min confidence threshold |
| `HOST`              | `0.0.0.0`                                    | Bind address             |
| `PORT`              | `8095`                                       | Server port              |

### Nemotron (ai-llm compose service)

**Model**: [unsloth/Nemotron-3-Nano-30B-A3B-GGUF](https://huggingface.co/unsloth/Nemotron-3-Nano-30B-A3B-GGUF) - NVIDIA's Nemotron-3-Nano-30B-A3B LLM (unsloth's ungated GGUF mirror of the nvidia repo, which 401s without gated access; models.yml `hf_repo` is the source of truth), quantized to Q4_K_M GGUF for efficient inference via llama.cpp.

`.env` is the source of truth; compose maps it onto the container env:

| `.env` variable  | Default (compose)                             | Description                                    |
| ---------------- | --------------------------------------------- | ---------------------------------------------- |
| `LLM_MODEL_PATH` | `/models/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf` | Passed to container as `MODEL_PATH` (NEM-5528) |
| `LLM_PORT`       | `8091`                                        | Host port (binds 127.0.0.1)                    |
| `GPU_LAYERS`     | `auto` (fit to available VRAM)                | Layers on GPU                                  |
| `CTX_SIZE`       | `262144` (8 slots x 32K each)                 | Context window size                            |
| `PARALLEL`       | `8`                                           | Parallel llama.cpp slots                       |
| `GPU_LLM`        | `0` (from `.env.example`)                     | Which physical GPU the LLM gets                |

### AI Gateway

| Variable                                       | Default                  | Description                                           |
| ---------------------------------------------- | ------------------------ | ----------------------------------------------------- |
| `AI_GATEWAY_PORT`                              | `8090`                   | Host port (binds 127.0.0.1)                           |
| `AI_GATEWAY_METRICS_PORT`                      | `8002`                   | Triton metrics port on host                           |
| `AI_GATEWAY_URL`                               | `http://ai-gateway:8090` | Backend clients' gateway base URL                     |
| `USE_AI_GATEWAY`                               | `true`                   | Toggle gateway vs direct-URL clients                  |
| `GPU_AI_SERVICES`                              | `1`                      | GPU CUDA_VISIBLE_DEVICES for the gateway              |
| `VEHICLE_QUANTIZED` / `DEMOGRAPHICS_QUANTIZED` | `false`                  | Use INT8 copies from `QUANTIZED_MODEL_DIR` (NEM-5533) |

Full env table in `ai/gateway/AGENTS.md`.

### Enrichment (Model Zoo)

Read in `ai/enrichment/model_registry.py` / `model.py`:

| Variable                          | Default                                                                    | Description                      |
| --------------------------------- | -------------------------------------------------------------------------- | -------------------------------- |
| `VRAM_BUDGET_GB`                  | `6.8`                                                                      | VRAM budget for on-demand models |
| `VEHICLE_MODEL_PATH`              | `/models/vehicle-segment-classification`                                   | Vehicle classifier path          |
| `PET_MODEL_PATH` / `PET_DEVICE`   | `/models/pet-classifier` / cuda:0 (cpu fallback)                           | Pet classifier path/device       |
| `CLOTHING_MODEL_PATH`             | `/models/fashion-clip`                                                     | FashionCLIP model path           |
| `DEPTH_MODEL_PATH`                | `/models/depth-anything-v2-tiny`                                           | Depth estimator path             |
| `POSE_MODEL_PATH`                 | `/models/yolov8n-pose/yolov8n-pose.pt`                                     | YOLOv8n-pose model path          |
| `THREAT_MODEL_PATH`               | `/models/threat-detection-yolov8n/weights/best.pt`                         | Threat detection model path      |
| `AGE_MODEL_PATH`                  | `/models/vit-age-classifier`                                               | Age classifier path              |
| `GENDER_MODEL_PATH`               | (unset - derived)                                                          | Gender classifier path           |
| `REID_MODEL_PATH` / `REID_DEVICE` | `/models/osnet-ain-x1-0/osnet_ain_x1_0_msmt17.pth` / cuda:0 (cpu fallback) | OSNet ReID path/device           |
| `ACTION_MODEL_PATH`               | `/models/xclip-base-patch16-16-frames`                                     | X-CLIP model path                |
| `YOLO26_ENRICHMENT_MODEL_PATH`    | `/models/yolo26m.pt`                                                       | Secondary detector path          |

## Security-Relevant Classes

YOLO26 filters detections to these classes only:

```python
SECURITY_CLASSES = {"person", "car", "truck", "dog", "cat", "bird", "bicycle", "motorcycle", "bus"}
```

## Risk Scoring (Nemotron)

| Score Range | Level    | Description                 |
| ----------- | -------- | --------------------------- |
| 0-29        | Low      | Normal activity             |
| 30-59       | Medium   | Unusual but not threatening |
| 60-84       | High     | Suspicious activity         |
| 85-100      | Critical | Potential security threat   |

### Enrichment Context for Nemotron

The enrichment service provides structured context to Nemotron for better risk assessment:

- **Threat Detection**: `[CRITICAL] GUN DETECTED: confidence=95%`
- **Pose Analysis**: `Posture: crouching (potentially hiding)`
- **Demographics**: `Person appears to be male, age 21-35`
- **Clothing**: `Alert: dark hoodie detected`
- **Vehicle**: `Vehicle type: pickup truck (commercial)`
- **Re-ID**: `Same person seen on front_door camera 5 minutes ago`
- **Action**: `Action: loitering (suspicious)`

## Hardware Requirements

- **GPU**: NVIDIA with CUDA support (tested on RTX A5500 24GB + RTX A400 4GB)
- **Container Runtime**: Podman (project standard; see AGENTS.md) or Docker
  with NVIDIA Container Toolkit
- **Total VRAM**: ~22 GB for all services running simultaneously
  - Nemotron LLM: ~14.7 GB model file; `.env.example` notes ~20GB at
    Q4_K_M with all layers + 32K ctx
  - AI Gateway / Triton (detection + enrichment + CLIP + Florence weights):
    the remainder, ~6-7 GB of Model Zoo budget plus model weights

### Multi-GPU Support

The system supports distributing AI workloads across multiple GPUs. See
**[Multi-GPU Support Guide](../docs/development/multi-gpu.md)** for
configuration instructions. Production selection is two env vars:
`GPU_LLM` (ai-llm) and `GPU_AI_SERVICES` (ai-gateway).

**Reference Multi-GPU Configuration (dual GPU A5500 + A400):**

| GPU   | Model     | VRAM  | What runs there (production)              |
| ----- | --------- | ----- | ----------------------------------------- |
| GPU 0 | RTX A5500 | 24 GB | ai-llm (`GPU_LLM=0`)                      |
| GPU 1 | RTX A400  | 4 GB  | ai-gateway / Triton (`GPU_AI_SERVICES=1`) |

### GPU Configuration Files (Auto-Generated)

The following files are auto-generated by the GPU Configuration Service when you apply changes via the UI:

- Docker Compose override for GPU assignments (in config directory)
- Human-readable GPU assignment reference (in config directory)

**Do not edit manually.** These files may not exist until GPU configuration is applied via the UI.

### Override File Format

Generated shape (service names as they exist in your compose file(s)):

```yaml
# Auto-generated by GPU Config Service - DO NOT EDIT MANUALLY
services:
  ai-llm:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']
              capabilities: [gpu]
  ai-enrichment:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['1']
              capabilities: [gpu]
    environment:
      - VRAM_BUDGET_GB=3.5
```

(The `ai-enrichment` entry applies to standalone enrichment deployments;
production compose has `ai-llm` and `ai-gateway` - for the production
two-container layout, prefer the `GPU_LLM` / `GPU_AI_SERVICES` env vars.)

### Using the Override File

```bash
# Start with GPU override
podman-compose -f docker-compose.prod.yml \
               -f config/docker-compose.gpu-override.yml up -d

# Restart specific service with GPU override
podman-compose -f docker-compose.prod.yml \
               -f config/docker-compose.gpu-override.yml \
               up -d --force-recreate --no-deps ai-enrichment
```

## Startup Scripts

### `download_models.sh`

Downloads the **models.yml download set** — the 25 entries (32.79 GiB ≈
~32.8GB by `size_mb`) that `setup_lib`'s rule selects:
`download_method != skip AND (hf_repo OR download_method)`
(`setup_lib/models_config.py::get_downloadable_models`). Repo-root
`models.yml` is the source of truth; the 5 `download_method: skip` entries
(brisque-quality, fast-alpr, paddleocr, yolo26-general, zero-dce-plus-plus)
are fetched by their libraries at runtime.

`enabled` in models.yml governs backend model_zoo VRAM slots, NOT disk
provisioning, so three `enabled: false` entries are still downloaded: `yolo26`
(n/s/m `.pt` from ultralytics/assets release v8.4.0 — `ai/gateway/export/`
`export_yolo26.py` + `scripts/prebuild-tensorrt-engines.sh` need
`model-zoo/yolo26/yolo26m.pt` on disk), `xclip-base`
(`backend/services/xclip_loader.py`), and `florence-2-large`
(`backend/services/florence_extractor.py` via the model_zoo loader map).

Largest single pull: Nemotron-3-Nano-30B Q4_K_M (~14.7GB,
`unsloth/Nemotron-3-Nano-30B-A3B-GGUF`).

### `start_detector.sh`

Runs YOLO26 server (`python model.py`) on port 8090 by default: the script sets `PORT` from `YOLO26_PORT:-8090`, so it matches the gateway's port for a host-run stand-in; `model.py` itself falls back to `PORT=8095` when the script does not set it.

### `start_llm.sh`

Simple llama-server startup for 4B model:

- Context: 4096 tokens
- GPU layers: 99

### `start_nemotron.sh`

Advanced startup for 30B model with auto-recovery:

- Context: 12288 tokens
- GPU layers: 35
- Startup timeout: 90 seconds
- Log file: `/tmp/nemotron.log`

## CUDA Streams for Parallel Preprocessing (NEM-3770)

The `cuda_streams.py` module provides CUDA stream management for overlapping preprocessing, inference, and postprocessing operations. This can provide 20-40% throughput improvement for batch processing workloads.

### Key Components

| Component                   | Purpose                                        |
| --------------------------- | ---------------------------------------------- |
| `CUDAStreamPool`            | Manages a pool of CUDA streams                 |
| `StreamedInferencePipeline` | Three-stage pipeline with overlapped execution |
| `StreamConfig`              | Configuration for stream management            |
| `PipelineStats`             | Statistics from pipeline execution             |

### Environment Variables

| Variable                 | Default | Description                          |
| ------------------------ | ------- | ------------------------------------ |
| `CUDA_STREAMS_ENABLED`   | `true`  | Enable/disable CUDA streams          |
| `CUDA_STREAMS_POOL_SIZE` | `3`     | Number of streams in the pool        |
| `CUDA_STREAMS_PRIORITY`  | `0`     | Stream priority (-1=high, 0=default) |

### Usage Example

```python
from cuda_streams import CUDAStreamPool, StreamedInferencePipeline

# Simple stream pool usage
pool = CUDAStreamPool(num_streams=3)
with pool.get_stream() as stream:
    with torch.cuda.stream(stream):
        tensor = preprocess(image)


# Full pipeline with overlapped execution
def preprocess(images):
    return processor(images, return_tensors="pt").to("cuda")


def postprocess(outputs, inputs):
    return outputs.logits.argmax(dim=-1).tolist()


pipeline = StreamedInferencePipeline(
    model=model,
    preprocess_fn=preprocess,
    postprocess_fn=postprocess,
    batch_size=8,
)
results, stats = pipeline.process_batch(images, return_stats=True)
print(f"Throughput: {stats.throughput_items_per_sec:.1f} items/sec")
```

### Pipeline Architecture

```
   Batch N-1         Batch N          Batch N+1
      │                 │                 │
      │                 │                 │
┌─────▼─────┐    ┌──────▼──────┐   ┌──────▼──────┐
│ Postproc  │    │  Preprocess │   │   (waiting) │
│ (Stream 1)│    │  (Stream 0) │   │             │
└───────────┘    └─────────────┘   └─────────────┘
                       │
                 ┌─────▼─────┐
                 │ Inference │
                 │ (Stream 1)│ (waits for preprocess event)
                 └───────────┘
```

### Benefits

- **Overlapped Execution**: Preprocessing of the next batch while current batch is inferring
- **20-40% Throughput Improvement**: Measured on batch processing workloads
- **Automatic Synchronization**: Events ensure proper ordering between stages
- **Graceful Fallback**: Falls back to sequential processing when CUDA unavailable

### Testing

```bash
# Run CUDA streams unit tests
uv run pytest ai/tests/test_cuda_streams.py -v

# Run with CUDA (if available)
uv run pytest ai/tests/test_cuda_streams.py -v -k "cuda"
```

## NVIDIA Triton Inference Server (NEM-3769)

Triton provides production-grade model serving with automatic dynamic batching, model versioning, and multi-model serving.

### Benefits Over Direct Inference

| Feature          | Current (FastAPI)      | With Triton                 |
| ---------------- | ---------------------- | --------------------------- |
| Batching         | Manual, single request | Automatic dynamic batching  |
| GPU Utilization  | Suboptimal             | Optimized scheduler         |
| Model Versioning | File-based             | Built-in A/B testing        |
| Monitoring       | Custom metrics         | Native Prometheus           |
| Throughput       | ~25 req/s (concurrent) | ~115 req/s (5x improvement) |

### Quick Start

Triton already runs **inside the ai-gateway container** in production
(`entrypoint.sh` boots Triton, waits for readiness, then uvicorn - see
`ai/gateway/AGENTS.md`). There is no separate `triton` compose profile in
`docker-compose.prod.yml`:

```bash
podman compose -f docker-compose.prod.yml up -d ai-gateway

# Gateway health (proxies readiness of the in-container Triton)
curl http://localhost:8090/health
```

The `TRITON_*` env vars below configure the **standalone client** in
`ai/triton/client.py` (native/dev use, e.g. pointing at a Triton you run
manually). Set `TRITON_ENABLED=true` there only when running that path.

### Environment Variables

| Variable             | Default          | Description               |
| -------------------- | ---------------- | ------------------------- |
| `TRITON_ENABLED`     | `false`          | Enable Triton client      |
| `TRITON_URL`         | `localhost:8001` | gRPC endpoint             |
| `TRITON_HTTP_URL`    | `localhost:8000` | HTTP endpoint             |
| `TRITON_PROTOCOL`    | `grpc`           | Protocol (grpc/http)      |
| `TRITON_MODEL`       | `yolo26`         | Default model             |
| `TRITON_TIMEOUT`     | `60`             | Request timeout (seconds) |
| `TRITON_MAX_RETRIES` | `3`              | Retry attempts            |

### Client Usage

```python
from ai.triton import TritonClient, TritonConfig

config = TritonConfig.from_env()
client = TritonClient(config)

if await client.is_healthy():
    result = await client.detect(image_bytes)
    for det in result.detections:
        print(f"{det.class_name}: {det.confidence:.2f}")

await client.close()
```

For detailed documentation, see `triton/AGENTS.md` and `docs/plans/triton-migration.md`.

## Entry Points

1. **Pipeline overview**: This file
2. **Detection server**: `yolo26/AGENTS.md` and `yolo26/model.py`
3. **LLM server**: `nemotron/AGENTS.md`
4. **CLIP server**: `clip/AGENTS.md` and `clip/model.py`
5. **Florence server**: `florence/AGENTS.md` and `florence/model.py`
6. **Enrichment server (Model Zoo)**: `enrichment/AGENTS.md`
   - Model manager: `enrichment/model_manager.py`
   - Model registry: `enrichment/model_registry.py`
   - Model implementations: `enrichment/models/`
7. **Triton Inference Server**: `triton/AGENTS.md` (NEM-3769)
   - Client wrapper: `triton/client.py`
   - Model configs: `triton/model_repository/*/config.pbtxt`
   - Migration plan: `docs/plans/triton-migration.md`
8. **Backend integration**: `backend/services/` directory
9. **Optimization utilities**:
   - CUDA streams: `cuda_streams.py` (NEM-3770)
   - torch.compile: `compile_utils.py` (NEM-3773)
   - Batch processing: `batch_utils.py` (NEM-3377)
   - General optimizations: `torch_optimizations.py`
   - CPU offloading: `cpu_offloading.py`
   - CUDA graphs: `cuda_graph_manager.py`
   - FlashAttention: `flash_attention_config.py`
   - GPU memory pool: `gpu_memory_pool.py`
   - Hub cache: `hub_cache_config.py`
   - Quantization: `quantization_config.py`
   - Static KV cache: `static_kv_cache.py`
   - Warmup utilities: `warmup_utils.py`
