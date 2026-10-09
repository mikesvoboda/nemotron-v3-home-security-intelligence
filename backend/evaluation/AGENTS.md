# Evaluation Module

## Purpose

This module measures the VLM verdict path: a detector gates each candidate and ONE vision-language
model describes, verifies and risk-scores it (`vlm_assess`). It holds the frozen eval-item schema, the
immutable eval store, the importers that turn labeled events and generated corpus sets into items, the
S2/S3/S5 metrics against the owner-set bars (S2 <= 5%, S3 >= 90%), and the replay that runs a served
VLM over the store through the shipped `VlmClient`.

The package exports nothing; import the submodules directly. `synthbench/run` and `synthbench/score`
(the only synthbench packages allowed to import `backend`) drive these modules through
`python -m synthbench replay` and `score`.

## Directory Structure

```
backend/evaluation/
├── AGENTS.md          # This file
├── __init__.py        # Docstring only; no re-exports
├── assess_input.py    # AssessInput / EvalItem frozen schema (the vlm_assess input contract)
├── control_freeze.py  # Freezes real events into the store (the D10 media-residence guard)
├── eval_store.py      # SQLite ledger: items, runs, results; synthetic label-set loader
├── label_import.py    # Owner-labeled events and generated corpus sets -> eval items
├── levels.py          # Risk score -> level banding (low 0-29, medium 30-59, high 60-84, critical 85+)
├── s_metrics.py       # S2 / S3 / S5 with 95% Wilson intervals, in-repo (no scipy)
└── vlm_replay.py      # Replays a served VLM over the store through the shipped VlmClient
```

## Key Components

### assess_input.py

`AssessInput` is the frozen snapshot the VLM verifier sees (camera, detections, zone state, household
context, timestamp, and the stored specialist outputs). `EvalItem` wraps it with the label and the
expected risk score. Items reference media by PATH only; the bytes never enter the store (D10).

### eval_store.py

A small SQLite ledger of frozen items, runs and results. Items are immutable once written; a run pins
its endpoint, build and conditions. The privacy guard refuses media paths that point into the repo or a
capture root. `load_synthetic_items` reads the committed label sets.

### label_import.py and control_freeze.py

`import_generated_items` turns a generated corpus export (`<category>/<set>/expected_labels.json` plus
the still) into frozen items; labels come from the set's placement and declared risk band, not from a
model. `import_loaded_event` / `import_event` turn an owner-labeled production event into an item.
`control_freeze` freezes events with the media-residence guard shared by both paths.

### levels.py

`score_to_level` and `level_at_or_above` are the single definition of the risk bands the dashboard,
the notification path and the harness share. Do not spell the 30/60/85 table anywhere else.

### s_metrics.py

S2 (false alarms on benign items scored at or above medium) and S3 (incidents scored at or above their
expected minimum level), each reported as rate, n and a 95% Wilson interval, plus S5 (refusals). The bars
(`S2_MAX_PCT`, `S3_MIN_PCT`) are the owner's; a change is an owner decision.

### vlm_replay.py

`run_replay` runs the store's items against a served `ai-vlm` through the SHIPPED `VlmClient` and writes
results through `EvalStore`. It reads each item's STORED specialist outputs and never re-runs a
specialist: the givens are the point of a replay.

Replay measures the judge production runs (B1.2):

- Every verdict passes through the analyzer's own `apply_verdict_invariants` with production's
  `SeverityService`, so a row's score and level are the ones the analyzer stores. The model's raw
  score stays in the row's verdict dump.
- The default frames mode, `selector`, is production's `build_assess_request` with
  `key_frame_spread_seconds`, for items whose detection rows name their frame. Other items (stills,
  frozen events) fall back to their stored frames, and each fallback is counted. `stored` (an
  item's first four media paths) re-runs a committed corpus byte for byte; `burst` feeds every
  frame.
- The report counts clamps and frame fallbacks (`parity`), and records its `severity_thresholds`
  and `selector_spread_seconds`.

## Testing

Tests live in `backend/tests/unit/evaluation/` (see its `AGENTS.md`). They need no GPU and no pandas.

## Related Documentation

- `/synthbench/AGENTS.md` - the benchmark that drives replay and score
- `/docs/vss-integration/` - the design record and the action-plan register
- `/backend/services/AGENTS.md` - `vlm_client.py`, `vlm_analyzer.py` and the verdict ladder
