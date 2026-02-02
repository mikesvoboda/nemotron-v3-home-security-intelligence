"""Unit tests for new Alert Rule Condition Types (TDD RED phase).

This module contains failing tests that define expected behavior for:
1. dwell_time - Alert when dwell exceeds threshold (data from DwellTimeRecord)
2. pose_type - Alert on specific poses (data from PoseResult)
3. action_type - Alert on X-CLIP actions (data from ActionResult)
4. threat_detected - Alert on weapon detection (data from ThreatDetection)
5. smoke_fire - Alert on smoke/fire (future model)

These tests are written FIRST (TDD red phase) and will initially fail.
Implementation should follow in the alert engine service.

Design reference: docs/plans/2026-02-01-platform-enhancement-strategy-design.md
Related issue: NEM-5084
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models import (
    ActionResult,
    AlertRule,
    AlertSeverity,
    Detection,
    DwellTimeRecord,
    Event,
    PoseResult,
    ThreatDetection,
)
from backend.services.alert_engine import AlertRuleEngine

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
            confidence=0.72,
        ),
    ]


# =============================================================================
# Dwell Time Condition Tests
# =============================================================================


class TestDwellTimeCondition:
    """Tests for dwell_time alert condition type.

    The dwell_time condition should:
    - Alert when an object dwells in a zone beyond a threshold
    - Support zone-specific filtering
    - Optionally exclude household members
    - Query DwellTimeRecord table for data
    """

    @pytest.mark.asyncio
    async def test_dwell_time_condition_triggers_when_exceeded(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that dwell_time condition triggers when threshold is exceeded.

        Expected behavior:
        - Rule has dwell_threshold_seconds=30
        - DwellTimeRecord exists with total_seconds=45 (exceeds threshold)
        - Rule should match and trigger alert
        """
        # Arrange: Create rule with dwell_time condition
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Loitering Detection",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            dwell_threshold_seconds=30,  # NEW FIELD - will fail until implemented
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock DwellTimeRecord query returning a record that exceeds threshold
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

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [dwell_record]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should match
        assert matches is True
        assert any("dwell_time" in cond for cond in matched_conditions)

    @pytest.mark.asyncio
    async def test_dwell_time_condition_no_trigger_below_threshold(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that dwell_time condition does not trigger when below threshold.

        Expected behavior:
        - Rule has dwell_threshold_seconds=60
        - DwellTimeRecord exists with total_seconds=30 (below threshold)
        - Rule should NOT match
        """
        # Arrange: Create rule with dwell_time condition
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Long Loitering Detection",
            enabled=True,
            severity=AlertSeverity.HIGH,
            dwell_threshold_seconds=60,  # NEW FIELD
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock DwellTimeRecord query returning a record below threshold
        dwell_record = DwellTimeRecord(
            id=1,
            zone_id=10,
            track_id=42,
            camera_id="front_door",
            object_class="person",
            entry_time=datetime.now(UTC) - timedelta(seconds=30),
            exit_time=None,
            total_seconds=30.0,
            triggered_alert=False,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [dwell_record]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should NOT match
        assert matches is False

    @pytest.mark.asyncio
    async def test_dwell_time_with_specific_zone_ids(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that dwell_time can filter by specific zone IDs.

        Expected behavior:
        - Rule has dwell_threshold_seconds=30 and zone_ids=[5, 10]
        - DwellTimeRecord exists with zone_id=10, total_seconds=45
        - Rule should match (zone matches and threshold exceeded)
        """
        # Arrange: Create rule with dwell_time and zone filter
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Entry Zone Loitering",
            enabled=True,
            severity=AlertSeverity.HIGH,
            dwell_threshold_seconds=30,
            zone_ids=[5, 10],  # Existing field
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock DwellTimeRecord in matching zone
        dwell_record = DwellTimeRecord(
            id=1,
            zone_id=10,  # Matches rule zone_ids
            track_id=42,
            camera_id="front_door",
            object_class="person",
            entry_time=datetime.now(UTC) - timedelta(seconds=45),
            exit_time=None,
            total_seconds=45.0,
            triggered_alert=False,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [dwell_record]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should match
        assert matches is True
        assert any("dwell_time" in cond for cond in matched_conditions)

    @pytest.mark.asyncio
    async def test_dwell_time_excludes_household_members(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that dwell_time can exclude household members.

        Expected behavior:
        - Rule has dwell_threshold_seconds=30 and exclude_household=True
        - Detection is matched to a household member (via household matcher)
        - Rule should NOT trigger (household member excluded)
        """
        # Arrange: Create rule with household exclusion
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Stranger Loitering",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            dwell_threshold_seconds=30,
            exclude_household_members=True,  # NEW FIELD
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock DwellTimeRecord
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

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [dwell_record]
        mock_session.execute.return_value = mock_result

        # Mock household matcher to return a match (household member detected)
        with patch(
            "backend.services.alert_engine.household_matcher_service.check_household_match",
            new_callable=AsyncMock,
            return_value=True,  # Is household member
        ):
            engine = AlertRuleEngine(mock_session)

            # Act: Evaluate rule
            matches, matched_conditions = await engine._evaluate_rule(
                rule, sample_event, sample_detections, datetime.now(UTC)
            )

        # Assert: Rule should NOT match (household member excluded)
        assert matches is False


# =============================================================================
# Pose Type Condition Tests
# =============================================================================


class TestPoseTypeCondition:
    """Tests for pose_type alert condition type.

    The pose_type condition should:
    - Alert on specific poses (crouching, lying_down, climbing, etc.)
    - Support confidence thresholds
    - Query PoseResult table for data
    """

    @pytest.mark.asyncio
    async def test_pose_type_triggers_on_crouching(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that pose_type condition triggers on crouching pose.

        Expected behavior:
        - Rule has pose_types=["crouching"]
        - PoseResult exists with pose_class="crouching"
        - Rule should match and trigger alert
        """
        # Arrange: Create rule with pose_type condition
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Suspicious Crouching",
            enabled=True,
            severity=AlertSeverity.HIGH,
            pose_types=["crouching"],  # NEW FIELD - will fail until implemented
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock PoseResult query
        pose_result = PoseResult(
            id=1,
            detection_id=1,
            keypoints=[[0, 0, 0.9]] * 17,  # Mock keypoints
            pose_class="crouching",
            confidence=0.92,
            is_suspicious=True,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pose_result]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should match
        assert matches is True
        assert any("pose_type" in cond for cond in matched_conditions)

    @pytest.mark.asyncio
    async def test_pose_type_triggers_on_lying_down(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that pose_type condition triggers on lying_down pose.

        Expected behavior:
        - Rule has pose_types=["lying_down"]
        - PoseResult exists with pose_class="lying_down"
        - Rule should match (could indicate fall or injury)
        """
        # Arrange: Create rule for fall detection
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Fall Detection",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            pose_types=["lying_down"],  # NEW FIELD
            cooldown_seconds=60,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock PoseResult query
        pose_result = PoseResult(
            id=1,
            detection_id=1,
            keypoints=[[0, 0, 0.9]] * 17,
            pose_class="lying_down",
            confidence=0.88,
            is_suspicious=True,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pose_result]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should match
        assert matches is True
        assert any("pose_type" in cond for cond in matched_conditions)

    @pytest.mark.asyncio
    async def test_pose_type_triggers_on_climbing(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that pose_type condition triggers on climbing pose.

        Expected behavior:
        - Rule has pose_types=["climbing"]
        - PoseResult exists with pose_class="climbing" (arms_raised)
        - Rule should match (potential intrusion attempt)
        """
        # Arrange: Create rule for climbing detection
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Fence Climbing Alert",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            pose_types=["climbing", "arms_raised"],  # NEW FIELD
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock PoseResult query
        pose_result = PoseResult(
            id=1,
            detection_id=1,
            keypoints=[[0, 0, 0.9]] * 17,
            pose_class="arms_raised",
            confidence=0.91,
            is_suspicious=True,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pose_result]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should match
        assert matches is True
        assert any("pose_type" in cond for cond in matched_conditions)

    @pytest.mark.asyncio
    async def test_pose_type_no_trigger_for_standing(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that pose_type condition does not trigger for standing pose.

        Expected behavior:
        - Rule has pose_types=["crouching", "lying_down"]
        - PoseResult exists with pose_class="standing"
        - Rule should NOT match (standing not in trigger list)
        """
        # Arrange: Create rule that doesn't include standing
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Suspicious Poses Only",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            pose_types=["crouching", "lying_down"],  # NEW FIELD
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock PoseResult query with standing pose
        pose_result = PoseResult(
            id=1,
            detection_id=1,
            keypoints=[[0, 0, 0.9]] * 17,
            pose_class="standing",
            confidence=0.95,
            is_suspicious=False,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pose_result]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should NOT match
        assert matches is False

    @pytest.mark.asyncio
    async def test_pose_type_with_confidence_threshold(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that pose_type respects confidence threshold.

        Expected behavior:
        - Rule has pose_types=["crouching"] and pose_confidence_threshold=0.9
        - PoseResult has pose_class="crouching" but confidence=0.75
        - Rule should NOT match (confidence below threshold)
        """
        # Arrange: Create rule with confidence threshold
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="High Confidence Crouching",
            enabled=True,
            severity=AlertSeverity.HIGH,
            pose_types=["crouching"],
            pose_confidence_threshold=0.9,  # NEW FIELD
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock PoseResult with low confidence
        pose_result = PoseResult(
            id=1,
            detection_id=1,
            keypoints=[[0, 0, 0.9]] * 17,
            pose_class="crouching",
            confidence=0.75,  # Below threshold
            is_suspicious=True,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pose_result]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should NOT match (confidence too low)
        assert matches is False


# =============================================================================
# Action Type Condition Tests
# =============================================================================


class TestActionTypeCondition:
    """Tests for action_type alert condition type.

    The action_type condition should:
    - Alert on specific X-CLIP recognized actions
    - Support confidence thresholds
    - Query ActionResult table for data
    """

    @pytest.mark.asyncio
    async def test_action_type_triggers_on_loitering(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that action_type condition triggers on loitering action.

        Expected behavior:
        - Rule has action_types=["loitering"]
        - ActionResult exists with action="loitering"
        - Rule should match and trigger alert
        """
        # Arrange: Create rule with action_type condition
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Loitering Detection",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            action_types=["loitering"],  # NEW FIELD - will fail until implemented
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock ActionResult query
        action_result = ActionResult(
            id=1,
            detection_id=1,
            action="loitering",
            confidence=0.87,
            is_suspicious=True,
            all_scores={"loitering": 0.87, "walking": 0.13},
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [action_result]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should match
        assert matches is True
        assert any("action_type" in cond for cond in matched_conditions)

    @pytest.mark.asyncio
    async def test_action_type_triggers_on_suspicious_behavior(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that action_type condition triggers on suspicious behavior.

        Expected behavior:
        - Rule has action_types=["peering_through_window"]
        - ActionResult exists with action="peering_through_window"
        - Rule should match
        """
        # Arrange: Create rule for suspicious actions
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Suspicious Behavior Alert",
            enabled=True,
            severity=AlertSeverity.HIGH,
            action_types=["peering_through_window", "trying_door_handle"],  # NEW FIELD
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock ActionResult query
        action_result = ActionResult(
            id=1,
            detection_id=1,
            action="peering_through_window",
            confidence=0.83,
            is_suspicious=True,
            all_scores={"peering_through_window": 0.83, "walking": 0.17},
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [action_result]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should match
        assert matches is True
        assert any("action_type" in cond for cond in matched_conditions)

    @pytest.mark.asyncio
    async def test_action_type_multiple_actions_any_match(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that action_type triggers if ANY action in list matches (OR logic).

        Expected behavior:
        - Rule has action_types=["running", "climbing", "jumping"]
        - ActionResult exists with action="running"
        - Rule should match (one of the actions matched)
        """
        # Arrange: Create rule with multiple action types
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Athletic Activity Alert",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            action_types=["running", "climbing", "jumping"],  # NEW FIELD
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock ActionResult query with one matching action
        action_result = ActionResult(
            id=1,
            detection_id=1,
            action="running",
            confidence=0.91,
            is_suspicious=False,
            all_scores={"running": 0.91, "walking": 0.09},
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [action_result]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should match
        assert matches is True
        assert any("action_type" in cond for cond in matched_conditions)

    @pytest.mark.asyncio
    async def test_action_type_with_confidence_threshold(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that action_type respects confidence threshold.

        Expected behavior:
        - Rule has action_types=["loitering"] and action_confidence_threshold=0.9
        - ActionResult has action="loitering" but confidence=0.70
        - Rule should NOT match (confidence below threshold)
        """
        # Arrange: Create rule with confidence threshold
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="High Confidence Loitering",
            enabled=True,
            severity=AlertSeverity.HIGH,
            action_types=["loitering"],
            action_confidence_threshold=0.9,  # NEW FIELD
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock ActionResult with low confidence
        action_result = ActionResult(
            id=1,
            detection_id=1,
            action="loitering",
            confidence=0.70,  # Below threshold
            is_suspicious=True,
            all_scores={"loitering": 0.70, "standing": 0.30},
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [action_result]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should NOT match (confidence too low)
        assert matches is False


# =============================================================================
# Threat Detection Condition Tests
# =============================================================================


class TestThreatDetectedCondition:
    """Tests for threat_detected alert condition type.

    The threat_detected condition should:
    - Alert on weapon detections (gun, knife, etc.)
    - Support severity filtering
    - Support confidence thresholds
    - Query ThreatDetection table for data
    - Bypass batching for CRITICAL alerts
    """

    @pytest.mark.asyncio
    async def test_threat_detected_triggers_on_weapon(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that threat_detected condition triggers on weapon detection.

        Expected behavior:
        - Rule has threat_detection_enabled=True
        - ThreatDetection exists with threat_type="gun"
        - Rule should match and trigger CRITICAL alert
        """
        # Arrange: Create rule with threat detection
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Weapon Detection",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            threat_detection_enabled=True,  # NEW FIELD - will fail until implemented
            cooldown_seconds=0,  # No cooldown for threats
            dedup_key_template="{camera_id}:{rule_id}:{threat_type}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock ThreatDetection query
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

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should match
        assert matches is True
        assert any("threat_detected" in cond for cond in matched_conditions)

    @pytest.mark.asyncio
    async def test_threat_detected_gun_is_critical(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that gun detection results in CRITICAL severity.

        Expected behavior:
        - ThreatDetection exists with threat_type="gun"
        - Alert severity should be CRITICAL regardless of rule severity
        - Should bypass normal batching (immediate alert)
        """
        # Arrange: Create rule with threat detection
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Any Weapon",
            enabled=True,
            severity=AlertSeverity.HIGH,  # Lower severity
            threat_detection_enabled=True,
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}:{threat_type}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock ThreatDetection query with gun
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

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should match
        assert matches is True
        # Note: Severity override to CRITICAL should happen in alert creation
        assert any("threat_detected" in cond for cond in matched_conditions)

    @pytest.mark.asyncio
    async def test_threat_detected_knife_is_high(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that knife detection results in HIGH severity.

        Expected behavior:
        - ThreatDetection exists with threat_type="knife"
        - Alert severity should be HIGH
        """
        # Arrange: Create rule with threat detection
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Sharp Object Detection",
            enabled=True,
            severity=AlertSeverity.HIGH,
            threat_detection_enabled=True,
            threat_types=["knife"],  # NEW FIELD - filter by type
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}:{threat_type}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock ThreatDetection query with knife
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

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should match
        assert matches is True
        assert any("threat_detected" in cond for cond in matched_conditions)

    @pytest.mark.asyncio
    async def test_threat_detected_with_severity_filter(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that threat_detected can filter by severity level.

        Expected behavior:
        - Rule has threat_min_severity="critical"
        - ThreatDetection exists with severity="high"
        - Rule should NOT match (severity below minimum)
        """
        # Arrange: Create rule with severity filter
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Critical Threats Only",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            threat_detection_enabled=True,
            threat_min_severity="critical",  # NEW FIELD
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock ThreatDetection with lower severity
        threat = ThreatDetection(
            id=1,
            detection_id=1,
            threat_type="knife",
            confidence=0.89,
            severity="high",  # Below "critical"
            bbox=[150, 150, 250, 250],
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [threat]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should NOT match (severity too low)
        assert matches is False

    @pytest.mark.asyncio
    async def test_threat_detected_with_confidence_threshold(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that threat_detected respects confidence threshold.

        Expected behavior:
        - Rule has threat_confidence_threshold=0.95
        - ThreatDetection has confidence=0.85
        - Rule should NOT match (confidence below threshold)
        """
        # Arrange: Create rule with confidence threshold
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="High Confidence Threats",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            threat_detection_enabled=True,
            threat_confidence_threshold=0.95,  # NEW FIELD
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock ThreatDetection with lower confidence
        threat = ThreatDetection(
            id=1,
            detection_id=1,
            threat_type="gun",
            confidence=0.85,  # Below threshold
            severity="critical",
            bbox=[100, 100, 200, 200],
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [threat]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should NOT match (confidence too low)
        assert matches is False


# =============================================================================
# Smoke/Fire Detection Condition Tests
# =============================================================================


class TestSmokeFireCondition:
    """Tests for smoke_fire alert condition type.

    The smoke_fire condition should:
    - Alert on smoke or fire detection
    - Require consecutive detections to reduce false positives
    - Support confidence thresholds
    - Query future SmokeFireResult table (model not yet implemented)
    """

    @pytest.mark.asyncio
    async def test_smoke_fire_condition_triggers(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that smoke_fire condition triggers on smoke/fire detection.

        Expected behavior:
        - Rule has smoke_fire_detection_enabled=True
        - SmokeFireResult exists (mocked - model not yet implemented)
        - Rule should match and trigger CRITICAL alert
        """
        # Arrange: Create rule with smoke/fire detection
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Fire Safety Alert",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            smoke_fire_detection_enabled=True,  # NEW FIELD - will fail until implemented
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock SmokeFireResult query (future model)
        # For now, simulate with a MagicMock
        smoke_result = MagicMock()
        smoke_result.detection_id = 1
        smoke_result.detection_type = "smoke"
        smoke_result.confidence = 0.92
        smoke_result.bbox = [100, 100, 300, 300]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [smoke_result]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should match
        assert matches is True
        assert any("smoke_fire" in cond for cond in matched_conditions)

    @pytest.mark.asyncio
    async def test_smoke_fire_requires_consecutive_detections(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that smoke_fire requires multiple consecutive detections.

        Expected behavior:
        - Rule has smoke_fire_detection_enabled=True
        - Rule has smoke_fire_consecutive_required=2
        - Only 1 detection exists (not enough)
        - Rule should NOT match (need 2 consecutive)
        """
        # Arrange: Create rule requiring consecutive detections
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Fire Safety with Confirmation",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            smoke_fire_detection_enabled=True,
            smoke_fire_consecutive_required=2,  # NEW FIELD
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock only 1 smoke detection (need 2)
        smoke_result = MagicMock()
        smoke_result.detection_id = 1
        smoke_result.detection_type = "smoke"
        smoke_result.confidence = 0.92
        smoke_result.consecutive_count = 1  # Not enough

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [smoke_result]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should NOT match (need more consecutive detections)
        assert matches is False

    @pytest.mark.asyncio
    async def test_smoke_fire_with_confidence_threshold(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that smoke_fire respects confidence threshold.

        Expected behavior:
        - Rule has smoke_fire_confidence_threshold=0.9
        - SmokeFireResult has confidence=0.70
        - Rule should NOT match (confidence below threshold)
        """
        # Arrange: Create rule with confidence threshold
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="High Confidence Fire Detection",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            smoke_fire_detection_enabled=True,
            smoke_fire_confidence_threshold=0.9,  # NEW FIELD
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock SmokeFireResult with low confidence
        smoke_result = MagicMock()
        smoke_result.detection_id = 1
        smoke_result.detection_type = "smoke"
        smoke_result.confidence = 0.70  # Below threshold
        smoke_result.bbox = [100, 100, 300, 300]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [smoke_result]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should NOT match (confidence too low)
        assert matches is False


# =============================================================================
# Combined Conditions Tests
# =============================================================================


class TestCombinedConditions:
    """Tests for combining new condition types with existing conditions.

    Tests that new conditions work with AND logic alongside existing conditions.
    """

    @pytest.mark.asyncio
    async def test_multiple_new_conditions_and_logic(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that multiple new conditions use AND logic.

        Expected behavior:
        - Rule has dwell_threshold_seconds=30 AND pose_types=["crouching"]
        - DwellTimeRecord exceeds threshold AND PoseResult matches
        - Rule should match (both conditions satisfied)
        """
        # Arrange: Create rule with multiple new conditions
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Crouching Loiterer",
            enabled=True,
            severity=AlertSeverity.HIGH,
            dwell_threshold_seconds=30,  # NEW FIELD
            pose_types=["crouching"],  # NEW FIELD
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock DwellTimeRecord
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

        # Mock PoseResult
        pose_result = PoseResult(
            id=1,
            detection_id=1,
            keypoints=[[0, 0, 0.9]] * 17,
            pose_class="crouching",
            confidence=0.92,
            is_suspicious=True,
        )

        # Mock both queries
        mock_dwell_result = MagicMock()
        mock_dwell_result.scalars.return_value.all.return_value = [dwell_record]

        mock_pose_result = MagicMock()
        mock_pose_result.scalars.return_value.all.return_value = [pose_result]

        # Configure mock to return different results for different queries
        mock_session.execute.side_effect = [mock_dwell_result, mock_pose_result]

        engine = AlertRuleEngine(mock_session)

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should match (both conditions met)
        assert matches is True
        assert any("dwell_time" in cond for cond in matched_conditions)
        assert any("pose_type" in cond for cond in matched_conditions)

    @pytest.mark.asyncio
    async def test_new_conditions_with_existing_conditions(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test that new conditions work alongside existing conditions.

        Expected behavior:
        - Rule has risk_threshold=70 (existing) AND threat_detection_enabled=True (new)
        - Event risk_score=85 AND ThreatDetection exists
        - Rule should match (all conditions satisfied)
        """
        # Arrange: Create rule with existing and new conditions
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="High Risk Weapon Detection",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            risk_threshold=70,  # Existing condition
            threat_detection_enabled=True,  # NEW FIELD
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Set event risk_score to meet threshold
        sample_event.risk_score = 85

        # Mock ThreatDetection
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

        # Act: Evaluate rule
        matches, matched_conditions = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )

        # Assert: Rule should match (both existing and new conditions met)
        assert matches is True
        assert any("risk_score" in cond for cond in matched_conditions)
        assert any("threat_detected" in cond for cond in matched_conditions)
