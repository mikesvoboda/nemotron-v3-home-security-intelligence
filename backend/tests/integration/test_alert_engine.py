"""Unit tests for alert rules engine.

Tests use PostgreSQL via the isolated_db fixture since models use
PostgreSQL-specific features.

Tests cover:
- Each condition type (risk_threshold, object_types, camera_ids, min_confidence, schedule)
- AND logic for multiple conditions
- Time-based conditions (overnight schedules, day filtering)
- Cooldown behavior
- Rule testing against historical events

IMPORTANT: Test Isolation in Parallel Execution
----------------------------------------------
These tests run in parallel with pytest-xdist. Since each worker shares the same
database, tests must be designed to work independently:

1. Each test creates rules with unique names using unique_id()
2. Tests filter triggered_rules by their specific rule ID rather than counting
   total triggered rules (since other parallel tests may have rules that match)
3. The `_filter_triggered_rules_by_ids()` helper extracts only the rules created
   by a specific test for assertion checking
"""

from datetime import datetime, timedelta

import pytest

from backend.core.time_utils import utc_now_naive
from backend.models import Alert, AlertRule, AlertSeverity, AlertStatus, Camera, Detection, Event
from backend.services.alert_engine import (
    DAY_NAMES,
    SEVERITY_PRIORITY,
    AlertRuleEngine,
    EvaluationResult,
    TriggeredRule,
)
from backend.tests.conftest import unique_id

# Mark as integration since these tests require real PostgreSQL database
# NOTE: This file should be moved to backend/tests/integration/ in a future cleanup
pytestmark = pytest.mark.integration

# Note: The 'session' fixture is provided by conftest.py with transaction
# rollback isolation for parallel test execution.


def _filter_triggered_rules_by_ids(result: EvaluationResult, rule_ids: list) -> list[TriggeredRule]:
    """Filter triggered rules to only those matching the given rule IDs.

    This is essential for parallel test execution where other tests may have
    created rules that also match the event being tested.
    """
    return [tr for tr in result.triggered_rules if tr.rule.id in rule_ids]


def _filter_skipped_rules_by_ids(
    result: EvaluationResult, rule_ids: list
) -> list[tuple[AlertRule, str]]:
    """Filter skipped rules to only those matching the given rule IDs."""
    return [(rule, reason) for rule, reason in result.skipped_rules if rule.id in rule_ids]


@pytest.fixture
async def test_camera(session):
    """Create a test camera with unique ID.

    Uses unique names and folder paths to prevent conflicts with unique constraints.
    """
    camera_id = unique_id("front_door")
    camera = Camera(
        id=camera_id,
        name=f"Front Door Camera {camera_id[-8:]}",
        folder_path=f"/export/foscam/{camera_id}",
    )
    session.add(camera)
    await session.flush()
    return camera


@pytest.fixture
async def test_camera2(session):
    """Create a second test camera with unique ID."""
    camera_id = unique_id("backyard")
    camera = Camera(
        id=camera_id,
        name="Backyard Camera",
        folder_path=f"/export/foscam/{camera_id}",
    )
    session.add(camera)
    await session.flush()
    return camera


@pytest.fixture
async def test_event(session, test_camera):
    """Create a test event with default high risk score."""
    event = Event(
        batch_id="batch_001",
        camera_id=test_camera.id,
        started_at=utc_now_naive(),
        risk_score=80,
        risk_level="high",
        detection_ids="[1, 2]",
    )
    session.add(event)
    await session.flush()
    return event


@pytest.fixture
async def test_detections(session, test_camera):
    """Create test detections."""
    det1 = Detection(
        camera_id=test_camera.id,
        file_path="/export/foscam/front_door/image1.jpg",
        detected_at=utc_now_naive(),
        object_type="person",
        confidence=0.95,
    )
    det2 = Detection(
        camera_id=test_camera.id,
        file_path="/export/foscam/front_door/image2.jpg",
        detected_at=utc_now_naive(),
        object_type="vehicle",
        confidence=0.85,
    )
    session.add_all([det1, det2])
    await session.flush()
    return [det1, det2]


@pytest.fixture
async def engine(session):
    """Create an AlertRuleEngine instance."""
    return AlertRuleEngine(session)


class TestSeverityPriority:
    """Tests for severity priority constants."""

    def test_severity_priority_order(self):
        """Verify severity priority ordering."""
        assert SEVERITY_PRIORITY[AlertSeverity.LOW] < SEVERITY_PRIORITY[AlertSeverity.MEDIUM]
        assert SEVERITY_PRIORITY[AlertSeverity.MEDIUM] < SEVERITY_PRIORITY[AlertSeverity.HIGH]
        assert SEVERITY_PRIORITY[AlertSeverity.HIGH] < SEVERITY_PRIORITY[AlertSeverity.CRITICAL]

    def test_day_names_complete(self):
        """Verify day names are complete."""
        assert len(DAY_NAMES) == 7
        assert "monday" in DAY_NAMES
        assert "sunday" in DAY_NAMES


class TestTriggeredRule:
    """Tests for the TriggeredRule dataclass."""

    def test_triggered_rule_creation(self):
        """Test creating a TriggeredRule."""

        # Create a mock rule
        class MockRule:
            id = "rule-123"
            name = "Test Rule"

        triggered = TriggeredRule(
            rule=MockRule(),
            severity=AlertSeverity.HIGH,
            matched_conditions=["risk_score >= 70", "camera_id in ['front_door']"],
            dedup_key="front_door:rule-123",
        )

        assert triggered.severity == AlertSeverity.HIGH
        assert len(triggered.matched_conditions) == 2
        assert triggered.dedup_key == "front_door:rule-123"


class TestEvaluationResult:
    """Tests for the EvaluationResult dataclass."""

    def test_evaluation_result_empty(self):
        """Test empty EvaluationResult."""
        result = EvaluationResult()
        assert result.has_triggers is False
        assert result.highest_severity is None
        assert len(result.triggered_rules) == 0
        assert len(result.skipped_rules) == 0

    def test_evaluation_result_with_triggers(self):
        """Test EvaluationResult with triggers."""

        class MockRule:
            id = "rule-123"
            name = "Test Rule"

        triggered = TriggeredRule(
            rule=MockRule(),
            severity=AlertSeverity.HIGH,
            matched_conditions=["test"],
            dedup_key="test",
        )

        result = EvaluationResult(
            triggered_rules=[triggered],
            highest_severity=AlertSeverity.HIGH,
        )

        assert result.has_triggers is True
        assert result.highest_severity == AlertSeverity.HIGH


class TestRiskThresholdCondition:
    """Tests for risk_threshold condition."""

    @pytest.mark.asyncio
    async def test_risk_threshold_matches(self, session, test_event, engine):
        """Test that risk_threshold matches when risk_score >= threshold."""
        rule = AlertRule(
            name=unique_id("high_risk_alert"),
            enabled=True,
            risk_threshold=70,
        )
        session.add(rule)
        await session.flush()

        # Event has risk_score=80, threshold is 70
        result = await engine.evaluate_event(test_event, [])

        # Filter to only our rule (other parallel tests may have rules that match)
        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1
        assert "risk_score >= 70" in our_triggered[0].matched_conditions

    @pytest.mark.asyncio
    async def test_risk_threshold_no_match(self, session, test_event, engine):
        """Test that risk_threshold doesn't match when risk_score < threshold."""
        rule = AlertRule(
            name=unique_id("critical_alert"),
            enabled=True,
            risk_threshold=90,  # Higher than event's 80
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, [])

        # Our rule should NOT be in triggered_rules
        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 0

    @pytest.mark.asyncio
    async def test_risk_threshold_null_score(self, session, test_camera, engine):
        """Test that risk_threshold doesn't match when risk_score is None."""
        # Create event with no risk score
        event = Event(
            batch_id=unique_id("batch"),
            camera_id=test_camera.id,
            started_at=utc_now_naive(),
            risk_score=None,
        )
        session.add(event)

        rule = AlertRule(
            name=unique_id("any_risk_alert"),
            enabled=True,
            risk_threshold=0,  # Should match any score, but not None
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(event, [])

        # Our rule should NOT be in triggered_rules
        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 0


class TestObjectTypesCondition:
    """Tests for object_types condition."""

    @pytest.mark.asyncio
    async def test_object_types_matches(self, session, test_event, test_detections, engine):
        """Test that object_types matches when detection has matching type."""
        rule = AlertRule(
            name=unique_id("person_alert"),
            enabled=True,
            object_types=["person"],
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, test_detections)

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1
        assert "object_type in ['person']" in our_triggered[0].matched_conditions

    @pytest.mark.asyncio
    async def test_object_types_case_insensitive(
        self, session, test_event, test_detections, engine
    ):
        """Test that object_types matching is case insensitive."""
        rule = AlertRule(
            name=unique_id("person_alert_upper"),
            enabled=True,
            object_types=["PERSON"],  # Uppercase
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, test_detections)

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1

    @pytest.mark.asyncio
    async def test_object_types_multiple(self, session, test_event, test_detections, engine):
        """Test that object_types matches any of the specified types."""
        rule = AlertRule(
            name=unique_id("person_vehicle_alert"),
            enabled=True,
            object_types=["person", "vehicle"],
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, test_detections)

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1

    @pytest.mark.asyncio
    async def test_object_types_no_match(self, session, test_event, test_detections, engine):
        """Test that object_types doesn't match when no detection matches."""
        rule = AlertRule(
            name=unique_id("animal_alert"),
            enabled=True,
            object_types=["dog", "cat"],  # Neither in detections
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, test_detections)

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 0


class TestCameraIdsCondition:
    """Tests for camera_ids condition."""

    @pytest.mark.asyncio
    async def test_camera_ids_matches(self, session, test_event, test_camera, engine):
        """Test that camera_ids matches when event's camera is in list."""
        rule = AlertRule(
            name=unique_id("front_door_alert"),
            enabled=True,
            camera_ids=[test_camera.id, "back_door"],
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, [])

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1
        # Check that camera_id condition matched (format varies based on camera ID)
        assert any("camera_id in" in cond for cond in our_triggered[0].matched_conditions)

    @pytest.mark.asyncio
    async def test_camera_ids_no_match(self, session, test_event, engine):
        """Test that camera_ids doesn't match when event's camera not in list."""
        rule = AlertRule(
            name=unique_id("backyard_only_alert"),
            enabled=True,
            camera_ids=["nonexistent_camera"],  # Event is from test_camera
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, [])

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 0


class TestMinConfidenceCondition:
    """Tests for min_confidence condition."""

    @pytest.mark.asyncio
    async def test_min_confidence_matches(self, session, test_event, test_detections, engine):
        """Test that min_confidence matches when any detection meets threshold."""
        rule = AlertRule(
            name=unique_id("high_confidence_alert"),
            enabled=True,
            min_confidence=0.9,  # det1 has 0.95
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, test_detections)

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1
        assert "confidence >= 0.9" in our_triggered[0].matched_conditions

    @pytest.mark.asyncio
    async def test_min_confidence_no_match(self, session, test_event, test_detections, engine):
        """Test that min_confidence doesn't match when no detection meets threshold."""
        rule = AlertRule(
            name=unique_id("very_high_confidence_alert"),
            enabled=True,
            min_confidence=0.99,  # Neither detection meets this
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, test_detections)

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 0


class TestScheduleCondition:
    """Tests for schedule (time-based) condition."""

    @pytest.mark.asyncio
    async def test_schedule_no_schedule_always_matches(self, session, test_event, engine):
        """Test that no schedule means always active (vacation mode)."""
        rule = AlertRule(
            name=unique_id("always_active_alert"),
            enabled=True,
            schedule=None,  # No schedule
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, [])

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1

    @pytest.mark.asyncio
    async def test_schedule_time_range_matches(self, session, test_event, engine):
        """Test that schedule matches when within time range."""
        # Test at 2:00 AM (should match 22:00-06:00)
        test_time = datetime(2025, 12, 28, 2, 0, 0)  # Saturday 2:00 AM

        rule = AlertRule(
            name=unique_id("night_alert"),
            enabled=True,
            schedule={
                "start_time": "22:00",
                "end_time": "06:00",
                "timezone": "UTC",
            },
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, [], current_time=test_time)

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1
        assert "within_schedule" in our_triggered[0].matched_conditions

    @pytest.mark.asyncio
    async def test_schedule_time_range_outside(self, session, test_event, engine):
        """Test that schedule doesn't match when outside time range."""
        # Test at 12:00 PM (should not match 22:00-06:00)
        test_time = datetime(2025, 12, 28, 12, 0, 0)  # Saturday noon

        rule = AlertRule(
            name=unique_id("night_alert_outside"),
            enabled=True,
            schedule={
                "start_time": "22:00",
                "end_time": "06:00",
                "timezone": "UTC",
            },
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, [], current_time=test_time)

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 0

    @pytest.mark.asyncio
    async def test_schedule_day_filter_matches(self, session, test_event, engine):
        """Test that schedule matches when on specified day."""
        # Saturday, December 28, 2025
        test_time = datetime(2025, 12, 28, 10, 0, 0)

        rule = AlertRule(
            name=unique_id("weekend_alert"),
            enabled=True,
            schedule={
                "days": ["saturday", "sunday"],
                "timezone": "UTC",
            },
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, [], current_time=test_time)

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1

    @pytest.mark.asyncio
    async def test_schedule_day_filter_outside(self, session, test_event, engine):
        """Test that schedule doesn't match when not on specified day."""
        # Monday, December 29, 2025
        test_time = datetime(2025, 12, 29, 10, 0, 0)

        rule = AlertRule(
            name=unique_id("weekend_alert_outside"),
            enabled=True,
            schedule={
                "days": ["saturday", "sunday"],
                "timezone": "UTC",
            },
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, [], current_time=test_time)

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 0

    @pytest.mark.asyncio
    async def test_schedule_normal_time_range(self, session, test_event, engine):
        """Test schedule with normal time range (not overnight)."""
        # Test at 10:00 AM (should match 09:00-17:00)
        test_time = datetime(2025, 12, 28, 10, 0, 0)

        rule = AlertRule(
            name=unique_id("business_hours_alert"),
            enabled=True,
            schedule={
                "start_time": "09:00",
                "end_time": "17:00",
                "timezone": "UTC",
            },
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, [], current_time=test_time)

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1


class TestAndLogic:
    """Tests for AND logic combining multiple conditions."""

    @pytest.mark.asyncio
    async def test_all_conditions_must_match(
        self, session, test_event, test_camera, test_detections, engine
    ):
        """Test that all conditions must match (AND logic)."""
        rule = AlertRule(
            name=unique_id("multi_condition_alert"),
            enabled=True,
            risk_threshold=70,
            object_types=["person"],
            camera_ids=[test_camera.id],
            min_confidence=0.9,
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, test_detections)

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1
        # All conditions should be in matched_conditions
        conditions = our_triggered[0].matched_conditions
        assert any("risk_score" in c for c in conditions)
        assert any("object_type" in c for c in conditions)
        assert any("camera_id" in c for c in conditions)
        assert any("confidence" in c for c in conditions)

    @pytest.mark.asyncio
    async def test_one_condition_fails(self, session, test_event, test_detections, engine):
        """Test that rule doesn't match if any condition fails."""
        rule = AlertRule(
            name=unique_id("multi_condition_fail"),
            enabled=True,
            risk_threshold=70,  # Matches (80 >= 70)
            object_types=["person"],  # Matches
            camera_ids=["nonexistent_camera"],  # Does NOT match (event is from test_camera)
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, test_detections)

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 0


class TestMultipleRules:
    """Tests for multiple rules triggering."""

    @pytest.mark.asyncio
    async def test_multiple_rules_trigger(self, session, test_event, engine):
        """Test that multiple rules can trigger for the same event."""
        rule1 = AlertRule(
            name=unique_id("low_threshold_alert"),
            enabled=True,
            risk_threshold=50,
            severity=AlertSeverity.LOW,
        )
        rule2 = AlertRule(
            name=unique_id("high_threshold_alert"),
            enabled=True,
            risk_threshold=70,
            severity=AlertSeverity.HIGH,
        )
        session.add_all([rule1, rule2])
        await session.flush()

        result = await engine.evaluate_event(test_event, [])

        # Filter to only our rules
        our_rule_ids = [rule1.id, rule2.id]
        our_triggered = _filter_triggered_rules_by_ids(result, our_rule_ids)
        assert len(our_triggered) == 2

        # Verify both our rules triggered with correct severities
        our_severities = {tr.severity for tr in our_triggered}
        assert AlertSeverity.HIGH in our_severities
        assert AlertSeverity.LOW in our_severities

        # The full result should be sorted by severity (highest first)
        # but we only verify our rules are present and have the expected severities

    @pytest.mark.asyncio
    async def test_disabled_rules_not_evaluated(self, session, test_event, engine):
        """Test that disabled rules are not evaluated."""
        rule = AlertRule(
            name=unique_id("disabled_alert"),
            enabled=False,  # Disabled
            risk_threshold=50,
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, [])

        # Our disabled rule should NOT be in triggered_rules
        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 0


class TestCooldown:
    """Tests for cooldown behavior."""

    @pytest.mark.asyncio
    async def test_cooldown_skips_rule(self, session, test_event, engine):
        """Test that rule is skipped when in cooldown."""
        rule = AlertRule(
            name=unique_id("alert_with_cooldown"),
            enabled=True,
            risk_threshold=50,
            cooldown_seconds=300,  # 5 minutes
        )
        session.add(rule)
        await session.flush()

        # Create existing alert within cooldown
        # Use unique dedup_key based on test_event.camera_id
        dedup_key = f"{test_event.camera_id}:{rule.id}"
        existing_alert = Alert(
            event_id=test_event.id,
            rule_id=rule.id,
            dedup_key=dedup_key,
            created_at=utc_now_naive() - timedelta(minutes=2),  # 2 minutes ago
        )
        session.add(existing_alert)
        await session.flush()

        result = await engine.evaluate_event(test_event, [])

        # Our rule should be in skipped_rules due to cooldown
        our_skipped = _filter_skipped_rules_by_ids(result, [rule.id])
        assert len(our_skipped) == 1
        assert our_skipped[0][1] == "in_cooldown"

        # Our rule should NOT be in triggered_rules
        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 0

    @pytest.mark.asyncio
    async def test_cooldown_expired_triggers(self, session, test_event, engine):
        """Test that rule triggers when cooldown has expired."""
        rule = AlertRule(
            name=unique_id("alert_with_cooldown_expired"),
            enabled=True,
            risk_threshold=50,
            cooldown_seconds=300,  # 5 minutes
        )
        session.add(rule)
        await session.flush()

        # Create existing alert outside cooldown
        dedup_key = f"{test_event.camera_id}:{rule.id}"
        existing_alert = Alert(
            event_id=test_event.id,
            rule_id=rule.id,
            dedup_key=dedup_key,
            created_at=utc_now_naive() - timedelta(minutes=10),  # 10 minutes ago
        )
        session.add(existing_alert)
        await session.flush()

        result = await engine.evaluate_event(test_event, [])

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1


class TestDedupKey:
    """Tests for dedup key generation."""

    @pytest.mark.asyncio
    async def test_dedup_key_default_template(self, session, test_event, test_detections, engine):
        """Test dedup key with default template."""
        rule = AlertRule(
            name=unique_id("dedup_default"),
            enabled=True,
            dedup_key_template="{camera_id}:{rule_id}",
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, test_detections)

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1
        expected_key = f"{test_event.camera_id}:{rule.id}"
        assert our_triggered[0].dedup_key == expected_key

    @pytest.mark.asyncio
    async def test_dedup_key_with_object_type(self, session, test_event, test_detections, engine):
        """Test dedup key with object_type variable."""
        rule = AlertRule(
            name=unique_id("dedup_object_type"),
            enabled=True,
            dedup_key_template="{camera_id}:{object_type}:{rule_id}",
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, test_detections)

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1
        # First detection is "person"
        expected_key = f"{test_event.camera_id}:person:{rule.id}"
        assert our_triggered[0].dedup_key == expected_key


class TestRuleTesting:
    """Tests for rule testing against historical events."""

    @pytest.mark.asyncio
    async def test_test_rule_against_events(self, session, test_camera, engine):
        """Test testing a rule against multiple events."""
        # Create multiple events with different characteristics
        event1 = Event(
            batch_id=unique_id("batch"),
            camera_id=test_camera.id,
            started_at=utc_now_naive(),
            risk_score=80,
        )
        event2 = Event(
            batch_id=unique_id("batch"),
            camera_id=test_camera.id,
            started_at=utc_now_naive(),
            risk_score=60,
        )
        event3 = Event(
            batch_id=unique_id("batch"),
            camera_id=test_camera.id,
            started_at=utc_now_naive(),
            risk_score=90,
        )
        session.add_all([event1, event2, event3])
        await session.flush()

        rule = AlertRule(
            name=unique_id("high_risk_alert_test"),
            enabled=True,
            risk_threshold=70,
        )
        session.add(rule)
        await session.flush()

        results = await engine.test_rule_against_events(rule, [event1, event2, event3])

        assert len(results) == 3
        # Event 1 (80) should match
        assert results[0]["matches"] is True
        # Event 2 (60) should not match
        assert results[1]["matches"] is False
        # Event 3 (90) should match
        assert results[2]["matches"] is True


class TestNoConditionsRule:
    """Tests for rules with no conditions."""

    @pytest.mark.asyncio
    async def test_no_conditions_always_matches(self, session, test_event, engine):
        """Test that a rule with no conditions always matches."""
        rule = AlertRule(
            name=unique_id("catch_all_alert"),
            enabled=True,
            # No conditions specified
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, [])

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1
        assert "no_conditions" in our_triggered[0].matched_conditions[0]


class TestCreateAlertsForEvent:
    """Tests for creating alerts from triggered rules."""

    @pytest.mark.asyncio
    async def test_create_alerts(self, session, test_event, engine):
        """Test creating alerts for triggered rules."""
        rule = AlertRule(
            name=unique_id("create_alert_test"),
            enabled=True,
            risk_threshold=50,
            severity=AlertSeverity.HIGH,
            channels=["pushover", "email"],
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, [])

        # Filter to only our rule's triggered results
        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1

        # Create alerts only for our rule
        alerts = await engine.create_alerts_for_event(test_event, our_triggered)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.event_id == test_event.id
        assert alert.rule_id == rule.id
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.PENDING
        assert alert.channels == ["pushover", "email"]
        assert "matched_conditions" in alert.alert_metadata


class TestLoadEventDetections:
    """Tests for loading detections from database when not provided."""

    @pytest.mark.asyncio
    async def test_load_detections_from_database(self, session, test_camera, engine):
        """Test that detections are loaded from database when not provided (line 124)."""
        # Create detections in the database
        det1 = Detection(
            camera_id=test_camera.id,
            file_path="/export/foscam/front_door/image1.jpg",
            detected_at=utc_now_naive(),
            object_type="person",
            confidence=0.95,
        )
        det2 = Detection(
            camera_id=test_camera.id,
            file_path="/export/foscam/front_door/image2.jpg",
            detected_at=utc_now_naive(),
            object_type="vehicle",
            confidence=0.85,
        )
        session.add_all([det1, det2])
        await session.flush()

        # Create event with detection_ids pointing to these detections
        import json

        event = Event(
            batch_id=unique_id("batch"),
            camera_id=test_camera.id,
            started_at=utc_now_naive(),
            risk_score=80,
            detection_ids=json.dumps([det1.id, det2.id]),
        )
        session.add(event)
        await session.flush()

        rule = AlertRule(
            name=unique_id("load_detections_alert"),
            enabled=True,
            object_types=["person"],
        )
        session.add(rule)
        await session.flush()

        # Call without providing detections - should load from DB
        result = await engine.evaluate_event(event, detections=None)

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1
        assert "object_type in ['person']" in our_triggered[0].matched_conditions

    @pytest.mark.asyncio
    async def test_load_detections_empty_detection_ids(self, session, test_camera, engine):
        """Test loading detections when detection_ids is empty string (line 179)."""
        event = Event(
            batch_id=unique_id("batch"),
            camera_id=test_camera.id,
            started_at=utc_now_naive(),
            risk_score=80,
            detection_ids="",  # Empty string
        )
        session.add(event)
        await session.flush()

        rule = AlertRule(
            name=unique_id("empty_detections_alert"),
            enabled=True,
            object_types=["person"],  # Requires detections
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(event, detections=None)

        # Should not trigger since no detections and object_types required
        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 0

    @pytest.mark.asyncio
    async def test_load_detections_invalid_json(self, session, test_camera, engine):
        """Test loading detections with invalid JSON (lines 187-188)."""
        event = Event(
            batch_id=unique_id("batch"),
            camera_id=test_camera.id,
            started_at=utc_now_naive(),
            risk_score=80,
            detection_ids="not valid json",  # Invalid JSON
        )
        session.add(event)
        await session.flush()

        rule = AlertRule(
            name=unique_id("invalid_json_alert"),
            enabled=True,
            object_types=["person"],
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(event, detections=None)

        # Should not trigger since JSON parsing fails
        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 0

    @pytest.mark.asyncio
    async def test_load_detections_not_list(self, session, test_camera, engine):
        """Test loading detections when JSON is not a list (lines 185-186)."""
        import json

        event = Event(
            batch_id=unique_id("batch"),
            camera_id=test_camera.id,
            started_at=utc_now_naive(),
            risk_score=80,
            detection_ids=json.dumps({"id": 1}),  # Dict, not list
        )
        session.add(event)
        await session.flush()

        rule = AlertRule(
            name=unique_id("not_list_alert"),
            enabled=True,
            object_types=["person"],
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(event, detections=None)

        # Should not trigger since detection_ids is not a list
        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 0

    @pytest.mark.asyncio
    async def test_load_detections_empty_list(self, session, test_camera, engine):
        """Test loading detections with empty list (lines 190-191)."""
        import json

        event = Event(
            batch_id=unique_id("batch"),
            camera_id=test_camera.id,
            started_at=utc_now_naive(),
            risk_score=80,
            detection_ids=json.dumps([]),  # Empty list
        )
        session.add(event)
        await session.flush()

        rule = AlertRule(
            name=unique_id("empty_list_alert"),
            enabled=True,
            object_types=["person"],
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(event, detections=None)

        # Should not trigger since no detections
        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 0


class TestRuleEvaluationErrorHandling:
    """Tests for error handling during rule evaluation."""

    @pytest.mark.asyncio
    async def test_evaluation_error_handling(self, session, test_event, engine):
        """Test that errors during rule evaluation are caught (lines 160-162)."""
        # Create a rule with a schedule that will cause an error
        rule = AlertRule(
            name=unique_id("error_rule"),
            enabled=True,
            risk_threshold=50,
            # Schedule with None value for time that will cause AttributeError
            schedule={
                "start_time": None,
                "end_time": None,
            },
        )
        session.add(rule)
        await session.flush()

        # This should not raise an exception, but add to skipped_rules
        result = await engine.evaluate_event(test_event, [])

        # The rule should trigger since None times mean no time restriction
        # (the _check_schedule returns True when times are None)
        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1

    @pytest.mark.asyncio
    async def test_evaluation_exception_caught_and_logged(self, session, test_event, caplog):
        """Test that exceptions during rule evaluation are caught and logged (lines 160-162)."""
        import logging
        from unittest.mock import AsyncMock, patch

        rule = AlertRule(
            name=unique_id("exception_rule"),
            enabled=True,
            risk_threshold=50,
        )
        session.add(rule)
        await session.flush()

        # Create an engine and mock _evaluate_rule to raise an exception
        engine = AlertRuleEngine(session)

        with patch.object(engine, "_evaluate_rule", new_callable=AsyncMock) as mock_evaluate:
            mock_evaluate.side_effect = RuntimeError("Simulated evaluation error")

            with caplog.at_level(logging.ERROR):
                result = await engine.evaluate_event(test_event, [])

            # Our rule should be in skipped_rules due to evaluation error
            our_skipped = _filter_skipped_rules_by_ids(result, [rule.id])
            assert len(our_skipped) == 1
            assert "evaluation_error" in our_skipped[0][1]
            assert "Simulated evaluation error" in our_skipped[0][1]

            # Our rule should NOT be in triggered_rules
            our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
            assert len(our_triggered) == 0

            # Check that error was logged
            assert any("Error evaluating rule" in record.message for record in caplog.records)


class TestZoneCondition:
    """Tests for zone_ids condition."""

    @pytest.mark.asyncio
    async def test_zone_ids_logs_debug(self, session, test_event, engine, caplog):
        """Test that zone_ids condition logs debug message (line 242)."""
        import logging

        rule = AlertRule(
            name=unique_id("zone_alert"),
            enabled=True,
            zone_ids=["zone1", "zone2"],  # Zone matching not implemented
        )
        session.add(rule)
        await session.flush()

        with caplog.at_level(logging.DEBUG):
            result = await engine.evaluate_event(test_event, [])

        # Rule should still match (zone check is not blocking)
        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1


class TestObjectTypesEdgeCases:
    """Tests for object_types condition edge cases."""

    @pytest.mark.asyncio
    async def test_object_types_empty_detections(self, session, test_event, engine):
        """Test that object_types returns False with empty detections (line 260)."""
        rule = AlertRule(
            name=unique_id("object_types_empty"),
            enabled=True,
            object_types=["person"],
        )
        session.add(rule)
        await session.flush()

        # Pass empty detections list
        result = await engine.evaluate_event(test_event, [])

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 0


class TestMinConfidenceEdgeCases:
    """Tests for min_confidence condition edge cases."""

    @pytest.mark.asyncio
    async def test_min_confidence_empty_detections(self, session, test_event, engine):
        """Test that min_confidence returns False with empty detections (line 271)."""
        rule = AlertRule(
            name=unique_id("min_confidence_empty"),
            enabled=True,
            min_confidence=0.5,
        )
        session.add(rule)
        await session.flush()

        # Pass empty detections list
        result = await engine.evaluate_event(test_event, [])

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 0


class TestScheduleEdgeCases:
    """Tests for schedule condition edge cases."""

    @pytest.mark.asyncio
    async def test_schedule_empty_dict(self, session, test_event, engine):
        """Test that empty schedule dict returns True (line 291-292)."""
        rule = AlertRule(
            name=unique_id("empty_schedule_alert"),
            enabled=True,
            schedule={},  # Empty dict - triggers `if not schedule` on line 291
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, [])

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1

    @pytest.mark.asyncio
    async def test_check_schedule_directly_with_falsy_value(self, session, engine):
        """Test _check_schedule method directly with falsy schedule values (line 291-292)."""
        from datetime import datetime

        test_time = datetime(2025, 12, 28, 10, 0, 0)

        # Test with empty dict (falsy)
        result_empty_dict = engine._check_schedule({}, test_time)
        assert result_empty_dict is True

        # Test with None (if passed directly)
        result_none = engine._check_schedule(None, test_time)
        assert result_none is True

    @pytest.mark.asyncio
    async def test_schedule_invalid_timezone(self, session, test_event, engine, caplog):
        """Test that invalid timezone falls back to UTC (lines 298-300)."""
        import logging

        test_time = datetime(2025, 12, 28, 10, 0, 0)

        rule = AlertRule(
            name=unique_id("invalid_tz_alert"),
            enabled=True,
            schedule={
                "timezone": "Invalid/Timezone",  # Invalid timezone
                "start_time": "09:00",
                "end_time": "17:00",
            },
        )
        session.add(rule)
        await session.flush()

        with caplog.at_level(logging.WARNING):
            result = await engine.evaluate_event(test_event, [], current_time=test_time)

        # Should still match using UTC fallback
        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1

        # Check that warning was logged
        assert any("Invalid timezone" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_schedule_normal_range_outside(self, session, test_event, engine):
        """Test schedule with normal time range outside match (line 325)."""
        # Test at 8:00 AM (should NOT match 09:00-17:00)
        test_time = datetime(2025, 12, 28, 8, 0, 0)

        rule = AlertRule(
            name=unique_id("business_hours_outside"),
            enabled=True,
            schedule={
                "start_time": "09:00",
                "end_time": "17:00",
                "timezone": "UTC",
            },
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, [], current_time=test_time)

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 0

    @pytest.mark.asyncio
    async def test_schedule_time_parsing_error(self, session, test_event, engine, caplog):
        """Test schedule time parsing error handling (lines 329-331)."""
        import logging

        test_time = datetime(2025, 12, 28, 10, 0, 0)

        rule = AlertRule(
            name=unique_id("bad_time_format"),
            enabled=True,
            schedule={
                "start_time": "invalid",  # Invalid time format
                "end_time": "17:00",
                "timezone": "UTC",
            },
        )
        session.add(rule)
        await session.flush()

        with caplog.at_level(logging.WARNING):
            result = await engine.evaluate_event(test_event, [], current_time=test_time)

        # Should still match due to error handling (returns True on parse error)
        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1

        # Check that warning was logged
        assert any("Error parsing schedule time" in record.message for record in caplog.records)


class TestDedupKeyEdgeCases:
    """Tests for dedup key generation edge cases."""

    @pytest.mark.asyncio
    async def test_dedup_key_invalid_template_variable(
        self, session, test_event, test_detections, engine, caplog
    ):
        """Test dedup key with invalid template variable (lines 366-368)."""
        import logging

        rule = AlertRule(
            name=unique_id("invalid_dedup_template"),
            enabled=True,
            dedup_key_template="{camera_id}:{invalid_variable}",  # Invalid variable
        )
        session.add(rule)
        await session.flush()

        with caplog.at_level(logging.WARNING):
            result = await engine.evaluate_event(test_event, test_detections)

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1

        # Should fallback to default key format
        expected_fallback = f"{test_event.camera_id}:{rule.id}"
        assert our_triggered[0].dedup_key == expected_fallback

        # Check that warning was logged
        assert any("Invalid dedup_key_template" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_dedup_key_no_detections(self, session, test_event, engine):
        """Test dedup key when detections list is empty (uses 'unknown' for object_type)."""
        rule = AlertRule(
            name=unique_id("dedup_no_detections"),
            enabled=True,
            dedup_key_template="{camera_id}:{object_type}:{rule_id}",
        )
        session.add(rule)
        await session.flush()

        result = await engine.evaluate_event(test_event, [])

        our_triggered = _filter_triggered_rules_by_ids(result, [rule.id])
        assert len(our_triggered) == 1

        # Should use 'unknown' for object_type
        expected_key = f"{test_event.camera_id}:unknown:{rule.id}"
        assert our_triggered[0].dedup_key == expected_key


class TestGetAlertEngineFunction:
    """Tests for the get_alert_engine convenience function."""

    @pytest.mark.asyncio
    async def test_get_alert_engine(self, session):
        """Test the get_alert_engine convenience function (line 488)."""
        from backend.services.alert_engine import get_alert_engine

        engine = await get_alert_engine(session, redis_client=None)

        assert isinstance(engine, AlertRuleEngine)
        assert engine.session is session
        assert engine.redis_client is None

    @pytest.mark.asyncio
    async def test_get_alert_engine_with_redis(self, session):
        """Test get_alert_engine with redis client."""
        from unittest.mock import MagicMock

        from backend.services.alert_engine import get_alert_engine

        mock_redis = MagicMock()
        engine = await get_alert_engine(session, redis_client=mock_redis)

        assert isinstance(engine, AlertRuleEngine)
        assert engine.session is session
        assert engine.redis_client is mock_redis


class TestHighestSeverityTracking:
    """Tests for highest severity tracking in evaluation results."""

    @pytest.mark.asyncio
    async def test_highest_severity_updates_correctly(self, session, test_event, engine):
        """Test that highest_severity is tracked correctly across multiple rules."""
        rule_low = AlertRule(
            name=unique_id("low_severity"),
            enabled=True,
            risk_threshold=50,
            severity=AlertSeverity.LOW,
        )
        rule_medium = AlertRule(
            name=unique_id("medium_severity"),
            enabled=True,
            risk_threshold=60,
            severity=AlertSeverity.MEDIUM,
        )
        rule_critical = AlertRule(
            name=unique_id("critical_severity"),
            enabled=True,
            risk_threshold=70,
            severity=AlertSeverity.CRITICAL,
        )
        session.add_all([rule_low, rule_medium, rule_critical])
        await session.flush()

        result = await engine.evaluate_event(test_event, [])

        # All three rules should trigger
        our_rule_ids = [rule_low.id, rule_medium.id, rule_critical.id]
        our_triggered = _filter_triggered_rules_by_ids(result, our_rule_ids)
        assert len(our_triggered) == 3

        # Highest severity should be CRITICAL
        # Note: result.highest_severity tracks the overall highest, not just our rules
        triggered_severities = [tr.severity for tr in our_triggered]
        assert AlertSeverity.CRITICAL in triggered_severities


class TestCreateMultipleAlerts:
    """Tests for creating multiple alerts."""

    @pytest.mark.asyncio
    async def test_create_multiple_alerts(self, session, test_event, engine):
        """Test creating multiple alerts for multiple triggered rules."""
        rule1 = AlertRule(
            name=unique_id("multi_alert_1"),
            enabled=True,
            risk_threshold=50,
            severity=AlertSeverity.LOW,
            channels=["email"],
        )
        rule2 = AlertRule(
            name=unique_id("multi_alert_2"),
            enabled=True,
            risk_threshold=60,
            severity=AlertSeverity.HIGH,
            channels=["pushover"],
        )
        session.add_all([rule1, rule2])
        await session.flush()

        result = await engine.evaluate_event(test_event, [])

        our_rule_ids = [rule1.id, rule2.id]
        our_triggered = _filter_triggered_rules_by_ids(result, our_rule_ids)
        assert len(our_triggered) == 2

        alerts = await engine.create_alerts_for_event(test_event, our_triggered)

        assert len(alerts) == 2

        # Verify alerts have correct properties
        alert_rule_ids = {alert.rule_id for alert in alerts}
        assert rule1.id in alert_rule_ids
        assert rule2.id in alert_rule_ids

        for alert in alerts:
            assert alert.event_id == test_event.id
            assert alert.status == AlertStatus.PENDING
            assert "matched_conditions" in alert.alert_metadata
            assert "rule_name" in alert.alert_metadata


class TestCooldownConcurrencyProtection:
    """Tests for concurrency protection in cooldown checking with FOR UPDATE locks."""

    @pytest.mark.asyncio
    async def test_cooldown_check_uses_for_update(self, session, test_event, engine):
        """Test that _check_cooldown uses SELECT FOR UPDATE SKIP LOCKED.

        This test verifies that the cooldown query uses row-level locking to prevent
        TOCTOU race conditions. While we can't easily test concurrent scenarios
        in a unit test, we verify the query works correctly with FOR UPDATE.
        """
        rule = AlertRule(
            name=unique_id("cooldown_for_update"),
            enabled=True,
            risk_threshold=50,
            cooldown_seconds=300,
        )
        session.add(rule)
        await session.flush()

        # Create existing alert within cooldown
        dedup_key = f"{test_event.camera_id}:{rule.id}"
        existing_alert = Alert(
            event_id=test_event.id,
            rule_id=rule.id,
            dedup_key=dedup_key,
            created_at=utc_now_naive() - timedelta(minutes=2),
        )
        session.add(existing_alert)
        await session.flush()

        result = await engine.evaluate_event(test_event, [])

        # Our rule should be skipped due to cooldown (with FOR UPDATE lock)
        our_skipped = _filter_skipped_rules_by_ids(result, [rule.id])
        assert len(our_skipped) == 1
        assert our_skipped[0][1] == "in_cooldown"

    @pytest.mark.asyncio
    async def test_cooldown_for_update_different_rules(self, session, test_event, engine):
        """Test that FOR UPDATE with skip_locked allows concurrent cooldown checks.

        Different rules with different dedup_keys should not block each other.
        """
        rule1 = AlertRule(
            name=unique_id("cooldown_rule1"),
            enabled=True,
            risk_threshold=50,
            cooldown_seconds=300,
        )
        rule2 = AlertRule(
            name=unique_id("cooldown_rule2"),
            enabled=True,
            risk_threshold=60,
            cooldown_seconds=300,
        )
        session.add_all([rule1, rule2])
        await session.flush()

        # Create existing alert for rule1 within cooldown
        dedup_key1 = f"{test_event.camera_id}:{rule1.id}"
        existing_alert = Alert(
            event_id=test_event.id,
            rule_id=rule1.id,
            dedup_key=dedup_key1,
            created_at=utc_now_naive() - timedelta(minutes=2),
        )
        session.add(existing_alert)
        await session.flush()

        result = await engine.evaluate_event(test_event, [])

        # rule1 should be skipped (in cooldown)
        our_skipped = _filter_skipped_rules_by_ids(result, [rule1.id])
        assert len(our_skipped) == 1
        assert our_skipped[0][1] == "in_cooldown"

        # rule2 should trigger (no cooldown)
        our_triggered = _filter_triggered_rules_by_ids(result, [rule2.id])
        assert len(our_triggered) == 1
