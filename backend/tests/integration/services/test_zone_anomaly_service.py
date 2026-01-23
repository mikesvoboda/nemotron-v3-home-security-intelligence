"""Integration tests for zone anomaly detection service.

Tests verify real database interactions for the ZoneAnomalyService including:
- Anomaly persistence to PostgreSQL
- Query methods with real database
- Acknowledgment workflow
- Integration with zone baseline service

Related: NEM-3198 (Backend Anomaly Detection Service)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from backend.models.camera import Camera
from backend.models.camera_zone import CameraZone
from backend.models.zone_anomaly import AnomalySeverity, AnomalyType, ZoneAnomaly
from backend.models.zone_baseline import ZoneActivityBaseline

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def sample_camera(db_session) -> Camera:
    """Create a sample camera for testing."""
    camera = Camera(
        id="test_anomaly_camera",
        name="Test Camera for Anomalies",
        status="active",
        folder_path="/test/anomaly",
    )
    db_session.add(camera)
    await db_session.flush()
    return camera


@pytest.fixture
async def sample_zone(db_session, sample_camera) -> CameraZone:
    """Create a sample zone for testing."""
    zone = CameraZone(
        id=str(uuid.uuid4()),
        camera_id=sample_camera.id,
        name="Test Zone",
        coordinates=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
        enabled=True,
    )
    db_session.add(zone)
    await db_session.flush()
    return zone


@pytest.fixture
async def sample_baseline(db_session, sample_zone) -> ZoneActivityBaseline:
    """Create a sample baseline for testing."""
    baseline = ZoneActivityBaseline(
        zone_id=sample_zone.id,
        camera_id=sample_zone.camera_id,
        sample_count=100,
        hourly_pattern=[0.0] * 6 + [5.0] * 12 + [0.0] * 6,  # Activity 6am-6pm
        hourly_std=[0.0] * 6 + [1.0] * 12 + [0.0] * 6,
        daily_pattern=[10.0] * 5 + [5.0] * 2,  # Less on weekends
        daily_std=[2.0] * 7,
        entity_class_distribution={"person": 50, "vehicle": 30},
        mean_daily_count=30.0,
        std_daily_count=8.0,
        min_daily_count=10,
        max_daily_count=60,
        typical_dwell_time=30.0,
        typical_dwell_std=10.0,
        typical_crossing_rate=5.0,
        typical_crossing_std=2.0,
        last_updated=datetime.now(UTC),
    )
    db_session.add(baseline)
    await db_session.flush()
    return baseline


@pytest.fixture
async def sample_anomalies(db_session, sample_zone) -> list[ZoneAnomaly]:
    """Create sample anomalies for testing queries."""
    now = datetime.now(UTC)
    anomalies = [
        ZoneAnomaly(
            zone_id=uuid.UUID(sample_zone.id),
            camera_id=sample_zone.camera_id,
            anomaly_type=AnomalyType.UNUSUAL_TIME,
            severity=AnomalySeverity.WARNING,
            title="Unusual activity at 03:00",
            description="Test anomaly 1",
            expected_value=0.0,
            actual_value=1.0,
            deviation=3.5,
            timestamp=now - timedelta(hours=2),
        ),
        ZoneAnomaly(
            zone_id=uuid.UUID(sample_zone.id),
            camera_id=sample_zone.camera_id,
            anomaly_type=AnomalyType.UNUSUAL_FREQUENCY,
            severity=AnomalySeverity.CRITICAL,
            title="Spike in activity",
            description="Test anomaly 2",
            expected_value=5.0,
            actual_value=25.0,
            deviation=4.5,
            timestamp=now - timedelta(hours=1),
            acknowledged=True,
            acknowledged_at=now - timedelta(minutes=30),
            acknowledged_by="test_user",
        ),
        ZoneAnomaly(
            zone_id=uuid.UUID(sample_zone.id),
            camera_id=sample_zone.camera_id,
            anomaly_type=AnomalyType.UNUSUAL_DWELL,
            severity=AnomalySeverity.INFO,
            title="Extended dwell time",
            description="Test anomaly 3",
            expected_value=30.0,
            actual_value=90.0,
            deviation=2.0,
            timestamp=now,
        ),
    ]
    for anomaly in anomalies:
        db_session.add(anomaly)
    await db_session.flush()
    return anomalies


# =============================================================================
# Model Tests
# =============================================================================


class TestZoneAnomalyModel:
    """Tests for ZoneAnomaly model database operations."""

    @pytest.mark.asyncio
    async def test_create_anomaly(self, db_session, sample_zone) -> None:
        """Test creating an anomaly in the database."""
        anomaly = ZoneAnomaly(
            zone_id=uuid.UUID(sample_zone.id),
            camera_id=sample_zone.camera_id,
            anomaly_type=AnomalyType.UNUSUAL_TIME,
            severity=AnomalySeverity.WARNING,
            title="Test anomaly",
            expected_value=0.0,
            actual_value=1.0,
            deviation=3.0,
        )
        db_session.add(anomaly)
        await db_session.flush()

        # Verify it was created with ID
        assert anomaly.id is not None
        assert anomaly.anomaly_type == AnomalyType.UNUSUAL_TIME
        assert anomaly.severity == AnomalySeverity.WARNING
        assert anomaly.acknowledged is False

    @pytest.mark.asyncio
    async def test_query_anomalies_by_zone(self, db_session, sample_zone, sample_anomalies) -> None:
        """Test querying anomalies by zone ID."""
        stmt = select(ZoneAnomaly).where(ZoneAnomaly.zone_id == uuid.UUID(sample_zone.id))
        result = await db_session.execute(stmt)
        anomalies = result.scalars().all()

        assert len(anomalies) == 3

    @pytest.mark.asyncio
    async def test_query_unacknowledged_anomalies(
        self, db_session, sample_zone, sample_anomalies
    ) -> None:
        """Test querying only unacknowledged anomalies."""
        stmt = select(ZoneAnomaly).where(
            ZoneAnomaly.zone_id == uuid.UUID(sample_zone.id),
            ZoneAnomaly.acknowledged == False,  # noqa: E712
        )
        result = await db_session.execute(stmt)
        anomalies = result.scalars().all()

        assert len(anomalies) == 2  # 1 is acknowledged

    @pytest.mark.asyncio
    async def test_query_anomalies_by_severity(
        self, db_session, sample_zone, sample_anomalies
    ) -> None:
        """Test querying anomalies by severity."""
        stmt = select(ZoneAnomaly).where(
            ZoneAnomaly.zone_id == uuid.UUID(sample_zone.id),
            ZoneAnomaly.severity == AnomalySeverity.CRITICAL,
        )
        result = await db_session.execute(stmt)
        anomalies = result.scalars().all()

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_acknowledge_anomaly(self, db_session, sample_zone) -> None:
        """Test acknowledging an anomaly."""
        anomaly = ZoneAnomaly(
            zone_id=uuid.UUID(sample_zone.id),
            camera_id=sample_zone.camera_id,
            anomaly_type=AnomalyType.UNUSUAL_FREQUENCY,
            severity=AnomalySeverity.WARNING,
            title="Test",
            deviation=3.0,
        )
        db_session.add(anomaly)
        await db_session.flush()

        # Acknowledge
        anomaly.acknowledge("admin@example.com")
        await db_session.flush()

        # Refresh and verify
        await db_session.refresh(anomaly)
        assert anomaly.acknowledged is True
        assert anomaly.acknowledged_at is not None
        assert anomaly.acknowledged_by == "admin@example.com"


# =============================================================================
# Service Integration Tests
# =============================================================================


class TestZoneAnomalyServiceIntegration:
    """Integration tests for ZoneAnomalyService with real database."""

    @pytest.mark.asyncio
    async def test_get_anomalies_for_zone(self, db_session, sample_zone, sample_anomalies) -> None:
        """Test getting anomalies for a zone via service."""
        from backend.services.zone_anomaly_service import (
            ZoneAnomalyService,
            reset_zone_anomaly_service,
        )

        reset_zone_anomaly_service()
        service = ZoneAnomalyService()

        anomalies = await service.get_anomalies_for_zone(
            uuid.UUID(sample_zone.id), session=db_session
        )

        assert len(anomalies) == 3

    @pytest.mark.asyncio
    async def test_get_anomalies_with_since_filter(
        self, db_session, sample_zone, sample_anomalies
    ) -> None:
        """Test filtering anomalies by timestamp."""
        from backend.services.zone_anomaly_service import (
            ZoneAnomalyService,
            reset_zone_anomaly_service,
        )

        reset_zone_anomaly_service()
        service = ZoneAnomalyService()

        # Get only anomalies from the last hour
        since = datetime.now(UTC) - timedelta(minutes=90)
        anomalies = await service.get_anomalies_for_zone(
            uuid.UUID(sample_zone.id), since=since, session=db_session
        )

        # Should get 2 anomalies (1 hour old and recent)
        assert len(anomalies) == 2

    @pytest.mark.asyncio
    async def test_get_anomalies_unacknowledged_only(
        self, db_session, sample_zone, sample_anomalies
    ) -> None:
        """Test filtering to only unacknowledged anomalies."""
        from backend.services.zone_anomaly_service import (
            ZoneAnomalyService,
            reset_zone_anomaly_service,
        )

        reset_zone_anomaly_service()
        service = ZoneAnomalyService()

        anomalies = await service.get_anomalies_for_zone(
            uuid.UUID(sample_zone.id), unacknowledged_only=True, session=db_session
        )

        assert len(anomalies) == 2

    @pytest.mark.asyncio
    async def test_acknowledge_anomaly_via_service(self, db_session, sample_zone) -> None:
        """Test acknowledging an anomaly via service."""
        from backend.services.zone_anomaly_service import (
            ZoneAnomalyService,
            reset_zone_anomaly_service,
        )

        # Create an anomaly
        anomaly = ZoneAnomaly(
            zone_id=uuid.UUID(sample_zone.id),
            camera_id=sample_zone.camera_id,
            anomaly_type=AnomalyType.UNUSUAL_TIME,
            severity=AnomalySeverity.WARNING,
            title="Test",
            deviation=3.0,
        )
        db_session.add(anomaly)
        await db_session.flush()

        reset_zone_anomaly_service()
        service = ZoneAnomalyService()

        # Acknowledge via service
        result = await service.acknowledge_anomaly(
            anomaly.id, acknowledged_by="test_user", session=db_session
        )

        assert result is not None
        assert result.acknowledged is True
        assert result.acknowledged_by == "test_user"

    @pytest.mark.asyncio
    async def test_acknowledge_nonexistent_anomaly(self, db_session) -> None:
        """Test acknowledging a non-existent anomaly returns None."""
        from backend.services.zone_anomaly_service import (
            ZoneAnomalyService,
            reset_zone_anomaly_service,
        )

        reset_zone_anomaly_service()
        service = ZoneAnomalyService()

        result = await service.acknowledge_anomaly(
            uuid.uuid4(), acknowledged_by="test_user", session=db_session
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_anomaly_counts_by_zone(
        self, db_session, sample_zone, sample_anomalies
    ) -> None:
        """Test getting anomaly counts grouped by zone."""
        from backend.services.zone_anomaly_service import (
            ZoneAnomalyService,
            reset_zone_anomaly_service,
        )

        reset_zone_anomaly_service()
        service = ZoneAnomalyService()

        counts = await service.get_anomaly_counts_by_zone(session=db_session)

        assert sample_zone.id in counts
        assert counts[sample_zone.id] == 3

    @pytest.mark.asyncio
    async def test_get_anomaly_counts_filtered_by_camera(
        self, db_session, sample_zone, sample_anomalies
    ) -> None:
        """Test getting anomaly counts filtered by camera ID."""
        from backend.services.zone_anomaly_service import (
            ZoneAnomalyService,
            reset_zone_anomaly_service,
        )

        reset_zone_anomaly_service()
        service = ZoneAnomalyService()

        counts = await service.get_anomaly_counts_by_zone(
            camera_id=sample_zone.camera_id, session=db_session
        )

        assert sample_zone.id in counts
        assert counts[sample_zone.id] == 3

        # Filter by non-existent camera
        counts = await service.get_anomaly_counts_by_zone(
            camera_id="nonexistent_camera", session=db_session
        )

        assert len(counts) == 0


# =============================================================================
# Relationship Tests
# =============================================================================


class TestZoneAnomalyRelationships:
    """Tests for zone anomaly model relationships."""

    @pytest.mark.asyncio
    async def test_zone_to_anomalies_relationship(
        self, db_session, sample_zone, sample_anomalies
    ) -> None:
        """Test loading anomalies through zone relationship."""
        stmt = select(CameraZone).where(CameraZone.id == sample_zone.id)
        result = await db_session.execute(stmt)
        zone = result.scalar_one()

        # Load the anomalies relationship
        await db_session.refresh(zone, ["anomalies"])

        assert len(zone.anomalies) == 3

    @pytest.mark.asyncio
    async def test_cascade_delete_zone_deletes_anomalies(
        self, db_session, sample_camera, sample_zone, sample_anomalies
    ) -> None:
        """Test that deleting a zone cascades to delete anomalies."""
        zone_id = sample_zone.id

        # Verify anomalies exist
        stmt = select(ZoneAnomaly).where(ZoneAnomaly.zone_id == uuid.UUID(zone_id))
        result = await db_session.execute(stmt)
        anomalies_before = result.scalars().all()
        assert len(anomalies_before) == 3

        # Delete the zone
        await db_session.delete(sample_zone)
        await db_session.flush()

        # Verify anomalies are deleted
        stmt = select(ZoneAnomaly).where(ZoneAnomaly.zone_id == uuid.UUID(zone_id))
        result = await db_session.execute(stmt)
        anomalies_after = result.scalars().all()
        assert len(anomalies_after) == 0


# =============================================================================
# Constraint Tests
# =============================================================================


class TestZoneAnomalyConstraints:
    """Tests for database constraints on zone anomaly model."""

    @pytest.mark.asyncio
    async def test_valid_anomaly_type_constraint(self, db_session, sample_zone) -> None:
        """Test that only valid anomaly types are accepted."""
        # Valid anomaly types should work
        for anomaly_type in AnomalyType:
            anomaly = ZoneAnomaly(
                zone_id=uuid.UUID(sample_zone.id),
                camera_id=sample_zone.camera_id,
                anomaly_type=anomaly_type,
                severity=AnomalySeverity.INFO,
                title=f"Test {anomaly_type}",
                deviation=2.0,
            )
            db_session.add(anomaly)
        await db_session.flush()

    @pytest.mark.asyncio
    async def test_valid_severity_constraint(self, db_session, sample_zone) -> None:
        """Test that only valid severity levels are accepted."""
        # Valid severities should work
        for severity in AnomalySeverity:
            anomaly = ZoneAnomaly(
                zone_id=uuid.UUID(sample_zone.id),
                camera_id=sample_zone.camera_id,
                anomaly_type=AnomalyType.UNUSUAL_TIME,
                severity=severity,
                title=f"Test {severity}",
                deviation=2.0,
            )
            db_session.add(anomaly)
        await db_session.flush()

    @pytest.mark.asyncio
    async def test_deviation_non_negative_constraint(self, db_session, sample_zone) -> None:
        """Test that deviation must be non-negative or null."""
        # Non-negative should work
        anomaly = ZoneAnomaly(
            zone_id=uuid.UUID(sample_zone.id),
            camera_id=sample_zone.camera_id,
            anomaly_type=AnomalyType.UNUSUAL_TIME,
            severity=AnomalySeverity.INFO,
            title="Test",
            deviation=0.0,
        )
        db_session.add(anomaly)
        await db_session.flush()

        # Null deviation should also work
        anomaly2 = ZoneAnomaly(
            zone_id=uuid.UUID(sample_zone.id),
            camera_id=sample_zone.camera_id,
            anomaly_type=AnomalyType.UNUSUAL_TIME,
            severity=AnomalySeverity.INFO,
            title="Test2",
            deviation=None,
        )
        db_session.add(anomaly2)
        await db_session.flush()
