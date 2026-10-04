# 21 — Entry pages record (2026-09-23)

> **Record, not state - never read this for what is true now.** On 2026-10-03 the owner decided (asked
> and answered in the session, recorded in `17-action-plan.md` under the Intake log entry "after the merge
> of #6783 and the reorganization decisions") that `README.md` and `AGENTS.md` become a maintained State of
> the stack and agent guide, and that their 2026-09-23 bodies move here. They are kept VERBATIM, with the
> correction banners they had accumulated, because this folder is a research record and the frozen-prose
> rule applies to them as to every other doc. Git history keeps the same text at `0d740944` and earlier.
>
> **Old line cites.** Other docs cite these bodies as `README.md:N` and `AGENTS.md:N`. Those line numbers
> are now line `N + 21` of this file for the README body and line `N + 115` for the AGENTS body (the
> README body starts at line 22 and the AGENTS body at line 116).
>
> The stale status lines below are the record of 2026-09-23, not a claim. The docs gate
> (`scripts/check-vss-docs-currency.py`) no longer guards them for README and AGENTS because they are no
> longer there.

---

## The README body (2026-09-23, verbatim)

# VSS Integration

> **Currency - 2026-10-03 [V].** The banner below and the body carry claims that need correcting.
> "M2 stays open because the VLM pick is still the owner's" is false: the owner picked
> Qwen3-VL-8B on 2026-09-28, and M2 closure is what is open (E29). "S3 fails its bar in every arm
> measured" holds, but the `10/20` is a 38-item set; the 450-still replay gives S3 36.5% and S2
> 6.7%, one draw among re-runs that vary (E30, E31).
> `docker-compose.prod.yml:578` is now `:484` (E37). "A single constrained call" covers stills only
> (E32). "ships as the default" needs `--profile vlm` (E34). Also: the Brev matrix was never run
> (E35), "Current state: the ledger" omits the synthbench corpus (E36), "rev 7 shortlist" is taken
> (E122). See [`16`](16-errata-2026-10-03.md) E29-E38.

Research and design for bringing NVIDIA's **Video Search and Summarization (VSS)** blueprint's
approach to this project on **consumer gaming GPUs**, a market VSS does not serve.

> **Currency — 2026-09-29 [V].** The status line below ("design approved, nothing implemented yet")
> was true when written and is now **false.** The
> VLM path is implemented and is the shipped default: `4bfd6fa4` ("Phase 1 - the VLM path runs end
> to end and ships as the default", #6681, 2026-09-27) flipped `docker-compose.prod.yml:578` to
> `PIPELINE_MODE=${PIPELINE_MODE:-vlm}`, and the A5500 qualification run is ledger items 38-41.
> What has _not_ happened is M1-M4 closure. M1 stays open — the run's own close pointer says so
> ("the notification link is unwired", ledger `:415`) — and M2 stays open because the VLM pick is
> still the owner's, listed as deferred at [`12`](12-postponed-roadmap.md) R10. S3 fails its bar in
> every arm measured (`10/20` at `:401` against `S3_MIN = 90%`, the ruling at `:221`). Read "shipped
> as the default" as "shipping", not as "accepted". The status line is kept as the record of what was
> decided on 2026-09-23. Current state: the ledger,
> [`2026-09-23-vss-gaming-gpu-ledger.md`](../plans/2026-09-23-vss-gaming-gpu-ledger.md).

> **Status (2026-09-23): design approved, nothing implemented yet.**
> The plan is the design spec:
> [`2026-09-23-vss-gaming-gpu-profile-design.md`](../superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md).
> Agents: start with [`AGENTS.md`](AGENTS.md).

## Where things stand

- **The decision.** A detector gates each FTP still. **One vision-language model** then describes,
  verifies and scores each candidate in a single constrained call. That's VSS's alert-verification
  pattern, aimed at this product's real problem: false positives.
- **Engines.** llama.cpp serves the model first. VSS's own RT-VLM joins behind the same contract in
  a later, gated phase.
- **Proof.** Development and replay run on the GB300. A Brev hardware matrix measures fit and latency per
  GPU tier, and the go-live happens on one RTX A5500 (24 GB).

**What the research found:**

- VSS's _services_ mostly don't fit a single-box product. They are video-first and tied to
  Kafka/Elasticsearch.
- Its _verification pattern_ fits exactly.
- The smallest configuration VSS validates is two 32 GB GPUs, so the consumer gap is real ([`11`](11-errata-2026-09-23.md) E2).

## Read in this order

| Document                                                                               | What it answers                                                                        |
| -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| **The design spec** (link above)                                                       | What we are building, the success criteria, the phases                                 |
| [`17-action-plan.md`](17-action-plan.md)                                               | The living issue register: what is broken or missing, who can act, and how each closes |
| [`15-progress-since-the-design.md`](15-progress-since-the-design.md)                   | What shipped and what was measured since the design (2026-09-23 to 2026-10-03)         |
| [`16-errata-2026-10-03.md`](16-errata-2026-10-03.md)                                   | Corrections to docs 00-14 since the first errata (E29 onward)                          |
| [`18-world-class-target.md`](18-world-class-target.md)                                 | Proposal: the capability ladder toward a world-class video reasoning pipeline          |
| [`19-nvidia-accuracy-benchmarking.md`](19-nvidia-accuracy-benchmarking.md)             | How NVIDIA's VSS team measures accuracy (research checkpoint, unaudited)               |
| [`20-model-tiers-benchmark-and-training.md`](20-model-tiers-benchmark-and-training.md) | VLMs per GPU tier, benchmarks, LoRA (research checkpoint, unaudited)                   |
| [`13-implementation-brief.md`](13-implementation-brief.md)                             | How the implementing agent works, including a kickoff prompt                           |
| [`12-postponed-roadmap.md`](12-postponed-roadmap.md)                                   | What we deliberately left for later, and what reopens each item                        |
| [`14-specialist-model-research.md`](14-specialist-model-research.md)                   | Which small models the specialists should use, and the rev 7 shortlist                 |
| [`10-audit-feature-inventory.md`](10-audit-feature-inventory.md)                       | Which VSS features are worth importing, and what we have that VSS lacks                |
| [`09-audit-integration-surfaces.md`](09-audit-integration-surfaces.md)                 | Which VSS components fit, with their exact contracts                                   |
| [`08-audit-profile-anatomy.md`](08-audit-profile-anatomy.md)                           | How VSS hardware profiles work; what an upstream consumer tier would take              |
| [`11-errata-2026-09-23.md`](11-errata-2026-09-23.md)                                   | Corrections to the earlier research (00-07)                                            |
| [`00-context.md`](00-context.md) … [`07-lean-backend.md`](07-lean-backend.md)          | The original 2026-09-18/19 research. Each doc carries an errata banner.                |

## Evidence convention

Every claim carries a marker. **Preserve these when editing.**

- **[V]** Verified against the source, cited with `path:line`
- **[C]** Computed from a verified formula
- **[E]** External source, needs primary confirmation
- **[?]** Open question
- **[O]** Stated by a human stakeholder; outranks repo inference
- **[A]** Agent-reported, not independently verified; check before acting

## Contributing to this directory

- Promote **[?]** or **[E]** to **[V]** only with a file and line you actually read.
- Record corrections as dated errata with a banner on the corrected doc. The original text stays as
  the record.
- When a roadmap item in [`12`](12-postponed-roadmap.md) is picked up, give it its own spec and mark
  it there with the date and a link.
- VSS is actively developed. A citation that no longer resolves means VSS moved; re-verify it.

---

## The AGENTS body (2026-09-23, verbatim)

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
