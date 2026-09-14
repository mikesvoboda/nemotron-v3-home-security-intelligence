# MoE-Aware Tensor Offloading for Nemotron

This document describes the Mixture of Experts (MoE) offloading strategy for the Nemotron-3-Nano-30B-A3B model, which selectively moves expert FFN weights to CPU RAM to free GPU VRAM with minimal performance impact.

## Nemotron-3-Nano Architecture

Nemotron-3-Nano-30B-A3B is a hybrid architecture with 31 billion total parameters but only ~3 billion active parameters per token. The model consists of 52 layers in three types:

| Layer Type    | Count | Role                                      | Expert Count  |
| ------------- | ----- | ----------------------------------------- | ------------- |
| Mamba (SSM)   | 23    | State-space model for sequence processing | None          |
| MoE (FFN)     | 23    | Mixture of Experts feed-forward layers    | 128 per layer |
| GQA Attention | 6     | Grouped-query attention                   | None          |

Each MoE layer routes tokens to **6 of 128** experts per token (~4.7% utilization). The router/gate network selects which experts to activate based on the input, making inference sparse even though the total parameter count is high.

### Why MoE Experts Are Ideal for CPU Offloading

1. **Extreme sparsity:** Only 6 of 128 experts activate per token. The other 122 expert weight tensors sit idle in VRAM for that token.
2. **Small active set:** The 6 active experts are relatively small sub-networks. Fetching them from CPU via PCIe adds modest latency compared to keeping all 128 on GPU.
3. **No quality loss:** The same weights are used regardless of where they are stored. Offloading only changes the memory location, not the computation.
4. **Significant VRAM savings:** Expert FFN weights (gate, up, down projections) make up the majority of MoE layer parameters. Offloading them frees 3--6 GB of VRAM.

### What Stays on GPU

- **Attention layers (6 GQA):** Critical for quality and frequently accessed.
- **Mamba layers (23 SSM):** Stateful layers that process every token sequentially.
- **Router/gate weights:** Small tensors that determine expert routing for each token.
- **Embedding layers:** Token embedding and output projection.
- **KV cache:** Attention key-value cache must remain on GPU for fast access.

## Enabling MoE Offloading

### Step 1: Inspect Model Tensors

Before enabling offloading, inspect the model to discover the correct tensor naming pattern:

```bash
# Run the inspection script against the running ai-llm container
./scripts/inspect-model-tensors.sh

# Or inspect a specific model file with a local llama-server binary
./scripts/inspect-model-tensors.sh --local /usr/local/bin/llama-server --model /path/to/model.gguf

# Show all tensors (not just MoE-related)
./scripts/inspect-model-tensors.sh --all
```

The script outputs:

- A list of MoE expert-related tensors
- Pattern analysis of tensor names
- A recommended `LLM_MOE_OFFLOAD_PATTERN` regex value

### Step 2: Set the Environment Variable

Add the recommended pattern to your `.env` file:

```bash
# In .env
LLM_MOE_OFFLOAD_PATTERN=\.ffn_.*_exps\.weight
```

This pattern typically matches tensors like:

- `blk.0.ffn_gate_exps.weight`
- `blk.0.ffn_down_exps.weight`
- `blk.0.ffn_up_exps.weight`
- `blk.1.ffn_gate_exps.weight`
- ... (across all 23 MoE layers)

The pattern is a regex passed to llama-server's `--override-tensor` flag. Only tensors matching the pattern are moved to CPU; everything else stays on GPU.

### Step 3: Restart the LLM Service

```bash
podman compose -f docker-compose.prod.yml up -d ai-llm
```

### Step 4: Verify Correct Offloading

Check the llama.cpp server logs for tensor offloading messages:

```bash
podman logs ai-llm 2>&1 | grep -iE "offload|override|tensor|CPU"
```

You should see messages indicating that matched tensors were placed on CPU. For example:

```
llm_load_tensors: overriding blk.0.ffn_gate_exps.weight to CPU
llm_load_tensors: overriding blk.0.ffn_down_exps.weight to CPU
llm_load_tensors: overriding blk.0.ffn_up_exps.weight to CPU
...
llm_load_tensors: offloaded N/M tensors to CPU
```

Verify VRAM usage decreased:

```bash
# Check GPU VRAM usage
nvidia-smi --query-gpu=memory.used,memory.total --format=csv
```

## Configuration Reference

### Environment Variables

| Variable                  | Default | Location   | Description                                         |
| ------------------------- | ------- | ---------- | --------------------------------------------------- |
| `LLM_MOE_OFFLOAD_PATTERN` | (empty) | `.env`     | Regex pattern for expert tensors to offload to CPU  |
| `MOE_OFFLOAD_PATTERN`     | (empty) | Dockerfile | Container-internal env var (set by compose mapping) |

### Data Flow

```
.env                         docker-compose.prod.yml           Dockerfile CMD
LLM_MOE_OFFLOAD_PATTERN  --> MOE_OFFLOAD_PATTERN=${LLM_...}  --> --override-tensor <pattern>=CPU
```

The `docker-compose.prod.yml` maps the `.env` variable to the container environment:

```yaml
# docker-compose.prod.yml (ai-llm service)
environment:
  - MOE_OFFLOAD_PATTERN=${LLM_MOE_OFFLOAD_PATTERN:-}
```

The Dockerfile CMD conditionally adds the flag:

```sh
# ai/nemotron/Dockerfile CMD
if [ -n "${MOE_OFFLOAD_PATTERN}" ]; then
    MOE_ARGS="--override-tensor ${MOE_OFFLOAD_PATTERN}=CPU"
fi
```

## Expected Performance Impact

### VRAM Savings

| Configuration        | Estimated VRAM | Notes                                    |
| -------------------- | -------------- | ---------------------------------------- |
| All on GPU (default) | ~17 GB         | Model weights + KV cache                 |
| With MoE offloading  | ~11-14 GB      | Expert weights on CPU, rest on GPU       |
| **Savings**          | **3-6 GB**     | Depends on quantization and tensor sizes |

### Latency Impact

The latency impact depends on your current configuration:

- **If GPU layers are currently overflowing to CPU:** MoE offloading can provide a **10--30% speedup** because the freed VRAM allows more non-expert layers to fit on GPU. Eliminating CPU overflow for attention and Mamba layers more than compensates for the expert fetch latency.
- **If all layers already fit on GPU:** MoE offloading may add **5--15% latency** due to PCIe transfers for active experts. In this case, the benefit is freeing VRAM for other uses (larger context, more parallel slots).

### Recommended Use Cases

1. **Single GPU with tight VRAM (less than 20 GB free):** Enable offloading to fit all non-expert layers on GPU.
2. **Want larger context window:** Free 3--6 GB to increase `CTX_SIZE` from 32K to 64K or higher.
3. **Want more parallel slots:** Free VRAM to increase `PARALLEL` from 2 to 3 or 4.
4. **Dual-GPU with comfortable headroom:** Offloading may not be necessary if the A5500 (24 GB) has sufficient VRAM.

## Troubleshooting

### Pattern Does Not Match Any Tensors

If llama.cpp logs show no offloading, the pattern may not match the model's tensor names:

```bash
# Inspect actual tensor names
./scripts/inspect-model-tensors.sh --all

# Look for expert-related patterns
./scripts/inspect-model-tensors.sh 2>&1 | grep -i "pattern"
```

Common causes:

- Different GGUF quantization tool may use different tensor naming conventions
- Model version update changed tensor names
- Typo in the regex pattern (remember to escape dots: `\.` not `.`)

### Model Fails to Load After Enabling Offloading

If llama-server crashes on startup with the pattern set:

1. Clear the pattern: set `LLM_MOE_OFFLOAD_PATTERN=` (empty) in `.env`
2. Restart: `podman compose -f docker-compose.prod.yml up -d ai-llm`
3. Verify the model loads without offloading
4. Re-run the inspect script to check for correct tensor names

### Inference Quality Degradation

MoE offloading should not affect inference quality since the same weights are used. If you observe degraded outputs:

1. Verify the pattern is not accidentally matching non-expert tensors (attention weights, embeddings)
2. Check that `--override-tensor` is using `=CPU` (not a different device)
3. Compare outputs with and without offloading on the same prompts

## Key Files

| File                                 | Purpose                                         |
| ------------------------------------ | ----------------------------------------------- |
| `ai/nemotron/Dockerfile`             | Dockerfile CMD with `--override-tensor` support |
| `.env` / `.env.example`              | `LLM_MOE_OFFLOAD_PATTERN` configuration         |
| `docker-compose.prod.yml`            | Maps `.env` variable to container environment   |
| `scripts/inspect-model-tensors.sh`   | Discovers tensor names and recommends pattern   |
| `docs/development/moe-offloading.md` | This documentation                              |

## References

- [llama.cpp --override-tensor documentation](https://github.com/ggerganov/llama.cpp/blob/master/examples/server/README.md)
- [Nemotron-3-Nano architecture (NVIDIA)](https://developer.nvidia.com/blog/nemotron-3-nano/)
- [LLM Inference Optimization](llm-inference-optimization.md) -- related VRAM and performance tuning
- [Multi-GPU Configuration](multi-gpu.md) -- GPU assignment for dual-GPU setups
