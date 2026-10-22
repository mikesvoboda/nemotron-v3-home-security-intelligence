"""Unit tests for `vlm_analyzer` (Phase 1.3, spec §2:100, §6 ladder).

The analyzer is the vlm-mode pipeline entry - a SIBLING of nemotron_analyzer
(that file is NOT edited; the legacy path stays byte-identical). Its whole
job is the §6 rule table, so this file pins that table row by row:

  - rejected => score clamped to <= SeverityService.low_max, and the clamp
    is VISIBLE in the stored reasoning (spec: log the clamp);
  - uncertain => score KEPT (spec §6:145 - uncertain is not rejected);
  - risk_level ALWAYS derived by SeverityService, never echoed from the
    model (VlmVerdict carries no level at all - spec §3 Derived row);
  - verification failure => event row WITH risk_score/risk_level NULL plus
    an EventVerification row reading verification_failed (spec §6:320-323) -
    the event exists precisely so the UI shows "needs review";
  - the VLM never originates an event: a batch with no camera metadata in
    Redis and no queue-payload camera (i.e. the detector never closed it)
    is refused LOUDLY with zero writes;
  - one assess() call per batch (the §6 retry-once lives INSIDE
    vlm_client - pinned in test_vlm_client.TestFailureLadder; duplicating
    it here would double the S4 latency budget).

Plus the seams the spec's "one code path" rule demands: build_assess_context
is ONE pure function over plain detection dicts (production feeds values
read in session 1; replay - 2.1 - feeds values from the eval store); the
broadcast payload carries the `verification` key rendered from the
analyzer's OWN transaction; replay never broadcasts; a broadcast failure
never un-does the committed event.

Style note (house, mirroring test_vlm_client.py): the DB/broadcaster/zone
seams are patched on THIS module's namespace (get_session,
get_zones_for_detection, load_household_context, and the lazily-imported
backend.services.event_broadcaster.get_broadcaster).
"""

from __future__ import annotations

import asyncio
import json
import logging
import operator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime, time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
import sqlalchemy
from sqlalchemy.dialects import postgresql

from backend.api.schemas.websocket import WebSocketEventData
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_verification import EventVerification
from backend.models.notification_preferences import (
    CameraNotificationSetting,
    NotificationPreferences,
    QuietHoursPeriod,
)
from backend.services import vlm_analyzer as va
from backend.services.severity import SeverityService, get_severity_service
from backend.services.vlm_client import VlmSchemaError, VlmTransportError
from backend.services.vlm_verdict import VlmAssessRequest, VlmVerdict

# The shipped band defaults (29/59/84) pinned EXPLICITLY so no .env drift
# can move the table this file asserts (SeverityService takes overrides).
SEV = SeverityService(low_max=29, medium_max=59, high_max=84)


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


def make_detection_row(
    det_id: int,
    *,
    camera_id: str = "front_door",
    object_type: str = "person",
    confidence: float | None = 0.9,
    detected_at: datetime | None = None,
    file_path: str | None = None,
    track_id: int | None = None,
    bbox: tuple[int, int, int, int] | None = None,
) -> dict[str, Any]:
    """A plain dict carrying exactly the `Detection` columns the analyzer
    reads. Production passes these after session-1 extraction (nemotron's
    `detections_for_enrichment` precedent, :2826); replay builds the same
    dicts from an eval-store item - the builder never touches an ORM
    object, which is what makes it the ONE path."""
    ts = detected_at or datetime(2026, 9, 25, 12, 0, 0, tzinfo=UTC)
    row: dict[str, Any] = {
        "id": det_id,
        "camera_id": camera_id,
        "object_type": object_type,
        "confidence": confidence,
        "detected_at": ts,
        "file_path": file_path or f"/media/front_door/det_{det_id}.jpg",
        "thumbnail_path": None,
        "track_id": track_id,
    }
    if bbox is not None:
        row.update(zip(("bbox_x", "bbox_y", "bbox_width", "bbox_height"), bbox, strict=True))
        row["video_width"] = 100
        row["video_height"] = 100
    return row


def make_verdict(
    *,
    verdict: str = "confirmed",
    risk_score: int = 85,
    engine: str = "llama.cpp",
    model_id: str = "Qwen3VL-8B-Instruct-Q4_K_M",
) -> VlmVerdict:
    return VlmVerdict(
        verdict=verdict,
        risk_score=risk_score,
        summary="A person stands at the door.",
        reasoning="Criterion evidence reviewed.",
        description="Front door, one person, evening.",
        criteria=[{"name": "person_present", "passed": True, "evidence": "full frame"}],
        provenance={"engine": engine, "model_id": model_id},
    )


class FakeRedis:
    """The analyzer's minimal Redis surface: string keys via get/set, and
    ``batch:<id>:detections`` as a LIST via lrange.

    The list half is not optional: BatchAggregator writes that key with RPUSH
    (batch_aggregator.py:23), so a fake that only speaks GET about it pins the
    fake, not production — analyze_batch reads it with LRANGE and a real client
    refuses GET on a LIST with WRONGTYPE. Seed lists via the ``lists`` arg.
    """

    def __init__(
        self,
        values: dict[str, str] | None = None,
        lists: dict[str, list[str]] | None = None,
    ) -> None:
        self.values: dict[str, str] = dict(values or {})
        self.lists: dict[str, list[str]] = {k: list(v) for k, v in (lists or {}).items()}
        self.sets: list[tuple[str, str]] = []

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, expire: int | None = None) -> None:
        self.values[key] = value
        self.sets.append((key, value))

    async def lrange(self, key: str, start: int, stop: int) -> list[str]:
        items = self.lists.get(key, [])
        return items[start:] if stop == -1 else items[start : stop + 1]


class FakeClient:
    """Scriptable assess: `script` is consumed one outcome per call - a
    VlmVerdict is returned, an exception is raised. prompt_text mirrors the
    real VlmClient's contract (text over request.context + the image paths)
    so the prompt-stored assertions pin the ANALYZER's behavior (store the
    client's prompt verbatim + the key-frame path line), not the fake's."""

    def __init__(self, script: list[Any]) -> None:
        self.script = list(script)
        self.calls: list[VlmAssessRequest] = []

    async def assess(self, request: VlmAssessRequest) -> VlmVerdict:
        self.calls.append(request)
        outcome = self.script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def prompt_text(self, request: VlmAssessRequest) -> str:
        return (
            f"ASSESS camera={request.context.camera_id} "
            f"zones={request.context.zones} "
            f"household={json.dumps(request.context.household, sort_keys=True)} "
            f"PATHS {request.image_paths}"
        )

    async def close(self) -> None:
        self.closed = True


class FakeBroadcaster:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def broadcast_event(self, message: dict[str, Any]) -> int:
        self.messages.append(message)
        return 1


def as_orm(row: dict[str, Any]) -> Any:
    """The analyzer reads ORM ATTRIBUTES off session-1 rows (production
    reality); the fixtures author plain dicts, so the fake session hands
    them over as attribute objects - the dict stays the builder's input
    shape, the ORM read stays the analyzer's. The nullable bbox/video
    columns the fixture omitted exist as None, like the real columns."""
    full = {
        "track_id": None,
        "bbox_x": None,
        "bbox_y": None,
        "bbox_width": None,
        "bbox_height": None,
        "video_width": None,
        "video_height": None,
    }
    full.update(row)
    return SimpleNamespace(**full)


class FakeResult:
    def __init__(self, rows: list[Any], scalar: Any = None) -> None:
        self._rows = rows
        self._scalar = scalar

    def scalars(self) -> FakeResult:
        return self

    def all(self) -> list[Any]:
        return list(self._rows)

    def first(self) -> Any:
        return self._rows[0] if self._rows else None

    def scalar_one_or_none(self) -> Any:
        if self._scalar is not None:
            return self._scalar
        return self._rows[0] if self._rows else None


class FakeSession:
    """Records add/flush and answers the analyzer's two SELECT shapes by
    table name; assigns fake autoincrement ids on add() so event.id and the
    verification FK resolve like a flush would."""

    def __init__(
        self,
        detections: list[Any] | None = None,
        existing_event: Any = None,
    ) -> None:
        # dict fixtures -> ORM-like rows, as production's SELECT would.
        self.detections = [as_orm(d) if isinstance(d, dict) else d for d in (detections or [])]
        self.existing_event = existing_event
        self.added: list[Any] = []
        self.flushes = 0
        self.executed: list[Any] = []
        self._next_id = 100

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            self._next_id += 1
            obj.id = self._next_id

    async def flush(self) -> None:
        self.flushes += 1

    async def execute(self, stmt: Any) -> FakeResult:
        self.executed.append(stmt)
        sql = str(stmt)
        # Order matters: "event_verifications" contains the substring
        # "events", so the verification table must be matched first.
        if "event_verifications" in sql:
            rows = [o for o in self.added if type(o).__name__ == "EventVerification"]
            return FakeResult(rows)
        if "events" in sql and "INSERT" not in sql:
            return FakeResult([self.existing_event] if self.existing_event is not None else [])
        if "detections" in sql and "INSERT" not in sql:
            return FakeResult(self.detections)
        return FakeResult([])


class ZoneLike:
    """get_zones_for_detection returns ORM Zone rows; the analyzer reads
    .id/.name only."""

    def __init__(self, zone_id: str, name: str) -> None:
        self.id = zone_id
        self.name = name


def make_analyzer(
    monkeypatch,
    *,
    client: FakeClient | None = None,
    redis: FakeRedis | None = None,
    detections: list[Any] | None = None,
    existing_event: Any = None,
    zones: list[ZoneLike] | None = None,
    household: dict[str, Any] | None = None,
    replay: bool = False,
    broadcast_error: Exception | None = None,
):
    session = FakeSession(
        detections=detections if detections is not None else [make_detection_row(11)],
        existing_event=existing_event,
    )
    broadcaster = FakeBroadcaster()
    if broadcast_error is not None:
        broadcaster.broadcast_event = AsyncMock(side_effect=broadcast_error)

    monkeypatch.setattr(va, "get_session", lambda: session, raising=False)
    monkeypatch.setattr(
        "backend.services.event_broadcaster.get_broadcaster",
        AsyncMock(return_value=broadcaster),
        raising=False,
    )
    if zones is not None:
        monkeypatch.setattr(
            va, "get_zones_for_detection", AsyncMock(return_value=zones), raising=False
        )
    if household is not None:
        monkeypatch.setattr(
            va, "load_household_context", AsyncMock(return_value=household), raising=False
        )

    analyzer = va.VlmAnalyzer(
        vlm_client=client or FakeClient([make_verdict()]),
        redis_client=redis if redis is not None else FakeRedis(),
        replay=replay,
    )
    return analyzer, session, broadcaster


async def analyze(analyzer: va.VlmAnalyzer, batch_id: str = "b1"):
    # The queue-payload flow: close_batch hands camera_id + detection_ids
    # to the consumer, so the production call site always passes them.
    return await analyzer.analyze_batch(batch_id, camera_id="front_door", detection_ids=[11])


# ---------------------------------------------------------------------------
# Pure builders: AssessInput field-for-field, ONE code path
# ---------------------------------------------------------------------------


class TestBuildAssessContext:
    def test_fields_mirror_assess_input_and_carry_values(self):
        from backend.evaluation.assess_input import AssessInput

        ctx = va.build_assess_context(
            camera_id="front_door",
            detections=[make_detection_row(7), make_detection_row(8, confidence=None)],
            zones=["driveway"],
            household={"z1": {"owner_id": 1}},
        )
        assert set(ctx.model_fields) == set(AssessInput.model_fields)
        assert ctx.camera_id == "front_door"
        assert ctx.zones == ["driveway"]
        assert ctx.household == {"z1": {"owner_id": 1}}
        assert ctx.zone_crossing is False
        assert [d["id"] for d in ctx.detections] == [7, 8]
        # confidence stays honest-None, never laundered to 0.0
        assert ctx.detections[1]["confidence"] is None
        # detection rows follow control_freeze._build_snapshot's keys
        # (id/object_type/confidence/bbox/detected_at) - the store shape.
        assert set(ctx.detections[0]) == {"id", "object_type", "confidence", "bbox", "detected_at"}
        assert ctx.detections[0]["bbox"] == [None, None, None, None] or ctx.detections[0]["bbox"]
        # timestamp: ISO of the EARLIEST detection (the snapshot's moment)
        assert ctx.timestamp.startswith("2026-09-25T12:00:00")

    def test_replay_store_rows_flow_through_unchanged(self):
        # The 2.1 half of "one path": an eval-store detection dict (bbox
        # already a list, detected_at already a string) builds the SAME
        # context without any DB.
        store_row = {
            "id": 3,
            "object_type": "vehicle",
            "confidence": 0.7,
            "bbox": [1, 2, 3, 4],
            "detected_at": "2026-09-25T12:00:00+00:00",
        }
        ctx = va.build_assess_context(
            camera_id="front_door", detections=[store_row], zones=[], household={}
        )
        assert ctx.detections[0]["bbox"] == [1, 2, 3, 4]
        assert ctx.timestamp == "2026-09-25T12:00:00+00:00"

    def test_detects_zone_crossing_from_track_membership_change(self):
        rows = [
            make_detection_row(1, track_id=5),
            make_detection_row(2, track_id=5),
        ]
        # same track seen in two DIFFERENT zone memberships -> crossed
        assert va.detect_zone_crossing(rows, {1: ["yard"], 2: ["driveway"]}) is True
        assert va.detect_zone_crossing(rows, {1: ["yard"], 2: ["yard"]}) is False
        # no memberships, or no shared track -> never crossed
        assert va.detect_zone_crossing(rows, {}) is False
        assert (
            va.detect_zone_crossing(
                [make_detection_row(1), make_detection_row(2)],
                {1: ["yard"], 2: ["driveway"]},
            )
            is False
        )

    def test_request_builder_selects_key_frames_within_one_to_four(self):
        rows = [make_detection_row(i, object_type=f"type{i}") for i in range(1, 6)]
        request = va.build_assess_request(
            context=va.build_assess_context(camera_id="c", detections=rows),
            detections=rows,
        )
        # 5 distinct (camera, class) pairs -> capped at the 4-frame budget
        assert len(request.image_paths) == 4
        assert all(p.endswith(".jpg") for p in request.image_paths)

    def test_request_builder_single_pair_yields_one_frame(self):
        rows = [make_detection_row(i) for i in range(1, 4)]
        request = va.build_assess_request(
            context=va.build_assess_context(camera_id="c", detections=rows),
            detections=rows,
        )
        assert len(request.image_paths) == 1

    # -------------------------------------------------------------------
    # Provenance names the rows whose PIXELS were shown (2026-09-27)
    # -------------------------------------------------------------------
    # The detector emits one Detection ROW per object over ONE shared
    # `file_path` (detector_client:1184), so `file_path` is not a key. The
    # selector picks per STILL and each pick carries the id of the row that
    # represents that still; the provenance row must be those ids. It used to
    # re-derive them with `{row["file_path"]: row["id"]}`, whose LAST write
    # wins - so with three objects on one JPEG the stored provenance named
    # whichever row happened to sort last in the batch while the model had
    # been shown the strongest one. `key_frame_detection_ids` is the UI's
    # thumbnail resolver (spec §4): a wrong id renders evidence that was not
    # the evidence.

    def test_shared_file_batch_shows_one_still(self) -> None:
        """Three objects on one JPEG -> the request carries ONE image, the
        still the model is actually shown (not the same file three times)."""
        rows = [
            make_detection_row(
                11, object_type="person", confidence=0.95, file_path="/media/f1.jpg"
            ),
            make_detection_row(12, object_type="car", confidence=0.90, file_path="/media/f1.jpg"),
            make_detection_row(13, object_type="dog", confidence=0.85, file_path="/media/f1.jpg"),
        ]
        request = va.build_assess_request(
            context=va.build_assess_context(camera_id="c", detections=rows),
            detections=rows,
        )
        assert request.image_paths == ["/media/f1.jpg"]

    def test_key_frame_ids_are_the_selectors_representatives(self) -> None:
        rows = [
            make_detection_row(
                11, object_type="person", confidence=0.95, file_path="/media/f1.jpg"
            ),
            make_detection_row(12, object_type="car", confidence=0.90, file_path="/media/f1.jpg"),
            make_detection_row(13, object_type="dog", confidence=0.85, file_path="/media/f1.jpg"),
        ]
        ctx = va.build_assess_context(camera_id="c", detections=rows)
        request = va.build_assess_request(context=ctx, detections=rows)
        # the strongest member of the shared still - NOT detection 13, which
        # is what a `{path: id}` dict hands back (last write wins).
        assert va.key_frame_ids(request, detections=rows) == [11]

    def test_key_frame_ids_line_up_with_image_paths_one_to_one(self) -> None:
        """id[i] is the row whose file is image_paths[i], for a batch mixing a
        crowded still with a distinct one - the pairing the UI relies on."""
        rows = [
            make_detection_row(
                11, object_type="person", confidence=0.95, file_path="/media/f1.jpg"
            ),
            make_detection_row(12, object_type="car", confidence=0.90, file_path="/media/f1.jpg"),
            make_detection_row(
                14, object_type="bicycle", confidence=0.50, file_path="/media/f2.jpg"
            ),
        ]
        ctx = va.build_assess_context(camera_id="c", detections=rows)
        request = va.build_assess_request(context=ctx, detections=rows)
        ids = va.key_frame_ids(request, detections=rows)
        by_id = {r["id"]: r["file_path"] for r in rows}
        assert len(ids) == len(request.image_paths)
        assert [by_id[i] for i in ids] == request.image_paths

    def test_request_names_every_row_on_each_attached_frame(self) -> None:
        """A5500 M1 (2026-09-28): three person rows on three stills, ONE still
        attached - the model assumed all three boxes were on the image it saw,
        found one person, and called the detector wrong. The request now says
        which rows sit on which attached frame: every row on that still, not
        only the selector's representative."""
        rows = [
            make_detection_row(
                11, object_type="person", confidence=0.95, file_path="/media/f1.jpg"
            ),
            make_detection_row(12, object_type="car", confidence=0.90, file_path="/media/f1.jpg"),
            make_detection_row(
                14, object_type="bicycle", confidence=0.50, file_path="/media/f2.jpg"
            ),
        ]
        ctx = va.build_assess_context(camera_id="c", detections=rows)
        request = va.build_assess_request(context=ctx, detections=rows)
        on = {p: sorted(r["id"] for r in rows if r["file_path"] == p) for p in request.image_paths}
        assert request.frame_detection_ids is not None
        assert [sorted(ids) for ids in request.frame_detection_ids] == [
            on[p] for p in request.image_paths
        ]

    def test_specialist_outputs_flow_from_the_snapshot_not_a_side_door(self):
        """Rev 6 plan: "the prompt builder takes the outputs FROM the
        snapshot." The context is the ONE carrier end to end; the builder has
        no side parameter and the request has no top-level duplicate (one
        carrier, spec §2/§6)."""
        rows = [make_detection_row(1)]
        ctx = va.build_assess_context(
            camera_id="c",
            detections=rows,
            specialist_outputs={"face": "1 unknown adult"},
        )
        assert ctx.specialist_outputs == {"face": "1 unknown adult"}
        request = va.build_assess_request(context=ctx, detections=rows)
        assert request.context.specialist_outputs == {"face": "1 unknown adult"}
        assert "specialist_outputs" not in VlmAssessRequest.model_fields
        # the side parameter is gone: passing one is a TypeError
        with pytest.raises(TypeError):
            va.build_assess_request(context=ctx, detections=rows, specialist_outputs={"face": "x"})

    FOSCAM = "/export/foscam/front_door/FoscamCamera_X/snap/MDAlarm_20260925-{}.jpg"
    ARRIVAL = datetime(2026, 9, 25, 15, 0, 0, tzinfo=UTC)  # 11:00 EDT

    def test_capture_tz_takes_the_timestamp_from_the_foscam_filename(self):
        row = make_detection_row(
            7, detected_at=self.ARRIVAL, file_path=self.FOSCAM.format("021400")
        )
        ctx = va.build_assess_context(
            camera_id="front_door", detections=[row], capture_tz=ZoneInfo("America/New_York")
        )
        assert ctx.timestamp == "2026-09-25T06:14:00+00:00"
        # rows keep arrival time: only the snapshot's moment moves
        assert ctx.detections[0]["detected_at"].startswith("2026-09-25T15:00:00")

    def test_capture_tz_unset_keeps_arrival_time(self):
        row = make_detection_row(
            7, detected_at=self.ARRIVAL, file_path=self.FOSCAM.format("021400")
        )
        ctx = va.build_assess_context(camera_id="front_door", detections=[row])
        assert ctx.timestamp.startswith("2026-09-25T15:00:00")

    def test_capture_tz_picks_the_earliest_capture_across_rows(self):
        rows = [
            make_detection_row(7, detected_at=self.ARRIVAL, file_path=self.FOSCAM.format("021405")),
            make_detection_row(8, detected_at=self.ARRIVAL, file_path=self.FOSCAM.format("021400")),
        ]
        ctx = va.build_assess_context(
            camera_id="front_door", detections=rows, capture_tz=ZoneInfo("America/New_York")
        )
        assert ctx.timestamp == "2026-09-25T06:14:00+00:00"

    def test_a_non_foscam_name_falls_back_to_arrival(self):
        row = make_detection_row(7, detected_at=self.ARRIVAL)  # /media/front_door/det_7.jpg
        ctx = va.build_assess_context(
            camera_id="front_door", detections=[row], capture_tz=ZoneInfo("America/New_York")
        )
        assert ctx.timestamp.startswith("2026-09-25T15:00:00")

    def test_store_rows_pass_through_with_capture_tz_set(self):
        # Replay: an eval-store row already carries its frozen ISO string.
        store_row = {
            "id": 1,
            "object_type": "person",
            "confidence": 0.9,
            "bbox": [1, 2, 3, 4],
            "detected_at": "2026-09-25T12:00:00+00:00",
        }
        ctx = va.build_assess_context(
            camera_id="front_door", detections=[store_row], capture_tz=ZoneInfo("America/New_York")
        )
        assert ctx.timestamp == "2026-09-25T12:00:00+00:00"


class TestCaptureTimeReachesTheRequest:
    async def test_analyze_batch_sends_the_filename_capture_time(self, monkeypatch):
        client = FakeClient([make_verdict()])
        row = make_detection_row(
            11,
            detected_at=datetime(2026, 9, 25, 15, 0, 0, tzinfo=UTC),
            file_path="/export/foscam/front_door/FoscamCamera_X/snap/MDAlarm_20260925-021400.jpg",
        )
        analyzer, _, _ = make_analyzer(monkeypatch, client=client, detections=[row])
        analyzer._settings = analyzer._settings.model_copy(
            update={"camera_timezone": "America/New_York"}
        )
        await analyze(analyzer)
        assert client.calls[0].context.timestamp == "2026-09-25T06:14:00+00:00"


# ---------------------------------------------------------------------------
# The §6 invariant table, per row
# ---------------------------------------------------------------------------


class TestVerdictInvariants:
    def test_rejected_clamps_to_low_max_and_shows_the_clamp(self):
        out = va.apply_verdict_invariants(make_verdict(verdict="rejected", risk_score=90), SEV)
        assert out["verdict"] == "rejected"
        assert out["risk_score"] == 29
        assert out["risk_level"] == "low"
        assert "clamped to <= 29" in out["reasoning"]

    def test_rejected_below_low_max_is_untouched(self):
        out = va.apply_verdict_invariants(make_verdict(verdict="rejected", risk_score=5), SEV)
        assert out["risk_score"] == 5
        assert out["risk_level"] == "low"
        assert "clamped" not in out["reasoning"]

    def test_uncertain_keeps_its_score(self):
        # spec §6:145 - uncertain is NOT rejected; only rejected is
        # "not a threat". A high score survives the gate.
        out = va.apply_verdict_invariants(make_verdict(verdict="uncertain", risk_score=85), SEV)
        assert out["risk_score"] == 85
        assert out["risk_level"] == "critical"

    def test_level_is_always_derived_never_echoed(self):
        # VlmVerdict has no level field at all; the table's derivation is
        # pinned across every band boundary (29/59/84 shipped defaults).
        for score, level in [
            (0, "low"),
            (29, "low"),
            (30, "medium"),
            (59, "medium"),
            (60, "high"),
            (84, "high"),
            (85, "critical"),
            (100, "critical"),
        ]:
            out = va.apply_verdict_invariants(make_verdict(risk_score=score), SEV)
            assert out["risk_level"] == level, score
            assert out["risk_score"] == score

    def test_failed_input_is_null_scored(self):
        out = va.apply_verdict_invariants(None, SEV)
        assert out["verdict"] == "verification_failed"
        assert out["risk_score"] is None
        assert out["risk_level"] is None
        assert out["summary"]  # honest text for the UI, never empty


# ---------------------------------------------------------------------------
# analyze_batch against fakes - the full ladder
# ---------------------------------------------------------------------------


class TestAnalyzeBatchScored:
    async def test_happy_path_writes_event_and_row_then_broadcasts_verification(self, monkeypatch):
        client = FakeClient([make_verdict(risk_score=85)])
        analyzer, session, broadcaster = make_analyzer(monkeypatch, client=client)
        event = await analyze(analyzer)

        expected_level = get_severity_service().risk_score_to_severity(85).value
        assert event.risk_score == 85
        assert event.risk_level == expected_level
        assert event.reviewed is False

        # Event AND EventVerification added, event first (same tx: one
        # FakeSession stands in for session 2; the row joined the add()
        # list before it ended).
        types = [type(o).__name__ for o in session.added]
        assert types == ["Event", "EventVerification"]
        row = session.added[1]
        assert row.verdict == "confirmed"
        assert row.criteria[0]["name"] == "person_present"
        assert row.scene_description == "Front door, one person, evening."
        assert row.key_frame_detection_ids == [11]
        # success provenance comes from the VERDICT (the engine's own label)
        assert row.engine == "llama.cpp"
        assert row.model_id == "Qwen3VL-8B-Instruct-Q4_K_M"
        assert row.latency_ms is not None and row.latency_ms >= 0

        # broadcast happened exactly once, with the verification key, and
        # it VALIDATES against the shipped WS schema (the key is P0.4's
        # exclude_if field - a vlm event must render through it).
        assert len(broadcaster.messages) == 1
        data = broadcaster.messages[0]["data"]
        assert data["verification"]["verdict"] == "confirmed"
        assert data["verification"]["key_frame_detection_ids"] == [11]
        assert data["risk_score"] == 85
        WebSocketEventData.model_validate(dict(data))

        # idempotency key set after the write (nemotron's batch_event:<id>)
        assert ("batch_event:b1", str(event.id)) in analyzer._redis.sets
        # exactly ONE assess per batch - the retry-once is the client's
        # ladder step (test_vlm_client.TestFailureLadder), not duplicated.
        assert len(client.calls) == 1

    async def test_junction_rows_written_for_batch_detections(self, monkeypatch):
        analyzer, session, _ = make_analyzer(monkeypatch)
        await analyze(analyzer)
        inserts = [str(s) for s in session.executed if "INSERT" in str(s)]
        assert any("event_detections" in s for s in inserts)

    async def test_llm_prompt_stores_text_and_paths_never_bytes(self, monkeypatch):
        analyzer, session, _ = make_analyzer(monkeypatch)
        event = await analyze(analyzer)
        assert event.llm_prompt
        assert "/media/front_door/det_11.jpg" in event.llm_prompt
        assert "data:image" not in event.llm_prompt  # D10/§6: paths, not bytes

    async def test_zones_and_household_reach_the_prompt(self, monkeypatch):
        rows = [make_detection_row(11, bbox=(10, 10, 20, 20))]
        analyzer, _, _ = make_analyzer(
            monkeypatch,
            detections=rows,
            zones=[ZoneLike("z1", "driveway")],
            household={"z1": {"owner_id": 3}},
        )
        event = await analyze(analyzer)
        assert "driveway" in event.llm_prompt
        assert "owner_id" in event.llm_prompt

    async def test_replay_mode_never_broadcasts(self, monkeypatch):
        analyzer, _session, broadcaster = make_analyzer(monkeypatch, replay=True)
        await analyze(analyzer)
        assert broadcaster.messages == []

    async def test_broadcast_failure_does_not_undo_the_event(self, monkeypatch):
        analyzer, session, _ = make_analyzer(
            monkeypatch, broadcast_error=RuntimeError("redis down")
        )
        event = await analyze(analyzer)  # must NOT raise
        assert event.risk_score == 85
        assert [type(o).__name__ for o in session.added] == ["Event", "EventVerification"]


class TestAnalyzeBatchVerificationFailed:
    async def _fails(self, monkeypatch, script):
        client = FakeClient(script)
        analyzer, session, broadcaster = make_analyzer(monkeypatch, client=client)
        event = await analyze(analyzer)
        return event, session, broadcaster

    async def test_transport_failure_writes_null_event_plus_row(self, monkeypatch):
        # vlm_client already burned its retry at temperature 0 (its own
        # pin); the analyzer maps the exhausted raise to §6 step 2.
        event, session, broadcaster = await self._fails(monkeypatch, [VlmTransportError("boom")])
        assert isinstance(event, Event)
        assert event.risk_score is None
        assert event.risk_level is None
        assert event.summary  # still tells a human something happened
        types = [type(o).__name__ for o in session.added]
        assert types == ["Event", "EventVerification"]
        row = session.added[1]
        assert row.verdict == "verification_failed"
        # degraded provenance falls back to the SETTINGS labels (NOT NULL
        # columns; no verdict existed to report the engine's own id)
        assert row.engine == va.get_settings().nemotron_verification_engine
        assert row.model_id == va.get_settings().vlm_model_id
        assert row.key_frame_detection_ids == [11]  # what WAS shown to the model

        # the broadcast still rides out: score null, verification present,
        # and the shipped WS schema accepts the present-None payload
        # (P0.25's rule).
        assert len(broadcaster.messages) == 1
        data = broadcaster.messages[0]["data"]
        assert data["risk_score"] is None
        assert data["risk_level"] is None
        assert data["verification"]["verdict"] == "verification_failed"
        WebSocketEventData.model_validate(dict(data))

    async def test_schema_error_maps_to_the_same_degraded_row(self, monkeypatch):
        event, session, _ = await self._fails(monkeypatch, [VlmSchemaError("bad json")])
        assert event.risk_score is None
        assert session.added[1].verdict == "verification_failed"

    async def test_enforcement_probe_failure_maps_too(self, monkeypatch):
        from backend.services.constrained_decoding import ConstrainedDecodingNotEnforced

        event, session, _ = await self._fails(
            monkeypatch, [ConstrainedDecodingNotEnforced("ignored")]
        )
        assert event.risk_score is None
        assert session.added[1].verdict == "verification_failed"


class TestAnalyzeBatchRefusals:
    async def test_empty_batch_refused_loudly_without_writes(self, monkeypatch):
        analyzer, session, broadcaster = make_analyzer(monkeypatch, detections=[])
        with pytest.raises(ValueError):
            await analyze(analyzer)
        assert session.added == []
        assert broadcaster.messages == []

    async def test_batch_without_detector_metadata_refused(self, monkeypatch):
        # §6 "the VLM never originates an event": the detector closing a
        # batch is what leaves `batch:<id>:camera_id` in Redis (or the
        # queue payload the consumer hands us). Neither present -> refuse
        # before any VLM I/O, zero writes.
        client = FakeClient([make_verdict()])
        analyzer, session, _ = make_analyzer(monkeypatch, client=client, redis=FakeRedis({}))
        with pytest.raises(ValueError):
            await analyzer.analyze_batch("ghost")
        assert session.added == []
        assert client.calls == []

    async def test_metadata_from_redis_only_is_enough(self, monkeypatch):
        # Queue payloads carry camera+detections; the Redis-fallback route
        # (nemotron's own shape) still works when only metadata exists.
        redis = FakeRedis(
            {"batch:b9:camera_id": "front_door"},
            # detections is a LIST in production (RPUSH), not a JSON string —
            # seeded as one so this fake can't hide a LIST-vs-GET defect.
            {"batch:b9:detections": ["11"]},
        )
        analyzer, _session, _ = make_analyzer(monkeypatch, redis=redis)
        event = await analyzer.analyze_batch("b9")
        assert event.risk_score == 85

    async def test_idempotency_hit_returns_existing_event_with_no_vlm_call(self, monkeypatch):
        existing = Event(
            id=42, batch_id="b1", camera_id="front_door", risk_score=10, risk_level="low"
        )
        client = FakeClient([make_verdict()])
        analyzer, session, broadcaster = make_analyzer(
            monkeypatch,
            client=client,
            redis=FakeRedis({"batch_event:b1": "42"}),
            existing_event=existing,
        )
        event = await analyze(analyzer)
        assert event is existing
        assert client.calls == []
        assert session.added == []
        assert broadcaster.messages == []


# ---------------------------------------------------------------------------
# Specialist stage wiring (rev 6, F11 ruling 4 / F12) — the texts ride the
# snapshot: production COMPUTES them into context.specialist_outputs before
# assess; replay NEVER re-runs them and passes the stored texts verbatim.
# ---------------------------------------------------------------------------


class TestSpecialistStageWiring:
    async def test_production_fills_specialist_outputs_before_assess(self, monkeypatch):
        texts = {
            "faces": "known person Dad (91% match)",
            "plates": "0 license plates detected",
            "person_reid": "unavailable: re-ID specialist did not run",
        }
        collect = AsyncMock(return_value=texts)
        monkeypatch.setattr(va, "collect_specialist_outputs", collect, raising=False)
        client = FakeClient([make_verdict()])
        analyzer, session, _ = make_analyzer(monkeypatch, client=client)

        await analyze(analyzer)

        # called exactly once, over the SAME key-frame picks the request got
        assert collect.await_count == 1
        kwargs = collect.await_args.kwargs
        assert [f.file_path for f in kwargs["key_frame_paths"]] == client.calls[0].image_paths
        assert kwargs["session"] is session  # the face leg reads the gallery on session 1
        # and the texts rode the snapshot the VLM call carried
        assert client.calls[0].context.specialist_outputs == texts

    async def test_replay_never_reruns_and_passes_stored_texts(self, monkeypatch):
        async def boom(**_kwargs):
            raise AssertionError("replay must never re-run the specialists")

        monkeypatch.setattr(va, "collect_specialist_outputs", boom, raising=False)
        stored = {"faces": "1 unknown face(s)", "plates": "OLDPLATE - not a household plate"}
        client = FakeClient([make_verdict()])
        analyzer, _session, _ = make_analyzer(monkeypatch, client=client, replay=True)

        await analyzer.analyze_batch(
            "b1", camera_id="front_door", detection_ids=[11], specialist_inputs=stored
        )

        assert client.calls[0].context.specialist_outputs == stored

    async def test_replay_without_stored_texts_carries_empty_not_lies(self, monkeypatch):
        async def boom(**_kwargs):
            raise AssertionError("replay must never re-run the specialists")

        monkeypatch.setattr(va, "collect_specialist_outputs", boom, raising=False)
        client = FakeClient([make_verdict()])
        analyzer, _session, _ = make_analyzer(monkeypatch, client=client, replay=True)

        await analyzer.analyze_batch("b1", camera_id="front_door", detection_ids=[11])

        assert client.calls[0].context.specialist_outputs == {}

    async def test_stage_bug_cannot_fail_the_verdict(self, monkeypatch):
        """The analyzer's own belt (plan 3b): a stage that RAISES despite its
        contract still yields all-unavailable texts and the normal event —
        a specialist bug never costs the batch its verdict."""

        async def explode(**_kwargs):
            raise RuntimeError("stage bug")

        monkeypatch.setattr(va, "collect_specialist_outputs", explode, raising=False)
        client = FakeClient([make_verdict()])
        analyzer, session, broadcaster = make_analyzer(monkeypatch, client=client)

        event = await analyze(analyzer)

        texts = client.calls[0].context.specialist_outputs
        assert set(texts) == {"faces", "plates", "person_reid"}
        assert all(t.startswith("unavailable") for t in texts.values())
        assert event.risk_score is not None  # the verdict still landed
        assert broadcaster.messages  # and the event still broadcast

    async def test_default_legs_degrade_to_texts_not_crash(self, monkeypatch):
        """NO specialist fake at all: the real legs run against fake paths
        (files absent, weights absent, [alpr] absent — the sandbox truth) and
        STILL produce three non-blank texts on the request. This is the
        never-blocks-the-verdict rule on the production code, unmocked."""
        client = FakeClient([make_verdict()])
        analyzer, _session, _ = make_analyzer(monkeypatch, client=client)

        await analyze(analyzer)

        texts = client.calls[0].context.specialist_outputs
        assert set(texts) >= {"faces", "plates", "person_reid"}
        assert all(v.strip() for v in texts.values())


# ---------------------------------------------------------------------------
# M1: the notify decision (owner decision 2026-10-03: analyzer-only first)
#
# should_notify existed, unit-tested and with no production caller; nothing
# turned a persisted verdict into a notify/no-notify answer. The analyzer now
# asks it AFTER the verdict is committed and the answer rides the existing
# `event` WebSocket message as `data.notify`. Alert rules and delivery
# channels stay separate follow-ups.
# ---------------------------------------------------------------------------

_ALL_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class NotifySession(FakeSession):
    """FakeSession that also answers the three notification-table SELECTs.

    `prefs`/`camera_setting`/`quiet` are what the DB would hold (None / [] =
    no row); `notify_tables_raise` makes any notification-table read fail,
    to pin that a broken lookup never costs the event or the alert."""

    def __init__(
        self,
        *args: Any,
        prefs=None,
        camera_setting=None,
        quiet=None,
        notify_tables_raise=None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.prefs = prefs
        self.camera_setting = camera_setting
        self.quiet = list(quiet or [])
        self.notify_tables_raise = notify_tables_raise

    async def execute(self, stmt: Any) -> FakeResult:
        sql = str(stmt)
        tables = ("notification_preferences", "camera_notification_settings", "quiet_hours_periods")
        if any(t in sql for t in tables):
            self.executed.append(stmt)
            if self.notify_tables_raise is not None:
                raise self.notify_tables_raise
            if "notification_preferences" in sql:
                return FakeResult([self.prefs] if self.prefs is not None else [])
            if "camera_notification_settings" in sql:
                return FakeResult([self.camera_setting] if self.camera_setting is not None else [])
            return FakeResult(self.quiet)
        return await super().execute(stmt)


def make_notify_analyzer(
    monkeypatch,
    *,
    prefs=None,
    camera_setting=None,
    quiet=None,
    notify_tables_raise=None,
    **kwargs: Any,
):
    analyzer, session, broadcaster = make_analyzer(monkeypatch, **kwargs)
    notify_session = NotifySession(
        detections=session.detections,
        existing_event=session.existing_event,
        prefs=prefs,
        camera_setting=camera_setting,
        quiet=quiet,
        notify_tables_raise=notify_tables_raise,
    )
    monkeypatch.setattr(va, "get_session", lambda: notify_session, raising=False)
    return analyzer, notify_session, broadcaster


class TestNotifyDecision:
    async def test_a_confirmed_high_risk_verdict_notifies_and_the_decision_rides_the_broadcast(
        self, monkeypatch
    ):
        analyzer, _, broadcaster = make_notify_analyzer(
            monkeypatch, client=FakeClient([make_verdict(risk_score=85)])
        )
        await analyze(analyzer)

        data = broadcaster.messages[0]["data"]
        assert data["notify"] is True
        WebSocketEventData.model_validate(dict(data))  # the shipped WS contract accepts it

    async def test_rejected_never_notifies_even_where_every_filter_would_page(self, monkeypatch):
        """spec section 6: rejected => never notifies. The preferences here
        pass the low band and the camera threshold is 0, so the scored path
        WOULD page for the clamped low score - only the verdict rule stops it."""
        prefs = NotificationPreferences(risk_filters=["low", "medium", "high", "critical"])
        camera = CameraNotificationSetting(camera_id="front_door", enabled=True, risk_threshold=0)
        analyzer, _, broadcaster = make_notify_analyzer(
            monkeypatch,
            prefs=prefs,
            camera_setting=camera,
            client=FakeClient([make_verdict(verdict="rejected", risk_score=5)]),
        )
        await analyze(analyzer)
        assert broadcaster.messages[0]["data"]["notify"] is False

    async def test_a_verification_failed_event_with_a_confident_person_detection_notifies(
        self, monkeypatch
    ):
        """spec section 6 step 3: the owner is never left blind - a NULL
        score falls back to the detector-only rule (person/vehicle at or
        above detection_confidence_threshold)."""
        analyzer, _, broadcaster = make_notify_analyzer(
            monkeypatch,
            client=FakeClient([VlmTransportError("boom")]),
            detections=[make_detection_row(11, object_type="person", confidence=0.95)],
        )
        event = await analyze(analyzer)
        assert event.risk_score is None
        assert broadcaster.messages[0]["data"]["notify"] is True

    async def test_a_verification_failed_event_without_a_security_class_stays_quiet(
        self, monkeypatch
    ):
        analyzer, _, broadcaster = make_notify_analyzer(
            monkeypatch,
            client=FakeClient([VlmTransportError("boom")]),
            detections=[make_detection_row(11, object_type="dog", confidence=0.95)],
        )
        await analyze(analyzer)
        assert broadcaster.messages[0]["data"]["notify"] is False

    async def test_globally_disabled_notifications_never_notify(self, monkeypatch):
        analyzer, _, broadcaster = make_notify_analyzer(
            monkeypatch,
            prefs=NotificationPreferences(enabled=False),
            client=FakeClient([make_verdict(risk_score=95)]),
        )
        await analyze(analyzer)
        assert broadcaster.messages[0]["data"]["notify"] is False

    async def test_a_disabled_camera_never_notifies(self, monkeypatch):
        camera = CameraNotificationSetting(camera_id="front_door", enabled=False, risk_threshold=0)
        analyzer, _, broadcaster = make_notify_analyzer(
            monkeypatch, camera_setting=camera, client=FakeClient([make_verdict(risk_score=95)])
        )
        await analyze(analyzer)
        assert broadcaster.messages[0]["data"]["notify"] is False

    async def test_quiet_hours_suppress_a_scored_notification(self, monkeypatch):
        quiet = [
            QuietHoursPeriod(
                label="all day", start_time=time(0, 0), end_time=time(23, 59, 59), days=_ALL_DAYS
            )
        ]
        analyzer, _, broadcaster = make_notify_analyzer(
            monkeypatch, quiet=quiet, client=FakeClient([make_verdict(risk_score=95)])
        )
        await analyze(analyzer)
        assert broadcaster.messages[0]["data"]["notify"] is False

    async def test_replay_makes_no_decision_and_reads_no_notification_tables(self, monkeypatch):
        """Replay stands beside production and writes nothing outward: it must
        neither compute a decision nor touch the owner's notification settings."""
        analyzer, session, _ = make_notify_analyzer(monkeypatch, replay=True)
        await analyze(analyzer)
        assert not [s for s in session.executed if "notification_preferences" in str(s)]

    async def test_a_failed_settings_lookup_never_loses_the_event_or_the_alert(self, monkeypatch):
        """The settings read can fail (DB hiccup). The committed event stands
        and the owner is still paged on a high-risk verdict: the decision falls
        back to the shipped default preferences, never to silence."""
        analyzer, _, broadcaster = make_notify_analyzer(
            monkeypatch,
            notify_tables_raise=RuntimeError("settings read failed"),
            client=FakeClient([make_verdict(risk_score=95)]),
        )
        event = await analyze(analyzer)
        assert event.risk_score == 95
        assert broadcaster.messages[0]["data"]["notify"] is True


# =============================================================================
# Consolidated from test_vlm_analyzer_batch38_y.py & batch38_ay.py (B4.1 step 2)
# =============================================================================


SEV = SeverityService(low_max=29, medium_max=59, high_max=84)
TS1 = datetime(2026, 9, 25, 12, 0, 0, tzinfo=UTC)
TS2 = datetime(2026, 9, 25, 12, 5, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# capture / patch helpers (no fixtures - the sweep calls plain functions)
# ---------------------------------------------------------------------------


class RecordList(logging.Handler):
    """Captures EVERY record emitted through va.logger while active."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def one(self, msg: str) -> logging.LogRecord:
        hits = [r for r in self.records if r.getMessage() == msg]
        assert len(hits) == 1, (msg, [r.getMessage() for r in self.records])
        return hits[0]

    def msgs(self) -> list[str]:
        return [r.getMessage() for r in self.records]


@contextmanager
def logcap():
    cap = RecordList()
    old_level = va.logger.level
    va.logger.addHandler(cap)
    va.logger.setLevel(logging.DEBUG)
    try:
        yield cap
    finally:
        va.logger.removeHandler(cap)
        va.logger.setLevel(old_level)


@contextmanager
def patched(obj: Any, attr: str, value: Any):
    old = getattr(obj, attr)
    setattr(obj, attr, value)
    try:
        yield value
    finally:
        setattr(obj, attr, old)


class Spy:
    """Records (args, kwargs) per call; optional side_effect. ``results``
    (when given) overrides ``result`` per call so one spy can answer one
    call loudly and the rest quietly (the idempotency-key probe)."""

    def __init__(
        self,
        result: Any = None,
        raises: Exception | None = None,
        results: dict[int, Any] | None = None,
    ) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.result = result
        self.raises = raises
        self.results = results or {}

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        if self.raises is not None:
            raise self.raises
        return self.results.get(len(self.calls) - 1, self.result)

    def kwargs(self, index: int = 0) -> dict[str, Any]:
        return self.calls[index][1]

    def args(self, index: int = 0) -> tuple[Any, ...]:
        return self.calls[index][0]

    @property
    def count(self) -> int:
        return len(self.calls)


class SyncSpy:
    """Same call-log surface as Spy for SYNCHRONOUS seams
    (record_pipeline_error is called without await)."""

    def __init__(self, result: Any = None, raises: Exception | None = None) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.result = result
        self.raises = raises

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        if self.raises is not None:
            raise self.raises
        return self.result

    def args(self, index: int = 0) -> tuple[Any, ...]:
        return self.calls[index][0]

    @property
    def count(self) -> int:
        return len(self.calls)


class _Y_FakeRedis:
    def __init__(
        self,
        values: dict[str, str] | None = None,
        lists: dict[str, list[str]] | None = None,
    ) -> None:
        self.values: dict[str, str] = dict(values or {})
        # batch:<id>:detections is a LIST in production (RPUSH,
        # batch_aggregator.py:23) — analyze_batch reads it with lrange.
        self.lists: dict[str, list[str]] = {k: list(v) for k, v in (lists or {}).items()}
        self.sets: list[tuple[str, str, Any]] = []

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, expire: Any = "UNSET") -> None:
        self.values[key] = value
        self.sets.append((key, value, expire))

    async def lrange(self, key: str, start: int, stop: int) -> list[str]:
        items = self.lists.get(key, [])
        return items[start:] if stop == -1 else items[start : stop + 1]


class _Y_FakeClient:
    def __init__(self, script: list[Any]) -> None:
        self.script = list(script)
        self.calls: list[Any] = []
        self.closed = 0

    async def assess(self, request: Any) -> Any:
        self.calls.append(request)
        outcome = self.script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def prompt_text(self, request: Any) -> str:
        return f"PROMPT {request.context.camera_id}"

    async def close(self) -> None:
        self.closed += 1


class _Y_FakeBroadcaster:
    def __init__(self, raises: Exception | None = None) -> None:
        self.messages: list[dict[str, Any]] = []
        self.raises = raises

    async def broadcast_event(self, message: dict[str, Any]) -> int:
        if self.raises is not None:
            raise self.raises
        self.messages.append(message)
        return 1


def getter_spy(broadcaster: _Y_FakeBroadcaster) -> Spy:
    spy = Spy(result=broadcaster)

    async def fake_get_broadcaster(redis: Any) -> _Y_FakeBroadcaster:
        await spy(redis)
        return broadcaster

    return spy


class _Y_ZoneLike:
    def __init__(self, zone_id: str, name: str) -> None:
        self.id = zone_id
        self.name = name


class _Y_FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _Y_FakeResult:
        return self

    def all(self) -> list[Any]:
        return list(self._rows)

    def first(self) -> Any:
        return self._rows[0] if self._rows else None


def _pred(stmt: Any) -> tuple[str | None, Any, Any]:
    """(column-name, operator, value) of a single binary whereclause."""
    wc = getattr(stmt, "whereclause", None)
    left = getattr(wc, "left", None)
    right = getattr(wc, "right", None)
    if left is None or right is None:
        return (None, None, None)
    return (getattr(left, "name", None), wc.operator, getattr(right, "value", None))


def _from_tables(stmt: Any) -> list[str]:
    import re

    m = re.search(r"FROM ([A-Za-z_][\w, ]+)", str(stmt))
    if not m:
        return []
    return [t.strip() for t in m.group(1).split(",")]


def _projects(stmt: Any, cls: type) -> bool:
    """True iff the SELECT still PROJECTS the ORM entity (a column of it).

    Needed because ``select(None).where(E.id == x)`` keeps the FROM clause
    (measured: 'SELECT NULL AS anon_1 FROM events WHERE ...'), so table-name
    matching alone would MASK the select-entity mutants (m7/m46/m336) that
    a real DB answers as an all-NULL scalar row, never an ORM object.
    """
    # Measured: select(E).column_descriptions -> [{'name': 'E', 'type': E}]
    # and select(None) -> [{'name': '_no_label', 'type': NULL}].
    return any(desc.get("type") is cls for desc in getattr(stmt, "column_descriptions", ()))


class _Y_FakeSession:
    """Answers the analyzer's three SELECT shapes SEMANTICALLY: rows come
    back only when the compiled statement keeps its shape (FROM table
    present, predicate operator/value intact). ``.where(None)`` (a silent
    WHERE NULL) or a flipped ``!=`` therefore returns [] exactly as the
    real DB would, and select(None) loses the FROM clause entirely."""

    def __init__(
        self,
        detections: list[Any] | None = None,
        existing_event: Any = None,
    ) -> None:
        self.detections = list(detections or [])
        self.existing_event = existing_event
        self.added: list[Any] = []
        self.flushes = 0
        self.executed: list[Any] = []
        self._next_id = 100

    async def __aenter__(self) -> _Y_FakeSession:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            self._next_id += 1
            obj.id = self._next_id

    async def flush(self) -> None:
        self.flushes += 1
        # faithful server default: event_verifications.created_at = utc_now()
        for obj in self.added:
            if isinstance(obj, EventVerification) and getattr(obj, "created_at", None) is None:
                obj.created_at = TS1

    async def execute(self, stmt: Any) -> _Y_FakeResult:
        self.executed.append(stmt)
        return _Y_FakeResult(self._rows_for(stmt))

    def _rows_for(self, stmt: Any) -> list[Any]:
        """One decision point: the rows a real DB would answer."""
        if "INSERT" in str(stmt):
            return []
        for cls, reader in (
            (EventVerification, self._verification_rows),
            (Event, self._existing_event_rows),
            (Detection, self._detection_rows),
        ):
            if _projects(stmt, cls):
                return reader(stmt)
        return []

    def _verification_rows(self, stmt: Any) -> list[Any]:
        col, op, _ = _pred(stmt)
        if op is operator.eq and col == "event_id":
            return [o for o in self.added if isinstance(o, EventVerification)]
        return []  # where(None)/!=/select(None): a real DB has none

    def _existing_event_rows(self, stmt: Any) -> list[Any]:
        col, op, _ = _pred(stmt)
        if op is operator.eq and col == "id" and self.existing_event is not None:
            return [self.existing_event]
        return []

    def _detection_rows(self, stmt: Any) -> list[Any]:
        # session-1 read is `Detection.id.in_(int_ids)`; a WHERE NULL, a
        # flipped operator, or select(None) all answer 0 rows.
        col, op, _ = _pred(stmt)
        want = _in_values(stmt)
        if col == "id" and op is not None and want is not None:
            return [d for d in self.detections if d.id in want]
        return []


def _in_values(stmt: Any) -> list[Any] | None:
    """The id-list of a `Detection.id.in_([...])` statement, else None."""
    wc = getattr(stmt, "whereclause", None)
    op = getattr(wc, "operator", None)
    if op is None or op.__name__ not in ("in_op",):
        return None
    try:
        params = stmt.compile().params
    except Exception:  # pragma: no cover
        return None
    for value in params.values():
        if isinstance(value, (list, tuple, set, frozenset)):
            return list(value)
    return None


def det_row(
    det_id: int,
    *,
    camera_id: str | None = "rcam",
    object_type: str | None = "person",
    confidence: float | None = 0.7,
    detected_at: datetime | None = TS1,
    file_path: str | None = None,
    thumbnail_path: str | None = "/thumbs/one.png",
    track_id: int | None = None,
    bbox: tuple[int, int, int, int] | None = None,
    video: tuple[int, int] | None = (100, 100),
) -> Any:
    full: dict[str, Any] = {
        "id": det_id,
        "camera_id": camera_id,
        "object_type": object_type,
        "confidence": confidence,
        "detected_at": detected_at,
        "file_path": file_path or f"/media/frames/det_{det_id}.jpg",
        "thumbnail_path": thumbnail_path,
        "track_id": track_id,
        "bbox_x": None,
        "bbox_y": None,
        "bbox_width": None,
        "bbox_height": None,
        "video_width": None,
        "video_height": None,
    }
    if bbox is not None:
        full.update(zip(("bbox_x", "bbox_y", "bbox_width", "bbox_height"), bbox, strict=True))
    if bbox is not None and video is not None:
        full["video_width"], full["video_height"] = video
    return SimpleNamespaceOf(full)


def SimpleNamespaceOf(mapping: dict[str, Any]) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(**mapping)


def _Y_make_verdict(
    *,
    verdict: str = "confirmed",
    risk_score: int = 85,
    summary: str = "A person stands at the door.",
    reasoning: str = "Criterion evidence reviewed.",
    description: str = "Front door, one person.",
) -> VlmVerdict:
    return VlmVerdict(
        verdict=verdict,
        risk_score=risk_score,
        summary=summary,
        reasoning=reasoning,
        description=description,
        criteria=[{"name": "person_present", "passed": True, "evidence": "full frame"}],
        provenance={"engine": "llama.cpp", "model_id": "Qwen3VL-8B"},
    )


class FakeTime:
    """va.time is the whole `time` MODULE the analyzer calls
    time.monotonic() twice per analyze (start, end); pop the script."""

    def __init__(self, values: list[float]) -> None:
        self._values = list(values)

    def monotonic(self) -> float:
        return self._values.pop(0)


@contextmanager
def analyzer_env(
    *,
    client: _Y_FakeClient | None = None,
    redis: _Y_FakeRedis | None = None,
    detections: list[Any] | None = None,
    existing_event: Any = None,
    replay: bool = False,
    zones: list[_Y_ZoneLike] | None = None,
    household: dict[str, Any] | None = None,
    collect: Spy | Exception | None = None,
    metrics: Spy | None = None,
    broadcaster: _Y_FakeBroadcaster | None = None,
    fake_time: FakeTime | None = None,
    severity: SeverityService | None = None,
):
    """Patches EVERY seam the analyzer touches and yields a namespace of
    the fakes so tests can assert calls. All patches undo in finally."""
    session = _Y_FakeSession(
        detections=detections if detections is not None else [det_row(11)],
        existing_event=existing_event,
    )
    if broadcaster is None:
        broadcaster = _Y_FakeBroadcaster()
    gb = getter_spy(broadcaster)
    if collect is None:
        collect_spy = Spy(result={"faces": "f", "plates": "p", "person_reid": "r"})
    elif isinstance(collect, Exception):
        collect_spy = Spy(raises=collect)
    else:
        collect_spy = collect
    if zones is None:
        zones_spy = Spy(result=[])
    elif isinstance(zones, Spy):
        zones_spy = zones
    else:
        zones_spy = Spy(result=zones)
    if household is None:
        hh_spy = Spy(result={})
    else:
        hh_spy = Spy(result=household)
    if metrics is None:
        metrics_spy = SyncSpy()
    else:
        metrics_spy = metrics
    analyzer = va.VlmAnalyzer(
        vlm_client=client or _Y_FakeClient([_Y_make_verdict()]),
        redis_client=redis if redis is not None else _Y_FakeRedis(),
        severity=severity,
        replay=replay,
    )
    with ExitStack() as stack:
        stack.enter_context(patched(va, "get_session", lambda: session))
        stack.enter_context(patch("backend.services.event_broadcaster.get_broadcaster", gb))
        stack.enter_context(patched(va, "get_zones_for_detection", zones_spy))
        stack.enter_context(patched(va, "load_household_context", hh_spy))
        stack.enter_context(patched(va, "collect_specialist_outputs", collect_spy))
        stack.enter_context(patched(va, "record_pipeline_error", metrics_spy))
        if fake_time is not None:
            stack.enter_context(patched(va, "time", fake_time))
        yield SimpleNamespaceOf(
            {
                "analyzer": analyzer,
                "session": session,
                "broadcaster": broadcaster,
                "getter": gb,
                "zones": zones_spy,
                "hh": hh_spy,
                "collect": collect_spy,
                "metrics": metrics_spy,
            }
        )


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# build_assess_context — the ONE code path, field by field
# ---------------------------------------------------------------------------


def test_build_assess_context_projects_every_row_field_exactly() -> None:
    # Values differ from EVERY fallback (`or`-defaults and the None-branch
    # defaults) so a renamed lookup key cannot hide behind a fallback.
    ctx = va.build_assess_context(
        camera_id="acat",
        detections=[
            {
                "id": 11,
                "object_type": "person",
                "confidence": 0.7,
                "detected_at": TS1,
                "bbox_x": 1,
                "bbox_y": 2,
                "bbox_width": 3,
                "bbox_height": 4,
            },
            {
                "id": 12,
                "object_type": "dog",
                "confidence": 0.4,
                "detected_at": TS2.isoformat(),
                "bbox": [9, 9, 9, 9],
            },
        ],
        zones=["yard", "drive"],
        household={"z9": {"owner_id": 3}},
        zone_crossing=True,
        specialist_outputs={"faces": "F"},
    )
    assert ctx.camera_id == "acat"
    assert ctx.zones == ["yard", "drive"]
    assert ctx.household == {"z9": {"owner_id": 3}}
    assert ctx.zone_crossing is True
    assert ctx.specialist_outputs == {"faces": "F"}
    assert ctx.detections == [
        {
            "id": 11,
            "object_type": "person",
            "confidence": 0.7,
            "bbox": [1, 2, 3, 4],
            "detected_at": TS1.isoformat(),
        },
        {
            "id": 12,
            "object_type": "dog",
            "confidence": 0.4,
            "bbox": [9, 9, 9, 9],
            "detected_at": TS2.isoformat(),
        },
    ]
    # earliest capture time wins (rows are given late-then-early)
    assert ctx.timestamp == TS1.isoformat()


def test_build_assess_context_assembles_bbox_from_parts() -> None:
    ctx = va.build_assess_context(
        camera_id="acat",
        detections=[{"id": 11, "bbox_x": 5, "bbox_y": 6, "bbox_width": 7, "bbox_height": 8}],
    )
    assert ctx.detections[0]["bbox"] == [5, 6, 7, 8]


def test_build_assess_context_empty_batch_gets_utc_now_timestamp() -> None:
    ctx = va.build_assess_context(camera_id="acat", detections=[])
    # `if times else datetime.now(UTC)`: an `or True` mutant min()s an empty
    # list (ValueError); a `now(None)` mutant loses the tzinfo.
    stamp = datetime.fromisoformat(ctx.timestamp)
    assert stamp.tzinfo is not None, ctx.timestamp


def test_build_assess_context_carries_zone_crossing_kwarg() -> None:
    ctx = va.build_assess_context(
        camera_id="c", detections=[], zones=["z"], household={}, zone_crossing=True
    )
    assert ctx.zone_crossing is True


def test_build_assess_context_defaults_are_untouched_when_absent() -> None:
    ctx = va.build_assess_context(camera_id="c", detections=[])
    assert ctx.zones == []
    assert ctx.household == {}
    assert ctx.zone_crossing is False
    assert ctx.specialist_outputs == {}


# ---------------------------------------------------------------------------
# detect_zone_crossing
# ---------------------------------------------------------------------------


def test_zone_crossing_true_only_on_membership_change() -> None:
    rows = [
        {"id": 1, "track_id": None},  # trackless row: skipped, never guessed
        {"id": 2, "track_id": 7},
        {"id": 3, "track_id": 7},
    ]
    assert va.detect_zone_crossing(rows, {2: ["porch"], 3: ["drive"]}) is True
    assert va.detect_zone_crossing(rows, {2: ["porch"], 3: ["porch"]}) is False


def test_zone_crossing_no_track_ids_stays_false_past_first_row() -> None:
    # `continue`->`break` (m7) would abandon the batch at the first
    # trackless row and answer False even though rows 2-3 cross zones.
    rows = [
        {"id": 1, "track_id": None},
        {"id": 2, "track_id": 7},
        {"id": 3, "track_id": 7},
    ]
    assert va.detect_zone_crossing(rows, {2: ["porch"], 3: ["drive"]}) is True


def test_zone_crossing_distinct_tracks_do_not_merge_under_one_key() -> None:
    # m14 (`setdefault(None, ...)` collides every track under key None)
    # would see one membership of {"porch","drive"} and answer True here.
    rows = [{"id": 2, "track_id": 7}, {"id": 3, "track_id": 8}]
    assert va.detect_zone_crossing(rows, {2: ["porch"], 3: ["drive"]}) is False


# ---------------------------------------------------------------------------
# build_frame_refs
# ---------------------------------------------------------------------------


def test_build_frame_refs_happy_row_field_by_field() -> None:
    from backend.services.key_frame_selector import FrameRef

    (frame,) = va.build_frame_refs(
        [
            {
                "id": 11,
                "camera_id": "rcam",
                "object_type": "person",
                "confidence": 0.7,
                "detected_at": TS1,
                "file_path": "/media/frames/one.jpg",
                "thumbnail_path": "/thumbs/one.png",
            }
        ],
        "acat",
    )
    assert frame == FrameRef(
        detection_id=11,
        camera_id="rcam",
        object_type="person",
        confidence=0.7,
        timestamp=int(TS1.timestamp()),
        file_path="/media/frames/one.jpg",
        thumbnail_path="/thumbs/one.png",
    )


def test_build_frame_refs_fallbacks_only_for_absent_values() -> None:
    from backend.services.key_frame_selector import FrameRef

    (frame,) = va.build_frame_refs(
        [
            {
                "id": 12,
                "camera_id": None,
                "object_type": None,
                "confidence": None,
                "detected_at": None,
                "file_path": "/media/frames/two.jpg",
                "thumbnail_path": None,
            }
        ],
        "acat",
    )
    # m8 (`isinstance(...) or True`) crashes on the non-datetime row;
    # m10 (`else 0` -> `else 1`) and m7 (`and False`) shift the epoch.
    assert frame == FrameRef(
        detection_id=12,
        camera_id="acat",
        object_type="unknown",
        confidence=None,
        timestamp=0,
        file_path="/media/frames/two.jpg",
        thumbnail_path=None,
    )


# ---------------------------------------------------------------------------
# build_assess_request / key_frame_ids (the camera_id fallback is load-bearing)
# ---------------------------------------------------------------------------


def _fallback_pair_rows() -> list[dict[str, Any]]:
    # r1 has NO row camera (the caller's camera_id is its only camera), r3
    # names the SAME camera explicitly. With the fallback intact they are
    # one (camera, class) pair -> ONE representative; with
    # `build_frame_refs(detections, None)` the pair splits (None vs acat)
    # and both rows claim a frame slot.
    return [
        {
            "id": 1,
            "camera_id": None,
            "object_type": "person",
            "confidence": 0.9,
            "detected_at": TS1,
            "file_path": "/media/frames/a.jpg",
            "thumbnail_path": None,
        },
        {
            "id": 3,
            "camera_id": "acat",
            "object_type": "person",
            "confidence": 0.95,
            "detected_at": TS1,
            "file_path": "/media/frames/b.jpg",
            "thumbnail_path": None,
        },
    ]


def test_build_assess_request_pairs_follow_the_camera_fallback() -> None:
    rows = _fallback_pair_rows()
    ctx = va.build_assess_context(camera_id="acat", detections=[])
    req = va.build_assess_request(context=ctx, detections=rows)
    assert req.image_paths == ["/media/frames/b.jpg"]
    assert req.frame_detection_ids == [[3]]


def test_key_frame_ids_are_the_representatives_under_the_fallback() -> None:
    rows = _fallback_pair_rows()
    ctx = va.build_assess_context(camera_id="acat", detections=[])
    req = va.build_assess_request(context=ctx, detections=rows)
    assert va.key_frame_ids(req, detections=rows) == [3]


# ---------------------------------------------------------------------------
# apply_verdict_invariants
# ---------------------------------------------------------------------------


def test_invariants_null_verdict_row_is_exact() -> None:
    out = va.apply_verdict_invariants(None, SEV)
    assert out == {
        "verdict": "verification_failed",
        "risk_score": None,
        "risk_level": None,
        "summary": "VLM verification failed; this event needs review.",
        "reasoning": (
            "The VLM could not produce a valid verdict within the §6 "
            "budget (transport or schema failure after one retry at "
            "temperature 0). Score and level are NULL by design - never "
            "a fabricated low score."
        ),
        "description": "",
        "criteria": None,
    }


def test_invariants_rejected_clamp_boundary_is_low_max_plus_one() -> None:
    # m32 (`>` -> `>=`) clamps AT low_max: the exact 29 row distinguishes.
    at = va.apply_verdict_invariants(_Y_make_verdict(verdict="rejected", risk_score=29), SEV)
    assert at["risk_score"] == 29
    assert "clamped" not in at["reasoning"]
    above = va.apply_verdict_invariants(_Y_make_verdict(verdict="rejected", risk_score=30), SEV)
    assert above["risk_score"] == 29
    assert above["reasoning"].endswith("[§6: verdict 'rejected' clamped to <= 29 (was 30)]")
    below = va.apply_verdict_invariants(_Y_make_verdict(verdict="rejected", risk_score=5), SEV)
    assert below["risk_score"] == 5
    assert below["risk_level"] == "low"


def test_invariants_pass_through_is_field_exact() -> None:
    v = _Y_make_verdict(verdict="uncertain", risk_score=45)
    out = va.apply_verdict_invariants(v, SEV)
    assert out == {
        "verdict": "uncertain",
        "risk_score": 45,
        "risk_level": "medium",
        "summary": v.summary,
        "reasoning": v.reasoning,
        "description": v.description,
        "criteria": [{"name": "person_present", "passed": True, "evidence": "full frame"}],
    }


# ---------------------------------------------------------------------------
# load_household_context (direct; the fake answers only shape-intact SQL)
# ---------------------------------------------------------------------------


class HouseholdFakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class HouseholdFakeSession:
    """Answers load_household_context's join the way a DB would: rows ONLY
    when the SELECT still projects zones, joins `zones.id = zh.zone_id`
    (text) and keeps a well-shaped equality on zones.camera_id.
    ``str(stmt)`` raises for the malformed-join mutants (m5/m7) exactly at
    execute time, so they land in the function's own except."""

    def __init__(self, rows: list[Any], camera_id: str) -> None:
        self.rows = rows
        self.camera_id = camera_id
        self.executed: list[Any] = []

    async def execute(self, stmt: Any) -> HouseholdFakeResult:
        self.executed.append(stmt)
        # m5/m7 render BYTE-IDENTICAL SQL to the original (probed: the
        # zone FK makes the explicit ON clause redundant), so NO observation
        # here can see them - they are registered EQUIVs. Every OTHER
        # shape break below answers the empty result a real DB would.
        return HouseholdFakeResult(self.rows if self._shape_ok(stmt) else [])

    def _shape_ok(self, stmt: Any) -> bool:
        import re as _re

        from backend.models.zone import Zone

        sql = str(stmt)  # an unrenderable statement raises into the except
        # the Zone ENTITY must be projected (m9 NULL-column / m11 dropped),
        # the INNER join must survive with its equality ON clause (m1/m2 no
        # statement; m12 flips it), and the WHERE keeps an equality on
        # camera_id bound to the right value (m3/m13).
        if not any(d.get("type") is Zone for d in getattr(stmt, "column_descriptions", ())):
            return False
        if "JOIN camera_zones ON" not in sql:  # m1/m2 (no statement at all)
            return False
        if _re.search(r"JOIN camera_zones ON camera_zones\.id (?:!=|<>)", sql):  # m12
            return False
        wc = getattr(stmt, "whereclause", None)
        left = getattr(wc, "left", None)
        right = getattr(wc, "right", None)
        if left is None or getattr(left, "name", None) != "camera_id":  # m3
            return False
        if wc.operator is not operator.eq:  # m13
            return False
        return getattr(right, "value", None) == self.camera_id


def _hh_row(zone_id: str, name: str, owner_id: int, members: list[int], vehicles: list[int]):
    from types import SimpleNamespace

    zone = SimpleNamespace(id=zone_id, name=name)
    config = SimpleNamespace(
        owner_id=owner_id, allowed_member_ids=members, allowed_vehicle_ids=vehicles
    )
    return (config, zone)


def test_load_household_context_builds_exact_keyed_dict() -> None:
    session = HouseholdFakeSession(
        [_hh_row("z1", "Porch", 3, [1, 2], []), _hh_row("z2", "Drive", 4, [], [9])],
        "cam7",
    )
    out = run(va.load_household_context(session, "cam7"))
    assert out == {
        "z1": {
            "zone": "Porch",
            "owner_id": 3,
            "allowed_member_ids": [1, 2],
            "allowed_vehicle_ids": [],
        },
        "z2": {
            "zone": "Drive",
            "owner_id": 4,
            "allowed_member_ids": [],
            "allowed_vehicle_ids": [9],
        },
    }
    assert len(session.executed) == 1


class ExplodingSession:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, stmt: Any) -> Any:
        self.calls += 1
        raise RuntimeError("connection reset")


def test_load_household_context_except_arm_is_exact() -> None:
    # The defensive arm must return honest-absent {} AND carry both extras
    # (camera_id, error) on the warning — never raise, never a partial dict.
    with logcap() as cap:
        out = run(va.load_household_context(ExplodingSession(), "cam7"))
    assert out == {}
    rec = cap.one("household context unavailable (assessing without it)")
    assert rec.camera_id == "cam7"
    assert rec.error == "connection reset"


# ---------------------------------------------------------------------------
# analyze_batch — the happy path (session-1 projection + session-2 write +
# idempotency + broadcast + the analyzed log line) driven against fakes.
# ---------------------------------------------------------------------------


def test_analyze_batch_happy_writes_exact_event_row_and_broadcasts() -> None:
    client = _Y_FakeClient([_Y_make_verdict(risk_score=85)])
    # distinct (camera, class) pairs -> the selector keeps BOTH stills
    # (one pick per pair); 0.7 > 0.6 fixes the pick ORDER.
    rows = [
        det_row(11, detected_at=TS1),
        det_row(12, object_type="dog", confidence=0.6, detected_at=TS2),
    ]
    with analyzer_env(client=client, detections=rows, fake_time=FakeTime([100.0, 102.0])) as env:
        with logcap() as cap:
            event = run(env.analyzer.analyze_batch("b1", camera_id="cam1", detection_ids=[11, 12]))
    # session-1 projection dicts read straight back through the captured
    # request context (row.get renames surface as None / fallback).
    ctx = client.calls[0].context
    assert ctx.camera_id == "cam1"
    assert [d["object_type"] for d in ctx.detections] == ["person", "dog"]
    assert [d["confidence"] for d in ctx.detections] == [0.7, 0.6]
    assert ctx.timestamp == TS1.isoformat()
    # the Event row keeps ARRIVAL times (min/max of detected_at).
    assert event.started_at == TS1
    assert event.ended_at == TS2
    assert event.risk_score == 85
    assert event.risk_level == "critical"
    assert event.reviewed is False
    # exactly Event then EventVerification.
    assert [type(o).__name__ for o in env.session.added] == ["Event", "EventVerification"]
    evrow = env.session.added[1]
    assert evrow.event_id == event.id
    assert evrow.verdict == "confirmed"
    assert evrow.scene_description == "Front door, one person."
    assert evrow.key_frame_detection_ids == [11, 12]
    assert evrow.engine == "llama.cpp"
    assert evrow.model_id == "Qwen3VL-8B"
    assert evrow.latency_ms == 2000  # FakeTime delta 2.0s -> int(2.0*1000)
    # idempotency set AFTER the write (nemotron's batch_event key).
    assert env.analyzer._redis.sets == [("batch_event:b1", str(event.id), 3600)]
    # broadcast rode exactly once with the P0.4 verification key (json-mode:
    # created_at is an ISO STRING, not a datetime).
    assert len(env.broadcaster.messages) == 1
    data = env.broadcaster.messages[0]["data"]
    assert data["verification"]["verdict"] == "confirmed"
    assert isinstance(data["verification"]["created_at"], str)
    WebSocketEventData.model_validate(dict(data))
    # the analyzed log line + its FULL extra surface.
    rec = cap.one("vlm batch analyzed")
    assert rec.batch_id == "b1"
    assert rec.camera_id == "cam1"
    assert rec.event_id == event.id
    assert rec.verdict == "confirmed"
    assert rec.degraded is False


def test_analyze_batch_all_row_times_none_falls_back_to_aware_now() -> None:
    # start/end default to now(UTC) / start_time: m174/m186 default=None
    # lands None on the Event; m176/m188 (default DELETED) crashes min/max
    # with "empty sequence"; m183 now(None) answers a NAIVE timestamp.
    rows = [det_row(11, detected_at=None), det_row(12, detected_at=None)]
    with analyzer_env(detections=rows) as env:
        with logcap():
            event = run(env.analyzer.analyze_batch("b1", camera_id="cam1", detection_ids=[11, 12]))
    assert event.started_at is not None
    assert event.started_at.tzinfo is not None, event.started_at
    assert event.ended_at == event.started_at


def test_analyze_batch_junction_insert_targets_the_pair_index() -> None:
    with analyzer_env() as env:
        run(env.analyzer.analyze_batch("b1", camera_id="cam1", detection_ids=[11]))
    junctions = [str(s) for s in env.session.executed if "INSERT INTO event_detections" in str(s)]
    assert len(junctions) == 1
    assert "ON CONFLICT (event_id, detection_id) DO NOTHING" in junctions[0]


def test_analyze_batch_refuses_without_any_camera() -> None:
    # no camera_id, redis carries no batch:<id>:camera_id -> loud refusal.
    with analyzer_env(redis=_Y_FakeRedis()) as env:
        with logcap():
            try:
                run(env.analyzer.analyze_batch("ghost"))
            except ValueError as exc:
                assert "never originates" in str(exc)
                assert "ghost" in str(exc)
            else:
                raise AssertionError("expected ValueError for a camera-less batch")


def test_analyze_batch_refuses_without_detections() -> None:
    # camera present, detection_ids None, redis has no detections -> m35's
    # `or True` would json.loads(None) and raise TypeError instead.
    with analyzer_env(redis=_Y_FakeRedis(), detections=[det_row(11)]) as env:
        with logcap():
            try:
                run(env.analyzer.analyze_batch("b1", camera_id="cam1", detection_ids=None))
            except ValueError as exc:
                assert "has no detections" in str(exc)
            else:
                raise AssertionError("expected ValueError for a detection-less batch")


def test_analyze_batch_refuses_when_no_rows_match_ids() -> None:
    # session-1 SELECT returns nothing (empty fixtures) -> 'No detections
    # found for batch <id>' (m50's ValueError(None) loses the message).
    with analyzer_env(detections=[]) as env:
        with logcap():
            try:
                run(env.analyzer.analyze_batch("b7", camera_id="cam1", detection_ids=[11]))
            except ValueError as exc:
                assert "No detections found for batch b7" in str(exc)
            else:
                raise AssertionError("expected ValueError when no detection rows match")


def test_analyze_batch_idempotency_hit_returns_stored_event_and_logs() -> None:
    # redis holds batch_event:b1 -> the DB SELECT fetches the stored Event;
    # broken SELECT shapes (m6/m7/m8) fall through and re-analyze instead.
    stored = Event(id=77, batch_id="b1", camera_id="cam1", risk_score=85)
    redis = _Y_FakeRedis({"batch_event:b1": "77"})
    client = _Y_FakeClient([_Y_make_verdict()])
    with analyzer_env(
        client=client, redis=redis, existing_event=stored, detections=[det_row(11)]
    ) as env:
        with logcap() as cap:
            returned = run(env.analyzer.analyze_batch("b1", camera_id="cam1", detection_ids=[11]))
    assert returned is stored
    assert returned.id == 77
    rec = cap.one("vlm idempotency hit: batch already analyzed")
    assert rec.batch_id == "b1"
    assert rec.event_id == 77
    assert client.calls == []  # never re-assessed


def test_analyze_batch_degraded_path_is_exact() -> None:
    # transport failure -> §6 step 2: metrics fired with the right key, the
    # warning carries the full extra, the event is NULL-scored and the
    # verification row falls back to the SETTINGS provenance.
    client = _Y_FakeClient([VlmTransportError("boom")])
    with analyzer_env(client=client) as env:
        with logcap() as cap:
            event = run(env.analyzer.analyze_batch("b1", camera_id="cam1", detection_ids=[11]))
    assert env.metrics.count == 1
    assert env.metrics.calls[0][0] == ("vlm_verification_failed",)
    rec = cap.one("vlm assess failed - event records verification_failed")
    assert rec.batch_id == "b1"
    assert rec.camera_id == "cam1"
    assert rec.error == "boom"
    assert event.risk_score is None
    assert event.risk_level is None
    assert event.summary == "VLM verification failed; this event needs review."
    evrow = env.session.added[1]
    assert evrow.verdict == "verification_failed"
    assert evrow.scene_description is None  # outcome["description"] or None
    assert evrow.engine == va.get_settings().nemotron_verification_engine
    assert evrow.model_id == va.get_settings().vlm_model_id
    done = cap.one("vlm batch analyzed")
    assert done.degraded is True
    assert done.verdict == "verification_failed"


def test_analyze_batch_zone_geometry_call_is_arg_exact() -> None:
    # m92-m107 pin the get_zones_for_detection call: dropping any arg
    # (m100-m107) or None-ing it (m92-m99) changes the recorded call.
    rows = [det_row(11, bbox=(10, 20, 30, 40), video=(640, 480))]
    zones = [_Y_ZoneLike("z1", "Porch")]
    with analyzer_env(detections=rows, zones=zones) as env:
        with logcap():
            run(env.analyzer.analyze_batch("b1", camera_id="cam1", detection_ids=[11]))
    assert env.zones.count == 1
    args, kwargs = env.zones.calls[0]
    assert args == ("cam1", 10, 20, 30, 40, 640, 480, env.session)
    assert kwargs == {}
    assert env.session.added[1].verdict == "confirmed"


def test_analyze_batch_skips_trackless_rows_but_keeps_reading() -> None:
    # m90 (`continue`->`break`): the FIRST row lacks bbox geometry; `break`
    # would abandon the whole loop before the geometry-bearing second row.
    rows = [det_row(12), det_row(11, bbox=(10, 20, 30, 40), video=(640, 480))]
    with analyzer_env(detections=rows, zones=[_Y_ZoneLike("z1", "Porch")]) as env:
        with logcap():
            run(env.analyzer.analyze_batch("b1", camera_id="cam1", detection_ids=[11, 12]))
    assert env.zones.count == 1  # exactly ONE call (row 11), not zero


def test_analyze_batch_bbox_only_row_skips_geometry_without_crash() -> None:
    # m81 (`or` -> `and`): a row with bbox but NO video_width must still be
    # skipped (bbox_x is not None AND video_width is None -> the mutant
    # calls geometry with None and the fake zone seam records it).
    rows = [det_row(11, bbox=(10, 20, 30, 40), video=None)]
    with analyzer_env(detections=rows) as env:
        with logcap():
            run(env.analyzer.analyze_batch("b1", camera_id="cam1", detection_ids=[11]))
    assert env.zones.count == 0


def test_analyze_batch_track_crossing_zones_reaches_the_context() -> None:
    # One track seen in TWO zone memberships -> zone_crossing True on the
    # assess context (m207 deletes the kwarg -> False; a renamed "track_id"
    # projection key m66/m67 -> no memberships -> False).
    client = _Y_FakeClient([_Y_make_verdict()])
    rows = [
        det_row(11, bbox=(10, 20, 30, 40), video=(640, 480), track_id=7),
        det_row(12, bbox=(10, 20, 30, 40), video=(640, 480), track_id=7),
    ]
    zones_spy = Spy(
        result=[_Y_ZoneLike("z1", "Porch")],
        results={1: [_Y_ZoneLike("z2", "Drive")]},  # second geometry call differs
    )
    with analyzer_env(client=client, detections=rows, zones=zones_spy) as env:
        with logcap():
            run(env.analyzer.analyze_batch("b1", camera_id="cam1", detection_ids=[11, 12]))
    assert client.calls[0].context.zone_crossing is True
    assert client.calls[0].context.zones == ["Drive", "Porch"]


def test_analyze_batch_household_seam_called_with_session_and_camera() -> None:
    with analyzer_env() as env:
        with logcap():
            run(env.analyzer.analyze_batch("b1", camera_id="cam1", detection_ids=[11]))
    # the seam is called POSITIONALLY as (session, camera_id): m127/m128
    # (None-ing either argument) die on the identity/value assertions.
    hh_args, hh_kwargs = env.hh.calls[0]
    assert hh_args == (env.session, "cam1")
    assert hh_kwargs == {}
    assert env.hh.count == 1


def test_analyze_batch_specialist_call_is_kwarg_exact_prod() -> None:
    # rows carry NO camera_id so the build_frame_refs CALLER's camera
    # fallback is the only camera source - m145 (None passed there) lands
    # FrameRef(camera_id=None) into the collected key_frame_paths.
    rows = [
        det_row(11, camera_id=None),
        det_row(12, camera_id=None, object_type="dog", confidence=0.6),
    ]
    with analyzer_env(detections=rows) as env:
        with logcap():
            run(env.analyzer.analyze_batch("b1", camera_id="cam1", detection_ids=[11, 12]))
    assert env.collect.count == 1
    args, kwargs = env.collect.calls[0]
    assert args == ()
    assert set(kwargs) == {"key_frame_paths", "settings", "detections", "session"}
    assert kwargs["settings"] is env.analyzer._settings
    assert kwargs["session"] is env.session
    assert [d["id"] for d in kwargs["detections"]] == [11, 12]
    # FULL FrameRef equality: camera_id/thumbnail/detected_at renames in
    # the session-1 projection (m54/55/64/65) shift a field here because
    # the row.get fallback cannot match the fixture value (row camera is
    # "rcam", the analyze arg camera is "cam1").
    from backend.services.key_frame_selector import FrameRef

    assert kwargs["key_frame_paths"] == [
        FrameRef(
            detection_id=11,
            camera_id="cam1",
            object_type="person",
            confidence=0.7,
            timestamp=int(TS1.timestamp()),
            file_path="/media/frames/det_11.jpg",
            thumbnail_path="/thumbs/one.png",
        ),
        FrameRef(
            detection_id=12,
            camera_id="cam1",
            object_type="dog",
            confidence=0.6,
            timestamp=int(TS1.timestamp()),
            file_path="/media/frames/det_12.jpg",
            thumbnail_path="/thumbs/one.png",
        ),
    ]


def test_analyze_batch_projection_camera_survives_rename_attacks() -> None:
    # rows carry their OWN camera ("rcam") different from the analyze arg
    # ("cam1"): a renamed "camera_id" projection key (m54/m55) makes
    # build_frame_refs fall back to cam1 - caught by FULL FrameRef equality.
    client = _Y_FakeClient([_Y_make_verdict()])
    rows = [det_row(11), det_row(12, object_type="dog", confidence=0.6)]
    with analyzer_env(client=client, detections=rows) as env:
        with logcap():
            run(env.analyzer.analyze_batch("b1", camera_id="cam1", detection_ids=[11, 12]))
    from backend.services.key_frame_selector import FrameRef

    assert env.collect.calls[0][1]["key_frame_paths"] == [
        FrameRef(
            detection_id=11,
            camera_id="rcam",
            object_type="person",
            confidence=0.7,
            timestamp=int(TS1.timestamp()),
            file_path="/media/frames/det_11.jpg",
            thumbnail_path="/thumbs/one.png",
        ),
        FrameRef(
            detection_id=12,
            camera_id="rcam",
            object_type="dog",
            confidence=0.6,
            timestamp=int(TS1.timestamp()),
            file_path="/media/frames/det_12.jpg",
            thumbnail_path="/thumbs/one.png",
        ),
    ]
    # the session-1 projection carries EVERY column the builders read,
    # value-exact (renames m54-m67 of confidence/thumbnail/track/... keys
    # also break the zone-crossing and frame-timestamp paths).
    assert client.calls[0].context.detections[0]["detected_at"] == TS1.isoformat()


def test_analyze_batch_replay_skips_specialists_and_broadcast() -> None:
    rows = [det_row(11)]
    with analyzer_env(
        detections=rows,
        replay=True,
    ) as env:
        with logcap():
            run(
                env.analyzer.analyze_batch(
                    "b1", camera_id="cam1", detection_ids=[11], specialist_inputs={"faces": "F"}
                )
            )
    assert env.collect.count == 0
    assert env.broadcaster.messages == []


def test_analyze_batch_replay_feeds_specialist_inputs_into_the_context() -> None:
    rows = [det_row(11)]
    client = _Y_FakeClient([_Y_make_verdict()])
    with analyzer_env(client=client, detections=rows, replay=True) as env:
        with logcap():
            run(
                env.analyzer.analyze_batch(
                    "b1", camera_id="cam1", detection_ids=[11], specialist_inputs={"faces": "F"}
                )
            )
    assert client.calls[0].context.specialist_outputs == {"faces": "F"}


def test_analyze_batch_specialist_belt_catch_lands_all_unavailable() -> None:
    with analyzer_env(collect=RuntimeError("stage exploded")) as env:
        with logcap() as cap:
            run(env.analyzer.analyze_batch("b1", camera_id="cam1", detection_ids=[11]))
    rec = cap.one("specialist stage raised (belt catch) - all specialists unavailable")
    assert rec.batch_id == "b1"
    assert rec.error == "stage exploded"
    # the batch survived: event + row still written.
    assert [type(o).__name__ for o in env.session.added] == ["Event", "EventVerification"]


def test_analyze_batch_broadcast_failure_never_undoes_the_event() -> None:
    with analyzer_env(broadcaster=_Y_FakeBroadcaster(raises=RuntimeError("redis down"))) as env:
        with logcap() as cap:
            event = run(env.analyzer.analyze_batch("b1", camera_id="cam1", detection_ids=[11]))
    assert event.risk_score == 85
    rec = cap.one("vlm event broadcast failed (event stands committed)")
    assert rec.event_id == event.id
    assert rec.error == "redis down"


def test_analyzer_replay_default_is_false() -> None:
    # m1 flips the `replay: bool = False` DEFAULT to True; every test that
    # passes replay explicitly cannot see it - read the stored attribute.
    assert va.VlmAnalyzer()._replay is False
    assert va.VlmAnalyzer(replay=True)._replay is True


def test_broadcast_without_redis_client_skips_quietly() -> None:
    analyzer = va.VlmAnalyzer(vlm_client=_Y_FakeClient([]), redis_client=None)
    event = Event(id=5, batch_id="b", camera_id="c")
    with logcap() as cap:
        run(analyzer._broadcast(event, {"verdict": "confirmed"}))
    # ONLY the debug skip line, nothing else.
    assert cap.msgs() == ["vlm broadcast skipped: no redis client"]
    assert all(r.levelno == logging.DEBUG for r in cap.records)


def test_broadcast_message_is_key_exact() -> None:
    analyzer = va.VlmAnalyzer(vlm_client=_Y_FakeClient([]), redis_client=_Y_FakeRedis())
    broadcaster = _Y_FakeBroadcaster()
    spy = getter_spy(broadcaster)
    event = Event(
        id=5,
        batch_id="b",
        camera_id="c",
        risk_score=42,
        risk_level="medium",
        summary="s",
        reasoning="r",
        started_at=TS1,
    )
    with patch("backend.services.event_broadcaster.get_broadcaster", spy):
        with logcap() as cap:
            run(analyzer._broadcast(event, {"verdict": "confirmed"}))
    assert spy.calls[0][0] == (analyzer._redis,)  # the broadcaster gets THIS redis
    assert broadcaster.messages == [
        {
            "type": "event",
            "data": {
                "id": 5,
                "event_id": 5,
                "batch_id": "b",
                "camera_id": "c",
                "risk_score": 42,
                "risk_level": "medium",
                "summary": "s",
                "reasoning": "r",
                "started_at": TS1.isoformat(),
                "verification": {"verdict": "confirmed"},
            },
        }
    ]
    assert cap.records == []


def test_broadcast_started_at_none_when_event_time_missing() -> None:
    # m29 (`and False`) answers None even WITH a started_at -> message
    # equality above kills it; this guards the OTHER polarity stays None.
    analyzer = va.VlmAnalyzer(vlm_client=_Y_FakeClient([]), redis_client=_Y_FakeRedis())
    broadcaster = _Y_FakeBroadcaster()
    event = Event(id=5, batch_id="b", camera_id="c", started_at=None)
    with patch("backend.services.event_broadcaster.get_broadcaster", getter_spy(broadcaster)):
        with logcap():
            run(analyzer._broadcast(event, None))
    assert broadcaster.messages[0]["data"]["started_at"] is None
    assert broadcaster.messages[0]["data"]["verification"] is None


# ---------------------------------------------------------------------------
# analyze_batch_streaming — the SSE vocabulary, model_dump shape by shape
# ---------------------------------------------------------------------------


def test_streaming_scored_event_completes_exact() -> None:
    analyzer = va.VlmAnalyzer(
        vlm_client=_Y_FakeClient([_Y_make_verdict(risk_score=85)]),
        redis_client=_Y_FakeRedis(),
    )
    session = _Y_FakeSession(detections=[det_row(11)])
    broadcaster = _Y_FakeBroadcaster()
    with ExitStack() as stack:
        stack.enter_context(patched(va, "get_session", lambda: session))
        stack.enter_context(
            patch("backend.services.event_broadcaster.get_broadcaster", getter_spy(broadcaster))
        )
        stack.enter_context(patched(va, "get_zones_for_detection", Spy(result=[])))
        stack.enter_context(patched(va, "load_household_context", Spy(result={})))
        stack.enter_context(patched(va, "collect_specialist_outputs", Spy(result={"faces": "f"})))
        stack.enter_context(patched(va, "record_pipeline_error", SyncSpy()))
        with logcap() as cap:
            events = run(
                _collect_stream(
                    analyzer.analyze_batch_streaming("b1", camera_id="cam1", detection_ids=[11])
                )
            )
    # the analyzed INFO line rides out; NO streaming-failure line.
    assert cap.msgs() == ["vlm batch analyzed"]
    assert events == [
        {
            "event_type": "progress",
            "content": "",
            "accumulated_text": "",
            "progress_percent": 5.0,
        },
        {
            "event_type": "complete",
            "event_id": 101,
            "risk_score": 85,
            "risk_level": "critical",
            "summary": "A person stands at the door.",
            "reasoning": "Criterion evidence reviewed.",
        },
    ]


async def _collect_stream(agen: Any) -> list[dict[str, Any]]:
    return [e async for e in agen]


def test_streaming_null_scored_event_answers_error_exact() -> None:
    # degraded verdict -> NULL score/level -> the honest ERROR update
    # (m42/m46 `or`->`and` would emit the COMPLETE shape instead).
    analyzer = va.VlmAnalyzer(
        vlm_client=_Y_FakeClient([VlmTransportError("down")]),
        redis_client=_Y_FakeRedis(),
    )
    session = _Y_FakeSession(detections=[det_row(11)])
    with ExitStack() as stack:
        stack.enter_context(patched(va, "get_session", lambda: session))
        stack.enter_context(
            patch(
                "backend.services.event_broadcaster.get_broadcaster",
                getter_spy(_Y_FakeBroadcaster()),
            )
        )
        stack.enter_context(patched(va, "get_zones_for_detection", Spy(result=[])))
        stack.enter_context(patched(va, "load_household_context", Spy(result={})))
        stack.enter_context(patched(va, "collect_specialist_outputs", Spy(result={"faces": "f"})))
        stack.enter_context(patched(va, "record_pipeline_error", SyncSpy()))
        with logcap():
            events = run(
                _collect_stream(
                    analyzer.analyze_batch_streaming("b1", camera_id="cam1", detection_ids=[11])
                )
            )
    assert events[1] == {
        "event_type": "error",
        "error_code": "LLM_INVALID_RESPONSE",
        "error_message": "VLM verification failed; the event needs review.",
        "recoverable": True,
    }


def test_streaming_wraps_every_analysis_raise_as_internal_error() -> None:
    # analyze_batch refuses (no camera) -> INTERNAL_ERROR arm, EXACT shape;
    # the m11-m15 arg mutations change WHICH failure happens (ValueError vs
    # TypeError) but the ERROR arm must still name the same two fields.
    analyzer = va.VlmAnalyzer(
        vlm_client=_Y_FakeClient([_Y_make_verdict()]), redis_client=_Y_FakeRedis()
    )
    session = _Y_FakeSession(detections=[det_row(11)])
    with ExitStack() as stack:
        stack.enter_context(patched(va, "get_session", lambda: session))
        stack.enter_context(
            patch(
                "backend.services.event_broadcaster.get_broadcaster",
                getter_spy(_Y_FakeBroadcaster()),
            )
        )
        stack.enter_context(patched(va, "get_zones_for_detection", Spy(result=[])))
        stack.enter_context(patched(va, "load_household_context", Spy(result={})))
        stack.enter_context(patched(va, "collect_specialist_outputs", Spy(result={"faces": "f"})))
        stack.enter_context(patched(va, "record_pipeline_error", SyncSpy()))
        with logcap() as cap:
            events = run(_collect_stream(analyzer.analyze_batch_streaming("ghost")))
    assert events[0]["event_type"] == "progress"
    assert events[1] == {
        "event_type": "error",
        "error_code": "INTERNAL_ERROR",
        "error_message": "Streaming analysis failed",
        "recoverable": True,
    }
    rec = cap.one("vlm streaming analysis failed")
    assert rec.batch_id == "ghost"
    # m11 (batch_id arg -> None) would say "Batch None has no camera..."
    assert "Batch ghost has no camera metadata" in rec.error


def test_streaming_null_score_with_level_still_answers_error() -> None:
    # `risk_score is None or risk_level is None` -> `and` (m17) needs the
    # divergent pair the real pipeline never builds - stub analyze_batch to
    # hand streaming exactly that. The ORIGINAL still answers the ERROR
    # update; the mutant falls into the COMPLETE arm, whose schema
    # (risk_score: int REQUIRED) rejects the NULL and the generator raises.
    class _Divergent(va.VlmAnalyzer):
        async def analyze_batch(self, *args: Any, **kwargs: Any) -> Event:
            return Event(id=9, batch_id="b", camera_id="c", risk_score=None, risk_level="low")

    analyzer = _Divergent(vlm_client=_Y_FakeClient([]), redis_client=_Y_FakeRedis())
    with logcap():
        events = run(_collect_stream(analyzer.analyze_batch_streaming("b1")))
    assert events[1]["event_type"] == "error"
    assert events[1]["error_code"] == "LLM_INVALID_RESPONSE"


def test_streaming_level_none_with_score_still_answers_error() -> None:
    # the mirrored polarity (score present, level NULL) - same argument.
    class _Divergent2(va.VlmAnalyzer):
        async def analyze_batch(self, *args: Any, **kwargs: Any) -> Event:
            return Event(id=9, batch_id="b", camera_id="c", risk_score=10, risk_level=None)

    analyzer = _Divergent2(vlm_client=_Y_FakeClient([]), redis_client=_Y_FakeRedis())
    with logcap():
        events = run(_collect_stream(analyzer.analyze_batch_streaming("b1")))
    assert events[1]["event_type"] == "error"
    assert events[1]["error_code"] == "LLM_INVALID_RESPONSE"


def test_streaming_empty_summary_and_reasoning_use_placeholders() -> None:
    # The degraded Event carries summary/reasoning; a SCORED event's
    # summary/reasoning come from the verdict. For the placeholder polarity
    # (`or "No summary"`) we drive a verdict-shaped event whose summary is
    # the empty string, by stubbing analyze_batch's return directly.
    class _Analyzer(va.VlmAnalyzer):
        async def analyze_batch(self, *args: Any, **kwargs: Any) -> Event:
            return Event(id=9, batch_id="b", camera_id="c", risk_score=10, risk_level="low")

    analyzer = _Analyzer(vlm_client=_Y_FakeClient([]), redis_client=_Y_FakeRedis())
    with logcap() as cap:
        events = run(_collect_stream(analyzer.analyze_batch_streaming("b1")))
    assert cap.records == []
    # Event(summary=None) -> `summary or "No summary"` placeholder.
    assert events[1]["summary"] == "No summary"
    assert events[1]["reasoning"] == "No reasoning"
    assert events[1]["event_id"] == 9
    assert events[1]["risk_score"] == 10
    assert events[1]["risk_level"] == "low"


# --- Consolidated from test_vlm_analyzer_batch38_ay.py ---


TS = datetime(2026, 10, 6, 12, 30, 45, 123456, tzinfo=UTC)

SHIPPED_SQL = (
    "INSERT INTO event_notify_decisions (event_id, notify, decided_by, created_at) "
    "VALUES (4242, true, 'vlm', NULL) "
    "ON CONFLICT (event_id) DO UPDATE SET notify = true, "
    "created_at = '2026-10-06 12:30:45.123456+00:00' "
    "RETURNING event_notify_decisions.id"
)


class RecordingSession:
    """Captures every executed statement; identity-pinned via `tag`."""

    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> Any:
        self.statements.append(stmt)
        return sqlalchemy.engine.Row


def compile_sql(stmt: Any) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


class _Patcher:
    """Minimal attribute save/restore (no monkeypatch in the b30 harness)."""

    def __init__(self, *triples: tuple[Any, str, Any]) -> None:
        self.triples = triples
        self.saved: list[tuple[Any, str, Any]] = []

    def __enter__(self) -> None:
        for obj, attr, value in self.triples:
            self.saved.append((obj, attr, getattr(obj, attr)))
            setattr(obj, attr, value)

    def __exit__(self, *exc: Any) -> bool:
        for obj, attr, value in reversed(self.saved):
            setattr(obj, attr, value)
        return False


def _patch_utc_now() -> _Patcher:
    return _Patcher((va, "utc_now", lambda: TS))


# ---------------------------------------------------------------------------
# _persist_notify_decision: the statement IS the product. Pinned literally.
# ---------------------------------------------------------------------------


def test_persist_notify_decision_compiles_to_the_shipped_upsert() -> None:
    """The whole body's observable output: one INSERT..ON CONFLICT DO UPDATE
    whose conflict target, SET columns and literal timestamp are all pinned.
    Kills the renamed-index (m15/m16), renamed-set (m17/m18), renamed-set-key
    (m19/m20) and dropped-statement arms, and any re-order of the columns."""
    rec = RecordingSession()
    with _patch_utc_now():
        asyncio.run(va.VlmAnalyzer._persist_notify_decision(rec, 4242, True))
    assert len(rec.statements) == 1, f"expected exactly one statement, got {len(rec.statements)}"
    assert compile_sql(rec.statements[0]) == SHIPPED_SQL


def test_persist_notify_decision_carries_its_arguments_verbatim() -> None:
    """event_id and notify reach the VALUES list; decided_by is the LITERAL
    'vlm' (never the caller's value), and the SET side re-applies notify."""
    for event_id, notify in ((7, False), (99991, True)):
        rec = RecordingSession()
        with _patch_utc_now():
            asyncio.run(va.VlmAnalyzer._persist_notify_decision(rec, event_id, notify))
        sql = compile_sql(rec.statements[0])
        assert f"VALUES ({event_id}, {'true' if notify else 'false'}, 'vlm', NULL)" in sql, sql
        assert f"DO UPDATE SET notify = {'true' if notify else 'false'}, " in sql, sql
        assert "'vlm'" in sql and "VALUES" in sql


def test_persist_notify_decision_indexes_the_conflict_on_event_id() -> None:
    """The UPSERT contract (docstring: "one-row-per-event by schema") lives in
    `index_elements=["event_id"]`. A renamed/case-flipped element renders a
    quoted, wrong identity column - the row would still insert but the
    RE-decide would fight the unique index. Assert the ON CONFLICT clause
    exactly, unquoted."""
    rec = RecordingSession()
    with _patch_utc_now():
        asyncio.run(va.VlmAnalyzer._persist_notify_decision(rec, 1, True))
    sql = compile_sql(rec.statements[0])
    on_conflict = sql.split("RETURNING")[0].split("ON CONFLICT")[1].split("DO UPDATE")[0]
    assert on_conflict.strip() == "(event_id)", on_conflict


def test_persist_notify_decision_updates_only_notify_and_created_at() -> None:
    """The SET list is exactly {notify, created_at}: decided_by is write-once
    (the first decision's attribution survives a re-decide) and event_id is
    the key. A renamed set key appears quoted; a dropped set_ entry shrinks
    the list. Assert the full clause text, not a substring."""
    rec = RecordingSession()
    with _patch_utc_now():
        asyncio.run(va.VlmAnalyzer._persist_notify_decision(rec, 1, True))
    sql = compile_sql(rec.statements[0])
    set_clause = sql.split("DO UPDATE SET ")[1].split(" RETURNING")[0]
    assert set_clause == (
        f"notify = true, created_at = '{TS.strftime('%Y-%m-%d %H:%M:%S.%f')}+00:00'"
    ), set_clause


def test_persist_notify_decision_stamp_comes_from_utc_now() -> None:
    """The created_at literal is the patched instant - so the SET clause is
    reproducible, and `utc_now()` (not a DB-side now(), not a constant) is
    proven to be the source. A mutant that drops the created_at entry entirely
    loses the whole tail of the clause."""
    rec = RecordingSession()
    with _patch_utc_now():
        asyncio.run(va.VlmAnalyzer._persist_notify_decision(rec, 5, False))
    sql = compile_sql(rec.statements[0])
    assert f"created_at = '{TS.strftime('%Y-%m-%d %H:%M:%S.%f')}+00:00'" in sql, sql
    assert "now()" not in sql.lower(), sql


def test_persist_notify_decision_rejects_a_broken_statement_shape() -> None:
    """Negative control for the deleted-argument arms: a UPSERT missing
    index_elements or set_ cannot even be BUILT (probed: ValueError from
    on_conflict_do_update, ArgumentError from pg_insert(None)). The shipped
    build must succeed, and each broken shape must raise - so an arm that
    quietly builds a DIFFERENT statement still dies on the positive pins, and
    an arm that builds nothing dies here."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from backend.models.event_notify import EventNotifyDecision

    base = pg_insert(EventNotifyDecision).values(event_id=1, notify=True, decided_by="vlm")
    broken = {
        "no index_elements": lambda: base.on_conflict_do_update(set_={"notify": True}),
        "no set_": lambda: base.on_conflict_do_update(index_elements=["event_id"]),
        "empty set_": lambda: base.on_conflict_do_update(index_elements=["event_id"], set_={}),
    }
    built_any: list[str] = []
    for label, build in broken.items():
        try:
            build()
        except (ValueError, sqlalchemy.exc.ArgumentError) as exc:
            assert str(exc), f"{label} raised an empty message"
        else:
            built_any.append(label)
    assert not built_any, f"broken UPSERT shapes that built anyway: {built_any}"
    rec = RecordingSession()
    with _patch_utc_now():
        asyncio.run(va.VlmAnalyzer._persist_notify_decision(rec, 1, True))
    assert compile_sql(rec.statements[0]).startswith("INSERT INTO event_notify_decisions")


# ---------------------------------------------------------------------------
# _notify_decision: the persist call's ARGUMENT TUPLES are pinned, and the
# initializer's world is observable through the fallback leg's call count.
# ---------------------------------------------------------------------------


class _FakeSessionCtx:
    """`async with get_session() as session` -> a stable, identity-checkable
    object. `boom=True` makes opening raise (the shipped fallback world)."""

    def __init__(self, session: Any, boom: bool = False) -> None:
        self.session = session
        self.boom = boom

    async def __aenter__(self) -> Any:
        if self.boom:
            raise RuntimeError("session could not be opened")
        return self.session

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class PersistSpy:
    """Records the EXACT call tuples of `_persist_notify_decision`."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def bind(self, analyzer: Any) -> None:
        analyzer._persist_notify_decision = self  # type: ignore[method-assign]

    async def __call__(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(args)


def _drive_notify(
    *,
    decide_results: list[Any],
    session: Any,
    boom: bool = False,
    analyzer: Any | None = None,
) -> tuple[Any, PersistSpy, int]:
    """Run `_notify_decision` once over a patched get_session + counting
    decide_notification. Returns (result, persist spy, decide call count)."""
    sent = analyzer or va.VlmAnalyzer.__new__(va.VlmAnalyzer)  # no __init__, no settings
    spy = PersistSpy()
    spy.bind(sent)
    counts = {"n": 0}

    async def decide(sess: Any, **kwargs: Any) -> Any:
        counts["n"] += 1
        outcome = decide_results[min(counts["n"] - 1, len(decide_results) - 1)]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    with _Patcher(
        (va, "decide_notification", decide),
        (va, "get_session", lambda: _FakeSessionCtx(session, boom=boom)),
    ):
        result = asyncio.run(
            sent._notify_decision(
                event_id=4242,
                camera_id="camera-kitchen",
                timestamp=TS,
                risk_score=50,
                verdict="confirmed",
                detections=[{"id": 1}],
            )
        )
    return result, spy, counts["n"]


def test_notify_decision_persists_the_decided_value_with_the_right_key() -> None:
    """Happy path: decide returns False (deliberately NOT None - the
    initializer's world must be distinguishable), and persist is called
    EXACTLY once with (the same session object, event_id 4242, False).
    Kills m17 (session->None: identity fails), m18 (event_id->None), m19
    (notify->None), m20 (session slot drops -> args shift to 2-tuple),
    m21/m22 (dropped args: wrong arity)."""
    SENT = object()
    result, spy, n = _drive_notify(decide_results=[False], session=SENT)
    assert result is False, result
    assert n == 1, f"decide_notification called {n} times, expected 1"
    assert spy.calls == [(SENT, 4242, False)], spy.calls


def test_notify_decision_persist_is_not_swallowed_by_the_guard() -> None:
    """The shipped persist sits INSIDE the try block (ISS-001: the persistence
    IS the recorded delivery). A decide result of True must still produce the
    write, and the returned value must be True - i.e. the try body runs to
    completion, not to the persist call only."""
    SENT = object()
    result, spy, n = _drive_notify(decide_results=[True], session=SENT)
    assert result is True
    assert spy.calls == [(SENT, 4242, True)], spy.calls


def test_notify_decision_falls_back_to_the_pure_path_when_the_session_decide_fails() -> None:
    """The session-leg decide raises (a settings read can abort the
    transaction - the docstring's whole point) -> the except logs and the
    `if notify is None` leg re-decides on the SHIPPED DEFAULTS (session=None).
    decide is therefore called TWICE and nothing persists. This is the leg the
    initializer mutants skip: with notify initialised to "" (m12/m357) the
    `is None` test is False, the leg is skipped, the result is the initializer
    and decide runs ONCE - so this test's (call count, result identity, zero
    writes) triple kills the initializer arms. The second decide's SESSION
    is pinned to None as well, which is the "deciding on the shipped defaults"
    contract itself."""
    SENT = object()
    seen_sessions: list[Any] = []
    seen_kwargs: list[dict[str, Any]] = []

    async def decide_two_legs(sess: Any, **kwargs: Any) -> Any:
        seen_sessions.append(sess)
        seen_kwargs.append(kwargs)
        if len(seen_sessions) == 1:
            raise RuntimeError("session dead")
        return False

    sent = va.VlmAnalyzer.__new__(va.VlmAnalyzer)
    spy = PersistSpy()
    spy.bind(sent)
    with _Patcher(
        (va, "decide_notification", decide_two_legs),
        (va, "get_session", lambda: _FakeSessionCtx(SENT)),
    ):
        result = asyncio.run(
            sent._notify_decision(
                event_id=4242,
                camera_id="camera-kitchen",
                timestamp=TS,
                risk_score=50,
                verdict="confirmed",
                detections=[{"id": 1}],
            )
        )
    assert seen_sessions[0] is SENT, "the session leg did not run"
    assert seen_sessions[1] is None, "the fallback must decide on the shipped defaults"
    assert len(seen_sessions) == 2, (
        f"expected one session attempt + one pure fallback, got {len(seen_sessions)}"
    )
    # Row-2 repair (birth m37): the fallback call is decide_notification(None,
    # **kwargs) - dropping **kwargs (mutmut renders it `decide_notification(None, )`)
    # was invisible while the spy swallowed kwargs. Full-kwargs equality on the
    # SECOND call pins the whole decision surface (risk_score/camera_id/
    # timestamp/verification_verdict/detections) rides BOTH legs.
    assert seen_kwargs[1] == {
        "risk_score": 50,
        "camera_id": "camera-kitchen",
        "timestamp": TS,
        "verification_verdict": "confirmed",
        "detections": [{"id": 1}],
    }, seen_kwargs[1]
    assert result is False, repr(result)
    assert spy.calls == [], spy.calls


def test_notify_decision_logs_the_session_failure_once() -> None:
    """The warning is the operator's only trace that the decision came from
    defaults, not from stored settings. Assert the message + the structured
    extra surface EXACTLY - a mutant that drops the log, renames the key,
    XX-wraps the text, or feeds the error through str(None) breaks here.
    (Row-2 repair: the first draft filtered on a "defaults" SUBSTRING and
    pinned only camera_id, which is exactly the fragment-count shape that
    passes XX-wrapped text and extra-key renames - birth adjudication run-1
    survivors m27/m31/m32/m33 proved the leak; equality + .error close it.)"""
    records: list[logging.LogRecord] = []

    class Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Collector()
    va.logger.addHandler(handler)
    try:
        result, spy, n = _drive_notify(
            decide_results=[RuntimeError("nope"), False], session=object(), boom=False
        )
    finally:
        va.logger.removeHandler(handler)
    assert result is False
    warns = [
        r
        for r in records
        if r.levelno == logging.WARNING
        and r.getMessage() == "notify decision session failed - deciding on the shipped defaults"
    ]
    assert len(warns) == 1, [r.getMessage() for r in records]
    assert getattr(warns[0], "camera_id", None) == "camera-kitchen"
    assert getattr(warns[0], "error", None) == "nope"


def test_notify_decision_returns_none_only_when_the_pure_path_fails() -> None:
    """Both legs fail -> None ("no key on the wire"). The initializer mutants
    (m12: "" / False-worlds) cannot produce None here because they skip the
    leg whose failure is the ONLY thing that returns None; assert the exact
    value plus the error log that pairs with it."""
    records: list[logging.LogRecord] = []

    class Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Collector()
    va.logger.addHandler(handler)
    try:
        result, spy, n = _drive_notify(
            decide_results=[RuntimeError("a"), RuntimeError("b")],
            session=object(),
            boom=True,
        )
    finally:
        va.logger.removeHandler(handler)
    assert result is None, repr(result)
    errs = [r for r in records if r.levelno >= logging.ERROR]
    assert len(errs) == 1, [r.getMessage() for r in records]
    assert spy.calls == []


def test_notify_decision_persist_failure_keeps_the_decision() -> None:
    """ISS-001's doctrine half: a persist that RAISES (the DB write failed)
    must not lose the decision - the result still comes back, and it is the
    decided value, not a fallback re-compute (decide called exactly once).
    Pins that persist really was attempted with the session tuple."""
    SENT = object()

    class Boom:
        async def __aenter__(self) -> Any:
            return SENT

        async def __aexit__(self, *exc: Any) -> bool:
            return False

    sent = va.VlmAnalyzer.__new__(va.VlmAnalyzer)
    calls: list[tuple[Any, ...]] = []

    async def persist(*args: Any) -> None:
        calls.append(args)
        raise RuntimeError("constraint violated")

    async def decide(sess: Any, **kwargs: Any) -> bool:
        return True

    sent._persist_notify_decision = persist  # type: ignore[method-assign]
    with _Patcher((va, "decide_notification", decide), (va, "get_session", lambda: Boom())):
        result = asyncio.run(
            sent._notify_decision(
                event_id=42,
                camera_id="c",
                timestamp=TS,
                risk_score=1,
                verdict="rejected",
                detections=[],
            )
        )
    assert result is True, repr(result)
    assert calls == [(SENT, 42, True)], calls


# ---------------------------------------------------------------------------
# Pure-builder EQUIV witnesses: shipped behavior pinned where the surviving
# mutants live, so a REGRESSION in the EQUIV direction (someone "fixes" the
# dead code into live code) is caught, and the ledger's claims stay measured.
# ---------------------------------------------------------------------------


def test_streaming_error_dump_keeps_recoverable_true_in_every_arm() -> None:
    """Witness for the m33/m48 EQUIV claim: the default IS True, so both
    streaming error arms dump identically with or without the kwarg. Pinned
    here so the EQUIV ruling (Y: model_dump identical in EVERY arm) is
    re-measured, not inherited."""
    a = va.StreamingErrorEvent(
        error_code="INTERNAL_ERROR", error_message="Streaming analysis failed", recoverable=True
    ).model_dump()
    b = va.StreamingErrorEvent(
        error_code="INTERNAL_ERROR", error_message="Streaming analysis failed"
    ).model_dump()
    assert (
        a
        == b
        == {
            "event_type": "error",
            "error_code": "INTERNAL_ERROR",
            "error_message": "Streaming analysis failed",
            "recoverable": True,
        }
    ), (a, b)


def test_streaming_progress_dump_keeps_accumulated_text_empty() -> None:
    """Witness for the m5 EQUIV claim (accumulated_text default "")."""
    a = va.StreamingProgressEvent(
        content="", accumulated_text="", progress_percent=5.0
    ).model_dump()
    b = va.StreamingProgressEvent(content="", progress_percent=5.0).model_dump()
    assert (
        a
        == b
        == {
            "event_type": "progress",
            "content": "",
            "accumulated_text": "",
            "progress_percent": 5.0,
        }
    ), (a, b)


def test_load_household_context_sql_is_the_fk_derived_join() -> None:
    """Witness for the m5/m7 EQUIV claim (join(Zone, None) / join(Zone,) render
    byte-identical SQL). Assert the shipped statement's ON clause text so a
    future schema change that makes the ON clause load-bearing re-opens the
    ruling instead of silently shipping a different join."""
    from sqlalchemy import select

    from backend.models.zone import Zone
    from backend.models.zone_household_config import ZoneHouseholdConfig

    shipped = str(
        select(ZoneHouseholdConfig, Zone)
        .join(Zone, Zone.id == ZoneHouseholdConfig.zone_id)
        .where(Zone.camera_id == "c")
        .compile(dialect=postgresql.dialect())
    )
    one_arg = str(
        select(ZoneHouseholdConfig, Zone)
        .join(Zone)
        .where(Zone.camera_id == "c")
        .compile(dialect=postgresql.dialect())
    )
    none_arg = str(
        select(ZoneHouseholdConfig, Zone)
        .join(Zone, None)
        .where(Zone.camera_id == "c")
        .compile(dialect=postgresql.dialect())
    )
    assert "JOIN camera_zones ON camera_zones.id = zone_household_configs.zone_id" in shipped
    assert shipped == one_arg == none_arg, "join arms diverged - the EQUIV ruling is stale"


def test_apply_verdict_invariants_maps_level_only_through_the_service() -> None:
    """Witness for the m37 EQUIV claim (risk_score is REQUIRED, the else arm is
    dead): the level comes from risk_score_to_severity(score).value on the
    SCORE path, and the None-score path belongs to verdict=None (the
    verification_failed dict), never to a constructed verdict. A stub severity
    service keeps this settings-free."""

    class StubSeverity:
        low_max = 30

        @staticmethod
        def risk_score_to_severity(score: int) -> Any:
            class _S:
                value = "high" if score >= 70 else "medium"

            return _S()

    from backend.services.vlm_verdict import VlmVerdict

    v = VlmVerdict(
        verdict="confirmed",
        risk_score=85,
        summary="A person stands at the door.",
        reasoning="Criterion evidence reviewed.",
        description="Front door, one person.",
        criteria=[{"name": "person_present", "passed": True, "evidence": "full frame"}],
        provenance={"engine": "llama.cpp", "model_id": "Qwen3VL-8B"},
    )
    out = va.apply_verdict_invariants(v, StubSeverity())  # type: ignore[arg-type]
    assert out["risk_level"] == "high", out
    assert out["risk_score"] == 85 and out["verdict"] == "confirmed"
    # The None-verdict world (not a None-score world) owns the NULL level.
    none_out = va.apply_verdict_invariants(None, StubSeverity())  # type: ignore[arg-type]
    assert none_out["risk_level"] is None and none_out["verdict"] == "verification_failed"


def test_verification_payload_reads_only_the_row_list() -> None:
    """Witness for the _EventView m1 / analyze_batch m341 EQUIV claim: the
    view's event_id is never read, and a non-empty rows list ALWAYS yields a
    payload (the m348 else arm is dead). Both halves of the claim measured on
    the real function."""
    from backend.api.schemas.event_verification import verification_payload

    class Row:
        id = 7
        created_at = TS
        verdict = "confirmed"
        risk_score = 85
        summary = "A person stands at the door."
        reasoning = "Criterion evidence reviewed."
        scene_description = "d"
        criteria = None
        key_frame_detection_ids = None
        engine = "vlm"
        model_id = "m"
        latency_ms = 1

    for event_id in (4242, None):
        view = va._EventView(event_id=event_id, rows=[Row()])  # type: ignore[arg-type]
        payload = verification_payload(view)
        assert payload is not None, f"event_id={event_id} produced no payload"
        assert payload.model_dump()["verdict"] == "confirmed"
    assert verification_payload(va._EventView(event_id=1, rows=[])) is None


def test_key_frame_ids_are_pairing_invariant() -> None:
    """Witness for the key_frame_ids m4 EQUIV claim: two rows sharing one
    file_path (the detector's one-row-per-object shape) with different
    object_types merge into one still whether the pairs are split by a real
    camera_id or merged by the fallback, and the WINNER per file is the
    max-ranked row - so `by_path` cannot disagree between shipped and the
    `build_frame_refs(..., None)` mutant."""
    from backend.services.vlm_analyzer import key_frame_ids

    def req(paths: list[str], camera_id: str) -> Any:
        class _Ctx:
            pass

        ctx = _Ctx()
        ctx.camera_id = camera_id

        class _Req:
            pass

        r = _Req()
        r.context = ctx
        r.image_paths = paths
        return r

    rows = [
        {
            "id": 1,
            "camera_id": "camA",
            "object_type": "person",
            "confidence": 0.9,
            "detected_at": None,
            "file_path": "/f/a.jpg",
            "thumbnail_path": None,
        },
        {
            "id": 2,
            "camera_id": "camA",
            "object_type": "car",
            "confidence": 0.8,
            "detected_at": None,
            "file_path": "/f/b.jpg",
            "thumbnail_path": None,
        },
    ]
    got = key_frame_ids(req(["/f/a.jpg", "/f/b.jpg"], "camA"), detections=rows)
    assert got == [1, 2], got


class NotifySpy:
    """Stands in for the bound `_notify_decision` method on the analyzer
    INSTANCE (attribute lookup beats the class def), recording the full
    kwargs of every call. Returns False - distinguishable from the
    `notify: bool | None = None` initializer so the broadcast key assert
    downstream is not vacuous."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> bool:
        self.calls.append(kwargs)
        return False

    @property
    def count(self) -> int:
        return len(self.calls)


def _drive_batch(*, replay: bool = False) -> Any:
    """One full analyze_batch drive over the battery-Y fake surface (the
    fakes are Y's, copied verbatim above; construction through the REAL
    __init__ is Y's own precedent - settings validate under the test env).
    Everything the shipped path calls outward is a spy; the analyzer is
    returned with the spies on a namespace. `_notify_decision` is replaced
    on the instance so the call site - NOT the decision internals, which
    the tests above pin directly - is what these drives measure."""
    session = _Y_FakeSession(detections=[det_row(11), det_row(12)])
    client = _Y_FakeClient([_Y_make_verdict()])
    broadcaster = _Y_FakeBroadcaster()
    gb = getter_spy(broadcaster)
    analyzer = va.VlmAnalyzer(
        vlm_client=client, redis_client=_Y_FakeRedis(), severity=SEV, replay=replay
    )
    notify_spy = NotifySpy()
    analyzer._notify_decision = notify_spy  # type: ignore[method-assign]
    with _Patcher(
        (va, "get_session", lambda: session),
        (va, "get_zones_for_detection", Spy(result=[])),
        (va, "load_household_context", Spy(result={})),
        (
            va,
            "collect_specialist_outputs",
            Spy(result={"faces": "f", "plates": "p", "person_reid": "r"}),
        ),
        (va, "record_pipeline_error", SyncSpy()),
    ):
        with patch("backend.services.event_broadcaster.get_broadcaster", gb):
            event = asyncio.run(
                analyzer.analyze_batch("b1", camera_id="cam1", detection_ids=[11, 12])
            )
    return SimpleNamespaceOf(
        {
            "event": event,
            "session": session,
            "notify": notify_spy,
            "broadcaster": broadcaster,
        }
    )


def test_analyze_batch_calls_notify_decision_with_the_flushed_event_id_and_batch_camera() -> None:
    """m360 (event_id -> None) / m361 (camera_id -> None) mutate the CALL
    SITE kwargs inside analyze_batch, so the kill has to drive analyze_batch
    itself and read what _notify_decision actually RECEIVED. event_id must
    be the id the write session's add/flush assigned (101 - the literal
    pins the flush contract, the event.id equality pins identity), and
    camera_id must be the RESOLVED BATCH camera ("cam1"), not the row
    camera: the projection row deliberately carries a DIFFERENT camera
    ("rcam", Y's divergence rule) so a projection-row substitution has a
    witness. The full key set is pinned too (renames/deletions die on the
    set, values on the dict)."""
    env = _drive_batch()
    spy = env.notify
    assert spy.count == 1, f"_notify_decision called {spy.count} times, expected 1"
    kw = spy.calls[0]
    assert set(kw) == {
        "event_id",
        "camera_id",
        "timestamp",
        "risk_score",
        "verdict",
        "detections",
    }, set(kw)
    assert kw["event_id"] == 101 == env.event.id, kw["event_id"]
    assert kw["camera_id"] == "cam1", kw["camera_id"]
    assert kw["timestamp"] == TS1, kw["timestamp"]
    assert kw["risk_score"] == 85, kw["risk_score"]
    assert kw["verdict"] == "confirmed", kw["verdict"]
    assert len(kw["detections"]) == 2 and kw["detections"][0]["id"] == 11, kw["detections"]
    # the decided value rides the broadcast frame (m357-adjacent: the
    # call site's result must reach _broadcast, and False - not absence)
    assert env.broadcaster.messages[0]["data"]["notify"] is False, env.broadcaster.messages


def test_analyze_batch_replay_never_asks_for_a_notify_decision() -> None:
    """The `if not self._replay` guard is the whole replay contract here
    (F11 ruling 4 - replay writes nothing outward and never reads the
    owner's settings): the decision call and the broadcast both stay silent
    while the event is still analyzed. Drops of the guard would call the
    spy and emit a frame."""
    env = _drive_batch(replay=True)
    assert env.notify.count == 0, env.notify.calls
    assert env.broadcaster.messages == [], env.broadcaster.messages
    assert env.event.id == 101, env.event.id
