"""P0.4 (spec §4) on the LIVE test Postgres: the `event_verifications` table
and the `verification` REST field, end to end.

Doctrine pinned here (spec §4 / plan Task 4 boxes 1-3):
  * create-new-tables-only: this repo has NO alembic chain (#4465); schema
    ships via create_all, which creates MISSING tables on an existing DB and
    never alters. Pinned by dropping the table under a populated DB and
    re-running create_all: the table returns, existing rows untouched.
  * retention: cleanup hard-deletes Events (Core DELETE). The verification
    FK is ON DELETE CASCADE, so an event delete cannot leave an orphan and
    cannot 500 on an FK violation. (Cascade was DECIDED over a FK-less
    provenance row - eval items are self-contained (D7), so nothing needs
    to survive retention here; the call is ledgered.)
  * payload: legacy event -> `verification` KEY ABSENT on list + detail
    (byte-identity); verified event -> populated object. `verification` is
    a valid sparse-fieldset field.

Fabricated rows only; media paths are fake strings (no file IO on this
tier); no real imagery anywhere.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select, text

from backend.models.camera import Camera
from backend.models.event import Event
from backend.models.event_verification import EventVerification

pytestmark = pytest.mark.integration


@pytest.fixture
async def async_client(client):
    yield client


@pytest.fixture
async def camera(db_session):
    cam = Camera(
        id=f"p04cam-{uuid.uuid4().hex[:8]}",
        name=f"p04-{uuid.uuid4().hex[:8]}",
        folder_path="/export/foscam/p04",
    )
    db_session.add(cam)
    await db_session.commit()
    return cam


async def _mk_event(db_session, camera, **kw):
    event = Event(
        batch_id=str(uuid.uuid4()),
        camera_id=camera.id,
        started_at=datetime(2026, 9, 25, 8, 0, tzinfo=UTC),
        risk_score=75,
        **kw,
    )
    db_session.add(event)
    await db_session.commit()
    return event


async def _mk_verification(db_session, event, **kw):
    row = EventVerification(
        event_id=event.id,
        **{"verdict": "confirmed", "engine": "llama.cpp", "model_id": "qwen3-vl-4b", **kw},
    )
    db_session.add(row)
    await db_session.commit()
    return row


class TestCreateAllDoctrine:
    async def test_create_all_recreates_table_on_existing_db(self, db_session, camera):
        """DROP the verification table under a populated DB, run create_all
        again: the table comes back and pre-existing rows survive - exactly
        what 'create_all creates new tables, never alters' means for shipping
        this model to an existing home DB."""
        from backend.core.database import get_engine
        from backend.models.camera import Base as ModelsBase

        event = await _mk_event(db_session, camera)

        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text("DROP TABLE IF EXISTS event_verifications CASCADE")
            )  # nosemgrep: avoid-sqlalchemy-text
        async with engine.begin() as conn:
            await conn.run_sync(ModelsBase.metadata.create_all)

        async with engine.connect() as conn:
            found = (
                await conn.execute(
                    text(  # nosemgrep: avoid-sqlalchemy-text
                        "SELECT 1 FROM information_schema.tables "
                        "WHERE table_name='event_verifications'"
                    )
                )
            ).scalar()
            assert found == 1, "create_all must create the new table on the existing DB"
            rows = (await conn.execute(select(func.count()).select_from(Event))).scalar()
            assert rows >= 1, "existing rows must survive"
        # the fresh table is usable end over the just-recreated schema
        await _mk_verification(db_session, event)
        assert (
            await db_session.scalar(
                select(func.count()).where(EventVerification.event_id == event.id)
            )
            == 1
        )


class TestRetentionCascade:
    async def test_event_hard_delete_cascades_verification_rows(self, db_session, camera):
        """cleanup_service's Core event delete must not orphan (and must not
        FK-500): the DB-level ON DELETE CASCADE sweeps verification rows."""
        from backend.core.database import get_engine

        event = await _mk_event(db_session, camera)
        await _mk_verification(db_session, event)

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


class TestRestVerificationField:
    async def test_legacy_event_absent_on_list_and_detail(self, async_client, db_session, camera):
        event = await _mk_event(db_session, camera)
        lst = await async_client.get("/api/events", params={"camera_id": camera.id})
        assert lst.status_code == 200
        item = next(i for i in lst.json()["items"] if i["id"] == event.id)
        assert "verification" not in item, (
            "legacy payload must stay byte-identical (absent, not null)"
        )

        detail = await async_client.get(f"/api/events/{event.id}")
        assert detail.status_code == 200
        assert "verification" not in detail.json()

    async def test_verified_event_populated_on_list_and_detail(
        self, async_client, db_session, camera
    ):
        event = await _mk_event(db_session, camera)
        await _mk_verification(
            db_session,
            event,
            verdict="verification_failed",
            scene_description=None,
            criteria=[{"name": "person_present", "passed": False, "evidence": "blur"}],
            key_frame_detection_ids=None,
            latency_ms=2500,
        )
        lst = await async_client.get("/api/events", params={"camera_id": camera.id})
        item = next(i for i in lst.json()["items"] if i["id"] == event.id)
        assert item["verification"]["verdict"] == "verification_failed"
        assert item["verification"]["engine"] == "llama.cpp"
        assert item["verification"]["criteria"][0]["name"] == "person_present"

        detail = await async_client.get(f"/api/events/{event.id}")
        ver = detail.json()["verification"]
        assert ver["model_id"] == "qwen3-vl-4b"
        assert ver["latency_ms"] == 2500

    async def test_sparse_fieldset_accepts_verification(self, async_client, db_session, camera):
        """`fields=verification` is ACCEPTED (the 400 allowlist) and renders.
        NB the route's pre-existing sparse-fieldset contract: a selection
        that omits EventResponse's required fields (camera_id/started_at)
        500s at HEAD too - a caller selects a superset of the required keys,
        so the test does the same and only pins verification's behavior."""
        event = await _mk_event(db_session, camera)
        await _mk_verification(db_session, event, verdict="rejected")
        resp = await async_client.get(
            "/api/events",
            params={"camera_id": camera.id, "fields": "id,camera_id,started_at,verification"},
        )
        assert resp.status_code == 200
        item = next(i for i in resp.json()["items"] if i["id"] == event.id)
        assert item["verification"]["verdict"] == "rejected"
        # (unselected optional fields still ride the envelope as null -
        # pre-existing EventListResponse dump behavior, not this slice's
        # contract; the verification KEY itself is the part under test)

    async def test_legacy_sparse_selection_still_drops_absent_key(
        self, async_client, db_session, camera
    ):
        event = await _mk_event(db_session, camera)
        resp = await async_client.get(
            "/api/events",
            params={"camera_id": camera.id, "fields": "id,camera_id,started_at,verification"},
        )
        item = next(i for i in resp.json()["items"] if i["id"] == event.id)
        assert "verification" not in item, "requested-but-absent renders as absent (not null)"
