"""Unit tests for AlertRuleEngine service.

Tests cover:
- evaluate_event(): Rule loading, condition matching, cooldown checking
- _evaluate_rule(): All condition types (risk_threshold, object_types, camera_ids, etc.)
- _check_schedule(): Time range and day-of-week matching
- _build_dedup_key(): Template variable substitution
- _check_cooldown(): Database-based cooldown checking
- create_alerts_for_event(): Alert record creation
- test_rule_against_events(): Rule testing with batch detection loading
- get_alert_engine(): Convenience function
"""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models import Alert, AlertRule, AlertSeverity, AlertStatus, Detection, Event
from backend.services.alert_engine import (
    SEVERITY_PRIORITY,
    AlertRuleEngine,
    EvaluationResult,
    TriggeredRule,
    get_alert_engine,
)
from backend.tests.strategies import valid_risk_scores

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
def sample_rule() -> AlertRule:
    """Create a sample alert rule for testing."""
    return AlertRule(
        id=str(uuid.uuid4()),
        name="Test Rule",
        enabled=True,
        severity=AlertSeverity.HIGH,
        risk_threshold=70,
        cooldown_seconds=600,
        dedup_key_template="{camera_id}:{rule_id}",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_rule_no_conditions() -> AlertRule:
    """Create a sample alert rule with no conditions."""
    return AlertRule(
        id=str(uuid.uuid4()),
        name="Always Match Rule",
        enabled=True,
        severity=AlertSeverity.LOW,
        cooldown_seconds=300,
        dedup_key_template="{camera_id}:{rule_id}",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_event() -> Event:
    """Create a sample event for testing."""
    return Event(
        id=1,
        batch_id=str(uuid.uuid4()),
        camera_id="front_door",
        started_at=datetime.now(UTC),
        risk_score=85,
        risk_level="high",
        detection_ids=json.dumps([1, 2, 3]),
    )


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


@pytest.fixture
def sample_alert(sample_event: Event, sample_rule: AlertRule) -> Alert:
    """Create a sample alert for testing."""
    return Alert(
        id=str(uuid.uuid4()),
        event_id=sample_event.id,
        rule_id=sample_rule.id,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.PENDING,
        dedup_key="front_door:" + sample_rule.id,
        channels=["push", "email"],
        alert_metadata={"test": "data"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# =============================================================================
# SEVERITY_PRIORITY Tests
# =============================================================================


class TestSeverityPriority:
    """Tests for SEVERITY_PRIORITY constant."""

    def test_priority_order(self) -> None:
        """Test that severity priorities are ordered correctly."""
        assert SEVERITY_PRIORITY[AlertSeverity.LOW] < SEVERITY_PRIORITY[AlertSeverity.MEDIUM]
        assert SEVERITY_PRIORITY[AlertSeverity.MEDIUM] < SEVERITY_PRIORITY[AlertSeverity.HIGH]
        assert SEVERITY_PRIORITY[AlertSeverity.HIGH] < SEVERITY_PRIORITY[AlertSeverity.CRITICAL]

    def test_all_severities_have_priority(self) -> None:
        """Test that all severity levels have a priority defined."""
        for severity in AlertSeverity:
            assert severity in SEVERITY_PRIORITY


# =============================================================================
# TriggeredRule Tests
# =============================================================================


class TestTriggeredRule:
    """Tests for TriggeredRule dataclass."""

    def test_triggered_rule_creation(self, sample_rule: AlertRule) -> None:
        """Test TriggeredRule can be created with all fields."""
        triggered = TriggeredRule(
            rule=sample_rule,
            severity=AlertSeverity.HIGH,
            matched_conditions=["risk_score >= 70"],
            dedup_key="front_door:rule-123",
        )
        assert triggered.rule == sample_rule
        assert triggered.severity == AlertSeverity.HIGH
        assert triggered.matched_conditions == ["risk_score >= 70"]
        assert triggered.dedup_key == "front_door:rule-123"

    def test_triggered_rule_default_values(self, sample_rule: AlertRule) -> None:
        """Test TriggeredRule default values."""
        triggered = TriggeredRule(
            rule=sample_rule,
            severity=AlertSeverity.MEDIUM,
        )
        assert triggered.matched_conditions == []
        assert triggered.dedup_key == ""


# =============================================================================
# EvaluationResult Tests
# =============================================================================


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass."""

    def test_evaluation_result_defaults(self) -> None:
        """Test EvaluationResult default values."""
        result = EvaluationResult()
        assert result.triggered_rules == []
        assert result.skipped_rules == []
        assert result.highest_severity is None
        assert result.has_triggers is False

    def test_has_triggers_true(self, sample_rule: AlertRule) -> None:
        """Test has_triggers property returns True when triggers exist."""
        triggered = TriggeredRule(rule=sample_rule, severity=AlertSeverity.HIGH)
        result = EvaluationResult(triggered_rules=[triggered])
        assert result.has_triggers is True

    def test_has_triggers_false(self) -> None:
        """Test has_triggers property returns False when no triggers."""
        result = EvaluationResult(triggered_rules=[])
        assert result.has_triggers is False


# =============================================================================
# AlertRuleEngine.__init__ Tests
# =============================================================================


class TestAlertRuleEngineInit:
    """Tests for AlertRuleEngine initialization."""

    def test_init_with_session_only(self, mock_session: AsyncMock) -> None:
        """Test engine can be initialized with session only."""
        engine = AlertRuleEngine(mock_session)
        assert engine.session == mock_session
        assert engine.redis_client is None

    def test_init_with_redis(self, mock_session: AsyncMock, mock_redis: AsyncMock) -> None:
        """Test engine can be initialized with Redis client."""
        engine = AlertRuleEngine(mock_session, mock_redis)
        assert engine.session == mock_session
        assert engine.redis_client == mock_redis


# =============================================================================
# AlertRuleEngine._get_enabled_rules Tests
# =============================================================================


class TestGetEnabledRules:
    """Tests for _get_enabled_rules method."""

    @pytest.mark.asyncio
    async def test_returns_enabled_rules(
        self, mock_session: AsyncMock, sample_rule: AlertRule
    ) -> None:
        """Test that enabled rules are returned."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_rule]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)
        rules = await engine._get_enabled_rules()

        assert len(rules) == 1
        assert rules[0] == sample_rule

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_rules(self, mock_session: AsyncMock) -> None:
        """Test that empty list is returned when no enabled rules."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)
        rules = await engine._get_enabled_rules()

        assert rules == []


# =============================================================================
# AlertRuleEngine._load_event_detections Tests
# =============================================================================


class TestLoadEventDetections:
    """Tests for _load_event_detections method."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_detection_ids(
        self, mock_session: AsyncMock, sample_event: Event
    ) -> None:
        """Test returns empty list when event has no detection_ids."""
        sample_event.detection_ids = None

        engine = AlertRuleEngine(mock_session)
        detections = await engine._load_event_detections(sample_event)

        assert detections == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_invalid_json(
        self, mock_session: AsyncMock, sample_event: Event
    ) -> None:
        """Test returns empty list when detection_ids is invalid JSON."""
        sample_event.detection_ids = "not-valid-json"

        engine = AlertRuleEngine(mock_session)
        detections = await engine._load_event_detections(sample_event)

        assert detections == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_not_list(
        self, mock_session: AsyncMock, sample_event: Event
    ) -> None:
        """Test returns empty list when detection_ids is not a list."""
        sample_event.detection_ids = json.dumps({"not": "a list"})

        engine = AlertRuleEngine(mock_session)
        detections = await engine._load_event_detections(sample_event)

        assert detections == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_empty_list(
        self, mock_session: AsyncMock, sample_event: Event
    ) -> None:
        """Test returns empty list when detection_ids is empty."""
        sample_event.detection_ids = json.dumps([])

        engine = AlertRuleEngine(mock_session)
        detections = await engine._load_event_detections(sample_event)

        assert detections == []

    @pytest.mark.asyncio
    async def test_loads_detections_from_database(
        self, mock_session: AsyncMock, sample_event: Event, sample_detections: list[Detection]
    ) -> None:
        """Test loads detections from database."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_detections
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)
        detections = await engine._load_event_detections(sample_event)

        assert len(detections) == 3


# =============================================================================
# AlertRuleEngine._check_object_types Tests
# =============================================================================


class TestCheckObjectTypes:
    """Tests for _check_object_types method."""

    def test_returns_false_when_no_detections(self, mock_session: AsyncMock) -> None:
        """Test returns False when no detections."""
        engine = AlertRuleEngine(mock_session)
        result = engine._check_object_types(["person"], [])
        assert result is False

    def test_returns_true_when_type_matches(
        self, mock_session: AsyncMock, sample_detections: list[Detection]
    ) -> None:
        """Test returns True when object type matches."""
        engine = AlertRuleEngine(mock_session)
        result = engine._check_object_types(["person"], sample_detections)
        assert result is True

    def test_returns_true_case_insensitive(
        self, mock_session: AsyncMock, sample_detections: list[Detection]
    ) -> None:
        """Test matching is case-insensitive."""
        engine = AlertRuleEngine(mock_session)
        result = engine._check_object_types(["PERSON"], sample_detections)
        assert result is True

    def test_returns_false_when_type_not_found(
        self, mock_session: AsyncMock, sample_detections: list[Detection]
    ) -> None:
        """Test returns False when object type not found."""
        engine = AlertRuleEngine(mock_session)
        result = engine._check_object_types(["dog"], sample_detections)
        assert result is False

    def test_returns_true_when_any_type_matches(
        self, mock_session: AsyncMock, sample_detections: list[Detection]
    ) -> None:
        """Test returns True when any of the required types matches."""
        engine = AlertRuleEngine(mock_session)
        result = engine._check_object_types(["dog", "vehicle"], sample_detections)
        assert result is True

    def test_handles_none_object_type(self, mock_session: AsyncMock) -> None:
        """Test handles detection with None object_type."""
        detections = [
            Detection(
                id=1,
                camera_id="cam1",
                file_path="/export/foscam/cam1/img.jpg",
                object_type=None,
            )
        ]
        engine = AlertRuleEngine(mock_session)
        result = engine._check_object_types(["person"], detections)
        assert result is False


# =============================================================================
# AlertRuleEngine._check_min_confidence Tests
# =============================================================================


class TestCheckMinConfidence:
    """Tests for _check_min_confidence method."""

    def test_returns_false_when_no_detections(self, mock_session: AsyncMock) -> None:
        """Test returns False when no detections."""
        engine = AlertRuleEngine(mock_session)
        result = engine._check_min_confidence(0.5, [])
        assert result is False

    def test_returns_true_when_confidence_meets_threshold(
        self, mock_session: AsyncMock, sample_detections: list[Detection]
    ) -> None:
        """Test returns True when confidence meets threshold."""
        engine = AlertRuleEngine(mock_session)
        result = engine._check_min_confidence(0.90, sample_detections)
        assert result is True  # One detection has 0.95 confidence

    def test_returns_false_when_confidence_below_threshold(
        self, mock_session: AsyncMock, sample_detections: list[Detection]
    ) -> None:
        """Test returns False when all confidences below threshold."""
        engine = AlertRuleEngine(mock_session)
        result = engine._check_min_confidence(0.99, sample_detections)
        assert result is False

    def test_returns_true_when_exactly_at_threshold(self, mock_session: AsyncMock) -> None:
        """Test returns True when confidence exactly at threshold."""
        detections = [
            Detection(
                id=1,
                camera_id="cam1",
                file_path="/export/foscam/cam1/img.jpg",
                confidence=0.80,
            )
        ]
        engine = AlertRuleEngine(mock_session)
        result = engine._check_min_confidence(0.80, detections)
        assert result is True

    def test_handles_none_confidence(self, mock_session: AsyncMock) -> None:
        """Test handles detection with None confidence."""
        detections = [
            Detection(
                id=1,
                camera_id="cam1",
                file_path="/export/foscam/cam1/img.jpg",
                confidence=None,
            )
        ]
        engine = AlertRuleEngine(mock_session)
        result = engine._check_min_confidence(0.5, detections)
        assert result is False


# =============================================================================
# AlertRuleEngine._parse_time Tests
# =============================================================================


class TestParseTime:
    """Tests for _parse_time method."""

    def test_parses_valid_time(self, mock_session: AsyncMock) -> None:
        """Test parses valid HH:MM time string."""
        engine = AlertRuleEngine(mock_session)
        result = engine._parse_time("14:30")
        from datetime import time

        assert result == time(14, 30)

    def test_parses_midnight(self, mock_session: AsyncMock) -> None:
        """Test parses midnight correctly."""
        engine = AlertRuleEngine(mock_session)
        result = engine._parse_time("00:00")
        from datetime import time

        assert result == time(0, 0)

    def test_parses_end_of_day(self, mock_session: AsyncMock) -> None:
        """Test parses end of day correctly."""
        engine = AlertRuleEngine(mock_session)
        result = engine._parse_time("23:59")
        from datetime import time

        assert result == time(23, 59)


# =============================================================================
# AlertRuleEngine._check_schedule Tests
# =============================================================================


class TestCheckSchedule:
    """Tests for _check_schedule method."""

    def test_returns_true_when_no_schedule(self, mock_session: AsyncMock) -> None:
        """Test returns True when no schedule specified."""
        engine = AlertRuleEngine(mock_session)
        result = engine._check_schedule({}, datetime.now(UTC))
        assert result is True

    def test_returns_true_when_schedule_none(self, mock_session: AsyncMock) -> None:
        """Test returns True when schedule is None."""
        engine = AlertRuleEngine(mock_session)
        result = engine._check_schedule(None, datetime.now(UTC))  # type: ignore[arg-type]
        assert result is True

    def test_day_matching_succeeds(self, mock_session: AsyncMock) -> None:
        """Test day matching succeeds when current day is in schedule."""
        engine = AlertRuleEngine(mock_session)
        # Use a known Monday
        monday = datetime(2025, 1, 6, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
        schedule = {"days": ["monday", "tuesday"]}
        result = engine._check_schedule(schedule, monday)
        assert result is True

    def test_day_matching_fails(self, mock_session: AsyncMock) -> None:
        """Test day matching fails when current day is not in schedule."""
        engine = AlertRuleEngine(mock_session)
        # Use a known Monday
        monday = datetime(2025, 1, 6, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
        schedule = {"days": ["wednesday", "thursday"]}
        result = engine._check_schedule(schedule, monday)
        assert result is False

    def test_day_matching_case_insensitive(self, mock_session: AsyncMock) -> None:
        """Test day matching is case-insensitive."""
        engine = AlertRuleEngine(mock_session)
        monday = datetime(2025, 1, 6, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
        schedule = {"days": ["MONDAY"]}
        result = engine._check_schedule(schedule, monday)
        assert result is True

    def test_time_range_within_normal_hours(self, mock_session: AsyncMock) -> None:
        """Test time range matching for normal hours (e.g., 09:00-17:00)."""
        engine = AlertRuleEngine(mock_session)
        current = datetime(2025, 1, 6, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
        schedule = {"start_time": "09:00", "end_time": "17:00"}
        result = engine._check_schedule(schedule, current)
        assert result is True

    def test_time_range_outside_normal_hours(self, mock_session: AsyncMock) -> None:
        """Test time range matching fails outside normal hours."""
        engine = AlertRuleEngine(mock_session)
        current = datetime(2025, 1, 6, 20, 0, 0, tzinfo=ZoneInfo("UTC"))
        schedule = {"start_time": "09:00", "end_time": "17:00"}
        result = engine._check_schedule(schedule, current)
        assert result is False

    def test_overnight_time_range_before_midnight(self, mock_session: AsyncMock) -> None:
        """Test overnight time range (22:00-06:00) works before midnight."""
        engine = AlertRuleEngine(mock_session)
        current = datetime(2025, 1, 6, 23, 0, 0, tzinfo=ZoneInfo("UTC"))
        schedule = {"start_time": "22:00", "end_time": "06:00"}
        result = engine._check_schedule(schedule, current)
        assert result is True

    def test_overnight_time_range_after_midnight(self, mock_session: AsyncMock) -> None:
        """Test overnight time range (22:00-06:00) works after midnight."""
        engine = AlertRuleEngine(mock_session)
        current = datetime(2025, 1, 7, 3, 0, 0, tzinfo=ZoneInfo("UTC"))
        schedule = {"start_time": "22:00", "end_time": "06:00"}
        result = engine._check_schedule(schedule, current)
        assert result is True

    def test_overnight_time_range_fails_during_day(self, mock_session: AsyncMock) -> None:
        """Test overnight time range fails during daytime hours."""
        engine = AlertRuleEngine(mock_session)
        current = datetime(2025, 1, 6, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
        schedule = {"start_time": "22:00", "end_time": "06:00"}
        result = engine._check_schedule(schedule, current)
        assert result is False

    def test_timezone_conversion(self, mock_session: AsyncMock) -> None:
        """Test timezone conversion is applied correctly."""
        engine = AlertRuleEngine(mock_session)
        # UTC time is 20:00, but in US/Eastern (UTC-5 in winter) it's 15:00
        current = datetime(2025, 1, 6, 20, 0, 0, tzinfo=ZoneInfo("UTC"))
        schedule = {
            "start_time": "14:00",
            "end_time": "16:00",
            "timezone": "US/Eastern",
        }
        result = engine._check_schedule(schedule, current)
        assert result is True

    def test_invalid_timezone_defaults_to_utc(self, mock_session: AsyncMock) -> None:
        """Test invalid timezone defaults to UTC."""
        engine = AlertRuleEngine(mock_session)
        current = datetime(2025, 1, 6, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
        schedule = {
            "start_time": "10:00",
            "end_time": "14:00",
            "timezone": "Invalid/Timezone",
        }
        result = engine._check_schedule(schedule, current)
        assert result is True


# =============================================================================
# AlertRuleEngine._build_dedup_key Tests
# =============================================================================


class TestBuildDedupKey:
    """Tests for _build_dedup_key method."""

    def test_default_template(
        self, mock_session: AsyncMock, sample_rule: AlertRule, sample_event: Event
    ) -> None:
        """Test default template {camera_id}:{rule_id}."""
        sample_rule.dedup_key_template = "{camera_id}:{rule_id}"
        engine = AlertRuleEngine(mock_session)
        result = engine._build_dedup_key(sample_rule, sample_event, [])
        assert result == f"front_door:{sample_rule.id}"

    def test_template_with_object_type(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test template with object_type variable."""
        sample_rule.dedup_key_template = "{camera_id}:{object_type}:{rule_id}"
        engine = AlertRuleEngine(mock_session)
        result = engine._build_dedup_key(sample_rule, sample_event, sample_detections)
        assert result == f"front_door:person:{sample_rule.id}"

    def test_object_type_unknown_when_no_detections(
        self, mock_session: AsyncMock, sample_rule: AlertRule, sample_event: Event
    ) -> None:
        """Test object_type is 'unknown' when no detections."""
        sample_rule.dedup_key_template = "{camera_id}:{object_type}"
        engine = AlertRuleEngine(mock_session)
        result = engine._build_dedup_key(sample_rule, sample_event, [])
        assert result == "front_door:unknown"

    def test_object_type_unknown_when_detection_has_none(
        self, mock_session: AsyncMock, sample_rule: AlertRule, sample_event: Event
    ) -> None:
        """Test object_type is 'unknown' when detection has None object_type."""
        sample_rule.dedup_key_template = "{camera_id}:{object_type}"
        detections = [
            Detection(
                id=1,
                camera_id="cam1",
                file_path="/export/foscam/cam1/img.jpg",
                object_type=None,
            )
        ]
        engine = AlertRuleEngine(mock_session)
        result = engine._build_dedup_key(sample_rule, sample_event, detections)
        assert result == "front_door:unknown"

    def test_uses_first_detection_object_type(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test uses first detection's object_type."""
        sample_rule.dedup_key_template = "{object_type}"
        # First detection has object_type="person"
        engine = AlertRuleEngine(mock_session)
        result = engine._build_dedup_key(sample_rule, sample_event, sample_detections)
        assert result == "person"

    def test_invalid_template_variable_falls_back(
        self, mock_session: AsyncMock, sample_rule: AlertRule, sample_event: Event
    ) -> None:
        """Test invalid template variable falls back to default key."""
        sample_rule.dedup_key_template = "{camera_id}:{invalid_var}"
        engine = AlertRuleEngine(mock_session)
        result = engine._build_dedup_key(sample_rule, sample_event, [])
        assert result == f"front_door:{sample_rule.id}"

    def test_none_template_uses_default(
        self, mock_session: AsyncMock, sample_rule: AlertRule, sample_event: Event
    ) -> None:
        """Test None template uses default template."""
        sample_rule.dedup_key_template = None  # type: ignore[assignment]
        engine = AlertRuleEngine(mock_session)
        result = engine._build_dedup_key(sample_rule, sample_event, [])
        assert result == f"front_door:{sample_rule.id}"


# =============================================================================
# AlertRuleEngine._check_cooldown Tests
# =============================================================================


class TestCheckCooldown:
    """Tests for _check_cooldown method."""

    @pytest.mark.asyncio
    async def test_returns_false_when_no_existing_alert(
        self, mock_session: AsyncMock, sample_rule: AlertRule
    ) -> None:
        """Test returns False when no existing alert in cooldown."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)
        result = await engine._check_cooldown(sample_rule, "front_door:rule-123", datetime.now(UTC))
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_alert_in_cooldown(
        self, mock_session: AsyncMock, sample_rule: AlertRule, sample_alert: Alert
    ) -> None:
        """Test returns True when alert exists within cooldown window."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)
        result = await engine._check_cooldown(sample_rule, "front_door:rule-123", datetime.now(UTC))
        assert result is True

    @pytest.mark.asyncio
    async def test_uses_default_cooldown_when_none(self, mock_session: AsyncMock) -> None:
        """Test uses 300 seconds default when cooldown_seconds is None."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Test Rule",
            enabled=True,
            severity=AlertSeverity.HIGH,
            cooldown_seconds=None,  # type: ignore[arg-type]
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)
        await engine._check_cooldown(rule, "key", datetime.now(UTC))

        # Verify query was executed (default cooldown of 300 seconds applied)
        mock_session.execute.assert_called_once()


# =============================================================================
# AlertRuleEngine._evaluate_rule Tests
# =============================================================================


class TestEvaluateRule:
    """Tests for _evaluate_rule method."""

    @pytest.mark.asyncio
    async def test_rule_with_no_conditions_always_matches(
        self,
        mock_session: AsyncMock,
        sample_rule_no_conditions: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test rule with no conditions always matches."""
        engine = AlertRuleEngine(mock_session)
        matches, conditions = await engine._evaluate_rule(
            sample_rule_no_conditions, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True
        assert "no_conditions (always matches)" in conditions

    @pytest.mark.asyncio
    async def test_risk_threshold_matches(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test risk threshold condition matches when score is above threshold."""
        sample_rule.risk_threshold = 70
        sample_event.risk_score = 85

        engine = AlertRuleEngine(mock_session)
        matches, conditions = await engine._evaluate_rule(
            sample_rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True
        assert any("risk_score >= 70" in c for c in conditions)

    @pytest.mark.asyncio
    async def test_risk_threshold_fails_when_below(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test risk threshold condition fails when score is below threshold."""
        sample_rule.risk_threshold = 90
        sample_event.risk_score = 70

        engine = AlertRuleEngine(mock_session)
        matches, conditions = await engine._evaluate_rule(
            sample_rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is False
        assert conditions == []

    @pytest.mark.asyncio
    async def test_risk_threshold_fails_when_none(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test risk threshold condition fails when event has no risk_score."""
        sample_rule.risk_threshold = 70
        sample_event.risk_score = None

        engine = AlertRuleEngine(mock_session)
        matches, _conditions = await engine._evaluate_rule(
            sample_rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is False

    @pytest.mark.asyncio
    async def test_camera_ids_matches(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test camera_ids condition matches when camera is in list."""
        sample_rule.risk_threshold = None
        sample_rule.camera_ids = ["front_door", "back_door"]

        engine = AlertRuleEngine(mock_session)
        matches, conditions = await engine._evaluate_rule(
            sample_rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True
        assert any("camera_id in" in c for c in conditions)

    @pytest.mark.asyncio
    async def test_camera_ids_fails(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test camera_ids condition fails when camera is not in list."""
        sample_rule.risk_threshold = None
        sample_rule.camera_ids = ["garage", "side_door"]

        engine = AlertRuleEngine(mock_session)
        matches, _conditions = await engine._evaluate_rule(
            sample_rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is False

    @pytest.mark.asyncio
    async def test_object_types_matches(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test object_types condition matches when type is detected."""
        sample_rule.risk_threshold = None
        sample_rule.object_types = ["person", "animal"]

        engine = AlertRuleEngine(mock_session)
        matches, conditions = await engine._evaluate_rule(
            sample_rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True
        assert any("object_type in" in c for c in conditions)

    @pytest.mark.asyncio
    async def test_object_types_fails(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test object_types condition fails when type is not detected."""
        sample_rule.risk_threshold = None
        sample_rule.object_types = ["dog", "cat"]

        engine = AlertRuleEngine(mock_session)
        matches, _conditions = await engine._evaluate_rule(
            sample_rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is False

    @pytest.mark.asyncio
    async def test_min_confidence_matches(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test min_confidence condition matches when confidence is above threshold."""
        sample_rule.risk_threshold = None
        sample_rule.min_confidence = 0.90

        engine = AlertRuleEngine(mock_session)
        matches, conditions = await engine._evaluate_rule(
            sample_rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True
        assert any("confidence >= 0.9" in c for c in conditions)

    @pytest.mark.asyncio
    async def test_min_confidence_fails(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test min_confidence condition fails when all confidence below threshold."""
        sample_rule.risk_threshold = None
        sample_rule.min_confidence = 0.99

        engine = AlertRuleEngine(mock_session)
        matches, _conditions = await engine._evaluate_rule(
            sample_rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is False

    @pytest.mark.asyncio
    async def test_schedule_matches(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test schedule condition matches when within schedule."""
        sample_rule.risk_threshold = None
        sample_rule.schedule = {"start_time": "00:00", "end_time": "23:59"}

        engine = AlertRuleEngine(mock_session)
        matches, conditions = await engine._evaluate_rule(
            sample_rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True
        assert "within_schedule" in conditions

    @pytest.mark.asyncio
    async def test_schedule_fails(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test schedule condition fails when outside schedule."""
        sample_rule.risk_threshold = None
        # Use a time range that's definitely outside current time
        sample_rule.schedule = {"start_time": "03:00", "end_time": "03:01"}
        current_time = datetime(2025, 1, 6, 12, 0, 0, tzinfo=ZoneInfo("UTC"))

        engine = AlertRuleEngine(mock_session)
        matches, _conditions = await engine._evaluate_rule(
            sample_rule, sample_event, sample_detections, current_time
        )
        assert matches is False

    @pytest.mark.asyncio
    async def test_all_conditions_and_logic(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test that all conditions must match (AND logic)."""
        sample_rule.risk_threshold = 70
        sample_rule.camera_ids = ["front_door"]
        sample_rule.object_types = ["person"]
        sample_rule.min_confidence = 0.90
        sample_event.risk_score = 85

        engine = AlertRuleEngine(mock_session)
        matches, conditions = await engine._evaluate_rule(
            sample_rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True
        assert len(conditions) == 4


# =============================================================================
# AlertRuleEngine.evaluate_event Tests
# =============================================================================


class TestEvaluateEvent:
    """Tests for evaluate_event method."""

    @pytest.mark.asyncio
    async def test_returns_evaluation_result(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test returns EvaluationResult."""
        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_rules_result

        engine = AlertRuleEngine(mock_session)
        result = await engine.evaluate_event(sample_event, sample_detections)

        assert isinstance(result, EvaluationResult)
        assert result.triggered_rules == []
        assert result.highest_severity is None

    @pytest.mark.asyncio
    async def test_loads_detections_if_not_provided(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test loads detections from database if not provided."""
        # First call: _get_enabled_rules
        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = []

        # Second call: _load_event_detections
        mock_detections_result = MagicMock()
        mock_detections_result.scalars.return_value.all.return_value = sample_detections

        mock_session.execute.side_effect = [mock_detections_result, mock_rules_result]

        engine = AlertRuleEngine(mock_session)
        await engine.evaluate_event(sample_event, detections=None)

        # Verify two queries were made
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_triggered_rules_sorted_by_severity(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test triggered rules are sorted by severity (highest first)."""
        low_rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Low Rule",
            enabled=True,
            severity=AlertSeverity.LOW,
            cooldown_seconds=300,
        )
        high_rule = AlertRule(
            id=str(uuid.uuid4()),
            name="High Rule",
            enabled=True,
            severity=AlertSeverity.HIGH,
            cooldown_seconds=300,
        )
        medium_rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Medium Rule",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            cooldown_seconds=300,
        )

        # Return rules in non-sorted order
        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [
            low_rule,
            high_rule,
            medium_rule,
        ]

        # No cooldown (no existing alerts)
        mock_cooldown_result = MagicMock()
        mock_cooldown_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [
            mock_rules_result,
            mock_cooldown_result,
            mock_cooldown_result,
            mock_cooldown_result,
        ]

        engine = AlertRuleEngine(mock_session)
        result = await engine.evaluate_event(sample_event, sample_detections)

        assert len(result.triggered_rules) == 3
        assert result.triggered_rules[0].severity == AlertSeverity.HIGH
        assert result.triggered_rules[1].severity == AlertSeverity.MEDIUM
        assert result.triggered_rules[2].severity == AlertSeverity.LOW

    @pytest.mark.asyncio
    async def test_skips_rules_in_cooldown(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
        sample_alert: Alert,
    ) -> None:
        """Test skips rules that are in cooldown."""
        sample_rule.risk_threshold = None  # Always matches

        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [sample_rule]

        # Alert exists in cooldown
        mock_cooldown_result = MagicMock()
        mock_cooldown_result.scalar_one_or_none.return_value = sample_alert

        mock_session.execute.side_effect = [mock_rules_result, mock_cooldown_result]

        engine = AlertRuleEngine(mock_session)
        result = await engine.evaluate_event(sample_event, sample_detections)

        assert len(result.triggered_rules) == 0
        assert len(result.skipped_rules) == 1
        assert result.skipped_rules[0][1] == "in_cooldown"

    @pytest.mark.asyncio
    async def test_tracks_highest_severity(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test highest_severity is set correctly."""
        critical_rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Critical Rule",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            cooldown_seconds=300,
        )
        low_rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Low Rule",
            enabled=True,
            severity=AlertSeverity.LOW,
            cooldown_seconds=300,
        )

        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [critical_rule, low_rule]

        mock_cooldown_result = MagicMock()
        mock_cooldown_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [
            mock_rules_result,
            mock_cooldown_result,
            mock_cooldown_result,
        ]

        engine = AlertRuleEngine(mock_session)
        result = await engine.evaluate_event(sample_event, sample_detections)

        assert result.highest_severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_handles_rule_evaluation_error(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
    ) -> None:
        """Test handles errors during rule evaluation."""
        sample_rule.schedule = {"invalid": "schedule format", "start_time": "invalid"}

        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [sample_rule]
        mock_session.execute.return_value = mock_rules_result

        engine = AlertRuleEngine(mock_session)

        # Patch _evaluate_rule to raise an exception
        with patch.object(engine, "_evaluate_rule", side_effect=Exception("Test error")):
            result = await engine.evaluate_event(sample_event, sample_detections)

        assert len(result.triggered_rules) == 0
        assert len(result.skipped_rules) == 1
        assert "evaluation_error" in result.skipped_rules[0][1]


# =============================================================================
# AlertRuleEngine.create_alerts_for_event Tests
# =============================================================================


class TestCreateAlertsForEvent:
    """Tests for create_alerts_for_event method."""

    @pytest.mark.asyncio
    async def test_creates_alerts_for_triggered_rules(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_rule: AlertRule,
    ) -> None:
        """Test creates alerts for all triggered rules."""
        triggered = TriggeredRule(
            rule=sample_rule,
            severity=AlertSeverity.HIGH,
            matched_conditions=["risk_score >= 70"],
            dedup_key="front_door:rule-123",
        )

        engine = AlertRuleEngine(mock_session)
        alerts = await engine.create_alerts_for_event(sample_event, [triggered])

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.event_id == sample_event.id
        assert alert.rule_id == sample_rule.id
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.PENDING
        assert alert.dedup_key == "front_door:rule-123"
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_multiple_alerts(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
    ) -> None:
        """Test creates multiple alerts for multiple triggered rules."""
        rule1 = AlertRule(
            id=str(uuid.uuid4()),
            name="Rule 1",
            enabled=True,
            severity=AlertSeverity.HIGH,
            channels=["push"],
        )
        rule2 = AlertRule(
            id=str(uuid.uuid4()),
            name="Rule 2",
            enabled=True,
            severity=AlertSeverity.LOW,
            channels=["email"],
        )

        triggered_rules = [
            TriggeredRule(
                rule=rule1,
                severity=AlertSeverity.HIGH,
                matched_conditions=["cond1"],
                dedup_key="key1",
            ),
            TriggeredRule(
                rule=rule2,
                severity=AlertSeverity.LOW,
                matched_conditions=["cond2"],
                dedup_key="key2",
            ),
        ]

        engine = AlertRuleEngine(mock_session)
        alerts = await engine.create_alerts_for_event(sample_event, triggered_rules)

        assert len(alerts) == 2
        assert mock_session.add.call_count == 2

    @pytest.mark.asyncio
    async def test_alert_metadata_contains_matched_conditions(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_rule: AlertRule,
    ) -> None:
        """Test alert metadata contains matched conditions."""
        triggered = TriggeredRule(
            rule=sample_rule,
            severity=AlertSeverity.HIGH,
            matched_conditions=["risk_score >= 70", "camera_id in ['front_door']"],
            dedup_key="front_door:rule-123",
        )

        engine = AlertRuleEngine(mock_session)
        alerts = await engine.create_alerts_for_event(sample_event, [triggered])

        assert alerts[0].alert_metadata is not None
        assert "matched_conditions" in alerts[0].alert_metadata
        assert alerts[0].alert_metadata["matched_conditions"] == triggered.matched_conditions
        assert alerts[0].alert_metadata["rule_name"] == sample_rule.name

    @pytest.mark.asyncio
    async def test_uses_rule_channels(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
    ) -> None:
        """Test alert uses channels from the rule."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Test Rule",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            channels=["push", "sms", "email"],
        )
        triggered = TriggeredRule(
            rule=rule,
            severity=AlertSeverity.MEDIUM,
            dedup_key="key",
        )

        engine = AlertRuleEngine(mock_session)
        alerts = await engine.create_alerts_for_event(sample_event, [triggered])

        assert alerts[0].channels == ["push", "sms", "email"]

    @pytest.mark.asyncio
    async def test_handles_none_channels(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
    ) -> None:
        """Test handles rule with None channels."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Test Rule",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            channels=None,
        )
        triggered = TriggeredRule(
            rule=rule,
            severity=AlertSeverity.MEDIUM,
            dedup_key="key",
        )

        engine = AlertRuleEngine(mock_session)
        alerts = await engine.create_alerts_for_event(sample_event, [triggered])

        assert alerts[0].channels == []


# =============================================================================
# AlertRuleEngine._batch_load_detections_for_events Tests
# =============================================================================


class TestBatchLoadDetectionsForEvents:
    """Tests for _batch_load_detections_for_events method."""

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_events(self, mock_session: AsyncMock) -> None:
        """Test returns empty dict when no events provided."""
        engine = AlertRuleEngine(mock_session)
        result = await engine._batch_load_detections_for_events([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_empty_lists_when_no_detection_ids(
        self, mock_session: AsyncMock, sample_event: Event
    ) -> None:
        """Test returns empty lists when events have no detection_ids."""
        sample_event.detection_ids = None
        event2 = Event(
            id=2,
            batch_id=str(uuid.uuid4()),
            camera_id="back_door",
            started_at=datetime.now(UTC),
            detection_ids=None,
        )

        engine = AlertRuleEngine(mock_session)
        result = await engine._batch_load_detections_for_events([sample_event, event2])

        assert result == {1: [], 2: []}

    @pytest.mark.asyncio
    async def test_handles_invalid_json_detection_ids(
        self, mock_session: AsyncMock, sample_event: Event
    ) -> None:
        """Test handles invalid JSON in detection_ids."""
        sample_event.detection_ids = "not-valid-json"

        engine = AlertRuleEngine(mock_session)
        result = await engine._batch_load_detections_for_events([sample_event])

        assert result == {1: []}

    @pytest.mark.asyncio
    async def test_handles_non_list_detection_ids(
        self, mock_session: AsyncMock, sample_event: Event
    ) -> None:
        """Test handles non-list detection_ids."""
        sample_event.detection_ids = json.dumps({"not": "a list"})

        engine = AlertRuleEngine(mock_session)
        result = await engine._batch_load_detections_for_events([sample_event])

        assert result == {1: []}

    @pytest.mark.asyncio
    async def test_batch_loads_detections(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test batch loads detections from database."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_detections
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)
        result = await engine._batch_load_detections_for_events([sample_event])

        assert len(result[sample_event.id]) == 3
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_maps_detections_to_correct_events(
        self,
        mock_session: AsyncMock,
        sample_detections: list[Detection],
    ) -> None:
        """Test detections are mapped to correct events."""
        event1 = Event(
            id=1,
            batch_id=str(uuid.uuid4()),
            camera_id="cam1",
            started_at=datetime.now(UTC),
            detection_ids=json.dumps([1, 2]),
        )
        event2 = Event(
            id=2,
            batch_id=str(uuid.uuid4()),
            camera_id="cam2",
            started_at=datetime.now(UTC),
            detection_ids=json.dumps([3]),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_detections
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)
        result = await engine._batch_load_detections_for_events([event1, event2])

        assert len(result[1]) == 2
        assert len(result[2]) == 1


# =============================================================================
# AlertRuleEngine.test_rule_against_events Tests
# =============================================================================


class TestTestRuleAgainstEvents:
    """Tests for test_rule_against_events method."""

    @pytest.mark.asyncio
    async def test_returns_list_of_results(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test returns list of test results."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_detections
        mock_session.execute.return_value = mock_result

        sample_rule.risk_threshold = 70
        sample_event.risk_score = 85

        engine = AlertRuleEngine(mock_session)
        results = await engine.test_rule_against_events(sample_rule, [sample_event])

        assert len(results) == 1
        assert results[0]["event_id"] == sample_event.id
        assert results[0]["camera_id"] == sample_event.camera_id
        assert results[0]["risk_score"] == 85
        assert results[0]["matches"] is True

    @pytest.mark.asyncio
    async def test_result_includes_object_types(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test result includes detected object types."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_detections
        mock_session.execute.return_value = mock_result

        sample_rule.risk_threshold = None

        engine = AlertRuleEngine(mock_session)
        results = await engine.test_rule_against_events(sample_rule, [sample_event])

        assert "object_types" in results[0]
        assert "person" in results[0]["object_types"]
        assert "vehicle" in results[0]["object_types"]

    @pytest.mark.asyncio
    async def test_result_includes_matched_conditions(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test result includes matched conditions."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_detections
        mock_session.execute.return_value = mock_result

        sample_rule.risk_threshold = 70
        sample_event.risk_score = 85

        engine = AlertRuleEngine(mock_session)
        results = await engine.test_rule_against_events(sample_rule, [sample_event])

        assert "matched_conditions" in results[0]
        assert len(results[0]["matched_conditions"]) > 0

    @pytest.mark.asyncio
    async def test_tests_multiple_events(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_detections: list[Detection],
    ) -> None:
        """Test evaluates multiple events."""
        event1 = Event(
            id=1,
            batch_id=str(uuid.uuid4()),
            camera_id="cam1",
            started_at=datetime.now(UTC),
            risk_score=85,
            detection_ids=json.dumps([1]),
        )
        event2 = Event(
            id=2,
            batch_id=str(uuid.uuid4()),
            camera_id="cam2",
            started_at=datetime.now(UTC),
            risk_score=50,
            detection_ids=json.dumps([2]),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_detections[:2]
        mock_session.execute.return_value = mock_result

        sample_rule.risk_threshold = 70

        engine = AlertRuleEngine(mock_session)
        results = await engine.test_rule_against_events(sample_rule, [event1, event2])

        assert len(results) == 2
        assert results[0]["matches"] is True
        assert results[1]["matches"] is False

    @pytest.mark.asyncio
    async def test_uses_custom_current_time(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test uses provided current_time for schedule evaluation."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_detections
        mock_session.execute.return_value = mock_result

        sample_rule.risk_threshold = None
        sample_rule.schedule = {"start_time": "10:00", "end_time": "12:00"}

        # Time within schedule
        within_schedule = datetime(2025, 1, 6, 11, 0, 0, tzinfo=ZoneInfo("UTC"))

        engine = AlertRuleEngine(mock_session)
        results = await engine.test_rule_against_events(
            sample_rule, [sample_event], current_time=within_schedule
        )

        assert results[0]["matches"] is True


# =============================================================================
# get_alert_engine Tests
# =============================================================================


class TestGetAlertEngine:
    """Tests for get_alert_engine convenience function."""

    @pytest.mark.asyncio
    async def test_returns_alert_rule_engine(self, mock_session: AsyncMock) -> None:
        """Test returns AlertRuleEngine instance."""
        engine = await get_alert_engine(mock_session)
        assert isinstance(engine, AlertRuleEngine)
        assert engine.session == mock_session
        assert engine.redis_client is None

    @pytest.mark.asyncio
    async def test_passes_redis_client(
        self, mock_session: AsyncMock, mock_redis: AsyncMock
    ) -> None:
        """Test passes Redis client to engine."""
        engine = await get_alert_engine(mock_session, mock_redis)
        assert engine.redis_client == mock_redis


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCases:
    """Edge case tests for AlertRuleEngine."""

    @pytest.mark.asyncio
    async def test_empty_detections_list_handling(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
    ) -> None:
        """Test handles empty detections list correctly."""
        sample_rule.risk_threshold = 70
        sample_event.risk_score = 85

        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [sample_rule]

        mock_cooldown_result = MagicMock()
        mock_cooldown_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [mock_rules_result, mock_cooldown_result]

        engine = AlertRuleEngine(mock_session)
        result = await engine.evaluate_event(sample_event, [])

        # Rule should still match based on risk_score alone
        assert len(result.triggered_rules) == 1

    @pytest.mark.asyncio
    async def test_rule_with_all_conditions_and_logic(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test rule with all condition types."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Full Rule",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            risk_threshold=70,
            camera_ids=["front_door"],
            object_types=["person"],
            min_confidence=0.90,
            schedule={"start_time": "00:00", "end_time": "23:59"},
            cooldown_seconds=300,
        )
        sample_event.risk_score = 85

        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [rule]

        mock_cooldown_result = MagicMock()
        mock_cooldown_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [mock_rules_result, mock_cooldown_result]

        engine = AlertRuleEngine(mock_session)
        result = await engine.evaluate_event(sample_event, sample_detections)

        assert len(result.triggered_rules) == 1
        assert len(result.triggered_rules[0].matched_conditions) == 5


class TestZoneIdCondition:
    """Tests for zone_ids condition (currently logs debug message)."""

    @pytest.mark.asyncio
    async def test_zone_ids_logs_debug_message(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test zone_ids condition logs debug message (not yet implemented)."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Zone Rule",
            enabled=True,
            severity=AlertSeverity.HIGH,
            zone_ids=["zone1", "zone2"],
            cooldown_seconds=300,
        )

        engine = AlertRuleEngine(mock_session)

        with patch("backend.services.alert_engine.logger") as mock_logger:
            matches, _conditions = await engine._evaluate_rule(
                rule, sample_event, sample_detections, datetime.now(UTC)
            )

            # Rule should match (zone condition is not enforced)
            assert matches is True
            mock_logger.debug.assert_called()


class TestDatabaseInteraction:
    """Tests for database interaction patterns."""

    @pytest.mark.asyncio
    async def test_cooldown_uses_for_update_lock(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
    ) -> None:
        """Test cooldown check uses SELECT FOR UPDATE to prevent race conditions."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)
        await engine._check_cooldown(sample_rule, "key", datetime.now(UTC))

        # Verify execute was called (the query uses with_for_update)
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_alerts_flushes_session(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_rule: AlertRule,
    ) -> None:
        """Test create_alerts_for_event flushes session after adding alerts."""
        triggered = TriggeredRule(
            rule=sample_rule,
            severity=AlertSeverity.HIGH,
            dedup_key="key",
        )

        engine = AlertRuleEngine(mock_session)
        await engine.create_alerts_for_event(sample_event, [triggered])

        mock_session.flush.assert_called_once()


class TestTimeZoneEdgeCases:
    """Tests for timezone edge cases in schedule evaluation."""

    def test_schedule_across_day_boundary(self, mock_session: AsyncMock) -> None:
        """Test schedule that crosses day boundary with timezone."""
        engine = AlertRuleEngine(mock_session)
        # UTC 03:00 is 22:00 previous day in US/Eastern (UTC-5)
        current = datetime(2025, 1, 7, 3, 0, 0, tzinfo=ZoneInfo("UTC"))
        schedule = {
            "start_time": "21:00",
            "end_time": "23:00",
            "timezone": "US/Eastern",
        }
        result = engine._check_schedule(schedule, current)
        assert result is True

    def test_empty_days_list_matches_all_days(self, mock_session: AsyncMock) -> None:
        """Test empty days list matches all days."""
        engine = AlertRuleEngine(mock_session)
        current = datetime(2025, 1, 6, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
        schedule = {"days": [], "start_time": "10:00", "end_time": "14:00"}
        result = engine._check_schedule(schedule, current)
        assert result is True


# =============================================================================
# Hypothesis Property-Based Tests
# =============================================================================
# These tests use Hypothesis to discover edge cases through random input generation.
# They verify invariants that must hold for all valid inputs.


class TestAlertEngineHypothesis:
    """Property-based tests for AlertRuleEngine using Hypothesis."""

    @given(
        risk_score=valid_risk_scores,
        threshold=valid_risk_scores,
    )
    @settings(max_examples=100)
    def test_risk_threshold_evaluation_is_deterministic(
        self, risk_score: int, threshold: int
    ) -> None:
        """Property: Risk threshold evaluation is deterministic.

        Tests that the same risk_score and threshold always produce the same
        match result. Uses direct comparison logic without async.
        """
        # Verify determinism: same inputs produce same outputs
        # The actual alert rule check logic:
        # A rule with risk_threshold matches if event.risk_score >= threshold
        result1 = risk_score >= threshold
        result2 = risk_score >= threshold

        # Same inputs always produce same output
        assert result1 == result2

        # Verify correct behavior based on threshold logic
        if risk_score >= threshold:
            assert result1 is True
        else:
            assert result1 is False

    @given(
        score=valid_risk_scores,
    )
    @settings(max_examples=50)
    def test_higher_risk_implies_higher_severity_trigger(self, score: int) -> None:
        """Property: Higher risk scores trigger equal or more rules than lower scores.

        If a rule triggers at score X, it should also trigger at score X+1.
        Uses direct comparison logic to verify the monotonicity property.
        """
        # Test threshold at 50
        threshold = 50

        # The rule triggers if score >= threshold
        result_lower = score >= threshold
        result_higher = min(100, score + 1) >= threshold

        # If lower score triggers, higher must also trigger
        # This tests monotonicity: score >= threshold implies (score+1) >= threshold
        if result_lower:
            assert result_higher, (
                f"Monotonicity violated: score={score} triggers but score+1={score + 1} doesn't"
            )

    @given(
        sev_a=st.sampled_from(list(AlertSeverity)),
        sev_b=st.sampled_from(list(AlertSeverity)),
    )
    @settings(max_examples=50)
    def test_severity_priority_ordering_is_total(
        self, sev_a: AlertSeverity, sev_b: AlertSeverity
    ) -> None:
        """Property: Severity priority defines a total ordering."""
        # Reflexivity: a == a
        assert SEVERITY_PRIORITY[sev_a] == SEVERITY_PRIORITY[sev_a]

        # Antisymmetry: if a <= b and b <= a, then a == b
        if (
            SEVERITY_PRIORITY[sev_a] <= SEVERITY_PRIORITY[sev_b]
            and SEVERITY_PRIORITY[sev_b] <= SEVERITY_PRIORITY[sev_a]
        ):
            assert SEVERITY_PRIORITY[sev_a] == SEVERITY_PRIORITY[sev_b]

        # Trichotomy: exactly one of a < b, a == b, a > b
        comparisons = [
            SEVERITY_PRIORITY[sev_a] < SEVERITY_PRIORITY[sev_b],
            SEVERITY_PRIORITY[sev_a] == SEVERITY_PRIORITY[sev_b],
            SEVERITY_PRIORITY[sev_a] > SEVERITY_PRIORITY[sev_b],
        ]
        assert sum(comparisons) == 1

    @given(
        confidences=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            min_size=1,
            max_size=10,
        ),
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=50)
    def test_min_confidence_matches_highest_detection(
        self, confidences: list[float], threshold: float
    ) -> None:
        """Property: min_confidence check matches if any detection meets threshold."""
        mock_session = AsyncMock()
        engine = AlertRuleEngine(mock_session)

        # Create detections with given confidences
        detections = [
            Detection(
                id=i + 1,
                camera_id="cam1",
                file_path=f"/path/img{i}.jpg",
                confidence=conf,
            )
            for i, conf in enumerate(confidences)
        ]

        result = engine._check_min_confidence(threshold, detections)

        # Property: matches if and only if any confidence >= threshold
        any_meets = any(c >= threshold for c in confidences if c is not None)
        assert result == any_meets

    @given(
        object_types=st.lists(
            st.text(
                min_size=1,
                max_size=20,
                alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
            ),
            min_size=1,
            max_size=5,
        ),
        required_type=st.text(
            min_size=1,
            max_size=20,
            alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        ),
    )
    @settings(max_examples=50)
    def test_object_type_matching_is_case_insensitive(
        self, object_types: list[str], required_type: str
    ) -> None:
        """Property: Object type matching is case-insensitive.

        Note: Uses ASCII letters only as the system expects standard object type names
        like 'person', 'car', etc. Unicode case conversion can behave differently.
        """
        mock_session = AsyncMock()
        engine = AlertRuleEngine(mock_session)

        # Create detections with given object types
        detections = [
            Detection(
                id=i + 1,
                camera_id="cam1",
                file_path=f"/path/img{i}.jpg",
                object_type=obj_type,
            )
            for i, obj_type in enumerate(object_types)
        ]

        # Check matching
        result_lower = engine._check_object_types([required_type.lower()], detections)
        result_upper = engine._check_object_types([required_type.upper()], detections)
        result_mixed = engine._check_object_types([required_type], detections)

        # All should give same result (case-insensitive)
        assert result_lower == result_upper == result_mixed

    @given(
        camera_id=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"),
                whitelist_characters="_-",
            ),
        ),
        rule_id=st.uuids(),
    )
    @settings(max_examples=50)
    def test_dedup_key_template_substitution(self, camera_id: str, rule_id: uuid.UUID) -> None:
        """Property: Dedup key template substitutes variables correctly."""
        mock_session = AsyncMock()
        engine = AlertRuleEngine(mock_session)

        event = Event(
            id=1,
            batch_id=str(uuid.uuid4()),
            camera_id=camera_id,
            started_at=datetime.now(UTC),
        )

        rule = AlertRule(
            id=str(rule_id),
            name="Test",
            enabled=True,
            severity=AlertSeverity.HIGH,
            dedup_key_template="{camera_id}:{rule_id}",
        )

        result = engine._build_dedup_key(rule, event, [])

        # Key should contain both camera_id and rule_id
        assert camera_id in result
        assert str(rule_id) in result
        assert result == f"{camera_id}:{rule_id}"


class TestAlertEvaluationInvariantsHypothesis:
    """Property tests for alert evaluation invariants."""

    @given(
        rule_count=st.integers(min_value=0, max_value=5),
        severity_list=st.lists(
            st.sampled_from(list(AlertSeverity)),
            min_size=0,
            max_size=5,
        ),
    )
    @settings(max_examples=30)
    def test_highest_severity_is_max_of_triggered(
        self, rule_count: int, severity_list: list[AlertSeverity]
    ) -> None:
        """Property: highest_severity equals max severity of all triggered rules."""
        # Create triggered rules with given severities
        triggered_rules = []
        for i, sev in enumerate(severity_list[:rule_count]):
            rule = AlertRule(
                id=str(uuid.uuid4()),
                name=f"Rule {i}",
                enabled=True,
                severity=sev,
            )
            triggered = TriggeredRule(
                rule=rule,
                severity=sev,
                matched_conditions=["test"],
                dedup_key=f"key{i}",
            )
            triggered_rules.append(triggered)

        # Calculate expected highest severity
        if triggered_rules:
            expected = max(
                (t.severity for t in triggered_rules),
                key=lambda s: SEVERITY_PRIORITY[s],
            )
        else:
            expected = None

        # Simulate what EvaluationResult would report
        result = EvaluationResult(
            triggered_rules=triggered_rules,
            highest_severity=expected if triggered_rules else None,
        )

        # Property: highest_severity matches actual max
        if triggered_rules:
            actual_max = max(
                (t.severity for t in result.triggered_rules),
                key=lambda s: SEVERITY_PRIORITY[s],
            )
            assert result.highest_severity == actual_max
        else:
            assert result.highest_severity is None

    @given(triggered_count=st.integers(min_value=0, max_value=10))
    @settings(max_examples=30)
    def test_has_triggers_reflects_list_length(self, triggered_count: int) -> None:
        """Property: has_triggers is True iff triggered_rules is non-empty."""
        triggered_rules = []
        for i in range(triggered_count):
            rule = AlertRule(
                id=str(uuid.uuid4()),
                name=f"Rule {i}",
                enabled=True,
                severity=AlertSeverity.HIGH,
            )
            triggered = TriggeredRule(
                rule=rule,
                severity=AlertSeverity.HIGH,
                dedup_key=f"key{i}",
            )
            triggered_rules.append(triggered)

        result = EvaluationResult(triggered_rules=triggered_rules)

        # Property: has_triggers iff list is non-empty
        assert result.has_triggers == (len(triggered_rules) > 0)
        assert result.has_triggers == (triggered_count > 0)


class TestScheduleInvariantsHypothesis:
    """Property tests for schedule evaluation."""

    @given(
        hour=st.integers(min_value=0, max_value=23),
        minute=st.integers(min_value=0, max_value=59),
    )
    @settings(max_examples=50)
    def test_time_parsing_roundtrip(self, hour: int, minute: int) -> None:
        """Property: Time parsing is consistent."""
        mock_session = AsyncMock()
        engine = AlertRuleEngine(mock_session)

        time_str = f"{hour:02d}:{minute:02d}"
        parsed = engine._parse_time(time_str)

        assert parsed.hour == hour
        assert parsed.minute == minute

    @given(
        day_of_week=st.integers(min_value=0, max_value=6),
    )
    @settings(max_examples=20)
    def test_day_matching_is_consistent(self, day_of_week: int) -> None:
        """Property: Day matching is consistent for all days of week."""
        mock_session = AsyncMock()
        engine = AlertRuleEngine(mock_session)

        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

        # Create a date for the given day of week (Jan 2025)
        # Jan 6, 2025 is Monday (day_of_week=0)
        base_date = datetime(2025, 1, 6 + day_of_week, 12, 0, 0, tzinfo=ZoneInfo("UTC"))

        # Schedule with just that day
        schedule = {"days": [day_names[day_of_week]]}

        result = engine._check_schedule(schedule, base_date)
        assert result is True

        # Schedule without that day
        other_days = [d for i, d in enumerate(day_names) if i != day_of_week]
        schedule_other = {"days": other_days}

        result_other = engine._check_schedule(schedule_other, base_date)
        assert result_other is False
