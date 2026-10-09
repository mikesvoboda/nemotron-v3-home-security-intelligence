# Unit Tests - synthbench spikes - Agent Guide

## Purpose

Tests for the pure logic of the P1 bake-off spike (`synthbench/spikes/p1_bakeoff/`). `measure.py`'s `RealTools` (the GPU models) and the live runner are exercised in plan Task 8, not here; the clip frame reader (`clip_frames`) is tested on a tiny synthetic mp4 with an audio track.

## Directory Structure

| Test file            | Under test (`synthbench/spikes/p1_bakeoff/`)                                                          |
| -------------------- | ----------------------------------------------------------------------------------------------------- |
| `test_p1_plan.py`    | `plan.py`, `cases.py`: job counts, stage-major order, keyframes, resume (`pending`)                   |
| `test_p1_run.py`     | `run.py`: records, VRAM settle and sampling, the transport and timeout breakers, `main`'s early exits |
| `test_p1_graphs.py`  | all 344 bake-off graphs, built through the runner, validate against the committed snapshot            |
| `test_p1_measure.py` | `measure.py`: plate scoring, refusal detection, the measurement size, dispatch, the clip frame reader |
| `test_p1_report.py`  | `report.py`: aggregation, refusals, pick rules, the markdown; `sheet.py`: the contact sheet           |
| `test_p1_judge.py`   | `judge.py`: the non-leading request, its fallbacks, `derive` and prop matching, the resumable CLI     |
| `test_p1_py312.py`   | the files that run in the renderer image stay Python 3.12-parseable                                   |

## Running Tests

```bash
uv run pytest backend/tests/unit/synthbench/spikes/ -n0 -q
```

## Patterns and Gotchas

- `test_p1_run.py`'s autouse `instant_settle` fixture replaces `run.settle_vram`, which really sleeps; settle's own tests drive it with a fake clock.
- `main()` tests use the `no_comfyui` fixture: starting ComfyUI fails the test, and the SIGTERM handler is put back.
- `measure.py` and `cases.py` run on the image's Python 3.12: keep them 3.12-parseable (`test_p1_py312.py` checks).
- `test_p1_judge.py` fakes the flagship with `httpx.MockTransport` (`FakeFlagship`) and passes it to `judge.main(..., transport=)`: never call the real flagship. Its clips are tiny mp4s written with PyAV in `tmp_path`.

## Related

- `synthbench/AGENTS.md`: the lane guide, whose spikes section carries the bake-off's rules (W3.1 folded the per-package guides into it)
- `../AGENTS.md`: the `synthbench/generate` tests
