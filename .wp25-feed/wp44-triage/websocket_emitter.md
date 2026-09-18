# WP4.4 Triage Dossier — backend/services/websocket_emitter.py

- Survivors: **101** (of 324 keys; 94 killed, 129 not-yet-checked)
- Diffs captured from `uv run mutmut show <key>` (all 101 succeeded, no fallback needed): `/tmp/wp25/wp44-triage/diffs.txt`
- Covering test files (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`):
  - `backend/tests/unit/services/test_websocket_emitter.py` (primary; 1361 lines — fixtures `emitter`, `mock_event_broadcaster`, `mock_system_broadcaster`, `mock_redis_client`; `@pytest.mark.asyncio`, AsyncMock-based)
  - `backend/tests/unit/test_websocket_emitter.py` (secondary/legacy class-style)
  - Peripheral: `backend/tests/unit/api/routes/test_scene_changes.py`, `backend/tests/unit/routes/test_system_routes.py`

## Root cause pattern

Almost every dispatch test asserts only `assert_called_once()` / `call_count == N` on the broadcaster mock — never the **message payload structure** passed to it. Correlation-ID and room propagation through the thin wrappers (`emit_to_user`, `broadcast`, `emit_batch`) is likewise never asserted (wrapper tests assert only the bool/`emit_count`). One structural assertion per dispatch site kills whole clusters.

## Cluster table

| #         | Cluster                                                                                                                                                                                       | Count   | Class      | Example keys (suffix)                   |
| --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ---------- | --------------------------------------- |
| C1        | `emit_to_user` drops room (`user:{id}` → None) and/or correlation_id into `emit()`                                                                                                            | 5       | TEST-GAP   | emit_to_user**1, **4, \_\_5             |
| C2        | `broadcast` drops correlation_id (`correlation_id=None` / kwarg removed)                                                                                                                      | 3       | TEST-GAP   | broadcast**3, **6, \_\_7                |
| C3        | `emit_batch` shared-correlation derivation/pass-through broken (`None`, `and`-flip, `str(None)`, per-event None, kwarg removed)                                                               | 5       | TEST-GAP   | emit_batch**3, **4, \_\_5               |
| C4        | `emit_batch` skip-warning log message text → `None`                                                                                                                                           | 1       | EQUIVALENT | emit_batch\_\_16                        |
| C5        | alert dispatch: `broadcast_alert(payload, alert_type_map[...])` arg swaps/drops (payload→None, alert-type→None, args dropped)                                                                 | 4       | TEST-GAP   | \_deb**15, **16, \_\_17                 |
| C6        | camera dispatch: `camera_payload` / `{"type":"camera_status","data":...}` message shape clobbered (whole dict→None, key renames `type`/`data`/`event_type`, value case/`XX` changes)          | 10      | TEST-GAP   | \_deb**20, **21, \_\_23                 |
| C7        | security-event dispatch: `broadcast_event({"type":"event","data":payload})` message shape clobbered                                                                                           | 7       | TEST-GAP   | \_deb**39, **40, \_\_44                 |
| C8        | service-status dispatch: `"timestamp"` field key/value clobbered (`XXtimestampXX`, `TIMESTAMP`, `message.get(None)` etc.)                                                                     | 5       | TEST-GAP   | \_deb**54, **56, \_\_58                 |
| C9        | worker dispatch: `worker_payload` / `{"type":"worker_status","data":...,"timestamp":...}` message shape clobbered                                                                             | 15      | TEST-GAP   | \_deb**60, **61, \_\_63                 |
| C10       | Redis-fallback dispatch: channel derivation (`channel=None`, `and`-flip, `get_event_channel(None)`) and `_publish_to_redis(message, channel)` arg drops                                       | 5       | TEST-GAP   | \_deb**76, **78, \_\_81                 |
| C11       | `_dispatch_to_event_broadcaster` guard log message text (incl. `None`)                                                                                                                        | 4       | EQUIVALENT | \_deb**2, **3, \_\_4                    |
| C12       | `_dispatch_to_event_broadcaster` `message.get("payload", {})` default tweak (only fires when "payload" key absent — always present via emit path)                                             | 2       | EQUIVALENT | \_deb**8, **10                          |
| C13       | system dispatch: `status_data = {"type","data","timestamp"}` message shape clobbered (whole dict→None, key renames, `get(None,{})`, `get("XXpayloadXX",{})` → data lost, timestamp key/value) | 14      | TEST-GAP   | \_dsb**6, **7, \_\_11                   |
| C14       | `_dispatch_to_system_broadcaster` guard log message text                                                                                                                                      | 4       | EQUIVALENT | \_dsb**2, **3, \_\_4                    |
| C15       | `_dispatch_to_system_broadcaster` `message.get("payload", {})` default tweak (absent-key-only)                                                                                                | 2       | EQUIVALENT | \_dsb**12, **14                         |
| C16       | `_publish_to_redis` log message texts (warning/debug/error) → `None`/case/`XX` variants                                                                                                       | 6       | EQUIVALENT | \_ptr**2, **10, \_\_11                  |
| C17       | `_publish_to_redis` `exc_info=True` → `None`/absent/`False` (traceback capture in error log; no test inspects log record)                                                                     | 3       | LOW-VALUE  | \_ptr**12, **14, \_\_15                 |
| C18       | `get_websocket_emitter` "Global WebSocket emitter initialized" info-log text                                                                                                                  | 4       | EQUIVALENT | get_websocket_emitter**17, **18, \_\_19 |
| **Total** |                                                                                                                                                                                               | **101** |            |                                         |

Key: `emit_to_user`/`broadcast`/`emit_batch` keys are `...ǁWebSocketEmitterServiceǁ<fn>__mutmut_N`; `_deb` = `_dispatch_to_event_broadcaster`, `_dsb` = `_dispatch_to_system_broadcaster`, `_ptr` = `_publish_to_redis`.

Notes:

- `_deb__79/__80` (the `"events"` fallback literal → `XXeventsXX`/`EVENTS`) are a separate EQUIVALENT cluster (C10b, count 2, listed below the main table), NOT part of C10's 5 TEST-GAP keys: every one of the 59 enum event types has a truthy `channel` in `EVENT_TYPE_METADATA` (`backend/core/websocket/event_types.py:739-749`), so `get_event_channel(event_type) or "events"` never takes the fallback and the string mutation is a semantic no-op.

C10b: Redis-fallback `"events"` default literal is dead code (all 59 event types carry a channel) — string mutation is a no-op | 2 | EQUIVALENT | keys: `_dispatch_to_event_broadcaster__mutmut_79, __80`.

Totals: TEST-GAP 57, EQUIVALENT 41 (C4 1 + C11 4 + C12 2 + C14 4 + C15 2 + C16 6 + C18 4 + C10b 2), LOW-VALUE 3.
Cluster count check: 5+3+5+1+4+10+7+5+15+5+4+2+14+4+2+6+3+4+2 = **101** ✓

## Why the TEST-GAP clusters are gaps (evidence from covering tests)

- `test_emit_to_user_uses_user_specific_room` (`backend/tests/unit/services/test_websocket_emitter.py:295-318`): asserts `broadcast_alert.assert_called_once()` — comment claims room verification, but nothing checks `room="user:user123"`. Alert routing is room-independent (`_dispatch_event` sends non-"system" channels to the event broadcaster), so dropping the room is invisible.
- `TestBroadcastMethod::test_broadcast_calls_emit_without_room` and `TestEmitToUserMethod::...` (`backend/tests/unit/test_websocket_emitter.py:269,290`): assert only `result is True` / `emit_count`.
- `test_emit_uses_provided_correlation_id` (`.../services/test_websocket_emitter.py:342-361`): asserts only `result is True` — correlation_id never observed.
- `TestEmitBatchMethod::test_emit_batch_with_shared_correlation_id` (`backend/tests/unit/test_websocket_emitter.py:336-354`): asserts only `success_count == 2`; the "shared" correlation id is never inspected.
- `test_dispatch_alert_events_to_event_broadcaster` (`.../services/test_websocket_emitter.py:547-604`), `test_dispatch_camera_events_to_event_broadcaster` (:608-639), `test_dispatch_worker_events_to_event_broadcaster` (:663-729), `test_dispatch_event_created_and_updated` (:1241-1275): all assert `call_count` only — the message dict passed to the mock is never checked (unlike `test_dispatch_service_status_event` :1061-1066, which checks `type`/`data` but not `timestamp` → C8 survives).
- `test_dispatch_system_events_to_system_broadcaster` (:643-659) and `test_broadcast_emits_to_all_clients` (:252-268): `broadcast_status.assert_called_once()` only → C13 survives.
- `test_dispatch_event_with_redis_fallback` (:1278-1301) / `test_validate_event_without_schema` (:1305-1324): `publish.assert_called_once()` only — channel and message unchecked → C10 survives.
- The `_when_none` guard tests (:1007, :1070, :1095) deliberately only check "does not raise" → the guard-message text clusters (C11/C14/C16) are genuinely unkillable-by-design = EQUIVALENT.

## Drafted tests (6) — kill coverage ≈ 64/101 survivors

All drafted against `backend/tests/unit/services/test_websocket_emitter.py` (append; reuses its fixtures). **TDD procedure for each: apply the cluster's mutant to `backend/services/websocket_emitter.py`, run the new test → assertion must FAIL on mutant, PASS on original.**

### T1 — camera dispatch message shape (kills C6, 10 mutants)

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_dispatch_camera_event_message_structure(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Camera dispatch must send {type: camera_status, data: {event_type, ...payload}}."""
    payload = {
        "camera_id": "front_door",
        "camera_name": "Front Door",
        "status": "online",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    result = await emitter.emit(WebSocketEventType.CAMERA_STATUS_CHANGED, payload)

    assert result is True
    mock_event_broadcaster.broadcast_camera_status.assert_called_once()
    message = mock_event_broadcaster.broadcast_camera_status.call_args[0][0]
    assert message["type"] == "camera_status"
    assert message["data"]["event_type"] == WebSocketEventType.CAMERA_STATUS_CHANGED.value
    assert message["data"]["camera_id"] == "front_door"
```

Kill check: `__20`/`__23` (dict→None → KeyError), `__21/__22` (`event_type` key renamed), `__24/__25` (`type` key), `__26/__27` (`camera_status` value), `__28/__29` (`data` key). Passes on original.

### T2 — worker dispatch message shape (kills C9, 15 mutants)

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_dispatch_worker_event_message_structure(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Worker dispatch must send {type, data{event_type,...}, timestamp} to broadcast_worker_status."""
    payload = {
        "worker_name": "worker-1",
        "worker_type": "detection",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    result = await emitter.emit(WebSocketEventType.WORKER_STARTED, payload)

    assert result is True
    mock_event_broadcaster.broadcast_worker_status.assert_called_once()
    message = mock_event_broadcaster.broadcast_worker_status.call_args[0][0]
    assert message["type"] == "worker_status"
    assert message["data"]["event_type"] == WebSocketEventType.WORKER_STARTED.value
    assert message["data"]["worker_name"] == "worker-1"
    assert isinstance(message["timestamp"], str) and message["timestamp"]
```

Kill check: `__60/__63` (None → KeyError), `__61/__62` (event_type key), `__64/__65` (type key), `__66/__67` (value), `__68/__69` (data key), `__70/__71` (timestamp key renamed), `__72/__73/__74` (`message.get(None/"XX.."/"TIMESTAMP")` → timestamp None). Passes on original.

### T3 — system dispatch message shape (kills C13, 14 mutants)

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_dispatch_system_event_status_data_structure(
    emitter: WebSocketEmitterService,
    mock_system_broadcaster: AsyncMock,
) -> None:
    """System dispatch must send {type, data, timestamp} built from the message payload."""
    payload = {
        "health": "healthy",
        "gpu": {"utilization": 45.2, "memory_used": 8192},
        "cameras": {"active": 2, "total": 3},
        "queue": {"pending": 5, "processing": 1},
        "timestamp": datetime.now(UTC).isoformat(),
    }

    result = await emitter.emit(WebSocketEventType.SYSTEM_STATUS, payload)

    assert result is True
    mock_system_broadcaster.broadcast_status.assert_called_once()
    status_data = mock_system_broadcaster.broadcast_status.call_args[0][0]
    assert status_data["type"] == WebSocketEventType.SYSTEM_STATUS.value
    assert status_data["data"] == payload
    assert isinstance(status_data["timestamp"], str) and status_data["timestamp"]
```

Kill check: `__6/__22` (None → KeyError), `__7/__8` (type key), `__9/__10` (data key), `__11` (`get(None,{})` → data `{}`), `__15/__16` (payload key renamed → data `{}`), `__17/__18` (timestamp key), `__19/__20/__21` (timestamp lookup broken → None). Passes on original. (`__12/__14` remain EQUIVALENT per C15 — not required to die.)

### T4 — service-status timestamp field (kills C8, 5 mutants)

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_dispatch_service_status_event_carries_message_timestamp(
    mock_event_broadcaster: AsyncMock,
) -> None:
    """SERVICE_STATUS_CHANGED dispatch must forward the message timestamp under 'timestamp'."""
    emitter = WebSocketEmitterService(
        event_broadcaster=mock_event_broadcaster,
        system_broadcaster=None,
        redis_client=None,
        validate_payloads=True,
    )
    payload = {
        "service": "yolo26",
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    result = await emitter.emit(
        WebSocketEventType.SERVICE_STATUS_CHANGED, payload, room="events"
    )

    assert result is True
    call = mock_event_broadcaster.broadcast_service_status.call_args[0][0]
    assert call["type"] == "service_status"
    assert call["data"] == payload
    assert isinstance(call["timestamp"], str) and call["timestamp"]
```

Kill check: `__54/__55` (key renamed → KeyError), `__56` (`get(None)` → None), `__57/__58` (key renamed in lookup → None). Passes on original.

### T5 — Redis fallback channel + message (kills C10, 5 mutants)

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_redis_fallback_publishes_to_event_channel_with_message(
    mock_redis_client: AsyncMock,
) -> None:
    """Unmapped events must publish the full message to the event type's channel."""
    emitter = WebSocketEmitterService(
        event_broadcaster=AsyncMock(),
        system_broadcaster=None,
        redis_client=mock_redis_client,
        validate_payloads=False,
    )

    result = await emitter.emit(
        WebSocketEventType.JOB_PROGRESS,
        {"job_id": "j1", "job_type": "export", "progress": 50, "status": "running"},
    )

    assert result is True
    mock_redis_client.publish.assert_called_once()
    channel, message = mock_redis_client.publish.call_args[0]
    assert channel == "jobs"  # get_event_channel(JOB_PROGRESS)
    assert message["type"] == WebSocketEventType.JOB_PROGRESS.value
```

Kill check: `__76` (channel None), `__77` (`and`-flip → "events"), `__78` (`get_event_channel(None)` → "events"), `__81` (message None), `__82` (channel None). Passes on original.

### T6 — room / correlation-id propagation through wrappers (kills C1+C2+C3, 13 mutants)

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_wrapper_methods_propagate_room_and_correlation_id(
    emitter_no_validation: WebSocketEmitterService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """emit_to_user/broadcast/emit_batch must forward room and correlation_id to emit()."""
    calls: list[dict] = []

    async def fake_emit(event_type, payload, *, room=None, correlation_id=None):
        calls.append({"room": room, "correlation_id": correlation_id})
        return True

    monkeypatch.setattr(emitter_no_validation, "emit", fake_emit)

    # emit_to_user: user room pattern + correlation passthrough
    assert await emitter_no_validation.emit_to_user(
        "user-7", WebSocketEventType.JOB_STARTED, {"a": 1}, correlation_id="cid-1"
    )
    assert calls[-1] == {"room": "user:user-7", "correlation_id": "cid-1"}

    # broadcast: no room, correlation passthrough
    assert await emitter_no_validation.broadcast(
        WebSocketEventType.JOB_STARTED, {"a": 1}, correlation_id="cid-2"
    )
    assert calls[-1] == {"room": None, "correlation_id": "cid-2"}

    # emit_batch: explicit correlation shared across all events
    calls.clear()
    count = await emitter_no_validation.emit_batch(
        [(WebSocketEventType.JOB_STARTED, {"a": 1}), (WebSocketEventType.JOB_STARTED, {"a": 2})],
        correlation_id="shared-9",
    )
    assert count == 2
    assert all(c["correlation_id"] == "shared-9" for c in calls)

    # emit_batch: implicit correlation generated once and shared
    calls.clear()
    await emitter_no_validation.emit_batch(
        [(WebSocketEventType.JOB_STARTED, {"a": 1}), (WebSocketEventType.JOB_STARTED, {"a": 2})]
    )
    ids = [c["correlation_id"] for c in calls]
    assert all(i is not None for i in ids) and len(set(ids)) == 1
```

Kill check: C1 `__1/__4` (room lost), `__5/__8/__9` (correlation lost); C2 `__3/__6/__7`; C3 `__3` (None), `__4` (`and`-flip regenerates or yields None), `__5` (`"None"` string fails `is not None`+set check? — `"None"` is non-None and shared, but the explicit-correlation block kills it since `correlation_id="shared-9"` → mutant yields... mutant `__5` changes `correlation_id or str(uuid4())` → `correlation_id or str(None)`; with explicit "shared-9" truthy it survives this leg, but with no explicit id yields `"None"` — shared and non-None → NOT killed by this test as drafted). Amend: assert the generated id parses as a UUID: `assert all(isinstance(i, str) and uuid.UUID(i) for i in ids)` (`uuid` already imported in the test module). Now `__5` dies ("None" is not a valid UUID). `__9/__12` (per-event None / kwarg dropped) die on the shared-9 block.

Passes on original.

## Remaining TEST-GAP clusters without drafts (fix sketches)

- **C5 (alert arg wiring, 4)**: one-liner in the existing loop test — `assert mock_event_broadcaster.broadcast_alert.call_args_list[i][0] == (payload, expected_alert_type)`.
- **C7 (security event shape, 7)**: same pattern as T1: `call = broadcast_event.call_args[0][0]; assert call == {"type": "event", "data": payload}`.

## Classification rationale summary

- EQUIVALENT (41): pure `logger.*(text)` mutations (C4, C11, C14, C16, C18 = 21) + defensive `.get(key, {})` defaults that only fire when the key is absent — impossible via the emit path since `_create_event_message` always includes `payload`/`timestamp` (C12, C15 = 4) + dead `or "events"` fallback literal (C10b = 2) + `_publish_to_redis` warning/debug text (inside C16). None change observable behavior for any input the function can actually receive.
- LOW-VALUE (3): `exc_info` on the Redis publish failure log (C17) — real behavior (traceback captured), but asserting on log-record internals for a fallback path nobody calls is not worth a test.
- TEST-GAP (57): message-dict shapes at all four dispatch sites + wrapper room/correlation propagation — every one is behavior a frontend consumer depends on (WebSocket message contracts), and every covering test executes the line with only a call-count assertion.
