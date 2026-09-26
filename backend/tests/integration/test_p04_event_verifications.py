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
    # dict-merge so a caller can OVERRIDE the defaults (a 1.6 filter test
    # needs a NULL-scored event, which `**kw` against a literal `risk_score=`
    # keyword would collide on).
    event = Event(
        batch_id=str(uuid.uuid4()),
        camera_id=camera.id,
        started_at=datetime(2026, 9, 25, 8, 0, tzinfo=UTC),
        **{"risk_score": 75, **kw},
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


# ---------------------------------------------------------------------------
# 1.6 backend prerequisite: GET /events gains a `verdict` filter.
#
# The frontend's verdict filter (plan Task 6) cannot be honest without it.
# Three rulings shape the pins:
#   * it filters on the JOIN to event_verifications, not on Event columns -
#     the verdict lives in exactly one place (F11: one source of truth), so
#     the filter reads that place;
#   * `verdict=none` is a first-class value, not an absent param: "which
#     events have NOT been verified yet" is the question an operator asks
#     first in a fresh vlm deployment, and it is not expressible as any of
#     the four verdicts;
#   * an unknown value RAISES (422) rather than returning an empty list. A
#     typo that quietly filters everything out reads as "no rejected
#     events", which is a false all-clear - the same no-silent-fallback rule
#     1.5 applied to PIPELINE_MODE.
# ---------------------------------------------------------------------------


@pytest.fixture
async def verdict_camera(db_session):
    """A private camera per test: the filter tests count totals, so they
    must not share a camera with any other test's events."""
    suffix = uuid.uuid4().hex[:8]
    cam = Camera(
        id=f"verdictcam-{suffix}",
        name=f"verdict-{suffix}",
        folder_path=f"/export/foscam/verdict-{suffix}",
    )
    db_session.add(cam)
    await db_session.commit()
    return cam


@pytest.fixture
async def verdict_fixture(db_session, verdict_camera):
    """One event per verdict + one unverified event, on one camera."""
    confirmed = await _mk_event(db_session, verdict_camera, summary="confirmed one")
    await _mk_verification(db_session, confirmed, verdict="confirmed")

    rejected = await _mk_event(db_session, verdict_camera, summary="rejected one")
    await _mk_verification(db_session, rejected, verdict="rejected")

    failed = await _mk_event(
        db_session, verdict_camera, summary="failed one", risk_score=None, risk_level=None
    )
    await _mk_verification(
        db_session, failed, verdict="verification_failed", scene_description=None
    )

    unverified = await _mk_event(db_session, verdict_camera, summary="never verified")

    return {
        "confirmed": confirmed,
        "rejected": rejected,
        "failed": failed,
        "unverified": unverified,
    }


class TestVerdictFilter:
    async def test_filter_returns_only_that_verdict(
        self, async_client, verdict_camera, verdict_fixture
    ):
        resp = await async_client.get(
            "/api/events", params={"camera_id": verdict_camera.id, "verdict": "rejected"}
        )
        assert resp.status_code == 200
        data = resp.json()
        ids = {i["id"] for i in data["items"]}
        assert ids == {verdict_fixture["rejected"].id}
        # The pagination total is filtered too: a count that ignores the
        # filter would make the UI show "4 events" above a 1-event list.
        assert data["pagination"]["total"] == 1

    async def test_none_selects_events_with_no_verification_row(
        self, async_client, verdict_camera, verdict_fixture
    ):
        resp = await async_client.get(
            "/api/events", params={"camera_id": verdict_camera.id, "verdict": "none"}
        )
        assert resp.status_code == 200
        ids = {i["id"] for i in resp.json()["items"]}
        assert ids == {verdict_fixture["unverified"].id}

    async def test_verification_failed_verdict_is_filterable(
        self, async_client, verdict_camera, verdict_fixture
    ):
        """The NULL-scored events are exactly the ones an operator must
        find, so the filter must reach them by verdict - they are not
        findable by any risk_level filter (both columns are NULL)."""
        resp = await async_client.get(
            "/api/events",
            params={"camera_id": verdict_camera.id, "verdict": "verification_failed"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert [i["id"] for i in items] == [verdict_fixture["failed"].id]
        assert items[0]["risk_score"] is None

    async def test_confirmed_verdict_needs_no_camera_scope(self, async_client, verdict_fixture):
        """Unscoped (no camera_id) — and written so it cannot pass
        vacuously: FastAPI IGNORES an unknown query param, so "my event came
        back" is true even with no filter at all. The teeth are 'nothing but
        confirmed came back' and 'my rejected event did not'."""
        resp = await async_client.get("/api/events", params={"verdict": "confirmed", "limit": 100})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert verdict_fixture["confirmed"].id in {i["id"] for i in items}
        assert verdict_fixture["rejected"].id not in {i["id"] for i in items}
        assert all(i["verification"]["verdict"] == "confirmed" for i in items)

    async def test_unknown_verdict_raises_rather_than_returning_empty(
        self, async_client, verdict_camera
    ):
        resp = await async_client.get(
            "/api/events", params={"camera_id": verdict_camera.id, "verdict": "deffinitly"}
        )
        assert resp.status_code == 422, (
            "a typo'd verdict must not read as 'no events with that verdict'"
        )

    async def test_combined_with_risk_level_filter(self, async_client, verdict_camera):
        """The verdict filter composes with the existing filters - the
        frontend's chip bar sends several at once."""
        resp = await async_client.get(
            "/api/events",
            params={"camera_id": verdict_camera.id, "verdict": "confirmed", "risk_level": "high"},
        )
        assert resp.status_code == 200
        assert all(i["risk_level"] == "high" for i in resp.json()["items"])

    async def test_search_endpoint_gains_the_same_param(
        self, async_client, verdict_camera, verdict_fixture
    ):
        """`/api/events/search` is what the list view's text box calls, so a
        verdict filter that only exists on `/api/events` would be lost the
        moment the user types. Non-vacuous by construction: the text query
        matches three of the four events ("one"), so the assertion that only
        the REJECTED one survives is the filter's, not the text search's."""
        resp = await async_client.get(
            "/api/events/search",
            params={"q": "one", "camera_id": verdict_camera.id, "verdict": "rejected"},
        )
        assert resp.status_code == 200
        ids = {i["id"] for i in resp.json()["results"]}
        assert ids == {verdict_fixture["rejected"].id}
