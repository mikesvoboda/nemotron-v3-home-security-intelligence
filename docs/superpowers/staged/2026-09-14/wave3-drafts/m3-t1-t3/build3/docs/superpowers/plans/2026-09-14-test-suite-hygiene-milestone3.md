# Test Suite Hygiene Implementation Plan (Milestone 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-tasks-to-land-a-plan to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax to track progress.

**Goal:** execute the 2026-09-13 test-suite audit: remove phantom and duplicated coverage, collapse the per-test integration-fixture cost, close the fixture-setup timeout hole (owner-gated), make vacuous tests assert, and reclassify the suite so its structure tells the truth — measured, not estimated, at every step.

**Architecture:** the audit (`docs/development/test-suite-audit-2026-09-13.md`) is the authority for WHAT and carries the evidence tags; this plan is the argument for the order and the guardrails. Four workstreams: (A) mechanical removals that cannot change behavior (symlinks, zero-byte files, dead fixtures); (B) the fixture-cost split (`integration_db` → once-per-worker schema + slim per-test wiring, cleanup memoization, `repositories/` isolation) — the single highest-value change; (C) timeout modernization (`signal` + `func_only=false`), gated on B's setup-cost collapse AND an explicit owner ruling; (D) truth-in-tests rewrites (vacuous/circular/construct-only assertions, parametrize consolidations, spec'd mocks, taxonomy/layout).

**Spec/authority:** `docs/development/test-suite-audit-2026-09-13.md` (Parts 0–8). Its provenance tags bind this plan: act freely on **[VERIFIED]** items; re-verify before bulk action on **[REPORTED]** items; treat **[ESTIMATE]** payoff numbers as hypotheses this plan must MEASURE, not assume.

**Tech Stack:** Python 3.14/pytest/pytest-xdist/pytest-asyncio 1.3/pytest-timeout 2.4/psycopg2, SQLAlchemy async, POSIX `sh`, git.

## Sequencing (binding)

1. **M3 execution begins after M2 (Fast Confidence Loop) records green** — mirror of FCL spec §9 discipline. Exceptions: measurement inputs that ride M1/M2's mandated runs (the run-9 per-phase durations already feed Task 5), and no-repo-change prep.
2. **Task 4 gates Task 5.** `func_only=false` shares one budget across setup+call+teardown; with today's per-test engine rebuild the setup phase cannot fit any sane budget (audit Part 6 "Do 2.1 before changing the timeout").
3. **Task 10 runs after M2 Tasks 10–13 landed** (`--fast` change→test selectors exist before file trees move; selectors must be re-baselined after moves).
4. **Owner rulings required (goal-prompt stop-and-ask list):** Task 5 (pyproject timeout config — P2), Task 7 chaos direction (rewrite-to-assert vs delete), Task 10's ~102 uncategorized files (domain-owner map), and any pipeline_workers production change (P1 — M3 may only prepare the ruling packet, never patch).
5. Gate protocol transplants from M1 verbatim: ONE heavy pytest job at a time (census `ps -eo args | grep -E 'python -m pytest|uv run pytest'` before launching); `.env` ABSENT during gate runs (ledger R-T8-ENVLEAK); TEST_DATABASE_URL/TEST_REDIS_URL persisted; disk-guard + RSS + durations recorders armed.

## Global Constraints (audit Part 7, binding)

- Do NOT delete cross-file "duplicate" tests — only intra-(file, class) parametrize clusters are real.
- Do NOT act on the 1,702s sleep total; the real awaited figure is ~164s. Do NOT touch 1000s/100s cancellation stand-ins.
- Do NOT set `timeout_func_only = false` while `timeout_method = "thread"` (audit Part 6 experiment: thread method = `os._exit(1)` worker suicide; signal survives and interrupts asyncio).
- Do NOT hoist the `client` fixture scope (mock call-count bleed). `integration_db`'s (a)/(b) split preserves its semantics — nothing else gets module scope in this fixture family.
- Do NOT "fix" `backend/tests/unit/core/test_template_strings.py` (valid PEP 750 t-strings on 3.14).
- Do NOT treat the 578 mock-assert-only tests as vacuous — only the 8 confirmed circular sites.
- Do NOT bulk-auto-sort the ~102 uncategorized `integration/` files.
- Do NOT sweep all 17,909 unspecced mocks; incremental, six hot files only.
- No production runtime changes in M3 (same boundary as M2: `backend/tests/`, `scripts/`, `pyproject.toml` [Task 5, owner-gated], docs only).
- Every commit ends with the `Co-Authored-By: Claude Code <noreply@anthropic.com>` trailer; never bypass pre-commit; ledger discipline as you go.
- Measurement discipline: every payoff claim lands with a before/after number in the commit message or ledger (wall clock via `time`, per-phase via `/tmp/durations_plugin.py` + `/tmp/analyze-durations.py`).

## File Structure

| File | Fate | Responsibility |
| --- | --- | --- |
| `backend/tests/integration/test_events.py`, `test_cameras.py` | delete (symlinks) | duplicates of `*_api.py` targets (−134 executions) |
| `backend/tests/integration/test_zone_baselines.py`, `unit/test_matchers.py`, `unit/core/test_result.py`, `unit/api/routes/test_cameras_heatmap.py` | delete | zero-byte phantom coverage |
| `backend/tests/conftest.py` | edit | dead worker-DB block removal; marker-skip reconciliation; timeout-marker fix (Task 5) |
| `backend/tests/integration/conftest.py` | edit | `_ensure_worker_schema` (a) + slim `integration_db` (b); deletion-order cache; repositories isolation |
| `backend/tests/chaos/conftest.py` | edit/delete per ruling | FaultInjector framework disposition |
| `pyproject.toml` | edit (owner-gated) | `timeout_method="signal"`, `timeout_func_only=false` |
| `/tmp/durations_plugin.py` → `backend/tests/plugins/durations_plugin.py` | promote | per-phase timing recorder becomes a repo fixture for regression checks |

---

### Task 1: Zero-risk deletions (audit 1.1, 1.2)

- [ ] Census before: `uv run pytest backend/tests/integration --collect-only -q | wc -l` (+ the four affected paths' counts: expect 72/72/62/62).
- [ ] `git rm backend/tests/integration/test_events.py backend/tests/integration/test_cameras.py` (symlinks; targets `test_events_api.py`/`test_cameras_api.py` remain and keep collecting).
- [ ] Delete the four zero-byte files. Check M2 Task 1's collection-sanity gate (`scripts/check-test-collection.py`) for `--allow` entries naming them; remove those entries in the same commit so the gate tightens.
- [ ] Census after: integration collection −134 exactly; unit tier green.
- [ ] Ledger row: counts before/after. Commit: `test(hygiene): delete duplicate symlinks + zero-byte placeholders (M3 T1, audit 1.1/1.2)`.

### Task 2: Dead fixtures purge (audit 5.3)

- [ ] Per-name zero-consumer proof FIRST (`grep -rn "name" backend/tests --include='test_*.py'` + conftest-internal refs), then delete: root `backend/tests/conftest.py:626-1187` worker-DB block (`template_database`→`worker_database` family), plus `authenticated_client`, `mock_threat_detector`, `mock_model_zoo`, `enrichment_scenarios`, `patch_database_dependency`, `patch_redis_dependency`.
- [ ] Resolve `session` / `mock_redis` conftest collisions: keep the integration-consumed implementation at each level; rename or delete the dead twin (document which wins and why).
- [ ] `chaos/conftest.py`: ASK OWNER (ruling packet: 718-line FaultInjector, 16/18 fixtures unused, zero `fault_injector` consumers) — default proposal: delete presets now; Task 7's chaos rewrite starts from a clean slate. Do not delete before the ruling lands.
- [ ] Full suite green; collection count unchanged (fixtures don't collect — a delta here means something referenced them).

### Task 3: Permanently-skipped `unit/` tests (audit 1.3)

- [ ] Reconcile 27-vs-43 (root cause: class-level markers); publish the authoritative list in the ledger.
- [ ] Per file: move genuinely-DB-backed tests to `integration/`, or drop the stray `integration` decorator where the test is actually a unit test. `unit/api/routes/test_system.py` (7+ sites) first.
- [ ] Acceptance: no item under `/unit/` carries the `integration` marker after collection modifyitems; unit tier count moves by exactly the reconciled number (moved tests appear in integration collection).

### Task 4: Fixture-cost split — the big one (audit 2.1 + 2.2 + 2.3 + 2.4)

- [ ] Baseline run WITH recorder: full integration tier, `.env` absent, `-p durations_plugin` — record wall clock + setup p50/p90/p99 (this is the before-number).
- [ ] (a) New session-scoped `_ensure_worker_schema` per worker DB: advisory lock + `create_all` + `ALTER`s + indexes + dedup `DELETE`s — once per worker DB (`worker_db_url` is already session-scoped).
- [ ] (b) Slim `integration_db` to engine wiring (`close_db`/`init_db` + env), depending on (a). Do NOT hoist `client`. Preserve `integration_env`'s CI-pool-settings behavior (audit's isolation-risk note).
- [ ] Memoize `get_table_deletion_order()` per worker session; drop the redundant third cleanup pass (`_cleanup_test_cameras` alias site).
- [ ] `repositories/`: give the 201 tests the per-worker-DB isolation, then drop `xdist_group("repository_tests_serial")` + `serial` markers. Watch work-steal balance in the RSS/progress trace.
- [ ] `test_api_protection.py`: 10× `sleep(1.5)` TTL waits → polling or explicit cache invalidation (~13–14s back). Do NOT touch cancellation stand-ins.
- [ ] After-run WITH recorder (×2 green required before the repositories marker-drop ships): wall-clock target ≥15 min saved **[ESTIMATE hypothesis — report the real number even if smaller]**; setup p99 ≪ 2s; zero node-downs.
- [ ] Ledger: before/after table (wall clock, setup p50/p90/p99, per-worker load spread). Commit per sub-step (a)/(b)/memoize/repositories/sleeps — each individually revertable.

### Task 5: Timeout modernization (audit Part 6) — OWNER-GATED (P2)

- [ ] Inputs: Task 4's post-split durations + run-9 (pre-split) table + the audit's signal-vs-thread experiment. Decision rule: setup p99 ≪ 2s → keep `timeout = 5` + `@pytest.mark.slow` offenders; else `timeout = 10`. 30s is off the table.
- [ ] Owner ruling packet: exact diff (`timeout_method = "signal"`, `timeout_func_only = false`, `timeout` value), the provenance finding (scar comment entered via unrelated squashed commit 07bd5657; signal doesn't kill the process at all), rerunfailures interaction test results, blast-radius math with per-phase data attached. STOP for ruling.
- [ ] On approval: pyproject change + fix `_apply_timeout_marker` to respect CLI `--timeout` (retire `/tmp/timeout_stamp_plugin.py` protocol workaround — closes ledger R-T7-TIMEOUT-GATE debt); rerunfailures smoke check (the scar-comment concern) with `pytest-rerunfailures` active.
- [ ] Verify a synthetic setup-hang fixture now fails cleanly at budget (no node-down) — the audit's three-hang harness as a scripts/ test.
- [ ] Full gate ×2 green, zero node-downs. Commit cites the ruling.

### Task 6: media_api lifespan hang root cause (audit Open Q2)

- [ ] First: is it still red post-ENVLEAK? (run-9 result settles whether the gw6-class hang needs a root cause or was hostname-resolution wedging on the leaked `.env`.) If green: record the close-out, keep a regression note; skip to step 4.
- [ ] If red: reproduce solo (`-o addopts=""`), instrument `test_media_api.py:201` lifespan entry points (`init_redis`, `FileWatcher`, broadcasters, `get_pipeline_manager`) to find which await never returns; fix the mock seam (test-side only).
- [ ] Either way: add the audit's recommendation — a guard so lifespan-hang classes can't silently consume a worker (Task 5's signal timeout is the backstop; the fixture fix is the cure).

### Task 7: Truth-in-tests rewrites (audit 3.1–3.3, 3.5)

- [ ] Reconcile the 19-vs-30 `# Implementation would` census; ledger the number.
- [ ] Chaos suite: with Task 2's ruling, rewrite the ~30 vacuous chaos tests to assert the resilience behavior their docstrings name (caplog/behavioral assertions), or `xfail(reason=...)` where the behavior genuinely doesn't exist yet. The `test_pubsub_failures.py:61` exemplar is the template.
- [ ] Fix the 8 confirmed circular mock-calls (call the real service; mock only true I/O boundaries): `unit/services/test_pipeline_worker.py:485`, `chaos/test_timeout_cascade.py:198,226`, `chaos/test_pubsub_failures.py:325`, `integration/test_disaster_recovery.py:262`, `test_consolidated_fixtures.py:59,306`, `test_ab_rollout_production.py:510`.
- [ ] The 16 construct-the-SUT-never-call tests: add the single obvious assertion each docstring describes.
- [ ] Fix only `integration/test_database_failover.py:249` from the tautology list (verify-or-add the reconnection test it claims exists). Leave intentional reflexivity/Hypothesis `PLR0124` cases alone.

### Task 8: Parametrize consolidations (audit Part 4) — bounded scope

- [ ] Build `scripts/parametrize-guard.py` (or inline pass): extracts `pytest.raises(match=...)` text per cluster member; refuses to merge clusters with differing matches (the 41 false-identical families).
- [ ] Merge the five named clusters (96 functions → 5 tests, all pairs preserved as params): `test_alert_dedup.py:250-425`, `test_xclip_loader.py:1068-1167`, `test_system_routes.py:4308-4400`, `test_vision_extractor.py:2173-2282`, `test_mqtt_publisher.py:111-224`.
- [ ] Broader −3,092 sweep: ledger checklist artifact + tooling from step 1, executed incrementally post-M3 (explicit stretch note — do NOT let it balloon this milestone).

### Task 9: Mock spec increment (audit 3.4)

- [ ] Add `spec=`/`create_autospec` to mocks in the six hot files only: `test_system_routes.py`, `test_nemotron_analyzer.py`, `test_events_routes.py`, `test_xclip_loader.py`, `test_database.py`, `test_clip_client.py` — file-by-file commits, unit tier green per file (specs will surface lies the mocks have been telling; those become fix-forwards).
- [ ] Convention entry in `docs/development/testing.md`: new mock fixtures default to `spec=`; autospec at patch sites where the patch target is production code.

### Task 10: Taxonomy + layout (audit 5.1, 5.2, 5.4) — last, high churn

- [ ] Marker taxonomy: delete or wire `network`/`redis` (zero uses); move `chaos` registration into `pyproject.toml`; dedupe `flaky`; fix `test_admin_api.py:525` (unit+integration simultaneously).
- [ ] Regenerate the 19.8%-never-touch-DB list (audit scratch output is not in-repo — small AST pass, transitive fixture resolution) and move those files to `unit/` mirroring source packages.
- [ ] Move the 71 filename-mapable files into existing subdirs (`*_api` → `api/` etc.) with `git mv` (history-preserving); re-run M2 `--fast` selector checks after; re-baseline any path-keyed expectations (timeout markers are path-keyed — `"/integration/"` patterns must still match after moves).
- [ ] The ~102 remainder: owner category map (STOP). Execute only the approved map.
- [ ] Full gate ×2 green post-moves (collection counts identical pre/post move; only paths change).

### Task 11: M3 close-out

- [ ] Measurements record in ledger: wall clock before/after, setup p50/p90/p99 before/after, node-down count, collection delta, executed-tests delta (−134 dupes), vacuous→asserted count. Every [ESTIMATE] marked confirmed/refuted with the number.
- [ ] Final full `./scripts/validate.sh` (no flags) green + `--fast` spot-check post-layout.
- [ ] Commit + push; close matching Linear tasks via `/linear-python`; update the goal prompt doc's DoD row.

## Definition of done (M3)

Tasks 1–11 landed with their measurement rows in the ledger; timeout config changed only with an owner ruling attached; no production runtime code touched; final full gate green ×2 with zero node-downs; suite executes 134 fewer duplicated tests; `integration_db` no longer rebuilds the schema per test; `timeout_stamp_plugin` protocol workaround retired; every audit [ESTIMATE] payoff replaced by a measured number.

## Out of scope (explicit)

pipeline_workers `await asyncio.sleep(0)` production fix (P1 — owner packet only, never patch here); the full 17,909-mock spec sweep; the full −3,092 consolidation sweep (tooling + checklist land; execution is post-M3); populating the zero-byte files with new coverage (deletion is the honest move; coverage belongs to feature work).
