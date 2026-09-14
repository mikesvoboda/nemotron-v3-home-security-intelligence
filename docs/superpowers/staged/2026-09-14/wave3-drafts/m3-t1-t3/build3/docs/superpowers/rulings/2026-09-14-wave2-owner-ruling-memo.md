# Owner Decision Memo — Wave-2 STOP-AND-ASK Queue (DRAFT — REQUEST FOR RULINGS)

**Date:** 2026-09-14 · **Branch:** `feat/context-map-2026-09-12`
**Tip requested by orchestrator:** `6c0329b7` · **Actual HEAD verified today:** `439cb23b` ("docs(ledger): wave-2 critic corrections + gate-14 chain state") — one docs-only commit ahead; queue contents unchanged.
**Box state:** gate-14 LIVE (pid 941436 = `sh ./scripts/validate.sh`, verified via `/tmp/gate14.pid` + `ps`). Nothing in this memo was produced by running tests; every number below is a re-read of `/tmp/dur-runs/runA2/` TSVs (stdlib, read-only) or a grep of repo files at HEAD.

> **This document requests rulings. It grants none.** No item below is applied, approved, or scheduled for apply. Ledger anchor: WAVE-2 dependency map §"ASK-THE-OWNER QUEUE (parallel, never on the box chain)" (docs/plans/2026-09-12-context-map-doc-updates.md:2109, as corrected by the critic pass at :2167-2177).

## Unblocks-at-a-glance

| # | Item | YES unlocks (wave-2 terms) | NO keeps blocked |
|---|------|---------------------------|------------------|
| a | M3-T5 timeout swap | W10 slot M3-T5 executes (packet §5 order); `/tmp` stamp-plugin workaround retired; R-T9-TIMEOUT-STAMP explicit `timeout(30)` markers retire wholesale; validate.sh `--timeout` becomes real | T5 stays owner-gated; every future session re-learns the stamp-plugin protocol from the ledger; setup-hangs keep eating workers |
| b | `init_db(create_schema=False)` seam | The *only* remaining lever on setup p90 1.161s → cheaper W4/W5 HEAVY-box measurement slots (full-tier runs x2 dominate those slots) | setup p90 floor stays at per-test `create_all`+advisory-lock cost; M3-T4 follow-up commits stall |
| c | chaos FaultInjector direction | W10 "M3-T2 dead-fixture purge" chaos half (ledger:2108 "chaos half is owner-gated") + M3-T7 chaos placeholder direction (rewrite-vs-delete) | 18 dead fixtures + 19 placeholder-site files stay in-tree; T2 executes only the non-chaos half |
| d | workers busy-loop P1 | Production patch of `pipeline_workers.py` unthrottled `continue` paths (M3 law: packet-only, never patch) | Latent prod spin-hazard stays unpatched; M3 closes with the packet only |
| e | API keys dead | Chosen auth contract: DB-backed validator, or honest deprecation of the CRUD surface | Admin UI keeps minting keys that unlock zero routes; R-T7-APIKEY-DEAD test keeps pinning the gap |
| f | risk_level column-vs-computed | Fix direction for filter/response disagreement (normalize-on-write vs filter-on-computed) | `?risk_level=` filter can silently return 0 rows for legacy/direct-SQL rows; P4 stays documented-only |
| g | ~102-file category map | W10 last step M3-T10 taxonomy/layout moves ("T10 after M2-T13 selectors exist + **owner map**", ledger:2108) | M3-T10 cannot execute at all (plan Task 10 step: "owner category map (STOP). Execute only the approved map"); ~102 files stay uncategorized |
| h | frontend logout() gap | Production frontend fix (wire cache drop / a logout caller) — currently barred by M3 scope law "tests only" | `logout()` leaves `isAuthenticated` true; shipped-gap test comments stand |
| i | Stream singleton reset guard | Approved test-prod seam guard (`reset_for_tests`-style) on the `redis_streams` singletons → standing R-T7-WS-OOM-adjacent hazard gets a structural mitigation | Cross-test singleton reuse hazard stays mitigated only by per-file mock suites |

---

## (a) M3-T5 — pyproject timeout swap (`signal` + `func_only=false`)

**Question (one sentence):** Approve the pyproject swap `timeout_method "thread"→"signal"`, `timeout_func_only true→false`, keeping `timeout = 5`, plus the conftest fix that stops the 5s stamp from overriding CLI `--timeout`?

**Evidence (re-anchored today):**
- Current config, verified at HEAD: pyproject.toml:471-473 — `timeout = 5`, `timeout_method = "thread"`, `timeout_func_only = true` with the scar comment claiming it "prevents pytest-rerunfailures server thread from being killed" (provenance is unrelated squashed commit 07bd5657, not a measurement — packet §2).
- Packet: docs/superpowers/rulings/2026-09-14-m3-t5-timeout-config-ruling-packet.md (exact diff §1, rationale §2, blast radius §3).
- Decision rule (packet §3, plan-mandated): setup p99 ≪ 2s → keep `timeout = 5` + `@pytest.mark.slow` offenders. **Re-verified today by direct stdlib pass over /tmp/dur-runs/runA2/*.tsv (n=4298 integration tests): setup p50 0.076s / p90 1.161s / p99 1.470s / max 2.408s** → rule resolves to `timeout = 5` (1.47 ≪ 2 satisfied; note the orchestrator's "p99 1.332s" figure is the stale run-9 number — the packet's own §3 table shows run-9 setup p99 1.33s; the current-baseline number is 1.470s, still ≪ 2s). Per-test total p99 3.63s, max 12.03s, 12 tests (0.28%) >5s — the @slow offender list (test_cameras_api ×6 etc., ledger:2123-2125) covers them.
- thread-method harm mechanism verified across this cycle: `os._exit(1)` kills the whole xdist worker ("node down"), e.g. R-T7-WORKERDOWN (ledger §, TestErrorHandlingWithEnrichment 8.8s legitimate run) and the run-9 gw6 setup-phase hang caught by faulthandler (packet §2).
- **NOT DONE:** the rerunfailures-active smoke (packet §2 REMAINING CHECK) has not run; ledger:2177 defers it to a post-gate-14 micro-slot (/tmp/t5 draft harness exists: /tmp/m3-draft/t5-hang-harness.sh drafted, likewise not run).

**Recommendation + tradeoff:** Approve as written (signal, func_only=false, timeout=5 + @slow list), conditioned on running the packet's §2 rerunfailures smoke green *before* apply — tradeoff: ~10 min box slot for the smoke, and ~0.5% of tests on the tail (p99 total 3.63s, max 12.03s) must carry @slow markers or start failing at the 5s cap the day func_only=false lands.

**Blocked while unanswered:** M3-T5 entirely (W10 chain); the conftest stamp fix + stamp-plugin retirement (packet §5 step 1, an "pure honesty fix" that is itself gated on this ruling by the M3 global constraint "pyproject via T5 owner ruling only", packet:5-6); R-T9-TIMEOUT-STAMP marker retirement (ledger:1505).

## (b) `init_db(create_schema=False)` production seam

**Question:** May test-fixture engine creation call a new `init_db(create_schema=False)` path (schema created once per worker DB, not per test), leaving production `init_db()` behavior unchanged?

**Evidence:** `backend/core/database.py:189` `async def init_db()` — takes NO parameters today (verified at HEAD; the `create_schema=False` form exists only as the ledger's "packet idea", ledger:1988). Schema creation is unconditional inside it: :391-410 — `pg_try_advisory_lock(_INIT_DB_LOCK_KEY)` then `ModelsBase.metadata.create_all` under the lock. Test callers that pay this per engine creation: backend/tests/conftest.py:1682, :1831; backend/tests/integration/conftest.py:1040. Measured cost: **setup p90 1.161s unchanged after Commit A**, with the ledger naming "init_db()'s own create_all + advisory lock per engine creation" as the next target (ledger:1985-1988); the 1.161s p90 was re-verified from runA2 TSVs today (item (a) evidence block). Production startup caller: backend/main.py:716 — must keep schema creation.
- Note: this is production-code surface (a new kwarg/default on a shipped function), hence STOP-AND-ASK per M3 rules even though the production default would be unchanged. [One design detail unverified: whether any caller depends on init_db's current "skip schema if lock busy" behavior — :396-398 — a patch-time check.]

**Recommendation + tradeoff:** Approve a keyword-only opt-out (`create_schema: bool = True`, tests pass False, schema instead created once in the worker-DB bootstrap) — tradeoff: one more production function signature vs removing ~1.16s p90 setup per test from every future measurement slot; risk is a fixture that forgets to create schema (mitigated by the one-time worker-DB bootstrap).

**Blocked:** all setup-cost reduction beyond T4-Commit-A; cheaper W4/W5 measurement runs; M3-T4's stated follow-up target.

## (c) chaos/conftest.py FaultInjector direction (rewrite-to-assert vs delete)

**Question:** Delete the dead FaultInjector fixture ecosystem, or invest in rewriting chaos tests to actually inject and assert?

**Evidence (re-verified today, HEAD):** `backend/tests/chaos/conftest.py` — 718 lines, `class FaultInjector` at :87, **exactly 18 `@pytest.fixture` definitions** (grep count today). Consumer census (per-test-arg scan of all 10 `chaos/test_*.py` files today): **17 fixtures have zero consumers; the 18th (`yolo26_timeout`)'s only textual hit is `CircuitBreaker(name="yolo26_timeout")` at chaos/test_gpu_runtime_failures.py:412 — a string, not a fixture request** (test signatures at :40,:66,:93,… take only mock_redis/none). Net: **18/18 dead**, matching ledger:1484-1487 ("Effectively 18/18 dead (audit said 16/18; worse)"). Related: the 19 "Implementation would"-class placeholder assertion sites are ALL in chaos/ (5 pool_exhaustion, 3 ftp, 4 gpu_runtime, 4 pubsub, 3 timeout_cascade — ledger:1479-1482); chaos is not in validate.sh, so this tier never gates anything today (ledger:2154).

**Recommendation + tradeoff:** Delete (option "delete" per the standing delete proposal, ledger:1487) — tradeoff: you lose an aspirational fault-injection harness and any future chaos-tier revival rebuilds from git history, vs removing 718 conftest lines + 19 vacuous-assertion files that create false assurance that resilience is tested. [The actual pass/fail state of the chaos files is unverified today — running them would violate the box lease.]

**Blocked:** W10's M3-T2 execution is split — the non-chaos dead-fixture purge (6+ sites, ledger:1466-1478) can go; the chaos half "is owner-gated" (ledger:2108); M3-T7 chaos direction likewise.

## (d) pipeline_workers busy-loop P1 packet (prepare-only per M3 law)

**Question:** May production throttle the unthrottled empty-stream `continue` paths in the worker loops (the spin-hazard behind the test-side OOM incident), and if so with what backoff?

**Evidence (re-verified today):** `backend/services/pipeline_workers.py:413` and `:935` — `if not messages:` → `continue` (grep -n today), exactly the R-T7-WS-OOM writeup's P1 candidates ("pipeline_workers.py:413/:935 (+audit BatchTimeout/QueueMetrics loops) — latent prod hazard beyond tests: any mock or fast-empty stream there spins the event loop", ledger:569-572). Mechanism fully documented at ledger:548-568 (run-8: gw3 worker 17.7 GB RSS, ~300 MB/s of `unittest.mock` call records; `docs/discoveries/pytest-oom-asyncmock-worker-loop.md`). The test-side fix shipped (fbb2f4ee full mock suite); the production throttle is explicitly "Owner-ruling candidates (NOT shipped)" (ledger:569). Note `block=True` on `consume_detections`/`consume_batches` means a healthy Redis blocks server-side — the spin needs a degenerate stream (mock, or fast-empty stream), which is exactly why it stayed latent.

**Recommendation + tradeoff:** Approve preparing + shipping a small patch (e.g. cap consecutive empty iterations with a short asyncio sleep/backoff) — tradeoff: tiny latency floor on an anomalous fast-empty stream vs an unbounded event-loop spin + memory blow-up whenever anything feeds it a truthy-but-empty-ish stream (already demonstrated to consume a production-mode worker in tests).

**Blocked:** any `pipeline_workers.py` production change (M3 constraint: "M3 may only prepare the ruling packet, never patch" — M3 plan :18); the P1 finding otherwise ships as documentation only.

## (e) API keys authenticating nothing (R-T7-APIKEY-DEAD)

**Question:** What is the contract for admin-UI-minted API keys — wire them into auth, deprecate the CRUD surface, or document settings-only as the contract?

**Evidence (re-verified today):** `/api/auth/api-keys` CRUD writes the `api_keys` table, but no shipped auth path reads it: `verify_api_key` exists at backend/api/routes/system.py:272, backend/api/routes/dlq.py:41, backend/api/routes/inbound_webhooks.py:121 (grep today, all three match the ledger's list); system.py:272 validates against `settings.api_keys` only; inbound_webhooks.py:121 is a dev stub accepting any key ≥16 chars; global AuthMiddleware is disabled (NEM-5527) and is settings-hashes too (ledger:654-666). The gap is *pinned by a passing test*: `test_db_created_key_does_not_authenticate` (created key → 401, ledger:663-665).

**Recommendation + tradeoff:** Option (c) document settings-only, short-term — tradeoff: leaves a misleading admin UI surface live until (a) is done, vs (a) DB-backed validator (check is_active/expiry/last_used_at) which is real auth code needing its own review/security pass on a single-user deployment whose security boundary is 127.0.0.1 binding (CLAUDE.md Key Design Decisions). Option (b) remove/deprecate is cheapest-honest.

**Blocked:** any production auth change touching api-keys; honest status of the admin API-keys page; R-T7-APIKEY-DEAD closure.

## (f) /api/events risk_level: column filter vs computed field (P4)

**Question:** Normalize the `events.risk_level` column on write, or switch the list filter to the `computed_risk_level` SQL expression, so filter and payload agree?

**Evidence (re-verified today):** filter queries the DB column — backend/api/routes/events.py:389-390 `query.where(Event.risk_level == risk_level)`; the response schema *recomputes* the field from score — backend/api/schemas/events.py:171-188 `@computed_field risk_level` via `_compute_risk_level(risk_score)` (thresholds: 0-39 low / 40-59 medium / 60-84 high / 85+ critical, ledger:679-685); the hybrid SQL expression already exists at backend/models/event.py:368/:401-411 (`computed_risk_level`). Probe proof (ledger:683-684): seeded column "high" rows with score 88 serialized as "critical" — so `?risk_level=critical` returns 0 rows for those events. The aggregate endpoint (events.py:585-594) also groups by the column, widening the inconsistency. [Whether any real legacy/direct-SQL rows currently exist in the live DB is unverified — this is a latent-inconsistency ruling, not a measured incident.]

**Recommendation + tradeoff:** Filter on `computed_risk_level` (expression exists at models/event.py:403, zero migration) — tradeoff: filter/group-by can no longer use a plain column index vs normalize-on-write which fixes the data model but needs a backfill of historical rows and a write-path guard.

**Blocked:** any production change to events filtering/write path; P4 remains "NOT touched" (ledger:686).

## (g) ~102 uncategorized integration files + pyproject markers (M3-T10)

**Question:** Provide (or approve a proposed) category map for the ~102 uncategorized `backend/tests/integration/` files so the taxonomy/layout move can execute.

**Evidence (re-verified today):** integration dir holds 175 top-level `.py` files (188 entries incl. dirs, counted today). M3 plan :18/:29/:119: Task 10's ~102 remainder needs an "owner category map (STOP). Execute only the approved map"; bulk-auto-sort is forbidden (plan :29). Ledger sequencing: "M3-T10 taxonomy LAST, after M2-T13 selectors exist + owner map" (ledger:2108) — and M2-T10/T13 selectors are recorded unlanded (scripts/fast_select.py absent, validate.sh has no --fast dispatch — ledger:2142-2144, asserted by that same-dated survey; treat as ledger-anchored rather than re-checked by this memo). **No t10 map draft exists yet**: /tmp/wave2-drafts/ currently carries only `m3-static/` (t2 census artifacts); /tmp/m3-draft/ carries only t5-hang-harness.sh + parametrize-guard.py — the "t10 map draft" the orchestrator mentions was not found on disk anywhere. pyproject already ships markers (unit/integration/e2e/gpu/slow, pyproject.toml:477-483) — a category map decides file *layout*, not marker syntax.

**Recommendation + tradeoff:** Owner either (i) rules "no re-layout — categorize in-place via markers/headers only" (cheap, skips the high-churn move), or (ii) supplies/approves a domain map (e.g. cameras/events/pipeline/…) — tradeoff: map route costs a high-churn moves commit + selector re-baseline and still waits on M2-T10-13; in-place route leaves the 175-file flat directory. Either way a *decision* is cheap now; what's expensive is guessing.

**Blocked:** M3-T10 entirely (last W10 step); the ~102 files stay uncategorized; T10's audit items 5.1/5.2/5.4.

## (h) frontend logout() shipped-gap

**Question:** Fix the shipped logout gap now (out-of-tests-scope production frontend change), or accept it as a documented limitation?

**Evidence (re-verified today):** `frontend/src/contexts/AuthContext.tsx:175-177` — `logout = useCallback(async () => { await logoutApi(); // Refetch current user after logout (will fail with 401, clearing state)`; react-query v5 keeps data through a rejecting refetch (in-hook trace proof, ledger:1690-1693), so **`isAuthenticated` stays true after logout()** until some consumer drops the cache. Caller scan today across frontend/src (components/app/pages, non-test): **zero callers wire `logout()`** — matching ledger:1699-1700 "no frontend caller wires logout() at all". The test at AuthContext.test.tsx asserts shipped guarantees + simulates the shell's cache drop; the gap is "recorded, unfixed by choice — M3 scope law = tests only" (ledger:1698-1701).

**Recommendation + tradeoff:** Ship a minimal fix — logout() itself drops the session cache (setQueryData null / clear) rather than relying on a rejecting refetch — tradeoff: touches shipped auth-adjacent frontend code (needs the usual frontend gates on a later box slot) vs a shipped button-less function that will mislead the next person who wires it up.

**Blocked:** the production fix itself (tests already pin shipped behavior); any UI work that would call logout().

## (i) DetectionStreamService/AnalysisStreamService singleton hazard (R-T7-WS-OOM-adjacent)

**Question:** Add a test-visible reset seam (e.g. `reset_for_tests()` clearing the module singletons) to redis_streams, and/or production lifetime rules, for the two module-level stream-service singletons?

**Evidence (re-verified today):** `backend/services/redis_streams.py:1172-1173` module globals `_detection_stream_service` / `_analysis_stream_service`; accessor `get_detection_stream_service` :1175-1191 caches on first call and **ignores the passed redis_client afterwards** (same pattern `get_analysis_stream_service` :1193-1205) — a test that initializes the singleton with one mock redis pins it for every later test in that worker. A `global` reset exists only via nothing: grep for `reset_for_tests` / shutdown-clearing in redis_streams.py returns zero today. This is the family behind R-T7-WS-OOM (ledger:548-568): lifespan-mocked TestClient + still-real stream services = the worker blow-up class; the per-file mock-suite fix shipped (fbb2f4ee) but the singleton lifetime itself is untouched — ledger queue item (d) calls it a "standing R-T7-WS-OOM hazard" reset-guard (ledger:2109).

**Recommendation + tradeoff:** Approve a test-only reset seam (pure addition to production module, called from conftest teardown) — tradeoff: a public function whose only caller is tests (slight API surface smell) vs structural immunity: today protection depends on every file remembering the full mock suite (the run-8 blow-up was exactly one file that forgot).

**Blocked:** the reset-guard itself; any future cleanup/close semantics on the singletons; ledger W10 queue item (d) resolution.

---

### Notes on memo scope
- **Numbering caveat:** this memo follows the orchestrator's a-i list; the ledger queue at :2109 uses its own letters (its (d)=singleton reset-guard = memo item (i); its (e)=logout = memo (h); its (f)=pipeline_workers P1 = memo (d); its (h)=unit/conftest session-scoped redis-global guard (run-4 residual) is NOT among this memo's items and remains open in the ledger). Memo (a)-(c),(e)-(g) match ledger (a)-(c),(e)-(g) by content.
- Gate-14 outcome may supersede chain-state sentences here (ledger:2177 defines post-gate states); re-read the ledger's WAVE-2 corrected section (docs/plans/2026-09-12-context-map-doc-updates.md:2082-2177) before acting.
- Every "VERIFIED today" number came from read-only file reads or stdlib parsing of pre-existing /tmp run data; no pytest/vitest/validate.sh/build was executed (box lease honored).
