"""Data corruption detection integration tests.

This module provides comprehensive integration tests for detecting and handling
data corruption scenarios in the database, including:

- Orphaned records (references to non-existent parent records)
- Referential integrity violations
- Data consistency checks (timestamps, enums, ranges)
- Recovery and resilience under corruption scenarios

These tests ensure the system can detect, log, and gracefully handle various
data corruption scenarios that may occur during database operations.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from backend.core.time_utils import utc_now
from backend.models import (
    Alert,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    Camera,
    Detection,
    Event,
    EventDetection,
)
from backend.tests.conftest import unique_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# Mark all tests as integration tests requiring real PostgreSQL database
pytestmark = pytest.mark.integration


class TestOrphanedRecordDetection:
    """Tests for detecting orphaned records in the database.

    Orphaned records are child records that reference non-existent parent records,
    violating referential integrity. These tests verify the database properly
    enforces foreign key constraints.
    """

    @pytest.mark.asyncio
    async def test_detection_without_camera_rejected(self, session: AsyncSession) -> None:
        """Verify that creating a detection with invalid camera_id is rejected."""
        # Arrange: Create detection with non-existent camera_id
        detection = Detection(
            camera_id="nonexistent_camera",
            file_path="/export/foscam/nonexistent/image.jpg",
            object_type="person",
            confidence=0.9,
        )
        session.add(detection)

        # Act & Assert: Should raise IntegrityError due to foreign key constraint
        with pytest.raises(IntegrityError) as exc_info:
            await session.flush()

        assert "cameras" in str(exc_info.value).lower()
        assert "foreign key" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_event_without_camera_rejected(self, session: AsyncSession) -> None:
        """Verify that creating an event with invalid camera_id is rejected."""
        # Arrange: Create event with non-existent camera_id
        event = Event(
            batch_id=unique_id("batch"),
            camera_id="nonexistent_camera",
            started_at=utc_now(),
            risk_score=75,
        )
        session.add(event)

        # Act & Assert: Should raise IntegrityError due to foreign key constraint
        with pytest.raises(IntegrityError) as exc_info:
            await session.flush()

        assert "cameras" in str(exc_info.value).lower()
        assert "foreign key" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_alert_without_event_rejected(self, session: AsyncSession) -> None:
        """Verify that creating an alert with invalid event_id is rejected."""
        # Arrange: Create alert with non-existent event_id
        alert = Alert(
            id=str(uuid4()),
            event_id=999999,  # Non-existent event
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            dedup_key=unique_id("dedup"),
        )
        session.add(alert)

        # Act & Assert: Should raise IntegrityError due to foreign key constraint
        with pytest.raises(IntegrityError) as exc_info:
            await session.flush()

        assert "events" in str(exc_info.value).lower()
        assert "foreign key" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_alert_with_invalid_rule_id_rejected(self, session: AsyncSession) -> None:
        """Verify that creating an alert with invalid rule_id is rejected."""
        # Arrange: Create camera and event first
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id=unique_id("batch"),
            camera_id=camera_id,
            started_at=utc_now(),
            risk_score=80,
        )
        session.add(event)
        await session.flush()

        # Create alert with non-existent rule_id
        alert = Alert(
            id=str(uuid4()),
            event_id=event.id,
            rule_id=str(uuid4()),  # Non-existent rule
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            dedup_key=unique_id("dedup"),
        )
        session.add(alert)

        # Act & Assert: Should raise IntegrityError due to foreign key constraint
        with pytest.raises(IntegrityError) as exc_info:
            await session.flush()

        assert "alert_rules" in str(exc_info.value).lower()
        assert "foreign key" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_event_detection_with_invalid_event_rejected(self, session: AsyncSession) -> None:
        """Verify that creating event_detection with invalid event_id is rejected."""
        # Arrange: Create camera and detection
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image.jpg",
        )
        session.add(detection)
        await session.flush()

        # Create event_detection with non-existent event_id
        event_detection = EventDetection(
            event_id=999999,  # Non-existent event
            detection_id=detection.id,
        )
        session.add(event_detection)

        # Act & Assert: Should raise IntegrityError due to foreign key constraint
        with pytest.raises(IntegrityError) as exc_info:
            await session.flush()

        assert "events" in str(exc_info.value).lower()
        assert "foreign key" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_event_detection_with_invalid_detection_rejected(
        self, session: AsyncSession
    ) -> None:
        """Verify that creating event_detection with invalid detection_id is rejected."""
        # Arrange: Create camera and event
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id=unique_id("batch"),
            camera_id=camera_id,
            started_at=utc_now(),
        )
        session.add(event)
        await session.flush()

        # Create event_detection with non-existent detection_id
        event_detection = EventDetection(
            event_id=event.id,
            detection_id=999999,  # Non-existent detection
        )
        session.add(event_detection)

        # Act & Assert: Should raise IntegrityError due to foreign key constraint
        with pytest.raises(IntegrityError) as exc_info:
            await session.flush()

        assert "detections" in str(exc_info.value).lower()
        assert "foreign key" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_orphaned_detections_prevented_by_cascade_delete(
        self, session: AsyncSession
    ) -> None:
        """Verify that deleting a camera cascades to delete detections, preventing orphans."""
        # Arrange: Create camera with detections
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Cascade Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection_ids = []
        for i in range(3):
            detection = Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/image_{i}.jpg",
            )
            session.add(detection)
            await session.flush()
            detection_ids.append(detection.id)

        # Act: Delete camera
        await session.delete(camera)
        await session.flush()

        # Assert: All detections should be deleted (no orphans)
        stmt = select(func.count()).select_from(Detection).where(Detection.id.in_(detection_ids))
        result = await session.execute(stmt)
        count = result.scalar()
        assert count == 0

    @pytest.mark.asyncio
    async def test_orphaned_events_prevented_by_cascade_delete(self, session: AsyncSession) -> None:
        """Verify that deleting a camera cascades to delete events, preventing orphans."""
        # Arrange: Create camera with events
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Cascade Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        event_ids = []
        for i in range(3):
            event = Event(
                batch_id=unique_id("batch"),
                camera_id=camera_id,
                started_at=utc_now(),
            )
            session.add(event)
            await session.flush()
            event_ids.append(event.id)

        # Act: Delete camera
        await session.delete(camera)
        await session.flush()

        # Assert: All events should be deleted (no orphans)
        stmt = select(func.count()).select_from(Event).where(Event.id.in_(event_ids))
        result = await session.execute(stmt)
        count = result.scalar()
        assert count == 0


class TestReferentialIntegrity:
    """Tests for referential integrity validation and enforcement.

    These tests verify that foreign key constraints properly maintain data integrity
    across related tables and that cascade behaviors work correctly.
    """

    @pytest.mark.asyncio
    async def test_camera_deletion_cascades_to_detections(self, session: AsyncSession) -> None:
        """Verify CASCADE delete from camera to detections."""
        # Arrange: Create camera with detections
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection_ids = []
        for i in range(5):
            detection = Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/image_{i}.jpg",
            )
            session.add(detection)
            await session.flush()
            detection_ids.append(detection.id)

        # Act: Delete camera
        await session.delete(camera)
        await session.flush()

        # Assert: All detections deleted via CASCADE
        stmt = select(func.count()).select_from(Detection).where(Detection.id.in_(detection_ids))
        result = await session.execute(stmt)
        assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_camera_deletion_cascades_to_events(self, session: AsyncSession) -> None:
        """Verify CASCADE delete from camera to events."""
        # Arrange: Create camera with events
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        event_ids = []
        for i in range(3):
            event = Event(
                batch_id=unique_id("batch"),
                camera_id=camera_id,
                started_at=utc_now(),
            )
            session.add(event)
            await session.flush()
            event_ids.append(event.id)

        # Act: Delete camera
        await session.delete(camera)
        await session.flush()

        # Assert: All events deleted via CASCADE
        stmt = select(func.count()).select_from(Event).where(Event.id.in_(event_ids))
        result = await session.execute(stmt)
        assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_event_deletion_cascades_to_alerts(self, session: AsyncSession) -> None:
        """Verify CASCADE delete from event to alerts."""
        # Arrange: Create camera, event, and alerts
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id=unique_id("batch"),
            camera_id=camera_id,
            started_at=utc_now(),
        )
        session.add(event)
        await session.flush()

        alert_ids = []
        for i in range(3):
            alert = Alert(
                id=str(uuid4()),
                event_id=event.id,
                severity=AlertSeverity.MEDIUM,
                status=AlertStatus.PENDING,
                dedup_key=unique_id("dedup"),
            )
            session.add(alert)
            await session.flush()
            alert_ids.append(alert.id)

        # Act: Delete event
        await session.delete(event)
        await session.flush()

        # Assert: All alerts deleted via CASCADE
        stmt = select(func.count()).select_from(Alert).where(Alert.id.in_(alert_ids))
        result = await session.execute(stmt)
        assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_event_deletion_cascades_to_event_detections(self, session: AsyncSession) -> None:
        """Verify CASCADE delete from event to event_detections junction table."""
        # Arrange: Create camera, event, detections, and event_detections
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id=unique_id("batch"),
            camera_id=camera_id,
            started_at=utc_now(),
        )
        session.add(event)
        await session.flush()

        detection_ids = []
        for i in range(3):
            detection = Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/image_{i}.jpg",
            )
            session.add(detection)
            await session.flush()
            detection_ids.append(detection.id)

            # Link detection to event
            event_detection = EventDetection(
                event_id=event.id,
                detection_id=detection.id,
            )
            session.add(event_detection)

        await session.flush()

        # Verify event_detections exist
        stmt = (
            select(func.count())
            .select_from(EventDetection)
            .where(EventDetection.event_id == event.id)
        )
        result = await session.execute(stmt)
        assert result.scalar() == 3

        # Act: Delete event
        await session.delete(event)
        await session.flush()

        # Assert: All event_detections deleted via CASCADE
        stmt = (
            select(func.count())
            .select_from(EventDetection)
            .where(EventDetection.event_id == event.id)
        )
        result = await session.execute(stmt)
        assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_detection_deletion_cascades_to_event_detections(
        self, session: AsyncSession
    ) -> None:
        """Verify CASCADE delete from detection to event_detections junction table."""
        # Arrange: Create camera, event, detection, and event_detection
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id=unique_id("batch"),
            camera_id=camera_id,
            started_at=utc_now(),
        )
        session.add(event)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image.jpg",
        )
        session.add(detection)
        await session.flush()

        event_detection = EventDetection(
            event_id=event.id,
            detection_id=detection.id,
        )
        session.add(event_detection)
        await session.flush()

        # Act: Delete detection
        await session.delete(detection)
        await session.flush()

        # Assert: event_detection deleted via CASCADE
        stmt = (
            select(func.count())
            .select_from(EventDetection)
            .where(EventDetection.detection_id == detection.id)
        )
        result = await session.execute(stmt)
        assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_alert_rule_deletion_with_set_null_behavior(self, session: AsyncSession) -> None:
        """Verify that deleting alert rule cascades to delete associated alerts.

        Note: The AlertRule model has cascade='all, delete-orphan' which overrides
        the database FK's ondelete='SET NULL' behavior.
        """
        # Arrange: Create camera, event, rule, and alert
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id=unique_id("batch"),
            camera_id=camera_id,
            started_at=utc_now(),
        )
        session.add(event)
        await session.flush()

        rule = AlertRule(
            id=str(uuid4()),
            name="Test Rule",
            risk_threshold=70,
            severity=AlertSeverity.HIGH,
        )
        session.add(rule)
        await session.flush()

        alert = Alert(
            id=str(uuid4()),
            event_id=event.id,
            rule_id=rule.id,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            dedup_key=unique_id("dedup"),
        )
        session.add(alert)
        await session.flush()
        alert_id = alert.id

        # Act: Delete rule
        await session.delete(rule)
        await session.flush()

        # Assert: Alert deleted due to cascade='all, delete-orphan'
        stmt = select(Alert).where(Alert.id == alert_id)
        result = await session.execute(stmt)
        remaining = result.scalar_one_or_none()
        assert remaining is None

    @pytest.mark.asyncio
    async def test_camera_cascade_to_multiple_tables(self, session: AsyncSession) -> None:
        """Verify camera deletion cascades to all dependent tables simultaneously."""
        # Arrange: Create camera with multiple dependent records
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Multi-Cascade Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Create detections
        detection_ids = []
        for i in range(3):
            detection = Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/det_{i}.jpg",
            )
            session.add(detection)
            await session.flush()
            detection_ids.append(detection.id)

        # Create events
        event_ids = []
        for i in range(2):
            event = Event(
                batch_id=unique_id("batch"),
                camera_id=camera_id,
                started_at=utc_now(),
            )
            session.add(event)
            await session.flush()
            event_ids.append(event.id)

        # Act: Delete camera
        await session.delete(camera)
        await session.flush()

        # Assert: All dependent records deleted
        stmt = select(func.count()).select_from(Detection).where(Detection.id.in_(detection_ids))
        assert (await session.execute(stmt)).scalar() == 0

        stmt = select(func.count()).select_from(Event).where(Event.id.in_(event_ids))
        assert (await session.execute(stmt)).scalar() == 0


class TestDataConsistency:
    """Tests for data consistency validation across models.

    These tests verify that CHECK constraints, enum validations, and business rules
    are properly enforced at the database level.
    """

    @pytest.mark.asyncio
    async def test_event_timestamp_consistency_enforced(self, session: AsyncSession) -> None:
        """Verify that ended_at must be >= started_at."""
        # Arrange: Create camera
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Create event with ended_at before started_at
        now = utc_now()
        event = Event(
            batch_id=unique_id("batch"),
            camera_id=camera_id,
            started_at=now,
            ended_at=now - timedelta(hours=1),  # Invalid: before started_at
        )
        session.add(event)

        # Act & Assert: Should raise IntegrityError due to CHECK constraint
        with pytest.raises(IntegrityError) as exc_info:
            await session.flush()

        assert "ck_events_time_order" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_event_risk_score_range_enforced(self, session: AsyncSession) -> None:
        """Verify that risk_score must be between 0 and 100."""
        # Arrange: Create camera
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Create event with invalid risk_score
        event = Event(
            batch_id=unique_id("batch"),
            camera_id=camera_id,
            started_at=utc_now(),
            risk_score=150,  # Invalid: > 100
        )
        session.add(event)

        # Act & Assert: Should raise IntegrityError due to CHECK constraint
        with pytest.raises(IntegrityError) as exc_info:
            await session.flush()

        assert "ck_events_risk_score_range" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_event_risk_level_enum_enforced(self, session: AsyncSession) -> None:
        """Verify that risk_level must be a valid enum value."""
        # Arrange: Create camera
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Act & Assert: Use raw SQL to bypass ORM validation
        # Must include all NOT NULL columns
        with pytest.raises(IntegrityError) as exc_info:
            await session.execute(
                text(
                    """
                    INSERT INTO events (batch_id, camera_id, started_at, risk_level, reviewed, is_fast_path)
                    VALUES (:batch_id, :camera_id, :started_at, :risk_level, :reviewed, :is_fast_path)
                    """
                ),
                {
                    "batch_id": unique_id("batch"),
                    "camera_id": camera_id,
                    "started_at": utc_now(),
                    "risk_level": "invalid_level",  # Invalid enum value
                    "reviewed": False,
                    "is_fast_path": False,
                },
            )
            await session.flush()

        assert "ck_events_risk_level" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_detection_confidence_range_enforced(self, session: AsyncSession) -> None:
        """Verify that confidence must be between 0.0 and 1.0."""
        # Arrange: Create camera
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Create detection with invalid confidence
        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image.jpg",
            confidence=1.5,  # Invalid: > 1.0
        )
        session.add(detection)

        # Act & Assert: Should raise IntegrityError due to CHECK constraint
        with pytest.raises(IntegrityError) as exc_info:
            await session.flush()

        assert "ck_detections_confidence_range" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_detection_media_type_enum_enforced(self, session: AsyncSession) -> None:
        """Verify that media_type must be 'image' or 'video'."""
        # Arrange: Create camera
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Act & Assert: Use raw SQL to bypass ORM validation
        with pytest.raises(IntegrityError) as exc_info:
            await session.execute(
                text(
                    """
                    INSERT INTO detections (camera_id, file_path, media_type, detected_at)
                    VALUES (:camera_id, :file_path, :media_type, :detected_at)
                    """
                ),
                {
                    "camera_id": camera_id,
                    "file_path": f"/export/foscam/{camera_id}/image.jpg",
                    "media_type": "invalid_type",  # Invalid enum value
                    "detected_at": utc_now(),
                },
            )
            await session.flush()

        assert "ck_detections_media_type" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_camera_status_enum_enforced(self, session: AsyncSession) -> None:
        """Verify that camera status must be a valid enum value."""
        # Act & Assert: Use raw SQL to bypass ORM validation
        camera_id = unique_id("camera")
        with pytest.raises(IntegrityError) as exc_info:
            await session.execute(
                text(
                    """
                    INSERT INTO cameras (id, name, folder_path, status, created_at)
                    VALUES (:id, :name, :folder_path, :status, :created_at)
                    """
                ),
                {
                    "id": camera_id,
                    "name": "Test Camera",
                    "folder_path": f"/export/foscam/{camera_id}",
                    "status": "invalid_status",  # Invalid enum value
                    "created_at": utc_now(),
                },
            )
            await session.flush()

        assert "ck_cameras_status" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_alert_rule_risk_threshold_range_enforced(self, session: AsyncSession) -> None:
        """Verify that alert rule risk_threshold must be between 0 and 100."""
        # Arrange: Create alert rule with invalid risk_threshold
        rule = AlertRule(
            id=str(uuid4()),
            name="Invalid Rule",
            risk_threshold=150,  # Invalid: > 100
            severity=AlertSeverity.HIGH,
        )
        session.add(rule)

        # Act & Assert: Should raise IntegrityError due to CHECK constraint
        with pytest.raises(IntegrityError) as exc_info:
            await session.flush()

        assert "ck_alert_rules_risk_threshold_range" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_alert_rule_min_confidence_range_enforced(self, session: AsyncSession) -> None:
        """Verify that alert rule min_confidence must be between 0.0 and 1.0."""
        # Arrange: Create alert rule with invalid min_confidence
        rule = AlertRule(
            id=str(uuid4()),
            name="Invalid Rule",
            min_confidence=1.5,  # Invalid: > 1.0
            severity=AlertSeverity.HIGH,
        )
        session.add(rule)

        # Act & Assert: Should raise IntegrityError due to CHECK constraint
        with pytest.raises(IntegrityError) as exc_info:
            await session.flush()

        assert "ck_alert_rules_min_confidence_range" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_alert_rule_cooldown_non_negative_enforced(self, session: AsyncSession) -> None:
        """Verify that alert rule cooldown_seconds must be non-negative."""
        # Arrange: Create alert rule with negative cooldown
        rule = AlertRule(
            id=str(uuid4()),
            name="Invalid Rule",
            cooldown_seconds=-100,  # Invalid: negative
            severity=AlertSeverity.HIGH,
        )
        session.add(rule)

        # Act & Assert: Should raise IntegrityError due to CHECK constraint
        with pytest.raises(IntegrityError) as exc_info:
            await session.flush()

        assert "ck_alert_rules_cooldown_non_negative" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_event_detection_count_consistency(self, session: AsyncSession) -> None:
        """Verify that event detection_count property matches actual junction records."""
        # Arrange: Create camera, event, and detections
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id=unique_id("batch"),
            camera_id=camera_id,
            started_at=utc_now(),
        )
        session.add(event)
        await session.flush()

        # Create detections and link to event
        expected_count = 5
        for i in range(expected_count):
            detection = Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/image_{i}.jpg",
            )
            session.add(detection)
            await session.flush()

            event_detection = EventDetection(
                event_id=event.id,
                detection_id=detection.id,
            )
            session.add(event_detection)

        await session.flush()

        # Refresh event to load relationships
        await session.refresh(event, ["detections"])

        # Assert: detection_count matches actual count
        assert event.detection_count == expected_count
        assert len(event.detection_id_list) == expected_count


class TestCorruptionRecovery:
    """Tests for system resilience and recovery from data corruption scenarios.

    These tests verify that the system can gracefully handle corrupted data,
    log corruption events, and continue operating without cascading failures.
    """

    @pytest.mark.asyncio
    async def test_cascade_delete_maintains_referential_integrity(
        self, session: AsyncSession
    ) -> None:
        """Verify that CASCADE delete properly cleans up dependent records."""
        # Arrange: Create camera with detections
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Cascade Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection_ids = []
        for i in range(3):
            detection = Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/image_{i}.jpg",
            )
            session.add(detection)
            await session.flush()
            detection_ids.append(detection.id)

        # Act: Delete camera - should cascade to detections
        await session.delete(camera)
        await session.flush()

        # Assert: All detections deleted via CASCADE (no orphans)
        stmt = select(func.count()).select_from(Detection).where(Detection.id.in_(detection_ids))
        result = await session.execute(stmt)
        count = result.scalar()
        assert count == 0

        # Assert: Camera is also deleted
        stmt = select(Camera).where(Camera.id == camera_id)
        result = await session.execute(stmt)
        remaining_camera = result.scalar_one_or_none()
        assert remaining_camera is None

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_integrity_violation(self, session: AsyncSession) -> None:
        """Verify that integrity violations trigger rollback and can be recovered from."""
        # Arrange: Create valid camera and detection in a separate committed transaction
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Valid Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        valid_detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/valid.jpg",
        )
        session.add(valid_detection)
        await session.flush()
        await session.commit()  # Commit the valid data
        valid_detection_id = valid_detection.id

        # Act: In a new transaction, try to create invalid detection
        invalid_detection = Detection(
            camera_id="nonexistent_camera",
            file_path="/export/foscam/invalid/image.jpg",
        )
        session.add(invalid_detection)

        try:
            await session.flush()
            pytest.fail("Expected IntegrityError but flush succeeded")
        except IntegrityError:
            await session.rollback()

        # Assert: Valid detection still exists after rollback
        # (it was committed in the first transaction)
        stmt = select(Detection).where(Detection.id == valid_detection_id)
        result = await session.execute(stmt)
        recovered = result.scalar_one_or_none()
        assert recovered is not None

    @pytest.mark.asyncio
    async def test_unique_constraint_violation_handled(self, session: AsyncSession) -> None:
        """Verify that duplicate camera names are prevented by unique constraint."""
        # Arrange: Create first camera
        camera1_id = unique_id("camera1")
        camera1 = Camera(
            id=camera1_id,
            name="Duplicate Name",
            folder_path=f"/export/foscam/{camera1_id}",
        )
        session.add(camera1)
        await session.flush()

        # Act: Try to create second camera with same name
        camera2_id = unique_id("camera2")
        camera2 = Camera(
            id=camera2_id,
            name="Duplicate Name",  # Same name as camera1
            folder_path=f"/export/foscam/{camera2_id}",  # Different path
        )
        session.add(camera2)

        # Assert: Should raise IntegrityError due to unique constraint
        with pytest.raises(IntegrityError) as exc_info:
            await session.flush()

        assert "idx_cameras_name_unique" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_duplicate_folder_path_rejected(self, session: AsyncSession) -> None:
        """Verify that duplicate camera folder_paths are prevented by unique constraint."""
        # Arrange: Create first camera
        folder_path = f"/export/foscam/{unique_id('shared_folder')}"
        camera1_id = unique_id("camera1")
        camera1 = Camera(
            id=camera1_id,
            name="Camera 1",
            folder_path=folder_path,
        )
        session.add(camera1)
        await session.flush()

        # Act: Try to create second camera with same folder_path
        camera2_id = unique_id("camera2")
        camera2 = Camera(
            id=camera2_id,
            name="Camera 2",  # Different name
            folder_path=folder_path,  # Same path as camera1
        )
        session.add(camera2)

        # Assert: Should raise IntegrityError due to unique constraint
        with pytest.raises(IntegrityError) as exc_info:
            await session.flush()

        assert "idx_cameras_folder_path_unique" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_duplicate_event_detection_association_prevented(
        self, session: AsyncSession
    ) -> None:
        """Verify that duplicate event-detection associations are prevented."""
        # Arrange: Create camera, event, and detection
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id=unique_id("batch"),
            camera_id=camera_id,
            started_at=utc_now(),
        )
        session.add(event)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image.jpg",
        )
        session.add(detection)
        await session.flush()

        # Create first association
        event_detection1 = EventDetection(
            event_id=event.id,
            detection_id=detection.id,
        )
        session.add(event_detection1)
        await session.flush()

        # Act: Try to create duplicate association
        event_detection2 = EventDetection(
            event_id=event.id,
            detection_id=detection.id,  # Same event-detection pair
        )
        session.add(event_detection2)

        # Assert: Should raise IntegrityError due to primary key constraint
        with pytest.raises(IntegrityError) as exc_info:
            await session.flush()

        assert "event_detections_pkey" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_partial_batch_insert_failure_rolls_back(self, session: AsyncSession) -> None:
        """Verify that partial failures in batch operations trigger complete rollback."""
        # Arrange: Create camera
        camera_id = unique_id("camera")
        camera = Camera(
            id=camera_id,
            name="Batch Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Act: Try to create batch with one invalid item
        detections = [
            Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/valid1.jpg",
                confidence=0.9,
            ),
            Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/valid2.jpg",
                confidence=0.8,
            ),
            Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/invalid.jpg",
                confidence=1.5,  # Invalid: > 1.0
            ),
        ]

        for detection in detections:
            session.add(detection)

        # Assert: Should raise IntegrityError
        with pytest.raises(IntegrityError):
            await session.flush()

        # Rollback and verify no detections were persisted
        await session.rollback()

        stmt = select(func.count()).select_from(Detection).where(Detection.camera_id == camera_id)
        result = await session.execute(stmt)
        count = result.scalar()
        assert count == 0  # No partial inserts
