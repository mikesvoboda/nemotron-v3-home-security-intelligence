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
  The renderer check fails closed: only `inactive` or `failed` counts as stopped.
- The client is the shipped `VlmClient`; only its settings and transport differ per model (plan
  ruling P5a-R2), and the prompt only by Cosmos's system message (the owner's decision). Its
  capture root is the export directory: `VlmClient` refuses any image outside
  `foscam_base_path`. The export is resolved before the import (the importer stores paths as
  joined from it), and a store holding stills outside the export is refused before the replay.
- A store whose held items differ from their sets in the export is refused (`check_current`):
  the importer skips an id the store holds, so an export rebuilt in place would replay old
  snapshots. The check imports the export into a scratch in-memory store and compares whole
  items. A set the importer refuses outright (`LabelImportError`) is `ImportRefused` (exit 2).
- `ModelField` keeps the request's extensions (the client's timeouts), merges a vLLM model's
  `request_extra` into each chat body and puts its `system_message` ahead of the shipped user
  message; a model's `read_timeout` replaces the client's `ai_vlm_read_timeout`. Only the vLLM
  models set any: `flagship` thinking off; `cosmos-reason2-8b` `max_tokens` 4096, 120 s and its
  model card's reasoning-format system message.
- Cosmos must be served with vLLM's `--reasoning-parser qwen3`: its reasoning then goes to the
  reasoning channel, and the reply's content holds only the verdict.
- Each replay gets a new eval run id. Its run directory is created before the first request;
  its `run.json`, written after, names the endpoint, build and commit, and the conditions it ran
  under as the requests carried them (`conditions`): enforcement probe, request extra,
  `max_tokens` (the extra's, else the shipped client's `_ASSESS_MAX_TOKENS`), the effective read
  timeout and the system message. `score` states them per model in the report.
