# Evaluation Module

## Purpose

Two evaluation chains live here. The one the shipped stack is measured with is the **VLM replay
chain**: a frozen corpus of eval items is replayed against a served `ai-vlm` through the shipped
`VlmClient`, and the results are scored as S2/S3 rates with Wilson intervals. The other is the
older **prompt-template harness** (`harness.py`), which speaks to a completions endpoint that no
shipped service provides and runs on CI only in `--mock` mode.

The owner-facing entry points are the `synthbench` commands (`synthbench/AGENTS.md` is the
corpus-side guide); this package holds the backend halves they import.

## The Live Chain, Step by Step

```
corpus events ($SYNTHBENCH_ROOT/corpus)
  -> python -m synthbench export vss          # writes the eval-store import layout
  -> import_generated_items / import_event    # label_import.py: born-labeled + owner-labeled items
     (freeze_event in control_freeze.py is the pre-switch sibling: same store, recorded control)
  -> EvalStore (eval_store.py)                # SQLite ledger of items/runs/results, off-repo path
  -> python -m synthbench replay --model qwen3-vl-8b
        # synthbench/run/replay.py calls vlm_replay.run_replay with ONE VlmClient per run
  -> python -m synthbench score --replay <id> [--replay <other-id>]
        # synthbench/score/* scores via s_metrics.py + levels.py, emits the report
```

Direct harness run (what `synthbench replay` wraps), verified against `vlm_replay.main()`:

```bash
uv run python -m backend.evaluation.vlm_replay \
    --store "$SYNTHBENCH_ROOT/eval/<version>" \
    --candidate Qwen3VL-8B-Instruct-Q4_K_M@ai-vlm:sm103-v12 \
    [--vlm-url http://127.0.0.1:8098] [--limit N] [--all-items] [--out report.json]
```

Without `--vlm-url` the endpoint comes from `settings.ai_vlm_url`, and the report records which
source produced it. `--candidate` and `--vlm-url` together are what make a bake-off's run rows
say what actually ran against what.

## Directory Structure

```
backend/evaluation/
├── AGENTS.md               # This file
├── __init__.py             # Legacy-harness exports (lazy, pandas-optional)
├── ab_experiment_runner.py # A/B statistical analysis (NEM-3731); imports scipy directly
├── assess_input.py         # AssessInput / EvalItem frozen schema (the vlm_assess contract shape)
├── combined_dataset.py     # Combined synthetic + external dataset loader
├── control_freeze.py       # P0.1: pre-switch Event -> EvalItem freeze with the recorded control
├── eval_store.py           # G0.4 SQLite ledger (items/runs/results) + the D10 privacy guard
├── harness.py              # Legacy PromptEvaluator harness + CLI (mock mode; --nemotron-url)
├── label_import.py         # P0.5: owner-labeled events + born-labeled generated items -> store
├── levels.py               # score -> risk level, the one level helper the harness may use
├── metrics.py              # Legacy prompt-evaluation metrics (numpy/pandas)
├── prompt_eval_dataset.py  # Synthetic scenario loader for the legacy harness
├── prompt_evaluator.py     # Legacy prediction-vs-expected evaluation
├── reports.py              # Legacy JSON/HTML report generation
├── s_metrics.py            # Wilson interval + S2/S3/S5/uncertain rates, in-repo math
└── vlm_replay.py           # The replay harness: frozen items -> served VLM -> EvalStore run
```

## Key Components

### vlm_replay.py

| Function          | Description                                                                 |
| ----------------- | --------------------------------------------------------------------------- |
| `run_replay`      | One run of the harness; names the candidate build and the measured endpoint |
| `replay_item`     | Sends one frozen item (its stored `specialist_outputs`, its `media_paths`)  |
| `client_factory`  | Builds the shipped `VlmClient` from the resolved endpoint                   |
| `compute_report`  | Aggregates the run's verdicts into the report dict                          |
| `save_vlm_report` | Writes the aggregate JSON next to the run id                                |
| `main`            | The CLI above                                                               |

Rev 6's rule is what the name means: **replay reads the items' stored `specialist_outputs` and
never re-runs a specialist** - the givens are the point of a replay. The module never imports
`vlm_specialists`, which `backend/tests/unit/evaluation/test_vlm_replay.py` asserts at the AST
level, and it feeds the item's own `media_paths` (<= 4) instead of key-frame selection, which
needs detection rows a frozen item does not have.

### s_metrics.py + levels.py

`s_metrics` computes S2 (benign scored at/above medium), S3 (incidents at/above their declared
floor), S5 refusals and the `uncertain` rate, each reported as rate + n + a 95 % Wilson interval
computed in-repo (`wilson_interval`), because scipy is transitive and the report must not rest on
it. The F14 bars (`S2_MAX_PCT = 5.0`, `S3_MIN_PCT = 90.0`) are printed beside the numbers and
**enforced by nothing** - a bar change is an owner decision.

`levels.py` is the single score -> level definition the harness may use. `test_levels.py` pins it
against the frontend's `RISK_THRESHOLDS` (`frontend/src/utils/risk.ts`) and against
`label_import._SEVERITY_FLOORS`, so the harness's S2 and the dashboard's gauge cannot drift apart
quietly.

### eval_store.py + label_import.py + control_freeze.py

`EvalStore` is a small SQLite ledger of immutable items, provenance-pinned runs and results; the
DB path is a required argument and production callers keep it outside the workspace (D10: the
privacy guard hard-errors on media paths that point into the repo or a capture root).
`label_import` turns owner-labeled events and born-labeled generated scenarios into items and
enforces the M0 size bar in code (`m0_size_report`). `control_freeze` freezes pre-switch events
with their recorded control verdict; its execution is ruled N/A while no pre-switch traffic
exists, but the tool is code-complete and tested so a returning production system can run it.

### harness.py (legacy)

`PromptEvaluator` runs two templates (`basic`, `model_zoo_enhanced`, from
`backend/services/prompts.py`) over scenarios and scores deviations. Its non-mock path POSTs to
`--nemotron-url`; no shipped service serves that endpoint, so a real-mode run cannot succeed
against this stack. The nightly `prompt-evaluation.yml` runs it `--mock`, which is green whether
or not the VLM works - it is not a signal about the shipped pipeline.

## Honest Limitations

- **A specialist change cannot be measured by this harness.** Replay feeds each item's stored
  `specialist_outputs`, and the exported tierb-v0 set declares no specialist context at all, so no
  currently runnable chain scores a specialist-prompt or specialist-leg change.
- **Nothing in production imports this package.** The only importers outside the tree are
  `synthbench/run/` and `synthbench/score/` (the repo's import rule allows exactly those) plus
  tests. That is why `ab_experiment_runner`'s top-level `from scipy import stats` is latent rather
  than fatal: scipy is transitive, not declared, and a `backend.evaluation` import chain that
  reaches it would fail at import. `s_metrics` deliberately keeps its own Wilson math for the
  same reason.
- **CI scores nothing.** `pyproject.toml` addopts exclude the gpu-marked tests, and the nightly
  that runs is the legacy harness in mock mode.

## Usage (legacy harness)

```bash
# Mock mode - no serving endpoint required
uv run python -m backend.evaluation.harness --mock --mock-count 50 \
    --output reports/prompt_evaluation.json --format json

# HTML report
uv run python -m backend.evaluation.harness --mock --output reports/report.html --format html
```

Programmatic entry points re-exported from `backend.evaluation` (`PromptEvaluator`,
`load_synthetic_eval_dataset`, `evaluate_prediction`, `calculate_metrics`, the report helpers)
all belong to this legacy chain; the replay chain's modules are imported by their full path.

## Design Decisions

1. **Lazy pandas imports**: the module imports without pandas installed; pandas arrives with the
   `nemo` extra (`uv sync --extra nemo`).
2. **One level definition**: harness code calls `levels.score_to_level` instead of spelling its
   own band table.
3. **Runs name themselves**: candidate id, git commit, engine and resolved endpoint are recorded
   by the run, so "the same replay per candidate" is a claim the data can check.

## Testing

```bash
uv run pytest backend/tests/unit/evaluation/ -v      # harness-side tests skip without pandas
uv run pytest backend/tests/unit/synthbench/ -v      # the export/replay/score contract
```

## Related

- `synthbench/AGENTS.md` - the corpus, the CLI, and the storage layout
- `docs/plans/2026-01-21-nemo-data-designer-integration-design.md` - the legacy scenario design
- `tools/nemo_data_designer/config.py` - its scenario config models
