# M2 Tasks 5/6/7 draft — reconciliation notes (DRAFT ONLY; nothing applied to the repo)

Repo: /agents/agent-nemo2/workspace @ fa6521ea (branch feat/context-map-2026-09-12).
Patch files (git-apply --check verified, rc noted, chain order t5 → t6 → t7):

| patch | vs | rc |
| --- | --- | --- |
| /tmp/wave3-drafts/t5/t5.patch | HEAD | 0 |
| /tmp/wave3-drafts/t6/t6.patch | HEAD+t5 | 0 |
| /tmp/wave3-drafts/t7/t7.patch | HEAD+t5+t6 | 0 |
| t5+t6+t7 after /tmp/t3-draft/t3.patch | stacked | 0 (t7 check rc=0) |

Re-generation script for the t7 layer (kept for rebase work): /tmp/wave3-drafts/t7/apply_t7.py.
All checks ran in the throwaway clone /tmp/wave3-drafts/repo; the workspace was never written.

## 1. THE LOUD FINDING: Tasks 5 and 6 ALREADY SHIPPED inside M1

Plan Tasks 5 and 6 are **not landable as written** — they landed during M1 Task 7:

- **Task 5** (`worker_id` / `worker_db_name` / `_create_worker_database` /
  `_drop_worker_database` + `backend/tests/test_db_isolation.py`) = commit
  **e85c2cf3** (2026-09-13, "test(core): per-worker DB isolation helpers +
  contract tests (spec 3.1)"), message: "Landed inside M1 Task 7 as substrate".
  Verified live at HEAD: conftest.py:638/:648/:661/:696 (helpers),
  test_db_isolation.py exists (5,523 B, 140 lines, both plan test classes).
- **Task 6** (`get_test_db_url` cutover + `TEST_DB_NO_WORKER_SUFFIX` opt-out) =
  commit **e8619d80** ("get_test_db_url returns per-worker databases (spec 3.1
  cutover)"). Verified live: conftest.py:573-625 (opt-out path 0 at :596,
  suffixed create at :612-618), ledger run-6 proof row "New worker DBs visible
  in pg_database (security_gw0..3, security_main) — cutover verifiably live"
  (docs/plans/2026-09-12-context-map-doc-updates.md:424-425).
- **Task 7** (lifecycle: memo + sweep + drop-at-session-end) = NOT landed. It is
  the real remainder of §3.1 and the only genuinely new code in this draft.

Per the task's reconciliation mandate, the three patches are re-scoped:

- **t5 → reconciliation patch** (no behavior change): (a) fixes the now-false
  header comment "get_test_db_url behavior is unchanged until the cutover task"
  (conftest.py:635) which still advertises the pre-cutover world; (b) adds
  `TestNameSafetyInvariants` — pure-string collision contracts pinning that
  `worker_db_name` never returns a protected/base name and that root-tier
  names never collide with the integration tier's `security_test*` — coverage
  neither e85c2cf3 nor e8619d80 shipped.
- **t6 → re-validation patch**: amends the existing `TestGetTestDbUrlCutover`
  with (a) `test_opt_out_does_not_disturb_env` (DiskFull lesson:
  TEST_DATABASE_URL/TEST_REDIS_URL come from /etc/sandbox-persistent.sh:7-8 and
  nothing may unset/default them — grep-verified today: zero test code writes
  TEST_DATABASE_URL except monkeypatch in test_db_isolation; the new test pins
  it), (b) `test_returned_url_actually_connects` (gate-9's InvalidCatalogNameError
  shape), and (c) one readability fix: the shipped opt-out assertion chained
  `.replace("postgresql+asyncpg://", "postgresql+asyncpg://")` (a no-op);
  replaced with the single normalization that matches the pre-cutover contract
  (`git show e8619d80^`). No duplicate test-class names (ruff F811-clean).
- **t7 → the real lifecycle patch**, described in §2.

## 2. t7 design — and where it deliberately deviates from the plan text

Plan Task 7 = "create-once memo + autouse session fixture
(`worker_database`) + prefix-scoped sweep". Shipped shape deviates twice, loudly:

1. **Hooks, not a fixture.** The name `worker_database` is TAKEN at HEAD
   (conftest.py:1211) by the DEAD template-family fixture the M3-static census
   maps (t2-dead-fixtures.md §1: family 948-1335, `worker_database` 0
   consumers, `cleanup_stale_databases` autouse and LIVE). Defining the plan's
   fixture would shadow it mid-census and collide with M3-T2's pending purge.
   Independently fatal: an autouse **session** fixture runs once per xdist
   worker (each worker = its own pytest.Session), so a fixture-shaped sweep
   runs -n times and races itself. `pytest_sessionstart` is the only
   once-per-run hook (xdist workers do fire it, but every worker sets
   PYTEST_XDIST_WORKER before its inner session starts —
   .venv/.../xdist/remote.py — so the master guard skips them).
2. **Reclaim at session end lives EARLY in pytest_sessionfinish, not at the
   tail.** The existing body early-`return`s when FLAKY_TEST_RESULTS_FILE is
   unset (conftest.py:265 default ""; that's exactly the validate.sh/gate env),
   so a tail-placed reclaim would silently never run on the box. (This bug was
   in the first draft and caught in self-review — see the NOTE comment added.)
   Hook ordering verified against the pinned pytest 8.4.2: conftest's
   `pytest_sessionfinish` runs LIFO **before** pytest-runner's, and
   `SetupState.teardown_exact(None)` (session fixture finalizers) runs inside
   the runner's sessionfinish (_pytest/runner.py:108-111, main.py:318-331) —
   i.e. our reclaim runs while OUR OWN session-scoped engines are still open,
   which is precisely why `_db_has_active_connections` (self-inclusive by
   design) defers our own DBs and the drop is best-effort.

Collision-safety machinery (the gate-9 lesson, ledger
"run 9's killer is MY concurrent -n auto run — DB-name collision",
docs/plans/2026-09-12-context-map-doc-updates.md:1911+):

- **Create-once memo** `_memo_worker_database` keyed `(worker_id(), base_url)`;
  cache hit = zero psycopg2 round-trip (plan Step 3 contract; `get_test_db_url`
  paths 1+2 now route through it).
- **Sweep** (`_sweep_stale_worker_dbs`, master, session-start): membership =
  anchored `re.fullmatch(rf"^{prefix}_(?:gw[0-9]+|main)$")` over LIKE-prefixed
  `pg_database` rows, minus `_PROTECTED_DB_NAMES`, minus anything with an
  active connection. On the box's gate env (`TEST_DATABASE_URL` base =
  `security`) membership is {security_main, security_gwN}; `security_test` and
  `security_test_gwN` (the LIVE integration tier's DBs — run 9's victims) and
  the bare base DB can never match (regex proof: unit-test
  `test_sweep_membership_and_active_guard`, 10-row catalog incl.
  `security_test_gw3`, `otherprefix_gw1`, `template_test`, `test_db_gw2`).
  LIKE `_` escaping applied (`\_`) so `security_db_1%` can't prefilter-match
  `security_dbX_...`; fullmatch is the real gate anyway. **The sweep also
  never deletes the pre-existing `security_test*` leftovers it encounters** —
  different namespace by construction, verified [VERIFIED, stdlib simulation of
  membership + the shipped code path].
- **Reclaim** (master, session-end): drops ONLY names in this process's
  `_worker_dbs_created` memo **and** with zero `pg_stat_activity` connections
  (fail-closed on server loss — psycopg2.Error propagates to a warning, never
  to a guess; unit-tested). Workers never drop at all (run-9 crash lesson +
  worksteal gwN-id recycling). Leftovers persist → next session's sweep.
  `TEST_DB_NO_WORKER_SUFFIX` disables both hooks' DB work.
- `cleanup_stale_databases` (root, autouse, LIVE — census fact) is KEPT
  untouched: it owns the legacy `test_db_gw*`/`template_test` namespace, and
  our sweep is disjoint from it. The dead template family (948-1335) is also
  KEPT — purging it is M3-T2's pending half; t7 only guarantees the new
  lifecycle neither reuses its names nor shadows its fixture.
- `_drop_worker_database` gets **no** new guard: it is also
  `cleanup_stale_databases`' mid-session drop primitive for template_test
  (before any lifecycle bookkeeping exists) — a fail-closed guard there would
  silently disable live hygiene. Safety lives in the callers instead
  (documented in its docstring).

## 3. Per-file audit table (every touched/verified file + the command that proves it)

| file | change | proof command (post-gate; run only with the DB tier idle — see §4) |
| --- | --- | --- |
| backend/tests/conftest.py | t5: header comment (635→region); t7: sessionstart hook (~:520 post-chain; exact numbers below read from the t3+t5+t6+t7 stack), sessionfinish early reclaim call (~:565), memo routing in get_test_db_url (612/617→_memo_worker_database), lifecycle block (:786-:973, memo + `_coordination_worker_id` :805, `_base_db_prefix`, `_list_databases_by_prefix`, `_db_has_active_connections`, `_sweep_stale_worker_dbs`, `_reclaim_root_worker_dbs_at_session_end` :932, `_reclaim_worker_dbs`) | `uv run pytest backend/tests/test_db_isolation.py -n0 -p no:randomly -o addopts=""` (imports conftest; exercises memo+sweep+reclaim offline classes) then full unit tier + integration tier (§4) |
| backend/tests/test_db_isolation.py | t5: +`TestNameSafetyInvariants` (3 tests, offline); t6: amended `TestGetTestDbUrlCutover` docstring + 2 new tests + assertion fix; t7: +`TestSessionLifecycle` (6 tests, monkeypatched = offline) | `uv run pytest backend/tests/test_db_isolation.py -n0 -p no:randomly -o addopts=""` — expect the 13 shipped tests (grep -c "def test_" today) + 11 new = 24 green; the 2 DB-touching new tests are -n0/master-path-only by design |
| (read-only consumers, no edits) | `get_test_db_url` importers verified contract-compatible: root fixtures conftest.py:1670/:1819 (`isolated_db`, `test_db` — consume URL, already survive e8619d80 live since run-6), 5 benchmark files (test_memory.py:43, test_performance.py:39, test_connection_pool.py:38, test_api_benchmarks.py:32, test_slow_query_detection.py:50 — set DATABASE_URL + cache_clear only), integration tier untouched (`integration/conftest.py:903` overwrites DATABASE_URL with its own worker URL; never reads `get_test_db_url` — grep-verified) | integration tier: `uv run pytest backend/tests/integration -n0 --timeout=30` must stay 4154-class green [baseline claim from ledger, UNVERIFIED this session]; root tier proves the rest |

No production files touched; no non-test paths touched. vulture_whitelist.py
untouched (t5/t6/t7 add zero unused names — every new symbol is used or
test-referenced; vulture min-confidence 80 doesn't flag used functions
[UNVERIFIED — vulture not run per lease]).

## 4. Cutover audit — "mechanical sed across many test files" is NOT applicable

Task 6 as planned ("cutover across many test files") does not exist at HEAD:
the cutover is a **5-line function-body change already shipped in e8619d80**,
and all 9 consumer sites (fixtures ×2, benchmarks ×5, its own tests ×2) read
the URL contract-agnostically (grep census in §3). t6's audit table above IS
the per-file audit; there is nothing left to sed. If the orchestrator
expected a file-by-file sweep, that expectation is stale — M1 consumed it.

## 5. Box-lease compliance + the run-9 standing-rule reconciliation for verification

Lease honored: zero pytest/vitest/npm/validate.sh/compose/podman runs; only
file reads + stdlib python3 (AST walks, regex membership simulation). The
gate-14 run (pid /tmp/gate14.pid, log /tmp/validate-full-14.log) was never
touched.

The plan's Task 5-7 verification commands (`-n4` runs of test_db_isolation,
the two-run hygiene check, the `psql ... datname LIKE '%\_gw%'` inspection)
**directly violate the ledger's run-9 standing rule** ("NEVER run
integration-tier pytest on the shared postgres while a gate/integration tier
is live — worker-DB NAMES COLLIDE BY CONSTRUCTION"). Two t7-specific
mitigations change the risk profile and one residual remains:

1. t7's new test classes are ALL offline (monkeypatched psycopg2 boundary) —
   they add zero DB traffic, so `test_db_isolation.py` under `-n0` after the
   gate no longer touches gw-namespaces at all.
2. Under -n0 the cutover uses `security_main` (never security_test*, never a
   DROP of foreign names) — the same class of call e8619d80 shipped and the
   ledger's 13/13-green runs already exercised.
3. RESIDUAL (must respect): the shipped `TestCreateDrop` class (from
   e85c2cf3) creates+drops `fcl_probe_gw0/gw1` against the live server —
   safe off-gate (names foreign to both tiers; `_db_has_active_connections`
   skips them in OUR sweep), but a `-n auto` invocation would still violate
   the standing rule. Micro-slot for t5/t6/t7 = **`-n0` only**, census-clear
   check first:
   `podman exec <gate-postgres> psql -Atc "SELECT datname FROM pg_database
   WHERE datname LIKE 'security\_%' OR datname LIKE 'fcl\_probe%'"` — expect
   at most live-tier rows.

## 6. applyGates (sequencing for the orchestrator)

- t5, t6: independent of each other's *behavior* but t6's hunk context
  includes t5's class tail → apply t5 first (chain verified in the table
  above); either order breaks only via git-apply conflict, which `--check`
  already ruled out.
- t7 depends on t5's amended comment context (sub #5 in apply_t7.py) — chain
  enforced by `git apply --check` rc=0 only in order t5→t6→t7.
- After /tmp/t3-draft/t3.patch: verified stackable (rc=0). After
  /tmp/wave2-drafts/t4 (ci.yml only) and m3-static (docs only): zero file
  overlap, no check needed but both were diffed against my paths.
- After any M3-T2 purge commit that deletes conftest.py:948-1335 (the dead
  template family): t7's lifecycle block sits ABOVE that region (stacked
  numbering :786-:973) but t7's context hunks do not overlap
  948-1335 — re-run the chain check if T2 lands first; expect clean because
  the touched anchors (:557-:625, :694-:746, sessionfinish ~:520) are all
  outside the census deletion set. [UNVERIFIED until T2's actual patch exists]

## 7. risks (loud)

1. **Plan-vs-HEAD conflict, resolved by re-scope** (this is the headline):
   Tasks 5+6 already shipped; re-applying plan text would duplicate
   `TestGetTestDbUrlCutover` (F811) and fight e8619d80. The patches carry
   reconciliation tests instead. Ledger must record M2 §3.1 remainder = t7.
2. **Sweep-while-gate-live residual**: session-start sweep could delete a
   parallel verification run's *quiesced* root-tier DBs (names it matches with
   zero current connections) — narrower than run-9 (which hit the live
   integration gate; structurally impossible here) but nonzero: a verification
   run between items can be idle in pg_stat_activity moments. Owner ruling
   candidate: gate `pytest_sessionstart` sweep to an explicit env
   (`TEST_DB_SWEEP=1`) for CI/nightly only — one-line change, not shipped in
   this draft to keep t7 minimal.
3. **Parallel-run DBs leak until next session** (master-only reclaim): 16
   × ~full-schema DB copies ≈ several GB disk transiently after an -n run.
   DiskFull-adjacent; next sessionstart reclaims. Mitigation available: the
   3s-grace per-worker variant (drafted, rejected as re-exposing the
   late-joiner window). If disk pressure becomes the binding constraint,
   revisit with the ledger's disk-guard.
4. **t7 hook vs the plan's `worker_database` fixture name**: t7 does NOT
   provide it; if a future task greps for it per plan text, it will find the
   DEAD census fixture — the class docstring + conftest comment block are the
   breadcrumbs; M3-T2's census entry stays authoritative.
5. **pytest 9 drift**: `os.environ["PYTEST_XDIST_WORKER"]` (xdist/remote.py)
   and the sessionfinish-LIFO-before-fixture-finalizers ordering are pinned
   to installed pytest 8.4.2 / xdist 3.8.0 (.venv verified today). pytest 9
   would need the finalizer-ordering claim re-verified (file:line cited:
   runner.py:108-111 vs main.py:318-331).
6. Unverified-by-lease items, explicitly: pytest never run (all green claims
   are static: AST parse + anchors + regex simulations); integration-tier
   4154 baseline quoted from ledger [UNVERIFIED]; vulture/ruff not executed
   (E501 manually verified <100 on added lines; F811 avoided by in-place
   class amendment; F401 — no unused imports added).
