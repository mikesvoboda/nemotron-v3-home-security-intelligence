# WP4.4 Triage Dossier — backend/services/system_broadcaster.py

**Run context:** WP4.3 baseline. Meta: 755 keys — 115 survived, 105 killed, 535 not yet checked (null).
**Scope of this dossier:** the 115 confirmed survivors (exit_code 0) only.
**Diff extraction:** `mutmut.mutation.diff_apply.get_diff_for_mutant` (read-only, repo cwd, per-key retries
around the live run's rewrites). All 115/115 diffs captured. Raw diffs JSON: `/tmp/wp25/wp44-triage/sb_diffs.json`.
**Covering tests:** `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`.

## Covering test files

| File | Key anchors (line) |
|---|---|
| `backend/tests/unit/services/test_system_broadcaster.py` | disconnect:88 · start_broadcasting:204 · stop_broadcasting:217 · already_running:232 · gpu_stats_error:321 · camera_stats_error:338 · reset_pubsub_connection:354 · reset_no_redis:374 · reset_unsub_err:386 · reset_sub_err:406 · gpu_stats_none_result:818 · degraded_state:1776 · connect_failure:1750 · camera_deprecated:2016 · get_health_status_healthy/degraded/unhealthy:2061/2084/2107 · gasync_fast_path:2152 · gasync_slow_path:2186 · gasync_updates:2218 · stop_system_broadcaster:2248 |
| `backend/tests/unit/services/test_system_broadcaster_history.py` | five_min:126 (`58 <= len <= 60` — loose) · fifteen_min:154 (`<= 60 and > 0` only) · sixty_min:180 (same) · partial_data:205 |
| `backend/tests/unit/services/test_async_context_managers.py` | test_start_stop_aliases:584 (calls `start(interval=10.0)` — never exercises the 5.0 default) |

**Why so much survives:** the history tests assert only counts with generous tolerances; the pub/sub
reset tests assert `assert_called_once()` with no args; error-path tests assert only 3 of 5 dict keys;
`stop_broadcasting` never has a connection attached; logger text is (rightly) never asserted.

## Cluster table (counts sum to 115)

| # | Cluster | Fn | Count | Class | Example keys (≤3) |
|---|---|---|---|---|---|
| C1 | Window length `timedelta(minutes=N)` → N+1 for each range (5→6, 15→16, 60→61) — includes/excludes a snapshot that should be at the window edge; existing tests never place a snapshot at the edge | `get_performance_history` (src :205,:209,:213) | 3 | **TEST-GAP** | `get_performance_history__mutmut_8` / `_17` / `_25` |
| C2 | Sampling-interval constant mutants `3→4`, `12→13`, `3/12→None` — returns wrong point count (45/55/180) or wrong cadence; tests assert only `<=60 and >0` | `get_performance_history` (:210,:214) | 4 | **TEST-GAP** | `get_performance_history__mutmut_19` / `_27` / `_26` |
| C3 | Time-range branch condition flipped (`elif == FIFTEEN_MIN → !=`, `if sample_interval == 1 → != 1`) — FIFTEEN_MIN falls into SIXTY_MIN branch (window 15m but interval-12 over-filtered; same 60-point count), FIVE_MIN gets unsampled branch; counts match, contents differ | `get_performance_history` (:208,:224) | 2 | **TEST-GAP** | `get_performance_history__mutmut_13` / `_33` |
| C4 | `max_points = 60 → 61` in each branch — cap off-by-one, invisible unless filtered/sampled len ever exceeds 60 (tests' 5-second spacing keeps it at ≤60) | `get_performance_history` (:207,:211,:215) | 3 | **TEST-GAP** | `get_performance_history__mutmut_12` / `_21` / `_29` |
| C5 | Window filter boundary `s.timestamp >= window_start → >` — snapshot exactly at the edge dropped; window_start is `datetime.now(UTC)`-derived inside, so only a frozen clock + boundary snapshot can hit it | `get_performance_history` (:218) | 1 | **TEST-GAP** | `get_performance_history__mutmut_31` |
| C6 | Return-cap short-circuits (`… if len > max and False`, `… if len > max or True`, `filtered[-max:] → filtered[+max:]`) — behavior diverges only when len(filtered)/len(sampled) exceeds max_points, which the 5s-spaced fixtures never produce | `get_performance_history` (:226,:230) | 4 | **TEST-GAP** | `get_performance_history__mutmut_35` / `_37` / `_42` |
| C7 | `system.shutdown` payload structure: whole message → None, `"type"`/`"data"`/`"reason"`/`"reconnect"` keys case/XX-renamed, `"system.shutdown"` value case-flipped, `"reconnect": True → False` — the NEM-4987 wire contract for reconnecting clients is asserted nowhere (test_system_broadcaster_stop_broadcasting:217 has no connections attached) | `stop_broadcasting` (:1122–:1125) | 12 | **TEST-GAP** | `stop_broadcasting__mutmut_3` / `_6` / `_17` |
| C8 | `self._pubsub.unsubscribe(SYSTEM_STATUS_CHANNEL, PERFORMANCE_UPDATE_CHANNEL)` channel-args mutants (arg→None, second arg dropped) — leaves a channel subscribed after reset; test :367 only `assert_called_once()` | `_reset_pubsub_connection` (:609) | 4 | **TEST-GAP** | `_reset_pubsub_connection__mutmut_8` / `_9` / `_10` |
| C9 | `redis_client.subscribe_dedicated(SYSTEM_STATUS_CHANNEL, PERFORMANCE_UPDATE_CHANNEL)` channel-args mutants (same shapes) — listener ends up on the wrong/None channel; test :369 asserts call-once without args | `_reset_pubsub_connection` (:622–:624) | 4 | **TEST-GAP** | `_reset_pubsub_connection__mutmut_16` / `_17` / `_18` |
| C10 | Error-fallback GPU dict key renames `"temperature"/"inference_fps" → "XX…"/"UPPER"` in the `except` return (:876–:882); `test_..._get_latest_gpu_stats_error`:321 asserts only utilization/memory_used/memory_total — 2 of 5 keys unwatched (the none-result test at :818 already kills the parallel copies in the `gpu_stat is None` dict) | `_get_latest_gpu_stats` (:876) | 4 | **TEST-GAP** | `_get_latest_gpu_stats__mutmut_13` / `_15` / `_14` |
| C11 | `get_system_broadcaster_async` slow-path construction kwargs: `redis_getter=redis_getter → None` (getter never wired), kwarg deleted entirely, `start_broadcasting(interval) → start_broadcasting(None)` — slow-path test (:2186) asserts `_redis_client` and `_running`, never `_redis_getter` or the interval threaded through | `get_system_broadcaster_async` (:1325–:1334) | 3 | **TEST-GAP** | `x_get_system_broadcaster_async__mutmut_9` / `_11` / `_13` |
| C12 | `start_broadcasting(interval: float = 5.0 → 6.0)` default, and `self._broadcast_loop(interval) → _broadcast_loop(None)` — every caller passes an explicit interval so the default is unexercised; sleep(None) would kill the real loop but tests patch `_broadcast_loop` | `start_broadcasting` (:1092,:1111) | 2 | **TEST-GAP** | `start_broadcasting__mutmut_1` / `_10` |
| C13 | `start()` alias default `interval: float = 5.0 → 6.0` — test_start_stop_aliases passes 10.0 explicitly; `async with broadcaster:` path (`__aenter__ → start()`) uses the default | `start` (:1145) | 1 | **TEST-GAP** | `start__mutmut_1` |
| C14 | `status_data = await self._get_system_status() → None` in connect's initial-status send — client receives `send_json(None)` instead of system status; the only connect test (:1750) stubs `_get_system_status` to *raise*, so the happy path's payload is unasserted | `connect` (:269) | 1 | **TEST-GAP** | `connect__mutmut_3` |
| C15 | DB-health probe expression mutants: `session.execute(select(func.count()).select_from(Camera)) → execute(None)` / `select(None)…` — with AsyncMock session both still "succeed"; only a real DB would raise; test (:2061) asserts only the returned string | `_get_health_status` (:1076) | 2 | **TEST-GAP** | `_get_health_status__mutmut_1` / `_3` |
| C16 | Log message text mutants across 10 functions: `logger.<level>(msg)` message → `None` / `"XX…XX"` / case flips (e.g. `logger.info(None)` replacing `"Global system broadcaster stopped"`) | many | 37 | **EQUIVALENT** | `disconnect__mutmut_2`, `x_stop_system_broadcaster__mutmut_3`, `broadcast_status__mutmut_14` |
| C17 | History return-cap conditions that are semantically identical to the original (`if len > 60` → `or True` (slice `[-60:]` of a ≤60 list is identity), `→ >=` (when len==60 both paths return the same list), `sample_interval == 1 → == 2` (FIVE_MIN falls to else with `[::1]` = identity), `sample_interval → None` in FIVE_MIN branch (`[::None]` = full copy)`), all inside `len ≤ max_points` reachable range | `get_performance_history` (:224–:230) | 6 | **EQUIVALENT** | `get_performance_history__mutmut_36` / `_38` / `_43` |
| C18 | Dead store: `self._pubsub = None → ""` at :618 — always overwritten by the resubscribe result (:622) or by the error handler's `= None` (:632) before any read; falsy-vs-None indistinguishable here | `_reset_pubsub_connection` (:618) | 1 | **EQUIVALENT** | `_reset_pubsub_connection__mutmut_14` |
| C19 | `exc_info=True` removal on error/warning log calls (→ None / False / argument dropped) — real change (traceback no longer captured in exception logs) but pure observability; no test should assert logging internals | 6 functions (connect, broadcast_status, _get_camera_stats, _get_latest_gpu_stats, _get_health_status, _reset_pubsub_connection) | 18 | **LOW-VALUE** | `connect__mutmut_5`, `_get_camera_stats__mutmut_2`, `broadcast_status__mutmut_18` |
| C20 | `system.shutdown` payload free-text: `"reason": "Server shutting down"` case/XX variants — human-readable string with no consumer asserting it (frontend grep: no reference to `system.shutdown` payload text) | `stop_broadcasting` (:1124) | 3 | **LOW-VALUE** | `stop_broadcasting__mutmut_12` / `_13` / `_14` |

**Totals:** TEST-GAP 50 · EQUIVALENT 44 · LOW-VALUE 21 = 115.

Notes:
- C19's `logger.error(None, exc_info=True)` message→None variants are counted in C16 (they are text mutants);
  C19 is only the exc_info argument changes.
- `_get_health_status` has no production callers (deprecated), but its unit tests execute every mutant line,
  so C15 stays TEST-GAP per the "executes the line, never asserts it" rule.
- The 6 EQUIVALENT copies of the GPU none-result dict keys (not in the survivor set) prove the dict-shape
  testing approach works — the error-dict gap in C10 is purely the weak test at :321.

## Drafted tests (UNVERIFIED — not yet run red/green)

Style follows `test_system_broadcaster.py` / `test_system_broadcaster_history.py`: `@pytest.mark.asyncio`,
`AsyncMock`, string-path `patch`. TDD procedure for each: apply the cluster's mutant diff → assert must FAIL (red);
revert to original → must PASS (green).

### D1 — exact history expectations (kills C1, C2, C3, C4, C5, C6) → `backend/tests/unit/services/test_system_broadcaster_history.py`

```python
@pytest.mark.asyncio
async def test_system_broadcaster_get_performance_history_five_min_exact_points():
    """5m range with dense (1s) data: exact 5-min window, interval 1, cap 60, >= boundary.

    // UNVERIFIED - not yet run red/green
    Kills: window 5->6 min, max_points 60->61, cap short-circuit mutants
    (and False / or True / +max_points slice), >= boundary drop, via a frozen
    clock + exact expected list.
    """
    broadcaster = SystemBroadcaster()

    frozen = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen

    # 240 snapshots at 1-second spacing (4 minutes) + one boundary snapshot exactly
    # at now-5min + one out-of-window snapshot at 5.5 minutes ago.
    snapshots = [
        PerformanceUpdate(timestamp=frozen - timedelta(seconds=240 - i)) for i in range(240)
    ]
    snapshots.insert(0, PerformanceUpdate(timestamp=frozen - timedelta(minutes=5)))
    snapshots.insert(0, PerformanceUpdate(timestamp=frozen - timedelta(minutes=5, seconds=30)))
    for s in snapshots:
        broadcaster._store_performance_snapshot(s)

    with patch("backend.services.system_broadcaster.datetime", _FrozenDateTime):
        result = broadcaster.get_performance_history(TimeRange.FIVE_MIN)

    # Window = last 5 min: the 5.5-min snapshot excluded, the exactly-at-boundary
    # snapshot INCLUDED (>=). 241 qualify -> cap keeps the LAST 60.
    assert len(result) == 60
    assert result == snapshots[-60:]
    assert all(s.timestamp >= frozen - timedelta(minutes=5) for s in result)


@pytest.mark.asyncio
async def test_system_broadcaster_get_performance_history_sampled_ranges_exact_points():
    """15m samples every 3rd, 60m every 12th — assert exact timestamps, not just counts.

    // UNVERIFIED - not yet run red/green
    Kills: interval 3->4, 12->13, 3/12->None, FIFTEEN_MIN elif-flip (13),
    sample_interval != 1 flip (33), and window/return-cap mutants on the
    sampled branch.
    """
    broadcaster = SystemBroadcaster()

    frozen = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen

    # 720 snapshots at 5s spacing covering the full 60 minutes (0..719).
    snapshots = [
        PerformanceUpdate(timestamp=frozen - timedelta(seconds=(720 - i) * 5)) for i in range(720)
    ]
    for s in snapshots:
        broadcaster._store_performance_snapshot(s)

    with patch("backend.services.system_broadcaster.datetime", _FrozenDateTime):
        result_15 = broadcaster.get_performance_history(TimeRange.FIFTEEN_MIN)
        result_60 = broadcaster.get_performance_history(TimeRange.SIXTY_MIN)

    # 15m: last 180 snapshots qualify; every 3rd -> 60 points; capped at 60.
    expected_15 = snapshots[-180:][::3]
    assert len(expected_15) == 60
    assert [s.timestamp for s in result_15] == [s.timestamp for s in expected_15]

    # 60m: all 720 qualify; every 12th -> 60 points.
    expected_60 = snapshots[::12]
    assert len(expected_60) == 60
    assert [s.timestamp for s in result_60] == [s.timestamp for s in expected_60]
```

Red proof sketch (one line): on `__mutmut_19` (interval 4) the 15m result is 45 points with
shifted timestamps → timestamp-list assert fails; on `_13` (FIFTEEN_MIN branch flipped to SIXTY)
result timestamps are `snapshots[::12]`-derived → mismatch; green on original by construction.

### D2 — shutdown wire contract (kills C7) → `backend/tests/unit/services/test_system_broadcaster.py`

```python
@pytest.mark.asyncio
async def test_system_broadcaster_stop_broadcasting_sends_shutdown_notice():
    """NEM-4987: clients must receive the exact system.shutdown notice on stop.

    // UNVERIFIED - not yet run red/green
    Kills all 12 structural payload mutants (type/data/reason/reconnect keys,
    value casing, reconnect True->False, whole message -> None).
    """
    broadcaster = SystemBroadcaster()
    mock_ws = AsyncMock()
    broadcaster.connections.add(mock_ws)
    broadcaster._running = True

    await broadcaster.stop_broadcasting()

    mock_ws.send_json.assert_called_once_with(
        {
            "type": "system.shutdown",
            "data": {"reason": "Server shutting down", "reconnect": True},
        }
    )
```

### D3 — reset uses both channels explicitly (kills C8 + C9) → `backend/tests/unit/services/test_system_broadcaster.py`

```python
@pytest.mark.asyncio
async def test_system_broadcaster_reset_pubsub_subscribes_both_channels():
    """Reset must unsubscribe and re-subscribe the *documented* channel pair.

    // UNVERIFIED - not yet run red/green
    Kills channel-arg mutants: unsubscribe(_SYSTEM_STATUS_CHANNEL|PERFORMANCE_UPDATE_CHANNEL|None...)
    and subscribe_dedicated(...) arg drops/None.
    """
    from backend.services.system_broadcaster import (
        PERFORMANCE_UPDATE_CHANNEL,
        SYSTEM_STATUS_CHANNEL,
    )

    mock_redis = AsyncMock()
    new_pubsub = AsyncMock()
    mock_redis.subscribe_dedicated.return_value = new_pubsub

    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    old_pubsub = AsyncMock()
    broadcaster._pubsub = old_pubsub

    await broadcaster._reset_pubsub_connection()

    old_pubsub.unsubscribe.assert_called_once_with(SYSTEM_STATUS_CHANNEL, PERFORMANCE_UPDATE_CHANNEL)
    mock_redis.subscribe_dedicated.assert_called_once_with(
        SYSTEM_STATUS_CHANNEL, PERFORMANCE_UPDATE_CHANNEL
    )
    assert broadcaster._pubsub is new_pubsub
```

### D4 — error-fallback GPU dict full shape (kills C10) → `backend/tests/unit/services/test_system_broadcaster.py`

```python
@pytest.mark.asyncio
async def test_system_broadcaster_get_gpu_stats_error_returns_all_null_keys():
    """Error path must expose the SAME 5-key schema as the success/none-result paths.

    // UNVERIFIED - not yet run red/green
    Kills temperature/inference_fps key-rename mutants in the except-return dict.
    """
    broadcaster = SystemBroadcaster()

    with patch("backend.services.system_broadcaster.get_session", autospec=True) as mock_session:
        mock_session.side_effect = ConnectionError("Database error")

        gpu_stats = await broadcaster._get_latest_gpu_stats()

    assert set(gpu_stats.keys()) == {
        "utilization",
        "memory_used",
        "memory_total",
        "temperature",
        "inference_fps",
    }
    assert all(value is None for value in gpu_stats.values())
```

### D5 — interval + redis_getter threading (kills C11 + C12 + C13) → `backend/tests/unit/services/test_system_broadcaster.py`

```python
@pytest.mark.asyncio
async def test_get_system_broadcaster_async_slow_path_threads_interval_and_getter():
    """Slow path must wire redis_getter and pass the (default) interval into the loop.

    // UNVERIFIED - not yet run red/green
    Kills: redis_getter=redis_getter->None and kwarg-deleted (TypeError->error),
    start_broadcasting(interval)->(None), and the 5.0->6.0 default (loop called
    with 6.0 instead of 5.0).
    """
    from backend.services.system_broadcaster import get_system_broadcaster_async, reset_broadcaster_state

    reset_broadcaster_state()

    mock_redis = AsyncMock()

    async def empty_listen(pubsub):
        for _ in []:
            yield

    mock_redis.listen = empty_listen
    mock_getter = MagicMock(return_value=mock_redis)

    with patch.object(SystemBroadcaster, "_broadcast_loop", autospec=True) as loop_mock:
        broadcaster = await get_system_broadcaster_async(redis_getter=mock_getter)

    loop_mock.assert_called_once_with(broadcaster, 5.0)  # module default interval
    assert broadcaster._redis_getter is mock_getter  # getter must survive construction

    # Cleanup
    await broadcaster.stop_broadcasting()
    reset_broadcaster_state()


@pytest.mark.asyncio
async def test_system_broadcaster_start_alias_default_interval_is_five_seconds():
    """start() alias default interval must stay 5.0 (used by the async-context path).

    // UNVERIFIED - not yet run red/green
    Kills start(interval: float = 5.0 -> 6.0).
    """
    broadcaster = SystemBroadcaster()
    broadcaster.start_broadcasting = AsyncMock()

    await broadcaster.start()

    broadcaster.start_broadcasting.assert_called_once_with(5.0)
```

Note: `_get_broadcaster_lock` is module-global; `reset_broadcaster_state()` (already used by the
neighboring tests at :2152+) keeps the fixture isolation identical to `test_get_system_broadcaster_async_slow_path_initialization`.

### D6 — connect sends the real initial status (kills C14) → `backend/tests/unit/services/test_system_broadcaster.py`

```python
@pytest.mark.asyncio
async def test_system_broadcaster_connect_sends_initial_status_payload():
    """On connect the client gets the freshly gathered system_status payload.

    // UNVERIFIED - not yet run red/green
    Kills status_data = await self._get_system_status() -> None (client would
    receive send_json(None)).
    """
    broadcaster = SystemBroadcaster()
    mock_websocket = AsyncMock()

    expected = {
        "type": "system_status",
        "data": {"gpu": {}, "cameras": {}, "queue": {}, "health": "healthy"},
        "timestamp": "2026-01-01T00:00:00+00:00",
    }

    with patch.object(broadcaster, "_get_system_status", return_value=expected, autospec=True):
        await broadcaster.connect(mock_websocket)

    assert mock_websocket in broadcaster.connections
    mock_websocket.send_json.assert_called_once_with(expected)
```

### D7 (optional, low priority) — DB probe is a real COUNT over camera (kills C15) → `backend/tests/unit/services/test_system_broadcaster.py`

```python
@pytest.mark.asyncio
async def test_system_broadcaster_get_health_status_probes_database_with_count_query():
    """The deprecated health check must probe the DB with a COUNT query over cameras.

    // UNVERIFIED - not yet run red/green
    Kills session.execute(None) (AttributeError on compile) and select(None)
    (compiled SQL has no count()).
    """
    broadcaster = SystemBroadcaster()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    mock_session.execute.return_value = mock_result

    @asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.system_broadcaster.get_session", mock_get_session),
        patch.object(broadcaster, "_check_redis_health", return_value=True, autospec=True),
    ):
        health = await broadcaster._get_health_status()

    assert health == "healthy"
    (statement,), _ = mock_session.execute.call_args
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True})).lower()
    assert "count" in compiled
    assert "camera" in compiled
```

## WP4.4 disposition recommendation

- Drafts D1–D6 (7 test functions) kill 44 of the 50 TEST-GAP survivors; D7 covers the remaining 2 (C15, deprecated fn — optional).
- C16/C17/C18 (44 EQUIVALENT) and C19/C20 (21 LOW-VALUE) can go to the suppression ledger as triaged-no-action;
  C19 (exc_info removals) is the one family a future "assert logging calls" convention would mop up wholesale if the team wants.
