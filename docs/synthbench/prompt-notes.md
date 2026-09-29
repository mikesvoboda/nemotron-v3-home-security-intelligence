# Synthbench prompt notes: what works with FLUX.2 [dev]

Living log of wording that produces good stills and wording that does not, for whoever drives
generation. It exists because a batch can only teach the _next_ batch: `check` freezes a prompt
before any image exists, and a reroll re-renders the frozen prompt at a new seed. Verified in
`provenance.json` for pilot-1: attempt 1 and attempt 2 carry the same `prompt_sha256` and differ
only in `seed`. **You cannot reword your way out of a bad still mid-batch.** Read this file before
writing prompts, and add to it after every batch.

## How to use this file

- **Every claim carries its n.** `n=11` means 11 renders were looked at. A single observation is
  not a rate. Nothing here is established until it repeats.
- Promote a note from _seen once_ to _confirmed_ only when a second batch shows it. Do not edit
  the earlier row's n; add a new batch row to the log below.
- Record the failures too, including your own misreads. A note that only lists successes will
  steer later batches wrong.
- This file changes what you write, never what `check` accepts. The rules are in
  `agent-handoff.md`; `check` is the authority.

## Facts about this pipeline that shape wording

These are verified, not opinions.

| Fact                                                                                                                                                                                                                  | Consequence for wording                                                                                                                                                                                                                                                                                                                                       |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `check` freezes the prompt; a reroll keeps `prompt_sha256` and changes only the seed                                                                                                                                  | Wording is a one-shot bet per event. Fix wording between batches, not within one.                                                                                                                                                                                                                                                                             |
| `check` appends `CAMERA_SUFFIX` to every prompt: "…fixed, high-mounted security camera looking down at the scene through a wide-angle lens, ordinary everyday detail, no on-screen text, no timestamp, no watermark." | The camera look is already said. Repeating it in your prompt wastes the length budget and its nouns are blocklisted. It also means every prompt inherits the same anti-text sentence — see the drawn-date defect below.                                                                                                                                       |
| Rule 1 accepts only `terms:` words for a subject's class                                                                                                                                                              | Role nouns fail. `worker`, `landscaper`, `technician`, `intruder` are **not** person terms. Use person / man / woman / figure / someone / individual / adult / teenager, and child / kid / toddler / boy / girl. Props likewise: handgun/pistol/gun, knife/blade, package/parcel/box, crowbar/pry bar, ski mask/balaclava, hedge trimmer, smoke, fire/flames. |
| Rule 4 rejects clock times                                                                                                                                                                                            | Write the light (`before dawn`, `midday`, `night`), never `4:40` or `9 pm`. `scene_time` is for you to infer light and weather from, not to quote.                                                                                                                                                                                                            |
| `camera` draws the real overlay into the top-left                                                                                                                                                                     | Never fight for that corner, and never name it. A second date there is a defect, not your overlay.                                                                                                                                                                                                                                                            |
| The spec's `subjects[].attributes.clothing` is ground truth                                                                                                                                                           | Describe the garment even when it looks odd for the scene (a blue coat on a toddler at a pool in July). The mismatch is the spec's, and an honest still shows it.                                                                                                                                                                                             |

## Wording that worked (pilot-1, n=10 events / 11 renders)

Confidence is low everywhere at this n. Treat as starting hypotheses worth keeping, not rules.

| Wording                                                                                                                                                                                                                                                                                                                                                               | Evidence                                                                                                                                      | Confidence                                      |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| A geometry clause naming the vantage without naming a lens: `seen from above the garage door looking down the concrete drive`, `seen from right beside the door frame at close range`, `seen from a tall pole at the edge of the lot looking down over the rows of parking spaces`, `seen from out in the yard at eave height`, `seen from a high corner of the room` | 0 `wrong_scene`, 0 `not_security_camera` across all 5 camera positions (day/clear, day/fog, ir_night/rain, porch_lit_night, indoor day). n=10 | low-mid (covers all 5 positions, but one batch) |
| Prop + where it sits on the body: `holding a handgun down at his side in one hand`, `holding a knife in one hand at his side`, `wedging a crowbar into the gap between the door and its frame, both arms working at it`                                                                                                                                               | Prop legible in 3/3 prop-bearing threat scenes. n=3                                                                                           | low                                             |
| `ir_night` written as an ordinary dark scene, no mention of infrared                                                                                                                                                                                                                                                                                                  | 2/2 came out correct IR grey after the camera stage. n=2                                                                                      | low, but cheap to keep                          |
| Plain declarative scene, one sentence per fact, ~430-480 chars                                                                                                                                                                                                                                                                                                        | No refusals, no `blank`, no `refusal_card`, no `broken_anatomy` in 11 renders. n=11                                                           | low                                             |

## Wording that worked (batch-1, n=50 events / 53 renders)

The same clauses, now on a second batch and a second set of facts. Promoted where the second
batch actually reproduced the result.

| Wording                                                                                                                                                                                                                                                                                                                 | Evidence                                                                                                                                                                                                          | Confidence                                                                                        |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Geometry clause naming the vantage, no lens noun (`seen from the eaves above the deck looking out over the wet paving`, `seen from a tall pole at the corner looking down at the sidewalk`, `seen from a high corner of the room across the floor`, `seen from just beside the front door looking down at the decking`) | 0 `wrong_scene`, 0 `not_security_camera`, 0 `blank`, 0 `refusal_card`, 0 `broken_anatomy` across all 53 renders, covering all 5 camera positions × day/dusk/golden/ir_night/porch_lit × clear/fog/rain/snow. n=53 | **confirmed** (two batches, 64 renders total, no counterexample)                                  |
| Prop + placement on the body (`a handgun held in one hand down at his side`, `a knife in one hand pointing down toward the deck`, `a pry bar jammed into the door frame beside the latch, both hands hard on it`, `a skimmer net … with arms extended`, `a machete … cutting through a thick woody stem`)               | Prop legible in 10/10 prop-bearing scenes this batch (handgun, knife ×2, crowbar, spray can, net, machete, grinder, flashlight, parcel ×2 counted separately). n=10 events                                        | **confirmed** (was n=3; nothing failed)                                                           |
| `ir_night` written as an ordinary dark scene, infrared never named                                                                                                                                                                                                                                                      | 13/13 `ir_night` events in batch-1 came out as correct grey IR after the camera stage; plus pilot-1's 2. n=15 across both batches                                                                                 | **confirmed**                                                                                     |
| Plain declarative, one sentence per fact, ~430-600 chars                                                                                                                                                                                                                                                                | No refusals and no `blank` in 64 renders. n=64                                                                                                                                                                    | **confirmed** for "does not provoke a refusal"; still untested as a _quality_ claim               |
| Hard negatives stated as ordinary facts (face gaiter on a snowy evening; machete clearing brush; toy blaster with orange tips)                                                                                                                                                                                          | 6/6 read as benign — `winter_face_covering` 006/045, `landscaper_machete` 008/047, `costume_weapon` 009/048 — with no extra wording arguing the case. n=6                                                         | low-mid — this is the class worth pushing hardest, since it is where a still can be quietly wrong |

Two new clauses that cost nothing and are worth keeping:

- **Weather as a visible surface, not an adjective**: `rain dimpling the surface of the pool and the
paving in a dense pattern`, `cut clippings dusting the snow at his feet`, `the beam showing
drifting mist and the top of the grass`. Weather was legible in 17/17 non-clear events (7 snow,
  6 rain, 4 fog) without exception. n=17.
- **Light source named where it falls**: `the glare of a vehicle's headlights from the street
floods across the drive and throws his shadow long toward the garage door`, `the lamp throwing
his shadow long across the boards`. Gave a coherent single light and readable shadows in 3/3
  `porch_lit_night` events plus the two events whose scene names a headlight glare (044, 046).
  n=5.

## Reviewing: prove a mark is FLUX's, not the camera's

The camera stage owns the top-left, so a mark there is ambiguous by default. Resolve it against
`events/B/<id>/renders/a<k>-s<seed>.png` — the **raw pre-camera render**. If the mark is in the
render, FLUX drew it and `text_overlay` is honest. If it appears only in `stills/*.jpg`, it is
overlay furniture and is never a reason.

The two files differ in size (batch-1: renders 1280×720, stills 1920×1080), so crop both by a
_fraction_ of width and height, not in pixels — a fixed 330 px window shows different ground in
each. Contrast-stretching a 5× upscale (`ImageOps.autocontrast`) turns "faint smudge or soffit
seam?" into legible letterforms. This settled three calls in batch-1 and reversed one of my own
first reads (000's "smudge" was the word `Gnålet`).

Pillow is not on the bare `python3` here — run the crops under `uv run python`.

## Defects seen

- **`text_overlay` — now confirmed, not a one-off. 3 of 53 renders (batch-1: 000, 002, 020, all
  attempt 1); pilot-1: 1 of 11 (007).** Three faces of one defect: a garbled second date above the
  camera's own (`IMEIUR 24128 10:…`), a line of pseudo-letterforms in the dark area above it
  (`Gnålet. 3 Larhh`), and a boxed pseudo-logo to the left of the date. All three verified
  **present in the raw pre-camera render**, and all three prompts were rule-4 clean — so this is
  FLUX drawing text unprompted, not a clock-time slip. **All 3/3 cleared on reroll** (frozen
  prompt, new seed), and 020's logo box vanished in the new render too: the defect is
  seed-dependent, not prompt-determined, so reroll is the right lever and no wording change is
  implied. Event-level loss 3/50 = 6%, above the 5% cap, yet every event recovered inside two
  attempts — the cap is a budget on _rerolls_, not on losses, and it held (3 of 5 used).
  _The `CAMERA_SUFFIX` lever in `synthbench/prompt/rules.py` stays untested: nothing here says a
  different suffix would suppress it, since the current suffix already forbids text._
- **Object-count drift — did not recur.** Pilot-1 drew three parcels where the spec fixed one
  (1 of 11). Batch-1's two package events drew exactly one (032, 036). _Seen once, then not seen
  at n=53._ Still no triage reason covers object count, and it stays an owner question: add a
  reason, or accept count drift.
- **Head cropped by the top edge — 1 of 50 (048, `costume_weapon`).** A `doorbell_fisheye` prompt
  I wrote as `seen from just beside the front door looking down at the decking` put a teenager's
  head above the frame. The close vantage is the spec's and no reason covers framing, so the
  verdict was `ok`. _Seen once; if it repeats, the wording lever is giving a near vantage room for
  a standing height instead of leaning on `close range`._
- **Dark is not blank — a false alarm from my own pre-screen.** 033 (indoor `ir_night`) had the
  lowest spread of the batch (stddev 16.6), and the only reason it could take is `blank`. A room
  lit by faint window light has flat statistics and still shows sofa, ski-mask eye holes and rug.
  Read the image before believing the number.
- **My own misread risk, not a model defect:** `check` first rejected "a worker in a white vest"
  (rule 1). Cost one round trip.

## Triage judgment calls to keep in front of the owner

- A **physical** sign posted on glass is not `text_overlay`; text _drawn into the scene_ is. Judge
  by whether it is an object in the room or pixels on top of the image. Seen four times and held
  each time: pilot-1 002 (paper notice taped to a lobby door), batch-1 003 (door), 010 (window),
  049 (notice on a lobby glass frontage). Printing on a cardboard box (032) and a clothing label on
  a cuff (023) are the same rule — objects.
- The top-left date from the camera stage is never a reason. Only a **second** text is — and prove
  it is FLUX's against the raw render before rerolling.
- "I cannot make out the prop" is never a reason. Visibility is the independent checker's call.
- Motion smear on a hand or a leaping animal mid-action is not `broken_anatomy` unless bodies are
  merged or duplicated (041, deer mid-bound).
- A subject's head cropped by the top edge of a close vantage is not a reason — no reason covers
  framing (048). Say so in the report rather than reroll on a hunch.
- A vehicle parked in the drive instead of on the street is a scene deviation, not a reason (044).

## Throughput actually achieved (batch-1, from file mtimes)

`batch.json` 00:31:14 → `prompts.jsonl` 00:34:03 → `triage.jsonl` 01:15:32 → `report.md`
01:16:17 (local, 2026-09-29): 50 events end-to-end in **44.7 min = 0.9 min/event**, of which
writing 50 prompts was 2.8 min and reviewing was the remaining ~41 min. GPU render was 7.3 min
of that (report.md), so the agent-side loop is the constraint, not the GPU — **~67 events per
hour** (0.9 min/event), against a GPU capable of ~430/h. Review is 4.3x the bottleneck. Use this,
not a per-image guess, when pricing a big run: 1,000 events ≈ 15 h, 7,157 ≈ 107 h of my loop.

## Getting real signal, not anecdotes

Ten events cannot rank wordings. Two options, both the owner's call because both cost corpus
events or host time:

1. **Controlled repeat.** `sample --batch <new> --n 10 --seed 2566691490` reproduces pilot-1's
   exact ten specs, and `--n 50 --seed 2404914502` reproduces batch-1's fifty (the seed is
   independent of the batch name), so reworded prompts face identical facts and the comparison is
   clean. Cost: near-duplicate facts enter the corpus.
2. **Just run big batches and log counts.** Cheaper, slower to learn, and no A/B.

Do not fill the top-left corner with a roof edge or door frame to hide the drawn-text defect: it
steers composition to game a checker.

On this defect, batch-1 settled what to do: **reroll, and stop treating the suffix as the obvious
lever.** All 3/3 clear on a new seed with the prompt frozen says the defect is seed-dependent, so
one reroll per hit buys a clean still for 1/5 of the batch cap. Editing `CAMERA_SUFFIX` to shout
"no text" louder is still untested and now unattractive: the suffix already forbids text, and it
is inherited by every prompt in every future corpus version — a change with no evidence behind it
for a defect rerolls already beat. Revisit only if a batch shows hits surviving a second seed.

## Owner notes (2026-09-29, before batch-2)

Written by the owner's side, not by the agent. They are facts about the setup and the plan. They
are not wording results, so they carry no n.

- **Rules synced.** `synthbench/prompt/rules.py` in this workspace now matches the host
  checkout's (the head of PR #6715). The only change is rule 4's clock-time pattern:

  - it now also rejects `12:30pm` (quoted whole) and `9 a.m` without the final dot;
  - `o'clock`, `H:MM` and `<n> am/pm` were already rejected.

  Your `check` and the owner's host `check` now apply identical rules.

- **Reroll-cap arithmetic for the 400-image run** (batches of 50, cap 5 triage rerolls each):
  - `text_overlay` ran at 4/64 renders so far (6.25%), so expect about 3 hits per batch.
  - About 1 batch in 10 will see a 6th hit. `triage` then marks that event `failed` and exits 2.
  - That is the designed outcome, not your error. Stop, report it, and wait: the owner will say
    to continue. Nothing is deleted, and the owner samples replacements later.
  - Do not try to reword around it. Prompts are frozen, and the defect is seed-dependent (see
    above).
- **Update this file at the end of every batch,** before your session is cleared. Each batch
  views 50+ images, and the owner may `/clear` between batches. This file is how the next
  session starts where you left off.
- **Owner hypothesis, untested: the suffix may prime the defect.** `CAMERA_SUFFIX` names "no
  timestamp", and naming it may itself prime FLUX to draw one. Changing the suffix is not
  possible inside `tierb-v0`: `check` would reject every frozen spec. Record any evidence for or
  against it here, but never propose editing the suffix mid-version.

- **Owner decision (2026-09-29): the 400 run is 4 × 100, and the last batch deepens the hard
  negatives.**
  - `batch-2`, `batch-3` and `batch-4` are drawn normally.
  - `batch-5` is drawn with
    `--only hooded_jogger,power_tools_at_night,winter_face_covering,flashlight_neighbor,landscaper_machete`,
    about 20 events each. It takes the false-alarm (S2) sample from about 10 to about 30 per type.
  - The owner accepts the cost: normal batches after it skip those five until the rest catch up,
    about 1,000 events.

## Batch log

| Batch   | Events | Renders | Rerolls            | Failed | What it taught                                                                                                                                                                                                                                                                                                                                                                               |
| ------- | -----: | ------: | ------------------ | -----: | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| pilot-1 |     10 |      11 | 1 (`text_overlay`) |      0 | Rule 1 rejects role nouns; FLUX drew a date unprompted once; geometry clauses held across all 5 camera positions.                                                                                                                                                                                                                                                                            |
| batch-1 |     50 |      53 | 3 (`text_overlay`) |      0 | `text_overlay` confirmed at 3/50 and **all 3 cleared on reroll** — seed-dependent, so reroll is the lever, not the suffix. Geometry clauses, prop-placement and `ir_night`-as-dark-scene promoted to confirmed. Pre-screen false-alarmed on a legitimately dark indoor IR room; pre-camera renders settle every corner mark. One head cropped by a close vantage (no reason covers framing). |
