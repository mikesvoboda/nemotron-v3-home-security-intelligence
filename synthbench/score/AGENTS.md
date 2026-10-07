# synthbench/score — Agent Guide

## Purpose

Scores replays of the exported items (synthbench P5a,
`docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` §5). With
`synthbench/run/`, the only synthbench package that may import `backend` (spec §7.1;
`backend/tests/unit/synthbench/test_import_rule.py`).

## Files

| File                   | What                                                                                                        |
| ---------------------- | ----------------------------------------------------------------------------------------------------------- |
| `metrics.py`           | pure: `Item`, `cell`, `outcome`, `band_position`, headline, slices, the audit summary, the comparison, rows |
| `report.py`            | `markdown` (aggregate only, committed by the scored run) and `html` (the failure gallery)                   |
| `scoring.py`           | `execute`: loads the replays, their eval store, the export and the audit; writes the four outputs           |
| `clip_audit_report.py` | `report`: the clip audit's survivor rates and declared-versus-picked matrices (ISS-038's disclosure)        |

The commands are `synthbench/commands/score.py` (`python -m synthbench score`) and
`synthbench/commands/clip_audit.py` (`clip audit bias`); the latter imports only this module,
inside its `bias()` step.

## Rules

- S2 and S3 come only from `backend/evaluation/s_metrics.py`. `outcome` restates their per-row
  rule for slices, the gallery and the comparison; a test holds the two equal.
- Labels and S3 floors come from the eval store, as `vlm_replay` derives them; facts and stills
  come from the export.
- `report.md` never names an item: it is committed. Per-item content lives in `results.jsonl`
  and `report.html`, under `$SYNTHBENCH_ROOT/runs/scores/`.
- `report.md` states each model's conditions (prompt, thinking, max tokens, read timeout,
  enforcement probe) from its `run.json` (decision A7), and shows paths relative to
  `$SYNTHBENCH_ROOT`, never an absolute host path; `metrics.json`'s identity keeps them absolute.
- Every rate is a `cell`: k, n, rate and the 95% Wilson interval, insufficient under n = 10.
