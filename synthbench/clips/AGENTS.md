# synthbench/clips — Agent Guide

## Purpose

Clip rounds (`docs/superpowers/specs/2026-09-30-synthbench-h3-clips-design.md`): MiniMax-H3
turbo clips of ready Tier B stills, kept for a future video VLM. The commands are in
`synthbench/commands/clip*.py`; this package holds their logic.

## Files

| File          | What                                                                      |
| ------------- | ------------------------------------------------------------------------- |
| `settings.py` | the clip settings a pilot gate approves; the H3 turbo weights' hashes     |
| `gate.py`     | `status/clip-gate.json`: the model, the 80% bar, what a new round may be  |
| `sample.py`   | the draw: the even split across groups, the seeded per-lighting sample    |
| `rules.py`    | the motion rules: the still rules 1-4 and rule 5, no camera moves or cuts |

## Rules

- No `backend` imports (the import rule).
- Only the owner's `audit --clips` writes the gate; the agent's sandbox mounts `status/`
  read-only.
- A clip event never modifies its source still (clips design C4).
