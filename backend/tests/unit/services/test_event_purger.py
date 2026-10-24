"""Unit tests for EventPurger (`backend/services/event_purger.py`, B4.4)."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

from backend.models.alert import Alert, AlertEvent, AlertRule, AlertSeverityEnum, AlertStatusEnum
from backend.models.audit import AuditLog
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.entity import Entity
from backend.models.event import Event
from backend.models.event_detection import EventDetection
from backend.models.event_notify import EventNotifyDecision
from backend.models.event_verification import EventVerification
from backend.models.face_identity import FaceDetectionEvent, FaceEmbedding, KnownPerson
from backend.models.household import HouseholdMember, MemberRole, PersonEmbedding, TrustLevel
from backend.models.household_org import Household
from backend.models.property import Property
from backend.services.batch_aggregator import BatchAggregator, recover_orphaned_detections
from backend.services.cleanup_service import CleanupService
from backend.services.event_purger import EventPurger, purge_deadline_for_event
from backend.services.event_service import EventService

pytestmark = pytest.mark.unit


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type: Any, _compiler: Any, **_kw: Any) -> str:
    return "JSON"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(_type: Any, _compiler: Any, **_kw: Any) -> str:
    return "VARCHAR(36)"


@compiles(TSVECTOR, "sqlite")
def _compile_tsvector_sqlite(_type: Any, _compiler: Any, **_kw: Any) -> str:
    return "TEXT"


@compiles(ARRAY, "sqlite")
def _compile_array_sqlite(_type: Any, _compiler: Any, **_kw: Any) -> str:
    return "JSON"


class _AsyncSQLiteSession:
    """Thin async wrapper around a real SQLite SQLAlchemy Session for unit tests."""

    def __init__(self, sync_session: Session) -> None:
        self._s = sync_session

    def add(self, instance: Any) -> None:
        self._s.add(instance)

    def add_all(self, instances: Any) -> None:
        self._s.add_all(instances)

    async def execute(self, statement: Any, params: Any = None, **kwargs: Any) -> Any:
        return self._s.execute(statement, params=params, **kwargs)

    async def scalars(self, statement: Any, params: Any = None, **kwargs: Any) -> Any:
        return self._s.scalars(statement, params=params, **kwargs)

    async def get(self, entity: Any, ident: Any, **kwargs: Any) -> Any:
        return self._s.get(entity, ident, **kwargs)

    async def flush(self) -> None:
        self._s.flush()

    async def commit(self) -> None:
        self._s.commit()

    async def refresh(self, instance: Any) -> None:
        self._s.refresh(instance)

    @contextlib.asynccontextmanager
    async def begin_nested(self):
        with self._s.begin_nested():
            yield


@pytest.fixture
def db_session(tmp_path: Path):
    """Create an isolated SQLite session with all required tables for EventPurger."""
    db_file = tmp_path / "purger_unit.db"
    engine = create_engine(f"sqlite:///{db_file}", future=True)

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    tables = [
        Household.__table__,
        Property.__table__,
        Camera.__table__,
        Event.__table__,
        EventVerification.__table__,
        EventNotifyDecision.__table__,
        Detection.__table__,
        EventDetection.__table__,
        Entity.__table__,
        KnownPerson.__table__,
        FaceEmbedding.__table__,
        FaceDetectionEvent.__table__,
        HouseholdMember.__table__,
        PersonEmbedding.__table__,
        AlertRule.__table__,
        Alert.__table__,
        AlertEvent.__table__,
        AuditLog.__table__,
    ]
    with engine.begin() as conn:
        for tbl in tables:
            tbl.create(conn, checkfirst=True)

    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as sync_sess:
        cam = Camera(
            id="front_door",
            name="Front Door",
            folder_path="/export/foscam/front_door",
            status="online",
        )
        sync_sess.add(cam)
        sync_sess.commit()
        yield _AsyncSQLiteSession(sync_sess)

    engine.dispose()


class TestPurgeDeadlineForEvent:
    """Tests for purge_deadline_for_event deadline math (4n-trash.md)."""

    def test_earlier_of_trash_and_general_retention(self) -> None:
        base = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
        # Trashed 20 days after start: started + 30d is earlier than deleted + 30d
        started = base
        deleted = base + timedelta(days=20)
        deadline = purge_deadline_for_event(
            deleted,
            started,
            retention_days=30,
            trash_retention_days=30,
        )
        assert deadline == started + timedelta(days=30)

        # Trashed 1 day after start with 7-day trash retention: deleted + 7d is earlier
        deadline2 = purge_deadline_for_event(
            base + timedelta(days=1),
            base,
            retention_days=30,
            trash_retention_days=7,
        )
        assert deadline2 == base + timedelta(days=8)

    def test_zero_trash_retention_disables_only_trash_clock(self) -> None:
        base = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
        deleted = base + timedelta(days=5)
        deadline = purge_deadline_for_event(
            deleted,
            base,
            retention_days=30,
            trash_retention_days=0,
        )
        assert deadline == base + timedelta(days=30)


class TestEventPurgerUnit:
    """Unit tests for EventPurger.purge invariants and ordering."""

    @pytest.mark.asyncio
    async def test_refuses_live_event_and_purges_trashed_event_with_derived_rows(
        self, db_session: _AsyncSQLiteSession, tmp_path: Path
    ) -> None:
        now = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
        clip_file = tmp_path / "clip1.mp4"
        img_file = tmp_path / "img1.jpg"
        thumb_file = tmp_path / "thumb1.jpg"
        shared_file = tmp_path / "shared.jpg"
        for f in (clip_file, img_file, thumb_file, shared_file):
            f.write_bytes(b"media-bytes")

        # Event 1: in Trash, with exclusive detection d1 and shared-file detection d_shared_file
        ev_trashed = Event(
            batch_id="b-trashed",
            camera_id="front_door",
            started_at=now - timedelta(hours=2),
            ended_at=now - timedelta(hours=1),
            risk_score=65,
            risk_level="high",
            summary="Trashed event summary that must not leak to audit log",
            clip_path=str(clip_file),
            deleted_at=now - timedelta(minutes=30),
        )
        # Event 2: live (not in Trash), has d_surviving using shared_file
        ev_live = Event(
            batch_id="b-live",
            camera_id="front_door",
            started_at=now - timedelta(minutes=20),
            ended_at=now - timedelta(minutes=10),
            risk_score=30,
            risk_level="low",
            summary="Live event",
            deleted_at=None,
        )
        db_session.add_all([ev_trashed, ev_live])
        await db_session.flush()

        d1 = Detection(
            camera_id="front_door",
            file_path=str(img_file),
            thumbnail_path=str(thumb_file),
            detected_at=now - timedelta(hours=2),
            object_type="person",
            confidence=0.92,
        )
        d_shared_file = Detection(
            camera_id="front_door",
            file_path=str(shared_file),
            thumbnail_path=None,
            detected_at=now - timedelta(hours=2),
            object_type="person",
            confidence=0.88,
        )
        d_surviving = Detection(
            camera_id="front_door",
            file_path=str(shared_file),
            thumbnail_path=None,
            detected_at=now - timedelta(minutes=15),
            object_type="person",
            confidence=0.90,
        )
        db_session.add_all([d1, d_shared_file, d_surviving])
        await db_session.flush()

        db_session.add_all(
            [
                EventDetection(event_id=ev_trashed.id, detection_id=d1.id),
                EventDetection(event_id=ev_trashed.id, detection_id=d_shared_file.id),
                EventDetection(event_id=ev_live.id, detection_id=d_surviving.id),
            ]
        )

        # Entity created from d1 (should be deleted) and entity from d_surviving (should stay)
        ent_purged = Entity(
            entity_type="person",
            trust_status="unknown",
            primary_detection_id=d1.id,
        )
        ent_kept = Entity(
            entity_type="person",
            trust_status="unknown",
            primary_detection_id=d_surviving.id,
        )
        db_session.add_all([ent_purged, ent_kept])

        # FaceDetectionEvent inside ev_trashed window (deleted) and outside window (kept)
        face_in_window = FaceDetectionEvent(
            camera_id="front_door",
            timestamp=now - timedelta(hours=1, minutes=30),
            bbox={"x1": 0, "y1": 0, "x2": 10, "y2": 10},
            embedding=b"\x00" * 16,
            is_unknown=True,
            quality_score=0.8,
        )
        face_outside_window = FaceDetectionEvent(
            camera_id="front_door",
            timestamp=now - timedelta(minutes=5),
            bbox={"x1": 0, "y1": 0, "x2": 10, "y2": 10},
            embedding=b"\x00" * 16,
            is_unknown=True,
            quality_score=0.8,
        )
        db_session.add_all([face_in_window, face_outside_window])

        # Enrolled references: KnownPerson FaceEmbedding + HouseholdMember PersonEmbedding
        known = KnownPerson(name="Alice", is_household_member=True)
        member = HouseholdMember(
            name="Alice",
            role=MemberRole.RESIDENT,
            trusted_level=TrustLevel.FULL,
        )
        db_session.add_all([known, member])
        await db_session.flush()

        face_ref = FaceEmbedding(
            person_id=known.id,
            embedding=b"\x01" * 16,
            quality_score=0.95,
            source_image_path=str(img_file),
        )
        person_ref = PersonEmbedding(
            member_id=member.id,
            embedding=b"\x02" * 16,
            source_event_id=ev_trashed.id,
            confidence=0.95,
        )
        db_session.add_all([face_ref, person_ref])
        await db_session.commit()

        purger = EventPurger()
        report = await purger.purge(
            [ev_trashed.id, ev_live.id, 999999],
            reason="user",
            session=db_session,  # type: ignore[arg-type]
        )
        await db_session.commit()

        assert report.purged == (ev_trashed.id,)
        assert report.refused == (ev_live.id,)
        assert report.not_found == (999999,)
        assert report.kept == ()
        assert not clip_file.exists()
        assert not img_file.exists()
        assert not thumb_file.exists()
        # Shared file referenced by d_surviving is preserved
        assert shared_file.exists()

        # Purged event and its detections are gone; live event and surviving detection remain
        assert await db_session.get(Event, ev_trashed.id) is None
        assert await db_session.get(Event, ev_live.id) is not None
        assert await db_session.get(Detection, d1.id) is None
        assert await db_session.get(Detection, d_shared_file.id) is None
        assert await db_session.get(Detection, d_surviving.id) is not None

        # Derived Entity and FaceDetectionEvent in window are gone; outside ones remain
        assert await db_session.get(Entity, ent_purged.id) is None
        assert await db_session.get(Entity, ent_kept.id) is not None
        assert await db_session.get(FaceDetectionEvent, face_in_window.id) is None
        assert await db_session.get(FaceDetectionEvent, face_outside_window.id) is not None

        # Enrolled reference embeddings stay with their links cleared
        await db_session.refresh(face_ref)
        await db_session.refresh(person_ref)
        assert face_ref.source_image_path is None
        assert person_ref.source_event_id is None

        # Content-free audit entry written
        audits = (
            await db_session.scalars(select(AuditLog).where(AuditLog.action == "event_purged"))
        ).all()
        assert len(audits) == 1
        assert audits[0].resource_id == str(ev_trashed.id)
        assert audits[0].details == {"event_id": ev_trashed.id, "reason": "user"}
        assert "Trashed event summary" not in str(audits[0].details)

    @pytest.mark.asyncio
    async def test_failed_file_deletion_leaves_event_in_trash_and_reported(
        self, db_session: _AsyncSQLiteSession, tmp_path: Path
    ) -> None:
        now = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
        locked_file = tmp_path / "locked.jpg"
        locked_file.write_bytes(b"locked")

        ev = Event(
            batch_id="b-locked",
            camera_id="front_door",
            started_at=now - timedelta(hours=1),
            ended_at=now,
            risk_score=50,
            risk_level="medium",
            summary="Locked event",
            deleted_at=now - timedelta(minutes=10),
        )
        db_session.add(ev)
        await db_session.flush()

        det = Detection(
            camera_id="front_door",
            file_path=str(locked_file),
            detected_at=now - timedelta(hours=1),
            object_type="person",
            confidence=0.9,
        )
        db_session.add(det)
        await db_session.flush()
        db_session.add(EventDetection(event_id=ev.id, detection_id=det.id))
        await db_session.commit()

        purger = EventPurger()
        with patch.object(
            EventPurger,
            "_unlink_path",
            side_effect=PermissionError("read-only fs"),
            autospec=True,
        ):
            report = await purger.purge([ev.id], reason="user", session=db_session)  # type: ignore[arg-type]
            await db_session.commit()

        assert report.purged == ()
        assert report.kept == (ev.id,)
        assert str(locked_file) in report.files_failed
        # Event and detection remain in Trash for retry
        surviving_ev = await db_session.get(Event, ev.id)
        assert surviving_ev is not None
        assert surviving_ev.deleted_at is not None
        assert await db_session.get(Detection, det.id) is not None

    @pytest.mark.asyncio
    async def test_alert_repointed_when_first_event_purged_and_removed_when_all_purged(
        self, db_session: _AsyncSQLiteSession
    ) -> None:
        now = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
        ev1 = Event(
            batch_id="b-alert-1",
            camera_id="front_door",
            started_at=now - timedelta(minutes=20),
            ended_at=now - timedelta(minutes=19),
            risk_score=80,
            risk_level="high",
            summary="First event",
            deleted_at=now - timedelta(minutes=5),
        )
        ev2 = Event(
            batch_id="b-alert-2",
            camera_id="front_door",
            started_at=now - timedelta(minutes=10),
            ended_at=now - timedelta(minutes=9),
            risk_score=82,
            risk_level="high",
            summary="Second event",
            deleted_at=None,
        )
        db_session.add_all([ev1, ev2])
        await db_session.flush()

        alert = Alert(
            event_id=ev1.id,
            last_event_id=ev2.id,
            last_seen_at=ev2.started_at,
            match_count=2,
            severity=AlertSeverityEnum.HIGH,
            status=AlertStatusEnum.OPEN,
            dedup_key="front_door:person:rule1",
        )
        db_session.add(alert)
        await db_session.flush()
        db_session.add_all(
            [
                AlertEvent(alert_id=alert.id, event_id=ev1.id),
                AlertEvent(alert_id=alert.id, event_id=ev2.id),
            ]
        )
        await db_session.commit()

        purger = EventPurger()
        # Purge ev1 while ev2 is still live -> alert is repointed to ev2 and stays open
        r1 = await purger.purge([ev1.id], reason="user", session=db_session)  # type: ignore[arg-type]
        await db_session.commit()
        assert r1.purged == (ev1.id,)

        await db_session.refresh(alert)
        assert alert.event_id == ev2.id
        assert alert.last_event_id == ev2.id
        assert alert.match_count == 1
        assert alert.status == AlertStatusEnum.OPEN

        # Now trash ev2 and purge it -> alert is removed when no event is left
        ev2.deleted_at = now
        await db_session.commit()

        r2 = await purger.purge([ev2.id], reason="user", session=db_session)  # type: ignore[arg-type]
        await db_session.commit()
        assert r2.purged == (ev2.id,)
        assert r2.rows_removed["alerts"] == 1
        assert await db_session.get(Alert, alert.id) is None

    @pytest.mark.asyncio
    async def test_alert_lifecycle_soft_delete_restore_and_purge(
        self, db_session: _AsyncSQLiteSession
    ) -> None:
        """An alert covering two events stays open when one is trashed, dismisses when both
        are trashed, does not reopen on restore, repoints when first is purged, and is removed
        when both are purged (4n-trash.md).
        """
        now = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
        ev1 = Event(
            batch_id="b-lc-1",
            camera_id="front_door",
            started_at=now - timedelta(minutes=20),
            ended_at=now - timedelta(minutes=19),
            risk_score=80,
            risk_level="high",
            summary="Event 1",
            deleted_at=None,
        )
        ev2 = Event(
            batch_id="b-lc-2",
            camera_id="front_door",
            started_at=now - timedelta(minutes=10),
            ended_at=now - timedelta(minutes=9),
            risk_score=82,
            risk_level="high",
            summary="Event 2",
            deleted_at=None,
        )
        db_session.add_all([ev1, ev2])
        await db_session.flush()

        alert = Alert(
            event_id=ev1.id,
            last_event_id=ev2.id,
            last_seen_at=ev2.started_at,
            match_count=2,
            severity=AlertSeverityEnum.HIGH,
            status=AlertStatusEnum.OPEN,
            dedup_key="front_door:person:lc",
        )
        db_session.add(alert)
        await db_session.flush()
        db_session.add_all(
            [
                AlertEvent(alert_id=alert.id, event_id=ev1.id),
                AlertEvent(alert_id=alert.id, event_id=ev2.id),
            ]
        )
        await db_session.commit()

        svc = EventService()
        # 1. Soft-delete ev1 -> ev2 is still live, so alert stays OPEN
        await svc.soft_delete_event(ev1.id, db_session)  # type: ignore[arg-type]
        await db_session.commit()
        await db_session.refresh(alert)
        assert alert.status == AlertStatusEnum.OPEN

        # 2. Soft-delete ev2 -> all events on alert are now in Trash -> DISMISSED
        await svc.soft_delete_event(ev2.id, db_session)  # type: ignore[arg-type]
        await db_session.commit()
        await db_session.refresh(alert)
        assert alert.status == AlertStatusEnum.DISMISSED
        assert alert.alert_metadata == {"dismissed_reason": "events moved to Trash"}

        # 3. Restore ev2 -> does NOT reopen the dismissed alert
        await svc.restore_event(ev2.id, db_session)  # type: ignore[arg-type]
        await db_session.commit()
        await db_session.refresh(alert)
        assert alert.status == AlertStatusEnum.DISMISSED

    @pytest.mark.asyncio
    async def test_fixed_clock_trash_retention_deadlines_and_zero_disables_trash_clock(
        self, db_session: _AsyncSQLiteSession
    ) -> None:
        """On a fixed clock the trash purge keeps an event trashed 29 days ago, purges one
        trashed 30 days ago, purges at started_at + retention_days when that is earlier,
        and 0 disables only the Trash clock (4n-trash.md).
        """
        fixed_now = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)

        # 1. Trashed 29 days ago (started 29 days ago) -> KEPT
        ev_29d = Event(
            batch_id="b-29d",
            camera_id="front_door",
            started_at=fixed_now - timedelta(days=29),
            ended_at=fixed_now - timedelta(days=29),
            risk_score=40,
            risk_level="medium",
            summary="Trashed 29d ago",
            deleted_at=fixed_now - timedelta(days=29),
        )
        # 2. Trashed 30 days ago (started 30 days ago) -> PURGED
        ev_30d = Event(
            batch_id="b-30d",
            camera_id="front_door",
            started_at=fixed_now - timedelta(days=30),
            ended_at=fixed_now - timedelta(days=30),
            risk_score=40,
            risk_level="medium",
            summary="Trashed 30d ago",
            deleted_at=fixed_now - timedelta(days=30),
        )
        # 3. Started 30 days ago, trashed 5 days ago -> PURGED at started_at + retention_days
        ev_general_earlier = Event(
            batch_id="b-gen-earlier",
            camera_id="front_door",
            started_at=fixed_now - timedelta(days=30),
            ended_at=fixed_now - timedelta(days=30),
            risk_score=40,
            risk_level="medium",
            summary="Started 30d ago, trashed 5d ago",
            deleted_at=fixed_now - timedelta(days=5),
        )
        db_session.add_all([ev_29d, ev_30d, ev_general_earlier])
        await db_session.commit()

        cleanup_30 = CleanupService(retention_days=30, trash_retention_days=30)
        assert cleanup_30.trash_retention_days == 30
        report = await cleanup_30.purge_expired_trash(
            db_session,  # type: ignore[arg-type]
            now=fixed_now,
        )
        await db_session.commit()

        assert set(report.purged) == {ev_30d.id, ev_general_earlier.id}
        assert await db_session.get(Event, ev_29d.id) is not None
        assert await db_session.get(Event, ev_30d.id) is None
        assert await db_session.get(Event, ev_general_earlier.id) is None

        # Now test trash_retention_days = 0: disables ONLY the Trash clock
        ev_trash_old_but_started_recent = Event(
            batch_id="b-zero-trash-kept",
            camera_id="front_door",
            started_at=fixed_now - timedelta(days=10),
            ended_at=fixed_now - timedelta(days=10),
            risk_score=40,
            risk_level="medium",
            summary="Started 10d ago, deleted 10d ago",
            deleted_at=fixed_now - timedelta(days=10),
        )
        ev_zero_general_due = Event(
            batch_id="b-zero-gen-due",
            camera_id="front_door",
            started_at=fixed_now - timedelta(days=30),
            ended_at=fixed_now - timedelta(days=30),
            risk_score=40,
            risk_level="medium",
            summary="Started 30d ago, deleted 2d ago",
            deleted_at=fixed_now - timedelta(days=2),
        )
        db_session.add_all([ev_trash_old_but_started_recent, ev_zero_general_due])
        await db_session.commit()

        cleanup_zero = CleanupService(retention_days=30, trash_retention_days=0)
        assert cleanup_zero.trash_retention_days == 0
        report_zero = await cleanup_zero.purge_expired_trash(
            db_session,  # type: ignore[arg-type]
            now=fixed_now,
        )
        await db_session.commit()

        assert report_zero.purged == (ev_zero_general_due.id,)
        assert await db_session.get(Event, ev_trash_old_but_started_recent.id) is not None
        assert await db_session.get(Event, ev_zero_general_due.id) is None

    @pytest.mark.asyncio
    async def test_after_purge_and_restart_orphan_recovery_finds_nothing(
        self, db_session: _AsyncSQLiteSession
    ) -> None:
        """After a purge and a restart, orphan recovery finds nothing (4n-trash.md)."""
        now = datetime.now(UTC)
        ev = Event(
            batch_id="b-orphan-purge",
            camera_id="front_door",
            started_at=now - timedelta(minutes=20),
            ended_at=now - timedelta(minutes=15),
            risk_score=60,
            risk_level="medium",
            summary="Event to purge",
            deleted_at=now - timedelta(minutes=5),
        )
        db_session.add(ev)
        await db_session.flush()

        # Detection older than ORPHAN_MIN_AGE_MINUTES (3 min) so it would be
        # eligible for orphan recovery if the purge left the detection row behind.
        det = Detection(
            camera_id="front_door",
            file_path="/cameras/orphan_check.jpg",
            detected_at=now - timedelta(minutes=15),
            object_type="person",
            confidence=0.92,
        )
        db_session.add(det)
        await db_session.flush()
        db_session.add(EventDetection(event_id=ev.id, detection_id=det.id))
        await db_session.commit()

        report = await EventPurger().purge([ev.id], reason="user", session=db_session)  # type: ignore[arg-type]
        await db_session.commit()
        assert report.purged == (ev.id,)
        assert report.rows_removed["detections"] == 1

        @contextlib.asynccontextmanager
        async def _mock_get_session():
            yield db_session

        aggregator = BatchAggregator()
        with patch(
            "backend.core.database.get_session",
            side_effect=_mock_get_session,
            autospec=True,
        ):
            recovered = await recover_orphaned_detections(aggregator)
        assert recovered == 0

    @pytest.mark.asyncio
    async def test_purge_deletes_notification_deliveries_when_the_table_exists(
        self, tmp_path: Path
    ) -> None:
        """Purging an alert's last event deletes its notification_deliveries rows.

        Regression for feature-check run 39901062658: `_delete_deliveries_if_present` bound a
        tuple into `text("... IN :alert_ids")`, which is one scalar in a list position -- every
        purge sent `IN $1` to Postgres, got `syntax error at or near "$1"`, and the method's
        own except swallowed it, returning 0 while the rows survived. The fix uses `delete()`
        + `in_()`, so this pins the deletion actually counting rows when the table is present
        (the B4.2-compatibility "table may not exist" path stays the except branch).
        """
        db_file = tmp_path / "purger_deliveries.db"
        engine = create_engine(f"sqlite:///{db_file}", future=True)

        @event.listens_for(engine, "connect")
        def _enable_fk(dbapi_conn, _conn_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        from backend.models.alert_delivery import (
            NotificationDelivery,
            Recipient,
            RecipientChannel,
        )
        from backend.models.user import User

        # The main fixture's table list (everything the purge path touches), plus the
        # delivery tables this test is for.
        tables = [
            Household.__table__,
            Property.__table__,
            Camera.__table__,
            Event.__table__,
            EventVerification.__table__,
            EventNotifyDecision.__table__,
            Detection.__table__,
            EventDetection.__table__,
            Entity.__table__,
            KnownPerson.__table__,
            FaceEmbedding.__table__,
            FaceDetectionEvent.__table__,
            HouseholdMember.__table__,
            PersonEmbedding.__table__,
            AlertRule.__table__,
            Alert.__table__,
            AlertEvent.__table__,
            AuditLog.__table__,
            User.__table__,
            Recipient.__table__,
            RecipientChannel.__table__,
            NotificationDelivery.__table__,
        ]
        with engine.begin() as conn:
            for tbl in tables:
                tbl.create(conn, checkfirst=True)

        factory = sessionmaker(engine, expire_on_commit=False)
        with factory() as sync_sess:
            sync_sess.add(
                Camera(
                    id="front_door",
                    name="Front Door",
                    folder_path="/export/foscam/front_door",
                    status="online",
                )
            )
            sync_sess.commit()

        class _Sess(_AsyncSQLiteSession):
            async def flush(self) -> None:
                self._s.flush()

        sess = _Sess(factory())
        now = datetime.now(UTC)
        ev = Event(
            batch_id="b-del-1",
            camera_id="front_door",
            started_at=now - timedelta(minutes=20),
            ended_at=now - timedelta(minutes=19),
            risk_score=80,
            risk_level="high",
            summary="Purge with deliveries",
            deleted_at=now - timedelta(minutes=5),
        )
        sess.add(ev)
        await sess.flush()

        alert = Alert(
            event_id=ev.id,
            last_event_id=ev.id,
            last_seen_at=ev.started_at,
            match_count=1,
            severity=AlertSeverityEnum.HIGH,
            status=AlertStatusEnum.OPEN,
            dedup_key="front_door:person:del",
        )
        sess.add(alert)
        await sess.flush()
        sess.add(Recipient(id="r-del-1", name="Household", enabled=True))
        await sess.flush()
        sess.add(RecipientChannel(id="c-del-1", recipient_id="r-del-1", kind="email", target="x@y"))
        await sess.flush()
        for key in ("idem-1", "idem-2"):
            sess.add(
                NotificationDelivery(
                    alert_id=alert.id,
                    recipient_id="r-del-1",
                    channel_id="c-del-1",
                    kind="email",
                    idempotency_key=key,
                )
            )
        await sess.commit()

        report = await EventPurger().purge([ev.id], reason="user", session=sess)  # type: ignore[arg-type]
        await sess.commit()
        assert report.purged == (ev.id,)
        assert report.rows_removed["alerts"] == 1
        assert report.rows_removed["deliveries"] == 2

        engine.dispose()
