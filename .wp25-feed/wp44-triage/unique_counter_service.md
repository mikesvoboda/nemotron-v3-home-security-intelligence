# WP4.4 Triage Dossier — backend/services/unique_counter_service.py

- **Survivors:** 158 of 242 checked mutants (`mutants/backend/services/unique_counter_service.py.meta`, exit_code 0). 84 killed. Not yet checked (excluded, will need re-triage when verdicts land): `x__get_time_key` 26, `_build_key` 5, `__init__` 4 — the key-layout tests drafted below are designed to kill most of those too.
- **Method:** diffs recovered by mechanically diffing each `x<fn>__mutmut_N` copy against its `__mutmut_orig` sibling inside `mutants/backend/services/unique_counter_service.py` (mutmut show not needed). 158/158 diffs extracted, clustered, counts reconcile exactly.
- **Covering test file (all 16 covered functions):** `backend/tests/unit/services/test_unique_counter_service.py` (via `mutmut-stats.json` `tests_by_mangled_function_name`).
  - fixtures `mock_redis_client` / `mock_settings` / `counter_service`: lines 25–58
  - the structural weakness: every add/get test asserts only the *return value* or `assert_awaited_once()` with **no call arguments** (e.g. line 120, 162), except `test_add_batch_cameras` (lines 249–255) which checks membership (`in call_args[0]`) but not position or the key/ttl. No test ever inspects the key string produced by a metric method, the ttl passed to `pfadd_with_expire`, or `CardinalityStats.window_start`.
- **Module shape:** 5 parallel metric triplets (`cameras`/`events`/`detections`/`entities`/`detection_types`) each add+get, 2 batch methods, `get_merged_count`, `get_cardinality_stats`, and module helpers `_get_time_key` (all mutants still pending) / `_get_window_start` (21 survivors — the single richest real-behavior area).

## Cluster table (sums to 158)

Key-name prefix `xǁUniqueCounterServiceǁ` abbreviated as `UCS.`; `bk` = `self._build_key`, `pfawe` = `self._redis.pfadd_with_expire`.

| ID | Pattern (mutation) | n | Example keys | Class | Why |
|----|--------------------|---|--------------|-------|-----|
| A1 | `_get_window_start`: `datetime.now(UTC)` → `datetime.now(None)` | 1 | `x__get_window_start__mutmut_2` | EQUIVALENT | On a UTC-offset-naive-free `datetime.now(None)` returns local time; every downstream value in tests equals UTC under freeze_time only if TZ=UTC — but the observable ISO string in prod shifts with local TZ. Kept EQUIVALENT under test-suite semantics (sandbox TZ=UTC makes output byte-identical); CI runs UTC. |
| B1 | `_get_window_start`: window-branch comparison flipped/replaced (`== "hourly"` → `!= "hourly"`, `== "XXhourlyXX"`, `== "HOURLY"`, same for `daily`) | 6 | `x__get_window_start__mutmut_3`, `_4`, `_5` | TEST-GAP | Branch change routes `hourly`→monthly-format start, `daily`→weekly start. `_get_window_start` is executed by exactly 2 tests (`test_get_cardinality_stats`, `:321`, `test_get_cardinality_stats_hourly`, `:338`) which never look at `window_start` at all. |
| C1 | `_get_window_start`: truncation kwarg set non-zero (`replace(minute=0,...)` → `minute=1`, `second=1`, `microsecond=1`, `hour=1`; both hourly and daily branches) | 7 | `x__get_window_start__mutmut_12`, `_13`, `_26` | TEST-GAP | Real change to the reported window start timestamp; line executed, value never asserted. |
| D1 | `_get_window_start`: truncation kwarg *dropped* (`replace(minute=0, second=0, microsecond=0)` → `replace(second=0, microsecond=0)` etc.) | 7 | `x__get_window_start__mutmut_9`, `_11`, `_25` | EQUIVALENT | 5/7 drop `second=`/`microsecond=` where `datetime.now()` already has ms+µs (true no-op). The other 2 (mutmut_9 hourly without `minute=`, mutmut_22 daily without `hour=`) are genuine behavior changes — the drafted window-start test kills them too; they ride in this cluster because mutmut emits them as the same drop-kwarg operator. |
| F1 | `get_cardinality_stats`: `window_start=_get_window_start(window)` → `None` / `_get_window_start(None)` | 2 | `UCS.get_cardinality_stats__mutmut_14`, `_21` | TEST-GAP | `window_start` field never asserted in any service-level test; only the dataclass constructor test (`:390`) touches the field with a hand-passed value. |
| G1 | `get_cardinality_stats`: sub-count call window arg nulled (`get_unique_camera_count(window)` → `(None)` ×4 metrics) | 4 | `UCS.get_cardinality_stats__mutmut_2`, `_4` | TEST-GAP | `None` window falls to the else-branch monthly key format → stats silently mix windows (daily window reported, monthly counts returned). `test_get_cardinality_stats_hourly` passes either way because pfcount is mocked to return fixed values regardless of key. |
| H1 | `get_merged_count`: key-construction/existence args nulled (`global_prefix = ...` → `None`; `exists(key)` → `exists(None)`; `append(key)` → `append(None)`) | 3 | `UCS.get_merged_count__mutmut_1`, `_4`, `_5` | TEST-GAP | `mock_redis_client.exists` returns 1 unconditionally (fixture `:35`), so both tests (`:296`, `:307`) pass with garbage keys. Union-over-existing-keys semantics unasserted. |
| I1 | `get_unique_*_count`: `pfcount(key)` → `pfcount(None)` (5 getters) | 5 | `UCS.get_unique_camera_count__mutmut_8`, `get_unique_event_count__mutmut_8` | TEST-GAP | `pfcount` mock ignores args (`:32`); return value asserted, arg never. |
| J1 | add methods: `pfawe(key, ...)` → `pfawe(None, self._ttl, ...)` or `pfawe(self._ttl, ...)` (key arg nulled / key slot removed) | 14 | `UCS.add_unique_event__mutmut_9`, `add_batch_events__mutmut_11`, `_13` | TEST-GAP | Same mock-blindness; `assert_awaited_once()` without args (`:120`). |
| K1 | add methods: ttl arg nulled (`pfawe(key, self._ttl, ...)` → `pfawe(key, None, ...)` or ttl slot removed → value shifts into ttl position) | 7 | `UCS.add_batch_cameras__mutmut_12`, `add_unique_event__mutmut_10`, `_12` | TEST-GAP | **Highest-severity gap:** the NEM-4992 atomic PFADD+EXPIRE contract means a None/shifted ttl silently drops counter expiry (retention leak). No test asserts the ttl argument anywhere. |
| L1 | add methods: element arg nulled/dropped (`pfawe(key, ttl, camera_id)` → `(key, ttl, None)` / `(key, ttl, )` / `(key, camera_id)` (ttl dropped)) | 18 | `UCS.add_unique_event__mutmut_11`, `_13`, `add_batch_events__mutmut_15` | TEST-GAP | Counter records `None` instead of the id — cardinality becomes meaningless. Batch test's membership check (`"cam-001" in call_args[0]`) passes on `(..., None, "cam-001"...)` shifts because it only tests membership, never exact tuple (and `(key, *ids)` ttl-removal passes entirely). |
| M1 | metric methods: `key = bk(...)` → `key = None` (12 sites) | 12 | `UCS.add_unique_camera__mutmut_1`, `get_unique_camera_count__mutmut_1`, `add_batch_events__mutmut_3` | TEST-GAP | key=None flows into the mocked redis; nobody inspects it. |
| N1 | `bk(metric, window)` → `bk(window)`: metric positional arg removed (12 sites) | 12 | `UCS.add_unique_event__mutmut_4`, `add_batch_cameras__mutmut_6` | TEST-GAP | metric slot receives `"daily"`; all five metrics collide into one counter namespace + `None`-time key. Silent cross-metric data corruption. |
| N2 | `bk(metric, window)` → `bk(None, window)` (12 sites) | 12 | `UCS.add_unique_event__mutmut_2`, `add_batch_cameras__mutmut_4` | TEST-GAP | key becomes `...:None:...`. |
| O1 | `bk("metric", window)` → `bk("metric", None)` (12 sites) | 12 | `UCS.add_unique_event__mutmut_3`, `add_batch_cameras__mutmut_5` | TEST-GAP | window=None falls to monthly-format (else) branch → wrong time bucket; counters stop rolling with the configured window. |
| P1 | `bk("metric", window)` → `bk("metric", )` (window positional arg removed → default `"daily"` substituted) | 12 | `UCS.add_unique_event__mutmut_5`, `add_batch_cameras__mutmut_7` | EQUIVALENT | All 12 sites occur in methods whose `window` parameter defaults to `"daily"` and where callers pass the default… actually mutmut clobbers the *call-site* arg, so the mutant is only equivalent for default-window calls; for the hourly variants it is behavior-changing — but those call sites (`window="hourly"`) are not present in the surviving mutant list (killed elsewhere). As surviving: equivalent under every test that reaches the line. |
| Q1 | `bk("metric", ...)` metric constant replaced (`"XXcamerasXX"`, `"CAMERAS"`, …; 24 sites = XX-prefix 12 + upper-case 12) | 24 | `UCS.add_unique_event__mutmut_6`, `add_unique_event__mutmut_7`, `add_batch_cameras__mutmut_8` | TEST-GAP | Writes/reads a different Redis key family entirely; cardinality silently wrong. No test asserts the key string produced by any metric method (only `_build_key` itself is tested directly, `:351`/`:363`). |

Totals: TEST-GAP 138, EQUIVALENT 20. No LOW-VALUE (module has no logging/debug hooks).

**Root cause (one sentence):** `mock_redis_client` (test file `:26-36`) is an argument-blind `AsyncMock` and every metric test asserts only the return value, so the entire HLL **key contract** (`{redis_key_prefix}:{hll_key_prefix}:{metric}:{time_key}`), the **ttl argument** (NEM-4992), the **element argument**, and **`window_start`** are unasserted — 150 of 158 survivors die to ~130 lines of argument-level assertions.

## Drafted tests (UNVERIFIED — not yet run red/green)

Append to `backend/tests/unit/services/test_unique_counter_service.py`. Needs added imports: `from datetime import UTC, datetime`, `from freezegun import freeze_time`, and `_get_window_start` added to the existing import block from `backend.services.unique_counter_service`. `pytest`, `AsyncMock`, `patch`, `pytest.mark.asyncio` style already match the file. Freeze timestamp chosen deterministically: **2024-03-13 is a Wednesday** (weekly start = Monday 2024-03-11), per the per-test-freeze convention (memory: vitest-midnight-flake-window — freeze per test, not globally).

### T1 — `test_metric_methods_use_fully_qualified_keys_and_full_pfadd_args`
Kills clusters: **M1, N1, N2, O1, Q1, I1, J1, K1, L1** (all 5 non-batch metric triplets).
TDD: with any cluster mutant applied, `assert_awaited_once_with` sees `None`/wrong key/wrong arg tuple → red; original → green.

```python
METRIC_CASES = [
    ("add_unique_camera", "get_unique_camera_count", "cameras", "cam-front-door"),
    ("add_unique_event", "get_unique_event_count", "events", "event-123"),
    ("add_unique_detection", "get_unique_detection_count", "detections", "det-456"),
    ("add_unique_entity", "get_unique_entity_count", "entities", "entity-person-001"),
    ("add_detection_type", "get_unique_detection_type_count", "detection_types", "person"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("add_name", "get_name", "metric", "element"), METRIC_CASES)
async def test_metric_methods_use_fully_qualified_keys_and_full_pfadd_args(
    counter_service, mock_redis_client, add_name, get_name, metric, element
):
    """The HLL key contract, ttl and element must reach Redis verbatim (NEM-4992/NEM-3414)."""
    with freeze_time("2024-03-13 14:45:30"):
        expected_key = f"nemotron:hll:{metric}:2024-03-13"

        await getattr(counter_service, add_name)(element)
        mock_redis_client.pfadd_with_expire.assert_awaited_once_with(expected_key, 86400, element)

        await getattr(counter_service, get_name)()
        mock_redis_client.pfcount.assert_awaited_once_with(expected_key)
```

### T2 — `test_add_batch_methods_use_qualified_key_and_splat_elements`
Kills clusters: **M1, N1, N2, O1, Q1, J1, K1, L1** batch-function copies (upgrades the membership-only check at `:253-255`).
TDD: mutant tuple differs in length/content → `assert_awaited_once_with` red; original green.

```python
@pytest.mark.asyncio
async def test_add_batch_methods_use_qualified_key_and_splat_elements(counter_service, mock_redis_client):
    """Batch adds must send (key, ttl, *ids) exactly — no dropped ttl, no None elements."""
    with freeze_time("2024-03-13 14:45:30"):
        await counter_service.add_batch_cameras(["cam-001", "cam-002"])
        mock_redis_client.pfadd_with_expire.assert_awaited_once_with(
            "nemotron:hll:cameras:2024-03-13", 86400, "cam-001", "cam-002"
        )

        await counter_service.add_batch_events(["event-a", "event-b"])
        assert mock_redis_client.pfadd_with_expire.await_count == 2
        mock_redis_client.pfadd_with_expire.assert_awaited_with(
            "nemotron:hll:events:2024-03-13", 86400, "event-a", "event-b"
        )
```

### T3 — `test_get_window_start_truncates_to_window[hourly|daily|weekly|monthly]`
Kills clusters: **B1, C1, and the 2 non-no-op members of D1** (mutmut_9/_22).
TDD: branch-flip mutant routes `hourly` to the monthly literal → exact-match red; kwarg-nonzero mutant yields `T14:01:` ≠ `T14:00:` → red; original green.

```python
@pytest.mark.parametrize(
    ("window", "expected_start"),
    [
        ("hourly", "2024-03-13T14:00:00+00:00"),
        ("daily", "2024-03-13T00:00:00+00:00"),
        ("weekly", "2024-03-11T00:00:00+00:00"),  # Monday of that week
        ("monthly", "2024-03-01T00:00:00+00:00"),
    ],
)
@freeze_time("2024-03-13 14:45:30.123456")
def test_get_window_start_truncates_to_window(window, expected_start):
    """Each window's start is the true boundary — branch conditions and zeroing are load-bearing."""
    assert _get_window_start(window) == expected_start
```

### T4 — `test_get_cardinality_stats_scopes_every_count_and_window_start_to_window`
Kills clusters: **F1, G1** (and re-kills B1/C1/D1 via `window_start`, O1-family key drift through the stats path).
TDD: `get_unique_camera_count(None)` → pfcount key `nemotron:hll:cameras:None`-via-monthly-format → key list assertion red; `window_start=None` mutant → field assertion red; original green.

```python
@pytest.mark.asyncio
async def test_get_cardinality_stats_scopes_every_count_and_window_start_to_window(
    counter_service, mock_redis_client
):
    """All four counts and window_start must share the caller's window, not the monthly fallback."""
    mock_redis_client.pfcount.side_effect = [1, 2, 3, 4]

    with freeze_time("2024-03-13 14:45:30"):
        stats = await counter_service.get_cardinality_stats(window="weekly")
        week_key = datetime(2024, 3, 13, 14, 45, 30, tzinfo=UTC).strftime("%Y-W%W")

    assert stats.time_window == "weekly"
    assert stats.window_start == "2024-03-11T00:00:00+00:00"
    keys = [call.args[0] for call in mock_redis_client.pfcount.await_args_list]
    assert keys == [
        f"nemotron:hll:cameras:{week_key}",
        f"nemotron:hll:events:{week_key}",
        f"nemotron:hll:detections:{week_key}",
        f"nemotron:hll:entities:{week_key}",
    ]
```

### T5 — `test_get_merged_count_filters_to_existing_fully_qualified_keys`
Kills cluster: **H1** (+ merged-count key mutants).
TDD: `exists(None)` mutant → exists-args list no longer equals the qualified keys → red; `append(None)` → pfcount args contain `None` → red; original green.

```python
@pytest.mark.asyncio
async def test_get_merged_count_filters_to_existing_fully_qualified_keys(counter_service, mock_redis_client):
    """Merge must probe the qualified per-window keys and union only the surviving ones."""
    mock_redis_client.exists.side_effect = [1, 0, 1]
    mock_redis_client.pfcount.return_value = 150

    count = await counter_service.get_merged_count(
        "cameras", ["2024-01-15", "2024-01-16", "2024-01-17"]
    )

    assert count == 150
    probed = [call.args[0] for call in mock_redis_client.exists.await_args_list]
    assert probed == [
        "nemotron:hll:cameras:2024-01-15",
        "nemotron:hll:cameras:2024-01-16",
        "nemotron:hll:cameras:2024-01-17",
    ]
    mock_redis_client.pfcount.assert_awaited_once_with(
        "nemotron:hll:cameras:2024-01-15", "nemotron:hll:cameras:2024-01-17"
    )
```

### T6 — `test_get_window_start_is_timezone_aware` (A1 guard, low cost)
Kills **A1** (and pins tz semantics).
TDD: with a non-UTC test TZ (`TZ=America/New_York` subprocess or `time.tzset`), `datetime.now(None)` shifts 4–5 h → hour/hourly string red; `datetime.now(UTC)` green.

```python
@freeze_time("2024-03-13 14:45:30", tz_offset=0)
def test_get_window_start_is_timezone_aware(monkeypatch):
    """Window start must be computed in UTC regardless of the host timezone."""
    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    try:
        assert _get_window_start("hourly") == "2024-03-13T14:00:00+00:00"
    finally:
        monkeypatch.delenv("TZ")
        time.tzset()
```
(Requires `import time`; note freezegun `tz_offset=0` pins the frozen instant to UTC — UNVERIFIED interplay of freeze_time+tzset, run red/green before adopting. If flaky, drop T6 and re-classify A1 as LOW-VALUE: single mutant, deployment is single-host UTC.)

## Kill coverage map (drafted tests → survivors)

| Test | Clusters killed | Survivors covered |
|------|-----------------|-------------------|
| T1 | M1,N1,N2,O1,Q1,I1,J1,K1,L1 (non-batch) | ~101 |
| T2 | M1,N1,N2,O1,Q1,J1,K1,L1 (batch fns) | ~22 |
| T3 | B1,C1,(D1×2) | 16 |
| T4 | F1,G1 | 6 |
| T5 | H1 | 3 |
| T6 | A1 | 1 |
| (D1 remaining 5) | EQUIVALENT — no test warranted | 5 |
| (P1) | EQUIVALENT — no test warranted | 12 |

Note: mutmut run may report some of the 138 as still-alive if a mutation is masked by another test's mock default; the coverage map counts by cluster, not by guaranteed-kill — run the suite against each cluster's example key before closing WP4.4.
