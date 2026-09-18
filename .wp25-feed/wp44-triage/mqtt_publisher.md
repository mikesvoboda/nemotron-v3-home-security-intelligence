# WP4.4 Triage Dossier — `backend/services/mqtt_publisher.py`

**Surviving mutants:** 100 of 254 keys (exit_code 0). Diffs obtained via `uv run mutmut show <key>` (all resolved; one key needed a retry).
**Single covering test file:** `backend/tests/unit/services/test_mqtt_publisher.py` (614 lines) — every function's
`tests_by_mangled_function_name` entry points into it. Key regions:

| Region | file:line | What it asserts | What it misses |
| --- | --- | --- | --- |
| `TestTopicMapping::test_event_type_maps_to_topic` | test_mqtt_publisher.py:118-174 | 18 (event, flat payload, topic) pairs | nested-`data` fallbacks for severity/object_type/entity_type; `zone.approach`, `service.`, `worker.` routing; `alerts/unknown` default |
| `TestMQTTPublisher::test_publish_adds_timestamp_if_missing` | :301-314 | `"timestamp" in payload` | value (None/naive), and that a caller-supplied timestamp is NOT clobbered |
| `TestMQTTPublisherBroadcasterIntegration::test_register_with_broadcaster` | :481-488 | `register_mqtt_callback.assert_called_once()` | the argument (callback identity); the `else`/no-attribute branch never runs — `MagicMock` satisfies `hasattr` for ANY key, so the guard's key string is untested |
| `test_publish_error_logged_not_raised` | :291-298 | does not raise | that anything was logged at all |

No test in the file uses `caplog`, so all 61 log-record mutants are structurally unkillsable today.

## Cluster table (counts sum to 100)

| # | Cluster | Fn | Count | Keys (≤3) | Class |
| --- | --- | --- | --- | --- | --- |
| 1 | Timestamp injection: presence-check key string, value set to `None`, `datetime.now(None)` (naive, no UTC) | publish_event | 4 | publish_event__36, _37, _39 | TEST-GAP |
| 2 | `object_type` fallback chain: `or`→`and`, `get(None)` on nested dict, `"data"`/`"object_type"` key strings, `"unknown"` default | get_topic | 9 | get_topic__53, _58, _65 | TEST-GAP |
| 3 | `entity_type` fallback chain: same six mutation shapes | get_topic | 9 | get_topic__70, _75, _82 | TEST-GAP |
| 4 | `severity` fallback default `"unknown"` → `"XXunknownXX"`/`"UNKNOWN"` | get_topic | 2 | get_topic__50, _51 | TEST-GAP |
| 5 | `service.`/`worker.` prefix-handler key + value strings (route to `health/system`) | get_topic | 8 | get_topic__115, _118, _121 | TEST-GAP |
| 6 | `zone.approach` exact-match key string | get_topic | 2 | get_topic__97, _98 | TEST-GAP |
| 7 | Broadcaster registration: `hasattr` key string (guard silently falls to no-op) and `register_mqtt_callback(None)` — the callback itself is never passed/asserted | register_with_broadcaster | 3 | register_with_broadcaster__5, _6, _7 | TEST-GAP |
| 8 | `"event."` prefix key renamed while its value (`events/{camera_id}`) is identical to the generic fallback's return — genuinely unreproducible behavior change | get_topic | 2 | get_topic__123, _124 | EQUIVALENT |
| 9 | `__init__` startup log message text (case/`XX` decoration) | __init__ | 3 | __init___8, _9, _10 | EQUIVALENT |
| 10 | `__init__` log `extra` field-name keys (`enabled`/`events_qos`/`status_qos`/`retain_status`) | __init__ | 8 | __init___11, _14, _17 | EQUIVALENT |
| 11 | `register_with_broadcaster` success log text | register_with_broadcaster | 4 | rwb__8, _9, _10 | EQUIVALENT |
| 12 | Skip-path debug logs (disabled / not-connected): message text, `extra=None`, `extra` arg dropped | publish_event | 16 | publish_event__2, _5, _13 | LOW-VALUE |
| 13 | Success debug log `"Published event to MQTT"` + its `extra` keys/args | publish_event | 14 | publish_event__59, _62, _70 | LOW-VALUE |
| 14 | Error-path log `"Failed to publish event to MQTT"` + `extra` keys, `str(None)` | publish_event | 13 | publish_event__82, _93, _95 | LOW-VALUE |

Sum: 4+9+9+2+8+2+3 = 37 TEST-GAP, 17 EQUIVALENT, 43 LOW-VALUE → 100. ✓

Notes on judgement calls:
- **Cluster 8 is a true equivalent**, not merely untested: the fallback `return f"events/{camera_id}"` (mqtt_publisher.py:187)
  is byte-identical to what the `"event."` entry returns, so no input can distinguish it. Mutmut's survivor is honest.
- **Clusters 9/10/11 are equivalent-in-effect**: `structlog` message/extra-key text carries no control flow; nothing in
  the product surface reads them. Clusters 12-14 mutate real log records (arg removal changes the emitted record), so
  they are LOW-VALUE, not EQUIVALENT — a single `caplog` assertion on the error path (cluster 14) is the cheapest way
  to kill 13 survivors if the team wants the number up; it is listed here rather than drafted because it asserts the
  observability string, not behavior.
- **Cluster 7 is why MagicMock hides a bug**: `hasattr(MagicMock(), anything)` is always True, so the guard's attribute
  name is untestable with the current fixture, and `assert_called_once()` never inspects the payload —
  `register_mqtt_callback(None)` is a silent production breakage (broadcaster registers a `None` callback).

## Drafted tests

All UNVERIFIED — not yet run red/green. TDD procedure for each: apply the cluster's mutant to
`backend/services/mqtt_publisher.py`, run the new test, confirm the assertion FAILS; restore the original, confirm it PASSES.
Style follows the existing file (fixtures `publisher`/`mock_mqtt_client`, `call_args.kwargs`, class-scoped grouping).

### T-A — kills cluster 1 (timestamp semantics)

```python
# append to class TestMQTTPublisher (backend/tests/unit/services/test_mqtt_publisher.py)

    @pytest.mark.asyncio
    async def test_publish_preserves_supplied_timestamp(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """A caller-supplied timestamp is never overwritten by the injected one."""
        supplied = "2026-02-01T10:00:00Z"

        await publisher.publish_event(
            "alert.created", {"type": "alert.created", "timestamp": supplied}
        )

        payload = mock_mqtt_client.publish.call_args.kwargs["payload"]
        assert payload["timestamp"] == supplied

    @pytest.mark.asyncio
    async def test_publish_injects_utc_timestamp(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """The injected timestamp is a tz-aware ISO-8601 string (UTC offset present)."""
        await publisher.publish_event("alert.created", {"type": "alert.created"})

        payload = mock_mqtt_client.publish.call_args.kwargs["payload"]
        ts = payload["timestamp"]
        assert isinstance(ts, str)
        assert datetime.fromisoformat(ts).tzinfo is not None  # kills datetime.now(None)
```

Needs `from datetime import datetime` added to the test file's imports (it currently imports none).

- `"XXtimestampXX" not in payload` / `"TIMESTAMP" not in payload` (36, 37): the guard no longer sees the supplied key,
  so the injected value clobbers it → first test fails.
- `payload["timestamp"] = None` (39): `isinstance(ts, str)` fails.
- `datetime.now(None).isoformat()` (42): naive datetime → `tzinfo is None` → second test fails.

### T-B — kills clusters 2, 3, 4 (nested `data` fallbacks + `"unknown"` defaults)

```python
# append to class TestTopicMapping

    @pytest.mark.parametrize(
        ("event_type", "payload", "expected_topic"),
        [
            # severity: nested-data fallback and default
            ("alert.created", {"data": {"severity": "critical"}}, "alerts/critical"),
            ("alert.created", {}, "alerts/unknown"),
            # object_type: nested-data fallback and default
            (
                "detection.new",
                {"camera_id": "garage", "data": {"object_type": "cat"}},
                "detections/garage/cat",
            ),
            ("detection.new", {"camera_id": "garage"}, "detections/garage/unknown"),
            # entity_type: nested-data fallback and default
            ("entity.matched", {"data": {"entity_type": "vehicle"}}, "entities/vehicle"),
            ("entity.matched", {}, "entities/unknown"),
        ],
        ids=[
            "severity_nested",
            "severity_default",
            "object_type_nested",
            "object_type_default",
            "entity_type_nested",
            "entity_type_default",
        ],
    )
    def test_nested_and_default_field_fallbacks(
        self, event_type: str, payload: dict, expected_topic: str
    ) -> None:
        """Field extraction falls back to the nested data dict, then to "unknown"."""
        assert get_topic_for_event(event_type, payload) == expected_topic
```

- Nested params kill the `data.get(None, {})`, `"XXdataXX"/"DATA"`, and inner-key variants (58, 59, 63, 64, 65, 66, 75, 76, 80, 81, 82, 83).
- Default params kill `"XXunknownXX"/"UNKNOWN"` (50, 51, 67, 68, 84, 85) and the `or`→`and` flips (53, 70), which yield
  `None` and render as `.../None`.

### T-C — kills clusters 5, 6 (untested routes)

```python
    @pytest.mark.parametrize(
        ("event_type", "payload", "expected_topic"),
        [
            ("zone.approach", {"zone_id": "porch"}, "zones/porch/approach"),
            ("service.status_changed", {}, "health/system"),
            ("worker.health_check_failed", {}, "health/system"),
            ("worker.recovered", {}, "health/system"),
        ],
        ids=["zone_approach", "service_status", "worker_health_failed", "worker_recovered"],
    )
    def test_service_worker_and_approach_routing(
        self, event_type: str, payload: dict, expected_topic: str
    ) -> None:
        """Documented AI/ops event types route to their declared topics."""
        assert get_topic_for_event(event_type, payload) == expected_topic
```

Note: the three `worker.`/`service.` params are `STATUS_EVENT_TYPES` members, so this also documents that those
status types have a real topic (they currently fall through to `events/unknown` under the key mutants).

### T-D — kills cluster 7 (broadcaster contract)

The existing test uses `MagicMock`, and `hasattr(MagicMock(), anything)` is always True — so the guard's attribute
name is untestable there, and `assert_called_once()` never inspects the argument. A minimal **real** broadcaster
exercises both halves of the contract:

```python
# append to class TestMQTTPublisherBroadcasterIntegration

    @pytest.mark.asyncio
    async def test_register_with_real_broadcaster_uses_callback(
        self, publisher: MQTTPublisher
    ) -> None:
        """Registration passes publisher.publish_event (MagicMock would not catch None or a wrong hasattr key)."""
        class _Broadcaster:
            def __init__(self) -> None:
                self.callback = None

            def register_mqtt_callback(self, cb) -> None:
                self.callback = cb

        broadcaster = _Broadcaster()
        publisher.register_with_broadcaster(broadcaster)

        assert broadcaster.callback is publisher.publish_event

    @pytest.mark.asyncio
    async def test_register_with_broadcaster_without_callback_support(
        self, publisher: MQTTPublisher, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A broadcaster lacking register_mqtt_callback is skipped with a warning, not crashed."""
        class _NoCallbackBroadcaster:
            pass

        with caplog.at_level("WARNING"):
            publisher.register_with_broadcaster(_NoCallbackBroadcaster())  # must not raise

        assert "does not support MQTT callback registration" in caplog.text
```

- Mutant 7 (`register_mqtt_callback(None)`): `broadcaster.callback` is `None` → first test fails.
- Mutants 5/6 (`hasattr` key → `"XXregister_mqtt_callbackXX"` / `"REGISTER_MQTT_CALLBACK"`): the guard misses the
  real object's method, nothing registers, `callback` stays `None` → first test fails. (The old MagicMock test
  passes under all three mutants — that is the gap.)
