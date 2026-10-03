"""Campaign #23 (batch-38, battery Y) - `backend/services/vlm_analyzer`.

# TARGET-MODULE: backend.services.vlm_analyzer

Harness contract (b30 sweep, /home/agent/runs/b30-sweep.py): NO pytest
fixtures, NO parametrize, NO monkeypatch - the sweep imports this file
directly and calls every module-level ``test_*`` with zero arguments in
ONE process, flipping os.environ[MUTANT_UNDER_TEST] per key. Async entry
points (analyze_batch, load_household_context, analyze_batch_streaming,
the private idempotency helpers, _broadcast) are driven with asyncio.run
INSIDE the test body. Seams are patched through the TARGET MODULE's
globals (va.get_session, va.get_zones_for_detection,
va.load_household_context, va.record_pipeline_error, va.logger, va.time)
and lazily-imported seams through their home module
(backend.services.event_broadcaster.get_broadcaster), always save/restore
via contextlib.ExitStack so a mid-test assert failure cannot leak a patch
into the next key's window.

Why so many exact-shape asserts (the campaign's disposition rule - shape
is EVIDENCE, observation decides):

  * log records are captured from va.logger (a stdlib logging.Logger -
    the repo's ContextFilter only ENRICHES) and asserted on msg + the
    FULL extra= surface as record attributes (record.batch_id, ...) - an
    extra=None or a renamed key then raises AttributeError, never slips;
  * SQL is asserted STRUCTURALLY: the fake session parses FROM-table +
    whereclause (column, operator, value). ``.where(None)`` compiles to a
    silent ``WHERE NULL`` (probed: sqlalchemy does NOT raise), so an
    equality-only read would mask the boundary mutants - the fake returns
    rows only for a well-shaped predicate, exactly like a real DB;
  * dicts the analyzer builds (the session-1 detections projection, the
    broadcast message, the streaming model_dump) are compared FIELD BY
    FIELD against literal expectations, so key renames ("XXcamera_idXX")
    and case flips all die; fixtures keep every row value DIFFERENT from
    its fallback so a fallback cannot mask a lookup-key rename;
  * the pure builders are called directly and their dataclass/pydantic
    results compared field-by-field; analyzer_batch drives a
    settings-identity, call-count and call-args spy for every seam call.

Honesty ledger (EQUIV candidates REGISTERED BY CONSTRUCTION; the sweep
verdict + the per-key probes in the campaign notes are the evidence - a
construction claim is not a verdict claim):
  - analyze_batch m347  payload is never None here (verification_payload
    only returns None for a non-list or empty rows; this call site always
    feeds the row it just selected... single-row view => non-None)
  - analyze_batch m340  the _EventView(event_id=None) ARG is unread (see
    the _EventView entry - verification_payload reads .verifications only)
  - analyze_batch m40/m42  dead initializers (zones/household are
    re-assigned unconditionally before their first read)
  - apply_verdict_invariants m37  VlmVerdict.risk_score is a REQUIRED
    int field => `risk_score is not None` is always True
  - _EventView.__init__ m1  verification_payload reads ONLY
    event.verifications (never event_id)
  - load_household_context m5/m7  join(Zone, None) / join(Zone,) render
    BYTE-IDENTICAL SQL (probed: the FK-derived ON clause is used; the
    zone_household_configs.zone_id FK makes the onclause redundant)
  - key_frame_ids m4  the by_path map is pairing-invariant: per file the
    winner is the max-ranked frame, whether the (camera,class) pairs are
    merged by the camera fallback or split by `build_frame_refs(..., None)`
  - analyze_batch_streaming m5  accumulated_text="" == the schema default
  - analyze_batch_streaming m25  recoverable=True == the schema default
  - analyze_batch_streaming m33 (BORN in the campaign run's generation,
    slot 33; pre-run this line had no mutant - battery coverage grew it)
    deleting the recoverable=True KWARG == the schema default
    (StreamingErrorEvent.recoverable Field default True, probed), so the
    model_dump is identical in EVERY arm - demonstrated, not assumed: the
    internal-error test below asserts the COMPLETE dump with
    "recoverable": True present.
"""

from __future__ import annotations

import asyncio
import logging
import operator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

from backend.api.schemas.websocket import WebSocketEventData
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_verification import EventVerification
from backend.services import vlm_analyzer as va
from backend.services.severity import SeverityService
from backend.services.vlm_client import VlmTransportError
from backend.services.vlm_verdict import VlmVerdict

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


class FakeRedis:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values: dict[str, str] = dict(values or {})
        self.sets: list[tuple[str, str, Any]] = []

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, expire: Any = "UNSET") -> None:
        self.values[key] = value
        self.sets.append((key, value, expire))


class FakeClient:
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


class FakeBroadcaster:
    def __init__(self, raises: Exception | None = None) -> None:
        self.messages: list[dict[str, Any]] = []
        self.raises = raises

    async def broadcast_event(self, message: dict[str, Any]) -> int:
        if self.raises is not None:
            raise self.raises
        self.messages.append(message)
        return 1


def getter_spy(broadcaster: FakeBroadcaster) -> Spy:
    spy = Spy(result=broadcaster)

    async def fake_get_broadcaster(redis: Any) -> FakeBroadcaster:
        await spy(redis)
        return broadcaster

    return spy


class ZoneLike:
    def __init__(self, zone_id: str, name: str) -> None:
        self.id = zone_id
        self.name = name


class FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> FakeResult:
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


class FakeSession:
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
        # faithful server default: event_verifications.created_at = utc_now()
        for obj in self.added:
            if isinstance(obj, EventVerification) and getattr(obj, "created_at", None) is None:
                obj.created_at = TS1

    async def execute(self, stmt: Any) -> FakeResult:
        self.executed.append(stmt)
        return FakeResult(self._rows_for(stmt))

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


def make_verdict(
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
    client: FakeClient | None = None,
    redis: FakeRedis | None = None,
    detections: list[Any] | None = None,
    existing_event: Any = None,
    replay: bool = False,
    zones: list[ZoneLike] | None = None,
    household: dict[str, Any] | None = None,
    collect: Spy | Exception | None = None,
    metrics: Spy | None = None,
    broadcaster: FakeBroadcaster | None = None,
    fake_time: FakeTime | None = None,
    severity: SeverityService | None = None,
):
    """Patches EVERY seam the analyzer touches and yields a namespace of
    the fakes so tests can assert calls. All patches undo in finally."""
    session = FakeSession(
        detections=detections if detections is not None else [det_row(11)],
        existing_event=existing_event,
    )
    if broadcaster is None:
        broadcaster = FakeBroadcaster()
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
        vlm_client=client or FakeClient([make_verdict()]),
        redis_client=redis if redis is not None else FakeRedis(),
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
    at = va.apply_verdict_invariants(make_verdict(verdict="rejected", risk_score=29), SEV)
    assert at["risk_score"] == 29
    assert "clamped" not in at["reasoning"]
    above = va.apply_verdict_invariants(make_verdict(verdict="rejected", risk_score=30), SEV)
    assert above["risk_score"] == 29
    assert above["reasoning"].endswith("[§6: verdict 'rejected' clamped to <= 29 (was 30)]")
    below = va.apply_verdict_invariants(make_verdict(verdict="rejected", risk_score=5), SEV)
    assert below["risk_score"] == 5
    assert below["risk_level"] == "low"


def test_invariants_pass_through_is_field_exact() -> None:
    v = make_verdict(verdict="uncertain", risk_score=45)
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
    client = FakeClient([make_verdict(risk_score=85)])
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
    with analyzer_env(redis=FakeRedis()) as env:
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
    with analyzer_env(redis=FakeRedis(), detections=[det_row(11)]) as env:
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
    redis = FakeRedis({"batch_event:b1": "77"})
    client = FakeClient([make_verdict()])
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
    client = FakeClient([VlmTransportError("boom")])
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
    zones = [ZoneLike("z1", "Porch")]
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
    with analyzer_env(detections=rows, zones=[ZoneLike("z1", "Porch")]) as env:
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
    client = FakeClient([make_verdict()])
    rows = [
        det_row(11, bbox=(10, 20, 30, 40), video=(640, 480), track_id=7),
        det_row(12, bbox=(10, 20, 30, 40), video=(640, 480), track_id=7),
    ]
    zones_spy = Spy(
        result=[ZoneLike("z1", "Porch")],
        results={1: [ZoneLike("z2", "Drive")]},  # second geometry call differs
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
    client = FakeClient([make_verdict()])
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
    client = FakeClient([make_verdict()])
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
    with analyzer_env(broadcaster=FakeBroadcaster(raises=RuntimeError("redis down"))) as env:
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
    analyzer = va.VlmAnalyzer(vlm_client=FakeClient([]), redis_client=None)
    event = Event(id=5, batch_id="b", camera_id="c")
    with logcap() as cap:
        run(analyzer._broadcast(event, {"verdict": "confirmed"}))
    # ONLY the debug skip line, nothing else.
    assert cap.msgs() == ["vlm broadcast skipped: no redis client"]
    assert all(r.levelno == logging.DEBUG for r in cap.records)


def test_broadcast_message_is_key_exact() -> None:
    analyzer = va.VlmAnalyzer(vlm_client=FakeClient([]), redis_client=FakeRedis())
    broadcaster = FakeBroadcaster()
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
    analyzer = va.VlmAnalyzer(vlm_client=FakeClient([]), redis_client=FakeRedis())
    broadcaster = FakeBroadcaster()
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
        vlm_client=FakeClient([make_verdict(risk_score=85)]),
        redis_client=FakeRedis(),
    )
    session = FakeSession(detections=[det_row(11)])
    broadcaster = FakeBroadcaster()
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
        vlm_client=FakeClient([VlmTransportError("down")]),
        redis_client=FakeRedis(),
    )
    session = FakeSession(detections=[det_row(11)])
    with ExitStack() as stack:
        stack.enter_context(patched(va, "get_session", lambda: session))
        stack.enter_context(
            patch(
                "backend.services.event_broadcaster.get_broadcaster",
                getter_spy(FakeBroadcaster()),
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
    analyzer = va.VlmAnalyzer(vlm_client=FakeClient([make_verdict()]), redis_client=FakeRedis())
    session = FakeSession(detections=[det_row(11)])
    with ExitStack() as stack:
        stack.enter_context(patched(va, "get_session", lambda: session))
        stack.enter_context(
            patch(
                "backend.services.event_broadcaster.get_broadcaster",
                getter_spy(FakeBroadcaster()),
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

    analyzer = _Divergent(vlm_client=FakeClient([]), redis_client=FakeRedis())
    with logcap():
        events = run(_collect_stream(analyzer.analyze_batch_streaming("b1")))
    assert events[1]["event_type"] == "error"
    assert events[1]["error_code"] == "LLM_INVALID_RESPONSE"


def test_streaming_level_none_with_score_still_answers_error() -> None:
    # the mirrored polarity (score present, level NULL) - same argument.
    class _Divergent2(va.VlmAnalyzer):
        async def analyze_batch(self, *args: Any, **kwargs: Any) -> Event:
            return Event(id=9, batch_id="b", camera_id="c", risk_score=10, risk_level=None)

    analyzer = _Divergent2(vlm_client=FakeClient([]), redis_client=FakeRedis())
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

    analyzer = _Analyzer(vlm_client=FakeClient([]), redis_client=FakeRedis())
    with logcap() as cap:
        events = run(_collect_stream(analyzer.analyze_batch_streaming("b1")))
    assert cap.records == []
    # Event(summary=None) -> `summary or "No summary"` placeholder.
    assert events[1]["summary"] == "No summary"
    assert events[1]["reasoning"] == "No reasoning"
    assert events[1]["event_id"] == 9
    assert events[1]["risk_score"] == 10
    assert events[1]["risk_level"] == "low"
