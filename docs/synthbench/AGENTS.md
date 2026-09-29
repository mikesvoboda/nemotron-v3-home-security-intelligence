# docs/synthbench - Agent Guide

## Purpose

Documents for agent-driven Tier B generation beside the flagship (agent-driven design §8,
`docs/superpowers/specs/2026-09-28-synthbench-agent-driven-generation-design.md`). The code is
in `synthbench/`.

## Files

| File                   | Reader             | What                                                                                     |
| ---------------------- | ------------------ | ---------------------------------------------------------------------------------------- |
| `agent-handoff.md`     | the flagship agent | start here if you drive generation: the loop, prompt rules, triage, limits, stop-and-ask |
| `command-reference.md` | the agent          | each command's options, files and exit codes                                             |
| `operator-runbook.md`  | the owner          | host units, the renderer, snapshot holds, the agent's sandbox, reviewing a batch         |

## Rules

- `command-reference.md` must list exactly each command's options: the options table under each command's heading is checked against argparse by `backend/tests/unit/synthbench/test_command_reference.py`.
  Change the document with the parser.
- `agent-handoff.md` names only the six agent commands (same test). It never describes GPU
  windows or host units (design G11); those belong in `operator-runbook.md`.
