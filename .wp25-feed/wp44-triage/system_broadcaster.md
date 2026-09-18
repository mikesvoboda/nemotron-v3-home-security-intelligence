# WP4.4 Triage Dossier — backend/services/system_broadcaster.py

**Survivors: 324** (of 755 mutants; 431 killed, 0 unchecked) — module kill-rate 57.1%.
Evidence extracted from `mutants/backend/services/system_broadcaster.py.meta` + per-mutant
function bodies in the mutant copy (manual region diff vs `__mutmut_orig`); the 25 mutants the
line-diff could not localize (closure-region / multi-line-arg mutations) were confirmed with
read-only `uv run mutmut show <key>` (all rc=0). Full raw per-key diff:
`/tmp/wp25/wp44-triage/system_broadcaster_diffs.txt` + `/tmp/wp25/wp44-triage/nodiff_mutmut.txt`;
key lists per cluster: `/tmp/wp25/wp44-triage/cluster_keys.json`.

**Covering test files** (from `mutants/mutmut-stats.json` `tests_by_mangled_function_name`):

| File | Covers |
|---|---|
| `backend/tests/unit/services/test_system_broadcaster.py` (2300 ln) | everything except history: connect/disconnect, broadcast_*, pubsub start/stop/reset, listener, recovery, status, AI health, singleton fns (lines cited inline below) |
| `backend/tests/unit/services/test_system_broadcaster_history.py` (276 ln) | `get_performance_history` (existing range tests L116-223: 5m test has a 59-60 tolerance + boundary pad, 15m/60m tests assert only `<= 60` and `> 0` — far too weak for sampling params) |
| `backend/tests/unit/services/test_async_context_managers.py` | `start`/`__aenter__` alias |

Cluster classification totals: **TEST-GAP 94 (29.0%)**, EQUIVALENT 190 (58.6%), LOW-VALUE 38 (11.7%). 35 clusters; counts sum to 324 exactly.

## Cluster table

Cluster keys are suffixes of `backend.services.system_broadcaster.` (`xǁSystemBroadcasterǁ` = class method).

| # | Cluster | N | Class | Diff pattern | Examples (<=3) |
|---|---|---:|---|---|---|
| 1 | **C2** logger message text | 110 | EQUIVALENT | `logger.X("msg")` → `logger.X(None)` / `"XXmsgXX"` / lower / UPPER; multi-line f-string log arg → `None` | `_listen_for_updates__mutmut_12`, `_attempt_listener_recovery__mutmut_49`, `x_stop_system_broadcaster__mutmut_4` |
| 2 | **C1** logger `exc_info` kwarg | 48 | EQUIVALENT | `exc_info=True` → `None`/`False`/removed, message identical | `_broadcast_loop__mutmut_6`, `_broadcast_loop__mutmut_8`, `_broadcast_loop__mutmut_9` |
| 3 | **SS1** system-status dict *key text* | 19 | EQUIVALENT | `"gpu"`-dict keys → `"XXmemory_usedXX"`/`"MEMORY_USED"`, `"timestamp"` key casing | `_get_system_status__mutmut_16`, `_get_system_status__mutmut_78`, `_get_system_status__mutmut_106` |
| 4 | **PS1** pub/sub channel args | 16 | TEST-GAP | `subscribe_dedicated(SYSTEM_STATUS, PERFORMANCE)` and `unsubscribe(...)` → first arg `None`, second `None`, only 2nd channel, only 1st channel (`system_status`/`performance_update` → `None`/dropped in 3 lifecycle fns) | `_reset_pubsub_connection__mutmut_10`, `_start_pubsub_listener__mutmut_12`, `_stop_pubsub_listener__mutmut_5` |
| 5 | **SD1** shutdown payload | 15 | TEST-GAP | `stop_broadcasting` NEM-4987 notice: `"XXtypeXX"`/`"TYPE"`, `"XXsystem.shutdownXX"`, `"XXreasonXX"`, `"XXreconnectXX"`, whole dict → `None`, **`"reconnect": True → False`**; test L217-228 never attaches a connection | `stop_broadcasting__mutmut_4`, `stop_broadcasting__mutmut_17`, `stop_broadcasting__mutmut_3` |
| 6 | **CB** circuit-breaker config kwargs | 14 | LOW-VALUE | `__init__` breaker kwargs `recovery_timeout 30→31/None`, `half_open_max_calls 1→2/None`, `success_threshold 1→2/None`, `name` text, kwargs *dropped* (22/23/25) | `__init____mutmut_18`, `__init____mutmut_22`, `__init____mutmut_27` |
| 7 | **H2** recovery backoff math | 12 | LOW-VALUE | `base_delay 1→2`, `max_delay 60→61`, `2**(n-1)` → `/2**`, `2*`, `3**`, `2**(n±1)`, jitter `delay/x`, `uniform(1.1,0.3)`, `delay−jitter` (all timing, tests stub `asyncio.sleep`) | `_attempt_listener_recovery__mutmut_21`, `_attempt_listener_recovery__mutmut_29`, `_attempt_listener_recovery__mutmut_43` |
| 8 | **G5a** history truncation short-circuit | 4 | EQUIVALENT | `if len>max` → `and False` / slice `[+max_points:]` (empty slice) + falsy-empty fallback `return filtered` == original when `len<=max`; tests only ever hit `len<=max` | `get_performance_history__mutmut_35`, `get_performance_history__mutmut_37`, `get_performance_history__mutmut_40` |
| 9 | **G5b** history truncation boundary | 4 | TEST-GAP | `or True` (always `[-60:]`), `>= max_points`, on both branches — observable **only when len(sampled) > 60**, which no test constructs (max window count = 60) | `get_performance_history__mutmut_36`, `get_performance_history__mutmut_38`, `get_performance_history__mutmut_41` |
| 10 | **SQL2** camera-stats SQL | 8 | TEST-GAP | `select(func.count())`→`select(None)`/`None` stmt, execute(None), `where(None)`, **`Camera.status == ONLINE.value` → `!=`** — mocked session never inspects compiled SQL | `_get_camera_stats_with_session__mutmut_11`, `_get_camera_stats_with_session__mutmut_1`, `_get_camera_stats_with_session__mutmut_8` |
| 11 | **G3** history sample_interval | 5 | TEST-GAP | 1/3/12 → `None`/4/13; 15m/60m tests assert `len<=60 and >0` so 4 or 13 sampling still passes | `get_performance_history__mutmut_9`, `get_performance_history__mutmut_19`, `get_performance_history__mutmut_27` |
| 12 | **L3** listener payload extraction | 6 | TEST-GAP | `wrapped_data.get("payload")` → `None`/`get(None)`/`"XXpayloadXX"`/`"PAYLOAD"`, `if not status_data` → `if status_data`, `status_data = wrapped_data` → `None` — existing message tests use *legacy* unwrapped format, never the `{_origin_instance, payload}` wrapper | `_listen_for_updates__mutmut_39`, `_listen_for_updates__mutmut_41`, `_listen_for_updates__mutmut_37` |
| 13 | **SQL1** GPU-stats SQL | 6 | TEST-GAP | `select(GPUStats)`→`None`, `order_by(None)`, `limit(1)→None/2`, `execute(None)` — mock returns 1 row whatever the statement | `_get_latest_gpu_stats_with_session__mutmut_3`, `_get_latest_gpu_stats_with_session__mutmut_5`, `_get_latest_gpu_stats_with_session__mutmut_1` |
| 14 | **H1** attempt counting / give-up cmp | 2 | TEST-GAP | `attempts += 1 → += 2`; `attempts > MAX` → `>= MAX` (boundary: existing test sets `MAX+1`, skipping the equality case) | `_attempt_listener_recovery__mutmut_4`, `_attempt_listener_recovery__mutmut_14` |
| 15 | **PP1** perf payload | 5 | TEST-GAP | broadcast_performance msg `"data"`→`"XXdataXX"`/`"DATA"`; `model_dump(mode="json")` → `None`/`"XXjsonXX"`/`"JSON"` (invalid modes raise → caught → silent drop) | `broadcast_performance__mutmut_13`, `broadcast_performance__mutmut_15`, `broadcast_performance__mutmut_16` |
| 16 | **AI1** httpx client kwargs/urls | 4 | TEST-GAP | `AsyncClient(timeout=AI_HEALTH_CHECK_TIMEOUT)` → `timeout=None` ×2; `client.get(f"{url}/health")` → `get(None)` ×2 (mock accepts anything) | `_check_ai_health__mutmut_6`, `_check_ai_health__mutmut_8`, `_check_ai_health__mutmut_15` |
| 17 | **SS2** status failure-path values | 4 | TEST-GAP | `gpu_stats/camera_stats/queue_stats = await _get_*()` → `None`; DB-error path `{"active": 0, "total": 0}` → `{"total": 1}` | `_get_system_status__mutmut_1`, `_get_system_status__mutmut_34`, `_get_system_status__mutmut_30` |
| 18 | **DG1** degraded-state payload keys | 4 | TEST-GAP | `"message"`→`"XXmessageXX"`/`"MESSAGE"`, `"circuit_state"`→`"XXcircuit_stateXX"`/`"CIRCUIT_STATE"` — existing test L1786-92 asserts type/service/status but **not** `message`/`circuit_state` | `_broadcast_degraded_state__mutmut_17`, `_broadcast_degraded_state__mutmut_22` |
| 19 | **L2** listener resets attempts | 2 | TEST-GAP | per-message `self._recovery_attempts = 0` → `1`/`None` (no test reads the counter after processing) | `_listen_for_updates__mutmut_19`, `_listen_for_updates__mutmut_20` |
| 20 | **L4** listener routing | 4 | TEST-GAP | `_send_to_local_clients(None)`, `listen(None)`, `continue→break` ×2 (early stop only observable with ≥2 messages; the 2-message test uses unwrapped dicts) | `_listen_for_updates__mutmut_45`, `_listen_for_updates__mutmut_16`, `_listen_for_updates__mutmut_36` |
| 21 | **NP1** None-as-payload | 2 | TEST-GAP | `_broadcast_loop`: `broadcast_status(None)`; `connect`: initial `status_data = None` then `send_json(None)` | `_broadcast_loop__mutmut_2`, `connect__mutmut_3` |
| 22 | **K1** `_recovery_attempts` init | 3 | TEST-GAP | `__init__`/`_start_pubsub_listener` reset `0 → 1/None` | `__init____mutmut_12`, `_start_pubsub_listener__mutmut_18`, `_start_pubsub_listener__mutmut_19` |
| 23 | **H3** restart-task dropped | 1 | TEST-GAP | recovery success path `self._listener_task = create_task(...)` → `None`: listener never restarted, unasserted | `_attempt_listener_recovery__mutmut_47` |
| 24 | **IID** instance id | 1 | TEST-GAP | `self._instance_id = str(uuid.uuid4())` → `str(None)` — kills multi-instance self-filtering uniqueness (existing self-skip test uses the mutated constant, so still passes) | `__init____mutmut_15` |
| 25 | **SG1** async-singleton wiring | 3 | TEST-GAP | `SystemBroadcaster(redis_getter=redis_getter)` → `redis_getter=None` / kwarg dropped; `start_broadcasting(interval)` → `(None)` | `x_get_system_broadcaster_async__mutmut_9`, `x_get_system_broadcaster_async__mutmut_11`, `x_get_system_broadcaster_async__mutmut_13` |
| 26 | **IV1a** loop interval arg | 1 | TEST-GAP | `create_task(self._broadcast_loop(None))` — `asyncio.sleep(None)` (indefinite) would wedge the loop; never run for real | `start_broadcasting__mutmut_10` |
| 27 | **G1a** history range dispatch | 1 | TEST-GAP | `elif time_range == FIFTEEN_MIN` → `!=` — 15m range silently falls into the 60m branch; existing 15m test (`<= 60`) can't tell | `get_performance_history__mutmut_13` |
| 28 | **AI2** AI aggregate booleans | 2 | LOW-VALUE | `"any_healthy": or→and`, `"all_healthy": and→or` — only observable in the 1-of-2 mixed case; **consumer `_get_system_status` derives its own aggregates and never reads `any_healthy`**, so the only victim is an unused dict field (see draft T6) | `_check_ai_health__mutmut_36`, `_check_ai_health__mutmut_39` |
| 29 | **G4** history max_points | 3 | LOW-VALUE | `max_points 60 → 61` ×3 — unobservable while window yields ≤60 points (every existing test) | `get_performance_history__mutmut_12`, `get_performance_history__mutmut_21`, `get_performance_history__mutmut_29` |
| 30 | **G2** history window minutes | 4 | LOW-VALUE | `timedelta(minutes=5/15/60)` ±1 — inside existing tolerance pads (5m test allows `five_min_ago` −5s slack) | `get_performance_history__mutmut_8`, `get_performance_history__mutmut_17`, `get_performance_history__mutmut_25` |
| 31 | **G1b** history sampling branches | 3 | LOW-VALUE | `if sample_interval == 1` → `!= 1` / `== 2` (routing identical for the tested 1/3/12 values), `s.timestamp >= window_start` → `>` (boundary point excluded, within tolerance) | `get_performance_history__mutmut_31`, `get_performance_history__mutmut_33`, `get_performance_history__mutmut_34` |
| 32 | **EQ1** break↔return | 2 | EQUIVALENT | `break` → `return` at loop-tail exits (identical) | `_broadcast_loop__mutmut_4`, `_listen_for_updates__mutmut_18` |
| 33 | **EQ2** None→"" falsy sentinels | 3 | EQUIVALENT | `_listener_task`/`_pubsub` `None` → `""` (all consumers are truthiness checks) | `__init____mutmut_3`, `__init____mutmut_8`, `_reset_pubsub_connection__mutmut_14` |
| 34 | **DP1** deprecated health probe | 2 | EQUIVALENT | deprecated `_get_health_status` DB probe `session.execute(select(count))` → `None`/`select(None)` — result unused; with mock session cannot raise | `_get_health_status__mutmut_1`, `_get_health_status__mutmut_3` |
| 35 | **IV1b** default interval | 2 | EQUIVALENT | `start`/`start_broadcasting(interval: float = 5.0)` → `6.0` — every production + test call site passes interval explicitly | `start__mutmut_1`, `start_broadcasting__mutmut_1` |

**TEST-GAP (94):** PS1 16, SD1 15, SQL2 8, L3 6, SQL1 6, G3 5, PP1 5, SS2 4, AI1 4, G5b 4, DG1 4, L4 4, H1 2, L2 2, NP1 2, K1 3, SG1 3, H3 1, IID 1, IV1a 1, G1a 1.
**EQUIVALENT (190):** C2 110, C1 48, SS1 19, G5a 4, EQ1 2, EQ2 3, DP1 2, IV1b 2.
**LOW-VALUE (38):** CB 14, H2 12, G2 4, G1b 3, G4 3, AI2 2.
Totals: 94 + 190 + 38 = 324 (exact).

## Drafted kill-tests (7 — UNVERIFIED, not run red/green)

Style follows `test_system_broadcaster.py` / `test_system_broadcaster_history.py` (`@pytest.mark.asyncio`, `AsyncMock`, `patch.object(..., autospec=True)`).

### T1 — pub/sub lifecycle uses BOTH channels — kills PS1 (16) (+ L4 `listen(None)` helper effect)

Target: `backend/tests/unit/services/test_system_broadcaster.py` (next to L492 `start_pubsub_listener_success`).

```python
@pytest.mark.asyncio
async def test_system_broadcaster_pubsub_lifecycle_subscribes_both_channels():
    """_start_pubsub_listener / _reset / _stop must use BOTH status+performance channels.

    WP4.4 kill-test for PS1 cluster: channel-arg mutations (None / single-channel)
    in subscribe_dedicated() and unsubscribe() calls. UNVERIFIED - not yet run red/green.
    """
    from backend.services.system_broadcaster import (
        PERFORMANCE_UPDATE_CHANNEL,
        SYSTEM_STATUS_CHANNEL,
    )

    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()
    mock_redis.subscribe_dedicated.return_value = mock_pubsub

    async def empty_listen(pubsub):
        for _ in []:
            yield

    mock_redis.listen = empty_listen

    broadcaster = SystemBroadcaster(redis_client=mock_redis)

    # --- start: subscribe_dedicated must name both channels, in order ---
    await broadcaster._start_pubsub_listener()
    assert mock_redis.subscribe_dedicated.call_args.args == (
        SYSTEM_STATUS_CHANNEL,
        PERFORMANCE_UPDATE_CHANNEL,
    )

    # --- stop: unsubscribe must name both channels ---
    await broadcaster._stop_pubsub_listener()
    mock_pubsub.unsubscribe.assert_called_once_with(
        SYSTEM_STATUS_CHANNEL, PERFORMANCE_UPDATE_CHANNEL
    )

    # --- reset: old sub unsubscribed from both, fresh sub created on both ---
    old_pubsub = AsyncMock()
    broadcaster._pubsub = old_pubsub
    await broadcaster._reset_pubsub_connection()
    old_pubsub.unsubscribe.assert_called_once_with(
        SYSTEM_STATUS_CHANNEL, PERFORMANCE_UPDATE_CHANNEL
    )
    assert mock_redis.subscribe_dedicated.call_args.args == (
        SYSTEM_STATUS_CHANNEL,
        PERFORMANCE_UPDATE_CHANNEL,
    )

    # Cleanup: cancel listener task spawned by the last subscribe path
    broadcaster._pubsub_listening = False
    if broadcaster._listener_task:
        broadcaster._listener_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await broadcaster._listener_task
```

TDD: on any PS1 mutant (e.g. `_start_pubsub_listener__mutmut_12` first-channel → `None`) the `call_args.args ==` assert fails; on original it passes because `system_broadcaster.py:550-552` passes both constants.

### T2 — shutdown notice shape + resilience — kills SD1 (15) + NP1-loop-half (partial)

Target: `test_system_broadcaster.py` (after L217 `stop_broadcasting`).

```python
@pytest.mark.asyncio
async def test_stop_broadcasting_sends_shutdown_notice_shape():
    """NEM-4987: stop_broadcasting must send type=system.shutdown with reconnect=True.

    WP4.4 kill-test for SD1 (payload key/value text mutations) — and proves the
    notice is best-effort: a dead socket must not abort shutdown.
    UNVERIFIED - not yet run red/green.
    """
    broadcaster = SystemBroadcaster()
    broadcaster._running = True

    good_ws = AsyncMock()
    dead_ws = AsyncMock()
    dead_ws.send_json.side_effect = ConnectionError("client already gone")
    broadcaster.connections.add(good_ws)
    broadcaster.connections.add(dead_ws)

    await broadcaster.stop_broadcasting()  # must not raise despite dead_ws

    good_ws.send_json.assert_called_once_with(
        {
            "type": "system.shutdown",
            "data": {"reason": "Server shutting down", "reconnect": True},
        }
    )
    assert broadcaster._running is False
    assert broadcaster._broadcast_task is None
```

TDD: `stop_broadcasting__mutmut_17` (`reconnect: False`) and every key-text mutant (`"XXtypeXX"`, `"REASON"`, …) fail the dict-equality assert; `__mutmut_3` (whole dict → `None`) fails on payload; original passes.

### T3 — listener forwards the `payload` of a remote wrapped message and resets attempts — kills L3 (6) + L2 (2) + L4 self-skip `continue→break` (36) + H3 (1) + K1 (3) + SS2 `_get_system_status__mutmut_1` (partial)

Target: `test_system_broadcaster.py` (after L1874 `listen_skips_self_originated_messages`).

```python
@pytest.mark.asyncio
async def test_listen_for_updates_forwards_remote_wrapped_payload():
    """Listener must unwrap {payload} from REMOTE instances and reset recovery state.

    WP4.4 kill-test: L3 (payload key mutations), L2 (_recovery_attempts reset),
    L4 (self-origin continue->break stops later messages), H3/K1 via follow-up
    recovery assertions. UNVERIFIED - not yet run red/green.
    """
    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()

    remote_payload = {"type": "system_status", "from": "other-instance"}
    second_payload = {"type": "performance_update", "seq": 2}
    messages = [
        # self-originated (must be skipped but NOT stop the loop)
        {
            "data": {
                "_origin_instance": "self-id",
                "payload": {"type": "system_status", "test": "mine"},
            }
        },
        {"data": {"_origin_instance": "remote-id", "payload": remote_payload}},
        {"data": {"_origin_instance": "remote-id", "payload": second_payload}},
    ]

    async def mock_listen(pubsub):
        for msg in messages:
            yield msg

    mock_redis.listen = mock_listen

    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._instance_id = "self-id"
    broadcaster._pubsub = mock_pubsub
    broadcaster._pubsub_listening = True
    broadcaster._recovery_attempts = 3  # dirty counter must be reset by message processing

    mock_ws = AsyncMock()
    broadcaster.connections.add(mock_ws)

    await broadcaster._listen_for_updates()

    # Both remote payloads forwarded verbatim (unwrapped), self message never sent
    assert mock_ws.send_text.call_count == 2
    assert json.loads(mock_ws.send_text.call_args_list[0].args[0]) == remote_payload
    assert json.loads(mock_ws.send_text.call_args_list[1].args[0]) == second_payload
    # Recovery bookkeeping on successful message processing
    assert broadcaster._recovery_attempts == 0
```

TDD: `get("XXpayloadXX")`-style mutants forward the wrapper or nothing → first `send_text` payload assert fails; `continue→break` (`__mutmut_36`) yields count 1 ≠ 2; `_recovery_attempts = 1/None` mutants fail the last assert; original passes.

### T4 — recovery timing bound + listener restart after success — kills H3 (1, co-kill), H2 (some), plus boundary give-up `>` vs `>=` — kills H1 (2)

Target: `test_system_broadcaster.py` (after L1611 `is_degraded_after_max_recovery_attempts`).

```python
@pytest.mark.asyncio
async def test_attempt_listener_recovery_backoff_bounds_and_restart():
    """Recovery sleep must be in [1s, 78s] with base=1 doubling, and restart the task.

    WP4.4 kill-test: H2 division/`3**`/base_delay mutants (sleep out of band) and
    H3 (_listener_task = None — listener never restarted).
    UNVERIFIED - not yet run red/green.
    """
    mock_redis = AsyncMock()
    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._pubsub_listening = True
    broadcaster._recovery_attempts = 2  # delay should be 1.0 * 2**(2-1) = 2.0s (+10-30% jitter)

    sleeps: list[float] = []

    async def capture_sleep(delay):
        sleeps.append(delay)

    restart_task = object()
    with (
        patch("asyncio.sleep", side_effect=capture_sleep, autospec=True),
        patch.object(broadcaster, "_reset_pubsub_connection", autospec=True) as mock_reset,
    ):
        # reset leaves a truthy pubsub, so the success path must restart the listener
        async def reset_ok():
            broadcaster._pubsub = AsyncMock()

        mock_reset.side_effect = reset_ok
        with patch("asyncio.create_task", return_value=restart_task) as mock_create:
            await broadcaster._attempt_listener_recovery()

    assert len(sleeps) == 1
    # original: 2.0s + [0.2, 0.6] jitter; /2**, 3**, base 2.0, -jitter mutants fall outside
    assert 2.0 <= sleeps[0] <= 2.8, f"backoff {sleeps[0]} outside bounded-exponential range"
    # H3: recovery success must re-spawn the listener task
    mock_create.assert_called_once()
    assert broadcaster._listener_task is restart_task


@pytest.mark.asyncio
async def test_attempt_listener_recovery_allows_attempt_at_max_boundary():
    """Give-up fires only ABOVE MAX_RECOVERY_ATTEMPTS (attempts > MAX, not >=).

    WP4.4 kill-test for H1 (_attempt_listener_recovery__mutmut_14: > -> >=).
    UNVERIFIED - not yet run red/green.
    """
    mock_redis = AsyncMock()
    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._pubsub_listening = True
    broadcaster._recovery_attempts = broadcaster.MAX_RECOVERY_ATTEMPTS - 1  # -> 5 after +=1, still <= MAX

    slept: list[float] = []

    async def capture_sleep(delay):
        slept.append(delay)
        broadcaster._pubsub_listening = False  # stop before reset, isolate the boundary

    with patch("asyncio.sleep", side_effect=capture_sleep, autospec=True):
        await broadcaster._attempt_listener_recovery()

    # On original: attempt 5 == MAX -> proceeds to backoff (sleep called), not degraded.
    # On __mutmut_14 (>=): degraded branch taken, no sleep, degraded True.
    assert slept, "attempt count == MAX must still be allowed to back off"
    assert broadcaster.is_degraded() is False
    assert broadcaster._recovery_attempts == broadcaster.MAX_RECOVERY_ATTEMPTS
```

TDD: `+= 2` mutant makes `_recovery_attempts` 6 > MAX → degraded, `slept` empty → both asserts fail; `>=` mutant skips sleep → `assert slept` fails; original passes both.

### T5 — SQL statement shape: GPU ORDER BY/LIMIT and camera ONLINE filter — kills SQL1 (6) + SQL2 (8)

Target: `test_system_broadcaster.py` (after L1179 `get_camera_stats_with_session`).

```python
@pytest.mark.asyncio
async def test_gpu_and_camera_statements_sql_shape():
    """GPU query: newest-first LIMIT 1; camera active-count filters ONLINE.

    WP4.4 kill-test: SQL1 (order_by/limit clobbering) and SQL2 — notably
    _get_camera_stats_with_session__mutmut_11 (WHERE == ONLINE -> != ONLINE).
    Mocked sessions cannot see this, so compile the captured statements.
    UNVERIFIED - not yet run red/green.
    """
    from sqlalchemy import select as sa_select

    from backend.models import Camera, CameraStatus

    broadcaster = SystemBroadcaster()

    # --- GPU: capture the executed statement ---
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    await broadcaster._get_latest_gpu_stats_with_session(mock_session)

    gpu_stmt = mock_session.execute.call_args.args[0]
    compiled = str(gpu_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "ORDER BY" in compiled.upper() and "DESC" in compiled.upper()
    # LIMIT 1 (limit(None) drops the clause; limit(2) -> 'LIMIT 2')
    assert "LIMIT 1" in compiled.upper()

    # --- Camera: second execute() is the active count and must filter ONLINE ---
    call_count = 0

    def mock_execute(*args):
        nonlocal call_count
        call_count += 1
        r = MagicMock()
        r.scalar_one.return_value = 0
        return r

    session2 = AsyncMock()
    session2.execute.side_effect = mock_execute
    await broadcaster._get_camera_stats_with_session(session2)
    assert call_count == 2

    active_stmt = session2.execute.call_args_list[1].args[0]
    active_compiled = str(active_stmt.compile(compile_kwargs={"literal_binds": True}))
    online = str(
        sa_select().where(Camera.status == CameraStatus.ONLINE.value).compile()
    )
    # the ONLINE predicate is present, same as the original equality form
    assert online.split("WHERE")[1].strip() in active_compiled
```

TDD: `!=` mutant's WHERE renders `camera.status != 'online'` — the equality-derived predicate substring is absent → assert fails; `order_by(None)`/`limit(None)`/`limit(2)` mutants fail the GPU ORDER BY/LIMIT asserts; statements that became `None`/`select(None)` raise ArgumentError before reaching asserts.

### T6 — AI health: one-down mixed state + request shape — kills AI1 (4) (+ AI2 with a widened assertion)

Target: `test_system_broadcaster.py` (after L1446 `check_ai_health_timeout`).

```python
@pytest.mark.asyncio
async def test_check_ai_health_mixed_state_and_request_shape():
    """One healthy + one failing service -> any_healthy True, all_healthy False;
    both requests must hit the /health endpoints with the short timeout.

    WP4.4 kill-test: AI1 (timeout=None, url=None) and AI2 aggregate flips
    (or->and / and->or are only distinguishable in the 1-of-2 case).
    UNVERIFIED - not yet run red/green.
    """
    broadcaster = SystemBroadcaster()

    with patch(
        "backend.services.system_broadcaster.httpx.AsyncClient", autospec=True
    ) as mock_client_cls:
        mock_client = AsyncMock()

        async def mock_get(url):
            resp = MagicMock()
            resp.status_code = 200 if url.endswith("health") and "yolo26" in url else 500
            return resp

        mock_client.get.side_effect = mock_get
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client_cls.return_value.__aexit__.return_value = None

        result = await broadcaster._check_ai_health()

    # yolo26 healthy (200), nemotron unhealthy (500)
    assert result["yolo26"] is True
    assert result["nemotron"] is False
    assert result["any_healthy"] is True   # __mutmut_36 (or->and) fails here
    assert result["all_healthy"] is False  # __mutmut_39 (and->or) fails here

    # request shape: every call is a real URL ending /health (kills get(None))
    urls = [c.args[0] for c in mock_client.get.call_args_list]
    assert len(urls) == 2
    assert all(isinstance(u, str) and u.endswith("/health") for u in urls)

    # timeout kwarg preserved (kills timeout=None) — autospec passes it through
    for c in mock_client_cls.call_args_list:
        assert c.kwargs.get("timeout") == 1.0  # AI_HEALTH_CHECK_TIMEOUT
```

TDD: aggregate mutants break the mixed-state asserts; `timeout=None` breaks the kwargs assert; `client.get(None)` breaks the URL assert; original passes.

### T7 — performance-history sampling exactness + truncation boundary — kills G1a (1) + G3 (5) + G5b (4)

Target: `backend/tests/unit/services/test_system_broadcaster_history.py` (append to the `get_performance_history` section).

```python
@pytest.mark.asyncio
async def test_get_performance_history_sampling_is_exact():
    """15m must sample every 3rd and 60m every 12th; >max_points must truncate to 60.

    WP4.4 kill-test: G1a (FIFTEEN_MIN branch dispatch flip), G3 (sample_interval
    3->4 / 12->13), G5b (>= / always-truncate mutants need len>60 which only a
    dense buffer produces). UNVERIFIED - not yet run red/green.
    """
    broadcaster = SystemBroadcaster()
    now = datetime.now(UTC)

    # 300 snapshots at 1s spacing -> 15m window holds 900 > 60 sampled... but
    # buffer maxlen is 720; use 360 snapshots covering 6 min at 1s each.
    for i in range(360):
        broadcaster._store_performance_snapshot(
            PerformanceUpdate(timestamp=now - timedelta(seconds=359 - i))
        )

    fifteen = broadcaster.get_performance_history(TimeRange.FIFTEEN_MIN)
    # all 360 snapshots are inside the 15m window; sampled[::3] = 120 -> truncate 60
    assert len(fifteen) == 60
    # exact stride: consecutive gaps are 3s (sample_interval==3)
    gaps = {(b.timestamp - a.timestamp).total_seconds() for a, b in zip(fifteen, fifteen[1:])}
    assert gaps == {3.0}

    sixty = broadcaster.get_performance_history(TimeRange.SIXTY_MIN)
    # sample_interval 12: stride 12s
    gaps60 = {(b.timestamp - a.timestamp).total_seconds() for a, b in zip(sixty, sixty[1:])}
    assert gaps60 == {12.0}
    assert len(sixty) == 30  # 360/12 = 30 sampled, under max_points
```

TDD: on `elif != FIFTEEN_MIN` (G1a) FIFTEEN_MIN falls into the 12/60m branch → gaps `{12.0}` ≠ `{3.0}` fails; `sample_interval 4/13` mutants → gaps `{4.0}`/`{13.0}` fail; `>= max_points` / `or True` mutants still return `[-60:]` at exactly-60 boundary... the always-truncate (`or True`) mutants are observable at len==60 (slice returns same list — EQUIVALENT there); `len(fifteen) == 60` keeps the truncation path exercised so `and False`-form (G5a) would return 120 and fail — original passes (stride math per source lines 204-230).

**Worth 3-6 — final selection:** T1 PS1(16), T2 SD1(15)+NP1 partial, T3 L3+L2+L4+H3 co-kill (~12), T4 H1+H2+H3 (~15), T5 SQL1+SQL2 (14), T6 AI1+AI2 (6), T7 G1a+G3+G5b+G5a-discriminator (~13). Total killable if green: ~95 survivors ≈ 29% of this module's survivor pool.

## Notes / caveats

- **SS1 vs SD1/DG1/PP1 split basis:** the `"XXgpuXX"→"XXmemory_usedXX"`-style key mutants in `_get_system_status` sit inside the *DB-error fallback dict* (source L791-799), reached only when `get_session` raises — under mock-based tests the key text is never observed, and the same text would be unasserted through the `data["gpu"]` pass-through path anyway; the three existing tests that touch the status shape assert key *presence* (`"gpu" in status["data"]`) not dict-equality, so a key rename passes them but breaks the frontend contract. Classified EQUIVALENT **as mutants-under-this-suite with a contract caveat**: a shape-equality assert on the full status dict (add to T3's file if cheap) kills SS1 *and* SS2 together; SS1 stays EQUIVALENT only because no production consumer asserts either — flag for WP4.5 if the frontend schema test (`frontend/src/services`) can pin it instead.
- C2 membership was heuristically assigned for 41 mutants (13%) whose diffs touch logger lines without a `logger.` prefix (continuation strings); 3 stragglers were hand-audited (all multi-line log args → `None`, correctly C2). Counts carry that caveat; all other clusters were verified per-function against the raw diff list (`cluster_keys.json`).
- AI2 is only killable via a *direct* `_check_ai_health` mixed-state test (T6) because the production consumer `_get_system_status` recomputes `healthy/degraded/unhealthy` from `yolo26`/`nemotron` directly (source L814-824) and never reads `any_healthy`/`all_healthy` — an API-level test cannot kill these two.
- Do not run any of these yet: a live mutation run owns pytest on this box (all UNVERIFIED).
