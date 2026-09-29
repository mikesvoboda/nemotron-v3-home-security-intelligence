# synthbench — Agent Guide

## Purpose

Synthetic benchmark generation: spec `docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md`.
Tier B generation is driven by a flagship agent beside the flagship: `docs/superpowers/specs/2026-09-28-synthbench-agent-driven-generation-design.md` (spec rev 3).
Phase plans live in `docs/superpowers/plans/*-synthbench-*.md`.

## Layout

| Path                                          | What                                                                                    |
| --------------------------------------------- | --------------------------------------------------------------------------------------- |
| `generate/weights.py` + `generate/manifests/` | pinned, sha256-verified weights; ComfyUI symlink farm (`/export/models/comfyui`)        |
| `generate/window.py`                          | GPU window: stops the flagship vLLM, ALWAYS restores it                                 |
| `generate/podman.py`                          | the dedicated podman store (`SYNTHBENCH_PODMAN_ROOT`): argv prefix and `TMPDIR`         |
| `generate/comfy/`                             | ComfyUI container (podman), HTTP client, graph validator, per-model graph builders      |
| `contract/`                                   | event contract: spec/truth/provenance models, corpus records, append-only `CorpusStore` |
| `taxonomy/`                                   | committed Tier B taxonomy YAML, its coherence rules, the seeded quota sampler           |
| `cli.py` + `__main__.py`                      | `python -m synthbench <command>`; exit 0 done, 1 error, 2 stop and ask the owner        |
| `spikes/p1_bakeoff/`                          | throwaway P1 bake-off harness (not a pattern to copy)                                   |

## Rules

- Only `synthbench/score/` and `synthbench/run/` may import `backend` (spec §7.1; test: `backend/tests/unit/synthbench/test_import_rule.py`).
- Tests live in `backend/tests/unit/synthbench/` (CI runs only `backend/tests/unit/`); no GPU in tests.
- Storage: weights in `HF_HOME=/export/models`, outputs in `SYNTHBENCH_ROOT=/synthbench`; never the root fs.
- Only `uv run python -m synthbench.generate.window run -- ...` may stop the flagship; never `docker compose up` on the dgx-inference stack.
- Our containers are podman, in a dedicated store under `SYNTHBENCH_PODMAN_ROOT` (default `/export/models/containers`), never the default one. Code builds podman argv from `podman_argv()`; shell commands use `$(uv run python -m synthbench.generate.podman) ...`. The flagship is rootful docker.
- The corpus lives at `$SYNTHBENCH_ROOT/corpus` (the ZFS dataset `primary/export/synthbench/corpus`) and is append-only; tests write only under `tmp_path`.
