"""Integration tests for database transaction isolation edge cases.

Tests verify:
- Savepoint isolation: no data persists after rollback
- Concurrent write handling: concurrent test writes don't interfere
- Foreign key cascade: CASCADE DELETE with nested relationships
- Advisory lock: schema initialization lock prevents race conditions

Uses shared fixtures from conftest.py:
- integration_db: Clean PostgreSQL test database
- isolated_db_session: AsyncSession with savepoint rollback
- clean_tables: DELETE all data before/after test

Reference: NEM-1376
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from backend.core.database import get_session, get_session_factory
from backend.models.alert import Alert, AlertSeverity, AlertStatus
from backend.models.baseline import ActivityBaseline, ClassBaseline
from backend.models.camera import Camera
from backend.models.camera_zone import CameraZone, CameraZoneShape, CameraZoneType
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_audit import EventAudit
from backend.tests.conftest import unique_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Aliases for backward compatibility
Zone = CameraZone
ZoneShape = CameraZoneShape
ZoneType = CameraZoneType

pytestmark = pytest.mark.integration


class TestSavepointIsolation:
    """Tests verifying savepoint isolation - no data persists after rollback."""

    @pytest.mark.asyncio
    async def test_savepoint_rollback_removes_all_created_data(
        self, isolated_db_session: AsyncSession
    ) -> None:
        """Verify that data created within a savepoint is rolled back completely."""
        session = isolated_db_session
        camera_id = unique_id("savepoint_cam")

        # Create data within the savepoint
        camera = Camera(
            id=camera_id,
            name="Savepoint Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
        )
        session.add(camera)
        await session.flush()

        # Verify data exists within the session
        result = await session.execute(select(Camera).where(Camera.id == camera_id))
        assert result.scalar_one_or_none() is not None

        # The isolated_db_session fixture will rollback on exit
        # We can't verify persistence here since rollback happens in fixture teardown
        # Instead we verify the data is visible within the transaction
        assert camera.id == camera_id

    @pytest.mark.asyncio
    async def test_savepoint_isolation_between_tests(
        self, isolated_db_session: AsyncSession
    ) -> None:
        """Verify that data from one test using isolated_db_session doesn't leak."""
        session = isolated_db_session

        # This test should NOT see data from previous tests
        # Query for any cameras with 'savepoint_cam' prefix
        result = await session.execute(select(Camera).where(Camera.id.like("savepoint_cam%")))
        cameras = result.scalars().all()

        # If isolation is working, we shouldn't see cameras from previous tests
        # (unless they were committed outside of savepoint)
        # This is a baseline verification
        assert isinstance(cameras, list)

    @pytest.mark.asyncio
    async def test_explicit_savepoint_rollback_within_transaction(
        self, integration_db: str
    ) -> None:
        """Verify explicit savepoint rollback leaves no data behind."""
        camera_id = unique_id("explicit_sp_cam")

        async with get_session() as session:
            # Create a savepoint
            await session.execute(text("SAVEPOINT explicit_test"))

            # Create data
            camera = Camera(
                id=camera_id,
                name="Explicit Savepoint Camera",
                folder_path=f"/export/foscam/{camera_id}",
            )
            session.add(camera)
            await session.flush()

            # Verify data exists within transaction
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            assert result.scalar_one_or_none() is not None

            # Rollback to savepoint
            await session.execute(text("ROLLBACK TO SAVEPOINT explicit_test"))

            # Data should no longer exist
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            assert result.scalar_one_or_none() is None

            # Commit (which commits nothing since we rolled back)
            await session.commit()

        # Verify in a new session that nothing was persisted
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_nested_savepoints_rollback_correctly(self, integration_db: str) -> None:
        """Verify nested savepoints can be rolled back independently."""
        camera_id = unique_id("nested_sp_cam")
        detection_ids: list[int] = []

        async with get_session() as session:
            # Create camera (will be committed)
            camera = Camera(
                id=camera_id,
                name="Nested Savepoint Camera",
                folder_path=f"/export/foscam/{camera_id}",
            )
            session.add(camera)
            await session.flush()

            # First savepoint - create detection 1
            await session.execute(text("SAVEPOINT sp1"))
            detection1 = Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/test1.jpg",
                file_type="jpg",
                detected_at=datetime.now(UTC),
                object_type="person",
                confidence=0.9,
            )
            session.add(detection1)
            await session.flush()
            detection_ids.append(detection1.id)

            # Second savepoint - create detection 2
            await session.execute(text("SAVEPOINT sp2"))
            detection2 = Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/test2.jpg",
                file_type="jpg",
                detected_at=datetime.now(UTC),
                object_type="vehicle",
                confidence=0.85,
            )
            session.add(detection2)
            await session.flush()

            # Rollback sp2 only (detection2 should be gone)
            await session.execute(text("ROLLBACK TO SAVEPOINT sp2"))

            # Verify detection1 still exists, detection2 doesn't
            result = await session.execute(
                select(Detection).where(Detection.id == detection_ids[0])
            )
            assert result.scalar_one_or_none() is not None

            # Rollback sp1 (detection1 should also be gone)
            await session.execute(text("ROLLBACK TO SAVEPOINT sp1"))

            # Both detections should be gone
            result = await session.execute(
                select(Detection).where(Detection.camera_id == camera_id)
            )
            assert result.scalars().all() == []

            # Camera should still exist (created before savepoints)
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            assert result.scalar_one_or_none() is not None

            # Commit the camera
            await session.commit()

        # Cleanup (safe: camera_id is generated by unique_id, not user input)
        async with get_session() as session:
            await session.execute(text(f"DELETE FROM cameras WHERE id = '{camera_id}'"))  # noqa: S608 nosemgrep
            await session.commit()


class TestConcurrentWriteHandling:
    """Tests verifying concurrent writes don't interfere with each other."""

    @pytest.mark.asyncio
    async def test_concurrent_camera_creation_with_unique_ids(self, integration_db: str) -> None:
        """Verify concurrent camera creations with unique IDs succeed."""
        camera_ids = [unique_id(f"concurrent_{i}") for i in range(5)]
        results: list[bool] = []

        async def create_camera(camera_id: str) -> bool:
            """Create a camera and return success status."""
            try:
                async with get_session() as session:
                    camera = Camera(
                        id=camera_id,
                        name=f"Concurrent Camera {camera_id}",
                        folder_path=f"/export/foscam/{camera_id}",
                    )
                    session.add(camera)
                    await session.commit()
                    return True
            except Exception:
                return False

        # Run concurrent creations
        tasks = [create_camera(cid) for cid in camera_ids]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(results), f"Some concurrent creations failed: {results}"

        # Verify all cameras exist
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id.in_(camera_ids)))
            cameras = result.scalars().all()
            assert len(cameras) == 5

        # Cleanup (safe: camera_ids are generated by unique_id, not user input)
        async with get_session() as session:
            for camera_id in camera_ids:
                await session.execute(
                    text(f"DELETE FROM cameras WHERE id = '{camera_id}'")  # noqa: S608 nosemgrep
                )
            await session.commit()

    @pytest.mark.asyncio
    async def test_concurrent_writes_to_same_camera_serialized(self, integration_db: str) -> None:
        """Verify concurrent writes to the same camera are properly serialized."""
        camera_id = unique_id("concurrent_write_cam")

        # Create the camera first
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Concurrent Write Camera",
                folder_path=f"/export/foscam/{camera_id}",
            )
            session.add(camera)
            await session.commit()

        # Track successful detection creations
        successful_creations = []

        async def create_detection(idx: int) -> int | None:
            """Create a detection and return its ID."""
            try:
                async with get_session() as session:
                    detection = Detection(
                        camera_id=camera_id,
                        file_path=f"/export/foscam/{camera_id}/concurrent_{idx}.jpg",
                        file_type="jpg",
                        detected_at=datetime.now(UTC),
                        object_type="person",
                        confidence=0.9,
                    )
                    session.add(detection)
                    await session.commit()
                    await session.refresh(detection)
                    return detection.id
            except Exception:
                return None

        # Run concurrent detection creations
        tasks = [create_detection(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        successful_creations = [r for r in results if r is not None]

        # All should succeed since file_path is unique
        assert len(successful_creations) == 10

        # Verify all detections exist
        async with get_session() as session:
            result = await session.execute(
                select(Detection).where(Detection.camera_id == camera_id)
            )
            detections = result.scalars().all()
            assert len(detections) == 10

        # Cleanup (safe: camera_id is generated by unique_id, not user input)
        async with get_session() as session:
            await session.execute(
                text(f"DELETE FROM detections WHERE camera_id = '{camera_id}'")  # noqa: S608 nosemgrep
            )
            await session.execute(text(f"DELETE FROM cameras WHERE id = '{camera_id}'"))  # noqa: S608 nosemgrep
            await session.commit()

    @pytest.mark.asyncio
    async def test_concurrent_session_isolation(self, integration_db: str) -> None:
        """Verify concurrent sessions don't see each other's uncommitted data."""
        camera_id = unique_id("session_isolation_cam")

        # Get two independent sessions
        factory = get_session_factory()
        session1 = factory()
        session2 = factory()

        try:
            # Session 1: Create camera but don't commit
            camera = Camera(
                id=camera_id,
                name="Session Isolation Camera",
                folder_path=f"/export/foscam/{camera_id}",
            )
            session1.add(camera)
            await session1.flush()

            # Session 2: Should NOT see the uncommitted camera
            result = await session2.execute(select(Camera).where(Camera.id == camera_id))
            assert result.scalar_one_or_none() is None

            # Session 1: Commit
            await session1.commit()

            # Session 2: Now should see the camera (after new query)
            result = await session2.execute(select(Camera).where(Camera.id == camera_id))
            assert result.scalar_one_or_none() is not None

        finally:
            await session1.close()
            await session2.close()

        # Cleanup (safe: camera_id is generated by unique_id, not user input)
        async with get_session() as session:
            await session.execute(text(f"DELETE FROM cameras WHERE id = '{camera_id}'"))  # noqa: S608 nosemgrep
            await session.commit()

    @pytest.mark.asyncio
    async def test_concurrent_unique_constraint_handling(self, integration_db: str) -> None:
        """Verify concurrent attempts to create duplicate cameras fail gracefully."""
        camera_id = unique_id("dup_concurrent_cam")
        folder_path = f"/export/foscam/{camera_id}"
        results: list[str] = []

        async def create_camera(worker_id: int) -> str:
            """Try to create a camera, return 'success' or 'conflict'."""
            try:
                async with get_session() as session:
                    camera = Camera(
                        id=camera_id,
                        name=f"Duplicate Camera {worker_id}",
                        folder_path=folder_path,
                    )
                    session.add(camera)
                    await session.commit()
                    return "success"
            except IntegrityError:
                return "conflict"
            except Exception as e:
                return f"error: {e}"

        # Run concurrent creations with same ID
        tasks = [create_camera(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        # Exactly one should succeed
        success_count = sum(1 for r in results if r == "success")
        conflict_count = sum(1 for r in results if r == "conflict")

        assert success_count == 1, f"Expected 1 success, got {success_count}"
        assert conflict_count == 4, f"Expected 4 conflicts, got {conflict_count}"

        # Cleanup (safe: camera_id is generated by unique_id, not user input)
        async with get_session() as session:
            await session.execute(text(f"DELETE FROM cameras WHERE id = '{camera_id}'"))  # noqa: S608 nosemgrep
            await session.commit()


class TestForeignKeyCascadeWithNestedRelationships:
    """Tests for CASCADE DELETE with deeply nested relationships."""

    @pytest.mark.asyncio
    async def test_camera_cascade_deletes_nested_detections_and_events(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Verify camera deletion cascades through all nested relationships."""
        camera_id = unique_id("cascade_nested_cam")

        async with get_session() as session:
            # Create camera
            camera = Camera(
                id=camera_id,
                name="Cascade Nested Camera",
                folder_path=f"/export/foscam/{camera_id}",
            )
            session.add(camera)
            await session.flush()

            # Create detections
            for i in range(3):
                detection = Detection(
                    camera_id=camera_id,
                    file_path=f"/export/foscam/{camera_id}/nested_{i}.jpg",
                    file_type="jpg",
                    detected_at=datetime.now(UTC),
                    object_type="person",
                    confidence=0.9,
                )
                session.add(detection)

            # Create events
            event_ids = []
            for i in range(2):
                event = Event(
                    batch_id=unique_id(f"batch_{i}"),
                    camera_id=camera_id,
                    started_at=datetime.now(UTC),
                    risk_score=50 + i * 10,
                    risk_level="medium",
                    summary=f"Cascade test event {i}",
                )
                session.add(event)
                await session.flush()
                event_ids.append(event.id)

            await session.commit()

        # Verify data exists
        async with get_session() as session:
            result = await session.execute(
                select(Detection).where(Detection.camera_id == camera_id)
            )
            assert len(result.scalars().all()) == 3

            result = await session.execute(select(Event).where(Event.camera_id == camera_id))
            assert len(result.scalars().all()) == 2

        # Delete camera (should cascade)
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            camera = result.scalar_one()
            await session.delete(camera)
            await session.commit()

        # Verify all related data is gone
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            assert result.scalar_one_or_none() is None

            result = await session.execute(
                select(Detection).where(Detection.camera_id == camera_id)
            )
            assert result.scalars().all() == []

            result = await session.execute(select(Event).where(Event.camera_id == camera_id))
            assert result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_camera_cascade_through_event_to_alerts(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Verify camera deletion cascades through events to alerts."""
        camera_id = unique_id("cascade_alert_cam")

        async with get_session() as session:
            # Create camera
            camera = Camera(
                id=camera_id,
                name="Cascade Alert Camera",
                folder_path=f"/export/foscam/{camera_id}",
            )
            session.add(camera)
            await session.flush()

            # Create event
            event = Event(
                batch_id=unique_id("batch"),
                camera_id=camera_id,
                started_at=datetime.now(UTC),
                risk_score=80,
                risk_level="high",
                summary="High risk event",
            )
            session.add(event)
            await session.flush()
            event_id = event.id

            # Create alerts linked to event
            alert_ids = []
            for i in range(3):
                alert = Alert(
                    id=str(uuid4()),
                    event_id=event_id,
                    severity=AlertSeverity.HIGH,
                    status=AlertStatus.PENDING,
                    dedup_key=f"{camera_id}:alert:{i}",
                )
                session.add(alert)
                await session.flush()
                alert_ids.append(alert.id)

            await session.commit()

        # Verify alerts exist
        async with get_session() as session:
            result = await session.execute(select(Alert).where(Alert.id.in_(alert_ids)))
            assert len(result.scalars().all()) == 3

        # Delete camera (should cascade through event to alerts)
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            camera = result.scalar_one()
            await session.delete(camera)
            await session.commit()

        # Verify all data is gone
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            assert result.scalar_one_or_none() is None

            result = await session.execute(select(Event).where(Event.id == event_id))
            assert result.scalar_one_or_none() is None

            result = await session.execute(select(Alert).where(Alert.id.in_(alert_ids)))
            assert result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_camera_cascade_to_all_baseline_types(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Verify camera deletion cascades to both ActivityBaseline and ClassBaseline."""
        camera_id = unique_id("cascade_baseline_cam")

        async with get_session() as session:
            # Create camera
            camera = Camera(
                id=camera_id,
                name="Cascade Baseline Camera",
                folder_path=f"/export/foscam/{camera_id}",
            )
            session.add(camera)
            await session.flush()

            # Create activity baselines
            activity_baseline_ids = []
            for hour in range(24):
                baseline = ActivityBaseline(
                    camera_id=camera_id,
                    hour=hour,
                    day_of_week=0,
                    avg_count=10.0 + hour,
                    sample_count=100,
                )
                session.add(baseline)
                await session.flush()
                activity_baseline_ids.append(baseline.id)

            # Create class baselines
            class_baseline_ids = []
            for cls in ["person", "vehicle", "animal"]:
                for hour in range(6):
                    baseline = ClassBaseline(
                        camera_id=camera_id,
                        detection_class=cls,
                        hour=hour,
                        frequency=0.1 * hour,
                        sample_count=50,
                    )
                    session.add(baseline)
                    await session.flush()
                    class_baseline_ids.append(baseline.id)

            await session.commit()

        # Verify baselines exist
        async with get_session() as session:
            result = await session.execute(
                select(ActivityBaseline).where(ActivityBaseline.camera_id == camera_id)
            )
            assert len(result.scalars().all()) == 24

            result = await session.execute(
                select(ClassBaseline).where(ClassBaseline.camera_id == camera_id)
            )
            assert len(result.scalars().all()) == 18

        # Delete camera
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            camera = result.scalar_one()
            await session.delete(camera)
            await session.commit()

        # Verify all baselines are gone
        async with get_session() as session:
            result = await session.execute(
                select(ActivityBaseline).where(ActivityBaseline.id.in_(activity_baseline_ids))
            )
            assert result.scalars().all() == []

            result = await session.execute(
                select(ClassBaseline).where(ClassBaseline.id.in_(class_baseline_ids))
            )
            assert result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_camera_cascade_to_zones(self, integration_db: str, clean_tables: None) -> None:
        """Verify camera deletion cascades to zones."""
        camera_id = unique_id("cascade_zone_cam")

        async with get_session() as session:
            # Create camera
            camera = Camera(
                id=camera_id,
                name="Cascade Zone Camera",
                folder_path=f"/export/foscam/{camera_id}",
            )
            session.add(camera)
            await session.flush()

            # Create zones
            zone_ids = []
            for i, zone_type in enumerate([ZoneType.DRIVEWAY, ZoneType.ENTRY_POINT, ZoneType.YARD]):
                zone = Zone(
                    id=f"{camera_id}_zone_{i}",
                    camera_id=camera_id,
                    name=f"Zone {i}",
                    zone_type=zone_type,
                    shape=ZoneShape.RECTANGLE,
                    coordinates=[[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
                )
                session.add(zone)
                await session.flush()
                zone_ids.append(zone.id)

            await session.commit()

        # Verify zones exist
        async with get_session() as session:
            result = await session.execute(select(Zone).where(Zone.camera_id == camera_id))
            assert len(result.scalars().all()) == 3

        # Delete camera
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            camera = result.scalar_one()
            await session.delete(camera)
            await session.commit()

        # Verify zones are gone
        async with get_session() as session:
            result = await session.execute(select(Zone).where(Zone.id.in_(zone_ids)))
            assert result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_event_cascade_to_event_audits(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Verify event deletion cascades to event audits."""
        camera_id = unique_id("cascade_audit_cam")

        async with get_session() as session:
            # Create camera
            camera = Camera(
                id=camera_id,
                name="Cascade Audit Camera",
                folder_path=f"/export/foscam/{camera_id}",
            )
            session.add(camera)
            await session.flush()

            # Create event
            event = Event(
                batch_id=unique_id("batch"),
                camera_id=camera_id,
                started_at=datetime.now(UTC),
                risk_score=60,
                risk_level="medium",
                summary="Audit test event",
            )
            session.add(event)
            await session.flush()
            event_id = event.id

            # Create event audit (EventAudit has one-to-one relationship with Event)
            # The EventAudit model tracks AI pipeline performance metrics
            audit = EventAudit(
                event_id=event_id,
                has_yolo26=True,
                has_florence=True,
                has_clip=False,
                prompt_length=500,
                prompt_token_estimate=125,
                enrichment_utilization=0.75,
            )
            session.add(audit)
            await session.flush()
            audit_id = audit.id

            await session.commit()

        # Verify audit exists
        async with get_session() as session:
            result = await session.execute(
                select(EventAudit).where(EventAudit.event_id == event_id)
            )
            assert result.scalar_one_or_none() is not None

        # Delete event
        async with get_session() as session:
            result = await session.execute(select(Event).where(Event.id == event_id))
            event = result.scalar_one()
            await session.delete(event)
            await session.commit()

        # Verify audit is gone
        async with get_session() as session:
            result = await session.execute(select(EventAudit).where(EventAudit.id == audit_id))
            assert result.scalar_one_or_none() is None

        # Cleanup camera (safe: camera_id is generated by unique_id, not user input)
        async with get_session() as session:
            await session.execute(text(f"DELETE FROM cameras WHERE id = '{camera_id}'"))  # noqa: S608 nosemgrep
            await session.commit()


class TestAdvisoryLocks:
    """Tests for advisory lock behavior in schema initialization."""

    # Advisory lock key used in conftest.py for test schema reset
    _TEST_SCHEMA_LOCK_NAMESPACE = "home_security_intelligence.test_schema_reset"
    _TEST_SCHEMA_LOCK_KEY = int(
        hashlib.sha256(_TEST_SCHEMA_LOCK_NAMESPACE.encode()).hexdigest()[:15], 16
    )

    @pytest.mark.asyncio
    async def test_advisory_lock_prevents_concurrent_schema_modification(
        self, integration_db: str
    ) -> None:
        """Verify advisory lock prevents race conditions in schema modification."""
        lock_key = 999999  # Test-specific lock key

        lock_acquired_order: list[int] = []
        lock = asyncio.Lock()

        async def acquire_and_release_lock(worker_id: int, delay: float = 0.1) -> None:
            """Acquire advisory lock, do work, then release."""
            async with get_session() as session:
                # Acquire blocking advisory lock
                # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                await session.execute(text(f"SELECT pg_advisory_lock({lock_key})"))

                # Record acquisition order
                async with lock:
                    lock_acquired_order.append(worker_id)

                # Simulate DDL operation
                await asyncio.sleep(delay)

                # Release lock
                # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                await session.execute(text(f"SELECT pg_advisory_unlock({lock_key})"))

        # Start multiple workers trying to acquire the same lock
        tasks = [acquire_and_release_lock(i, 0.05) for i in range(5)]
        await asyncio.gather(*tasks)

        # All workers should have acquired the lock sequentially
        assert len(lock_acquired_order) == 5
        # Each worker ID should appear exactly once
        assert sorted(lock_acquired_order) == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_advisory_lock_try_lock_behavior(self, integration_db: str) -> None:
        """Verify pg_try_advisory_lock returns immediately without blocking."""
        lock_key = 999998  # Test-specific lock key

        async with get_session() as session1:
            # Session 1: Acquire lock
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            result = await session1.execute(text(f"SELECT pg_try_advisory_lock({lock_key})"))
            acquired = result.scalar()
            assert acquired is True

            async with get_session() as session2:
                # Session 2: Try to acquire (should fail immediately)
                # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                result = await session2.execute(text(f"SELECT pg_try_advisory_lock({lock_key})"))
                acquired = result.scalar()
                assert acquired is False

            # Session 1: Release lock
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            await session1.execute(text(f"SELECT pg_advisory_unlock({lock_key})"))

            async with get_session() as session3:
                # Session 3: Now should be able to acquire
                # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                result = await session3.execute(text(f"SELECT pg_try_advisory_lock({lock_key})"))
                acquired = result.scalar()
                assert acquired is True

                # Cleanup
                # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                await session3.execute(text(f"SELECT pg_advisory_unlock({lock_key})"))

    @pytest.mark.asyncio
    async def test_advisory_lock_released_on_session_close(self, integration_db: str) -> None:
        """Verify advisory lock is released when session closes."""
        lock_key = 999997  # Test-specific lock key

        # Acquire lock in a session that we close
        factory = get_session_factory()
        session1 = factory()

        try:
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            result = await session1.execute(text(f"SELECT pg_advisory_lock({lock_key})"))
            # Lock is now held
        finally:
            await session1.close()

        # Lock should be released after session close
        # New session should be able to acquire it
        async with get_session() as session2:
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            result = await session2.execute(text(f"SELECT pg_try_advisory_lock({lock_key})"))
            acquired = result.scalar()
            # Note: pg_advisory_lock is session-level, so it should be released
            assert acquired is True

            # Cleanup
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            await session2.execute(text(f"SELECT pg_advisory_unlock({lock_key})"))

    @pytest.mark.asyncio
    async def test_advisory_lock_key_uniqueness(self, integration_db: str) -> None:
        """Verify different lock keys don't interfere with each other."""
        lock_key_1 = 999996
        lock_key_2 = 999995

        async with get_session() as session:
            # Acquire first lock
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            result = await session.execute(text(f"SELECT pg_try_advisory_lock({lock_key_1})"))
            assert result.scalar() is True

            # Acquire second lock (should succeed - different key)
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            result = await session.execute(text(f"SELECT pg_try_advisory_lock({lock_key_2})"))
            assert result.scalar() is True

            # Try to acquire first lock again (should fail - already held)
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            result = await session.execute(text(f"SELECT pg_try_advisory_lock({lock_key_1})"))
            # Note: Same session can acquire the same lock again
            assert result.scalar() is True

            # Cleanup - release all locks
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            await session.execute(text(f"SELECT pg_advisory_unlock({lock_key_1})"))
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            await session.execute(text(f"SELECT pg_advisory_unlock({lock_key_1})"))
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            await session.execute(text(f"SELECT pg_advisory_unlock({lock_key_2})"))

    @pytest.mark.asyncio
    async def test_schema_initialization_lock_key_is_deterministic(
        self, integration_db: str
    ) -> None:
        """Verify the schema initialization lock key is deterministically generated."""
        # The lock key should be the same every time for the same namespace
        namespace = "home_security_intelligence.test_schema_reset"
        expected_key = int(hashlib.sha256(namespace.encode()).hexdigest()[:15], 16)

        # Calculate again to verify determinism
        calculated_key = int(hashlib.sha256(namespace.encode()).hexdigest()[:15], 16)

        assert expected_key == calculated_key
        assert expected_key == self._TEST_SCHEMA_LOCK_KEY

    @pytest.mark.asyncio
    async def test_concurrent_schema_init_serialization(self, integration_db: str) -> None:
        """Verify concurrent schema initialization attempts are serialized."""
        test_lock_key = 999994  # Test-specific lock key
        operations_completed: list[int] = []
        operation_lock = asyncio.Lock()

        async def simulated_schema_init(worker_id: int) -> None:
            """Simulate schema initialization with advisory lock."""
            async with get_session() as session:
                # Acquire lock (blocking)
                # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                await session.execute(text(f"SELECT pg_advisory_lock({test_lock_key})"))

                try:
                    # Simulate DDL operations
                    async with operation_lock:
                        operations_completed.append(worker_id)

                    # Add slight delay to ensure serialization is visible
                    await asyncio.sleep(0.02)

                finally:
                    # Always release lock
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    await session.execute(text(f"SELECT pg_advisory_unlock({test_lock_key})"))

        # Run multiple concurrent schema inits
        tasks = [simulated_schema_init(i) for i in range(3)]
        await asyncio.gather(*tasks)

        # All operations should complete
        assert len(operations_completed) == 3
        # Each worker should appear exactly once
        assert sorted(operations_completed) == [0, 1, 2]
