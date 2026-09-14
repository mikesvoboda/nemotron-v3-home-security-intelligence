# Fast Confidence Loop — Measurements Record (M2 Task 15 prefill)

<!-- M1 §6 release event anchor: milestone1-design.md:178-179 "`./scripts/
validate.sh` exit 0 on aarch64 (coverage gate 80 combined)" — the green
RECORD of that run is plan §9's release condition, not the run's end. -->

> Target home when applied: `docs/development/fast-confidence-loop-measurements.md`
> (plan Task 15; scaffolded at Task 8 in the plan — this file pre-fills every
> row that is ledger-measured TODAY and leaves BLANK boxes for pending arms).
> DRAFT under /tmp/wave3-drafts — nothing in the repo has been written.

**Measurement box reality (must precede every number):** the spec's §1
baselines are labeled "GB300 dev box: 72 cores, 494 GB RAM", but the ledger's
anchor runs (gate 10, runA2, gate 13) were measured on the CURRENT box:
**16 cores, MemTotal 65,744,332 kB = 62.69 GiB** (`/proc/meminfo`,
`nproc` — read 2026-09-14, corroborated by /tmp/t3-draft/measurement-plan.md
§"Box reality"). Targets written for the fatter box are stretch goals here and
are labeled as such per arm. Never compare a row across boxes without saying
so.

## M1-pre-plan datapoints (spec §9 / Task 8 scaffold rows)

| # | Datapoint | Value | Evidence |
| --- | --- | --- | --- |
| P1 | Backend combined lane, M1 era | ~2.5–3 h; host load 8.1/72 cores, all queue (R-T7-DBRACE-FINAL) | M1 spec §1 (docs/superpowers/specs/2026-09-12-fast-confidence-loop-design.md:13-14) |
| P2 | 443 GB lane-1 kernel-OOM worker datapoint + D2 late-lane hard-crash tail | (text rides in M1 ledger R-T7-POISON-CASCADE + AMENDMENT-RESOLUTION) | plan Task 8 "Pre-existing content to absorb" |
| P3 | D1 arbiter: chaos solo `-n0` rerun HUNG, RC=1 timeout dump at redis_streams.py:402 — hang-class, not 137/139 | chaos scoped OUT of validate.sh combined gate (commit 0b1f8882) | plan :1322-1335 |

## Ledger-measured rows (PREFILLED) + pending arms (BLANK boxes)

### Row B1 — backend integration tier wall-time (M3 T4c program)

| Arm | Wall | Record |
| --- | --- | --- |
| pre-T4 | 919.75 s | ledger (goal-prompt doc :9; context-map plan :2116 region) |
| runA2 (post-T4c, VERIFIED green: 4165 passed / 131 skipped / 2 xfailed, zero node-downs) | **618.53 s** (−33%) | docs/plans/2026-09-12-context-map-doc-updates.md:1973-1979, :2116 |
| gate 13 (same code; tier RED — 11 failed, all test_github_workflows class) | **597.47 s** (−3.4% vs A2, within noise; do NOT quote as "verified green") | same file :2158 |
| teardown p50 | 1.043 s → **0.224 s** | context-map plan :1981 |
| setup p90 | 1.161 s unchanged (next target: init_db seam) | context-map plan :1983-1984 |

### Row B2 — combined backend full gate wall at `-n auto` (spec §6.1; target <30 min on fat box)

| Arm | Wall | Record |
| --- | --- | --- |
| BEFORE (M1) | `________________` (~2.5–3 h, P1) | M1 spec §1 |
| gate 13 NOTE: validate.sh integration-tier exit (red tier) | 597.47 s | see B1; gate-14 chain state row |
| AFTER — gate 14 (validation gate LIVE: no-flag `./scripts/validate.sh`, pid 941436, log /tmp/validate-full-14.log) | `________________` [pending — fill from gate-14 close line ONLY if green; unit/integration split per D14] | gate14.pid / validate-full-14.log:______ |
| AFTER — §6.1 green ×2 confirmation runs | `________________` `________________` | plan Task 8 Step 2/3 |
| node-down count across the two runs | `____` / `____` (hard requirement: 0) | same logs |

### Row B3 — combined coverage (gate is 80; bar NEVER moved — spec §7)

| Arm | Value | Record |
| --- | --- | --- |
| run-7 `coverage combine` (unit+integration merged) | **87.96%** ≥ 80 [OK] | ledger context-map plan :1792 (`/tmp/validate-coverage-report.log` content quoted there; the literal TOTAL line also sits at /tmp/validate-full-10.log:30) |
| runA2 merged | `________________` [not recorded in the A2 entry] | — |
| gate 14 merged | `________________` [pending] | /tmp/validate-coverage-report.log (overwritten per run) |

### Row F1 — frontend full vitest suite (spec §6.2; target <10 min on GB300, stretch on this box)

| Arm | Wall | Record |
| --- | --- | --- |
| BEFORE — serial forks (supersedes spec §1's 1472 s figure per ledger item 4) | **2981.18 s** (~49.7 min; 781 files, 20,340 tests; internal split transform 23.89 / setup 350.85 / import 556.89 / tests 743.30 / environment 855.94) | /tmp/validate-full-10.log:35473 `Duration 2981.18s`; ledger context-map plan :2091 |
| control (T3 patch applied, envs unset — proves inert) | `________________` | T3 measurement-plan protocol arm 0 |
| manual parallel arm 2: `VITEST_PARALLEL=1 VITEST_MAX_WORKERS=8 VITEST_HEAP_MB=8192` | `________________` (forecast 420–750 s) | protocol arm 2 |
| arm 3: `--max-workers 16`, heap 4096 (if arm 2 survives) | `________________` (forecast ~5–8 min) | protocol arm 3 |
| peak summed RSS per arm | `________________` | protocol arm 4 (ps sampling) |
| §6.2 18-file saturation re-prove (green in-suite AND green-alone) | `________________` | protocol arm 5 |

### Row F2 — fast-tier playbook (spec §6.3; each of 5 changes ≤10 min)

| Change (route/service/component/hook/config) | Selected (be/fe) | Wall | rc |
| --- | --- | --- | --- |
| `________________` ×5 | `________________` | `________________` | `____` |

Blocked-by: T10/T11/T12 runners (`scripts/fast_select.py`,
`fast-backend-runner.sh`, `fast-frontend-runner.sh` — verified ABSENT at
fa6521ea) + T13 apply (M1 §6 record). Footer contract at T13 apply:
`SELECTED: n files total (backend: … frontend: …)` + loud
`FAST TIER — no coverage proof; full gate still required before merge.` +
NO `VALIDATION SUCCESSFUL` string on the --fast path (plan Task 13 Step 3).

### Row H1 — honesty acceptance (spec §6.4)

| Probe | Expected | Result |
| --- | --- | --- |
| injected failing frontend test → CI frontend job RED | red | `________________` (needs T4 ci.yml honesty landed + GH run; T4 draft in /tmp/wave2-drafts/t4/) |
| injected zero-byte tracked test file → collection-sanity job RED | red | `________________` (scripts/check-test-collection.py EXISTS at HEAD — landed; CI job wiring + injection record pending) [job wiring UNVERIFIED] |

### Row S1 — full-gate strictness byte-identity (spec §6.5; quote in PR)

- `git diff <M1-final>..<HEAD> -- scripts/validate.sh pyproject.toml` →
  quote: `________________` [pending M1 §6 record = the diff's base anchor]
- Sanctioned delta 1 (T3): package.json NODE_OPTIONS wrapper — quote-style
  change only; effective NODE_OPTIONS identical with envs unset. Diff quote:
  `________________` (from /tmp/t3-draft/t3.patch, package.json hunk)
- Sanctioned delta 2 candidate (T13): `git apply --check` stat at fa6521ea =
  **2 files, +93 insertions, −0 deletions** (validate.sh +84, AGENTS.md +9);
  hunks at :11-16/:27-32/:78-88 (docs+flag init), :191-196 (arg case),
  :508-513 (function insertion), :516-521 (guarded dispatch) — with `--fast`
  absent, `RUN_FAST` stays `false` so zero new lines execute; no existing
  line is touched. Diff quote: from /tmp/wave3-drafts/t13-t14-m2/
  t13-validate-fast-wiring.patch.
- pyproject addopts delta: `________________` [none planned; verify at quote time]

### Row S2 — flake allowlist hygiene (spec §6.6)

| Fact | Value | Record |
| --- | --- | --- |
| Allowlist location (gate-13 lesson: .github/workflows/* is meta-validated as workflows by backend/tests/integration/test_github_workflows.py — data files must live elsewhere) | `.github/flake-allowlist.yml` (relocated by commit 17b62e1c), `flakes: []` | HEAD ls; test_github_workflows.py:64 glob; ledger gate-13 postmortem |
| Integration pytest retry masks | 4/4 torn down (single honest runs under `set -euo pipefail`, flakes gated behind `scripts/flake-k-filter.py`) | ci.yml integration jobs (e.g. "Run API integration tests") |
| Remaining `for attempt in 1 2 3` in ci.yml at fa6521ea | **5** — all FRONTEND-side: npm ci install retry ×1, Playwright browser-install retries ×3 (:1448/:1583 region), **Playwright E2E test retries ×2 (:1491, :1626)** | `grep -c 'for attempt in 1 2 3' .github/workflows/ci.yml` = 5 |
| Ruling needed | the two E2E test-retry loops are blanket TEST retries — §5.2's enumerated sites were the 4 pytest jobs, but "zero blanket retries remain" (§6 row 6) arguably covers these. STOP-AND-ASK candidate for the owner memo's queue. | this row |

## M1 CI-blind-spot findings (Task 15 Step 2 — carry verbatim from M1 ledger when scaffolding lands)

1. profiler disabled in CI masked the pyroscope aarch64 crash class.
2. the frontend exit-0-on-first-summary hack hid the R-T7-VITEST class for months (hack still LIVE in ci.yml push job at fa6521ea: pkill at ci.yml:1319 — T4 fixes).
3. zero-byte tracked test files lived green on main (Task 1's collection-sanity class; script landed, job record pending).

## Nightly trend rows (T14 home; fill after first `gh workflow run`)

| Nightly # | date | backend wall | combined cov | frontend wall | status |
| --- | --- | --- | --- | --- | --- |
| 1 | `________` | `________` | `________` | `________` | `____` |
