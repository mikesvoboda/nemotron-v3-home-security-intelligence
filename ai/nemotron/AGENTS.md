# NVIDIA Nemotron LLM Service Directory

## Purpose

Contains configuration for **NVIDIA Nemotron** language models that power AI-driven risk reasoning. The models run via [llama.cpp](https://github.com/ggerganov/llama.cpp) server (containerized with NVIDIA GPU passthrough) and analyze batches of object detections to generate risk scores and natural language summaries.

**NVIDIA Nemotron** is a family of large language models optimized for reasoning and instruction-following tasks. This project uses GGUF quantized versions for efficient local inference.

## Port and Resources

- **Port**: 8091
- **Server**: llama.cpp with CUDA 12.4.1
- **Inference Time**: 2-5s per analysis
- **Format**: ChatML with `<|im_start|>` / `<|im_end|>` message delimiters

## Directory Contents

```
ai/nemotron/
├── AGENTS.md       # This file
├── Dockerfile      # Multi-stage build for llama.cpp with CUDA
├── config.json     # llama.cpp server config reference
└── .gitkeep        # Placeholder (GGUF models downloaded at runtime)
```

**Note**: GGUF model files are downloaded via `../download_models.sh` and are NOT committed to git.

## Model Options

This project supports two NVIDIA Nemotron models depending on deployment profile:

### Production Model: NVIDIA Nemotron-3-Nano-30B-A3B

The production model is NVIDIA's state-of-the-art reasoning model with massive context capability.

| Specification      | Value                                                                                             |
| ------------------ | ------------------------------------------------------------------------------------------------- |
| **Model Name**     | Nemotron-3-Nano-30B-A3B                                                                           |
| **HuggingFace**    | [nvidia/Nemotron-3-Nano-30B-A3B-GGUF](https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF) |
| **Filename**       | `Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf`                                                             |
| **Parameters**     | 30 billion (A3B active routing variant)                                                           |
| **Quantization**   | Q4_K_M (4-bit, medium quality)                                                                    |
| **File Size**      | ~18 GB                                                                                            |
| **VRAM Required**  | ~14.7 GB                                                                                          |
| **Context Window** | 131,072 tokens (128K)                                                                             |
| **Architecture**   | Transformer with Mixture-of-Experts (MoE) routing                                                 |
| **Startup Script** | `../start_nemotron.sh`                                                                            |

**Why 128K Context Matters:**

- Analyze all detections across an extended time window (hours of activity)
- Include rich historical baselines ("Is this normal for 3am on Tuesday?")
- Correlate activity across multiple cameras in a single prompt
- Process detailed enrichment data (clothing, vehicles, behavior, scene descriptions)

### Development Model: NVIDIA Nemotron Mini 4B Instruct

For development and resource-constrained environments.

| Specification      | Value                                                                                                       |
| ------------------ | ----------------------------------------------------------------------------------------------------------- |
| **Model Name**     | Nemotron Mini 4B Instruct                                                                                   |
| **HuggingFace**    | [bartowski/nemotron-mini-4b-instruct-GGUF](https://huggingface.co/bartowski/nemotron-mini-4b-instruct-GGUF) |
| **Filename**       | `nemotron-mini-4b-instruct-q4_k_m.gguf`                                                                     |
| **Parameters**     | 4 billion                                                                                                   |
| **Quantization**   | Q4_K_M (4-bit, medium quality)                                                                              |
| **File Size**      | ~2.5 GB                                                                                                     |
| **VRAM Required**  | ~3 GB                                                                                                       |
| **Context Window** | 4,096 tokens                                                                                                |
| **Startup Script** | `../start_llm.sh`                                                                                           |

## Key Files

### `Dockerfile`

Multi-stage build for llama.cpp with CUDA support:

**Stage 1 (Builder):**

- Base: `nvidia/cuda:12.4.1-devel-ubuntu22.04`
- Clones llama.cpp from GitHub (commit `9496bbb80`)
- Builds with `GGML_CUDA=ON` for GPU support

**Stage 2 (Runtime):**

- Base: `nvidia/cuda:12.4.1-runtime-ubuntu22.04`
- Copies compiled `llama-server` binary
- Non-root user: `llama` for security
- Health check with 120s start period for model loading

**Environment Variables:**

```bash
MODEL_PATH=/models/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf
PORT=8091
GPU_LAYERS=35        # Layers offloaded to GPU (adjust for VRAM)
CTX_SIZE=131072      # Full 128K context window
PARALLEL=1           # Single-slot dedicated inference
```

**CMD:**

```bash
llama-server --model ${MODEL_PATH} \
  --host 0.0.0.0 --port ${PORT} \
  --n-gpu-layers ${GPU_LAYERS} \
  --ctx-size ${CTX_SIZE} \
  --parallel ${PARALLEL} \
  --cont-batching --metrics
```

### `config.json`

Reference configuration for llama.cpp server (informational only):

```json
{
  "model": "ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf",
  "host": "0.0.0.0",
  "port": 8091,
  "ctx_size": 131072,
  "n_gpu_layers": 99,
  "parallel": 1,
  "cont_batching": true
}
```

**Note**: Actual configuration is passed via command-line arguments, not this file.

## API Endpoints (llama.cpp)

### GET /health

Health check endpoint. Returns 200 when model is loaded and ready.

### POST /completion

Raw completion endpoint. This is the primary endpoint used by the backend.

```json
{
  "prompt": "<|im_start|>system\nYou are a security analyst...<|im_end|>\n<|im_start|>user\n...",
  "temperature": 0.7,
  "max_tokens": 1536,
  "stop": ["<|im_end|>", "<|im_start|>"]
}
```

### POST /v1/chat/completions

OpenAI-compatible chat endpoint (alternative).

```json
{
  "messages": [
    { "role": "system", "content": "You are a security analyst." },
    { "role": "user", "content": "Analyze: person detected at front door" }
  ],
  "temperature": 0.7,
  "max_tokens": 500
}
```

## Risk Scoring

The backend (`nemotron_analyzer.py`) prompts NVIDIA Nemotron to return JSON with risk analysis:

| Score Range | Level    | Description                 |
| ----------- | -------- | --------------------------- |
| 0-29        | Low      | Normal activity             |
| 30-59       | Medium   | Unusual but not threatening |
| 60-84       | High     | Suspicious activity         |
| 85-100      | Critical | Potential security threat   |

## Prompt Engineering

### ChatML Format

NVIDIA Nemotron uses ChatML format for message structuring. All prompts use these delimiters:

```
<|im_start|>system
{system message}
<|im_end|>
<|im_start|>user
{user message}
<|im_end|>
<|im_start|>assistant
{model response begins here}
```

**Stop Tokens**: `["<|im_end|>", "<|im_start|>"]` - The model stops generation at these tokens.

### Prompt Templates

The backend uses five prompt templates with increasing sophistication. Selection is automatic based on available enrichment data:

| Template        | When Used                                     | Key Features                                       |
| --------------- | --------------------------------------------- | -------------------------------------------------- |
| `basic`         | Fallback when enrichment unavailable          | Camera, time, detection list only                  |
| `enriched`      | Zone/baseline/cross-camera context available  | Adds zone analysis, baseline comparison, deviation |
| `full_enriched` | Enriched + license plates/faces from pipeline | Adds vision enrichment (plates, faces, OCR)        |
| `vision`        | Florence-2 extraction + context enrichment    | Detailed attributes, re-ID, scene analysis         |
| `model_zoo`     | Full model zoo enrichment available           | Violence, weather, clothing, vehicles, pets, depth |

### Prompt Template Details

**Basic Prompt** (`RISK_ANALYSIS_PROMPT`):

- Camera name and time window
- Simple detection list with timestamps and confidence
- Risk level guidelines

**Enriched Prompt** (`ENRICHED_RISK_ANALYSIS_PROMPT`):

- Zone analysis (entry points, high-security areas)
- Baseline comparison (expected vs. actual activity)
- Deviation score (0 = normal, 1 = highly unusual)
- Cross-camera correlation summary

**Full Enriched Prompt** (`FULL_ENRICHED_RISK_ANALYSIS_PROMPT`):

- All enriched context plus:
- License plate detections (known vs. unknown)
- Face detections for identity review
- OCR text from images

**Vision Enhanced Prompt** (`VISION_ENHANCED_RISK_ANALYSIS_PROMPT`):

- Florence-2 vision-language attributes (clothing, actions, carrying items)
- Person/vehicle re-identification context
- Scene analysis (environment description)
- Service worker detection (lower risk)

**Model Zoo Enhanced Prompt** (`MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT`):

- Violence detection alerts
- Weather/visibility context
- Detailed clothing analysis (FashionCLIP + SegFormer)
- Face covering detection
- Vehicle type and damage analysis
- Pet detection (false positive filtering)
- Pose and action recognition
- Image quality/tampering indicators
- Comprehensive risk interpretation guide

### Generation Parameters

```python
payload = {
    "prompt": prompt,
    "temperature": 0.7,    # Balanced creativity/consistency
    "top_p": 0.95,         # Nucleus sampling
    "max_tokens": 1536,    # Room for detailed explanations
    "stop": ["<|im_end|>", "<|im_start|>"]  # ChatML terminators
}
```

### Response Parsing

NVIDIA Nemotron-3-Nano outputs `<think>...</think>` reasoning blocks before JSON. The backend:

1. Strips `<think>...</think>` blocks
2. Extracts JSON using regex pattern matching
3. Validates `risk_score` (0-100) and `risk_level` (low/medium/high/critical)
4. Provides fallbacks if parsing fails

## Backend Integration

Called by `backend/services/nemotron_analyzer.py`:

```python
from backend.services.nemotron_analyzer import NemotronAnalyzer

analyzer = NemotronAnalyzer(
    redis_client=redis_client,
    use_enriched_context=True,       # Zone/baseline enrichment
    use_enrichment_pipeline=True,    # License plates, faces, model zoo
)

# Batch analysis (normal path)
event = await analyzer.analyze_batch(batch_id, camera_id, detection_ids)

# Fast path (high-confidence critical detections)
event = await analyzer.analyze_detection_fast_path(camera_id, detection_id)
```

### Integration Flow

1. Load detection details from database
2. Enrich context (zones, baselines, cross-camera)
3. Run enrichment pipeline (plates, faces, model zoo)
4. Select appropriate prompt template
5. POST to `/completion` endpoint
6. Parse and validate JSON response
7. Create Event record with risk assessment
8. Broadcast via WebSocket

## Starting the Service

### Container (Production)

```bash
docker compose -f docker-compose.prod.yml up ai-llm
```

The production configuration mounts the model from:

```
${AI_MODELS_PATH:-/export/ai_models}/nemotron/nemotron-3-nano-30b-a3b-q4km:/models:ro
```

### Native (Development)

**4B Model (Simple):**

```bash
./ai/start_llm.sh
```

**30B Model (Advanced with auto-recovery):**

```bash
./ai/start_nemotron.sh
```

Configuration for `start_nemotron.sh`:

- Port: 8091 (configurable via `NEMOTRON_PORT`)
- Context: 12288 (configurable via `NEMOTRON_CONTEXT_SIZE`)
- GPU layers: 35 (configurable via `NEMOTRON_GPU_LAYERS`)
- Startup timeout: 90 seconds
- Log file: `/tmp/nemotron.log`

## Prerequisites

- **llama.cpp**: `llama-server` binary must be available (built in container)
- **CUDA**: NVIDIA CUDA 11.8+ required for GPU acceleration
- **VRAM**: ~3 GB (4B model) or ~14.7 GB (30B model)
- **Disk**: ~2.5 GB (4B model) or ~18 GB (30B model)

## Testing

```bash
# Health check
curl http://localhost:8091/health

# Test completion with ChatML format
curl -X POST http://localhost:8091/completion \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "<|im_start|>system\nYou are a security analyst.<|im_end|>\n<|im_start|>user\nAnalyze: A person detected at 14:30 at the front door.<|im_end|>\n<|im_start|>assistant\n",
    "temperature": 0.7,
    "max_tokens": 500,
    "stop": ["<|im_end|>"]
  }'

# OpenAI-compatible chat
curl -X POST http://localhost:8091/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is a security risk?"}],
    "max_tokens": 100
  }'
```

## Performance Characteristics

| Metric              | Production (30B)      | Development (4B)       |
| ------------------- | --------------------- | ---------------------- |
| Inference time      | 2-5 seconds           | 1-3 seconds            |
| Token generation    | ~50-100 tokens/second | ~100-200 tokens/second |
| Context processing  | ~1000 tokens/second   | ~2000 tokens/second    |
| Concurrent requests | 1-2 (configured)      | 2-4 (configurable)     |
| VRAM usage          | ~14.7 GB              | ~3 GB                  |

## Entry Points

1. **Dockerfile**: Container build with llama.cpp compilation
2. **config.json**: Reference configuration parameters
3. **Start scripts**: `../start_llm.sh` (4B) or `../start_nemotron.sh` (30B)
4. **Backend integration**: `backend/services/nemotron_analyzer.py`
5. **Prompt templates**: `backend/services/prompts.py`

## Related Documentation

- [AI Pipeline Architecture](../../docs/architecture/ai-pipeline.md)
- [Risk Analysis Developer Guide](../../docs/developer/risk-analysis.md)
- [AI Configuration](../../docs/operator/ai-configuration.md)
- [Model Zoo Enrichment](../../docs/plans/prompt-enrichment-tasks.md)

## External Resources

- [NVIDIA Nemotron-3-Nano-30B-A3B on HuggingFace](https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF)
- [llama.cpp GitHub Repository](https://github.com/ggerganov/llama.cpp)
- [GGUF Format Specification](https://github.com/ggerganov/ggml/blob/master/docs/gguf.md)
