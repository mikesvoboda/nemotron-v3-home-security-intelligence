# Model Inventory and Consumer-GPU Sizing

> **Errata (2026-09-23):** E2, E8, E9, E10 in [`11-errata-2026-09-23.md`](11-errata-2026-09-23.md) correct claims in this document. The original text is kept as the record; read those entries before relying on it. Current design: [`2026-09-23-vss-gaming-gpu-profile-design.md`](../superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md).

Source for all **[V]** claims: `skills/vss-build-vision-ai/references/sizing.md`,
`.../references/edge.md`, `.../references/services/rt-vlm.md`, `docs/real-time-vlm.mdx`, and
`deploy/docker/services/nim/` in the VSS repo, read 2026-09-18.

## VSS's own sizing formula **[V]**

```text
weights_GB = parameters_billions * bits_per_parameter / 8
model_GB   = weights_GB * 1.3

dedicated fits when model_GB <= 0.85 * GPU_VRAM_GB
shared    fits when sum(service budgets) <= 0.85 * GPU_VRAM_GB
```

Bits per parameter: **16** for FP16/BF16, **8** for FP8/INT8, **4** for INT4/NVFP4.

The 30% multiplier covers KV cache and activations. The remaining 15% GPU reserve covers CUDA
graphs, framework allocations, and runtime variance. VSS states: _"Do not tune a discrete-GPU
allocation above `0.85`."_

**The formula is self-consistent with their published table** — it reproduces three of their
quoted budgets exactly (9B FP8 = 11.7, 7B FP16 = 18.2, 8B FP16 = 20.8).

> ### ⚠️ DO NOT EXTRAPOLATE THE FORMULA TO 4-BIT **[V, 2026-09-19]**
>
> **Budget from HuggingFace blob sizes, never from the formula.** The formula assumes every
> parameter is quantized. Real NVFP4 checkpoints quantize only part of the network.
>
> For `NVIDIA-Nemotron-Nano-12B-v2-VL-NVFP4-QAD`, **2,216,376,832 parameters stay BF16** — the
> vision tower, four attention layers, the Mamba `conv1d`, the projector, and `lm_head` are all in
> `config.json`'s `ignore` list. That BF16 floor is _identical_ in the FP8 and NVFP4 repos.
>
> | Model                | Formula  | Actual (HF blob × 1.3) | Error |
> | -------------------- | -------- | ---------------------- | ----- |
> | 12B-VL NVFP4         | 7.80 GB  | **13.78 GB**           | −43%  |
> | 12B-VL FP8           | 15.60 GB | **20.02 GB**           | −22%  |
> | Nemotron Nano 9B FP8 | 11.70 GB | **13.39 GB**           | −13%  |
>
> The earlier hedge in this document — "treat every FP4 figure as an optimistic lower bound" — was
> correct. The magnitude is now measured: **the formula understates 4-bit by roughly 40%.**
> The FP4 column in the table below is retained only to show what the formula predicts. **It is
> wrong.** Use [`04-fp4-and-deployment.md`](04-fp4-and-deployment.md) for real numbers.

**MoE caveat [V]:** for mixture-of-experts models, budget **total** parameters, not active
parameters. VSS says this explicitly of Nemotron 3.5 Lightning 30B-A3B: _"budget total parameters
(30 B), not active parameters (3 B)."_ The `A3B` in a model name is a latency property, not a
memory property.

## GPU budgets

VSS's published table **[V]**, extended with consumer cards **[C]**:

| GPU                               | Memory         |            85% budget | Source                   |
| --------------------------------- | -------------- | --------------------: | ------------------------ |
| B200 / GB200                      | 192 GB         |              163.2 GB | **[V]**                  |
| H200                              | 141 GB         |              119.9 GB | **[V]**                  |
| DGX Spark / Thor                  | 128 GB unified | size from actual free | **[V]**                  |
| RTX PRO 6000 Blackwell            | 96 GB          |               81.6 GB | **[V]**                  |
| H100 / A100 80 GB                 | 80 GB          |               68.0 GB | **[V]**                  |
| L40S / L40 / RTX 6000 Ada / A40   | 48 GB          |               40.8 GB | **[V]**                  |
| RTX PRO 4500 Blackwell            | 32 GB          |               27.2 GB | **[V]** ← smallest entry |
| **RTX 5090** (consumer Blackwell) | 32 GB discrete |               27.2 GB | **[C]**                  |
| **RTX 4090** (consumer Ada)       | 24 GB discrete |               20.4 GB | **[C]**                  |

**There is no GeForce row in VSS's table.** The market gap is documented by its absence.

**Critical distinction [V]:** the DGX Spark / Thor row is _unified memory_, 128 GB shared between
CPU and GPU. VSS's edge profiles exist because there is a lot of slow shared memory, not because
the models are small. `edge.md` notes the local edge LLM "is **slow**" and recommends a remote
endpoint for latency. **The edge profile solves the opposite problem from a consumer GPU and does
not transfer.**

## Model budgets

Published by VSS **[V]**; FP4 column computed from their formula **[C]**:

| Model                                    | Slot        | Params |       BF16/FP16 |             FP8 |             FP4 **[C]** |
| ---------------------------------------- | ----------- | -----: | --------------: | --------------: | ----------------------: |
| Nemotron 3.5 Lightning 30B-A3B (default) | LLM         |    30B |  ~78 GB **[V]** |               — |                ~19.5 GB |
| ↳ INT4 profile `vllm-int4-tp1-pp1-32.0`  | LLM         |    30B |               — |               — | ~45 GB observed **[V]** |
| Nemotron Nano 9B v2 FP8                  | LLM         |     9B |               — | 11.7 GB **[V]** |                 ~5.9 GB |
| `nemotron-nano-12b-v2-vl`                | VLM         |    12B |        ~31.2 GB |        ~15.6 GB |                 ~7.8 GB |
| Nemotron-3-Nano-Omni-30B-A3B-Reasoning   | VLM (audio) |    30B |          ~78 GB |          ~39 GB |                ~19.5 GB |
| Cosmos Reason 1 7B                       | VLM         |     7B | 18.2 GB **[V]** |         ~9.1 GB |                 ~4.6 GB |
| Cosmos Reason 2 8B                       | VLM         |     8B | 20.8 GB **[V]** |        ~10.4 GB |                 ~5.2 GB |
| Qwen3-VL 8B                              | VLM         |     8B | 20.8 GB **[V]** |        ~10.4 GB |                 ~5.2 GB |
| `nemotron-embed-vl-1b-v2`                | Embedding   |     1B |         ~2.6 GB |         ~1.3 GB |                 ~0.7 GB |

**Note the INT4 anomaly:** VSS observes ~45 GB for the 30B-A3B at INT4, against a formula
prediction of ~19.5 GB. The `vllm-int4-tp1-pp1-32.0` profile carries
`min_vram_per_device_gb: 32.0` **[V]**. The gap between formula and observation is unexplained and
matters a great deal for extrapolating FP4 numbers — **treat every FP4 figure in this table as an
optimistic lower bound until this discrepancy is understood [?]**.

## Slot assignments

### Nemotron Nano 9B v2 FP8 is text-only **[V]**

Not multimodal. It occupies the LLM slot exclusively. Evidence:

- Service profile keys are `llm_local_nvidia-nemotron-nano-9b-v2-fp8` and
  `llm_local_shared_nvidia-nemotron-nano-9b-v2-fp8`
- Helm exposes it as `llmNameSlug` (`deploy/helm/developer-profiles/dev-profile-base/values-base.yaml:23`)
- `edge.md` calls it an explicit `--llm` fallback
- Its init container fetches `nemotron_toolcall_parser_no_streaming.py` — tool calling, a text-LLM
  concern
- Served by raw vLLM (`nvcr.io/nvidia/vllm:26.07-py3`), not a NIM
- It never appears as `VLM_NAME` or `VLM_MODEL_PATH`

Hardware profiles shipped for it **[V]**: `hw-DGX-SPARK`, `hw-AGX-THOR`, `hw-IGX-THOR`, `hw-OTHER`,
each with a `-shared` variant.

### Multimodal Nemotron variants exist and fill the VLM slot **[V]**

| Model                                      | Mode              | Evidence                                                                   |
| ------------------------------------------ | ----------------- | -------------------------------------------------------------------------- |
| `nemotron-nano-12b-v2-vl`                  | `openai-compat`   | `docs/real-time-vlm.mdx:1529`                                              |
| Nemotron-3-Nano-Omni-30B-A3B-Reasoning     | `vllm-compatible` | `docs/real-time-vlm.mdx:82`                                                |
| Nemotron-3-Nano-Omni-30B-A3B-Reasoning-FP8 | `vllm-compatible` | `docs/real-time-vlm.mdx:83`                                                |
| Qwen3-Omni-30B-A3B-Instruct                | `vllm-compatible` | `docs/real-time-vlm.mdx:85`                                                |
| `Nemotron-Nano-V3-Omni-GA0420-FP8`         | `VLM_MODEL_PATH`  | HuggingFace git ref, in-tree env                                           |
| `nemotron-embed-vl-1b-v2`                  | Embedding         | `libs/vss/core/src/vss_core/knowledge/adapters/{langchain,llama_index}.py` |

**Omni models do native single-model video + audio understanding [V]**
(`docs/real-time-vlm.mdx:1622`), available _only_ on Omni models (`:1650`). They require
`VLM_TRUST_REMOTE_CODE=true` and `VLM_MODEL_SUPPORTS_AUDIO=true` (`:97`).

Audio is a genuinely differentiated signal for home security — glass break, raised voices, smoke
alarm, barking — and our current pipeline has no audio capability at all. But at 30B total
parameters, the Omni line is out of consumer reach at FP8 (~39 GB) and only marginal at FP4
(~19.5 GB, and see the INT4 anomaly above). **Watch this; do not build on it yet.**

### NIM directories shipped in-tree **[V]**

`deploy/docker/services/nim/` contains exactly three model directories:

- `cosmos3-reasoner`
- `nemotron-3.5-lightning-30b-a3b`
- `nvidia-nemotron-nano-9b-v2-fp8`

Plus `compose.yml`, `nim.env`, and `fallback-override.env`. Anything not in this list is reached
through `vllm-compatible` or `openai-compat` mode rather than a wired NIM profile — a meaningful
difference in how much work it is to run.

## The co-packing problem

A consumer deployment has **one** GPU. VSS's sizing procedure assumes several: _"Inventory every
GPU's model, total memory, free memory... Place fixed-footprint services first... Place singleton
RT-VLM last, into the capacity step 3 leaves behind; never displace or co-pack a fixed service to
free a GPU for it"_ **[V]**.

On a single card that placement algebra collapses into one question — **what co-resides** — which
is the unsolved case, not a scaled-down solved one.

Rough arithmetic at FP8, VLM + separate LLM **[C]**:

```text
nemotron-nano-12b-v2-vl  15.6 GB
Nemotron Nano 9B v2 FP8  11.7 GB
                         -------
                         27.3 GB   vs RTX 4090 budget 20.4  -> DOES NOT FIT
                                   vs RTX 5090 budget 27.2  -> saturated, nothing left
```

That leaves zero headroom for RT-CV and RT-Embed, which have their own footprints (not yet
quantified — **[?]**). **A VLM-only arithmetic is misleading; the perception tier must be
counted.**

### The likely consumer shape **[C]**, unverified

One VL model doing both captioning and reasoning, rather than VLM + separate LLM:

```text
nemotron-nano-12b-v2-vl FP8   15.6 GB
  -> RTX 4090 (20.4): 4.8 GB left for RT-CV + RT-Embed
  -> RTX 5090 (27.2): 11.6 GB left for RT-CV + RT-Embed
```

This is a **topology** claim, not a quantization claim, and it differs from both systems: our
pipeline splits captioning (Florence-2) from reasoning (Nemotron); VSS's default splits RT-VLM
from a separate LLM NIM. The consumer-constrained answer may collapse that split. **Unverified —
needs the RT-CV/RT-Embed footprints and a real measurement.**

## Open sizing questions **[?]**

1. What are the actual VRAM footprints of RT-CV and RT-Embed? Until these are known, no
   configuration can be declared to fit.
2. Why does the 30B-A3B INT4 profile observe ~45 GB against a ~19.5 GB formula prediction?
3. Do official FP4/NVFP4 checkpoints exist for any VLM-slot model, or only quantization recipes?
4. **Does NVFP4 serving work on consumer Blackwell?** Kernel support is gated by compute
   capability, and GeForce Blackwell is `sm_120` while datacenter Blackwell is `sm_100`. "The 5090
   has FP4 tensor cores" and "vLLM will serve an NVFP4 checkpoint on a 5090" are different claims.
5. Does `nemotron-nano-12b-v2-vl` have a local deployment path, or is it remote-endpoint-only?
   Suggestive evidence **[V]**: a vLLM model-executor patch exists at
   `services/rtvi/rt-vlm/docker/rtvi_vlm/patches/evs_vllm_public_files/model_executor/models/nano_nemotron_vl.py`
   containing `NemotronBaseVLMultiModalProcessor` — you do not patch vLLM's model executor for a
   model you only call over HTTP.

## Related

- [`01-vss-architecture.md`](01-vss-architecture.md) — the service decomposition
- [`03-open-questions.md`](03-open-questions.md) — the full open-question register
