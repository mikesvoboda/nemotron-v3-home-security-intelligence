# TARGET-MODULE: backend.services.event_broadcaster
"""Batch-31 kill battery B: the 20 publish wrappers of ``EventBroadcaster``.

Every wrapper runs the same 5-phase contract, table-driven below:
  P1 full-form payload: publishes EXACTLY
     (channel, <message>.model_dump(mode="json")) and returns the subscriber
     count, and emits its shipped DEBUG line verbatim;
  P2 bare payload (no "type" key): the wrap branch must produce the SAME
     published payload + same DEBUG line (kills guard polarity, wrap-dict
     value/case mutations and the wrap `= None` family);
  P3 payload missing ONE required field: ValueError with shipped prefix,
     exactly ONE "Field required" in its text (kills the
     ``.get("data", ...)`` key-swap/None family — they validate {} / None and
     produce all-fields-missing instead), nothing published;
  P4 publish raising: original exception propagates, shipped
     "Failed to broadcast X: boom" ERROR pinned (kills the catch-all log
     family and the swallow mutants);
  P5 (payload-shape wrappers) payload equality covers the literal
     {"type": ..., "data": validated} dict's key/value mutations directly.

COMPARATOR NOTE (found the hard way this session): every published-payload
assert goes through ``_pub``, which compares ``repr`` rather than ``==``. These
schemas' enums are ``str`` subclasses, so ``WebSocketAlertSeverity.HIGH ==
"high"`` is True and a plain ``==`` silently rates a python-mode dump (enum
object) equal to the shipped json-mode dump (str). Under ``==`` 14 ``mode=``
keys looked EQUIVALENT and were ledgered as such; ``repr`` exposes them as
KILLABLE and they are killed here. An earlier version of this file claimed the
``mode=`` family was "equivalent because the python dump equals the json dump"
-- that claim was an artifact of the weak comparator, not a measurement.

Honesty ledger for the 91 keys STILL green here (each argued against the
shipped def, and every ``mode=`` member re-measured):
  * ``model_dump(mode=...)`` -> None / "XXjsonXX" / "JSON" on the wrappers
    whose dump contains NO enum -- batch analysis x3, detection x2,
    scene_change, zone x4, entity x2, ai x2 and summary_update's three dump
    sites. pydantic 2.13 treats an unknown/None mode as "python", and for an
    all-JSON-native payload the python dump IS the json dump, so ``_pub``
    cannot tell them apart -- which is exactly why they stay green. The same
    mutation on a dump that DOES carry a str-subclass enum is observable (the
    mutant publishes ``<RiskLevel.HIGH: 'high'>`` where shipped publishes
    ``'high'``) and IS killed: ``broadcast_event``, ``broadcast_camera_status``,
    ``broadcast_service_status`` (whose mode family is then fully killed) and
    ``broadcast_worker_status`` keep only their non-mode greens.
  * the wrap-dict ``{"type": T, "data": ...}`` entry, KEY and VALUE renames
    alike: the wrap dict is write-only -- the guard exists only to feed
    ``.get("data", {})``, and the published payload is rebuilt from the message
    model, whose ``type`` is a Literal the mutation never touches.
  * ``broadcast_summary_update`` ``{"hourly": None, "daily": None}`` KEY
    renames (_2.._5): the dict is consumed by
    ``WebSocketSummaryUpdateData.model_validate`` and re-dumped; the mutated
    keys are dropped as extras and the published dict always carries
    hourly/daily.
  * ``broadcast_alert`` _7/_8/_9 (the ALERT_DELETED arm's ``mode=``):
    WebSocketAlertDeletedData is ``{id: str, reason: str | None}`` -- no enum,
    no datetime -- so this arm's python dump equals its json dump. _29/_30/_31
    (the non-deleted arm, which DOES carry severity/status enums) are killed.
The ``.get("data", {})`` -> None / trailing-comma survivors are NOT
equivalent and P6 kills them: a ``{"type": T}``-only input passes the guard
without a "data" key, shipped validates {} (>= 2 "Field required") while the
mutants validate None ("Input should be a valid dictionary", 0).
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Fragment lives outside the repo tree during authoring (/home/agent/runs/b31-frags);
# the sweep always runs with the repo root (or the mutant home) as cwd.
_ROOT = str(Path.cwd())
if (Path(_ROOT) / "backend" / "services" / "event_broadcaster.py").is_file():
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from backend.api.schemas.websocket import (  # noqa: E402
    WebSocketAlertAcknowledgedMessage,
    WebSocketAlertCreatedMessage,
    WebSocketAlertData,
    WebSocketAlertDeletedData,
    WebSocketAlertDeletedMessage,
    WebSocketAlertDismissedMessage,
    WebSocketAlertEventType,
    WebSocketAlertResolvedMessage,
    WebSocketAlertUpdatedMessage,
    WebSocketBatchAnalysisCompletedData,
    WebSocketBatchAnalysisCompletedMessage,
    WebSocketBatchAnalysisFailedData,
    WebSocketBatchAnalysisFailedMessage,
    WebSocketBatchAnalysisStartedData,
    WebSocketBatchAnalysisStartedMessage,
    WebSocketCameraStatusData,
    WebSocketCameraStatusMessage,
    WebSocketDetectionBatchData,
    WebSocketDetectionBatchMessage,
    WebSocketDetectionNewData,
    WebSocketDetectionNewMessage,
    WebSocketEventData,
    WebSocketEventMessage,
    WebSocketSceneChangeData,
    WebSocketSceneChangeMessage,
    WebSocketServiceStatusData,
    WebSocketServiceStatusMessage,
    WebSocketSummaryData,
    WebSocketSummaryUpdateData,
    WebSocketSummaryUpdateMessage,
    WebSocketWorkerStatusData,
    WebSocketWorkerStatusMessage,
)
from backend.core.websocket.event_schemas import (  # noqa: E402
    AIActionRecognizedPayload,
    AIThreatDetectedPayload,
    EntityMatchedPayload,
    EntityTrackUpdatedPayload,
    ZoneApproachPayload,
    ZoneCrossingPayload,
    ZoneDwellAlertPayload,
    ZoneDwellStartedPayload,
)
from backend.services import event_broadcaster as eb  # noqa: E402
from backend.services.event_broadcaster import EventBroadcaster  # noqa: E402

CHANNEL = "b31:chan"


def _run(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _ListHandler(logging.Handler):
    def __init__(self, sink: list[logging.LogRecord]) -> None:
        super().__init__()
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        self.sink.append(record)


class LogCapture:
    def __enter__(self) -> LogCapture:
        self.records: list[logging.LogRecord] = []
        self._handler = _ListHandler(self.records)
        eb.logger.addHandler(self._handler)
        self._old_level = eb.logger.level
        eb.logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, *exc: object) -> None:
        eb.logger.removeHandler(self._handler)
        eb.logger.setLevel(self._old_level)

    def texts(self) -> list[str]:
        return [r.getMessage() for r in self.records]


class FakeRedis:
    def __init__(self) -> None:
        self.published: list[tuple[Any, Any]] = []

    async def publish(self, channel: Any, data: Any) -> int:
        self.published.append((channel, data))
        return 3


class RaisingRedis(FakeRedis):
    async def publish(self, channel: Any, data: Any) -> int:
        raise RuntimeError("boom")


def _broadcaster(redis: Any) -> EventBroadcaster:
    return EventBroadcaster(redis, channel_name=CHANNEL)


def _pub(redis: Any, expected: Any) -> list[Any]:
    """PUBLISHED payload of ``redis`` vs ``expected``, TYPE-STRICTLY equal.

    Plain ``==`` is blind to the ``model_dump(mode=...)`` family: these schemas'
    enums are ``str`` subclasses, so ``WebSocketAlertSeverity.HIGH == "high"``
    is True and a python-mode dump (enum object) compares equal to the shipped
    json-mode dump (plain str) even though the published wire value differs.
    ``repr`` keeps the type, which is what the Redis payload actually carries.
    Every battery-B payload assert goes through here for that reason.
    """
    got = redis.published
    assert len(got) == len(expected), f"publish count: {got!r} vs {expected!r}"
    for (ch, payload), exp in zip(got, expected, strict=True):
        assert ch == exp[0], f"channel: {ch!r} vs {exp[0]!r}"
        assert repr(payload) == repr(exp[1]), (
            f"payload (type-strict):\n  got  {payload!r}\n  want {exp[1]!r}"
        )
    return got


def _strip(payload: dict[str, Any], drop: str) -> dict[str, Any]:
    """Copy of a wrapped payload with one required field dropped from data."""
    p = {k: (dict(v) if isinstance(v, dict) else v) for k, v in payload.items()}
    del p["data"][drop]
    return p


def _strip_payload(payload: dict[str, Any], drop: str) -> dict[str, Any]:
    """Copy of a payload-shape event with one required field dropped."""
    p = dict(payload)
    del p[drop]
    return p


def run_wrapped(
    method: str,
    full: dict[str, Any],
    expected: Callable[[dict[str, Any]], dict[str, Any]],
    debug_line: str,
    drop: str,
    err_prefix: str,
    failed_label: str,
    msg_type: str | None = None,
) -> None:
    """5-phase contract for guard+get('data')+message-model wrappers."""
    # P1 full form
    r1 = FakeRedis()
    b1 = _broadcaster(r1)
    with LogCapture() as cap1:
        n = _run(getattr(b1, method)(dict(full)))
    assert n == 3, f"{method}: subscriber count"
    _pub(r1, [(CHANNEL, expected(full))])  # P1 payload
    assert cap1.texts() == [debug_line], f"{method}: P1 debug"

    # P2 bare form: the guard must wrap it to the SAME full form the shipped
    # code would have produced, so the expectation is built from the wrapped
    # dict (not from `full`, which may carry sibling keys the wrap cannot add).
    # Wrappers WITHOUT a guard branch (broadcast_service_status) skip P2.
    if msg_type is not None:
        wrapped = {"type": msg_type, "data": dict(full["data"])}
        r2 = FakeRedis()
        b2 = _broadcaster(r2)
        with LogCapture() as cap2:
            n = _run(getattr(b2, method)(dict(full["data"])))
        assert n == 3, f"{method}: bare subscriber count"
        _pub(r2, [(CHANNEL, expected(wrapped))])  # P2 payload
        assert cap2.texts() == [debug_line], f"{method}: P2 debug"

    # P3 one required field missing -> shipped ValueError, ONE Field-required
    r3 = FakeRedis()
    b3 = _broadcaster(r3)
    with LogCapture() as cap3:
        try:
            _run(getattr(b3, method)(_strip(full, drop)))
            raise AssertionError(f"{method}: expected ValueError")
        except ValueError as ve:
            text = str(ve)
            assert text.startswith(err_prefix), f"{method}: prefix {text[:60]!r}"
            assert text.count("Field required") == 1, f"{method}: {text[:120]!r}"
            assert drop in text, f"{method}: dropped field {drop!r} unnamed"
    assert r3.published == [], f"{method}: nothing published on invalid"
    errs = [t for t in cap3.texts() if "validation failed" in t]
    assert len(errs) == 1, f"{method}: validation ERROR log count {cap3.texts()}"

    # P6 input has "type" but NO "data" key: shipped .get("data", {})
    # validates {} -> EVERY required field is enumerated in the error text.
    # The .get("data", None) / .get("data", ) mutants validate None instead:
    # pydantic says "Input should be a valid dictionary" with ZERO
    # Field-required entries. >= 2 pins the shipped default.
    r6 = FakeRedis()
    b6 = _broadcaster(r6)
    try:
        _run(getattr(b6, method)({"type": full.get("type", "x")}))
        raise AssertionError(f"{method}: expected ValueError for missing data")
    except ValueError as ve:
        text6 = str(ve)
        assert text6.startswith(err_prefix), f"{method}: P6 prefix {text6[:60]!r}"
        assert text6.count("Field required") >= 2, f"{method}: P6 {text6[:140]!r}"
    assert r6.published == [], f"{method}: P6 nothing published"

    # P4 publish raises -> original propagates with shipped failure ERROR
    b4 = _broadcaster(RaisingRedis())
    with LogCapture() as cap4:
        try:
            _run(getattr(b4, method)(dict(full)))
            raise AssertionError(f"{method}: expected RuntimeError")
        except RuntimeError as re_exc:
            assert str(re_exc) == "boom"
    assert f"Failed to broadcast {failed_label}: boom" in cap4.texts(), cap4.texts()


def run_payload_shape(
    method: str,
    payload: dict[str, Any],
    msg_type: str,
    payload_cls: Any,
    debug_line: str,
    drop: str,
    err_prefix: str,
    failed_label: str,
) -> None:
    """Contract for the zone/entity/ai wrappers (payload validated whole)."""
    expected = {
        "type": msg_type,
        "data": payload_cls.model_validate(payload).model_dump(mode="json"),
    }

    r1 = FakeRedis()
    b1 = _broadcaster(r1)
    with LogCapture() as cap1:
        n = _run(getattr(b1, method)(dict(payload)))
    assert n == 3, f"{method}: subscriber count"
    _pub(r1, [(CHANNEL, expected)])  # P1 payload
    assert cap1.texts() == [debug_line], f"{method}: P1 debug"

    r3 = FakeRedis()
    b3 = _broadcaster(r3)
    with LogCapture() as cap3:
        try:
            _run(getattr(b3, method)(_strip_payload(payload, drop)))
            raise AssertionError(f"{method}: expected ValueError")
        except ValueError as ve:
            text = str(ve)
            assert text.startswith(err_prefix), f"{method}: prefix {text[:60]!r}"
            assert text.count("Field required") == 1, f"{method}: {text[:120]!r}"
            assert drop in text, f"{method}: dropped field {drop!r} unnamed"
    assert r3.published == [], f"{method}: nothing published on invalid"
    errs = [t for t in cap3.texts() if "validation failed" in t]
    assert len(errs) == 1, f"{method}: validation ERROR log count {cap3.texts()}"

    b4 = _broadcaster(RaisingRedis())
    with LogCapture() as cap4:
        try:
            _run(getattr(b4, method)(dict(payload)))
            raise AssertionError(f"{method}: expected RuntimeError")
        except RuntimeError as re_exc:
            assert str(re_exc) == "boom"
    assert f"Failed to broadcast {failed_label}: boom" in cap4.texts(), cap4.texts()


# ---------------------------------------------------------------------------
# broadcast_event — 37 survivor keys: _1, _2, _3, _4, _5, _6, _7, _8, _9, _10, _11, _12, _13, _14, _15, _16, _17, _18, _19, _20, _21, _22, _23, _24, _25, _26, _27, _28, _29, _30, _31, _32, _33, _34, _35, _36, _37
# ---------------------------------------------------------------------------
_BROADCAST_EVENT_FULL: dict[str, Any] = {
    "type": "event",
    "data": {
        "id": 1,
        "event_id": 1,
        "batch_id": "batch_1",
        "camera_id": "cam-9",
        "risk_score": 75,
        "risk_level": "high",
        "summary": "s",
        "reasoning": "r",
        "started_at": "2025-12-23T12:00:00",
    },
}


def _broadcast_event_expected(p: dict[str, Any]) -> dict[str, Any]:
    return WebSocketEventMessage(data=WebSocketEventData.model_validate(p["data"])).model_dump(
        mode="json"
    )


def test_broadcast_event_contract() -> None:
    run_wrapped(
        "broadcast_event",
        _BROADCAST_EVENT_FULL,
        _broadcast_event_expected,
        "Event broadcast to Redis: event (subscribers: 3)",
        "camera_id",
        "Invalid event message format: ",
        "event",
        "event",
    )


# ---------------------------------------------------------------------------
# broadcast_service_status — 15 survivor keys: _3, _5, _15, _16, _18, _19, _20, _21, _23, _24, _25, _33, _34, _35, _36
# ---------------------------------------------------------------------------
_BROADCAST_SERVICE_STATUS_FULL: dict[str, Any] = {
    "type": "service_status",
    "data": {"service": "svc-a", "status": "healthy", "message": "ok"},
    "timestamp": "2026-01-01T00:00:00Z",
}


def _broadcast_service_status_expected(p: dict[str, Any]) -> dict[str, Any]:
    return WebSocketServiceStatusMessage(
        data=WebSocketServiceStatusData.model_validate(p["data"]),
        timestamp=p.get("timestamp", ""),
    ).model_dump(mode="json")


def test_broadcast_service_status_contract() -> None:
    run_wrapped(
        "broadcast_service_status",
        _BROADCAST_SERVICE_STATUS_FULL,
        _broadcast_service_status_expected,
        "Service status broadcast to Redis: service_status (subscribers: 3)",
        "service",
        "Invalid service status message format: ",
        "service status",
        None,
    )


# ---------------------------------------------------------------------------
# broadcast_scene_change — 15 survivor keys: _1, _2, _5, _6, _7, _8, _13, _15, _23, _24, _25, _33, _34, _35, _36
# ---------------------------------------------------------------------------
_BROADCAST_SCENE_CHANGE_FULL: dict[str, Any] = {
    "type": "scene_change",
    "data": {
        "id": 5,
        "camera_id": "cam-9",
        "detected_at": "2026-01-03T10:30:00Z",
        "change_type": "view_blocked",
        "similarity_score": 0.23,
    },
}


def _broadcast_scene_change_expected(p: dict[str, Any]) -> dict[str, Any]:
    return WebSocketSceneChangeMessage(
        data=WebSocketSceneChangeData.model_validate(p["data"])
    ).model_dump(mode="json")


def test_broadcast_scene_change_contract() -> None:
    run_wrapped(
        "broadcast_scene_change",
        _BROADCAST_SCENE_CHANGE_FULL,
        _broadcast_scene_change_expected,
        "Scene change broadcast to Redis: scene_change (subscribers: 3)",
        "camera_id",
        "Invalid scene change message format: ",
        "scene change",
        "scene_change",
    )


# ---------------------------------------------------------------------------
# broadcast_camera_status — 12 survivor keys: _5, _6, _7, _8, _13, _15, _23, _24, _25, _34, _35, _36
# ---------------------------------------------------------------------------
_BROADCAST_CAMERA_STATUS_FULL: dict[str, Any] = {
    "type": "camera_status",
    "data": {
        "event_type": "camera.offline",
        "camera_id": "cam-9",
        "camera_name": "Cam Nine",
        "status": "offline",
        "timestamp": "2026-01-09T10:30:00Z",
    },
}


def _broadcast_camera_status_expected(p: dict[str, Any]) -> dict[str, Any]:
    return WebSocketCameraStatusMessage(
        data=WebSocketCameraStatusData.model_validate(p["data"])
    ).model_dump(mode="json")


def test_broadcast_camera_status_contract() -> None:
    run_wrapped(
        "broadcast_camera_status",
        _BROADCAST_CAMERA_STATUS_FULL,
        _broadcast_camera_status_expected,
        "Camera status broadcast to Redis: camera_status (camera_id: cam-9, status: offline, subscribers: 3)",
        "camera_id",
        "Invalid camera status message format: ",
        "camera status",
        "camera_status",
    )


# ---------------------------------------------------------------------------
# broadcast_worker_status — 20 survivor keys: _5, _6, _7, _8, _13, _15, _29, _30, _31, _32, _39, _40, _41, _42, _43, _44, _45, _46, _47, _48
# ---------------------------------------------------------------------------
_BROADCAST_WORKER_STATUS_FULL: dict[str, Any] = {
    "type": "worker_status",
    "data": {
        "event_type": "worker.started",
        "worker_name": "w1",
        "worker_type": "detection",
        "timestamp": "2026-01-13T10:30:00Z",
    },
    "timestamp": "2026-01-13T10:30:00Z",
}


def _broadcast_worker_status_expected(p: dict[str, Any]) -> dict[str, Any]:
    return WebSocketWorkerStatusMessage(
        data=WebSocketWorkerStatusData.model_validate(p["data"]),
        timestamp=p.get("timestamp"),
    ).model_dump(mode="json")


def test_broadcast_worker_status_contract() -> None:
    run_wrapped(
        "broadcast_worker_status",
        _BROADCAST_WORKER_STATUS_FULL,
        _broadcast_worker_status_expected,
        "Worker status broadcast to Redis: worker_status (worker: w1, event: worker.started, subscribers: 3)",
        "worker_name",
        "Invalid worker status message format: ",
        "worker status",
        "worker_status",
    )


# ---------------------------------------------------------------------------
# broadcast_detection_new — 40 survivor keys: _1, _2, _3, _4, _5, _6, _7, _8, _9, _10, _11, _12, _13, _14, _15, _16, _17, _18, _19, _20, _21, _22, _23, _24, _25, _26, _27, _28, _29, _30, _31, _32, _33, _34, _35, _36, _37, _38, _39, _40
# ---------------------------------------------------------------------------
_BROADCAST_DETECTION_NEW_FULL: dict[str, Any] = {
    "type": "detection.new",
    "data": {
        "detection_id": 123,
        "batch_id": "batch_abc",
        "camera_id": "cam-9",
        "label": "person",
        "confidence": 0.95,
        "timestamp": "2026-01-13T10:30:00Z",
    },
}


def _broadcast_detection_new_expected(p: dict[str, Any]) -> dict[str, Any]:
    return WebSocketDetectionNewMessage(
        data=WebSocketDetectionNewData.model_validate(p["data"])
    ).model_dump(mode="json")


def test_broadcast_detection_new_contract() -> None:
    run_wrapped(
        "broadcast_detection_new",
        _BROADCAST_DETECTION_NEW_FULL,
        _broadcast_detection_new_expected,
        "Detection new broadcast to Redis: detection.new (detection_id: 123, camera_id: cam-9, subscribers: 3)",
        "camera_id",
        "Invalid detection new message format: ",
        "detection new",
        "detection.new",
    )


# ---------------------------------------------------------------------------
# broadcast_detection_batch — 43 survivor keys: _1, _2, _3, _4, _5, _6, _7, _8, _9, _10, _11, _12, _13, _14, _15, _16, _17, _18, _19, _20, _21, _22, _23, _24, _25, _26, _27, _28, _29, _30, _31, _32, _33, _34, _35, _36, _37, _38, _39, _40, _41, _42, _43
# ---------------------------------------------------------------------------
_BROADCAST_DETECTION_BATCH_FULL: dict[str, Any] = {
    "type": "detection.batch",
    "data": {
        "batch_id": "b7",
        "camera_id": "cam-9",
        "detection_ids": [1, 2],
        "detection_count": 2,
        "started_at": "2026-01-13T10:30:00Z",
        "closed_at": "2026-01-13T10:31:00Z",
    },
}


def _broadcast_detection_batch_expected(p: dict[str, Any]) -> dict[str, Any]:
    return WebSocketDetectionBatchMessage(
        data=WebSocketDetectionBatchData.model_validate(p["data"])
    ).model_dump(mode="json")


def test_broadcast_detection_batch_contract() -> None:
    run_wrapped(
        "broadcast_detection_batch",
        _BROADCAST_DETECTION_BATCH_FULL,
        _broadcast_detection_batch_expected,
        "Detection batch broadcast to Redis: detection.batch (batch_id: b7, camera_id: cam-9, detection_count: 2, subscribers: 3)",
        "camera_id",
        "Invalid detection batch message format: ",
        "detection batch",
        "detection.batch",
    )


# ---------------------------------------------------------------------------
# broadcast_batch_analysis_started — 15 survivor keys: _1, _2, _5, _6, _7, _8, _13, _15, _23, _24, _25, _26, _34, _35, _36
# ---------------------------------------------------------------------------
_BROADCAST_BATCH_ANALYSIS_STARTED_FULL: dict[str, Any] = {
    "type": "batch.analysis_started",
    "data": {
        "batch_id": "b7",
        "camera_id": "cam-9",
        "detection_count": 3,
        "queue_position": 0,
        "started_at": "2026-01-13T12:01:30.000Z",
    },
}


def _broadcast_batch_analysis_started_expected(p: dict[str, Any]) -> dict[str, Any]:
    return WebSocketBatchAnalysisStartedMessage(
        data=WebSocketBatchAnalysisStartedData.model_validate(p["data"])
    ).model_dump(mode="json")


def test_broadcast_batch_analysis_started_contract() -> None:
    run_wrapped(
        "broadcast_batch_analysis_started",
        _BROADCAST_BATCH_ANALYSIS_STARTED_FULL,
        _broadcast_batch_analysis_started_expected,
        "Batch analysis started broadcast to Redis: batch.analysis_started (batch_id: b7, camera_id: cam-9, subscribers: 3)",
        "camera_id",
        "Invalid batch analysis started message format: ",
        "batch analysis started",
        "batch.analysis_started",
    )


# ---------------------------------------------------------------------------
# broadcast_batch_analysis_completed — 15 survivor keys: _1, _2, _5, _6, _7, _8, _13, _15, _23, _24, _25, _26, _34, _35, _36
# ---------------------------------------------------------------------------
_BROADCAST_BATCH_ANALYSIS_COMPLETED_FULL: dict[str, Any] = {
    "type": "batch.analysis_completed",
    "data": {
        "batch_id": "b7",
        "camera_id": "cam-9",
        "event_id": 42,
        "risk_score": 75,
        "risk_level": "high",
        "duration_ms": 2500,
        "completed_at": "2026-01-13T12:01:35.000Z",
    },
}


def _broadcast_batch_analysis_completed_expected(p: dict[str, Any]) -> dict[str, Any]:
    return WebSocketBatchAnalysisCompletedMessage(
        data=WebSocketBatchAnalysisCompletedData.model_validate(p["data"])
    ).model_dump(mode="json")


def test_broadcast_batch_analysis_completed_contract() -> None:
    run_wrapped(
        "broadcast_batch_analysis_completed",
        _BROADCAST_BATCH_ANALYSIS_COMPLETED_FULL,
        _broadcast_batch_analysis_completed_expected,
        "Batch analysis completed broadcast to Redis: batch.analysis_completed (batch_id: b7, event_id: 42, risk_score: 75, subscribers: 3)",
        "event_id",
        "Invalid batch analysis completed message format: ",
        "batch analysis completed",
        "batch.analysis_completed",
    )


# ---------------------------------------------------------------------------
# broadcast_batch_analysis_failed — 15 survivor keys: _1, _2, _5, _6, _7, _8, _13, _15, _23, _24, _25, _26, _34, _35, _36
# ---------------------------------------------------------------------------
_BROADCAST_BATCH_ANALYSIS_FAILED_FULL: dict[str, Any] = {
    "type": "batch.analysis_failed",
    "data": {
        "batch_id": "b7",
        "camera_id": "cam-9",
        "error": "timeout",
        "error_type": "timeout",
        "retryable": True,
        "failed_at": "2026-01-13T12:03:30.000Z",
    },
}


def _broadcast_batch_analysis_failed_expected(p: dict[str, Any]) -> dict[str, Any]:
    return WebSocketBatchAnalysisFailedMessage(
        data=WebSocketBatchAnalysisFailedData.model_validate(p["data"])
    ).model_dump(mode="json")


def test_broadcast_batch_analysis_failed_contract() -> None:
    run_wrapped(
        "broadcast_batch_analysis_failed",
        _BROADCAST_BATCH_ANALYSIS_FAILED_FULL,
        _broadcast_batch_analysis_failed_expected,
        "Batch analysis failed broadcast to Redis: batch.analysis_failed (batch_id: b7, error_type: timeout, subscribers: 3)",
        "error_type",
        "Invalid batch analysis failed message format: ",
        "batch analysis failed",
        "batch.analysis_failed",
    )


# ---------------------------------------------------------------------------
# broadcast_zone_crossing — 12 survivor keys: _10, _11, _12, _18, _19, _20, _21, _22, _23, _24, _25, _26
# ---------------------------------------------------------------------------
_BROADCAST_ZONE_CROSSING_PAYLOAD: dict[str, Any] = {
    "zone_id": "z1",
    "entity_id": "e1",
    "camera_id": "cam-9",
    "timestamp": "2026-02-01T00:00:00Z",
    "direction": "in",
}


def test_broadcast_zone_crossing_contract() -> None:
    run_payload_shape(
        "broadcast_zone_crossing",
        _BROADCAST_ZONE_CROSSING_PAYLOAD,
        "zone.crossing",
        ZoneCrossingPayload,
        "Zone crossing broadcast to Redis: zone_id=z1, entity_id=e1, subscribers=3",
        "zone_id",
        "Invalid zone crossing payload: ",
        "zone crossing",
    )


# ---------------------------------------------------------------------------
# broadcast_zone_dwell_started — 11 survivor keys: _10, _11, _12, _14, _18, _19, _20, _21, _22, _23, _24
# ---------------------------------------------------------------------------
_BROADCAST_ZONE_DWELL_STARTED_PAYLOAD: dict[str, Any] = {
    "zone_id": "z1",
    "entity_id": "e1",
    "camera_id": "cam-9",
    "timestamp": "2026-02-01T00:00:00Z",
}


def test_broadcast_zone_dwell_started_contract() -> None:
    run_payload_shape(
        "broadcast_zone_dwell_started",
        _BROADCAST_ZONE_DWELL_STARTED_PAYLOAD,
        "zone.dwell_started",
        ZoneDwellStartedPayload,
        "Zone dwell started broadcast to Redis: zone_id=z1, entity_id=e1, subscribers=3",
        "entity_id",
        "Invalid zone dwell started payload: ",
        "zone dwell started",
    )


# ---------------------------------------------------------------------------
# broadcast_zone_dwell_alert — 11 survivor keys: _10, _11, _12, _14, _18, _19, _20, _21, _22, _23, _24
# ---------------------------------------------------------------------------
_BROADCAST_ZONE_DWELL_ALERT_PAYLOAD: dict[str, Any] = {
    "zone_id": "z1",
    "entity_id": "e1",
    "camera_id": "cam-9",
    "timestamp": "2026-02-01T00:00:00Z",
    "dwell_duration_seconds": 90,
    "threshold_seconds": 60,
}


def test_broadcast_zone_dwell_alert_contract() -> None:
    run_payload_shape(
        "broadcast_zone_dwell_alert",
        _BROADCAST_ZONE_DWELL_ALERT_PAYLOAD,
        "zone.dwell_alert",
        ZoneDwellAlertPayload,
        "Zone dwell alert broadcast to Redis: zone_id=z1, dwell=90s, subscribers=3",
        "threshold_seconds",
        "Invalid zone dwell alert payload: ",
        "zone dwell alert",
    )


# ---------------------------------------------------------------------------
# broadcast_zone_approach — 11 survivor keys: _10, _11, _12, _14, _18, _19, _20, _21, _22, _23, _24
# ---------------------------------------------------------------------------
_BROADCAST_ZONE_APPROACH_PAYLOAD: dict[str, Any] = {
    "zone_id": "z1",
    "entity_id": "e1",
    "camera_id": "cam-9",
    "timestamp": "2026-02-01T00:00:00Z",
    "direction": "in",
    "speed": 2.5,
    "eta_seconds": 12,
}


def test_broadcast_zone_approach_contract() -> None:
    run_payload_shape(
        "broadcast_zone_approach",
        _BROADCAST_ZONE_APPROACH_PAYLOAD,
        "zone.approach",
        ZoneApproachPayload,
        "Zone approach broadcast to Redis: zone_id=z1, eta=12s, subscribers=3",
        "eta_seconds",
        "Invalid zone approach payload: ",
        "zone approach",
    )


# ---------------------------------------------------------------------------
# broadcast_entity_matched — 16 survivor keys: _10, _11, _12, _14, _18, _19, _20, _21, _22, _23, _24, _25, _26, _27, _28, _29
# ---------------------------------------------------------------------------
_BROADCAST_ENTITY_MATCHED_PAYLOAD: dict[str, Any] = {
    "entity_id": "e1",
    "matched_entity_id": "m2",
    "similarity_score": 0.91,
    "camera_id": "cam-9",
    "timestamp": "2026-02-01T00:00:00Z",
}


def test_broadcast_entity_matched_contract() -> None:
    run_payload_shape(
        "broadcast_entity_matched",
        _BROADCAST_ENTITY_MATCHED_PAYLOAD,
        "entity.matched",
        EntityMatchedPayload,
        "Entity matched broadcast to Redis: entity_id=e1, matched=m2, score=0.91, subscribers=3",
        "matched_entity_id",
        "Invalid entity matched payload: ",
        "entity matched",
    )


# ---------------------------------------------------------------------------
# broadcast_entity_track_updated — 11 survivor keys: _10, _11, _12, _14, _18, _19, _20, _21, _22, _23, _24
# ---------------------------------------------------------------------------
_BROADCAST_ENTITY_TRACK_UPDATED_PAYLOAD: dict[str, Any] = {
    "entity_id": "e1",
    "camera_id": "cam-9",
    "timestamp": "2026-02-01T00:00:00Z",
    "position": {"x": 0.5, "y": 0.5},
    "bbox": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2},
}


def test_broadcast_entity_track_updated_contract() -> None:
    run_payload_shape(
        "broadcast_entity_track_updated",
        _BROADCAST_ENTITY_TRACK_UPDATED_PAYLOAD,
        "entity.track_updated",
        EntityTrackUpdatedPayload,
        "Entity track updated broadcast to Redis: entity_id=e1, camera=cam-9, subscribers=3",
        "position",
        "Invalid entity track updated payload: ",
        "entity track updated",
    )


# ---------------------------------------------------------------------------
# broadcast_ai_threat_detected — 16 survivor keys: _10, _11, _12, _14, _18, _19, _20, _21, _22, _23, _24, _25, _26, _27, _28, _29
# ---------------------------------------------------------------------------
_BROADCAST_AI_THREAT_DETECTED_PAYLOAD: dict[str, Any] = {
    "detection_id": "d9",
    "camera_id": "cam-9",
    "timestamp": "2026-02-01T00:00:00Z",
    "threat_type": "weapon",
    "severity": "high",
    "confidence": 0.88,
}


def test_broadcast_ai_threat_detected_contract() -> None:
    run_payload_shape(
        "broadcast_ai_threat_detected",
        _BROADCAST_AI_THREAT_DETECTED_PAYLOAD,
        "ai.threat_detected",
        AIThreatDetectedPayload,
        "AI threat detected broadcast to Redis: threat_type=weapon, severity=high, confidence=0.88, subscribers=3",
        "threat_type",
        "Invalid AI threat detected payload: ",
        "AI threat detected",
    )


# ---------------------------------------------------------------------------
# broadcast_ai_action_recognized — 11 survivor keys: _10, _11, _12, _14, _18, _19, _20, _21, _22, _23, _24
# ---------------------------------------------------------------------------
_BROADCAST_AI_ACTION_RECOGNIZED_PAYLOAD: dict[str, Any] = {
    "detection_id": "d9",
    "camera_id": "cam-9",
    "timestamp": "2026-02-01T00:00:00Z",
    "action_type": "loitering",
    "confidence": 0.77,
}


def test_broadcast_ai_action_recognized_contract() -> None:
    run_payload_shape(
        "broadcast_ai_action_recognized",
        _BROADCAST_AI_ACTION_RECOGNIZED_PAYLOAD,
        "ai.action_recognized",
        AIActionRecognizedPayload,
        "AI action recognized broadcast to Redis: action_type=loitering, confidence=0.77, subscribers=3",
        "action_type",
        "Invalid AI action recognized payload: ",
        "AI action recognized",
    )


# ---------------------------------------------------------------------------
# broadcast_alert — 9 survivor keys: _17, _18, _19, _25, _26, _27, _28, _29, _31
# ---------------------------------------------------------------------------
_ALERT_FULL: dict[str, Any] = {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "event_id": 123,
    "rule_id": "550e8400-e29b-41d4-a716-446655440001",
    "severity": "high",
    "status": "pending",
    "dedup_key": "front_door:person:rule1",
    "created_at": "2026-01-09T12:00:00Z",
    "updated_at": "2026-01-09T12:00:00Z",
}


def test_broadcast_alert_dispatches_alert_created() -> None:
    # kills the elif-chain mutants that swap this arm's message class (the
    # published `type` is the pinned Literal): type == "alert_created".
    r = FakeRedis()
    b = _broadcaster(r)
    expected = WebSocketAlertCreatedMessage(
        data=WebSocketAlertData.model_validate(_ALERT_FULL)
    ).model_dump(mode="json")
    with LogCapture() as cap:
        n = _run(b.broadcast_alert(dict(_ALERT_FULL), WebSocketAlertEventType.ALERT_CREATED))
    assert n == 3
    _pub(r, [(CHANNEL, expected)])
    assert cap.texts() == ["Alert broadcast to Redis: alert_created (subscribers: 3)"]


def test_broadcast_alert_dispatches_alert_updated() -> None:
    # kills the elif-chain mutants that swap this arm's message class (the
    # published `type` is the pinned Literal): type == "alert_updated".
    r = FakeRedis()
    b = _broadcaster(r)
    expected = WebSocketAlertUpdatedMessage(
        data=WebSocketAlertData.model_validate(_ALERT_FULL)
    ).model_dump(mode="json")
    with LogCapture() as cap:
        n = _run(b.broadcast_alert(dict(_ALERT_FULL), WebSocketAlertEventType.ALERT_UPDATED))
    assert n == 3
    _pub(r, [(CHANNEL, expected)])
    assert cap.texts() == ["Alert broadcast to Redis: alert_updated (subscribers: 3)"]


def test_broadcast_alert_dispatches_alert_acknowledged() -> None:
    # kills the elif-chain mutants that swap this arm's message class (the
    # published `type` is the pinned Literal): type == "alert_acknowledged".
    r = FakeRedis()
    b = _broadcaster(r)
    expected = WebSocketAlertAcknowledgedMessage(
        data=WebSocketAlertData.model_validate(_ALERT_FULL)
    ).model_dump(mode="json")
    with LogCapture() as cap:
        n = _run(b.broadcast_alert(dict(_ALERT_FULL), WebSocketAlertEventType.ALERT_ACKNOWLEDGED))
    assert n == 3
    _pub(r, [(CHANNEL, expected)])
    assert cap.texts() == ["Alert broadcast to Redis: alert_acknowledged (subscribers: 3)"]


def test_broadcast_alert_dispatches_alert_resolved() -> None:
    # kills the elif-chain mutants that swap this arm's message class (the
    # published `type` is the pinned Literal): type == "alert_resolved".
    r = FakeRedis()
    b = _broadcaster(r)
    expected = WebSocketAlertResolvedMessage(
        data=WebSocketAlertData.model_validate(_ALERT_FULL)
    ).model_dump(mode="json")
    with LogCapture() as cap:
        n = _run(b.broadcast_alert(dict(_ALERT_FULL), WebSocketAlertEventType.ALERT_RESOLVED))
    assert n == 3
    _pub(r, [(CHANNEL, expected)])
    assert cap.texts() == ["Alert broadcast to Redis: alert_resolved (subscribers: 3)"]


def test_broadcast_alert_dispatches_alert_dismissed() -> None:
    # kills the elif-chain mutants that swap this arm's message class (the
    # published `type` is the pinned Literal): type == "alert_dismissed".
    r = FakeRedis()
    b = _broadcaster(r)
    expected = WebSocketAlertDismissedMessage(
        data=WebSocketAlertData.model_validate(_ALERT_FULL)
    ).model_dump(mode="json")
    with LogCapture() as cap:
        n = _run(b.broadcast_alert(dict(_ALERT_FULL), WebSocketAlertEventType.ALERT_DISMISSED))
    assert n == 3
    _pub(r, [(CHANNEL, expected)])
    assert cap.texts() == ["Alert broadcast to Redis: alert_dismissed (subscribers: 3)"]


def test_broadcast_alert_deleted_arm() -> None:
    # The ALERT_DELETED branch uses the DELETED data schema (id + reason):
    # pins the branch's message class (type "alert_deleted"), the narrow
    # payload shape (event_id etc. must NOT be required here) and its debug.
    deleted = {"id": "550e8400-e29b-41d4-a716-446655440000", "reason": "Duplicate alert"}
    r = FakeRedis()
    b = _broadcaster(r)
    expected = WebSocketAlertDeletedMessage(
        data=WebSocketAlertDeletedData.model_validate(deleted)
    ).model_dump(mode="json")
    with LogCapture() as cap:
        n = _run(b.broadcast_alert(dict(deleted), WebSocketAlertEventType.ALERT_DELETED))
    assert n == 3
    _pub(r, [(CHANNEL, expected)])
    assert cap.texts() == ["Alert broadcast to Redis: alert_deleted (subscribers: 3)"]


def test_broadcast_alert_unknown_type_raises_and_invalid_raises() -> None:
    # Unknown enum string hits the else-raise; invalid full data yields the
    # shipped ValueError prefix with exactly one Field-required; nothing
    # published in either case.
    r = FakeRedis()
    b = _broadcaster(r)
    try:
        _run(b.broadcast_alert(dict(_ALERT_FULL), "not-a-type"))
        raise AssertionError("expected ValueError")
    except ValueError as ve:
        assert str(ve) == "Unknown alert event type: not-a-type", str(ve)
    assert r.published == []
    bad = dict(_ALERT_FULL)
    del bad["dedup_key"]
    with LogCapture() as cap_inv:
        try:
            _run(b.broadcast_alert(bad, WebSocketAlertEventType.ALERT_CREATED))
            raise AssertionError("expected ValueError")
        except ValueError as ve:
            text = str(ve)
            assert text.startswith("Invalid alert message format: ")
            assert text.count("Field required") == 1
    assert len([t for t in cap_inv.texts() if "validation failed" in t]) == 1, cap_inv.texts()
    assert r.published == []


def test_broadcast_alert_publish_failure_wraps() -> None:
    b = _broadcaster(RaisingRedis())
    with LogCapture() as cap:
        try:
            _run(b.broadcast_alert(dict(_ALERT_FULL), WebSocketAlertEventType.ALERT_CREATED))
            raise AssertionError("expected RuntimeError")
        except RuntimeError as re_exc:
            assert str(re_exc) == "boom"
    assert "Failed to broadcast alert: boom" in cap.texts(), cap.texts()


# ---------------------------------------------------------------------------
# broadcast_summary_update — 32 survivor keys: _2, _3, _4, _5, _12, _13, _14, _15, _23, _24, _25, _26, _33, _34, _35, _41, _42, _43, _44, _45, _46, _47, _48, _49, _50, _51, _52, _53, _54, _55, _56, _57
# ---------------------------------------------------------------------------
_SUMMARY_HOURLY: dict[str, Any] = {
    "id": 1,
    "content": "hour text",
    "event_count": 2,
    "window_start": "2026-01-18T14:00:00Z",
    "window_end": "2026-01-18T15:00:00Z",
    "generated_at": "2026-01-18T14:55:00Z",
}
_SUMMARY_DAILY: dict[str, Any] = {
    "id": 2,
    "content": "day text",
    "event_count": 9,
    "window_start": "2026-01-18T00:00:00Z",
    "window_end": "2026-01-19T00:00:00Z",
    "generated_at": "2026-01-19T00:05:00Z",
}


def _summary_expected(
    hourly: dict[str, Any] | None, daily: dict[str, Any] | None
) -> dict[str, Any]:
    data = {
        "hourly": (
            WebSocketSummaryData.model_validate(hourly).model_dump(mode="json")
            if hourly is not None
            else None
        ),
        "daily": (
            WebSocketSummaryData.model_validate(daily).model_dump(mode="json")
            if daily is not None
            else None
        ),
    }
    return WebSocketSummaryUpdateMessage(
        data=WebSocketSummaryUpdateData.model_validate(data)
    ).model_dump(mode="json")


def _summary_contract(
    hourly: dict[str, Any] | None, daily: dict[str, Any] | None, h_yes: str, d_yes: str
) -> None:
    r = FakeRedis()
    b = _broadcaster(r)
    with LogCapture() as cap:
        n = _run(b.broadcast_summary_update(hourly, daily))
    assert n == 3
    _pub(r, [(CHANNEL, _summary_expected(hourly, daily))])
    assert cap.texts() == [
        f"Summary update broadcast to Redis: summary_update "
        f"(hourly: {h_yes}, daily: {d_yes}, subscribers: 3)"
    ]


def test_summary_update_both() -> None:
    _summary_contract(_SUMMARY_HOURLY, _SUMMARY_DAILY, "yes", "yes")


def test_summary_update_hourly_only() -> None:
    _summary_contract(_SUMMARY_HOURLY, None, "yes", "no")


def test_summary_update_daily_only() -> None:
    _summary_contract(None, _SUMMARY_DAILY, "no", "yes")


def test_summary_update_neither() -> None:
    # both None: data payload is exactly {"hourly": None, "daily": None} —
    # kills the dict-literal key renames and the None-default swaps.
    _summary_contract(None, None, "no", "no")
    r = FakeRedis()
    b = _broadcaster(r)
    _run(b.broadcast_summary_update(None, None))
    assert r.published[0][1]["data"] == {"hourly": None, "daily": None}


def test_summary_update_invalid_hourly_and_daily() -> None:
    r = FakeRedis()
    b = _broadcaster(r)
    bad = dict(_SUMMARY_HOURLY)
    del bad["content"]
    with LogCapture() as cap_h:
        try:
            _run(b.broadcast_summary_update(bad, None))
            raise AssertionError("expected ValueError")
        except ValueError as ve:
            text = str(ve)
            assert text.startswith("Invalid hourly summary format: "), text[:80]
            assert text.count("Field required") == 1
    hourly_errs = [t for t in cap_h.texts() if t.startswith("Hourly summary validation failed")]
    assert len(hourly_errs) == 1, cap_h.texts()
    bad2 = dict(_SUMMARY_DAILY)
    del bad2["generated_at"]
    with LogCapture() as cap_d:
        try:
            _run(b.broadcast_summary_update(None, bad2))
            raise AssertionError("expected ValueError")
        except ValueError as ve:
            text = str(ve)
            assert text.startswith("Invalid daily summary format: "), text[:80]
            assert text.count("Field required") == 1
    daily_errs = [t for t in cap_d.texts() if t.startswith("Daily summary validation failed")]
    assert len(daily_errs) == 1, cap_d.texts()
    assert r.published == []


def test_summary_update_publish_failure_wraps() -> None:
    b = _broadcaster(RaisingRedis())
    with LogCapture() as cap:
        try:
            _run(b.broadcast_summary_update(_SUMMARY_HOURLY, None))
            raise AssertionError("expected RuntimeError")
        except RuntimeError as re_exc:
            assert str(re_exc) == "boom"
    assert "Failed to broadcast summary update: boom" in cap.texts(), cap.texts()


def test_service_status_bare_timestamp_defaults_empty() -> None:
    # The service wrapper passes timestamp=status_data.get("timestamp", ""):
    # a payload WITHOUT a top-level timestamp must publish timestamp ""
    # (kills the None/"XXXX"/dropped-default family on that get).
    full = dict(_BROADCAST_SERVICE_STATUS_FULL)
    full.pop("timestamp", None)
    r = FakeRedis()
    b = _broadcaster(r)
    with LogCapture() as cap:
        n = _run(b.broadcast_service_status(full))
    assert n == 3
    payload = r.published[0][1]
    assert payload["timestamp"] == "", payload
    assert cap.texts() == ["Service status broadcast to Redis: service_status (subscribers: 3)"]
