# `vlm_assess` prompt review and a gated prompt-experiment plan (2026-10-04)

**Status:** proposal **[A]**, agent-authored, not ratified, revised after two Codex adversarial
passes (section 9). It asks the owner for two staged approvals and one semantics confirmation
(sections 1 and 4).
Nothing here changes code, the contract or the bars. Every arm below is a **development arm, not a
holdout**: the author read the `tierb-v0` taxonomy before writing the candidate prompts.

**Reviewers, read first.**

- **Code is cited at main `6b33a2af`.** Later commits can move the cited lines, so read code with
  `git show 6b33a2af:<path>`.
- **The sweep evidence is on PR #6787** (`origin/docs/vss-sweep-report`, tip `be389adb`). Read it with
  `git show origin/docs/vss-sweep-report:<path>`.
- **The off-repo evidence is the eval store and the rubric arm's files.** The eval store is
  `/agents/agent-vss5/gpu/out/sbroot/eval/tierb-v0/eval.sqlite` (sha256 `2e4181a2…fc48`). The rubric
  arm's files are under `/agents/agent-vss5/gpu/out/experiments/{2026-10-03-rubric-logprob,model-sweep}/`.
- **Scripts (off-repo):**
  - The section 2 re-derivations are `an1.py`-`an8.py` and `render.py` in
    `/agents/agent-vss5/gpu/out/experiments/2026-10-04-stage1/rederive/`. They are Python, standard
    library only, and read a `mode=ro` copy of the store (see the README there).
  - The stage-1 kit (shim, replay, probes, analyses, `run_stage1.sh`) is the directory above it.

**Markers.**

- **[V]** read in code at `6b33a2af`, or in llama.cpp source at the named tag.
- **[V-store]** re-derived by the author from the eval store or the logprob files, which are
  themselves [A] artifacts.
- **[C]** cited doc; **[A]** agent artifact not re-derived; **[?]** unverified.

**Runs.** Item counts: 209 benign (64 plain, 145 hard negatives) and 241 incidents. The three
incident groups are the sweep's: **A** stranger or intent, 64; **B** context risk, 82; **C** object
cued, 95 (report.md:95).

| Name    | Build    | Prompt  | eval_run_id | S2     | S3      | A-group | AUROC A vs hard negatives | AUROC A vs plain benign |
| ------- | -------- | ------- | ----------- | ------ | ------- | ------- | ------------------------- | ----------------------- |
| `ctl`   | `b11376` | shipped | `f1faa819…` | 21/209 | 94/241  | 0/64    | 0.314 [0.189, 0.463]      | 0.507 [0.351, 0.654]    |
| `arm A` | `b7972`  | shipped | `4a94b256…` | 18/209 | 88/241  | 2/64    | 0.410 [0.258, 0.581]      | 0.523 [0.353, 0.680]    |
| `arm B` | `b7972`  | rubric  | `696c7168…` | 34/209 | 105/241 | 3/64    | 0.352 [0.217, 0.495]      | 0.713 [0.590, 0.823]    |

S2, S3 and A-group counts for arms A and B match ISS-086's update. The AUROC columns are [V-store]:
the brackets are 95% class-stratified scenario-bootstrap intervals (4,000 resamples, seed
20261004; 6 A scenarios against 5 hard-negative or 7 plain-benign scenarios; `an8.py`). With so few
clusters these intervals are illustrative, not decisive.

## Status (2026-10-04, evening) [A]

- **Stage 1 approved; first run stopped.** The owner approved stage 1 and chose to screen it on
  vss5's idle `probe8b` server (the shipped 8B on `b11376`), since the host shell holds no
  `agent-gpu` session token.
- **Run 1 is answered [V-store]** (304 of R0's raw replies):
  - The key order is criteria, description, provenance, reasoning, risk_score, summary, verdict
    on 304/304.
  - The model's top raw token at the verdict slot is `"REAL"` on 304/304. The chosen enum token's
    median raw logprob is −18.5.
- **R0 matches the control solo** (the shipped prompt, logprobs on): identical to the `b11376`
  control on 305/305 items. The server is equivalent, and requesting logprobs does not change
  answers.
- **Concurrency changes greedy outputs [V-store].**
  - **What happened:** vss5's probe 4 began sending to `probe8b` at about 19:07 UTC, so both slots
    were busy. R0 then differed from the control on 5 of 13 items (e.g. 10 → 75, 60 → 85). It was
    stopped at 19:14 UTC.
  - **Why:** a 2-slot llama.cpp server decodes concurrent requests in one batch, and batched greedy
    decoding differs from solo decoding.
  - **For experiments:** every replay must run solo. The shim now carries a guard: it waits for an
    idle server, then checks that the token counters moved by exactly the call's own usage.
  - **For production:** `ai-vlm` runs `PARALLEL=2`, so two concurrent camera batches can change
    each other's scores. The "temperature 0 is deterministic, 450/450" reading (README section 3,
    OD-24) comes from sequential replays.
  - **Scope:** observed on `b11376`; `b7972` is unverified. A register entry is pending,
    coordinated with vss5, which edits the same docs.
- **Stage 1 is handed to vss5** at the owner's direction. The handoff was
  `docs/plans/2026-10-04-stage1-handoff-to-vss5.md` in vss5's clone, untracked (deleted on the
  owner's direction 2026-10-05, after stage 1 ran; its unique §0 concurrency finding survives in
  the kit's `RUN-NOTES.md` and doc 22 section 2). The kit and the
  `results/REPORT.md` are in `/agents/agent-vss5/gpu/out/experiments/2026-10-04-stage1/`.
  vss5 serves a dedicated container: `b7972` paired with arm A if its image remains, otherwise
  `b11376` paired with the control.
- **Related independent work:** vss5's draft doc 22 (untracked in its clone) reports 37-event prompt
  probes. Wording moved the operating point but not the discrimination, and a cue taxonomy fired on
  flashlight and face-covering benigns. That bears on stage 2; reconciling the two is the owner's
  call.

## 1. The decision requested

**Two approvals, in two stages.**

1. **Stage 1, now: about 1 GPU hour through `agent-gpu` on `b7972`.** It covers run 1 and the
   fields arm with its checks (runs 2, 2b and 2c). These fix the verdict defect (section 2,
   finding 3) whether or not prompts can lift S3, so they do not wait on anything below.
2. **Stage 2, after a precondition:**
   - **Precondition:** the owner's blind observability audit of about 90 stills, roughly 30-45
     minutes of owner time (section 5, run A0).
   - **Then:** about 2-3 GPU hours for the cue and rewrite arms (runs 3-6), run as a **capped
     exploratory screen**.

**Not requested:** any contract change, a model change, a sweep, or shipping a prompt from stage 2.

**What stage 2 can and cannot conclude.** It ends in one of three predeclared outcomes:

- **advance** to independent confirmation;
- **inconclusive;**
- **budget stop.**

With 31 scenarios it **cannot establish that prompts are futile**. A budget stop records where the
money ran out, not that the prompt lever is exhausted (section 5). The S3 question goes to OD-2 and
ISS-086 (multi-frame input, relabelling, or the bar) on the evidence, not by default.

## 2. Findings

1. **Hard negatives outscore stranger-or-intent incidents; against the real look-alikes the
   shipped model sits at chance.** (Corrected after Codex pass 2. The first revision said "inverted,
   which no calibration can fix", which overstated the evidence.)
   - **Against hard negatives** (an S2 contrast), the scenario-bootstrap interval excludes 0.5 on
     the `b11376` control (0.314 [0.189, 0.463]) and on arm B (0.352 [0.217, 0.495]). It does
     **not** exclude 0.5 on the shipped build: arm A reads 0.410 [0.258, 0.581] [V-store]. For
     contrast, C vs hard negatives is 0.94-0.98.
   - **Against the plain-benign look-alikes** (delivery, passer-by, resident: the S3 contrast that
     matters), the shipped model is at chance: 0.523 [0.353, 0.680] on arm A. The rubric raised it to
     0.713 [0.590, 0.823]. The paired gain is +0.190 [−0.015, +0.380], suggestive but not
     established [V-store].
   - The pre-grammar first-digit probability mass for a high score orders A vs hard negatives the
     same way as the integer score (AUROC 0.309 on arm A, 0.290 on arm B; no intervals computed)
     [V-store]. Logprob re-reading shows no hidden headroom.
   - Every hard-negative false alarm cites an appearance cue (hood, mask, flashlight or tool): 20/20
     in ctl, 33/33 in arm B. The screen is crude, and the cues also appear in 75% of correctly
     scored hard negatives, so they are necessary, not sufficient [V-store].
   - The ctl false alarms are `hooded_jogger` 10, `power_tools_at_night` 7, `flashlight_neighbor` 3
     and one `neighbor_passing` [V-store].
   - **S2 and S3 are separable problems.** On arm A every score from 30 to 59 is a false alarm:
     remapping that band to 29 gives S2 10/209 (4.8%) with S3 unchanged at 88/241 [V-store;
     Codex's counterexample, re-derived]. That is an in-sample remap that deletes the medium band,
     not a fix. It shows S2 sits near its bar on this corpus while S3 does not.
2. **The model names the activity and assigns a benign purpose. Whether the still supports the
   incriminating purpose is not established.**
   - Examples, ctl:
     - `B-batch-1-019` (package theft): "consistent with a delivery or pickup".
     - `B-batch-1-013` (casing): "take a photo or video of the snowy lakeside scene".
     - `B-batch-1-012` (car doors): "possibly unlocking".
   - Benign-explanation words appear in 43/64 A-group replies under the shipped prompt and 64/64
     under the rubric [V-store, crude regex].
   - **This is not evidence of a reasoning error.** Seeing someone carry a package does not
     establish theft. The taxonomy gives `delivery_driver` and `package_theft` opposite labels for
     a person holding a package (`tier_b_v0.yaml:138`, `:304`; ISS-086) [C]. The replay supplies no
     identity evidence. The owner's 60-still audit checked scene, people and conditions, not whether
     intent is visible.
   - The prose cannot separate three causes: wrong risk reasoning, missing information, or a still
     whose declared label it does not show. **Prompt-addressability is a hypothesis** until the
     blind audit (run A0) separates the stills where the cue is visible from those where it is not.
3. **The verdict is a grammar artifact.**
   - At the `verdict` value slot the model's top pre-grammar token is `"REAL"` on **450/450** items
     in both arm A and arm B. This is the prompt's own phrase.
   - The enum token the grammar forces has a median raw logprob of −15.5 (arm A) and −19.3 (arm B).
     `"REAL"` is grammar-illegal yet appears in `top_logprobs`, which shows the capture is
     pre-grammar [V-store].
   - The prompt never names `confirmed`/`rejected`/`uncertain`. 433/450 verdicts are `confirmed`.
   - In production the verdict gates the `rejected` clamp (`vlm_analyzer.py:285-294`) and notify.
4. **The framing is verification; the scale is unused.**
   - The summary parrots "CORRECTLY IDENTIFIED" in 358/448 ctl replies; with one clause changed
     (arm B) it does so in 8/450.
   - Criteria are named after _output fields_ in 290/448 replies.
   - The medium band (30-59) holds 16/448 replies (arm B: 48/450). Scores sit on a round-number
     lattice [V-store].
   - With `Detections: []` the model answers `uncertain`/0 on most stills (errata 16:318-321) [C].
5. **The emission order is alphabetical, not the prompt's order.**
   - The contract generator sorts keys (`scripts/gen-ai-contract.py:659`), and the client preserves
     that order (`vlm_client.py:205-218,433-437`) [V].
   - llama.cpp parses the body as `ordered_json` (b7972 `tools/server/server-common.h:16`). It
     builds objects in `properties` order and discards `required`'s order in an `unordered_set`:
     - b7972 `common/json-schema-to-grammar.cpp:15,620-644,855-866`;
     - b11376 `common/json-schema.cpp:136-152`, `json-schema-to-grammar.cpp:897-910`,
       `common/json.cpp:14` [V].
   - The model therefore writes `criteria{evidence,name,passed}` → `description` → `provenance` →
     `reasoning` → `risk_score` → `summary` → `verdict`.
   - **Reasoning precedes the score** ("score before reasoning" is refuted), but every pre-score
     field is written under verification framing.
   - This upgrades ISS-012's [?] to source-verified; one served call would make it empirical.
6. **Output budget waste.**
   - `criteria` is 37% of output characters (ctl). Its `evidence` is the class name in 480/1,156
     entries (arm B: 1,084/1,201) [V-store].
   - The prompt asks for `provenance` "from the served model's own reported identity", which the
     prompt never supplies. The client then overwrites the field (`vlm_client.py:549-551,886`) [V].
   - The eval prompt is 263 counted tokens in a 16,384-token slot: input is cheap, output is not.
7. **The context lines are inert on this corpus.** Specialists are mentioned 0/450 times, zones ≤1,
   crossing ≤2 and household ≤14 [V-store]. The eval path sends `{}` for both specialists and
   household (`vlm_replay.py:123-131`) [V].
8. **The eval prompt contains a dangling sentence.** Oracle rows carry no bbox, yet `_box_guidance`
   renders "A row's bbox is [x, y, width, height] in pixels of its 1920x1080 source frame…"
   (`vlm_client.py:651-657`). The author confirmed this by executing the renderer [V].

**What the S3 bar requires.**

- S3 ≥ 90% means 217/241 hits. B + C cap at 177, so the A group needs **≥ 40/64 even with B and C
  perfect** [V-store, items.csv floors].
- 46 of the 64 A items have a high floor (60).
- 132/241 incidents need a critical score (≥ 85): all of C, plus `child_alone_at_pool`, `person_down`
  and `blunt_weapon`.
- **A prompt alone probably cannot reach S3 on this corpus. Realistic goals:**
  - a verdict the model chooses;
  - a non-inverted ranking;
  - S2 moving toward 5%.

## 3. Hypotheses (prompt-addressable), ranked

| #   | Hypothesis                                                                                                         | Primary test                                                                                                                                  |
| --- | ------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| H0  | **Competing explanation:** many A stills lack the information (input insufficiency), so no prompt can recover them | Run A0's blind audit; then compare stage-2 gains on observable vs indeterminate stills                                                        |
| H1  | The score responds to appearance and aggression, not behaviour or location (finding 1)                             | Cue arm (run 3): paired S2 on hard negatives; S3 on the observable A subset                                                                   |
| H2  | When the still shows no purpose, the model supplies the commonest benign one (finding 2)                           | Cue arm (run 3): observable A subset vs the plain-benign look-alikes; S2 on delivery and resident                                             |
| H3  | Verification framing fills the pre-score context (findings 3-5)                                                    | Fields arm (run 2)                                                                                                                            |
| H4  | No anchors, so the scale is used as a binary                                                                       | Arm B: anchors moved A vs plain benign from 0.523 to 0.713, but triggered appearance false alarms; arm (a) tests anchors without the triggers |
| H5  | Field order                                                                                                        | Raw call (run 1), then the wire-reorder arm (run 5)                                                                                           |
| H6  | Empty context reads as "no evidence" (evidence against: finding 7)                                                 | Ablation (run 6), expected null                                                                                                               |
| H7  | Criteria crowd the 1,024-token budget (an S5 and latency issue, not calibration)                                   | Fields arm output length and truncations                                                                                                      |

H1, H2 and H4 are only testable where the still shows the cue. H0 says how much of the A group that
is. Until A0 runs, a stage-2 result on the full A group cannot separate prompt failure from missing
information.

## 4. Candidate prompts

### (a) Minimal diff

This replaces only the first paragraph of `_render_prompt` (`vlm_client.py:544-551`). The context
block and box guidance stay byte-identical, except that the pixel sentence renders only when a row
has a box.

```text
You are the verification expert for a home security camera. The detections below were produced by an object detector on the attached frame(s). Do two separate things: decide whether the detections are real and correctly identified (verdict), and score how much the scene needs the homeowner's attention (risk_score 0-100). A correct detection says nothing about risk.
Base the score on what people and vehicles do and where they are; clothing, face coverings, darkness and tools in use are neutral. A purpose counts only when the frame shows it.
Bands: 0-29 low = activity the frame explains (residents, visible deliveries or work, people passing on the street, animals); 30-59 medium = a person on the property with no shown purpose, or one who lingers or watches the property; 60-84 high = someone entering, handling, taking or damaging what is not visibly theirs; 85-100 critical = someone hurt or in immediate danger, a weapon used or pointed at people, a break-in under way, or fire.
Write the JSON fields in this order: criteria (one per object type in the rows: name = that object_type, passed = true if it is real and correctly identified, evidence = a few words), description (what the frame shows), provenance (write "n/a" for engine and model_id), reasoning (what each person or vehicle is doing and where, ending with the band), risk_score (a number inside that band), summary (one sentence), verdict ("confirmed" = at least one detection is real and correctly identified, "rejected" = none is, "uncertain" = the frame cannot tell).
```

**Scope:** prompt-string only. The fields are listed in the order the grammar already emits, and
`"n/a"` passes `min_length=1`.

**Two wording choices exist because of the first Codex pass (section 9).**

- **Criteria are per object type, not per row.** That bounds output by the number of distinct
  classes rather than by batch size.
- **`rejected` means "no detection is real".** In production `rejected` clamps the score to ≤29 and
  never notifies (`vlm_analyzer.py:285-294`, `:789-790`) [V]. "Rejected if any row is wrong" would let
  one mislabelled extra row silence a real incident. This is a **product-semantics choice** about
  what gates alerts, carried in prompt text, so the owner should confirm it.

### (b) Rewrite

Images come first, as today.

```text
You triage events from a home security camera for the homeowner. An object detector found the candidates under Detections on the attached frame(s).

Camera: {camera_id}
Time: {time}
[Zones: {zones} (crossing: {crossing})]            <- only when zones exist
{box guidance, verbatim}
Detections: {rows}
[Household context: {json}]                        <- only when non-empty
Specialist outputs (faces/plates/re-ID; these are detector evidence, not yours to invent): {json, or "none available"}

Job 1, verification: for each object type in the rows, decide whether that object is really in the frame and correctly labelled.
Job 2, risk: decide how much the scene needs the homeowner's attention. Answer four questions:
- Who: a known person or household vehicle (named in the specialist lines), someone doing a visible job, or an unknown person?
- Where: street or sidewalk, on the property, at a door, window, gate or vehicle, or inside?
- Doing what: passing, working, waiting or watching, handling a door, window, gate, vehicle or someone else's belongings, going in, carrying things away, damaging something, hurting someone, or hurt themselves?
- When: night makes an unknown person's presence more notable; on its own it adds nothing.
A purpose counts only when the frame or a specialist line shows it: a uniform, a marked vehicle, a task in progress, a household match. Otherwise the purpose is unknown. Clothing, face coverings, darkness and tools in use are neutral.
Pick the highest band that fits:
- critical (85-100): someone hurt or in immediate danger, a weapon used or pointed at people, a break-in under way, fire.
- high (60-84): someone goes in, handles, takes or damages what is not visibly theirs.
- medium (30-59): an unknown person on the property with no shown purpose, or one who waits, watches or lingers near a door, window, gate or vehicle.
- low (0-29): everything else: residents, visible work or deliveries, people passing, animals, an empty scene.

Write the JSON fields in this order:
- description: what the frame shows, in one or two plain sentences.
- criteria: one entry per object type in the rows; name = that object_type; passed = true if real and correctly labelled; evidence = a few words.
- verdict: "confirmed" if at least one detection is real and correctly labelled, "rejected" if none is, "uncertain" if the frame cannot tell.
- reasoning: answer who, where, doing what and when, then name the band.
- risk_score: a whole number inside that band.
- summary: one sentence for the homeowner.
- provenance: write "n/a" for engine and model_id.
```

**Scope:**

- **Prompt-string only:** all of the text, plus the conditional lines.
- **Client wire shaping, no contract change:** reorder `properties` in `_wire_schema()` to the
  listed order. It needs ISS-012's order-pin test and a passing enforcement probe; it can be tested
  today via the shim.
- **Contract changes (owner decisions, deferred):**
  - drop `provenance` from the wire (ISS-012);
  - constrain criteria names to the row classes;
  - add a `band` enum before `risk_score`, which contradicts spec §3's "the model never emits a
    level" (`vlm_verdict.py:11-12`).

### Benign-side guardrails (both texts)

- Appearance cues are neutral, in positive form. This targets 20 of the 21 ctl false alarms.
- "A purpose counts only when shown" is symmetric: it blocks invented menace and invented innocence
  alike.
- Low names visible work, deliveries and people passing.
- "Danger" and "threat" framing is avoided. Explicit danger prompts raised Qwen3-VL-8B false alarms to
  0.17-0.18 vs 0.04-0.10 for neutral prompts (SPRINT, `2026-10-04-video-question-research.md:295`)
  [C].
- Per-type verification stays, so an event whose detections are all false still reaches the
  `rejected` clamp, while one wrong extra row cannot clamp a real incident.

**Known S2 risk.** The medium rung "unknown person with no shown purpose" can catch
`resident_arrival` and `flashlight_neighbor`, because the eval supplies no identity evidence.

### Leakage control

- **Bands are anchored to the homeowner's action ladder:** low = log, medium = review later,
  high = notify now, critical = notify and get help.
- **Cue classes follow `backend/services/risk_rubrics.py`**, which was added 2026-01-26, before the
  taxonomy (2026-09-28) [V]: "lingering" = moderate; "testing doors, vandalism, theft" = high;
  "weapon visible, violence" = critical.
- **Scenario nouns are avoided**, but the author read the taxonomy, so both texts remain
  development-only.

## 5. Runs, cheapest first

**Shared conditions.**

- 450 stills, temperature 0, `b7972`, through the shipped `VlmClient`.
- A transport shim generalised from
  `/agents/agent-vss5/gpu/out/experiments/2026-10-03-rubric-logprob/replay_exp.py`, with
  `EXP_LOGPROBS=1`. The shim rewrites the text part and, for run 5, reorders the
  `vlm_verdict`-named schema's `properties`. The probe schema is left alone.
- Paired against arm A. About 20-40 minutes of GPU per arm.

**Each arm reports:**

- S2 and S3 with Wilson intervals, **both raw and production-effective.** Replay stores the model's
  raw score (`vlm_replay.py:139-144`), and `s_metrics` scores any non-NULL `risk_score` regardless of
  verdict (`s_metrics.py:56-62`) [V]. Production applies `apply_verdict_invariants` first: a
  `rejected` score is clamped to ≤29. The production-effective numbers re-score each stored row
  after that clamp. This needs no GPU. Today the two readings are identical for ctl, arm A and
  arm B, because those runs reject 7, 5 and 3 items, at most one of them an incident [V-store].
  An arm that changes verdicts can open the gap.
- **Verdict counts and the false-rejection rate.** Every oracle detection in the 450 is a declared
  subject, so any `rejected` on the 450 is a false rejection. The exception is the owner audit's one
  missing prop in 15 (P5a report) [C].
- **Notify-effective count (secondary).** `decide_notification` run offline over the post-clamp
  rows. Whether its pure path (`session=None`) reproduces production defaults offline is [?]; check
  it before relying on the number.
- **The decision quantities (stage 2):** paired dS2 and dS3 against arm A on the
  production-effective rates, by the OD-26 scenario-cluster bootstrap. Both arms are resampled
  together over the same 31 scenarios (10,000 resamples, seed fixed before the run), rates are
  item-weighted as the bars are, and the decision is repeated with each scenario left out once.
- **Subsets (stage 2):** every reading on the full 450, and separately on run A0's observable and
  indeterminate A items.
- **Diagnostics only, never a gate:** AUROC of A vs the plain-benign look-alikes (the S3 contrast)
  and of A vs the hard negatives (the S2 contrast). Both are reported as a paired difference from
  arm A under the same joint scenario resampling.
- Per-scenario false alarms for the five hard negatives plus `delivery_driver` and `resident_arrival`.
- Medium-band occupancy, the verdict-slot raw logprob, output characters and truncations.

**The runs.**

- **Stage 1 (approve now):** runs 1, 2, 2b and 2c.
- **Stage 2 (after A0):** runs 3-6.
- **Later:** runs 7-9.

- **Run 0.** **Done, no GPU:** the store re-analysis in section 2.
- **Run 1.** **One raw served call** (about a minute). Record the `content` key order and the verdict slot.
  This closes ISS-012's [?].
- **Run 2.** **Fields arm (H3, H7).** Name the enum (with the alert-safe `rejected` definition), define
  criteria per object type, set provenance to "n/a", re-scope reasoning to risk, and list fields in
  emitted order. The risk clause is unchanged. Prediction: the chosen verdict token's raw logprob
  goes from about −15 to about 0, and the criteria share drops below 20%.
  **This is the only arm that may ship on its own merits** (it uses no corpus knowledge). Its
  ship gate requires all of:
  - **No harm on production-effective S2 and S3** (OD-26 no-harm, after the clamp).
  - **False rejections on the 450 no higher than arm A's 5.**
  - **Run 2b no worse than arm A on the same injected sets.**
  - **Zero truncations in run 2c.**
  - **The owner confirms the `rejected` semantics** (section 4).
- **Run 2b.** **Rejection check** (no rendering; the shim rewrites only the `Detections` rows). Build two
  injected sets from about 60 stratified items by relabelling `object_type` to a plausible wrong
  class:

  - **all-wrong:** every row is relabelled. Expected verdict: `rejected` or `uncertain`.
  - **mixed:** one extra wrong row is added beside the correct ones. Expected verdict:
    `confirmed`, with the score unchanged.

  Run arm A's prompt and the fields arm's prompt on both, paired. The 450 alone cannot measure
  whether the model rejects false detections, only whether it falsely rejects true ones.

- **Run 2c.** **Dense-batch output check.** A handful of requests with 50-100 rows cloned from real items
  (distinct ids, 3-6 object types), at the shipped `max_tokens` 1,024. Gate: zero `VlmTruncatedError`
  and every reply valid. Codex measured 100 per-row criteria alone at 1,302 counted tokens; the
  450 stills carry only 1-3 rows each (section 9) [A].
- **Run A0.** **Blind observability audit (owner, no GPU; precondition for runs 3-6).**
  - **Material:** the 64 A items plus the plain-benign look-alikes `delivery_driver` (10),
    `neighbor_passing` (9) and `resident_arrival` (10): 93 stills, shuffled, with scenario and label
    hidden. An agent builds the viewer and answer sheet.
  - **Questions about what is visible, not about intent.** Is a person at or touching a door,
    window, gate or vehicle? Carrying an item, and is the direction of travel visible? Looking in
    through glass from outside? Photographing or filming the property? Following another person
    through a door? Showing a visible purpose (uniform, marked vehicle, task in progress, keys in
    hand)?
  - **Each still is labelled `observable`** (a visible risk cue and no visible purpose)
    **or `indeterminate`.**
  - **Cost:** about 30-45 minutes of owner time. The flagship VLM-as-judge agreed with the owner at
    chance (kappa 0.06, `p1-bakeoff.md`) [C], so it cannot substitute.
  - **Output:** the observable subset, and from it the prompt-addressable share of S3 that ISS-086
    asks for. A rough figure is enough; it overlaps OD-15's larger blind audit.
- **Run 3.** **Cue arm (H1, H2).** The shipped prompt plus the two cue sentences from (a); no bands. The
  first stage-2 screen.
- **Run 4.** **Arm (a),** compared against arm B: the same band anchors without the trigger examples.
- **Run 5.** **Arm (b);** then (b) with the wire reorder, with the verdict both before and after reasoning.
- **Run 6.** **Empty-line ablation (H6),** as a null control.
- **Run 7.** **Guard:** re-run the winner on a real-detector set (the A5500 38-item set, off-repo). The 450
  stills carry no boxes, so they cannot test the box sentences (section 7).
- **Run 8.** **Optional:** re-run the 17-clip frame-burst probe [A] with the winner. It uses the shipped
  4-still path.
- **Run 9.** **Confirm on a frozen holdout** (ISS-016, ISS-043) with the prompt hash pre-registered.

**Decision rule for stage 2 (pre-registered; frozen before run 3).** Revised after Codex pass 2:
the first version gated on A vs hard-negative AUROC, which can rise with no decision changing and
stay flat while S2 reaches its bar (section 9).

- **Primary measures:** paired production-effective dS2 and dS3 against arm A, at the product's
  existing thresholds. This is the OD-26 test, so prompt arms and model arms share one rule.
- **Guards (all must hold, or the arm is dropped):**
  - **OD-26 no clear harm:** the upper bound of dS2 is ≤ +2.0 points, and the lower bound of dS3 is
    ≥ −5.0 points.
  - **No regression on the object-cued and context-risk incidents:** the lower bound of paired dS3
    over groups B and C together is ≥ −5.0 points.
  - **Refusals and false rejections at or below arm A's** (0 and 5), and run 2b no worse.
- **Minimum worthwhile effect (point estimate):** dS3 ≥ +5.0 points (13 or more extra hits of 241),
  or dS2 ≤ −3.0 points (7 or more fewer false alarms of 209).
- **Outcomes:**
  - **Advance** to independent confirmation (run 9): the guards hold, the minimum worthwhile effect
    is met, and the OD-26 clear-benefit clause holds (the upper bound of dS2 is below 0, or the lower
    bound of dS3 is above 0). The decision must also survive leaving out any one scenario.
  - **Inconclusive:** the guards hold and the minimum worthwhile effect is met, but the clear-benefit
    clause fails or flips under leave-one-out. The owner may carry the arm to confirmation, as with
    OD-26's nearest miss.
  - **Budget stop:** stage 2 is capped at runs 3-6 plus one revision, about 3 GPU hours. If nothing
    advances by then, record "no advance at this budget". **That is not futility.**
- **Futility is out of reach here.** It needs an upper bound on dS3 that excludes the minimum
  worthwhile effect, on independent, adequately sized evidence (ISS-016, ISS-043). The 31 dev
  scenarios cannot supply that, and the dev intervals do not validate generalisation after
  taxonomy-informed prompt writing.
- **Reading the subsets:**
  - Gains on observable A stills with flat indeterminate stills support H1/H2 on the observable
    part. The indeterminate part then goes to OD-2 and ISS-086 (evidence or relabelling), not to
    more prompting.
  - No gain on observable stills is evidence against prompt-addressability, still short of futility.

## 6. Not re-run as-is

**Arm B's rubric** (`rubric.txt` is byte-identical to `replay_exp.py:15-26`) [V]. Revised after
Codex pass 2: the first version dismissed it too fast. Its results:

- +17 S3 hits and +16 S2 false alarms (31 gained / 14 lost; 21 / 5, ISS-086 update) [C].
- The S3 gain came from group B (+14), not A (+1).
- **On the S3 contrast it is the only arm that moved:** A vs plain benign went from 0.523 to 0.713,
  a paired +0.190 [−0.015, +0.380] [V-store].
- On the S2 contrast it lost ground: A vs hard negatives fell to 0.352, through appearance false
  alarms.

**Arm (a) keeps its band anchors and removes what went wrong.** Run 4 compares the two directly.

What went wrong, from its outputs:

- It kept the verification framing and the undefined enum: `"REAL"` is still 450/450.
- Its examples acted as triggers: "tool" raised `power_tools_at_night` from 4 to 9 false alarms and
  `landscaper_machete` from 0 to 4.
- Its negation was ignored: "stationary and appears calm … low", `B-batch-1-010`.
- Its "visitors, residents, workers" clause supplied benign stories for 64/64 A items.

**Contract changes, more sweeps, and fine-tuning** are deferred until runs 2-4 report.

## 7. Load-bearing; keep these

- **`bbox_2d` grounding plus "never reject a detection because of its box numbers alone"**
  (`vlm_client.py:586-621,658-661`). On the A5500 real-detector set it moved confirmed/uncertain from
  4/31 to 33/2 and S3 from 5/20 to 10/20 (ledger :395-405, `2fd5c54bc`) [C]. Keep it byte-identical.
- **The frame index and `null` sentence** (`:662-668`).
- **"Not yours to invent"** on the specialist lines (spec §6). Add what the lines mean; keep the guard.
- **The truncation marker** (`:733-737`).
- **The capture-time `Time:` line,** with `detected_at` dropped (`:528-532`).
- **Greedy decoding and the grammar.**

## 8. Assumptions and weaknesses this plan depends on

1. **Superseded: "the AUROC is the right gate".** Codex pass 2 showed it is not (section 9). The
   gate is now paired production-effective S2/S3 (section 5). The remaining weakness is power: with
   31 scenario clusters, OD-26's intervals run 6-26 points wide (sweep report), so **inconclusive is
   the likeliest stage-2 outcome** even for a real effect. Budget for that.
2. **The keyword screens** (findings 1 and 2) are crude regexes over model prose, and they count
   negated mentions. They illustrate; they do not measure.
3. **The logprobs are pre-grammar.** This is inferred from a grammar-illegal token (`"REAL"`)
   appearing in `top_logprobs`, not from the llama.cpp source.
4. **The emission order is source-verified, not observed;** run 1 observes it.
5. **The whole ladder sits on one build** (`b7972`). `b7972` and `b11376` disagree on 200/450
   items (ISS-087), and the shipped build has 2/64 A hits where the sweep's build has 0/64.
6. **Declared truth, not verified truth.** The corpus scores declared truth with oracle detections
   and no specialist context. The prompts' identity rung ("who") is never exercised. Production adds
   specialist lines that the 450 stills cannot test.
7. **Both candidate prompts were written after reading the taxonomy.** Any gain on the 450 stills
   is partly fitted; only run 9 counts.
8. **The S3 arithmetic depends on the OD-2 floor reading** (midpoint vs band minimum). The prompts
   deliberately do not target either reading.
9. **The minimal diff keeps the "verification expert" role line.** It may itself sustain the
   framing; run 2 vs (b) separates the two.
10. **The 450 cannot measure verdict correctness or output length under load.** Every oracle
    detection is correct and every item has 1-3 rows. Runs 2b and 2c cover these gaps with injected
    labels and cloned rows, both synthetic. A real-detector set (run 7) is the only check on real
    misdetections.
11. **A0 has one rater.** Observable is not the same as true, and a single owner pass carries that
    rater's errors. The audit separates visible cues from inference; it does not validate the
    declared labels. Leakage risk: the owner knows the taxonomy, so the viewer hides scenario names
    and shuffles the look-alikes in with the A items.
12. **Temporal and identity evidence are mostly out of scope.** Codex pass 2 recommends comparing
    prompt-only changes with added temporal or identity evidence. Video and multi-call are excluded
    by the review brief, and the 450 carry no specialist lines. The only in-scope temporal check is
    run 8, the shipped 4-still path.

## 9. Review log

**Codex adversarial review, pass 1 (2026-10-04).** Target: this file, untracked. Verdict:
needs-attention. Both findings were accepted.

| Finding                                          | What Codex said                                                                                                                                                                 | Resolution in this revision                                                                                                                                                                                                                                 |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [high] The gate ignores verdict changes          | Replay and `s_metrics` score raw scores, while production clamps `rejected` to ≤29 and suppresses notifications. A verdict-changing arm could pass replay and drop real alerts. | Every arm reports production-effective S2/S3 and the false-rejection rate. Run 2b adds injected all-wrong and mixed sets. The fields arm's ship gate requires all three. The `rejected` definition is now alert-safe (section 4) and flagged for the owner. |
| [medium] Per-row criteria vs the 1,024-token cap | The renderer accepts 100 rows untrimmed; 100 per-row criteria alone count 1,302 tokens. The 450 have 1-3 rows each, so they cannot catch the resulting truncation.              | Criteria are per object type in both prompts. Run 2c adds a dense-batch check with zero truncations as its gate.                                                                                                                                            |

**Verified by the author after the review [V/V-store].**

- `s_metrics.py:56-62` scores on `risk_score` alone, and `vlm_analyzer.py:285-294` clamps `rejected`.
- Raw and post-clamp S2/S3 are identical for ctl (21, 94), arm A (18, 88) and arm B (34, 105).
- The 450 items carry 1, 2 or 3 detection rows: 148, 293 and 9 items respectively.
- Codex's 1,302-token count is [A]: not re-run by the author.

**Codex adversarial review, pass 2 (2026-10-04).** Focus: the stop rule, its primary metric, and
whether section 2 supports prompt-addressability. Verdict: needs-attention. All three findings were
accepted; the third with two limits.

| Finding                                                                       | What Codex said                                                                                                                                                                                                                   | Resolution in this revision                                                                                                                                                                                                                                                                                                                                                                   |
| ----------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [high] The AUROC gate can reward no improvement and reject useful calibration | A constructed edit of arm A raises AUROC to 0.893 with S2/S3 unchanged. Remapping 30-59 to 29 gives S2 10/209 and S3 88/241 at AUROC 0.410, which would trigger the stop. The gate also left B/C S3 unprotected.                  | The gate is now paired production-effective dS2/dS3 by the OD-26 rule, with guards (including B+C S3 non-regression), a minimum worthwhile effect, and AUROC demoted to a diagnostic (section 5).                                                                                                                                                                                             |
| [high] Eleven clusters do not support a stopping inference                    | Arm A's interval is [0.257, 0.580]. Comparing a candidate's lower bound with a fixed 0.410 is not a paired test. A point estimate below 0.5 is not futility, and dev intervals cannot validate generalisation.                    | Joint paired resampling and leave-one-scenario-out. Three outcomes, with futility reserved for independent evidence. Section 2 finding 1 is corrected: on the shipped build the inversion is not established.                                                                                                                                                                                 |
| [high] Section 2 does not establish prompt-addressability                     | Recognising package handling does not establish theft; delivery and theft share a still type. The prose cannot separate wrong reasoning from missing information or label ambiguity. Hard negatives are the wrong contrast for A. | H0 (input insufficiency) added. Run A0, a blind observability audit, is a precondition for stage 2, and readings are split by observable vs indeterminate stills. A vs plain benign is now the S3 diagnostic. Finding 2 is reworded. **Limits:** the temporal/identity comparison is mostly out of scope (section 8 item 12), and A0 costs owner time because the flagship judge is unusable. |

**Verified by the author after the review [V-store, `an8.py`].**

- Remapping 30-59 to 29 on arm A gives S2 10/209 and S3 88/241.
- Arm A's A-vs-hard-negative AUROC interval is [0.258, 0.581] (Codex: [0.257, 0.580]). The `ctl`
  interval is [0.189, 0.463] and arm B's is [0.217, 0.495].
- A vs plain benign is 0.523 [0.353, 0.680] for arm A and 0.713 [0.590, 0.823] for arm B, a paired
  +0.190 [−0.015, +0.380].
- Codex's 0.893 counterexample is a constructed edit and was not re-run.

**Consequence for section 2:** the first revision overstated finding 1 and framed finding 2 as a
reasoning error. Both are corrected in place, and the corrections are marked.
