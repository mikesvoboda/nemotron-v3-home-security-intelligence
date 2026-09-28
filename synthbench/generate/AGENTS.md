# synthbench/generate — Agent Guide

## Purpose

The durable generation stack (spec §3) that P3 builds on: pinned weights, the GPU window and the ComfyUI renderer. TDD applies here.

## Key Files

| Path                      | What                                                                                    |
| ------------------------- | --------------------------------------------------------------------------------------- |
| `weights.py`              | manifest loading, sha256 fetch, symlink farm, `extra_model_paths` text; CLI `sync`      |
| `manifests/p1-slate.json` | the pinned P1 weights (37 rows, 34 unique files); committed, never edited by hand       |
| `window.py`               | GPU window: stops the flagship vLLM, ALWAYS restores it; CLI `run`, `restore`, `status` |
| `podman.py`               | the dedicated podman store: `podman_argv()` prefix, `podman_env()` `TMPDIR`; CLI prefix |
| `comfy/`                  | the ComfyUI renderer (see `comfy/AGENTS.md`)                                            |

## Rules

- Never import `backend` (spec §7.1; test: `backend/tests/unit/synthbench/test_import_rule.py`).
- Tests live in `backend/tests/unit/synthbench/`; they never touch the GPU or the flagship.
- Only `uv run python -m synthbench.generate.window run -- ...` may stop the flagship.
- Every podman call goes through `podman_argv()` (shell: `$(uv run python -m synthbench.generate.podman) ...`); builds and pulls also pass `env=podman_env()`.
