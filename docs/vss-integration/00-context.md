# Context: Why This Research Exists

> **Errata (2026-09-23):** E2, E3 in [`11-errata-2026-09-23.md`](11-errata-2026-09-23.md) correct claims in this document. The original text is kept as the record; read those entries before relying on it. Current design: [`2026-09-23-vss-gaming-gpu-profile-design.md`](../superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md).

**Status:** Research in progress. Nothing here is a commitment or a plan.
**Started:** 2026-09-18

## The situation

This project was built rapidly in early 2026 and then abandoned. It is being picked back up
because the owner moved to a team at NVIDIA where this work counts as their job.

After building it, the owner found another NVIDIA team shipping a product in the same space:
**Metropolis VSS** (Video Search and Summarization), a published AI Blueprint.

## The three-step plan under evaluation

1. **Stabilize the testing environment**, frontend and backend.
2. **Replace this project's AI pipeline with the VSS pipeline.**
3. **Position the result as a "consumer-friendly VSS" targeting gaming GPUs** — a market segment
   the VSS team has not explored, since VSS targets datacenter and, more recently, edge.

Step 1 is well advanced: see the test-platform program in
[`docs/superpowers/plans/2026-09-15-test-platform-improvement.md`](../superpowers/plans/2026-09-15-test-platform-improvement.md)
and its ledger at
[`docs/plans/2026-09-12-context-map-doc-updates.md`](../plans/2026-09-12-context-map-doc-updates.md).

Steps 2 and 3 are what this directory investigates.

## Why the two systems are comparable

Our pipeline turns images into text with small specialized vision models, then hands the text to
an LLM for reasoning. That was a deliberate design choice made to fit a **24 GB VRAM budget** with
Nemotron v3 Nano on the host. It is why there are so many small models in `ai/`.

**VSS is the same shape.** It also composes a perception tier with a reasoning tier. See
[`01-vss-architecture.md`](01-vss-architecture.md) for the module-by-module mapping. The two
systems converged on the same architecture independently, which is evidence the architecture is
correct for the problem rather than an accident of either team.

## The market thesis

VSS's own sizing documentation **[V]** bottoms out at a 32 GB workstation card
(`RTX PRO 4500 Blackwell`). There is no GeForce row in its GPU table. Its edge profiles
(DGX Spark, AGX Thor, IGX Thor) are **unified-memory** platforms with 128 GB shared between CPU
and GPU — a fundamentally different constraint than a discrete consumer GPU with 24-32 GB of fast
VRAM and no unified pool.

So the gap is real and documented by its absence: **nothing in VSS addresses a discrete consumer
GPU.** That is the thesis. It also means there is no existing profile to crib from — the edge
profile solves the opposite problem and does not transfer.

## The decision this research feeds

Two decisions, in order:

1. **Is the in-flight test-platform work serving this goal?** Specifically, an agent executing
   WP4.4 (mutation-evidence test consolidation) requested 2-3 more days of census processing.
   Whether that is the right spend depends on which of the modules being hardened survive a
   pipeline swap.
2. **What is the cheapest experiment that would falsify the consumer-VSS thesis?** Before
   committing months, there should be a small check that produces real information.

## What this is not

- Not a decision to adopt VSS. That has not been made.
- Not a commitment to contribute upstream to VSS. That option is under evaluation; see
  [`03-open-questions.md`](03-open-questions.md).
- Not an endorsement of the effort estimates herein. They are rough and marked as such.

## Related

- [`01-vss-architecture.md`](01-vss-architecture.md) — what VSS actually is
- [`02-model-inventory.md`](02-model-inventory.md) — the models and the VRAM math
- [`03-open-questions.md`](03-open-questions.md) — what is still unknown
