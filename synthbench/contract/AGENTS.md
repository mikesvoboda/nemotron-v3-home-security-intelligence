# synthbench/contract - Agent Guide

## Purpose

The event contract (spec §2): pydantic models for what an event is meant to show (`spec.json`),
what it does show (`truth.json`) and how it was made (`provenance.json`), plus the corpus records
and the append-only store.

## Files

| File            | What                                                                                                                                           |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `common.py`     | `ContractModel` base (frozen, no extra keys, JSON uses aliases such as `class`), labels, validated `Box`, `HHMM`, `RiskBand`, `Sha256`, `SLUG` |
| `spec.py`       | `Spec`, `Cell`, `Subject`, `Prop`; the sampler writes facts, P3 freezes `prompt` + `camera_suffix` together                                    |
| `truth.py`      | `Truth` and its parts, exactly parent spec §2.3's shape                                                                                        |
| `provenance.py` | `Provenance`, `Attempt`, `Triage` (verdict plus a `TriageReason`, one of the 7 reroll reasons), `MAX_ATTEMPTS = 3`                             |
| `corpus.py`     | `CorpusManifest` (corpus.json), `BatchRecord` (batch.json), `IndexRow` (index.jsonl), `TIER_B_RENDER_SIZE`                                     |
| `store.py`      | `CorpusStore`: paths under `$SYNTHBENCH_ROOT/corpus/<version>/`, `write_new` (atomic, never replaces), the index                               |

## Rules

- The corpus is append-only (agent-driven design §2): no command deletes, moves or overwrites
  an image or a clip. P2 creates files only through `CorpusStore.write_new`, which raises
  `FileExistsError` rather than replace, and appends rows to `index.jsonl` only through
  `CorpusStore.append_index`. The in-place JSON updates the design allows (a prompt
  frozen into `spec.json`, attempts added to `provenance.json`) arrive with P3 and go through
  the store too.
- `CorpusStore.event_dir` accepts only `A-`/`B-` ids of ASCII letters, digits, `_` and `-`, so
  no event path can leave the version directory.
- Truth stores facts, never expected model outputs (spec §2.2).
- A new field in a file model means a `schema_version` bump and a migration note in the spec.
- No `backend` imports (test: `test_import_rule.py`).
