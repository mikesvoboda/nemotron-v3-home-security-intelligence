# The funded clip measurement, pre-registered (ISS-003 acceptance shape, 2026-10-07)

The pre-registration OD-5's cell says the funded clip experiment needs before any GPU spend
("the experiment still needs its own pre-registration and spend go-ahead", 17 Intake log
2026-10-05). It fixes, **in writing and before any number exists**, what the two arms are,
which clips they run on, what gets computed, and what it costs. The owner's signature on
§7 is the spend go-ahead; nothing in this document is a route decision — measuring
frame-burst is within ISS-003's acceptance; adopting it is the owner's ruling (C1).

The question, one line: **what does a clip buy over a still, measured as
arm (a) 4-frame bursts through `VlmClient` versus arm (b) a video-capable engine on the
same clips**, with S2/S3 and Wilson intervals, per-clip latency, and peak VRAM against the
S1 bar — ISS-003's acceptance, verbatim in §2.

Why the question is worth the spend, three numbers from
[`docs/research/2026-10-07-iss086-s3-ceiling/`](../2026-10-07-iss086-s3-ceiling/README.md)
(PR #6829, merged 2026-10-07): the single-still ceiling is 73.4–76.3% across 15 arms
(74.7% shipped); A-group recovery — the loiter/case/door-check scenarios time-revealed
behavior is exactly about — is 3/64 for the shipped path and never exceeded 7/64 across
the sweep; and the true-twin pairs the rubric made _worse_ are the time-revealed ones
(`loitering` vs `neighbor_passing` 0.506→0.333). No prompt moved that group. The clip lane
is the only untested input change under it.

## 1. Status and gates

Draft, 2026-10-07, agent-authored; **unsigned**. It binds once the owner signs §7, and it
can only be amended by a dated addendum in this folder — never silently, and not at all
mid-run. A campaign stop condition: a Phase 1e surprise that changes this design forces
re-pre-registration _before_ any arm runs.

| gate                 | who         | lands where                                            |
| -------------------- | ----------- | ------------------------------------------------------ |
| 0a this document     | owner signs | this file, §7                                          |
| 0b harness (ISS-037) | agent       | PR #6831 (pending merge; merge is the owner's)         |
| 0c ISS-033 / ISS-005 | agent       | behind their own tests, before any arm run             |
| 1e/1f probes         | owner signs | fenced `agent-gpu` windows, named in §7                |
| 2 render             | owner       | renderer window (H3 neighbors the flagship: owner GPU) |
| 3 blind audit        | owner       | ISS-038/OD-15 instrument; binds: \*\*no clip number is |
|                      |             | published before it\*\*                                |
| 4 the measurement    | owner       | the §7 window, on the audited subset only              |

## 2. What is fixed (the acceptance, verbatim, then what each word means here)

ISS-003 acceptance (`docs/vss-integration/17-action-plan.md`): "A dated decision doc with a
measurement: the same N>=60 clips scored (a) as 4-frame still bursts through `VlmClient`
and (b) through a video-capable engine, reporting S2/S3 with Wilson intervals, per-clip
latency, and peak VRAM against the S1 bar; includes whether the llama.cpp pin supports
video (tested, not assumed)…"

- **Arm (a) — frame-burst.** `export vss --sequences 4` (ISS-037, PR #6831) samples each
  READY clip's ok-triaged mp4 at fixed fractions `(0.10, 0.36, 0.62, 0.90)` into a 4-frame
  set; `replay --frames burst --with-sequences` sends all four with `frame_detection_ids` —
  the declared subjects and props at their frame times. Burst is fixed as the arm-(a) shape
  because ISS-003's acceptance names "4-frame still bursts": every frame reaches the wire,
  so the VLM's own key-frame choice (what selector mode measures, ISS-005) is not in the arm.
- **Arm (b) — video-native.** The strongest available video-capable path on this machine at
  run time, served in a fenced `agent-gpu` container (`vss8-*`), pinned to its image digest
  and weights sha256 before the run. Candidate set: Qwen3-VL with native video under vLLM,
  else Cosmos's video path — both are engines the VSS stack's own surface audit treats as
  video-capable (`docs/vss-integration/09-audit-integration-surfaces.md:154`: fixed-rate
  `VLM_VIDEO_PRUNING_RATE` covers Nemotron Nano VL, Qwen2.5-VL, Qwen3-VL and Cosmos3). The
  choice is made once, before the run, and recorded with its version; never swapped between
  arms — same clips, same truth, both arms.
- **Same N>=60 clips** — the audited set of §3, identical membership in both arms.
- **S2/S3 with Wilson intervals** — `synthbench score` (SCORE_VERSION 5), MIN_N = 10 rule,
  plus the ISS-043 tooling: scenario-cluster bootstrap intervals beside Wilson
  (`backend/evaluation/cluster_stats.py` `cluster_bootstrap`), exact McNemar on the paired
  discordants (`mcnemar_exact`), and the noise-floor spread (`noise_floor`).
- **Per-clip latency** — client-side seconds per item from the replay, median and p95.
- **Peak VRAM against the S1 bar** — sampled peak during the arm run; the bar is S1 at most
  20.4 GiB (register ISS-046 evidence, from `docs/plans/2026-09-23-vss-gaming-gpu-ledger.md`
  :423, the A5500 resident-set basis). Arm (b)'s engine is the likely bar-breaker; that is a
  finding, and OD-8's gaming-GPU-acceptance scope stays the owner's, not this doc's.
- **llama.cpp b7972 video support: tested, not assumed** — Phase 1e, first probe, §5.

## 3. The clips: supply, render plan, audit, frozen composition

**Supply, re-counted 2026-10-07 from every row of
`/synthbench/corpus/tierb-v0/clip-index.jsonl` + each ready/prompted event's `spec.json`
(ISS-093's 2026-10-03 read still holds).** 459 clip events by latest status: **ready 164**
= benign 144 + incident 17 + ambiguous 3; **prompted 205**, all incidents — threat 196 +
suspicious 9; rendered (awaiting triage) 10; failed 80. 481 render attempts on record
(benign 401 + incident 59 + ambiguous 21), one mp4 per attempt, re-rolls included.

**The composition is the risk, and it is sharper than "the backlog is weapon-heavy".**
Today's 17 ready incidents are _entirely_ the time-revealed group — `loitering` 5,
`tailgating` 5, `trying_car_doors` 4, `peering_into_windows` 2, `casing_with_phone` 1 — and
nothing else. The 205-event backlog that could reach N≥60 is the opposite population: seven
weapon/threat scenarios at 19 (`firearm_visible`, `knife_visible`, `forced_entry`,
`fire_or_smoke`, `package_theft`, `child_alone_at_pool`, `masked_intruder_night` = 133) and
seven at 9 (`vandalism`, `fence_climbing`, `blunt_weapon`, `person_down`,
`catalytic_converter_theft`, `car_break_in`, `pool_trespass` = 63) — and **only 9 of the 205
are suspicious** (`trying_car_doors` 3, `peering_into_windows` 3, `casing_with_phone` 2,
`loitering` 1). `tailgating` has no backlog at all; `package_theft`, an A-group scenario in
#6829's recovery table, has 0 ready but 19 prompted. So at current supply the corpus is 100%
time-revealed at n=17, below the acceptance's N≥60, and reaching N≥60 from the backlog
dilutes it to roughly 24 of the corpus's ~60 incident clips (F1's projection); `tailgating`
stays untested by clips either way. And crossing motion fails to render
at elevated rates (`docs/synthbench/h3-prompt-notes.md:32`: runner crossing 0/13 ready,
walker crossing 4/9, working-in-place 24/26), so the survivor set skews in-place even within
a scenario (ISS-038). The render plan is fixed **now**, before any clip renders, so nobody
discovers a thin slice after a number exists:

**Freeze F1 — render allocation (Phase 2, owner's window; the supply-target ruling stays
ISS-093's, this is the proposal it rules on).** Render **148 attempts** from the prompted
backlog: **all 9 suspicious** (every prompted suspicious clip that exists), then **139
threat proportional to backlog size** — the seven 19-count scenarios at 13 each (91) and
the seven 9-count at 6 each (42) = 133, with the 6 residual going, one each, to six of the
19-count scenarios in clip-index order — so six scenarios render 14 of their 19, the seventh
13 of 19, and every 9-count scenario 6 of its own 9. Within a scenario,
render in clip-index order — no cherry-picking, no substitution of one scenario for another.

- **Yield basis, measured rather than assumed.** Incident events have consumed 59 render
  attempts to produce 17 ready (27 attempts on 9 failed events, 10 attempts awaiting triage)
  = **17/59 ≈ 29% per attempt**; benign ran 401 attempts to 144 ready ≈ 36%. 43 new ready
  incidents (to reach 60 with today's 17) therefore project to 43/0.29 ≈ 148 attempts at the
  incident basis, ≈ 120 at the benign basis. F1 takes the worse basis. Motion-bearing
  scenarios may do worse than either, which is what the h3 numbers above say; that is
  F3's disclosure's job, not a reason to re-plan mid-window.
- **The A-group slice is capped by supply, and it is pre-registered here.** A-group =
  #6829's six time-revealed scenarios. At 29% yield the 9 suspicious attempts project ≈ 3
  ready and `package_theft`'s 14 attempts ≈ 4 more, so the time-revealed slice lands near
  24 of ~60 incident clips (17 ready now + ≈7 new; `tailgating` has no backlog to render) —
  versus 64 A-group items on the stills. The A-group comparison is therefore reported as a
  **pre-registered small-n slice** (direction and n, no bar), and the paired
  depth-1-vs-depth-4 control of §4 is the statistic that speaks to it on the same items.
  Growing the A-group itself — new prompts or the H3 scripted triplet renders — is ISS-093's
  supply ruling and the owner's renderer window, not this plan's.
- **Audit rejects are not backfilled silently.** 148 targets ≥60 _ready_; the ISS-038 audit's
  rejection rate is unknown before it runs, so if the audited corpus falls under 60 the
  owner's choices are a dated addendum (§1) opening one more render window, or proceeding at
  N<60 with the limitation named (F4) — never re-selecting clips after seeing which survived.

If the owner's ISS-093 ruling sets a different supply target, F1's proportions stand and its
totals move.

**Freeze F2 — benign supply.** The S2 denominator draws from the 144 ready benign clips,
stratified by group (benign / hard_negative) and lighting — ISS-038's instrument requires
the stratification, and the audit sample sizes the benign half to mirror the incident half
(so the burst-vs-still contrast has power on both labels).

**Freeze F3 — motion-type coverage.** The clip specs carry no motion-type field (checked:
nothing to stratify on), so the Phase 0d audit instrument records a **motion question** per
audited clip (alongside scene / prop / people / conditions), and the survivor-bias
disclosure — ready and failed by scenario, computed from `clip-index.jsonl` — ships beside
every clip number.

**Freeze F4 — the audited subset is the corpus.** The audited set: ready incident clips
(plus the mirrored benign half for S2) drawn by the ISS-038/OD-15 instrument — blind,
stratified by group and motion type, owner-audited. Both arms run on the audited clips only.
Clips the audit rejects leave the corpus before any arm runs; the audit's answers join the
truth ledger, never the prompt. **If the audit leaves fewer than 60, the acceptance's
"N>=60 clips" is not met, and the decision doc names that as its own limitation** — the
acceptance sets a floor on the measurement's size, and a run that misses it is reported as
missing it rather than padded.

**Freeze F5 — the split.** `splits.json` covers the stills' 30 scenarios and scenario is
the arm unit, so a clip inherits its scenario's arm. Read rule: dev-scenario clips are
exploratory (reported, may motivate an addendum); holdout-scenario clips are confirmatory.
Every clip number carries #6829's holdout-skew caveat unchanged — on stills the holdout arm
read S3 32.8% against dev 47.5% purely by composition.

## 4. What is computed on every arm

Per arm: S2 (labeled-benign scored medium+), S3 (incidents at or above their floor; both
bands reported, midpoint primary per OD-2's existing reading — no new floor choice rides on
this run), refusals by error class, verdict mix, per-clip latency median/p95, peak VRAM.
Paired statistics (both arms on the same clips): `identical` {k, n} (ISS-087), McNemar
exact on bar-level discordants, ΔS2/ΔS3 with scenario-cluster bootstrap CIs (ISS-043).
Slices: per frames-fed bucket (1 vs 4 — the same clips' stills run in the same score as the
in-corpus control, via ISS-037's frames slice), per motion type (F3), per arm-of-split (F5),
and per A-group-vs-threat (F1's small-n cap binds it: direction and n, never a bar).
OD-26's wording binds: no arm is "the winner" inside the noise floor; the decision doc
reports the spread before any pick.

**The control that costs nothing and answers the confound.** Arm (a)'s clips already sit in
the export as stills: the same clips scored at depth 1 (stored mode, one replay) against
depth 4 (burst) on identical items. The register requires this control: doc 22's probe 1 ran
"4 ordered clip frames vs the single still, same prompt" and got **null — 0/17 hits either
way** (`22-prompt-research-and-probes-2026-10-04.md:30`), under the pre-OD-29 prompt, and the
Intake entry of 2026-10-05 binds that any pre-registration carries a 1-frame control "or it
re-runs a known-null while moving input and operating point together." This run moves the
operating point too (the shipped post-OD-29 rubric), so the control is in-run and paired, not
a re-citation of the old null. If burst ≈ still on the A-group, the honest conclusion is "4
frames at fixed fractions is not yet what time-revealed behavior needs" — and ISS-003 gets
decided on arm (b) — not that clips are worthless. This is the comparison ISS-086's ceiling
says to run before anything else, and it needs no second engine.

## 5. Phased probes (what runs before the spend, and what it can still change)

- **1e, first, decisive: does b7972 take video at all?** The pinned
  `ai/vlm/Dockerfile` `LLAMA_CPP_REF=b7972` serves images; whether that build's served path
  accepts a native video input is untested [?]. One clip, one fenced container, minutes. A
  negative kills arm (b) as a llama.cpp feature and makes it the vLLM/second-engine question
  of §2 — which changes the §7 spend, so it runs first and its result lands in the register
  either way.
- **1f, smoke, zero corpus claims:** burst-path frame extraction on 3–5 ready clips sizes
  the per-clip token and latency cost before any window is booked. No number from 1f is
  quotable as a result.

## 6. What this pre-registration does not decide

No route is adopted (C1: the frame-burst arm is evidence FOR the decision doc). No OD is
ruled: OD-2's remedy choice, OD-5's lane, OD-8's acceptance scope and ISS-093's
supply-target ruling all stay the owner's; F1 is a proposal inside ISS-093's open ruling,
not a substitute for it. No clip bar exists: the S2/S3 bars name labeled items, not media
types; if a future bar names clips, that is a spec revision (OD-3's lane). No relabelling:
#6829 showed relabelling could be scenario-selectable; that is a caution, not a license.

## 7. The spend line (owner signature block)

| #   | window                 | size, with arithmetic                                            | status         |
| --- | ---------------------- | ---------------------------------------------------------------- | -------------- |
| 1   | Phase 1e (b7972 video) | fenced container, ≤15 min                                        | proposed       |
| 2   | Phase 1f (burst smoke) | fenced container, ≤30 min, ≤5 clips                              | proposed       |
| 3   | Phase 2 render         | F1's 148 attempts (incident 29%-yield basis; benign basis would  | owner's window |
|     |                        | size it ≈120): ~330 s/clip measured (328.7 s, three clips varied |                |
|     |                        | 1.7 s — `docs/benchmarks/synthbench/clips-probes.md`), one clip  |                |
|     |                        | per `clip render` call (CALL_LIMIT_S 570): ≈13.5 h worst case,   |                |
|     |                        | ≈11.0 h at the benign basis                                      |                |
| 4   | Phase 4 measurement    | ≈60 incident + ≤60 benign mirrored (F2) ≈ up to 120 items;       | owner's        |
|     |                        | arms (a) + still control are image calls at the 8B dogfood       | go-ahead       |
|     |                        | median 5.76 s/item ≈ 2×12 min server time; arm (b) video cost    |                |
|     |                        | is the open size —                                               |                |
|     |                        | 1e/1f bound it (token load scales with native video, not with    |                |
|     |                        | our 4 frames) before the window is booked                        |                |
| 5   | Peak-VRAM sampling     | free (same windows)                                              | included       |

Signature lines (owner): probe windows (1–2) \_**\_ ; render window (3) \_\_** ; measurement
go-ahead (4) \_**\_ ; date \_\_\_\_** . Signing §7 spends nothing by itself — each window opens
on its own line.
