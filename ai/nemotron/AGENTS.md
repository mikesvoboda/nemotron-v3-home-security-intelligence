# Nemotron LLM Service Directory

## Purpose

This directory contains the Nemotron Mini 4B Instruct language model used for AI-powered risk reasoning and natural language generation in the home security system. The model runs via llama.cpp server and analyzes batches of object detections to generate risk scores and summaries.

## Directory Contents

```
ai/nemotron/
├── AGENTS.md                                    # This file
├── config.json                                  # llama.cpp server runtime config reference
├── .gitkeep                                     # Placeholder for git
└── nemotron-mini-4b-instruct-q4_k_m.gguf       # Downloaded model file (not in git)
```

### Model File (Downloaded)

**Filename**: `nemotron-mini-4b-instruct-q4_k_m.gguf`

- **Size**: ~2.5GB
- **Format**: GGUF (GPT-Generated Unified Format)
- **Quantization**: Q4_K_M (4-bit with K-quant medium)
- **Source**: HuggingFace (bartowski/nemotron-mini-4b-instruct-GGUF)
- **Base model**: NVIDIA Nemotron Mini 4B Instruct
- **Purpose**: Risk assessment and natural language reasoning

## Model Information

### Nemotron Mini 4B Instruct

- **Parameters**: 4 billion
- **Architecture**: Decoder-only transformer (GPT-style)
- **Training**: Instruction-tuned for following directions and reasoning tasks
- **Context window**: 4096 tokens
- **Quantization**: Q4_K_M reduces memory from ~8GB to ~2.5GB with minimal quality loss
- **Inference speed**: ~2-5 seconds per risk analysis

### VRAM Usage

- **Q4_K_M quantization**: ~3GB VRAM
- **GPU layers**: 99 (all layers offloaded to GPU)
- **CPU fallback**: Available but much slower

## Starting the Service

### Download model (first time only):

```bash
cd /home/msvoboda/github/nemotron-v3-home-security-intelligence
./ai/download_models.sh

# Or provide custom model path:
NEMOTRON_GGUF_PATH=/path/to/model.gguf ./ai/download_models.sh
```

### Start LLM server:

```bash
./ai/start_llm.sh

# Or with custom model path:
NEMOTRON_MODEL_PATH=/path/to/model.gguf ./ai/start_llm.sh
```

This starts `llama-server` with configuration (also mirrored in `ai/nemotron/config.json`):

- **Port**: 8091
- **Model**: `ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf`
- **Context size**: 4096 tokens
- **GPU layers**: 99 (all on GPU)
- **Host**: 0.0.0.0 (accessible from network)
- **Parallelism**: 2 concurrent requests
- **Continuous batching**: Enabled for better throughput

Server runs at: `http://localhost:8091`

## API Endpoints (llama.cpp)

The llama-server provides standard llama.cpp endpoints:

### `GET /health`

Health check endpoint.

### `POST /completion`

Generate text completion from prompt.

**Request**:

```json
{
  "prompt": "Your prompt here...",
  "temperature": 0.7,
  "max_tokens": 500,
  "stop": ["\n\n"]
}
```

**Response**:

```json
{
  "content": "Generated text response...",
  "model": "nemotron-mini-4b-instruct-q4_k_m.gguf",
  "tokens_predicted": 120,
  "tokens_evaluated": 50
}
```

### Other endpoints

- `GET /v1/models` - List available models
- `POST /v1/chat/completions` - OpenAI-compatible chat endpoint
- `POST /tokenize` - Tokenize input text
- `POST /detokenize` - Convert tokens to text

See llama.cpp documentation for full API reference.

## Integration with Backend

Called by `backend/services/nemotron_analyzer.py`:

```python
from backend.services.nemotron_analyzer import NemotronAnalyzer

analyzer = NemotronAnalyzer(redis_client)
event = await analyzer.analyze_batch(batch_id)
# Returns Event with risk_score, risk_level, summary, reasoning
```

### Analysis Flow

1. **Fetch batch**: Get detection data from Redis/database
2. **Format prompt**: Create risk analysis prompt with detection details
3. **Call LLM**: POST to `/completion` endpoint with structured prompt
4. **Parse response**: Extract JSON with risk assessment
5. **Validate**: Ensure risk_score (0-100) and risk_level (low/medium/high/critical) are valid
6. **Create Event**: Store risk assessment in database
7. **Broadcast**: Send event notification via WebSocket

### Prompt Template

Located in `backend/services/prompts.py`:

```python
RISK_ANALYSIS_PROMPT = """
You are a security AI analyzing activity from camera {camera_name}.

Time window: {start_time} to {end_time}
Detections:
{detections_list}

Provide a risk assessment as JSON:
{
  "risk_score": 0-100,
  "risk_level": "low|medium|high|critical",
  "summary": "Brief description of activity",
  "reasoning": "Detailed analysis and context"
}
"""
```

### Risk Scoring Guidelines

- **0-25 (low)**: Normal activity, no concern
- **26-50 (medium)**: Unusual but not threatening
- **51-75 (high)**: Suspicious activity requiring attention
- **76-100 (critical)**: Potential security threat, immediate action needed

## Performance Characteristics

### Inference Speed

- **Risk analysis**: ~2-5 seconds per batch
- **Token generation**: ~50-100 tokens/second (GPU)
- **Context processing**: ~1000 tokens/second
- **Concurrent requests**: Up to 2 simultaneous (configured)

### Memory Usage

- **Model weights**: ~2.5GB disk, ~3GB VRAM
- **Context buffer**: ~1GB (4096 tokens × 4 bytes × batch)
- **KV cache**: Dynamic, scales with active requests

### Quality

- **Quantization**: Q4_K_M provides good balance of speed and quality
- **Accuracy**: Minimal degradation vs. full precision (~2-3% perplexity increase)
- **Reasoning**: Suitable for risk assessment and natural language generation

## Error Handling

Handled by `backend/services/nemotron_analyzer.py`:

### LLM Service Unavailable

Falls back to default risk assessment:

```python
{
    "risk_score": 50,
    "risk_level": "medium",
    "summary": "Analysis unavailable - LLM service error",
    "reasoning": "Failed to analyze detections: <error details>"
}
```

### Invalid JSON Response

- Uses regex to extract JSON from mixed text/JSON responses
- Validates required fields: `risk_score`, `risk_level`
- Normalizes values to valid ranges
- Infers missing fields from available data

### Timeout

- Default timeout: 60 seconds
- Catches `httpx.TimeoutException`
- Returns fallback risk assessment

## Development Notes

### Prerequisites

- **llama.cpp**: Must be installed with `llama-server` command available
- **CUDA**: Required for GPU acceleration (NVIDIA GPU only)
- **VRAM**: Minimum 3GB free for model

### Installation

```bash
# Clone llama.cpp
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp

# Build with CUDA support
make LLAMA_CUDA=1

# Add to PATH or symlink
sudo ln -s $(pwd)/llama-server /usr/local/bin/llama-server
```

### Testing

```bash
# Test health endpoint
curl http://localhost:8091/health

# Test completion endpoint
curl -X POST http://localhost:8091/completion \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Analyze this security event: A person was detected at 14:30.",
    "temperature": 0.7,
    "max_tokens": 200
  }'
```

### Monitoring

- Check GPU usage: `nvidia-smi`
- View logs: Check stdout/stderr from `start_llm.sh`
- Health checks: Backend performs periodic health checks

## Model Characteristics

### Strengths

- Fast inference on GPU (~2-5 seconds)
- Low VRAM usage (~3GB)
- Good at structured output (JSON)
- Effective for risk reasoning tasks
- Stable and reliable responses

### Limitations

- Small context window (4096 tokens)
- Limited to analyzing ~50-100 detections per batch
- May struggle with very complex scenarios
- Quantization causes minor quality degradation
- Not suitable for very large batches

### Best Practices

- Keep prompts concise and structured
- Request JSON output explicitly
- Provide clear scoring guidelines
- Validate and normalize responses
- Handle edge cases with fallback logic

## Future Enhancements

Potential improvements (not yet implemented):

- Larger model variants (7B, 13B) for better reasoning
- Fine-tuning on security-specific data
- Multi-turn conversations for event clarification
- Integration with vector database for historical context
- Streaming responses for real-time updates
