# synthbench/export — Agent Guide

## Purpose

Writes corpus events in layouts other tools read. Synthbench P5a
(`docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` §2) adds the first: the
VSS eval store's import layout, which `synthbench replay` imports and replays.

## Files

| File     | What                                                                                                                                                                                                                  |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `vss.py` | the category map, the scene-timestamp rule, `expected_labels.json` (including the declared subjects and props as an ideal detector's `detections`), the attribution sidecar, writing a set once and reading sets back |

The command is `synthbench/commands/export.py` (`python -m synthbench export vss`).

## Rules

- Never import `backend` here (spec §7.1); a test pins `CATEGORY_LABEL` equal to the importer's
  `_CATEGORY_LABELS`.
- Exports go under `$SYNTHBENCH_ROOT/exports/`, never into the append-only corpus or the repo (the
  eval store refuses repo-resident media).
- A set is create-once: identical content is skipped, different content is an `ExportConflict`
  (exit 2). A new set is staged beside the export directory, never under it, because the importer
  reads every `*/*/expected_labels.json` there.
