"""Integration tests for ThreatMonitorService - end-to-end threat detection to alert flow.

NEM-5278: Phase 1 - Threat Detection Immediate Alerts (TDD Red Phase)

These tests verify the complete flow from threat detection to alert creation:
1. ThreatDetection record is created in database
2. ThreatMonitorService processes the detection
3. Alert is created with correct severity
4. WebSocket notification is broadcast

All tests are expected to FAIL until the implementation is complete.

Test Categories:
- Database integration: Tests that verify Alert records are persisted
- Service integration: Tests that verify ThreatMonitorService works with real services
- End-to-end: Complete flow from detection to alert with severity mapping
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Alert, AlertSeverity, AlertStatus, Camera, Detection, Event
from backend.models.enrichment import ThreatDetection

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def test_camera(db_session: AsyncSession) -> Camera:
    """Create a test camera for the integration tests."""
    camera = Camera(
        camera_id="integration_test_cam_01",
        display_name="Integration Test Camera",
        rtsp_url="rtsp://localhost:8554/test_stream",
        enabled=True,
        created_at=datetime.now(UTC),
    )
    db_session.add(camera)
    await db_session.commit()
    await db_session.refresh(camera)
    return camera


@pytest.fixture
async def test_detection(db_session: AsyncSession, test_camera: Camera) -> Detection:
    """Create a test detection associated with the test camera."""
    detection = Detection(
        camera_id=test_camera.camera_id,
        object_type="person",
        confidence=0.92,
        bbox_x1=100,
        bbox_y1=200,
        bbox_x2=200,
        bbox_y2=400,
        file_path="/export/foscam/integration_test_cam_01/frame_001.jpg",
        created_at=datetime.now(UTC),
    )
    db_session.add(detection)
    await db_session.commit()
    await db_session.refresh(detection)
    return detection


@pytest.fixture
async def test_event(db_session: AsyncSession, test_camera: Camera) -> Event:
    """Create a test event associated with the test camera."""
    event = Event(
        camera_id=test_camera.camera_id,
        risk_score=75,
        started_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)
    return event


@pytest.fixture
async def gun_threat_in_db(db_session: AsyncSession, test_detection: Detection) -> ThreatDetection:
    """Create a gun threat detection record in the database."""
    threat = ThreatDetection(
        detection_id=test_detection.id,
        threat_type="gun",
        confidence=0.95,
        severity="critical",
        bbox=[100, 200, 150, 250],
        created_at=datetime.now(UTC),
    )
    db_session.add(threat)
    await db_session.commit()
    await db_session.refresh(threat)
    return threat


@pytest.fixture
async def knife_threat_in_db(
    db_session: AsyncSession, test_detection: Detection
) -> ThreatDetection:
    """Create a knife threat detection record in the database."""
    threat = ThreatDetection(
        detection_id=test_detection.id,
        threat_type="knife",
        confidence=0.88,
        severity="high",
        bbox=[120, 180, 160, 220],
        created_at=datetime.now(UTC),
    )
    db_session.add(threat)
    await db_session.commit()
    await db_session.refresh(threat)
    return threat


@pytest.fixture
async def bat_threat_in_db(db_session: AsyncSession, test_detection: Detection) -> ThreatDetection:
    """Create a bat threat detection record in the database."""
    threat = ThreatDetection(
        detection_id=test_detection.id,
        threat_type="weapon",  # Generic for bat/crowbar
        confidence=0.82,
        severity="medium",
        bbox=[80, 150, 200, 300],
        created_at=datetime.now(UTC),
    )
    db_session.add(threat)
    await db_session.commit()
    await db_session.refresh(threat)
    return threat


# =============================================================================
# End-to-End Integration Tests
# =============================================================================


class TestThreatDetectionToAlertFlow:
    """Integration tests for the complete threat detection to alert flow."""

    @pytest.mark.asyncio
    async def test_gun_detection_creates_critical_alert_in_database(
        self,
        db_session: AsyncSession,
        test_event: Event,
        gun_threat_in_db: ThreatDetection,
    ) -> None:
        """Test end-to-end: Gun detection -> CRITICAL alert persisted to database.

        This is the primary integration test verifying that:
        1. ThreatMonitorService reads the ThreatDetection from DB
        2. It creates an Alert with CRITICAL severity
        3. The Alert is persisted to the database
        """
        from backend.services.threat_monitor_service import ThreatMonitorService

        # Create service with real database session
        service = ThreatMonitorService(db_session, redis_client=None)

        # Process the threat detection
        alert = await service.process_threat_detection(
            threat_detection=gun_threat_in_db,
            event=test_event,
        )

        # Verify alert was created
        assert alert is not None
        assert alert.id is not None  # Was persisted to DB

        # Verify alert has correct properties
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.PENDING
        assert alert.event_id == test_event.id

        # Verify we can query the alert from database
        stmt = select(Alert).where(Alert.id == alert.id)
        result = await db_session.execute(stmt)
        persisted_alert = result.scalar_one()

        assert persisted_alert.severity == AlertSeverity.CRITICAL
        assert persisted_alert.event_id == test_event.id

    @pytest.mark.asyncio
    async def test_knife_detection_creates_high_alert_in_database(
        self,
        db_session: AsyncSession,
        test_event: Event,
        knife_threat_in_db: ThreatDetection,
    ) -> None:
        """Test end-to-end: Knife detection -> HIGH alert persisted to database."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(db_session, redis_client=None)

        alert = await service.process_threat_detection(
            threat_detection=knife_threat_in_db,
            event=test_event,
        )

        assert alert is not None
        assert alert.severity == AlertSeverity.HIGH

        # Verify persistence
        stmt = select(Alert).where(Alert.id == alert.id)
        result = await db_session.execute(stmt)
        persisted_alert = result.scalar_one()

        assert persisted_alert.severity == AlertSeverity.HIGH

    @pytest.mark.asyncio
    async def test_bat_detection_creates_medium_alert_in_database(
        self,
        db_session: AsyncSession,
        test_event: Event,
        bat_threat_in_db: ThreatDetection,
    ) -> None:
        """Test end-to-end: Bat detection -> MEDIUM alert persisted to database."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(db_session, redis_client=None)

        alert = await service.process_threat_detection(
            threat_detection=bat_threat_in_db,
            event=test_event,
        )

        assert alert is not None
        assert alert.severity == AlertSeverity.MEDIUM

    @pytest.mark.asyncio
    async def test_alert_metadata_contains_threat_details(
        self,
        db_session: AsyncSession,
        test_event: Event,
        gun_threat_in_db: ThreatDetection,
    ) -> None:
        """Test that alert metadata includes threat detection details."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(db_session, redis_client=None)

        alert = await service.process_threat_detection(
            threat_detection=gun_threat_in_db,
            event=test_event,
        )

        # Verify metadata
        assert alert.alert_metadata is not None
        assert alert.alert_metadata.get("threat_type") == "gun"
        assert alert.alert_metadata.get("threat_confidence") == 0.95
        assert "threat_detection_id" in alert.alert_metadata

    @pytest.mark.asyncio
    async def test_dedup_key_prevents_duplicate_alerts(
        self,
        db_session: AsyncSession,
        test_event: Event,
        gun_threat_in_db: ThreatDetection,
    ) -> None:
        """Test that duplicate threat detections don't create multiple alerts.

        When a second gun is detected within the cooldown window for the same
        camera, we should not create another alert.
        """
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(db_session, redis_client=None)

        # First detection creates an alert
        alert1 = await service.process_threat_detection(
            threat_detection=gun_threat_in_db,
            event=test_event,
        )
        assert alert1 is not None

        # Create another gun threat detection (simulating second detection)
        second_threat = ThreatDetection(
            detection_id=gun_threat_in_db.detection_id,
            threat_type="gun",
            confidence=0.92,
            severity="critical",
            bbox=[110, 210, 160, 260],
            created_at=datetime.now(UTC),
        )
        db_session.add(second_threat)
        await db_session.commit()
        await db_session.refresh(second_threat)

        # Second detection should NOT create a new alert (within cooldown)
        alert2 = await service.process_threat_detection(
            threat_detection=second_threat,
            event=test_event,
        )

        # Should return None due to dedup cooldown
        assert alert2 is None

        # Verify only one alert exists
        stmt = select(Alert).where(Alert.event_id == test_event.id)
        result = await db_session.execute(stmt)
        alerts = result.scalars().all()

        assert len(alerts) == 1


class TestThreatMonitorServiceWithDatabase:
    """Integration tests for ThreatMonitorService database operations."""

    @pytest.mark.asyncio
    async def test_service_queries_existing_alerts_for_cooldown(
        self,
        db_session: AsyncSession,
        test_event: Event,
        test_detection: Detection,
    ) -> None:
        """Test that service correctly queries existing alerts for cooldown check."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        # Create an existing alert for the camera
        existing_alert = Alert(
            event_id=test_event.id,
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.PENDING,
            dedup_key=f"{test_event.camera_id}:gun:threat",
            channels=[],
            created_at=datetime.now(UTC),
        )
        db_session.add(existing_alert)
        await db_session.commit()

        # Create a new threat detection
        threat = ThreatDetection(
            detection_id=test_detection.id,
            threat_type="gun",
            confidence=0.90,
            severity="critical",
            bbox=[100, 200, 150, 250],
            created_at=datetime.now(UTC),
        )
        db_session.add(threat)
        await db_session.commit()
        await db_session.refresh(threat)

        service = ThreatMonitorService(db_session, redis_client=None)

        # Should not create new alert due to cooldown
        alert = await service.process_threat_detection(
            threat_detection=threat,
            event=test_event,
        )

        # Should return None because of existing alert within cooldown
        assert alert is None

    @pytest.mark.asyncio
    async def test_multiple_threats_creates_single_highest_severity_alert(
        self,
        db_session: AsyncSession,
        test_event: Event,
        test_detection: Detection,
    ) -> None:
        """Test that multiple weapons in one frame create one alert with highest severity."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        # Create gun threat (CRITICAL)
        gun_threat = ThreatDetection(
            detection_id=test_detection.id,
            threat_type="gun",
            confidence=0.90,
            severity="critical",
            bbox=[100, 200, 150, 250],
            created_at=datetime.now(UTC),
        )
        db_session.add(gun_threat)

        # Create knife threat (HIGH)
        knife_threat = ThreatDetection(
            detection_id=test_detection.id,
            threat_type="knife",
            confidence=0.85,
            severity="high",
            bbox=[200, 100, 250, 150],
            created_at=datetime.now(UTC),
        )
        db_session.add(knife_threat)

        await db_session.commit()
        await db_session.refresh(gun_threat)
        await db_session.refresh(knife_threat)

        service = ThreatMonitorService(db_session, redis_client=None)

        alert = await service.process_multiple_threat_detections(
            threat_detections=[gun_threat, knife_threat],
            event=test_event,
        )

        # Should create single alert with CRITICAL severity (highest)
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL

        # Verify only one alert was created
        stmt = select(Alert).where(Alert.event_id == test_event.id)
        result = await db_session.execute(stmt)
        alerts = result.scalars().all()

        assert len(alerts) == 1


class TestBatchAggregatorThreatBypassIntegration:
    """Integration tests for BatchAggregator threat bypass with ThreatMonitorService."""

    @pytest.mark.asyncio
    async def test_batch_aggregator_bypasses_for_gun_detection(
        self,
        db_session: AsyncSession,
        test_camera: Camera,
        test_detection: Detection,
        test_event: Event,
    ) -> None:
        """Test that BatchAggregator triggers threat fast path for gun detection.

        This test verifies the integration between BatchAggregator and
        ThreatMonitorService when a high-priority threat is detected.
        """
        from backend.core.redis import RedisClient
        from backend.services.batch_aggregator import BatchAggregator

        # Create mock Redis client
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis._client = MagicMock()
        mock_redis._client.rpush = AsyncMock(return_value=1)

        aggregator = BatchAggregator(redis_client=mock_redis)

        # Add detection with gun threat
        with patch.object(aggregator, "_process_threat_fast_path") as mock_fast_path:
            mock_fast_path.return_value = None

            batch_id = await aggregator.add_detection(
                camera_id=test_camera.camera_id,
                detection_id=test_detection.id,
                _file_path=test_detection.file_path,
                confidence=0.90,
                object_type="person",
                threat_type="gun",
            )

            # Should have triggered threat fast path
            mock_fast_path.assert_called_once()

            # Should return threat fast path batch ID
            assert "fast_path" in batch_id.lower() or "threat" in batch_id.lower()

    @pytest.mark.asyncio
    async def test_batch_aggregator_normal_batch_for_non_threat(
        self,
        db_session: AsyncSession,
        test_camera: Camera,
        test_detection: Detection,
    ) -> None:
        """Test that BatchAggregator uses normal batching for non-threat detections."""
        from backend.core.redis import RedisClient
        from backend.services.batch_aggregator import BatchAggregator

        # Create mock Redis client
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis._client = MagicMock()
        mock_redis._client.rpush = AsyncMock(return_value=1)
        mock_redis._client.expire = AsyncMock(return_value=True)

        # Mock pipeline for batch creation
        class MockPipeline:
            def set(self, key, value, ex=None):
                return self

            async def execute(self):
                return [True]

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False

        mock_redis._client.pipeline = MagicMock(return_value=MockPipeline())

        aggregator = BatchAggregator(redis_client=mock_redis)

        with patch("backend.services.batch_aggregator.generate_batch_id") as mock_gen:
            mock_gen.return_value = "batch-normal123"

            batch_id = await aggregator.add_detection(
                camera_id=test_camera.camera_id,
                detection_id=test_detection.id,
                _file_path=test_detection.file_path,
                confidence=0.90,
                object_type="person",
                threat_type=None,  # No threat
            )

        # Should use normal batch
        assert batch_id == "batch-normal123"

        # Should have used RPUSH for batch
        mock_redis._client.rpush.assert_called()


class TestAlertRuleEngineIntegrationWithThreatMonitor:
    """Integration tests for AlertRuleEngine with ThreatMonitorService.

    These tests verify that threat alerts created by ThreatMonitorService
    work correctly with the existing AlertRuleEngine infrastructure.
    """

    @pytest.mark.asyncio
    async def test_threat_alert_triggers_webhook(
        self,
        db_session: AsyncSession,
        test_event: Event,
        gun_threat_in_db: ThreatDetection,
    ) -> None:
        """Test that threat alert triggers outbound webhook notification."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        with patch("backend.services.threat_monitor_service.get_webhook_service") as mock_webhook:
            mock_service = AsyncMock()
            mock_service.trigger_webhooks_for_event = AsyncMock()
            mock_webhook.return_value = mock_service

            service = ThreatMonitorService(db_session, redis_client=None)

            await service.process_threat_detection(
                threat_detection=gun_threat_in_db,
                event=test_event,
            )

            # Should have triggered webhook for ALERT_FIRED event
            mock_service.trigger_webhooks_for_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_threat_alert_respects_existing_rule_cooldown(
        self,
        db_session: AsyncSession,
        test_event: Event,
        test_detection: Detection,
    ) -> None:
        """Test that threat alerts respect existing AlertRule cooldown periods.

        If an AlertRule exists for threat detection with a specific cooldown,
        the ThreatMonitorService should respect that cooldown.
        """
        from backend.models.alert import AlertRule
        from backend.services.threat_monitor_service import ThreatMonitorService

        # Create an alert rule for threat detection
        rule = AlertRule(
            name="Weapon Detection Alert",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            threat_detection_enabled=True,
            threat_types=["gun", "knife"],
            cooldown_seconds=600,  # 10 minute cooldown
            dedup_key_template="{camera_id}:threat:{rule_id}",
        )
        db_session.add(rule)
        await db_session.commit()
        await db_session.refresh(rule)

        # Create first threat
        threat1 = ThreatDetection(
            detection_id=test_detection.id,
            threat_type="gun",
            confidence=0.90,
            severity="critical",
            bbox=[100, 200, 150, 250],
            created_at=datetime.now(UTC),
        )
        db_session.add(threat1)
        await db_session.commit()
        await db_session.refresh(threat1)

        service = ThreatMonitorService(db_session, redis_client=None)

        # First alert should be created
        alert1 = await service.process_threat_detection(
            threat_detection=threat1,
            event=test_event,
            rule=rule,
        )
        assert alert1 is not None

        # Second threat within cooldown
        threat2 = ThreatDetection(
            detection_id=test_detection.id,
            threat_type="knife",
            confidence=0.85,
            severity="high",
            bbox=[200, 100, 250, 150],
            created_at=datetime.now(UTC),
        )
        db_session.add(threat2)
        await db_session.commit()
        await db_session.refresh(threat2)

        # Second alert should NOT be created due to cooldown
        alert2 = await service.process_threat_detection(
            threat_detection=threat2,
            event=test_event,
            rule=rule,
        )
        assert alert2 is None
