"""Unit tests for AlertRuleEngine class.

Tests use PostgreSQL via the isolated_db/session fixtures since models use
PostgreSQL-specific features (JSON columns, UUID primary keys).

Since the AlertRuleEngine fetches ALL enabled rules from the database,
tests use a TestableAlertRuleEngine subclass that only evaluates rules
passed explicitly to each test, ensuring test isolation.

Coverage includes:
- AlertRuleEngine initialization
- Rule evaluation logic with various conditions
- Severity threshold matching
- Camera/zone filtering
- Time-based rule constraints (schedule)
- Edge cases: empty rules, invalid conditions, None values
- Cooldown checking
- Alert creation
- Batch detection loading
- Rule testing against historical events
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from backend.models import (
    Alert,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    Camera,
    Detection,
    Event,
)
from backend.services.alert_engine import (
    SEVERITY_PRIORITY,
    AlertRuleEngine,
    EvaluationResult,
    TriggeredRule,
    get_alert_engine,
)
from backend.tests.conftest import unique_id


def _utcnow() -> datetime:
    """Return current UTC time as a timezone-aware datetime."""
    return datetime.now(UTC)


def _utcnow_naive() -> datetime:
    """Return current UTC time as a naive datetime for PostgreSQL compatibility."""
    return datetime.now(UTC).replace(tzinfo=None)


# =============================================================================
# Test-Isolated AlertRuleEngine
# =============================================================================


class IsolatedAlertRuleEngine(AlertRuleEngine):
    """AlertRuleEngine subclass for testing with explicit rule list.

    This subclass overrides _get_enabled_rules to return only the rules
    explicitly set via set_test_rules(), ensuring test isolation when
    the database contains rules from other tests.

    Note: Class name intentionally avoids 'Test' prefix to prevent pytest
    from trying to collect it as a test class.
    """

    def __init__(self, session, redis_client=None):
        super().__init__(session, redis_client)
        self._test_rules: list[AlertRule] = []

    def set_test_rules(self, rules: list[AlertRule]) -> None:
        """Set the rules to use for evaluation."""
        self._test_rules = rules

    async def _get_enabled_rules(self) -> list[AlertRule]:
        """Return only the rules set for this test."""
        return [r for r in self._test_rules if r.enabled]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_prefix():
    """Generate a unique prefix for this test run to ensure isolation."""
    return unique_id("engine")


@pytest.fixture
async def test_camera(session, test_prefix):
    """Create a test camera for use in engine tests."""
    camera_id = f"{test_prefix}_front_door"
    camera = Camera(
        id=camera_id,
        name="Front Door Camera",
        folder_path=f"/export/foscam/{camera_id}",
    )
    session.add(camera)
    await session.flush()
    return camera


@pytest.fixture
async def test_event(session, test_camera):
    """Create a test event for use in engine tests."""
    event = Event(
        batch_id=unique_id("batch"),
        camera_id=test_camera.id,
        started_at=_utcnow(),
        risk_score=80,
        risk_level="high",
        detection_ids=None,
    )
    session.add(event)
    await session.flush()
    return event


@pytest.fixture
async def test_detections(session, test_camera):
    """Create test detections for use in engine tests."""
    detections = [
        Detection(
            camera_id=test_camera.id,
            file_path="/path/to/image1.jpg",
            object_type="person",
            confidence=0.95,
            detected_at=_utcnow(),
        ),
        Detection(
            camera_id=test_camera.id,
            file_path="/path/to/image2.jpg",
            object_type="vehicle",
            confidence=0.85,
            detected_at=_utcnow(),
        ),
    ]
    for d in detections:
        session.add(d)
    await session.flush()
    return detections


@pytest.fixture
async def test_event_with_detections(session, test_camera, test_detections):
    """Create a test event with linked detection IDs."""
    detection_ids = [d.id for d in test_detections]
    event = Event(
        batch_id=unique_id("batch"),
        camera_id=test_camera.id,
        started_at=_utcnow(),
        risk_score=75,
        risk_level="high",
        detection_ids=json.dumps(detection_ids),
    )
    session.add(event)
    await session.flush()
    return event


@pytest.fixture
async def alert_engine(session):
    """Create an IsolatedAlertRuleEngine instance for isolated testing."""
    return IsolatedAlertRuleEngine(session, redis_client=None)


# =============================================================================
# Test Classes
# =============================================================================


class TestAlertRuleEngineInit:
    """Tests for AlertRuleEngine initialization."""

    def test_init_with_session_only(self, session):
        """Test initialization with session only."""
        engine = AlertRuleEngine(session)
        assert engine.session is session
        assert engine.redis_client is None

    def test_init_with_redis_client(self, session, mock_redis):
        """Test initialization with Redis client."""
        engine = AlertRuleEngine(session, redis_client=mock_redis)
        assert engine.session is session
        assert engine.redis_client is mock_redis

    @pytest.mark.asyncio
    async def test_get_alert_engine_factory(self, session):
        """Test the get_alert_engine convenience function."""
        engine = await get_alert_engine(session)
        assert isinstance(engine, AlertRuleEngine)
        assert engine.session is session

    @pytest.mark.asyncio
    async def test_get_alert_engine_with_redis(self, session, mock_redis):
        """Test get_alert_engine with Redis client."""
        engine = await get_alert_engine(session, redis_client=mock_redis)
        assert engine.redis_client is mock_redis


class TestTriggeredRule:
    """Tests for TriggeredRule dataclass."""

    def test_triggered_rule_defaults(self):
        """Test TriggeredRule with default values."""
        rule = AlertRule(name="Test Rule")
        triggered = TriggeredRule(rule=rule, severity=AlertSeverity.HIGH)

        assert triggered.rule is rule
        assert triggered.severity == AlertSeverity.HIGH
        assert triggered.matched_conditions == []
        assert triggered.dedup_key == ""

    def test_triggered_rule_with_conditions(self):
        """Test TriggeredRule with matched conditions."""
        rule = AlertRule(name="Test Rule")
        triggered = TriggeredRule(
            rule=rule,
            severity=AlertSeverity.CRITICAL,
            matched_conditions=["risk_score >= 80", "camera_id in ['front']"],
            dedup_key="front:rule123",
        )

        assert triggered.severity == AlertSeverity.CRITICAL
        assert len(triggered.matched_conditions) == 2
        assert triggered.dedup_key == "front:rule123"


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass."""

    def test_evaluation_result_defaults(self):
        """Test EvaluationResult with default values."""
        result = EvaluationResult()

        assert result.triggered_rules == []
        assert result.skipped_rules == []
        assert result.highest_severity is None
        assert result.has_triggers is False

    def test_evaluation_result_has_triggers(self):
        """Test has_triggers property."""
        rule = AlertRule(name="Test")
        triggered = TriggeredRule(rule=rule, severity=AlertSeverity.HIGH)

        result = EvaluationResult(
            triggered_rules=[triggered],
            highest_severity=AlertSeverity.HIGH,
        )

        assert result.has_triggers is True

    def test_evaluation_result_with_skipped_rules(self):
        """Test EvaluationResult with skipped rules."""
        rule = AlertRule(name="Skipped Rule")
        result = EvaluationResult(
            skipped_rules=[(rule, "in_cooldown")],
        )

        assert len(result.skipped_rules) == 1
        assert result.skipped_rules[0][1] == "in_cooldown"
        assert result.has_triggers is False


class TestSeverityPriority:
    """Tests for severity priority constants."""

    def test_severity_ordering(self):
        """Test that severity priorities are correctly ordered."""
        assert SEVERITY_PRIORITY[AlertSeverity.LOW] < SEVERITY_PRIORITY[AlertSeverity.MEDIUM]
        assert SEVERITY_PRIORITY[AlertSeverity.MEDIUM] < SEVERITY_PRIORITY[AlertSeverity.HIGH]
        assert SEVERITY_PRIORITY[AlertSeverity.HIGH] < SEVERITY_PRIORITY[AlertSeverity.CRITICAL]

    def test_all_severities_have_priority(self):
        """Test that all severities have a priority defined."""
        for severity in AlertSeverity:
            assert severity in SEVERITY_PRIORITY


class TestRuleEvaluationBasic:
    """Tests for basic rule evaluation logic."""

    @pytest.mark.asyncio
    async def test_evaluate_event_no_rules(self, session, alert_engine, test_event):
        """Test evaluation when no rules exist."""
        alert_engine.set_test_rules([])
        result = await alert_engine.evaluate_event(test_event)

        assert result.has_triggers is False
        assert result.triggered_rules == []
        assert result.highest_severity is None

    @pytest.mark.asyncio
    async def test_evaluate_event_rule_with_no_conditions(
        self, session, alert_engine, test_event, test_prefix
    ):
        """Test that a rule with no conditions always matches."""
        rule = AlertRule(
            name=f"No Conditions Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.LOW,
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=[])

        assert result.has_triggers is True
        assert len(result.triggered_rules) == 1
        assert "no_conditions" in result.triggered_rules[0].matched_conditions[0]

    @pytest.mark.asyncio
    async def test_evaluate_event_disabled_rule_ignored(
        self, session, alert_engine, test_event, test_prefix
    ):
        """Test that disabled rules are not evaluated."""
        rule = AlertRule(
            name=f"Disabled Rule {test_prefix}",
            enabled=False,  # Disabled
            severity=AlertSeverity.HIGH,
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event)

        assert result.has_triggers is False


class TestRiskThresholdCondition:
    """Tests for risk_threshold condition evaluation."""

    @pytest.mark.asyncio
    async def test_risk_threshold_matches(self, session, alert_engine, test_event, test_prefix):
        """Test rule matches when risk_score >= threshold."""
        # test_event has risk_score=80
        rule = AlertRule(
            name=f"Risk Threshold Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.HIGH,
            risk_threshold=70,
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event)

        assert result.has_triggers is True
        assert "risk_score >= 70" in result.triggered_rules[0].matched_conditions

    @pytest.mark.asyncio
    async def test_risk_threshold_exact_match(self, session, alert_engine, test_event, test_prefix):
        """Test rule matches when risk_score == threshold (boundary)."""
        # test_event has risk_score=80
        rule = AlertRule(
            name=f"Risk Threshold Exact {test_prefix}",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            risk_threshold=80,
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event)

        assert result.has_triggers is True

    @pytest.mark.asyncio
    async def test_risk_threshold_not_met(self, session, alert_engine, test_event, test_prefix):
        """Test rule does not match when risk_score < threshold."""
        # test_event has risk_score=80
        rule = AlertRule(
            name=f"High Threshold Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            risk_threshold=90,
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event)

        assert result.has_triggers is False

    @pytest.mark.asyncio
    async def test_risk_threshold_with_none_risk_score(
        self, session, alert_engine, test_camera, test_prefix
    ):
        """Test rule does not match when event has no risk_score."""
        event = Event(
            batch_id=unique_id("batch"),
            camera_id=test_camera.id,
            started_at=_utcnow(),
            risk_score=None,  # No risk score
        )
        session.add(event)
        await session.flush()

        rule = AlertRule(
            name=f"Risk Threshold None {test_prefix}",
            enabled=True,
            risk_threshold=50,
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(event)

        assert result.has_triggers is False


class TestCameraIdCondition:
    """Tests for camera_ids condition evaluation."""

    @pytest.mark.asyncio
    async def test_camera_id_matches(
        self, session, alert_engine, test_event, test_camera, test_prefix
    ):
        """Test rule matches when camera_id is in the list."""
        rule = AlertRule(
            name=f"Camera Filter Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            camera_ids=[test_camera.id, "other_camera"],
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event)

        assert result.has_triggers is True
        assert f"camera_id in {rule.camera_ids}" in result.triggered_rules[0].matched_conditions

    @pytest.mark.asyncio
    async def test_camera_id_not_in_list(self, session, alert_engine, test_event, test_prefix):
        """Test rule does not match when camera_id is not in the list."""
        rule = AlertRule(
            name=f"Other Cameras Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.HIGH,
            camera_ids=["backyard", "garage"],  # Different cameras
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event)

        assert result.has_triggers is False

    @pytest.mark.asyncio
    async def test_empty_camera_ids_matches_all(
        self, session, alert_engine, test_event, test_prefix
    ):
        """Test that empty camera_ids means all cameras match."""
        rule = AlertRule(
            name=f"All Cameras Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.LOW,
            camera_ids=[],  # Empty list
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event)

        # Empty list is falsy, so condition is not applied
        assert result.has_triggers is True


class TestObjectTypesCondition:
    """Tests for object_types condition evaluation."""

    @pytest.mark.asyncio
    async def test_object_type_matches(
        self, session, alert_engine, test_event, test_detections, test_prefix
    ):
        """Test rule matches when detection has matching object type."""
        rule = AlertRule(
            name=f"Person Detection Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.HIGH,
            object_types=["person"],
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=test_detections)

        assert result.has_triggers is True
        assert "object_type in ['person']" in result.triggered_rules[0].matched_conditions

    @pytest.mark.asyncio
    async def test_object_type_case_insensitive(
        self, session, alert_engine, test_event, test_detections, test_prefix
    ):
        """Test object type matching is case-insensitive."""
        rule = AlertRule(
            name=f"Case Insensitive Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            object_types=["PERSON", "Vehicle"],  # Different case
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=test_detections)

        assert result.has_triggers is True

    @pytest.mark.asyncio
    async def test_object_type_not_found(
        self, session, alert_engine, test_event, test_detections, test_prefix
    ):
        """Test rule does not match when no detection has matching object type."""
        rule = AlertRule(
            name=f"Animal Detection Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.LOW,
            object_types=["animal", "dog", "cat"],  # Not in detections
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=test_detections)

        assert result.has_triggers is False

    @pytest.mark.asyncio
    async def test_object_type_with_no_detections(
        self, session, alert_engine, test_event, test_prefix
    ):
        """Test rule with object_types does not match when no detections."""
        rule = AlertRule(
            name=f"Object Types No Detections {test_prefix}",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            object_types=["person"],
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=[])

        assert result.has_triggers is False


class TestMinConfidenceCondition:
    """Tests for min_confidence condition evaluation."""

    @pytest.mark.asyncio
    async def test_min_confidence_matches(
        self, session, alert_engine, test_event, test_detections, test_prefix
    ):
        """Test rule matches when detection confidence >= threshold."""
        # test_detections have confidence 0.95 and 0.85
        rule = AlertRule(
            name=f"High Confidence Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.HIGH,
            min_confidence=0.90,
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=test_detections)

        assert result.has_triggers is True
        assert "confidence >= 0.9" in result.triggered_rules[0].matched_conditions

    @pytest.mark.asyncio
    async def test_min_confidence_not_met(
        self, session, alert_engine, test_event, test_detections, test_prefix
    ):
        """Test rule does not match when no detection meets confidence threshold."""
        rule = AlertRule(
            name=f"Very High Confidence Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            min_confidence=0.99,  # Higher than any detection
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=test_detections)

        assert result.has_triggers is False

    @pytest.mark.asyncio
    async def test_min_confidence_with_none_confidence(
        self, session, alert_engine, test_event, test_camera, test_prefix
    ):
        """Test rule with detections that have None confidence."""
        detection = Detection(
            camera_id=test_camera.id,
            file_path="/path/to/image.jpg",
            object_type="unknown",
            confidence=None,  # No confidence
            detected_at=_utcnow(),
        )
        session.add(detection)
        await session.flush()

        rule = AlertRule(
            name=f"Confidence None Rule {test_prefix}",
            enabled=True,
            min_confidence=0.5,
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=[detection])

        assert result.has_triggers is False


class TestScheduleCondition:
    """Tests for schedule (time-based) condition evaluation."""

    @pytest.mark.asyncio
    async def test_schedule_within_time_range(self, session, alert_engine, test_event, test_prefix):
        """Test rule matches when current time is within schedule."""
        # Use a time that's definitely within 09:00-17:00 UTC
        current_time = datetime(2024, 1, 15, 12, 0, 0)  # Monday 12:00 UTC

        rule = AlertRule(
            name=f"Business Hours Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            schedule={
                "start_time": "09:00",
                "end_time": "17:00",
                "timezone": "UTC",
            },
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(
            test_event, detections=[], current_time=current_time
        )

        assert result.has_triggers is True
        assert "within_schedule" in result.triggered_rules[0].matched_conditions

    @pytest.mark.asyncio
    async def test_schedule_outside_time_range(
        self, session, alert_engine, test_event, test_prefix
    ):
        """Test rule does not match when current time is outside schedule."""
        # Use a time that's outside 09:00-17:00 UTC
        current_time = datetime(2024, 1, 15, 20, 0, 0)  # Monday 20:00 UTC

        rule = AlertRule(
            name=f"Business Hours Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            schedule={
                "start_time": "09:00",
                "end_time": "17:00",
                "timezone": "UTC",
            },
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(
            test_event, detections=[], current_time=current_time
        )

        assert result.has_triggers is False

    @pytest.mark.asyncio
    async def test_schedule_overnight_range(self, session, alert_engine, test_event, test_prefix):
        """Test schedule that spans midnight (e.g., 22:00-06:00)."""
        # Use a time at 23:00 which should be within 22:00-06:00
        current_time = datetime(2024, 1, 15, 23, 0, 0)  # Monday 23:00 UTC

        rule = AlertRule(
            name=f"Night Watch Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.HIGH,
            schedule={
                "start_time": "22:00",
                "end_time": "06:00",
                "timezone": "UTC",
            },
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(
            test_event, detections=[], current_time=current_time
        )

        assert result.has_triggers is True

    @pytest.mark.asyncio
    async def test_schedule_overnight_early_morning(
        self, session, alert_engine, test_event, test_prefix
    ):
        """Test overnight schedule matches in early morning."""
        # Use a time at 03:00 which should be within 22:00-06:00
        current_time = datetime(2024, 1, 15, 3, 0, 0)  # Monday 03:00 UTC

        rule = AlertRule(
            name=f"Night Watch Early {test_prefix}",
            enabled=True,
            severity=AlertSeverity.HIGH,
            schedule={
                "start_time": "22:00",
                "end_time": "06:00",
                "timezone": "UTC",
            },
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(
            test_event, detections=[], current_time=current_time
        )

        assert result.has_triggers is True

    @pytest.mark.asyncio
    async def test_schedule_day_filter(self, session, alert_engine, test_event, test_prefix):
        """Test schedule with specific days of week."""
        # Monday, January 15, 2024
        current_time = datetime(2024, 1, 15, 12, 0, 0)  # Monday

        rule = AlertRule(
            name=f"Weekday Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            schedule={
                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                "start_time": "09:00",
                "end_time": "17:00",
                "timezone": "UTC",
            },
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(
            test_event, detections=[], current_time=current_time
        )

        assert result.has_triggers is True

    @pytest.mark.asyncio
    async def test_schedule_wrong_day(self, session, alert_engine, test_event, test_prefix):
        """Test schedule does not match on wrong day of week."""
        # Saturday, January 20, 2024
        current_time = datetime(2024, 1, 20, 12, 0, 0)  # Saturday

        rule = AlertRule(
            name=f"Weekday Only Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            schedule={
                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                "start_time": "09:00",
                "end_time": "17:00",
                "timezone": "UTC",
            },
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(
            test_event, detections=[], current_time=current_time
        )

        assert result.has_triggers is False

    @pytest.mark.asyncio
    async def test_schedule_empty_means_always_active(
        self, session, alert_engine, test_event, test_prefix
    ):
        """Test that empty/null schedule means rule is always active."""
        rule = AlertRule(
            name=f"No Schedule Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.LOW,
            schedule=None,
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=[])

        assert result.has_triggers is True

    @pytest.mark.asyncio
    async def test_schedule_invalid_timezone_uses_utc(
        self, session, alert_engine, test_event, test_prefix
    ):
        """Test that invalid timezone falls back to UTC."""
        current_time = datetime(2024, 1, 15, 12, 0, 0)  # Monday 12:00

        rule = AlertRule(
            name=f"Invalid TZ Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.LOW,
            schedule={
                "start_time": "09:00",
                "end_time": "17:00",
                "timezone": "Invalid/Timezone",  # Invalid
            },
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(
            test_event, detections=[], current_time=current_time
        )

        # Should still work using UTC fallback
        assert result.has_triggers is True


class TestMultipleConditions:
    """Tests for rules with multiple conditions (AND logic)."""

    @pytest.mark.asyncio
    async def test_all_conditions_must_match(
        self, session, alert_engine, test_event, test_detections, test_camera, test_prefix
    ):
        """Test that all conditions must match for rule to trigger."""
        rule = AlertRule(
            name=f"Multi Condition Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            risk_threshold=70,  # Will match (event has 80)
            camera_ids=[test_camera.id],  # Will match
            object_types=["person"],  # Will match
            min_confidence=0.90,  # Will match (0.95 detection)
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=test_detections)

        assert result.has_triggers is True
        assert len(result.triggered_rules[0].matched_conditions) == 4

    @pytest.mark.asyncio
    async def test_one_condition_fails_rule_not_triggered(
        self, session, alert_engine, test_event, test_detections, test_prefix
    ):
        """Test that if any condition fails, rule does not trigger."""
        rule = AlertRule(
            name=f"Multi Condition Fail Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            risk_threshold=70,  # Will match
            camera_ids=["other_camera"],  # Will NOT match
            object_types=["person"],  # Will match
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=test_detections)

        assert result.has_triggers is False


class TestMultipleRules:
    """Tests for evaluating multiple rules."""

    @pytest.mark.asyncio
    async def test_multiple_rules_can_trigger(
        self, session, alert_engine, test_event, test_detections, test_prefix
    ):
        """Test that multiple rules can trigger for same event."""
        rule1 = AlertRule(
            name=f"Low Threshold Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.LOW,
            risk_threshold=50,
        )
        rule2 = AlertRule(
            name=f"Person Alert Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.HIGH,
            object_types=["person"],
        )
        session.add(rule1)
        session.add(rule2)
        await session.flush()

        alert_engine.set_test_rules([rule1, rule2])
        result = await alert_engine.evaluate_event(test_event, detections=test_detections)

        assert len(result.triggered_rules) == 2

    @pytest.mark.asyncio
    async def test_triggered_rules_sorted_by_severity(
        self, session, alert_engine, test_event, test_prefix
    ):
        """Test that triggered rules are sorted by severity (highest first)."""
        rule_low = AlertRule(
            name=f"Low Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.LOW,
        )
        rule_critical = AlertRule(
            name=f"Critical Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
        )
        rule_medium = AlertRule(
            name=f"Medium Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
        )
        session.add(rule_low)
        session.add(rule_critical)
        session.add(rule_medium)
        await session.flush()

        alert_engine.set_test_rules([rule_low, rule_critical, rule_medium])
        result = await alert_engine.evaluate_event(test_event, detections=[])

        assert len(result.triggered_rules) == 3
        assert result.triggered_rules[0].severity == AlertSeverity.CRITICAL
        assert result.triggered_rules[1].severity == AlertSeverity.MEDIUM
        assert result.triggered_rules[2].severity == AlertSeverity.LOW

    @pytest.mark.asyncio
    async def test_highest_severity_tracked(self, session, alert_engine, test_event, test_prefix):
        """Test that highest_severity is correctly tracked."""
        rule1 = AlertRule(
            name=f"Medium Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
        )
        rule2 = AlertRule(
            name=f"High Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.HIGH,
        )
        session.add(rule1)
        session.add(rule2)
        await session.flush()

        alert_engine.set_test_rules([rule1, rule2])
        result = await alert_engine.evaluate_event(test_event, detections=[])

        assert result.highest_severity == AlertSeverity.HIGH


class TestCooldownBehavior:
    """Tests for cooldown checking."""

    @pytest.mark.asyncio
    async def test_rule_in_cooldown_skipped(self, session, alert_engine, test_event, test_prefix):
        """Test that rule in cooldown is skipped."""
        rule = AlertRule(
            name=f"Cooldown Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.HIGH,
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
        )
        session.add(rule)
        await session.flush()

        # Create existing alert within cooldown
        existing_alert = Alert(
            event_id=test_event.id,
            rule_id=rule.id,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            dedup_key=f"{test_event.camera_id}:{rule.id}",
            created_at=_utcnow_naive() - timedelta(minutes=2),  # 2 minutes ago
        )
        session.add(existing_alert)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=[])

        assert result.has_triggers is False
        assert len(result.skipped_rules) == 1
        assert result.skipped_rules[0][1] == "in_cooldown"

    @pytest.mark.asyncio
    async def test_rule_outside_cooldown_triggers(
        self, session, alert_engine, test_event, test_prefix
    ):
        """Test that rule outside cooldown triggers."""
        rule = AlertRule(
            name=f"Cooldown Expired Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.HIGH,
            cooldown_seconds=60,  # 1 minute cooldown
            dedup_key_template="{camera_id}:{rule_id}",
        )
        session.add(rule)
        await session.flush()

        # Create old alert outside cooldown
        old_alert = Alert(
            event_id=test_event.id,
            rule_id=rule.id,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            dedup_key=f"{test_event.camera_id}:{rule.id}",
            created_at=_utcnow_naive() - timedelta(minutes=5),  # 5 minutes ago
        )
        session.add(old_alert)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=[])

        assert result.has_triggers is True


class TestDedupKeyBuilding:
    """Tests for dedup key template building."""

    @pytest.mark.asyncio
    async def test_dedup_key_default_template(self, session, alert_engine, test_event, test_prefix):
        """Test default dedup key template."""
        rule = AlertRule(
            name=f"Default Dedup Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            # Uses default: "{camera_id}:{rule_id}"
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=[])

        expected_key = f"{test_event.camera_id}:{rule.id}"
        assert result.triggered_rules[0].dedup_key == expected_key

    @pytest.mark.asyncio
    async def test_dedup_key_with_object_type(
        self, session, alert_engine, test_event, test_detections, test_prefix
    ):
        """Test dedup key with object_type variable."""
        rule = AlertRule(
            name=f"Object Type Dedup Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            dedup_key_template="{camera_id}:{object_type}:{rule_id}",
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=test_detections)

        # First detection is "person"
        expected_key = f"{test_event.camera_id}:person:{rule.id}"
        assert result.triggered_rules[0].dedup_key == expected_key

    @pytest.mark.asyncio
    async def test_dedup_key_unknown_object_type(
        self, session, alert_engine, test_event, test_prefix
    ):
        """Test dedup key with no detections uses 'unknown' for object_type."""
        rule = AlertRule(
            name=f"Unknown Object Dedup Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            dedup_key_template="{camera_id}:{object_type}",
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=[])

        expected_key = f"{test_event.camera_id}:unknown"
        assert result.triggered_rules[0].dedup_key == expected_key


class TestLoadDetections:
    """Tests for loading detections from database."""

    @pytest.mark.asyncio
    async def test_load_detections_from_event(
        self, session, alert_engine, test_event_with_detections, test_detections, test_prefix
    ):
        """Test that detections are loaded from event.detection_ids."""
        rule = AlertRule(
            name=f"Auto Load Detections Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            object_types=["person"],  # Requires detections to match
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        # Don't pass detections - should load from event.detection_ids
        result = await alert_engine.evaluate_event(test_event_with_detections)

        assert result.has_triggers is True

    @pytest.mark.asyncio
    async def test_load_detections_empty_detection_ids(
        self, session, alert_engine, test_event, test_prefix
    ):
        """Test handling of empty detection_ids."""
        # test_event has detection_ids=None
        rule = AlertRule(
            name=f"Empty Detections Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.LOW,
            object_types=["person"],
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event)

        # Should not match because no detections
        assert result.has_triggers is False

    @pytest.mark.asyncio
    async def test_load_detections_invalid_json(
        self, session, alert_engine, test_camera, test_prefix
    ):
        """Test handling of invalid JSON in detection_ids."""
        event = Event(
            batch_id=unique_id("batch"),
            camera_id=test_camera.id,
            started_at=_utcnow(),
            risk_score=50,
            detection_ids="not valid json",
        )
        session.add(event)
        await session.flush()

        rule = AlertRule(
            name=f"Invalid JSON Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.LOW,
            object_types=["person"],
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(event)

        # Should not crash, just return empty detections
        assert result.has_triggers is False


class TestCreateAlertsForEvent:
    """Tests for creating alert records."""

    @pytest.mark.asyncio
    async def test_create_alerts_for_triggered_rules(
        self, session, alert_engine, test_event, test_prefix
    ):
        """Test creating alerts for triggered rules."""
        rule = AlertRule(
            name=f"Create Alert Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.HIGH,
            channels=["pushover", "email"],
        )
        session.add(rule)
        await session.flush()

        triggered = TriggeredRule(
            rule=rule,
            severity=AlertSeverity.HIGH,
            matched_conditions=["no_conditions"],
            dedup_key=f"{test_event.camera_id}:{rule.id}",
        )

        alerts = await alert_engine.create_alerts_for_event(test_event, [triggered])

        assert len(alerts) == 1
        assert alerts[0].event_id == test_event.id
        assert alerts[0].rule_id == rule.id
        assert alerts[0].severity == AlertSeverity.HIGH
        assert alerts[0].status == AlertStatus.PENDING
        assert alerts[0].channels == ["pushover", "email"]
        assert alerts[0].alert_metadata["rule_name"] == rule.name

    @pytest.mark.asyncio
    async def test_create_alerts_multiple_rules(
        self, session, alert_engine, test_event, test_prefix
    ):
        """Test creating alerts for multiple triggered rules."""
        rule1 = AlertRule(
            name=f"Rule 1 {test_prefix}",
            enabled=True,
            severity=AlertSeverity.LOW,
        )
        rule2 = AlertRule(
            name=f"Rule 2 {test_prefix}",
            enabled=True,
            severity=AlertSeverity.HIGH,
        )
        session.add(rule1)
        session.add(rule2)
        await session.flush()

        triggered_rules = [
            TriggeredRule(rule=rule1, severity=AlertSeverity.LOW, dedup_key="key1"),
            TriggeredRule(rule=rule2, severity=AlertSeverity.HIGH, dedup_key="key2"),
        ]

        alerts = await alert_engine.create_alerts_for_event(test_event, triggered_rules)

        assert len(alerts) == 2


class TestBatchLoadDetections:
    """Tests for batch detection loading."""

    @pytest.mark.asyncio
    async def test_batch_load_detections_multiple_events(
        self, session, alert_engine, test_camera, test_prefix
    ):
        """Test batch loading detections for multiple events."""
        # Create detections
        detections = []
        for i in range(4):
            d = Detection(
                camera_id=test_camera.id,
                file_path=f"/path/to/image{i}.jpg",
                object_type="person" if i % 2 == 0 else "vehicle",
                confidence=0.9,
                detected_at=_utcnow(),
            )
            session.add(d)
            detections.append(d)
        await session.flush()

        # Create events with different detection sets
        event1 = Event(
            batch_id=unique_id("batch"),
            camera_id=test_camera.id,
            started_at=_utcnow(),
            risk_score=50,
            detection_ids=json.dumps([detections[0].id, detections[1].id]),
        )
        event2 = Event(
            batch_id=unique_id("batch"),
            camera_id=test_camera.id,
            started_at=_utcnow(),
            risk_score=60,
            detection_ids=json.dumps([detections[2].id, detections[3].id]),
        )
        session.add(event1)
        session.add(event2)
        await session.flush()

        # Batch load
        result = await alert_engine._batch_load_detections_for_events([event1, event2])

        assert event1.id in result
        assert event2.id in result
        assert len(result[event1.id]) == 2
        assert len(result[event2.id]) == 2

    @pytest.mark.asyncio
    async def test_batch_load_detections_empty_events(self, session, alert_engine):
        """Test batch loading with empty event list."""
        result = await alert_engine._batch_load_detections_for_events([])
        assert result == {}


class TestTestRuleAgainstEvents:
    """Tests for testing rules against historical events."""

    @pytest.mark.asyncio
    async def test_test_rule_against_events(self, session, alert_engine, test_camera, test_prefix):
        """Test testing a rule against multiple events."""
        # Create events with different risk scores
        events = []
        for risk in [40, 60, 80]:
            event = Event(
                batch_id=unique_id("batch"),
                camera_id=test_camera.id,
                started_at=_utcnow(),
                risk_score=risk,
            )
            session.add(event)
            events.append(event)
        await session.flush()

        rule = AlertRule(
            name=f"Test Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.HIGH,
            risk_threshold=50,
        )
        session.add(rule)
        await session.flush()

        results = await alert_engine.test_rule_against_events(rule, events)

        assert len(results) == 3
        assert results[0]["matches"] is False  # risk_score=40
        assert results[1]["matches"] is True  # risk_score=60
        assert results[2]["matches"] is True  # risk_score=80


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_rule_evaluation_error_handled(
        self, session, alert_engine, test_event, test_prefix
    ):
        """Test that rule evaluation errors are handled gracefully."""
        # Create a rule that will cause an error during evaluation
        rule = AlertRule(
            name=f"Error Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.HIGH,
            schedule={"invalid_key": "invalid"},  # May cause issues
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        # Should not raise, just skip the rule
        result = await alert_engine.evaluate_event(test_event, detections=[])

        # Depending on implementation, may or may not trigger
        # The important thing is it doesn't crash
        assert isinstance(result, EvaluationResult)

    @pytest.mark.asyncio
    async def test_detection_with_none_object_type(
        self, session, alert_engine, test_event, test_camera, test_prefix
    ):
        """Test handling of detections with None object_type."""
        detection = Detection(
            camera_id=test_camera.id,
            file_path="/path/to/image.jpg",
            object_type=None,  # No object type
            confidence=0.9,
            detected_at=_utcnow(),
        )
        session.add(detection)
        await session.flush()

        rule = AlertRule(
            name=f"Object Type Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.LOW,
            object_types=["person"],
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=[detection])

        # Should not crash, just not match
        assert result.has_triggers is False

    @pytest.mark.asyncio
    async def test_zone_ids_logged_but_not_implemented(
        self, session, alert_engine, test_event, test_prefix
    ):
        """Test that zone_ids condition is acknowledged but not blocking."""
        rule = AlertRule(
            name=f"Zone Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            zone_ids=["entry_zone", "driveway"],  # Zone filtering specified
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=[])

        # Zone matching is not implemented yet, so rule should still match
        # (zone condition is logged but doesn't fail the rule)
        assert result.has_triggers is True

    @pytest.mark.asyncio
    async def test_invalid_dedup_key_template_variable(
        self, session, alert_engine, test_event, test_prefix
    ):
        """Test handling of invalid variables in dedup_key_template."""
        rule = AlertRule(
            name=f"Invalid Template Rule {test_prefix}",
            enabled=True,
            severity=AlertSeverity.LOW,
            dedup_key_template="{camera_id}:{invalid_var}",  # Invalid variable
        )
        session.add(rule)
        await session.flush()

        alert_engine.set_test_rules([rule])
        result = await alert_engine.evaluate_event(test_event, detections=[])

        # Should fall back to default key format
        assert result.has_triggers is True
        assert result.triggered_rules[0].dedup_key == f"{test_event.camera_id}:{rule.id}"
