# WP4.4 Triage Dossier — backend/services/camera_service.py

**Date:** 2026-09-17 · **Phase:** WP4.3 surviving-mutant feed → WP4.4
**Meta:** `mutants/backend/services/camera_service.py.meta` — 239 keys: 95 killed, **113 survived**, 31 pending (null, ignored).
**Diffs:** all 113 captured read-only via `uv run mutmut show` → `/tmp/wp25/wp44-triage/camera_service_diffs.txt` (no test execution, no repo mutation).
**Covering test file (all functions):** `backend/tests/unit/services/test_camera_service.py` — convenience methods :159 (`TestCameraServiceConvenienceMethods`), WS events :255 (`TestCameraServiceWebSocketEvents`), debouncing :428 (`TestCameraServiceDebouncing`), `_map_status_string_to_enum` :559 (`TestMapStatusStringToEnum`). Source under test: `backend/services/camera_service.py` (`set_camera_online` :203, `set_camera_offline` :221, `set_camera_error` :239, `_emit_status_change_event` :261, `_should_emit_debounced` :322, `_emit_camera_events` :394, `_map_status_string_to_enum` :489).

Key-name shorthand below: `esc_` = `_emit_status_change_event`, `sed_` = `_should_emit_debounced`, `ece_` = `_emit_camera_events`, `map_` = `_map_status_string_to_enum`.

## Per-cluster table

| #   | Cluster                                                                                                                                                                                                                                                                              | Count | Classification | Example keys                                                                                 | Killable by |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----- | -------------- | -------------------------------------------------------------------------------------------- | ----------- |
| 1   | Convenience methods pass `camera_id=None` to `update_camera_status` (set\_\*\_online/offline/error all three)                                                                                                                                                                        | 3     | TEST-GAP       | `set_camera_online__mutmut_1`, `set_camera_offline__mutmut_1`, `set_camera_error__mutmut_1`  | Draft T1    |
| 2   | `set_camera_offline`/`set_camera_error` drop the caller `timestamp` (→ `None` / arg removed) → repo gets `datetime.now()` instead of caller's time                                                                                                                                   | 4     | TEST-GAP       | `set_camera_offline__mutmut_3`, `set_camera_offline__mutmut_6`, `set_camera_error__mutmut_3` | Draft T1    |
| 3   | Event `timestamp` becomes `None` / naive (`datetime.now(None)`) before reaching payloads                                                                                                                                                                                             | 3     | TEST-GAP       | `esc_22`, `esc_23`, `esc_26`                                                                 | Draft T2    |
| 4   | Debounce reads Redis with key `None` instead of `camera:status:debounce:<id>` — with real Redis, events would **never** emit (get always misses)                                                                                                                                     | 1     | TEST-GAP       | `sed_5`                                                                                      | Draft T3    |
| 5   | Generic `camera.status_changed` payload key renames (`camera_id`, `camera_name`, `timestamp`, `reason`, `details` → `XXkXX`/`K` variants)                                                                                                                                            | 10    | TEST-GAP       | `ece_60`, `ece_62`, `ece_74`                                                                 | Draft T2    |
| 6   | Specific `camera.offline`/`camera.error` payload key renames (`camera_name`, `timestamp`, `error_code`)                                                                                                                                                                              | 10    | TEST-GAP       | `ece_19`, `ece_21`, `ece_38`                                                                 | Draft T2    |
| 7   | `camera.error` fallback text `"Unknown error"` altered (payload-visible when `reason=None`)                                                                                                                                                                                          | 3     | TEST-GAP       | `ece_35`, `ece_36`, `ece_37`                                                                 | Draft T2    |
| 8   | `specific_event_type` initial `None` → `""`: for a status outside online/offline/error (e.g. `CameraStatus.UNKNOWN`) the guard `is not None` passes, emits a bogus `""`-typed event then crashes on `.value` (swallowed by the caller's except). Entire `else:` branch untested      | 1     | TEST-GAP       | `ece_4`                                                                                      | Draft T4    |
| 9   | `_emit_status_change_event` log-only mutations: message→`None`, `extra`→`None`/removed, extra-key renames, `exc_info` True→None/False, `debounced: True→False`, `str(e)→str(None)`                                                                                                   | 26    | EQUIVALENT     | `esc_2`, `esc_13`, `esc_45`                                                                  | —           |
| 10  | `_should_emit_debounced` log-only mutations (debug ×2 branches + Redis-failure warning)                                                                                                                                                                                              | 27    | EQUIVALENT     | `sed_8`, `sed_27`, `sed_44`                                                                  | —           |
| 11  | `_emit_camera_events` log-only mutations (both `logger.info` call sites)                                                                                                                                                                                                             | 23    | EQUIVALENT     | `ece_47`, `ece_53`, `ece_88`                                                                 | —           |
| 12  | Generic-payload ternary `if previous_status` → `if (previous_status) or True`: both arms then yield `None` for `previous_status=None` because `_map_status_string_to_enum(None) is None` — indistinguishable for every real input (only `""` would differ, never occurs)             | 1     | EQUIVALENT     | `ece_70`                                                                                     | —           |
| 13  | `_map_status_string_to_enum`: `CameraStatus(status_lower).value` → `CameraStatus(None).value` — `CameraStatus(None)` raises `ValueError`, caught, returns `status_lower`, which **equals** the enum value for every member (values are the lowercase names) → semantically identical | 1     | EQUIVALENT     | `map_4`                                                                                      | —           |

**Sum:** TEST-GAP 35 (1–8) + EQUIVALENT 78 (9–13) = **113**.

No LOW-VALUE clusters: every non-log mutation is either client-visible contract (payload/Redis/event-type) or provably dead-equivalent.

## Why the TEST-GAP clusters survive (test reads)

- `test_set_camera_online/offline/error` (:163/:176/:189) assert **only** `call_args.kwargs["new_status"]` — never `camera_id`, never `new_last_seen`. `test_convenience_methods_accept_timestamp` (:202) checks `new_last_seen` but **only for `set_camera_online`** — that is why online's timestamp mutants are killed while offline/error's survived. Repository mocks are key-blind (`return_value` unconditionally), so `camera_id=None` flows through invisibly.
- Debounce tests mock `redis.get` with an unconditional `return_value` (:441/:470/:495), so `get(None)` returns whatever was scripted → cluster 4 survives; they also never assert the key `get` was called with.
- WS-event tests assert `payload["camera_id"]`, `payload["reason"]`, `payload["error"]`, `payload["status"]`, `payload["previous_status"]` — precisely the keys that were **killed** when renamed. Surviving renames are exactly the unasserted keys (`camera_name`/`timestamp` in offline+error payloads, `error_code`, five keys of the generic payload). `"timestamp" in payload` (:286) passes even when the value is `None`.
- No test ever feeds a status outside {online, offline, error} through `_emit_camera_events`, so the `else:` branch and the `specific_event_type` sentinel mutation (cluster 8) are unexercised.
- Log clusters: no test uses `caplog`; `logger.debug(None)` doesn't raise (logging `str()`s the msg, and debug is usually filtered anyway), renamed `extra` keys are plain custom attrs → zero behavioral delta → EQUIVALENT, do not assert log text.

## Drafted tests (UNVERIFIED — not yet run red/green)

Target file: `backend/tests/unit/services/test_camera_service.py` (append to the named classes; fixtures `mock_session`, `mock_camera`, `mock_redis`, `mock_emitter` already exist at :26–:83).
TDD procedure (all four): apply the mutant to the source, run the new test — the new assert must FAIL; restore original — it must PASS; then re-run to confirm each survivor in the killed cluster flips survived→killed.

### T1 — convenience methods forward camera_id + timestamp (kills clusters 1+2, 7 survivors) → `TestCameraServiceConvenienceMethods`

```python
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("setter_name", "expected_status"),
        [
            ("set_camera_online", "online"),
            ("set_camera_offline", "offline"),
            ("set_camera_error", "error"),
        ],
    )
    async def test_convenience_methods_forward_camera_id_and_timestamp(
        self, mock_session, mock_camera, setter_name, expected_status
    ):
        """Convenience methods must pass camera_id and the caller's timestamp through unchanged."""
        service = CameraService(mock_session)
        timestamp = datetime.now(UTC) - timedelta(minutes=5)

        service.repository.get_by_id = AsyncMock(return_value=mock_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await getattr(service, setter_name)("front_door", timestamp)

        call_args = service.repository.update_status_optimistic.call_args
        assert call_args.kwargs["camera_id"] == "front_door"
        assert call_args.kwargs["new_status"] == expected_status
        assert call_args.kwargs["new_last_seen"] == timestamp
```

Red on `camera_id=None` (first assert) and on timestamp dropped/`None` (`new_last_seen == now() ≠ timestamp`, third assert); green on original.

### T2 — full WebSocket payload contract for all three statuses (kills clusters 3, 5, 6, 7 — 26 survivors) → `TestCameraServiceWebSocketEvents`

```python
    @pytest.mark.asyncio
    async def test_status_change_event_payload_contract(self, mock_session, mock_emitter):
        """Every emitted payload must carry its full client-facing key set with sane values."""
        service = CameraService(mock_session, emitter=mock_emitter)

        async def _capture(prev_status, camera_status, new_status, reason=None):
            previous = MagicMock()
            previous.id = "front_door"
            previous.status = prev_status

            camera = MagicMock()
            camera.id = "front_door"
            camera.name = "Front Door Camera"
            camera.status = camera_status

            service.repository.get_by_id = AsyncMock(return_value=previous)
            service.repository.update_status_optimistic = AsyncMock(return_value=(True, camera))
            mock_emitter.emit.reset_mock()

            await service.update_camera_status("front_door", new_status, reason=reason)
            return [call[0] for call in mock_emitter.emit.call_args_list]

        # --- online: specific payload has exactly id/name/timestamp, tz-aware ISO ---
        (etype, payload), (gtype, gpayload) = _capture("offline", "online", "online")
        assert etype == WebSocketEventType.CAMERA_ONLINE
        assert set(payload) == {"camera_id", "camera_name", "timestamp"}
        assert isinstance(payload["timestamp"], str)
        assert datetime.fromisoformat(payload["timestamp"]).tzinfo is not None
        assert gtype == WebSocketEventType.CAMERA_STATUS_CHANGED
        assert set(gpayload) == {
            "camera_id", "camera_name", "status", "previous_status",
            "timestamp", "reason", "details",
        }
        assert gpayload["camera_id"] == "front_door"
        assert gpayload["camera_name"] == "Front Door Camera"
        assert gpayload["status"] == "online"
        assert gpayload["previous_status"] == "offline"
        assert gpayload["reason"] is None
        assert gpayload["details"] is None
        assert datetime.fromisoformat(gpayload["timestamp"]).tzinfo is not None

        # --- offline: specific payload carries reason; generic mirrors it ---
        (etype, payload), (gtype, gpayload) = _capture(
            "online", "offline", "offline", reason="Connection timeout"
        )
        assert etype == WebSocketEventType.CAMERA_OFFLINE
        assert set(payload) == {"camera_id", "camera_name", "timestamp", "reason"}
        assert payload["reason"] == "Connection timeout"
        assert gpayload["reason"] == "Connection timeout"
        assert gpayload["previous_status"] == "online"

        # --- error with no reason: fallback text and error_code are contract ---
        (etype, payload), (gtype, gpayload) = _capture("online", "error", "error")
        assert etype == WebSocketEventType.CAMERA_ERROR
        assert set(payload) == {
            "camera_id", "camera_name", "error", "error_code", "timestamp",
        }
        assert payload["error"] == "Unknown error"
        assert payload["error_code"] is None
```

Red paths: any key rename breaks a `set(payload)` equality; `timestamp=None` → `fromisoformat(None)` raises TypeError; naive `datetime.now(None).isoformat()` → `tzinfo is None`; each `"Unknown error"` variant fails the error assert. Green on original (values match `CameraStatus` string-enum `.value`s and `_map_status_string_to_enum` mapping).

### T3 — debounce must read/write the camera-specific Redis key (kills cluster 4, 1 survivor) → `TestCameraServiceDebouncing`

```python
    @pytest.mark.asyncio
    async def test_debounce_reads_and_writes_camera_specific_key(
        self, mock_session, mock_camera, mock_redis, mock_emitter
    ):
        """Debounce state must be keyed by camera:status:debounce:<id> on every Redis call."""
        previous_camera = MagicMock()
        previous_camera.id = "front_door"
        previous_camera.status = "offline"

        mock_camera.status = "online"
        # Key-faithful fake: unlike the shared fixture, the fake Redis here answers
        # get()/delete() only for the exact key that setex() stored.
        store: dict = {}
        mock_redis.get = AsyncMock(side_effect=lambda key: store.get(key))
        mock_redis.setex = AsyncMock(side_effect=lambda key, ttl, value: store.__setitem__(key, value))
        mock_redis.delete = AsyncMock(side_effect=lambda key: store.pop(key, None))

        service = CameraService(mock_session, redis=mock_redis, emitter=mock_emitter)
        service.repository.get_by_id = AsyncMock(return_value=previous_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        # First change: recorded as pending, event debounced.
        await service.update_camera_status("front_door", "online")
        assert store == {f"{CAMERA_DEBOUNCE_KEY_PREFIX}front_door": "online"}
        mock_emitter.emit.assert_not_called()

        # Repeat of the same status: only a key-accurate get() sees it as stable.
        await service.update_camera_status("front_door", "online")
        mock_redis.get.assert_awaited_with(f"{CAMERA_DEBOUNCE_KEY_PREFIX}front_door")
        assert mock_emitter.emit.call_count == 2
```

Red on `get(None)` (fake returns `None` for the wrong key → status never "stable" → no emission, and `assert_awaited_with` records `get(None)`); green on original.

### T4 — status outside the known three emits only the generic event (kills cluster 8, 1 survivor) → `TestCameraServiceWebSocketEvents`

```python
    @pytest.mark.asyncio
    async def test_unknown_status_emits_only_generic_event(self, mock_session, mock_emitter):
        """A status outside online/offline/error must emit only camera.status_changed."""
        previous_camera = MagicMock()
        previous_camera.id = "front_door"
        previous_camera.status = "offline"

        camera = MagicMock()
        camera.id = "front_door"
        camera.name = "Front Door Camera"
        camera.status = "unknown"

        service = CameraService(mock_session, emitter=mock_emitter)
        service.repository.get_by_id = AsyncMock(return_value=previous_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, camera))

        await service.update_camera_status("front_door", "unknown")

        assert mock_emitter.emit.call_count == 1
        event_type, payload = mock_emitter.emit.call_args_list[0][0]
        assert event_type == WebSocketEventType.CAMERA_STATUS_CHANGED
        assert payload["status"] == "unknown"
        assert payload["previous_status"] == "offline"
```

Red on `specific_event_type = ""` (first emit carries `""` instead of the enum — the `is not None` guard passes — then `.value` raises `AttributeError`, swallowed upstream): the event-type assert fails. Green on original (sentinel `None` skips the specific emit entirely).

## Disposition notes

- **WP4.4 action:** add T1–T4 to `test_camera_service.py`; the four drafts together cover all 35 TEST-GAP survivors (T1: 7, T2: 26 [clusters 5+6+7] — also kills the 3 timestamp mutants of cluster 3, T3: 1, T4: 1).
- **Mutmut suppression:** the 78 EQUIVALENT survivors (clusters 9–13) are log-text/extra-dict and provably-dead mutations; recommend per-module equivalent-mutant suppression (`# pragma` not needed — mutmut equivalent list / skip-rule for `logger.*` argument and `extra` dict-literal-key mutations) rather than tests. Asserting log text would calcify debug output as contract.
- The 31 `null` keys were not yet verdicted at meta read time (16:58); re-check meta before finalizing module score.
