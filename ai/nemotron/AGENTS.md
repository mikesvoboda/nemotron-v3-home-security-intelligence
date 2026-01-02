# Nemotron LLM Service Directory

## Purpose

Contains Nemotron language model configuration for AI-powered risk reasoning. The model runs via llama.cpp server (containerized with GPU passthrough) and analyzes batches of object detections to generate risk scores and summaries.

## Port and Resources

- **Port**: 8091
- **Expected VRAM**: ~14.7 GB (30B model) or ~3 GB (4B model)
- **Inference Time**: 2-5s per analysis

## Directory Contents

```
ai/nemotron/
├── AGENTS.md       # This file
├── Dockerfile      # Multi-stage build for llama.cpp with CUDA
├── config.json     # llama.cpp server config reference
└── .gitkeep        # Placeholder (GGUF models downloaded at runtime)
```

**Note**: GGUF model files are downloaded via `../download_models.sh` and are NOT committed to git.

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

```
MODEL_PATH=/models/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf
PORT=8091
GPU_LAYERS=30
CTX_SIZE=131072
PARALLEL=1
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

## Model Options

### Nemotron-3-Nano-30B-A3B (Production)

- **File**: `Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf`
- **Size**: ~16GB
- **VRAM**: ~14.7 GB
- **Context**: 131072 tokens
- **Startup script**: `../start_nemotron.sh`

### Nemotron Mini 4B Instruct (Development)

- **File**: `nemotron-mini-4b-instruct-q4_k_m.gguf`
- **Size**: ~2.5GB
- **VRAM**: ~3GB
- **Context**: 4096 tokens
- **Startup script**: `../start_llm.sh`

## API Endpoints (llama.cpp)

### GET /health

Health check endpoint.

### POST /completion

Raw completion endpoint.

```json
{
  "prompt": "Analyze this security event...",
  "temperature": 0.7,
  "max_tokens": 500
}
```

### POST /v1/chat/completions

OpenAI-compatible chat endpoint.

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

The backend (`nemotron_analyzer.py`) prompts Nemotron to return JSON with risk analysis:

| Score Range | Level    | Description                 |
| ----------- | -------- | --------------------------- |
| 0-29        | Low      | Normal activity             |
| 30-59       | Medium   | Unusual but not threatening |
| 60-84       | High     | Suspicious activity         |
| 85-100      | Critical | Potential security threat   |

## Backend Integration

Called by `backend/services/nemotron_analyzer.py`:

```python
analyzer = NemotronAnalyzer(redis_client)
event = await analyzer.analyze_batch(batch_id)
# Returns Event with risk_score, risk_level, summary, reasoning
```

## Starting the Service

### Container (Production)

```bash
docker compose -f docker-compose.prod.yml up ai-llm
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
- GPU layers: 45 (configurable via `NEMOTRON_GPU_LAYERS`)
- Startup timeout: 90 seconds
- Log file: `/tmp/nemotron.log`

## Prerequisites

- **llama.cpp**: `llama-server` binary must be available (built in container)
- **CUDA**: Required for GPU acceleration
- **VRAM**: 3GB (4B model) or 16GB (30B model)

## Testing

```bash
# Health check
curl http://localhost:8091/health

# Test completion
curl -X POST http://localhost:8091/completion \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Analyze: A person detected at 14:30.", "max_tokens": 200}'

# OpenAI-compatible chat
curl -X POST http://localhost:8091/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is a security risk?"}],
    "max_tokens": 100
  }'
```

## Entry Points

1. **Dockerfile**: Container build with llama.cpp compilation
2. **config.json**: Reference configuration parameters
3. **Start scripts**: `../start_llm.sh` (4B) or `../start_nemotron.sh` (30B)
4. **Backend integration**: `backend/services/nemotron_analyzer.py`
