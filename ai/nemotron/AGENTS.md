# Nemotron LLM Service Directory

## Purpose

Contains Nemotron language model configuration for AI-powered risk reasoning. The model runs via llama.cpp server and analyzes batches of object detections to generate risk scores and summaries.

## Directory Contents

```
ai/nemotron/
├── AGENTS.md                                  # This file
├── config.json                                # llama.cpp server config reference (informational)
├── .gitkeep                                   # Placeholder for git
└── nemotron-mini-4b-instruct-q4_k_m.gguf     # Downloaded model file (not in git)
```

## config.json

Reference configuration for llama.cpp server:

```json
{
  "model": "ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf",
  "host": "0.0.0.0",
  "port": 8091,
  "ctx_size": 4096,
  "n_gpu_layers": 99,
  "parallel": 2,
  "cont_batching": true
}
```

**Note**: This file is informational. The actual configuration is passed via command-line arguments in the startup scripts.

## Model Options

### Nemotron Mini 4B Instruct (Default)

- **File**: `nemotron-mini-4b-instruct-q4_k_m.gguf`
- **Size**: ~2.5GB
- **VRAM**: ~3GB
- **Context**: 4096 tokens
- **Startup script**: `../start_llm.sh`

### Nemotron-3-Nano-30B-A3B (Alternative)

- **File**: `Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf`
- **Size**: ~16GB
- **VRAM**: ~16GB
- **Context**: 12288 tokens
- **Startup script**: `../start_nemotron.sh`

## Starting the Service

### Simple startup (4B model):

```bash
./ai/start_llm.sh
```

Configuration:

- Port: 8091
- Context: 4096 tokens
- GPU layers: 99 (all on GPU)
- Host: 0.0.0.0

### Advanced startup with auto-recovery (30B model):

```bash
./ai/start_nemotron.sh
```

Configuration:

- Port: 8091 (configurable via `NEMOTRON_PORT`)
- Context: 12288 (configurable via `NEMOTRON_CONTEXT_SIZE`)
- GPU layers: 45 (configurable via `NEMOTRON_GPU_LAYERS`)
- Startup timeout: 90 seconds
- Log file: `/tmp/nemotron.log`

**Model search paths**:

1. `$NEMOTRON_MODEL_PATH`
2. `/export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf`
3. `ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf`

**llama-server search paths**:

1. `$LLAMA_SERVER_PATH`
2. `/usr/bin/llama-server`
3. `/export/ai_models/nemotron/llama.cpp/build/bin/llama-server`
4. System PATH

## API Endpoints (llama.cpp)

### `GET /health`

Health check.

### `POST /completion`

```json
{
  "prompt": "Analyze this security event...",
  "temperature": 0.7,
  "max_tokens": 500
}
```

### `POST /v1/chat/completions`

OpenAI-compatible chat endpoint.

## Backend Integration

Called by `backend/services/nemotron_analyzer.py`:

```python
analyzer = NemotronAnalyzer(redis_client)
event = await analyzer.analyze_batch(batch_id)
# Returns Event with risk_score, risk_level, summary, reasoning
```

### Risk Scoring

- **0-25 (low)**: Normal activity
- **26-50 (medium)**: Unusual but not threatening
- **51-75 (high)**: Suspicious activity
- **76-100 (critical)**: Potential security threat

## Prerequisites

- **llama.cpp**: `llama-server` command must be available
- **CUDA**: Required for GPU acceleration
- **VRAM**: 3GB (4B model) or 16GB (30B model)

### Installing llama.cpp

```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make LLAMA_CUDA=1
sudo ln -s $(pwd)/llama-server /usr/local/bin/llama-server
```

## Testing

```bash
# Health check
curl http://localhost:8091/health

# Test completion
curl -X POST http://localhost:8091/completion \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Analyze: A person detected at 14:30.", "max_tokens": 200}'
```

## Entry Points

1. **Config**: `config.json` - llama.cpp parameters reference
2. **Simple startup**: `../start_llm.sh` - 4B model
3. **Advanced startup**: `../start_nemotron.sh` - 30B model with auto-recovery
4. **Model download**: `../download_models.sh` - model acquisition
5. **Backend integration**: `backend/services/nemotron_analyzer.py`
