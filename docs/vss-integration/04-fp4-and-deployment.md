# FP4, Local Deployment, and the Consumer Fit

> **Errata (2026-09-23):** E1, E8, E9, E13, E14, E15, E16, E17, E27 in [`11-errata-2026-09-23.md`](11-errata-2026-09-23.md) correct claims in this document. The original text is kept as the record; read those entries before relying on it. Current design: [`2026-09-23-vss-gaming-gpu-profile-design.md`](../superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md).

**Investigated 2026-09-19** against VSS `cdad5cc0e`, with an adversarial verification pass.
Three recon claims were downgraded by that pass and are marked **[CORRECTED]**. This document
supersedes the FP4 arithmetic in [`02-model-inventory.md`](02-model-inventory.md).

## Headline

**A consumer configuration exists, on a 5090, and the model weights are ungated.** It is not the
one VSS documents, and the path to it runs through a README snippet that does not work as written.

## 1. FP4 availability

### The one checkpoint that matters **[V-ext]**

`nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-NVFP4-QAD` on HuggingFace:

| Property       | Value                                               |
| -------------- | --------------------------------------------------- |
| `gated`        | **false** — no NGC entitlement, no login            |
| Size           | 10.62 GB (FP8 sibling 15.40, BF16 26.36)            |
| `quant_method` | `modelopt`                                          |
| `quant_algo`   | `NVFP4`, w4a4, group size 16                        |
| Accuracy       | AI2D **87.1 vs 87.1** BF16; OCRBenchV2 61.9 vs 62.0 |

Quantization-aware distillation at near-parity accuracy, first-party, publicly pullable. This is
the single most important artifact found in the entire evaluation.

### Cosmos has no verifiable 4-bit **[CORRECTED]**

Recon claimed official Cosmos FP4 checkpoints. **Overstated.** NVIDIA's HF org publishes **zero**
quantized Cosmos-Reason checkpoints — no FP4, no FP8. `Cosmos3-Nano-Reasoner` and
`Cosmos3-Super-Reasoner` are absent from the org listing and return 401, despite
`docs/real-time-vlm.mdx:77,81` listing `git:` URLs for them. Cosmos 4-bit exists only as in-tree
NGC tag strings; `api.ngc.nvidia.com` returns `UNAUTHORIZED` anonymously. Every public 4-bit
Cosmos repo is community-built.

### The formula trap **[CORRECTED]**

See the boxed warning in [`02-model-inventory.md`](02-model-inventory.md). Short version: real
NVFP4 checkpoints leave the vision tower, some attention layers, the Mamba `conv1d`, the
projector, and `lm_head` in BF16. **The VSS sizing formula understates 4-bit by ~40%.**

## 2. Local deployment of `nemotron-nano-12b-v2-vl`

**Yes, mechanically — but it is one README snippet, not a curated path. [CORRECTED]** — recon
called it "supported-but-uncurated"; it is README-grade only.

**Evidence it is first-class in the engine [V]:**
`services/rtvi/rt-vlm/src/models/vllm_compatible/vllm_compatible_model.py:632` defines
`_NEMOTRON_OMNI_ARCHS = frozenset({"NemotronH_Nano_VL_V2", "NemotronH_Nano_Omni_Reasoning_V3"})`,
branched at `:638, :1692, :1784, :2486, :3738, :3831, :3862`. The HF NVFP4 checkpoint declares
exactly `architectures: ["NemotronH_Nano_VL_V2"]`. EVS video-token pruning is benchmarked on it:
8193→4353 prompt tokens, **26.7s → 14.2s** per 30s/30-frame chunk (`README.md:838-843`).

**Evidence the coverage is thin [V]:** `grep -rniE "nemotron[-_]nano[-_]12b"` returns **5 lines
across 2 files**, two of them the unrelated remote `openai-compat` example. No NIM directory, no
helm chart, no compose profile, no `hw-*.env`, no `dev-profile.sh` mapping, no tests, and absent
from the Supported Models table.

### ⚠️ The README recipe will not start **[V]**

`README.md:845-852` sets `VLM_TRUST_REMOTE_CODE=true`. That flag is itself an
allowlist-enforcement trigger: `src/vlm_pipeline/model_path_policy.py:41-55` raises
`"RTVI_MODEL_PATH_ALLOWLIST must be set when allowlist enforcement is on"`. **The documented
recipe omits it and fails at boot.** Set the allowlist to the exact model path string.

Also note the recipe uses `MODEL_PATH=ngc:nim/nvidia/nemotron-nano-12b-v2-vl:nvfp4-refresh`, and
that NGC tag returns **401 anonymously**. The durable path is the ungated HF one:

```bash
MODEL_PATH=git:https://huggingface.co/nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-NVFP4-QAD
RTVI_VLM_MODEL_PATH_ALLOWLIST=git:https://huggingface.co/nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-NVFP4-QAD
```

`ngc:` and `git:` are weight **downloaders** (`src/vlm_pipeline/ngc_model_downloader.py`) into
`NGC_MODEL_CACHE`, then served by an in-process vLLM engine. A bare filesystem path is a third,
credential-free scheme.

## 3. The consumer fit

Budgets: **4090 = 20.4 GB**, **5090 = 27.2 GB**. RT-CV ≈ 3.0 GB (bracket 1.7–4.5). **RT-Embed is a
fixed 10 GB** — `sizing.md`: _"Reserve about 10 GB for RT-Embed"_, no knob, no 4-bit path **[V]**.

| Configuration                             | Arithmetic                 | Verdict                                                                 |
| ----------------------------------------- | -------------------------- | ----------------------------------------------------------------------- |
| **5090: 12B-VL NVFP4 + RT-CV**            | 13.78 + 3.0 = **16.78**    | **FITS** — 10.4 GB spare                                                |
| 5090: 12B-VL FP8 + RT-CV                  | 20.02 + 3.0 = 23.02        | FITS (fallback)                                                         |
| 5090: 12B-VL NVFP4 + RT-CV + RT-Embed     | 13.78 + 3.0 + 10.0 = 26.78 | MARGINAL (0.42 GB headroom)                                             |
| 5090: 12B-VL FP8 + RT-CV + RT-Embed       | 33.02                      | **NO** (+5.8)                                                           |
| 4090: 12B-VL NVFP4 + RT-CV                | 16.78                      | Fits VRAM; **FP4 emulated on sm_89**                                    |
| 4090: 12B-VL FP8 + RT-CV                  | 23.02                      | **NO** (+2.6)                                                           |
| 4090: Cosmos3 Nano BF16, VLM-only         | 22.1 > 20.4                | **NO** — VSS's default at its only tested precision does not fit a 4090 |
| Either card: any VLM **+ local text LLM** | —                          | **STRUCTURALLY BLOCKED** — see below                                    |

### The LLM blocker is architectural, not arithmetic **[V]**

`deploy/docker/scripts/dev-profile.sh:1161-1165`:

> Two vLLM engines cannot share one GPU at all. Each sizes itself as (fraction × total) − (memory
> held by every other process) and then expands its KV cache to fill the remainder, so no pair of
> fractions satisfies both.

VSS **hard-errors** on this at 48 GB (L40S). RT-VLM and the Nemotron 9B NIM are both vLLM engines.
So the options are: remote LLM, a second GPU, or no separate agent tier.

**This confirms the one-VL-model topology** hypothesised earlier — but for a harder reason than
VRAM. It is not that two models are a tight fit; it is that two vLLM engines on one device are
structurally impossible. A single VL model doing both captioning and reasoning is not an
optimization, it is the only single-GPU shape.

### Compute may bind before VRAM **[V]**

RT-CV hits **95-96% SM utilization at 2-3 streams**, and every VSS dGPU benchmark dedicates a
whole GPU to it. `docs/prerequisites.mdx:282-295` gives the 32 GB RTX PRO 4500 exactly one row —
_alerts profile, remote LLM_ — with no single-GPU column.

**[CORRECTED]** The 7.28s NVFP4 result in that table was a **two-GPU** run, not single-GPU.

**[CORRECTED]** `.github/skill-eval/run_leg.py:58-61` contains
`RTX4090_ALL_TESTS = frozenset()` and `RTX4090_TESTS = {}` — **zero tests route to the 4090 pool.**
That is declared intent, not running CI.

## 4. Cosmos Reason verdict

Strong family, best-curated in-tree, loses on three counts for this use case:

1. **Weights are NGC-gated and externally unverifiable** (401 anonymously).
2. `docs/real-time-vlm.mdx:93` warns _"hallucinations may occur with modelopt-fp8 and
   modelopt-nvfp4 variants"_ — exactly the precisions a consumer card needs, and **a hallucinated
   threat is the unacceptable failure mode for home security.**
3. No EVS pruning on CR1/CR2. CR3 Super is contractually H100 / RTX PRO 6000 with a dedicated GPU.
   CR1 is unsupported in VSS 3.3 (`docs/real-time-vlm.mdx:18`).

### The sleeper: Cosmos3 Edge **[V]**

4B omni (~2.4B reasoner), **`gated:false`, 1.54M downloads**, architecture
`Cosmos3EdgeForConditionalGeneration` matching the in-tree vLLM plugin at `src/vllm_cosmos3/`
exactly — and **the only Cosmos model NVIDIA markets for GeForce**. It has _zero_ VSS table,
profile, or sizing coverage. Worth a look as a second candidate.

## 5. Still unverifiable **[?]**

1. **Does NVFP4 actually compute on `sm_120`?** RT-VLM pins an NVIDIA-internal vLLM
   (`0.17.1+a03ca76a.nv26.3...cu132`, `Dockerfile:380`) whose build flags cannot be read
   statically. Upstream vLLM has the branch (`nvfp4_scaled_mm_entry.cu`: `sm >= 120 && sm < 130`).
   **[CORRECTED]** `TORCH_CUDA_ARCH_LIST` at `Dockerfile:67` does not govern this — vLLM is
   `FROM ${VLLM_IMAGE}`, prebuilt, never compiled here. Note `8.9` (Ada/4090) is absent from that list.
2. **Does the HF NVFP4-QAD checkpoint do video?** Its card says _"supports single image
   inference"_ and lists hardware compatibility as **"B100 SXM"** only. The NGC `nvfp4-refresh`
   tag is the one benchmarked on 30-frame chunks — and it is 401.
3. **[CORRECTED]** `VLLM_USE_NVFP4_CT_EMULATIONS` cannot rescue a 4090. It is read only in vLLM's
   _compressed-tensors_ path; `modelopt.py` never reads it, and this checkpoint is
   `quant_method:"modelopt"`. 4-bit weight residency on Ada is plausible via Marlin or emulation,
   but not via that knob.

## 6. The cheapest falsifying experiment

Settles unknowns 1 and 2 in one run:

```bash
# Image is on ghcr, anonymous, ~11.3 GB — no NGC entitlement needed
podman pull ghcr.io/nvidia-ai-blueprints/vss/vss-rt-vlm:develop-latest

MODEL_PATH=git:https://huggingface.co/nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-NVFP4-QAD
RTVI_VLM_MODEL_PATH_ALLOWLIST=git:https://huggingface.co/nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-NVFP4-QAD
VLM_MODEL_TO_USE=vllm-compatible
VLM_TRUST_REMOTE_CODE=true
```

Caption a 30-second / 30-frame clip. **Watch the vLLM startup log for the resolved quantization
method.** If it reports `W4A16_NVFP4` or _"Your GPU does not have native support for FP4
computation"_, you are dequantizing to 16-bit rather than running w4a4 — the memory win holds but
the speed win does not.

Note that the image being anonymously pullable from ghcr is a **partial answer to the credential
question** (Q2 in [`03-open-questions.md`](03-open-questions.md)): at least this container needs
no NGC entitlement, and neither does the HF checkpoint.

## Related

- [`02-model-inventory.md`](02-model-inventory.md) — model table (FP4 column superseded here)
- [`03-open-questions.md`](03-open-questions.md) — open register
