# Unit Tests - synthbench - Agent Guide

## Purpose

Unit tests for `synthbench/generate/` (the durable generation stack: pinned weights, the GPU window, the ComfyUI renderer), `synthbench/contract/`, `synthbench/taxonomy/` and the CLI. They live here rather than under `synthbench/` because CI runs only `backend/tests/unit/` (spec §7.1, deviation 1). The P1 spike's tests are in `spikes/`.

## Directory Structure

| Test file                | Under test                                                                                |
| ------------------------ | ----------------------------------------------------------------------------------------- |
| `test_weights.py`        | `synthbench/generate/weights.py`: manifest, sha256 fetch, symlink farm, the HF_HOME guard |
| `test_window.py`         | `synthbench/generate/window.py`: the GPU window always restores the flagship              |
| `test_podman.py`         | `synthbench/generate/podman.py`: the dedicated podman store                               |
| `test_serve.py`          | `synthbench/generate/comfy/serve.py`: podman arguments, readiness, the baked farm path    |
| `test_comfy_client.py`   | `synthbench/generate/comfy/client.py` against a fake ComfyUI (`httpx.MockTransport`)      |
| `test_validate.py`       | `synthbench/generate/comfy/validate.py`: the offline graph validator                      |
| `test_graphs.py`         | `synthbench/generate/comfy/graphs.py`: every builder against the captured `/object_info`  |
| `test_snapshot.py`       | `synthbench/generate/comfy/snapshot.py`                                                   |
| `test_smoke.py`          | `synthbench/generate/comfy/smoke.py`                                                      |
| `test_import_rule.py`    | spec §7.1: only `synthbench/score/` and `synthbench/run/` may import `backend`            |
| `test_contract.py`       | `synthbench/contract/` models: §2.3 round-trip, validation, `class` alias                 |
| `test_contract_store.py` | `synthbench/contract/store.py`: layout, atomic create-never-replace, index                |
| `test_taxonomy.py`       | `synthbench/taxonomy/model.py` + the committed YAML: coherence rules                      |
| `test_sampler.py`        | `synthbench/taxonomy/sampler.py`: determinism, quota coverage, legal cells, midnight wrap |
| `test_cli_sample.py`     | `python -m synthbench sample`: writes, reruns, refusals, exit codes                       |

## Running Tests

```bash
uv run pytest backend/tests/unit/synthbench/ -n0 -q
uv run pytest backend/tests/unit/synthbench/ -n auto -q -p randomly   # as CI runs them
```

## Patterns and Gotchas

- No GPU, docker, podman or network: every subprocess and HTTP call goes through an injected fake (`run=`, `transport=`, `runtime=`). Live checks are CLI steps in the plan, never `@pytest.mark.gpu` (the CI GPU runner has no ComfyUI).
- pytest-timeout is 5 s, and the suite runs under xdist and `-p randomly`: never sleep for real; pass a fake `sleep` and `clock`.
- `conftest.py` imports the backend modules that the inherited autouse fixtures import lazily (`backend.core.config`, `backend.services.severity`). pytest-timeout also times setup and teardown, so otherwise the first test on each worker paid that ~2.3 s import inside its 5 s budget, and a busy host under `-n auto` interrupted it halfway. Keep it in step with those fixtures.
- Signal tests use `test_window.py`'s `trapped_signals` fixture. A signal the window fails to defer then fails the test instead of killing the worker, and no handler leaks.
- `gpu_window()` stops real podman containers by default: tests pass a fake `before_restore` (`test_window.py`'s `_window` helper does).

## Related

- `synthbench/AGENTS.md`, `synthbench/generate/AGENTS.md`, `synthbench/contract/AGENTS.md` and `synthbench/taxonomy/AGENTS.md`: the code under test
- `spikes/AGENTS.md`: the P1 spike's tests
