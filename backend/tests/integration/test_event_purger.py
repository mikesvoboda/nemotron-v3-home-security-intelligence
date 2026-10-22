"""Integration tests for EventPurger and its four adapters (`B4.4` / `4n-trash.md`)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.core.database import get_session
from backend.models.alert import Alert, AlertEvent, AlertSeverityEnum, AlertStatusEnum
from backend.models.audit import AuditLog
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.entity import Entity
from backend.models.event import Event
from backend.models.event_detection import EventDetection
from backend.models.face_identity import FaceDetectionEvent, FaceEmbedding, KnownPerson
from backend.models.household import HouseholdMember, MemberRole, PersonEmbedding, TrustLevel
from backend.services.batch_aggregator import BatchAggregator, recover_orphaned_detections
from backend.services.cleanup_service import CleanupService
from backend.services.event_purger import EventPurger

pytestmark = pytest.mark.integration


async def _seed_camera(camera_id: str) -> str:
    async with get_session() as db:
        existing = await db.get(Camera, camera_id)
        if existing is None:
            db.add(
                Camera(
                    id=camera_id,
                    name=camera_id,
                    folder_path=f"/export/foscam/{camera_id}",
                    status="online",
                )
            )
            await db.commit()
    return camera_id


class TestEventPurgerIntegration:
    """End-to-end integration tests for EventPurger against PostgreSQL and HTTP routes."""

    @pytest.mark.asyncio
    async def test_single_permanent_delete_409_live_then_trash_and_purge_with_derived_rows(
        self, client: AsyncClient, tmp_path: Path
    ) -> None:
        cam_id = await _seed_camera(f"purge_cam_{uuid.uuid4().hex[:8]}")
        now = datetime.now(UTC)

        clip_path = tmp_path / "event_clip.mp4"
        img_path = tmp_path / "det_img.jpg"
        thumb_path = tmp_path / "det_thumb.jpg"
        for p in (clip_path, img_path, thumb_path):
            p.write_bytes(b"test-media")

        async with get_session() as db:
            ev = Event(
                batch_id=f"batch_{uuid.uuid4().hex[:8]}",
                camera_id=cam_id,
                started_at=now - timedelta(minutes=30),
                ended_at=now - timedelta(minutes=25),
                risk_score=70,
                risk_level="high",
                summary="Sensitive summary that must not appear in audit log",
                clip_path=str(clip_path),
                deleted_at=None,
            )
            db.add(ev)
            await db.flush()

            det = Detection(
                camera_id=cam_id,
                file_path=str(img_path),
                thumbnail_path=str(thumb_path),
                detected_at=now - timedelta(minutes=28),
                object_type="person",
                confidence=0.95,
            )
            db.add(det)
            await db.flush()
            db.add(EventDetection(event_id=ev.id, detection_id=det.id))

            ent = Entity(
                entity_type="person",
                trust_status="unknown",
                primary_detection_id=det.id,
            )
            face_ev = FaceDetectionEvent(
                camera_id=cam_id,
                timestamp=now - timedelta(minutes=27),
                bbox={"x1": 0, "y1": 0, "x2": 10, "y2": 10},
                embedding=b"\x00" * 16,
                is_unknown=True,
                quality_score=0.9,
            )
            known = KnownPerson(name="Resident", is_household_member=True)
            member = HouseholdMember(
                name="Resident",
                role=MemberRole.RESIDENT,
                trusted_level=TrustLevel.FULL,
            )
            db.add_all([ent, face_ev, known, member])
            await db.flush()

            face_ref = FaceEmbedding(
                person_id=known.id,
                embedding=b"\x01" * 16,
                quality_score=0.95,
                source_image_path=str(img_path),
            )
            person_ref = PersonEmbedding(
                member_id=member.id,
                embedding=b"\x02" * 16,
                source_event_id=ev.id,
                confidence=0.95,
            )
            db.add_all([face_ref, person_ref])
            await db.commit()

            event_id = ev.id
            det_id = det.id
            ent_id = ent.id
            face_ev_id = face_ev.id
            face_ref_id = face_ref.id
            person_ref_id = person_ref.id

        # 1. Permanent delete of a live event returns 409
        res_409 = await client.delete(f"/api/events/{event_id}?permanent=true")
        assert res_409.status_code == 409

        # 2. Soft-delete moves event to Trash without deleting files
        res_soft = await client.delete(f"/api/events/{event_id}")
        assert res_soft.status_code == 204
        assert clip_path.exists()
        assert img_path.exists()
        assert thumb_path.exists()

        # 3. Permanent delete of the trashed event purges event, detection, files, and derived rows
        res_purge = await client.delete(f"/api/events/{event_id}?permanent=true")
        assert res_purge.status_code == 204
        assert not clip_path.exists()
        assert not img_path.exists()
        assert not thumb_path.exists()

        res_404 = await client.get(f"/api/events/{event_id}")
        assert res_404.status_code == 404

        async with get_session() as db:
            assert await db.get(Event, event_id) is None
            assert await db.get(Detection, det_id) is None
            assert await db.get(Entity, ent_id) is None
            assert await db.get(FaceDetectionEvent, face_ev_id) is None

            # Enrolled references remain with links cleared
            fe = await db.get(FaceEmbedding, face_ref_id)
            pe = await db.get(PersonEmbedding, person_ref_id)
            assert fe is not None and fe.source_image_path is None
            assert pe is not None and pe.source_event_id is None

            # Content-free audit entry exists
            audit = (
                await db.execute(
                    select(AuditLog).where(
                        AuditLog.action == "event_purged",
                        AuditLog.resource_id == str(event_id),
                    )
                )
            ).scalar_one_or_none()
            assert audit is not None
            assert audit.details == {"event_id": event_id, "reason": "user"}

    @pytest.mark.asyncio
    async def test_bulk_permanent_delete_and_empty_trash_and_orphan_recovery(
        self, client: AsyncClient
    ) -> None:
        cam_id = await _seed_camera(f"bulk_purge_cam_{uuid.uuid4().hex[:8]}")
        now = datetime.now(UTC)

        async with get_session() as db:
            ev_trashed = Event(
                batch_id=f"batch_{uuid.uuid4().hex[:8]}",
                camera_id=cam_id,
                started_at=now - timedelta(minutes=20),
                ended_at=now - timedelta(minutes=19),
                risk_score=50,
                risk_level="medium",
                summary="Trashed 1",
                deleted_at=now - timedelta(minutes=5),
            )
            ev_live = Event(
                batch_id=f"batch_{uuid.uuid4().hex[:8]}",
                camera_id=cam_id,
                started_at=now - timedelta(minutes=15),
                ended_at=now - timedelta(minutes=14),
                risk_score=40,
                risk_level="medium",
                summary="Live 2",
                deleted_at=None,
            )
            ev_trashed_2 = Event(
                batch_id=f"batch_{uuid.uuid4().hex[:8]}",
                camera_id=cam_id,
                started_at=now - timedelta(minutes=10),
                ended_at=now - timedelta(minutes=9),
                risk_score=60,
                risk_level="medium",
                summary="Trashed 3",
                deleted_at=now - timedelta(minutes=2),
            )
            db.add_all([ev_trashed, ev_live, ev_trashed_2])
            await db.flush()

            det1 = Detection(
                camera_id=cam_id,
                file_path="/nonexistent/det1.jpg",
                detected_at=now - timedelta(minutes=15),
                object_type="person",
                confidence=0.9,
            )
            db.add(det1)
            await db.flush()
            db.add(EventDetection(event_id=ev_trashed.id, detection_id=det1.id))
            await db.commit()

            trashed_id = ev_trashed.id
            live_id = ev_live.id
            trashed_2_id = ev_trashed_2.id
            det1_id = det1.id

        # Bulk permanent delete of trashed + live purges trashed and refuses live
        bulk_res = await client.request(
            "DELETE",
            "/api/events/bulk",
            json={"event_ids": [trashed_id, live_id], "soft_delete": False},
        )
        assert bulk_res.status_code == 207
        body = bulk_res.json()
        assert body["succeeded"] == 1
        assert body["failed"] == 1
        assert body["results"][0]["status"] == "success"
        assert body["results"][1]["status"] == "failed"
        assert "not in Trash" in body["results"][1]["error"]

        # Empty Trash purges remaining trashed events
        empty_res = await client.delete("/api/events/deleted")
        assert empty_res.status_code == 200
        empty_body = empty_res.json()
        assert trashed_2_id in empty_body["purged"]

        # Verify orphan recovery finds nothing for the purged detection
        aggregator = BatchAggregator(redis_client=AsyncMock())
        recovered = await recover_orphaned_detections(aggregator)
        assert recovered == 0
        async with get_session() as db:
            assert await db.get(Detection, det1_id) is None

    @pytest.mark.asyncio
    async def test_alert_folded_events_trash_and_purge_invariants(
        self, client: AsyncClient
    ) -> None:
        cam_id = await _seed_camera(f"alert_purge_cam_{uuid.uuid4().hex[:8]}")
        now = datetime.now(UTC)

        async with get_session() as db:
            ev1 = Event(
                batch_id=f"batch_{uuid.uuid4().hex[:8]}",
                camera_id=cam_id,
                started_at=now - timedelta(minutes=20),
                ended_at=now - timedelta(minutes=19),
                risk_score=80,
                risk_level="high",
                summary="Alert event 1",
            )
            ev2 = Event(
                batch_id=f"batch_{uuid.uuid4().hex[:8]}",
                camera_id=cam_id,
                started_at=now - timedelta(minutes=10),
                ended_at=now - timedelta(minutes=9),
                risk_score=85,
                risk_level="critical",
                summary="Alert event 2",
            )
            db.add_all([ev1, ev2])
            await db.flush()

            alert = Alert(
                event_id=ev1.id,
                last_event_id=ev2.id,
                last_seen_at=ev2.started_at,
                match_count=2,
                severity=AlertSeverityEnum.HIGH,
                status=AlertStatusEnum.OPEN,
                dedup_key=f"{cam_id}:person:default",
            )
            db.add(alert)
            await db.flush()
            db.add_all(
                [
                    AlertEvent(alert_id=alert.id, event_id=ev1.id),
                    AlertEvent(alert_id=alert.id, event_id=ev2.id),
                ]
            )
            await db.commit()
            ev1_id, ev2_id, alert_id = ev1.id, ev2.id, alert.id

        # Trashing ev1 leaves alert OPEN because ev2 is still live
        assert (await client.delete(f"/api/events/{ev1_id}")).status_code == 204
        async with get_session() as db:
            al = await db.get(Alert, alert_id)
            assert al is not None and al.status == AlertStatusEnum.OPEN

        # Purging ev1 repoints alert to ev2 and keeps it OPEN
        assert (await client.delete(f"/api/events/{ev1_id}?permanent=true")).status_code == 204
        async with get_session() as db:
            al = await db.get(Alert, alert_id)
            assert al is not None
            assert al.event_id == ev2_id
            assert al.last_event_id == ev2_id
            assert al.match_count == 1
            assert al.status == AlertStatusEnum.OPEN

        # Trashing ev2 (now the only remaining event) dismisses alert with reason
        assert (await client.delete(f"/api/events/{ev2_id}")).status_code == 204
        async with get_session() as db:
            al = await db.get(Alert, alert_id)
            assert al is not None
            assert al.status == AlertStatusEnum.DISMISSED
            assert al.alert_metadata == {"dismissed_reason": "events moved to Trash"}

        # Purging ev2 removes the alert completely
        assert (await client.delete(f"/api/events/{ev2_id}?permanent=true")).status_code == 204
        async with get_session() as db:
            assert await db.get(Alert, alert_id) is None

    @pytest.mark.asyncio
    async def test_cleanup_service_trash_retention_deadlines(self, test_db) -> None:
        cam_id = await _seed_camera(f"cleanup_trash_cam_{uuid.uuid4().hex[:8]}")
        fixed_now = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)

        async with get_session() as db:
            ev_keep_29 = Event(
                batch_id=f"batch_{uuid.uuid4().hex[:8]}",
                camera_id=cam_id,
                started_at=fixed_now - timedelta(days=29),
                ended_at=fixed_now - timedelta(days=29),
                risk_score=40,
                risk_level="medium",
                summary="Keep 29d",
                deleted_at=fixed_now - timedelta(days=29),
            )
            ev_purge_30 = Event(
                batch_id=f"batch_{uuid.uuid4().hex[:8]}",
                camera_id=cam_id,
                started_at=fixed_now - timedelta(days=30),
                ended_at=fixed_now - timedelta(days=30),
                risk_score=40,
                risk_level="medium",
                summary="Purge 30d",
                deleted_at=fixed_now - timedelta(days=30),
            )
            db.add_all([ev_keep_29, ev_purge_30])
            await db.commit()
            keep_id, purge_id = ev_keep_29.id, ev_purge_30.id

        svc = CleanupService(retention_days=30, trash_retention_days=30)
        report = await svc.purge_expired_trash(now=fixed_now)
        assert purge_id in report.purged
        assert keep_id not in report.purged

        async with get_session() as db:
            assert await db.get(Event, keep_id) is not None
            assert await db.get(Event, purge_id) is None
            await EventPurger().purge([keep_id], reason="user", session=db)
            await db.commit()
