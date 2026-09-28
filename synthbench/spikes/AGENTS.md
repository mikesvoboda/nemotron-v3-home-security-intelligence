# synthbench/spikes — Agent Guide

## Purpose

Throwaway harnesses, each answering one phase question (spec `docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md`). They are not patterns to copy: durable code lives in `synthbench/generate/`.

## Key Files

| Path          | What                                                                                                     |
| ------------- | -------------------------------------------------------------------------------------------------------- |
| `p1_bakeoff/` | the P1 model bake-off: cases, runner, measurement, contact sheet and report (see `p1_bakeoff/AGENTS.md`) |

## Rules

- A spike unit-tests only its pure logic; the tests live in `backend/tests/unit/synthbench/spikes/`.
- Media and run state go under `$SYNTHBENCH_ROOT` (default `/export/synthbench`), never into the repo or onto the root filesystem.
- A spike may import `synthbench.generate`; `synthbench.generate` never imports a spike (or `backend`).
- A spike's GPU work runs only inside a GPU window (`uv run python -m synthbench.generate.window run -- ...`), which the controller opens.
