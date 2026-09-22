# Test Suite Audit — Findings and Remediation Plan

**Date:** 2026-09-13
**Method:** Four parallel static-analysis passes (AST over 973–983 test files) plus direct
verification by the coordinating session. **No tests were executed** — run-8e held the shared
Postgres, and concurrent runs corrupt each other (three of our runs died this way).
**Companion doc:** `docs/discoveries/pytest-oom-asyncmock-worker-loop.md`

## How to read this

Every claim carries a provenance tag. Do not treat them as equivalent.

| Tag | Meaning |
|---|---|
| **[VERIFIED]** | Coordinating session independently re-checked the file/count. Act on it. |
| **[REPORTED]** | Single analysis pass, evidence cited but not independently re-checked. Verify before acting at scale. |
| **[ESTIMATE]** | Derived arithmetic, not measurement. Treat as order-of-magnitude. |

Scale for context: 983 test files, 33,709 test functions tree-wide; `backend/tests/integration`
is 4,303 collected / 4,215 functions / 209 files; 670,877 LOC of tests against 295,487 LOC of
backend source (**2.27:1**).

---

## Part 0 — Corrections to beliefs currently in circulation

Read this first; it prevents re-chasing dead ends.

1. **The gw6-class hang does not leak.** RSS at death was 873 MB with 55 GiB free. The
   ~300 MB/s figure belongs to the WS-mock `AsyncMock` leak already fixed in `fbb2f4ee`. This
   hang class *deadlocks without growing*. Budget-size arguments based on 300 MB/s are a
   worst-case ceiling, not the typical case. **[VERIFIED via run-8e trace as reported by worktree]**
2. **`backend/tests/unit/core/test_template_strings.py` has no syntax error.** It uses PEP 750
   t-strings, valid under the project's Python 3.14. One analysis pass flagged a "syntax error at
   line 35" using a 3.12 parser. **[VERIFIED — venv is `python3.14`]** Do not "fix" this file.
3. **Duplication is concentrated in `unit/`, not `integration/`.** 2,649 of 3,092 mergeable
   functions (85.7%) are under `backend/tests/unit`; integration holds only 248 (5.9% of that
   subset). The 2.27:1 ratio is driven by unit-test copy-paste. **[REPORTED]**
4. **Three additional `TestClient(app)` files were checked and are NOT affected** by the OOM
   class: `test_media_api.py`, `test_media_security.py`, `test_websocket_broadcast.py` — all
   patch `get_pipeline_manager`/`create_detection_worker`/`register_workers` so `_run_loop`
   never spawns. **[REPORTED]** (Note the tension with item 2 in Part 6 — `test_media_api.py:201`
   was nonetheless observed wedging in `TestClient.__enter__`. Both can be true: not the
   *leak* class, but still a lifespan *hang* class. Worth root-causing.)
5. **Two independent passes disagreed on DB-touching test count**: 2,162 (51.2%, direct fixture
   params) vs 3,386 (80.2%, transitive resolution). The transitive figure is the correct method.
   This matters — it changes the derived per-test cost from ~5.0s to **~3.3s**. **[ESTIMATE]**

---

## Part 1 — Zero-risk deletions (do these first, no judgment required)

### 1.1 Two symlinks cause 134 tests to run twice **[VERIFIED]**

```
backend/tests/integration/test_events.py  -> test_events_api.py   (72 tests)
backend/tests/integration/test_cameras.py -> test_cameras_api.py  (62 tests)
```

Confirmed against full collection: all four paths collect independently (72/72/62/62). These are
committed to git, present on host and in the worktree. **Action:** delete the two symlinks.
No coverage is lost — the targets remain.

### 1.2 Four committed zero-byte test files **[VERIFIED]**

`backend/tests/integration/test_zone_baselines.py`, `backend/tests/unit/test_matchers.py`,
`backend/tests/unit/core/test_result.py`, `backend/tests/unit/api/routes/test_cameras_heatmap.py`

They imply coverage of zone baselines, matchers, the Result type, and camera heatmaps that does
not exist. **Action:** populate or delete. If placeholders, add an explicit
`pytest.skip("not yet implemented")` so they read as TODO rather than passing.

### 1.3 Tests under `unit/` that never execute **[mechanism VERIFIED, count needs care]**

`backend/tests/conftest.py:422-425` adds `skip_integration` to any item under `/unit/` whose
keywords include `integration` — **with no check whether a database is actually available**.
Combined with explicit `@pytest.mark.integration` decorators under `unit/`, those tests are
skipped on every run, silently.

Count discipline: we confirm **27 decorator sites across 4 files** (e.g.
`backend/tests/unit/api/routes/test_system.py:547,582,620,633,931,966,998`); one pass reported
**43 affected tests**. Both can be right — a class-level marker covers every test in the class.
**Action:** resolve the count first, then either move the files to `integration/` or drop the
stray decorator. Do not bulk-edit on the unreconciled number.

---

## Part 2 — Efficiency: one change dominates everything else

### 2.1 `integration_db` is function-scoped and rebuilds the DB engine per test **[VERIFIED]**

`backend/tests/integration/conftest.py:808`. Its own docstring concedes why: *"function-scoped
because pytest-asyncio doesn't support module-scoped async fixtures well."*

Every invocation performs:
`get_settings.cache_clear()` → `close_db()` (disposes pool) → `init_db()` (**new**
`create_async_engine` + `create_all` under advisory lock) → **a second advisory-lock acquisition
with a different key** (up to 10 retries × 0.5s) → **another** `create_all` (redundant with the one
`init_db()` just did, line 883) → 2–4 `ALTER TABLE ... IF NOT EXISTS` → 2 dedup `DELETE ... ROW_NUMBER()`
window queries → 2 `CREATE UNIQUE INDEX IF NOT EXISTS`.

Every statement is already `IF NOT EXISTS`-idempotent — the idempotence was designed for
repeat-safety, not for needing to run every test.

**Reach:** 3,386 of 4,222 integration tests (80.2%) transitively depend on it **[REPORTED]**.
**Estimated saving:** 18–21 minutes off a ~24-minute wall clock **[ESTIMATE — derived, not measured]**.

**Recommended split** (preserves current semantics):
- **(a)** New session-or-module-scoped `_ensure_worker_schema`: advisory lock + `create_all` +
  `ALTER` + `CREATE INDEX`, run **once per worker database**. Per-worker DBs already exist
  (`worker_db_url`, session-scoped, `integration/conftest.py:650-682`). The dedup `DELETE`s can
  move here too — `clean_tables` TRUNCATEs between tests, so duplicates cannot reaccumulate.
- **(b)** Keep `integration_db` function-scoped, reduced to `close_db()`/`init_db()` env/engine wiring,
  depending on (a).

**Isolation risk if hoisted naively:** `integration_env` (function-scoped, `:715-805`) sets
`DATABASE_POOL_SIZE`/`DATABASE_POOL_OVERFLOW` from `os.environ.get("CI")` *before* `init_db()`.
Hoisting the whole fixture would freeze pool settings to whichever test ran first and stop
resetting the engine between tests. The (a)/(b) split above avoids this.

**Do NOT hoist `client`** (`integration/conftest.py:1342`). It rebuilds `MagicMock`/`AsyncMock`
background-service mocks per test; module/session scope would accumulate call counts across tests
and break every `assert_called_once()`. This is a genuine isolation requirement.

### 2.2 `get_table_deletion_order()` is not memoized **[REPORTED]**

`backend/tests/integration/conftest.py:164`. Every call does `engine.connect()` +
`inspector.get_table_names()` + `get_foreign_keys()` **per table** across 27 tables, then
`SET session_replication_role=replica` + 27 `TRUNCATE ... CASCADE` + reset + commit — roughly 58
round-trips per invocation. `client`-based tests trigger cleanup **3×** (`:1363` pre-test,
`:1463` in `finally`, and again via `_cleanup_test_cameras` alias at `:1334` invoked at `:969`)
≈ **174 round-trips of pure bookkeeping per test**.

**Action:** cache the deletion order once per worker session (schema is static mid-run) and drop
the redundant third pass. Fold into 2.1 — same code path.

### 2.3 `repositories/` is pinned to a single worker **[VERIFIED: exactly 201 tests]**

`backend/tests/conftest.py:438-443` applies `xdist_group("repository_tests_serial")` + `serial` to
everything under `/repositories/`, because those tests use a non-isolated `test_db` fixture
(documented in `integration/repositories/conftest.py:1-13`). `--dist=worksteal` cannot
redistribute a group, so one worker carries all 201 while others idle.

This also **contaminates our per-test averages** — idle worker-seconds were being attributed to
test execution, which is why derived per-test costs run high.

**Action:** give `repositories/` the same per-worker-DB isolation used elsewhere, then drop both
markers. Doesn't reduce total work; removes a load-imbalance floor.

### 2.4 Sleep audit — and what NOT to touch **[REPORTED]**

A naive AST sum says 703 sleep sites totalling **1,702.94s**. That number is wrong to act on.
287 sites are `sleep(1000)`-style *cancellation stand-ins* inside helper coroutines that get
cancelled (e.g. `unit/routes/test_websocket_job_logs.py:74`,
`unit/services/test_pg_notify_listener.py:299`). They never elapse.

Real figure: **393 sites, 164.38s** actually awaited in test bodies. Worst offenders:
- `integration/test_api_protection.py` — 10× `asyncio.sleep(1.5)` = 15.0s, all commented
  "intentional - cache refresh delay", waiting for a TTL to expire
  (lines 250, 337, 411, 458, 519, 552, 602, 648, 712, 771)
- `chaos/test_worker_chaos.py` — 9 sleeps of 1.5–3.0s ≈ 21.5s
- file-watcher debounce waits ≈ 7s

**Action:** convert `test_api_protection.py`'s TTL waits to polling or explicit cache
invalidation (~13–14s). **Do NOT touch the 1000s/100s sleeps** — they are correct as written.

---

## Part 3 — Accuracy: tests that cannot fail

### 3.1 625 fully vacuous tests; 611 run for real and verify nothing **[REPORTED]**

Of 2,404 zero-plain-assert tests: 1,200 use `pytest.raises` (legitimate), 1 uses `pytest.warns`,
578 assert only on mocks (legitimate *if* the mock stands for a real collaborator), and **625 are
fully vacuous**. Of those, 14 are skip/xfail; **596 execute real setup and assert nothing**.

`chaos/` is worst by concentration: 42 zero-assert, 30 vacuous, only 11 skip-marked.

**Verified example**, `backend/tests/chaos/test_pubsub_failures.py:61`
`test_disconnect_logs_warning_and_reconnects` **[VERIFIED verbatim]** — patches
`backend.core.redis.logger`, configures a mock to raise, catches its own manufactured exception
with `pass`, and ends on the comment `# Implementation would log: "Redis pub/sub connection lost,
reconnecting"`. `mock_logger` is bound and never used. **The entire chaos suite would pass
unchanged if the resilience behaviour it names were deleted from production.**

We confirm **19** occurrences of the self-admitting `# Implementation would` / `# Should log`
marker in `chaos/` **[VERIFIED]** (one pass reported 30 across 5 files under a looser pattern —
reconcile before bulk action).

**Action:** for each, add the assertion the docstring already describes, or mark
`xfail(reason=...)`. Do not leave them reporting resilience coverage that does not exist.

### 3.2 Eight circular mock assertions — test calls the mock, then asserts the mock was called **[VERIFIED: 1 of 8 verbatim]**

`backend/tests/unit/services/test_pipeline_worker.py:485` in full:

```python
async def test_shutdown_cleans_up_resources(self, mock_redis_client):
    """Test shutdown properly cleans up Redis connections."""
    # Simulate shutdown sequence
    await mock_redis_client.disconnect()
    mock_redis_client.disconnect.assert_called_once()
```

No worker shutdown method is invoked. This verifies that Python can call a mock. Others:
`chaos/test_timeout_cascade.py:198,226`, `chaos/test_pubsub_failures.py:325`,
`integration/test_disaster_recovery.py:262`, `test_consolidated_fixtures.py:59,306`,
`test_ab_rollout_production.py:510`.

**Action:** rewrite to call the real service/route, keeping mocks only at the true I/O boundary.

### 3.3 Sixteen "construct the SUT, never call it" tests **[REPORTED]**

E.g. `unit/models/test_api_key_model.py:323` builds expired/active/permanent `APIKey` objects to
test `is_expired`, then comments *"Leaving as documentation of expected behavior"* — zero
assertions. Also `test_job_transition.py:101`, `test_job_log.py:105`, `test_job_attempt.py:106`,
`test_user_model.py:385`, `test_enrichment_classification_errors.py:621,660,695`,
`test_job_tracker.py:567,749`.

**Action:** each needs the single obvious assertion its own docstring describes. Small, targeted.

### 3.4 92.9% of mocks carry no spec; `autospec=True` is used zero times **[VERIFIED]**

19,286 `Mock`/`MagicMock`/`AsyncMock`/`create_autospec` constructors; **17,909 (92.9%) pass no
`spec=`/`spec_set=`/`autospec=`** (AsyncMock 97.6% unspecced). And across **8,585 `patch()` /
`patch.object()` sites, `autospec=True` appears 0 times** — independently re-counted.

This is precisely the defect class behind the documented OOM: an unspecced `AsyncMock` is truthy
and iterates into more mocks, so `if not messages: continue` spun forever. A spec'd mock would
have raised instead of silently satisfying the branch.

**Action:** default new mock fixtures to `spec=`/`create_autospec`. Start with the heaviest and
most hazardous files: `test_system_routes.py` (330), `test_nemotron_analyzer.py` (323),
`test_events_routes.py` (318), `test_xclip_loader.py` (264), `test_database.py` (218),
`test_clip_client.py` (214). This is a large mechanical change — do it incrementally, not in one
sweep.

### 3.5 Tautological assertions are a non-issue — do not inflate this **[REPORTED]**

Only **12 exist suite-wide**. Four `x == x` checks are *intentional* reflexivity tests in
Hypothesis property suites, explicitly commented `# noqa: PLR0124`. Of 8 `assert True`, three are
self-admittedly vacuous and the rest are dead code in smoke tests that would fail on exception
anyway. **Action:** fix only `integration/test_database_failover.py:249`, which claims real
reconnection "is tested in other tests" — grep found no such test. Verify or add it. Leave the rest.

---

## Part 4 — Reducing volume without losing coverage

**3,092 of 33,709 test functions (9.2%) are mergeable via parametrize with zero loss of distinct
assertion paths** — 2,649 of them (85.7%) under `backend/tests/unit`. **[REPORTED]**

Top consolidations, each verified safe by the analysis pass:

| Target | Now | After |
|---|---|---|
| `unit/services/test_alert_dedup.py:250-425` `TestValidateDedupKey` | 26 methods, 130 lines | 1 test, ~38 lines |
| `unit/services/test_xclip_loader.py:1068-1167` `TestGetActionRiskWeight` | 22 methods, 68 lines | 1 test, ~30 lines |
| `unit/routes/test_system_routes.py:4308-4400` `TestPipelineLatencyHistoryParameterValidation` | 18 methods, 72 lines | 1 test, ~28 lines |
| `unit/services/test_vision_extractor.py:2173-2282` `TestYOLOFlorenceSemanticEquivalence` | 19 methods, 84 lines | 1 test |
| `unit/services/test_mqtt_publisher.py:111-224` `TestTopicMapping` | 14 methods, 80 lines | 1 test, ~28 lines |

Combined: 96 functions → 5; 434 lines → ~152; all 96 input/output pairs preserved as parametrize cases.

**Mandatory guard before merging any error-path cluster:** extract the `pytest.raises(match=...)`
text per member first. The analysis pass found **41 clusters that looked identical but asserted
different error messages** — i.e. genuinely different validation branches. Example:
`TestValidateDedupKey` looked like one 30-member cluster but splits into `"cannot be empty"` (1),
`"cannot be whitespace-only"` (1), `"leading or trailing whitespace"` (2), `"invalid characters"`
(26). Only the last 26 are true duplicates. Other files needing this care:
`test_alerts.py::TestValidateTimeFormat`, `test_sanitization.py`, `test_stream_config.py`,
`test_pagination.py`, `test_prompt_ab_config.py`, `ai/yolo26/tests/test_security.py`.

---

## Part 5 — Structure and classification

### 5.1 836 of 4,222 integration tests (19.8%) never touch a DB or HTTP client **[REPORTED]**

Determined by transitive fixture-dependency resolution, not parameter-name matching. By area:
top-level `integration/` 773 of 3,682 (21%); `services/` 63 of 140 (45%); `api/`, `core/`,
`database/`, `models/`, `repositories/`, `websocket/` are 0% — genuinely integration-shaped.

They inherit the 5s path-based timeout and an unconditional `integration` marker despite doing no
I/O, because `_apply_timeout_marker` (`backend/tests/conftest.py:346-369`) keys purely on
`"/integration/" in fspath_str`. **Action:** move to `backend/tests/unit/` mirroring source
packages. This is file-by-file work; the per-test list is in the analysis scratch output.

### 5.2 Marker taxonomy is nominal, not real **[REPORTED]**

Classification is 100% path-driven: `pytest_collection_modifyitems` unconditionally stamps `unit`
on everything under `/unit/` and `integration` under `/integration/`, so decorators are mostly
decorative. `network` and `redis` are declared in `pyproject.toml:482,484` and used **zero** times.
`chaos` is used 176× but registered via `addinivalue_line` in `conftest.py:304-307` rather than the
canonical list. `flaky` is registered in **both** places. One test
(`integration/test_admin_api.py:525`) carries `unit` *and* `integration` simultaneously.

**Action:** drop or wire up `network`/`redis`; move `chaos` into `pyproject.toml`; delete the
duplicate `addinivalue_line` registrations.

### 5.3 ~20 of 73 fixtures are dead, including a 718-line unused framework **[VERIFIED for chaos]**

11 conftest files, 73 fixture definitions, 71 unique names.

- **`chaos/conftest.py` — 16 of 18 fixtures unused.** The entire 718-line `FaultInjector` preset
  framework has no consumers: **`grep -rln "fault_injector" backend/tests/chaos --include=test_*.py`
  returns 0 files [VERIFIED]**. Chaos tests build mocks inline instead.
- **Dead duplicate worker-DB subsystem:** `backend/tests/conftest.py:626-1187` (`template_database`
  → `worker_database`, ~230 lines) has zero real usages and duplicates the *live* implementation in
  `integration/conftest.py:328-682`. Two competing "database per worker" systems; one is wired up.
- **Name collisions:** `session` and `mock_redis` are each defined in two conftests with materially
  different implementations. Resolution is directory-proximity-correct, but it's a discoverability trap.
- Also dead: `authenticated_client`, `mock_threat_detector`, `mock_model_zoo`,
  `enrichment_scenarios`, `patch_database_dependency`, `patch_redis_dependency`.

**Action:** delete the dead root-conftest worker-DB block. For `chaos/`, decide the direction —
either delete the 16 presets or rewrite the 10 chaos files to use `fault_injector`. Statics cannot
tell which was intended; given Part 3.1, rewriting chaos tests to actually assert is likely the
better path and would naturally consume these fixtures.

### 5.4 `integration/` is 83% flat **[REPORTED]**

173 of 209 files sit directly in `integration/` with no grouping. 71 of them (41%) map onto the
*existing* subdirectories by filename alone:

- `*_api.py` (38) → `integration/api/` · `*service*.py` (19) → `integration/services/`
- `*websocket*|*broadcast*` (6) → `integration/websocket/` · `*database*|*db_*` (4) → `integration/database/`
- `*model*` (4) → `integration/models/`

The remaining ~102 (alerts, cache, backup, auth, dlq, analytics, audit, baseline,
disaster-recovery) need new categories and **domain-owner judgment** — filenames alone are
ambiguous (`test_audit.py` vs `test_audit_api.py`). Do not auto-sort these.

---

## Part 6 — Timeout configuration (decision pending measurement)

### The hole **[VERIFIED]**

`pyproject.toml:466-468` sets `timeout = 5`, `timeout_method = "thread"`, `timeout_func_only = true`.
Per `pytest_timeout.py:189` vs `:212`, `func_only=true` installs the timer in
`pytest_runtest_call` **only** — so **a hang in fixture setup is never timed out**. Demonstrated:
a fixture blocking forever survives past 40s and must be killed externally (RC=124); with
`func_only=false` it fails in 5.16s.

This is live, not theoretical: run-8e lost gw6 with a faulthandler dump showing
`starlette/testclient.py:688 __enter__` ← `test_media_api.py:201 client` ← `pytest_fixture_setup`.

### Both flags must move together **[VERIFIED by experiment]**

Three async hangs (fixture setup / test body / fixture teardown) under `timeout=5`, host venv
(pytest-timeout 2.4.0, pytest-asyncio 1.3.0, Python 3.14):

| Method | Result |
|---|---|
| `signal` + `func_only=false` | All three caught, 15.29s, per-test reporting, **process survives**. SIGALRM interrupts `selectors.py:452 _selector.poll()` inside the live event loop. |
| `thread` + `func_only=false` | First timeout → faulthandler dump → **`os._exit(1)`**; no summary, remaining tests never run. |

So: `thread` causes the "node down: Not properly terminated" worker deaths, and **`signal` handles
asyncio fine** — the concern that SIGALRM cannot interrupt an event loop does not reproduce.
**Never set `func_only=false` while `timeout_method="thread"`.**

### Provenance of the current setting **[VERIFIED]**

The comment on `pyproject.toml:468` justifies `func_only=true` as preventing a
pytest-rerunfailures thread from being killed. Git history: the line entered via **07bd5657,
"feat: Enhanced Threat UI Treatment (NEM-5025 Phase 6) (#5851)"** — a squashed MQTT/zone-events
feature commit whose body never mentions timeouts, rerunfailures, or worker deaths. The rationale
may be sound but is **not evidenced by the commit that introduced it**. Note also that `signal`
does not kill the process at all, which addresses that concern more directly than `func_only=true` did.

### Recommended sequencing

**Do 2.1 (fixture scope) before changing the timeout.** `func_only=false` puts setup+call+teardown
under one shared budget. Interim call-phase data from run-8e (n=2,496, contention-inclusive):
p50 1.34s, p90 3.37s, p95 3.52s, **p99 3.91s**, max 49.5s, >5s = 31 (~1.2%). A p99 of 3.91s leaves
only ~1.1s for setup+teardown — and the per-test engine rebuild in 2.1 will not fit in 1.1s. Fix
the fixture first; setup cost collapses; then 5s shared is comfortable rather than marginal.

**Still needed:** true per-phase durations (`--durations=0 --durations-min=0`). Decision rule —
if setup p99 ≪ 2s, keep `timeout = 5` and mark the few offenders `@pytest.mark.slow` (already 30s);
otherwise raise the shared budget to ~10s. Do not go to 30s.

---

## Part 7 — Do NOT do these

1. **Do not delete cross-file "duplicate" tests.** 2,308 cross-file clusters are dominated by
   tests hitting *different targets* that share shape. Only intra-(file, class) clusters are real.
2. **Do not act on the 1,702s sleep total.** The real figure is 164s; 287 sites are
   cancellation stand-ins that never elapse.
3. **Do not set `timeout_func_only = false` without also setting `timeout_method = "signal"`.**
4. **Do not hoist the `client` fixture** to module/session scope — mock call counts would bleed.
5. **Do not "fix" `test_template_strings.py`.** It is valid Python 3.14.
6. **Do not treat the 578 mock-assert-only tests as vacuous.** Most assert on mocks invoked
   through real production calls. Only 8 are confirmed circular.
7. **Do not bulk-auto-sort the ~102 uncategorized `integration/` files.** Needs domain judgment.
8. **Do not sweep all 17,909 unspecced mocks at once.** Incremental, starting with the 6 hot files.

---

## Part 8 — Open questions

1. **Per-phase durations** — the blocking input for Part 6. Worktree agent has the recorder built.
2. **`test_media_api.py:201`** — observed wedging in `TestClient.__enter__` yet reported as
   correctly neutering worker startup. Root-cause rather than marking it slow.
3. **The 27-vs-43 count** for permanently-skipped `unit/` tests (Part 1.3).
4. **19-vs-30 count** for the `# Implementation would` marker in `chaos/` (Part 3.1).
5. **`chaos/` direction** — delete 16 dead fixtures, or rewrite the tests to use them? Given
   Part 3.1, the suite needs real assertions either way.
6. **Production hazard still open** (not a test issue): `pipeline_workers.py:413-414` and
   `:935-936` both `continue` with no `await asyncio.sleep(0)`. Bounded in production by
   `DEFAULT_BLOCK_MS = 5000`, so not urgent — but it is what made the mocked path unbounded.

---

## Suggested order of work

| # | Item | Risk | Payoff |
|---|---|---|---|
| 1 | Delete 2 symlinks (1.1) | none | −134 duplicate executions |
| 2 | Zero-byte files (1.2) | none | removes phantom coverage |
| 3 | Dead fixtures + dead worker-DB block (5.3) | low | −~950 lines |
| 4 | **`integration_db` split (2.1) + cleanup caching (2.2)** | medium | **est. 18–21 min/run** |
| 5 | Timeout config, after 4 (Part 6) | medium | closes the hang hole |
| 6 | Circular + vacuous tests (3.1–3.3) | low | real coverage where none exists |
| 7 | `repositories/` isolation (2.3) | medium | removes worker-imbalance floor |
| 8 | Parametrize consolidations (Part 4) | low | −3,092 functions |
| 9 | Reclassification + layout (5.1, 5.4) | high churn | correct taxonomy |

Items 1–3 are mechanical. Item 4 is the single highest-value change and gates item 5.
Item 9 is the largest and should come last.
