# autovlm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build autovlm, an agentic tree search that improves the VLM threat-detection path's accuracy (S2 false alarms, S3 incident hits) per GPU memory tier, without letting the search fool itself.

**Architecture:** A host-side executor turns declarative recipes into replays on blinded inputs; a scorer that alone holds the labels answers by split tier (per-item on train, aggregates on select, owner-only on holdout); a Claude manager writes briefs that flagship-Qwen workers in sbx sandboxes execute as recipe commits. Ranking is OD-26's paired scenario-cluster test per tier, judged against a null-perturbation envelope.

**Tech Stack:** Python 3.14, pydantic 2, PyYAML, httpx, Pillow, pytest; the repo's `synthbench` export and `backend` VLM client and evaluation modules; `agent-gpu`, `agent-dgx`, herdr and sbx from `dgx-station-inference-stack`.

**Spec:** [`docs/auto-vlm-research/`](../../auto-vlm-research/README.md) (design, 2026-10-23). Read its README and `01`–`05` before any task; this plan argues from them.

## Global Constraints

- **Start condition:** no task starts before the `docs/uplevel/` campaign completes (owner, 2026-10-23). The plan was written against `origin/main` `9cb9e60b0`; every task that touches an existing module opens with a step that re-verifies that module's interface, and adapts the task if the interface moved.
- Python 3.14 (`.python-version`); type hints on every function (mypy); ruff, line length 100.
- `autovlm/` is a new top-level package beside `synthbench/`. Its tests live in `backend/tests/unit/autovlm/`, because CI runs only `backend/tests/unit/`. Unit tests never need a GPU; tests that do carry `@pytest.mark.gpu`, which the default `addopts` (`-m 'not gpu'`) excludes.
- Never commit with `--no-verify`. If the git hooks are not installed, run `uvx pre-commit run --files <changed files>` and commit only when it exits 0.
- Blinded inputs never contain labels, scenario names, categories, item ids, generation prompts, or declared subjects and props (design `01` §3.3).
- Holdout answers only the owner's confirmation (design `02` §2). No task automates it.
- OD-26 margins: no clear harm = upper(dS2) ≤ +2.0 and lower(dS3) ≥ −5.0 points; clear benefit = upper(dS2) < 0 or lower(dS3) > 0; 10,000 resamples of whole scenarios; the seed is recorded with every result.
- S3 keeps its per-incident floor at every threshold: false alarm iff a benign score ≥ T; hit iff an incident score ≥ max(T, the incident's floor). At T = 30 this reproduces the 2026-10-03 sweep exactly. Single-cutoff readings (AUROC, recall at 5% false alarms) are diagnostics and are never compared with the F14 90% bar.
- S3 floor per incident: the shipped level of the band midpoint, `(min_score + max_score) // 2`, through `backend/evaluation/levels.py` (low 0, medium 30, high 60, critical 85). Verified on all 241 `tierb-v0` incidents.
- Tier budgets (GiB, 0.85 of card memory): 8.5, 10.2, 13.6, 20.4, 27.2, 40.8, plus unbounded.
- autovlm never stops the flagship, never writes to `main` or the product, and never raises the global `agent-gpu` VRAM cap.
- Later phases' plans go in this directory (UR-87).

## Phases

| Phase | File                                                   | Detail                            | Delivers                                                                                                                                        |
| ----- | ------------------------------------------------------ | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| P0    | [`p0-spikes.md`](p0-spikes.md)                         | Step level                        | Seven spikes, each with a pass criterion; results recorded in the design folder                                                                 |
| P1    | [`p1-measurement-core.md`](p1-measurement-core.md)     | Step level                        | The `autovlm` package: recipe, blinding, splits, scorer, checks, envelope, stages, `blind`/`split`/`eval`; the realistic baseline report        |
| P2    | [`p2-executor-and-front.md`](p2-executor-and-front.md) | Task level; expand when P1 merges | Cache, run ledger, front per tier, manifest check, endpoint pool, executor queue and API, scorer socket service, `status`                       |
| P3    | [`p3-one-worker-loop.md`](p3-one-worker-loop.md)       | Task level; expand when P2 merges | Prompt-template seam, findings register, briefs, worker verbs, herdr control, skills, stack-repo launch flag, first agentic run                 |
| P4    | [`p4-tree-fleet.md`](p4-tree-fleet.md)                 | Task level; expand when P3 merges | N workers, brief kinds and epochs, `wait`, fresh batches with a drained fleet, the auditor, Brev hand-off                                       |
| P5    | [`p5-expensive-lanes.md`](p5-expensive-lanes.md)       | Task level; expand when P4 merges | Trainer lane and registry, LoRA, system-1 (gated on research), plugins in fenced containers, specialists, tracking, automated Brev confirmation |

**A parallel research track, R1: system-1.** The questions in design [`04`](../../auto-vlm-research/04-system-1-research.md) are answered by research, not code, and can start any time after P1 (its first experiment needs P1's realistic baseline). Run it with the repo's `research` skill or a dedicated session; its report lands beside `04-system-1-research.md` and decides P5 Task 3's gate.

**Why later phases are task level.** Each phase builds on code the previous one creates, and the tree will have moved by the time this plan runs. Writing step-level code for P2–P5 now would guess at both. When a phase's predecessor merges, run superpowers:writing-plans on that phase's file against the then-current tree; the task list, interfaces, tests and acceptance criteria written here are the expansion's requirements.

## Dependencies

```
P0 spikes ──► P1 measurement core ──► P2 executor ──► P3 one-worker loop ──► P4 fleet ──► P5 lanes
   S7 gates P1 Task 12 (detector path)          S1, S4 gate P2 scorer/API     S2, S3 gate P3     S5 gates P5 probe
```

## Status

- [ ] P0 spikes
- [ ] P1 measurement core
- [ ] P2 executor and front
- [ ] P3 one-worker loop
- [ ] P4 tree fleet
- [ ] P5 expensive lanes
- [ ] R1 system-1 research (parallel, after P1)
