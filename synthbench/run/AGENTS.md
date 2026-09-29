# synthbench/run — Agent Guide

## Purpose

Replays served VLMs over the exported items (synthbench P5a,
`docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` §3). With
`synthbench/score/`, the only synthbench package that may import `backend` (spec §7.1;
`backend/tests/unit/synthbench/test_import_rule.py`).

## Files

| File        | What                                                                                                                                 |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `models.py` | `Model` and `MODELS`: each replayable model's transport, served identity and default endpoint; imports nothing from `backend`        |
| `replay.py` | the pre-run checks, the import, the `VlmClient` factory (capture root: the export; `ModelField` for vLLM) and `execute` (`run.json`) |

The command is `synthbench/commands/replay.py` (`python -m synthbench replay`); it imports
`replay.py` inside `run()`.

## Rules

- `models.py` stays backend-free: `cli.py` imports every command at startup, and `replay`'s
  command imports `models.py` (a test pins this).
- Replay never starts, stops or reconfigures a model server, and refuses while the renderer runs.
- The client is the shipped `VlmClient`; only its settings and transport differ per model (plan
  ruling P5a-R2). Its capture root is the export directory: `VlmClient` refuses any image outside
  `foscam_base_path`. The export is resolved before the import (the importer stores paths as
  joined from it), and a store holding stills outside the export is refused before the replay.
- `ModelField` keeps the request's extensions (the client's timeouts) and merges a vLLM model's
  `request_extra` into each chat body; a model's `read_timeout` replaces the client's
  `ai_vlm_read_timeout`. Only the vLLM models set either: `flagship` thinking off;
  `cosmos-reason2-8b` `max_tokens` 4096 and 120 s.
- Each replay gets a new eval run id; its `run.json` names the endpoint, build, request extra,
  read timeout and commit.
