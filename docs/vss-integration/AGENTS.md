# VSS Integration - Agent Guide

## Start here

This directory is the **research record** behind an approved design for running a VSS-style AI tier
on one consumer-class GPU. **Nothing is implemented yet.** Pick your branch:

- **Implementing, planning, or asking "what did we decide?"** → the design spec,
  [`2026-09-23-vss-gaming-gpu-profile-design.md`](../superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md).
  It holds the locked decisions (D1-D12), success criteria (S1-S6), phases and milestones (M0-M4),
  and an A5500 bring-up checklist. It is the single source of truth for the plan.
  **Then read [`13-implementation-brief.md`](13-implementation-brief.md)**: how to work, the risk
  spikes to run first, the ledger, the guardrails, and where to stop and ask the owner.
- **Asking "is this deferred, or did we miss it?"** → [`12-postponed-roadmap.md`](12-postponed-roadmap.md)
  (R1-R14: streaming ingest, NemoClaw, agent features, upstream PRs, model choices, and more).
- **Citing any claim from docs 00-07** → check [`11-errata-2026-09-23.md`](11-errata-2026-09-23.md)
  first (E1-E28). Each of those docs carries a banner naming the entries that correct it.
- **Asking "why was it decided this way?"** → the audits of VSS `1e94133b4`:
  [`08`](08-audit-profile-anatomy.md) (profiles, placement, architecture, CI),
  [`09`](09-audit-integration-surfaces.md) (component contracts: what we can incorporate),
  [`10`](10-audit-feature-inventory.md) (features to import, our differentiators, NemoClaw).

**The design in one breath:** a detector gates FTP stills, and **one VLM** describes, verifies and
scores each candidate in a single constrained call. llama.cpp serves it first; VSS's RT-VLM joins
behind the same `ai_contract` op in a gated phase. It is developed on the GB300, proven by replay, measured across a Brev hardware matrix, and cut over
behind a flag on a single RTX A5500 (24 GB, sm_86).

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
└── 13-implementation-brief.md    # How the implementing agent works: spikes, ledger, guardrails, stops
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
