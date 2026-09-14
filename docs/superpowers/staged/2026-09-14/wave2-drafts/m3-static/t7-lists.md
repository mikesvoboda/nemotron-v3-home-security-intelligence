# M3 Task 7 — Truth-in-Tests Rewrites: candidate lists with file:line evidence (DRAFT ONLY)

Repo @ `439cb23b` (= plan base `6c0329b7` + 2 docs-only commits; all line numbers re-checked
against the working tree this session). Method: stdlib AST + grep only
(`t7_placeholder_vacuity.py`, `t2b_placeholder_owner_fix2.py`, `t7_circular_sites.py`,
`t7_construct_only.py`, `t7_parametrize_clusters.py`, `t7_mock_spec_census.py`).
**Zero pytest, zero runs** (gate-14 lease). Nothing modified.

Tier legend (for box batching): **U** = unit-tier run verifies · **C** = chaos-tier direct
run (chaos is `--ignore`d by validate.sh:331/345, so it needs its own LIGHT dispatch) ·
**I** = integration-tier needed · **F** = file-only, no box.

---

## 1. The `# Implementation would` / `# Should log` census — 19-vs-30 RECONCILED

**Authoritative count: 19 sites.** Exact-pattern grep over `backend/tests/` [VERIFIED this
session]: all 19 are in `chaos/`. The audit's "30 across 5 files under a looser pattern"
reproduces as follows: loosening the pattern to any `# *would log*`-class phrasing tree-wide
hits 67, so 30 was a looser sweep; the ledger's 19 (5 pool_exhaustion, 3 ftp_failures,
4 gpu_runtime, 4 pubsub, 3 timeout_cascade) is the exact-pattern truth — though the
file-by-file split differs slightly at file granularity below (pool 4 + ftp 6 + gpu 1 +
pubsub 6 + cascade 2 = 19; the ledger's per-file split doesn't sum to its own 19).

**Ownership map [VERIFIED this session, AST with trailing-comment attribution fix]:**

| # | file:line (marker) | owning test @line | test has real assert? | skip-marked? |
| --- | --- | --- | --- | --- |
| 1 | chaos/test_database_pool_exhaustion.py:183 | test_unclosed_connection_detected@170 | no | **skip(NEM-2142)** |
| 2 | :246 | test_slow_query_logs_performance_warning@239 | no | **skip(NEM-2142)** |
| 3 | :311 | test_stale_connection_recycled_on_checkout@292 | no | **skip(NEM-2142)** |
| 4 | :497 | test_deadlock_logged_with_query_context@482 | no | no |
| 5 | chaos/test_ftp_failures.py:223 | test_corrupted_jpeg_handled_gracefully@203 | yes(1) | no |
| 6 | :284 | test_disk_full_during_file_copy_logged@258 | no | no |
| 7 | :342 | test_unreadable_file_permission_denied@318 | yes(1) | no |
| 8 | :373 | test_directory_permission_denied_stops_watcher@353 | no | no |
| 9 | :412 | test_file_deleted_before_validation@388 | no | no |
| 10 | :500 | test_text_file_with_image_extension_rejected@479 | yes(1) | no |
| 11 | chaos/test_gpu_runtime_failures.py:163 | test_vram_fragmentation_degrades_performance@144 | yes(1) | no |
| 12-13 | chaos/test_pubsub_failures.py:75,78 | test_disconnect_logs_warning_and_reconnects@61 | **no — audit's VERIFIED exemplar** | no |
| 14 | :102 | test_multiple_broadcast_failures_trigger_circuit_breaker@82 | no | no |
| 15 | :122 | test_message_loss_detected_via_subscriber_count@110 | no | no |
| 16-17 | :289,290 | test_subscribe_to_invalid_channel_fails_gracefully@277 | no | no |
| 18 | chaos/test_timeout_cascade.py:64 | test_detection_timeout_creates_degraded_event@45 | no | **skip(NEM-2142)** |
| 19 | :87 | test_enrichment_timeout_uses_default_risk_score@69 | no | no |

**Vacuity context [VERIFIED this session, AST]:** chaos suite = 176 test functions;
**34 have zero assert/raises/warns** (audit said 42 zero-assert/30 vacuous/11 skip — count
drifted with the tree; current truth: 34 zero-assert, of which the `@pytest.mark.skip`
decorator count across chaos files is 34 markers in 4 files, heavy overlap with the zero-assert
set — the *executing*-vacuous number the T7 row needs must come at exec from
`t7_placeholder_vacuity.py` minus skip-marked; statically the ~30 executing-vacuous claim is
**not confirmed** (34 zero-assert − ≥11 skip-marked among them ⇒ ≤34, likely ~23-27). BLANK
measurement row.)

**[UNVERIFIED]** whether the 4 tests with a (1) real assert are *non-vacuous* for the
docstring's claimed behavior (their assert may test something adjacent). Exec-time read per
site; T7's rewrite unit = the owning test, not the marker line.

**Direction (rewrite-to-assert vs `xfail(reason=...)`) is OWNER-GATED** per plan Sequencing 4
("Task 7 chaos direction"). Draft packet framing: 4 of the 19 owners are already
`skip(NEM-2142)` — for those, xfail is the honest relabel; the other 15 are the
rewrite-to-assert candidates (caplog behavioral assertions on the logger each docstring
names; `chaos/conftest.py`'s dead `assert_degraded_response`/`assert_circuit_breaker_*`
helpers [see t2 draft §4] are the natural assertion vocabulary).
**Tier: C** per file (5 files), plus F for the census ledger row.

---

## 2. Circular mock-calls — 8 audit sites, all LOCATED; ledger's "3 vanished" claim is WRONG

Ledger "M3 T7 prep" says `test_consolidated_fixtures.py` and `test_ab_rollout_production.py`
"FILE NO LONGER EXISTS". **They exist — in `unit/`, not `integration/`; the audit cited them
bare, and the ledger searched integration-relative.** [VERIFIED: `git log --follow` shows the
unit/ paths' full history (from 7bb26cab / 91a84150); no integration/ version ever existed in
git history — `git log --all -- integration/test_consolidated_fixtures.py` = empty.]

| # | audit cite | actual file:line [VERIFIED this session] | shape | status |
| --- | --- | --- | --- | --- |
| 1 | unit/services/test_pipeline_worker.py:485 | **CONFIRMED at 485-490** `test_shutdown_cleans_up_resources`: `await mock_redis_client.disconnect()` then `disconnect.assert_called_once()`, zero asserts | call-the-mock | FIX |
| 2 | chaos/test_timeout_cascade.py:198 | **CONFIRMED 198-222** `test_api_timeout_sends_timeout_message_to_websocket`: broadcasts in a hand-rolled try/except, only mock assert at :222, zero production call | call-the-mock | FIX (C tier) |
| 3 | chaos/test_timeout_cascade.py:226 | **CONFIRMED 226-241** `test_websocket_timeout_closes_connection_gracefully` — same shape (:241) | call-the-mock | FIX (C tier) |
| 4 | chaos/test_pubsub_failures.py:325 | **CONFIRMED 325-342** `test_publish_failure_falls_back_to_direct_websocket` (:342) | call-the-mock | FIX (C tier) |
| 5 | integration/test_disaster_recovery.py:262 | **CONFIRMED 262-272** `test_cache_invalidation_pattern`: `await mock_redis.delete(key)` then `delete.assert_called_once_with(key)` | call-the-mock | FIX (I tier) |
| 6 | test_consolidated_fixtures.py:59 | **unit/test_consolidated_fixtures.py:59-67** `test_add_and_commit_flow`: add/commit on mock, asserts mock | call-the-mock | FIX (U tier) |
| 7 | test_consolidated_fixtures.py:306 | **unit/test_consolidated_fixtures.py:306-309** `test_update_baseline` | call-the-mock | FIX (U tier) |
| 8 | test_ab_rollout_production.py:510 | **unit/config/test_ab_rollout_production.py:510-524** `test_analyzer_can_use_production_manager`: `MagicMock().set_rollout_manager(manager)` then assert_called_once_with | call-the-mock | FIX (U tier) |

Nuance for #6/#7: `unit/test_consolidated_fixtures.py` is *meta-test by design* ("Tests for
the mock_db_session fixture itself") — the fix there is arguably re-scope (these assert the
fixture contract, which is legitimate for a fixture-doc file) rather than call-a-real-service;
flag in the commit, keep the audit's rewrite as default per plan row. [UNVERIFIED] intent.
Fix recipe per audit 3.2: call the real service/route; mock only true I/O boundaries.

**Tier: U×3, C×3, I×1 (+1 F re-scope decision).** Batchable: U trio with any unit-tier gate.

---

## 3. Construct-the-SUT-never-call-it — 10 enumerated sites (audit says 16; 6 unnamed)

All 10 audit-named sites re-verified [VERIFIED this session] as zero-assert/zero-raises/
zero-warns functions in the CURRENT tree (the integration/job_tracker twin at 567/749 is a
DIFFERENT, asserting test — audit's sites are the `unit/services/test_job_tracker.py` ones):

| file:line | test | one-line assertion the docstring describes |
| --- | --- | --- |
| unit/models/test_api_key_model.py:323 | test_api_key_expired_property | `assert key.is_expired is True/False` per the expired/active/permanent objects it builds (drop the "Leaving as documentation" comment) |
| unit/models/test_job_transition.py:101 | test_job_transition_auto_generates_id | `assert t.id is not None` (UUID default fires on flush — docstring itself notes defaults apply at insert; may need flush ⇒ check tier) |
| unit/models/test_job_log.py:105 | test_job_log_auto_generates_id | same pattern |
| unit/models/test_job_attempt.py:106 | test_job_attempt_auto_generates_id | same pattern |
| unit/models/test_user_model.py:385 | test_user_has_sessions_relationship | `assert "sessions" in User.__mapper__.relationships` or equivalent mapper check |
| unit/services/test_enrichment_classification_errors.py:621 | test_clothing_error_includes_detection_context | caplog assertion naming detection context |
| :660 | test_vehicle_error_includes_detection_context | same |
| :695 | test_pet_error_includes_detection_context | same |
| unit/services/test_job_tracker.py:567 | test_async_broadcast_callback_with_running_loop | assert the loop's `call_soon_threadsafe`/task was scheduled (mock the loop, assert on it) |
| :749 | test_schedule_persist_with_event_loop | assert persistence scheduled |

**Count reconciliation [UNVERIFIED]:** audit says "16 tests" but names 10; the remaining 6
were in its scratch output (not in-repo, per audit 5.1's own complaint). Exec-time: rerun the
zero-plain-assert AST scan (`t7_construct_only.py` generalized) restricted to
construct-then-comment shape. Draft list stays at 10 named + a scan step.
**Tier: U** per file (5 files) — but the four `unit/models/*` ones may need a DB-flush ⇒ could
escalate to I; verify per-file at exec; models tests currently unit-marked.

---

## 4. Tautology fix — exactly one site (audit 3.5 discipline)

`integration/test_database_failover.py:249`: `assert True  # Test demonstrates error handling
pattern` — verbatim confirmed this session; surrounding comment at :248: "Real reconnection is
tested in other tests". T7 step: **verify-or-add the reconnection test** [UNVERIFIED that one
exists — `grep -ril reconnect` over integration/ hits 9+ files but none seen as a DB
reconnection test for this seam; exec-time check: `test_database_failover.py`'s own
`test_stale_connection_replaced_on_checkout` @251 is the closest sibling]. Tier: **I**.
Leave the intentional `x == x`/Hypothesis `# noqa: PLR0124` cases alone (Global Constraint).

---

## 5. Mock-spec increment support data (audit 3.4 → plan T9 six hot files; T7-adjacent)

Current-tree counts [VERIFIED this session, AST constructor scan + regex patch-site scan]:

| file | Mock/AsyncMock ctors | unspecced | patch-sites | autospec=True |
| --- | --- | --- | --- | --- |
| unit/routes/test_system_routes.py | 332 | 330 | 131 | 0 |
| unit/services/test_nemotron_analyzer.py | 361 | 323 | 179 | 0 |
| unit/routes/test_events_routes.py | 319 | 318 | 0 | 0 |
| unit/services/test_xclip_loader.py | 272 | 265 | 6 | 0 |
| unit/core/test_database.py | 218 | 218 | 39 | 0 |
| unit/services/test_clip_client.py | 214 | 214 | 67 | 0 |

All six paths confirmed present; audit's per-file numbers hold within noise (xclip 264→265).
Note `test_events_routes.py` uses 319 inline Mock ctors with zero `patch()` — its spec work is
`spec=`/`create_autospec` at construction only. Tier: **U per-file** (T9's own rows, listed
here because T7's circular fixes at some sites convert mocks to autospec'd seams).

---

## 6. Parametrize-cluster guard inputs (audit Part 4 → plan T8; drafted here since T7/T8 share the file)

Method-count re-verification [VERIFIED this session, AST], with `pytest.raises(match=…)`
buckets proving the guard's necessity on the live tree:

| class (file:span) | methods now | audit said | raises-match buckets |
| --- | --- | --- | --- |
| unit/services/test_alert_dedup.py::TestValidateDedupKey (168-425) | **39** | 26 (measured only the same-match sub-cluster) | `'invalid characters'`×28, none×6, `'cannot be empty'`×2, `'leading or trailing whitespace'`×2, `'cannot be whitespace-only'`×1 → **only the 28 are true dupes; 4 distinct matches confirm the 41-false-identical finding** |
| unit/services/test_xclip_loader.py::TestGetActionRiskWeight (1064-1167) | 23 | 22 | no raises ⇒ safe-merge class |
| unit/routes/test_system_routes.py::TestPipelineLatencyHistoryParameterValidation (4295-4400) | 18 | 18 | no raises |
| unit/services/test_vision_extractor.py::TestYOLOFlorenceSemanticEquivalence (2162-2321) | 22 | 19 | no raises |
| unit/services/test_mqtt_publisher.py::TestTopicMapping (108-229) | 18 | 14 | no raises |

Audit's line-ranges under-cover class bodies now (dedup class starts 168, not 250; florence
ends 2321, not 2282). **Exec-time member counts must come from the parametrize-guard tool,
not this snapshot** (matches ledger T8-prep's identical conclusion). Tier: **U** per merged
cluster; guard tool itself: scripts/ + its self-tests (file + micro).

---

## 7. T7 acceptance bookkeeping for the orchestrator

- Plan T7 checkboxes mapped: census-reconcile = §1 (F); chaos rewrite/xfail = §1 (C, after
  owner direction + couples to T2 chaos ruling); 8 circular = §2 (U/C/I mix); 16→10+6
  construct-only = §3 (U); tautology = §4 (I).
- Total file touches (static estimate, BLANK until exec): 5 chaos + 1 disaster_recovery +
  2 unit-consolidated/ab_rollout + 5 construct-only files + 1 failover = **14 files**, of
  which 5 are chaos-tier-only (invisible to validate.sh — needs the chaos dispatch).
- No measurement rows can be filled from a static pass; every "vacuous→asserted count" is a
  box-slot number.
