# synthbench/contract - Agent Guide

## Purpose

The event contract (spec §2): pydantic models for what an event is meant to show (`spec.json`),
what it does show (`truth.json`) and how it was made (`provenance.json`), plus the corpus records
and the append-only store.

## Files

| File            | What                                                                                                                                                    |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `common.py`     | `ContractModel` base (frozen, no extra keys, JSON uses aliases such as `class`), labels, validated `Box`, `HHMM`, `RiskBand`, `Sha256`, `SLUG`          |
| `spec.py`       | `Spec`, `Cell`, `Subject`, `Prop`; the sampler writes facts, P3 freezes `prompt` + `camera_suffix` together                                             |
| `truth.py`      | `Truth` and its parts, exactly parent spec §2.3's shape                                                                                                 |
| `provenance.py` | `Provenance` (schema 2), `Attempt` (render failures, overlay time), `Triage`, `attempt_seed`, `render_name`/`still_name`, `MAX_ATTEMPTS = 3`            |
| `corpus.py`     | `CorpusManifest` (corpus.json), `BatchRecord` (batch.json), `IndexRow` (index.jsonl), `TIER_B_RENDER_SIZE`, `PromptRow`, `TriageRow` (the agent's rows) |
| `clip.py`       | the clip side of all of it: `ClipSpec`, `ClipProvenance`, `RoundRecord`, `ClipIndexRow`, the agent's motion/triage rows                                 |
| `clip_audit.py` | the blind clip audit's three row kinds: the draw (`ClipAuditDrawRow`), the answers, the pre-screen flags (ISS-038)                                      |
| `store.py`      | `CorpusStore`: paths under `$SYNTHBENCH_ROOT/corpus/<version>/`, `write_new` (atomic, never replaces), the index                                        |

## Rules

- The corpus is append-only (agent-driven design §2): no command deletes, moves or overwrites
  an image or a clip. Files are created only through `CorpusStore.write_new` /
  `write_new_bytes`, which raise `FileExistsError` rather than replace; JSON files and the
  batch views change only through `replace_text` / `replace_json` (atomic); `index.jsonl`
  grows only through `append_index`. Every write stays inside the version directory.
- `ContractModel.updated(...)` is the only way to change a model: `model_copy(update=...)`
  skips the validators.
- `CorpusStore.event_dir` accepts only `A-`/`B-` ids of ASCII letters, digits, `_` and `-`, so
  no event path can leave the version directory.
- Truth stores facts, never expected model outputs (spec §2.2).
- A new field in a file model means a `schema_version` bump and a migration note in the spec.
- No `backend` imports (test: `test_import_rule.py`).
