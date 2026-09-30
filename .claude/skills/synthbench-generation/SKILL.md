---
name: synthbench-generation
description: Use when driving or planning synthbench Tier B generation (sample, check, render, camera, triage, report) or a clip round (animating ready stills with MiniMax-H3: clip sample, check, render, triage, report), when asked about the corpus's spread or coverage (scenario mix, lighting, weather, property, camera, artifacts), when steering future batches, or when locating a spec, still, clip, strip, verdict or report under /synthbench/corpus.
---

# Synthbench generation

## Overview

The CLI (`uv run python -m synthbench <command>`) is the interface, and the corpus files are the
record. Everything below is verified against the code, so answer spread, lever and path questions
from here and from `corpus coverage`. Do not re-derive them from `sampler.py` or `check.py`.

## Every session

1. `uv run python -m synthbench doctor`. On exit 2, send the owner the `FAIL` lines and wait.
2. Read `docs/synthbench/agent-handoff.md` (the loop, prompt rules, triage limits) and the
   notes for the work in hand: `docs/synthbench/flux-prompt-notes.md` before a stills batch,
   `docs/synthbench/h3-prompt-notes.md` before a clip round (what worked before, and the
   owner's notes). Add to that file at the end of every batch or round; the owner commits it.

## What you can steer

| Want                                         | Lever                                                                                                                                                                                                                        |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| a different draw                             | a new batch name (it seeds the batch), or `sample --seed`                                                                                                                                                                    |
| more or fewer events                         | `sample --n` (1-500)                                                                                                                                                                                                         |
| more of chosen scenarios                     | `sample --only id,id`. It is a lasting trade: later batches without `--only` skip those scenarios until the rest catch up. After a 100-event `--only` batch on five weight-1 scenarios, that takes about 1,000 events.       |
| more night, fog, indoor or one property type | Only indirectly: `--only` scenarios whose allowed zones and lighting skew that way. Measure first with `corpus coverage --n N --only ...`. Changing a weight is a taxonomy edit: a new corpus version, and the owner's call. |
| change a sampled fact                        | Impossible. `check` re-derives every spec from `batch.json` and exits 2 on any drift.                                                                                                                                        |
| reword a frozen prompt                       | Impossible. A reroll changes only the seed; a different prompt is a new event.                                                                                                                                               |

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
uv run python -m synthbench corpus coverage                    # the corpus, and the next 400
uv run python -m synthbench corpus coverage --n 100 --only a,b # a targeted batch, before you sample
```

For each axis it prints every value's long-run chance per event (`p`), the events still needed
for 30 of the value (`to 30`, counting every drawn event that has not failed, so in-flight ones
count), what the corpus holds (`expect`, `drawn`, `ready`) and what the next n events add. The
next n come from the same allocation `sample` makes. Its thin-values list counts, by label, every
scenario that can show each rare value; none benign means no false-alarm rate for that value. Read
it before you write what a batch cannot measure. It is read-only and takes about a second.
`docs/synthbench/command-reference.md` explains every column.

## Clip rounds

A clip animates one ready still for ~10 s with MiniMax-H3 turbo. Clips are kept for a future
video model; nothing scores them yet. Run them only when the owner asks. The loop, the motion
rules and the reroll reasons are in `docs/synthbench/agent-handoff.md`, "Clip rounds".

- **Pacing.** A round can take every ready still (`--n` up to 500; there is no pilot). Each
  `clip render` call renders one clip, about 5.5 minutes, so a full round is about two days of
  calls. Exit 2 from any clip command means stop and ask: no loops, no new round to get around
  it, no edits.
- **You do not choose stills.** `clip sample` draws ready stills without a clip, evenly across
  groups. The round name (it seeds the draw) and `--n` are the only levers.
- **A motion continues the still.**
  - Frame 0 is the still, so open it first.
  - Say only what moves next: no re-described scene, light or weather.
  - Name every subject and prop with a taxonomy term, and keep all of them in frame. Nobody
    walks off, nothing is pulled out or put away, and nothing new appears (no passing car).
  - Stay in character for the label.
  - The camera never moves and the shot never cuts (rule 5).
- **Triage the strip mechanically.** Six frames per clip. Reroll only for `camera_moved`,
  `subject_lost`, `subject_duplicated`, `prop_lost`, `morphing` or `scene_cut`. A clip has 3
  seeds.
- **The first `clip render` of a round may render nothing:** the switch to H3 and its warm-up
  can take the whole call. Run it again.

## Reference

`reference.md` in this directory has the corpus layout and file fields, the taxonomy model's
names, and pointers into the specs. Tier B's purpose is breadth: detection, threat, vehicle type,
pets, pose and the VLM verdict, across many environments. See the parent spec
`docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md` §1.1 and, for the
labels and the false-alarm bucket, §1.3.

## Common mistakes

| Mistake                                                                  | Instead                                                                                                                                                         |
| ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tax.property_types` (AttributeError)                                    | `tax.properties`. The spec field is `cell.property_type`.                                                                                                       |
| Treating lighting and weather as uniform                                 | They are weighted. Run `corpus coverage` instead of computing shares.                                                                                           |
| Ignoring `cell.artifacts` in a prompt                                    | Describe each declared artifact (headlight glare, droplets on the lens, motion blur) in scene terms.                                                            |
| One giant batch                                                          | Prompts freeze before any image exists. Batches of 50-100 let `flux-prompt-notes.md` lessons reach the next batch.                                              |
| Editing corpus files, or running `check` for the owner                   | Change the corpus only through commands. The owner's host `check` is the owner's to run.                                                                        |
| Implying coverage the corpus lacks                                       | Say what a batch cannot measure. `tierb-v0` has no vehicle attribute, so vehicle type is unscorable, and its commercial properties are a few percent of events. |
| Recording an owner decision you were not given                           | Write down only what the owner said. Mark your own proposals as proposals.                                                                                      |
| Building a tool or drafting a taxonomy you need                          | Describe what you need and send it to the owner. Changes under `synthbench/` and taxonomy drafts are the owner's side's work, even when a fix looks small.      |
| Retrying `clip render` in a loop after it exits 2                        | Exit 2 is the owner's. Send the message and wait.                                                                                                               |
| Camera or edit words in a motion ("pans", "zooms in", "cut to", "later") | Describe only what the people and objects do; `clip check` adds the fixed camera.                                                                               |
| Rerolling a clip because its action is dull or not what you wanted       | Only the six mechanical reasons. Nothing audits clips yet; the owner watches them in `sheet.html`.                                                              |
| Asking to animate a particular still                                     | Say what coverage you need; the draw is the host's.                                                                                                             |
| Calling clips scored or validated                                        | Nothing scores or audits clips yet; triage only removes mechanical failures.                                                                                    |
