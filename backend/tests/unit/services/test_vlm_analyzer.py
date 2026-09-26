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

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.api.schemas.websocket import WebSocketEventData
from backend.models.event import Event
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
    model_id: str = "Qwen3VL-4B-Instruct-Q4_K_M",
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
    """The analyzer only gets/sets string keys (nemotron's analyzer fakes
    use the same minimal surface)."""

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values: dict[str, str] = dict(values or {})
        self.sets: list[tuple[str, str]] = []

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, expire: int | None = None) -> None:
        self.values[key] = value
        self.sets.append((key, value))


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
        assert row.model_id == "Qwen3VL-4B-Instruct-Q4_K_M"
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
        from backend.services.nemotron_analyzer import ConstrainedDecodingNotEnforced

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
            {
                "batch:b9:camera_id": "front_door",
                "batch:b9:detections": json.dumps([11]),
            }
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
