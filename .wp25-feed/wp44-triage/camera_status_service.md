# WP4.4 Triage Dossier — backend/services/camera_status_service.py

- **Module:** `backend/services/camera_status_service.py`
- **Survivors:** 57 of 140 mutants (83 killed, 0 unchecked)
- **Covering test file (only one):** `backend/tests/unit/services/test_camera_status_service.py`
  - Happy path + payload asserts: line 64 (`test_set_camera_status_updates_database_and_broadcasts`)
  - Unchanged-status skip: line 126; missing camera: line 156
  - Convenience methods: lines 179 / 220 / 261
  - Broadcast-failure: line 302; success info-log: line 350
  - Standalone `broadcast_camera_status_change`: lines 403 / 443 / 512 / 541
  - `_get_event_type_for_status`: lines 479–508
- **Diff source:** `uv run mutmut show <key>` for all 57 keys (no fallback needed; batch dump at `/tmp/wp25/wp44-triage/cam-status-diffs/all.json`).

## Why tests miss these (root causes in the existing suite)

1. `get_broadcaster` is patched with `autospec=True, return_value=mock` everywhere — the **call argument (the redis client) is never asserted**, so `get_broadcaster(None)` survives (autospec checks arity, not value).
2. Payload assertions on `call_args` check `"timestamp" in call_args` — **membership, not value** — so `timestamp = None` and naive `datetime.now(None)` survive.
3. Convenience-method tests assert `set_status(camera_id, status)` but **never assert `reason` reaches the broadcast payload** (it only survives via the payload).
4. Log assertions (`caplog`) check **message text only**, never the structured `extra=` payload — every `extra` key rename/None/drop in the three log sites survives. `exc_info` tweaks likewise invisible to `caplog.text`.
5. `mock_repo.get_by_id` call **arguments are never asserted** (only `set_status` is).
6. The autouse fixture (`caplog.set_level(logging.INFO)`, line 25) means the `logger.debug` unchanged-status branch is not even captured — its mutants are only killable by re-setting level to DEBUG.
7. Every test overwrites `service._repository = mock_repo` right after construction, so constructor wiring (`CameraRepository(session)`) is executed but never asserted.

## Cluster table (counts sum to 57)

| # | Cluster (pattern) | Count | Keys (≤3 examples) | Class | Kill route |
|---|-------------------|-------|--------------------|-------|------------|
| C1 | Convenience methods drop the `reason` argument (`set_camera_status(camera_id, STATUS, reason)` → `..., None)` / arg omitted) | 6 | `set_camera_online__mutmut_3`, `set_camera_offline__mutmut_6`, `set_camera_error__mutmut_3` | TEST-GAP | Draft T1: parametrize 3 methods, assert `call_args["reason"]` |
| C2 | `repository.get_by_id(camera_id)` → `get_by_id(None)` (wrong lookup key) | 1 | `set_camera_status__mutmut_2` | TEST-GAP | Draft T5: `get_by_id.assert_awaited_once_with("nonexistent")` |
| C3 | Redis client dropped on the way to `get_broadcaster(...)` (arg or `self._redis` set to `None`) | 3 | `__init____mutmut_2`, `_broadcast_status_change__mutmut_2`, `x_broadcast_camera_status_change__mutmut_2` | TEST-GAP | Draft T3: `mocked_get_broadcaster.assert_awaited_once_with(mock_redis)` |
| C4 | Broadcast payload timestamp broken (`timestamp = None` / `datetime.now(None)` naive) | 4 | `_broadcast_status_change__mutmut_3`, `_broadcast_status_change__mutmut_4`, `x_broadcast_camera_status_change__mutmut_3` (also `...__mutmut_4`) | TEST-GAP | Draft T2: `fromisoformat` + assert tz-aware UTC |
| C5 | Constructor wiring unasserted (`_repository = None` / `CameraRepository(None)`) | 2 | `__init____mutmut_3`, `__init____mutmut_4` | TEST-GAP | Draft T3 (folded): `service._repository.session is mock_session` (tests overwrite `_repository` later, so the ctor's real wiring is never observed) |
| C6 | `self._session = None` — attribute is written but **never read** by the module (repo gets the `session` param directly; no external consumer found) | 1 | `__init____mutmut_1` | EQUIVALENT | dead store, not killable meaningfully |
| C7 | Missing-camera `logger.warning` payload (msg→`None`, `extra=None`/dropped, key renames `XXcamera_idXX`/`CAMERA_ID`/`XXstatusXX`/`STATUS`) | 7 | `set_camera_status__mutmut_4`, `set_camera_status__mutmut_8`, `set_camera_status__mutmut_11` | TEST-GAP | Draft T5: caplog record message + `record.camera_id`/`record.status` |
| C8 | Unchanged-status `logger.debug` payload (msg→`None`, `extra=None`/dropped, key renames) — debug-level, not captured at the suite's INFO level; nobody should assert debug payloads | 7 | `set_camera_status__mutmut_14`, `set_camera_status__mutmut_15`, `set_camera_status__mutmut_20` | LOW-VALUE | skip (would need `caplog.set_level(DEBUG)` for noise) |
| C9 | Success-path `logger.info` structured payload (`extra=None`/dropped + renames of `camera_id`, `event_type`, `previous_status`, `new_status`, `reason`, `subscribers`) | 14 | `_broadcast_status_change__mutmut_27`, `_broadcast_status_change__mutmut_33`, `_broadcast_status_change__mutmut_41` | TEST-GAP | Draft T4: assert all six `record.*` fields (message already asserted at test-file line 350) |
| C10 | Failure-path `logger.error` payload (`extra=None`/dropped, `camera_id`/`status`/`error` renames, `str(e)`→`str(None)`) | 9 | `_broadcast_status_change__mutmut_43`, `_broadcast_status_change__mutmut_50`, `_broadcast_status_change__mutmut_54` | TEST-GAP | Draft T6: assert `record.camera_id`/`record.status`/`"Redis down" in record.error` |
| C11 | Failure-path `exc_info=True` → `None`/`False`/dropped (traceback no longer attached to the error record) | 3 | `_broadcast_status_change__mutmut_44`, `_broadcast_status_change__mutmut_47`, `_broadcast_status_change__mutmut_55` | TEST-GAP | Draft T6 (folded): `assert record.exc_info is not None` |

**Totals:** 6+1+3+4+2+1+7+7+14+9+3 = **57** ✓ · TEST-GAP 49 (C1,C2,C3,C4,C5,C7,C9,C10,C11) · LOW-VALUE 7 (C8) · EQUIVALENT 1 (C6).

## Drafted tests (6 drafts, kill 49 survivors: C1–C5, C7, C9–C11)

All UNVERIFIED — not yet run red/green. Append to `backend/tests/unit/services/test_camera_status_service.py`; add `timedelta` to the existing `from datetime import UTC, datetime` import. TDD procedure for each: run against the mutant source copy (mutant applied) → the new assertion fails (red); run against original `backend/services/camera_status_service.py` → passes (green).

### T1 — convenience methods forward camera_id and reason (kills C1 ×6)

```python
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "expected_status"),
    [
        ("set_camera_online", "online"),
        ("set_camera_offline", "offline"),
        ("set_camera_error", "error"),
    ],
)
async def test_convenience_methods_forward_reason_to_broadcast(
    method_name: str,
    expected_status: str,
) -> None:
    """Convenience methods must pass camera_id and reason through to the payload.

    WP4.4: kills reason-dropped mutants (set_camera_*_mutmut_3/_6) — the existing
    convenience tests assert set_status args but never the broadcast reason.
    """
    mock_session = MagicMock()
    mock_redis = _FakeRedis()
    start_status = "offline" if expected_status == "online" else "online"
    mock_camera = _create_mock_camera(status=start_status)

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=mock_camera)

    async def mock_set_status(camera_id: str, status: str) -> Camera:
        mock_camera.status = status
        return mock_camera

    mock_repo.set_status = AsyncMock(side_effect=mock_set_status)

    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_camera_status = AsyncMock(return_value=1)

    service = CameraStatusService(mock_session, mock_redis)  # type: ignore[arg-type]
    service._repository = mock_repo

    with patch(
        "backend.services.camera_status_service.get_broadcaster",
        return_value=mock_broadcaster,
        autospec=True,
    ):
        method = getattr(service, method_name)
        await method(camera_id="front_door", reason="Operator intervention")

    mock_repo.get_by_id.assert_awaited_once_with("front_door")
    mock_repo.set_status.assert_awaited_once_with("front_door", expected_status)
    call_args = mock_broadcaster.broadcast_camera_status.await_args.args[0]
    assert call_args["reason"] == "Operator intervention"
    assert call_args["status"] == expected_status
    assert call_args["previous_status"] == start_status
```

### T2 — payload timestamp is real and tz-aware (kills C4 ×4)

```python
@pytest.mark.asyncio
async def test_broadcast_payload_timestamp_is_timezone_aware() -> None:
    """Payload timestamp must be a tz-aware ISO-8601 string, not just a key.

    WP4.4: kills timestamp=None and datetime.now(None) mutants — existing tests
    only assert `"timestamp" in call_args`.
    """
    mock_redis = _FakeRedis()
    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_camera_status = AsyncMock(return_value=1)

    with patch(
        "backend.services.camera_status_service.get_broadcaster",
        return_value=mock_broadcaster,
        autospec=True,
    ):
        await broadcast_camera_status_change(
            redis=mock_redis,  # type: ignore[arg-type]
            camera_id="front_door",
            camera_name="Front Door Camera",
            status="online",
        )

    call_args = mock_broadcaster.broadcast_camera_status.await_args.args[0]
    parsed = datetime.fromisoformat(call_args["timestamp"])  # fails on None mutant
    assert parsed.tzinfo is not None  # fails on datetime.now(None) mutant
    assert parsed.utcoffset() == timedelta(0)
```

(The class-side timestamp in `_broadcast_status_change` uses the identical expression; T4's happy-path run executes it, so mirror the check there too — see note under T4.)

### T3 — redis client + repository wiring survive construction (kills C3 ×3, C5 ×2)

```python
@pytest.mark.asyncio
async def test_service_wires_redis_and_session_to_dependencies() -> None:
    """The redis/session passed to the constructor must reach broadcaster/repository.

    WP4.4: kills `self._redis = None`, `get_broadcaster(None)`,
    `self._repository = None`, `CameraRepository(None)` — existing tests overwrite
    `_repository` and patch `get_broadcaster` without asserting its call args.
    """
    mock_session = MagicMock()
    mock_redis = _FakeRedis()
    mock_camera = _create_mock_camera(status="online")

    service = CameraStatusService(mock_session, mock_redis)  # type: ignore[arg-type]

    assert isinstance(service._repository, CameraRepository)
    assert service._repository.session is mock_session

    async def mock_set_status(camera_id: str, status: str) -> Camera:
        mock_camera.status = status
        return mock_camera

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=mock_camera)
    mock_repo.set_status = AsyncMock(side_effect=mock_set_status)
    service._repository = mock_repo

    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_camera_status = AsyncMock(return_value=1)

    with patch(
        "backend.services.camera_status_service.get_broadcaster",
        return_value=mock_broadcaster,
        autospec=True,
    ) as mock_get_broadcaster:
        await service.set_camera_status(camera_id="front_door", status="offline")
        mock_get_broadcaster.assert_awaited_once_with(mock_redis)

        await broadcast_camera_status_change(
            redis=mock_redis,  # type: ignore[arg-type]
            camera_id="front_door",
            camera_name="Front Door Camera",
            status="offline",
        )
        mock_get_broadcaster.assert_awaited_with(mock_redis)
```

(`from backend.repositories.camera_repository import CameraRepository` must be added to imports.)

### T4 — success info-log carries the full structured payload (kills C9 ×14)

```python
@pytest.mark.asyncio
async def test_broadcast_success_log_has_structured_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The success log's `extra` payload is an observability contract.

    WP4.4: kills extra=None / extra-dropped / 12 key-rename mutants — the existing
    test at line 350 asserts only the message text.
    """
    mock_session = MagicMock()
    mock_redis = _FakeRedis()
    mock_camera = _create_mock_camera(status="online")

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=mock_camera)

    async def mock_set_status(camera_id: str, status: str) -> Camera:
        mock_camera.status = status
        return mock_camera

    mock_repo.set_status = AsyncMock(side_effect=mock_set_status)

    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_camera_status = AsyncMock(return_value=2)

    service = CameraStatusService(mock_session, mock_redis)  # type: ignore[arg-type]
    service._repository = mock_repo

    with patch(
        "backend.services.camera_status_service.get_broadcaster",
        return_value=mock_broadcaster,
        autospec=True,
    ):
        await service.set_camera_status(
            camera_id="front_door",
            status="offline",
            reason="Connection timeout",
        )

    records = [r for r in caplog.records if "Broadcast camera status change" in r.message]
    assert len(records) == 1
    record = records[0]
    assert record.camera_id == "front_door"
    assert record.event_type == "camera.offline"
    assert record.previous_status == "online"
    assert record.new_status == "offline"
    assert record.reason == "Connection timeout"
    assert record.subscribers == 2
```

Note: `_broadcast_status_change__mutmut_3/_4` (class-side timestamp) are killed by T4 if the payload check is mirrored: add `parsed = datetime.fromisoformat(mock_broadcaster.broadcast_camera_status.await_args.args[0]["timestamp"]); assert parsed.tzinfo is not None` — or rely on T2's pattern being copied into the service flow; T2 alone only covers the standalone function. Attribute-missing on a renamed LogRecord raises AttributeError → red, so C9 kills are exact.

### T5 — missing-camera path: correct lookup key + warning payload (kills C2 ×1, C7 ×7)

```python
@pytest.mark.asyncio
async def test_missing_camera_warning_carries_structured_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Not-found path must look up by camera_id and log a structured warning.

    WP4.4: kills `get_by_id(None)` and the warning msg/extra mutants (set_camera_status
    _4/_5/_7/_8/_9/_10/_11) — the existing not-found test asserts only the return value.
    """
    mock_session = MagicMock()
    mock_redis = _FakeRedis()

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=None)

    service = CameraStatusService(mock_session, mock_redis)  # type: ignore[arg-type]
    service._repository = mock_repo

    result = await service.set_camera_status(camera_id="nonexistent", status="offline")

    assert result is None
    mock_repo.get_by_id.assert_awaited_once_with("nonexistent")

    records = [r for r in caplog.records if "camera not found" in r.message]
    assert len(records) == 1
    record = records[0]
    assert record.camera_id == "nonexistent"
    assert record.status == "offline"
```

### T6 — broadcast-failure error log: payload fields + traceback attached (kills C10 ×9, C11 ×3)

```python
@pytest.mark.asyncio
async def test_broadcast_failure_log_has_structured_fields_and_exc_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Best-effort broadcast failures must be diagnosable from the error record.

    WP4.4: kills error-extra renames/None/drop, `str(e)`->`str(None)`, and the
    exc_info mutants — the existing test at line 302 asserts only the message substring.
    """
    mock_session = MagicMock()
    mock_redis = _FakeRedis()
    mock_camera = _create_mock_camera(status="online")

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=mock_camera)

    async def mock_set_status(camera_id: str, status: str) -> Camera:
        mock_camera.status = status
        return mock_camera

    mock_repo.set_status = AsyncMock(side_effect=mock_set_status)

    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_camera_status = AsyncMock(side_effect=RuntimeError("Redis down"))

    service = CameraStatusService(mock_session, mock_redis)  # type: ignore[arg-type]
    service._repository = mock_repo

    with patch(
        "backend.services.camera_status_service.get_broadcaster",
        return_value=mock_broadcaster,
        autospec=True,
    ):
        await service.set_camera_status(camera_id="front_door", status="offline")

    records = [r for r in caplog.records if "Failed to broadcast camera status change" in r.message]
    assert len(records) == 1
    record = records[0]
    assert record.camera_id == "front_door"
    assert record.status == "offline"
    assert "Redis down" in record.error
    assert record.exc_info is not None
```

## Notes

- LogRecord `extra` fields: `backend.core.logging.get_logger` returns a stdlib `logging.Logger`, so `extra=` keys land on the caplog-captured record as attributes (`record.camera_id` etc.); renamed keys leave the old attribute absent → `AttributeError`/missing from filter, which is the kill mechanism for C7/C9/C10.
- C8 (debug payload, 7 mutants) deliberately not drafted: killing it requires `caplog.set_level(logging.DEBUG)` inside a test whose whole subject is a no-op skip path — pure assertion noise per WP4.4 LOW-VALUE criteria. (If the baseline later wants the number, it is the same one-test pattern as T5 with level DEBUG and message "status unchanged".)
- C6 (`self._session = None`) verified dead: `self._session` is never read inside `camera_status_service.py` (repository receives the constructor's `session` parameter directly) and no external module reads `CameraStatusService._session` — EQUIVALENT, no action.
- Mutant `set_camera_status__mutmut_2` (`get_by_id(None)`) is otherwise unkillable through mocked flows (mocks return regardless of args); only the call-args assertion in T5/T1 pins it.
