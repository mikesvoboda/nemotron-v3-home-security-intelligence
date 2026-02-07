# LLM Inference Performance Optimization

This document describes the current Nemotron LLM inference configuration, recent performance optimizations, observed characteristics, known limitations, and recommended next steps.

## Current LLM Configuration

### Model and Quantization

| Parameter        | Value                                                        |
| ---------------- | ------------------------------------------------------------ |
| Model            | Nemotron-3-Nano-30B-A3B (31B parameters, Mixture of Experts) |
| Quantization     | Q4_K_M (4-bit, k-quant medium)                               |
| Model file       | `Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf`                        |
| Inference server | llama.cpp (`llama-server`)                                   |
| CUDA toolkit     | 13.1.1                                                       |

The GGUF model file is mounted read-only into the container at `/models/` from the host path configured by `AI_MODELS_PATH` (default: `/export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km`).

### Server Flags

The `ai-llm` service runs `llama-server` with the following flags, configured via environment variables in `.env`:

```
llama-server \
    --model /models/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf \
    --host 0.0.0.0 \
    --port 8091 \
    --n-gpu-layers ${GPU_LAYERS}   # 999 = all layers on GPU \
    --ctx-size ${CTX_SIZE}         # 32768 tokens \
    --parallel ${PARALLEL}         # 2 concurrent slots \
    --cont-batching \
    --metrics \
    --flash-attn on                # conditional on FLASH_ATTENTION=true
```

Flags are injected via the Dockerfile CMD and Docker Compose environment variables. The Dockerfile defaults are overridden by `.env` values through `docker-compose.prod.yml`.

### Environment Variables (`.env` -- Single Source of Truth)

| Variable          | Default | Description                                                                                                                        |
| ----------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `GPU_LAYERS`      | `999`   | Number of model layers offloaded to GPU. `999` means all layers.                                                                   |
| `CTX_SIZE`        | `32768` | Context window size in tokens. Shared between llama.cpp and the Python backend (via `validation_alias="CTX_SIZE"` in `config.py`). |
| `PARALLEL`        | `2`     | Number of concurrent inference slots. llama.cpp splits `CTX_SIZE` evenly across slots (2 slots = 16K tokens each).                 |
| `FLASH_ATTENTION` | `true`  | Enables flash attention in llama.cpp to reduce VRAM usage with minimal performance impact.                                         |
| `GPU_LLM`         | `0`     | GPU index for the LLM service (maps to `CUDA_VISIBLE_DEVICES`).                                                                    |
| `LLM_PORT`        | `8091`  | Host port bound to `127.0.0.1` for the LLM service.                                                                                |

### Backend Configuration (`backend/core/config.py`)

The Python backend reads these settings for prompt token budgeting:

| Setting                                 | Default       | Source                                                                   |
| --------------------------------------- | ------------- | ------------------------------------------------------------------------ |
| `nemotron_context_window`               | `32768`       | Reads from `CTX_SIZE` env var (validation_alias). Range: 1,000--131,072. |
| `nemotron_max_output_tokens`            | `1536`        | Tokens reserved for the LLM response. Range: 100--8,192.                 |
| `context_utilization_warning_threshold` | `0.80`        | Logs a warning when prompt tokens exceed 80% of available context.       |
| `llm_tokenizer_encoding`                | `cl100k_base` | Tiktoken encoding used for token counting.                               |
| `enrichment_pipeline_timeout_seconds`   | `30.0`        | Hard timeout for the enrichment pipeline before Nemotron analysis.       |

Available tokens for the prompt = `CTX_SIZE - nemotron_max_output_tokens` = 32,768 - 1,536 = **31,232 tokens**.

### Container Configuration (`docker-compose.prod.yml`)

The `ai-llm` service in the production compose file:

- **Build context:** `./ai/nemotron` (multi-stage build with CUDA 13.1.1)
- **Port:** `127.0.0.1:${LLM_PORT:-8091}:8091` (localhost-only binding)
- **Resource limits:** 4 CPUs, 12GB RAM (8GB reserved)
- **GPU:** All GPUs passed; `CUDA_VISIBLE_DEVICES` selects GPU 0 (A5500 24GB)
- **Health check:** `curl -f http://localhost:8091/health` every 10s, 300s start period (model loading takes ~5 minutes for 31B parameters)
- **Restart policy:** `unless-stopped`

## Recent Optimizations (NEM-5369)

### 1. Parallel Inference Slots (`PARALLEL=2`)

llama.cpp now runs with 2 concurrent inference slots, each allocated 16K tokens (CTX_SIZE / PARALLEL = 32,768 / 2). This enables the backend to process two batch analysis requests simultaneously, effectively doubling throughput for concurrent batches. The `ANALYSIS_WORKER_COUNT=2` setting in `.env` matches the slot count.

### 2. Context Window Right-Sizing (`CTX_SIZE=32768`)

The context window was reduced from 131,072 (128K) to 32,768 (32K) tokens. This change:

- Saves approximately 4GB of VRAM (KV cache scales linearly with context size)
- Is sufficient for home security analysis prompts, which typically consume 5K--10K tokens
- Established `CTX_SIZE` in `.env` as the single source of truth, read by both llama.cpp (via Docker environment) and the Python backend (via Pydantic `validation_alias`)

### 3. Flash Attention Enabled (`FLASH_ATTENTION=true`)

Flash attention reduces VRAM consumption by computing attention scores without materializing the full attention matrix. It is conditionally enabled in the Dockerfile CMD:

```sh
if [ "${FLASH_ATTENTION}" = 'true' ]; then FLASH_ARGS='--flash-attn on'; fi
```

This provides VRAM savings with minimal latency impact.

### 4. Prompt Token Budgeting System

The `TokenCounter` service (`backend/services/token_counter.py`) manages context window usage:

- **Tiktoken-based counting:** Uses `cl100k_base` encoding for accurate token estimation
- **Validation:** Checks prompts against `context_window - max_output_tokens` before sending to the LLM
- **Intelligent truncation:** When prompts exceed the budget, enrichment sections are removed in priority order (lowest-value sections first: depth, pose, action, pet, weather, vehicle, clothing, violence, reid, then high-priority sections like scene analysis and detections)
- **Prometheus metrics:** Context utilization is tracked via `hsi_context_utilization_ratio` gauge for Grafana dashboards

### 5. Prompt Deduplication

The enrichment pipeline avoids sending redundant information to the LLM:

- **Florence-2:** Region-level captions and global dense captions are deduplicated when they describe the same objects
- **CLIP:** Low-confidence classification results below the noise threshold are filtered before inclusion in the prompt

### 6. Adaptive Enrichment Quality Levels

The `ENRICHMENT_QUALITY_LEVEL` setting (`full`, `standard`, `minimal`) controls how many enrichment models run before LLM analysis:

| Level      | Models Run                                                                                                               | Use Case                               |
| ---------- | ------------------------------------------------------------------------------------------------------------------------ | -------------------------------------- |
| `full`     | All models (Florence captions, CLIP embeddings, pose, threat, action, vehicle, clothing, demographics, depth, pet, reid) | Default -- best accuracy               |
| `standard` | Skip Florence enhanced captioning + CLIP classification                                                                  | Faster processing, reduced prompt size |
| `minimal`  | Only detections + threat/pose/action                                                                                     | Fastest -- for high-load scenarios     |

Lower quality levels produce smaller prompts, reducing both token consumption and LLM inference time.

## Performance Characteristics

### VRAM Usage

| Component                       | VRAM      | Notes                                                                                                   |
| ------------------------------- | --------- | ------------------------------------------------------------------------------------------------------- |
| Model weights (Q4_K_M)          | ~14.7GB   | 35 of ~60 layers on GPU (with GPU_LAYERS=999, some layers may spill to CPU depending on available VRAM) |
| KV cache (32K context, 2 slots) | ~2GB      | Scales with CTX_SIZE and PARALLEL                                                                       |
| Flash attention overhead        | Minimal   | Reduces peak VRAM vs. standard attention                                                                |
| **Total**                       | **~17GB** | Fits within 24GB A5500 with room for Florence-2 (~1.5GB)                                                |

### Token Budget

| Budget Component                 | Tokens         |
| -------------------------------- | -------------- |
| Context window                   | 32,768         |
| Reserved for output              | 1,536          |
| Available for prompt             | 31,232         |
| Typical prompt (full enrichment) | 5,000--10,000  |
| Worst-case prompt                | ~10,000        |
| Headroom                         | ~21,000 tokens |

### Throughput

- **Parallel slots:** 2 concurrent requests processed simultaneously
- **Batch window:** 90 seconds (detections grouped before analysis)
- **Idle timeout:** 30 seconds (batch closes after inactivity)
- **Pipeline timeout:** 30 seconds hard limit on enrichment before LLM call
- **LLM read timeout:** 120 seconds maximum wait for inference response
- **Analysis workers:** 2 concurrent workers pulling from the analysis queue

### GPU Assignment (Dual-GPU Setup)

| GPU   | Device                  | Services                                                                                 | VRAM Budget            |
| ----- | ----------------------- | ---------------------------------------------------------------------------------------- | ---------------------- |
| GPU 0 | NVIDIA RTX A5500 (24GB) | ai-llm (~17GB), ai-florence (~1.5GB)                                                     | ~22GB used             |
| GPU 1 | NVIDIA A400 (4GB)       | ai-yolo26 (~5MB), ai-clip (~0.8GB), ai-enrichment-light (~1.2GB), ai-enrichment (~4.3GB) | ~6.3GB across services |

## Known Limitations

### 1. CPU Layer Overflow

With `GPU_LAYERS=999`, llama.cpp attempts to place all ~60 model layers on GPU. However, with the KV cache and other GPU-resident services (Florence-2), approximately 6 layers overflow to CPU RAM. CPU-offloaded layers add latency to each forward pass since data must transfer across the PCIe bus.

### 2. Q4_K_M Quantization Tradeoff

The Q4_K_M quantization reduces the model from ~60GB (FP16) to ~17GB, enabling single-GPU inference. However, 4-bit quantization introduces some accuracy degradation compared to higher-precision formats (FP16, Q8_0). For home security risk scoring, this tradeoff is acceptable -- the model produces coherent risk assessments with structured JSON output.

### 3. Reduced Context Window

The context window was reduced from 128K to 32K to fit within VRAM constraints. While 32K is sufficient for current prompt sizes (typical: 5K--10K tokens), this limits the system's ability to include very large enrichment contexts or analyze many simultaneous detections in a single prompt. The `TokenCounter` truncation system mitigates this by intelligently removing low-priority sections.

### 4. Single Model Architecture

The system relies on a single LLM instance. If the model is busy processing one request, the second slot is available, but any additional requests queue behind the 2 parallel slots. Under sustained high load (more than 2 concurrent analysis requests), latency increases.

## Recommended Next Steps

### Short-Term (VRAM Optimization)

#### MoE Expert Offloading (NEM-5536)

Nemotron-3-Nano's MoE layers have 128 experts per layer but only 6 activate per token. Offloading expert FFN weights to CPU frees 3--6 GB of VRAM with minimal latency impact. See [MoE Offloading](moe-offloading.md) for full documentation and setup instructions.

#### KV Cache Quantization

llama.cpp supports quantized KV caches that reduce VRAM usage with minimal quality impact:

```bash
llama-server \
    --cache-type-k q8_0 \
    --cache-type-v q4_0 \
    ...
```

- **Expected savings:** 2--3GB VRAM (KV cache compressed from FP16 to mixed Q8/Q4)
- **Impact:** Negligible quality degradation for most tasks
- **Benefit:** Could free enough VRAM to fit all model layers on GPU, eliminating CPU overflow latency

#### More Aggressive Quantization

Smaller quantization formats could fit the entire model on GPU:

| Format           | Estimated Size | Quality  | All Layers on GPU?   |
| ---------------- | -------------- | -------- | -------------------- |
| Q4_K_M (current) | ~17GB          | Good     | No (6 layers on CPU) |
| Q3_K_M           | ~14GB          | Moderate | Likely yes           |
| IQ3_XXS          | ~12GB          | Lower    | Yes, with headroom   |

Tradeoff: Lower quantization reduces risk scoring accuracy. Recommended to benchmark against the current Q4_K_M baseline before switching.

### Medium-Term (Throughput)

#### Speculative Decoding with Draft Model

llama.cpp supports speculative decoding where a smaller "draft" model proposes tokens that the main model verifies in batch. NVIDIA offers Nemotron-Mini-4B-Instruct as a potential draft model:

- **Expected speedup:** 1.5--2.5x for structured JSON output (high acceptance rate)
- **Additional VRAM:** ~2.5GB for the 4B draft model
- **Requirement:** Both models must share the same tokenizer vocabulary

#### vLLM Evaluation

The `ai-llm-vllm` service is already defined in `docker-compose.prod.yml` (behind the `vllm` profile) for benchmarking:

- **PagedAttention v2:** More efficient KV cache memory management
- **Continuous batching:** Better throughput under concurrent load
- **Limitation:** Nemotron-3-Nano-30B quantized formats (NVFP4, AWQ) have compatibility issues with current vLLM builds and the RTX A5500 GPU. GGUF quantizations via llama.cpp remain the recommended path until vLLM support matures.

### Long-Term (Architecture)

#### Smaller Model Evaluation

With the enrichment pipeline providing rich structured context (Florence-2 captions, CLIP embeddings, pose analysis, threat detection, vehicle classification), a smaller LLM may be sufficient for risk scoring:

- **Candidate:** Nemotron-Mini-8B (or 4B) with full enrichment context
- **Rationale:** If enrichment models handle perception, the LLM only needs to reason about risk -- a simpler task
- **Benefit:** Dramatically lower VRAM (fits entirely on GPU with room for additional parallel slots), faster inference
- **Requirement:** Benchmark risk scoring quality against the 30B model

#### Dedicated Inference GPU

Adding a second high-VRAM GPU (e.g., RTX A5500 or A6000) would allow:

- Full model on GPU with no CPU overflow
- Higher `PARALLEL` slot count (3--4 concurrent requests)
- Larger context window (64K--128K) for complex multi-camera scenarios

## Key Files Reference

| File                                      | Purpose                                                                                        |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `ai/nemotron/Dockerfile`                  | Multi-stage build for llama.cpp with CUDA; defines model path, default env vars, CMD flags     |
| `.env` / `.env.example`                   | Single source of truth for `CTX_SIZE`, `GPU_LAYERS`, `PARALLEL`, `FLASH_ATTENTION`, `GPU_LLM`  |
| `docker-compose.prod.yml`                 | `ai-llm` service definition with resource limits, health checks, GPU assignment                |
| `backend/core/config.py`                  | `nemotron_context_window` (reads `CTX_SIZE`), `nemotron_max_output_tokens`, tokenizer settings |
| `backend/services/token_counter.py`       | Token counting, prompt validation, intelligent truncation by priority                          |
| `backend/services/nemotron_analyzer.py`   | Prompt assembly, LLM API calls, retry logic, structured JSON parsing                           |
| `backend/services/enrichment_pipeline.py` | Multi-model enrichment with quality levels and timeout                                         |
| `backend/services/prompts.py`             | Prompt templates for different enrichment levels                                               |
