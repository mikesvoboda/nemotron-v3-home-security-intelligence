# VSS Integration - Agent Guide

> **Currency - 2026-10-03 [V].** Corrections to the claims below, checked at `5c605e1d`. The
> compose anchor `docker-compose.prod.yml:578` has rotted: the `PIPELINE_MODE=${PIPELINE_MODE:-vlm}`
> default is at `:484` (E37). "S3 sits below its bar in every arm measured" still holds, but `10/20`
> is a 38-item set; the corpus-scale reading is P5a (450 stills: S3 36.5%, S2 6.7%) (E30, E31).
> "Route to the ledger" misses P5a and synthbench, which have no ledger row (E36). "It is the single
> source of truth for the plan" is wrong for the S2/S3 bars: the spec still shows `[?]`, the bars
> are 5% and 90% (F14) (E39). "Since spec rev 5 the legacy text-LLM path is unsupported" understates
> it: R8 deleted it (E44). "No CI gate reads these status lines" is stale (E40). See
> [`16`](16-errata-2026-10-03.md) E30-E44, E46, E66, E80, E100, E115, E117, E120-E122.

## Start here

> **Currency — 2026-09-29 [V].** The sentence below ("**Nothing is implemented yet.**") was true
> when written and is now **false** — `4bfd6fa4` made the VLM path the shipped default on
> 2026-09-27 (`docker-compose.prod.yml:578`), and ledger items 38-41 are a real A5500 run against
> it. It survived this long because no CI gate reads these status lines. **For "what has actually
> run?", do not route by this page — route to the ledger**,
> [`2026-09-23-vss-gaming-gpu-ledger.md`](../plans/2026-09-23-vss-gaming-gpu-ledger.md); this
> directory stays the research record. M1 is still open — the run's close pointer says the
> notification link is unwired (ledger `:415`) and S3 sits below its bar in every arm measured
> (`10/20` at `:401` against `S3_MIN = 90%` at `:221`) — so "implemented" is not "accepted". The
> sentence stays as the record of 2026-09-23.

This directory is the **research record** behind an approved design for running a VSS-style AI tier
on one consumer-class GPU. **Nothing is implemented yet.** Pick your branch:

- **Implementing, planning, or asking "what did we decide?"** → the design spec,
  [`2026-09-23-vss-gaming-gpu-profile-design.md`](../superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md).
  It holds the locked decisions (D1-D12), success criteria (S1-S6), phases and milestones (M0-M4),
  and an A5500 bring-up checklist. It is the single source of truth for the plan.
  **Then read [`13-implementation-brief.md`](13-implementation-brief.md)**: how to work, the risk
  spikes to run first, the ledger, the guardrails, and where to stop and ask the owner.
- **Checking "what has actually run?"** → the execution ledger,
  [`docs/plans/2026-09-23-vss-gaming-gpu-ledger.md`](../plans/2026-09-23-vss-gaming-gpu-ledger.md):
  one row per step and spike, with the command, result and commit behind every status.
- **Asking "is this deferred, or did we miss it?"** → [`12-postponed-roadmap.md`](12-postponed-roadmap.md)
  (R1-R14: streaming ingest, NemoClaw, agent features, upstream PRs, model choices, and more).
- **Choosing or changing a specialist model** (face, plate, re-ID, open-vocabulary, pose, novelty)
  → [`14-specialist-model-research.md`](14-specialist-model-research.md): verified candidates, the
  Task 3b picks, and the rev 7 shortlist. Owner rulings are in the ledger as F12.
- **Citing any claim from docs 00-07** → check [`11-errata-2026-09-23.md`](11-errata-2026-09-23.md)
  first (E1-E28). Each of those docs carries a banner naming the entries that correct it.
- **Asking "why was it decided this way?"** → the audits of VSS `1e94133b4`:
  [`08`](08-audit-profile-anatomy.md) (profiles, placement, architecture, CI),
  [`09`](09-audit-integration-surfaces.md) (component contracts: what we can incorporate),
  [`10`](10-audit-feature-inventory.md) (features to import, our differentiators, NemoClaw).
- **Asking "what is broken, missing, or next?"** → [`17-action-plan.md`](17-action-plan.md), the living
  issue register (`ISS-nnn`: evidence, acceptance condition, who can act). Add new issues to its
  intake log as you find them; close, never delete. What shipped and was measured since the design:
  [`15`](15-progress-since-the-design.md). Corrections to 00-14 since the first errata:
  [`16`](16-errata-2026-10-03.md) (E29 onward). The proposed target:
  [`18`](18-world-class-target.md). Research checkpoints (unaudited): NVIDIA's accuracy practice
  [`19`](19-nvidia-accuracy-benchmarking.md); models per GPU tier, benchmarks, LoRA
  [`20`](20-model-tiers-benchmark-and-training.md).

**The design in one breath:** a detector gates FTP stills, and **one VLM** describes, verifies and
scores each candidate in a single constrained call. llama.cpp serves it first; VSS's RT-VLM joins
behind the same `ai_contract` op in a gated phase. It is developed on the GB300, proven by replay, measured across a Brev hardware matrix, and goes live
on a single RTX A5500 (24 GB, sm_86). Since spec rev 5 the legacy text-LLM path is unsupported.

## Purpose

The effort investigated NVIDIA's Video Search and Summarization (VSS) blueprint for a
**consumer-friendly VSS on gaming GPUs**: a single-box, single-user, offline-capable deployment tier
VSS does not serve. It began as an evaluation of replacing this project's AI pipeline (docs 00-07,
2026-09-18/19). It became a downstream-first design (2026-09-23) that imports VSS's **verification
pattern** rather than its services.

## Directory structure

```
docs/vss-integration/
├── AGENTS.md                     # This file - start here
├── README.md                     # Human entry point
├── 00-context.md                 # The goal, the two repos, the original decision
├── 01-vss-architecture.md        # VSS service map and mapping to our pipeline
├── 02-model-inventory.md         # Models, slots, sizing formula (4-bit column is wrong; see 04)
├── 03-open-questions.md          # Question register (Q1-Q9)
├── 04-fp4-and-deployment.md      # FP4 reality, the formula trap, consumer fit arithmetic
├── 05-hardware-profiles.md       # Halo / volume / entry tiering
├── 06-repo-a-readiness.md        # This repo's readiness (CI blockers closed 2026-09-21)
├── 07-lean-backend.md            # Avoiding Milvus/ES/Neo4j/Kafka; overlay recommendation
├── 08-audit-profile-anatomy.md   # Audit A (2026-09-23): profiles, placement, arch, CI, contribution
├── 09-audit-integration-surfaces.md  # Audit B: component contracts, what to incorporate
├── 10-audit-feature-inventory.md # Audit C: features to import, gap matrix, NemoClaw addendum
├── 11-errata-2026-09-23.md       # Corrections to 00-07 (E1-E28)
├── 12-postponed-roadmap.md       # Deliberately deferred items (R1-R14)
├── 13-implementation-brief.md    # How the implementing agent works: spikes, ledger, guardrails, stops
├── 14-specialist-model-research.md  # Specialist model candidates (2026-09-25), 3b picks, rev 7 shortlist
├── 15-progress-since-the-design.md  # What shipped and was measured, 2026-09-23 to 2026-10-03
├── 16-errata-2026-10-03.md       # Corrections to 00-14 (E29 onward)
├── 17-action-plan.md             # The living issue register (ISS-nnn): status, evidence, acceptance
├── 18-world-class-target.md      # Proposal: the capability ladder for a world-class pipeline
├── 19-nvidia-accuracy-benchmarking.md  # How NVIDIA's VSS team measures accuracy (checkpoint)
└── 20-model-tiers-benchmark-and-training.md  # VLMs per GPU tier, benchmarks, LoRA (checkpoint)
```

The design spec lives outside this directory, with the repo's other specs:
[`docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md`](../superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md).

## Evidence convention

**Every claim in this directory carries a status marker.** Preserve this when editing: the point is
that a future agent can tell a verified fact from an inference.

| Marker  | Meaning                                                                        |
| ------- | ------------------------------------------------------------------------------ |
| **[V]** | Verified by reading the source in-session. Cited with `path:line`.             |
| **[C]** | Computed from a verified formula. The formula and inputs are shown.            |
| **[E]** | External knowledge or web source. Needs confirmation against a primary source. |
| **[?]** | Open question. Not established.                                                |
| **[O]** | Stated by a human stakeholder. Outranks repo inference.                        |
| **[A]** | Agent-reported, not independently verified. Check before acting.               |

Promote a **[?]** or **[E]** to **[V]** only with the file and line you read.

## The VSS repository

Upstream: `NVIDIA-AI-Blueprints/video-search-and-summarization` (public). Docs 00-07 cite commit
`cdad5cc0e`; docs 08-12 and the spec cite `1e94133b4`. VSS moved 78 commits and 701 files in the
four days between those commits. **Re-verify any `path:line` before relying on it**; a citation
that fails to resolve means VSS moved, not that the finding was wrong.

## Patterns

- **Name the layer.** VSS bundles three independently adoptable layers:

  1. models: RT-CV, RT-Embed, RT-VLM, LLM;
  2. storage: Milvus, Elasticsearch, Neo4j, ArangoDB;
  3. bus: Kafka.

  Say which one a question is about. The design adopts a _pattern_ from layer 1 and none of layers
  2-3.

- **Separate three model claims:**

  1. a variant _exists_;
  2. VSS _wires_ it;
  3. it _runs on a consumer GPU_.

  Only the third decides anything.

- **Size from blob sizes, never the VSS formula.** The formula understates NVFP4 by ~40% (see 02's
  boxed warning and 04). For llama.cpp, sum the weights, mmproj, KV and buffers.
- **Record corrections as errata.** Add a dated errata file (or entries to 11) and a banner on the
  corrected doc. The original text stays as the evidence record.
- **When a roadmap item is picked up,** give it its own spec and mark it in 12 with the date and a
  link.

## Related documentation

- [`ai/AGENTS.md`](../../ai/AGENTS.md): the AI tier. Note that E4 corrects its on-demand Triton
  loading claim for production.
- [`backend/ai_contract/AGENTS.md`](../../backend/ai_contract/AGENTS.md): the contract seam the
  design extends with `vlm_assess`.
- [`docs/ROADMAP.md`](../ROADMAP.md): the project-wide post-MVP roadmap.
