# synthbench/spikes/p1_bakeoff — Agent Guide

## Purpose

The throwaway P1 bake-off harness (spec §3.7; plan `docs/superpowers/plans/2026-09-27-synthbench-p1-bakeoff.md`). Not a pattern to copy: durable code lives in `synthbench/generate/`.

## Key Files

| File         | What                                                                                 |
| ------------ | ------------------------------------------------------------------------------------ |
| `cases.py`   | the hard prompts, identity shots, clip cases, seeds and sizes                        |
| `plan.py`    | expands the cases into stage-major jobs (each model's jobs are contiguous)           |
| `run.py`     | resumable runner, run inside a GPU window; writes `records.jsonl` and `groups.jsonl` |
| `measure.py` | OWLv2, facenet and EasyOCR measurement; runs inside the renderer image               |
| `sheet.py`   | the static HTML contact sheet the owner rates                                        |
| `report.py`  | aggregates records, measures and ratings into the P1 report under `docs/benchmarks/` |

## Rules

- Outputs go under `$SYNTHBENCH_ROOT/p1`; every CLI here takes `--root`. Media never enters the repo.
- `measure.py` and `cases.py` run on the renderer image's Python 3.12: keep them 3.12-parseable.
- Tests live in `backend/tests/unit/synthbench/spikes/` and cover only the pure logic.
