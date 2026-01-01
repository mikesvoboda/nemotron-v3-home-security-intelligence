"""Unit tests for alert engine service.

Tests cover:
- AlertRuleEngine initialization
- Rule evaluation against events and detections
- Condition matching (risk threshold, camera IDs, object types, etc.)
- Schedule checking
- Cooldown handling
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models import AlertRule, AlertSeverity, Detection, Event
from backend.services.alert_engine import (
    DAY_NAMES,
    SEVERITY_PRIORITY,
    AlertRuleEngine,
    EvaluationResult,
    TriggeredRule,
    _utc_now_naive,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def sample_event() -> Event:
    """Create a sample event for testing."""
    return Event(
        id=1,
        batch_id="batch-123",
        camera_id="cam-front",
        started_at=datetime(2025, 12, 23, 10, 0, 0),
        ended_at=datetime(2025, 12, 23, 10, 1, 0),
        risk_score=75,
        risk_level="high",
        summary="Test event",
        detection_ids="[1, 2]",
    )


@pytest.fixture
def sample_detections() -> list[Detection]:
    """Create sample detections for testing."""
    return [
        Detection(
            id=1,
            camera_id="cam-front",
            file_path="/path/to/image1.jpg",
            object_type="person",
            confidence=0.92,
            detected_at=datetime(2025, 12, 23, 10, 0, 0),
        ),
        Detection(
            id=2,
            camera_id="cam-front",
            file_path="/path/to/image2.jpg",
            object_type="vehicle",
            confidence=0.85,
            detected_at=datetime(2025, 12, 23, 10, 0, 30),
        ),
    ]


@pytest.fixture
def sample_rule() -> AlertRule:
    """Create a sample alert rule for testing."""
    return AlertRule(
        id=str(uuid.uuid4()),
        name="Test Rule",
        enabled=True,
        severity=AlertSeverity.HIGH,
        risk_threshold=70,
        object_types=None,
        camera_ids=None,
        zone_ids=None,
        min_confidence=None,
        schedule=None,
        cooldown_seconds=300,
        dedup_key_template="alert:{camera_id}:{rule_id}",
        created_at=datetime(2025, 12, 23, 10, 0, 0),
        updated_at=datetime(2025, 12, 23, 10, 0, 0),
    )


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestUtcNowNaive:
    """Tests for _utc_now_naive helper function."""

    def test_returns_naive_datetime(self) -> None:
        """Test that _utc_now_naive returns a naive datetime."""
        result = _utc_now_naive()
        assert result.tzinfo is None

    def test_returns_recent_time(self) -> None:
        """Test that the returned time is recent."""
        result = _utc_now_naive()
        now = datetime.now(UTC).replace(tzinfo=None)
        assert abs((now - result).total_seconds()) < 1


class TestSeverityPriority:
    """Tests for severity priority constants."""

    def test_severity_order(self) -> None:
        """Test that severity priorities are correctly ordered."""
        assert SEVERITY_PRIORITY[AlertSeverity.LOW] < SEVERITY_PRIORITY[AlertSeverity.MEDIUM]
        assert SEVERITY_PRIORITY[AlertSeverity.MEDIUM] < SEVERITY_PRIORITY[AlertSeverity.HIGH]
        assert SEVERITY_PRIORITY[AlertSeverity.HIGH] < SEVERITY_PRIORITY[AlertSeverity.CRITICAL]


class TestDayNames:
    """Tests for day name constants."""

    def test_day_names_length(self) -> None:
        """Test that DAY_NAMES has 7 entries."""
        assert len(DAY_NAMES) == 7

    def test_day_names_values(self) -> None:
        """Test that DAY_NAMES contains expected values."""
        assert "monday" in DAY_NAMES
        assert "sunday" in DAY_NAMES


# =============================================================================
# EvaluationResult Tests
# =============================================================================


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass."""

    def test_has_triggers_empty(self) -> None:
        """Test has_triggers returns False when no triggers."""
        result = EvaluationResult()
        assert result.has_triggers is False

    def test_has_triggers_with_triggers(self, sample_rule: AlertRule) -> None:
        """Test has_triggers returns True when triggers exist."""
        triggered = TriggeredRule(
            rule=sample_rule,
            severity=AlertSeverity.HIGH,
            matched_conditions=["test"],
        )
        result = EvaluationResult(triggered_rules=[triggered])
        assert result.has_triggers is True


class TestTriggeredRule:
    """Tests for TriggeredRule dataclass."""

    def test_default_values(self, sample_rule: AlertRule) -> None:
        """Test TriggeredRule default values."""
        triggered = TriggeredRule(
            rule=sample_rule,
            severity=AlertSeverity.HIGH,
        )
        assert triggered.matched_conditions == []
        assert triggered.dedup_key == ""


# =============================================================================
# AlertRuleEngine Tests
# =============================================================================


class TestAlertRuleEngineInit:
    """Tests for AlertRuleEngine initialization."""

    def test_init_with_session_only(self, mock_session: AsyncMock) -> None:
        """Test initialization with only session."""
        engine = AlertRuleEngine(mock_session)
        assert engine.session == mock_session
        assert engine.redis_client is None


class TestCheckObjectTypes:
    """Tests for _check_object_types method."""

    def test_empty_detections(self, mock_session: AsyncMock) -> None:
        """Test with no detections."""
        engine = AlertRuleEngine(mock_session)
        result = engine._check_object_types(["person"], [])
        assert result is False

    def test_matching_object_type(
        self, mock_session: AsyncMock, sample_detections: list[Detection]
    ) -> None:
        """Test with matching object type."""
        engine = AlertRuleEngine(mock_session)
        result = engine._check_object_types(["person"], sample_detections)
        assert result is True

    def test_non_matching_object_type(
        self, mock_session: AsyncMock, sample_detections: list[Detection]
    ) -> None:
        """Test with non-matching object type."""
        engine = AlertRuleEngine(mock_session)
        result = engine._check_object_types(["animal"], sample_detections)
        assert result is False

    def test_case_insensitive_match(
        self, mock_session: AsyncMock, sample_detections: list[Detection]
    ) -> None:
        """Test case-insensitive object type matching."""
        engine = AlertRuleEngine(mock_session)
        result = engine._check_object_types(["PERSON"], sample_detections)
        assert result is True


class TestCheckMinConfidence:
    """Tests for _check_min_confidence method."""

    def test_empty_detections(self, mock_session: AsyncMock) -> None:
        """Test with no detections."""
        engine = AlertRuleEngine(mock_session)
        result = engine._check_min_confidence(0.8, [])
        assert result is False

    def test_above_threshold(
        self, mock_session: AsyncMock, sample_detections: list[Detection]
    ) -> None:
        """Test with confidence above threshold."""
        engine = AlertRuleEngine(mock_session)
        result = engine._check_min_confidence(0.9, sample_detections)
        assert result is True

    def test_below_threshold(
        self, mock_session: AsyncMock, sample_detections: list[Detection]
    ) -> None:
        """Test with confidence below threshold."""
        engine = AlertRuleEngine(mock_session)
        result = engine._check_min_confidence(0.95, sample_detections)
        assert result is False


class TestCheckSchedule:
    """Tests for _check_schedule method."""

    def test_empty_schedule(self, mock_session: AsyncMock) -> None:
        """Test with empty schedule allows all times."""
        engine = AlertRuleEngine(mock_session)
        result = engine._check_schedule({}, datetime(2025, 12, 23, 10, 0, 0))
        assert result is True

    def test_within_time_range(self, mock_session: AsyncMock) -> None:
        """Test when current time is within schedule."""
        engine = AlertRuleEngine(mock_session)
        schedule = {
            "start_time": "09:00",
            "end_time": "17:00",
        }
        current_time = datetime(2025, 12, 23, 10, 0, 0)
        result = engine._check_schedule(schedule, current_time)
        assert result is True

    def test_outside_time_range(self, mock_session: AsyncMock) -> None:
        """Test when current time is outside schedule."""
        engine = AlertRuleEngine(mock_session)
        schedule = {
            "start_time": "09:00",
            "end_time": "17:00",
        }
        current_time = datetime(2025, 12, 23, 20, 0, 0)
        result = engine._check_schedule(schedule, current_time)
        assert result is False


class TestEvaluateRule:
    """Tests for _evaluate_rule method."""

    @pytest.mark.asyncio
    async def test_rule_matches_risk_threshold(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
    ) -> None:
        """Test rule matches when risk threshold is met."""
        engine = AlertRuleEngine(mock_session)
        matches, conditions = await engine._evaluate_rule(
            sample_rule,
            sample_event,
            sample_detections,
            datetime(2025, 12, 23, 10, 0, 0),
        )
        assert matches is True
        assert any("risk_score" in c for c in conditions)

    @pytest.mark.asyncio
    async def test_rule_fails_risk_threshold(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
    ) -> None:
        """Test rule fails when risk threshold not met."""
        sample_rule.risk_threshold = 90
        sample_event.risk_score = 50
        engine = AlertRuleEngine(mock_session)
        matches, conditions = await engine._evaluate_rule(
            sample_rule,
            sample_event,
            sample_detections,
            datetime(2025, 12, 23, 10, 0, 0),
        )
        assert matches is False
        assert conditions == []

    @pytest.mark.asyncio
    async def test_rule_matches_camera_ids(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
    ) -> None:
        """Test rule matches when camera ID is in list."""
        sample_rule.camera_ids = ["cam-front", "cam-back"]
        sample_rule.risk_threshold = None
        engine = AlertRuleEngine(mock_session)
        matches, conditions = await engine._evaluate_rule(
            sample_rule,
            sample_event,
            sample_detections,
            datetime(2025, 12, 23, 10, 0, 0),
        )
        assert matches is True
        assert any("camera_id" in c for c in conditions)

    @pytest.mark.asyncio
    async def test_rule_fails_camera_ids(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
    ) -> None:
        """Test rule fails when camera ID not in list."""
        sample_rule.camera_ids = ["cam-back", "cam-side"]
        sample_rule.risk_threshold = None
        engine = AlertRuleEngine(mock_session)
        matches, _conditions = await engine._evaluate_rule(
            sample_rule,
            sample_event,
            sample_detections,
            datetime(2025, 12, 23, 10, 0, 0),
        )
        assert matches is False

    @pytest.mark.asyncio
    async def test_rule_with_no_conditions(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
    ) -> None:
        """Test rule with no conditions always matches."""
        sample_rule.risk_threshold = None
        sample_rule.camera_ids = None
        sample_rule.object_types = None
        sample_rule.min_confidence = None
        sample_rule.schedule = None
        engine = AlertRuleEngine(mock_session)
        matches, conditions = await engine._evaluate_rule(
            sample_rule,
            sample_event,
            sample_detections,
            datetime(2025, 12, 23, 10, 0, 0),
        )
        assert matches is True
        assert "no_conditions" in conditions[0]


class TestGetEnabledRules:
    """Tests for _get_enabled_rules method."""

    @pytest.mark.asyncio
    async def test_get_enabled_rules(self, mock_session: AsyncMock, sample_rule: AlertRule) -> None:
        """Test loading enabled rules from database."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_rule]
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)
        rules = await engine._get_enabled_rules()

        assert len(rules) == 1
        assert rules[0].name == "Test Rule"


class TestLoadEventDetections:
    """Tests for _load_event_detections method."""

    @pytest.mark.asyncio
    async def test_load_detections_empty_ids(
        self, mock_session: AsyncMock, sample_event: Event
    ) -> None:
        """Test loading detections when event has no detection IDs."""
        sample_event.detection_ids = None
        engine = AlertRuleEngine(mock_session)
        detections = await engine._load_event_detections(sample_event)
        assert detections == []

    @pytest.mark.asyncio
    async def test_load_detections_invalid_json(
        self, mock_session: AsyncMock, sample_event: Event
    ) -> None:
        """Test loading detections with invalid JSON."""
        sample_event.detection_ids = "not-valid-json"
        engine = AlertRuleEngine(mock_session)
        detections = await engine._load_event_detections(sample_event)
        assert detections == []

    @pytest.mark.asyncio
    async def test_load_detections_success(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test successful detection loading."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_detections
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)
        detections = await engine._load_event_detections(sample_event)

        assert len(detections) == 2


class TestEvaluateEvent:
    """Tests for evaluate_event method."""

    @pytest.mark.asyncio
    async def test_evaluate_event_no_rules(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Test evaluation when no rules exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)
        result = await engine.evaluate_event(
            sample_event,
            sample_detections,
            datetime(2025, 12, 23, 10, 0, 0),
        )

        assert result.triggered_rules == []
        assert result.has_triggers is False

    @pytest.mark.asyncio
    async def test_evaluate_event_with_matching_rule(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
    ) -> None:
        """Test evaluation when rule matches."""
        # First call returns enabled rules
        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [sample_rule]

        # Second call (cooldown check) returns None (not in cooldown)
        mock_cooldown_result = MagicMock()
        mock_cooldown_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [mock_rules_result, mock_cooldown_result]

        engine = AlertRuleEngine(mock_session)
        result = await engine.evaluate_event(
            sample_event,
            sample_detections,
            datetime(2025, 12, 23, 10, 0, 0),
        )

        assert result.has_triggers is True
        assert len(result.triggered_rules) == 1
        assert result.highest_severity == AlertSeverity.HIGH


# =============================================================================
# Additional Alert Engine Tests
# =============================================================================


class TestEvaluateEventWithCooldown:
    """Tests for evaluate_event with cooldown scenarios."""

    @pytest.mark.asyncio
    async def test_evaluate_event_rule_in_cooldown(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
    ) -> None:
        """Test evaluation skips rule in cooldown."""
        from backend.models import Alert

        # Mock existing alert (in cooldown)
        existing_alert = MagicMock(spec=Alert)

        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [sample_rule]

        mock_cooldown_result = MagicMock()
        mock_cooldown_result.scalar_one_or_none.return_value = existing_alert

        mock_session.execute.side_effect = [mock_rules_result, mock_cooldown_result]

        engine = AlertRuleEngine(mock_session)
        result = await engine.evaluate_event(
            sample_event,
            sample_detections,
            datetime(2025, 12, 23, 10, 0, 0),
        )

        assert result.has_triggers is False
        assert len(result.skipped_rules) == 1
        assert result.skipped_rules[0][1] == "in_cooldown"


class TestEvaluateRuleWithSchedule:
    """Tests for _evaluate_rule with schedule conditions."""

    @pytest.mark.asyncio
    async def test_rule_matches_schedule(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
    ) -> None:
        """Test rule matches when within schedule."""
        sample_rule.risk_threshold = None
        sample_rule.schedule = {
            "start_time": "08:00",
            "end_time": "12:00",
        }

        engine = AlertRuleEngine(mock_session)
        matches, conditions = await engine._evaluate_rule(
            sample_rule,
            sample_event,
            sample_detections,
            datetime(2025, 12, 23, 10, 0, 0),
        )
        assert matches is True
        assert "within_schedule" in conditions

    @pytest.mark.asyncio
    async def test_rule_fails_schedule(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
    ) -> None:
        """Test rule fails when outside schedule."""
        sample_rule.risk_threshold = None
        sample_rule.schedule = {
            "start_time": "22:00",
            "end_time": "06:00",  # Overnight schedule
        }

        engine = AlertRuleEngine(mock_session)
        matches, _conditions = await engine._evaluate_rule(
            sample_rule,
            sample_event,
            sample_detections,
            datetime(2025, 12, 23, 10, 0, 0),  # 10 AM - outside overnight window
        )
        assert matches is False


class TestScheduleWithDays:
    """Tests for schedule with day-of-week restrictions."""

    def test_check_schedule_with_days_matching(self, mock_session: AsyncMock) -> None:
        """Test schedule with matching day."""
        engine = AlertRuleEngine(mock_session)
        schedule = {
            "days": ["monday", "tuesday"],
            "start_time": "09:00",
            "end_time": "17:00",
        }
        # December 23, 2025 is a Tuesday
        current_time = datetime(2025, 12, 23, 10, 0, 0)
        result = engine._check_schedule(schedule, current_time)
        assert result is True

    def test_check_schedule_with_days_not_matching(self, mock_session: AsyncMock) -> None:
        """Test schedule with non-matching day."""
        engine = AlertRuleEngine(mock_session)
        schedule = {
            "days": ["saturday", "sunday"],
            "start_time": "09:00",
            "end_time": "17:00",
        }
        # December 23, 2025 is a Tuesday
        current_time = datetime(2025, 12, 23, 10, 0, 0)
        result = engine._check_schedule(schedule, current_time)
        assert result is False


class TestScheduleWithTimezone:
    """Tests for schedule with timezone."""

    def test_check_schedule_invalid_timezone(self, mock_session: AsyncMock) -> None:
        """Test schedule with invalid timezone falls back to UTC."""
        engine = AlertRuleEngine(mock_session)
        schedule = {
            "timezone": "Invalid/Timezone",
            "start_time": "09:00",
            "end_time": "17:00",
        }
        current_time = datetime(2025, 12, 23, 10, 0, 0)
        # Should not raise, should use UTC
        result = engine._check_schedule(schedule, current_time)
        assert result is True


class TestScheduleOvernightRange:
    """Tests for overnight schedule ranges."""

    def test_check_schedule_overnight_during_night(self, mock_session: AsyncMock) -> None:
        """Test overnight schedule during night hours."""
        engine = AlertRuleEngine(mock_session)
        schedule = {
            "start_time": "22:00",
            "end_time": "06:00",
        }
        # 2 AM should match overnight schedule
        current_time = datetime(2025, 12, 23, 2, 0, 0)
        result = engine._check_schedule(schedule, current_time)
        assert result is True

    def test_check_schedule_overnight_during_day(self, mock_session: AsyncMock) -> None:
        """Test overnight schedule during day hours."""
        engine = AlertRuleEngine(mock_session)
        schedule = {
            "start_time": "22:00",
            "end_time": "06:00",
        }
        # 10 AM should NOT match overnight schedule
        current_time = datetime(2025, 12, 23, 10, 0, 0)
        result = engine._check_schedule(schedule, current_time)
        assert result is False


class TestBuildDedupKey:
    """Tests for _build_dedup_key method."""

    def test_build_dedup_key_with_detections(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
    ) -> None:
        """Test building dedup key with detections."""
        sample_rule.dedup_key_template = "{camera_id}:{object_type}"
        engine = AlertRuleEngine(mock_session)
        key = engine._build_dedup_key(sample_rule, sample_event, sample_detections)
        assert key == "cam-front:person"

    def test_build_dedup_key_no_detections(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_rule: AlertRule,
    ) -> None:
        """Test building dedup key without detections."""
        sample_rule.dedup_key_template = "{camera_id}:{object_type}"
        engine = AlertRuleEngine(mock_session)
        key = engine._build_dedup_key(sample_rule, sample_event, [])
        assert key == "cam-front:unknown"

    def test_build_dedup_key_default_template(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_rule: AlertRule,
    ) -> None:
        """Test building dedup key with default template."""
        sample_rule.dedup_key_template = None
        engine = AlertRuleEngine(mock_session)
        key = engine._build_dedup_key(sample_rule, sample_event, [])
        assert sample_event.camera_id in key
        assert sample_rule.id in key

    def test_build_dedup_key_invalid_template(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_rule: AlertRule,
    ) -> None:
        """Test building dedup key with invalid template variable."""
        sample_rule.dedup_key_template = "{invalid_variable}"
        engine = AlertRuleEngine(mock_session)
        key = engine._build_dedup_key(sample_rule, sample_event, [])
        # Should fallback to default key
        assert sample_event.camera_id in key


class TestCreateAlertsForEvent:
    """Tests for create_alerts_for_event method."""

    @pytest.mark.asyncio
    async def test_create_alerts_success(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_rule: AlertRule,
    ) -> None:
        """Test creating alerts for triggered rules."""
        triggered = TriggeredRule(
            rule=sample_rule,
            severity=AlertSeverity.HIGH,
            matched_conditions=["test_condition"],
            dedup_key="test_key",
        )

        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        engine = AlertRuleEngine(mock_session)
        alerts = await engine.create_alerts_for_event(sample_event, [triggered])

        assert len(alerts) == 1
        assert alerts[0].event_id == sample_event.id
        assert alerts[0].rule_id == sample_rule.id
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()


class TestTestRuleAgainstEvents:
    """Tests for test_rule_against_events method."""

    @pytest.mark.asyncio
    async def test_test_rule_against_events(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_rule: AlertRule,
    ) -> None:
        """Test testing a rule against historical events."""
        # Mock detection loading
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        sample_event.detection_ids = None

        engine = AlertRuleEngine(mock_session)
        results = await engine.test_rule_against_events(
            sample_rule, [sample_event], datetime(2025, 12, 23, 10, 0, 0)
        )

        assert len(results) == 1
        assert results[0]["event_id"] == sample_event.id
        assert results[0]["camera_id"] == sample_event.camera_id


class TestGetAlertEngine:
    """Tests for get_alert_engine convenience function."""

    @pytest.mark.asyncio
    async def test_get_alert_engine(self, mock_session: AsyncMock) -> None:
        """Test get_alert_engine returns engine instance."""
        from backend.services.alert_engine import get_alert_engine

        engine = await get_alert_engine(mock_session)
        assert isinstance(engine, AlertRuleEngine)
        assert engine.session == mock_session


class TestEvaluateEventWithNullDetections:
    """Tests for evaluate_event loading detections."""

    @pytest.mark.asyncio
    async def test_evaluate_event_loads_detections(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
    ) -> None:
        """Test evaluation loads detections when not provided."""
        # First call - detection loading
        mock_detection_result = MagicMock()
        mock_detection_result.scalars.return_value.all.return_value = sample_detections

        # Second call - rules loading
        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [sample_rule]

        # Third call - cooldown check
        mock_cooldown_result = MagicMock()
        mock_cooldown_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [
            mock_detection_result,
            mock_rules_result,
            mock_cooldown_result,
        ]

        engine = AlertRuleEngine(mock_session)
        # Pass None for detections to force loading
        result = await engine.evaluate_event(
            sample_event,
            None,
            datetime(2025, 12, 23, 10, 0, 0),
        )

        assert result.has_triggers is True


class TestEvaluateRuleWithObjectTypes:
    """Tests for rule evaluation with object type conditions."""

    @pytest.mark.asyncio
    async def test_rule_matches_object_types(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
    ) -> None:
        """Test rule matches object types."""
        sample_rule.risk_threshold = None
        sample_rule.object_types = ["person", "vehicle"]

        engine = AlertRuleEngine(mock_session)
        matches, conditions = await engine._evaluate_rule(
            sample_rule,
            sample_event,
            sample_detections,
            datetime(2025, 12, 23, 10, 0, 0),
        )
        assert matches is True
        assert any("object_type" in c for c in conditions)

    @pytest.mark.asyncio
    async def test_rule_fails_object_types(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
    ) -> None:
        """Test rule fails when object types don't match."""
        sample_rule.risk_threshold = None
        sample_rule.object_types = ["animal"]

        engine = AlertRuleEngine(mock_session)
        matches, _conditions = await engine._evaluate_rule(
            sample_rule,
            sample_event,
            sample_detections,
            datetime(2025, 12, 23, 10, 0, 0),
        )
        assert matches is False


class TestEvaluateRuleWithMinConfidence:
    """Tests for rule evaluation with min_confidence condition."""

    @pytest.mark.asyncio
    async def test_rule_matches_min_confidence(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
    ) -> None:
        """Test rule matches min_confidence."""
        sample_rule.risk_threshold = None
        sample_rule.min_confidence = 0.85

        engine = AlertRuleEngine(mock_session)
        matches, conditions = await engine._evaluate_rule(
            sample_rule,
            sample_event,
            sample_detections,
            datetime(2025, 12, 23, 10, 0, 0),
        )
        assert matches is True
        assert any("confidence" in c for c in conditions)

    @pytest.mark.asyncio
    async def test_rule_fails_min_confidence(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
    ) -> None:
        """Test rule fails when confidence below threshold."""
        sample_rule.risk_threshold = None
        sample_rule.min_confidence = 0.99

        engine = AlertRuleEngine(mock_session)
        matches, _conditions = await engine._evaluate_rule(
            sample_rule,
            sample_event,
            sample_detections,
            datetime(2025, 12, 23, 10, 0, 0),
        )
        assert matches is False


class TestEvaluateRuleWithZoneIds:
    """Tests for rule evaluation with zone_ids condition."""

    @pytest.mark.asyncio
    async def test_rule_with_zone_ids_logs_debug(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
    ) -> None:
        """Test rule with zone_ids condition (not yet implemented)."""
        sample_rule.risk_threshold = None
        sample_rule.zone_ids = ["zone-1", "zone-2"]

        engine = AlertRuleEngine(mock_session)
        # Should not fail, zone matching is not yet implemented
        matches, _conditions = await engine._evaluate_rule(
            sample_rule,
            sample_event,
            sample_detections,
            datetime(2025, 12, 23, 10, 0, 0),
        )
        # Rule matches because no other conditions fail
        assert matches is True


class TestEvaluateEventRuleEvaluationError:
    """Tests for evaluate_event with rule evaluation errors."""

    @pytest.mark.asyncio
    async def test_evaluate_event_handles_rule_error(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        sample_rule: AlertRule,
    ) -> None:
        """Test evaluation handles rule errors gracefully."""
        # Make the rule cause an error during evaluation
        sample_rule.risk_threshold = "invalid"  # Will cause comparison error

        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [sample_rule]

        mock_session.execute.return_value = mock_rules_result

        engine = AlertRuleEngine(mock_session)
        result = await engine.evaluate_event(
            sample_event,
            sample_detections,
            datetime(2025, 12, 23, 10, 0, 0),
        )

        # Rule error should be caught, rule skipped
        assert len(result.skipped_rules) == 1
        assert "evaluation_error" in result.skipped_rules[0][1]


class TestParseTime:
    """Tests for _parse_time helper method."""

    def test_parse_time_valid(self, mock_session: AsyncMock) -> None:
        """Test parsing valid time string."""
        engine = AlertRuleEngine(mock_session)
        result = engine._parse_time("14:30")
        assert result.hour == 14
        assert result.minute == 30

    def test_parse_time_midnight(self, mock_session: AsyncMock) -> None:
        """Test parsing midnight."""
        engine = AlertRuleEngine(mock_session)
        result = engine._parse_time("00:00")
        assert result.hour == 0
        assert result.minute == 0


class TestLoadEventDetectionsNotList:
    """Tests for _load_event_detections with non-list JSON."""

    @pytest.mark.asyncio
    async def test_load_detections_not_list(
        self, mock_session: AsyncMock, sample_event: Event
    ) -> None:
        """Test loading detections when JSON is not a list."""
        sample_event.detection_ids = '{"id": 1}'  # Valid JSON but not a list
        engine = AlertRuleEngine(mock_session)
        detections = await engine._load_event_detections(sample_event)
        assert detections == []

    @pytest.mark.asyncio
    async def test_load_detections_empty_list(
        self, mock_session: AsyncMock, sample_event: Event
    ) -> None:
        """Test loading detections with empty list."""
        sample_event.detection_ids = "[]"
        engine = AlertRuleEngine(mock_session)
        detections = await engine._load_event_detections(sample_event)
        assert detections == []
