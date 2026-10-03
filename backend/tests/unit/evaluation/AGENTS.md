# Unit Tests for Backend Evaluation

## Purpose

Unit tests for `backend/evaluation/`, the measurement code for the VLM verdict path (eval store,
importers, S2/S3/S5 metrics, level banding, the replay). They run without a GPU, a served model or
pandas; the replay tests use a fake transport.

## Key Files

| File                     | Tests For                                                              |
| ------------------------ | ---------------------------------------------------------------------- |
| `test_build_gen2.py`     | The generation-2 corpus build (items that carry specialist outputs)    |
| `test_control_freeze.py` | Freezing events into the store, the sequencing rule, the D10 guard     |
| `test_eval_store.py`     | Items, runs, results, immutability, the synthetic label-set loader     |
| `test_label_import.py`   | Owner-labeled events and generated sets -> items, the M0 size bar      |
| `test_levels.py`         | Score -> level banding, pinned against the frontend risk thresholds    |
| `test_s_metrics.py`      | S2 / S3 / S5, Wilson intervals, the zero-floor double report           |
| `test_vlm_replay.py`     | The replay through the shipped `VlmClient`, run and report shape       |

## Running

```bash
uv run pytest backend/tests/unit/evaluation/ -q
```

## Related Documentation

- `/backend/evaluation/AGENTS.md` - the module under test
- `/backend/tests/unit/synthbench/` - the synthbench commands that drive these modules
