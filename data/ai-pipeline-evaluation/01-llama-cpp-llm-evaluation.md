# llama.cpp LLM Inference Evaluation Report

**Date:** 2026-02-08
**Model:** Nemotron-3-Nano-30B-A3B (Q4_K_M GGUF)
**Hardware:** NVIDIA RTX A5500 (24GB VRAM)
**Pinned Commit:** 9496bbb80

---

## Executive Summary

The current llama.cpp configuration is **well-optimized for the given hardware constraints** but has several high-value improvements available. The most impactful changes are: (1) enabling the `GGML_CUDA_GRAPH_OPT=1` environment variable for up to 35% faster token generation, (2) adding `--cache-reuse 256` server flag to enable KV shifting for prompt prefix reuse, (3) adding `--merge-qkv` to fuse attention Q/K/V projections on GPU, and (4) updating the pinned llama.cpp commit to pick up 6+ months of CUDA kernel improvements and Mamba hybrid model optimizations.

The `cache_prompt: true` parameter is already correctly sent in the API request body from `nemotron_analyzer.py`, and the `--cache-prompt` CLI flag noted in memory as "added but not deployed" is actually unnecessary -- prompt caching in llama-server is controlled per-request via the API, not via a CLI flag. The Dockerfile already documents this correctly at line 103.

**Total estimated throughput improvement: 40-70% for token generation, 30-50% for prompt processing (TTFT).**

---

## Current Configuration Analysis

### What is Configured Correctly

| Setting                | Value                 | Assessment                                                                                                |
| ---------------------- | --------------------- | --------------------------------------------------------------------------------------------------------- |
| `FLASH_ATTENTION=true` | `--flash-attn on`     | Correct. Reduces VRAM and improves attention throughput.                                                  |
| `CACHE_TYPE_K=q8_0`    | `--cache-type-k q8_0` | Correct. Saves ~50% KV memory with negligible quality loss. Appropriate given only 6/52 attention layers. |
| `CACHE_TYPE_V=q8_0`    | `--cache-type-v q8_0` | Correct. Same as above.                                                                                   |
| `BATCH_SIZE=2048`      | `--batch-size 2048`   | Good. Appropriate for prompt processing throughput.                                                       |
| `UBATCH_SIZE=512`      | `--ubatch-size 512`   | Good. Reasonable sub-batch size for GPU memory management.                                                |
| `--cont-batching`      | Enabled               | Correct. Required for parallel slot utilization.                                                          |
| `--metrics`            | Enabled               | Correct. Enables Prometheus-compatible metrics endpoint.                                                  |
| `cache_prompt: true`   | API request body      | **Already deployed.** Sent correctly in `nemotron_analyzer.py` line 3993.                                 |
| `CTX_SIZE=32768`       | `--ctx-size 32768`    | Appropriate. 32K is sufficient for security event analysis prompts (typically 500-2000 tokens).           |
| `PARALLEL=2`           | `--parallel 2`        | Appropriate for 2-slot batching with 16K per slot.                                                        |

### What Needs Attention

| Setting               | Current                                                         | Issue                                                                                                                                                                                               |
| --------------------- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GPU_LAYERS`          | 48 (Dockerfile default) but compose passes `${GPU_LAYERS:-999}` | **Discrepancy.** `.env` says 48, but `docker-compose.prod.yml` line 218 defaults to 999. Compose override wins at runtime, so all 53 layers are likely on GPU already. Verify actual runtime value. |
| `--cache-reuse`       | Not set (default: 0, disabled)                                  | **Missing.** KV shifting for prefix reuse is disabled server-side.                                                                                                                                  |
| `--merge-qkv`         | Not set                                                         | **Missing.** QKV fusion for attention layers not enabled.                                                                                                                                           |
| `GGML_CUDA_GRAPH_OPT` | Not set                                                         | **Missing.** CUDA graph optimizations not enabled.                                                                                                                                                  |
| `--mlock`             | Not set                                                         | **Missing.** Model weights not locked in RAM.                                                                                                                                                       |
| `--defrag-thold`      | Not set (default: 0.1)                                          | Default is reasonable; may benefit from tuning with PARALLEL=2.                                                                                                                                     |
| Build flags           | Minimal cmake                                                   | **Missing `GGML_CUDA_FA_ALL_QUANTS` and `GGML_NATIVE`.**                                                                                                                                            |
| Commit                | 9496bbb80 (pinned)                                              | **Stale.** Likely 3-6 months behind HEAD; missing CUDA kernel improvements, Mamba optimizations, and CUDA graph support.                                                                            |

---

## Recommended Optimizations

### 1. Enable CUDA Graph Optimizations [HIGH IMPACT]

**What to change:** Add `GGML_CUDA_GRAPH_OPT=1` as an environment variable to the ai-llm service in `docker-compose.prod.yml`.

**Expected impact:** Up to 35% faster token generation. CUDA graphs capture the GPU execution graph and replay it, eliminating CPU-side kernel launch overhead. This is particularly effective for batch-size-1 token generation (the dominant workload for security event analysis). It also enables concurrent CUDA streams for Q/K/V projections in attention layers.

**Implementation effort:** LOW -- single environment variable addition.

**Risks:** Minimal. CUDA graphs are well-tested on NVIDIA RTX GPUs. The feature has been in llama.cpp since mid-2025 and is stable. However, the pinned commit (9496bbb80) may predate this feature -- updating the commit first is recommended.

```yaml
# docker-compose.prod.yml, ai-llm service
environment:
  - GGML_CUDA_GRAPH_OPT=1
```

**References:**

- [NVIDIA Blog: Optimizing llama.cpp AI Inference with CUDA Graphs](https://developer.nvidia.com/blog/optimizing-llama-cpp-ai-inference-with-cuda-graphs/)
- [llama.cpp Discussion #17621: Optimizing Token Generation in CUDA Backend](https://github.com/ggml-org/llama.cpp/discussions/17621)
- [NVIDIA Blog: Open Source AI Tool Upgrades Speed Up LLM and Diffusion Models on RTX PCs](https://developer.nvidia.com/blog/open-source-ai-tool-upgrades-speed-up-llm-and-diffusion-models-on-nvidia-rtx-pcs/)

---

### 2. Update Pinned llama.cpp Commit [HIGH IMPACT]

**What to change:** Update `Dockerfile` line 23 from `git checkout 9496bbb80` to a recent stable commit or tagged release (e.g., `b5200` or later).

**Expected impact:** 20-40% cumulative improvement from 6+ months of CUDA kernel optimizations, Flash Attention improvements, Mamba/hybrid model backend enhancements, CUDA graph support, `--merge-qkv` support, and bug fixes. The Nemotron-3-Nano architecture (`nemotron_h_moe`) has received specific optimizations in recent commits.

**Key features added since ~mid-2025:**

- CUDA graph support (`GGML_CUDA_GRAPH_OPT`)
- QKV merging (`--merge-qkv`)
- Improved Flash Attention with Volta tensor core compatibility and non-padded masks
- Better MoE expert offloading with `--override-tensor` regex patterns
- Concurrent CUDA streams for attention projections
- `--cache-reuse` flag for KV shifting
- Speculative decoding in server mode (`--model-draft`)
- Improved Mamba SSM kernel performance

**Implementation effort:** MEDIUM -- requires rebuild with `--no-cache`, followed by smoke testing the model loads correctly and produces quality output.

**Risks:** MEDIUM. Newer commits may change behavior. Test with the existing Q4_K_M model file and verify:

1. Model loads without errors
2. Health endpoint responds
3. Prompt processing produces equivalent quality output
4. VRAM usage does not exceed 24GB

```dockerfile
# Pin to a recent stable release tag instead of a commit hash
RUN git clone https://github.com/ggerganov/llama.cpp.git
WORKDIR /build/llama.cpp
RUN git checkout b5200  # Or latest stable tag
```

**References:**

- [llama.cpp Releases](https://github.com/ggml-org/llama.cpp/releases)
- [Nemotron-3-Nano-30B-A3B GGUF (Unsloth)](https://huggingface.co/unsloth/Nemotron-3-Nano-30B-A3B-GGUF)

---

### 3. Add --cache-reuse for KV Shifting [HIGH IMPACT]

**What to change:** Add `--cache-reuse 256` to the llama-server command in the Dockerfile CMD.

**Expected impact:** 30-50% reduction in time-to-first-token (TTFT) for requests with shared prompt prefixes. The security analysis system uses a ~3K token static system prompt that is identical across all requests. With `cache_prompt: true` already in the API body (which is correct), the server will attempt to reuse cached KV data. However, `--cache-reuse` enables KV shifting, which allows the server to efficiently reuse cached prefix data even when slot assignment changes. The default of 0 (disabled) means KV shifting is off.

**How it works:** With 2 parallel slots and a shared system prompt prefix:

- Slot 0 processes request A with system prompt + event data A
- Slot 1 processes request B with system prompt + event data B
- Without `--cache-reuse`: if request C lands on slot 0, the entire prompt must be re-processed even though the system prompt prefix is identical
- With `--cache-reuse 256`: the server uses KV shifting to retain the shared prefix, only processing the new event data tokens

**Implementation effort:** LOW -- single flag addition.

**Risks:** LOW. The feature is well-documented and defaults are conservative.

```dockerfile
# Add to CMD in Dockerfile
--cache-reuse 256 \
```

**References:**

- [Tutorial: KV cache reuse with llama-server](https://github.com/ggml-org/llama.cpp/discussions/13606)
- [llama.cpp Discussion #10311: How to effectively use cache_prompt](https://github.com/ggml-org/llama.cpp/discussions/10311)

---

### 4. Add --merge-qkv Flag [MEDIUM IMPACT]

**What to change:** Add `--merge-qkv` to the llama-server command in the Dockerfile CMD.

**Expected impact:** 5-15% improvement in token generation speed for attention layers. This flag merges Q, K, and V attention tensors together, enabling more efficient memory access patterns and potential kernel fusion. Since Nemotron-3-Nano has only 6 attention layers (out of 52), the impact is more modest than for pure transformer models, but it is essentially free performance.

**Implementation effort:** LOW -- single flag addition.

**Risks:** LOW. The flag has no impact on model quality. Requires the attention layers to be on GPU (which they should be with GPU_LAYERS >= 48).

**Note:** This flag may require a newer llama.cpp commit than 9496bbb80. Verify availability after updating the commit (Recommendation #2).

```dockerfile
# Add to CMD in Dockerfile
--merge-qkv \
```

**References:**

- [HuggingFace Blog: Performant MoE CPU inference with GPU acceleration](https://huggingface.co/blog/Doctor-Shotgun/llamacpp-moe-offload-guide)
- [llama-server manpage](https://manpages.debian.org/unstable/llama.cpp-tools/llama-server.1.en.html)

---

### 5. Add --mlock Flag [MEDIUM IMPACT]

**What to change:** Add `--mlock` to the llama-server command in the Dockerfile CMD.

**Expected impact:** Prevents the OS from paging model weights to swap, ensuring consistent inference latency. Without `--mlock`, the 5 CPU-offloaded layers (~500MB-1GB) may be swapped to disk under memory pressure, causing latency spikes. With the container memory limit of 12GB and the model using ~9.5GB on GPU, the remaining system RAM usage should be modest.

**Implementation effort:** LOW -- single flag addition.

**Risks:** LOW-MEDIUM. Requires sufficient system RAM to lock the model weights. The container has a 12GB memory limit, which should be sufficient for the CPU-offloaded layers. If GPU_LAYERS is actually 999 (all on GPU), this flag has minimal effect since only embedding/output layers would be in CPU RAM.

**When to use vs. `--no-mmap`:**

- `--mlock`: Keeps model memory-mapped but locks pages in RAM. Best for most cases.
- `--no-mmap`: Disables memory mapping entirely, loads model fully into RAM. Slower startup, higher memory usage, but eliminates page faults entirely.
- **Recommendation:** Use `--mlock` only. `--no-mmap` is not recommended for this deployment.

```dockerfile
# Add to CMD in Dockerfile
--mlock \
```

**References:**

- [llama.cpp Discussion #1876: Understanding memory usage](https://github.com/ggml-org/llama.cpp/discussions/1876)
- [llama.cpp Guide](https://blog.steelph0enix.dev/posts/llama-cpp-guide/)

---

### 6. Resolve GPU_LAYERS Discrepancy [MEDIUM IMPACT]

**What to change:** Verify actual runtime GPU_LAYERS value and align `.env`, `.env.example`, and Dockerfile defaults.

**Current state:**

- `Dockerfile` default: `ENV GPU_LAYERS=35` (line 66)
- `.env` and `.env.example`: `GPU_LAYERS=48`
- `docker-compose.prod.yml` line 218: `GPU_LAYERS=${GPU_LAYERS:-999}`

**The compose default of 999 means if `.env` has `GPU_LAYERS=48`, all 53 layers go on GPU via the .env value. But if the env var is unset, compose defaults to 999 (all layers on GPU).**

The comment on `.env.example` line 357 says "48/53 layers on GPU for RTX A5500 24GB (leaves headroom for compute buffers + 32K context)". However, with Q4_K_M at ~9.5GB, q8_0 KV cache for 6 attention layers at ~192MB, and 32K context, total VRAM usage should be approximately:

- Model weights: ~9.5GB
- KV cache (6 attn layers, 32K ctx, q8_0): ~192MB
- Compute buffers: ~1-2GB
- **Total: ~11-12GB out of 24GB**

This means **all 53 layers can fit on GPU with significant headroom**. Setting GPU_LAYERS=48 leaves 5 layers on CPU unnecessarily, adding latency for every token that traverses those CPU layers.

**Expected impact:** If currently running at 48 layers, moving to all 53 on GPU eliminates CPU-GPU data transfers for 5 layers, improving both prompt processing and generation speed by 5-15%.

**Implementation effort:** LOW -- change `.env` value.

**Risks:** LOW. The 24GB A5500 has ample headroom. Monitor VRAM usage with `nvidia-smi` after the change.

```env
# .env
GPU_LAYERS=999  # All layers on GPU (A5500 has sufficient VRAM)
```

**References:**

- [llama.cpp Discussion #7678: Fine grained control of GPU offloading](https://github.com/ggml-org/llama.cpp/discussions/7678)

---

### 7. Improve Build Flags [MEDIUM IMPACT]

**What to change:** Add `GGML_CUDA_FA_ALL_QUANTS=ON` and `GGML_NATIVE=ON` to the cmake build in the Dockerfile.

**Expected impact:**

- `GGML_CUDA_FA_ALL_QUANTS=ON`: Compiles Flash Attention kernels for all KV cache quantization types. Since we use q8_0 for KV cache, this ensures optimal FA kernels are available. Without this flag, only a subset of quantization types are supported, and the server may fall back to non-FA attention for unsupported types.
- `GGML_NATIVE=ON`: Enables native CPU optimizations for the build machine's architecture. Improves performance of CPU-offloaded operations.

**Implementation effort:** LOW -- modify cmake command. Build time increases slightly due to additional kernel compilation.

**Risks:** LOW. These are standard optimization flags. `GGML_NATIVE=ON` makes the binary architecture-specific (non-portable), but since the container runs on the same machine it is built on, this is not a concern.

```dockerfile
RUN cmake -B build \
    -DGGML_CUDA=ON \
    -DGGML_CUDA_FA_ALL_QUANTS=ON \
    -DGGML_NATIVE=ON \
    -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build --config Release --target llama-server -j"$(nproc)"
```

**References:**

- [llama.cpp Build Documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md)

---

### 8. Evaluate Speculative Decoding [LOW IMPACT for Mamba Hybrid]

**What to change:** Add `--model-draft <path-to-draft.gguf>` to the llama-server command.

**Expected impact for Nemotron-3-Nano: LOW to NEGATIVE.** Speculative decoding works by having a small "draft" model generate candidate tokens that the large "target" model then verifies in parallel. This typically yields 2-3x speedup for pure transformer models. However, **Nemotron-3-Nano is a Mamba-Transformer hybrid where 46/52 layers are Mamba SSM layers**, which already perform sequential decoding efficiently without the overhead that speculative decoding is designed to mitigate.

Research from "The Mamba in the Llama" (NeurIPS 2024) confirms that linear RNN models (like Mamba) have "significantly different performance characteristics that make them less amenable to speculative decoding, as sequential decoding using recurrent-style sampling is already significantly faster than attention."

**Key challenges:**

1. No compatible smaller Nemotron-3-Nano draft model exists (the architecture is unique)
2. Draft model must share tokenizer/vocabulary, limiting options
3. The Mamba layers already decode efficiently, reducing the benefit
4. Additional VRAM required for draft model (A5500 at 95.9% usage)

**Implementation effort:** HIGH -- requires finding/creating a compatible draft model, additional VRAM allocation, and extensive benchmarking.

**Risks:** HIGH. May actually decrease throughput due to the overhead of running two models on an already VRAM-constrained GPU. Not recommended unless VRAM usage drops significantly (e.g., by using a smaller quantization).

**References:**

- [NeurIPS 2024: The Mamba in the Llama](https://arxiv.org/html/2408.15237v1)
- [llama.cpp Discussion #10466: Speculative decoding for consumer GPUs](https://github.com/ggml-org/llama.cpp/discussions/10466)

---

### 9. Quantization Assessment [LOW IMPACT - Current Choice is Optimal]

**Current:** Q4_K_M (~9.5GB model, ~14GB total VRAM with 32K context)

**Assessment of alternatives:**

| Quantization | File Size  | VRAM\*    | Quality           | Recommendation                                                                                                                                 |
| ------------ | ---------- | --------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Q8_0         | ~17GB      | ~22GB     | Near-lossless     | Possible but tight on 24GB. Would require reducing CTX_SIZE or PARALLEL. Not recommended.                                                      |
| Q6_K         | ~13GB      | ~18GB     | Excellent         | Feasible. Would leave ~6GB headroom. Consider if accuracy improvement is needed.                                                               |
| Q5_K_M       | ~11GB      | ~16GB     | Very good         | Feasible. Good balance if quality improvement is desired.                                                                                      |
| **Q4_K_M**   | **~9.5GB** | **~14GB** | **Good**          | **Current. Best balance for A5500 with 32K context and PARALLEL=2.**                                                                           |
| IQ4_XS       | ~8.5GB     | ~13GB     | Similar to Q4_K_M | Saves ~1GB VRAM but IQ quantizations have slower inference on CUDA (lookup table overhead). Not recommended for throughput-focused deployment. |
| Q3_K_M       | ~7.5GB     | ~12GB     | Noticeable loss   | Not recommended. Quality loss affects risk scoring accuracy.                                                                                   |

**Recommendation:** Stay with Q4_K_M. The current quantization provides the best balance of quality, speed, and VRAM utilization for the A5500. IQ4_XS is not recommended because:

1. Only marginal quality improvement per bit
2. IQ quantizations use codebook lookups that are slower on CUDA GPUs
3. 1GB VRAM savings is not needed given ample headroom

If accuracy improvement is desired in the future (e.g., the 95.5% scoring accuracy needs improvement), consider Q5_K_M which adds ~1.5GB VRAM usage but provides measurably better quality.

**References:**

- [LessWrong: Comparing Quantized Performance in Llama Models](https://www.lesswrong.com/posts/qmPXQbyYA66DuJbht/comparing-quantized-performance-in-llama-models)
- [llama.cpp Discussion #5962: Blind testing different quants](https://github.com/ggml-org/llama.cpp/discussions/5962)

---

### 10. Batch Size Tuning for Security Use Case [LOW IMPACT]

**Current:** BATCH_SIZE=2048, UBATCH_SIZE=512

**Assessment:** These values are well-suited for the security event analysis workload:

- Typical prompts: 500-2000 tokens (system prompt ~3K + event data ~500-2000)
- BATCH_SIZE=2048 means the entire prompt can be processed in a single batch pass
- UBATCH_SIZE=512 provides good GPU utilization without excessive memory spikes

**Potential tuning:**

- Increasing BATCH_SIZE to 4096 would allow processing larger prompts without chunking, but the current 2048 is sufficient for the typical workload
- Decreasing UBATCH_SIZE to 256 could reduce peak VRAM usage during prompt processing, but 512 is well within the A5500's capacity

**Recommendation:** No change needed. Current values are optimal for the workload.

---

## Additional Considerations

### Clarification: `--cache-prompt` CLI Flag

The memory notes mention `--cache-prompt` as "added to LLM Dockerfile but not yet deployed." After thorough investigation:

1. **There is no `--cache-prompt` CLI flag for llama-server.** Prompt caching is controlled per-request via the `cache_prompt` parameter in the API request body.
2. The backend at `nemotron_analyzer.py` line 3993 already sends `"cache_prompt": True` in every request.
3. The Dockerfile comment at line 103 correctly documents this: "Prompt caching: enabled via `cache_prompt: true` in API request body (not a CLI flag)."
4. **The `--cache-reuse` flag** (Recommendation #3 above) is the server-side complement that enables KV shifting for more effective cache reuse.

**Conclusion:** Prompt caching IS already deployed and working. The `--cache-reuse` flag is the missing piece that would make it more effective.

### MoE Expert Offloading (Already Configured)

The `.env.example` documents MoE expert offloading via `LLM_MOE_OFFLOAD_PATTERN`, which would use `--override-tensor` to move expert FFN weights to CPU. This is currently disabled (empty pattern). Given that:

- The A5500 has 24GB VRAM
- Q4_K_M uses ~9.5GB
- All 53 layers on GPU uses ~14GB total
- There is ~10GB headroom

**MoE expert offloading is NOT recommended.** The GPU has sufficient VRAM to keep all weights resident. Offloading to CPU would add latency for the 6 active experts per token.

### CUDA Version

The Dockerfile uses CUDA 13.1.1, which is current. No update needed.

---

## Summary of Recommendations

| #   | Recommendation                          | Impact                         | Effort | Risk   | Status                |
| --- | --------------------------------------- | ------------------------------ | ------ | ------ | --------------------- |
| 1   | Enable `GGML_CUDA_GRAPH_OPT=1`          | HIGH (up to 35% TPS)           | LOW    | LOW    | **DO**                |
| 2   | Update pinned llama.cpp commit          | HIGH (20-40% cumulative)       | MEDIUM | MEDIUM | **DO** (with testing) |
| 3   | Add `--cache-reuse 256`                 | HIGH (30-50% TTFT)             | LOW    | LOW    | **DO**                |
| 4   | Add `--merge-qkv`                       | MEDIUM (5-15% TPS)             | LOW    | LOW    | **DO**                |
| 5   | Add `--mlock`                           | MEDIUM (latency stability)     | LOW    | LOW    | **DO**                |
| 6   | Set GPU_LAYERS=999                      | MEDIUM (5-15% if currently 48) | LOW    | LOW    | **VERIFY & DO**       |
| 7   | Add build flags (FA_ALL_QUANTS, NATIVE) | MEDIUM (5-10%)                 | LOW    | LOW    | **DO**                |
| 8   | Speculative decoding                    | LOW-NEGATIVE for Mamba         | HIGH   | HIGH   | **SKIP**              |
| 9   | Change quantization                     | LOW (Q4_K_M is optimal)        | LOW    | LOW    | **KEEP Q4_K_M**       |
| 10  | Batch size tuning                       | LOW (current is optimal)       | LOW    | LOW    | **NO CHANGE**         |

### Recommended Implementation Order

1. **Phase 1 (Quick wins, no rebuild):** Items 1, 3, 5, 6 -- environment variables and Dockerfile CMD flags only
2. **Phase 2 (Rebuild required):** Items 2, 4, 7 -- update commit, add build flags, rebuild container with `--no-cache`
3. **Phase 3 (Validate):** Run validation suite, compare TTFT and TPS metrics before/after

### Projected Cumulative Impact

With all Phase 1 + Phase 2 optimizations applied:

- **Token generation speed:** 40-70% improvement (CUDA graphs + commit update + merge-qkv + all layers on GPU)
- **Prompt processing (TTFT):** 30-50% improvement (cache-reuse + commit update + build flags)
- **Latency consistency:** Improved (mlock prevents swap-induced spikes)
- **VRAM usage:** Approximately unchanged (no model size change)

---

## Files Referenced

| File                                                                                                 | Purpose                                                       |
| ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `/home/msvoboda/github/nemotron-v3-home-security-intelligence/ai/nemotron/Dockerfile`                | llama.cpp build and runtime configuration                     |
| `/home/msvoboda/github/nemotron-v3-home-security-intelligence/ai/nemotron/config.json`               | Informational runtime config (not used by Dockerfile)         |
| `/home/msvoboda/github/nemotron-v3-home-security-intelligence/docker-compose.prod.yml`               | Service definition with environment overrides (lines 186-256) |
| `/home/msvoboda/github/nemotron-v3-home-security-intelligence/.env`                                  | Runtime port and GPU_LAYERS configuration                     |
| `/home/msvoboda/github/nemotron-v3-home-security-intelligence/.env.example`                          | Full documented configuration reference (lines 345-464)       |
| `/home/msvoboda/github/nemotron-v3-home-security-intelligence/backend/services/nemotron_analyzer.py` | LLM client with `cache_prompt: true` (line 3993)              |

---

## External References

- [llama.cpp Server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [llama.cpp Build Documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md)
- [llama.cpp Releases](https://github.com/ggml-org/llama.cpp/releases)
- [NVIDIA Blog: Optimizing llama.cpp with CUDA Graphs](https://developer.nvidia.com/blog/optimizing-llama-cpp-ai-inference-with-cuda-graphs/)
- [NVIDIA Blog: Open Source AI Tool Upgrades for RTX PCs (CES 2026)](https://developer.nvidia.com/blog/open-source-ai-tool-upgrades-speed-up-llm-and-diffusion-models-on-nvidia-rtx-pcs/)
- [llama.cpp Discussion #17621: CUDA Backend Token Generation](https://github.com/ggml-org/llama.cpp/discussions/17621)
- [llama.cpp Discussion #15013: Performance on NVIDIA CUDA](https://github.com/ggml-org/llama.cpp/discussions/15013)
- [Tutorial: KV Cache Reuse with llama-server](https://github.com/ggml-org/llama.cpp/discussions/13606)
- [HuggingFace: Performant MoE CPU Inference Guide](https://huggingface.co/blog/Doctor-Shotgun/llamacpp-moe-offload-guide)
- [llama.cpp Discussion #18049: Automation for GPU layers with MoE](https://github.com/ggml-org/llama.cpp/discussions/18049)
- [Feature Request: Nemotron-3-Nano-30B-A3B (nemotron_h_moe)](https://github.com/ggml-org/llama.cpp/issues/18064)
- [Unsloth Nemotron-3-Nano GGUF](https://huggingface.co/unsloth/Nemotron-3-Nano-30B-A3B-GGUF)
- [NVIDIA Nemotron-3 Technical Paper](https://research.nvidia.com/labs/nemotron/files/NVIDIA-Nemotron-3-White-Paper.pdf)
- [NeurIPS 2024: The Mamba in the Llama](https://arxiv.org/html/2408.15237v1)
- [llama-server Debian Manpage](https://manpages.debian.org/unstable/llama.cpp-tools/llama-server.1.en.html)
