"""ISS-001's closure test, on the LIVE test Postgres: a notify decision that
survives its own frame.

OD-31 (ruled 2026-10-05, docs/vss-integration/17-action-plan.md Intake log, and
the OD table's OD-31 row) narrowed ISS-001's acceptance to two things this file
supplies: "(or recorded delivery)" IS the persisted ``EventNotifyDecision``
row, and closure is "the live-DB ``notify=true``-reaches-a-surface test". The
AST half of the narrowed guard is
``backend/tests/unit/services/test_notify_reachability_guard.py``; this file is
the other half, end to end through the analyzer's own ``analyze_batch`` with a
scripted fake VLM (the 1.3 harness in ``test_vlm_analyzer.py`` - FakeClient,
make_verdict, the camera/detection helpers, ``reset_broadcaster_state`` around
the broadcast, and ``TestRestVerificationField``'s client + db_session +
real_redis trio for the REST read-back).

The four arms, and why each is its own test
------------------------------------------
  a. confirmed / score 75 / default prefs - the row says ``notify=true`` AND
     both REST surfaces carry ``"notify": true``. Row-only would not close
     ISS-001 (the decision existed and was unreadable - that WAS the bug);
     surface-only would not close OD-31's "(or recorded delivery)".
  b. rejected - the row says ``notify=false`` AND both surfaces carry
     ``"notify": false``. This is the arm that makes the field mean something:
     a recorded decision to stay quiet is a real answer, present in the
     payload. A consumer asking "why was I not paged?" has to be able to tell
     this event from one that was never judged.
  c. a legacy event with no row - the key is ABSENT on both surfaces, not
     null. The presence contract is shared with ``verification``
     (``backend/api/schemas/events.py``, whose exclude_if this field mirrors),
     and the whole asymmetry is false-present vs absent: if absence could leak
     as null, arm (b) and arm (c) would be the same payload.
  d. replay - no row is written and the key stays absent. ``_notify_decision``
     is called only when ``not self._replay`` (the analyzer never reads the
     owner's settings or writes outward during a replay), so the ABSENCE half
     of the contract is what replay produces even though it commits a real
     event row. Pinning that here rather than in the unit tier matters because
     the tempting wrong fix is "make the REST field re-derive notify from the
     stored score" - which would silently invent a decision for every replay
     row, and would also re-arm the ISS-018 divergence on the display path
     (the read-time recompute ISS-001's mechanism note eliminates).

Score choice for arm (a): 75 is what ISS-001's acceptance names, and under the
OD-29 operating point it is an unambiguous "notify" - ``risk_level`` high is in
the shipped default ``risk_filters`` (medium/high/critical) and the score
clears ``DEFAULT_CAMERA_RISK_THRESHOLD`` = 60, the floor a camera with no
setting row takes. No preferences row is inserted anywhere in this file: the
filter's "no row means the shipped default setting" rule is part of what arm
(a) is exercising.

Fabricated rows and synthetic verdicts only (D10); the fake client never reads
an image path. Same-session compose rule (E11): run with the live test PG/Redis
up -
    uv run pytest backend/tests/integration/test_notify_decision_wiring.py -n0
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_notify import EventNotifyDecision
from backend.services.vlm_analyzer import VlmAnalyzer
from backend.services.vlm_verdict import VlmVerdict

pytestmark = pytest.mark.integration


class FakeClient:
    """Scripted VLM, same shape as the 1.3 harness in test_vlm_analyzer.py:
    prompt_text + assess + the per-call close() the analyzer's client
    lifecycle expects. No transport, no imagery."""

    def __init__(self, *, verdict: VlmVerdict | None = None, error: Exception | None = None):
        self._verdict = verdict
        self._error = error
        self.closed = False
        self.assess_calls = 0

    def prompt_text(self, request) -> str:
        return f"ASSESS camera={request.context.camera_id} PATHS {request.image_paths}"

    async def assess(self, request) -> VlmVerdict:
        self.assess_calls += 1
        if self._error is not None:
            raise self._error
        assert self._verdict is not None
        return self._verdict

    async def close(self) -> None:
        self.closed = True


def make_verdict(**overrides) -> VlmVerdict:
    data = {
        "verdict": "confirmed",
        "risk_score": 75,
        "summary": "A person stands at the side gate.",
        "reasoning": "Criterion evidence reviewed.",
        "description": "Side gate, one person, evening.",
        "criteria": [{"name": "person_present", "passed": True, "evidence": "full frame"}],
        "provenance": {"engine": "llama.cpp", "model_id": "Qwen3VL-8B-Instruct-Q4_K_M"},
    } | overrides
    return VlmVerdict.model_validate(data)


@pytest.fixture
async def camera(db_session):
    cam = Camera(
        id=f"ntcam-{uuid.uuid4().hex[:8]}",
        name=f"notify-{uuid.uuid4().hex[:8]}",
        folder_path="/export/foscam/notify",
    )
    db_session.add(cam)
    await db_session.commit()
    return cam


async def _mk_detections(db_session, camera, count: int = 2) -> list[int]:
    """Synthetic detection rows (fake paths - the fake client never opens
    one). person@0.9 so the NULL-score detector rule would pass too; the arms
    below are scored, so that only matters for reading them honestly."""
    ids: list[int] = []
    for i in range(count):
        det = Detection(
            camera_id=camera.id,
            file_path=f"/export/foscam/notify/det_{uuid.uuid4().hex[:6]}.jpg",
            object_type="person",
            confidence=0.9,
            detected_at=datetime(2026, 10, 5, 10, i, tzinfo=UTC),
        )
        db_session.add(det)
        await db_session.flush()
        ids.append(det.id)
    await db_session.commit()
    return ids


async def _analyze(
    verdict: VlmVerdict, camera, det_ids, real_redis, *, replay: bool = False
) -> Event:
    """One batch through the real analyzer, with the broadcaster bound to this
    test's redis and released after (the 1.3 pattern: a broadcaster holding a
    dead loop poisons the next test on the worker)."""
    from backend.services.event_broadcaster import reset_broadcaster_state

    reset_broadcaster_state()
    analyzer = VlmAnalyzer(
        vlm_client=FakeClient(verdict=verdict), redis_client=real_redis, replay=replay
    )
    try:
        return await analyzer.analyze_batch(
            f"batch-{uuid.uuid4().hex[:8]}", camera_id=camera.id, detection_ids=det_ids
        )
    finally:
        reset_broadcaster_state()


async def _decision_row(db_session, event_id: int) -> EventNotifyDecision | None:
    return await db_session.scalar(
        select(EventNotifyDecision).where(EventNotifyDecision.event_id == event_id)
    )


async def _surfaces(client, camera, event_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
    """(list item, detail body) for one event - both REST surfaces the
    decision has to reach, read the way the UI reads them (AlertsPage and the
    ActivityFeed both read GET /api/events; the detail endpoint is what a
    clicked event loads).

    The list is filtered to OUR camera and the item found by id: Event ids
    restart per test on this tier, so "items[0]" would be a coin flip - the
    same first-frame-wins hazard test_vlm_analyzer.py documents for WS frames.
    """
    lst = await client.get("/api/events", params={"camera_id": camera.id})
    assert lst.status_code == 200
    item = next(i for i in lst.json()["items"] if i["id"] == event_id)
    detail = await client.get(f"/api/events/{event_id}")
    assert detail.status_code == 200
    return item, detail.json()


class TestRecordedDecisionReachesASurface:
    """OD-31's closure: a decided notify=true is readable from a surface a
    human sees, after the fact, from the database."""

    async def test_confirmed_decision_is_persisted_and_rendered(
        self, client, db_session, camera, real_redis
    ):
        det_ids = await _mk_detections(db_session, camera)
        event = await _analyze(make_verdict(risk_score=75), camera, det_ids, real_redis)

        # --- the recorded delivery (OD-31's reading of the acceptance's clause)
        row = await _decision_row(db_session, event.id)
        assert row is not None, "no event_notify_decisions row - ISS-001 is not closed"
        assert row.notify is True
        assert row.decided_by == "vlm"

        # --- and the same answer on both surfaces, from the row
        item, detail = await _surfaces(client, camera, event.id)
        assert item["notify"] is True, "the list surface lost a true decision"
        assert detail["notify"] is True, "the detail surface lost a true decision"

    async def test_rejected_decision_is_recorded_as_false_and_rendered_present(
        self, client, db_session, camera, real_redis
    ):
        """The asymmetry's other half, in one test: false is a DECISION and
        must arrive as ``"notify": false`` - not as absence.

        spec section 6's rejected rule is what makes the answer false (the
        filter returns False for a rejected verdict before any level or
        threshold logic), and the analyzer's own invariant clamps the stored
        score to <= low_max, so the row is the only place the operator's
        "why was I not paged?" question is answered.
        """
        det_ids = await _mk_detections(db_session, camera)
        event = await _analyze(
            make_verdict(verdict="rejected", risk_score=85), camera, det_ids, real_redis
        )

        row = await _decision_row(db_session, event.id)
        assert row is not None, "a decision to stay quiet is still a decision"
        assert row.notify is False

        item, detail = await _surfaces(client, camera, event.id)
        assert "notify" in item and item["notify"] is False, (
            f"the list surface dropped a recorded false into absence: {sorted(item)}"
        )
        assert "notify" in detail and detail["notify"] is False, (
            f"the detail surface dropped a recorded false into absence: {sorted(detail)}"
        )

    async def test_exactly_one_row_per_event(self, client, db_session, camera, real_redis):
        """One row, not one per attempt.

        ``event_notify_decisions.event_id`` is UNIQUE and the writer is a
        pg_insert on_conflict_do_update, so a re-analyzed batch re-decides the
        same row - the decision belongs to the event and not to the run
        (unlike event_verifications, where a repair path may stack rows). A
        single analyze here pins the row COUNT, which is what a stacking bug
        would break.
        """
        det_ids = await _mk_detections(db_session, camera)
        event = await _analyze(make_verdict(risk_score=95), camera, det_ids, real_redis)
        rows = (
            await db_session.scalars(
                select(EventNotifyDecision).where(EventNotifyDecision.event_id == event.id)
            )
        ).all()
        assert len(rows) == 1, [str(r) for r in rows]


class TestAbsenceIsNotFalse:
    """The presence contract, on the arm with no row at all.

    ``backend/api/schemas/events.py`` gives ``notify`` the same
    ``exclude_if=lambda v: v is None`` rule as ``verification``, and
    ``backend/tests/integration/test_p04_event_verifications.py`` already owns
    that shape for the verification key. What ISS-001 adds is the pairing: the
    absence arm and the false arm must be told apart by the SAME consumer
    reading the SAME key - which is why this class sits next to the false arm
    above rather than reusing p04's file.
    """

    async def test_legacy_event_has_no_key_on_either_surface(self, client, db_session, camera):
        """A hand-inserted Event - no verification row, no decision row -
        renders with NO notify key.

        Deliberately not written by the analyzer: "legacy" is exactly an event
        the analyzer never produced, and the row is what the absence is about.
        """
        event = Event(
            batch_id=f"legacy-{uuid.uuid4().hex[:8]}",
            camera_id=camera.id,
            started_at=datetime(2026, 10, 4, 3, 0, tzinfo=UTC),
            risk_score=95,  # high risk and NO decision: absence must not read as "quiet"
        )
        db_session.add(event)
        await db_session.commit()

        assert await _decision_row(db_session, event.id) is None

        item, detail = await _surfaces(client, camera, event.id)
        assert "notify" not in item, (
            "a legacy item carried notify=null - absence leaked as a value and a "
            "consumer can no longer tell 'never decided' from 'decided: do not page'"
        )
        assert "notify" not in detail, "the detail surface rendered a null notify"

    async def test_replay_writes_the_event_but_no_decision(
        self, client, db_session, camera, real_redis
    ):
        """Replay's half of the contract, on the live DB.

        ``analyze_batch`` under ``replay=True`` runs the identical pipeline and
        writes a real scored event + verification row, but ``_notify_decision``
        is gated on ``not self._replay`` - replay never reads the owner's
        notification settings and never writes outward. So the event EXISTS and
        carries no decision, which is precisely the case the absence rule
        exists for.

        This is the pin for the tempting wrong fix: nothing in the read path
        may re-derive notify from the stored score. A score-95 replay row under
        a "derive at read time" implementation would render ``notify=true``
        here and this test would fail - correctly, because the system never
        decided anything about that event. (The unit tier pins the other
        direction - replay reads no notification tables - in
        ``backend/tests/unit/services/test_vlm_analyzer.py``
        ``test_replay_makes_no_decision_and_reads_no_notification_tables``.)
        """
        det_ids = await _mk_detections(db_session, camera)
        event = await _analyze(
            make_verdict(risk_score=95), camera, det_ids, real_redis, replay=True
        )

        # the pipeline ran: a real scored event exists
        assert event.risk_score == 95
        assert event.risk_level == "critical"

        assert await _decision_row(db_session, event.id) is None, (
            "replay persisted a notify decision - replay must write nothing outward"
        )

        item, detail = await _surfaces(client, camera, event.id)
        assert "notify" not in item, "a replay row rendered a decision it never made"
        assert "notify" not in detail, "a replay row rendered a decision it never made"
