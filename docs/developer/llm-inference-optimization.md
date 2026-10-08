# LLM Inference Performance Optimization

> How the shipped reasoning engine — `ai-vlm`, a llama.cpp `llama-server`
> container — is configured, budgeted, and tuned.

The reasoning step of the pipeline is one constrained-decoding call to
`ai-vlm` (`backend/services/vlm_client.py`). Everything on this page is that
service's live configuration.

---

## Model and Server

| Item          | Value                                                                                      |
| ------------- | ------------------------------------------------------------------------------------------ |
| Model         | `Qwen3VL-8B-Instruct-Q4_K_M.gguf` + `mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf`                 |
| Server        | llama.cpp `llama-server`, pinned at `b7972` (`VLM_REQUIRED_BUILD`, `.env.example:265`)     |
| Build         | `ai/vlm/Dockerfile` — CUDA 13.3.1, compiled for the host GPU via `CUDA_ARCHITECTURES`      |
| Port          | container-side `PORT=8098` fixed (`ai/vlm/Dockerfile:123`); host mapping via `AI_VLM_PORT` |
| GPU           | `nvidia.com/gpu=${GPU_LLM:-0}` + `CUDA_VISIBLE_DEVICES=${GPU_LLM:-0}`                      |
| Weights mount | `${AI_MODELS_PATH}/vlm:/models:ro` — the service never downloads weights                   |
| Bring-up      | in the default compose set (`docker-compose.prod.yml:141`) — a plain `up -d` starts it     |

## Server Flags

`ai/vlm/Dockerfile:141` assembles the `llama-server` command from env:

```
llama-server \
    --model ${MODEL_PATH} \
    [--mmproj ${MMPROJ_PATH}] \
    [--alias ${MODEL_ALIAS}] \
    [--sleep-idle-seconds ${SLEEP_IDLE_SECONDS}] \
    [--cache-type-k ${CACHE_TYPE_K}] [--cache-type-v ${CACHE_TYPE_V}] \
    --host 0.0.0.0 --port ${PORT} \
    --n-gpu-layers ${GPU_LAYERS} \
    --ctx-size ${CTX_SIZE} \
    --parallel ${PARALLEL} \
    --threads ${THREADS} --threads-batch ${THREADS} \
    --batch-size ${BATCH_SIZE} --ubatch-size ${UBATCH_SIZE} \
    --cont-batching --metrics --cache-reuse 256 --jinja \
    [--flash-attn on]
```

Compose threads the real values (`docker-compose.prod.yml:180-241`; vars
declared in `.env.example:425-446`):

| Env var                  | Compose default   | Flag                   | Notes                                                                                  |
| ------------------------ | ----------------- | ---------------------- | -------------------------------------------------------------------------------------- |
| `VLM_MODEL_PATH`         | Qwen3VL-8B Q4_K_M | `--model`              | Q4_K_M keeps the 8B inside a single-GPU budget                                         |
| `VLM_MMPROJ_PATH`        | Q8_0 projector    | `--mmproj`             | **Without it the server starts text-only** — `/health` still says 200                  |
| `VLM_MODEL_ALIAS`        | `Qwen3VL-8B`      | `--alias`              | Names the model in `/props` so verdict provenance records identity                     |
| `VLM_GPU_LAYERS`         | `auto`            | `--n-gpu-layers`       | `auto` lets llama.cpp fit layers to free VRAM                                          |
| `VLM_CTX_SIZE`           | `32768`           | `--ctx-size`           | Total pool, split across slots (see budget below)                                      |
| `VLM_PARALLEL`           | `2`               | `--parallel`           | Two concurrent `vlm_assess` calls; `ANALYSIS_WORKER_COUNT=2` matches                   |
| `VLM_THREADS`            | `4`               | `--threads`            | CPU fallback threads                                                                   |
| `VLM_CACHE_TYPE_K/V`     | `q8_0`            | `--cache-type-k/v`     | KV cache at half the f16 pool; a quantized V cache **requires** flash attention        |
| `VLM_FLASH_ATTENTION`    | `true`            | `--flash-attn on`      | Enabled; also cuts peak attention VRAM                                                 |
| `VLM_SLEEP_IDLE_SECONDS` | `300`             | `--sleep-idle-seconds` | After 5 min idle the weights go to CPU RAM and VRAM is released to other GPU residents |

The container health-checks `curl -f http://localhost:8098/health` with a
120s start period (`ai/vlm/Dockerfile:138`); compose aligns its own check so
the two never disagree.

## The Context Budget

llama.cpp splits one `--ctx-size` pool across `--parallel` slots, and one
`vlm_assess` only ever gets one slot. The backend mirrors that arithmetic:
`vlm_context_window` (`backend/core/config.py:1334`, alias `VLM_CTX_SIZE`) is
the per-slot budget the client fits every prompt against.

The client's fit test (`backend/services/vlm_client.py:703`) reserves, per
request:

| Reservation         | Amount                        | Source                                                                                                                        |
| ------------------- | ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Verdict output      | 2,048 tokens                  | `_ASSESS_MAX_TOKENS` in `backend/services/vlm_client.py`                                                                      |
| Images              | 1,280 × (frames, ≤4)          | `_IMAGE_TOKENS_PER_FRAME` in `backend/services/vlm_client.py` (Qwen3-VL encodes one still at ≤~1280 vision tokens)            |
| Counting correction | ×1.5 served-vs-counted tokens | `_SERVED_TOKENS_PER_COUNTED` in `backend/services/vlm_client.py` (the Qwen3-VL vocab serves more tokens than tiktoken counts) |

With the shipped defaults (32,768 ÷ 2 = 16,384 per slot) a worst-case
4-image request reserves 2,048 + 5,120 tokens of output+image space before
text. If the rendered text still exceeds the remainder, the client keeps the
strongest-confidence detections and appends a visible omission marker
(`backend/services/vlm_client.py:676`) — the same ranking the key-frame
selector uses, so what survives is what the attached stills can corroborate.
`record_prompt_truncated()` fires once per batch at the wire.

Token counting itself is `TokenCounter` (`backend/services/token_counter.py`)
— tiktoken `cl100k_base`, warmed at startup (`backend/main.py:1259`),
`validate_prompt()`/`get_context_budget()` available for anything that needs
a budget check.

## Enforcement Probe and Build Pin

`VLM_ENFORCEMENT_PROBE_ENABLED=true` (`.env.example:260`): before the first
real call the client sends one schema-constrained probe and verifies the
engine actually enforces the JSON schema (grammar-constrained decoding) —
if it does not, `ConstrainedDecodingNotEnforced` fails closed rather than
trusting unconstrained output. `VLM_REQUIRED_BUILD=b7972` pins the
`llama-server` build the pin was verified against; a drifted `/props`
`build_info` refuses to run.

## Performance Characteristics

- **VRAM**: Q4_K_M 8B weights + q8_0 KV on a 24GB card leaves room for the
  Triton gateway alongside; the `--sleep-idle-seconds 300` residency means an
  idle VLM hands its VRAM back and a wake ping (`backend/services/vlm_client.py:1142`,
  one `max_tokens: 1` request) rouses it before the real call.
- **Read timeout**: `AI_VLM_READ_TIMEOUT=25.0` (`.env.example`, the `AI_VLM_READ_TIMEOUT` block) is a
  per-read IDLE budget, not an attempt deadline: a stalled reply is a budget
  (`VlmSlowReplyError`), NOT retried and NOT breaker-charged, while an engine that
  dribbles the reply within it runs on. Keep it under S4's p95 of 30 s to bound
  the silent-server case. The §6 temp-0 retry re-asks only where that can differ:
  fast trip faults, 5xx, a schema-violating complete reply.
- **Batch pacing**: analysis runs after the 90s/30s/500 batch window
  closes, so back-to-back calls, not streaming, are the throughput unit.
- **Concurrency**: more than `VLM_PARALLEL` concurrent analyses queue behind
  the slots.

## Known Limitations

- **Text-only start is silent.** Forgetting `MMPROJ_PATH` still yields
  `200 /health`. Confirm with `podman logs ai-vlm | grep -i mmproj`.
- **The slot is smaller than the pool.** A prompt sized against total
  `VLM_CTX_SIZE` rather than `VLM_CTX_SIZE/VLM_PARALLEL` will overflow the
  served slot (the engine answers HTTP 400 `exceed_context_size_error`,
  which the client raises as `VlmContextOverflowError` without burning a
  retry).
- **Length-truncated verdicts don't retry.** A reply cut at `max_tokens`
  raises `VlmTruncatedError` immediately — re-asking the same body at the
  same budget would produce the same cut object.

## Key Files Reference

| File                                | Purpose                                     |
| ----------------------------------- | ------------------------------------------- |
| `ai/vlm/Dockerfile`                 | llama.cpp build + CMD flag assembly         |
| `docker-compose.prod.yml`           | `ai-vlm` service: env, GPU, profile, limits |
| `.env.example`                      | `VLM_*` and `AI_VLM_*` variables            |
| `backend/core/config.py`            | `vlm_context_window`, `ai_vlm_url`          |
| `backend/services/vlm_client.py`    | The only dialer; fit test, ladder, probe    |
| `backend/services/token_counter.py` | Token counting and budget helpers           |

## Related Documentation

- [Risk Analysis](risk-analysis.md) - What the VLM decides
- [Prompt Management](prompt-management.md) - Stored prompt configs
- [Multi-GPU Setup](multi-gpu.md) - GPU assignment

---

[Back to Developer Hub](README.md)
