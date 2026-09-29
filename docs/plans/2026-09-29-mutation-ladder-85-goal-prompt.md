# Mutation ladder to 85% — plan of record + /goal prompt

**2026-09-29, authored after the M6 publish (`1aec4f8c`).** This doc is the
ORDER + measured sizing for the campaign ladder that carries the mutmut badge
from M6 to 85%. The standing measurement ledger stays
`docs/plans/2026-09-12-context-map-doc-updates.md` (the L file): every close's
numbers are rowed THERE, measured in-session. This file carries the plan; it is
NOT a substitute for L rows.

## Where we stand (M6, published 2026-09-29)

| milestone | score                 | kt (killed+timeout) / total |
| --------- | --------------------- | --------------------------- |
| M1        | 64.3236%              | —                           |
| M2        | 65.45381499940281%    | —                           |
| M3        | 66.3192%              | —                           |
| M4        | 67.43042239483464%    | 62,243 / 92,307             |
| M5        | 68.01666756859137%    | 62,844 / 92,395             |
| **M6**    | **68.9482506662082%** | **64,166 / 93,064**         |

Bank state at M6 (from `.github/mutation-history.json` run #9 /
`/home/agent/runs/score-b30-final.txt`): survived **28,157**, no_tests 741
(713 = sticky trio, recoverable at the next FULL RE-BANK), 231 modules,
unchecked 0, completed=true.

## The arithmetic (measured, this session)

- **85% = 79,104 kt → gap 14,938 kills = 53.1% of the survivor pool.**
- 80% needs +10,285 (36.5% of pool); 75% +5,632 (20.0%); 72% +2,840 (10.1%).
- Killable-yield anchor: batch-30 measured **757/845 = 89.6%** of `prompts.py`
  survivors killable by authored batteries (residue = dead branches,
  falsy-default swaps, compared-never-rendered sentinels).
- Ceiling sensitivity (kills = f x 28,157; denominator +5% from newly-covered
  lines, the prompts precedent):

| killable fraction | ceiling |
| ----------------- | ------- |
| 90%               | 94.7%   |
| 85%               | 93.3%   |
| 80%               | 91.8%   |
| 75%               | 90.3%   |

**Conclusion: 85% is reachable by battery kills alone — no denominator-policy
change required, and none is authorized here.** The STOP-AND-ASK branches
(`mutate_only_covered_lines` policy, WP4.5 coverage-gap widening, in-denominator
omits) stay OFF the critical path; they only accelerate the far tail. The
binding constraint is campaign labor, not policy.

## Ordering rule (the ladder is a RULE, not a frozen list)

> **⛔ R8 SHIELD (2026-09-29): READ
> `docs/plans/2026-09-29-r8-teardown-mutation-impact.md` BEFORE picking a
> module.** `chore/r8-s2-nemotron-teardown` deletes 33 bank rows (14,295 kt,
> 15.4% of the denominator; post-merge badge ≈ 64.5%). **NEVER author
> batteries for the dead:** `enrichment_pipeline`, `vision_extractor`,
> `vitpose_loader`, `florence_extractor`, `pose_analysis_service`,
> `package_tracking_service`, `prompt_auto_tuner`, `analyzer_facade`,
> `ai_services`, and the 16 `*_loader` modules on its list — the
> authoritative death list is `DEAD_MODULES`/`DEAD_LOADERS` in
> `backend/tests/unit/test_r8_s2b_nemotron_deletion.py` on that branch.
> `prompts.py` (−89% of its lines) and `api/routes/system.py` are
> do-not-start. The M6-snapshot table below PREDATES the shield — its rows
> 4–6, 8, 13 are void; the impact doc carries the post-teardown order. Before
> ANY campaign: `git diff --name-only origin/main...<r8-branch> --
backend/services backend/api/routes` and skip everything it deletes.

At each campaign start, re-census survivors from the latest published
score JSON (`scripts/mutation-score.py` snapshot) and take the **largest
survivor pool whose score is < ~80%** as the next module; the estimate order
below is just that rule applied to the M6 snapshot. Pools shrink/change as
earlier campaigns re-enumerate lines, so a stale list would mislead.

M6 snapshot — top 30 pools (post-fill, measured):

| rank | module                               | survivors | kt / total    | score |
| ---- | ------------------------------------ | --------- | ------------- | ----- |
| 1    | `services/event_broadcaster.py`      | 723       | 563 / 1,286   | 43.8% |
| 2    | `services/batch_aggregator.py`       | 644       | 511 / 1,155   | 44.2% |
| 3    | `services/clip_client.py`            | 559       | 486 / 1,045   | 46.5% |
| 4    | `services/florence_client.py`        | 394       | 772 / 1,166   | 66.2% |
| 5    | `services/vision_extractor.py`       | 392       | 1,054 / 1,446 | 72.9% |
| 6    | `services/enrichment_pipeline.py`    | 420       | 5,933 / 6,353 | 93.4% |
| 7    | `services/baseline.py`               | 368       | 398 / 766     | 52.0% |
| 8    | `services/file_watcher.py`           | 339       | 336 / 675     | 49.8% |
| 9    | `services/redis_json.py`             | 338       | 256 / 594     | 43.1% |
| 10   | `services/cleanup_service.py`        | 337       | 344 / 681     | 50.5% |
| 11   | `services/vlm_specialists.py`        | 336       | 441 / 777     | 56.8% |
| 12   | `services/vitpose_loader.py`         | 317       | 307 / 624     | 49.2% |
| 13   | `api/routes/system.py`               | 351       | 1,713 / 2,064 | 83.0% |
| 14   | `services/onvif_service.py`          | 312       | 291 / 603     | 48.3% |
| 15   | `services/vlm_client.py`             | 324       | 536 / 860     | 62.3% |
| 16   | `services/prompt_service.py`         | 321       | 360 / 681     | 52.9% |
| 17   | `services/system_broadcaster.py`     | 320       | 442 / 762     | 58.0% |
| 18   | `services/job_tracker.py`            | 309       | 433 / 742     | 58.4% |
| 19   | `services/zone_anomaly_service.py`   | 290       | 237 / 527     | 45.0% |
| 20   | `services/scene_ocr_service.py`      | 279       | 422 / 701     | 60.2% |
| 21   | `services/cost_tracker.py`           | 277       | 295 / 572     | 51.6% |
| 22   | `services/notification.py`           | 272       | 339 / 611     | 55.5% |
| 23   | `services/stream_manager.py`         | 257       | 104 / 361     | 28.8% |
| 24   | `services/gpu_config_service.py`     | 266       | 299 / 565     | 52.9% |
| 25   | `services/partition_manager.py`      | 264       | 469 / 733     | 64.0% |
| 26   | `services/background_evaluator.py`   | 248       | 144 / 392     | 36.7% |
| 27   | `services/vlm_analyzer.py`           | 259       | 490 / 749     | 65.4% |
| 28   | `services/threat_monitor_service.py` | 244       | 118 / 362     | 32.6% |
| 29   | `services/audit_logger.py`           | 242       | 166 / 408     | 40.7% |
| 30   | `services/pg_notify_listener.py`     | 238       | 235 / 473     | 49.7% |

Bucket census: 18 modules >=300 survivors (23% of pool) / 101 modules 100-299 /
55 modules 25-99 / 47 modules 1-24 / 10 closed modules; the long tail (<100
survivors, 102 modules) holds 3,953 (14%).

## The ladder

Model estimates below use the batch-30-anchored yield (0.92 for modules under
50%, 0.88 for 50-75%, 0.82 above) — **planning estimates, not admissible
numbers**; each real milestone carries its own measured L row.

| campaign | target                   | survivors | est. kills | est. score after |
| -------- | ------------------------ | --------- | ---------- | ---------------- |
| 1        | `event_broadcaster.py`   | 723       | ~665       | 69.64%           |
| 2        | `batch_aggregator.py`    | 644       | ~592       | 70.26%           |
| 3        | `clip_client.py`         | 559       | ~514       | 70.80%           |
| 4        | `florence_client.py`     | 394       | ~347       | 71.15%           |
| 5        | `vision_extractor.py`    | 392       | ~345       | 71.50%           |
| 6        | `enrichment_pipeline.py` | 420       | ~344       | 71.77%           |
| 7        | `baseline.py`            | 368       | ~324       | 72.11%           |
| 8        | `file_watcher.py`        | 339       | ~312       | 72.43%           |
| 9        | `redis_json.py`          | 338       | ~311       | 72.76%           |
| 10       | `cleanup_service.py`     | 337       | ~297       | 73.06%           |

- campaigns 11–39: the remaining ≥100-survivor pools (`prompt_service` 321, `system_broadcaster` 320, `job_tracker` 309, `zone_anomaly_service` 290, `scene_ocr_service` 279, `cost_tracker` 277, `notification` 272, `stream_manager` 257, `background_evaluator` 248, `threat_monitor_service` 244, `worker_supervisor` 243 …) one per campaign → **campaign 39 ≈ 80%**
- campaigns 40+: 12-module tail bundles (102 modules / 3,953 survivors, <100
  each) → **campaign 68 ≈ 85%**

- **FULL RE-BANK interlude** (after ladder campaign 4): stats-edge
  re-collection + from-scratch-family repair restores the sticky-713 trio rows
  and re-admits stale-def families (~+500 kt + fresh mutants in the
  just-batteried modules); it rides as its own milestone.
- **Milestone mapping** (numbering = the table above, campaigns counted FROM
  M6): campaign 1 close = M7, 2 = M8, … one milestone per close, plus the
  re-bank milestone. Expected landings (model): 70% ≈ M8, 72%/tier-bar
  (kt >= 66,524) ≈ campaign 7 close (+ re-bank), 75% ≈ campaign 17 close,
  80% ≈ campaign 39 close, **85% ≈ campaign 68 close**.
- **Why this order:** pools are front-loaded — the top 30 hold 36.5% of all
  survivors; modules scoring <50% (`stream_manager` 28.8%,
  `threat_monitor_service` 32.6%, `background_evaluator` 36.7%,
  `event_broadcaster` 43.8%, `redis_json` 43.1%, `batch_aggregator` 44.2%) are
  whole untested functions — the cheapest first-order mutants, exactly the
  batch-30 (`prompts.py`) situation that yielded 89.6%.

## Per-campaign protocol (batch-30 proven — repeat verbatim)

1. **Inventory**: survivor keys per function from the bank metas
   (`/home/agent/runs/<b>-survivor-inventory.json` pattern); triage file per
   function.
2. **Disposition sweep**: single-process trampoline sweep (NEVER pytest-per-key
   in the mutant home — 6m40s collect); controls = shipped-green + foreign-key
   GREEN + known-KILLED RED. Sweep predictions are reconciled against bank
   verdicts after the run; **bank verdicts are the score's source of truth**.
3. **Batteries**: vulture-gate at authoring; mock hook WP4.2
   (`autospec=True` at every `patch.object`); mypy + ruff clean; gates run on
   the COMMITTED bytes. EQUIVALENT residue ledgered in battery headers.
4. **Run**: `MUTMAX=14 ./scripts/mutation-run.sh <module>` ONLY (no raw
   mutmut; no-arg run = sanctioned hole-fill/repair). Guard alive (attached to
   the live mutmut pid, launched separately — never two `&` in one command).
5. **Fill** (if needed): sanctioned full-set repair; audit-redecide script
   clean (no unexplained verdict changes; self-heal families whitelisted by
   measured census).
6. **Close**: completed=true score strictly > last milestone;
   `--history .github/mutation-history.json --date <today>` append; L row with
   row-by-row denominator disclosure; commit + push; **refresh
   `guard-restore.tgz` to the new era bank** (`tar` from INSIDE `mutants/`).

## Guards and mines (every run, no exceptions)

- `guard.sh`: key-floor **78,000** (strips DELETE keys — hole count alone is
  blind) + kill-line **5,500**; restores `guard-restore.tgz` and the extract
  cwd MUST be `mutants/`; abort if `mutmut-stats.json` missing.
- **After every merge touching `backend/tests`**: `git diff --diff-filter=A`
  for ADDED test files, grep each for `REPO_ROOT` / `parents[N]` path-reads,
  add read targets to `also_copy` BEFORE the next run — no external green scan
  can catch this class (new test files enter the mutant home only at
  generation).
- A run that dies "at the clean gate" may have ALREADY stripped the bank
  (generation precedes the gate): mtimes + key census decide, never the log
  tail. Post-generation ~1h collect grind = pyc rebuild + sentinel
  `ast.parse`, not a hang (py-spy before panic).
- One source-mutating job at a time; `pgrep` patterns bracketed near live
  runners.

## The /goal prompt (paste verbatim — this doc is the plan of record)

```text
MUTATION LADDER TO 85% — branch mutation-testing-s3. READ
docs/plans/2026-09-29-mutation-ladder-85-goal-prompt.md FIRST — plan of record
(ordering rule, protocol, guards). GOAL: mutmut badge
(killed+timeout)/total from 68.9482506662082% (M6) to 85% by per-module
campaigns. L=docs/plans/2026-09-12-context-map-doc-updates.md: every
DECIDE/number rowed in L AND the commit body, measured THIS session.
NEXT: re-census survivors from the published score JSON; BEFORE picking a
module, read docs/plans/2026-09-29-r8-teardown-mutation-impact.md (R8 legacy
teardown deletes 33 bank rows — never battery a module on its shield list;
death list = DEAD_MODULES/DEAD_LOADERS in
backend/tests/unit/test_r8_s2b_nemotron_deletion.py on the r8 branch); run
the largest pool
scoring <80% (doc order at M6: event_broadcaster, batch_aggregator,
clip_client, florence_client, vision_extractor, enrichment_pipeline, baseline,
file_watcher, redis_json; then descending; 12-module tail bundles; ONE FULL
RE-BANK interlude ~campaign 4). Each campaign closes as a milestone:
completed=true score STRICTLY > last + mutation-history append + L row +
commit + refresh guard-restore.tgz. Per-campaign protocol per doc: inventory
-> trampoline disposition sweep -> vulture-gated batteries ->
MUTMAX=14 ./scripts/mutation-run.sh <module> -> sanctioned fill ->
audit-redecide clean -> publish. NEVER: lower a floor; --no-verify or SKIP;
raw mutmut; badge claims from red-check counts; bend production. Guards
key-floor 78,000 + kill-line 5,500 alive on every run; after any merge
touching backend/tests audit ADDED test files for REPO_ROOT path-reads
(also_copy family) before running. STOP AND ASK: denominator/widened-set
policy changes; continue-on-error or break flips; bulk quarantine;
pg/redis/GPU. If 85% demonstrably needs a policy change, stop and ask.
```
