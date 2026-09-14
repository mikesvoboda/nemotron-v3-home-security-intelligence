"""Integration tests for SQLAlchemy model cascade behaviors.

Tests cascade delete operations for the security intelligence system models:
- Camera deletion cascades to detections, events, zones, and baselines
- Alert/AlertRule cascade behaviors
- Event deletion cascades to alerts

These tests verify that referential integrity is maintained and orphan
records are properly cleaned up when parent records are deleted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from backend.core.time_utils import utc_now
from backend.models import (
    ActivityBaseline,
    Alert,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    Camera,
    ClassBaseline,
    Detection,
    Event,
    Zone,
    ZoneShape,
    ZoneType,
)
from backend.tests.conftest import unique_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# Mark all tests as integration tests requiring real PostgreSQL database
pytestmark = pytest.mark.integration


class TestCameraCascadeToDetections:
    """Test Camera -> Detection cascade delete."""

    @pytest.mark.asyncio
    async def test_camera_deletion_deletes_detections(self, session: AsyncSession) -> None:
        """Verify that deleting a camera cascades to delete all its detections."""
        # Arrange: Create camera with detections
        camera_id = unique_id("cascade_cam")
        camera = Camera(
            id=camera_id,
            name="Cascade Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Create multiple detections for this camera
        detection_ids = []
        for i in range(5):
            detection = Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/image_{i:03d}.jpg",
                object_type="person",
                confidence=0.9,
            )
            session.add(detection)
            await session.flush()
            detection_ids.append(detection.id)

        # Verify detections exist
        stmt = select(func.count()).select_from(Detection).where(Detection.camera_id == camera_id)
        result = await session.execute(stmt)
        count_before = result.scalar()
        assert count_before == 5

        # Act: Delete the camera
        await session.delete(camera)
        await session.flush()

        # Assert: All detections should be deleted
        stmt = select(func.count()).select_from(Detection).where(Detection.id.in_(detection_ids))
        result = await session.execute(stmt)
        count_after = result.scalar()
        assert count_after == 0

    @pytest.mark.asyncio
    async def test_camera_deletion_does_not_affect_other_cameras_detections(
        self, session: AsyncSession
    ) -> None:
        """Verify that deleting one camera does not affect another camera's detections."""
        # Arrange: Create two cameras with detections
        camera1_id = unique_id("cam1")
        camera2_id = unique_id("cam2")

        camera1 = Camera(
            id=camera1_id,
            name="Camera 1",
            folder_path=f"/export/foscam/{camera1_id}",
        )
        camera2 = Camera(
            id=camera2_id,
            name="Camera 2",
            folder_path=f"/export/foscam/{camera2_id}",
        )
        session.add_all([camera1, camera2])
        await session.flush()

        # Create detections for both cameras
        detection1 = Detection(
            camera_id=camera1_id,
            file_path=f"/export/foscam/{camera1_id}/image_001.jpg",
        )
        detection2 = Detection(
            camera_id=camera2_id,
            file_path=f"/export/foscam/{camera2_id}/image_001.jpg",
        )
        session.add_all([detection1, detection2])
        await session.flush()
        detection2_id = detection2.id

        # Act: Delete camera1
        await session.delete(camera1)
        await session.flush()

        # Assert: camera2's detection should still exist
        stmt = select(Detection).where(Detection.id == detection2_id)
        result = await session.execute(stmt)
        remaining = result.scalar_one_or_none()
        assert remaining is not None
        assert remaining.camera_id == camera2_id


class TestCameraCascadeToEvents:
    """Test Camera -> Event cascade delete."""

    @pytest.mark.asyncio
    async def test_camera_deletion_deletes_events(self, session: AsyncSession) -> None:
        """Verify that deleting a camera cascades to delete all its events."""
        # Arrange: Create camera with events
        camera_id = unique_id("event_cam")
        camera = Camera(
            id=camera_id,
            name="Event Cascade Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Create multiple events for this camera
        event_ids = []
        for i in range(3):
            event = Event(
                batch_id=f"batch_{camera_id}_{i:03d}",
                camera_id=camera_id,
                started_at=utc_now(),
                risk_score=50 + i * 10,
            )
            session.add(event)
            await session.flush()
            event_ids.append(event.id)

        # Verify events exist
        stmt = select(func.count()).select_from(Event).where(Event.camera_id == camera_id)
        result = await session.execute(stmt)
        count_before = result.scalar()
        assert count_before == 3

        # Act: Delete the camera
        await session.delete(camera)
        await session.flush()

        # Assert: All events should be deleted
        stmt = select(func.count()).select_from(Event).where(Event.id.in_(event_ids))
        result = await session.execute(stmt)
        count_after = result.scalar()
        assert count_after == 0


class TestCameraCascadeToZones:
    """Test Camera -> Zone cascade delete."""

    @pytest.mark.asyncio
    async def test_camera_deletion_deletes_zones(self, session: AsyncSession) -> None:
        """Verify that deleting a camera cascades to delete all its zones."""
        # Arrange: Create camera with zones
        camera_id = unique_id("zone_cam")
        camera = Camera(
            id=camera_id,
            name="Zone Cascade Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Create multiple zones for this camera
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

        # Verify zones exist
        stmt = select(func.count()).select_from(Zone).where(Zone.camera_id == camera_id)
        result = await session.execute(stmt)
        count_before = result.scalar()
        assert count_before == 3

        # Act: Delete the camera
        await session.delete(camera)
        await session.flush()

        # Assert: All zones should be deleted
        stmt = select(func.count()).select_from(Zone).where(Zone.id.in_(zone_ids))
        result = await session.execute(stmt)
        count_after = result.scalar()
        assert count_after == 0


class TestCameraCascadeToBaselines:
    """Test Camera -> ActivityBaseline and ClassBaseline cascade delete with passive_deletes."""

    @pytest.mark.asyncio
    async def test_camera_deletion_deletes_activity_baselines(self, session: AsyncSession) -> None:
        """Verify that deleting a camera cascades to delete all its activity baselines."""
        # Arrange: Create camera with activity baselines
        camera_id = unique_id("baseline_cam")
        camera = Camera(
            id=camera_id,
            name="Baseline Cascade Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Create activity baselines for different time slots
        baseline_ids = []
        for hour in range(24):
            baseline = ActivityBaseline(
                camera_id=camera_id,
                hour=hour,
                day_of_week=0,  # Monday
                avg_count=10.0 + hour,
                sample_count=100,
            )
            session.add(baseline)
            await session.flush()
            baseline_ids.append(baseline.id)

        # Verify baselines exist
        stmt = (
            select(func.count())
            .select_from(ActivityBaseline)
            .where(ActivityBaseline.camera_id == camera_id)
        )
        result = await session.execute(stmt)
        count_before = result.scalar()
        assert count_before == 24

        # Act: Delete the camera
        await session.delete(camera)
        await session.flush()

        # Assert: All activity baselines should be deleted
        stmt = (
            select(func.count())
            .select_from(ActivityBaseline)
            .where(ActivityBaseline.id.in_(baseline_ids))
        )
        result = await session.execute(stmt)
        count_after = result.scalar()
        assert count_after == 0

    @pytest.mark.asyncio
    async def test_camera_deletion_deletes_class_baselines(self, session: AsyncSession) -> None:
        """Verify that deleting a camera cascades to delete all its class baselines."""
        # Arrange: Create camera with class baselines
        camera_id = unique_id("class_baseline_cam")
        camera = Camera(
            id=camera_id,
            name="Class Baseline Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Create class baselines for different detection classes
        baseline_ids = []
        for cls in ["person", "vehicle", "animal"]:
            for hour in range(6):  # Just first 6 hours for brevity
                baseline = ClassBaseline(
                    camera_id=camera_id,
                    detection_class=cls,
                    hour=hour,
                    frequency=0.1 * hour,
                    sample_count=50,
                )
                session.add(baseline)
                await session.flush()
                baseline_ids.append(baseline.id)

        # Verify baselines exist
        stmt = (
            select(func.count())
            .select_from(ClassBaseline)
            .where(ClassBaseline.camera_id == camera_id)
        )
        result = await session.execute(stmt)
        count_before = result.scalar()
        assert count_before == 18  # 3 classes * 6 hours

        # Act: Delete the camera
        await session.delete(camera)
        await session.flush()

        # Assert: All class baselines should be deleted
        stmt = (
            select(func.count())
            .select_from(ClassBaseline)
            .where(ClassBaseline.id.in_(baseline_ids))
        )
        result = await session.execute(stmt)
        count_after = result.scalar()
        assert count_after == 0


class TestCameraCompleteCascade:
    """Test complete cascade behavior when deleting a camera with all related records."""

    @pytest.mark.asyncio
    async def test_camera_deletion_cascades_all_relationships(self, session: AsyncSession) -> None:
        """Verify that deleting a camera cascades to all related tables."""
        # Arrange: Create camera with all related records
        camera_id = unique_id("full_cascade_cam")
        camera = Camera(
            id=camera_id,
            name="Full Cascade Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Create detections
        for i in range(3):
            detection = Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/image_{i}.jpg",
            )
            session.add(detection)

        # Create events
        for i in range(2):
            event = Event(
                batch_id=f"batch_{camera_id}_{i}",
                camera_id=camera_id,
                started_at=utc_now(),
            )
            session.add(event)

        # Create zones
        zone = Zone(
            id=f"{camera_id}_zone",
            camera_id=camera_id,
            name="Test Zone",
            zone_type=ZoneType.ENTRY_POINT,
            shape=ZoneShape.RECTANGLE,
            coordinates=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        )
        session.add(zone)

        # Create activity baseline
        activity_baseline = ActivityBaseline(
            camera_id=camera_id,
            hour=12,
            day_of_week=3,
            avg_count=5.0,
        )
        session.add(activity_baseline)

        # Create class baseline
        class_baseline = ClassBaseline(
            camera_id=camera_id,
            detection_class="person",
            hour=12,
            frequency=0.5,
        )
        session.add(class_baseline)

        await session.flush()

        # Verify all records exist before deletion
        assert (
            await session.execute(
                select(func.count()).select_from(Detection).where(Detection.camera_id == camera_id)
            )
        ).scalar() == 3
        assert (
            await session.execute(
                select(func.count()).select_from(Event).where(Event.camera_id == camera_id)
            )
        ).scalar() == 2
        assert (
            await session.execute(
                select(func.count()).select_from(Zone).where(Zone.camera_id == camera_id)
            )
        ).scalar() == 1
        assert (
            await session.execute(
                select(func.count())
                .select_from(ActivityBaseline)
                .where(ActivityBaseline.camera_id == camera_id)
            )
        ).scalar() == 1
        assert (
            await session.execute(
                select(func.count())
                .select_from(ClassBaseline)
                .where(ClassBaseline.camera_id == camera_id)
            )
        ).scalar() == 1

        # Act: Delete the camera
        await session.delete(camera)
        await session.flush()

        # Assert: All related records should be deleted
        assert (
            await session.execute(
                select(func.count()).select_from(Detection).where(Detection.camera_id == camera_id)
            )
        ).scalar() == 0
        assert (
            await session.execute(
                select(func.count()).select_from(Event).where(Event.camera_id == camera_id)
            )
        ).scalar() == 0
        assert (
            await session.execute(
                select(func.count()).select_from(Zone).where(Zone.camera_id == camera_id)
            )
        ).scalar() == 0
        assert (
            await session.execute(
                select(func.count())
                .select_from(ActivityBaseline)
                .where(ActivityBaseline.camera_id == camera_id)
            )
        ).scalar() == 0
        assert (
            await session.execute(
                select(func.count())
                .select_from(ClassBaseline)
                .where(ClassBaseline.camera_id == camera_id)
            )
        ).scalar() == 0


class TestAlertEventCascade:
    """Test Alert -> Event cascade delete (ondelete='CASCADE')."""

    @pytest.mark.asyncio
    async def test_event_deletion_deletes_alerts(self, session: AsyncSession) -> None:
        """Verify that deleting an event cascades to delete all its alerts."""
        # Arrange: Create camera, event, and alerts
        camera_id = unique_id("alert_cam")
        camera = Camera(
            id=camera_id,
            name="Alert Cascade Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id=f"batch_{camera_id}_alert",
            camera_id=camera_id,
            started_at=utc_now(),
            risk_score=80,
        )
        session.add(event)
        await session.flush()

        # Create multiple alerts for this event
        alert_ids = []
        for i in range(3):
            alert = Alert(
                id=str(uuid4()),
                event_id=event.id,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key=f"{camera_id}:alert:{i}",
            )
            session.add(alert)
            await session.flush()
            alert_ids.append(alert.id)

        # Verify alerts exist
        stmt = select(func.count()).select_from(Alert).where(Alert.event_id == event.id)
        result = await session.execute(stmt)
        count_before = result.scalar()
        assert count_before == 3

        # Act: Delete the event
        await session.delete(event)
        await session.flush()

        # Assert: All alerts should be deleted
        stmt = select(func.count()).select_from(Alert).where(Alert.id.in_(alert_ids))
        result = await session.execute(stmt)
        count_after = result.scalar()
        assert count_after == 0


class TestAlertRuleCascade:
    """Test Alert -> AlertRule cascade behavior.

    Note: The AlertRule model has cascade='all, delete-orphan' on the alerts relationship.
    This means SQLAlchemy will explicitly delete alerts when the rule is deleted, even though
    the FK has ondelete='SET NULL'. The SQLAlchemy cascade takes precedence over the database
    FK constraint when deleting through the ORM.
    """

    @pytest.mark.asyncio
    async def test_alert_rule_deletion_deletes_alerts_via_cascade(
        self, session: AsyncSession
    ) -> None:
        """Verify that deleting an alert rule cascades to delete its alerts.

        The AlertRule.alerts relationship has cascade='all, delete-orphan', which includes
        the 'delete' cascade. This causes SQLAlchemy to explicitly delete alerts before
        the parent rule is deleted, overriding the database's SET NULL FK constraint.
        """
        # Arrange: Create camera, event, alert rule, and alert
        camera_id = unique_id("rule_cam")
        camera = Camera(
            id=camera_id,
            name="Rule Cascade Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id=f"batch_{camera_id}_rule",
            camera_id=camera_id,
            started_at=utc_now(),
            risk_score=75,
        )
        session.add(event)
        await session.flush()

        # Create alert rule
        rule = AlertRule(
            id=str(uuid4()),
            name="High Risk Alert Rule",
            risk_threshold=70,
            severity=AlertSeverity.HIGH,
        )
        session.add(rule)
        await session.flush()
        rule_id = rule.id

        # Create alert linked to the rule
        alert = Alert(
            id=str(uuid4()),
            event_id=event.id,
            rule_id=rule.id,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            dedup_key=f"{camera_id}:rule_test",
        )
        session.add(alert)
        await session.flush()
        alert_id = alert.id

        # Verify alert has rule_id set
        stmt = select(Alert).where(Alert.id == alert_id)
        result = await session.execute(stmt)
        alert_before = result.scalar_one()
        assert alert_before.rule_id == rule_id

        # Act: Delete the alert rule
        await session.delete(rule)
        await session.flush()

        # Assert: Alert should be deleted due to cascade='all, delete-orphan'
        stmt = select(Alert).where(Alert.id == alert_id)
        result = await session.execute(stmt)
        alert_after = result.scalar_one_or_none()
        assert alert_after is None


class TestAlertRuleAlertsCascade:
    """Test AlertRule.alerts cascade='all, delete-orphan' behavior."""

    @pytest.mark.asyncio
    async def test_alert_rule_deletion_deletes_alerts_via_delete_orphan(
        self, session: AsyncSession
    ) -> None:
        """Test that AlertRule deletion cascades to delete associated alerts.

        The AlertRule model has cascade='all, delete-orphan' on the alerts relationship.
        This includes the 'delete' cascade, which causes SQLAlchemy to issue explicit
        DELETE statements for alerts before deleting the rule.
        """
        # Arrange: Create camera, event, alert rule, and alert
        camera_id = unique_id("orphan_cam")
        camera = Camera(
            id=camera_id,
            name="Orphan Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id=f"batch_{camera_id}_orphan",
            camera_id=camera_id,
            started_at=utc_now(),
            risk_score=85,
        )
        session.add(event)
        await session.flush()

        rule = AlertRule(
            id=str(uuid4()),
            name="Test Rule for Orphan",
            risk_threshold=80,
            severity=AlertSeverity.CRITICAL,
        )
        session.add(rule)
        await session.flush()

        # Create alert linked to the rule
        alert = Alert(
            id=str(uuid4()),
            event_id=event.id,
            rule_id=rule.id,
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.PENDING,
            dedup_key=f"{camera_id}:orphan_test",
        )
        session.add(alert)
        await session.flush()
        alert_id = alert.id

        # Verify alert exists
        stmt = select(func.count()).select_from(Alert).where(Alert.id == alert_id)
        result = await session.execute(stmt)
        assert result.scalar() == 1

        # Act: Delete the rule
        await session.delete(rule)
        await session.flush()

        # Assert: Alert should be deleted due to cascade
        stmt = select(Alert).where(Alert.id == alert_id)
        result = await session.execute(stmt)
        remaining_alert = result.scalar_one_or_none()
        assert remaining_alert is None


class TestEventAlertsCascade:
    """Test Event.alerts cascade='all, delete-orphan' behavior."""

    @pytest.mark.asyncio
    async def test_event_alerts_cascade_delete_orphan(self, session: AsyncSession) -> None:
        """Verify that Event.alerts cascade properly deletes orphaned alerts."""
        # Arrange: Create camera and event with alerts
        camera_id = unique_id("event_orphan_cam")
        camera = Camera(
            id=camera_id,
            name="Event Orphan Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id=f"batch_{camera_id}_event_orphan",
            camera_id=camera_id,
            started_at=utc_now(),
            risk_score=90,
        )
        session.add(event)
        await session.flush()

        # Create alerts for the event
        alert_ids = []
        for i in range(2):
            alert = Alert(
                id=str(uuid4()),
                event_id=event.id,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key=f"{camera_id}:event_orphan:{i}",
            )
            session.add(alert)
            await session.flush()
            alert_ids.append(alert.id)

        # Verify alerts exist
        stmt = select(func.count()).select_from(Alert).where(Alert.id.in_(alert_ids))
        result = await session.execute(stmt)
        assert result.scalar() == 2

        # Act: Delete the event
        await session.delete(event)
        await session.flush()

        # Assert: All alerts should be deleted due to cascade
        stmt = select(func.count()).select_from(Alert).where(Alert.id.in_(alert_ids))
        result = await session.execute(stmt)
        assert result.scalar() == 0


class TestCameraEventAlertChain:
    """Test the full cascade chain: Camera -> Event -> Alert."""

    @pytest.mark.asyncio
    async def test_camera_deletion_cascades_through_events_to_alerts(
        self, session: AsyncSession
    ) -> None:
        """Verify that deleting a camera cascades through events to delete alerts."""
        # Arrange: Create camera, events, and alerts
        camera_id = unique_id("chain_cam")
        camera = Camera(
            id=camera_id,
            name="Chain Cascade Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Create events
        event_ids = []
        alert_ids = []
        for i in range(2):
            event = Event(
                batch_id=f"batch_{camera_id}_chain_{i}",
                camera_id=camera_id,
                started_at=utc_now(),
                risk_score=70 + i * 10,
            )
            session.add(event)
            await session.flush()
            event_ids.append(event.id)

            # Create alerts for each event
            for j in range(2):
                alert = Alert(
                    id=str(uuid4()),
                    event_id=event.id,
                    severity=AlertSeverity.MEDIUM,
                    status=AlertStatus.PENDING,
                    dedup_key=f"{camera_id}:chain:{i}:{j}",
                )
                session.add(alert)
                await session.flush()
                alert_ids.append(alert.id)

        # Verify data exists
        assert (
            await session.execute(
                select(func.count()).select_from(Event).where(Event.id.in_(event_ids))
            )
        ).scalar() == 2
        assert (
            await session.execute(
                select(func.count()).select_from(Alert).where(Alert.id.in_(alert_ids))
            )
        ).scalar() == 4

        # Act: Delete the camera
        await session.delete(camera)
        await session.flush()

        # Assert: All events and alerts should be deleted
        assert (
            await session.execute(
                select(func.count()).select_from(Event).where(Event.id.in_(event_ids))
            )
        ).scalar() == 0
        assert (
            await session.execute(
                select(func.count()).select_from(Alert).where(Alert.id.in_(alert_ids))
            )
        ).scalar() == 0


class TestAlertRuleWithMultipleAlerts:
    """Test AlertRule with multiple alerts behavior."""

    @pytest.mark.asyncio
    async def test_alert_rule_deletion_cascades_to_all_alerts(self, session: AsyncSession) -> None:
        """Verify alert rule deletion cascades to delete all alerts from multiple events.

        The AlertRule model has cascade='all, delete-orphan', which deletes all alerts
        linked to the rule when the rule is deleted, regardless of which event they belong to.
        """
        # Arrange: Create camera, multiple events, one rule, and multiple alerts
        camera_id = unique_id("multi_alert_cam")
        camera = Camera(
            id=camera_id,
            name="Multi Alert Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Create alert rule
        rule = AlertRule(
            id=str(uuid4()),
            name="Multi-Event Rule",
            risk_threshold=60,
            severity=AlertSeverity.MEDIUM,
        )
        session.add(rule)
        await session.flush()
        rule_id = rule.id

        # Create multiple events with alerts linked to the same rule
        alert_ids = []
        event_ids = []
        for i in range(3):
            event = Event(
                batch_id=f"batch_{camera_id}_multi_{i}",
                camera_id=camera_id,
                started_at=utc_now(),
                risk_score=65 + i * 5,
            )
            session.add(event)
            await session.flush()
            event_ids.append(event.id)

            alert = Alert(
                id=str(uuid4()),
                event_id=event.id,
                rule_id=rule.id,
                severity=AlertSeverity.MEDIUM,
                status=AlertStatus.PENDING,
                dedup_key=f"{camera_id}:multi:{i}",
            )
            session.add(alert)
            await session.flush()
            alert_ids.append(alert.id)

        # Verify all alerts have rule_id set
        for alert_id in alert_ids:
            stmt = select(Alert).where(Alert.id == alert_id)
            result = await session.execute(stmt)
            alert = result.scalar_one()
            assert alert.rule_id == rule_id

        # Verify alerts count before deletion
        stmt = select(func.count()).select_from(Alert).where(Alert.id.in_(alert_ids))
        result = await session.execute(stmt)
        assert result.scalar() == 3

        # Act: Delete the rule
        await session.delete(rule)
        await session.flush()

        # Assert: All alerts should be deleted due to cascade
        stmt = select(func.count()).select_from(Alert).where(Alert.id.in_(alert_ids))
        result = await session.execute(stmt)
        assert result.scalar() == 0

        # But events should still exist (they're not deleted via rule cascade)
        stmt = select(func.count()).select_from(Event).where(Event.id.in_(event_ids))
        result = await session.execute(stmt)
        assert result.scalar() == 3


class TestOrphanCleanup:
    """Test orphan record cleanup behaviors."""

    @pytest.mark.asyncio
    async def test_removing_alert_from_event_relationship_deletes_orphan(
        self, session: AsyncSession
    ) -> None:
        """Verify that removing an alert from event.alerts relationship orphans it for deletion."""
        # Arrange: Create camera, event, and alerts
        camera_id = unique_id("orphan_cleanup_cam")
        camera = Camera(
            id=camera_id,
            name="Orphan Cleanup Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id=f"batch_{camera_id}_orphan_cleanup",
            camera_id=camera_id,
            started_at=utc_now(),
            risk_score=75,
        )
        session.add(event)
        await session.flush()

        alert = Alert(
            id=str(uuid4()),
            event_id=event.id,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            dedup_key=f"{camera_id}:orphan_cleanup",
        )
        session.add(alert)
        await session.flush()
        alert_id = alert.id

        # Refresh to load relationships
        await session.refresh(event, ["alerts"])

        # Verify alert is in event.alerts
        assert len(event.alerts) == 1

        # Act: Remove alert from relationship (orphan it)
        event.alerts.clear()
        await session.flush()

        # Assert: Alert should be deleted due to delete-orphan cascade
        stmt = select(Alert).where(Alert.id == alert_id)
        result = await session.execute(stmt)
        remaining = result.scalar_one_or_none()
        assert remaining is None
