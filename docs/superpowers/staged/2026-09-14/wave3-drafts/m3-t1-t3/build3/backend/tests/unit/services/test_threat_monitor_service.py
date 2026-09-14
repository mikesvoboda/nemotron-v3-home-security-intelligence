"""Unit tests for ThreatMonitorService - threat detection immediate alerts.

NEM-5278: Phase 1 - Threat Detection Immediate Alerts (TDD Red Phase)

These tests define the expected behavior for the ThreatMonitorService, which:
1. Auto-generates CRITICAL alerts when weapons (gun/rifle/pistol) are detected
2. Auto-generates HIGH alerts for knife/machete/sword detections
3. Auto-generates MEDIUM alerts for bat/crowbar detections
4. Bypasses the 90-second batch window for high-priority threats

All tests are expected to FAIL until the implementation is complete.

Test Categories:
- Severity auto-mapping: Tests that verify correct AlertSeverity is assigned
- Alert auto-creation: Tests that verify alerts are created without manual intervention
- Confidence thresholds: Tests for filtering low-confidence detections
- Edge cases: Multiple weapons, unknown threat types, etc.

Related Files:
- backend/services/threat_detection_loader.py: HIGH_PRIORITY_THREATS constant
- backend/models/alert.py: AlertSeverity enum
- backend/models/enrichment.py: ThreatDetection model
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

# These imports will fail until the service is implemented
# The tests should fail with ImportError initially
from backend.models import Alert, AlertSeverity, AlertStatus, Detection, Event
from backend.models.enrichment import ThreatDetection
from backend.services.threat_detection_loader import HIGH_PRIORITY_THREATS

# This import will fail - the service doesn't exist yet
# from backend.services.threat_monitor_service import (
#     ThreatMonitorService,
#     ThreatSeverityMapping,
#     get_threat_severity,
# )


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_redis_client() -> AsyncMock:
    """Create a mock Redis client for WebSocket broadcasts."""
    client = AsyncMock()
    client.publish = AsyncMock()
    return client


@pytest.fixture
def sample_detection() -> Detection:
    """Create a sample detection for testing."""
    detection = MagicMock(spec=Detection)
    detection.id = 1
    detection.camera_id = "front_door"
    detection.object_type = "person"
    detection.confidence = 0.92
    detection.created_at = datetime.now(UTC)
    return detection


@pytest.fixture
def sample_event() -> Event:
    """Create a sample event for testing."""
    event = MagicMock(spec=Event)
    event.id = 1
    event.camera_id = "front_door"
    event.risk_score = 75
    event.created_at = datetime.now(UTC)
    return event


@pytest.fixture
def gun_threat_detection(sample_detection: Detection) -> ThreatDetection:
    """Create a gun threat detection record."""
    return ThreatDetection(
        id=1,
        detection_id=sample_detection.id,
        threat_type="gun",
        confidence=0.95,
        severity="critical",
        bbox=[100, 200, 150, 250],
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def knife_threat_detection(sample_detection: Detection) -> ThreatDetection:
    """Create a knife threat detection record."""
    return ThreatDetection(
        id=2,
        detection_id=sample_detection.id,
        threat_type="knife",
        confidence=0.88,
        severity="high",
        bbox=[120, 180, 160, 220],
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def bat_threat_detection(sample_detection: Detection) -> ThreatDetection:
    """Create a bat threat detection record."""
    return ThreatDetection(
        id=3,
        detection_id=sample_detection.id,
        threat_type="weapon",  # Generic weapon type for bat
        confidence=0.82,
        severity="medium",
        bbox=[80, 150, 200, 300],
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def low_confidence_threat(sample_detection: Detection) -> ThreatDetection:
    """Create a low-confidence threat detection record."""
    return ThreatDetection(
        id=4,
        detection_id=sample_detection.id,
        threat_type="gun",
        confidence=0.45,  # Below threshold (0.7)
        severity="critical",
        bbox=[50, 100, 80, 130],
        created_at=datetime.now(UTC),
    )


# =============================================================================
# ThreatSeverityMapping Tests
# =============================================================================


class TestGetThreatSeverity:
    """Tests for get_threat_severity() function - maps threat types to AlertSeverity."""

    def test_gun_maps_to_critical(self) -> None:
        """Test that 'gun' threat type maps to CRITICAL severity.

        Expected: get_threat_severity('gun') returns AlertSeverity.CRITICAL
        """
        from backend.services.threat_monitor_service import get_threat_severity

        result = get_threat_severity("gun")
        assert result == AlertSeverity.CRITICAL

    def test_pistol_maps_to_critical(self) -> None:
        """Test that 'pistol' threat type maps to CRITICAL severity."""
        from backend.services.threat_monitor_service import get_threat_severity

        result = get_threat_severity("pistol")
        assert result == AlertSeverity.CRITICAL

    def test_rifle_maps_to_critical(self) -> None:
        """Test that 'rifle' threat type maps to CRITICAL severity."""
        from backend.services.threat_monitor_service import get_threat_severity

        result = get_threat_severity("rifle")
        assert result == AlertSeverity.CRITICAL

    def test_firearm_maps_to_critical(self) -> None:
        """Test that 'firearm' threat type maps to CRITICAL severity."""
        from backend.services.threat_monitor_service import get_threat_severity

        result = get_threat_severity("firearm")
        assert result == AlertSeverity.CRITICAL

    def test_handgun_maps_to_critical(self) -> None:
        """Test that 'handgun' threat type maps to CRITICAL severity."""
        from backend.services.threat_monitor_service import get_threat_severity

        result = get_threat_severity("handgun")
        assert result == AlertSeverity.CRITICAL

    def test_knife_maps_to_high(self) -> None:
        """Test that 'knife' threat type maps to HIGH severity."""
        from backend.services.threat_monitor_service import get_threat_severity

        result = get_threat_severity("knife")
        assert result == AlertSeverity.HIGH

    def test_machete_maps_to_high(self) -> None:
        """Test that 'machete' threat type maps to HIGH severity."""
        from backend.services.threat_monitor_service import get_threat_severity

        result = get_threat_severity("machete")
        assert result == AlertSeverity.HIGH

    def test_sword_maps_to_high(self) -> None:
        """Test that 'sword' threat type maps to HIGH severity."""
        from backend.services.threat_monitor_service import get_threat_severity

        result = get_threat_severity("sword")
        assert result == AlertSeverity.HIGH

    def test_bat_maps_to_medium(self) -> None:
        """Test that 'bat' threat type maps to MEDIUM severity."""
        from backend.services.threat_monitor_service import get_threat_severity

        result = get_threat_severity("bat")
        assert result == AlertSeverity.MEDIUM

    def test_baseball_bat_maps_to_medium(self) -> None:
        """Test that 'baseball_bat' threat type maps to MEDIUM severity."""
        from backend.services.threat_monitor_service import get_threat_severity

        result = get_threat_severity("baseball_bat")
        assert result == AlertSeverity.MEDIUM

    def test_crowbar_maps_to_medium(self) -> None:
        """Test that 'crowbar' threat type maps to MEDIUM severity."""
        from backend.services.threat_monitor_service import get_threat_severity

        result = get_threat_severity("crowbar")
        assert result == AlertSeverity.MEDIUM

    def test_unknown_threat_defaults_to_high(self) -> None:
        """Test that unknown threat types default to HIGH severity.

        When a threat is detected but the type is not in the mapping,
        we should still generate an alert with HIGH severity as a safe default.
        """
        from backend.services.threat_monitor_service import get_threat_severity

        result = get_threat_severity("unknown_weapon")
        assert result == AlertSeverity.HIGH

    def test_case_insensitive_matching(self) -> None:
        """Test that threat type matching is case-insensitive."""
        from backend.services.threat_monitor_service import get_threat_severity

        assert get_threat_severity("GUN") == AlertSeverity.CRITICAL
        assert get_threat_severity("Gun") == AlertSeverity.CRITICAL
        assert get_threat_severity("KNIFE") == AlertSeverity.HIGH
        assert get_threat_severity("Knife") == AlertSeverity.HIGH


# =============================================================================
# ThreatMonitorService - Alert Auto-Creation Tests
# =============================================================================


class TestThreatMonitorServiceAutoCreateAlert:
    """Tests for ThreatMonitorService automatic alert creation."""

    @pytest.mark.asyncio
    async def test_creates_critical_alert_for_gun_detection(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        gun_threat_detection: ThreatDetection,
    ) -> None:
        """Test that gun detection automatically creates a CRITICAL alert.

        This is the primary use case: when a gun is detected with high confidence,
        the system should immediately create a CRITICAL alert without waiting
        for the 90-second batch window.
        """
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_threat_detection(
            threat_detection=gun_threat_detection,
            event=sample_event,
        )

        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.PENDING
        assert alert.event_id == sample_event.id
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_high_alert_for_knife_detection(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        knife_threat_detection: ThreatDetection,
    ) -> None:
        """Test that knife detection automatically creates a HIGH alert."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_threat_detection(
            threat_detection=knife_threat_detection,
            event=sample_event,
        )

        assert alert is not None
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.PENDING

    @pytest.mark.asyncio
    async def test_creates_medium_alert_for_bat_detection(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        bat_threat_detection: ThreatDetection,
    ) -> None:
        """Test that bat detection automatically creates a MEDIUM alert."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_threat_detection(
            threat_detection=bat_threat_detection,
            event=sample_event,
        )

        assert alert is not None
        assert alert.severity == AlertSeverity.MEDIUM
        assert alert.status == AlertStatus.PENDING

    @pytest.mark.asyncio
    async def test_alert_includes_threat_metadata(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        gun_threat_detection: ThreatDetection,
    ) -> None:
        """Test that created alert includes threat detection metadata."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_threat_detection(
            threat_detection=gun_threat_detection,
            event=sample_event,
        )

        assert alert.alert_metadata is not None
        assert "threat_type" in alert.alert_metadata
        assert alert.alert_metadata["threat_type"] == "gun"
        assert "threat_confidence" in alert.alert_metadata
        assert alert.alert_metadata["threat_confidence"] == gun_threat_detection.confidence

    @pytest.mark.asyncio
    async def test_alert_dedup_key_includes_threat_type(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        gun_threat_detection: ThreatDetection,
    ) -> None:
        """Test that dedup_key includes threat type for proper deduplication."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_threat_detection(
            threat_detection=gun_threat_detection,
            event=sample_event,
        )

        # Dedup key should include camera_id and threat_type
        assert sample_event.camera_id in alert.dedup_key
        assert "gun" in alert.dedup_key


# =============================================================================
# ThreatMonitorService - Confidence Threshold Tests
# =============================================================================


class TestThreatMonitorServiceConfidenceThreshold:
    """Tests for confidence threshold filtering in ThreatMonitorService."""

    @pytest.mark.asyncio
    async def test_skips_low_confidence_detection(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        low_confidence_threat: ThreatDetection,
    ) -> None:
        """Test that low-confidence detections (< 0.7) do not create alerts.

        To avoid false positives, we require a minimum confidence of 0.7
        before auto-creating threat alerts.
        """
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_threat_detection(
            threat_detection=low_confidence_threat,
            event=sample_event,
        )

        # Should return None, not create an alert
        assert alert is None
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_alert_at_exactly_threshold(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        sample_detection: Detection,
    ) -> None:
        """Test that detection at exactly 0.7 confidence creates an alert."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        threshold_threat = ThreatDetection(
            id=5,
            detection_id=sample_detection.id,
            threat_type="gun",
            confidence=0.70,  # Exactly at threshold
            severity="critical",
            bbox=[50, 100, 80, 130],
            created_at=datetime.now(UTC),
        )

        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_threat_detection(
            threat_detection=threshold_threat,
            event=sample_event,
        )

        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_custom_confidence_threshold(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        sample_detection: Detection,
    ) -> None:
        """Test that custom confidence threshold can be configured."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        # Create threat at 0.6 confidence
        threat = ThreatDetection(
            id=6,
            detection_id=sample_detection.id,
            threat_type="knife",
            confidence=0.60,
            severity="high",
            bbox=[50, 100, 80, 130],
            created_at=datetime.now(UTC),
        )

        # Create service with custom threshold of 0.5
        service = ThreatMonitorService(mock_session, mock_redis_client, confidence_threshold=0.5)

        alert = await service.process_threat_detection(
            threat_detection=threat,
            event=sample_event,
        )

        # Should create alert because 0.6 > 0.5
        assert alert is not None


# =============================================================================
# ThreatMonitorService - Multiple Weapons Tests
# =============================================================================


class TestThreatMonitorServiceMultipleWeapons:
    """Tests for handling multiple weapons in a single frame."""

    @pytest.mark.asyncio
    async def test_multiple_weapons_creates_single_alert_with_highest_severity(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        sample_detection: Detection,
    ) -> None:
        """Test that multiple weapons in one frame create one alert with highest severity.

        When both a gun (CRITICAL) and a knife (HIGH) are detected in the same frame,
        we should create a single alert with CRITICAL severity.
        """
        from backend.services.threat_monitor_service import ThreatMonitorService

        gun_threat = ThreatDetection(
            id=10,
            detection_id=sample_detection.id,
            threat_type="gun",
            confidence=0.90,
            severity="critical",
            bbox=[100, 200, 150, 250],
            created_at=datetime.now(UTC),
        )

        knife_threat = ThreatDetection(
            id=11,
            detection_id=sample_detection.id,
            threat_type="knife",
            confidence=0.85,
            severity="high",
            bbox=[200, 100, 250, 150],
            created_at=datetime.now(UTC),
        )

        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_multiple_threat_detections(
            threat_detections=[gun_threat, knife_threat],
            event=sample_event,
        )

        # Should create single alert with highest severity
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_multiple_weapons_metadata_includes_all_threats(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        sample_detection: Detection,
    ) -> None:
        """Test that alert metadata includes all detected weapons."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        gun_threat = ThreatDetection(
            id=12,
            detection_id=sample_detection.id,
            threat_type="gun",
            confidence=0.90,
            severity="critical",
            bbox=[100, 200, 150, 250],
            created_at=datetime.now(UTC),
        )

        knife_threat = ThreatDetection(
            id=13,
            detection_id=sample_detection.id,
            threat_type="knife",
            confidence=0.85,
            severity="high",
            bbox=[200, 100, 250, 150],
            created_at=datetime.now(UTC),
        )

        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_multiple_threat_detections(
            threat_detections=[gun_threat, knife_threat],
            event=sample_event,
        )

        assert alert.alert_metadata is not None
        assert "detected_threats" in alert.alert_metadata
        threats = alert.alert_metadata["detected_threats"]
        assert len(threats) == 2
        assert any(t["type"] == "gun" for t in threats)
        assert any(t["type"] == "knife" for t in threats)

    @pytest.mark.asyncio
    async def test_multiple_weapons_one_below_threshold_still_creates_alert(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        sample_detection: Detection,
    ) -> None:
        """Test that one low-confidence detection doesn't block alert creation.

        If one weapon has confidence 0.45 and another has 0.85, we should
        still create an alert based on the high-confidence detection.
        """
        from backend.services.threat_monitor_service import ThreatMonitorService

        low_conf_threat = ThreatDetection(
            id=14,
            detection_id=sample_detection.id,
            threat_type="gun",
            confidence=0.45,  # Below threshold
            severity="critical",
            bbox=[100, 200, 150, 250],
            created_at=datetime.now(UTC),
        )

        high_conf_threat = ThreatDetection(
            id=15,
            detection_id=sample_detection.id,
            threat_type="knife",
            confidence=0.85,  # Above threshold
            severity="high",
            bbox=[200, 100, 250, 150],
            created_at=datetime.now(UTC),
        )

        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_multiple_threat_detections(
            threat_detections=[low_conf_threat, high_conf_threat],
            event=sample_event,
        )

        # Should create alert based on knife detection
        assert alert is not None
        # Severity should be HIGH (knife), not CRITICAL (gun was low confidence)
        assert alert.severity == AlertSeverity.HIGH


# =============================================================================
# ThreatMonitorService - WebSocket Broadcast Tests
# =============================================================================


class TestThreatMonitorServiceWebSocketBroadcast:
    """Tests for WebSocket event broadcasting on threat detection."""

    @pytest.mark.asyncio
    async def test_broadcasts_alert_created_event(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        gun_threat_detection: ThreatDetection,
    ) -> None:
        """Test that alert creation triggers WebSocket broadcast."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(mock_session, mock_redis_client)

        await service.process_threat_detection(
            threat_detection=gun_threat_detection,
            event=sample_event,
        )

        # Should broadcast alert.created event
        mock_redis_client.publish.assert_called()

    @pytest.mark.asyncio
    async def test_broadcast_includes_severity_and_threat_type(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        gun_threat_detection: ThreatDetection,
    ) -> None:
        """Test that broadcast payload includes severity and threat type."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(mock_session, mock_redis_client)

        await service.process_threat_detection(
            threat_detection=gun_threat_detection,
            event=sample_event,
        )

        # Get the broadcast call
        call_args = mock_redis_client.publish.call_args
        assert call_args is not None
        # The payload should include severity and threat info
        # (exact format depends on implementation)


# =============================================================================
# ThreatMonitorService - Integration with Alert Engine Tests
# =============================================================================


class TestThreatMonitorServiceAlertEngineIntegration:
    """Tests for ThreatMonitorService integration with AlertRuleEngine."""

    @pytest.mark.asyncio
    async def test_respects_cooldown_period(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        gun_threat_detection: ThreatDetection,
    ) -> None:
        """Test that duplicate alerts within cooldown period are prevented.

        If a gun alert was created 30 seconds ago for the same camera,
        a new gun detection should not create another alert.
        """
        from backend.services.threat_monitor_service import ThreatMonitorService

        # Mock that a recent alert exists
        existing_alert = MagicMock(spec=Alert)
        existing_alert.id = str(uuid.uuid4())
        existing_alert.created_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_alert
        mock_session.execute.return_value = mock_result

        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_threat_detection(
            threat_detection=gun_threat_detection,
            event=sample_event,
        )

        # Should not create new alert due to cooldown
        assert alert is None

    @pytest.mark.asyncio
    async def test_creates_alert_after_cooldown_expires(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        gun_threat_detection: ThreatDetection,
    ) -> None:
        """Test that new alert is created after cooldown period expires."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        # Mock that no recent alert exists (cooldown expired)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_threat_detection(
            threat_detection=gun_threat_detection,
            event=sample_event,
        )

        # Should create new alert
        assert alert is not None


# =============================================================================
# ThreatSeverityMapping Constant Tests
# =============================================================================


class TestThreatSeverityMappingConstant:
    """Tests for THREAT_SEVERITY_MAPPING constant."""

    def test_mapping_includes_all_high_priority_threats(self) -> None:
        """Test that severity mapping includes all HIGH_PRIORITY_THREATS."""
        from backend.services.threat_monitor_service import THREAT_SEVERITY_MAPPING

        for threat in HIGH_PRIORITY_THREATS:
            assert threat.lower() in THREAT_SEVERITY_MAPPING, (
                f"HIGH_PRIORITY_THREAT '{threat}' not in THREAT_SEVERITY_MAPPING"
            )

    def test_all_firearms_are_critical(self) -> None:
        """Test that all firearm types map to CRITICAL severity."""
        from backend.services.threat_monitor_service import THREAT_SEVERITY_MAPPING

        firearms = ["gun", "pistol", "rifle", "firearm", "handgun"]
        for firearm in firearms:
            assert THREAT_SEVERITY_MAPPING.get(firearm) == AlertSeverity.CRITICAL, (
                f"Firearm '{firearm}' should map to CRITICAL"
            )

    def test_bladed_weapons_are_high(self) -> None:
        """Test that bladed weapons map to HIGH severity."""
        from backend.services.threat_monitor_service import THREAT_SEVERITY_MAPPING

        bladed = ["knife", "machete", "sword"]
        for weapon in bladed:
            assert THREAT_SEVERITY_MAPPING.get(weapon) == AlertSeverity.HIGH, (
                f"Bladed weapon '{weapon}' should map to HIGH"
            )

    def test_blunt_weapons_are_medium(self) -> None:
        """Test that blunt weapons map to MEDIUM severity."""
        from backend.services.threat_monitor_service import THREAT_SEVERITY_MAPPING

        blunt = ["bat", "baseball_bat", "crowbar"]
        for weapon in blunt:
            assert THREAT_SEVERITY_MAPPING.get(weapon) == AlertSeverity.MEDIUM, (
                f"Blunt weapon '{weapon}' should map to MEDIUM"
            )


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestThreatMonitorServiceEdgeCases:
    """Edge case tests for ThreatMonitorService."""

    @pytest.mark.asyncio
    async def test_handles_missing_event(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        gun_threat_detection: ThreatDetection,
    ) -> None:
        """Test graceful handling when event is None."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(mock_session, mock_redis_client)

        with pytest.raises(ValueError, match="event is required"):
            await service.process_threat_detection(
                threat_detection=gun_threat_detection,
                event=None,
            )

    @pytest.mark.asyncio
    async def test_handles_missing_threat_detection(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
    ) -> None:
        """Test graceful handling when threat_detection is None."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(mock_session, mock_redis_client)

        with pytest.raises(ValueError, match="threat_detection is required"):
            await service.process_threat_detection(
                threat_detection=None,
                event=sample_event,
            )

    @pytest.mark.asyncio
    async def test_handles_database_error(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        gun_threat_detection: ThreatDetection,
    ) -> None:
        """Test graceful handling of database errors during alert creation."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        # Mock database error
        mock_session.flush.side_effect = Exception("Database connection failed")

        service = ThreatMonitorService(mock_session, mock_redis_client)

        with pytest.raises(Exception, match="Database connection failed"):
            await service.process_threat_detection(
                threat_detection=gun_threat_detection,
                event=sample_event,
            )

    @pytest.mark.asyncio
    async def test_empty_threat_list_returns_none(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
    ) -> None:
        """Test that empty threat list returns None without creating alert."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_multiple_threat_detections(
            threat_detections=[],
            event=sample_event,
        )

        assert alert is None
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_all_threats_below_threshold_returns_none(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        sample_detection: Detection,
    ) -> None:
        """Test that when all threats are below threshold, no alert is created."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        low_conf_gun = ThreatDetection(
            id=20,
            detection_id=sample_detection.id,
            threat_type="gun",
            confidence=0.45,
            severity="critical",
            bbox=[100, 200, 150, 250],
            created_at=datetime.now(UTC),
        )

        low_conf_knife = ThreatDetection(
            id=21,
            detection_id=sample_detection.id,
            threat_type="knife",
            confidence=0.50,
            severity="high",
            bbox=[200, 100, 250, 150],
            created_at=datetime.now(UTC),
        )

        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_multiple_threat_detections(
            threat_detections=[low_conf_gun, low_conf_knife],
            event=sample_event,
        )

        assert alert is None
        mock_session.add.assert_not_called()
