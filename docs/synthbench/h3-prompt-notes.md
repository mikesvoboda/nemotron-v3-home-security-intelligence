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

## Round log

| Round | Clips | Rerolls by reason | Notes |
| ----- | ----- | ----------------- | ----- |
