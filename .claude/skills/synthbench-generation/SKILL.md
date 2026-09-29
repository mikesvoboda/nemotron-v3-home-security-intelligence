---
name: synthbench-generation
description: Use when driving or planning synthbench Tier B generation (sample, check, render, camera, triage, report), when asked about the corpus's spread or coverage (scenario mix, lighting, weather, property, camera, artifacts), when steering future batches, or when locating a spec, still, verdict or report under /synthbench/corpus.
---

# Synthbench generation

## Overview

The CLI (`uv run python -m synthbench <command>`) is the interface, and the corpus files are the
record. Everything below is verified against the code, so answer spread, lever and path questions
from here and from `coverage.py`. Do not re-derive them from `sampler.py` or `check.py`.

## Every session

1. `uv run python -m synthbench doctor`. On exit 2, send the owner the `FAIL` lines and wait.
2. Read `docs/synthbench/agent-handoff.md` (the loop, prompt rules, triage limits) and
   `docs/synthbench/prompt-notes.md` (what worked in earlier batches, and the owner's notes).
   Add to it at the end of every batch; the owner commits it.

## What you can steer

| Want                                         | Lever                                                                                                                                                                                                                           |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| a different draw                             | a new batch name (it seeds the batch), or `sample --seed`                                                                                                                                                                       |
| more or fewer events                         | `sample --n` (1-500)                                                                                                                                                                                                            |
| more of chosen scenarios                     | `sample --only id,id`. It is a lasting trade: later batches without `--only` skip those scenarios until the rest catch up. After a 100-event `--only` batch on five weight-1 scenarios, that takes about 1,000 events.          |
| more night, fog, indoor or one property type | Only indirectly: `--only` scenarios whose allowed zones and lighting skew that way. Measure first with `coverage.py --expected N --only ...`. Changing a weight is a taxonomy edit: a new corpus version, and the owner's call. |
| change a sampled fact                        | Impossible. `check` re-derives every spec from `batch.json` and exits 2 on any drift.                                                                                                                                           |
| reword a frozen prompt                       | Impossible. A reroll changes only the seed; a different prompt is a new event.                                                                                                                                                  |

## How the sampler draws

- **Scenario** is the only balanced axis. The quota method allocates over scenario `weight`s, so
  every scenario stays within one event of its weighted share across batches drawn without
  `--only`. Prior counts are every event in the version, failed ones included.
- Given the scenario:
  - **(property, zone, camera)** is uniform over its compatible cells: the zone is in the
    scenario's, the property's and the camera's zone lists.
  - **Lighting** and **weather** are weighted draws among the values the scenario allows.
    Indoor cameras never get outdoor-only lighting, and their weather is always clear.
  - **Each artifact** is an independent draw with its own probability, where lighting, weather
    and outdoor rules allow it.
  - **`scene_time`** is uniform within the lighting's hours.
  - **Clothing** is a color plus a garment.
- So property, camera, lighting and weather shares are consequences of the scenario mix and of
  zone compatibility, not targets. The tilt is structural: eave-wide cameras and front porches
  dominate, and the commercial properties and some zones are rare or unreachable.
- A few hundred events give marginals, not crossings. Most scenario × property × lighting ×
  weather combinations appear once, so report per-axis shares, never a crossed cell rate.

## Measure, don't estimate

```bash
uv run python .claude/skills/synthbench-generation/coverage.py                 # everything so far
uv run python .claude/skills/synthbench-generation/coverage.py --batch batch-1
uv run python .claude/skills/synthbench-generation/coverage.py --expected 400  # the next 400, simulated
uv run python .claude/skills/synthbench-generation/coverage.py --expected 100 --only a,b
```

It prints the scenario balance against the weighted shares, the realized spread on every axis,
and the expected spread of the next N events, drawn with the real sampler. It is read-only and
takes under a second.

## Reference

`reference.md` in this directory has the corpus layout and file fields, the taxonomy model's
names, and pointers into the specs. Tier B's purpose is breadth: detection, threat, vehicle type,
pets, pose and the VLM verdict, across many environments. See the parent spec
`docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md` §1.1 and, for the
labels and the false-alarm bucket, §1.3.

## Common mistakes

| Mistake                                                | Instead                                                                                                                                                         |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tax.property_types` (AttributeError)                  | `tax.properties`. The spec field is `cell.property_type`.                                                                                                       |
| Treating lighting and weather as uniform               | They are weighted. Run `coverage.py` instead of computing shares.                                                                                               |
| Ignoring `cell.artifacts` in a prompt                  | Describe each declared artifact (headlight glare, droplets on the lens, motion blur) in scene terms.                                                            |
| One giant batch                                        | Prompts freeze before any image exists. Batches of 50-100 let `prompt-notes.md` lessons reach the next batch.                                                   |
| Editing corpus files, or running `check` for the owner | Change the corpus only through commands. The owner's host `check` is the owner's to run.                                                                        |
| Implying coverage the corpus lacks                     | Say what a batch cannot measure. `tierb-v0` has no vehicle attribute, so vehicle type is unscorable, and its commercial properties are a few percent of events. |
| Recording an owner decision you were not given         | Write down only what the owner said. Mark your own proposals as proposals.                                                                                      |
