# Auto-VLM research: an agentic search for threat-detection accuracy

> **Status: design proposal. Nothing here is built.** Work starts after the `docs/uplevel/` campaign completes, so this design assumes nothing about the tree as it will stand then. Every path, number and module named below is **evidence as of `origin/main` `9cb9e60b0` (2026-10-23)**, cited to show where a claim came from. The design depends on the interfaces and requirements it states, not on those paths.

## What this is

[autocuda](https://gitlab-master.nvidia.com/blelbach/autocuda) is an NVIDIA-internal agent system that optimizes CUDA code by parallel tree search: a manager agent writes short research briefs, worker agents each build and measure one idea on its own git branch, and the manager steers the search from the measurements. This folder designs an equivalent for this project, called **autovlm** here, whose objective is the accuracy of the VLM threat-detection path rather than kernel speed: fewer false alarms (S2) and more incidents caught (S3), at every GPU memory size the product targets.

autovlm keeps autocuda's search machinery and replaces its measurement model. CUDA benchmarks are noisy measurements of a quantity the code fully determines, so more trials converge on the truth. Our replays are deterministic, but they measure a small sample of the scenes that matter, so more trials converge on the sample. The design spends most of its effort there: blinded inputs, a scorer that holds the labels where no agent can read them, scenario-clustered statistics, and fresh scenario batches every epoch.

## Why now

The project has already run two searches by hand, and both showed what an automated one must handle.

- **The 2026-10-03 model sweep** ran 12 VLMs and 3 controls on the 450 `tierb-v0` stills. No arm advanced under the OD-26 rule; the shipped Qwen3-VL-8B read S2 10.0% and S3 39.0% against the F14 bars of 5% and 90%. With 31 scenarios the clustered intervals were 6 to 26 points wide, so the corpus could not separate the arms (`docs/benchmarks/synthbench/sweep-2026-10-03/report.md`).
- **The prompt programme** (2026-10-04 to 10-05) ran ten prompt arms in four stages for about 10.8 GPU-hours. None passed OD-26 at the shipped threshold; it concluded that confirmed-wrong verdicts are a perception limit, not a wording problem (`docs/vss-integration/23-prompt-programme-stages-1-4-2026-10-05.md`).
- **One still cannot reach F14.** Across all 15 sweep arms the single-still S3 ceiling is 73.4% to 76.3% (`docs/research/2026-10-07-iss086-s3-ceiling/README.md`).

A search harness makes such programmes cheaper to run and harder to fool yourself with. It does not make a 31-scenario corpus able to certify a small gain; growing the corpus is part of the design.

## Decisions so far

Taken by the owner in the design session of 2026-10-23.

| ID  | Decision                                                                                                                          | Where it is designed                                 |
| --- | --------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| D1  | Optimize a **Pareto front per GPU memory tier**: accuracy, VRAM and latency together, one best stack per tier                     | [`02-evaluation.md`](02-evaluation.md)               |
| D2  | Data: **grow synthbench** with fresh scenario batches, and use **public datasets for training only**, never for selection         | [`02-evaluation.md`](02-evaluation.md)               |
| D3  | Compute: **search on the GB300** through `agent-gpu`; **confirm tier fit on Brev** cards                                          | [`05-stack-integration.md`](05-stack-integration.md) |
| D4  | Agents: a **Claude manager** and **flagship-Qwen workers**                                                                        | [`01-architecture.md`](01-architecture.md)           |
| D5  | Build an **in-repo harness that borrows autocuda's concepts**, rather than adopting autocuda or writing skills only               | [`01-architecture.md`](01-architecture.md)           |
| D6  | Memory is the run ledger, the caches and a **findings register** of mechanism-level results; **workers never talk to each other** | [`01-architecture.md`](01-architecture.md)           |
| D7  | **No network ports between agents.** Workers reach one token-gated host service; the scorer listens on no TCP port                | [`01-architecture.md`](01-architecture.md)           |
| D8  | System-1 decision models need **more research** before the harness commits to a design for them                                   | [`04-system-1-research.md`](04-system-1-research.md) |

## Reading order

1. [`01-architecture.md`](01-architecture.md) — the units, their interfaces, how they communicate, and why no agent needs a network port to another.
2. [`02-evaluation.md`](02-evaluation.md) — splits, metrics, the Pareto front, the noise floor, anti-gaming, and how a winner leaves the harness.
3. [`03-idea-catalogue.md`](03-idea-catalogue.md) — what the search would explore, layer by layer, with cost, evidence and gates for each idea.
4. [`04-system-1-research.md`](04-system-1-research.md) — the open research brief for fast decision models.
5. [`05-stack-integration.md`](05-stack-integration.md) — what changes in `dgx-station-inference-stack`, and the spikes that must pass first.

## Build order

Each phase is useful on its own; later phases need the earlier ones.

| Phase | Delivers                                                                                                                                                                                                                   | Useful without agents?                            |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| P0    | The spikes in [`05-stack-integration.md`](05-stack-integration.md)                                                                                                                                                         | —                                                 |
| P1    | The measurement core: blinded export, detector-fed inputs, the split-tier scorer and its query ledger, cluster ranking, the null envelope, recipe v0. A human runs `autovlm eval <recipe>` and gets the realistic baseline | Yes. The realistic baseline is worth having alone |
| P2    | The executor: host daemon, content-addressed cache, token-gated API, `autovlm status` with the Pareto front                                                                                                                | Yes. Humans submit recipes                        |
| P3    | A one-worker loop: manager and worker skills, the findings register seeded from existing research, herdr control, the stack-repo launch flag                                                                               | First agentic run                                 |
| P4    | The tree fleet: N workers, briefs and epochs, combine briefs, the auditor, fresh synthbench batches per epoch                                                                                                              | —                                                 |
| P5    | The expensive lanes: LoRA and system-1 training, specialist plugins, automated Brev tier confirmation                                                                                                                      | —                                                 |

A dated implementation plan for any phase goes under `docs/superpowers/<date>-<slug>/` (UR-87), not in this folder.

## Open questions for the owner

- **Placement.** The design proposes a new top-level `autovlm/` package with its own `AGENTS.md`. That needs a lane after the uplevel campaign and a boundary entry in `.agents-md-validator.yml`.
- **What kind of doc this folder is.** The uplevel vocabulary treats every doc outside the history folders as a living doc that must match the tree. This folder describes something unbuilt, so the docs lane may want to classify it as history, like `docs/vss-integration/`.
- **Specialist ship gates.** The harness may explore new specialist models, but promoting one keeps the existing gate: an owner-approved spec revision and a false-alarm check on the owner's night footage.
