# Hardware Profiles: The Tiering Strategy

**Proposed 2026-09-19.** This reframes the product thesis from "port VSS to consumer GPUs" to
"contribute a consumer-GPU profile tier, for which a reference implementation already exists."

## Why profiles, and why this is the right frame

**Profiles are VSS's native idiom, not an imposition on it [V]:**

- `deploy/docker/developer-profiles/` — base, search, lvs, alerts
- `deploy/docker/industry-profiles/` — warehouse-operations and others
- `hw-DGX-SPARK.env`, `hw-AGX-THOR.env`, `hw-IGX-THOR.env`, `hw-OTHER.env` per NIM, each with a
  `-shared` variant
- Foundations: `alerts`, `search`, `warehouse`, public safety, smart city

Adding `hw-GEFORCE-*` is speaking VSS's language. It asks the project to extend a pattern it
already maintains rather than to change shape.

**The consumer market is not one tier.** The 32 GB RTX 5090 is the halo card. The volume segment
is **12-16 GB** — 5080, 5070 Ti, 4070 Ti Super, 3060 12 GB. A single "consumer profile" aimed at
32 GB addresses the smallest slice of the market it claims.

## The tiers

| Tier       | VRAM (85% budget)        | Shape                                                    | Status                              |
| ---------- | ------------------------ | -------------------------------------------------------- | ----------------------------------- |
| **Halo**   | 32 GB (27.2)             | 12B-VL NVFP4 (13.78) + RT-CV (3.0) = **16.78**           | **[V]** Fits, 10.4 GB spare         |
| **Volume** | **12-16 GB (10.2-13.6)** | **Small CV zoo → text → small text LLM**                 | **This is the existing `ai/` tier** |
| Entry      | 8 GB (6.8)               | Detection + alerting only; reasoning via remote endpoint | Degraded but shippable              |

### The line where the VLM approach dies **[C]**

At 16 GB the budget is 13.6 GB. The 12B-VL NVFP4 checkpoint is **13.78 GB** — it does not fit
_solo_, before RT-CV, before RT-Embed's fixed 10 GB.

**Below roughly 24 GB, a single large VL model is not viable.** The only remaining shape is
specialized small models producing text, with a small text-only LLM reasoning over it. That is
precisely the architecture in `ai/`, designed for a 24 GB budget and compressible further.

## The structural advantage

VSS's single-GPU blocker is architectural, not arithmetic **[V]**
(`deploy/docker/scripts/dev-profile.sh:1161-1165`):

> Two vLLM engines cannot share one GPU at all. Each sizes itself as (fraction × total) − (memory
> held by every other process) and then expands its KV cache to fill the remainder, so no pair of
> fractions satisfies both.

RT-VLM and the LLM NIM are **both** vLLM engines, so VSS's default shape cannot run on one card at
any precision.

**Our architecture does not have this problem.** YOLO26, Florence-2, and CLIP are plain
PyTorch/FastAPI HTTP servers, not vLLM engines. One vLLM engine for the text LLM plus N small
model servers is a supported configuration. The constraint that blocks VSS on a single GPU does
not bind here.

This is the core of the contribution claim: **the existing architecture is better suited to
consumer hardware than VSS's is.** Not a compromise — a genuine fit advantage, and the reason a
reference implementation for the volume tier already exists.

### Corroborating: the duty-cycle gap

VSS has no idle/evict/on-demand path; its alert route is literally
`/api/v1/realtime/always-on` **[A]**. This repo has `gpu_oom_handler`, `model_zoo` LRU eviction,
and 90-second event-triggered batching. On a consumer box the GPU is shared with whatever else the
owner is doing, so always-on residency is a product defect, not just an efficiency one.

**Caveat [?]:** whether this layer is _good_ or merely _present_ is unverified. It was written by
the same regime that produced a 54% mutation score, and its own tier's tests largely do not
collect (see [`06-repo-a-readiness.md`](06-repo-a-readiness.md)). Making `ai/` collectable answers
this, and is the reason that task outranks further mutation census work.

## The reasoning model for the volume tier

**Requirement:** text-only (vision handled by the CV zoo), small footprint, permissive license, no
NGC entitlement.

### Qwen is strategically safer than it looks

**VSS already ships Qwen support [V]** — `Qwen3-VL-30B-A3B-Instruct` and
`Qwen3-Omni-30B-A3B-Instruct` in `docs/real-time-vlm.mdx`, `Qwen3-VL` and `Qwen3.5-27B` in
`sizing.md`. NVIDIA's own blueprint blesses Qwen, so a Qwen-based tier is not off-message inside
NVIDIA.

It also **directly dissolves the credential blocker**: Apache-2.0 weights on HuggingFace, no NGC
gate, no AI Enterprise licence, nothing for a consumer user to hold an entitlement for. Compare
the NVIDIA path, where microservices ship under an **Evaluation** license, `README.md:99` requires
AI Enterprise to self-host a NIM, and SLA §8.9 bars publishing benchmark data — which covers the
sentence "this runs well on a 5090" **[A]**.

### Candidates to size

Keep both families in play; the tier should be model-agnostic by construction.

| Family                    | Why                                                                                         |
| ------------------------- | ------------------------------------------------------------------------------------------- |
| Qwen3 small dense (4B/8B) | Apache-2.0, strong reasoning-per-byte, no entitlement                                       |
| Nemotron Nano 9B v2       | Already the incumbent here; FP8 is **13.39 GB** actual **[V]** — too large for a 16 GB tier |
| Nemotron Nano smaller     | If a sub-4B text variant exists, it keeps the tier on-family                                |

> ⚠️ **Size from HuggingFace blob sizes, not the VSS formula.** The formula understated the 12B-VL
> NVFP4 checkpoint by 43% because the vision tower stays BF16. Text-only models lack that
> particular trap, so the formula should behave better — but the lesson stands: **verify against
> blobs before committing to a tier boundary.** See [`04-fp4-and-deployment.md`](04-fp4-and-deployment.md).

## What the volume tier has to prove

Not latency. **Salience.**

Home security is a _false-positive suppression_ problem; VSS is a _description_ problem. A model
that returns schema-valid `MEDIUM` on an empty porch is product-worthless regardless of how fast
it does it. The volume tier's acceptance test is the boring-frames test in
[`06-repo-a-readiness.md`](06-repo-a-readiness.md) §4, not a tokens-per-second number.

## Open questions for this document **[?]**

1. What are the real blob-level footprints of the candidate text LLMs at FP8 and 4-bit?
2. What does the CV zoo actually cost in VRAM when co-resident? `ai/` has YOLO26, Florence-2, CLIP,
   enrichment, and enrichment-light. Which are simultaneously resident vs LRU-evicted?
3. Can RT-CV be swapped in for YOLO26 in the volume tier, or does DeepStream drag in too much?
   RT-CV is ~3.0 GB but hits 95-96% SM utilization at 2-3 streams **[A]** — on a shared consumer
   GPU that may be disqualifying regardless of VRAM.
4. Is there an 8 GB tier that still does something a user would pay for, or does the product floor
   sit at 12 GB?

## Related

- [`04-fp4-and-deployment.md`](04-fp4-and-deployment.md) — the halo-tier numbers and the FP4 trap
- [`06-repo-a-readiness.md`](06-repo-a-readiness.md) — what must be fixed here first
- [`03-open-questions.md`](03-open-questions.md) — the open register
