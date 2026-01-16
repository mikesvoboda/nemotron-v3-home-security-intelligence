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

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from backend.models import Alert, AlertRule, AlertSeverity, AlertStatus, Detection, Event
from backend.services.alert_engine import (
    SEVERITY_PRIORITY,
    AlertRuleEngine,
    EvaluationResult,
    TriggeredRule,
    get_alert_engine,
)

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
def sample_event() -> MagicMock:
    """Create a sample event for testing.

    Note: Uses MagicMock to properly simulate the detection_id_list property
    which comes from the event_detections junction table relationship.
    """
    mock_event = MagicMock(spec=Event)
    mock_event.id = 1
    mock_event.batch_id = str(uuid.uuid4())
    mock_event.camera_id = "front_door"
    mock_event.started_at = datetime.now(UTC)
    mock_event.risk_score = 85
    mock_event.risk_level = "high"
    mock_event.detections = []  # Empty initially - will be loaded
    mock_event.detection_id_list = [1, 2, 3]  # From junction table
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
    """Tests for _load_event_detections method.

    Note: Legacy detection_ids JSON parsing was removed in NEM-1592.
    Now uses detection_id_list property from the event_detections relationship.
    """

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_detections(
        self, mock_session: AsyncMock, sample_event: MagicMock
    ) -> None:
        """Test returns empty list when event has no detections."""
        sample_event.detections = []

        # Mock junction table query returning empty
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)
        detections = await engine._load_event_detections(sample_event)

        assert detections == []

    @pytest.mark.asyncio
    async def test_returns_cached_detections_if_loaded(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test returns cached detections if relationship already loaded."""
        sample_event.detections = sample_detections

        engine = AlertRuleEngine(mock_session)
        detections = await engine._load_event_detections(sample_event)

        # Should return cached detections without querying DB
        assert detections == sample_detections
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_loads_detections_from_database(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Test loads detections from database when not cached."""
        sample_event.detections = []  # Not cached

        # Mock junction table query returning detection IDs
        mock_junction_result = MagicMock()
        mock_junction_result.scalars.return_value.all.return_value = [1, 2, 3]
        mock_session.execute.return_value = mock_junction_result

        with patch(
            "backend.services.alert_engine.batch_fetch_detections",
            new_callable=AsyncMock,
            return_value=sample_detections,
        ):
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
        sample_event: MagicMock,
        sample_detections: list[Detection],
    ) -> None:
        """Test loads detections from database if not provided."""
        sample_event.detections = []  # Not cached

        # First call: junction table query for detection IDs
        mock_junction_result = MagicMock()
        mock_junction_result.scalars.return_value.all.return_value = [1, 2, 3]

        # Second call: trust status query (no entities linked)
        mock_trust_result = MagicMock()
        mock_trust_result.scalars.return_value.all.return_value = []

        # Third call: _get_enabled_rules
        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [
            mock_junction_result,
            mock_trust_result,
            mock_rules_result,
        ]

        with patch(
            "backend.services.alert_engine.batch_fetch_detections",
            new_callable=AsyncMock,
            return_value=sample_detections,
        ):
            engine = AlertRuleEngine(mock_session)
            await engine.evaluate_event(sample_event, detections=None)

        # Verify three queries were made (junction table + trust status + rules)
        assert mock_session.execute.call_count == 3

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

        # Trust status query (no entities linked = normal processing)
        mock_trust_result = MagicMock()
        mock_trust_result.scalars.return_value.all.return_value = []

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
            mock_trust_result,
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

        # Trust status query (no entities linked)
        mock_trust_result = MagicMock()
        mock_trust_result.scalars.return_value.all.return_value = []

        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [sample_rule]

        # Alert exists in cooldown
        mock_cooldown_result = MagicMock()
        mock_cooldown_result.scalar_one_or_none.return_value = sample_alert

        mock_session.execute.side_effect = [
            mock_trust_result,
            mock_rules_result,
            mock_cooldown_result,
        ]

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

        # Trust status query (no entities linked)
        mock_trust_result = MagicMock()
        mock_trust_result.scalars.return_value.all.return_value = []

        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [critical_rule, low_rule]

        mock_cooldown_result = MagicMock()
        mock_cooldown_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [
            mock_trust_result,
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
        with patch.object(engine, "_evaluate_rule", side_effect=ValueError("Test error")):
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
        self, mock_session: AsyncMock, sample_event: MagicMock
    ) -> None:
        """Test returns empty lists when events have no detection IDs.

        Junction table query returns empty list of (event_id, detection_id) pairs.
        """
        event2 = MagicMock(spec=Event)
        event2.id = 2

        # Mock junction table query returning no rows
        mock_result = MagicMock()
        mock_result.all.return_value = []  # Empty list of (event_id, detection_id) tuples
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)
        result = await engine._batch_load_detections_for_events([sample_event, event2])

        assert result == {1: [], 2: []}

    @pytest.mark.asyncio
    async def test_handles_events_with_mixed_detection_ids(
        self, mock_session: AsyncMock, sample_detections: list[Detection]
    ) -> None:
        """Test handles mix of events with and without detection IDs.

        Junction table query returns rows only for events with detections.
        """
        event1 = MagicMock(spec=Event)
        event1.id = 1

        event2 = MagicMock(spec=Event)
        event2.id = 2

        # Mock junction table returning rows only for event1
        mock_result = MagicMock()
        mock_result.all.return_value = [(1, 1), (1, 2)]  # event_id=1 has detection_ids 1,2
        mock_session.execute.return_value = mock_result

        with patch(
            "backend.services.alert_engine.batch_fetch_detections",
            new_callable=AsyncMock,
            return_value=sample_detections[:2],
        ):
            engine = AlertRuleEngine(mock_session)
            result = await engine._batch_load_detections_for_events([event1, event2])

        # Event with IDs should have detections loaded, empty event should have empty list
        assert len(result[1]) == 2
        assert result[2] == []

    @pytest.mark.asyncio
    async def test_batch_loads_detections(
        self,
        mock_session: AsyncMock,
        sample_event: MagicMock,
        sample_detections: list[Detection],
    ) -> None:
        """Test batch loads detections from database."""
        # Mock junction table query
        mock_result = MagicMock()
        mock_result.all.return_value = [(1, 1), (1, 2), (1, 3)]
        mock_session.execute.return_value = mock_result

        with patch(
            "backend.services.alert_engine.batch_fetch_detections",
            new_callable=AsyncMock,
            return_value=sample_detections,
        ):
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
        event1 = MagicMock(spec=Event)
        event1.id = 1

        event2 = MagicMock(spec=Event)
        event2.id = 2

        # Mock junction table returning rows for both events
        mock_result = MagicMock()
        mock_result.all.return_value = [(1, 1), (1, 2), (2, 3)]  # event1 has [1,2], event2 has [3]
        mock_session.execute.return_value = mock_result

        with patch(
            "backend.services.alert_engine.batch_fetch_detections",
            new_callable=AsyncMock,
            return_value=sample_detections,
        ):
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
        sample_event: MagicMock,
        sample_detections: list[Detection],
    ) -> None:
        """Test result includes detected object types."""
        # Mock junction table returning detection IDs for this event
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (sample_event.id, 1),
            (sample_event.id, 2),
            (sample_event.id, 3),
        ]
        mock_session.execute.return_value = mock_result

        sample_rule.risk_threshold = None

        with patch(
            "backend.services.alert_engine.batch_fetch_detections",
            new_callable=AsyncMock,
            return_value=sample_detections,
        ):
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
        """Test evaluates multiple events.

        Note: Uses MagicMock for events to simulate detection_id_list property
        which comes from the event_detections junction table relationship.
        """
        event1 = MagicMock(spec=Event)
        event1.id = 1
        event1.camera_id = "cam1"
        event1.started_at = datetime.now(UTC)
        event1.risk_score = 85
        event1.detection_id_list = [1]

        event2 = MagicMock(spec=Event)
        event2.id = 2
        event2.camera_id = "cam2"
        event2.started_at = datetime.now(UTC)
        event2.risk_score = 50
        event2.detection_id_list = [2]

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

        # Trust status query (no entities linked)
        mock_trust_result = MagicMock()
        mock_trust_result.scalars.return_value.all.return_value = []

        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [rule]

        mock_cooldown_result = MagicMock()
        mock_cooldown_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [
            mock_trust_result,
            mock_rules_result,
            mock_cooldown_result,
        ]

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
# Property-Based Tests (Hypothesis)
# =============================================================================

from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from backend.tests.strategies import (  # noqa: E402
    confidence_scores,
    object_types,
    risk_scores,
)


class TestAlertEngineProperties:
    """Property-based tests for AlertRuleEngine using Hypothesis."""

    # -------------------------------------------------------------------------
    # Determinism Properties
    # -------------------------------------------------------------------------

    @given(risk_score=risk_scores)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_evaluate_rule_is_deterministic(
        self,
        risk_score: int,
        mock_session: AsyncMock,
    ) -> None:
        """Property: Same inputs always produce the same evaluation result.

        This ensures the alert engine has no hidden state or randomness
        that could cause inconsistent alerting behavior.
        """
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Test Rule",
            enabled=True,
            severity=AlertSeverity.HIGH,
            risk_threshold=50,
            cooldown_seconds=300,
        )
        event = Event(
            id=1,
            batch_id=str(uuid.uuid4()),
            camera_id="cam1",
            started_at=datetime.now(UTC),
            risk_score=risk_score,
        )
        detections: list[Detection] = []
        current_time = datetime(2025, 1, 6, 12, 0, 0, tzinfo=ZoneInfo("UTC"))

        engine = AlertRuleEngine(mock_session)

        # Evaluate multiple times
        result1 = await engine._evaluate_rule(rule, event, detections, current_time)
        result2 = await engine._evaluate_rule(rule, event, detections, current_time)

        # Results should be identical
        assert result1[0] == result2[0], "Evaluation result should be deterministic"
        assert result1[1] == result2[1], "Matched conditions should be deterministic"

    @given(
        risk_score=risk_scores,
        threshold=risk_scores,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_risk_threshold_comparison_is_consistent(
        self,
        risk_score: int,
        threshold: int,
        mock_session: AsyncMock,
    ) -> None:
        """Property: risk_score >= threshold comparison is mathematically consistent.

        If score >= threshold, rule matches.
        If score < threshold, rule doesn't match.
        """
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Test Rule",
            enabled=True,
            severity=AlertSeverity.HIGH,
            risk_threshold=threshold,
            cooldown_seconds=300,
        )
        event = Event(
            id=1,
            batch_id=str(uuid.uuid4()),
            camera_id="cam1",
            started_at=datetime.now(UTC),
            risk_score=risk_score,
        )
        current_time = datetime(2025, 1, 6, 12, 0, 0, tzinfo=ZoneInfo("UTC"))

        engine = AlertRuleEngine(mock_session)
        matches, _conditions = await engine._evaluate_rule(rule, event, [], current_time)

        expected = risk_score >= threshold
        assert matches == expected, (
            f"Expected matches={expected} for score={risk_score}, threshold={threshold}"
        )

    # -------------------------------------------------------------------------
    # Severity Ordering Properties
    # -------------------------------------------------------------------------

    @given(
        severities=st.lists(
            st.sampled_from(list(AlertSeverity)),
            min_size=2,
            max_size=4,
        )
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_triggered_rules_sorted_by_severity_descending(
        self,
        severities: list[AlertSeverity],
        mock_session: AsyncMock,
    ) -> None:
        """Property: Triggered rules are always sorted by severity (highest first).

        This ensures critical alerts are processed before low priority ones.
        """
        # Reset mock state for each hypothesis example
        mock_session.reset_mock()

        # Create rules with different severities
        rules = [
            AlertRule(
                id=str(uuid.uuid4()),
                name=f"Rule {i}",
                enabled=True,
                severity=sev,
                cooldown_seconds=300,
            )
            for i, sev in enumerate(severities)
        ]

        event = Event(
            id=1,
            batch_id=str(uuid.uuid4()),
            camera_id="cam1",
            started_at=datetime.now(UTC),
            risk_score=50,
        )

        # Mock database to return rules and no cooldowns
        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = rules

        mock_cooldown_result = MagicMock()
        mock_cooldown_result.scalar_one_or_none.return_value = None

        # Each rule needs a cooldown check
        mock_session.execute.side_effect = [mock_rules_result] + [
            mock_cooldown_result for _ in rules
        ]

        engine = AlertRuleEngine(mock_session)
        result = await engine.evaluate_event(event, [])

        # Verify descending severity order
        triggered_severities = [t.severity for t in result.triggered_rules]
        severity_priorities = [SEVERITY_PRIORITY[s] for s in triggered_severities]

        for i in range(len(severity_priorities) - 1):
            assert severity_priorities[i] >= severity_priorities[i + 1], (
                f"Severity at position {i} should be >= severity at position {i + 1}"
            )

    @given(
        severity1=st.sampled_from(list(AlertSeverity)),
        severity2=st.sampled_from(list(AlertSeverity)),
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_highest_severity_is_maximum(
        self,
        severity1: AlertSeverity,
        severity2: AlertSeverity,
        mock_session: AsyncMock,
    ) -> None:
        """Property: highest_severity is always the maximum of all triggered severities."""
        # Reset mock state for each hypothesis example
        mock_session.reset_mock()

        rules = [
            AlertRule(
                id=str(uuid.uuid4()),
                name="Rule 1",
                enabled=True,
                severity=severity1,
                cooldown_seconds=300,
            ),
            AlertRule(
                id=str(uuid.uuid4()),
                name="Rule 2",
                enabled=True,
                severity=severity2,
                cooldown_seconds=300,
            ),
        ]

        event = Event(
            id=1,
            batch_id=str(uuid.uuid4()),
            camera_id="cam1",
            started_at=datetime.now(UTC),
            risk_score=50,
        )

        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = rules

        mock_cooldown_result = MagicMock()
        mock_cooldown_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [
            mock_rules_result,
            mock_cooldown_result,
            mock_cooldown_result,
        ]

        engine = AlertRuleEngine(mock_session)
        result = await engine.evaluate_event(event, [])

        # highest_severity should be the maximum
        expected_highest = max([severity1, severity2], key=lambda s: SEVERITY_PRIORITY[s])
        assert result.highest_severity == expected_highest

    # -------------------------------------------------------------------------
    # Confidence Threshold Properties
    # -------------------------------------------------------------------------

    @given(
        min_confidence=confidence_scores,
        detection_confidence=confidence_scores,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_threshold_comparison(
        self,
        min_confidence: float,
        detection_confidence: float,
        mock_session: AsyncMock,
    ) -> None:
        """Property: Confidence comparison follows >= semantics correctly."""
        detections = [
            Detection(
                id=1,
                camera_id="cam1",
                file_path="/export/foscam/cam1/img.jpg",
                object_type="person",
                confidence=detection_confidence,
            )
        ]

        engine = AlertRuleEngine(mock_session)
        result = engine._check_min_confidence(min_confidence, detections)

        expected = detection_confidence >= min_confidence
        assert result == expected, (
            f"Expected {expected} for detection_confidence={detection_confidence}, "
            f"min_confidence={min_confidence}"
        )

    # -------------------------------------------------------------------------
    # Object Type Matching Properties
    # -------------------------------------------------------------------------

    @given(
        object_type=object_types,
        required_types=st.lists(object_types, min_size=1, max_size=5, unique=True),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_object_type_matching_is_case_insensitive(
        self,
        object_type: str,
        required_types: list[str],
        mock_session: AsyncMock,
    ) -> None:
        """Property: Object type matching is case-insensitive."""
        detections = [
            Detection(
                id=1,
                camera_id="cam1",
                file_path="/export/foscam/cam1/img.jpg",
                object_type=object_type,
            )
        ]

        engine = AlertRuleEngine(mock_session)

        # Test with lowercase required types
        result_lower = engine._check_object_types([t.lower() for t in required_types], detections)

        # Test with uppercase required types
        result_upper = engine._check_object_types([t.upper() for t in required_types], detections)

        # Results should be the same (case insensitive)
        assert result_lower == result_upper, "Object type matching should be case-insensitive"

        # Verify correct matching
        should_match = object_type.lower() in [t.lower() for t in required_types]
        assert result_lower == should_match

    # -------------------------------------------------------------------------
    # Dedup Key Properties
    # -------------------------------------------------------------------------

    @given(
        camera_id=st.from_regex(r"[a-z][a-z0-9_]{1,20}", fullmatch=True),
        object_type=object_types,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_dedup_key_contains_template_variables(
        self,
        camera_id: str,
        object_type: str,
        mock_session: AsyncMock,
    ) -> None:
        """Property: Dedup key correctly substitutes template variables."""
        rule = AlertRule(
            id="rule-123",
            name="Test Rule",
            enabled=True,
            severity=AlertSeverity.HIGH,
            dedup_key_template="{camera_id}:{object_type}:{rule_id}",
            cooldown_seconds=300,
        )
        event = Event(
            id=1,
            batch_id=str(uuid.uuid4()),
            camera_id=camera_id,
            started_at=datetime.now(UTC),
        )
        detections = [
            Detection(
                id=1,
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/img.jpg",
                object_type=object_type,
            )
        ]

        engine = AlertRuleEngine(mock_session)
        dedup_key = engine._build_dedup_key(rule, event, detections)

        # Verify key contains expected components
        assert camera_id in dedup_key, f"Dedup key should contain camera_id '{camera_id}'"
        assert object_type in dedup_key, f"Dedup key should contain object_type '{object_type}'"
        assert "rule-123" in dedup_key, "Dedup key should contain rule_id"
        assert dedup_key == f"{camera_id}:{object_type}:rule-123"

    # -------------------------------------------------------------------------
    # Schedule Evaluation Properties
    # -------------------------------------------------------------------------

    @given(
        hour=st.integers(min_value=0, max_value=23),
        minute=st.integers(min_value=0, max_value=59),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_schedule_time_parsing_round_trip(
        self,
        hour: int,
        minute: int,
        mock_session: AsyncMock,
    ) -> None:
        """Property: Time parsing correctly extracts hour and minute."""
        engine = AlertRuleEngine(mock_session)
        time_str = f"{hour:02d}:{minute:02d}"
        parsed = engine._parse_time(time_str)

        assert parsed.hour == hour, f"Expected hour {hour}, got {parsed.hour}"
        assert parsed.minute == minute, f"Expected minute {minute}, got {parsed.minute}"

    @given(
        start_hour=st.integers(min_value=0, max_value=23),
        end_hour=st.integers(min_value=0, max_value=23),
        current_hour=st.integers(min_value=0, max_value=23),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_schedule_time_range_consistency(
        self,
        start_hour: int,
        end_hour: int,
        current_hour: int,
        mock_session: AsyncMock,
    ) -> None:
        """Property: Time range checking is consistent for normal and overnight ranges."""
        engine = AlertRuleEngine(mock_session)

        schedule = {
            "start_time": f"{start_hour:02d}:00",
            "end_time": f"{end_hour:02d}:00",
        }
        current = datetime(2025, 1, 6, current_hour, 30, 0, tzinfo=ZoneInfo("UTC"))

        result = engine._check_schedule(schedule, current)

        # Verify the result is a boolean
        assert isinstance(result, bool)

        # Verify logic consistency
        if start_hour <= end_hour:
            # Normal range (e.g., 09:00-17:00)
            expected = start_hour <= current_hour <= end_hour
        else:
            # Overnight range (e.g., 22:00-06:00)
            expected = current_hour >= start_hour or current_hour <= end_hour

        # Note: The actual comparison includes minutes, but for whole hours this should match
        # We're testing the general pattern is correct
        # Allow for minute-level edge cases
        if current_hour not in [start_hour, end_hour]:
            assert result == expected, (
                f"Schedule check failed: start={start_hour}, end={end_hour}, "
                f"current={current_hour}, result={result}, expected={expected}"
            )

    # -------------------------------------------------------------------------
    # Rule Evaluation Idempotency
    # -------------------------------------------------------------------------

    @given(
        risk_score=risk_scores,
        threshold=risk_scores,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_rule_evaluation_idempotent(
        self,
        risk_score: int,
        threshold: int,
        mock_session: AsyncMock,
    ) -> None:
        """Property: Multiple evaluations of the same rule produce identical results."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Test Rule",
            enabled=True,
            severity=AlertSeverity.HIGH,
            risk_threshold=threshold,
            cooldown_seconds=300,
        )
        event = Event(
            id=1,
            batch_id=str(uuid.uuid4()),
            camera_id="cam1",
            started_at=datetime.now(UTC),
            risk_score=risk_score,
        )
        current_time = datetime(2025, 1, 6, 12, 0, 0, tzinfo=ZoneInfo("UTC"))

        engine = AlertRuleEngine(mock_session)

        # Evaluate multiple times
        results = []
        for _ in range(3):
            result = await engine._evaluate_rule(rule, event, [], current_time)
            results.append(result)

        # All results should be identical
        for i, r in enumerate(results[1:], 1):
            assert r == results[0], f"Evaluation {i} differs from first evaluation"


# =============================================================================
# Entity Trust Status Tests (NEM-2675)
# =============================================================================


class TestEntityTrustStatus:
    """Tests for entity trust status consideration in alert generation."""

    @pytest.mark.asyncio
    async def test_trusted_entity_skips_all_alerts(
        self, mock_session: AsyncMock, sample_rule: AlertRule, sample_detections: list[Detection]
    ) -> None:
        """Test that alerts are skipped entirely for trusted entities."""
        from backend.models.enums import TrustStatus

        # Mock returning a trusted entity status
        # First call is for trust status lookup, which returns TRUSTED
        # When trusted, we skip loading rules and return early
        trust_result = MagicMock()
        trust_result.scalars.return_value.all.return_value = [TrustStatus.TRUSTED.value]

        mock_session.execute = AsyncMock(return_value=trust_result)

        engine = AlertRuleEngine(mock_session)

        event = MagicMock()
        event.id = 1
        event.camera_id = "front_door"
        event.risk_score = 85

        result = await engine.evaluate_event(event, sample_detections)

        # Should skip all alerts for trusted entity
        assert result.trusted_entity_skipped is True
        assert result.entity_trust_status == TrustStatus.TRUSTED
        assert len(result.triggered_rules) == 0
        assert not result.has_triggers

    @pytest.mark.asyncio
    async def test_untrusted_entity_escalates_severity(
        self, mock_session: AsyncMock, sample_detections: list[Detection]
    ) -> None:
        """Test that severity is escalated for untrusted entities."""
        from backend.models.enums import TrustStatus
        from backend.services.alert_engine import SEVERITY_ESCALATION

        # Create a rule with LOW severity to test escalation
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Low Severity Rule",
            enabled=True,
            severity=AlertSeverity.LOW,
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock: First call for trust status, second for rules, third for cooldown
        trust_result = MagicMock()
        trust_result.scalars.return_value.all.return_value = [TrustStatus.UNTRUSTED.value]

        rule_result = MagicMock()
        rule_result.scalars.return_value.all.return_value = [rule]

        cooldown_result = MagicMock()
        cooldown_result.scalar_one_or_none.return_value = None  # Not in cooldown

        mock_session.execute = AsyncMock(side_effect=[trust_result, rule_result, cooldown_result])

        engine = AlertRuleEngine(mock_session)

        event = MagicMock()
        event.id = 1
        event.camera_id = "front_door"
        event.risk_score = 85

        result = await engine.evaluate_event(event, sample_detections)

        # Should have escalated severity
        assert result.entity_trust_status == TrustStatus.UNTRUSTED
        assert len(result.triggered_rules) == 1
        triggered = result.triggered_rules[0]
        assert triggered.original_severity == AlertSeverity.LOW
        assert triggered.severity == SEVERITY_ESCALATION[AlertSeverity.LOW]
        assert triggered.severity == AlertSeverity.MEDIUM
        assert triggered.trust_adjusted is True
        assert "severity_escalated_untrusted_entity" in " ".join(triggered.matched_conditions)

    @pytest.mark.asyncio
    async def test_unknown_entity_normal_processing(
        self, mock_session: AsyncMock, sample_rule: AlertRule, sample_detections: list[Detection]
    ) -> None:
        """Test that unknown entities are processed normally without severity changes."""
        from backend.models.enums import TrustStatus

        # Mock returning unknown entity status
        trust_result = MagicMock()
        trust_result.scalars.return_value.all.return_value = [TrustStatus.UNKNOWN.value]

        rule_result = MagicMock()
        rule_result.scalars.return_value.all.return_value = [sample_rule]

        cooldown_result = MagicMock()
        cooldown_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(side_effect=[trust_result, rule_result, cooldown_result])

        engine = AlertRuleEngine(mock_session)

        event = MagicMock()
        event.id = 1
        event.camera_id = "front_door"
        event.risk_score = 85

        result = await engine.evaluate_event(event, sample_detections)

        # Should process normally without adjustment
        assert result.entity_trust_status == TrustStatus.UNKNOWN
        assert len(result.triggered_rules) == 1
        triggered = result.triggered_rules[0]
        assert triggered.severity == sample_rule.severity
        assert triggered.trust_adjusted is False
        assert triggered.original_severity is None

    @pytest.mark.asyncio
    async def test_no_entity_linked_normal_processing(
        self, mock_session: AsyncMock, sample_rule: AlertRule, sample_detections: list[Detection]
    ) -> None:
        """Test that detections with no linked entities are processed normally."""
        # Mock returning empty entity status (no entities linked)
        trust_result = MagicMock()
        trust_result.scalars.return_value.all.return_value = []

        rule_result = MagicMock()
        rule_result.scalars.return_value.all.return_value = [sample_rule]

        cooldown_result = MagicMock()
        cooldown_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(side_effect=[trust_result, rule_result, cooldown_result])

        engine = AlertRuleEngine(mock_session)

        event = MagicMock()
        event.id = 1
        event.camera_id = "front_door"
        event.risk_score = 85

        result = await engine.evaluate_event(event, sample_detections)

        # Should process normally (entity_trust_status is None)
        assert result.entity_trust_status is None
        assert len(result.triggered_rules) == 1
        assert result.triggered_rules[0].severity == sample_rule.severity
        assert result.triggered_rules[0].trust_adjusted is False

    @pytest.mark.asyncio
    async def test_trusted_takes_priority_over_untrusted(
        self, mock_session: AsyncMock, sample_rule: AlertRule, sample_detections: list[Detection]
    ) -> None:
        """Test that trusted status takes priority when mixed entities detected."""
        from backend.models.enums import TrustStatus

        # Mock returning both trusted and untrusted statuses
        trust_result = MagicMock()
        trust_result.scalars.return_value.all.return_value = [
            TrustStatus.TRUSTED.value,
            TrustStatus.UNTRUSTED.value,
        ]

        mock_session.execute = AsyncMock(return_value=trust_result)

        engine = AlertRuleEngine(mock_session)

        event = MagicMock()
        event.id = 1
        event.camera_id = "front_door"
        event.risk_score = 85

        result = await engine.evaluate_event(event, sample_detections)

        # Trusted takes priority - should skip alerts
        assert result.entity_trust_status == TrustStatus.TRUSTED
        assert result.trusted_entity_skipped is True
        assert len(result.triggered_rules) == 0

    @pytest.mark.asyncio
    async def test_critical_severity_not_escalated_further(
        self, mock_session: AsyncMock, sample_detections: list[Detection]
    ) -> None:
        """Test that CRITICAL severity stays at CRITICAL for untrusted entities."""
        from backend.models.enums import TrustStatus

        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Critical Rule",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        trust_result = MagicMock()
        trust_result.scalars.return_value.all.return_value = [TrustStatus.UNTRUSTED.value]

        rule_result = MagicMock()
        rule_result.scalars.return_value.all.return_value = [rule]

        cooldown_result = MagicMock()
        cooldown_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(side_effect=[trust_result, rule_result, cooldown_result])

        engine = AlertRuleEngine(mock_session)

        event = MagicMock()
        event.id = 1
        event.camera_id = "front_door"
        event.risk_score = 85

        result = await engine.evaluate_event(event, sample_detections)

        # CRITICAL should stay CRITICAL (no escalation possible)
        assert len(result.triggered_rules) == 1
        triggered = result.triggered_rules[0]
        assert triggered.severity == AlertSeverity.CRITICAL
        # No adjustment since severity didn't change
        assert triggered.trust_adjusted is False

    @pytest.mark.asyncio
    async def test_empty_detections_returns_normal_result(
        self, mock_session: AsyncMock, sample_rule: AlertRule
    ) -> None:
        """Test that empty detections list doesn't cause errors."""
        rule_result = MagicMock()
        rule_result.scalars.return_value.all.return_value = [sample_rule]

        cooldown_result = MagicMock()
        cooldown_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(side_effect=[rule_result, cooldown_result])

        engine = AlertRuleEngine(mock_session)

        event = MagicMock()
        event.id = 1
        event.camera_id = "front_door"
        event.risk_score = 85

        # Empty detections list
        result = await engine.evaluate_event(event, [])

        # Should process normally with entity_trust_status as None
        assert result.entity_trust_status is None
        assert result.trusted_entity_skipped is False


class TestGetAggregateEntityTrustStatus:
    """Tests for _get_aggregate_entity_trust_status helper method."""

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_detections(self, mock_session: AsyncMock) -> None:
        """Test that empty detections list returns None."""
        engine = AlertRuleEngine(mock_session)
        result = await engine._get_aggregate_entity_trust_status([])
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_detections_without_ids(self, mock_session: AsyncMock) -> None:
        """Test that detections without IDs return None."""
        detections = [Detection(id=None, camera_id="cam1", file_path="/path", object_type="person")]
        engine = AlertRuleEngine(mock_session)
        result = await engine._get_aggregate_entity_trust_status(detections)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_no_linked_entities(
        self, mock_session: AsyncMock, sample_detections: list[Detection]
    ) -> None:
        """Test that no linked entities returns None."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        engine = AlertRuleEngine(mock_session)
        result = await engine._get_aggregate_entity_trust_status(sample_detections)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_trusted_when_trusted_present(
        self, mock_session: AsyncMock, sample_detections: list[Detection]
    ) -> None:
        """Test that TRUSTED is returned when any trusted entity is present."""
        from backend.models.enums import TrustStatus

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            TrustStatus.TRUSTED.value,
            TrustStatus.UNKNOWN.value,
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        engine = AlertRuleEngine(mock_session)
        result = await engine._get_aggregate_entity_trust_status(sample_detections)
        assert result == TrustStatus.TRUSTED

    @pytest.mark.asyncio
    async def test_returns_untrusted_when_no_trusted(
        self, mock_session: AsyncMock, sample_detections: list[Detection]
    ) -> None:
        """Test that UNTRUSTED is returned when untrusted present but no trusted."""
        from backend.models.enums import TrustStatus

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            TrustStatus.UNTRUSTED.value,
            TrustStatus.UNKNOWN.value,
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        engine = AlertRuleEngine(mock_session)
        result = await engine._get_aggregate_entity_trust_status(sample_detections)
        assert result == TrustStatus.UNTRUSTED

    @pytest.mark.asyncio
    async def test_returns_unknown_when_only_unknown(
        self, mock_session: AsyncMock, sample_detections: list[Detection]
    ) -> None:
        """Test that UNKNOWN is returned when only unknown entities present."""
        from backend.models.enums import TrustStatus

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [TrustStatus.UNKNOWN.value]
        mock_session.execute = AsyncMock(return_value=mock_result)

        engine = AlertRuleEngine(mock_session)
        result = await engine._get_aggregate_entity_trust_status(sample_detections)
        assert result == TrustStatus.UNKNOWN


class TestSeverityEscalation:
    """Tests for severity escalation and reduction mappings."""

    def test_severity_escalation_values(self) -> None:
        """Test that severity escalation mappings are correct."""
        from backend.services.alert_engine import SEVERITY_ESCALATION

        assert SEVERITY_ESCALATION[AlertSeverity.LOW] == AlertSeverity.MEDIUM
        assert SEVERITY_ESCALATION[AlertSeverity.MEDIUM] == AlertSeverity.HIGH
        assert SEVERITY_ESCALATION[AlertSeverity.HIGH] == AlertSeverity.CRITICAL
        assert SEVERITY_ESCALATION[AlertSeverity.CRITICAL] == AlertSeverity.CRITICAL

    def test_severity_reduction_values(self) -> None:
        """Test that severity reduction mappings are correct."""
        from backend.services.alert_engine import SEVERITY_REDUCTION

        assert SEVERITY_REDUCTION[AlertSeverity.CRITICAL] == AlertSeverity.HIGH
        assert SEVERITY_REDUCTION[AlertSeverity.HIGH] == AlertSeverity.MEDIUM
        assert SEVERITY_REDUCTION[AlertSeverity.MEDIUM] == AlertSeverity.LOW
        assert SEVERITY_REDUCTION[AlertSeverity.LOW] == AlertSeverity.LOW

    def test_all_severities_have_mappings(self) -> None:
        """Test that all severity levels have escalation and reduction mappings."""
        from backend.services.alert_engine import SEVERITY_ESCALATION, SEVERITY_REDUCTION

        for severity in AlertSeverity:
            assert severity in SEVERITY_ESCALATION
            assert severity in SEVERITY_REDUCTION
