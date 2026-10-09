# 23. The prompt-programme stages 1-4 (run 2026-10-04 to 2026-10-05)

> Frozen research record, like docs 00-14 and 22: this describes what was measured on 2026-10-04
> and 2026-10-05, not what is true today. It is the continuation of
> [doc 22](22-prompt-research-and-probes-2026-10-04.md) — doc 22's probes said the shipped prompt
> cannot lift `risk_score` by wording; this doc records the controlled experiment that tested the
> claim (four stages, ten prompt arms, one frozen ship rule) and its outcome. Everything here is
> **[A]** agent-authored; the underlying artifacts (captures, `run.json`, per-arm analysis files)
> are on disk at the paths below and were read in-session **[V]**.

## 1. What ran

Question: can any prompt, at the shipped operating point, pass the OD-26 ship rule against the
shipped arm A prompt — and if not, is the binding constraint the client's token budget, the prompt
content, or the architecture? Stages, in order, all on one dedicated solo `b7972` container
(Qwen3-VL-8B-Instruct-Q4_K_M, temp 0, one client, 450 `tierb-v0` stills, oracle detections):

- **Stage 1** — the fields arm (owner-signed `rejected` semantics): fails OD-26 no-harm
  (dS3 −2.5 CI [−6.4,+2.4]) despite fixing the logprob-extraction defect. **[V]** `stage1/results/`.
- **Stage 2** — five reasoning-layout arms (cue, a, b reason-first, vb verdict-before, va
  verdict-after) + an empty-line probe. None ships; all four reasoning-bearing arms **do** improve
  AUROC against plain-benign stills by +0.20..+0.245 (CI lower bound > 0) — the failures are on the
  alert-safe guards (no-clear-harm, B+C non-regression), not on ranking ability.
- **Stage 3** — token-budget ablation: cue/a/b/emptyline re-run at `max_tokens` 2048
  (client `26b900bc`). **450/450 row-identity with their 1024 twins on all four arms**: the budget
  was never the binding constraint; every OD-26 failure is a CONTENT failure. The truncations are
  content too — the same `img_sha256` items finish=length at both budgets (>2048-token greedy
  outputs). Commit `26b900bc` stays correct engineering; it resurrects no arm. **[V]**
  `stage3/REPORT-stage3.md`.
- **Stage 3.5** — held-out threshold protocol (label-stratified item split, T\* = argmax(hits − FP)
  on one half, evaluated on the other, both selection directions). **Arm B at T=60-70 is the only
  candidate that survives in both directions** (FP cuts strictly negative, hits parity to one
  short). This is a production threshold change — owner territory, flagged, never automated here.
- **Stage 4** — three NVIDIA-VSS-architecture arms composed from frozen stage-2 bytes:
  verify-framing, operational-negatives (replacing (b)'s band block + severity map), post-hoc
  judge (turn-1 = frozen (b); separate turn-2 prompt, downgrade-only enforced in shim code).
  None passes OD-26 at T=30.

Whole-programme artifact kit: `/agents/agent-vss5/gpu/out/experiments/2026-10-04-stage1/` (off-repo
scratch like the model sweep; per-stage `PRE-REGISTER*.md` verbatim incl. amendments, SHA256SUMS
locks, captures under `out/sbroot/runs/replays/`). The full arm-by-arm table, held-out detail and
per-stage GPU-hours are in its `FINAL-REPORT.md`; the numbers quoted below are read from the same
captures. Baseline arm A `4a94b2562919419a975bed4972646740` (S2 18/209, S3 88/241, 0 refusals);
stored arm B `696c71687e264577b4deb6bd5c99af26` (S2 34/209, S3 105/241) — the rubric arm of
doc 22's table, which is why "development arms" never shipped either.

## 2. What the ten arms teach (the mechanisms, not the scoreboard)

1. **Verdict placement is a measured hazard on both sides.** Verdict-BEFORE-reasoning anchoring is
   actively harmful (vb: dS3 −17.0 CI [−30.6,−3.3] vs arm A); verdict-LAST schemas (criteria-first
   field order) get truncated before the verdict key on evidence-rich scenes — the verify arm's 97
   truncated rows all contain only the `criteria` enumeration at exactly the 2048 cap, while its
   342 completed rows used a median of 425.5 tokens. Both results point the same way: **verdict
   early, reasoning after** — which is what arm (b) already does. Reason-first detection beats both
   reorders at full n (73/241 vs 56 vs 47). **[V]** `stage4/results/` key_order census.
2. **Post-hoc judging cannot filter what turn-1 confidently got wrong.** 449 separate-prompt
   challenges of confirmed verdicts (NVIDIA enrichment-processor shape: distinct prompt, runs after
   the verdict, downgrade-only in code) produced **exactly one downgrade** across the corpus, and
   cost ~0.4 pts of detection (dS3 −0.4 CI [−1.3,+0.0] vs base; FP set bit-identical). Confirmed-
   wrong verdicts are a perception limit on the scene, not an elaboration gap a second call closes.
3. **Operational negatives erase a known FP regression and buy nothing net.** The negatives arm
   removed (b)'s entire FP regression (dS2 −13.9 CI [−29.3,+0.6] vs base b, with hits parity; 0
   refusals, 0 false rejections, 0 truncations — the cleanest gate pass built) and still DROPs: at
   T=30 the guards here fail on detection, and the A0 audit bounds how much detection prompts can
   reach at all — **44/64 A-incidents are prompt-addressable (68.75%); `resident_arrival` 0/10**.
4. **The corpus cannot certify a small win at this n.** CI width, not point estimates, is what
   blocked every near-miss (emptyline's dS2 +1.4 CI [−2.3,+5.4] was the closest to the shipped
   point). Any future "small improvement" claim needs a bigger corpus or a paired design with more
   power, not a better-phrased arm.

## 3. What follows from this doc

- **Ship-adjacent, owner-gated:** arm B text + threshold 60 (possibly 70) — the only honest
  held-out survivor. A threshold change needs the owner's own acceptance frame; the OD-26 rule was
  written for prompt-vs-prompt at fixed T=30. Flagged 2026-10-05, queued, not automated.
- **Input-pipeline next steps** (out of this programme's scope, from the NVIDIA VSS scan and
  consistent with §2): 10-frame end-anchored clips; severity grading in the rule engine, not in
  the VLM's 0-100; the `resident_arrival` FP class is prompt-unreachable — it belongs to the
  detector/specialist tier.
- **Instrument lessons banked as rules:** check container TTL before long collection windows (the
  programme lost its server mid-verify-arm at 09:39:01Z; the 11 tail refusals are server-death
  artifacts, excluded from the content claim, full incident in `stage4/PRE-REGISTER-stage4.md`);
  `d_predicted` is a client ESTIMATE and wobbles ±10 between byte-identical replays — the owner
  co-tenancy guard rule now rests on wait, inflight and d_prompt surplus over own+8 (amendment
  06:50, flagged for owner ratification).
- **Register rows** for ISS-099..ISS-102 (the format-fit sweep caveat and friends) were drafted at
  tip `95505d7d` and left append-only for the owner's merge into `17-action-plan.md`, per the
  ledger discipline; nothing was pushed in this programme.

## 4. Cost, honestly

≈10.8 GPU-h of collection across the four GPU stages (stage 1 ~1.1, stage 2 ~4.0, stage 3 ~2.7,
stage 4 ~3.0), each measured as run-name timestamp → capture last-write and logged against its
pre-registered estimate at close-out; stage 3.5, A0, all analyses and the two-turn collapse probe
were CPU-only. No arm was collected twice at temp 0.

## 5. Follow-up (appended 2026-10-05, after the owner's answers; no text above changed)

All four queued items got answers on 2026-10-05 [O: asked and answered in the session; durable
sources named per item]:

- **Ship-adjacent became shipped:** the owner accepted arm B text + floor 60 (OD-29; mechanism
  chosen: the per-camera `risk_threshold` default 60, `risk_filters` and the level map untouched,
  saved values win). Durable source: `17-action-plan.md` Intake log entry 2026-10-05 and the code on
  `fix/vlm-assess-token-budget`; §3's first bullet reads "flagged, queued" as of its freeze and is
  superseded by this entry, not rewritten.
- **Register rows filed:** ISS-099..ISS-102 merged into `17-action-plan.md` on the owner's
  instruction; §3's last bullet stands as the drafting record.
- **The guard amendment is ratified** (co-tenancy = wait ∨ inflight ∨ d_prompt surplus over own+8;
  `d_predicted` does not carry it): committed as 'GPU run kits: one client per server' in
  `docs/vss-integration/AGENTS.md`, sourced to the same Intake entry; ISS-102 tracks the guard's
  mechanical home.
- **The push executed:** this branch moves to the owner's remote; nothing else about OD-10 changed.
