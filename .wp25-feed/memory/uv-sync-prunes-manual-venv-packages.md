---
name: uv-sync-prunes-manual-venv-packages
description: 'uv sync removes manually-installed packages from .venv (pre-commit among them), silently breaking git hooks'
metadata:
  node_type: memory
  type: project
  originSessionId: a4bfff8c-fd38-45e3-bf4d-045ba7d1b435
  modified: 2026-09-15T20:10:04.356Z
---

In this repo, `uv sync --extra dev` (or any `uv sync`) **prunes every package not declared in the lockfile** from `/agents/agent-nemo2/workspace/.venv` — including tools that were installed manually and are referenced by the venv path in `.git/hooks/pre-commit`. `pre-commit` is one of them (it lives in neither `pyproject.toml` nor `uv.lock`; the hook script does `exec "$INSTALL_PYTHON" -mpre_commit`). After any `uv sync`, `git commit` fails with `No module named pre_commit` until `uv pip install pre-commit` is re-run.

**Why:** hit during the Python dependency refresh (#6542, 2026-09-15) — the refreshed sync pruned the whole old venv state and the first commit attempt died in the hook.

**How to apply:** after any `uv sync` in this workspace, re-run `uv pip install pre-commit` before committing. Do not "fix" the hook by pointing INSTALL_PYTHON elsewhere or bypassing hooks (standing rule: never bypass). Related: [[ci-merge-gate-and-retrigger-quirks]]
