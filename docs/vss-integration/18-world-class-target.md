# 18 — What We Will Build: a World-Class Video Processing and Reasoning Pipeline

> **Status — 2026-10-03 [?]. A PROPOSAL, pending owner approval.** Nothing here has been ruled on.
> Every rung is [?], every threshold is a placeholder for an owner ruling, and no number below is
> a promise about any model or technique: for candidates this document gives fit, mechanism and
> the experiment that would test them, never an expected accuracy. Repo tip `5c605e1d` (main
> through #6767 plus one docs commit). Markers follow [`AGENTS.md`](AGENTS.md). [V] means a command
> run on 2026-10-03 showed it at that tip, or, for the off-repo run artifacts of 2026-10-03, that
> the file was read that day. The directory is a research record: this file edits no existing doc,
> and the corrections it owes older docs are listed in §11 for the banner pass.

> **Since the pin — 2026-10-03 [V: `git show --stat` of each commit].** Three commits landed after
> `5c605e1d` and changed facts this document states. Everything below is left as written at the
> pin and is scoped to it; every `path:line` anchor is as at `5c605e1d`. The three files the first
> two commits touched in the VLM path (`backend/services/vlm_client.py`,
> `backend/evaluation/s_metrics.py` and `backend/evaluation/vlm_replay.py`) have shifted lines, and
> so has `pyproject.toml`, which the third touched (the `alpr` extra cited in L1 is at `:173` at
> `HEAD`, not `:192`), so prefer the symbol names.
>
> 1. **`9f4e65cd`, the assess call is greedy.** `backend/services/vlm_client.py` now sends
>    `"temperature": _ASSESS_TEMPERATURE` with `_ASSESS_TEMPERATURE = 0.0` on the assess call; at the
>    pin it sent an unseeded `0.1` (§2.2). The spec §6 transport retry stays explicit at 0 and is now
>    a plain re-send. `test_assess_samples_greedily` pins the constant, the wire value and the absence
>    of `top_p`, `top_k`, `min_p` and `seed`. The commit message records two temperature-0 replays
>    that agreed on 450 of 450 items, S2 18/209 and S3 88/241 (handoff Addendum 4; those replays
>    forced the temperature with a transport shim in a scratch driver, they did not run the committed
>    client; handoff Addendum 6 records the commit). Read §2.2, §3 finding 1, §5.1 stage 5, L5 (d),
>    OD-7 and §10 as the state at `5c605e1d`: temperature 0 is now shipped, a seed and k-sample
>    means are not.
> 2. **`d8482861`, the retired Nemotron prompt-evaluation harness is deleted** (43 files changed,
>    137 insertions, 7,770 deletions): seven modules of `backend/evaluation/` (`harness`,
>    `prompt_evaluator`, `prompt_eval_dataset`, `combined_dataset`, `ab_experiment_runner`,
>    `metrics` and `reports`), six unit tests, `backend/tests/integration/test_nemotron_prompts.py`,
>    the nightly workflow `.github/workflows/prompt-evaluation.yml` and two
>    `prompt-evaluation-results.md` pages.
>    `backend.evaluation` now holds `assess_input`, `control_freeze`, `eval_store`, `label_import`,
>    `levels`, `s_metrics` and `vlm_replay` (handoff Addendum 7). The L1 observation about that
>    workflow is resolved by deletion; L1 says what CI still does not measure about the VLM path.
>    The edits to `s_metrics.py` and `vlm_replay.py` in that commit are docstring and comment
>    changes only.
> 3. **`efa1b586`, the NeMo Data Designer tooling and the `nemo` extra are deleted** (41 files
>    changed, 29 of them deleted; 36 insertions, 8,873 deletions): `tools/` (its only package was
>    `tools/nemo_data_designer/`; `git ls-files tools` prints nothing at `HEAD`), the two integration
>    tests that imported it (`test_multimodal_pipeline.py` and `test_enrichment_edge_cases.py`),
>    `backend/tests/fixtures/synthetic/`, two developer pages, the `synthetic_scenarios` and
>    `scenario_by_type` fixtures of `backend/tests/conftest.py`, and both `nemo` dependency blocks
>    of `pyproject.toml`. `uv.lock` drops 23 packages (the `data-designer` family, `pandas`,
>    `pyarrow`, `duckdb`, `mcp` and others), adds none and changes no version
>    [V: `git show --stat`, and the `uv.lock` package lists compared at `9f4e65cd` and `efa1b586`].
>    The census baseline `pytest_skip_imperative` in `scripts/test_suppression_census.py` goes from
>    99 to 86 [V: its diff]. This document names the tool and the extra only in §10 (the ISS-083
>    neighbor), which is scoped to the pin and now carries a dated note; that note also says what the
>    commit left for the owner, a `cryptography` upgrade that now resolves and is not applied.

Sources of the proposal: three independent architect proposals, two judges and one synthesis (§8);
[`12`](12-postponed-roadmap.md) (R1-R14); [`10`](10-audit-feature-inventory.md) (what VSS offers,
what we have that it lacks); a register of 86 issues (§10: ISS-001 to ISS-077 from the discovery
pass, ISS-078 to ISS-082 from the sandbox exercise, ISS-083 to ISS-086 added after `9f4e65cd` and
`d8482861`); and the measurements of 2026-10-03 in
[`docs/plans/2026-10-03-vss-vlm-exercise-handoff.md`](../plans/2026-10-03-vss-vlm-exercise-handoff.md)
(untracked at `5c605e1d`). That file's addenda are cited here as Addendum 1 (its "state after the
recreate"), Addendum 2 ("the first full replay"), Addendum 3 ("the repeat run"), Addendum 4
("temperature 0 is deterministic and does not move accuracy") and Addendum 5 ("decisions, and where
the research now lives", owner decisions [O]); Addenda 6 and 7 record `9f4e65cd` and `d8482861`
(as of this edit, no addendum records `efa1b586`).
Addendum 8 ("rubric-prompt and logprob experiments", written later on 2026-10-03, after this file's
first draft) holds the results of the two experiments of Addendum 5; see the dated notes under L5.

## 1. Thesis

The shipped pipeline is a **still-frame verifier**. A detector gates FTP stills, and one VLM
describes, verifies and scores each candidate in one constrained call. It runs, it is the default
(`docker-compose.prod.yml:484`), and it does not yet meet its own bars (§2).

A world-class pipeline, as proposed here, is not first of all one that sees more video. It is one
whose owner can answer four questions for any alert or any non-alert:

1. What did the model see?
2. What did it say?
3. How often is that kind of call right?
4. Did the last change make it worse?

Today the first three have partial answers and the fourth has none [?]. Video, tracks and cross-event
memory are built **after** those four can be answered, and only through a pre-registered paired
test that is allowed to say "no". That makes the ladder (§4) **trust-first**: measurement, honest
bars, actionable and auditable verdicts, and calibration come before any video engine. §3 states
the evidence for that order from the replay results.

Two caps no rung removes:

- **The notification link is unwired (M1).** `should_notify`, `evaluate_event` and `deliver_alert`
  have no non-test caller, so no rung is user-visible until L3 closes it [V, §4 L3].
- **Hardware time is the critical path.** Any change to model, context, image handling or output
  budget needs the owner's 24 GB box again; S2/S3/prompt work does not
  (`docs/plans/2026-09-23-vss-gaming-gpu-ledger.md:423`) [V].

## 2. Where we start: L0, measured

L0 is the path as shipped: Qwen3-VL-8B `Q4_K_M` with its mmproj on llama.cpp `b7972`, two slots of
16,384 tokens, behind the registered `vlm_assess` op, run over the 450 exportable sets of the
`tierb-v0` corpus. It was scored once on 2026-09-30 (committed) and twice on 2026-10-03.

### 2.1 The readings

All three readings use the same 450 sets (export labels sha256 `3a9b16e3…c847d`), the same build
`b7972-e06088da0`, the shipped prompt, `max_tokens` 1024 and a 25 s timeout. Code is unchanged
between them: `git diff --numstat ca73f1ef 5c605e1d --` over the 13 core files (`vlm_client.py`,
`vlm_verdict.py`, `vlm_analyzer.py`, `vlm_specialists.py`, `key_frame_selector.py`,
`vlm_replay.py`, `s_metrics.py`, `levels.py`, `assess_input.py`, `label_import.py`,
`ai/vlm/Dockerfile`, `synthbench/run/replay.py`, `synthbench/export/vss.py`) printed nothing [V].
Since the pin the same command run against `HEAD` prints three files, `vlm_client.py` (+13/-3,
`9f4e65cd`), `s_metrics.py` (+1/-3) and `vlm_replay.py` (+1/-6) (the last two are the comment and
docstring edits of `d8482861`) [V, 2026-10-03].
The committed report records the weights as sha256 `67d1659b…`; the two 2026-10-03 score files
record them as `unrecorded`, and the same hash comes from the owner's check against vss1 (handoff
Addendum 2) [A].

| Reading                                    | S2 (bar ≤ 5%)              | S3 (bar ≥ 90%)                  | Refusals (S5)            |
| ------------------------------------------ | -------------------------- | ------------------------------- | ------------------------ |
| Committed baseline, 2026-09-30, `ca73f1ef` | 14/209 = 6.7% [4.0-10.9]   | 88/241 = 36.5% [30.7-42.8]      | 1 (length truncation)    |
| 2026-10-03 run 1, score `20261003T133003Z` | 19/209 = 9.1% [5.9-13.8]   | 87/241 = 36.1% [30.3-42.3]      | 0                        |
| 2026-10-03 run 2, score `20261003T134742Z` | 18/209 = 8.6% [5.5-13.2]   | 84/241 = 34.9% [29.1-41.1]      | 1 (`VlmTruncatedError`)  |
| Mean and sd of the three (n = 3, rough)    | 17.0 FP = 8.1%, sd 2.6 FP  | 86.3 hits = 35.8%, sd 2.1       | not 0 in 2 of 3 readings |
| A point-estimate pass would need           | ≤ 10 FP (4.78%) [C]        | ≥ 217 hits (90.04%) [C]         | 0                        |
| A "demonstrated" pass (L2) needs           | ≤ 4 FP (Wilson upper 4.8%) | ≥ 227 hits (Wilson lower 90.5%) | 0                        |

Sources: the baseline row is `docs/benchmarks/synthbench/p5a-2026-09-30.md` (headline table) with
counts from handoff Addendum 3 [V]; the two 2026-10-03 rows were re-read from `metrics.json` of
the two score directories under the sandbox's `$AGENT_GPU_DIR/out/sbroot/runs/scores/` (off-repo)
[V]. The bars are the owner's ruling F14 (`docs/plans/2026-09-23-vss-gaming-gpu-ledger.md:221`)
[O]. Pass means the point estimate meets the bar; the ruling labels a result marginal when the
interval straddles it. Neither bar passes (point estimate) in any reading. The baseline S2 interval
[4.0-10.9] straddles 5%, so under F14 it reads marginal; the two 2026-10-03 S2 intervals lie wholly
above 5% and read fail (handoff Addendum 2 records the flip from marginal to fail), and every S3
interval lies wholly below 90%, so S3 reads fail throughout [C: from the intervals in the table].
S3 is about 130 hits short [C: 217 − 86.3]. Wilson intervals recomputed [C] from the counts above.

The flagship comparator in the committed report, same prompt and sets, reads S3 58.9%
[52.6-65.0] and S2 8.6% [5.5-13.2] (`docs/benchmarks/synthbench/p5a-2026-09-30.md`) [V]. It is a
measured reading, not a target.

### 2.2 What the readings say

**Run-to-run noise is as large as S2's gap to its bar.** [C: sd 2.6 false alarms and a range of 5
(14-19), against a gap of about 7 (mean 17.0 minus the point-pass bar of 10); the counts are [V],
the "as large as" judgement is an inference] At `5c605e1d` the shipped assess request sampled at
`"temperature": 0.1` with no seed (`backend/services/vlm_client.py:796`); temperature 0 appeared
only on the retry (`backend/services/vlm_client.py:805-807`), and `seed`, self-consistency and
`n_samples` appeared nowhere in `vlm_client.py`, `vlm_analyzer.py` or `vlm_verdict.py` (grep at
`5c605e1d`, no hits). So the variation was a property of production behaviour, not only of the
benchmark. **Since the pin (2026-10-03, `9f4e65cd`):** the assess call is greedy
(`_ASSESS_TEMPERATURE = 0.0`), and the temperature-0 experiment of handoff Addendum 4 found 450 of
450 items identical across two replays with S2 18/209 and S3 88/241 [V, read in the handoff and the
commit message]; the three readings of §2.1 are all at temperature 0.1 and stay as the record. At
`HEAD` `seed` still appears nowhere in the three files except the word "unseeded" in the comment
that explains the constant [V]. Between the two 2026-10-03 runs, on one server, 278 of 450 items (62%)
returned an identical verdict and score; 164 changed score (165 counting the one item run 2
refused), 123 of them by 10 points or more; 51 changed risk level among the 449 items scored in
both runs (52 counting the refused item, which scored 0 in run 1 and none in run 2; the handoff's
Addendum 3 says 52). Recomputed from the two `results.jsonl` files with the shipped bands
(29/59/84), which also give 13 false alarms common to both runs, 6 only in run 1 and 5 only in
run 2 [V]. The S2 false alarms sit almost wholly in
three hard-negative scenarios: all 19 of run 1 are `hooded_jogger` 9, `power_tools_at_night` 8 and
`flashlight_neighbor` 2; 16 of run 2's 18 are the same three (9, 4 and 3) and 2 are `wildlife`
(score rows) [V]. A point pass needs 10 false alarms or fewer and the readings are 14, 19 and 18,
against a spread of about 2.6 [C, n = 3]. A single replay is one draw; an S2 "improvement" of two
or three items is inside one standard deviation of it. The ledger recorded the same shape on a
13-item set earlier ("the two runs disagree", the 2.1.6 re-run entry,
`docs/plans/2026-09-23-vss-gaming-gpu-ledger.md:132`) [V].

**The model confirms and then scores low.** [V] In the two 2026-10-03 runs 63.1% and 63.3% of
incident scores sit below their declared band (152 of 241; 152 of 240 scored), by 53.1 and 52.8
points on average, and none sit above (`metrics.json` `band` block); the committed baseline reads
62.7% below, 54.2 points on average (`docs/benchmarks/synthbench/p5a-2026-09-30.md`, "Risk band").
The same report states that both models confirm the declared objects on 96-98% of stills (the
per-item definition behind that range was not re-derived here, so treat the range as the
report's own statement [A]); the verdict mix is a checkable stand-in: confirmed 440 of 450 in run
1 and 436 of 450 in run 2 [V].

Computed from the scored rows of the two 2026-10-03 runs [C] (`results.jsonl`, off-repo; formulas
in the lists):

- Of 154 incident misses in run 1, 149 carry the verdict `confirmed`, 5 `uncertain`, none
  `rejected`; 135 scored 29 or less. Run 2: 156 misses, 151 `confirmed`, 132 scored 29 or less.
- No incident was rated `rejected` in either run (0 of 241; 0 of 240 scored). All 4 and all 5
  `rejected` verdicts sit on benign items.
- Incident scores are bimodal. Run 1: 135 incidents at 29 or less, 6 between 30 and 69, 100 at 70
  or more.
- The AUROC of `risk_score`, incident against benign, is 0.697 (run 1) and 0.700 (run 2), by
  Mann-Whitney U over all 241 × 209 pairs (240 × 209 in run 2, one incident refused) with ties
  counted half, cross-checked by pair counting.
- **Ceiling of any monotone remapping of the score.** Under S2/S3 as defined, every incident in
  this corpus has a floor of `medium` or higher, so for any monotone remap the best S3 at a given
  S2 equals the share of incidents scoring at or above the benign-FPR threshold. At S2 ≤ 5% that
  threshold is a raw score of 61, with 41.5% of incidents above it in run 1 and 40.8% in run 2
  (benign FPR 4.3% and 3.8%). This is **in-sample** (the threshold was chosen on the same 450
  items), so it is an upper bound for remapping on these stills, not an estimate for new data. It
  says remapping alone cannot reach 90% here; it does not say what a changed prompt or added
  evidence would do.

**Video cannot be the S3 fix.** [C] In run 1 the suspicious group hits 1 of 45 and the threat group
86 of 196 (the baseline: 1/45 and 87/196). If every suspicious scene became a hit and nothing else
moved, S3 would be (86 + 45)/241 = 54.4% in run 1, (83 + 45)/241 = 53.1% in run 2 and
(87 + 45)/241 = 54.8% on the baseline split. Suspicious scenes (loitering, peering and the like)
are the temporal ones; 109 or more of the misses are threat scenes, among them `package_theft`
and `child_alone_at_pool`, 0 of 19 hits each in both runs; `child_alone_at_pool` is a state, not a
movement [?]. The video gain may be zero, and L7 exists to say so.

**S5 is not yet demonstrated.** [V] The bar is 0 unparseable verdicts (spec S5,
`docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md:87`); the baseline had one
length truncation, run 1 none, run 2 one (`B-batch-4-012`, `VlmTruncatedError`, stop `length` at
1024 tokens).

### 2.3 What L0 cannot say

Every number above is conditioned (the P5a replay design requires "Stated conditions, printed on
the report's first line",
`docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md:62`) [V]:

- **Declared truth.** The sampler declares each item's scenario and risk band. The owner audited 60
  stills: scene, people and conditions matched on all 60 (0.0% [0.0-6.0]); the prop was missing
  in 1 of 15 (`docs/benchmarks/synthbench/p5a-2026-09-30.md`, "Audit"). The scene question is the
  leading "Does this show X?" (`synthbench/audit/sample.py:75`), so 60 of 60 is a weak test of
  truth [?]. The 2026-10-03 runs have no audit slice (the audit log lives on the host).
- **Ideal detector.** The VLM is handed each item's declared subjects and props as detections at
  confidence 1.0 with no boxes (`synthbench/export/vss.py`, `declared_detections`). A real detector
  misses some, and a stills-only prompt with no detections refuses to judge (same docstring).
- **No specialist context in the replay.** The labels document emits no `specialist_context`
  (`synthbench/export/vss.py`, `labels_document`), so the stored `specialist_outputs` is an empty
  dict (`backend/evaluation/eval_store.py:421`, `_render_specialist_outputs`), while production
  prompts always carry three keys, `faces`, `plates` and `person_reid`, each possibly an
  `unavailable` line (`backend/services/vlm_specialists.py:884`, `collect_specialist_outputs`).
- **Stills only, synthetic, GB300.** The corpus is generated renders; the box is shared, so no
  latency or memory figure here is S1 or S4 (the ledger's F13 entry,
  `docs/plans/2026-09-23-vss-gaming-gpu-ledger.md:210`, ruling 5 at `:216`).
- **Slices are thin.** 12 of the 19 incident scenarios have n = 9 and read "insufficient" under
  `MIN_N = 10` (`synthbench/score/metrics.py:28`); 7 have n = 19 [C: 12 × 9 + 7 × 19 = 241].

**On a 24 GB card** the ledger relays an S1 peak of about 9.4-9.6 GiB (9,662-9,826 MiB) against a
20.4 GiB bar (`docs/plans/2026-09-23-vss-gaming-gpu-ledger.md:408` and `:420`) and, from a 13-item
set and 21 requests, an S4 p95 of 16.2 s against 30 s (the ledger's A5500 S4 re-take entry, `:417`
for the p95 and the 21-request shape, `:419` for the 13 items and the median)
[A, relayed, not re-run]. The
GB300 reading of the same config, 9,056 MiB of VRAM by the runner, is a fit reading and not S1
(handoff Addendum 1) [V].

## 3. Why the ladder is trust-first

Six findings, each with its evidence, set the order. None depends on a model we have not run.

1. **We cannot yet tell a gain from noise.** Three readings give S2 false alarms of 14, 19 and 18
   with 62% item-level agreement between two runs (§2.2). Any rung claiming an improvement needs
   a noise floor, a paired comparison and a negative control first. That is L2. [Dated note,
   2026-10-03: those readings are at temperature 0.1. At temperature 0 two same-build replays
   reproduced on 450 of 450 items (Addendum 4, by a transport shim), and `9f4e65cd` makes the
   shipped call greedy, so L2's repeat option becomes a reproducibility check; whether any other
   source of run-to-run variation remains is unmeasured [?].]
2. **The bars are numbers, not gates.** `S2_MAX_PCT` and `S3_MIN_PCT` are defaults carried as
   `bar_pct` in the metrics, and "nothing in here enforces them"
   (`backend/evaluation/s_metrics.py:29-33`); no other non-test `.py`, `.yml` or `.json` reads
   them, `synthbench/score` and `vlm_replay.py` never mention a bar, and the committed report
   prints none. Nothing in `backend/evaluation` or
   `synthbench` computes pass, marginal or demonstrated (grep) [V]. The spec rows still read `[?]`
   (`docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md:84-85`) [V].
3. **The miss is a low score on a confirmed verdict, and a remap cannot rescue it.** §2.2: 149 of
   154 misses are `confirmed`; AUROC is about 0.70; the in-sample remap ceiling at S2 ≤ 5% is about
   41%. So the lever is not calibration alone. It is what the model is asked and shown
   (`_render_prompt` gives no scoring anchor beyond "how threatening it is (`risk_score` 0-100)",
   `backend/services/vlm_client.py:518-551` at `5c605e1d` [V]), the evidence it gets (the replay
   carries no specialist context), or the model, and L5 tests those separately.
4. **Video cannot carry the claim.** §2.2: a perfect fix of every suspicious scene caps S3 near
   54%.
5. **Nothing is user-visible until M1 closes.** The trio has no caller (§4 L3).
   `frontend/src/hooks/usePushNotifications.ts` and `useDesktopNotifications.ts` define
   `showSecurityAlert`, and `frontend/src/hooks/useIntegratedNotifications.ts` wraps both (its
   `showSecurityAlert` calls `desktop.showSecurityAlert` and `push.showSecurityAlert`), but the
   wrapper has no non-test caller: its one consumer,
   `frontend/src/components/settings/NotificationSettings.tsx`, destructures only permission and
   audio members [V].
6. **The replay is optimistic in ways that cut both ways.** An ideal detector flatters recall; no
   specialist context and a leading audit leave truth and inputs unmeasured. L2 builds the
   production-condition table and L6 the real-corpus measurement; until then every S2/S3 figure
   is accuracy-only.

What the evidence does **not** say: that video is useless, that the 8B is the wrong pick, or that
S3 = 90% is reachable. L5's close-by-negative-result path and L7's gate exist because those three
stay open.

## 4. The capability ladder

Ordering: L1 → L2 → (L3 ∥ L4, once L2's noise floor exists) → L5 → L6 → L7 → (L8, L9, L10 only on
an L7 "go"). Each rung's exit bar is measurable, and every threshold is [?]. The Gate column lists
the headline gates; §9 holds the full "Gates:" list of each open decision (for example OD-3 also
gates L8 and OD-11 gates L8-L10).

| Rung | Adds                                             | Headline exit bar                                                     | Hardware            | Gate                |
| ---- | ------------------------------------------------ | --------------------------------------------------------------------- | ------------------- | ------------------- |
| L1   | Defect sweep, no new capability                  | Mixed still+clip batch never refused; band parity; errata             | none (hermetic)     | OD-4, OD-10, OD-12  |
| L2   | Honest bars, noise floor, paired regression gate | `{meets_point, straddles, demonstrated}`; flip rate; paired           | GB300 replays       | OD-2, OD-3, OD-5    |
| L3   | Actionable, auditable verdicts (closes M1)       | Null-score delivery test; a trace row per verdict                     | none to build       | OD-4                |
| L4   | Time-aware evidence on the same engine           | Video batches reach the engine; per-frame times; no stills regression | GB300, then 24 GB   | OD-5, OD-6          |
| L5   | Verdicts that rank, plus abstention              | Held-out S2/S3 at one operating point, or a recorded no               | GB300 (prompt work) | OD-7, OD-2          |
| L6   | Real-corpus evaluation with human corrections    | First real S2/S3 with Wilson intervals; blind audit                   | owner's cameras     | OD-9                |
| L7   | Clip eval and the temporal-value gate            | Pre-registered paired rule decides L8-L10                             | GB300               | OD-8, OD-3, OD-5    |
| L8   | Video-VLM option behind `vlm_assess`             | Beats the L4 control arm by the L7 rule; S1/S4 on 24 GB               | 24 GB               | L7 go               |
| L9   | Tracks, dwell, cross-event memory                | Tracker yield; measured false-merge rate                              | 24 GB               | L7 go, labeled data |
| L10  | Segment ingest, multi-camera incidents           | R1 trigger met; incident-level S2/S3                                  | 24 GB               | L7 go, M3 14 days   |

### L1. Defect sweep [?]

**Capability.** Fix verified defects that need no new capability, no GPU and no model change.

**Exit bar [?].** Mechanical, and S2/S3 on the 450 sets must not move beyond the spread of the
three readings of §2.1 (the L2 tool replaces that rough band with a measured floor).

1. Every defect below has a red-then-green hermetic test or a dated doc banner.
2. A property test shows a mixed still+clip batch never selects a path `VlmClient` would refuse,
   with the Hypothesis determinism and one-per-file pins still green.
3. A notification-decision test covers the detector's COCO `car` and `truck`, and pins the band
   edges of `NotificationFilterService._risk_score_to_level` to `SeverityService`.
4. A specialist-stage p95 is reported with the plate leg enabled.
5. Doc-truth errata follow `AGENTS.md` (dated banner, original prose kept) with
   `scripts/check-vss-docs-currency.py` green.

**Defects, each [V] at `5c605e1d`** (the mixed-batch chain is code reading, not executed [?]):

- **Mixed batches.** `select_key_frames` has no media-type filter (it ranks by confidence and
  recency, one pick per `file_path`; `backend/services/key_frame_selector.py:73`), and
  `VlmClient._image_parts` refuses any non-image suffix for the whole call
  (`backend/services/vlm_client.py:467`). So a clip detection that wins a slot should sink the
  verdict for the batch. The cameras do emit both: `snap/*.jpg` and `record/*.mkv`
  (`backend/services/capture_time.py` docstring).
- **Vehicles.** `SECURITY_RELEVANT_CLASSES = frozenset({"person", "vehicle"})`
  (`backend/services/notification_filter.py:22`) while the detector emits COCO `car`, `bus` and
  `truck` (`ai/gateway/adapters/yolo26.py:43-50`); the only `car`-to-`vehicle` map is in the
  unwired `backend/services/frigate_integration.py:213-214`. The file's own comment says widening
  the set needs owner sign-off, so the fix waits on OD-4.
- **Band edges.** `_risk_score_to_level` cuts at 40/60/80
  (`backend/services/notification_filter.py:175-190`); the shipped bands are 30/60/85
  (`backend/core/config.py:2423-2440`, `frontend/src/utils/risk.ts:80-85`). A score of 30-39 is
  `medium` on the dashboard and `low` to the filter (ISS-018).
- **Specialists.** `load_fast_alpr` rebuilds the ALPR on every call
  (`backend/services/fast_alpr_loader.py:66`, called per leg at
  `backend/services/vlm_specialists.py:568`); `vlm_specialists.py` and `vlm_analyzer.py` have no
  `wait_for` or timeout; the backend image installs only `--extra face`
  (`backend/Dockerfile:134`) while `alpr` is a separate extra (`pyproject.toml:192` at the pin,
  `:173` at `HEAD`), so the plate leg reads `unavailable`. Compose defaults `BACKEND_MODEL_PRELOAD`
  to false (`docker-compose.prod.yml:489`); `backend/core/config.py:2692` says `setup.py` sets it
  true at 24 GB or more, so the face and re-ID legs depend on the deployment.
- **Dormant controls, to be recorded and not silently wired.** The weapon and smoke/fire batch
  bypasses are reachable only from `backend/api/routes/debug.py:1771-1772`; `priority_*` settings
  (`backend/core/config.py:997-1012`) have no reader outside config; `should_apply_backpressure`
  (`backend/services/batch_aggregator.py:1257`) has no production caller. Each may have been left
  dormant for a reason that has to be checked first [?].
- **CI that said nothing about the VLM path (resolved by deletion in `d8482861`, 2026-10-03).**
  At `5c605e1d` the nightly workflow `.github/workflows/prompt-evaluation.yml` (92 lines; its two
  `--mock` steps start at lines 41 and 53) ran the legacy Nemotron harness
  (`backend.evaluation.harness` in mock mode), so a green job proved nothing about the shipped path
  [V at the pin]. `d8482861`
  deleted the workflow and the harness [V: `git show --stat`, and the file is absent from
  `.github/workflows` now]. What CI still does not measure about the VLM path [V: grep of
  `.github/workflows` at `5c605e1d` and at `HEAD`, 2026-10-03]: no workflow mentions `vlm_replay`,
  `s_metrics`, `ai/vlm` or `synthbench replay`, so none builds or scans the `ai/vlm` image, serves
  a real llama.cpp build, replays items, computes S2, S3 or S5, or compares a run with a stored
  baseline; `docker-compose.ci.yml` has no `ai-vlm` and `backend/tests/gpu/` holds only
  `test_detector_integration.py`. What CI does run is the unit tier (`backend/tests/unit/`, which
  holds `test_vlm_client.py` against an in-process fake llama server, `test_s_metrics.py`,
  `test_vlm_replay.py` and the `synthbench` tests), ruff and mypy over `synthbench/`, and
  `scripts/gen-ai-contract.py --check`: wire shape and metric arithmetic, not accuracy, grammar
  enforcement by a real build, or latency. Every S2, S3 and S5 figure here therefore comes from a
  manual GPU replay. The register carries the gap as ISS-017 (smoke job and baseline-replay gate)
  and ISS-059 (`ai/vlm` outside CI); the gate is L2's.
- **Doc-truth.** The comment at `backend/services/vlm_client.py:473` (at `5c605e1d`) says ffmpeg is
  not in the backend image, and `backend/Dockerfile:63` and `:170` install it;
  `backend/ai_contract/AGENTS.md:5` and `:16` say 38 operations and `:20` says 45 schemas, while
  `backend/ai_contract/operations.py` registers 9 and `backend/ai_contract/schemas/` holds 15
  files; `backend/ai_contract/operations.py:53` and `:66`
  cite `ai/nemotron/model_hf.py` and `backend/services/nemotron_analyzer.py`, both deleted;
  `docker-compose.prod.yml:33` documents `CTX_SIZE` 262144 over 8 slots against the shipped
  `VLM_CTX_SIZE` 32768 over 2 (`:205-206`); doc [`05`](05-hardware-profiles.md) lists gateway
  routers the gateway no longer mounts (`ai/gateway/main.py:276-277` mounts `/yolo26` and
  `/enrich-lt`); spec D6 says ingest is stills only
  (`docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md:69`) while
  `backend/services/file_watcher.py:76-78` accepts `.mp4`, `.mkv`, `.avi` and `.mov`; and the
  ledger, the stated home of "what has actually run", has no row for the committed P5a baseline or
  the 2026-10-03 re-runs (`grep -ci p5a` of it returns 0 [V]; ISS-080, and the owner merges ledger
  rows).
- **Optional.** Move the enforcement probe off the first request (ISS-071).

**Builds on.** `backend/services/key_frame_selector.py`, `backend/services/notification_filter.py`,
`backend/services/vlm_specialists.py`, `backend/services/fast_alpr_loader.py`,
`backend/Dockerfile`. (At the pin this list also named the prompt-evaluation workflow, deleted by
`d8482861`.)

**Issues.** ISS-004, 018, 023, 025, 026, 052, 069, 071, 074, 075, 076, 080 (§10).

### L2. Honest bars and a regression gate [?]

**Capability.** Offline, no product behaviour change. A replay reports a status per bar under
F14's rule plus a stricter flag that says whether the interval itself clears the bar. It applies
the production invariants, carries a measured noise floor, and reports its production-condition
inputs. A paired comparison and a seeded-regression negative control become the admission gate for
every later rung. S4′ is baselined on a clock that starts when the batch's first file arrives.

**Exit bar [?].**

1. **Parity.** A `FakeProvider` verdict `rejected` with `risk_score` 70 yields a replay row at or
   below `SeverityService.low_max` and equal to `apply_verdict_invariants`. Today replay stores the
   raw score (`backend/evaluation/vlm_replay.py:145`) and does not set `frame_detection_ids`; only
   `backend/services/vlm_analyzer.py:255` clamps. [V] Four items were `rejected` in run 1, so the
   effect on today's numbers is at most four items; the parity matters for any later prompt.
2. **Bar judge.** `backend/evaluation/s_metrics.py` gains a `judge(rate, n, bar, direction)` that
   emits `{meets_point, straddles, demonstrated}` for S2 and S3 plus the literal S5 = 0. Re-scoring
   the same replay twice gives byte-identical `metrics.json` (sha256). Expected [C]: S2 not-pass
   and marginal or fail, S3 fail.
3. **Noise floor in the tool.** `synthbench replay` has no repeat option today (`--model`, `--url`,
   `--limit`, `--export`; `synthbench/commands/replay.py:37-45`). Add `--repeat N` and report the
   per-item flip rate at the medium boundary and the min-max of S2/S3. A rung's claimed gain must
   exceed it. Starting point: three readings exist (§2.1) and 62% item-level agreement between
   two runs [V]. Reporting S2/S3 as a mean over repeats, or at a fixed seed with the choice
   recorded in the conditions line, is the handoff's own first consequence (Addendum 3; the
   register carries it in the acceptance of ISS-043 and in ISS-078). Dated note, 2026-10-03: the
   shipped call has been greedy since `9f4e65cd`, and Addendum 4 recommends stating temperature 0
   on the conditions line; `--repeat N` then verifies reproducibility rather than sizing sampling
   noise (§3 finding 1).
4. **S3 both ways** (band-midpoint floor and declared-band-minimum floor) until OD-2 rules. The
   floor is derived from the band midpoint (`backend/evaluation/levels.py`,
   `floor_for_expected_score`; `backend/evaluation/eval_store.py`, `_midpoint`) [V].
5. **Production-condition table.** (a) ideal detector (today), (b) real YOLO26 detections frozen
   into `AssessInput.detections`, (c) plus stored specialist outputs. The a-to-b delta is the
   detector tax. The export needs a builder step that runs `DetectorClient` and the specialist
   stage once on the stills.
6. **Per-scenario S3** with its n and an "insufficient" rule (§2.3: 12 of 19 incident scenarios
   at n = 9).
7. **Paired report.** Exact McNemar or a bootstrap on discordant items, extending
   `comparison` in `synthbench/score/metrics.py:195` (it lists the items one model gets wrong that
   the other gets right, with no interval) [V]. A deliberately degraded build (revert the image
   token cap, drop `frame_detection_ids`, raise the temperature) is flagged as a regression; a
   build compared with itself reads "no change".
8. **Prompt-render goldens** for fixed `AssessInput` fixtures, so a prompt or frame-time edit needs
   an explicit golden bump.
9. **S4′.** p50 and p95 on at least 200 batches on the A5500 from the existing `total_pipeline`
   stage metric (`backend/services/pipeline_workers.py:1080`; its clock is the first file's arrival
   at the watcher, `backend/services/file_watcher.py:881`, stored once per batch at
   `backend/services/batch_aggregator.py:429`), stated against the [C] floor of 36-41 s for a
   single-still batch (30 s idle timeout and up to 5 s check interval,
   `backend/core/config.py:925-962` [V], plus about 6 s warm verdict, ledger median 5,982 ms [A])
   and, for a busy batch, up to the 90 s window plus the verdict. Spec S4 is the p95 per-batch verdict
   (`docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md:86`), and the
   `batch_to_analyze` metric starts at analysis (`backend/services/pipeline_workers.py:1065`), so
   neither sees the idle wait [V].
10. **Operating curve and AUROC** as a standing report section. Starting point from §2.2: about
    0.70 [C].
11. **Identity.** Score identity records the weights hash (today `unrecorded`), the prompt hash,
    the served config and a dirty-tree flag (ISS-045, ISS-046).

**Builds on [V].** `backend/evaluation/vlm_replay.py` (`replay_item`);
`backend/services/vlm_analyzer.py` (`apply_verdict_invariants`, to be moved into a pure module so
evaluation does not import the analyzer; `vlm_replay.py` imports none today);
`backend/evaluation/s_metrics.py`; `backend/evaluation/eval_store.py` (a run manifest beside the
run); `synthbench/run/replay.py`, `synthbench/score/metrics.py`, `synthbench/score/report.py`;
`synthbench/export/vss.py`; `.github/workflows/ci.yml` for the hermetic tier. Patch the spec's
S2/S3 rows with an F14 pointer in the same change (OD-3; the register's ISS-081 carries the stale
`[?]` rows, and the owner approves the spec revision).

**Needs.** GB300 replays through `agent-gpu`, about 17-19 minutes each for the 8B: 18m43s in the
committed report, and at most 17m44s and 16m52s from replay start to the score for the two
2026-10-03 runs (`started_utc` in each `run.json` against `created_utc` in each score's
`metrics.json`, so an upper bound that includes scoring) [V]. `synthbench replay` refuses to run
from a sandbox without `systemctl` (`synthbench/run/replay.py:114`); the 2026-10-03 runs used the
same harness without that one check
at the owner's direction (handoff Addendum 2), and OD-5 settles the rule. Handoff Addendum 5
(decision 4 [O]) directs that replays keep running with the check bypassed under the `agent-gpu`
fence, each run labelled `renderer_check: SKIPPED` in its `run.json`; a committed, tested way to
do that is the register's ISS-079. The same runs needed `ENVIRONMENT=development` and a
placeholder `DATABASE_URL` to get past the settings validators (handoff Addendum 2; ISS-082).

**Issues.** ISS-007, 014, 015, 017, 024, 043, 045, 046, 079, 081, 082.

### L3. Actionable, auditable verdicts (closes M1) [?]

**Capability.** Every verdict class has a defined user-visible action, and a failed or abstained
verdict is never silent. For any event the owner can open a record of what the VLM saw, what it
said, how it was clamped and which specialists were available.

**Exit bar [?].**

1. The spec's "null-score delivery end to end" test is green and table-driven over `confirmed` ×
   four score bands, `uncertain`, `rejected` and `verification_failed` with and without a person at
   or above `detection_confidence_threshold`: database → WebSocket → "unverified" badge →
   detector-only notification, no acknowledgment (spec §7,
   `docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md:377`). `rejected` never
   notifies even with a camera `risk_threshold` inside the low band (spec §6) [V].
2. An AST guard on the pattern of `backend/tests/unit/test_no_legacy_pipeline_branches.py` fails if
   `should_notify`, `evaluate_event` or `deliver_alert` loses its last non-test caller. Today none
   has one: a grep of non-test `backend/*.py` at `5c605e1d` finds only the definitions
   (`backend/services/notification_filter.py:35`, `backend/services/notification.py:633`,
   `backend/services/alert_engine.py:166`), two docstring examples
   (`backend/services/notification.py:10`, `backend/services/alert_engine.py:22`), a docstring
   mention that is not a caller (`backend/services/notification_filter.py:100`, "moved verbatim out
   of `should_notify`") and an unrelated route handler that happens to be named `evaluate_event`
   (`backend/api/routes/ai_audit.py:193`) [V].
3. Every new `event_verifications` row has a linked `llm_interactions` row holding the raw model
   JSON (or the error class), the pre-clamp score, a prompt template version, temperature and
   attempt, image sha256 and size, the `_fitted_prompt` truncation record and the structured
   specialist outputs. `GET /api/llm-reasoning/events/{event_id}` returns 200 for a VLM event.
   Today it cannot: nothing outside tests builds an `LLMInteraction` (grep for the constructor
   finds only the model's own `class` line and `__repr__` string), and the route answers 404 when
   no row exists, while the modal still mounts the explorer
   (`frontend/src/components/events/EventDetailModal.tsx:693`) [V].
4. `/alerts` has no `risk_score || 0` site and shows a verdict badge. Today
   `frontend/src/components/alerts/AlertsPage.tsx:116` and
   `frontend/src/components/alerts/AlertCameraGroup.tsx:74` coalesce a NULL score to 0 [V].
5. New counters and promtool-tested rules for the `verification_failed` ratio, verdict mix,
   `uncertain` ratio, output-truncation share and the `ai-vlm` degraded state, and a producer for
   the score histograms that already exist (below). Series that exist and are fed today:
   `hsi_pipeline_errors_total` (reasons `vlm_verification_failed`,
   `backend/services/vlm_analyzer.py:561`, and `vlm_circuit_open`,
   `backend/services/vlm_client.py:766`), `hsi_prompt_truncated_total` (prompt-fit truncation, not
   output truncation), `hsi_ai_service_degraded` (set for `ai-vlm` by `VlmClient._push_unhealthy`)
   and `hsi_specialist_unavailable_total` (`backend/core/metrics.py:3388`). Registered and alerted
   on but never observed on the VLM path: the histograms `hsi_risk_score` (`RISK_SCORE`,
   `backend/core/metrics.py:454`) and `hsi_risk_score_distribution` (`RISK_SCORE_DISTRIBUTION`,
   `:474`) and the counters `hsi_risk_tier_total` (`:483`) and `hsi_events_by_risk_level_total`
   (`:461`). The `score_calibration_alerts` group of `monitoring/ai-pipeline-alerts.yml`
   (`RiskScoreCalibrationDrift` and `RiskScoreAllCritical` among its rules) reads
   `hsi_risk_tier_total`, so by reading its expressions it cannot fire on this path [?: read, not
   run]. Their writers
   `observe_risk_score`, `observe_risk_score_distribution` and `record_event_by_risk_level` have no
   non-test caller (a grep of non-test `backend/*.py` finds only their definitions in
   `backend/core/metrics.py`), and `backend/services/vlm_analyzer.py` imports only
   `record_pipeline_error` from that module [V], so L3 wires the existing producers instead of
   adding a second histogram. Missing: a verdict-mix, uncertain-ratio or output-truncation series.
   The grep of `monitoring/` finds no rule keyed on the VLM reasons, `hsi_ai_service_degraded`,
   `hsi_specialist_unavailable_total` or `hsi_prompt_truncated_total`; the rules on
   `hsi_pipeline_errors_total` aggregate over every `error_type` (`monitoring/prometheus_rules.yml`)
   or key on other values (`detection`, `analysis` and `clip_anomaly.*`, in
   `monitoring/prometheus-rules.yml` and `monitoring/ai-pipeline-alerts.yml`), and a dashboard JSON
   uses `hsi_prompt_truncated_total` [V]. There is no
   `promtool test rules` unit test and no `promtool` step in any workflow under `.github`; the
   Validation section of `monitoring/AGENTS.md` documents a manual `promtool check rules` run over
   the seven rule files, and `backend/tests/unit/core/test_prometheus_rules.py` checks the rule
   YAML in Python [V].
6. Failures are never silent: a batch lost outside the VLM ladder gets an event row or a retry; a
   `verification_failed` row carries an enumerated reason; a re-verification path heals events
   after the VLM recovers (ISS-042, 032, 010).
7. `NotificationFilterService` band parity (L1), the NULL-score path honours camera-enabled and
   quiet hours (ISS-019), and a delivery record exists so someone can prove a human was told
   (ISS-049).
8. The frontend alert push (the `useIntegratedNotifications` wrapper's `showSecurityAlert`, over
   the desktop and push hooks) has a non-test caller on a WebSocket event.

**Builds on [V].** Reuse the orphan `backend/models/llm_interaction.py` instead of adding columns:
the repo is `create_all`-only (`backend/core/database.py:408`) and an ALTER needs a hand-run SQL
file under `docs/api/migrations/`. `raw_response` and `enrichment_snapshot` are NOT NULL and the
event FK cascades on delete (`backend/models/llm_interaction.py:54-61`), which also makes the FK
the only retention path. Write it in the analyzer's second session beside `EventVerification`
(`backend/services/vlm_analyzer.py:574-609`), persisting only what `Event.llm_prompt` lacks
(`:586` stores the prompt and the key-frame paths). Add a `PROMPT_TEMPLATE_VERSION` constant beside
`_ASSESS_MAX_TOKENS` (`backend/services/vlm_client.py:91`). After the write, call
`NotificationFilterService.should_notify`, then `deliver_alert` and a frontend push
(`frontend/src/hooks/useIntegratedNotifications.ts`, `usePushNotifications.ts`). Make
`alert_engine.evaluate_event` a production caller or delete it. Metrics in
`backend/core/metrics.py`, rules beside `monitoring/ai-pipeline-alerts.yml`.
`backend/main.py:1132-1150` registers `ai-vlm` with breaker-push health by design (probe polling
would conflate sleep with failure) and `critical=False`, so the metrics must expose its health
(ISS-058). Retire `pipeline_quality_audit_service` self-critique as a quality signal: a model
grading itself is not evidence.

**Privacy.** Specialist texts (face names, plates) touch R13, which has no retention clock,
consent record or erasure path. The FK cascade stays the only retention path.

**Needs.** An owner ruling on touching the notification path (OD-4). The reviewers disagreed on
whether the ledger marks it owner-owned, so treat it as needing one [?].

**Issues.** ISS-001, 010, 011, 013, 019, 020, 031, 032, 034, 041, 042, 047, 048, 049, 058.

### L4. Time-aware evidence [?]

**Capability.** Video is no longer a hole. Same llama.cpp engine, same `VlmVerdict`, no new
resident model. Video and multi-still batches produce a chronological frame set, each frame
carries its capture time or clip offset in the prompt, and the frames the VLM saw are kept until
the event is deleted. The frame count rises above four only if S4 holds. This frame-burst
carriage is the **control arm** any video-VLM must beat (L7), and the fallback if none does. L4
claims no quality: L7 measures it. It runs beside L3 once L2's noise floor exists.

**The hole today [V].** The detection rows of a video frame carry the clip as `file_path`
(`backend/services/detector_client.py:1174` sets `detection_file_path = video_path`; the row is
built at `:1281-1283`). The extracted JPEGs are removed in an unconditional `finally` of
`DetectionQueueWorker._process_video_detection` (`backend/services/pipeline_workers.py:746`, calling
`VideoProcessor.cleanup_extracted_frames`, `backend/services/video_processor.py:812`). The selector
therefore sees one file, picks one frame, and `_image_parts` refuses its `.mp4` suffix, so the
batch should end `verification_failed` with a NULL score; the comment at
`backend/services/vlm_client.py:472` calls it "the shipped path's known gap". That chain is
**code reading, not executed** [?]; L4's first exit bar executes it.

**Exit bar [?].**

1. Video-origin batches ending in `VlmImageError`: 0 (today 100% by construction), shown by an
   ingest-path integration test (fixture mp4 plus `FakeProvider`) and a GB300 live run on at least
   50 ready clips, with S5 = 0 for batches that reach the engine.
2. 100% of multi-frame requests render a per-frame time line. With `frame_times` absent the prompt
   is byte-identical to today's (a golden pin; the precedent is `frame_detection_ids`,
   `backend/services/vlm_verdict.py:115`).
3. No stills regression on the 450 sets: S2 and S3 inside the L2 noise floor, by the paired
   report.
4. S4 p95 ≤ 30 s including cold start and S1 ≤ 20.4 GiB on 24 GB-class hardware (spec S1/S4;
   the GB300 is not admissible).
5. Frames are retrievable by event id until retention deletes the event.

**Builds on [V].**

- Keep the selected frames in an evidence directory instead of deleting them; store a per-detection
  frame offset. A new table is free under `create_all`; an ALTER on `detections` needs a hand-run
  SQL file. `VideoProcessor.extract_frames_for_detection_batch` already exists
  (`backend/services/video_processor.py:632`); the worker calls it with
  `video_frame_interval_seconds` 4.0 and `video_max_frames` 20 (`backend/core/config.py:2245`,
  `:2595`).
- Chronological presentation order and a temporal-diversity term in `select_key_frames` (today
  strength then recency, one pick per (camera, class) pair and per file); the file identity becomes
  (`file_path`, offset) for video.
- `frame_times` as an optional, index-aligned field on `VlmAssessRequest`, default None. The limit
  of four is hard-coded in five places that must move together:
  `backend/services/key_frame_selector.py:37`, `backend/services/vlm_verdict.py:113` and `:117`,
  `backend/services/vlm_client.py:450`, `backend/evaluation/vlm_replay.py:71`.
- Replace the flat 1,280 vision tokens per frame (`backend/services/vlm_client.py:107`) with a
  per-frame estimate from header dimensions (`VlmClient._frame_dims`): eight frames at the flat
  figure would reserve 10,240 of one 16,384-token slot [C: 8 × 1,280].
- Time lines come from `resolve_capture_time` (`backend/services/capture_time.py:61`).
  `_render_prompt` drops each row's `detected_at` when `CAMERA_TIMEZONE` is set
  (`backend/services/vlm_client.py:522-526`), which L4 reconciles with the per-frame lines.
- The capture-root guard in `_image_parts` (resolved path must lie under `foscam_base_path`,
  `backend/core/config.py:887`) must be widened deliberately to admit the evidence directory;
  `video_thumbnails_dir` defaults to `data/thumbnails` (`:2591`), outside it.
- Record the carriage in the stamped provenance engine string so `EventVerification.engine` slices
  metrics. Regenerate `scripts/gen-ai-contract.py`, the goldens under
  `backend/tests/contracts/ai_providers/golden` and the `FakeProvider` arm.
- Stored rows keep paths and never embed bytes (spec §6). `FrameBuffer` holds raw frames for a
  consumer that no longer exists (ISS-068) and is the wrong seed for the burst.

**Needs.** 24 GB hardware time (OD-5); a retention policy for the evidence directory (OD-6).

**Issues.** ISS-002, 005, 006, 030, 033, 065, 068, 070.

### L5. Verdicts that rank, plus abstention [?]

**Capability.** Make `risk_score` separate incidents from benign at **one** operating point (F14
ruling 3: one prompt, thresholds and build for both bars), and make "cannot call it" a first-class
outcome that notifies conservatively instead of silently scoring. Because §2.2 shows a remap
alone is capped, L5 tests four levers **separately**, each as its own arm on a development split,
plus one diagnostic:

- **(a) Prompt.** A band-anchored rubric sourced from the severity settings, not hard-coded;
  scoring after the criteria; camera context. Mechanism: the prompt today gives no anchor beyond
  "how threatening it is (`risk_score` 0-100)" [V]. The generated wire schema lists `properties`
  alphabetically (`criteria` first, `verdict` last) while `required` lists the declared order
  (`verdict`, `risk_score` first) (`backend/ai_contract/schemas/vlm_assess.response.json`) [V];
  which order llama.cpp's grammar emits is not established [?], and ISS-012 asks for a test that
  pins it.
- **(b) Inputs.** The L2 production-condition arms: real detections, stored specialist outputs.
- **(c) Remap and abstention.** A monotone map plus an abstain band (isotonic, fitted on the
  development split only), consumed through the existing severity thresholds, not as a new score.
  §2.2 gives its in-sample ceiling; the held-out figure is the test.
- **(d) Decoding.** Temperature 0 with a seed, or the mean of k samples. Mechanism: the run-to-run
  noise has a known cause (§2.2). Cost: k samples multiply latency against S4, so use it only on
  abstain-band batches or not at all. Handoff Addendum 4 records two temperature-0 replays
  (`20261003T134900Z-qwen3-vl-8b-T0` and `20261003T141303Z-qwen3-vl-8b-T0`), an experiment with the
  request's `temperature` forced to 0 by a transport shim in a scratch driver, not the shipped
  path: identical (`verdict`, `risk_score`) on 450 of 450 items, S2 18/209 = 8.6%, S3 88/241 =
  36.5%, 0 refusals [V, read from the handoff]. Those figures sit on the temperature-0.1 means (S2
  17.0 = 8.1%, S3 86.3 = 35.8%), so temperature 0 removes the noise and does not move accuracy:
  this lever is a measurement-reproducibility lever, not an accuracy lever. **Dated note,
  2026-10-03:** the temperature-0 half of this lever is no longer open. The owner decided to move
  the shipped call to temperature 0 (handoff Addendum 5, decision 3 [O]) and `9f4e65cd` did it
  (handoff Addendum 6): `_ASSESS_TEMPERATURE = 0.0`, pinned by `test_assess_samples_greedily`, which
  also asserts that no `seed` is sent. What this arm proposed at the pin and is still open is a
  seed and the mean of k samples [?]; OD-7 holds that question and the register carries the lever
  as ISS-078.
- **(e) Diagnostic E1, accuracy only on the GB300.** The same prompt on two larger VLMs, to say
  whether the gap tracks model size or score mapping, with no expectation either way. The flagship
  already reads S3 58.9% at this prompt (§2.1). The ledger relays that on `b7972` the `json_schema`
  path failed 75-100% against one candidate's GGUF, so that candidate may need a newer llama.cpp
  pin (the "LARGER-MODEL SURVEY" entry, `docs/plans/2026-09-23-vss-gaming-gpu-ledger.md:309`)
  [A].

**Owner direction on the S3 experiments, 2026-10-03 [O].** Handoff Addendum 5 decisions 1 and 2:
the free S3 experiments (a severity-rubric prompt arm and a logprob-score arm, both at temperature
0, scratch-driver shims only, no repo change) run on the GB300 now, and whether S3 ≥ 90% is
attainable from a single still is decided after them, with the bar kept as is until then. They
correspond to arm (a) and to exit bar 7 below; their results were not in this document when it was
first written [?], and are now in the handoff's Addendum 8 (see the note below).
Handoff Addendum 4 also relays an agent analysis that emitted scores are polarised and that 64 of
241 incidents are stranger or intent scenes a single still may not separate from their benign
twins, which would cap S3 near 73% for any model on single stills [A: as relayed in Addendum 4].
**Update, 2026-10-03 (later, handoff Addendum 8).** Addendum 8 re-derives the grouping and the cap
and marks them [C] itself, from its own run; this document did not recompute them from the
replay, so they are [A: handoff Addendum 8, not re-derived here]. With arm A reproducing 88/241
and 18/209 at temperature 0, hits by scene type are 2/64 stranger-or-intent, 18/82 context-risk
and 68/95 object-cued, AUROC 0.703, recall 42.3% at 5% false alarms, and S3 caps at 177/241 = 73%
even with the other two groups perfect. Only the arithmetic is checked here [C: 2 + 18 + 68 = 88
hits and 64 + 82 + 95 = 241 incidents agree with arm A's 88/241; 82 + 95 = 177 = 241 − 64;
177/241 = 73.4%]. Also [A], and not re-derived in Addendum 8 either: the claim that scores are
polarised with 68% of them in {0, 5, 10}. The ceilings this document computes in §2.2 are different
quantities (the in-sample remap ceiling and the suspicious-scene video cap). The register carries
the experiments and the single-still ceiling as ISS-086.

**Results of the free experiments, 2026-10-03 (later; handoff Addendum 8, not re-run here) [A].**
Arm (a) was run as a rubric prompt (arm B) against the shipped prompt (arm A) on the 450 sets at
temperature 0: the rubric reads S2 34/209 = 16.3% and S3 105/241 = 43.6% against 18/209 = 8.6% and
88/241 = 36.5%, AUROC 0.778 against 0.703, and recall at 5% false alarms 53.5% against 42.3%. A
first-digit logprob soft score has AUROC 0.717 (arm A) and 0.771 (arm B) and no recall gain, so the
handoff reads no ranking headroom in the logprobs (an approximation: only the first digit's
alternatives are used). These are development arms, not a holdout: the rubric was written knowing
the corpus, so any adoption still needs the frozen split of exit bar 1. The rubric trades 17 more
hits for 16 more false alarms at the shipped medium threshold and fails S2 more badly, so the bars
stay as they are and the owner's decision on attainability from a single still is not taken here.

**Exit bar [?].**

1. A pre-registered, scenario-stratified, hash-pinned split of `tierb-v0` with a fixed seed.
   Tuning and calibration fit use the development part only; the held-out part is scored once.
   About 120 incident items are expected in the held-out part, so per-scenario n in the held-out part
   is about 4-10 (full corpus 9-19) [C], and most scenario slices will read `insufficient`;
   per-scenario claims need the full corpus or a pooled slice.
2. A held-out report: AUROC with an interval, a 10-bin reliability table with Wilson intervals, and
   S2/S3 at **one** operating point with the L2 statuses; the rate at which declared incidents are
   rated `rejected` (0 of 241 in run 1 and 0 of 240 scored in run 2, §2.2; the spec's go-live stop
   trigger is the same event seen in the field,
   `docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md:313`; a ≤ 1% bar is
   proposed [?]); and the rejection rate on phantom detections.
3. **If no single operating point meets both bars on held-out, the rung closes by recording**
   "bars not reachable by prompt and calibration on this model and corpus" and bringing it to the
   owner under spec rev 7 flip condition (iii)
   (`docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md:6-16`). The bars are not
   lowered; they are the owner's (F14).
4. An abstention table: coverage against selective risk at three abstain widths; the owner picks.
5. Test-retest flip rate after any L5 change ≤ the L2 noise floor plus a margin.
6. S5 = 0 on the 450 sets at the 1,024-token budget, with the truncation refusal rate tracked
   (handoff Addendum 3, consequence 3).
7. A probe records whether `b7972` returns token logprobs under a `json_schema` grammar. None is
   used today (grep of `vlm_client.py`) [V]; the probe pattern is `scripts/vlm_probes/enforcement.py`.
   Note, 2026-10-03 (later): handoff Addendum 8 requested token logprobs through a scratch transport
   shim and scored a first-digit soft score (AUROC 0.717 and 0.771, no ranking headroom) [A]; that
   is an experiment, not this probe, which still asks whether the engine returns logprobs under the
   `json_schema` grammar.

**Builds on [V].** `backend/services/vlm_client.py` (`_render_prompt`);
`backend/core/config.py` severity settings and `validate_severity_thresholds`; a new pure-Python
`backend/evaluation/calibration.py` (reliability, AUROC, Brier, isotonic; scipy is not a declared
dependency); a phantom-detection export variant in `synthbench/export/vss.py` (it emits only
declared, true detections; `EvalItem` has no `expected_verdict`, so this needs a new generation,
precedent `build_gen2` at `backend/evaluation/eval_store.py:599`); `synthbench/run/models.py` rows
for E1 (the registry is `MODELS` of `Model`, with transports `ai-vlm` and `vllm`). Any threshold
change must keep `frontend/src/utils/risk.ts` in step (`backend/evaluation/levels.py` pins them
together). Do **not** wire `CameraCalibration` or `FeedbackProcessor._auto_adjust_offset`
(`backend/services/feedback_processor.py:294`): it steps an offset on a feedback-click false-positive
rate with no interval, no holdout and selection-biased input, and nothing but a docstring imports
the processor.

**Needs.** Prompt-only work needs no 24 GB box (the ledger's close pointer, "S2/S3/prompt work
does not", `docs/plans/2026-09-23-vss-gaming-gpu-ledger.md:423`); re-check S4 and S5 if prompt
length grows [?]. OD-7.

**Issues.** ISS-008, 012, 016, 078, 086.

### L6. Real-corpus evaluation with human corrections [?]

**Capability.** S2/S3 on the owner's own events with unbiased sampling. Each correction becomes an
eval item that carries the exact input the VLM saw. Drift is watched against the replay estimate,
and the first real-versus-synthetic gap is quantified.

**Exit bar [?].**

1. The eval store holds at least 100 benign and 20 incident real-camera items with media (the spec
   M0 size, `docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md:255`;
   `backend/evaluation/label_import.py:606`, `m0_size_report`), including a random-audit stratum of
   at least 50 benign items, not only owner-flagged false positives.
2. A first real-corpus S2/S3 table with Wilson intervals and "demonstrated" flags, beside
   `tierb-v0`. 100 benign items at 0 false positives can only demonstrate S2 ≤ 3.7% [C: Wilson
   upper bound of 0/100].
3. The alarm budget in owner terms: expected false medium-or-higher alerts per day = S2 × benign
   events per day. F14 puts 5% at about one a day at 20 benign events a day, so the 8.1% mean of
   §2.1 is about 1.6 a day [C: 0.081 × 20].
4. The spec's go-live stop triggers
   (`docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md:313`) implemented as
   queries and dry-run on at least 14 days of real events.
5. Owner labeling cost measured in labels per minute.
6. A **blind or free-answer** audit. The current `synthbench audit` asks "Does this show X?"
   (`synthbench/audit/sample.py:75`) and got 60 of 60 yes, a weak test of truth.

**Builds on [V].** A review queue fed by the L5 abstain set, a random stratum of low-score and
`rejected` events, and owner feedback. Reuse the audit pattern (`synthbench/audit/sample.py`,
`synthbench/audit/page.py`: a localhost page, an append-only log, latest answer wins) but show the
still first, take a free or multiple-choice answer, then reveal. Replace the feedback taxonomy
(`frontend/src/components/feedback/FeedbackPanel.tsx:65-73` and
`backend/api/schemas/feedback.py:119-127` list retired models) with
`detector_missed`, `detector_false`, `vlm_misread`, `score_too_low`, `score_too_high`, `face_wrong`,
`plate_wrong`, `reid_wrong` and `wrong_frames_shown`, each mapped to a report slice.
`backend/evaluation/control_freeze.py:96` (`map_feedback`) makes benign only from `false_positive`
and leaves accurate-on-low and `severity_wrong` unlabeled, so a real S2 built from feedback alone
is selected on false positives; `backend/evaluation/label_import.py:166-168` writes `zones=[]` and
`household={}` into its snapshots, so source them from the L3 trace instead. The eval-store guard
must learn the real capture root (ISS-061). Real media stays off-repo (D10).

**Needs.** L3 (trace) and L5 (abstain set). Owner labeling effort is unmeasured, and the owner's
Foscam stills on the A5500 box are unverified [?]. OD-9.

**Issues.** ISS-044, 061, 066, 067.

### L7. Clip eval and the temporal-value gate [?]

**Capability.** The single go/no-go for L8-L10. Make video measurable before any video engine is
built, with a paired ablation on the same clips. **Arm A:** the single best still. **Arm B:** K
frames plus times through the shipped `VlmClient` (L4). **Arm C:** the GB300 flagship with frames,
a non-shippable ceiling, and with native `video_url` only if its endpoint accepts it [?]. Report
S2, S3, verdict mix and S5 with Wilson intervals, and print pass or fail against the F14 bars. The
rung ships a measurement capability and a decision, not product behaviour.

**Exit bar [?].**

1. At least 100 ready incident clips and at least 100 ready benign clips, scored on all arms.
2. An owner audit of at least 60 clips, blind or free-answer, with a truth-error interval. Clip
   truth is inherited from the still by declaration (clips design C5), and the owner waived the
   pilot gate (C10) so the design has no clip audit, leaving one to whoever first uses the clips
   (C13) (`docs/superpowers/specs/2026-09-30-synthbench-h3-clips-design.md:34` and `:42`) [V].
3. **A pre-registered decision rule:** build L8 only if the best non-A arm raises S3 over arm A by
   at least 10 points (paired, lower interval bound above 0) with S2 no worse than +2 points.
   Otherwise L4's frame burst is the shipped video answer and the remaining S3 gap is handed to L5.
   Both constants are placeholders [?].
4. The report prints pass or fail against S2 ≤ 5% and S3 ≥ 90%, which nothing prints today.
5. Slices follow `MIN_N = 10`; n = 100 gives about ±10 points at p = 0.5 [C: 1.96 × √(0.25/100)].
6. **Claim scope.** A perfect fix of all suspicious scenes caps S3 near 54% (§2.2), so the gate
   cannot justify a video engine on S3 grounds alone. A better S2, or a clip-specific
   verdict-changing case, is also needed.

**The clip supply today [V, live snapshot].** Read 2026-10-03 from
`/synthbench/corpus/tierb-v0/clip-index.jsonl`, latest status per event (459 events; it may
drift): `ready` 164 (benign 144, incident 17, ambiguous 3), `failed` 80 (benign 65, incident 9,
ambiguous 6), `prompted` 205 (all incident), `rendered` 10 (all incident). The 17 ready incident
clips are `loitering` 5, `tailgating` 5, `trying_car_doors` 4, `peering_into_windows` 2 and
`casing_with_phone` 1. **None of the 196 threat clips is ready**, all 196 are `prompted`.
`hooded_jogger` has 5 ready and 24 failed. So the bar of 100 ready incident clips is unreachable
today without re-prioritised rendering toward threats, new motion wording for lateral movement, a
new corpus version or owner clips. One probe clip took 328.7 s for 243 frames beside the flagship
(`docs/benchmarks/synthbench/clips-probes.md:58`) [V]; rendering the 205 prompted at that rate
takes about 18.7 hours before rerolls [C: 205 × 328.7 s], and 80 of 244 triaged clips have failed
so far [C: 80/(164 + 80)].

**Builds on [V].**

- `synthbench/export/vss.py`: export clip sets with the same category map and declared-truth
  label.
- `backend/evaluation/assess_input.py`: `EvalItem` is frozen (`:46-55`), so clip or frame fields
  need a new store generation or a sibling store (precedent `build_gen2`).
- `backend/evaluation/vlm_replay.py`: arm parameters. Note the replay feeds an item's
  `media_paths` straight to the client and deliberately has **no key-frame selection** (module
  docstring), so selector behaviour and frame order are unmeasured by any current replay
  (ISS-037).
- Per-frame detections need a real YOLO26 pass over clip frames, because the ideal-detector
  injection carries no per-frame or track information.
- Finish `clips-1` rendering **serialised** with replay: `renderer_stopped` refuses while the
  renderer runs, and the flagship must stay resident (spec D12).
- Spec rev 8 must allow what the clips design rejected, "clips sampled into still bursts, scored
  by the product VLM"
  (`docs/superpowers/specs/2026-09-30-synthbench-h3-clips-design.md:407`), as the **control arm
  only** (OD-3).

**Needs.** OD-8 (clip supply), OD-3, OD-5.

**Issues.** ISS-003, 037, 038, 063.

### L8. A video-VLM option behind `vlm_assess` [?]

**Capability.** Built only on an L7 "go". One op id and one `VlmVerdict`; the request gains a
mutually exclusive clip carriage. `VlmClient` chooses the carriage by provider capability (native
`video_url` for engines that take video, frame parts for llama.cpp) and provenance records which.
The degradation ladder becomes: video engine, then frame burst (L4), then single best still, then
the detector-only rule (spec §6).

**Exit bar [?], on 24 GB-class hardware.**

1. Beats arm B on the L7 clip set by the L7 rule.
2. S1 ≤ 20.4 GiB with detector, specialists and the VLM resident and no CPU offload (spec S1).
3. S4 p95 ≤ 30 s including cold start.
4. S5 = 0 on clip items.
5. `scripts/gen-ai-contract.py --check` clean, the conformance suite green including a clip arm,
   and `FakeProvider` coverage (spec S6).
6. A fault-injection test (the `FakeProvider` fault knobs, `backend/ai_contract/fake/app.py:57`)
   shows each ladder step degrades without a fabricated NULL score.
7. If no engine passes S1 and S4 on 24 GB, record the negative result and keep L4; the option is
   then 32 GB-tier only (R11).

**Builds on [V].** `backend/services/vlm_verdict.py`: `image_paths` is 1-4 and required (`:113`);
relax it to exactly one of image paths or a clip (a path under the capture or evidence root, start
and end, a sample-rate cap), with the response unchanged. `backend/ai_contract/operations.py` keeps
op id `vlm_assess` (`:81`); the registry's path for the op is `/vlm/chat/completions`, while the
shipped client posts to `/v1/chat/completions` (`backend/services/vlm_client.py:85`). In
`backend/ai_contract/providers.py:188-194`, `OPENAI_VLM` and `RTVI_VLM` both register with
`deployed=False`; add a capability declaration (carriage: frames or video) and flip `deployed`
only for the engine that passes. A new compose profile beside `ai-vlm`
(`docker-compose.prod.yml:154`).

**Candidate engines, fit and mechanism only.**

- **vLLM, OpenAI-compatible**, serving a small Qwen3-VL-class model. The GB300 replay already
  drives vLLM endpoints (`synthbench/run/models.py`); whether the endpoint accepts `video_url` is
  unverified [?].
- **RT-VLM in integrated vllm-compatible mode**, which accepts `video_url` and `image_url`
  ([`09`](09-audit-integration-surfaces.md): "Content parts are only `text`, `image_url` and
  `video_url`") and has EVS token pruning, video only, which VSS's own benchmark reports as
  26.7 s to 14.2 s per 30 s chunk on one model ([`10`](10-audit-feature-inventory.md) F6;
  **[E]**, not re-measured here). It reserves
  GPU memory at init and has no unload ([`10`](10-audit-feature-inventory.md) §6 item 2,
  [`12`](12-postponed-roadmap.md) R9), so it would replace or time-share `ai-vlm`, not co-reside.
- llama.cpp `b7972` has no `video_url` ([`09`](09-audit-integration-surfaces.md) **[E]**), so it
  stays the frames carriage.
- Whether any of these fits 24 GB beside the detector is unmeasured [?]. A 4B-class llama.cpp
  fallback failed S5 (8 of 13 truncated; the ledger's A5500 run entry,
  `docs/plans/2026-09-23-vss-gaming-gpu-ledger.md:411`) [A].

Spec §3 Engine 2 says the RT-VLM adapter "tiles the key frames into one composite"
(`docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md:176-177`) [V]; tiling is the
wrong use of its video differentiator, and rev 8 amends it (OD-3).

**Issues.** ISS-003 is the decision; no register issue is the build.

### L9. Tracks, dwell and cross-event memory [?]

**Capability.** Built only on an L7 "go" plus labeled data. A CPU tracker runs over per-frame
detections of a clip and writes `Detection.track_id`, which makes zone crossing real. Per-track
summaries (first and last seen, dwell seconds, displacement, direction against the zone) replace
per-frame detection rows in the prompt. A post-verdict writer stores person embeddings so the
re-ID specialist can say "seen earlier on camera X".

**Why the seams are empty today [V].** No non-test code sets `Detection.track_id` (the column is
`backend/models/detection.py:64`; none of the `Detection(...)` constructors in
`backend/services/detector_client.py`, `backend/api/routes/admin.py` or
`backend/api/routes/detections.py` passes it), so `detect_zone_crossing`
(`backend/services/vlm_analyzer.py:169`) is structurally false while `_render_prompt` prints
`(crossing: False)` as a fact. `TrackService.create_or_update_track`
(`backend/services/track_service.py:78`) has docstring callers only. The entity store has no
production writer: outside tests, the only code that calls `store_embedding` or
`store_detection_embedding` is those two services' own methods
(`backend/services/reid_service.py:761`, `backend/services/hybrid_entity_storage.py:310`) and
docstring examples; no route or pipeline stage does (grep). The gateway's `enrich_lt_person_reid`
op has no backend client method (`backend/ai_contract/operations.py:14-26`). The re-ID specialist
compares to the household gallery only (`backend/services/vlm_specialists.py`,
`collect_reid_text`). The gateway has no tracker route (the yolo26 `/track` route was deleted in
`2ab66ff1`, 2026-09-19).

**Exit bar [?].**

1. Tracker, on L7 clips with exactly one declared subject: at least 90% yield one track covering at
   least 80% of frames; ID switches are reported.
2. `detect_zone_crossing` is no longer constant False on a zone-crossing fixture set, and until
   then crossing renders as "unknown" (ISS-035).
3. Prompt text tokens for a 20-frame clip are no larger than the L4 single-frame budget.
4. Memory: false-merge rate ≤ 2% with recall, both with Wilson intervals, on a purpose-built
   same-cast two-event set. **No such set exists**: `tierb-v0` events are single stills, so it needs
   Tier A generation (sites and a consistent cast, listed as out of scope of the current generation
   design, `docs/superpowers/specs/2026-09-28-synthbench-agent-driven-generation-design.md:26`) or
   new generation. Calibrate `reid_similarity_threshold`, provisional at 0.7
   (`backend/core/config.py:1713`). A false "same person as 10 minutes ago" pushes the VLM toward
   alarm, an S2 driver, so memory ships only with a measured false-merge rate.
5. S2/S3 not worse than L4 or L8 on clips; S4 ≤ 30 s with the tracker running.

**Builds on.** A tracker (BoxMOT or roboflow trackers, per [`14`](14-specialist-model-research.md)
"Trackers"; trackers only help within a clip, re-ID links separate uploads) fed by denser sampling
than 4.0 s and 20 frames. Optional `Track` rows. A new specialist key: `SPECIALIST_KEYS` is a
closed frozenset (`backend/services/vlm_specialists.py:881`) while `specialist_outputs` is
`dict[str, str]` (`backend/services/vlm_verdict.py`, `VlmAssessContext`), so no contract change.
An entity writer through `HybridEntityStorage.store_detection_embedding`, using either the resident
Triton `reid` model via `/enrich-lt/person-reid` or the in-process `osnet_loader`. Embeddings stay
partitioned by model id. Doc 14's shortlist is a proposal whose premises are partly stale (it
assumes a CLIP-era re-ID and a resident SigLIP2 tower; re-ID is OSNet-AIN today), so re-read it
before building. Biometric traces fall under R13.

**Issues.** ISS-035, 036, 054.

### L10. Segment ingest and multi-camera incidents [?]

**Capability.** A segmenter writes 10-second clips into the watched root, so the existing
`file_watcher` → detector → batch path is reused (the "ingest-agnostic" seam R1 relies on, which is
true for stills and not for video until L4). A motion gate runs ahead of YOLO26. An incidents table
groups events across cameras and time, and a text-only roll-up runs through the same `ai-vlm` with
no new images (VSS's incident-consolidation concept, doc 10 F11, not its service). Notifications
dedupe per incident.

**Exit bar [?].**

1. The R1 reopen trigger is met: M3 holds 14 days ([`12`](12-postponed-roadmap.md) index, spec
   `docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md:482`). M1 and M2 are not
   closed today.
2. S1 ≤ 20.4 GiB re-measured on 24 GB hardware with continuous decode for N cameras, NVDEC and SM
   headroom measured, not asserted.
3. S4 p95 ≤ 30 s unchanged.
4. Incident-level S2/S3 with Wilson intervals on a multi-camera set. **No such set exists**; it
   needs Tier A (anchored sites, consistent cast) or owner data.
5. At most one notification per incident on that set.

**Builds on [V].** `go2rtc` already runs for live view (`docker-compose.prod.yml:856`);
`StreamManager` has no runtime importer beyond the package re-export
(`backend/services/__init__.py:305` and `:491`), and the MQTT/Frigate chain is unwired
([`12`](12-postponed-roadmap.md) R2). An ffmpeg segment writer into `foscam_base_path`; a new
`incidents` table referencing event ids (`Event` is single-camera with a unique `batch_id`); a
text-only roll-up through the `VlmClient` seam with a new constrained schema; dedupe in
`should_notify` once wired (L3). Do not use RT-VLM's live-alert mode, which fires on the substring
"yes" ([`10`](10-audit-feature-inventory.md) F3; [`12`](12-postponed-roadmap.md) R1).

**Issues.** ISS-039.

## 5. Reference architecture

### 5.1 The pipeline

```text
video ingest ──► detector gate ──► evidence assembly ──► VLM reasoning ──► verdict ──► action
```

Each stage reads "today" ([V] at `5c605e1d`, with its seam) and "new" (the rung that adds it).

1. **Ingest.** Today: FTP stills and clips through `backend/services/file_watcher.py` (native
   filesystem events by default, polling optional; `.jpg`, `.jpeg`, `.png`, `.mp4`, `.mkv`, `.avi`,
   `.mov`). New: an ffmpeg segmenter writing 10-second clips into the watched root (L10).
2. **Detector gate.** Today: `DetectionQueueWorker._process_video_detection` extracts frames (4.0 s,
   20 max), then YOLO26 through `DetectorClient` and the gateway. New: keep the selected frames and a
   per-detection offset (L4); a motion gate ahead of YOLO26 (L10).
3. **Batch.** Today: `BatchAggregator`, per camera, 90 s window and 30 s idle, with a wake of
   `ai-vlm` on batch open (`backend/services/batch_aggregator.py:676`). New: S4′ measured from the
   batch's first file arrival with the existing `total_pipeline` metric (L2).
4. **Evidence assembly.** Today: `build_frame_refs`, `select_key_frames`,
   `collect_specialist_outputs` (faces, plates, person re-ID) and `build_assess_context` into
   `VlmAssessContext`, the one snapshot shared by production and replay. New: a media-type filter
   (L1); order, `frame_times` and diversity (L4); per-track summaries and "seen earlier" lines (L9).
5. **VLM reasoning.** Today: `VlmClient.assess` is the registered `vlm_assess` op; the schema is
   derived from `VlmVerdict` by `scripts/gen-ai-contract.py`; a per-endpoint enforcement probe;
   temperature 0.1 then 0.0 (since `9f4e65cd`, 0.0 on both attempts); a 1,024-token budget;
   breaker `ai-vlm`. New: rubric, abstention and a decoding arm (L5); on an L7 go, a carriage
   chosen by provider capability (L8).
6. **Verdict.** Today: `apply_verdict_invariants` (`rejected` clamps to the low band), then `Event`
   and `EventVerification` in one transaction (`backend/services/vlm_analyzer.py:574-609`). New: the
   same invariants in replay (L2); an `llm_interactions` trace row in the same session (L3).
7. **Action.** Today: WebSocket broadcast and the dashboard; `should_notify`, `evaluate_event`,
   `deliver_alert` and the `useIntegratedNotifications` wrapper's `showSecurityAlert` (over the
   desktop and push hooks) have no non-test caller. New: the notification link plus
   an AST guard against losing the last caller (L3).

### 5.2 Contract rule

**No new `ai_contract` op.** `vlm_assess` gains optional fields only (`frame_times` in L4, an
exclusive clip carriage in L8). Everything is generated through `scripts/gen-ai-contract.py`, with
golden and `FakeProvider` updates, so drift is gated by `gen-ai-contract.py --check`. Prompt text and
calibration artifacts change behind `vlm_assess` and are gated by the L2 paired report and the
prompt-render goldens. A second op for a "lite" verdict is excluded: latency does not bind (§7).

### 5.3 Degradation ladder

After L8: video engine, then frame burst, then single best still, then the detector-only rule (spec
§6, `NotificationFilterService`). Each step records its carriage in the provenance engine string,
so replay and the S-metrics slice by it. Until L8: frame burst, still, detector-only.

### 5.4 Evidence tiers

- **T0, hermetic CI, no GPU.** `FakeProvider` conformance, prompt-render goldens, invariants parity,
  the bar judge, the notification decision table, caller guards, doc-currency checks.
- **T1, a GPU host through `agent-gpu`** (`synthbench replay` refuses from a sandbox without
  `systemctl`). `tierb-v0` replays, repeats, paired comparison. The GB300 is not admissible for S1
  and S4.
- **T1-24GB, owner hardware** (A5500, or a Brev A10G or L4). Every S1/S4 re-measure after a change
  to model, context, image handling or output budget.
- **T2, the real-corpus eval store**, off-repo (D10), fed by L6.

## 6. Reused from VSS, and built here

VSS is read through docs [`09`](09-audit-integration-surfaces.md) and
[`10`](10-audit-feature-inventory.md) at VSS `1e94133b4`; none of it was re-read upstream in this
session, so every VSS statement is as those docs mark it ([V] against VSS at that commit, or
**[E]**). The design imports patterns from the models layer and none of the storage or bus layers
([`AGENTS.md`](AGENTS.md), "Name the layer").

**Reused as a pattern or concept:**

- Constrained verdict output (doc 10 F4, `json_schema`): already shipped as `response_format` with
  an enforcement probe (`backend/services/vlm_client.py`).
- A `file://` plus allowlist idea (doc 10 §2.1): our analogue is the capture-root guard, which L4
  widens deliberately.
- RT-VLM's `video_url` contract and EVS pruning (doc 10 F6, video only) as an optional engine: L8,
  only on an L7 go.
- Incident consolidation and file summarisation concepts (doc 10 F11, F13) as a text roll-up and
  not as the services: L10.
- Human-in-the-loop prompts (doc 10 F23): the L6 review queue.
- Dedupe and confirmed-verdict protection as candidates for the notification layer [?]: L3, L10.

**Not reused:**

- RT-CV and NvDCF: stream-only, a 17.8 GB image ([`12`](12-postponed-roadmap.md) R1).
- Kafka, Elasticsearch, VIOS and behavior analytics: storage and bus layers; behavior analytics
  needs continuous tracks (doc 10 §8).
- RT-VLM live-alert mode: a substring "yes" trigger and no rejections recorded (doc 10 F3; doc 12
  R1).
- The critic agent (doc 10 F19) as quality evidence: a model grading a model needs its own
  calibration first.

**Built here, and kept as differentiators (doc 10 §6, partly re-checked).** §6 of doc 10 was written
against the pre-retirement tree, and its own 2026-10-03 banner calls the section stale without
enumerating survivors. Item 5 (the Florence cascade and the enrichment tier) is gone, deleted by
`602379e2` [A: from the earlier re-check of this paragraph, not re-run for this edit]. Items 1 (FTP
still ingest, `backend/services/file_watcher.py`, §5.1 stage 1) and 6 (the llama.cpp GGUF engine with
sleep-on-idle, the `ai-vlm` service in `docker-compose.prod.yml`) also survive but are not
differentiators the ladder builds on, so they carry no bullet below. Items 4, 8, 9, 10 and 11
were not re-checked here [?] and may survive in part (the prompt A/B harness of item 8 was deleted
by `d8482861`). These are the three that the ladder keeps:

- **Event-triggered compute.** 90 s and 30 s batching (`backend/core/config.py:925-934`), a wake on
  batch open (`backend/services/batch_aggregator.py:676`) and llama.cpp sleep after idle
  (`docker-compose.prod.yml:236`, default 300 s) [V].
- **A graded 0-100 score with a `SeverityService`-derived level.** The model never emits a level
  (`VlmVerdict` has no level field, `backend/services/vlm_verdict.py:55-72`) [V].
- **Single-GPU degradation.** The breaker named `ai-vlm`, the detector-only rule and the
  `DegradationManager` registration (`backend/main.py:1150`) [V].

What this project adds that VSS lacks and the ladder builds: stored `rejected` verdicts
(`EventVerification.verdict` carries all four values), the bar judge, noise floor and paired gate
(L2), the trace and notification wiring (L3), the calibrated verdict (L5), and the real-corpus loop
(L6).

**The roadmap, item by item.** The ladder touches [`12`](12-postponed-roadmap.md) as follows; none
of its items is picked up here without its own spec.

- **R1** is L10. Its stated premise, "ingest-agnostic", holds for stills only: a clip should fail
  today (L4 hole, code reading). Trigger unchanged (M3 14 days).
- **R2** is not on the ladder; L10 uses a go2rtc segmenter instead of the unwired Frigate and MQTT
  chain.
- **R3-R5** are not on the ladder. L3's trace and L10's incident table are prerequisites for
  reports and chat, and L3 settles whether `evaluate_event` lives (R5).
- **R6** is superseded as written: YOLO-World left the model set in R8
  (`backend/services/yolo_world_loader.py` is gone), and doc 14 names YOLOE-26 for a future slot.
  Not on the ladder.
- **R7, R9** are not on the ladder.
- **R8** is executed (`602379e2`, `3b73b9b6`, `392d69fd`); the ladder builds on the shipped
  VLM-only tree.
- **R10:** the 8B pick is provisional; L5's close-by-negative-result path and E1 are the only
  places the ladder can reopen it.
- **R11:** L4, L8, L9 and L10 each need a 24 GB re-measure; the Brev matrix has not run.
- **R12, R13:** ISS-063 (clips and corpus licences); L3 and L9 respect R13 and do not solve it.
- **R14:** a non-goal, no engine or model-pin change (§7).

## 7. Non-goals

1. **Not promising that video evidence fixes S3.** §2.2: a perfect fix of all suspicious scenes caps
   S3 near 54%; the video gain may be zero, and L7 exists to say so before L8-L10 are built.
2. **Not lowering or re-tuning the bars.** S2 ≤ 5% and S3 ≥ 90% are the owner's (F14). If no single
   operating point reaches both on held-out data, L5 records it and brings spec rev 7 flip
   condition (iii) to the owner. The owner's own sequencing agrees: keep the bar as is until the
   free S3 experiments are done, then decide whether 90% is attainable from a single still (handoff
   Addendum 5, decision 2 [O]). The experiments are done as of handoff Addendum 8 (2026-10-03,
   later; S3 105/241 = 43.6% on the rubric arm, a development arm) [A]; the owner's decision is
   still open [?].
3. **No new `ai_contract` op for video or triage.** A stakes-ordered scheduler, a "lite" verdict op
   and an early-verdict fast path are deferred until M1 ships and S4′ is measured: the warm median is
   about 6 s against a 30 s bar [A, ledger] and the dormant fast path was disabled because it
   bypassed enrichment (`backend/core/config.py:1892`). The verify-then-notify against
   notify-then-verify policy stays an owner product decision (ISS-021).
4. **No load-shed ladder, 12 or 16 GiB profiles, ghcr `ai-vlm` service, offline-install work or
   larger-VLM escalation tier.** The ghcr gap is marked owner-adjudicated
   (`.github/workflows/deploy.yml:31-33`) [V]. E1 stays as one diagnostic row.
5. **No engine or model-pin change, and no 4B fallback, without passing the L2 gate.** A pin change
   invalidates the S1, S4 and enforcement evidence, and the 4B already failed S5 [A, ledger].
6. **No wiring of `CameraCalibration`, `FeedbackProcessor._auto_adjust_offset` or the
   retired-model feedback taxonomy as written** (selection-biased, no interval, no holdout).
7. **No RT-VLM live-alert mode, RT-CV or NvDCF, Kafka, Elasticsearch, VIOS or behavior analytics,**
   and no model-grading-model self-critique as quality evidence.
8. **No stored image bytes in rows** (spec §6) and no retention path outside the event lifecycle for
   biometric traces (R13). Real media stays off-repo (D10).
9. **No cross-event or cross-camera memory shipped without a measured false-merge rate** on a labeled
   same-cast set, and no stream ingest before the R1 reopen trigger.
10. **No claim from a `tierb-v0` pass as sufficient.** It is generated renders under declared truth:
    necessary, not sufficient. Real-corpus S2/S3 (L6) is the final arbiter.
11. **No silent wiring of dormant controls** (weapon and fire bypasses, `priority_*`, memory-pressure
    backpressure). Each was left dormant for a reason that must be checked, so L1 records them as
    issues.
12. **No agent features, per-camera rules or audio** ([`12`](12-postponed-roadmap.md) R3-R7). The
    ladder is about the verdict pipeline.

## 8. How the three architect angles were judged

Three architects worked independently from the same repo at `5c605e1d`, each from a different
angle. Two judges scored them on four axes (groundedness, feasibility, ambition, measurability, each
out of 10) and, by their own report, each checked the proposals' citations against the tree. One
synthesis then built this ladder. The scores, the judges' assessments below and the claim that they
checked citations are agent output that was not re-derived here [A]; only the sums are computed [C],
and the findings this document relies on from them were re-checked where §2 and §4 mark [V].

| Angle                                                 | Judge 1 [A] | Judge 2 [A] | Sum [C] |
| ----------------------------------------------------- | ----------- | ----------- | ------- |
| **Temporal-video-first** (time-aware evidence ladder) | 31          | 32          | 63      |
| **Evidence-and-eval-first** (trust-first ladder)      | 30          | 33          | 63      |
| **Edge-efficiency-first** (budgeted cascade, 24 GB)   | 26          | 26          | 52      |

What the judges said, in brief [A]:

- **Temporal-video-first.** The best-grounded code reading of the video hole, the dead `track_id`
  and the clip supply. The thesis over-attributes the weakness to time, and its own gate (100 ready
  incident clips) is unreachable today.
- **Evidence-and-eval-first.** The most measurable; it fits the owner's own F14 text (the lever is
  prompts and specialist context) and its early rungs are cheap and hermetic. Rungs 1-4 add no
  capability, so it under-answers "video".
- **Edge-efficiency-first.** The best operational insight, and it found the best cheap defects. It
  optimises latency and VRAM, which do not bind (warm median about 6 s against 30 s; peak about 9.4-9.6
  GiB against 20.4 GiB [A]).

Judge 1 picked the temporal angle with the trust-first angle's first rung prepended. Judge 2 picked
the trust-first angle with the temporal angle's video fixes pulled forward [A]. **They tie at 63
each, so the spine is a synthesis, not a result** [?]; both gave the same build order [A], which
this ladder uses.

**What was grafted.**

- **From evidence-and-eval-first, the spine:** L1 (with the defect list), L2, L3, L5, L6. They are
  hermetic or cheap, and they are the preconditions for judging anything else.
- **From temporal-video-first, the video track:** L4, L7, L8, L9, L10, **gated by its own
  pre-registered paired rule** (L7). Judge 2's S3 arithmetic (§2.2) scopes the video claim, and its
  corpus check (17 ready incident clips, none of them a threat) is the gate's reality check.
- **From edge-efficiency-first, only verified cheap defects and one measurement:** the mixed-batch
  poisoning, the `vehicle` class gap, the ALPR cache, deadline and image extra, the dormant controls,
  S4′, and E1 as a single diagnostic row. Excluded: the `vlm_triage` op, the stakes scheduler, the
  early-verdict fast path, load shedding, the 12 and 16 GiB profiles, the ghcr `ai-vlm` service and
  the escalation tier (§7).

## 9. Owner decisions the ladder needs

All are [?]. Each is a ruling for the owner, not for an agent. OD-n numbers are local to this file.

- **OD-1. Approve or amend this document as the plan of record.** The spine choice is a synthesis
  of a tie (§8). Gates: all.
- **OD-2. The S3 floor rule.** Item floor from the band midpoint (today) or from the
  declared-band minimum. This decides whether a new frozen `EvalItem` generation with a
  declared-minimum field, and an `expected_verdict` for phantom items, is built. Gates: L2, L5.
- **OD-3. Spec rev 8.** Patch the S2/S3 rows with F14's numbers; reconcile D6 (stills only) with
  the video ingest the code already accepts; amend §3 Engine 2 (tiling); and permit still-burst clip
  scoring as the **control arm only**, which the clips design (C1) rejected as a product answer.
  "Rev 7" is already taken by the 2026-09-28 pick, so the next free revision is rev 8. Gates: L2,
  L7, L8.
- **OD-4. M1 and the notification path.** Approve wiring `should_notify`, `deliver_alert` and the
  frontend push; the verdict-to-action mapping per verdict class; whether `evaluate_event` becomes a
  production caller or is deleted; widening `SECURITY_RELEVANT_CLASSES` to `car` and `truck` (its
  own comment requires sign-off); and the policy for `rejected`, `uncertain` and quiet hours against
  measured recall (ISS-041). Gates: L1, L3.
- **OD-5. Hardware time and scheduling.** Owner 24 GB time (A5500, or Brev A10G or L4) for every
  S1/S4 re-measure; GB300 scheduling, since clip rendering and replay cannot overlap and the
  flagship stays resident (spec D12); whether replay may run while the renderer runs, and where
  `eval/` and `runs/` live (handoff Addendum 1). Handoff Addendum 5 (decision 4 [O]) answers the
  first for the `agent-gpu` sandbox, replays continue with the check bypassed and every such run
  labelled in its `run.json`; the second is still open [?]. Gates: L2, L4, L7-L10.
- **OD-6. Frame retention for L4.** Evidence-directory location, retention tied to event deletion,
  a deliberate widening of the capture-root guard, and a new table against an ALTER on `detections`
  (a hand-run SQL runbook). Gates: L4.
- **OD-7. Calibration policy for L5.** The single operating point for both bars (F14 ruling 3), the
  abstain width, the alarm budget in notifications per day, the proposed ≤ 1% bar for declared
  incidents rated `rejected`; whether the assess call may change decoding (seed, temperature 0,
  k samples); and whether a declared-truth replay may trigger flip condition (iii). Dated note,
  2026-10-03: the decoding question is answered for temperature 0 only, by the owner's decision
  (handoff Addendum 5, decision 3 [O]) and `9f4e65cd`; a seed and k samples remain open [?]. Gates:
  L5.
- **OD-8. Clip supply for L7.** Re-prioritise rendering toward threat scenarios (0 of 196 ready)
  and lateral-motion wording, a new corpus version, or owner clips. Without it the
  100-incident-clip bar is unreachable (17 ready). Gates: L7.
- **OD-9. Labeling effort for L6.** The random-audit stratum, labels per minute, and approval of a
  blind or free-answer audit in place of the leading form. Gates: L6.
- **OD-10. Specialist defaults.** Install the `alpr` extra in the prod image and settle
  `BACKEND_MODEL_PRELOAD`, or ship per-event specialist availability; and whether the compose
  default (`ai-vlm` behind profile `vlm` while `PIPELINE_MODE` defaults to `vlm`) is acceptable,
  noting the ghcr gap is already owner-adjudicated. Gates: L1.
- **OD-11. If L7 returns no-go.** Whether a video VLM, tracks or cross-event memory are wanted at
  all, and what ambition replaces them (for example, L4's frame burst becomes the shipped video
  answer). Gates: L8-L10.
- **OD-12. Where the plan lives.** A new dated plan plus errata banners on `docs/vss-integration/*`
  (this directory's `AGENTS.md`: the original text stays as the evidence record), against an
  in-place rewrite. This document takes the first. The register agrees: ISS-026 gives the house
  convention that "frozen research prose is never rewritten: it stays under a dated banner", its
  critical-path step 4 reads "Dated errata and banners for the stale statements (never in-place
  rewrites)", and its severity note says only that "the owner asked for this work" [V: read in
  [`17`](17-action-plan.md)]. No source read here records an owner request to rewrite instead of
  banner [?], so what is left to rule is whether to keep the convention. Gates: L1.
- **OD-13. The detector gate's recall ceiling.** A periodic or motion-triggered candidate-free scene
  pass measured on the corpus, or an explicit documented scope limit (ISS-040). No rung measures what
  the gate never raises. Gates: none; outside the ladder.

## 10. Rungs to issues

Issue ids are those of the 2026-10-03 register in [`17`](17-action-plan.md), which holds 86 issues
(its Currency banner and Dashboard table, read when this section was last edited): ISS-001 to
ISS-077 from the discovery pass, ISS-078 to ISS-082 added the same day from the sandbox exercise,
and ISS-083 to ISS-086 added after `9f4e65cd` and `d8482861` (ids are stable; the count grows, so
re-read the banner). The register is
agent-produced and its severities are its own [A]; each of the 86 ids appears exactly once below as
primary (ISS-003 is primary at L7 and is named again under L8) [C: counted from this section]. A †
marks an issue the architect synthesis did not name [A] and that §4 now names, whose register
acceptance test attaches it to that rung. Each build bullet in §4 becomes one issue with its exit
bar as the acceptance test.

- **L1.** ISS-004 mixed-batch selector; ISS-018 filter bands; ISS-023 fast-alpr in the image;
  ISS-025 specialist availability alert; ISS-052 specialist stage budget; ISS-026 doc errata and
  status pages; ISS-069 video statements in docs; ISS-076 contract docs; ISS-074 anchor check;
  ISS-075 validator baseline; ISS-071† enforcement-probe hardening; ISS-080 a ledger row for the
  P5a baseline and the
  re-runs, and the stale `10/20` citations (the owner merges ledger rows).
- **L2.** ISS-014 bar verdicts and replay invariants; ISS-015 S3 floor (OD-2); ISS-043 noise floor
  and intervals; ISS-045 reproducible replay; ISS-046 scripted S1/S4 and the S5 notification half;
  ISS-007 claim scope and detector-realistic arms; ISS-024 specialist context in replay; ISS-017
  GPU-runner regression gate; ISS-081 the spec's S2/S3 `[?]` rows and stale M1, S1 and G0.3 text
  (OD-3); ISS-079 replay from an `agent-gpu` sandbox (OD-5); ISS-082 replay settings validators.
- **L3.** ISS-001 notification wiring (the only P0); ISS-019 NULL-score path; ISS-041 policy (OD-4);
  ISS-048 payload; ISS-049 push and delivery record; ISS-020 channel config; ISS-010
  re-verification; ISS-011 ladder alerts; ISS-031 dead AI tab; ISS-032 failure reasons; ISS-034
  prompt-truncation metrics; ISS-042 lost batches; ISS-047 alert rules; ISS-058 health push; ISS-013†
  admission and breaker accounting.
- **L4.** ISS-002 clip frame extraction; ISS-005 temporal-spread selection; ISS-033 order and
  per-frame time; ISS-006† prompt-fit row truncation; ISS-065 evidence display; ISS-070† frame size
  from an unresolved path; ISS-068 `FrameBuffer`; ISS-030 stills and biometric retention.
- **L5.** ISS-008 prompt rubric and calibration (its acceptance should absorb §2.2: the AUROC and
  the remap ceiling); ISS-012 S5, provenance round-trip and wire order; ISS-016 pre-registered split
  (lands with L2, binds L5); ISS-078 the sampling policy of the assess call (arm (d), OD-7; it also
  bears on L2's noise floor, and the register records it `done` in `9f4e65cd`, which is the
  temperature-0 half only); ISS-086 the free S3 experiments and the single-still ceiling (the
  owner-directed work of handoff Addendum 5; its results are in Addendum 8, which re-derives the
  73% cap [C] but is a development run, not a holdout).
- **L6.** ISS-044 blind audit; ISS-061 eval-store capture root; ISS-066 review queue; ISS-067
  feedback taxonomy.
- **L7.** ISS-037 multi-frame eval; ISS-038 clip evaluation design (OD-8); ISS-003 video path
  decision (also gates L8); ISS-063 clip and model licences.
- **L8.** ISS-003 only; no register issue is the build.
- **L9.** ISS-035 `track_id` and tracking; ISS-036 cross-event context; ISS-054 face and re-ID
  thresholds.
- **L10.** ISS-039 streaming-ingest premise (R1).

**Handoff candidates, now on the register.** The first version of this section (2026-10-03) listed
four candidate issues from the handoff's Addenda 2 and 3 as not carried by the register. The
register carries them now, so they are pointed at it and not re-filed. (1) Report S2/S3 as a mean
over repeats with the spread, or at a fixed seed or temperature 0, with the choice on the
conditions line: the acceptance of ISS-043 names the repeat spread and the temperature-0 mode, and
ISS-078 holds the cause (L2). (2) A decoding policy for the assess call: ISS-078 (OD-24 in the
register, OD-7 here; L5 arm (d)); the temperature-0 option shipped in `9f4e65cd` after the owner's
decision (handoff Addendum 5, decision 3 [O]; Addendum 6), a seed and k-sample means remain open
[?]. (3) Track the truncation refusal rate at the 1,024-token budget: ISS-012, whose acceptance
reports the unparseable count over three 450-item replays (L5 exit bar 6). The production-side
output-truncation series is L3 exit bar 5's; the nearest register issues are ISS-032 (an enumerated
failure class that includes truncation) and ISS-034 (prompt-fit truncation, a different counter).
(4) The `Service 'ai-vlm' not registered` warning on every replay request is the same path
production uses for degradation tracking: ISS-058 covers it.

**On the register but off the ladder.** These are real and several are P1; they are not rungs
because they do not change what the pipeline can measure or decide.

- **Decisions deferred:** ISS-021 immediate-alert path (§7 item 3); ISS-040 detector-independent pass
  (OD-13); ISS-053 which specialists feed the VLM for the weak classes (decide after L5's inputs arm
  and E1).
- **Deploy, serving, CI and residue:** ISS-022 ghcr gateway boot; ISS-027 `.env.example` loopback;
  ISS-028 release artifacts without `ai-vlm`; ISS-050 Triton `reid` and `threat` fate; ISS-051 deploy
  export phase; ISS-055 dead trees; ISS-056 restart tooling; ISS-057 weights provisioning; ISS-059
  `ai/vlm` image outside CI; ISS-060 main-green classes; ISS-064 offline enforcement; ISS-073 dead
  enrichment surface; ISS-077 CI `ai-tests` scope.
- **Nemotron-era neighbors left by `d8482861`:** ISS-083, ISS-084 and ISS-085, the register's issues
  for what that commit deliberately did not touch (handoff Addendum 7). ISS-083 is
  `tools/nemo_data_designer/` and the `nemo` extra; ISS-084 is the prompt-management stack; ISS-085
  is the text-only `/completion` consumers and the three `llm_*` contract operations (the register
  finds that three of the handoff's four `/completion` sites talk to `ai-vlm` and that the fourth
  is the enforcement probe) [V: read in the three blocks of `17-action-plan.md`]. They wait on the
  register's OD-25 and change nothing the pipeline measures.
  **Dated note, 2026-10-03, `efa1b586` (after the pin):** the first neighbor is gone from the
  tree. The commit deletes `tools/` and both `nemo` blocks of `pyproject.toml`, and `uv.lock`
  drops 23 packages (banner item 3) [V]. The register's ISS-083 block was written at `d8482861`
  and keeps its own status, so read it there; the commit's file list names no path of ISS-084 or
  ISS-085 [V: no path in it contains "prompt" or "completion"]. The commit also unblocks an owner
  decision: the ledger's row 63 (owner option 2, "restructure" the `nemo` extra), `.trivyignore`
  and `.github/workflows/dependency-audit.yml` blame the Dependabot `cryptography` ceiling on the
  extra's engine pin. With the extra gone,
  `uv lock --dry-run --upgrade-package cryptography` prints
  `Update cryptography v49.0.0 -> v50.0.2` [V: run 2026-10-03; `uv.lock` is unchanged, so nothing
  is applied], and `.trivyignore` gives 50.0.0 as the fix version of its advisory [V: read]. The
  commit leaves the upgrade for the owner and leaves those two notes untouched; both still blame
  the old ceiling at `HEAD` [V: read], and no ruling is recorded in the ledger, whose last commit
  is 2026-10-01 [?: the owner may have ruled outside the repo].
  Later the same day: **Applied later the same day (`f0ff083e`).** The owner ruled in-session ("yes we can perform the cryptography upgrade", 2026-10-03 **[O]**) and `f0ff083e` applies it: `uv.lock` changes exactly one package (`cryptography` 49.0.0 to 50.0.2), the `CVE-2026-69247` entry is deleted from `.trivyignore` (its own text said to), and the four `--ignore-vuln` flags written for the old ceiling are removed from `dependency-audit.yml` **[V: `git show --stat f0ff083e`]**. `pip-audit` over the new lock, exported as CI does and run without those four ignores, reported "No known vulnerabilities found" **[V: run 2026-10-03]**; the unit and contract tiers passed (28,271) and the scripts tiers (663) on `cryptography` 50.0.2 **[V: recorded in the commit message]**. The uncommitted edits noted above were these. Whether the Dependabot uv job now passes is not read **[?]**.
  **M1's missing decision exists (`ab3bd002`).** `decide_notification` in `backend/services/notification_filter.py` loads the preferences, the camera's setting and the quiet hours and calls `should_notify`; `vlm_analyzer` runs it in its own short session after the event commits (skipped in replay) and the answer rides the WebSocket `event` as `data.notify`, the key absent when no decision was made; the frontend type is regenerated (`notify?: boolean | null`) **[V: `git show --stat ab3bd002`, 7 files, +397/-13]**. Red first: 9 new analyzer tests failed with `KeyError: 'notify'` before the code; 13 tests added; unit, contract and repo-root scripts tiers 28,563 passed **[V: recorded in the commit message]**. **M1 is not closed:** nothing acts on `notify` yet (the frontend `showSecurityAlert`, the alert-rule engine and `deliver_alert` have no caller of it) and no live-database integration run was possible in the sandbox.
  **Every measured number is specific to the llama.cpp build (found 2026-10-03, after `ab3bd002`).** The shipped 8B Q4_K_M, same weights, prompt and greedy decoding, served on a newly built llama.cpp `b11376` (`a55e952b8`; the sweep also sets `LLAMA_ARG_CACHE_RAM=0` and `LLAMA_ARG_CACHE_IDLE_SLOTS=0`) and replayed over the same 450 sets read **S2 21/209, S3 94/241, AUROC 0.677, 2 refusals** (both `VlmTruncatedError` at 1,024 tokens) against S2 18/209, S3 88/241, AUROC 0.703, 0 refusals on `b7972`; item by item only 250 of 450 return an identical (verdict, risk_score), 143 differ by 10 points or more **[V: `eval.sqlite`, run `20261003T194331Z-control-q4km` against `20261003T154038Z-qwen3-vl-8b-armA-shipped`]**. The cause (build or the two cache flags) is not attributed **[?]**; a repeat control and a default-cache control were running. Both builds fail the F14 bars. A cross-model comparison is valid only on one build, and a build bump needs a control replay (register ISS-087). For the ladder this means rung L1's reproducibility bar should pin the llama.cpp build and require a control replay on a build bump **[?: a proposal]**.
- **Security and privacy:** ISS-009 prompt injection through untrusted fields; ISS-029
  unauthenticated API on the LAN; ISS-062 trust inputs to the VLM; ISS-072 erasure.

ISS-029 needs the owner's eye (P1 in the register, unverified by this document [A]): a pipeline that
is measured, calibrated and auditable but serves an unauthenticated API on the LAN would not meet
this document's own standard, and no rung here addresses it.

## 11. What this document does not establish, and corrections it owes

**Not re-run or not read this session [?].** The A5500 S1/S4 figures and the 4B and larger-model
survey rows are ledger-relayed [A]. Not read by any reviewer:
`docs/benchmarks/synthbench/clips-probes.md` beyond the render-time line, `p5a-probes.md`, the
baseline's own `results.jsonl` (so no baseline AUROC), VSS upstream, llama.cpp `b7972` video
support and `--cache-reuse` with an mmproj, and whether vLLM or RT-VLM accept `video_url`. Docs
[`09`](09-audit-integration-surfaces.md), [`10`](10-audit-feature-inventory.md),
[`12`](12-postponed-roadmap.md) and [`14`](14-specialist-model-research.md) were read for the
statements cited, not in full. The clip counts are a live snapshot. Re-verify every number at the
commit being edited.

**Corrections to the synthesis found while verifying (this session).**

- The synthesis said "14 of 19 incident scenarios sit at n = 9"; recomputed it is **12 of 19**
  [C, §2.3].
- It named a `ModelField` in `synthbench/run/models.py`; the class is `Model`, registered in
  `MODELS`.
- It said "three judges"; there were two (§8).
- It treated run-to-run noise as unmeasured and the baseline AUROC as unreachable; the handoff
  measured the noise (§2.2) and the two 2026-10-03 score files supply the AUROC (§2.2).
- It said the specialist legs read `unavailable` by default; that is the compose default only, the
  plate leg is unavailable regardless, and `setup.py` sets preload at 24 GB or more (L1).
- It inferred that the S3 miss "may be risk calibration rather than missing evidence". §2.2 narrows
  that: the miss is a low score on a confirmed verdict, but a monotone remap is capped near 41% in
  sample, so calibration alone is not the lever.
- Its proposals cited the `file_watcher.py` extension sets at `:70-72` (they are at `:76-78`) and
  the `go2rtc` service at `:643` (a `depends_on` entry; the service is at `:856`).

**Corrections owed to older docs (for the banner pass; originals stay).**
[`12`](12-postponed-roadmap.md) R1 says the VLM path is ingest-agnostic and a stream front end
plugs in without changing the selector; false for video (L4). [`12`](12-postponed-roadmap.md) R6
names YOLO-World, removed in R8. [`10`](10-audit-feature-inventory.md) §6 item 4 cites
`enrichment_pipeline.py`, item 5 names the Florence cascade and item 8 a prompt auto-tuner; all
three modules are gone (`602379e2`; `backend/services/prompt_auto_tuner.py` does not exist). Doc
[`14`](14-specialist-model-research.md) assumes a CLIP-era re-ID and a resident SigLIP2 tower, and
labels its shortlist "rev 7", which collides with the 2026-09-28 pick. Doc
[`05`](05-hardware-profiles.md) lists gateway routers (`/florence`, `/clip`, `/enrichment`) that no
longer exist. `backend/ai_contract/AGENTS.md` says 38 operations. `README.md` and `AGENTS.md` of
this directory cite `docker-compose.prod.yml:578` for the default flip, which is `:484`; that was
owed as of the pin, and the banner pass has since added an E37 note to each (`README.md:8` and
`AGENTS.md:4` [V: read]), so for those two the correction is discharged and the original prose
stays. The docstring of `scripts/check-vss-docs-currency.py` carries the same anchor (line 6 [V])
and has no banner.

## 12. Sources

- Measurements and decisions of 2026-10-03: `docs/plans/2026-10-03-vss-vlm-exercise-handoff.md`
  (Addenda 1-5: the state after the recreate, the first full replay, the repeat run, temperature 0,
  and the owner decisions; Addenda 6 and 7 record `9f4e65cd` and `d8482861`; Addendum 8 holds the
  rubric-prompt and logprob experiments, written later on 2026-10-03), and the two score
  directories `20261003T133003Z` and `20261003T134742Z` under the sandbox's
  `$AGENT_GPU_DIR/out/sbroot/runs/scores/` (off-repo).
- The register: [`17`](17-action-plan.md) (86 issues, read from its Currency banner when this file
  was last edited).
- The committed baseline: `docs/benchmarks/synthbench/p5a-2026-09-30.md`.
- The bars and rules: the ledger's F14 entry (`docs/plans/2026-09-23-vss-gaming-gpu-ledger.md:221`).
  The design spec: `docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md`. The clips
  design: `docs/superpowers/specs/2026-09-30-synthbench-h3-clips-design.md`.
- Research: [`10`](10-audit-feature-inventory.md), [`12`](12-postponed-roadmap.md),
  [`13`](13-implementation-brief.md), [`14`](14-specialist-model-research.md).
- Commits: `4bfd6fa4` (#6681, the VLM default), `ca73f1ef` (the baseline's scoring commit),
  `602379e2`, `3b73b9b6` and `392d69fd` (R8 slices), `2ab66ff1` (yolo26 model-server `/track`
  removal, 2026-09-19). After the pin, all 2026-10-03: `9f4e65cd` (the assess call samples at
  temperature 0), `d8482861` (the Nemotron prompt-evaluation harness and its CI workflow are
  deleted) and `efa1b586` (the NeMo Data Designer tooling and the `nemo` extra are deleted).
