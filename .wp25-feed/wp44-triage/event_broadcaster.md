# WP4.4 Triage Dossier — backend/services/event_broadcaster.py

**Source of truth**: `mutants/backend/services/event_broadcaster.py.meta` — 1288 keys, **590 survived** (exit_code 0), 0 unchecked.
**Method**: diffs extracted by diffing each `x<fn>__mutmut_N` block against `__mutmut_orig` inside the mutant copy (mutmut cache was concurrently owned, so `mutmut show` was not used; 590/590 keys diffed). Per-survivor assignment machine-checked: cluster counts sum exactly to 590 (TG 155 / LV 143 / EQ 292).
**Covering tests** (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`): primary files are `backend/tests/unit/services/test_event_broadcaster.py` (helpers `_FakeRedis` L34-45), `test_broadcast_retry.py`, `test_message_buffer.py`, `test_event_broadcaster_new_events.py`, `test_batch_aggregator.py` (indirect only), `test_event_broadcaster_worker.py`, `test_event_broadcaster_summary.py`.

## Key semantic rulings (evidence, not vibes)

- **`model_dump(mode=...)` mutants (68) are EQUIVALENT.** Probed against the project venv (pydantic 2.13.5): `mode=None`, `"JSON"`, `"XXjsonXX"` all fall back to python-mode silently (no warning). Every broadcast schema in `backend/api/schemas/websocket.py` declares timestamps as `str` (`WebSocketDetectionNewData.timestamp: str`, `WebSocketSummaryData.window_start: str`, alert `id: str`), so python-mode == json-mode output for all validated messages. No observable difference → cannot be killed; equivalent, not a test gap.
- **Wrap-envelope `{"type": ...}` literal mutants (36) are EQUIVALENT.** In `broadcast_*`, the literal type string only applies when the caller omits `"type"`; tests always pass a pre-typed envelope, and the validated message's own default (`WebSocketDetectionNewMessage.type` etc.) re-overrides it on the published dict. Verified shape: surviving change is key `"type"`→`"TYPE"`/value case only.
- **`.get("data", {})` default mutants (20) are EQUIVALENT** — default only fires when `"data"` key is absent, which validation would reject anyway (guard path is on the other cluster).
- **`requires_ack` default mutants (4) EQUIVALENT**: `data.get("risk_score", 1)`, `risk_level` default `None`/`""`/`"XXXX"` — all still compare `>= 80` / `== "critical"` identically for present/absent keys.
- **`record_ack` `>`→`>=` (mutmut_7) EQUIVALENT** — assignment stores the same value when equal.
- **`if retry_count in ...` flip (record_success mutmut_9) EQUIVALENT** — else-branch is `retry_counts[k] = 1`, same as the if-branch increments from 0.
- **`break`→`return` in `_listen_for_events`/`_supervise_listener` (3) EQUIVALENT** — no code follows the loop.

## Cluster table (counts sum = 590)

| # | Cluster | Class | N | Example keys (suffix) | Note |
|---|---------|-------|---|----------------------|------|
| 1 | EQ-log-message-text (case/XX/identical renames of logger & error strings) | EQUIVALENT | 152 | xǁEventBroadcasterǁǁ_event_broadcaster__init__: `x_get_broadcaster__mutmut_7..10`, `xǁEventBroadcasterǁstart__mutmut_2/3`, `xǁEventBroadcasterǁ_handle_dead_listener__mutmut_2/3/4` | Pure log text incl. `logger.info(None)`; no log-content assertions anywhere |
| 2 | EQ-model-dump-mode-noop (`mode="json"`→None/"JSON"/"XXjsonXX") | EQUIVALENT | 68 | `xǁEventBroadcasterǁbroadcast_ai_action_recognized__mutmut_10/11/12` | Pydantic silently falls back to python mode; schemas carry str timestamps (see ruling above) |
| 3 | EQ-wrap-envelope-type-literal-overridden | EQUIVALENT | 36 | `xǁEventBroadcasterǁbroadcast_batch_analysis_completed__mutmut_5/6/7` | Type literal only used on untyped-input path; schema default re-overrides |
| 4 | LV-log-structure (dropped `extra=`, `exc_info=`, attempt-counter text in log payload) | LOW-VALUE | 126 | `x_broadcast_alert_with_retry_background__mutmut_14/15/17`, `x_broadcast_with_retry__mutmut_42..87` | Structured-log-field changes; nobody should assert logging config |
| 5 | EQ-envelope-get-data-default | EQUIVALENT | 20 | `xǁEventBroadcasterǁbroadcast_batch_analysis_completed__mutmut_13/15` | `.get("data", {})`→`.get("data", None)`; key always present in valid payloads |
| 6 | EQ-comment-text / dead-init-assignments / break-vs-return / to_dict-key / requires_ack-defaults / record_ack-ge / record_success-membership | EQUIVALENT | 16 | `x_broadcast_with_retry__mutmut_1`, `xǁEventBroadcasterǁ_listen_for_events__mutmut_12`, `xǁEventBroadcasterǁbroadcast_detection_batch__mutmut_43` | 3+3+2+2+4+1+1, all semantically inert (details above) |
| 7 | **TG-broadcast-publish-call-args** (`_redis.publish(...)` channel/payload args → None/dropped, return forced None) | TEST-GAP | 17 | `xǁEventBroadcasterǁbroadcast_detection_batch__mutmut_26`, `xǁEventBroadcasterǁbroadcast_ai_action_recognized__mutmut_14`, `xǁEventBroadcasterǁbroadcast_zone_dwell_started__mutmut_9` | `test_event_broadcaster_new_events.py` (L100s) asserts `published["type"]` but NOT `channel` for dwell_started/dwell_alert/approach/entity_track_updated/ai_action; detection_new/batch have no direct test at all (only via `test_batch_aggregator.py`, which mocks the broadcaster — `backend/tests/unit/core/test_websocket.py:373`) |
| 8 | **TG-broadcast-payload-literal-shape** (wrap dict `"data"` key, envelope `.get(None...)`, data_dict=None) | TEST-GAP | 20 | `xǁEventBroadcasterǁbroadcast_detection_batch__mutmut_4/10`, `xǁEventBroadcasterǁbroadcast_detection_new__mutmut_7` | Same direct-call gap as #7 |
| 9 | **TG-batch-envelope-guard** (`if "type" not in batch_data:` → "TYPE"/"XXtypeXX"/`in`; `batch_data = None`) | TEST-GAP | 23 | `xǁEventBroadcasterǁbroadcast_batch_analysis_completed__mutmut_1/2`, `xǁEventBroadcasterǁbroadcast_detection_new__mutmut_2` | The wrap-when-untyped path is never exercised directly |
| 10 | **TG-validation-pipeline-bypass** (`validated_*`/`model_validate(...)` → None) | TEST-GAP | 8 | `xǁEventBroadcasterǁbroadcast_detection_batch__mutmut_18/19/20` | Would raise ValueError at publish time — only killed by a direct happy-path call |
| 11 | **TG-stop-shutdown-payload-literal** (`system.shutdown` json + send_text args in `stop()` L675-685) | TEST-GAP | 17 | `xǁEventBroadcasterǁstop__mutmut_11/12/13` | `test_event_broadcaster.py::test_stop_unsubscribes_and_disconnects_all_connections` (L239-261) never inspects what `ws.send_text` received |
| 12 | **TG-degraded-payload-literal** (`_broadcast_degraded_state` dict keys/values L2211-2221) | TEST-GAP | 20 | `xǁEventBroadcasterǁ_broadcast_degraded_state__mutmut_10..16` | `test_event_broadcaster.py::test_broadcast_degraded_state_to_clients` (L2058-2081) asserts only substrings `"service_status" in msg` / `"degraded" in msg` — survives key renames & value casing where substring still appears |
| 13 | **TG-supervisor-handle-dead-listener** (return-flag swaps 4, `+=1` arithmetic 3, restart-task 4, resubscribe-cond 1) | TEST-GAP | 12 | `xǁEventBroadcasterǁ_handle_dead_listener__mutmut_10/16/17/25` | `test_event_broadcaster.py::test_supervise_listener_detects_dead_listener` (L1345) / `respects_max_attempts` (L1388) assert only log substrings + `_is_listening`; never the return value, `_recovery_attempts` value, or the restarted task identity |
| 14 | **TG-supervisor-handle-healthy-listener** (flag→False/None 2, `>0` gate →`>=0`/`>1` 2) | TEST-GAP | 4 | `xǁEventBroadcasterǁ_handle_healthy_listener__mutmut_1/3` | `test_supervise_listener_resets_recovery_on_healthy` (L1420) starts at 3 so `>1` still resets; nothing asserts `_listener_healthy is True` after the call; `>=0` spams the recovery log when already 0 — unasserted |
| 15 | **TG-stop-listener-health-flag** (`stop()` `_listener_healthy=False`→True/None) | TEST-GAP | 2 | `xǁEventBroadcasterǁstop__mutmut_3/4` | No stop() test touches `_listener_healthy`/`is_listener_healthy` |
| 16 | **TG-init-circuit-breaker-config** (ctor kwargs to `WebSocketCircuitBreaker`: threshold 5→removed(3)/None, timeout 30→31/None, half_open/success 1→2/None) + `_listener_healthy` init None/True | TEST-GAP | 11 | `xǁEventBroadcasterǁ__init____mutmut_12/13/22` | No test reads `broadcaster.circuit_breaker.failure_threshold` / `_recovery_timeout` / `_half_open_max_calls` / `_success_threshold`; some None-arg mutants also blow up only in half-open state |
| 17 | **TG-metrics-counter-reset** (`+=`→`=1` in record_success/record_failure + `record_failure(attempt+1)`→`attempt±1`) | TEST-GAP | 5 | `xǁBroadcastRetryMetricsǁrecord_failure__mutmut_3/6`, `x_broadcast_with_retry__mutmut_68/69`, `xǁBroadcastRetryMetricsǁrecord_success__mutmut_10` | `test_broadcast_retry.py::test_record_failure` (L62) records ONE failure then asserts `== 1` — reset-vs-increment indistinguishable; `retry_counts[0]` checked once-only (L49) |
| 18 | **TG-metrics-success_rate-guard** (`>0`→`>1`, `+`→`-` in guard) | TEST-GAP | 2 | `xǁBroadcastRetryMetricsǁto_dict__mutmut_17/19` | `test_to_dict` (L72) uses s=2,f=1 (1/3 vs -1/3 both ≈ guarded?) — mutant `-` gives guard-false 0.0 only when f>s; `test_success_rate_zero_broadcasts` (L89) only checks the 0/0 case |
| 19 | **TG-record-ack-baseline-one** (`_client_acks.get(ws, 0)`→`get(ws, 1)`) | TEST-GAP | 1 | `xǁEventBroadcasterǁrecord_ack__mutmut_6` | `test_message_buffer.py::test_record_ack_stores_sequence` (L277) acks 42; first-ACK-of-0 (legit seq-0) never acked — mutant silently refuses to store seq 0 |
| 20 | **TG-client-format-negotiation** (`connect`: `_client_formats[ws]=None`; `disconnect`: `pop(None,None)` leaks entry) | TEST-GAP | 2 | `xǁEventBroadcasterǁconnect__mutmut_2`, `xǁEventBroadcasterǁdisconnect__mutmut_5` | `test_event_broadcaster.py::test_connect_accepts_websocket_and_registers` (L363) never asserts `_client_formats`/`get_client_format`; no disconnect format-cleanup test |
| 21 | **TG-background-alert-lambda-args** (`broadcast_alert(alert_data, event_type)` arg→None/drop) | TEST-GAP | 4 | `x_broadcast_alert_with_retry_background__mutmut_10/11/12/13` | `test_broadcast_retry.py::test_successful_broadcast` (L289) asserts `assert_called_once()` only — not with-args |
| 22 | **TG-resubscribe-true-on-failure** (`_resubscribe_for_supervisor` returns True on failure) | TEST-GAP | 1 | `xǁEventBroadcasterǁ_resubscribe_for_supervisor__mutmut_4` | Covered via `test_event_broadcaster.py` (only 1 covering test, supervisor happy-path); failure path asserts nothing |
| 23 | **TG-listen-recovery-gate** (`_recovery_attempts <= MAX`→`<`) | TEST-GAP | 1 | `xǁEventBroadcasterǁ_listen_for_events__mutmut_43` | `test_listen_for_events_recovery_bounded` (L1233) never lands exactly on attempts==MAX-1→MAX to see the extra restart |
| 24 | LV-send-all-stats-flags (`track_stats=`, `return_exceptions=`, `format=` kwargs) | LOW-VALUE | 8 | `xǁEventBroadcasterǁ_send_to_all_clients__mutmut_19/20/22` | Compression-stats flags + gather mode; real behavior only under multi-client failure/telemetry nobody asserts |
| 25 | TG-send-all-format-payload (`_client_formats.get(None...)`, message_dict/str=None) | TEST-GAP | 5 | `xǁEventBroadcasterǁ_send_to_all_clients__mutmut_4/11/26` | Format-negotiation cache path only exercised in test_event_broadcaster.py with default-JSON clients |
| 26 | LV-listener-backoff-constants (`2**`→`3**`, cap 30→31), LV-supervisor-sleep-arg, LV-resubscribe/listen-channel-arg, LV-send-single-if-or, LV-retry-log-gates(2), LV-background-message-type(1) | LOW-VALUE | 9 | `xǁEventBroadcasterǁ_listen_for_events__mutmut_50/53`, `xǁEventBroadcasterǁ_supervise_listener__mutmut_5`, `x_broadcast_with_retry__mutmut_10/11` | Timing/backoff constants & sleep args — asserted nowhere and timing asserts would be flaky; recommend baseline exclusion |
| | **TOTAL** | | **590** | | TG=155, LV=143, EQ=292 |

## Drafted tests (top 6 TEST-GAP clusters) — // UNVERIFIED - not yet run red/green

TDD procedure (same for all): apply each mutant of the target cluster to the source, run the new test — it must FAIL (red); revert to original, run — must PASS (green).

### T1 — `test_stop_sends_system_shutdown_notice` (kills cluster 11, TG-stop-shutdown-payload-literal, 17)
Target file: `backend/tests/unit/services/test_event_broadcaster.py` (after `test_stop_unsubscribes_and_disconnects_all_connections`, L262).

```python
@pytest.mark.asyncio
async def test_stop_sends_system_shutdown_notice() -> None:
    """NEM-4987: stop() must send a system.shutdown notice with reconnect=True
    to every connected client BEFORE disconnecting them."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._is_listening = True
    broadcaster._pubsub = _FakePubSub()

    ws1 = AsyncMock()
    ws2 = AsyncMock()
    ws1.close = AsyncMock(return_value=None)
    ws2.close = AsyncMock(return_value=None)
    broadcaster._connections = {ws1, ws2}  # type: ignore[assignment]

    await broadcaster.stop()

    for ws in (ws1, ws2):
        ws.send_text.assert_awaited_once()
        payload = json.loads(ws.send_text.await_args.args[0])
        assert payload["type"] == "system.shutdown"
        assert payload["data"]["reason"] == "Server shutting down"
        assert payload["data"]["reconnect"] is True
```
Add `import json` to the test file header. Red on any key/value casing or None-payload mutant (`json.loads(None)` raises; `"type"` key rename → KeyError; `reconnect: False`/`"SYSTEM.SHUTDOWN"` → assert fails). Green on original.

### T2 — `test_broadcast_degraded_state_payload_structure` (kills cluster 12, TG-degraded-payload-literal, 20)
Target file: `backend/tests/unit/services/test_event_broadcaster.py` (next to `test_broadcast_degraded_state_to_clients`, L2058).

```python
@pytest.mark.asyncio
async def test_broadcast_degraded_state_payload_structure() -> None:
    """Degraded notice must be a structured service_status message:
    type/data.service/data.status/data.message/data.circuit_state — not just
    substring-matched text."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    ws = AsyncMock()
    ws.send_text = AsyncMock(return_value=None)
    ws.close = AsyncMock(return_value=None)
    broadcaster._connections = {ws}  # type: ignore[assignment]

    await broadcaster._broadcast_degraded_state()

    ws.send_text.assert_awaited_once()
    msg = json.loads(ws.send_text.await_args.args[0])
    assert msg["type"] == "service_status"
    assert msg["data"]["service"] == "event_broadcaster"
    assert msg["data"]["status"] == "degraded"
    assert isinstance(msg["data"]["message"], str) and msg["data"]["message"]
    assert msg["data"]["circuit_state"] in {"closed", "open", "half_open"}
```
Kills every key-rename/case mutant (subscript on renamed key raises, value casing fails assert). Green on original.

### T3 — `TestDirectDetectionBroadcasting` (kills clusters 7+8+9+10 = 68: publish args, payload literal shape, envelope guard, validation bypass)
Target file: `backend/tests/unit/services/test_event_broadcaster.py` (new class after L2114).

```python
class TestDirectDetectionBroadcasting:
    """Direct-call coverage for broadcast_detection_new / broadcast_detection_batch.

    These were only exercised indirectly via batch_aggregator tests, which mock
    the broadcaster — so publish() args, the envelope guard and the validation
    pipeline were never asserted end to end.
    """

    _NEW = {
        "detection_id": 123,
        "batch_id": "batch_abc123",
        "camera_id": "front_door",
        "label": "person",
        "confidence": 0.95,
        "timestamp": "2026-01-13T12:00:00.000Z",
    }

    @pytest.mark.asyncio
    async def test_broadcast_detection_new_publishes_validated_envelope(self) -> None:
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        count = await broadcaster.broadcast_detection_new(dict(self._NEW))

        assert count == 1
        redis.publish.assert_awaited_once()
        channel, published = redis.publish.await_args.args
        assert channel == broadcaster.channel_name
        assert published["type"] == "detection.new"
        assert published["data"]["detection_id"] == 123
        assert published["data"]["label"] == "person"

    @pytest.mark.asyncio
    async def test_broadcast_detection_new_with_full_envelope(self) -> None:
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        envelope = {"type": "detection.new", "data": dict(self._NEW)}
        count = await broadcaster.broadcast_detection_new(envelope)

        assert count == 1
        _, published = redis.publish.await_args.args
        assert published["type"] == "detection.new"
        assert published["data"]["batch_id"] == "batch_abc123"

    @pytest.mark.asyncio
    async def test_broadcast_detection_batch_publishes_validated_envelope(self) -> None:
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        batch = {
            "batch_id": "batch_abc123",
            "camera_id": "front_door",
            "detection_ids": [123, 124],
            "detection_count": 2,
            "started_at": "2026-01-13T12:00:00.000Z",
            "closed_at": "2026-01-13T12:01:30.000Z",
            "close_reason": "timeout",
        }
        count = await broadcaster.broadcast_detection_batch(batch)

        assert count == 1
        channel, published = redis.publish.await_args.args
        assert channel == broadcaster.channel_name
        assert published["type"] == "detection.batch"
        assert published["data"]["detection_count"] == 2
        assert published["data"]["close_reason"] == "timeout"

    @pytest.mark.asyncio
    async def test_broadcast_detection_new_rejects_invalid_payload(self) -> None:
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        bad = dict(self._NEW)
        del bad["confidence"]
        with pytest.raises(ValueError):
            await broadcaster.broadcast_detection_new(bad)
        redis.publish.assert_not_awaited()
```
The happy-path `count == 1` + `channel ==` asserts kill publish-arg mutants (channel→None, payload→None, return forced); `published["data"]` subscript kills envelope-guard `.get("data", None)` and `data_dict=None` mutants that reach publish; `pytest.raises(ValueError)` + `publish.assert_not_awaited()` kills validation-pipeline-bypass mutants (a None `validated_data` produces a ValidationError→ValueError path the original raises through). Green on original.

### T4 — `TestSupervisorListenerFlags` (kills clusters 13+14+15+22 = 19)
Target file: `backend/tests/unit/services/test_event_broadcaster.py` (new class near the supervisor tests, ~L1465).

```python
class TestSupervisorListenerFlags:
    """_handle_dead_listener / _handle_healthy_listener / stop() flags and return values.

    Existing supervisor tests assert log substrings only; the boolean contract
    (break-the-loop vs keep-retrying) and the recovery counter arithmetic were
    never asserted.
    """

    @pytest.mark.asyncio
    async def test_handle_dead_listener_recovers_with_exact_attempt_increment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
        broadcaster._is_listening = True
        broadcaster._pubsub = _FakePubSub()
        broadcaster._recovery_attempts = 2

        result = await broadcaster._handle_dead_listener()

        assert result is False  # keep supervising
        assert broadcaster._recovery_attempts == 3  # exactly +1
        assert broadcaster._listener_task is not None
        assert broadcaster._listener_healthy is True
        broadcaster._listener_task.cancel()

    @pytest.mark.asyncio
    async def test_handle_dead_listener_gives_up_at_max(self) -> None:
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
        broadcaster._is_listening = True
        broadcaster._pubsub = _FakePubSub()
        broadcaster._recovery_attempts = broadcaster.MAX_RECOVERY_ATTEMPTS

        result = await broadcaster._handle_dead_listener()

        assert result is True  # supervision loop must break
        assert broadcaster.is_degraded() is True

    @pytest.mark.asyncio
    async def test_handle_dead_listener_resubscribes_when_pubsub_missing(
        self,
    ) -> None:
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
        broadcaster._is_listening = True
        broadcaster._pubsub = None

        result = await broadcaster._handle_dead_listener()

        assert result is False
        redis.subscribe.assert_awaited_once_with(broadcaster.channel_name)
        assert broadcaster._listener_task is not None
        broadcaster._listener_task.cancel()

    @pytest.mark.asyncio
    async def test_handle_healthy_listener_sets_flags_without_spurious_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
        broadcaster._recovery_attempts = 0

        await broadcaster._handle_healthy_listener()

        assert broadcaster._listener_healthy is True
        assert broadcaster.is_listener_healthy() is False  # not listening yet
        # recovery-attempt 0 must NOT log a "recovered" message
        assert not any("recovered" in r.message.lower() for r in caplog.records)

    @pytest.mark.asyncio
    async def test_handle_healthy_listener_resets_single_recovery_attempt(self) -> None:
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
        broadcaster._recovery_attempts = 1  # exactly 1: kills '>1' gate mutant

        await broadcaster._handle_healthy_listener()

        assert broadcaster._recovery_attempts == 0

    @pytest.mark.asyncio
    async def test_stop_marks_listener_unhealthy(self) -> None:
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
        broadcaster._is_listening = True

        await broadcaster.stop()

        assert broadcaster._listener_healthy is False
        assert broadcaster.is_listener_healthy() is False

    @pytest.mark.asyncio
    async def test_resubscribe_for_supervisor_reports_failure(self) -> None:
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
        redis.subscribe = AsyncMock(side_effect=ConnectionError("redis down"))

        ok = await broadcaster._resubscribe_for_supervisor()

        assert ok is False  # mutant returns True → supervision wrongly proceeds
        assert broadcaster._pubsub is None
```
Note: `is_listener_healthy()` returning exactly `False` (not `None`) kills the `= None` flag mutants via `is False`/`is True` identity checks. `test_handle_dead_listener_gives_up_at_max` returns-True mutants (`return False`) flip the assert. Red/green per mutant.

### T5 — `test_broadcast_metrics_accumulate_across_events` + `test_broadcaster_circuit_breaker_configuration` (kills clusters 17+18+16 = 18)
Target files: `backend/tests/unit/services/test_broadcast_retry.py` (metrics test, class `TestBroadcastRetryMetrics`, after L95) and `backend/tests/unit/services/test_event_broadcaster.py` (config test, near L1777 `test_get_circuit_state`).

```python
def test_broadcast_metrics_accumulate_across_events(self) -> None:
    """Success/failure counters must ACCUMULATE across repeated events —
    a mutant that reassigns (=1) instead of increments (+=1) passes the
    single-event tests but breaks here."""
    metrics = BroadcastRetryMetrics()

    metrics.record_success(attempts=1)
    metrics.record_success(attempts=1)
    metrics.record_failure(attempts=4)
    metrics.record_failure(attempts=4)

    assert metrics.total_attempts == 10  # 1 + 1 + 4 + 4
    assert metrics.successful_broadcasts == 2
    assert metrics.failed_broadcasts == 2
    assert metrics.retries_exhausted == 2
    assert metrics.retry_counts[0] == 2

    result = metrics.to_dict()
    assert result["success_rate"] == 0.5

def test_success_rate_with_single_success(self) -> None:
    """Guard `>0` vs `>1`: one broadcast must already yield a real rate."""
    metrics = BroadcastRetryMetrics()
    metrics.record_success(attempts=1)

    assert metrics.to_dict()["success_rate"] == 1.0

def test_all_failures_success_rate_is_zero(self) -> None:
    """Guard `+`→`-` mutant: s=0,f=2 gives (0-2)>0 false → same 0.0, but
    s=1,f=2 must be 1/3 not guarded away."""
    metrics = BroadcastRetryMetrics()
    metrics.record_failure(attempts=4)
    metrics.record_success(attempts=1)

    assert abs(metrics.to_dict()["success_rate"] - (1 / 3)) < 1e-9
```

```python
def test_broadcaster_circuit_breaker_configuration() -> None:
    """Circuit breaker must be tuned to MAX_RECOVERY_ATTEMPTS with the
    documented one-shot half-open policy."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    breaker = broadcaster.circuit_breaker

    assert breaker.failure_threshold == EventBroadcaster.MAX_RECOVERY_ATTEMPTS
    assert breaker._recovery_timeout == 30.0
    assert breaker._half_open_max_calls == 1
    assert broadcaster._listener_healthy is False  # kills __init__ None/True mutant
    assert breaker._success_threshold == 1
```
(For the two `record_failure(attempt±1)` mutants in cluster 17 also assert `metrics.total_attempts == max_retries + 1` inside the existing failure path — `test_failure_after_all_retries` currently checks only counts; extend it with `assert metrics.total_attempts == 4`.)

### T6 — `TestAckAndFormatTracking` (kills clusters 19+20 = 3)
Target file: `backend/tests/unit/services/test_message_buffer.py` (append to the ACK class, after `test_acks_are_per_client` L317) — format part in `backend/tests/unit/services/test_event_broadcaster.py` (after `test_connect_accepts_websocket_and_registers` L404).

```python
def test_record_ack_stores_zero_sequence(
    self, broadcaster: EventBroadcaster, mock_websocket: MagicMock
) -> None:
    """Sequence 0 is a legal first ACK and must be stored — a baseline default
    of 1 instead of 0 silently drops it."""
    broadcaster.record_ack(mock_websocket, 0)

    assert mock_websocket in broadcaster._client_acks
    assert broadcaster.get_last_ack(mock_websocket) == 0
```

```python
@pytest.mark.asyncio
async def test_connect_records_client_format_and_disconnect_clears_it() -> None:
    """NEM-3737: connect() must store the negotiated format per client, and
    disconnect() must clean the entry up (no dict leak)."""
    from backend.api.schemas.websocket import SerializationFormat

    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    ws = AsyncMock()

    await broadcaster.connect(ws, format=SerializationFormat.MSGPACK)
    assert broadcaster.get_client_format(ws) is SerializationFormat.MSGPACK
    assert broadcaster._client_formats[ws] is SerializationFormat.MSGPACK

    await broadcaster.disconnect(ws)
    assert ws not in broadcaster._client_formats
```

## Where the covering tests fall short (file:line)

| Cluster | Test that executes but under-asserts | Misses |
|---|---|---|
| shutdown notice (11) | `test_event_broadcaster.py:239` `test_stop_unsubscribes...` | `ws.send_text` payload at all (stop also sends via L683) |
| degraded payload (12) | `test_event_broadcaster.py:2058` | structural keys; uses substring `in msg` |
| detection publish/envelope/validation (68) | `test_batch_aggregator.py` (indirect; broadcaster mocked, see `test_event_broadcaster.py` absence) | direct invocation of broadcast_detection_new/batch |
| supervisor flags (13/14/15/22) | `test_event_broadcaster.py:1345/1388/1420` | return values, `_recovery_attempts` arithmetic, task identity, `_listener_healthy` |
| init breaker (16) | `test_event_broadcaster.py:1777` `test_get_circuit_state` | threshold/timeout/half-open config values |
| metrics accumulate (17/18) | `test_broadcast_retry.py:40-95` | repeated events (>1 record_* call), 1-of-1 and 1-of-3 success_rate cases |
| record_ack seq 0 (19) | `test_message_buffer.py:277-306` | storing sequence 0 |
| client format map (20) | `test_event_broadcaster.py:363` | `_client_formats` after connect/disconnect |
| zone publish channel (7) | `test_event_broadcaster_new_events.py:80-120` | `channel` arg for dwell_started/dwell_alert/approach/entity_track_updated/ai_action (crossing/entity_matched/ai_threat already assert it) |

**Baseline hygiene recommendation**: clusters 1+4 (278 EQ/LV log-text mutants) and cluster 2 (68 model_dump mutants) are 60% of this module's survivors. Consider mutmut config exclusions for logger-call text args, or accept them as documented EQUIVALENT in the score.
