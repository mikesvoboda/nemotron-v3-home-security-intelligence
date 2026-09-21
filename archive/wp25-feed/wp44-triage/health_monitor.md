# WP4.3 mutation triage dossier — backend/services/health_monitor.py

Wave: triage wave (UNVERIFIED drafting tier). Generated 2026-09-18.
Verdicts source: `mutants/backend/services/health_monitor.py.meta` (`exit_code_by_key`).
Survivors: **143** of 298 keys (144 killed, 11 untested). Diffs extracted by diffing each
`xǁ…ǁ<fn>__mutmut_N` variant body against its `__mutmut_orig` in the mutant copy
(mutmut show not needed).

## Covering test files

- `backend/tests/unit/core/test_health_monitor.py` (1411 lines) — primary: loop, failure handling,
  backoff, restart, broadcast, events. Key anchors: `fast_sleep` fixture :14-34 (only accelerates
  the 2s post-restart pause), `test_restart_with_exponential_backoff` :208-258,
  `test_max_retries_stops_restart_attempts` :264-309, `test_recovery_resets_failure_count` :312-351,
  `test_broadcast_event_format` :657-676 (checks presence of `type/data/service/status/timestamp`,
  **never `data.message`**), event tests :1245-1411 (assert `event_type` via membership filter,
  **never `event.service`/`event.message`/`event.timestamp`**).
- `backend/tests/unit/services/test_health_monitor.py` — `TestHealthMonitorTaskNaming` :47-100:
  asserts `"health" in task_name.lower()` and `not task_name.startswith("Task-")` — too weak to pin
  the documented name (NEM-5057).
- Downstream consumer raising stakes on event fields: `backend/api/routes/system.py:1358-1367`
  serializes `get_recent_events()` into `/api/system/health` `recent_events` with
  `timestamp/service/event_type/message`; WS payload has the same fields.

## Recurring convergence pattern (why so much survived)

`_health_check_loop` wraps every service check in `except Exception` that re-broadcasts
"unhealthy" and calls `_handle_failure(service)`; `_handle_failure` wraps the restart block in
`except Exception` that broadcasts "restart_failed"; the loop's recovery branch resets failure
counts on the next healthy cycle. Consequently mutants that **crash an inner call** (arg clobber
`None`, `sleep(None)`, `is_healthy = None`) converge to roughly-correct end state one step later
and every existing assertion (presence-of-broadcast, `failure_count == 0` *eventually*,
`restart_count <= N`) still passes. Only exact-string message assertions, exact backoff sequences,
direct-call unit assertions, and event/payload field assertions can kill them.

## Cluster table (counts sum to 143)

| # | Pattern | Fn | Keys (<=3 examples) | N | Class |
|---|---------|----|---------------------|---|-------|
| G1 | Broadcast `message` lost/`XX…XX`/case-clobbered, or `service` arg clobbered so the call dies and the except-handler re-broadcasts with "Health check error:/Restart error:" instead of the documented message | `_health_check_loop` + `_handle_failure` | loop#13, loop#16, hf#11 | 36 | TEST-GAP |
| G2 | `event_type_map` key or value clobbered (status→event-type mapping breaks or mislabels); recorded events missing/wrong `event_type`, other statuses' events satisfy membership-style test | `_broadcast_status` | bs#20 (`"XXunhealthyXX"`), bs#22 (`"XXfailureXX"`), bs#33 (`"RESTART_DISABLED"`) | 16 | TEST-GAP |
| G3 | `HealthEvent` fields clobbered at construction/call site: `service=None`, `message=None`/dropped, `timestamp=None`/`now(None)` — `/api/system/health` `recent_events` loses service/message/tz-aware timestamp | `_record_event`, `_broadcast_status` | re#2 (`timestamp=None`), bs#46 (`_record_event(None,…)`), bs#48 (`message=None`) | 7 | TEST-GAP |
| G4 | WS envelope schema: `data.message` key renamed `XXmessageXX`/`MESSAGE`; top-level `timestamp` becomes naive via `datetime.now(None)` | `_broadcast_status` | bs#64, bs#65, bs#68 | 3 | TEST-GAP |
| G5 | Exponential backoff formula broken: `base / 2^(n-1)`, `base * (2*(n-1))`, `3^(n-1)` base, `2^(n-2)` shift — sleep schedule no longer `base*2^(n-1)` | `_handle_failure` | hf#34, hf#35, hf#36 | 4 | TEST-GAP |
| G6 | Max-retries boundary `>` → `>=` — gives up one restart attempt early | `_handle_failure` | hf#23 | 1 | TEST-GAP |
| G7 | Post-restart-success verification/accounting broken: `is_healthy=None` (always restart_failed), count reset `=0`→`=1`, `sleep(2)`→`sleep(None)` (TypeError → except path), verify `check_health(None)` — all masked by the *loop's* recovery branch resetting counts/broadcasting healthy later | `_handle_failure` | hf#55, hf#59, hf#53 | 4 | TEST-GAP |
| G8 | Loop recovery-detection threshold `count > 0` mutated: `>= 0` spams a recovery broadcast+event on every healthy cycle once the key exists; `> 1` skips recovery broadcast for single failures (count stuck at 1) | `_health_check_loop` | loop#10, loop#11 | 2 | TEST-GAP |
| G9 | `_handle_failure(None)` arg clobber (both call sites) — crashes immediately, except path re-broadcasts unhealthy + retries with correct arg; net effect: duplicate "unhealthy" broadcasts/crash logs, same eventual restart | `_health_check_loop` | loop#24, loop#38 | 2 | TEST-GAP |
| G10 | `create_task(name=…)` string clobbered (`XXservice-health-monitorXX`, `SERVICE-HEALTH-MONITOR`) — survives existing test which only checks `"health" in name.lower()` | `start` | start#16, start#17 | 2 | TEST-GAP |
| E1 | Logger message-text mutations only (`logger.*(None)`, `XX…XX`, lower/upper-case string swaps) — no control/behavior change | all | start#1, stop#6, loop#2 | 46 | EQUIVALENT |
| E2 | Log-level / `exc_info` tweaks: `exc_info=True`→None/False/dropped; `log_level` ternary forced-warning (`and False`)/forced-info (`or True`)/flipped (`!=`) — affects only diagnostics | loop, hf, bs | bs#2, bs#71, loop#26 | 14 | EQUIVALENT |
| E3 | `break`→`return` in CancelledError handler — only difference is skipping the final "Health check loop stopped" log line | `_health_check_loop` | loop#44 | 1 | EQUIVALENT |
| L1 | Non-behavioral argument-removal artifacts on exception logs: `logger.warning(f"…")` → `logger.warning()` (bs#72, missing positional → TypeError raised inside the broadcast-failure `except`, swallowed by the outer per-service guard; monitor keeps running) and `get_recent_events(limit=50)` → `limit=51` default (gre#1; one extra event at most from a 100-deque, no spec depends on 50) | `_broadcast_status`, `get_recent_events` | bs#72, gre#1 | 2 | LOW-VALUE |

TEST-GAP 77 / EQUIVALENT 64 / LOW-VALUE 2. Sum: 36+16+7+3+4+1+4+2+2+2+49+14+1+2 = 143 (partition machine-verified: no key in two clusters, none missing).

### G1 full key list (36) — wire `message` payload and arg-clobbers converging to it
loop: 13, 15, 16, 18, 21, 22, 23, 32, 35; hf: 5, 8, 11, 12, 13 (restart_disabled msg), 27, 30
(failed msg), 44, 47 (restarting msg), 62, 65, 68, 69, 70 (healthy msg), 72, 74, 75, 77, 80, 81,
82 (restart_failed msg/service clobbers), 84, 86, 87, 89 (restart-failed msg/service clobbers),
99, 102 (restart-error msg). Test file gap: `test_broadcast_event_format` (core/test_health_monitor.py:657)
asserts payload *keys* only — never `data["message"]` content on any status.

## Drafted tests (UNVERIFIED — not yet run red/green)

TDD procedure (one line): write the test, run it against the mutant copy first (expect FAILED —
assertion trips on the mutated string/value), then against original `backend/services/health_monitor.py`
(expect PASSED); commit only on that red→green order.

### T1 — kills G5 (backoff formula). Target: backend/tests/unit/core/test_health_monitor.py

```python
# Test: Exponential Backoff (exact schedule) — WP4.4 G5

@pytest.mark.asyncio
async def test_backoff_delays_follow_exponential_schedule(mock_manager, sample_config, mock_broadcaster):
    """Test that restart backoff delays are exactly backoff_base * 2**(failures-1)."""
    recorded_delays: list[float] = []

    async def record_sleep(delay):
        recorded_delays.append(delay)

    mock_manager.restart.return_value = False  # keep out of the 2s verification path

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[sample_config],
        broadcaster=mock_broadcaster,
        check_interval=0.1,
    )

    with patch.object(asyncio, "sleep", side_effect=record_sleep, autospec=True):
        await monitor._handle_failure(sample_config)  # failure #1 -> 0.1s
        await monitor._handle_failure(sample_config)  # failure #2 -> 0.2s

    assert recorded_delays == [0.1, 0.2], f"Expected [0.1, 0.2], got {recorded_delays}"
```

Kills hf#34 (`[0.1, 0.05]`), hf#35 (`[0.0, 0.2]`), hf#36 (`[0.1, 0.3]`), hf#38 (`[0.05, 0.1]`).
Original: exact equality holds. `sample_config.backoff_base=0.1`.

### T2 — kills G6 (max-retries boundary). Target: backend/tests/unit/core/test_health_monitor.py

```python
# Test: Max Retries (exact boundary) — WP4.4 G6

@pytest.mark.asyncio
async def test_max_retries_boundary_grants_exactly_max_attempts(
    mock_manager, mock_broadcaster, fast_sleep
):
    """Test that exactly max_retries restart attempts happen before the 'failed' broadcast."""
    mock_manager.check_health.return_value = False
    mock_manager.restart.return_value = False

    config = ServiceConfig(
        name="test_service",
        health_url="http://localhost:9999/health",
        restart_cmd="echo test",
        health_timeout=1.0,
        max_retries=2,
        backoff_base=0.01,
    )
    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[config],
        broadcaster=mock_broadcaster,
        check_interval=0.1,
    )

    with patch.object(asyncio, "sleep", autospec=True):
        await monitor._handle_failure(config)  # attempt 1 -> restart
        await monitor._handle_failure(config)  # attempt 2 -> restart
        await monitor._handle_failure(config)  # attempt 3 -> give up

    assert mock_manager.restart.await_count == 2, (
        f"Expected exactly 2 restart attempts, got {mock_manager.restart.await_count}"
    )
    statuses = [c[0][0]["data"]["status"] for c in mock_broadcaster.broadcast_service_status.call_args_list]
    assert statuses.count("failed") == 1, "Expected exactly one 'failed' broadcast on give-up"
    assert monitor.get_status()[config.name]["failure_count"] == 3
```

Mutant hf#23 (`>=`) gives up on attempt 2 → `restart.await_count == 1` → red. Original: 2 attempts
then give-up → green. (Existing test at :264 only asserts `restart_count <= 2`.)

### T3 — kills G7 (restart-success verification + accounting). Target: backend/tests/unit/core/test_health_monitor.py

```python
# Test: Restart success path direct unit — WP4.4 G7

@pytest.mark.asyncio
async def test_restart_success_resets_count_and_broadcasts_healthy(
    mock_manager, sample_config, mock_broadcaster, fast_sleep
):
    """Test that a successful restart resets the failure count and broadcasts healthy with exact message."""
    mock_manager.restart.return_value = True
    mock_manager.check_health.return_value = True

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[sample_config],
        broadcaster=mock_broadcaster,
        check_interval=10.0,
    )
    monitor._failure_counts[sample_config.name] = 0

    await monitor._handle_failure(sample_config)

    # Post-restart health verification must target the correct service (kills check_health(None))
    mock_manager.check_health.assert_awaited_once_with(sample_config)
    # Successful restart must reset the counter (kills =1 reset) and report healthy (kills is_healthy=None / sleep(None))
    assert monitor.get_status()[sample_config.name]["failure_count"] == 0
    payload = mock_broadcaster.broadcast_service_status.call_args[0][0]
    assert payload["data"]["status"] == "healthy"
    assert payload["data"]["message"] == "Service restarted successfully"
```

Red on hf#55 (status becomes `restart_failed`), hf#56 (`assert_awaited_once_with(sample_config)`
sees `None`), hf#59 (`failure_count == 1`), hf#53 (`sleep(None)` TypeError → `restart_failed` /
"Restart error:" message). Green on original (single `check_health` call inside `_handle_failure`).

### T4 — kills G2 + G3 + G4 (event mapping, event fields, WS envelope). Target: backend/tests/unit/core/test_health_monitor.py

```python
# Test: Broadcast status -> event history + WS envelope contract — WP4.4 G2/G3/G4

@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected_event_type"),
    [
        ("unhealthy", "failure"),
        ("restart_failed", "failure"),
        ("failed", "failure"),
        ("restart_disabled", "failure"),
        ("healthy", "recovery"),
        ("restarting", "restart"),
    ],
)
async def test_broadcast_status_records_expected_event_and_payload(
    mock_manager, sample_config, mock_broadcaster, status, expected_event_type
):
    """Test that each status records a correctly-typed event and WS payload fields."""
    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[sample_config],
        broadcaster=mock_broadcaster,
        check_interval=10.0,
    )

    await monitor._broadcast_status(sample_config, status, "detail text")

    events = monitor.get_recent_events()
    assert len(events) == 1, f"status {status!r} must record exactly one event"
    assert events[0].event_type == expected_event_type
    assert events[0].service == sample_config.name
    assert events[0].message == "detail text"
    assert events[0].timestamp is not None and events[0].timestamp.tzinfo is not None

    payload = mock_broadcaster.broadcast_service_status.call_args[0][0]
    assert payload["data"]["message"] == "detail text"
    assert payload["data"]["service"] == sample_config.name
    assert payload["data"]["status"] == status
    parsed_ts = datetime.fromisoformat(payload["timestamp"])
    assert parsed_ts.tzinfo is not None, "WS timestamp must be tz-aware UTC"
```

(Add `from datetime import datetime` to the test file imports — currently the module-level imports
lack it; existing tests import `datetime` locally inside functions.) Red on bs#20-35 (missing/mislabeled
events), bs#46/48/51 + re#2/re#5/re#9/re#10 (event service/message/timestamp), bs#64/65/68
(payload key/naive timestamp). Note re#2/re#5/re#9/re#10 mutate `_record_event` internals; this test
kills them through the broadcast path; it is exercised by every recorded event.

### T5 — kills G1 (wire message content, 36 mutants incl. converging clobbers). Target: backend/tests/unit/core/test_health_monitor.py

```python
# Test: Unhealthy cycle broadcast message contract — WP4.4 G1

@pytest.mark.asyncio
async def test_unhealthy_cycle_broadcasts_expected_message_strings(
    mock_manager, sample_config, mock_broadcaster, fast_sleep
):
    """Test that failure-path broadcasts carry the documented human-readable messages."""
    mock_manager.check_health.return_value = False
    mock_manager.restart.return_value = False

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[sample_config],
        broadcaster=mock_broadcaster,
        check_interval=0.1,
    )

    await monitor.start()
    await asyncio.sleep(0.25)  # one full failure cycle (backoff 0.1s)
    await monitor.stop()

    messages = {
        call[0][0]["data"]["message"]
        for call in mock_broadcaster.broadcast_service_status.call_args_list
    }
    assert "Health check failed" in messages
    assert "Attempting restart (attempt 1/3)" in messages
    assert "Restart command failed (attempt 1/3)" in messages
```

Any XX/case/None message mutation removes the exact expected string → red. Arg-clobber mutants
(loop#13/#16, hf#72/#75/#84/#87) make `_broadcast_status` crash and the except handler substitute
"Health check error: …"/"Restart error: …" → expected strings absent → red. Original → green
(fast_sleep accelerates only the 2s pause; the 0.1s backoff is real and fits the 0.25s window).
Does not cover restart_disabled/failed-path message mutants (hf#5/#8/#11-13/#27/#30) — a second
parametrized variant calling `_handle_failure` with `restart_cmd=None` configs is the follow-up.

### T6 — kills G10 (exact task name). Target: backend/tests/unit/services/test_health_monitor.py

```python
    @pytest.mark.asyncio
    async def test_task_name_is_exact_identifier(
        self,
        mock_manager: MagicMock,
        mock_broadcaster: MagicMock,
        service_config: ServiceConfig,
    ) -> None:
        """Test that the task uses the exact documented name (NEM-5057), not just 'health'-ish."""
        monitor = ServiceHealthMonitor(
            manager=mock_manager,
            services=[service_config],
            broadcaster=mock_broadcaster,
            check_interval=0.05,
        )

        await monitor.start()
        try:
            assert monitor._task.get_name() == "service-health-monitor"
        finally:
            await monitor.stop()
```

Red on start#16 (`XXservice-health-monitorXX`) and start#17 (`SERVICE-HEALTH-MONITOR`); green on original.

## Notes on remaining TEST-GAP clusters (no draft this wave)

- **G8 (loop#10/#11)**: killable by a loop-level test asserting *exactly one* healthy/recovery
  broadcast after recovery (kills `>=0` spam) and that a single-failure recovery emits healthy
  (kills `>1`). Deferred: needs careful cycle-count timing against `check_interval`.
- **G9 (loop#24/#38)**: `_handle_failure(None)` converges via the except path; net observable is a
  duplicate "unhealthy" broadcast per cycle. Low drafting value — T5-style exact-message assertion
  partially catches the crash noise only. Classify TEST-GAP-low; consider killing later with a
  "exactly one unhealthy broadcast per failed cycle" count assertion.
- G1 residual: restart_disabled/failed message mutants need the second variant of T5 (direct
  `_handle_failure` calls with `restart_cmd=None` and pre-seeded `max_retries`-exceeded state).
