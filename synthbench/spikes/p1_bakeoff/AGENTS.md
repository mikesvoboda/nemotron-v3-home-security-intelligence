# synthbench/spikes/p1_bakeoff — Agent Guide

## Purpose

The throwaway P1 bake-off harness (spec §3.7; plan `docs/superpowers/plans/2026-09-27-synthbench-p1-bakeoff.md`). Not a pattern to copy: durable code lives in `synthbench/generate/`.

## Key Files

| File         | What                                                                                 |
| ------------ | ------------------------------------------------------------------------------------ |
| `cases.py`   | the hard prompts, identity shots, clip cases, seeds and sizes                        |
| `plan.py`    | expands the cases into stage-major jobs (each model's jobs are contiguous)           |
| `run.py`     | resumable runner, run inside a GPU window; writes `records.jsonl` and `groups.jsonl` |
| `measure.py` | OWLv2, facenet and EasyOCR measurement, and the `refused` flag; renderer image only  |
| `judge.py`   | the flagship as VLM judge (host, flagship up): `judge.jsonl`, report evidence only   |
| `sheet.py`   | the static HTML contact sheet the owner rates                                        |
| `report.py`  | aggregates records, measures and ratings into the P1 report under `docs/benchmarks/` |

## Rules

- Outputs go under `$SYNTHBENCH_ROOT/p1`; every CLI here takes `--root`. Media never enters the repo.
- `measure.py` and `cases.py` run on the renderer image's Python 3.12: keep them 3.12-parseable.
- Tests live in `backend/tests/unit/synthbench/spikes/` and cover only the pure logic.
- A **refusal** is an image whose OCR text is the model's safety card ("Image blocked by safety filter"; Ideogram 4 paints it as a gray card or over a partial scene). `measure.py` reads every image once with EasyOCR and writes `refused` (from the text, `is_refusal_text`) and `card_like` (a diagnostic: grayscale std under `CARD_GRAY_STD_MAX` at the measure size); clips are never refused. `report.py` counts a refusal as not good in the threat good rates (rated or not), leaves it out of OWL hit, identity drift and the judge columns, and lists each model's cases refused at least half the time; `sheet.py` marks the cell REFUSED and keeps its radios. We never work around a model's safety behaviour.
- `judge.py` runs on the host (`uv run python -m synthbench.spikes.p1_bakeoff.judge`) only while the flagship is up, never in a GPU window. It is non-leading: the flagship sees only pixels and one fixed instruction, never the prompt, case id or path. Its model is the same family as the pipeline's VLM stage (Qwen3VL-4B), so `propose_picks` never reads it: the report shows it as evidence plus a judge-vs-owner calibration.
