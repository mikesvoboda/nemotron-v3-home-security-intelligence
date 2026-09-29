# Synthbench Tier B generation: agent handoff

**Start here if you are the agent driving synthbench generation.** Read this whole file before
you run anything. `command-reference.md` beside it lists every option.

## What this run is

You write scene prompts for a synthetic security-camera benchmark, render them, look at every
image, and report to the owner.

A seeded sampler has already fixed the facts of each event: the place, camera, lighting,
weather, time, people, animals and objects, and the label. Those facts become ground truth for
the benchmark. You write the words; you never change the facts.

The images come from FLUX.2 [dev], which runs in ComfyUI on the host beside the model you run
on. Rendering slows that model, so `render` waits whenever the model has requests queued.

## What you can and cannot do

You can:

- run `uv run python -m synthbench <command>` from the root of your repository clone;
- write two files per batch in the corpus: `prompts.jsonl` and `triage.jsonl`;
- open any image the commands made, to look at it;
- read `/synthbench/status/`.

You cannot, and must not try to:

- start, stop or restart the renderer, the model server, docker, podman, or anything on the
  GPU;
- delete, move, rename or edit any other file in `/synthbench/corpus/`. The corpus is
  append-only, and `check` detects a changed image;
- change the library code to get past a rule. The owner runs `check` again on the host.

## How to run the commands

- First, once: run `uv sync --frozen` from the repository root, with a Bash timeout of
  600000 ms (10 minutes). The first sync takes several minutes.
- **Step 0:** run `uv run python -m synthbench doctor`. On exit 2, send the owner its FAIL
  lines and wait; the owner may say to go ahead with prompt work only (`sample` and `check`)
  while the renderer is down.
- Run every command from the repository root: `uv run python -m synthbench <command> --batch <name>`.
- Give `render` a Bash timeout of 600000 ms (10 minutes). It stops starting images after
  480 s, prints `N still to render`, and you run it again until N is 0.
- Every command exits `0` when done, and `1` when your request or your file needs fixing: read
  the message, fix it, and run the command again.
- Exit `2` means **stop and ask the owner**. Do not retry it and do not work around it. Tell
  the owner the command and its full message, and wait.
- A message that starts `unexpected error`, or a Python traceback, is also a stop-and-ask,
  whatever the exit code. It is never yours to fix in the library code.

## The loop for one batch

Batch names are lowercase letters, digits and hyphens, and each one is new: `pilot-1`,
`batch-1`, `batch-2`. The corpus version is in each spec as `corpus_version` (`tierb-v0` today).
Below, `<corpus>` is `/synthbench/corpus/<version>`.

1. **Sample.** `uv run python -m synthbench sample --batch <b> --n <n>`. It prints where the
   specs are: `<corpus>/events/B/<event id>/spec.json`.
   - A pilot is 10 events and a full batch is 50.
   - Before the first batch in a new area, run a 10-event pilot. `--only <scenario ids>` limits
     a pilot to some scenarios.
2. **Write prompts.** Read every spec in the batch. Write `<corpus>/batches/<b>/prompts.jsonl`,
   one JSON object per line: `{"event_id": "B-<b>-000", "prompt": "..."}`. The rules are in the
   next section.
3. **Check.** `uv run python -m synthbench check --batch <b>`.
   - On exit 1 it lists each problem as `<event id>: rule N: ...`. Fix those rows and run it
     again.
   - When every prompt passes, it freezes them. A frozen prompt never changes.
4. **Render.** `uv run python -m synthbench render --batch <b>`, repeated until it prints
   `0 still to render`.
5. **Camera.** `uv run python -m synthbench camera --batch <b>`. It turns each new render into
   the 1920x1080 still the pipeline will see.
6. **Look, and write verdicts.** Open every new still. Its path is
   `<corpus>/events/B/<event id>/stills/a<k>-s<seed>.jpg`; the attempt number `k` and the
   seed are in that event's `provenance.json`. Add one line per still to
   `<corpus>/batches/<b>/triage.jsonl`:

   - `{"event_id": "B-<b>-000", "k": 1, "verdict": "ok"}`, or
   - `{"event_id": "B-<b>-000", "k": 1, "verdict": "reroll", "reason": "blank"}`.

   Keep the earlier lines when you add new ones.

7. **Triage.** `uv run python -m synthbench triage --batch <b>`. If it scheduled rerolls,
   repeat steps 4-7 for them. Their attempt number is 2.
8. **Report.** `uv run python -m synthbench report --batch <b>`, then write your report to the
   owner (below).

Every command resumes where it stopped. If you were interrupted, run the same step again.

## Writing prompts (what `check` enforces)

Describe the scene in plain, concrete words:

- the place, as seen from the spec's camera position (see `cell.camera` below);
- the time of day, the light and the weather;
- each person or animal: what they wear and what they do;
- each object.

Use the spec's facts, and add no person, animal or weapon that is not in it.

1. **Name every subject and prop.** For each entry in `subjects` and `props`, use one word or
   phrase from its class's list under `terms:` in `synthbench/taxonomy/tier_b_v0.yaml`. For
   class `handgun` write "handgun" or "pistol"; for `package`, "package" or "parcel".
2. **Keep it realistic and non-graphic.**
   - Show what a camera sees: a weapon in a hand, a forced door, a person lying on the ground.
     Never injury detail, blood or gore.
   - Every person is anonymous. Describe people generically ("a man in a gray hoodie"); never
     name or suggest a real or famous person.
3. **Length:** at most 1,200 characters.
4. **No camera words.** Describe what the camera position sees, never the camera or its lens.
   `check` adds the camera look to every prompt itself, and the camera stage draws the real
   timestamp. `check` rejects these words and phrases in any case, with or without hyphens,
   and their plurals (rule 4 of `synthbench/prompt/blocklist.yaml`): `security camera`,
   `cctv`, `surveillance`, `footage`, `camera view`, `timestamp`, `time stamp`, `date stamp`,
   `watermark`, `caption`, `on screen text`, `text overlay`, `subtitle`, `logo`,
   `wide angle lens`, `fisheye`.

What the spec's fields mean:

| Field                                          | Meaning                                                                                     |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `cell.property_type`, `cell.zone`              | the place                                                                                   |
| `cell.camera`                                  | the camera position: doorbell_fisheye, eave_wide, garage_mounted, pole_lot or indoor_corner |
| `cell.lighting`                                | day, golden_hour, dusk, ir_night or porch_lit_night                                         |
| `cell.weather`, `cell.artifacts`, `scene_time` | weather, lens effects, and the time (HH:MM)                                                 |
| `subjects[].attributes.clothing`               | what a person wears                                                                         |
| `props[].held_by`                              | which subject holds the prop                                                                |

For `cell.camera`, describe what that position sees: a close view of the front step from
beside the door, or a driveway from above the garage. Never name the lens: `fisheye` and
`wide angle lens` break rule 4.

For `ir_night`, write a night scene; the camera stage turns it into infrared grey.

## Triage: when you may reroll

Look at every still. Reroll an event only for one of these reasons, and at most once per event:

| Reason                | Meaning                                                                    |
| --------------------- | -------------------------------------------------------------------------- |
| `blank`               | a black, white, flat or noise image                                        |
| `refusal_card`        | a safety or error card instead of a scene                                  |
| `wrong_scene`         | not the spec's kind of place (indoors for a driveway, a street for a pool) |
| `no_person`           | the spec has people and the image has none                                 |
| `broken_anatomy`      | merged or duplicated bodies, grossly broken limbs                          |
| `not_security_camera` | the image does not read as a fixed security camera's view                  |
| `text_overlay`        | text drawn into the scene: a watermark, a caption, a second timestamp      |

The date and time in the top-left corner are the camera's own overlay. They are not a reason.

Everything else is `ok`. In particular, "I cannot make out the knife" is **not** a reason:
whether a prop is visible is decided later by an independent checker and the owner. Rerolling
until an image looks right to you would bias the benchmark toward what your own model sees.

Limits:

- One reroll per event. A second failed triage marks the event failed.
- A batch may reroll at most 10% of its events: 1 in a 10-event pilot, 5 in a 50-event batch.
  Past that, `triage` marks the event failed and exits 2.
- Failed events stay in the corpus, and the report lists them.

## Your report to the owner

After `report`, write a short message with:

- the batch name, the corpus version, and the paths of `report.md` and `sheet.html`;
- counts: events, ready, rerolled (by reason), and failed;
- the median render time per image, and any failed render jobs;
- any snapshot hold the report shows;
- what you noticed across the batch, such as a scenario that keeps coming out wrong or wording
  that worked;
- after a pilot, what you will change in your wording for the full batch.

## Stop and ask the owner when

- any command exits 2, or prints `unexpected error` or a Python traceback;
- `check` reports a problem that is not in your own prompt rows (for example, a spec whose
  facts differ);
- you are unsure whether a prompt meets the content rules;
- a still shows something disturbing, or out of place in a way no triage reason covers;
- you think a rule or a limit is wrong. Say so; do not work around it.

## Out of scope

This run does not cover:

- Tier A (sites, cast, clips);
- the independent verifier and the audit page;
- benchmark runs;
- any change to the taxonomy, the camera parameters or the library code.

If the owner wants one of these, they will give you a different document.
