# VSS Integration Research

Research into replacing this project's self-built AI pipeline with NVIDIA's **Video Search and
Summarization (VSS)** blueprint, targeting a market VSS does not currently serve: **consumer
gaming GPUs**.

> **Status: research in progress. Nothing here has been implemented or decided.**

## Read in this order

| Document                                               | What it answers                                         |
| ------------------------------------------------------ | ------------------------------------------------------- |
| [`00-context.md`](00-context.md)                       | Why this exists; the three-step plan; the market thesis |
| [`01-vss-architecture.md`](01-vss-architecture.md)     | What VSS actually is, and how it maps onto `ai/`        |
| [`02-model-inventory.md`](02-model-inventory.md)       | Every model, its slot, and whether it fits 24-32 GB     |
| [`03-open-questions.md`](03-open-questions.md)         | What is unresolved, and what to verify first            |
| [`04-fp4-and-deployment.md`](04-fp4-and-deployment.md) | FP4 reality and the verified consumer fit               |
| [`05-hardware-profiles.md`](05-hardware-profiles.md)   | Hardware tiering: halo / volume / entry                 |
| [`06-repo-a-readiness.md`](06-repo-a-readiness.md)     | What must be fixed in THIS repo first                   |
| [`07-lean-backend.md`](07-lean-backend.md)             | Avoiding Milvus/ES/Neo4j/Kafka; the overlay play        |

Agents should also read [`AGENTS.md`](AGENTS.md) for the evidence convention.

## The one-paragraph summary

VSS and this project independently converged on the same architecture: a perception tier of
specialized models feeding a reasoning tier. VSS's `services/rtvi/` (RT-CV, RT-Embed, RT-VLM) maps
almost one-to-one onto our YOLO26, CLIP, and Florence-2, and both use Nemotron for reasoning. The
opportunity is that VSS's sizing documentation stops at a 32 GB workstation card and its edge
profiles target unified-memory devices — **nothing addresses a discrete consumer GPU.**

**A consumer configuration has since been verified to exist**: an ungated NVFP4 checkpoint
(`NVIDIA-Nemotron-Nano-12B-v2-VL-NVFP4-QAD`, 10.62 GB, near-parity accuracy) plus RT-CV fits an
RTX 5090 with 10.4 GB spare. Below ~24 GB the VLM shape stops fitting, and the only viable
architecture is small specialized models feeding a small text LLM — **which is exactly what `ai/`
already is.** VSS's own default shape cannot run on a single card at any precision, because two
vLLM engines cannot share one GPU; ours can, because our perception servers are not vLLM engines.

**The remaining obstacles are not the ones we started with.** The heavy stateful infrastructure is
avoidable (see `07`). What is _not_ yet settled: whether NVFP4 actually computes on consumer
Blackwell (`sm_120`) rather than dequantizing to 16-bit; the NIM licensing and redistribution
terms, which are a legal question and not in the repo; and a set of verified defects in _this_
repository — backend and frontend coverage compute nothing, and the `ai/` tier's tests largely do
not collect — which must be fixed before any swap claim can be believed (see `06`).

## Current state and what to do next

Nothing is decided and nothing is implemented. The recommended order:

1. ~~**Talk to the VSS team**~~ — **DONE 2026-09-19.** VSS PM confirms **consumer GPUs are not on
   the VSS roadmap**, so the segment is unowned rather than merely unaddressed. See
   [`05-hardware-profiles.md`](05-hardware-profiles.md). Still unasked: _which_ flavour of
   "not on the roadmap," and the licensing/redistribution question, which is legal not roadmap.
2. **Fix this repo's coverage and `ai/` collection** (`06` §1). Hours of work, and until it lands
   every number produced here is unverifiable.
3. **Run the salience demo**, not a latency benchmark (`06` §4). Fifty boring frames.
4. **Send the consumer-GPU procurement request.** Longest lead time, five minutes of effort.

## Evidence convention

Every claim carries a marker. **Preserve these when editing.**

- **[V]** Verified against the VSS repo, cited with `path:line`
- **[C]** Computed from a verified formula
- **[E]** External source, needs primary confirmation
- **[?]** Open question
- **[O]** Stated by a human stakeholder — outranks repo inference
- **[A]** Agent-reported, not independently verified — check before acting

## Contributing to this directory

- Do not promote **[?]** or **[E]** to **[V]** without citing a file and line you actually read.
- When a question in [`03-open-questions.md`](03-open-questions.md) is answered, move the answer
  into the relevant topic document and strike it in the register with the date.
- VSS is actively developed. A citation that no longer resolves means VSS moved — re-verify rather
  than assuming the finding was wrong.
