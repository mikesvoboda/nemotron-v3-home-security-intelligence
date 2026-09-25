"""P0.3 -> P0.4 producer wiring, pinned against the live schema (plan Task 4
box 4's "pin with an integration test").

The unit tier (test_p03_constrained_verdict.py) proves the analyzer
CONSTRUCTS the right EventVerification objects; this file proves those
objects are the same class the live Postgres schema accepts - real
verdict CHECK constraint, real engine/model_id NOT NULLs, real FK +
CASCADE - written through the analyzer's own producer method. Synthetic
rows only (D10); no LLM, no network.

Same-session compose rule (E11): run with the live test PG up:
    TEST_DATABASE_URL=... uv run pytest backend/tests/integration/test_p03_verification_producer.py -n0
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from backend.models.camera import Camera
from backend.models.event import Event
from backend.models.event_verification import EventVerification
from backend.services.nemotron_analyzer import NemotronAnalyzer, VerificationRowOutcome

pytestmark = pytest.mark.integration


class _LabeledProducer:
    """The producer method reads only self._verification_engine/_id; this
    stand-in lets the integration test drive the REAL method unbound -
    no production reshaping, no analyzer construction (which needs Redis)."""

    _verification_engine = "llama.cpp"
    _verification_model_id = "Nemotron-3-Nano-30B-A3B-Q4_K_M"

    _row = staticmethod(NemotronAnalyzer._verification_row)

    def row(self, event, outcome, *, summary):
        return self._row(self, event, outcome, summary=summary)


def producer() -> _LabeledProducer:
    return _LabeledProducer()


@pytest.fixture
async def async_client(client):
    # same local alias test_p04_event_verifications.py uses over the shared
    # `client` fixture
    yield client


@pytest.fixture
async def camera(db_session):
    cam = Camera(
        id=f"p03cam-{uuid.uuid4().hex[:8]}",
        name=f"p03-{uuid.uuid4().hex[:8]}",
        folder_path="/export/foscam/p03",
    )
    db_session.add(cam)
    await db_session.commit()
    return cam


async def _mk_null_event(db_session, camera):
    """A P0.3 fail-closed event: NULL score/level is legal at the column
    (premise-checked in the ledger) and REST-safe (P0.25)."""
    event = Event(
        batch_id=str(uuid.uuid4()),
        camera_id=camera.id,
        started_at=datetime(2026, 9, 25, 9, 0, tzinfo=UTC),
        risk_score=None,
        risk_level=None,
        summary="Verification unavailable - analysis service error",
    )
    db_session.add(event)
    await db_session.commit()
    return event


class TestProducerRoundTrip:
    async def test_fail_closed_row_round_trips_the_live_schema(self, db_session, camera):
        """The analyzer's producer output PASSES the live table's real
        constraints: verdict CHECK admits 'verification_failed', the NOT NULL
        engine/model_id the analyzer ships, honest NULL latency (a transport
        failure before any completed call)."""
        event = await _mk_null_event(db_session, camera)

        row = producer().row(
            event,
            VerificationRowOutcome(flagged=True, raw_completion="", latency_ms=None),
            summary=event.summary,
        )
        db_session.add(row)
        await db_session.commit()

        stored = await db_session.scalar(
            select(EventVerification).where(EventVerification.event_id == event.id)
        )
        assert stored is not None
        assert stored.verdict == "verification_failed"
        assert stored.engine == "llama.cpp"
        assert stored.model_id == "Nemotron-3-Nano-30B-A3B-Q4_K_M"
        assert stored.latency_ms is None
        assert stored.scene_description is None, (
            "no raw text existed - honest empty, never invented"
        )

    async def test_fire_confirmed_row_carries_the_honest_scene_text(self, db_session, camera):
        """Non-LLM evidence (fire override): verdict 'confirmed' with the
        event summary as scene text - the row and the 100/critical badge
        agree (spec §4)."""
        event = await _mk_null_event(db_session, camera)
        event.risk_score = 100
        event.risk_level = "critical"
        event.summary = "FIRE DETECTED - Immediate response required"
        await db_session.commit()

        row = producer().row(
            event,
            VerificationRowOutcome(flagged=False, raw_completion="", latency_ms=812),
            summary=event.summary,
        )
        db_session.add(row)
        await db_session.commit()

        stored = await db_session.scalar(
            select(EventVerification).where(EventVerification.event_id == event.id)
        )
        assert stored.verdict == "confirmed"
        assert "FIRE DETECTED" in stored.scene_description
        assert stored.latency_ms == 812

    async def test_event_detail_renders_the_produced_row(self, async_client, db_session, camera):
        """The composition the UI consumes: a NULL-score event WITH a
        producer row serializes without crash - risk_score null, the
        verification object present (P0.25 no-crash + P0.4 present-when-row
        on one real fail-closed-shaped record)."""
        event = await _mk_null_event(db_session, camera)
        row = producer().row(
            event,
            VerificationRowOutcome(
                flagged=True, raw_completion="prose that never parsed", latency_ms=431
            ),
            summary=event.summary,
        )
        db_session.add(row)
        await db_session.commit()

        detail = await async_client.get(f"/api/events/{event.id}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["risk_score"] is None
        assert body["verification"] is not None
        assert body["verification"]["verdict"] == "verification_failed"

    async def test_retention_sweeps_producer_rows(self, db_session, camera):
        """A producer row must die with its event (CASCADE, the ledgered
        P0.4 decision) - the fail-closed path writes one per failed verdict,
        so an orphan leak here would grow unboundedly."""
        from sqlalchemy import delete, text

        from backend.core.database import get_engine

        event = await _mk_null_event(db_session, camera)
        row = producer().row(
            event,
            VerificationRowOutcome(flagged=True, raw_completion="x", latency_ms=None),
            summary=event.summary,
        )
        db_session.add(row)
        await db_session.commit()

        async with get_engine().begin() as conn:
            await conn.execute(delete(Event).where(Event.id == event.id))
        async with get_engine().connect() as conn:
            orphans = await conn.scalar(
                text(  # nosemgrep: avoid-sqlalchemy-text
                    "SELECT count(*) FROM event_verifications WHERE event_id = :eid"
                ),
                {"eid": event.id},
            )
        assert orphans == 0
        assert (
            await db_session.scalar(
                select(func.count())
                .select_from(EventVerification)
                .where(EventVerification.event_id == event.id)
            )
            == 0
        )
