# WP4.4 Triage Dossier — `backend/services/pg_notify_listener.py`

**Run context:** WP4.3 finding feed → WP4.4. Mutant keys from
`mutants/backend/services/pg_notify_listener.py.meta` (`exit_code_by_key`, `exit_code == 0` = survived).

| Metric                      | Value                        |
| --------------------------- | ---------------------------- |
| Total mutant keys           | 473                          |
| Survived (`exit_code == 0`) | **127**                      |
| Killed                      | 98                           |
| Not yet checked (`null`)    | 248 — excluded per task spec |

**Cluster counts sum to 127** (verified twice: once by mutant-index ranges, once by diff-text content —
see "Verification" at the bottom). Classification totals: **TEST-GAP 81, LOW-VALUE 27, EQUIVALENT 19**.

## Covering test file

`backend/tests/unit/services/test_pg_notify_listener.py` (980 lines) is the **only** covering test file.
Test-group → line map (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`):

| Function                 | Tests (file:line)                                                                                                                                                                             |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `_handle_event_new`      | `TestPgNotifyListenerHandlers::test_handle_event_new` (:332), `test_full_notification_flow` (:943), `test_handle_notification_no_redis` (:539), `test_handle_notification_redis_error` (:554) |
| `_handle_event_update`   | `test_handle_event_update` (:371), `test_handle_event_update_redis_error` (:404)                                                                                                              |
| `_handle_detection_new`  | `test_handle_detection_new` (:426), `test_handle_detection_new_redis_error` (:461)                                                                                                            |
| `_handle_alert_new`      | `test_handle_alert_new` (:483), `test_handle_alert_new_redis_error` (:517)                                                                                                                    |
| `_notification_callback` | `TestPgNotifyListenerCallback::test_notification_callback_creates_task` (:673)                                                                                                                |
| `get_status`             | `TestPgNotifyListenerHealth::test_get_status` (:716), `test_get_status_no_connection` (:735)                                                                                                  |
| `start`                  | `TestPgNotifyListenerStartStop::test_start_success` (:272), `test_start_already_running` (:287)                                                                                               |
| `stop`                   | `test_stop_cleanup` (:298), `test_start_success` (:272)                                                                                                                                       |
| `get_pg_notify_listener` | `TestGlobalInstance::test_get_pg_notify_listener_creates_instance` (:890), `test_get_pg_notify_listener_returns_same_instance` (:906)                                                         |

**The dominant shape of this module's survivors:** every handler test asserts
`assert_called_once()` + `type` + 2-3 selected `data` fields, but never the `source` envelope field, never
the remaining data fields, never the `extra=` debug-log payload, and never the full message dict. mutmut's
string mutations (case flips, `XX..XX` wrappers, `None`) land almost entirely in the un-asserted remainder.

## Per-cluster table

| #   | Function                 | Diff pattern                                                                                             | Count | Class      | Example keys (`backend.services.pg_notify_listener.` prefix omitted)                                             |
| --- | ------------------------ | -------------------------------------------------------------------------------------------------------- | ----- | ---------- | ---------------------------------------------------------------------------------------------------------------- |
| C1  | 3 handlers               | envelope `source` key **or** value changed (`"XXsourceXX"`, `"SOURCE"`, `"XXpg_notifyXX"`, `"PG_NOTIFY`) | 12    | TEST-GAP   | `…_handle_alert_new__mutmut_7`, `…_handle_detection_new__mutmut_9`, `…_handle_event_update__mutmut_10`           |
| C2  | `_handle_alert_new`      | published `data` field keys (`event_id`, `rule_id`, `status`) or their source lookups mutated            | 15    | TEST-GAP   | `…_handle_alert_new__mutmut_18`, `…_handle_alert_new__mutmut_25`, `…_handle_alert_new__mutmut_37`                |
| C3  | `_handle_detection_new`  | same for `camera_id`, `timestamp`/`detected_at`                                                          | 10    | TEST-GAP   | `…_handle_detection_new__mutmut_18`, `…_handle_detection_new__mutmut_35`, `…_handle_detection_new__mutmut_37`    |
| C4  | `_handle_event_update`   | same for `id`, `event_id`, `risk_score`, `risk_level`, `summary`                                         | 25    | TEST-GAP   | `…_handle_event_update__mutmut_13`, `…_handle_event_update__mutmut_25`, `…_handle_event_update__mutmut_37`       |
| C5  | 3 handlers               | `redis.publish(settings.redis_event_channel, …)` → `redis.publish(None, …)`                              | 5     | TEST-GAP   | `…_handle_alert_new__mutmut_39`, `…_handle_detection_new__mutmut_44`, `…_handle_event_update__mutmut_44`         |
| C6  | `_notification_callback` | `create_task` arg mutated: `None`, `channel→None`, `payload→None`, dropped args                          | 5     | TEST-GAP   | `…_notification_callback__mutmut_1`, `…_notification_callback__mutmut_4`, `…_notification_callback__mutmut_5`    |
| C7  | `get_status`             | `… and not conn.is_closed() if conn else False` → `or True` guard / `and`→`or`                           | 2     | TEST-GAP   | `…get_status__mutmut_8`, `…get_status__mutmut_9`                                                                 |
| C8  | `get_pg_notify_listener` | `PgNotifyListener(redis_client=…, broadcaster=…)` kwargs → `None` / dropped                              | 4     | TEST-GAP   | `x_get_pg_notify_listener__mutmut_3`, `x_get_pg_notify_listener__mutmut_4`, `x_get_pg_notify_listener__mutmut_6` |
| C9  | `start`                  | `self._reconnect_attempts = 0` → `None` / `1`                                                            | 2     | TEST-GAP   | `…start__mutmut_7`, `…start__mutmut_8`                                                                           |
| C14 | `stop`                   | `contextlib.suppress(Exception)` → `suppress(None)` (close error now propagates)                         | 1     | TEST-GAP   | `…stop__mutmut_7`                                                                                                |
| C10 | 3 handlers               | `logger.debug(msg, extra={…})` second arg → `None` / removed / its keys mutated                          | 22    | LOW-VALUE  | `…_handle_alert_new__mutmut_45`, `…_handle_event_update__mutmut_50`, `…_handle_detection_new__mutmut_55`         |
| C11 | 3 handlers               | `logger.error(f"Failed to publish …")` → `logger.error(None)` (inside Redis-failure handler)             | 5     | LOW-VALUE  | `…_handle_alert_new__mutmut_43`, `…_handle_detection_new__mutmut_43`, `…_handle_event_update__mutmut_48`         |
| C12 | 3 handlers               | debug log message **text** only (`"XXPublished…XX"`, case variants)                                      | 7     | EQUIVALENT | `…_handle_alert_new__mutmut_49`, `…_handle_event_update__mutmut_55`, `…_handle_detection_new__mutmut_50`         |
| C13 | `start`, `stop`          | lifecycle log text/None only (`"PgNotifyListener started/stopped/already running"`)                      | 12    | EQUIVALENT | `…start__mutmut_1`, `…start__mutmut_14`, `…stop__mutmut_9`                                                       |

### Classification rationale

- **TEST-GAP (81):** the mutation changes observable behavior (the JSON envelope a WebSocket/Redis
  consumer receives, or lifecycle state/exception propagation), and the existing tests **do execute the
  mutated line** — they call the handler/lifecycle method and assert _some_ of it — but they never assert
  the specific element the mutant corrupts. E.g. `test_handle_event_update` (:371) reads the full
  `message` dict from `publish.call_args` yet asserts only `message["type"]` and
  `message["data"]["reviewed"]`, leaving the other five data fields un-asserted (C4, 25 survivors — the
  single largest gap). C5 is a weaker variant of an assertion that exists for `_handle_event_new`
  (`test_handle_event_new`:361 `assert call_args[0][0] == "security_events"`) but was **never copied** to
  the update/detection/alert tests.
- **LOW-VALUE (27):** `extra=` structured-log payloads and `logger.error(None)` message text. Real
  changes, but they only alter log records on the `debug`/`error` path — no test asserts log content, and
  the repo doesn't test logging text elsewhere in this suite. C11 is arguably a mild gap (losing the error
  text on a Redis failure degrades diagnosis) but not worth an assertion in a mutation baseline.
- **EQUIVALENT (22):** pure message-string mutations (case flips, `XX…XX` wrapping) on info/warning/debug
  lifecycle logs — semantically no-ops for program behavior.

**Kill math for WP4.4:** the drafted tests below kill C1+C2+C3+C4+C5 (67) + C6+C7 (7) + C8+C9+C14 (7)
= **all 81 TEST-GAP survivors**. LOW-VALUE clusters are left deliberately (mutmut "unkillable by design" bucket);
EQUIVALENTs can go to a `# pragma: no mutate` / mutmut config exclusion conversation later.

## Drafted tests (append to `backend/tests/unit/services/test_pg_notify_listener.py`)

// UNVERIFIED — not yet run red/green. TDD procedure for each: run against the mutant copy (the
cluster's mutated variant) and confirm the new assert FAILS, then against `backend/` original and
confirm it PASSES.

### 1. `test_handle_event_update_full_message_contract` — kills C4 (25), contributes to C1 + C5

```python
    @pytest.mark.asyncio
    async def test_handle_event_update_full_message_contract(self) -> None:
        """Every field the event_update contract promises must survive mutation.

        Existing test_handle_event_update only checks type/reviewed, so 25 mutants
        in the message dict's other fields survived. Assert the full envelope and
        the full data dict, and the publish channel.
        """
        mock_redis = AsyncMock()
        listener = PgNotifyListener(redis_client=mock_redis)

        payload = PgNotifyPayload(
            channel="events_update",
            operation="UPDATE",
            table="events",
            data={
                "id": 7,
                "risk_score": 85,
                "risk_level": "critical",
                "summary": "Person with weapon detected",
                "reviewed": True,
            },
        )

        with patch(
            "backend.services.pg_notify_listener.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value.redis_event_channel = "security_events"

            await listener._handle_event_update(payload)

            mock_redis.publish.assert_called_once()
            channel, message = mock_redis.publish.call_args[0]
            assert channel == "security_events"  # kills the publish(None) mutant
            assert message == {  # whole-dict equality kills every key/value mutant
                "type": "event_update",
                "source": "pg_notify",
                "data": {
                    "id": 7,
                    "event_id": 7,
                    "risk_score": 85,
                    "risk_level": "critical",
                    "summary": "Person with weapon detected",
                    "reviewed": True,
                },
            }
```

### 2. `test_handle_detection_new_full_message_contract` — kills C3 (10), contributes to C1 + C5

```python
    @pytest.mark.asyncio
    async def test_handle_detection_new_full_message_contract(self) -> None:
        """Full detection.new envelope: type/source plus all five data fields.

        Existing test checked type/detection_id/label/confidence but not source,
        camera_id or timestamp — 10 mutants survived there.
        """
        mock_redis = AsyncMock()
        listener = PgNotifyListener(redis_client=mock_redis)

        payload = PgNotifyPayload(
            channel="detections_new",
            operation="INSERT",
            table="detections",
            data={
                "id": 100,
                "camera_id": "back_yard",
                "object_type": "person",
                "confidence": 0.95,
                "detected_at": "2026-01-23T12:30:00Z",
            },
        )

        with patch(
            "backend.services.pg_notify_listener.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value.redis_event_channel = "security_events"

            await listener._handle_detection_new(payload)

            channel, message = mock_redis.publish.call_args[0]
            assert channel == "security_events"
            assert message == {
                "type": "detection.new",
                "source": "pg_notify",
                "data": {
                    "detection_id": 100,
                    "camera_id": "back_yard",
                    "label": "person",
                    "confidence": 0.95,
                    "timestamp": "2026-01-23T12:30:00Z",
                },
            }
```

### 3. `test_handle_alert_new_full_message_contract` — kills C2 (15), contributes to C1 + C5

```python
    @pytest.mark.asyncio
    async def test_handle_alert_new_full_message_contract(self) -> None:
        """Full alert_created envelope: type/source plus all five data fields.

        Existing test checked type/id/severity only; event_id, rule_id, status and
        source were un-asserted, so 15 mutants survived.
        """
        mock_redis = AsyncMock()
        listener = PgNotifyListener(redis_client=mock_redis)

        payload = PgNotifyPayload(
            channel="alerts_new",
            operation="INSERT",
            table="alerts",
            data={
                "id": "alert-uuid-123",
                "event_id": 1,
                "rule_id": "rule-uuid-456",
                "severity": "high",
                "status": "pending",
            },
        )

        with patch(
            "backend.services.pg_notify_listener.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value.redis_event_channel = "security_events"

            await listener._handle_alert_new(payload)

            channel, message = mock_redis.publish.call_args[0]
            assert channel == "security_events"
            assert message == {
                "type": "alert_created",
                "source": "pg_notify",
                "data": {
                    "id": "alert-uuid-123",
                    "event_id": 1,
                    "rule_id": "rule-uuid-456",
                    "severity": "high",
                    "status": "pending",
                },
            }
```

### 4. `test_handle_event_new_full_message_contract` — kills the remaining C1 member + future drift

(`_handle_event_new` had no surviving keys — its test already asserts 3 fields — but its envelope still
carries 8 fields and 4 are un-asserted; locking the full contract here prevents the same gap re-opening.)

```python
    @pytest.mark.asyncio
    async def test_handle_event_new_full_message_contract(self) -> None:
        """event envelope contract is pinned in full (source + every data field)."""
        mock_redis = AsyncMock()
        listener = PgNotifyListener(redis_client=mock_redis)

        payload = PgNotifyPayload(
            channel="events_new",
            operation="INSERT",
            table="events",
            data={
                "id": 1,
                "batch_id": "batch_123",
                "camera_id": "front_door",
                "risk_score": 75,
                "risk_level": "high",
                "summary": "Person detected",
                "started_at": "2026-01-23T12:00:00Z",
            },
        )

        with patch(
            "backend.services.pg_notify_listener.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value.redis_event_channel = "security_events"

            await listener._handle_event_new(payload)

            channel, message = mock_redis.publish.call_args[0]
            assert channel == "security_events"
            assert message == {
                "type": "event",
                "source": "pg_notify",
                "data": {
                    "id": 1,
                    "event_id": 1,
                    "batch_id": "batch_123",
                    "camera_id": "front_door",
                    "risk_score": 75,
                    "risk_level": "high",
                    "summary": "Person detected",
                    "started_at": "2026-01-23T12:00:00Z",
                },
            }
```

### 5. `test_notification_callback_forwards_channel_and_payload` — kills C6 (5)

```python
    def test_notification_callback_forwards_channel_and_payload(self) -> None:
        """The asyncpg callback must schedule the handler with BOTH real args.

        Existing test only asserts create_task was called once, so 5 mutants that
        passed None / dropped args survived (those crash or misroute at runtime).
        """
        listener = PgNotifyListener()
        mock_connection = MagicMock()
        payload = json.dumps({"operation": "INSERT", "table": "events", "data": {"id": 1}})

        with patch("asyncio.create_task", autospec=True) as mock_create_task:
            listener._notification_callback(mock_connection, 12345, "events_new", payload)

            mock_create_task.assert_called_once()
            coro = mock_create_task.call_args[0][0]
            # _handle_notification is a coroutine function: inspect its bound args
            assert coro.__qualname__.endswith("_handle_notification")
            cr_frame = coro.cr_frame
            assert cr_frame is not None, "callback scheduled something other than _handle_notification"
            assert cr_frame.f_locals["channel"] == "events_new"
            assert cr_frame.f_locals["payload"] == payload
            coro.close()  # never awaited — silence the 'never awaited' warning
```

### 6. `test_get_status_connected_false_when_connection_closed` — kills C7 (2)

```python
    def test_get_status_connected_false_when_connection_closed(self) -> None:
        """connected must be False when the connection is closed, True only when open.

        Existing get_status tests cover open and None connections but never a
        CLOSED one — so `and`->`or` and the `if conn else False` -> `or True`
        guard mutants both survived.
        """
        listener = PgNotifyListener()
        mock_connection = MagicMock()
        mock_connection.is_closed.return_value = True
        listener._connection = mock_connection

        assert listener.get_status()["connected"] is False
```

### 7. `test_get_pg_notify_listener_wires_dependencies` — kills C8 (4)

```python
    @pytest.mark.asyncio
    async def test_get_pg_notify_listener_wires_dependencies(self) -> None:
        """Singleton factory must pass redis/broadcaster through to the listener.

        Existing tests check creation + identity, so 4 mutants that swapped the
        kwargs for None (silently disabling Redis/WebSocket bridging) survived.
        """
        import backend.services.pg_notify_listener as module

        module._listener = None
        mock_redis = MagicMock()
        mock_broadcaster = MagicMock()
        try:
            listener = await get_pg_notify_listener(
                redis_client=mock_redis, broadcaster=mock_broadcaster
            )
            assert listener._redis is mock_redis
            assert listener._broadcaster is mock_broadcaster
        finally:
            module._listener = None
```

### 8. `test_start_resets_reconnect_attempts` — kills C9 (2)

```python
    @pytest.mark.asyncio
    async def test_start_resets_reconnect_attempts(self) -> None:
        """start() must reset the reconnect counter so a restart gets a fresh budget.

        test_start_success never inspects _reconnect_attempts, so `= 0` -> `= 1` /
        `= None` survived (a lingering counter makes the NEXT failure trip the max
        attempts limit early, or blow up on `1 >= None` comparison).
        """
        listener = PgNotifyListener()
        listener._reconnect_attempts = 5

        with patch.object(listener, "_connect", autospec=True):
            await listener.start()
            try:
                assert listener._reconnect_attempts == 0
            finally:
                await listener.stop()
```

### 9. `test_stop_survives_close_failure` — kills C14 (1)

```python
    @pytest.mark.asyncio
    async def test_stop_survives_close_failure(self) -> None:
        """stop() must suppress connection.close() errors (shutdown must not raise).

        test_stop_cleanup uses a clean AsyncMock, so contextlib.suppress(Exception)
        -> suppress(None) (which re-raises) survived.
        """
        listener = PgNotifyListener()
        listener._is_running = True

        mock_connection = AsyncMock()
        mock_connection.close.side_effect = OSError("connection already gone")
        listener._connection = mock_connection

        await listener.stop()  # must not raise

        assert listener._connection is None
```

## Verification

- Survivor set: re-extracted from `.meta` twice (JSONDecodeError retry not needed).
- Diffs: `uv run mutmut show <key>` spot-checked for 3 keys (`x_get_pg_notify_listener__mutmut_3`,
  `get_status__mutmut_9`, `stop__mutmut_7`) — byte-identical to the manual variant-vs-`__mutmut_orig`
  diffs from `mutants/backend/services/pg_notify_listener.py`; the manual method was used for all 127 to
  avoid hammering the concurrently-written cache.
- Cluster sums: index-range assignment and diff-text-content assignment independently both total 127, and
  their per-cluster disagreements were reconciled key-by-key (the only ambiguity was the debug-log
  message/extra boundary between C10/C12, resolved by whether the diff touches `extra=` vs the message
  string).
- `logger` is a stdlib `logging.Logger` (`backend/core/logging.py:1107` `get_logger` returns
  `logging.getLogger`-backed objects) → `logger.*(None)` raises `TypeError`, so C11/C13 survivors prove
  no test exercises those log lines (basis for the LOW-VALUE/EQUIVALENT split).
- No files in the repo were read-modified; only `/tmp/wp25/**` was written. No pytest/mutmut run invoked.
