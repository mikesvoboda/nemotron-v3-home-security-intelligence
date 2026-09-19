# WP4.4 triage dossier — backend/api/routes/alertmanager.py

Status: **UNVERIFIED (drafting wave — no tests were run; read-only triage per harness constraints)**

## Provenance

- Verdicts: `mutants/backend/api/routes/alertmanager.py.meta` — 43 keys total, **34 survived** (exit_code 0), 9 killed (exit_code 1), 0 untried.
- Every mutant (all 43) sits under the single mangled name
  `backend.api.routes.alertmanager.x__broadcast_prometheus_alert` (confirmed against
  `alertmanager.py.spans`: one span set, `x__broadcast_prometheus_alert__mutmut_*`). The module's
  route handler `receive_alertmanager_webhook` contributed no mutants (it is a separate function and
  apparently not mutated in this run).
- All diffs obtained via `uv run mutmut show <key>` (worked; no fallback diffing needed).
- Mutation sites live in `_broadcast_prometheus_alert` at `backend/api/routes/alertmanager.py:34-79`
  (guard :44, payload dict :51-61, `create_event` :64-67, `publish` :70, handlers :73-79).

## Coverage map (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`)

Only 4 tests cover the function, all in
`backend/tests/unit/api/routes/test_alertmanager.py`:

| test | line | what it asserts |
|---|---|---|
| `TestBroadcastPrometheusAlert::test_broadcast_with_no_redis_returns_false` | :351 | `result is False` only |
| `TestBroadcastPrometheusAlert::test_broadcast_with_broadcaster_not_initialized` | :368 | `result is False` only |
| `TestBroadcastPrometheusAlert::test_broadcast_success` | :393 | `result is True` + `publish.assert_called_once()` — **call ARGS never inspected** |
| `TestBroadcastPrometheusAlert::test_broadcast_failure_returns_false` | :421 | `result is False` only |

The webhook-route tests in the same file (:96-344) all **patch `_broadcast_prometheus_alert` out**
(e.g. :100-104), so they exercise none of these mutants. No integration test touches the broadcast
path (`test_monitoring_stack_integration.py` only asserts "alertmanager" appears in configs).

Why survivors are structurally guaranteed: `broadcaster._redis.publish` is an `AsyncMock`
(:411), so ANY argument passed to it is accepted, and the only success-path assertion is
"publish was called once" + return `True`. The published **event content** (payload keys/values,
event type, channel) is asserted nowhere.

Frontend contract that makes the payload a real behavior surface (why key mutants are TEST-GAP,
not cosmetic): `frontend/src/types/websocket-events.ts:1431-1448` declares the consumer shape
(`fingerprint`, `alertname`, `severity`, `starts_at`, `ends_at: string | null`, `received_at`),
`frontend/src/stores/prometheus-alert-store.ts` keys the active-alert map by `fingerprint`, and
`backend/core/websocket/event_types.py:581-586` (`EVENT_TYPE_METADATA[PROMETHEUS_ALERT].payload_fields`)
documents `["fingerprint","status","alertname","severity","starts_at"]` as the required fields.
(The metadata registry is documentation — not enforced at runtime — so a renamed key ships silently.)

## Cluster table (counts sum to 34)

| # | Pattern | n | Class | Example keys (≤3 of n) |
|---|---|---|---|---|
| A | Debug-level log message text mutated (`None` / `XX…XX` wrap / case flip) in guard (:45), success (:71) and RuntimeError handler (:75) | 6 | EQUIVALENT | …_2, …_3, …_38 (also 4, 5, 40) |
| B | Warning-level log message text mutated to `None` in generic exception handler (:78) | 1 | LOW-VALUE | …_42 |
| C | Entire payload dict literal replaced by `None` (:51) | 1 | TEST-GAP | …_8 |
| D | Payload dict **key** renamed (`"k"` → `"XXkXX"` / `"K"`), all 9 keys ×2 | 18 | TEST-GAP | …_9, …_11, …_27 (keys 9-24, 27, 28) |
| E | `ends_at` ternary condition weakened with `and False` → payload `ends_at` always `None` (:60) | 1 | TEST-GAP | …_25 |
| F | `create_event` return swapped to `None` (:64) / its event-type arg → `None` (:65) / its payload arg → `None` (:66) | 3 | TEST-GAP | …_29, …_30, …_31 |
| G | `redis.publish` arg mutations: channel → `None` (:70), event → `None` (:70), channel arg dropped (`publish(event)`), event arg dropped (`publish(channel_name)`) | 4 | TEST-GAP | …_34, …_35, …_36 (also 37) |

Totals: TEST-GAP 27 (C+D+E+F+G), EQUIVALENT 6 (A), LOW-VALUE 1 (B). 6+1+1+18+1+3+4 = 34. ✔

(Key prefix `…_N` = `backend.api.routes.alertmanager.x__broadcast_prometheus_alert__mutmut_N`.)

## Cluster detail & rulings

### A — debug log message text (2,3,4,5,38,40) — EQUIVALENT, 6

Pure message-text changes (`None`, `XX…XX`, lowercase, UPPERCASE) inside `logger.debug(...)` calls.
Return values, control flow, publish args all identical. No test in the file asserts debug-level
output anywhere (log-content asserts exist only for error/warning/info on the webhook route,
:179/:201/:220). Killing these would only encode incidental prose. EQUIVALENT per task rubric
("pure log/message text").

### B — warning message in exception handler (42) — LOW-VALUE, 1

`logger.warning(f"Failed to broadcast Prometheus alert: {e}")` → `logger.warning(None)`. A real
change (error text lost from warning log during broadcast failures), but it is message text with no
effect on the return value or caller. The file's style *could* kill it cheaply (autospec-logger +
`assert "Publish failed" in str(call_args)` like :179-182), but nobody should be forced to assert a
debug-adjacent string; not among drafted tests. LOW-VALUE.

### C — payload dict → None (8) — TEST-GAP, 1

`payload = {…}` → `payload = None`. `create_event` accepts it unvalidated; publish receives an event
whose `payload` is `None`; function still returns `True`. In production every WS client gets an
envelope with no data — the frontend store (`prometheus-alert-store.ts:149-163`) would receive an
undefined payload and drop/corrupt the alert. Test executes the line, asserts nothing about it.
Killed by Draft-1 (key-set assertion on `event["payload"]` → AttributeError on mutant).

### D — payload key renames (9-24, 27, 28 — 18 mutants) — TEST-GAP, 18

Each payload key string XX-wrapped or uppercased (`"fingerprint"` → `"XXfingerprintXX"` /
`"FINGERPRINT"`). Value expressions untouched, so dict size and `publish.assert_called_once()` are
unaffected — survival is guaranteed by the absence of any key/value assertion. This is the exact
wire contract consumed by `usePrometheusAlertWebSocket.ts` / `prometheus-alert-store.ts` and listed
in `EVENT_TYPE_METADATA` payload_fields. Highest-count cluster; one payload-contract test kills all
18 plus cluster C and one of F.

### E — `ends_at … and False` (25) — TEST-GAP, 1

`alert.ends_at.isoformat() if (alert.ends_at) and False else None` → payload `ends_at` is
unconditionally `None`. Real semantic loss: a RESOLVED alert broadcast tells clients it never ended
(`websocket-events.ts:1446` types `ends_at: string | null` as the resolution time; store keys active
alerts by fingerprint). The existing success test (:393) only builds a **FIRING** alert with
`ends_at=None`, so the resolved path of this ternary has zero coverage. (The route-level year-0001
test at :315 covers DB normalization *before* the model — it patches this helper out entirely.)

### F — create_event sabotage (29, 30, 31) — TEST-GAP, 3

29: `event = None` → publishes `None` as the event, returns `True`. 30: event-type arg → `None` →
clients can't route the message (`event["type"]` no longer `prometheus.alert`). 31: payload arg →
`None` (same consumer impact as C). All invisible to `assert_called_once`. Killed by Draft-1/Draft-3
(type + payload assertions on the captured publish args).

### G — publish arg mutations (34, 35, 36, 37) — TEST-GAP, 4

34: channel → `None` (message to a null channel — delivered nowhere real). 35: event → `None`
(clients get nothing). 36: `publish(event)` — in production the missing `message` arg raises
`TypeError`, is swallowed by the broad `except Exception` at :77, and the function returns **False**
(broadcast silently reported as failed); under the AsyncMock harness no error occurs, so the
`result is True` assert passes. 37: `publish(channel_name)` — same TypeError-swallow story in prod.
These are the mutants where the mocked-arg survival actively hides a production **return-value**
change, so the exact-args assertion matters. Killed by Draft-4
(`publish.assert_called_once_with("events", <event>)`).

## Drafted tests

Target file: `backend/tests/unit/api/routes/test_alertmanager.py`, added to class
`TestBroadcastPrometheusAlert` (line :347). New module-level import needed:
`from backend.core.websocket.event_types import WebSocketEventType` (add to the import block at :12-31).
Harness style is copied from `test_broadcast_success` (:393-418).

**TDD procedure (applies to each):** run the test against the mutated copy — assertion (or the
TypeError/ValueError it triggers) fails red on the mutant diff, then passes green on original.

All four drafts are **UNVERIFIED — not yet run red/green**.

```python
# // UNVERIFIED - not yet run red/green
# Expected payload keys — mirrors frontend/src/types/websocket-events.ts:1431-1448 and
# EVENT_TYPE_METADATA[PROMETHEUS_ALERT].payload_fields (backend/core/websocket/event_types.py:581).
PROMETHEUS_ALERT_PAYLOAD_KEYS = {
    "fingerprint", "status", "alertname", "severity", "labels",
    "annotations", "starts_at", "ends_at", "received_at",
}

def _firing_alert(**overrides):  # shared fixture-builder for the drafts below
    kwargs = dict(
        id=1,
        fingerprint="test-fp",
        status=ModelPrometheusAlertStatus.FIRING,
        labels={"alertname": "Test", "severity": "warning"},
        annotations={"summary": "Test alert"},
        starts_at=datetime(2026, 1, 20, 12, 0, 0, tzinfo=UTC),
        received_at=datetime(2026, 1, 20, 12, 0, 5, tzinfo=UTC),
    )
    kwargs.update(overrides)
    return PrometheusAlert(**kwargs)
```

### Draft 1 — `test_broadcast_success_payload_matches_schema`
Kills: cluster D (all 18 key renames), cluster C (payload=None), cluster F mutmut_31 (payload arg=None).

```python
    @pytest.mark.asyncio
    async def test_broadcast_success_payload_matches_schema(self) -> None:
        """Published WS event payload must carry the exact PrometheusAlertPayload contract.

        Kills payload key-rename mutants (frontend consumers in
        frontend/src/stores/prometheus-alert-store.ts read these exact keys).
        """
        alert = _firing_alert()
        mock_redis = MagicMock()

        with patch(
            "backend.api.routes.alertmanager.EventBroadcaster", autospec=True
        ) as mock_broadcaster_cls:
            mock_broadcaster = MagicMock()
            mock_broadcaster._redis = MagicMock()
            mock_broadcaster._redis.publish = AsyncMock()
            mock_broadcaster.channel_name = "events"
            mock_broadcaster_cls.get_instance = MagicMock(return_value=mock_broadcaster)

            result = await _broadcast_prometheus_alert(alert, redis_client=mock_redis)

        assert result is True
        (channel, event) = mock_broadcaster._redis.publish.call_args.args
        payload = event["payload"]
        # Mutant mutmut_8 replaces the dict with None -> AttributeError here.
        assert set(payload.keys()) == PROMETHEUS_ALERT_PAYLOAD_KEYS
        assert payload["fingerprint"] == "test-fp"
        assert payload["status"] == "firing"
        assert payload["alertname"] == "Test"
        assert payload["severity"] == "warning"
        assert payload["labels"] == {"alertname": "Test", "severity": "warning"}
        assert payload["annotations"] == {"summary": "Test alert"}
        assert payload["starts_at"] == "2026-01-20T12:00:00+00:00"
        assert payload["ends_at"] is None  # still firing
        assert payload["received_at"] == "2026-01-20T12:00:05+00:00"
```

Red-proof sketch: any of the 18 key mutations makes `set(payload.keys())` differ → assert fails;
mutmut_8/31 make `event["payload"]` `None` → `set(None.keys())` errors. Green on original (values
match the model properties `alertname`/`severity` shown at test_alertmanager.py:523-524).

### Draft 2 — `test_broadcast_resolved_alert_payload_includes_ends_at`
Kills: cluster E (mutmut_25, `and False`).

```python
    @pytest.mark.asyncio
    async def test_broadcast_resolved_alert_payload_includes_ends_at(self) -> None:
        """A RESOLVED alert's broadcast payload must carry the resolution timestamp.

        Kills the ternary-weakening mutant that forces ends_at to None on every event
        (clients would render resolved alerts as still-firing).
        """
        ends = datetime(2026, 1, 20, 12, 30, 0, tzinfo=UTC)
        alert = _firing_alert(
            status=ModelPrometheusAlertStatus.RESOLVED,
            fingerprint="fp-resolved",
            ends_at=ends,
        )
        mock_redis = MagicMock()

        with patch(
            "backend.api.routes.alertmanager.EventBroadcaster", autospec=True
        ) as mock_broadcaster_cls:
            mock_broadcaster = MagicMock()
            mock_broadcaster._redis = MagicMock()
            mock_broadcaster._redis.publish = AsyncMock()
            mock_broadcaster.channel_name = "events"
            mock_broadcaster_cls.get_instance = MagicMock(return_value=mock_broadcaster)

            result = await _broadcast_prometheus_alert(alert, redis_client=mock_redis)

        assert result is True
        (_channel, event) = mock_broadcaster._redis.publish.call_args.args
        payload = event["payload"]
        assert payload["status"] == "resolved"
        assert payload["ends_at"] == "2026-01-20T12:30:00+00:00"  # mutant 25 -> None -> fail
```

Red-proof sketch: mutmut_25 short-circuits the ternary → `payload["ends_at"] is None` ≠ the ISO
string → fails. Green on original (model `ends_at` is a nullable column, prometheus_alert.py:61).

### Draft 3 — `test_broadcast_success_publishes_prometheus_alert_event_envelope`
Kills: cluster F (mutmut_29 event=None, mutmut_30 type=None; 31 also dies here).

```python
    @pytest.mark.asyncio
    async def test_broadcast_success_publishes_prometheus_alert_event_envelope(self) -> None:
        """The published object must be a WS envelope typed prometheus.alert.

        Kills create_event sabotage mutants (event=None, event-type=None, payload=None).
        """
        alert = _firing_alert()
        mock_redis = MagicMock()

        with patch(
            "backend.api.routes.alertmanager.EventBroadcaster", autospec=True
        ) as mock_broadcaster_cls:
            mock_broadcaster = MagicMock()
            mock_broadcaster._redis = MagicMock()
            mock_broadcaster._redis.publish = AsyncMock()
            mock_broadcaster.channel_name = "events"
            mock_broadcaster_cls.get_instance = MagicMock(return_value=mock_broadcaster)

            result = await _broadcast_prometheus_alert(alert, redis_client=mock_redis)

        assert result is True
        (_channel, event) = mock_broadcaster._redis.publish.call_args.args
        assert event is not None  # mutmut_29 -> None
        assert event["type"] == WebSocketEventType.PROMETHEUS_ALERT  # mutmut_30 -> None
        assert event["payload"] is not None  # mutmut_31 (and mutmut_8) -> None
        assert "timestamp" in event  # create_event envelope invariant
```

### Draft 4 — `test_broadcast_publishes_event_to_broadcaster_channel`
Kills: cluster G (mutmut_34, 35, 36, 37).

```python
    @pytest.mark.asyncio
    async def test_broadcast_publishes_event_to_broadcaster_channel(self) -> None:
        """publish() must be awaited once with (broadcaster.channel_name, event) exactly.

        Kills publish-arg mutants; in production the dropped-arg variants (mutmut_36/37)
        raise TypeError that the broad except swallows into a silent False, and the
        None-channel/event variants deliver the alert nowhere.
        """
        alert = _firing_alert()
        mock_redis = MagicMock()

        with patch(
            "backend.api.routes.alertmanager.EventBroadcaster", autospec=True
        ) as mock_broadcaster_cls:
            mock_broadcaster = MagicMock()
            mock_broadcaster._redis = MagicMock()
            mock_broadcaster._redis.publish = AsyncMock()
            mock_broadcaster.channel_name = "events"
            mock_broadcaster_cls.get_instance = MagicMock(return_value=mock_broadcaster)

            result = await _broadcast_prometheus_alert(alert, redis_client=mock_redis)

        assert result is True
        mock_broadcaster._redis.publish.assert_called_once()
        (args, kwargs) = mock_broadcaster._redis.publish.call_args
        assert len(args) == 2  # mutmut_36/37 pass 1 positional -> fail
        assert args[0] == "events"  # mutmut_34 (channel None) -> fail
        event = args[1]
        assert isinstance(event, dict)  # mutmut_35 (event None) / mutmut_29 -> fail
        assert event["payload"]["fingerprint"] == "test-fp"
```

## Draft coverage vs clusters

| Draft | Kills clusters | Mutants |
|---|---|---|
| 1 | C, D, F(31) | 20 |
| 2 | E | 1 |
| 3 | F (29, 30, 31) | 3 |
| 4 | G | 4 |

4 drafts collectively kill **all 27 TEST-GAP survivors**; A/B (7) left EQUIVALENT/LOW-VALUE by ruling.

## Notes / traps observed

- The naive "payload = same dict built by the test" equality assert would be fine, but note
  `assert_called_once_with("events", event)` needs the *actual* event (it embeds a live timestamp),
  which is why drafts capture `call_args` and assert structure instead — mirroring the
  `call_args = str(mock_logger.error.call_args)` capture style at :180.
- `mutmut_1` (guard `is None` → `is not None`) was already killed; the surviving guard-path
  mutants are message-only, so `test_broadcast_with_no_redis_returns_false` (:351) is adequate.
- `EVENT_TYPE_METADATA.payload_fields` is documentation only — nothing validates the payload at
  runtime — so key-rename mutants ship silently to the frontend. That is the core justification for
  treating cluster D as TEST-GAP rather than LOW-VALUE.
- Killed-for-context keys: 1, 6, 7, 26, 32, 33, 39, 41, 43 (return-value/guard class).
