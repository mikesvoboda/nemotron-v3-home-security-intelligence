# Synthbench prompt notes: what works with MiniMax-H3 turbo

Living log of motion wording that produces good clips and wording that does not, for whoever
drives clip rounds. The stills' log is `flux-prompt-notes.md`; this one is only for motions. It
exists for the same reason: `clip check` freezes every motion in a round before any clip
renders, and a reroll re-renders the frozen motion at a new seed (`prompt_sha256` is kept, only
the seed changes). **A round can only teach the next round.** Read this file before writing
motions, and add to it after every round.

## How to use this file

- **Every claim carries its n.** `n=12` means 12 clips were looked at. A single observation is
  not a rate. Nothing here is established until it repeats.
- Promote a note from _seen once_ to _confirmed_ only when a second round shows it. Do not edit
  the earlier row's n; add a new round row to the log below.
- Record the failures too, including your own misreads of a strip. A note that only lists
  successes will steer later rounds wrong.
- This file changes what you write, never what `clip check` accepts. The motion rules are in
  `agent-handoff.md`, "Clip rounds"; `clip check` is the authority.

## Facts about this pipeline that shape wording

These are verified, not opinions.

| Fact                                                                                                                | Consequence for wording                                                                                           |
| ------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Frame 0 is the source still's render, before the camera stage                                                       | The scene, light and weather are already fixed. Say only what moves next; re-describing them invites a new scene. |
| `clip check` appends `CLIP_SUFFIX`: "Fixed security camera; the camera does not move; one continuous shot."         | The camera is already said. Camera and edit words are rejected (rule 5, `synthbench/prompt/camera_moves.yaml`).   |
| A clip is 243 frames at 24 fps, about 10 s                                                                          | One to three plain actions fit. A long sequence of actions is more than 10 s can show.                            |
| Triage may reroll only `camera_moved`, `subject_lost`, `subject_duplicated`, `prop_lost`, `morphing` or `scene_cut` | A dull clip is `ok`. Wording is the only lever on how interesting a clip is, and it moves one round at a time.    |

## Subjects that cross the frame (clips-1, seen once)

Counted on 2026-10-01 at 23:30, mid-round, from `clip-index.jsonl` (finished clips: ready, or
failed after 3 seeds) and `rounds/clips-1/motions.jsonl`. One round, so every row is _seen once_.

| Motion                                                                                          | Finished | Ready | Failed |
| ----------------------------------------------------------------------------------------------- | -------: | ----: | -----: |
| A runner crossing the frame: "runs / jogs along the paving", "across", "past" (hooded_jogger)   |       13 |     0 |     13 |
| A runner on the camera's line of sight: "runs up the drive toward the house" (hooded_jogger)    |        5 |     3 |      2 |
| A walker crossing the frame: "walks along the pavement", "across the paving" (neighbor_passing) |        9 |     4 |      5 |
| Someone working in place (pool_service, yard_maintenance, delivery_driver)                      |       26 |    24 |      2 |

- **"They stay inside the frame the whole clip" does not keep the camera still.** Every
  hooded_jogger motion said it. H3 follows a runner who crosses the frame by moving the camera:
  of the scenario's 50 verdicts, 36 were `camera_moved`, 5 `subject_lost`, 3 `scene_cut` and 3
  `subject_duplicated`; 3 were `ok`.
- **Point the movement along the camera's line of sight.** A runner going up the drive toward
  the house stays in frame by moving toward or away from the camera, so H3 has no subject to
  follow sideways: 3 of 5 passed, against 0 of 13 across.
- **Speed matters.** Walkers crossing the frame passed 4 of 9; runners crossing it, 0 of 13.
- **Settings do not fix it.** The 2026-09-30 settings trial re-rendered 15 clips at the same
  still, motion and seed, changing one input at a time: the still as the last frame, shift 12, 6
  steps, 124 frames, and the full 20-step model. None stopped H3 moving the camera; the ones that
  pinned the framing hardest turned a slow drift into a hard cut instead. Wording is the lever.
- **To try next round (untested):** keep a crossing subject's movement short and inside the
  shot. A jogger who slows at the corner and jogs in place, or stops to check a watch; a walker
  who pauses at the gate. Or turn the path toward the camera: up the drive, along the path to
  the door.

## Round log

| Round | Clips | Rerolls by reason | Notes |
| ----- | ----- | ----------------- | ----- |
