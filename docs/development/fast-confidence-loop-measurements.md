# Fast Confidence Loop — Measurements Record

**Home:** `docs/development/fast-confidence-loop-measurements.md` (plan Task 15).
Every row carries its box; rows are never compared across boxes silently.

**Measurement box reality (precedes every number):** the spec's §1 baselines are
labeled "GB300 dev box: 72 cores, 494 GB RAM", but ALL rows below were measured
on the CURRENT box: **16 cores, MemTotal 65,744,332 kB = 62.69 GiB**
(`/proc/meminfo`, `nproc`, read 2026-09-14, corroborated by
`t3-draft/measurement-plan.md` §"Box reality"). Targets written for the fatter
box are stretch goals here and labeled as such per arm. §6.2's "< 10 min" is a
fat-box target; on this box the parallel arms are OWNER-DEFERRED to a 96 GiB
machine (ledger §9 release-event deferral row) — the serial control arm is this
box's honest envelope.

## M1-pre-plan datapoints (spec §9 / Task 8 scaffold rows)

| #   | Datapoint                                                                                                    | Value                                                                | Evidence                                                           |
| --- | ------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- | ------------------------------------------------------------------ |
| P1  | Backend combined lane, M1 era                                                                                | ~2.5–3 h; host load 8.1/72 cores, all queue (R-T7-DBRACE-FINAL)      | M1 spec §1 (specs/2026-09-12-fast-confidence-loop-design.md:13-14) |
| P2  | 443 GB lane-1 kernel-OOM worker datapoint + D2 late-lane hard-crash tail                                     | (text rides in M1 ledger R-T7-POISON-CASCADE + AMENDMENT-RESOLUTION) | plan Task 8 "Pre-existing content to absorb"                       |
| P3  | D1 arbiter: chaos solo `-n0` rerun HUNG, RC=1 timeout dump at redis_streams.py:402 — hang-class, not 137/139 | chaos scoped OUT of validate.sh combined gate (commit 0b1f8882)      | plan :1322-1335                                                    |

## Ledger-measured rows

### Row B1 — backend integration tier wall-time (M3 T4c program)

| Arm                                                                                      | Wall                                                                   | Record                                                                               |
| ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| pre-T4                                                                                   | 919.75 s                                                               | ledger (context-map plan :2116 region)                                               |
| runA2 (post-T4c, VERIFIED green: 4165 passed / 131 skipped / 2 xfailed, zero node-downs) | **618.53 s** (−33%)                                                    | ledger :1973-1979, :2116                                                             |
| gate 13 (same code; tier RED — 11 failed, all test_github_workflows class)               | 597.47 s (−3.4% vs A2, within noise; NOT quotable as "verified green") | ledger :2158                                                                         |
| **gate 19 (M1 §6 closing gate — GREEN record, tip 1be83995)**                            | **574.01 s**, 4165 passed, ZERO node-downs                             | gate19-capture/validate-backend-integration.log; ledger "M1 §6 CLOSE-OUT" (10373abd) |
| teardown p50                                                                             | 1.043 s → 0.224 s                                                      | ledger :1981                                                                         |
| setup p90                                                                                | 1.161 s unchanged (next target: init_db seam)                          | ledger :1983-1984                                                                    |

### Row B2 — combined backend full gate wall (`-n auto`; spec §6.1 target <30 min fat box)

| Arm                                                                  | Wall                                                                                                                             | Record                                                                      |
| -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| BEFORE (M1 era)                                                      | ~2.5–3 h (P1)                                                                                                                    | M1 spec §1                                                                  |
| **gate 19 unit tier**                                                | **84.45 s** (27524 passed)                                                                                                       | gate19-capture/validate-backend-unit.log                                    |
| **gate 19 integration tier**                                         | **574.01 s** (4165 passed, zero node-downs)                                                                                      | gate19-capture/validate-backend-integration.log                             |
| gate 19 total backend wall (unit+integration+combine, serial stages) | ~658 s + combine ≈ **~11 min** — under 30 min ON THIS BOX (fat-box target met early; honest note: 16-core box, worksteal `-n 8`) | arithmetic of the two log close lines; D14 split means stages don't overlap |
| §6.1 green ×2 (T5 step-4)                                            | gate 17 = 1/2 (backend green under T5 config); **gate 19 = 2/2**                                                                 | handoff scoreboard; ledger §6 record                                        |

### Row B3 — combined coverage (gate is 80; bar NEVER moved — spec §7)

| Arm                                                | Value                                                              | Record                                      |
| -------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------- |
| run-7 `coverage combine` (unit+integration merged) | 87.96% ≥ 80 [OK]                                                   | ledger :1792                                |
| **gate 19 merged (TOTAL line)**                    | **87.94%** (79229 stmts / 8098 miss / 19234 branch / 2134 partial) | gate19-capture/validate-coverage-report.log |

### Row F1 — frontend full vitest suite (spec §6.2; <10 min = fat-box target)

| Arm                                                                                   | Wall                                                                                                                                                                                                                                                                                                                                                        | Record                                                                               |
| ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| BEFORE — serial forks (supersedes spec §1's 1472 s per ledger item 4)                 | 2981.18 s (781 files, 20,340 tests; split transform 23.89 / setup 350.85 / import 556.89 / tests 743.30 / environment 855.94)                                                                                                                                                                                                                               | /tmp/validate-full-10.log:35473 (wiped 2026-09-14; quoted value ledger-pinned :2091) |
| **gate 19 (M1-final, serial, T3 patch NOT yet applied)**                              | **2966.63 s** — 778 passed / 3 skipped files; 20235 passed / 136 skipped tests                                                                                                                                                                                                                                                                              | gate19-capture/validate-full-19 raw log close lines                                  |
| **T3 control arm (patch APPLIED, envs unset — inertness proof, THIS box)**            | **2985.45 s** (transform 23.30 / setup 341.65 / import 554.19 / tests 1009.75 / environment 833.62) — 778 passed / 3 skipped; 20235 passed / 136 skipped; rc=0; VALIDATION SUCCESSFUL banner                                                                                                                                                                | /tmp/t3-control-2.log + .rc (2026-09-14 22:16)                                       |
| control-arm delta vs gate 19                                                          | **+18.82 s = +0.63%** — within noise; test-file/test counts BYTE-IDENTICAL to gate 19; `Duration`-line internal split shows the only >1% mover is `tests` (+266 s / +36% wall-in-reported vs gate-10-era 743 s) while env/setup/import all match ±3% — same box, same serial profile, session-dependent test-body time; no behavioral change from the patch | arithmetic of the two quoted lines                                                   |
| serial-path proof (control arm)                                                       | NO "Parallel vitest" banner (grep 0 hits; validate.sh :490 branch requires MemTotal ≥ 67,108,864 kB; box 65,744,332 kB); wrapper `NODE_OPTIONS="--max-old-space-size=${VITEST_HEAP_MB:-8192}"` fired → 8192 MB default inherited                                                                                                                            | /tmp/t3-control-2.log                                                                |
| **control-arm RSS (plan Step-4 sampling, 5 s cadence, serial single-fork)**           | peak single node worker **0.56 GiB**; peak concurrent-summed **0.82 GiB** (single fork at a time — serial `fileParallelism:false`); vs the 8192 MB per-process ceiling the box never comes near → the ceiling is a fat-box concern only                                                                                                                     | /tmp/t3-rss-2.log (1192 samples)                                                     |
| manual parallel arm (8×8192)                                                          | **OWNER-DEFERRED to the 96 GiB box** (owner ruling recorded at the §9 release event; this box's 62.69 GiB makes the heap arm not defensibly measurable — never silently degrade the arm)                                                                                                                                                                    | ledger §9 release-event deferral row; t3-draft/risk-notes.md heap math               |
| arm 3 (16 workers/4 GiB)                                                              | deferred with arm 2 (same ruling)                                                                                                                                                                                                                                                                                                                           | same                                                                                 |
| §6.2 18-file saturation re-prove                                                      | deferred with arm 2 (rides the parallel arm; green-alone equivalence must be re-proved there)                                                                                                                                                                                                                                                               | measurement-plan Step 5                                                              |
| **fork census (plan Step 3): `npx vitest related --run src/hooks/useAlertsQuery.ts`** | **20 files selected / 671 passed / 1 skipped / 176.40 s; peak CONCURRENT worker forks = 1** (1 Hz ps census, 193 samples; raw `node`-comm census peaked at 3 = npx wrapper + vitest main + ONE fork; worker-pattern census (excludes the `related` parent) peaked at 1) — serial contract holds: no parallelism without VITEST_PARALLEL                     | /tmp/t3-related-2.log, /tmp/fork-census.log, /tmp/fork-census-2.log                  |
| **`vitest related` honest scale note**                                                | a 1-hook probe still pulls 20 files / 672 tests / 176 s on this box — related follows the full TRANSITIVE import graph (runner header documents this as honest-by-design); the fast tier's ≤10 min budget has real headroom (2985 s full-suite ↔ 176 s single-hook)                                                                                        | same                                                                                 |

### Row F2 — fast-tier playbook (spec §6.3; 5 changes ≤10 min each)

`scripts/fast-validation-playbook.sh` (committed; the plan's LISTFILE GOTCHA
corrected + dirty-tree setup guard added before the revert trap — see commit
message). BASE = `git merge-base HEAD origin/main` (no local `main` in this
repo).

Run 1 (pre-fix, BASE=merge-base): all five printed walls 7/8/73/73/68 s but
the runs behind three of them were NOT real (vitest v5.0.0 at wrong root,
Python-invalid probe, tee RC-mask — see runners' RECONCILIATION headers;
evidence preserved /home/agent/gate19-prep/fcl-playbook-run1-logs/). Run 2
(post-fix, BASE=HEAD probe-only diffs) is the quotable one:

| Change                            | Selected (be/fe)                                                | Wall  | rc  | verdict                                                                 |
| --------------------------------- | --------------------------------------------------------------- | ----- | --- | ----------------------------------------------------------------------- |
| route(alerts.py)                  | be 8 files                                                      | 9 s   | 0   | OK (≤600 s wall)                                                        |
| service(alert_service.py)         | be 3 files / 159 tests                                          | 7 s   | 0   | OK                                                                      |
| component(ActionableInsights.tsx) | fe 1 file                                                       | 21 s  | 0   | OK                                                                      |
| hook(useAlertsQuery.ts)           | fe 20 files / 672 tests                                         | 178 s | 0   | OK — transitive-graph honest scale (matches the 176.40 s Step-3 census) |
| config(vite.config.ts)            | fe 0 (full-suite GUARD NOTICE fired, Tier-0 fallback by design) | 1 s   | 0   | OK — guard is the expected behavior, wall bound asserted only           |

Summary: 5/5 within the spec §6.3 10-minute wall; playbook rc=0
(/tmp/fcl-playbook2.log; per-case logs trap-wiped at exit by design — the
outer log carries the table). Fastest real case 7 s vs the ~11 min full
backend gate and ~50 min full frontend suite — the §6.3 aim (≤10 min/change)
met with ≥30× headroom on the backend cases.

Footer contract check (plan T13 Step 3, exercised by `--fast` after rows land):
`SELECTED: n files total` + loud `FAST TIER — no coverage proof; full gate still
required before merge.` + NO `VALIDATION SUCCESSFUL` string on the --fast path.

### Row H1 — honesty acceptance (spec §6.4)

| Probe                                                | Expected     | Result                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ---------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| collection-sanity gate exists and is wired           | script + job | `scripts/check-test-collection.py` landed (c5de7d57, spec 5.3); allowlist `.github/flake-allowlist.yml` (17b62e1c); frontend zero-byte trio allowlisted (a4c061fd, R-FCL-T1-TRIO) — the allowlist is the honest-red carve-out record                                                                                                                                                                                                                         |
| injected failing frontend test → CI frontend job RED | red          | nightly-full-gate.yml (ed3c9f0a) is the honest full-suite runner BY CONSTRUCTION (real exit code, no grep->pkill->exit-0, no un-pipefail'd status pipes — header states why); ci.yml push-job hack still lives (T4-class, ci.yml:1319 pkill); first red-on-injection record needs a GH-side run post-merge-to-main (workflow registration constraint: GitHub registers workflows only from the default branch — dispatch 404 pre-merge, observed 2026-09-14) |

### Row S1 — full-gate strictness byte-identity (spec §6.5; quote in PR)

- Quote for the PR, measured per-file at the M2 tip (e53c2b0e; docs commits
  after it touch none of these paths):
  `git diff 1be83995..HEAD -- scripts/validate.sh pyproject.toml frontend/vite.config.ts frontend/package.json scripts/AGENTS.md`
  → `validate.sh +97/−1 · vite.config.ts +11/−3 · package.json 2/2 · AGENTS.md +9/−0`
  — **pyproject.toml: ZERO delta** (verified at T13 apply and again at this tip).
  1be83995 = M1-final gate-19 tip; base anchor is the §6 record.
- Sanctioned delta 1 (T3): package.json NODE_OPTIONS wrapper — quote-style
  change only (2/2); effective NODE_OPTIONS identical with envs unset (control
  arm re-proved: wrapper fires `--max-old-space-size=${VITEST_HEAP_MB:-8192}`).
- Sanctioned delta 2 (T13): with `--fast` absent `RUN_FAST` stays `false` →
  zero new lines execute; `--bogus` still exits 1 with identical two lines
  (probe: /tmp/t13-bogus.log); `--help` shows the flag.
- First `validate.sh --fast` exercise (T13 Step 2, /tmp/t13-fast-probe.sh,
  VALIDATE_BASE=HEAD docs-only diff): rc=0; footer `SELECTED: 0 files total
(backend: 0 …, frontend: 0 …)` + loud `FAST TIER — no coverage proof; full
gate still required before merge.`; `grep -c "VALIDATION SUCCESSFUL"` = 0 on
  the fast-path log; tree clean after. A prior probe variant also captured the
  honest REAL-change path: run 2's hook case left `useAlertsQuery.ts` dirty
  (a race, recorded honestly) and fast tier fed exactly `src/hooks/
useAlertsQuery.ts` to related → 20 files / 672 tests, rc=0.

### Row S2 — flake allowlist hygiene (spec §6.6)

| Fact                                       | Value                                                                                                        | Record                                                                                                                                                                             |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Allowlist location                         | `.github/flake-allowlist.yml` (relocated 17b62e1c — meta-test globs `.github/workflows/` only), `flakes: []` | HEAD ls; test_github_workflows.py:64 glob                                                                                                                                          |
| Integration pytest retry masks             | 4/4 torn down (single honest runs under `set -euo pipefail`; flake-k-filter gate)                            | ci.yml integration jobs                                                                                                                                                            |
| Remaining `for attempt in 1 2 3` in ci.yml | **5** — frontend-side: npm ci ×1, Playwright browser-install ×3, **Playwright E2E test retries ×2**          | grep at fa6521ea, re-verified; the two E2E test-retry loops are blanket TEST retries → owner ruling queued (spec §6 row 6 "zero blanket retries" cannot be signed while they live) |

## M1 CI-blind-spot findings (Task 15 Step 2 — carried from M1 ledger)

1. profiler disabled in CI masked the pyroscope aarch64 crash class.
2. the frontend exit-0-on-first-summary hack hid the R-T7-VITEST class for
   months (hack still LIVE in ci.yml push job — T4-class fix; the nightly
   workflow deliberately does NOT copy it, header states so).
3. zero-byte tracked test files lived green on main (collection-sanity class;
   script + job landed c5de7d57; trio allowlisted honestly a4c061fd).

## Nightly trend rows (T14 home)

GitHub registers workflows ONLY from the default branch (`main`); the nightly
file lives on `feat/context-map-2026-09-12` and returns 404 to dispatch until
the branch lands on main (observed 2026-09-14, gh api). First row fills after
merge: first 04:17 UTC schedule run, or manual dispatch post-merge.

| Nightly # | date       | backend wall | combined cov | frontend wall | status |
| --------- | ---------- | ------------ | ------------ | ------------- | ------ |
| 1         | `________` | `________`   | `________`   | `________`    | `____` |
