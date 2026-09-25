"""Batch-25 chunk-09 kill battery: NemotronAnalyzer.analyze_detection_fast_path.

Chunk: /tmp/wp-batch25/chunks/chunk-09.json (130 keys, fn
xǁNemotronAnalyzerǁanalyze_detection_fast_path).

Every assertion pins SHIPPED behavior of
backend/services/nemotron_analyzer.py:3143-3613 (probed, not assumed):
  * session 1 issues exactly two queries, in order:
      select(Camera).where(Camera.id == camera_id)               # 3210
      select(Detection).where(Detection.id == detection_id_int)  # 3222-3224
    asserted as EXACT SQL strings against a fake session that dispatches on
    exact SQL text (a substring dispatcher would let select(None) mutants
    through, since "SELECT NULL ... FROM cameras" still mentions cameras).
  * _call_llm is called with camera_name=<camera.name>, start/end =
    detection_time.isoformat(), detections_list=_format_detections([det]),
    enriched_context / enrichment_result / camera_health_context /
    detection_dicts exactly as built.
  * log_context(batch_id=..., camera_id=..., detection_id=...) then
    logger.info("Batch analysis started"); the idempotency-hit branch logs
    info("Idempotency hit: fast path already processed as event",
    extra={"batch_id": ..., "event_id": ...}).
  * success: observe_ai_request_duration("nemotron", 2.0) and
    logger.debug("Fast path LLM analysis completed for detection 42",
    extra={"camera_id":..., "detection_id":..., "duration_ms": 1000});
    LLM failure: same metric plus logger.error with duration_ms (and the
    sanitized error text).

time is patched INSIDE the module (patch.object(MOD, "time", autospec=True))
with a +1.0-per-call counter, so every duration is bit-exact: llm_start is
read at 1001.0 and the two duration reads land on 1002.0 / 1003.0 ->
duration_ms 1000, seconds 2.0.

RED-CHECK: each docstring's kill list is the VERIFIED first-killing
attribution from applying the exact mutant (line-level, from the
instrumented copy) — 129/130 keys die on this file; key 103 is the only
survivor and is ruled equivalent (proof in verdicts_09.json).

OCCURRENCE-TWIN note: mutant identity is occurrence order among identical
minus/plus shapes, so several shape groups carry keys at DIFFERENT source
sites (e.g. the enriched_context=None group covers _call_llm:3314,
create_partial_audit:3449, _build_enrichment_snapshot:3481 and
_build_context_sources:3487). One shape group -> one verdict with all keys
carried; each distinct occurrence gets its own test below.
"""

from __future__ import annotations

import itertools
import os
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.unit

# Mirror the minimum env the repo unit conftest sets (this file lives outside
# backend/tests/unit, so that conftest does not apply). Values copied from
# backend/tests/unit/conftest.py + backend/tests/conftest.py, not invented.
os.environ.setdefault("API_KEY_ENABLED", "true")  # pragma: allowlist secret
os.environ.setdefault("API_KEYS", '["test-unit-api-key-12345"]')  # pragma: allowlist secret
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:***@localhost:5432/test_db",  # pragma: allowlist secret
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")  # pragma: allowlist secret

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services import nemotron_analyzer as MOD
from backend.services.nemotron_analyzer import NemotronAnalyzer

CAMERA_ID = "front_door"
DETECTION_ID = 42
DETECTION_TIME = datetime(2026, 5, 1, 10, 30, 0, tzinfo=UTC)
ISO = DETECTION_TIME.isoformat()

GOLD_CAMERA_SQL = str(select(Camera).where(Camera.id == CAMERA_ID))
GOLD_DETECTION_SQL = str(select(Detection).where(Detection.id == DETECTION_ID))


def _detection(**over: Any) -> Any:
    """Plain attribute bag standing in for the Detection ORM row."""

    class _Det:
        pass

    d = _Det()
    d.id = DETECTION_ID
    d.camera_id = CAMERA_ID
    d.object_type = over.get("object_type", "person")
    d.confidence = over.get("confidence", 0.9)
    d.file_path = over.get("file_path", "/export/foscam/front_door/alert_img.jpg")
    d.detected_at = over.get("detected_at", DETECTION_TIME)
    d.bbox_x = over.get("bbox_x", 10)
    d.bbox_y = over.get("bbox_y", 20)
    d.bbox_width = over.get("bbox_width", 30)
    d.bbox_height = over.get("bbox_height", 40)
    d.video_width = over.get("video_width", 1920)
    d.video_height = over.get("video_height", 1080)
    return d


def _camera() -> Any:
    class _Cam:
        pass

    c = _Cam()
    c.id = CAMERA_ID
    c.name = "Front Door Camera"
    return c


def _enrichment_result() -> Any:
    er = MagicMock(name="EnrichmentResult")
    er.to_storage_dict.return_value = {}
    er.smoke_fire_detection = None
    er.person_household_matches = []
    er.vehicle_household_matches = []
    return er


def _tracking(er: Any) -> Any:
    t = MagicMock(name="EnrichmentTrackingResult")
    t.has_data = True
    t.data = er
    return t


class _Result:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _Session:
    """Fake AsyncSession recording executed SQL; dispatches on EXACT SQL."""

    def __init__(self, camera: Any, detection: Any) -> None:
        self.camera = camera
        self.detection = detection
        self.sql: list[str] = []
        self.added: list[Any] = []
        self.flush = AsyncMock()
        self.add = MagicMock(side_effect=self._add)

    def _add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, query: Any) -> Any:
        text = str(query)
        self.sql.append(text)
        if text == GOLD_CAMERA_SQL:
            return _Result(self.camera)
        if text == GOLD_DETECTION_SQL:
            return _Result(self.detection)
        return _Result(None)


class _Ctx:
    """Re-entrant async context manager returning a fixed value."""

    def __init__(self, value: Any) -> None:
        self.value = value

    async def __aenter__(self) -> Any:
        return self.value

    async def __aexit__(self, *exc: Any) -> bool:
        return False


def _llm_ok() -> dict[str, Any]:
    return {
        "risk_score": 75,
        "risk_level": "high",
        "summary": "someone at the door",
        "reasoning": "person at door after hours",
        "raw_response": "raw",
        "llm_prompt": "PROMPT",
        "entities": None,
        "flags": None,
        "confidence_factors": None,
        "recommended_action": None,
    }


class _Harness:
    """Fully-mocked fast path; each run() executes one analyze_detection_fast_path."""

    def __init__(self, detection: Any = None, camera: Any = "default") -> None:
        self.detection = detection if detection is not None else _detection()
        self.camera = _camera() if camera == "default" else camera
        self.analyzer = NemotronAnalyzer.__new__(NemotronAnalyzer)
        self.analyzer._redis = MagicMock(name="redis")
        self.analyzer._use_enriched_context = True
        self.analyzer._use_enrichment_pipeline = True
        self.session1 = _Session(self.camera, self.detection)
        self.session2 = _Session(self.camera, self.detection)

    async def run(
        self,
        *,
        detection_id: Any = DETECTION_ID,
        existing_event_id: int | None = None,
        existing_event: Any = None,
        tracking: Any = None,
        enriched_context: Any = None,
        scene_changes: Any = (),
        health_context: str = "HEALTH-CONTEXT",
        llm_error: Exception | None = None,
        llm_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        a = self.analyzer
        sessions = [_Ctx(self.session1), _Ctx(self.session2), _Ctx(self.session2)]
        counter = itertools.count(1000.0, 1.0)
        audit_service = MagicMock(name="audit_service")
        audit_service.create_partial_audit.return_value = MagicMock(id=99)

        def P(obj: Any, attr: str, **kw: Any) -> Any:
            return patch.object(obj, attr, autospec=True, **kw).start()

        check = P(a, "_check_idempotency")
        check.return_value = existing_event_id
        get_existing = P(a, "_get_existing_event")
        get_existing.return_value = existing_event
        set_idem = P(a, "_set_idempotency")
        enriched = P(a, "_get_enriched_context")
        enriched.return_value = enriched_context
        scene = P(a, "_get_recent_scene_changes")
        scene.return_value = list(scene_changes)
        enrich_track = P(a, "_get_enrichment_result_from_data")
        enrich_track.return_value = tracking
        call_llm = P(a, "_call_llm")
        if llm_error is not None:
            call_llm.side_effect = llm_error
        else:
            call_llm.side_effect = lambda *_a, **_kw: llm_result or _llm_ok()
        broadcast = P(a, "_broadcast_event")
        webhook = P(a, "_trigger_event_created_webhook")
        enqueue = P(a, "_enqueue_for_evaluation")
        snapshot = P(a, "_build_enrichment_snapshot")
        snapshot.return_value = {"snapshot": True}
        sources = P(a, "_build_context_sources")
        sources.return_value = {"sources": True}
        observe = P(MOD, "observe_ai_request_duration")
        stage = P(MOD, "observe_stage_duration")
        created = P(MOD, "record_event_created")
        by_camera = P(MOD, "record_event_by_camera")
        pipeline_error = P(MOD, "record_pipeline_error")
        log_ctx = P(MOD, "log_context")
        health = P(MOD, "format_camera_health_context")
        health.return_value = health_context
        logger = P(MOD, "logger")
        get_session = patch.object(
            MOD, "get_session", autospec=True, side_effect=lambda: sessions.pop(0)
        ).start()
        module_time = patch.object(MOD, "time", autospec=True).start()
        module_time.time.side_effect = lambda: next(counter)
        get_audit = patch(
            "backend.services.pipeline_quality_audit_service.get_audit_service",
            autospec=True,
        ).start()
        get_audit.return_value = audit_service

        try:
            result = await a.analyze_detection_fast_path(CAMERA_ID, detection_id)
        finally:
            patch.stopall()

        llm_kwargs = call_llm.call_args.kwargs if call_llm.call_args is not None else {}
        return {
            "result": result,
            "analyzer": a,
            "session1": self.session1,
            "session2": self.session2,
            "events": [o for o in self.session2.added if isinstance(o, Event)],
            "check": check,
            "get_existing": get_existing,
            "set_idem": set_idem,
            "enriched": enriched,
            "scene": scene,
            "enrich_track": enrich_track,
            "call_llm": call_llm,
            "llm_kwargs": llm_kwargs,
            "snapshot": snapshot,
            "sources": sources,
            "audit": audit_service.create_partial_audit,
            "observe": observe,
            "stage": stage,
            "created": created,
            "by_camera": by_camera,
            "pipeline_error": pipeline_error,
            "logger": logger,
            "log_ctx": log_ctx,
            "health": health,
            "broadcast": broadcast,
            "webhook": webhook,
            "enqueue": enqueue,
            "get_session": get_session,
        }


# =============================================================================
# Guard clause (shipped 3170-3171)
# =============================================================================


@pytest.mark.asyncio
async def test_missing_redis_raises_exact_runtime_error_message():
    """Kills mutmut_3.

    Shipped raises RuntimeError("Redis client not initialized"); the mutant
    raises "XXRedis client not initializedXX". Pinned with an EQUALITY assert
    on str(exc) — a re.search match= would let the XX-wrapped text pass.
    """
    h = _Harness()
    h.analyzer._redis = None
    with pytest.raises(RuntimeError) as excinfo:
        await h.run()
    assert str(excinfo.value) == "Redis client not initialized"


# =============================================================================
# Idempotency-hit branch (shipped 3185-3188)
# =============================================================================


@pytest.mark.asyncio
async def test_idempotency_hit_logs_message_and_extra_fields():
    """Kills mutmut_13, _14, _16, _17, _18, _19, _20, _21, _22, _23.

    Shipped logs logger.info("Idempotency hit: fast path already processed as
    event", extra={"batch_id": batch_id, "event_id": existing_event_id}) and
    returns the existing Event. Kills msg->None, the three msg case/XX
    variants, extra=None, the deleted-extra mutant and the four extra-key
    renames.
    """
    ev = Event(batch_id="fast_path_42", camera_id=CAMERA_ID, risk_score=10, risk_level="low")
    h = _Harness()
    out = await h.run(existing_event_id=555, existing_event=ev)

    assert out["result"] is ev
    hits = [
        c
        for c in out["logger"].info.call_args_list
        if "already processed" in str(c.args[0]).lower()
    ]
    assert len(hits) == 1, out["logger"].info.call_args_list
    assert hits[0].args[0] == "Idempotency hit: fast path already processed as event"
    assert hits[0].kwargs["extra"] == {"batch_id": "fast_path_42", "event_id": 555}


@pytest.mark.asyncio
async def test_idempotency_hit_looks_up_event_by_returned_id():
    """Kills mutmut_25.

    Shipped forwards the id returned by _check_idempotency to
    _get_existing_event; the mutant passes None (bound-method autospec, so
    recorded call args exclude self).
    """
    ev = Event(batch_id="fast_path_42", camera_id=CAMERA_ID, risk_score=10, risk_level="low")
    h = _Harness()
    out = await h.run(existing_event_id=555, existing_event=ev)
    out["get_existing"].assert_called_once_with(555)


# =============================================================================
# Start-of-analysis logging (shipped 3200-3201)
# =============================================================================


@pytest.mark.asyncio
async def test_log_context_carries_batch_camera_detection():
    """Kills mutmut_27, _28, _29, _30, _31, _32.

    Shipped opens log_context(batch_id=batch_id, camera_id=camera_id,
    detection_id=detection_id_int); the six mutants null or drop one kwarg.
    """
    h = _Harness()
    out = await h.run()
    assert out["log_ctx"].call_args_list[0].kwargs == {
        "batch_id": "fast_path_42",
        "camera_id": CAMERA_ID,
        "detection_id": DETECTION_ID,
    }


@pytest.mark.asyncio
async def test_batch_analysis_started_message_is_exact():
    """Kills mutmut_33, _34, _35, _36.

    logger.info("Batch analysis started") with the msg replaced by None,
    "XXBatch analysis startedXX", the lowercase and the uppercase variant all
    miss the exact-match assertion.
    """
    h = _Harness()
    out = await h.run()
    assert any(c.args[0] == "Batch analysis started" for c in out["logger"].info.call_args_list), (
        out["logger"].info.call_args_list
    )


# =============================================================================
# Session 1 queries and camera name (shipped 3210-3223)
# =============================================================================


@pytest.mark.asyncio
async def test_camera_and_detection_queries_are_exact_sql():
    """Kills mutmut_38.

    Shipped session 1 issues select(Camera).where(Camera.id == camera_id)
    then select(Detection).where(Detection.id == detection_id_int) as the
    first two executed statements; this test pins both SQL strings exactly
    (sibling tests are the first killers for the other query mutants because
    those fail earlier with "Detection not found").
    """
    h = _Harness()
    out = await h.run()
    assert out["session1"].sql[:2] == [GOLD_CAMERA_SQL, GOLD_DETECTION_SQL]


@pytest.mark.asyncio
async def test_camera_name_from_row_is_passed_to_llm():
    """Kills mutmut_39, _41, _43.

    With a camera row present shipped uses camera.name; camera_name=None
    (mutmut_44) and the == -> != query flip (mutmut_41, which routes this
    fixture's exact-dispatch session to "no camera" -> name = camera_id) both
    break the equality below.
    """
    h = _Harness()
    out = await h.run()
    assert out["llm_kwargs"]["camera_name"] == "Front Door Camera"


@pytest.mark.asyncio
async def test_missing_camera_falls_back_to_camera_id():
    """Kills mutmut_43, _46, _118.

    With no camera row shipped uses camera_id as the name; `if camera:`
    dereferences None.name, execute(None)/select-missing (mutmut_46 shape at
    the detection query) break the run outright, and camera_name=None at
    _call_llm fails the equality.
    """
    h = _Harness(camera=None)
    out = await h.run()
    assert out["llm_kwargs"]["camera_name"] == CAMERA_ID


# =============================================================================
# Payload handed to the enrichment pipeline (shipped 3232-3249, 3272-3273, 3278-3282)
# =============================================================================


@pytest.mark.asyncio
async def test_format_detections_output_reaches_llm():
    """Kills mutmut_54, _121.

    Shipped computes detections_list = self._format_detections([detection])
    and forwards it unchanged as detections_list=; the mutants replace the
    assignment and the kwarg value with None respectively.
    """
    h = _Harness()
    out = await h.run()
    expected = out["analyzer"]._format_detections([h.detection])
    assert expected
    assert out["llm_kwargs"]["detections_list"] == expected


def _expected_enrichment_dict(det: Any) -> dict[str, Any]:
    return {
        "id": det.id,
        "object_type": det.object_type,
        "confidence": det.confidence,
        "file_path": det.file_path,
        "bounding_box": {
            "bbox_x": det.bbox_x,
            "bbox_y": det.bbox_y,
            "bbox_width": det.bbox_width,
            "bbox_height": det.bbox_height,
        }
        if det.bbox_x is not None
        else None,
        "video_width": det.video_width,
        "video_height": det.video_height,
    }


@pytest.mark.asyncio
async def test_enrichment_payload_carries_exact_keys_with_bounding_box():
    """Kills mutmut_57, _58, _59, _60, _61, _62, _63, _64, _66, _67, _70, _71, _72, _73, _96
        _99.
    _71, _72, _73, _94, _95.

    Shipped hands _get_enrichment_result_from_data exactly one data dict with
    those key names/values (bbox present) plus batch_id and
    camera_id=camera_id; every XX../UPPER key rename, the
    `is not None` -> `and False` flip (mutmut_67 group second direction), and
    the batch_id / detections-list nulling at the call break the equality.
    """
    h = _Harness()
    out = await h.run()
    args = out["enrich_track"].call_args
    assert args.args[0] == "fast_path_42"
    assert args.args[1] == [_expected_enrichment_dict(h.detection)]
    assert args.kwargs == {"camera_id": CAMERA_ID}


@pytest.mark.asyncio
async def test_enrichment_payload_without_bounding_box():
    """Kills mutmut_56, _65, _68, _69, _95.

    With bbox_x None shipped emits bounding_box None; `(is not None) or True`
    and `is None` emit the coordinate dict instead, the whole-dict -> None
    mutant and the select(None) query shape break the run before this point.
    """
    h = _Harness(detection=_detection(bbox_x=None))
    out = await h.run()
    assert out["enrich_track"].call_args.args[1][0]["bounding_box"] is None


@pytest.mark.asyncio
async def test_enrichment_call_arguments_and_unwrap():
    """Kills mutmut_93, _94, _123.

    Shipped calls _get_enrichment_result_from_data(batch_id, [data],
    camera_id=camera_id) — dropping the camera_id kwarg, nulling it, or
    replacing the whole call with None changes the recorded call or unwraps
    to no enrichment result.
    """
    er = _enrichment_result()
    h = _Harness()
    out = await h.run(tracking=_tracking(er))
    args = out["enrich_track"].call_args
    assert args.args[0] == "fast_path_42"
    assert isinstance(args.args[1], list) and len(args.args[1]) == 1
    assert args.kwargs == {"camera_id": CAMERA_ID}
    assert out["llm_kwargs"]["enrichment_result"] is er


@pytest.mark.asyncio
async def test_enrichment_tracking_none_never_dereferences_has_data():
    """Kills mutmut_102.

    Shipped short-circuits `enrichment_tracking is not None and
    enrichment_tracking.has_data`; with tracking None the or-mutant
    dereferences None (AttributeError — nothing around this line catches it)
    and the enrichment_result kwarg deletion at _call_llm breaks the
    assertion.
    """
    h = _Harness()
    out = await h.run(tracking=None)
    assert out["llm_kwargs"]["enrichment_result"] is None


@pytest.mark.asyncio
async def test_tracking_without_data_yields_no_enrichment_result():
    """Guard for the has_data gate (no first-kill attribution; keeps
    mutmut_102 pinned from regressing alongside mutmut_101).

    A tracking result with has_data False must NOT unwrap .data.
    """
    er = _enrichment_result()
    tracking = MagicMock(name="tracking")
    tracking.has_data = False
    tracking.data = er
    h = _Harness()
    out = await h.run(tracking=tracking)
    assert out["llm_kwargs"]["enrichment_result"] is None


# =============================================================================
# Context enrichment + camera health (shipped 3254-3260)
# =============================================================================


@pytest.mark.asyncio
async def test_enriched_context_call_arguments_and_forwarding():
    """Kills mutmut_49, _75, _76, _77, _78, _122, _130.

    Shipped: enriched_context = await self._get_enriched_context(batch_id,
    camera_id, [detection_id_int], session); nulling any of the four
    arguments (including passing None instead of the session object) breaks
    the recorded call.
    """
    ctx = MagicMock(name="EnrichedContext")
    h = _Harness()
    out = await h.run(enriched_context=ctx)
    args = out["enriched"].call_args
    assert args.args[:3] == ("fast_path_42", CAMERA_ID, [DETECTION_ID])
    assert args.args[3] is out["session1"]
    assert "enriched_context" in out["llm_kwargs"]
    assert out["llm_kwargs"]["enriched_context"] is ctx


@pytest.mark.asyncio
async def test_recent_scene_changes_arguments():
    """Kills mutmut_83, _84, _85.

    Shipped: recent_scene_changes = await
    self._get_recent_scene_changes(camera_id, session); the mutants null one
    of the two arguments.
    """
    h = _Harness()
    out = await h.run(scene_changes=("sc1",))
    assert out["scene"].call_args.args == (CAMERA_ID, out["session1"])


@pytest.mark.asyncio
async def test_camera_health_context_arguments_and_forwarding():
    """Kills mutmut_88, _89, _90, _124, _132.

    Shipped: camera_health_context = format_camera_health_context(camera_id,
    recent_scene_changes), forwarded verbatim to _call_llm; the mutants null
    the scene-changes call or either formatter argument, null the kwarg
    value, or delete the camera_health_context kwarg.
    """
    h = _Harness()
    out = await h.run(scene_changes=("sc1", "sc2"))
    assert out["health"].call_args.args == (CAMERA_ID, ["sc1", "sc2"])
    assert "camera_health_context" in out["llm_kwargs"]
    assert out["llm_kwargs"]["camera_health_context"] == "HEALTH-CONTEXT"


# =============================================================================
# _call_llm call shape (shipped 3299-3318)
# =============================================================================


@pytest.mark.asyncio
async def test_call_llm_time_bounds_and_confidence_dicts():
    """Kills mutmut_48, _107, _110, _112, _113, _116, _119, _120.

    Shipped passes start_time = end_time = detection_time.isoformat() and
    detection_dicts = [{"confidence": det.confidence, "class_name":
    det.object_type or "unknown"}]; mutants null either time bound, replace
    the whole conditional expression with None, rename the confidence /
    class_name keys, or delete the detection_dicts kwarg.
    """
    h = _Harness()
    out = await h.run()
    kw = out["llm_kwargs"]
    assert kw["start_time"] == ISO
    assert kw["end_time"] == ISO
    assert kw["detection_dicts"] == [{"confidence": 0.9, "class_name": "person"}]


@pytest.mark.asyncio
async def test_detection_dicts_empty_when_confidence_is_none():
    """Kills mutmut_108, _125.

    With confidence None shipped emits detection_dicts=[]; the `or True` and
    `is None` flips emit a one-element list, the whole-expression -> None
    mutant and the detection_dicts=None kwarg emit None, and the != detection
    query shape (mutmut_49) aborts the run with "Detection not found".
    """
    h = _Harness(detection=_detection(confidence=None))
    out = await h.run()
    assert out["llm_kwargs"]["detection_dicts"] == []


@pytest.mark.asyncio
async def test_detection_dicts_class_name_fallback_is_unknown():
    """Kills mutmut_106, _109, _111, _114, _115, _133.

    With object_type None shipped emits class_name exactly "unknown"; the
    `and False` confidence flip emits a row with confidence None, the
    or -> and flip emits None, and the XXunknown/UNKNOWN mutants change the
    literal.
    """
    h = _Harness(detection=_detection(object_type=None, confidence=0.5))
    out = await h.run()
    assert out["llm_kwargs"]["detection_dicts"] == [{"confidence": 0.5, "class_name": "unknown"}]


@pytest.mark.asyncio
async def test_call_llm_preserves_camera_context_and_enrichment_kwargs():
    """Kills mutmut_40, _42, _44, _74, _118, _131.

    Shipped forwards camera_name / enriched_context / enrichment_result to
    _call_llm; execute(None) / where(None) / camera=None (mutmut_38/_39/_42
    abort or reroute the session-1 reads), the `is None` tracking flip
    (mutmut_102: AttributeError on None.has_data) and the enriched_context /
    enrichment_result kwarg nulling+deletion all fail this run or its
    asserts.
    """
    er = _enrichment_result()
    ctx = MagicMock(name="EnrichedContext")
    h = _Harness()
    out = await h.run(enriched_context=ctx, tracking=_tracking(er))
    kw = out["llm_kwargs"]
    assert kw["camera_name"] == "Front Door Camera"
    assert "enrichment_result" in kw
    assert kw["enrichment_result"] is er
    assert "enriched_context" in kw
    assert kw["enriched_context"] is ctx


# =============================================================================
# LLM duration metrics + logs, success path (shipped 3320-3329)
# =============================================================================


@pytest.mark.asyncio
async def test_success_path_duration_metric_and_debug_log():
    """Kills mutmut_46, _101, _134, _136, _137, _138, _140, _141, _145, _146, _147, _148, _150
        _151, _152, _153, _154, _155.
    _150, _151, _152, _153, _154, _155.

    With time patched per-module (+1.0 per read) shipped computes
    llm_duration_ms = int((now - llm_start) * 1000) == 1000 and
    llm_duration_seconds == 2.0, records
    observe_ai_request_duration("nemotron", 2.0) and logs
    logger.debug("Fast path LLM analysis completed for detection 42",
    extra={"camera_id": "front_door", "detection_id": 42, "duration_ms":
    1000}). Kills /1000, +llm_start, *1001, None, the seconds +-flip, the
    service-name None/XXnemotronXX/NEMOTRON renames, the debug msg -> None,
    extra -> None, the deleted extra and the three extra key renames.
    """
    h = _Harness()
    out = await h.run()
    obs = out["observe"].call_args_list
    assert len(obs) == 1
    assert obs[0].args[0] == "nemotron"
    assert obs[0].args[1] == 2.0
    dbg = [
        c
        for c in out["logger"].debug.call_args_list
        if "Fast path LLM analysis completed" in str(c.args[0])
    ]
    assert len(dbg) == 1, out["logger"].debug.call_args_list
    assert dbg[0].args[0] == "Fast path LLM analysis completed for detection 42"
    assert dbg[0].kwargs["extra"] == {
        "camera_id": CAMERA_ID,
        "detection_id": DETECTION_ID,
        "duration_ms": 1000,
    }


# =============================================================================
# LLM duration metrics + logs, failure path (shipped 3333-3344)
# =============================================================================


@pytest.mark.asyncio
async def test_llm_failure_path_duration_metric_and_error_log():
    """Kills mutmut_157, _159, _160, _161, _163, _164, _168, _169, _184, _185, _186, _187
        _188.
    _186, _187, _188.

    Shipped recomputes the same duration pair inside the except arm, records
    observe_ai_request_duration("nemotron", 2.0) and logs logger.error with
    extra={"camera_id":..., "detection_id":..., "duration_ms": 1000,
    "error": "boom"}, then falls back to risk_score 50 / risk_level medium.
    """
    h = _Harness()
    out = await h.run(llm_error=RuntimeError("boom"))
    obs = out["observe"].call_args_list
    assert len(obs) == 1
    assert obs[0].args[0] == "nemotron"
    assert obs[0].args[1] == 2.0
    err = [c for c in out["logger"].error.call_args_list if "LLM analysis failed" in str(c.args[0])]
    assert len(err) == 1, out["logger"].error.call_args_list
    assert err[0].kwargs["extra"] == {
        "camera_id": CAMERA_ID,
        "detection_id": DETECTION_ID,
        "duration_ms": 1000,
        "error": "boom",
    }
    assert out["events"][0].risk_score == 50
    assert out["events"][0].risk_level == "medium"


# =============================================================================
# Session 2: audit + LLMInteraction builders (shipped 3450-3451, 3481-3488)
# =============================================================================


@pytest.mark.asyncio
async def test_partial_audit_receives_context_and_enrichment():
    """Kills mutmut_47, _327, _328, _331.

    Shipped calls audit_service.create_partial_audit(event_id=...,
    llm_prompt=..., enriched_context=enriched_context,
    enrichment_result=enrichment_result); the _get_enriched_context whole-call
    -> None mutant (mutmut_74) makes the forwarded enriched_context None, and
    the shape group's null/delete mutants at THIS occurrence break the kwargs.
    """
    er = _enrichment_result()
    ctx = MagicMock(name="EnrichedContext")
    h = _Harness()
    out = await h.run(enriched_context=ctx, tracking=_tracking(er))
    kwargs = out["audit"].call_args.kwargs
    assert "enriched_context" in kwargs
    assert kwargs["enriched_context"] is ctx
    assert kwargs["enrichment_result"] is er


@pytest.mark.asyncio
async def test_llm_interaction_builders_receive_context_and_enrichment():
    """Kills mutmut_346, _347, _352, _353.

    Shipped calls _build_enrichment_snapshot(detection_ids=[id],
    enrichment_result=enrichment_result, enriched_context=enriched_context)
    and _build_context_sources(enrichment_result=enrichment_result,
    enriched_context=enriched_context) — the four remaining occurrences of
    the two shared shapes, both directions at both sites.
    """
    er = _enrichment_result()
    ctx = MagicMock(name="EnrichedContext")
    h = _Harness()
    out = await h.run(enriched_context=ctx, tracking=_tracking(er))
    snap = out["snapshot"].call_args.kwargs
    assert snap["enrichment_result"] is er
    assert snap["enriched_context"] is ctx
    src = out["sources"].call_args.kwargs
    assert src["enrichment_result"] is er
    assert src["enriched_context"] is ctx
