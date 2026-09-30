# Synthbench P3 acceptance: the live handoff dry run (2026-09-29)

Design §9: a flagship agent in a fresh sandbox, given only `docs/synthbench/agent-handoff.md`,
completes a 10-event pilot and a 50-event batch. Plan Task 14. Recorded on 2026-09-29, after the
run, from the batch reports, the host checks, the guard's journal and the agent's
`docs/synthbench/prompt-notes.md` (renamed `flux-prompt-notes.md` on 2026-09-30).

| Criterion (design §9)                                  | Result                                                                                                                                                                                                     |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| the reports arrive                                     | **pass**: `report.md` and `sheet.html` for both batches (04:08 and 05:16 UTC), and the agent's reports to the owner                                                                                        |
| the owner's host `check` passes on both batches        | **pass**: pilot-1 verified 22 files, batch-1 106 files; both exited 0                                                                                                                                      |
| the flagship stays healthy throughout (guard stops: 0) | **pass**: the guard's journal has one stop since install, at 2026-09-28 23:28 during the Task 12 flagship restart (`swap.sh`), before the sandbox existed; none during the run                             |
| the owner only read reports and answered stop-and-ask  | **pass, owner to confirm**: no owner edit touched the agent's workspace during the run (the first, a `rules.py` sync, came after batch-1); any nudge typed in the agent's own session is not recorded here |

**Result: pass.** P3 is accepted.

## Batches

| Batch   | Events | Ready | Rerolled (by reason) | Failed | Median render s | Failed jobs |
| ------- | ------ | ----- | -------------------- | ------ | --------------- | ----------- |
| pilot-1 | 10     | 10    | 1 (`text_overlay`)   | 0      | 8.3 (p90 9.1)   | 0           |
| batch-1 | 50     | 50    | 3 (`text_overlay`)   | 0      | 8.0 (p90 9.0)   | 0           |

The sandbox was `agent-synthbench-gen`, created from the owner's checkout at `ed2b72b2`. The two
batches took 64 renders and 8.9 minutes of render time.

## Stop-and-ask questions and nudges

None reached the controller's session. The owner's first message after the run reported it
finished. (Owner: add any nudge or answer given inside the agent's session.)

## What the agent changed after the pilot

The agent keeps `docs/synthbench/prompt-notes.md`, a log of what worked, and used the pilot's
lessons in batch-1:

- It kept the geometry clauses that held across all five camera positions, and wrote `ir_night`
  scenes as ordinary dark scenes without naming infrared. That came out right in 13 of 13
  batch-1 `ir_night` events.
- It rewrote role nouns that `check` rule 1 rejects.
- It treated `text_overlay` (a second, garbled date drawn by FLUX) as seed-dependent. All three
  batch-1 cases cleared on reroll, so it rerolls rather than rewording the prompt.
- It learned to compare a render with its still, before calling a mark FLUX's or the camera
  stage's.

It also added a comment to `synthbench/taxonomy/tier_b_v0.yaml` stating the owner's sign-off.
The comment does not change the taxonomy's hash. The owner committed it (28fc5fda).

## Camera stage against a real still (owner)

Plan step 4: compare one pilot still with a real Foscam still, on the host only (no real pixel
leaves the machine):

- the timestamp's position, format and size;
- noise, contrast and JPEG look.

Owner: record the differences here. They are inputs to the calibration plan (parent spec D13), not
fixes for P3.

## Deviations

- **Gate: taxonomy sign-off.** The P2 handoff's review items for `tier_b_v0.yaml` were not worked
  through before the first batch. They were: generic terms such as `gun` and `bat`, the label mix,
  zone shares, clothing against scenario and weather, and lighting coverage. The sign-off is the
  agent's comment, committed by the owner. `tierb-v0`'s values are frozen by the events already drawn from it,
  so the items become inputs to `tierb-v1`.
- **After the acceptance run**, not during it: the owner synced the host's `rules.py` into the
  workspace, added owner notes to `prompt-notes.md`, gave the agent the `synthbench-generation`
  skill and `corpus coverage`, and drove the 400-event run (batch-2 to batch-5) with a `/goal`.

## Follow-ups

- **Camera calibration** (plan P3-R3, parent D13) gets its own plan. It needs the owner's notes
  above and a mapping of the five real cameras to camera types.
- **`tierb-v1`**: the taxonomy review items above, commercial properties, vehicle type, and zones
  no scenario reaches (`corpus coverage` lists them).
- Fixed with this record: the final review's parked items. `render` keeps the failed events in
  a later stop's message; `camera` no longer counts failed events as awaiting a render;
  `report` counts only failed jobs, with an unreachable renderer on its own line; `corpus
snapshot` keeps an unexpected error's traceback in the journal; the runbook's same-commit
  check no longer creates a sandbox when the commits differ; and stale docs.
- Still open, by design: a failed renderer warm-up (`ExecStartPost`) can leave the unit's own
  container running. The guard and the runbook's manual fallback cover it.
