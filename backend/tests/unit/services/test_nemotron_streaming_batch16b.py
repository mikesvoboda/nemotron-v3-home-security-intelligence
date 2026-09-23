"""Batch-16b battery: nemotron_streaming ERROR-PATH clusters (C6 ERRMSG,
C7/C8 IDEMPOTENCY, C15 ACCUMTEXT, C16 PARSEFALLBACK, C17 EVENT-CONSTRUCT,
C18 COMPLETE-FALLBACK, C20 BROADCAST) from the WP4.4 dossier
(``archive/wp25-feed/wp44-triage/nemotron_streaming.md``).

Sibling of ``test_nemotron_streaming_batch16.py`` (shipped ``561e86f5``), which
pins the request-build clusters. This file pins the guard/error paths of
``analyze_batch_streaming``: every yielded event dict is asserted with FULL
SHAPE (exact four-key error dumps, exact five-key complete dumps) — the
shipped suite's substring/membership asserts left these paths key-mangling
free.

EVERY literal below MEASURED this session via ``/tmp/b16-harness.py`` probes
(consolidated ``/tmp/b16-probes.json`` sections an_err_*, an_parse_*,
an_idem_*, an_complete_blank, an_broadcast_fail, an_redis_sourced,
an_no_camera; plus ``/tmp/b16-probe-last2.json`` pe_event/tf_* and
``/tmp/b16-probe-wire.json``). Production was NOT bent to any mutant. No kill
tallies claimed here — those come only from the ns16b lane red-check.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services import nemotron_streaming as NS
from backend.services.enrichment_pipeline import EnrichmentResult

pytestmark = pytest.mark.unit

NSP = "backend.services.nemotron_streaming"
BASE_TIME = datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)


def make_analyzer():
    """MEASURED carrier analyzer (probe harness /tmp/b16-harness.py)."""
    a = MagicMock(name="analyzer")
    a._redis = AsyncMock()
    a._redis.get = AsyncMock(return_value=None)
    a._get_auth_headers = MagicMock(return_value={"X-Auth": "auth-token"})
    a._format_detections = MagicMock(return_value="FORMATTED_DETECTIONS")
    a._parse_llm_response = MagicMock(
        return_value={
            "risk_score": 75,
            "risk_level": "high",
            "summary": "Parsed summary",
            "reasoning": "Parsed reasoning",
        }
    )
    a._validate_risk_data = MagicMock(side_effect=lambda x: x)
    a._check_idempotency = AsyncMock(return_value=None)
    a._set_idempotency = AsyncMock()
    a._get_existing_event = AsyncMock(return_value=None)
    a._get_enriched_context = AsyncMock(return_value=None)
    a._get_enrichment_result = AsyncMock(return_value=None)
    a._broadcast_event = AsyncMock()
    a._build_enrichment_snapshot = MagicMock(return_value="SNAP")
    a._build_context_sources = MagicMock(return_value="SOURCES")
    return a


def sample_detections():
    return [
        Detection(
            id=1,
            camera_id="test_camera",
            file_path="/export/foscam/test_camera/img1.jpg",
            detected_at=BASE_TIME,
            object_type="person",
            confidence=0.95,
            bbox_x=10,
            bbox_y=20,
            bbox_width=30,
            bbox_height=40,
            video_width=1920,
            video_height=1080,
            track_id=7,
        ),
        Detection(
            id=2,
            camera_id="test_camera",
            file_path="/export/foscam/test_camera/img2.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 15, tzinfo=UTC),
            object_type="car",
            confidence=0.88,
            bbox_x=None,
            video_width=None,
            video_height=None,
            track_id=None,
        ),
    ]


_DEFAULT = object()


def make_session(camera=_DEFAULT, event_id=456):
    if camera is _DEFAULT:
        camera = Camera(id="test_camera", name="Test Camera", folder_path="/test/path")
    session = MagicMock(name="session")
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    camera_result = MagicMock(name="camera_result")
    camera_result.scalar_one_or_none = MagicMock(return_value=camera)
    session.execute = AsyncMock(return_value=camera_result)
    session.add = MagicMock()
    session.commit = AsyncMock()

    async def refresh(obj):
        if isinstance(obj, Event):
            obj.id = event_id

    session.refresh = AsyncMock(side_effect=refresh)
    return session


async def run_analyze(
    analyzer,
    *,
    session=None,
    detections=None,
    chunks=("Based", " on"),
    llm_side_effect=None,
    camera=_DEFAULT,
    event_id=456,
    patches=(),
    **call_kw,
):
    """Drive ``analyze_batch_streaming``; return yielded events + call-site facts."""
    detections = sample_detections() if detections is None else detections
    session = make_session(camera=camera, event_id=event_id) if session is None else session
    captured: dict = {}

    if llm_side_effect is None:

        async def llm_side_effect(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            for c in chunks:
                yield c

    sess_m = patch(f"{NSP}.get_session", return_value=session, autospec=True)
    fetch_m = patch(f"{NSP}.batch_fetch_detections", return_value=detections, autospec=True)
    llm_m = patch(f"{NSP}.call_llm_streaming", side_effect=llm_side_effect, autospec=True)
    ai_m = patch(f"{NSP}.observe_ai_request_duration", autospec=True)
    stage_m = patch(f"{NSP}.observe_stage_duration", autospec=True)
    created_m = patch(f"{NSP}.record_event_created", autospec=True)
    camera_metric_m = patch(f"{NSP}.record_event_by_camera", autospec=True)
    metrics = (ai_m, stage_m, created_m, camera_metric_m)
    ctxs = [sess_m, fetch_m, llm_m, *metrics, *patches]
    entered = [c.__enter__() for c in ctxs]
    events: list = []
    try:
        call_kw.setdefault("analyzer", analyzer)
        call_kw.setdefault("batch_id", "test_batch")
        call_kw.setdefault("camera_id", "test_camera")
        call_kw.setdefault("detection_ids", [1, 2])
        async for ev in NS.analyze_batch_streaming(**call_kw):
            events.append(ev)
    finally:
        for c in ctxs:
            c.__exit__(None, None, None)
    return {
        "events": events,
        "captured": captured,
        "session": session,
        "fetch_mock": entered[1],
        "llm_mock": entered[2],
        "metrics": {
            "observe_ai_request_duration": entered[3],
            "observe_stage_duration": entered[4],
            "record_event_created": entered[5],
            "record_event_by_camera": entered[6],
        },
        "execute_calls": session.execute.call_args_list,
        "add_calls": session.add.call_args_list,
        "commit_count": session.commit.call_count,
    }


def err_dict(code, message, recoverable):
    """MEASURED error-dump shape: exactly these four keys, in this order."""
    return {
        "event_type": "error",
        "error_code": code,
        "error_message": message,
        "recoverable": recoverable,
    }


class TestGuardErrorPaths:
    """C6 ERRMSG: full-shape error events for every guard (probes an_err_*)."""

    async def test_no_redis_yields_internal_error_only(self):
        a = make_analyzer()
        a._redis = None
        r = await run_analyze(a)
        assert r["events"] == [err_dict("INTERNAL_ERROR", "Redis client not initialized", False)]
        assert r["commit_count"] == 0 and r["add_calls"] == []
        assert r["fetch_mock"].call_count == 0

    async def test_batch_missing_in_redis(self):
        a = make_analyzer()
        a._redis.get = AsyncMock(return_value=None)
        r = await run_analyze(a, camera_id=None, detection_ids=[1, 2])
        assert r["events"] == [
            err_dict("BATCH_NOT_FOUND", "Batch test_batch not found in Redis", False)
        ]
        a._redis.get.assert_awaited_once_with("batch:test_batch:camera_id")
        assert r["session"].execute.call_count == 0

    async def test_empty_detection_ids_from_redis(self):
        a = make_analyzer()
        a._redis.get = AsyncMock(return_value=None)  # detections key missing -> []
        r = await run_analyze(a, detection_ids=None)
        assert r["events"] == [
            err_dict("NO_DETECTIONS", "Batch test_batch has no detections", False)
        ]

    async def test_non_int_detection_id(self):
        a = make_analyzer()
        r = await run_analyze(a, detection_ids=["invalid"])
        assert r["events"] == [
            err_dict(
                "INTERNAL_ERROR",
                "Invalid detection_id: invalid literal for int() with base 10: 'invalid'",
                False,
            )
        ]

    async def test_no_db_detections(self):
        a = make_analyzer()
        r = await run_analyze(a, detections=[])
        assert r["events"] == [
            err_dict("NO_DETECTIONS", "No detections found for batch test_batch", False)
        ]
        assert r["fetch_mock"].call_count == 1


class TestLlmErrorPaths:
    """C6 ERRMSG llm-side (probes an_err_llm_timeout/connect/server)."""

    async def test_timeout(self):
        a = make_analyzer()

        async def boom(*args, **kwargs):
            raise httpx.ReadTimeout("ReadTimeout")
            yield  # pragma: no cover

        r = await run_analyze(a, llm_side_effect=boom)
        assert r["events"] == [err_dict("LLM_TIMEOUT", "LLM timeout: ReadTimeout", True)]

    async def test_connect_error(self):
        a = make_analyzer()

        async def boom(*args, **kwargs):
            raise httpx.ConnectError("Connection refused")
            yield  # pragma: no cover

        r = await run_analyze(a, llm_side_effect=boom)
        assert r["events"] == [
            err_dict("LLM_CONNECTION_ERROR", "LLM connection error: Connection refused", True)
        ]

    async def test_server_error_generic(self):
        a = make_analyzer()

        async def boom(*args, **kwargs):
            raise RuntimeError("kaboom")
            yield  # pragma: no cover

        r = await run_analyze(a, llm_side_effect=boom)
        assert r["events"] == [err_dict("LLM_SERVER_ERROR", "LLM inference failed", True)]
        assert r["session"].add.call_count == 0  # event never created


class TestIdempotencyPaths:
    """C7/C8 IDEMPOTENCY (probes an_idem_full, an_idem_blank)."""

    async def test_hit_with_populated_existing_event_short_circuits(self):
        a = make_analyzer()
        existing = Event(
            id=123,
            batch_id="b",
            camera_id="c",
            risk_score=75,
            risk_level="high",
            summary="S",
            reasoning="R",
        )
        a._check_idempotency = AsyncMock(return_value=123)
        a._get_existing_event = AsyncMock(return_value=existing)
        r = await run_analyze(a)
        # MEASURED an_idem_full: single complete event, exact dict
        assert r["events"] == [
            {
                "event_type": "complete",
                "event_id": 123,
                "risk_score": 75,
                "risk_level": "high",
                "summary": "S",
                "reasoning": "R",
            }
        ]
        a._check_idempotency.assert_awaited_once_with("test_batch")
        a._get_existing_event.assert_awaited_once_with(123)
        assert r["session"].add.call_count == 0  # nothing written
        assert r["fetch_mock"].call_count == 0  # short-circuit before DB work

    async def test_hit_with_blank_fields_uses_or_defaults(self):
        a = make_analyzer()
        existing = Event(
            id=123,
            batch_id="b",
            camera_id="c",
            risk_score=None,
            risk_level=None,
            summary=None,
            reasoning=None,
        )
        a._check_idempotency = AsyncMock(return_value=123)
        a._get_existing_event = AsyncMock(return_value=existing)
        r = await run_analyze(a)
        assert r["events"] == [
            {
                "event_type": "complete",
                "event_id": 123,
                "risk_score": 50,
                "risk_level": "medium",
                "summary": "No summary available",
                "reasoning": "No reasoning available",
            }
        ]  # MEASURED an_idem_blank — these defaults DIFFER from the tail-path
        # defaults ("No summary"/"No reasoning"): two separate literals.

    async def test_hit_but_event_missing_falls_through(self):
        a = make_analyzer()
        a._check_idempotency = AsyncMock(return_value=999)
        a._get_existing_event = AsyncMock(return_value=None)
        r = await run_analyze(a)
        assert r["events"][-1]["event_type"] == "complete"  # full analysis ran
        assert a._get_existing_event.await_args.args == (999,)


class TestRedisSourcedIds:
    """C13-adjacent: detection_ids sourced from Redis JSON (an_redis_sourced)."""

    async def test_redis_json_ids_int_cast(self):
        a = make_analyzer()

        async def fake_get(key):
            return {
                "batch:test_batch:camera_id": "camera_from_redis",
                "batch:test_batch:detections": "[1, 2]",
            }[key]

        a._redis.get = AsyncMock(side_effect=fake_get)
        r = await run_analyze(a, camera_id=None, detection_ids=None)
        assert [c.args[0] for c in a._redis.get.call_args_list] == [
            "batch:test_batch:camera_id",
            "batch:test_batch:detections",
        ]
        assert r["fetch_mock"].call_args.args[1] == [1, 2]
        # MEASURED an_redis_sourced: enrich cache call carries the REDIS-sourced
        # camera_id, while the camera row (session returns one) provides the name.
        assert a._get_enriched_context.call_args.args[:3] == (
            "test_batch",
            "camera_from_redis",
            [1, 2],
        )
        assert r["llm_mock"].call_args.kwargs["camera_name"] == "Test Camera"


class TestParseFallbackAndDefaults:
    """C16 PARSEFALLBACK + C17 Event defaults (probes an_parse_empty,
    an_parse_raises, b16-probe-last2.json pe_*)."""

    async def test_parse_returns_empty_dict_uses_event_get_defaults(self):
        a = make_analyzer()
        a._parse_llm_response = MagicMock(return_value={})
        r = await run_analyze(a, chunks=["AAABBB"])
        assert r["events"][-1] == {
            "event_type": "complete",
            "event_id": 456,
            "risk_score": 50,
            "risk_level": "medium",
            "summary": "No summary",
            "reasoning": "No reasoning",
        }  # MEASURED pe_event
        a._parse_llm_response.assert_called_once_with("AAABBB")
        ev = next(c.args[0] for c in r["add_calls"] if isinstance(c.args[0], Event))
        assert (ev.risk_score, ev.risk_level, ev.summary, ev.reasoning, ev.reviewed) == (
            50,
            "medium",
            "No summary",
            "No reasoning",
            False,
        )  # MEASURED pe_ev_fields

    async def test_parse_raises_valueerror_fallback_dict(self):
        a = make_analyzer()
        a._parse_llm_response = MagicMock(side_effect=ValueError("bad json"))
        r = await run_analyze(a, chunks=["Invalid JSON"])
        assert r["events"][-1] == {
            "event_type": "complete",
            "event_id": 456,
            "risk_score": 50,
            "risk_level": "medium",
            "summary": "Analysis unavailable",
            "reasoning": "Could not parse LLM response",
        }  # MEASURED an_parse_raises — DISTINCT literals from the empty-dict path

    async def test_complete_blank_event_fields_or_defaults(self):
        a = make_analyzer()
        a._parse_llm_response = MagicMock(
            return_value={"risk_score": None, "risk_level": None, "summary": "", "reasoning": ""}
        )
        r = await run_analyze(a)
        assert r["events"][-1] == {
            "event_type": "complete",
            "event_id": 456,
            "risk_score": 50,
            "risk_level": "medium",
            "summary": "No summary",
            "reasoning": "No reasoning",
        }  # MEASURED an_complete_blank (tail-path defaults, NOT the idem-path ones)


class TestTrackingFlowAndBroadcast:
    """C15 tracking-data gate + C20 BROADCAST (an_broadcast_fail, tf_*)."""

    async def test_tracking_no_data_gate_passes_none(self):
        a = make_analyzer()
        tr = MagicMock(has_data=False)
        tr.data = MagicMock(name="must-not-be-used")
        a._get_enrichment_result = AsyncMock(return_value=tr)
        r = await run_analyze(a)
        assert r["llm_mock"].call_args.kwargs["enrichment_result"] is None
        lli = next(
            c.args[0] for c in r["add_calls"] if type(c.args[0]).__name__ == "LLMInteraction"
        )
        assert lli.household_matches is None

    async def test_tracking_has_data_identity_flow(self):
        a = make_analyzer()
        er = EnrichmentResult(
            license_plates=["LP1"],
            faces=[],
            vision_extraction=None,
            person_reid_matches={},
            vehicle_reid_matches={},
            person_household_matches={},
            vehicle_household_matches={},
        )
        tr = MagicMock(has_data=True)
        tr.data = er
        a._get_enrichment_result = AsyncMock(return_value=tr)
        r = await run_analyze(a)
        assert r["llm_mock"].call_args.kwargs["enrichment_result"] is er  # tf_data_identity

    async def test_tracking_matches_dict_shape(self):
        a = make_analyzer()
        er = EnrichmentResult(
            license_plates=[],
            faces=[],
            vision_extraction=None,
            person_reid_matches={},
            vehicle_reid_matches={},
            person_household_matches=[{"p": 1}],
            vehicle_household_matches=[],
        )
        tr = MagicMock(has_data=True)
        tr.data = er
        a._get_enrichment_result = AsyncMock(return_value=tr)
        r = await run_analyze(a)
        lli = next(
            c.args[0] for c in r["add_calls"] if type(c.args[0]).__name__ == "LLMInteraction"
        )
        assert lli.household_matches == {"persons": [{"p": 1}], "vehicles": []}

    async def test_broadcast_failure_does_not_break_stream(self):
        a = make_analyzer()
        a._broadcast_event = AsyncMock(side_effect=RuntimeError("ws down"))
        r = await run_analyze(a)
        assert r["events"][-1]["event_type"] == "complete"
        assert a._broadcast_event.await_args.args[0].id == 456  # MEASURED arg_type Event

    async def test_metrics_and_idempotency_set_called(self):
        a = make_analyzer()
        r = await run_analyze(a)
        m = r["metrics"]
        assert m["observe_ai_request_duration"].call_args.args[0] == "nemotron"
        assert m["observe_stage_duration"].call_args.args[0] == "analyze"
        assert m["record_event_created"].call_count == 1
        a._set_idempotency.assert_awaited_once_with("test_batch", 456)  # MEASURED set_idem
