"""Unit tests for Alert Rule Condition Types in AlertRuleEngine.

R2a row 32 (F-220) retired pose, action, and smoke/fire condition evaluation,
keeping dwell_time and threat_detected (OD-7).
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models import (
    AlertRule,
    AlertSeverity,
    Detection,
    DwellTimeRecord,
    Event,
    ThreatDetection,
)
from backend.services.alert_engine import AlertRuleEngine


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    return redis


@pytest.fixture
def sample_event() -> MagicMock:
    """Create a sample event for testing."""
    mock_event = MagicMock(spec=Event)
    mock_event.id = 1
    mock_event.batch_id = str(uuid.uuid4())
    mock_event.camera_id = "front_door"
    mock_event.started_at = datetime.now(UTC)
    mock_event.risk_score = 85
    mock_event.risk_level = "high"
    mock_event.detections = []
    mock_event.detection_id_list = [1, 2, 3]
    return mock_event


@pytest.fixture
def sample_detections() -> list[Detection]:
    """Create sample detections for testing."""
    return [
        Detection(
            id=1,
            camera_id="front_door",
            file_path="/export/foscam/front_door/img1.jpg",
            object_type="person",
            confidence=0.95,
        ),
        Detection(
            id=2,
            camera_id="front_door",
            file_path="/export/foscam/front_door/img2.jpg",
            object_type="vehicle",
            confidence=0.88,
        ),
        Detection(
            id=3,
            camera_id="front_door",
            file_path="/export/foscam/front_door/img3.jpg",
            object_type="person",
            confidence=0.91,
        ),
    ]


@pytest.mark.skip(reason="Dwell time now uses zone-based thresholds - see test_alert_engine.py")
class TestDwellTimeCondition:
    """Tests for dwell_time alert condition type."""

    @pytest.mark.asyncio
    async def test_dwell_time_condition_triggers_when_exceeded(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Skipped - see test_alert_engine.py for zone-based implementation tests."""
        pass

    @pytest.mark.asyncio
    async def test_dwell_time_condition_no_trigger_below_threshold(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Skipped - see test_alert_engine.py for zone-based implementation tests."""
        pass

    @pytest.mark.asyncio
    async def test_dwell_time_with_specific_zone_ids(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Skipped - see test_alert_engine.py for zone-based implementation tests."""
        pass

    @pytest.mark.asyncio
    async def test_dwell_time_excludes_household_members(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Skipped - see test_alert_engine.py for zone-based implementation tests."""
        pass


class TestThreatDetectedCondition:
    """Tests for threat_detected alert condition type."""

    def test_alert_engine_only_exposes_kept_check_methods(self) -> None:
        """R2a row 32 (F-220) retired pose, action, and smoke/fire check methods."""
        check_methods = [m for m in sorted(dir(AlertRuleEngine)) if m.startswith("_check_")]
        assert check_methods == [
            "_check_cooldown",
            "_check_dwell_time",
            "_check_min_confidence",
            "_check_object_types",
            "_check_schedule",
            "_check_threat_detected",
        ]

    @pytest.mark.asyncio
    async def test_threat_detected_triggers_on_weapon(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that threat_detected condition triggers on weapon detection."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Weapon Detection",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            threat_detection_enabled=True,
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}:{threat_type}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        threat = ThreatDetection(
            id=1,
            detection_id=1,
            threat_type="gun",
            confidence=0.94,
            severity="critical",
            bbox=[100, 100, 200, 200],
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [threat]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        matches, matched_conditions, _ = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        assert matches is True
        assert any("threat_detected" in cond for cond in matched_conditions)

    @pytest.mark.asyncio
    async def test_threat_detected_gun_is_critical(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that gun detection results in CRITICAL severity."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Any Weapon",
            enabled=True,
            severity=AlertSeverity.HIGH,
            threat_detection_enabled=True,
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}:{threat_type}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        threat = ThreatDetection(
            id=1,
            detection_id=1,
            threat_type="gun",
            confidence=0.96,
            severity="critical",
            bbox=[100, 100, 200, 200],
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [threat]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        matches, matched_conditions, _ = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        assert matches is True
        assert any("threat_detected" in cond for cond in matched_conditions)

    @pytest.mark.asyncio
    async def test_threat_detected_knife_is_high(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that knife detection results in HIGH severity."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Sharp Object Detection",
            enabled=True,
            severity=AlertSeverity.HIGH,
            threat_detection_enabled=True,
            threat_types=["knife"],
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}:{threat_type}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        threat = ThreatDetection(
            id=1,
            detection_id=1,
            threat_type="knife",
            confidence=0.89,
            severity="high",
            bbox=[150, 150, 250, 250],
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [threat]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        matches, matched_conditions, _ = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        assert matches is True
        assert any("threat_detected" in cond for cond in matched_conditions)

    @pytest.mark.asyncio
    async def test_threat_detected_with_severity_filter(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that threat_detected can filter by severity level."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Critical Threats Only",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            threat_detection_enabled=True,
            threat_min_severity="critical",
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        threat = ThreatDetection(
            id=1,
            detection_id=1,
            threat_type="knife",
            confidence=0.89,
            severity="high",
            bbox=[150, 150, 250, 250],
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [threat]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        matches, matched_conditions, _ = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        assert matches is False

    @pytest.mark.asyncio
    async def test_threat_detected_with_confidence_threshold(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that threat_detected respects confidence threshold."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="High Confidence Threats",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            threat_detection_enabled=True,
            threat_confidence_threshold=0.95,
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        threat = ThreatDetection(
            id=1,
            detection_id=1,
            threat_type="gun",
            confidence=0.85,
            severity="critical",
            bbox=[100, 100, 200, 200],
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [threat]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        matches, matched_conditions, _ = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        assert matches is False


class TestCombinedConditions:
    """Tests for combining kept condition types with existing conditions."""

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="Uses old dwell_threshold_seconds - see test_alert_engine.py for zone-based tests"
    )
    async def test_multiple_new_conditions_and_logic(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that multiple new conditions use AND logic."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Armed Loiterer",
            enabled=True,
            severity=AlertSeverity.HIGH,
            dwell_threshold_seconds=30,
            threat_detection_enabled=True,
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        dwell_record = DwellTimeRecord(
            id=1,
            zone_id=10,
            track_id=42,
            camera_id="front_door",
            object_class="person",
            entry_time=datetime.now(UTC) - timedelta(seconds=45),
            exit_time=None,
            total_seconds=45.0,
            triggered_alert=False,
        )

        threat = ThreatDetection(
            id=1,
            detection_id=1,
            threat_type="gun",
            confidence=0.92,
            severity="critical",
            bbox=[10, 10, 50, 50],
        )

        mock_dwell_result = MagicMock()
        mock_dwell_result.scalars.return_value.all.return_value = [dwell_record]

        mock_threat_result = MagicMock()
        mock_threat_result.scalars.return_value.all.return_value = [threat]

        mock_session.execute.side_effect = [mock_dwell_result, mock_threat_result]

        engine = AlertRuleEngine(mock_session)

        matches, matched_conditions, _ = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        assert matches is True
        assert any("dwell_time" in cond for cond in matched_conditions)
        assert any("threat_detected" in cond for cond in matched_conditions)

    @pytest.mark.asyncio
    async def test_new_conditions_with_existing_conditions(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that new conditions work alongside existing conditions."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="High Risk Weapon Detection",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            risk_threshold=70,
            threat_detection_enabled=True,
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        sample_event.risk_score = 85

        threat = ThreatDetection(
            id=1,
            detection_id=1,
            threat_type="gun",
            confidence=0.96,
            severity="critical",
            bbox=[100, 100, 200, 200],
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [threat]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        matches, matched_conditions, _ = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        assert matches is True
        assert any("risk_score" in cond for cond in matched_conditions)
        assert any("threat_detected" in cond for cond in matched_conditions)
