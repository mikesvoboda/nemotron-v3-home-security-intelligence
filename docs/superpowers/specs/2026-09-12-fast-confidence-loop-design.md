# Fast Confidence Loop — Design (M2 workstream 1)

**Goal:** a small change earns local test confidence in ≤10 minutes, while the full validation gate keeps its exact strictness and stops sitting on the developer's critical path.

**Architecture:** three moves — (1) finish the test substrate the repo already designed (per-worker database isolation, machine-aware frontend parallelism), (2) tier the gates (new change-scoped `--fast` mode; full gate unchanged in semantics, repositioned to CI), (3) make CI truthful so the full run can be delegated with confidence.

**Owner decision context (2026-09-12):** brainstormed after the M1 validation marathon; owner chose the test-confidence loop over config-only speedups and over a microservices split. The split was explicitly rejected: this repo already deploys ~16 services plus separate `ai/` services; test wall-time is set by *shared mutable state* (one Postgres, one Redis), not by process boundaries, and a solo-developer single-user system earns none of the coordination benefits of further splitting. Revisit only if a non-productity requirement appears (independent scaling, fault isolation, team growth) — see §8.

## 1. Measured baselines (this design's problem statement, all measured 2026-09-12 on the GB300 dev box: 72 cores, 494 GB RAM)

| Measurement | Value | Evidence |
| --- | --- | --- |
| Backend combined pytest lane (validate.sh tier) | ~2.5–3 h; first lane hung ~2 h before diagnosis | `/tmp/t7-backend*.log`, lane 1 killed at 75% |
| Host load while lane ran | **load avg 8.1 on 72 cores**; one worker at 96% CPU, seven waiting | `uptime` + `ps` census during lane |
| Frontend full vitest suite | 24.5 min, run **serially** | `/tmp/t7-full-vitest.log` `Duration 1472s`; `frontend/vite.config.ts:375` `fileParallelism: false` |
| Frontend heap cap | `--max-old-space-size=8192` (package.json:19–21) — inherited from an 8 GB CI runner; box has 494 GB | `frontend/package.json` |
| Tests failed in CI-green state, discovered this milestone | ~67 frontend + ~145 backend + 3 zero-byte test files, all masked | SDD ledger `2026-09-12-arm64-gb300-milestone1/progress.md` (R-T7-VITEST, DBRACE, CONTAM sections) |

**The serialization, root-caised (R-T7-DBRACE-FINAL in the ledger):** `backend/tests/conftest.py:1642` fixture `test_db` → `get_test_db_url()` (`:557`) returns the raw exported `TEST_DATABASE_URL` (`scripts/validate.sh:148`), so every xdist worker shares one live-stack Postgres, and each fixture invocation runs `_reset_db_schema()` behind a pg advisory lock — a queue, not compute. Compounding: the authors' own protection is inert in the combined gate because pyproject addopts (`pyproject.toml:465`, `--dist=worksteal`) **ignores `xdist_group`** (only `loadgroup` honors it) and the `serial` marker has no consumer. The integration tier's `worker_db_url` machinery (`backend/tests/integration/conftest.py`, per-worker DBs) already exists — the legacy chain *bypasses* it. Redis is the A2 suspect for the queues/admin/dlq failure clusters: validate.sh exports one `REDIS_URL` at db 0 (`scripts/validate.sh:165`).

## 2. Principles (non-negotiable framing)

1. **Make the fast check cheap; never make the slow check optional.** Tier 1 adds a signal; it never removes one.
2. **A fast gate you can't audit is a fast gate you won't trust.** Tier 1 must print what ran and why.
3. **Fix shared-state serialization at the state, not by splitting processes.** (The rejected §8 option fails this test.)
4. **A gate that lies is worse than a slow gate that tells the truth.** All CI changes in §5 are honesty restorations, never strictness reductions.

## 3. Substrate workstream (removes the ceiling)

### 3.1 Per-worker Postgres isolation

- Retire the raw-env bypass: `get_test_db_url()` (`backend/tests/conftest.py:557`) must route through per-worker database creation (name suffixed by `PYTEST_XDIST_WORKER`; `-n0`/absent → deterministic single name) instead of returning `TEST_DATABASE_URL` verbatim. Reuse the proven machinery in `backend/tests/integration/conftest.py` (`worker_db_url`), which already creates per-worker DBs even under override mode — the goal is one path, not two.
- `scripts/validate.sh` keeps exporting `TEST_DATABASE_URL` (connection *parameters*: host/port/user/password/db prefix) but the suffix logic moves into conftest so workers never share the DB itself.
- Acceptance: the M1 `R-T7-DBRACE` cluster (alert_repository 41, zone/queues/admin/dlq, api_protection) passes under `-n auto` with **zero** xdist node-downs; the M1 `--dist=loadgroup` flag ships as the interim belt and is REMOVED only after this lands green in two consecutive full runs (supersession recorded in validate.sh's comment + a ledger/notes line).
- Template-per-worker (`createdb -T template1`) is the implementation unless the M2 measurements show template cost dominates; teardown drops the worker DB (atexit + defensive pre-clean of stale `*_gw*` names, mirroring the integration conftest's existing hygiene).

### 3.2 Per-worker Redis isolation

- conftest-scope only: derive `REDIS_URL` db index from the xdist worker slot (`redis://localhost:6379/{1+worker_index}`; main = 0) before redis clients construct, honoring an explicit env override; flush the worker's logical DB at session start instead of relying on shared db0 hygiene.
- Acceptance: the A2-class clusters (test_queues_api / test_admin_api / test_dlq_api) pass under `-n auto`; no test file or production module changes (this is TEST-only; production config untouched).

### 3.3 Frontend parallelism, machine-aware

- `fileParallelism` becomes env-driven in `frontend/vite.config.ts`: default stays `false` (small-heap CI stays safe); `VITEST_PARALLEL=1` enables file-parallel with `maxWorkers` bounded by an env (`VITEST_MAX_WORKERS`, default `min(cpus, 8)`) and heap raised only in that mode. validate.sh sets both from detected RAM (≥64 GB → parallel).
- Follow-up (same workstream, separate commit, gated on a measured CI runner OOM fix): raise the 8192 MB cap for CI too. Until then CI behavior is byte-identical to today's.
- Acceptance: full frontend suite < 10 min on the GB300 with zero saturation-shaped failures (§6 protocol rerun of the previously-flaky 18-file set, green-alone equivalence must still hold).

## 4. Gate tiering

Tier 0 (seconds; already exists, unchanged): ruff / eslint / tsc / mypy on the tree.

### 4.1 Tier 1 — `scripts/validate.sh --fast` (target ≤10 min)

- **Change set:** `git diff --name-only` against a base ref (arg; default = merge-base with `main`, overridable by env `VALIDATE_BASE`). Renames/deletions handled by git's own filter.
- **Frontend selection:** `npx vitest related <changed files> --run` — vitest's native import-graph selection. Files with no import path to tests fall back to Tier 0 + a notice line.
- **Backend selection:** path-proximity mapping table (v1, predictable): `backend/api/routes/X.py` → `tests/**/test_X*.py` + `tests/integration/test_*api*.py` named matches; `backend/services/Y.py`, `backend/models/…`, mirrored `tests/unit/…` siblings; anything unmapped → printed as UNMAPPED + smoke set (see below). testmon is explicitly v2-behind-a-flag (`--fast=testmon`) — its staleness class (misses tests whose behavior changed under unchanged imports) is acceptable for an advisory tier only after v1's selection data exists.
- **Smoke set (always included):** the existing contracts tier (`uv run pytest backend/tests/contracts -n0` — small, catches route-wiring/config-break class) + the 3 smoke files named in validate.sh's contracts step.
- **Output contract:** header prints `SELECTED: n tests across m files (frontend: x via related, backend: y via proximity, smoke: z)` and `--why` lists per-file selection reason. Exit semantics mirror validate.sh's (nonzero = any failure), with a loud footer: `FAST TIER — no coverage proof; full gate still required before merge.`
- **Non-goals:** no coverage measurement (coverage is the full gate's identity), no prettier/lint (Tier 0), no e2e/load/benchmarks (already out of gate).

### 4.2 Tier 2 — full gate, unchanged semantics

`./scripts/validate.sh` stays exactly as M1 leaves it (combined-cov 80, single pytest invocation, strict frontend step, `--dist=loadgroup` per M1 until §3.1 supersedes it). Its *position* moves: run on PR + nightly by CI (§5), not on every keystroke by the developer.

## 5. Honest CI (the enabling condition)

Findings from this milestone's forensics, each a concrete fix (all in `.github/workflows/ci.yml`; line numbers from its current state):

1. **Frontend exit-0-on-first-summary hack** (`ci.yml:1305–1321` region: the job `exit 0`s 5 s after a "passed" line appears, as an OOM workaround). Replace with: real exit code + bounded `maxWorkers`/heap via §3.3 envs + `--no-file-parallelism` only if a measured runner OOM demands it, with the OOM issue tracked. Acceptance: an intentionally failing frontend test turns the job red.
2. **Blanket retry masks** (integration jobs retry ×3 with `exit 0` fallbacks at `ci.yml:360, 462, 573, 690, 799`). Replace with a **registered-flake allowlist**: a single YAML/JSON list mapping test-id → tracking-ref + expiry date; pytest-rerunfires applies only to allowlisted ids (via `-k` selection of the allowlist, or a `--rerun` wrapper). Un-allowlisted failures fail once and stay failed. Expired entries fail until re-registered or fixed.
3. **Collection sanity:** a CI step (or pre-commit-consistent script in `scripts/`) that fails when any tracked `*.test.ts(x)`/`test_*.py` file collects zero tests OR is zero bytes. Three zero-byte test files sat undetected on `main` this milestone; this step makes that state red within one push.
4. **Nightly full run** (`schedule` trigger) running the no-flag `validate.sh` artifact-equivalent on the existing runner matrix, results posted as a job summary — restoring "the full suite ran somewhere trustworthy yesterday" so the local suite returns to being a tool, not the only honest gate.
5. Out of scope here: runner hardware, self-hosted runners, matrix expansion. If §3.3's envs make CI OOM recur, that's evidence for a runner conversation, not for restoring the hack.

## 6. Verification of this work (exit criteria)

Each row measured before/after on the GB300 dev box, numbers recorded in a notes doc under `docs/development/` (the CI-blind-spots findings from M1 ride along):

| # | Criterion | Target |
| --- | --- | --- |
| 1 | Backend combined tier wall-time at `-n auto` | < 30 min, **zero** node-downs |
| 2 | Frontend full suite with §3.3 envs | < 10 min, zero saturation-shaped failures (18-file §6 re-prove) |
| 3 | `validate.sh --fast` on the scripted 5-change playbook (one route, one service, one component, one hook, one config) | ≤ 10 min each; selection table printed; playbook file committed under `scripts/` |
| 4 | Injected failing test / injected zero-byte test file | CI frontend job red; collection-sanity step red |
| 5 | Full gate strictness | byte-identical pytest/vitest invocations + coverage bar vs M1-final `scripts/validate.sh`, diff quoted in PR |
| 6 | Flake allowlist | every entry carries a tracking ref; zero blanket retries remain |

## 7. Explicit non-goals

- No service splitting (§8 documents the settled reasoning and the trigger to revisit).
- No change to production runtime code except where a *test-infrastructure* change forces a hook (none expected; anything larger is a new spec).
- No coverage-bar movement, no test deletion, no `.skip`, no assertion contortion — the M1 escalation rules transplant verbatim.
- No CI runner/hardware changes; no `docker-compose.prod.yml` edits (M1's hard stop remains repo policy).

## 8. The settled split decision, and the trigger to reopen it

Rejected 2026-09-12 (owner-approved framing): the repo already deploys ~16 services plus separate `ai/` services; the remaining "monolith" (one FastAPI process ≈1,513 modules, one React app) gains no test-speed benefit from splitting while shared state is the serialization — services sharing one Postgres schema-reset lock are a monolith with extra HTTP. For a solo developer on a single-user box, team-coordination benefits are ≈0 and operational costs (contract ceremony, deployment graph, observability surface) are all real. **Reopen iff** any of: a second developer with divergent deploy cadence; a component needing independent scaling or fault isolation (the enrichment pipeline is the named candidate — GPU-bound, different failure domain); or tests *still* serialize after §3 lands (which would mean coupling lives in code, not config — then slice along the seams the tests reveal).

## 9. Sequencing and dependencies

1. §3.1 (per-worker PG) — unblocks everything measured; first deliverable includes the before/after lane numbers.
2. §3.3 (frontend envs) — independent; ships in parallel.
3. §5.1–5.3 (CI honesty + collection sanity) — can start once §3.3 envs exist; §5.4 nightly last.
4. §4.1 `--fast` — after §3.1 (selection over a contended suite is unreliable — the M1 contamination lesson); its playbook doubles as §6.3 verification.
5. §2's `--dist=loadgroup` removal — strictly after §3.1 green ×2, supersession recorded.

M1 constraint: nothing in this spec may touch `scripts/validate.sh`, `pyproject.toml` addopts, or `frontend/vite.config.ts` behavior while M1's final no-flag `validate.sh` run is still outstanding. This spec's plan must sequence its first commits *after* M1 close-out (or land purely-inert additive files — `--fast` behind a new flag in a branch, merged post-M1).
