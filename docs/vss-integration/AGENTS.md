# VSS Integration Research - Agent Guide

## Purpose

Findings from investigating NVIDIA's Video Search and Summarization (VSS) blueprint as a
replacement for this project's self-built AI pipeline. The product goal is a **consumer-friendly
VSS targeting gaming GPUs** — a single-box, single-user, offline-capable deployment profile in a
market segment the VSS team has not served.

This directory is **research, not a plan**. Nothing here has been implemented. Read
[`00-context.md`](00-context.md) first; it explains why this work exists and what decision it
feeds.

## Directory Structure

```
docs/vss-integration/
├── AGENTS.md               # This file - AI navigation
├── README.md               # Human entry point
├── 00-context.md           # The goal, the two repos, the decision this feeds
├── 01-vss-architecture.md  # What VSS is; service map; mapping to our pipeline
├── 02-model-inventory.md   # Models, slots, sizing math, consumer-GPU budgets
├── 03-open-questions.md    # Unresolved questions and in-flight investigations
├── 04-fp4-and-deployment.md # FP4 availability, local paths, verified consumer fit
├── 05-hardware-profiles.md # Tiering strategy: halo / volume / entry
├── 06-repo-a-readiness.md  # What must be fixed HERE before any swap
└── 07-lean-backend.md      # Can we avoid VSS's infrastructure? (yes, with caveats)
```

## Key Files

| File                       | Purpose                                                            |
| -------------------------- | ------------------------------------------------------------------ |
| `00-context.md`            | Why this research exists; the three-step product plan              |
| `01-vss-architecture.md`   | VSS service decomposition and how it maps onto our `ai/` tier      |
| `02-model-inventory.md`    | Every model VSS can serve, its slot, precision, and VRAM budget    |
| `03-open-questions.md`     | What is still unknown, and what must be verified before deciding   |
| `04-fp4-and-deployment.md` | FP4 reality, the formula trap, verified consumer fit math          |
| `05-hardware-profiles.md`  | Hardware tiering; why the volume tier is the existing architecture |
| `06-repo-a-readiness.md`   | Verified defects in THIS repo that block a swap                    |
| `07-lean-backend.md`       | Storage/bus abstraction reality; the overlay recommendation        |

## Evidence Convention

**Every claim in this directory carries a status marker.** Preserve this when editing — the whole
point is that a future agent can tell a verified fact from an inference.

| Marker  | Meaning                                                                        |
| ------- | ------------------------------------------------------------------------------ |
| **[V]** | Verified by reading the VSS repo in-session. Cited with `path:line`.           |
| **[C]** | Computed from a verified formula. The formula and inputs are shown.            |
| **[E]** | External knowledge or web source. Needs confirmation against a primary source. |
| **[?]** | Open question. Not established.                                                |

Do not promote a **[?]** or **[E]** to **[V]** without citing the file and line you read.

## The VSS Repository

Findings here were gathered from a local clone:

```
/home/msvoboda/github/video-search-and-summarization
```

**This path is machine-local and not guaranteed to exist for you.** It is the
`NVIDIA-AI-Blueprints/video-search-and-summarization` public repository. VSS is actively
developed — commits landed during this research — so **re-verify any `path:line` citation before
relying on it.** A citation that fails to resolve means VSS moved, not that the finding was wrong.

## Entry Points

### Starting fresh on this topic

**File:** [`00-context.md`](00-context.md)

Read in order: `00` → `07`. The numbering is a reading order, not a priority order.

**If you only read two:** [`06-repo-a-readiness.md`](06-repo-a-readiness.md) for what to do next
in this repo, and [`04-fp4-and-deployment.md`](04-fp4-and-deployment.md) for whether the consumer
thesis holds.

### Answering "will X fit on a consumer GPU?"

**File:** [`04-fp4-and-deployment.md`](04-fp4-and-deployment.md) — **not** `02`.

`02` contains VSS's sizing formula and GPU budgets, but its 4-bit column is **wrong** and labelled
as such: the formula understates NVFP4 by ~40% because vision towers stay BF16. **Always size from
HuggingFace blob sizes.**

### Deciding what to work on next

**File:** [`06-repo-a-readiness.md`](06-repo-a-readiness.md)

Four verified CI defects in this repo outrank further mutation-census work, including a coverage
pipeline that has never computed anything.

## Patterns

### Separate the three layers before answering any integration question

VSS bundles three independently adoptable layers. Most confusion about "adopting VSS" comes from
treating them as one thing:

1. **Model tier** — RT-CV, RT-Embed, RT-VLM, LLM. This is the part with the value we lack.
2. **Storage tier** — Milvus, Elasticsearch, Neo4j, ArangoDB. Scales to warehouses and cities.
3. **Message bus** — Kafka. Decoupling and/or durability, depending on the path.

Adopting layer 1 does not require layers 2 and 3. Say which layer a question is about.

### Distinguish three different claims about any model

These get conflated constantly and only the third one decides anything:

1. A variant **exists** (someone published a checkpoint).
2. **VSS wires it** (there is a tested configuration in-tree).
3. **It runs on a consumer GPU** (kernels exist for that compute capability, and it fits VRAM).

## Related Documentation

- [`ai/AGENTS.md`](../../ai/AGENTS.md) - The pipeline VSS would replace
- [`backend/AGENTS.md`](../../backend/AGENTS.md) - Backend services, including the AI clients
- [`docs/ROADMAP.md`](../ROADMAP.md) - Post-MVP direction
- [`docs/plans/2026-09-12-context-map-doc-updates.md`](../plans/2026-09-12-context-map-doc-updates.md) - The ledger; test-platform program ground truth
