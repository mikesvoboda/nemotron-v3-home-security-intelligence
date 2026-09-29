# synthbench/audit — Agent Guide

## Purpose

The owner's audit of exported stills (synthbench P5a,
`docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` §4). Its answers put an
error bar on the declared truth P5a scores against, and later measure a judge model.

## Files

| File        | What                                                                                                 |
| ----------- | ---------------------------------------------------------------------------------------------------- |
| `sample.py` | the stratified, seeded 60-still sample (`STRATA`, `allocate`, `sample`) and each still's `questions` |
| `page.py`   | `AuditApp.handle(method, path, body)`, the whole page, and `serve()`, its loopback-only server       |

The command is `synthbench/commands/audit.py` (`python -m synthbench audit`).

## Rules

- `handle` is pure and tested without a socket; `serve` binds `127.0.0.1` only.
- Stills are served by sample index, never by a path from the request.
- The answer log is append-only; the latest answer per (event, question) wins.
