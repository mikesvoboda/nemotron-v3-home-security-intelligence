# Revival Timeline — 2026-09-12 → 2026-09-15

Narrative companion to the ledger
[`2026-09-12-context-map-doc-updates.md`](2026-09-12-context-map-doc-updates.md).
The ledger is exhaustive and ordered by gate run; this document is ordered by
day and explains _why_ each phase happened. The ledger remains ground truth —
where the two disagree, believe the ledger.

Reconstructed from `git log` across all branches plus the ledger's own gate rows
and owner rulings.

## Summary

The project was built over Dec 2025 – Feb 2026, then sat dormant for six and a
half months. Development resumed on 2026-09-12 when the codebase was brought up
on a new arm64 (GB300) workstation. Four days and 330 commits later the full
validation gate ran green, the branch merged to `main`, and a six-month backlog
of flagged dependency updates was cleared.

Almost none of it was new features.

| Commit type | Count |
| ----------- | ----- |
| `test`      | 156   |
| `docs`      | 92    |
| `fix`       | 28    |
| `chore`     | 20    |
| `ci`        | 13    |
| `style`     | 6     |
| `feat`      | 5     |

## The dormancy

| Period          | Commits | Phase            |
| --------------- | ------- | ---------------- |
| 2025-12         | 428     | Original build   |
| 2026-01         | 626     | Peak development |
| 2026-02         | 121     | Wind-down        |
| 2026-04         | 1       | Stray bot commit |
| 2026-09-12 → 15 | 330     | Revival          |

Last active commit before the gap: `3396d3ef` (2026-02-25, PR #6394). First
commit of the revival: `b5da576a` (2026-09-12 01:03) — an arm64/GB300
milestone-1 design spec. The work opened with a written plan, not with code.

## Day 1 — 2026-09-12 (39 commits): arm64 bring-up

Design spec, implementation plan, and a findings ledger were all committed
within seventeen minutes. Platform deltas followed:

- `53299751` — `.env.example` never declared the `TEMPO`,
  `AI_GATEWAY_METRICS`, and `GPU_AI_SERVICES` ports that the production compose
  file already referenced.
- `9f31253d`, `c8a2ee80` — GB300 env template and an **additive** compose
  overlay carrying the single-GPU and rootless-socket deltas. Additive by
  design, so amd64 users never load the file and the production compose stays
  untouched.
- `67c9fa2c` — node-exporter root bind without `rslave`, required under rootless
  podman.
- `4e4ad536` — `scripts/bootstrap-gb300.sh`, codifying the bring-up once proven.

Fifteen services were healthy on arm64 by 01:41.

The first test-side signal was architecture-specific: `a579b5a0` disabled the
pyroscope native profiler under pytest, because it crashed the test process
under xdist on aarch64 — a failure mode invisible on x86.

Then the discovery that shaped the next three days:

- `c5de7d57` — CI gate rejecting **zero-byte and zero-test tracked test files**.
- `547d3213` — quarantine of a frontend "zero-byte class".

Test files were tracked in git and counted toward the suite while containing
nothing, or collecting no tests. The gate now fails the build if that recurs.

## Day 2 — 2026-09-13 (67 commits): gate convergence

First full `./scripts/validate.sh` run on arm64:

> **315 failed / 29,954 passed / 242 skipped / 1,550 errors — coverage 27.31%**
> (gate requires 80%)

Successive runs, each recorded as a ledger row:

| Run | Result                               |
| --- | ------------------------------------ |
| 1   | 315F / 1550E — coverage 27.31%       |
| 2   | 238F / 766E (722s)                   |
| 3   | 352F / 355E (1147s)                  |
| 4   | 226F / 1398E — coverage 85.17%       |
| 5   | 239F / 377E — coverage 25.26% (FAIL) |
| 6   | integration tier killed at 99%       |

The numbers oscillated because most of the early noise was **infrastructure,
not test defects**:

- **1,550 of run-1's errors were self-inflicted.** Probe runs issued alongside
  the gate churned testcontainers port-forwards. Rule recorded: the gate runs
  alone.
- `0978d11f` — OTEL tracing inside the test process drove an OOM cascade.
- `5bbd6939` — `clean_tables` used `TRUNCATE`, whose relfilenode churn exhausted
  inodes and triggered a postmaster `PANIC` on `ENOSPC`. Switched to `DELETE`.
  The ledger carries an explicit correction here: the suspected "external inode
  burst" was self-inflicted.
- `R-T7-DBRACE-CUTOVER` — root-tier database URL replaced with per-worker
  databases.
- `R-T7-WORKERDOWN` — apparent worker crashes were `pytest-timeout` calling
  `os._exit(1)`, not a memory leak.

Two genuine production bugs surfaced, found by tests that had never been run:

1. `dfa8bc0c` (ruling F1) — `zones_redirect_router` was registered _before_ the
   real `/api/zones` routers, shadowing them.
2. `R-T7-BACKUP-MOUNT` (ruling F4) — `/api/backup` was fully implemented and
   called by the frontend (`backupApi.ts`), but was never mounted in any
   revision. It returned 404 in production. Mounting it took that test file from
   29 failures to 7.

## Day 3 — 2026-09-14 (160 commits): the repair wave

The largest day; 52 commits landed in the midnight hour alone. The bulk was
`R-T9-*` realignments teaching each test the **shipped** contract rather than an
assumed one:

- `R-T9-ACTIONEVENTS404` — an unknown camera answers 200 with an empty page, not 404.
- `R-T9-CALIBRATION` — threshold adjustment is integer; the asserted float bound
  was unattainable.
- `R-T9-CORS` — tests assumed `http://localhost:3000`; the shipped allowlist is
  the `:8444` trio plus `frontend:8080`.
- `R-T9-RISKVAL` — the gap-rate test raised `IndexError` on zero scenarios
  instead of skipping, meaning it had been passing vacuously.
- `R-T7-APIKEY-DEAD` — API keys created in the database authenticate nothing;
  only `settings.api_keys` is ever checked.

The memory investigation closed:

- `R-T7-WS-OOM` — the worker leak was mock-fed pipeline worker loops that never
  terminated.
- `R-T8-ENVLEAK` — a gate run contaminated its own summary by generating `.env`
  mid-run. Gates now require `.env` to be absent.

Two frontend root causes worth keeping:

1. A `useLocalStorage` call site passed an inline object literal as
   `initialValue`. `JSON.parse` returns a fresh object each call, so the memo
   identity changed every render, the sync effect re-ran, and the
   setState → effect → render loop never settled — exhausting an 8 GiB heap.
   Any inline-literal call site is a render-loop bomb.
2. A tremor `useTooltip(300)` **real** timer outlived jsdom teardown in a reused
   fork. Vitest attributed the resulting unhandled error to whichever file ran
   _next_, so the reported file was an innocent neighbor. Fake-timer cleanup
   cannot see real-timer library leaks.

Hardware and process: workstation RAM raised 62.7 → 96 GiB; a power cycle killed
gate 18 mid-run, with a handoff document written before the halt.

**Gate 19 ran green** at 17:21–18:25 — a bare `validate.sh`, 63m53s, zero
`[ERROR]` lines.

## Day 4 — 2026-09-15 (64 commits): hygiene, merge, dependencies

Milestone 3 turned the one-off repairs into standing guarantees:

- `autospec` applied across mock call sites — 67 patches in the clip_client
  tests, 86 in the nemotron analyzer — so mocks are checked against real
  signatures.
- Dead fixtures and a dead worker-database block removed; unit/integration
  double-marks resolved.
- New permanent guards in `scripts/`: `timeout-guard.py`,
  `parametrize-guard.py`, `flake-k-filter.py`, `check-test-collection.py`.
- **Gate 20 green in 20.9 minutes** against a 2,966s anchor — the first
  parallel-vitest run on the larger box. **Gate 21 green** confirmed it.

Repository cleanup: a 978 MB tracked snapshot de-tracked, Git LFS removed, three
dead workflows fixed or deleted.

Merge and CI parity: PR **#6538** landed the branch on `main`; Node 24 LTS and
Python 3.14 were then enforced with `.nvmrc` and `.python-version` as the single
source of truth (#6539, #6540).

The dependency backlog accumulated during dormancy was cleared:

| PR    | Change                                                                                                |
| ----- | ----------------------------------------------------------------------------------------------------- |
| #6541 | Frontend lockfile refresh — clears npm audit high/critical                                            |
| #6542 | Python lockfile refresh — clears the pip-audit backlog                                                |
| #6544 | `uv` group, 15 updates                                                                                |
| #6545 | rollup-plugin-visualizer 6.0.5 → 7.0.0                                                                |
| #6508 | nvidia/cuda → 13.2.1-runtime-ubuntu22.04                                                              |
| #6548 | ubuntu 24.04 → 26.04; nvidia/tensorrt 26.01 → 26.04 (yolo26 + clip); GitHub Actions minor/patch group |

Upgrading the toolchain then broke it, so `94b48ac9` cleared the resulting
ruff 0.16 and mypy 2.3 failures, and `1b18aed3` held msw at 2.12.10 to keep a
working combination.

## End state

908 backend and 807 frontend test files, running green:

| Tier                | Result                                  |
| ------------------- | --------------------------------------- |
| Backend unit        | 27,524 passed                           |
| Backend integration | 4,165 passed                            |
| Frontend            | 20,220 passed / 136 skipped (777 files) |

## What this bought

The fixes matter less than the mechanisms. Each failure mode found during the
revival now has a gate that prevents its return:

| Failure mode                          | Prevented by                                  |
| ------------------------------------- | --------------------------------------------- |
| Test files that contain no tests      | collection-sanity gate                        |
| Tests that hang instead of failing    | `timeout-guard.py`                            |
| Mocks that drift from real signatures | `autospec` convention + `check-test-mocks.py` |
| Toolchain version drift               | `.nvmrc` / `.python-version` parity gate      |
| Gate runs contaminating themselves    | `.env`-absent rule (R-T8-ENVLEAK)             |

The class of rot that accumulated silently over six and a half months of
dormancy cannot now recur without failing CI.
