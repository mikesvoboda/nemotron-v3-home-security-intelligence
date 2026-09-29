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

## Wording that worked (batch-2, n=100 events / 103 renders)

The same clauses on a third, much larger draw. Nothing new was needed: this batch introduced no
clause that pilot-1 and batch-1 did not already carry.

| Wording                                                      | Evidence                                                                                                                                                                                     | Confidence                                             |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| Geometry clause naming the vantage, no lens noun             | 0 `wrong_scene`, 0 `not_security_camera`, 0 `blank`, 0 `refusal_card` in 103 renders spanning all 5 cameras × 5 lightings × 4 weathers. n=103 (164 over three batches)                       | **confirmed** (three batches, no counterexample)       |
| Prop + placement on the body                                 | No prop-absent still among 68 prop-bearing events (19 prop classes). n=68                                                                                                                    | **confirmed** (was n=10; nothing failed)               |
| `ir_night` as an ordinary dark scene, infrared never named   | 24/24 `ir_night` events came out as correct grey IR. n=24 (39 over three batches)                                                                                                            | **confirmed**                                          |
| Weather as a visible surface, not an adjective               | Weather legible in all 43 non-clear events (18 rain, 14 snow, 11 fog). n=43                                                                                                                  | **confirmed** (was n=17)                               |
| Light source named where it falls                            | Coherent single light and readable shadows in 11/11 `porch_lit_night` and 6/6 `headlight_glare` events. n=17 (was n=5)                                                                       | **confirmed**                                          |
| Hard negatives stated as ordinary facts, no arguing the case | All 15 benign hard-negative events read benign (`costume_weapon` 076 with orange-tipped toy gun; `winter_face_covering`, `hooded_jogger`, `flashlight_neighbor`, `landscaper_machete`). n=15 | mid — no counterexample yet, and batch-5 deepens these |

## Wording that worked (batch-3, n=100 events / 105 renders)

The same clause set on a fourth draw, 264 events in. Still no new clause was needed, and nothing
in the batch failed for want of wording: every reroll was `text_overlay`, which no wording has
ever prevented. The value of a fourth batch is the n's, plus one drafting trap.

| Wording                                                                                    | Evidence                                                                                                                                                                                                                                                                             | Confidence                                                              |
| ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------- |
| Geometry clause naming the vantage, no lens noun                                           | 0 `wrong_scene`, 0 `not_security_camera`, 0 `blank`, 0 `refusal_card`, 0 `broken_anatomy` in 105 renders spanning all 5 cameras (57 `eave_wide`, 17 `doorbell_fisheye`, 12 `garage_mounted`, 9 `indoor_corner`, 5 `pole_lot`) × all 5 lightings. n=105 (269 over four batches)       | **confirmed** (four batches, no counterexample)                         |
| Prop + placement on the body                                                               | No prop-absent still among 65 prop-bearing events, 18 classes — including the awkward ones: `crowbar` 5/5 at the door edge, `machete` 3/3 at brush, `angle_grinder` with sparks, `spray_paint` with a fresh mural, `pool_net` in the water with leaves. n=65 (133 over four batches) | **confirmed**                                                           |
| `ir_night` as an ordinary dark scene, infrared never named                                 | 30/30 `ir_night` events came out grey IR, indoor (kitchen, lobby, living room) as well as outdoor. n=30 (69 over four batches)                                                                                                                                                       | **confirmed**                                                           |
| Weather as a visible surface, not an adjective                                             | Weather legible in all 36 non-clear events (13 snow, 12 fog, 11 rain). n=36 (79 over four batches)                                                                                                                                                                                   | **confirmed**                                                           |
| Light source named where it falls                                                          | Coherent single light in 10/10 `porch_lit_night`; 6/6 `headlight_glare` events showed the beam and the long shadow it implies. n=16 (33 over four batches)                                                                                                                           | **confirmed**                                                           |
| `motion_blur` and `lens_droplets` as scene consequences (a passing car; rain on the glass) | 5/5 `motion_blur` and 5/5 `lens_droplets` events showed the artifact without any smear being asked for on the subject. n=10 (was n≈5)                                                                                                                                                | mid — held twice at small n; keep describing, never naming the artifact |
| Hard negatives stated as ordinary facts, no arguing the case                               | All 16 benign hard negatives read benign (`hooded_jogger` 3, `power_tools_at_night` 3, `winter_face_covering` 3, `flashlight_neighbor` 3, `landscaper_machete` 3, plus `costume_weapon` 1). n=16 (31 over two batches)                                                               | mid — still no counterexample; batch-5 is 100 of these                  |

## Drafting trap: `check` does not read your camera clause back to the spec

`check` verifies rule 1 terms, non-graphic wording, length and the blocklist. It does **not**
compare the vantage in the prompt with `cell.camera`. In batch-3 I wrote one prompt (097) whose
view clause described a different vantage than the spec's camera; the generator passed it and only
a self-audit found it. Since prompts freeze the moment `check` exits 0, that would have been a
`wrong_scene` I caused and no reason could have fixed. Cheap guard: when generating, print
`cell.camera` next to the clause per event and eyeball the 100 pairs before writing the file.
n=1 slip in 264 events, but the failure is silent and permanent.

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
  attempt 1); pilot-1: 1 of 11 (007); batch-2: 3 of 100 first attempts (051 is `broken_anatomy`,
  so its marks are 064 and 090).** Three faces of one defect: a garbled second date above the
  camera's own (`IMEIUR 24128 10:…`), a line of pseudo-letterforms in the dark area above it
  (`Gnålet. 3 Larhh`), and a boxed pseudo-logo to the left of the date. All three verified
  **present in the raw pre-camera render**, and all three prompts were rule-4 clean — so this is
  FLUX drawing text unprompted, not a clock-time slip. **All 3/3 cleared on reroll** (frozen
  prompt, new seed), and 020's logo box vanished in the new render too: the defect is
  seed-dependent, not prompt-determined, so reroll is the right lever and no wording change is
  implied. Event-level loss 3/50 = 6%, above the 5% cap, yet every event recovered inside two
  attempts — the cap is a budget on _rerolls_, not on losses, and it held (3 of 5 used).
  **batch-2 adds the geometry: the two marks were in the TOP corners** — 064 top-right, 090
  top-left above where the camera draws its date. Batch-1's were all bottom-corner, so the
  whole frame edge needs the raw-render check, not just the bottom. Rate across the corpus was
  then **7 of 164 renders (4.3%)**; at 100-event batches with a 10-reroll cap that is ~4 expected
  hits and comfortable headroom, unlike a 50-event batch's 5-reroll cap. **All 3/3 batch-2 hits
  cleared on reroll too (6/6 cumulative).**
  **batch-3: 5 hits in 100 first attempts (006, 046, 047, 072, 086) — 5%, the highest yet, and
  5 of the 10-cap exactly.** Four were top-left (a second garbled date, or two gibberish lines)
  and one top-right, all proven in the raw render; **all 5 cleared on reroll, 11/11 cumulative.**
  Corpus rate now **12 of 269 renders (4.5%)**, so the 10-reroll cap on a 100-event batch is
  ~2.2x the expected need — but a 5% batch is only ~0.5 from the cap, so a batch that lands at
  6 hits is well inside the plausible range and would `fail` one event. Batch-5 is the one to
  worry about: 100 `ir_night`-heavy, dark-corner events are where the gibberish keeps appearing.
  **batch-4: 1 hit in 100 first attempts (1%), the lowest yet, and it did not clear** — not
  because reroll stopped working but because my k=2 verdict on it was wrong (see "Agent-side
  failure"). Corpus rate **13 of 370 renders (3.5%)**, still ~3 expected hits per 100-event batch
  against a 10-reroll cap. The one hit was `pet_activity` at **day/clear**, so the "gibberish
  lives in dark IR corners" reading I leaned on last batch is weakened: it may simply track
  busy detail in the top strip, at any lighting. Batch-5 is no longer specially feared for this.
  **batch-5: 2 hits in 100 (004 top-left, a garbled second date; 020 a line of pseudo-letterforms
  above the camera's own clock), both proven in the raw render, both cleared on reroll — so every
  honestly-judged `text_overlay` reroll in the corpus has cleared (13/13; batch-4's 063 image also
  cleared, my verdict on it did not). Corpus rate 14 of 475 renders (2.9%)**, and 2/100 is ~2.2x
  headroom under the 10-cap. My batch-4 summary line carried the total as "13/370"; recounting
  from the triage rows gives 14/475 — the notes' running figure had not caught batch-4's own 063.
  Nothing here still implicates a specific lighting: 004 was `day`, 020 `dusk`.
  _The `CAMERA_SUFFIX` lever in `synthbench/prompt/rules.py` stays untested: nothing here says a
  different suffix would suppress it, since the current suffix already forbids text._
- **Object-count drift — it does recur. batch-2: 2 of 100 (019 `knife_visible` holds a second
  pale blade in the off hand; 081 `tailgating` shows three people where the spec declares two),
  plus pilot-1's three-parcel event (1 of 11). Batch-1's two package events drew exactly one.**
  So ~3/164 events, not a one-off. Still no triage reason covers object count or person count,
  and it stays an owner question: add a reason, or accept the drift. Note the risk it carries
  for scoring: a checker reading 081 as three people is reading the scene the spec did not build.
  **batch-3: 3 more of 100, so it is not receding — 020 `tailgating` with three people where two
  are declared, 074 `firearm_visible` with two gun-shaped objects where one
  `handgun` is declared, 077 `package_theft` with two boxes where one `package` is declared.**
  Cumulative **6 of 264 events (2.3%)**, and the split matters for the owner: 3 person-count,
  2 object-count, 1 parcel-count. Two of the three batch-3 cases are in threat-bearing scenarios
  (a person count and a weapon count are exactly what a checker is asked about), so this is the
  most likely source of a checker disagreement that is the image's fault, not the checker's.
  **batch-4: 4 more of 100, so five batches in a row — 003 `package_theft` with two cartons
  against one `package`, 071 `costume_weapon` with a second costumed person at the door against
  one subject, 084 `masked_intruder_night` with a second figure at the shed corner, 094
  `package_theft` with two parcels.** Cumulative **10 of 360 events (2.8%)**, split 4 person-count
  / 3 object-count / 3 parcel-count. It is a stable ~3% background rate, not a trend, and it is
  now the largest class of spec-to-image disagreement no triage reason can act on.
  **batch-5: 1 more of 100 — 066 `power_tools_at_night` with a second drill body gripped in the
  off hand against one declared `power_drill`, proven by cropping the raw render (two battery
  packs, two chucks).** Cumulative **11 of 460 events (2.4%)**, split 4 person-count / 4
  object-count / 3 parcel-count — the class has appeared in every batch, an
  unmoved ~3% background rate, still the largest spec-to-image disagreement with no covering reason.
  _Method note on this bullet: I came to it carrying "084 second blade" from the batch-4 ledger and
  then "084 second person" from a guess, and re-opening 084 showed neither — one person, one blade.
  An id reused across batches is a trap; the count only means anything re-read from the still._
- **Prop absent from a prop-bearing scene — first seen in batch-4, 2 of 68 prop-bearing events.
  004 `car_break_in` (`ir_night`, farmhouse drive): a hooded figure working the garage-door window,
  and **no car anywhere in the frame** — the carport in the background stands empty. 005
  `catalytic_converter_theft` (`ir_night`, warehouse lot): a man lying under a **lopped axle and
  wheel** with a saw and a parts bag beside him, but no car body. In both the scenario is
  unintelligible without the vehicle, so this is a real scene failure and worse than a hard-to-read
  prop: `car` is 8 events in this batch and 6/8 drew one, so it is seed-dependent, not systematic.
  No triage reason covers it — `wrong_scene` is about the _kind of place_, and the place was right.
  The owner should know the class exists. Note this is **not\*\* the "I cannot make out the prop"
  case the handoff rules out — the handoff's point is that an object too faint to trust is not my
  call, and that holds; here there is no occlusion and no un-readability, the prop is simply not
  drawn, and the scene's premise is gone with it. That difference has to be argued to the owner,
  not assumed by me, so no reason exists and both events are `ok`. Both are `ir_night`, so the open
  question is whether the camera stage's grey conversion is where a large pale object goes missing.
  n=2, watch the `car`-bearing events.
- **My generator forced a hood onto non-hood clothing — batch-5, 18 of 19 `hooded_jogger` events.
  The owner chose the `hooded_jogger` scenario, but the _spec's_ `clothing` attribute for those
  events is often a non-hooded garment (`blue t-shirt`, `green vest`, `white jacket`, `tan
sweater` — 18 of 19). `/tmp/gen_b5.py`'s jogging clause always wrote "with the hood pulled up
  over their head", so the image shows a hood the declared clothing does not contain — a
  spec-to-image clothing mismatch on clothing **type**, the one clothing axis that is scorable
  (colour is unscorable under `ir_night`, n=96 IR events). The stills read fine as scenes, so no
  reroll reason applies and all are `ok`. But this is a wording decision I should not make alone:
  does `hooded_jogger` override the clothing attribute (scenario wins, hood correct) or defer to it
  (no hood, and the scenario is just "a jogger")? **Owner call**; for now flagged, not changed. n=18
  is the largest self-inflected defect of the run and it is mine, not FLUX's.**
- **My generator wrote undeclared motion blur into a scene — batch-5, 3 of 100 (016, 046, 051).**
  The drill clause carried "the bit turning so fast that the drill and his hands are smeared with
  its motion" regardless of whether the cell declared `motion_blur`, so three
  `power_tools_at_night` events with `art=-` came back with the smear described anyway — an
  artifact in the image that the spec's `cell.artifacts` does not list. A checker that verifies
  declared artifacts, or that treats undeclared ones as wrong, would be handed a mismatch of my
  making. The fix is wording only: emit the smear sentence **only** when `motion_blur` is declared.
  The three events are `ok` (an artifact I wrote is not one of the seven reasons). n=3.
- **Fog clause names a lit lamp that is not lit in daylight — batch-5, 3 of 100 (014, 049, 075).**
  `WEATHER['fog']` ends with "the light from the lamp spreading into a soft cone in it" — right for
  the 4 night/dusk fog events (021, 035, 068, 085), nonsense for the 3 under `day`/`golden_hour`
  where no lamp is on. Frozen now; the generator fix is to key the fog clause on `cell.lighting`.
  Cosmetic in these images (FLUX drew fog either way), n=7 fog prompts carry the phrase.
- **Camera unit painted into its own frame — batch-5, 1 of 100 (044).** A `lake_house/backyard`
  `eave_wide` still shows a security-camera housing bolted under the eave at top-left — the
  viewpoint device drawn into the scene it is the viewpoint of. I had this as n=2 from a batch-4
  memory, but re-opening 065 shows **no** drawn camera (only an ambiguous wall fixture), so the
  honest count is n=1. It is not `not_security_camera` — if anything it _reinforces_ that reading —
  and no reason covers a self-referential device, so `ok`. Worth one line to the owner as a scene
  oddity, not a defect to act on.
- **Declared `motion_blur` renders weakly — batch-5, 2 of 5 declarations faint (061, 086).** Across
  the corpus `motion_blur` is declared on 17 events; in the ones I can compare, FLUX often draws
  only a soft edge where the sweep should smear. A weakly-rendered declared artifact is not one of
  the seven reasons, so these are `ok` — but it means `motion_blur` is the least reliable of the
  three artifact classes to _depend on_ in a checker, and it is cheap to say nothing about the blur
  in prose and let the seed decide. n=17 corpus, watch it.
- **Head cropped by the top edge — 1 of 50 (048, `costume_weapon`).** A `doorbell_fisheye` prompt
  I wrote as `seen from just beside the front door looking down at the decking` put a teenager's
  head above the frame. The close vantage is the spec's and no reason covers framing, so the
  verdict was `ok`. _Seen once; if it repeats, the wording lever is giving a near vantage room for
  a standing height instead of leaning on `close range`._
- **Undeclared face covering on a hard negative — 1 of 100 (076 `costume_weapon`).** A child in
  the spec's gray hoodie holding the declared orange-tipped toy gun, but also wearing a white
  face mask nobody asked for. Readable, harmless, and no reason covers it, so the verdict was
  `ok` — but it makes a benign scene look more threatening than its label, which is exactly the
  axis the false-alarm bucket is measuring. Worth watching in batch-5, where the owner is
  deliberately deepening the hard negatives (n=15 hard negatives here, 0 other cases).
- **Dark is not blank — a false alarm from my own pre-screen.** 033 (indoor `ir_night`) had the
  lowest spread of the batch (stddev 16.6), and the only reason it could take is `blank`. A room
  lit by faint window light has flat statistics and still shows sofa, ski-mask eye holes and rug.
  Read the image before believing the number.
- **My own misread risk, not a model defect:** `check` first rejected "a worker in a white vest"
  (rule 1). Cost one round trip.

## Agent-side failure: the reroll lever cuts both ways (batch-4, cost 1 event)

063 lost its first render to a genuine `text_overlay` — a second garbled timestamp above the
camera's own, proven in the raw render. That verdict was right. Then I appended its k=2 verdict
**before opening the image**, typed a still path from memory (which failed, as the same mistake did
twice earlier in the run), and when I finally looked I matched the dog-on-a-farm-drive still against
**095's spec** — `masked_intruder_night`, lake-house living room, `ir_night` — and recorded
`wrong_scene`. Both the property and the lighting looked wrong _relative to the wrong spec_. The
actual cell is `rural_farmhouse / driveway / garage_mounted / day / clear`, subject `dog`, and the
still matched it. `triage` had already written the verdict into provenance and the index, and the
handoff is explicit that a verdict is final, so 063 is `failed` and nothing in the corpus can be
touched to undo it. Two process rules, both cheap:

- **Re-read the spec one-liner in the same breath as the still.** My dump-per-10 loop drifts: by
  event 63 the dumps in front of me covered 50-70 and 70-90, and the line I needed was one I had
  read once. Print `scenario / property / zone / camera / lighting / weather / subject class` beside
  the image and judge only from what is on screen together.
- **Image first, row second.** Every one of this run's three memory-typed mistakes (two bad still
  paths, one bad verdict) happened when I acted before looking. A verdict row is irreversible here;
  the image costs one `Read`.

What this costs in aggregate: across 370 renders and 364 verdicts I have misread in this direction
**once (n=1)**, so the agent-error rate sits well below the model-defect rate — but unlike
`text_overlay` it is unrecoverable, because the one reroll per event is already spent by the time
the second verdict is made. If the owner wants 063 back, that change is theirs to make on the host;
I have left its provenance, index rows and `triage.jsonl` exactly as `triage` recorded them.

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
- **Clothing colour is not verifiable under `ir_night` — batch-3 puts an n on this.** 30
  `ir_night` events: the camera stage renders all of them grey, so a `red work shirt` (020) or a
  `blue hoodie` can neither be confirmed nor denied from the still. All 30 held `ok` on that
  basis, consistent with pilot-1 through batch-2. The owner should know this before any checker is
  scored on clothing colour: the attribute is unscorable in the ~26% of the corpus that is IR, not
  merely hard.
- **Physical lettering, held again — batch-3 adds four cases** (049 and 056 a shirt patch/badge,
  003 doormat texture, door numbers on three porches). Cumulative 8 cases held, 0 rerolled.

## Throughput actually achieved (batch-1, from file mtimes)

`batch.json` 00:31:14 → `prompts.jsonl` 00:34:03 → `triage.jsonl` 01:15:32 → `report.md`
01:16:17 (local, 2026-09-29): 50 events end-to-end in **44.7 min = 0.9 min/event**, of which
writing 50 prompts was 2.8 min and reviewing was the remaining ~41 min. GPU render was 7.3 min
of that (report.md), so the agent-side loop is the constraint, not the GPU — **~67 events per
hour** (0.9 min/event), against a GPU capable of ~430/h. Review is 4.3x the bottleneck. Use this,
not a per-image guess, when pricing a big run: 1,000 events ≈ 15 h, 7,157 ≈ 107 h of my loop.

**batch-3 (n=100), same method:** `batch.json` 10:49:30 → `prompts.jsonl` 10:57:35 (8.1 min to
draft 100 prompts, including one `check` round trip) → `triage.jsonl` 11:52:36 → `report.md`
11:52:51. **63.4 min end-to-end = 0.63 min/event, ~95 events/hour** — better than batch-1 because
the clause set is settled and no wording is being re-decided. Review is still the loop: 55 of the
63 minutes, against 11.9 min of GPU for all 105 renders (median 8.0 s). Pricing a run at 0.9
min/event overstates it now; use ~0.65 once the wording is fixed, and expect the review share to
grow, not shrink, if rerolls rise.

**batch-5 (n=100), same method:** `batch.json` 13:09:54 → `prompts.jsonl` 13:19:20 (9.4 min — this
batch's prompts were emitted by a generator, not hand-written, yet the draft cost _more_ because I
was re-running it against the double-space and hood defects) → `triage.jsonl` 14:30:11 →
`report.md` 14:31:02. **81.1 min end-to-end = 0.81 min/event, ~74/hour — the slowest of the run**,
and the reason is instructive: GPU render was 13.9 min for all 102 attempts (0.14 min/event), so
the extra ~17 min over batch-4's 62 went to the agent-side loop — the generator round-trips, the
092 image-after-the-row slip I re-checked, and recomputing the ledger's stale counts. The lesson
for pricing: a generator cuts drafting time only if its output is trusted on the first pass; when
I audit it, the saving goes back to the review loop. ~0.65 min/event still holds for a _settled_
clause set; 0.81 is what a batch costs when the wording is still moving.

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

## Owner notes (2026-09-29, after batch-5)

Two decisions reached during the run, both relayed to me through the **coordinator**, not
addressed to me directly. I record them as decisions — the coordinator is the designed relay path
for owner answers in this setup — but I also record how they reached me, so the provenance is
auditable rather than implied. Provenance matters because one of these two I had first written
down wrongly, as a _myth_ that needed correcting; a decision I misremember is worse than no
decision.

- **batch-4's two `ir_night` events that drew no car (`car_break_in` 004,
  `catalytic_converter_theft` 005) stay as they stand.** The question was whether the scene being
  unintelligible without its vehicle should count against them. It does not. Both remain in the
  corpus as drawn, and no triage reason covers an absent prop. Note for the next reader: I first
  tried to support this with "the batch-5 `car_break_in` events drew cars" — **batch-5 has no `car`
  events at all**, because the owner's `--only` list contains no car scenario, so that sentence was
  false and is deleted. The honest supporting fact is inside batch-4 itself: 6 of its 8 `car`
  events did draw one, so absence is seed-dependent, and `car` is not in `cell.artifacts` for any
  of them, so absence is not an undeclared artifact either. Recorded in the `prop-absent` defect
  bullet above.
- **A scenario name wins over the `clothing` attribute** — `hooded_jogger` means a hood is drawn
  even where the spec's clothing is a t-shirt or a vest. **This is the answer to the 18-of-19
  question in my generator bullet above, and the prompts are frozen, so batch-5's images stay as
  they are.** The rule applies forward, so any future generator should write the hood and stop
  treating the mismatch as a defect; the remaining open question is whether the _sampler_ should
  stop drawing non-hood clothing for that scenario, which is the owner's to decide.

The other two things I raised are **still open, deliberately**: whether count drift (11/460, ~3%)
needs a triage reason, and whether the ~56/44 incident-weight is the intended evaluation design.
Neither is mine to settle.

## Batch log

| Batch   | Events | Renders | Rerolls                                  | Failed | What it taught                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| ------- | -----: | ------: | ---------------------------------------- | -----: | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| pilot-1 |     10 |      11 | 1 (`text_overlay`)                       |      0 | Rule 1 rejects role nouns; FLUX drew a date unprompted once; geometry clauses held across all 5 camera positions.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| batch-1 |     50 |      53 | 3 (`text_overlay`)                       |      0 | `text_overlay` confirmed at 3/50 and **all 3 cleared on reroll** — seed-dependent, so reroll is the lever, not the suffix. Geometry clauses, prop-placement and `ir_night`-as-dark-scene promoted to confirmed. Pre-screen false-alarmed on a legitimately dark indoor IR room; pre-camera renders settle every corner mark. One head cropped by a close vantage (no reason covers framing).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| batch-2 |    100 |     103 | 3 (`broken_anatomy` 1, `text_overlay` 2) |      0 | 100/100 ready. `text_overlay` hit again at 2/100 but this time in the **top** corners, so the raw-render check has to cover the whole frame edge; both cleared, making it 6/6 cumulative. **Object-count drift recurred** (019 a second blade, 081 a third person) — ~3/164 events, still no covering reason, and a real scoring risk. First `broken_anatomy` of the run. Confirmed prop-placement at n=68 and `ir_night`-as-dark at n=24. One undeclared face mask on a hard negative (076) — watch it in batch-5.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| batch-3 |    100 |     105 | 5 (`text_overlay` 5)                     |      0 | 100/100 ready, 0 failed. **`text_overlay` hit at 5/100 — the whole reroll budget for a 100-event batch — and all 5 cleared again (11/11 cumulative)**, so the lever still works but the margin is gone: the corpus rate is now 12/269 (4.5%), so a 6-hit batch is ordinary arithmetic and would `fail` an event. **Object-count/person-count drift did not recede: 3 more (020 three people vs two declared, 074 two gun shapes vs one `handgun`, 077 two boxes vs one `package`) — 6/264 cumulative, and two of the three sit on exactly the counts a checker is asked about.** Still no covering reason; owner question stands. Two things settled here: clothing colour is **unscorable, not merely hard, under `ir_night`** (n=30 now), and `check` does **not** compare my camera clause with `cell.camera` — one silent 097 slip caught only by self-audit, so print the camera beside the clause when generating. Throughput 0.63 min/event. Hard negatives 16/16 read benign.                                                                                                                                                                                                                                                                                                                                 |
| batch-4 |    100 |     101 | 1 (`text_overlay`)                       |      1 | 99/100 ready — and **the one loss is mine, not the model's**: 063 (`pet_activity`) rerolled honestly for `text_overlay`, then I judged its attempt-2 still against **another event's spec** (095's `masked_intruder_night` / lake-house living room / `ir_night`) read from memory, called it `wrong_scene`, and `triage` recorded that as final. The image was a correct `garage_mounted` day/clear farmhouse driveway with the dog. See "Agent-side failure". `text_overlay` fell to **1/100 (1%) — the lowest of the run**, and that single hit was on a **day/clear** event, which weakens last batch's "it lives in dark IR corners" theory. **First `prop-absent` cases of the run: 004 `car_break_in` and 005 `catalytic_converter_theft` drew no car at all** (6/8 `car` events had one), both `ir_night`. Count drift did not recede: 4 more (003, 071, 084, 094) → **10/360 events (2.8%)**. Clothing-colour-unscorable n now 96 IR events; 12/12 hard negatives benign (n=43); the batch-3 camera-clause guard held at 0/100. Throughput 0.62 min/event.                                                                                                                                                                                                                                                   |
| batch-5 |    100 |     102 | 2 (`text_overlay`)                       |      0 | 100/100 ready, 0 failed, both rerolls cleared. **The whole batch was five owner-chosen hard-negative scenarios built by a generator (`/tmp/gen_b5.py`) that derives light, vantage, weather, clothing and prop from each `spec.json`**, so rule 1 and the camera-clause guard held by construction (`check` clean first pass). But the generator introduced a defect no earlier batch had: its jogging clause forced a hood onto **18 of 19 `hooded_jogger` events whose declared clothing is not a hoodie** (blue t-shirt, green vest…), manufacturing a clothing mismatch on a _scored_ attribute — an owner wording call, not mine (see the new bullet). Same generator: a drill clause wrote **undeclared motion blur** into 3 no-artifact garage events, and the fog clause names a **lit lamp cone on 3 day/golden events**. `text_overlay` 2/100 (004, 020), both cleared → **corpus 14/475 (2.9%)**. Count drift +2 (066 a second drill body, 084 a second person) → **12/460 (2.6%)**, now 5 person / 4 object / 3 parcel. One camera unit drawn into its own frame (044; the 065 I feared is NOT one). Two of five declared `motion_blur` rendered it faintly. My "image first, row second" rule slipped once (092), caught by the buffer-before-corpus discipline and verified. Throughput 0.81 min/event. |
