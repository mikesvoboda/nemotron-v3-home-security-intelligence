# M3 Task 2 — Dead-Fixture Purge: static census + per-fixture evidence (DRAFT ONLY)

Repo `/agents/agent-nemo2/workspace` @ tip `439cb23b` (branch `feat/context-map-2026-09-12`;
plan baseline `6c0329b7` + 2 docs-only commits — all cited line numbers re-checked against
the working tree this session; `git status` clean).
Method: stdlib-AST consumer census + grep (`/tmp/wave2-drafts/m3-static/t2_consumer_census.py`,
`t2_collision_strict.py`, `t2_helper_sharing.py`, `t2_full_fixture_census.py`,
`t2_root_family_census.py`). **Zero pytest, zero test runs** (gate-14 lease honored, pid 941436
confirmed live). No repo file touched.

Consumer rule used (stronger than audit's plain grep, because the ledger already proved plain
grep yields false positives): a consumer = a top-level test function or class-method or
fixture function that lists the name as a **parameter**, or a `request.getfixturevalue("name")`
site. Docstring mentions, local variables named the same, and Python-module imports of the
same spelling are NOT consumers.

Scope correction vs audit 5.3: audit counted "11 conftest files, 73 fixture definitions,
71 unique names"; the current tree defines **1,001 unique fixture names tree-wide** (many are
module-local), so the "~20 of 73 dead" figure is only about conftest-level fixtures; this
draft sticks to the audit-named list plus the collision twins.

---

## 1. Root `backend/tests/conftest.py` worker-DB block (`template_database` → `worker_database` family)

**Audit claim [VERIFIED there]**: `conftest.py:626-1187`, ~230 lines, zero real usages,
duplicates the live implementation in `integration/conftest.py`.

**Drift finding (line numbers moved).** In the current tree the family is:

| Symbol | deco/def | end | line in current tree |
| --- | --- | --- | --- |
| `cleanup_stale_databases` | 948–949 | 1015 | session-scoped **autouse=True** |
| `_apply_schema_to_database` (helper) | 1018 | ~1108 | only consumer: `template_database` :1200 |
| `template_database` | 1111–1112 | 1207 | requests `cleanup_stale_databases` (:1113) |
| `worker_database` | 1210–1211 | 1335 | requests `template_database` (:1211) |

i.e. audit's `626-1187` is now ~**948–1335**. The dead family spans **~390 lines**, not ~230.
**[VERIFIED this session, AST]**

**Consumer evidence [VERIFIED this session, AST]:**
- `worker_database`: **0 consumers anywhere** (test files, conftests, helpers).
- `template_database`: 1 consumer = `worker_database`'s own parameter (:1211) — closed loop.
- `_apply_schema_to_database`: 1 reference = inside `template_database` (:1200) — dies with it.
- `_get_base_database_url` (def :799), `_parse_database_url` (def :820): refs ONLY at
  :981/:1153/:1255 + :982/:1154/:1256 = `cleanup_stale_databases`, `template_database`,
  `worker_database` — **all three inside the deletion set** → die with it.
- `_drop_database_with_lock` (def :877): refs :1008 (cleanup) + :1331 (worker_database) → dies with it.
- `_check_postgres_connection` (def :352): refs :616 (**LIVE** — `get_test_db_url` path 2),
  :975, :1147, :1249 → **MUST BE KEPT**.
- Outside `backend/tests/`: only `vulture_whitelist.py:88` (`_.cleanup_stale_databases`) →
  remove that line in the same commit.
- Live worker-DB machinery is now **root-side too** (`_create_worker_database` :661 /
  `_drop_worker_database` :696 / `worker_db_name` :655, consumed by `get_test_db_url` and
  tested by `backend/tests/test_db_isolation.py:16-103`) — the ledger's R-T7-DBRACE-CUTOVER
  landed the per-worker DBs root-side, deepening the audit's "two competing systems; one is
  wired up" finding.

**⚠ CRITICAL — `cleanup_stale_databases` is autouse and live (audit missed this).**
`conftest.py:948-949`: `@pytest.fixture(scope="session", autouse=True)` — it runs every
session on the master process and drops `test_db_gw<N>` + `template_test` leftovers
(:1002 LIKE pattern). It has **zero explicit consumers only because autouse fixtures need
none**. Its target names are precisely what the LIVE machinery creates:
`worker_db_name()` → `<base>_gwN`/`<base>_main` (conftest.py:655-670) and `template_test` is
only ever created by the dead `template_database` (:1128-1130). Today it is
**stale-sweep coverage for the live `_gwN` naming**.

**Proposed per-item one-line change (root block):**
- `template_database` (1111–1207) + `worker_database` (1210–1335) +
  `_apply_schema_to_database` (1018–~1108): **delete** (closed-loop dead family).
- Helpers `_get_base_database_url`, `_parse_database_url`, `_drop_database_with_lock`:
  **delete** (consumers all inside the deleted family; re-run
  `t2_helper_sharing.py` post-delete → expect zero refs).
- `cleanup_stale_databases` (948–1015): **DECISION-NEEDED (not owner-gated; a task-level call
  the orchestrator can make)**: option A keep as-is (live stale-sweep of live `_gwN` names);
  option B delete alongside the family and fold stale-sweep into the M2 worker-DB lifecycle
  (ledger notes drop-at-end + stale-sweep was FCL Task 7's job). My evidence favors A-now
  (deleting it regresses orphan-DB cleanup with zero lines saved against B's fold-in work).
  If A: remove from `vulture_whitelist.py:88` is NOT needed; if B: remove it there too.
- Keep `_check_postgres_connection` (:352), `_ensure_clean_db` (:1342, consumed by
  `isolated_db` :1686), `_reset_db_schema` (:1357, consumed :1354/:1834).

**Verify tier:** unit-tier collection + root-tier light run (fixtures don't collect →
collection count must be unchanged; plan's "a delta means something referenced them").
LIGHT box slot.

---

## 2. Named dead fixtures (audit's list) — per-fixture evidence

| Fixture | Definition (current tree) | Consumers [VERIFIED this session] | Ledger pre-check | Verdict |
| --- | --- | --- | --- | --- |
| `authenticated_client` | `unit/api/routes/conftest.py:87-88` (end 106) — NOT root conftest as audit implied | **0** fixture consumers. `test_debug_api.py:25` imports `authenticated_async_client as authenticated_client` — a *different* fixture (`unit/conftest.py:82`) under that alias, called explicitly at :79/:102. | FALSE-POSITIVE correction confirmed | **DELETE** (dead twin of the live `create_authenticated_client()` ctx-manager, conftest:62) |
| `mock_threat_detector` | `backend/tests/conftest.py:2554-2555` (end 2576) | **0** anywhere | confirmed dead | **DELETE** |
| `mock_model_zoo` | `backend/tests/conftest.py:2579-2580` (end 2625) | **0** fixture consumers; `test_model_downloader.py:566+` uses a *local variable* `mock_model_zoo = MagicMock(...)` — not the fixture | confirmed dead | **DELETE** |
| `enrichment_scenarios` | `backend/tests/conftest.py:2628-2629` (end 2662) | **0** fixture consumers; `test_enrichment_edge_cases.py:23` imports the *module* `tools.nemo_data_designer.enrichment_scenarios` | confirmed dead | **DELETE** |
| `patch_database_dependency` | `contracts/conftest.py:96-97` (end 110) — NOT root conftest | **0** anywhere | confirmed dead | **DELETE** |
| `patch_redis_dependency` | `contracts/conftest.py:113-114` (end 127) — NOT root conftest | **0** anywhere | confirmed dead | **DELETE** |

**Proposed per-fixture one-line change:** delete each definition (decorator-through-end-line
as tabled); after all six + the root block, re-run `t2_consumer_census.py` → expect every
TARGETS row `consumers_total=0, definitions=[]`, plus a root-conftest docstring cleanup
(:10-12 documents `cleanup_stale_databases`/`template_database`/`worker_database` in the
module header — reword if option A above keeps the sweeper).

**Verify tier:** unit tier green + collection count unchanged (fixtures don't collect);
contracts tier for the two `contracts/conftest.py` deletions. LIGHT box slot (one slot can
cover T2 as a whole: unit+contracts light gates, no integration tier needed — matches the
survey agent's "Unit-only: T2" map).

---

## 3. `session` / `mock_redis` conftest collisions (plan T2 bullet 2)

### `session`
- Root twin: `conftest.py:1706-1707` (end 1739) — savepoint-rollback session over
  `get_session()`, depends on `isolated_db`.
- Integration twin: `integration/conftest.py:1237-1238` (end 1249) — alias for
  `isolated_db_session`; its docstring says it exists to **override the root twin for
  integration tests**.
- Resolution census [VERIFIED this session, strict AST + nearest-conftest resolution]:
  **216 real consumer sites resolve to the integration twin** (all under `integration/`);
  **15 resolve to the root twin — and all 15 are in one file**:
  `unit/models/test_soft_delete.py` (class `TestCameraSoftDeleteMethods` @70 carries
  `@pytest.mark.integration`, so per conftest :419-441 every one of these tests is
  permanently skipped — exactly the 15 tests ledger "M3 T3 MEASUREMENT" counts for this file:
  *"test_soft_delete.py 15 (5 class marks)"*).
  Apparent-but-false consumers [VERIFIED individually]: `pytest_sessionfinish(session, ...)`
  :520 (pytest hook arg), `factories.py:872`, `utils/async_helpers.py:314`,
  `unit/core/test_database.py:1074`, `unit/services/test_household_matcher.py:842`,
  `unit/services/test_performance_collector.py:1154/1157/1983/1986` (nested `def` params, not
  fixture injection).

**Verdict + one-line change: integration twin WINS (keep). Root twin is dead-but-coupled:**
its only consumers are the 15 permanently-skipped tests that **M3 Task 3 will move to
`integration/`** (where they re-resolve to the integration twin). Proposed: *T2 leaves root
`session` alone; T3's move deletes it in its own commit* (document: integration impl wins
because root's consumers are 100% T3-movers; deleting earlier would break nothing today —
the 15 are skipped — but leaves T3's move with no working `session`). [UNVERIFIED] whether
`isolated_db` has other consumers after T3 — its 115 in-root refs need re-census at exec time.

### `mock_redis`
- Root twin `conftest.py:1862-1863` (end 1888): **1 consumer** =
  `benchmarks/test_memory.py:116` `def get_test_client(mock_redis: AsyncMock)` — a plain
  `@contextmanager` helper parameter, called explicitly from :152 with
  `mock_redis_for_memory` (benchmarks own fixture, :99). **Not a fixture request.**
  → root `mock_redis` is **0-consumer = dead**.
- Integration twin `integration/conftest.py:1252-1253` (end 1306): **444–445** genuine
  consumer sites (all under `integration/`, incl. integration conftest's own `client` :1438)
  + ~50 module-local shadows elsewhere — those bind their own file's fixture, not either twin.

**Verdict + one-line change: integration WINS (keep); DELETE root `mock_redis` (1862–1888).**
Zero behavior change (0 resolvable consumers).

---

## 4. `backend/tests/chaos/conftest.py` — FaultInjector framework — **DECISION-NEEDED (owner-gated)**

Per task instruction: evidence drafted, disposition NOT planned here, removal NOT scheduled.
Plan T2: "Do not delete before the ruling lands." Ask-the-owner queue item (c).

Evidence [VERIFIED this session, AST census `t2_full_fixture_census.py`]:
- File = exactly **718 lines** (audit's figure holds).
- **18 fixtures**: `fault_injector` :236-244 + 17 presets
  (`yolo26_timeout` :253, `yolo26_connection_error` :270, `yolo26_server_error` :291,
  `yolo26_intermittent` :311, `redis_unavailable` :337, `redis_timeout` :368,
  `redis_intermittent` :390, `database_unavailable` :436, `database_slow` :455,
  `database_intermittent` :474, `nemotron_timeout` :490, `nemotron_unavailable` :507,
  `nemotron_malformed_response` :525, `high_latency` :552, `packet_loss` :580,
  `all_ai_services_down` :617, `cache_and_ai_down` :645).
- **External consumers: 0 for ALL 18 fixtures** (audit said 16/18 unused; ledger's stricter
  pass said 18/18 — the 17 refs to `fault_injector` are the preset fixtures' own parameters,
  i.e. self-referential within conftest.py). `yolo26_timeout`'s text hit elsewhere is the
  string `CircuitBreaker(name="yolo26_timeout")` — confirmed [VERIFIED via ledger + grep].
- **New this session — the file also ships 3 non-fixture assertion helpers**:
  `assert_degraded_response` :680, `assert_circuit_breaker_open` :695,
  `assert_circuit_breaker_closed` :707. Chaos test files import NOTHING from
  `chaos/conftest` [VERIFIED: zero `conftest` mentions in `chaos/test_*.py`] and reference
  neither the helpers nor `FaultInjector` → these are dead too. This matters to the ruling:
  T7's rewrite-to-assert direction would *naturally consume* exactly these helpers + the
  presets (audit Part 8 Q5 logic), so the ruling is "delete 718 lines" vs "wire them into
  T7's rewritten chaos tests", not "fixtures only".
- Tier fact for the orchestrator: chaos is `--ignore`d by `scripts/validate.sh` (:331/:345) —
  no gate currently runs chaos, so a chaos-side change can only be verified by a direct
  chaos-tier dispatch (LIGHT box; chaos is DB-less per its inline-mock style).

**Draft decision options for the packet (owner chooses; both need T7 coupling):**
- A (plan default): delete presets + FaultInjector now (718 lines, `git rm`-style), T7
  rewrites start from clean slate. Verify: chaos direct-run green ×1 (no fixtures consumed →
  deletion is behavior-neutral by census; collection count unchanged).
- B: keep `fault_injector` + selected presets; T7's rewritten chaos tests request them
  (each rewritten test picks the preset its docstring names). Verify: chaos direct-run green
  ×1 after rewrites.

**Verify tier (either option):** chaos-tier direct run, LIGHT box slot; collection census.

---

## 5. Sequencing notes for the orchestrator

1. T2 deletions touch: `backend/tests/conftest.py`, `backend/tests/contracts/conftest.py`,
   `backend/tests/unit/api/routes/conftest.py`, (chaos per ruling), `vulture_whitelist.py`,
   root-conftest docstring. No production files — M3 scope law satisfied.
2. Root-`session` deletion must ride T3's `test_soft_delete.py` move commit, not T2's
   (cross-task dependency this draft discovered; ledger's wave-2 chain lists T3 before T2 —
   consistent).
3. Measurement rows in the plan ("collection count unchanged", unit tier green) are the only
   boxes needed: **1 LIGHT slot for T2-minus-chaos** (+1 LIGHT for chaos half post-ruling).
   No integration tier, no HEAVY slot.
4. Every payoff claim here is static (line counts); the only [ESTIMATE]-class number —
   audit's "−~950 lines" — measures to: root block ~390 + helpers (~200 incl. the two URL
   helpers) + six fixtures (~150) + chaos 718 = **~1,460 lines if everything lands**;
   T2-minus-chaos alone ≈ **~740 lines**. BLANK until exec (durations/wall not measurable
   statically).
5. Ledger re-checks performed: the three "FALSE positives" the ledger recorded
   (`authenticated_client`, `mock_model_zoo`, `enrichment_scenarios`) — re-derived
   independently and **confirmed dead anyway** (the aliases/local-vars/imports are not fixture
   consumers), so the ledger's "All six/plus-worker-block are dead → deletable" stands.
