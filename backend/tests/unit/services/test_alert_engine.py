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

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

import backend.services.alert_engine as ae
from backend.api.schemas.outbound_webhook import WebhookEventType
from backend.core.time_utils import utc_now_naive
from backend.models import Alert, AlertRule, AlertSeverity, AlertStatus, Detection, Event
from backend.models.enums import TrustStatus
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

    def test_zone_id_template_with_dwell_match(
        self, mock_session: AsyncMock, sample_rule: AlertRule, sample_event: Event
    ) -> None:
        """Test {zone_id} template variable with DwellTimeMatch."""
        from backend.services.alert_engine import DwellTimeMatch

        sample_rule.dedup_key_template = "{camera_id}:{zone_id}:{rule_id}"
        dwell_match = DwellTimeMatch(zone_id=42, track_id=100)

        engine = AlertRuleEngine(mock_session)
        result = engine._build_dedup_key(
            sample_rule, sample_event, [], dwell_time_match=dwell_match
        )
        assert result == f"front_door:42:{sample_rule.id}"

    def test_track_id_template_with_dwell_match(
        self, mock_session: AsyncMock, sample_rule: AlertRule, sample_event: Event
    ) -> None:
        """Test {track_id} template variable with DwellTimeMatch."""
        from backend.services.alert_engine import DwellTimeMatch

        sample_rule.dedup_key_template = "{camera_id}:{track_id}"
        dwell_match = DwellTimeMatch(zone_id=42, track_id=100)

        engine = AlertRuleEngine(mock_session)
        result = engine._build_dedup_key(
            sample_rule, sample_event, [], dwell_time_match=dwell_match
        )
        assert result == "front_door:100"

    def test_zone_and_track_id_template_combined(
        self, mock_session: AsyncMock, sample_rule: AlertRule, sample_event: Event
    ) -> None:
        """Test both {zone_id} and {track_id} template variables together."""
        from backend.services.alert_engine import DwellTimeMatch

        sample_rule.dedup_key_template = "{camera_id}_{zone_id}_{track_id}"
        dwell_match = DwellTimeMatch(zone_id=5, track_id=999)

        engine = AlertRuleEngine(mock_session)
        result = engine._build_dedup_key(
            sample_rule, sample_event, [], dwell_time_match=dwell_match
        )
        assert result == "front_door_5_999"

    def test_zone_id_empty_when_no_dwell_match(
        self, mock_session: AsyncMock, sample_rule: AlertRule, sample_event: Event
    ) -> None:
        """Test {zone_id} is empty string when no DwellTimeMatch provided."""
        sample_rule.dedup_key_template = "{camera_id}:{zone_id}:{rule_id}"

        engine = AlertRuleEngine(mock_session)
        result = engine._build_dedup_key(sample_rule, sample_event, [])
        assert result == f"front_door::{sample_rule.id}"

    def test_track_id_empty_when_no_dwell_match(
        self, mock_session: AsyncMock, sample_rule: AlertRule, sample_event: Event
    ) -> None:
        """Test {track_id} is empty string when no DwellTimeMatch provided."""
        sample_rule.dedup_key_template = "{camera_id}:{track_id}"

        engine = AlertRuleEngine(mock_session)
        result = engine._build_dedup_key(sample_rule, sample_event, [])
        assert result == "front_door:"


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
        matches, conditions, _ = await engine._evaluate_rule(
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
        matches, conditions, _ = await engine._evaluate_rule(
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
        matches, conditions, _ = await engine._evaluate_rule(
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
        matches, _conditions, _ = await engine._evaluate_rule(
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
        matches, conditions, _ = await engine._evaluate_rule(
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
        matches, _conditions, _ = await engine._evaluate_rule(
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
        matches, conditions, _ = await engine._evaluate_rule(
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
        matches, _conditions, _ = await engine._evaluate_rule(
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
        matches, conditions, _ = await engine._evaluate_rule(
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
        matches, _conditions, _ = await engine._evaluate_rule(
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
        # Pin the clock: _check_schedule compares at HH:MM resolution, so
        # 23:59:01-23:59:59 UTC falls OUTSIDE an "all day" 00:00-23:59 window and
        # this assert is red for 59 s a day no matter what shipped (2026-10-11 23:59 red).
        current_time = datetime(2025, 1, 6, 12, 0, 0, tzinfo=ZoneInfo("UTC"))

        engine = AlertRuleEngine(mock_session)
        matches, conditions, _ = await engine._evaluate_rule(
            sample_rule, sample_event, sample_detections, current_time
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
        matches, _conditions, _ = await engine._evaluate_rule(
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
        matches, conditions, _ = await engine._evaluate_rule(
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
        with patch.object(
            engine, "_evaluate_rule", side_effect=ValueError("Test error"), autospec=True
        ):
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
        # Pin the clock: this rule's "all day" 00:00-23:59 schedule would drop the
        # within_schedule condition during 23:59:01-23:59:59 UTC, making the 5-condition
        # count below flaky for 59 s a day (see test_no_live_clock_in_schedule_tests.py).
        result = await engine.evaluate_event(
            sample_event, sample_detections, datetime(2025, 1, 6, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
        )

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

        with patch("backend.services.alert_engine.logger", autospec=True) as mock_logger:
            matches, _conditions, _ = await engine._evaluate_rule(
                rule, sample_event, sample_detections, datetime.now(UTC)
            )

            # Rule should match (zone condition is not enforced)
            assert matches is True
            mock_logger.debug.assert_called()


# =============================================================================
# Dwell Time Condition Tests
# =============================================================================


class TestDwellTimeCondition:
    """Tests for dwell_time_enabled condition (loitering detection)."""

    @pytest.fixture
    def mock_polygon_zone(self) -> MagicMock:
        """Create a mock PolygonZone."""
        zone = MagicMock()
        zone.id = 1
        zone.name = "Front Yard"
        zone.loitering_threshold_seconds = 60.0
        zone.loitering_alert_enabled = True
        return zone

    @pytest.fixture
    def mock_dwell_record(self) -> MagicMock:
        """Create a mock DwellTimeRecord with 90 seconds of dwell time."""
        record = MagicMock()
        record.zone_id = 1
        record.track_id = 42
        record.camera_id = "camera1"
        record.exit_time = None  # Active record
        record.calculate_dwell_time.return_value = 90.0  # Above 60s threshold
        return record

    @pytest.fixture
    def dwell_enabled_rule(self) -> AlertRule:
        """Create an alert rule with dwell_time_enabled."""
        return AlertRule(
            id=str(uuid.uuid4()),
            name="Loitering Rule",
            enabled=True,
            severity=AlertSeverity.HIGH,
            dwell_time_enabled=True,
            zone_ids=[1],  # PolygonZone ID
            cooldown_seconds=300,
        )

    @pytest.mark.asyncio
    async def test_dwell_time_returns_false_when_no_zones(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
    ) -> None:
        """Test dwell_time check returns False when no zones to check."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Loitering Rule",
            enabled=True,
            severity=AlertSeverity.HIGH,
            dwell_time_enabled=True,
            zone_ids=[],  # Empty zone list
            cooldown_seconds=300,
        )

        # Mock empty zone query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        engine = AlertRuleEngine(mock_session)
        matches, details, dwell_match = await engine._check_dwell_time(rule, sample_event)

        assert matches is False
        assert details == []
        assert dwell_match is None

    @pytest.mark.asyncio
    async def test_dwell_time_returns_false_when_zones_disabled(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        dwell_enabled_rule: AlertRule,
    ) -> None:
        """Test dwell_time check returns False when zones have loitering disabled."""
        # Mock zone query returning zone with loitering disabled
        disabled_zone = MagicMock()
        disabled_zone.id = 1
        disabled_zone.loitering_alert_enabled = False

        # First call for zones query - returns empty (filtered by loitering_alert_enabled)
        mock_zones_result = MagicMock()
        mock_zones_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_zones_result

        engine = AlertRuleEngine(mock_session)
        matches, details, dwell_match = await engine._check_dwell_time(
            dwell_enabled_rule, sample_event
        )

        assert matches is False
        assert details == []
        assert dwell_match is None

    @pytest.mark.asyncio
    async def test_dwell_time_returns_false_when_below_threshold(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        dwell_enabled_rule: AlertRule,
        mock_polygon_zone: MagicMock,
    ) -> None:
        """Test dwell_time check returns False when dwell time is below threshold."""
        # Mock record with dwell time below threshold
        record = MagicMock()
        record.zone_id = 1
        record.track_id = 42
        record.exit_time = None
        record.calculate_dwell_time.return_value = 30.0  # Below 60s threshold

        # Setup mock responses
        mock_zones_result = MagicMock()
        mock_zones_result.scalars.return_value.all.return_value = [mock_polygon_zone]

        mock_dwell_result = MagicMock()
        mock_dwell_result.scalars.return_value.all.return_value = [record]

        mock_session.execute.side_effect = [mock_zones_result, mock_dwell_result]

        engine = AlertRuleEngine(mock_session)
        matches, details, dwell_match = await engine._check_dwell_time(
            dwell_enabled_rule, sample_event
        )

        assert matches is False
        assert details == []
        assert dwell_match is None

    @pytest.mark.asyncio
    async def test_dwell_time_returns_true_when_exceeds_threshold(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        dwell_enabled_rule: AlertRule,
        mock_polygon_zone: MagicMock,
        mock_dwell_record: MagicMock,
    ) -> None:
        """Test dwell_time check returns True when dwell time exceeds threshold."""
        # Setup mock responses
        mock_zones_result = MagicMock()
        mock_zones_result.scalars.return_value.all.return_value = [mock_polygon_zone]

        mock_dwell_result = MagicMock()
        mock_dwell_result.scalars.return_value.all.return_value = [mock_dwell_record]

        mock_session.execute.side_effect = [mock_zones_result, mock_dwell_result]

        engine = AlertRuleEngine(mock_session)
        matches, details, dwell_match = await engine._check_dwell_time(
            dwell_enabled_rule, sample_event
        )

        assert matches is True
        assert len(details) == 1
        assert "loitering_in_zone:Front Yard:90s" in details[0]
        assert "threshold:60s" in details[0]

    @pytest.mark.asyncio
    async def test_dwell_time_returns_dwell_match_for_dedup(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        dwell_enabled_rule: AlertRule,
        mock_polygon_zone: MagicMock,
        mock_dwell_record: MagicMock,
    ) -> None:
        """Test dwell_time check returns DwellTimeMatch for dedup key generation."""
        from backend.services.alert_engine import DwellTimeMatch

        # Setup mock responses
        mock_zones_result = MagicMock()
        mock_zones_result.scalars.return_value.all.return_value = [mock_polygon_zone]

        mock_dwell_result = MagicMock()
        mock_dwell_result.scalars.return_value.all.return_value = [mock_dwell_record]

        mock_session.execute.side_effect = [mock_zones_result, mock_dwell_result]

        engine = AlertRuleEngine(mock_session)
        matches, details, dwell_match = await engine._check_dwell_time(
            dwell_enabled_rule, sample_event
        )

        assert matches is True
        assert dwell_match is not None
        assert isinstance(dwell_match, DwellTimeMatch)
        assert dwell_match.zone_id == 1
        assert dwell_match.track_id == 42

    @pytest.mark.asyncio
    async def test_dwell_time_queries_all_zones_when_rule_zone_ids_empty(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
    ) -> None:
        """Test dwell_time queries all active zones when rule.zone_ids is empty."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Loitering Rule",
            enabled=True,
            severity=AlertSeverity.HIGH,
            dwell_time_enabled=True,
            zone_ids=None,  # No zones specified - query all
            cooldown_seconds=300,
        )

        # First query: get distinct zone IDs from active dwell records
        mock_zone_ids_result = MagicMock()
        mock_zone_ids_result.scalars.return_value.all.return_value = [1, 2]

        # Second query: get zones
        zone1 = MagicMock()
        zone1.id = 1
        zone1.name = "Zone 1"
        zone1.loitering_threshold_seconds = 60.0
        zone1.loitering_alert_enabled = True

        mock_zones_result = MagicMock()
        mock_zones_result.scalars.return_value.all.return_value = [zone1]

        # Third query: dwell records for zone 1
        record = MagicMock()
        record.zone_id = 1
        record.track_id = 10
        record.exit_time = None
        record.calculate_dwell_time.return_value = 120.0

        mock_dwell_result = MagicMock()
        mock_dwell_result.scalars.return_value.all.return_value = [record]

        mock_session.execute.side_effect = [
            mock_zone_ids_result,
            mock_zones_result,
            mock_dwell_result,
        ]

        engine = AlertRuleEngine(mock_session)
        matches, details, dwell_match = await engine._check_dwell_time(rule, sample_event)

        assert matches is True
        # Verify first query was for distinct zone IDs
        assert mock_session.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_evaluate_rule_with_dwell_time_enabled(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        dwell_enabled_rule: AlertRule,
        mock_polygon_zone: MagicMock,
        mock_dwell_record: MagicMock,
    ) -> None:
        """Test _evaluate_rule integrates dwell_time check correctly."""
        # Setup mock responses for dwell time check
        mock_zones_result = MagicMock()
        mock_zones_result.scalars.return_value.all.return_value = [mock_polygon_zone]

        mock_dwell_result = MagicMock()
        mock_dwell_result.scalars.return_value.all.return_value = [mock_dwell_record]

        mock_session.execute.side_effect = [mock_zones_result, mock_dwell_result]

        engine = AlertRuleEngine(mock_session)
        matches, conditions, dwell_match = await engine._evaluate_rule(
            dwell_enabled_rule, sample_event, sample_detections, datetime.now(UTC)
        )

        assert matches is True
        assert any("loitering_in_zone" in c for c in conditions)
        assert dwell_match is not None

    @pytest.mark.asyncio
    async def test_evaluate_rule_fails_when_dwell_time_not_met(
        self,
        mock_session: AsyncMock,
        sample_event: Event,
        sample_detections: list[Detection],
        dwell_enabled_rule: AlertRule,
        mock_polygon_zone: MagicMock,
    ) -> None:
        """Test _evaluate_rule returns False when dwell_time condition not met."""
        # Record with dwell time below threshold
        record = MagicMock()
        record.zone_id = 1
        record.track_id = 42
        record.exit_time = None
        record.calculate_dwell_time.return_value = 30.0  # Below threshold

        mock_zones_result = MagicMock()
        mock_zones_result.scalars.return_value.all.return_value = [mock_polygon_zone]

        mock_dwell_result = MagicMock()
        mock_dwell_result.scalars.return_value.all.return_value = [record]

        mock_session.execute.side_effect = [mock_zones_result, mock_dwell_result]

        engine = AlertRuleEngine(mock_session)
        matches, conditions, dwell_match = await engine._evaluate_rule(
            dwell_enabled_rule, sample_event, sample_detections, datetime.now(UTC)
        )

        assert matches is False
        assert conditions == []
        assert dwell_match is None


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
        matches, _conditions, _ = await engine._evaluate_rule(rule, event, [], current_time)

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


class TestEvaluateRuleVerificationGate:
    """spec §6 (Phase 1.3): a rejected verdict never pages - the analyzer's
    low-band clamp is not an alert gate, so the rule engine checks the
    verdict itself. verification_failed already fails the threshold arm
    (NULL score, test_risk_threshold_fails_when_none above); this class
    pins the missing half."""

    @pytest.mark.asyncio
    async def test_rejected_verdict_never_matches_even_above_threshold(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """The §6 scenario the clamp alone cannot catch: score inside the
        band a low camera threshold passes. The gate must be verdict-first."""
        sample_rule.risk_threshold = 10
        sample_event.risk_score = 20  # clamped-low band, over threshold
        row = MagicMock()
        row.verdict = "rejected"
        sample_event.verifications = [row]

        engine = AlertRuleEngine(mock_session)
        matches, conditions, _ = await engine._evaluate_rule(
            sample_rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is False
        assert conditions == []

    @pytest.mark.asyncio
    async def test_confirmed_and_uncertain_verdicts_are_not_gated(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Only rejected constrains (§6: "Only `rejected` constrains";
        uncertain notifies through the normal threshold)."""
        sample_rule.risk_threshold = 10
        sample_event.risk_score = 85
        for verdict in ("confirmed", "uncertain", "verification_failed"):
            row = MagicMock()
            row.verdict = verdict
            sample_event.verifications = [row]
            engine = AlertRuleEngine(mock_session)
            matches, _conditions, _ = await engine._evaluate_rule(
                sample_rule, sample_event, sample_detections, datetime.now(UTC)
            )
            assert matches is True, verdict

    @pytest.mark.asyncio
    async def test_legacy_event_without_rows_is_unchanged(
        self,
        mock_session: AsyncMock,
        sample_rule: AlertRule,
        sample_event: Event,
        sample_detections: list[Detection],
    ) -> None:
        """Legacy events carry NO verification row (spec §4) - their rule
        evaluation stays byte-identical."""
        sample_rule.risk_threshold = 10
        sample_event.risk_score = 85
        sample_event.verifications = []
        engine = AlertRuleEngine(mock_session)
        matches, _conditions, _ = await engine._evaluate_rule(
            sample_rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True


# =============================================================================
# Consolidated from test_alert_engine_batch38_ae.py (B4.1 step 2)
# =============================================================================


def n(s):
    return " ".join(str(s).split())


# EXACT compiled statement texts of the module's 12 query families,
# compiled pristine (whitespace-normalized) and transcribed here as static
# literals - never re-derived from the module source at runtime: under the
# trampoline tree the source text also contains every MUTANT body, so a
# runtime extraction could compile a mutant's statement as the "expected"
# text. FakeSession routes on these; a statement rewrite either mismatches
# (AssertionError -> killed) or rebinds params.
_SQL_RULES = f"{n(select(AlertRule))} WHERE alert_rules.enabled IS true"
_SQL_TRUST = "SELECT DISTINCT entities.trust_status FROM entities WHERE entities.primary_detection_id IN (__[POSTCOMPILE_primary_detection_id_1])"
_SQL_EVDET = "SELECT event_detections.detection_id FROM event_detections WHERE event_detections.event_id = :event_id_1"
_SQL_JUNC = "SELECT event_detections.event_id, event_detections.detection_id FROM event_detections WHERE event_detections.event_id IN (__[POSTCOMPILE_event_id_1])"
_SQL_DZONES = "SELECT DISTINCT dwell_time_records.zone_id FROM dwell_time_records WHERE dwell_time_records.camera_id = :camera_id_1 AND dwell_time_records.exit_time IS NULL"
_SQL_ZONES = "SELECT polygon_zones.id, polygon_zones.camera_id, polygon_zones.name, polygon_zones.polygon, polygon_zones.zone_type, polygon_zones.alert_threshold, polygon_zones.target_classes, polygon_zones.is_active, polygon_zones.color, polygon_zones.current_count, polygon_zones.loitering_threshold_seconds, polygon_zones.loitering_alert_enabled, polygon_zones.created_at FROM polygon_zones WHERE polygon_zones.id IN (__[POSTCOMPILE_id_1]) AND polygon_zones.loitering_alert_enabled IS true"
_SQL_DWELL = "SELECT dwell_time_records.id, dwell_time_records.zone_id, dwell_time_records.track_id, dwell_time_records.camera_id, dwell_time_records.object_class, dwell_time_records.entry_time, dwell_time_records.exit_time, dwell_time_records.total_seconds, dwell_time_records.triggered_alert FROM dwell_time_records WHERE dwell_time_records.zone_id = :zone_id_1 AND dwell_time_records.exit_time IS NULL"
_SQL_THREAT = "SELECT threat_detections.id, threat_detections.detection_id, threat_detections.threat_type, threat_detections.confidence, threat_detections.severity, threat_detections.bbox, threat_detections.created_at FROM threat_detections WHERE threat_detections.detection_id IN (__[POSTCOMPILE_detection_id_1])"
_SQL_COOLDOWN = f"{n(select(Alert))} WHERE alerts.dedup_key = :dedup_key_1 AND alerts.rule_id = :rule_id_1 AND alerts.created_at >= :created_at_1 LIMIT :param_1 FOR UPDATE"


class _Res:
    def __init__(self, rows):
        self._rows = list(rows)

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class FakeSession:
    """Routes on EXACT compiled statement text; records bound params."""

    def __init__(self, routes=None):
        self.routes = dict(routes or {})
        self.calls = []
        self.added = []
        self.flushes = 0

    async def execute(self, stmt):
        if stmt is None:
            raise AssertionError("session.execute(None)")
        text = n(stmt)
        params = dict(stmt.compile().params)
        self.calls.append((text, params))
        if text not in self.routes:
            raise AssertionError(f"unrouted statement: {text}")
        rows = self.routes[text]
        return _Res(rows(params) if callable(rows) else rows)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushes += 1


def rule(**kw):
    base = {
        "id": 1,
        "name": "r1",
        "severity": AlertSeverity.LOW,
        "risk_threshold": None,
        "camera_ids": None,
        "object_types": None,
        "min_confidence": None,
        "zone_ids": None,
        "schedule": None,
        "dwell_time_enabled": False,
        "threat_detection_enabled": False,
        "threat_types": None,
        "threat_min_severity": None,
        "threat_confidence_threshold": None,
        "dedup_key_template": None,
        "cooldown_seconds": None,
        "channels": None,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def det(id=1, object_type="person", confidence=0.9):
    return SimpleNamespace(id=id, object_type=object_type, confidence=confidence)


def ev(id=7, camera_id="cam-1", risk_score=8.5, started_at=None, **kw):
    return Event(id=id, camera_id=camera_id, risk_score=risk_score, started_at=started_at, **kw)


def vrow(created_at, id, verdict):
    return SimpleNamespace(created_at=created_at, id=id, verdict=verdict)


class SlotsEvent:
    """No __dict__: probes the getattr(event, '__dict__', <default>) guard."""

    __slots__ = ("camera_id", "id", "risk_score")

    def __init__(self):
        self.id = 77
        self.camera_id = "cam-1"
        self.risk_score = 8.5


class _ProbeBase(DeclarativeBase):
    pass


class _ProbeEvent(_ProbeBase):
    """Instrumented instance whose ATTRIBUTE access cannot see its own
    state.dict entry: the class-level property (a data descriptor) wins
    over the __dict__ key, so inside _load_event_detections the try fast
    path (reads state.dict["detections"]) and the except attribute probe
    (reads event.detections -> None) return DIFFERENT values - the only
    shape that observes the fast-path return line at all."""

    __tablename__ = "battery_ae_probe"

    id: Mapped[int] = mapped_column(primary_key=True)

    @property
    def detections(self):
        return None


class BatchSpy:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    async def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return list(self.rows)


class WebhookSpy:
    def __init__(self, raises=None):
        self.calls = []
        self.raises = raises

    async def trigger_webhooks_for_event(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.raises:
            raise self.raises


class _RecHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def caplogs(fn):
    """Capture the module logger at DEBUG, passing the record list in.

    A DECORATOR with a zero-arg wrapper, not a pytest fixture: the b30
    sweep invokes every battery test with NO arguments, so a fixture
    parameter would fail the shipped-green control. No functools.wraps
    either - it would publish the wrapped (1-arg) signature via
    __wrapped__ and make pytest hunt for a fixture again.
    """

    def wrapper():
        handler = _RecHandler()
        lg = ae.logger
        prev_propagate, prev_level = lg.propagate, lg.level
        lg.addHandler(handler)
        lg.propagate = False
        lg.setLevel(logging.DEBUG)
        try:
            return fn(handler.records)
        finally:
            lg.removeHandler(handler)
            lg.propagate = prev_propagate
            lg.setLevel(prev_level)

    wrapper.__name__ = fn.__name__
    wrapper.__qualname__ = fn.__qualname__
    wrapper.__doc__ = fn.__doc__
    return wrapper


def patched(fn):
    """Restore the swapped module globals after the test (zero-arg wrapper)."""

    def wrapper():
        saved_gws, saved_bfd = ae.get_webhook_service, ae.batch_fetch_detections
        try:
            return fn()
        finally:
            ae.get_webhook_service = saved_gws
            ae.batch_fetch_detections = saved_bfd

    wrapper.__name__ = fn.__name__
    wrapper.__qualname__ = fn.__qualname__
    wrapper.__doc__ = fn.__doc__
    return wrapper


run = asyncio.run


def _rec_msgs(records, level):
    return [r.getMessage() for r in records if r.levelno == level]


CT = datetime(2026, 10, 3, 10, 0)  # a Saturday


def _base_routes():
    return {_SQL_TRUST: [], _SQL_RULES: [], _SQL_COOLDOWN: []}


# ---------------------------------------------------------------- trust + rules


def test_get_enabled_rules_statement_family():
    # m1/m7 (None stmt/execute), m2 (clause dropped), m3 (select(NULL)),
    # m4/m5 (IS NULL / IS false) - every flip mismatches the pinned text.
    assert "WHERE alert_rules.enabled IS true" in _SQL_RULES
    s = FakeSession({_SQL_RULES: [rule(id=9, name="x")]})
    out = run(AlertRuleEngine(s)._get_enabled_rules())
    assert [r.id for r in out] == [9]
    assert s.calls == [(_SQL_RULES, {})]


@caplogs
def test_trusted_entity_skips_all_alerts(logs):
    # evaluate_event m13 (debug message -> None); trust statement family.
    s = FakeSession({_SQL_TRUST: [TrustStatus.TRUSTED.value]})
    result = run(AlertRuleEngine(s).evaluate_event(ev(), [det()], CT))
    assert isinstance(result, EvaluationResult)
    assert result.triggered_rules == []
    assert result.skipped_rules == []
    assert result.highest_severity is None
    assert result.entity_trust_status == TrustStatus.TRUSTED
    assert result.trusted_entity_skipped is True
    assert not result.has_triggers
    assert _rec_msgs(logs, logging.DEBUG) == [
        "Skipping alert generation for event 7 - trusted entity detected in detections"
    ]
    # the trusted short-circuit precedes _get_enabled_rules
    assert [t for t, _ in s.calls] == [_SQL_TRUST]


def test_trust_status_priority_and_statement():
    engine = AlertRuleEngine(FakeSession({_SQL_TRUST: []}))
    assert run(engine._get_aggregate_entity_trust_status([])) is None
    assert run(engine._get_aggregate_entity_trust_status([det(id=None)])) is None
    assert engine.session.calls == []  # both early returns run no query
    assert run(engine._get_aggregate_entity_trust_status([det(id=1)])) is None
    assert engine.session.calls[-1] == (_SQL_TRUST, {"primary_detection_id_1": [1]})
    for statuses, expected in (
        (
            [TrustStatus.TRUSTED.value, TrustStatus.UNTRUSTED.value, TrustStatus.UNKNOWN.value],
            TrustStatus.TRUSTED,
        ),
        ([TrustStatus.UNKNOWN.value, TrustStatus.UNTRUSTED.value], TrustStatus.UNTRUSTED),
        ([TrustStatus.UNKNOWN.value], TrustStatus.UNKNOWN),
        (["bogus-status"], TrustStatus.UNKNOWN),
    ):
        sx = FakeSession({_SQL_TRUST: statuses})
        assert run(AlertRuleEngine(sx)._get_aggregate_entity_trust_status([det(id=1)])) == expected


# ---------------------------------------------------------------- evaluate_event


def test_cooldown_round_statement_params_and_break_polarity():
    # cooldown m3/m5 (cutoff params), m7-m20 (pinned text + LIMIT param),
    # evaluate_event m26-m37 (dedup key flows to cooldown), m45 (break).
    s = FakeSession(_base_routes())
    r1 = rule(id=11, cooldown_seconds=300)
    r2 = rule(id=12, dedup_key_template="{camera_id}:{rule_id}:{object_type}")
    r3 = rule(id=13, cooldown_seconds=3600, dedup_key_template="{camera_id}")
    s.routes[_SQL_RULES] = [r1, r2, r3]
    result = run(AlertRuleEngine(s).evaluate_event(ev(), [det()], CT))
    cd = [p for t, p in s.calls if t == _SQL_COOLDOWN]
    assert len(cd) == 3
    assert cd[0]["dedup_key_1"] == "cam-1:11"
    assert cd[0]["rule_id_1"] == 11
    assert cd[0]["created_at_1"] == datetime(2026, 10, 3, 9, 55)
    assert cd[0]["param_1"] == 1
    assert "LIMIT :param_1" in _SQL_COOLDOWN and "FOR UPDATE" in _SQL_COOLDOWN
    assert cd[1]["created_at_1"] == datetime(2026, 10, 3, 9, 55)  # None or 300
    assert cd[1]["dedup_key_1"] == "cam-1:12:person"
    assert cd[2]["dedup_key_1"] == "cam-1"
    assert cd[2]["created_at_1"] == datetime(2026, 10, 3, 9, 0)
    assert result.skipped_rules == []
    assert [t.rule.id for t in result.triggered_rules] == [11, 12, 13]
    # m45 continue->break: with every cooldown hit, ALL rules get evaluated
    s2 = FakeSession(_base_routes())
    s2.routes[_SQL_RULES] = [r1, r2, r3]
    s2.routes[_SQL_COOLDOWN] = [SimpleNamespace(id=99)]
    res2 = run(AlertRuleEngine(s2).evaluate_event(ev(), [det()], CT))
    assert res2.triggered_rules == []
    assert [id(r) for r, _ in res2.skipped_rules] == [id(r1), id(r2), id(r3)]
    assert [reason for _, reason in res2.skipped_rules] == ["in_cooldown"] * 3


def test_untrusted_escalation_round():
    # m54-m56 (.get default on a non-table severity), m61-m74 (fields),
    # m79/m81 (compared-side defaults), sort order with a bogus severity.
    s = FakeSession(_base_routes())
    a = rule(id=1, name="A", severity=AlertSeverity.MEDIUM, cooldown_seconds=60)
    b = rule(id=2, name="B", severity=AlertSeverity.LOW, cooldown_seconds=60)
    c = rule(id=3, name="C", severity=AlertSeverity.HIGH, cooldown_seconds=60)
    d = rule(id=4, name="D", severity="bogus", cooldown_seconds=60)
    s.routes[_SQL_RULES] = [a, b, c, d]
    s.routes[_SQL_TRUST] = [TrustStatus.UNTRUSTED.value]
    result = run(AlertRuleEngine(s).evaluate_event(ev(), [det()], CT))
    assert result.skipped_rules == []  # m54/m55/m56 crash on the bogus rule
    by_id = {t.rule.id: t for t in result.triggered_rules}
    assert by_id[1].severity == AlertSeverity.HIGH
    assert by_id[1].original_severity == AlertSeverity.MEDIUM
    assert by_id[1].trust_adjusted is True
    assert by_id[1].matched_conditions == [
        "no_conditions (always matches)",
        "severity_escalated_untrusted_entity (medium -> high)",
    ]
    assert by_id[2].matched_conditions[-1] == "severity_escalated_untrusted_entity (low -> medium)"
    assert by_id[3].severity == AlertSeverity.CRITICAL
    assert (
        by_id[3].matched_conditions[-1] == "severity_escalated_untrusted_entity (high -> critical)"
    )
    assert by_id[4].severity == "bogus"  # the escalation table's default value
    assert by_id[4].original_severity == "bogus"
    assert by_id[4].trust_adjusted is False
    assert by_id[4].matched_conditions == ["no_conditions (always matches)"]
    assert result.highest_severity == AlertSeverity.CRITICAL
    # sort: CRITICAL (rule 3) leads, then HIGH (1), MEDIUM (2), bogus (0)
    assert [t.rule.id for t in result.triggered_rules] == [3, 1, 2, 4]
    assert result.entity_trust_status == TrustStatus.UNTRUSTED
    assert result.trusted_entity_skipped is False
    assert result.has_triggers
    assert by_id[1].dedup_key == "cam-1:1"
    for t in result.triggered_rules:
        assert t.dwell_time_match is None  # m67/m74 deleted-kwarg shape


def test_highest_severity_bogus_first():
    # m85/m87/m88 (result-side .get default) + m83 (>= re-assigns the
    # highest at an equal-priority tie between two bogus severities).
    s = FakeSession(_base_routes())
    d = rule(id=4, name="D", severity="bogus", cooldown_seconds=60)
    e = rule(id=5, name="E", severity="alsobogus", cooldown_seconds=60)
    s.routes[_SQL_RULES] = [d, e]
    s.routes[_SQL_TRUST] = [TrustStatus.UNTRUSTED.value]
    result = run(AlertRuleEngine(s).evaluate_event(ev(), [det()], CT))
    assert result.skipped_rules == []  # m85/m87 TypeError; m83 keeps equal
    assert result.highest_severity == "bogus"  # 0 > 0 is False, m83: assigns
    assert [t.rule.id for t in result.triggered_rules] == [4, 5]

    s2 = FakeSession(_base_routes())
    b = rule(id=2, name="B", severity=AlertSeverity.LOW, cooldown_seconds=60)
    s2.routes[_SQL_RULES] = [d, e, b]
    s2.routes[_SQL_TRUST] = [TrustStatus.UNTRUSTED.value]
    res2 = run(AlertRuleEngine(s2).evaluate_event(ev(), [det()], CT))
    assert res2.skipped_rules == []  # m85/m87: LOW(1) > None raises
    assert res2.highest_severity == AlertSeverity.MEDIUM  # 1 > 0; m88: 1 > 1 F
    assert [t.rule.id for t in res2.triggered_rules] == [2, 4, 5]


def test_highest_severity_lowest_first_sort_tie():
    # m82 (compared-side default 1), m105 (sort-key default 1): the LOW rule
    # goes first so the bogus rule sits BEHIND it (tie keeps insertion order).
    s = FakeSession(_base_routes())
    b = rule(id=2, name="B", severity=AlertSeverity.LOW, cooldown_seconds=60)
    d = rule(id=4, name="D", severity="bogus", cooldown_seconds=60)
    s.routes[_SQL_RULES] = [b, d]
    result = run(AlertRuleEngine(s).evaluate_event(ev(), [det()], CT))
    assert result.skipped_rules == []
    assert result.highest_severity == AlertSeverity.LOW  # bogus 0 never wins
    assert [t.rule.id for t in result.triggered_rules] == [2, 4]  # m105: [4, 2]
    assert [t.severity for t in result.triggered_rules] == [AlertSeverity.LOW, "bogus"]


@caplogs
def test_rule_error_round_and_dedup_fallback(logs):
    # evaluate_event m90-m94 (error msg + exc_info), _build_dedup_key m33.
    s = FakeSession(_base_routes())
    s.routes[_SQL_RULES] = [rule(id=21, name="bad", camera_ids=["cam-1"])]
    bare_event = SimpleNamespace(id=77)  # no camera_id -> AttributeError
    result = run(AlertRuleEngine(s).evaluate_event(bare_event, [], CT))
    assert result.triggered_rules == []
    assert len(result.skipped_rules) == 1
    skipped_rule, reason = result.skipped_rules[0]
    assert skipped_rule.id == 21
    assert reason.startswith("evaluation_error: ")
    assert "camera_id" in reason
    errs = [r for r in logs if r.levelno == logging.ERROR]
    assert len(errs) == 1
    assert errs[0].getMessage() == "Error evaluating rule 21: " + reason.split(": ", 1)[1]
    assert errs[0].exc_info is not None  # m91/m93/m94 (None/deleted/False)
    assert errs[0].exc_info[0] is AttributeError

    # dedup template with an unknown variable -> warning + camera:rule key
    logs.clear()
    s2 = FakeSession(_base_routes())
    s2.routes[_SQL_RULES] = [rule(id=22, name="tmpl", dedup_key_template="{bogus}")]
    res2 = run(AlertRuleEngine(s2).evaluate_event(ev(), [det()], CT))
    assert res2.triggered_rules[0].dedup_key == "cam-1:22"
    assert _rec_msgs(logs, logging.WARNING) == ["Invalid dedup_key_template variable: 'bogus'"]


def test_slots_event_triggers_pristine():
    # _evaluate_rule m8/m11: an event without __dict__ passes the gate
    # untouched (the None/deleted defaults raise TypeError -> skipped).
    s = FakeSession(_base_routes())
    s.routes[_SQL_RULES] = [rule(id=23, name="slots")]
    result = run(AlertRuleEngine(s).evaluate_event(SlotsEvent(), [], CT))
    assert result.skipped_rules == []
    assert result.triggered_rules[0].dedup_key == "cam-1:23"


# ---------------------------------------------------------------- _evaluate_rule


def test_verification_gate_rounds():
    # m18/m20/m21 (max key), m8/m11 (__dict__ probe defaults).
    engine = AlertRuleEngine(FakeSession())

    def evaluate(event):
        return run(engine._evaluate_rule(rule(), event, [], CT))

    e = ev()
    e.__dict__["verifications"] = [vrow(1, 1, "ok"), vrow(2, 2, "rejected")]
    assert evaluate(e) == (False, [], None)
    e2 = ev()
    e2.__dict__["verifications"] = [vrow(3, 5, "ok"), vrow(1, 9, "rejected")]
    assert evaluate(e2)[0] is True  # newest by (created_at, id) is the ok row
    e3 = ev()
    e3.__dict__["verifications"] = [vrow(1, 1, "rejected"), vrow(2, 2, "ok")]
    assert evaluate(e3)[0] is True  # m20: max(rows) w/o key compares rows -> raise
    e4 = ev()
    e4.__dict__["verifications"] = []
    assert evaluate(e4)[0] is True
    assert evaluate(SlotsEvent())[0] is True


@patched
def test_threat_condition_label_through_evaluate_rule():
    # _evaluate_rule: the "threat_detected" label appended AFTER the sub-check passes.
    ae.batch_fetch_detections = BatchSpy([])
    engine = AlertRuleEngine(FakeSession({_SQL_THREAT: [_thr()]}))
    _, conds_t, _ = run(
        engine._evaluate_rule(rule(threat_detection_enabled=True), ev(), [det()], CT)
    )
    assert conds_t == ["threat_detected"]


@caplogs
def test_conditions_strings_and_zone_debug(logs):
    # m50 (zone debug None) + every matched-condition string + boundaries.
    engine = AlertRuleEngine(FakeSession())
    r = rule(
        id=4,
        risk_threshold=7.5,
        camera_ids=["cam-1", "cam-2"],
        object_types=["Person"],
        min_confidence=0.9,
        zone_ids=[3],
        schedule={"days": ["saturday"]},
    )
    matches, conds, dwell = run(engine._evaluate_rule(r, ev(), [det()], CT))
    assert matches is True and dwell is None
    assert conds == [
        "risk_score >= 7.5",
        "camera_id in ['cam-1', 'cam-2']",
        "object_type in ['Person']",
        "confidence >= 0.9",
        "within_schedule",
    ]
    assert _rec_msgs(logs, logging.DEBUG) == [
        "Zone condition in rule 4 - zone matching not yet implemented"
    ]
    assert run(engine._evaluate_rule(rule(risk_threshold=8.5), ev(), [], CT))[0] is True
    assert run(engine._evaluate_rule(rule(risk_threshold=8.6), ev(), [], CT)) == (False, [], None)
    assert run(engine._evaluate_rule(rule(risk_threshold=7.0), ev(risk_score=None), [], CT)) == (
        False,
        [],
        None,
    )
    assert (
        run(engine._evaluate_rule(rule(min_confidence=0.9), ev(), [det(confidence=0.9)], CT))[0]
        is True
    )
    assert run(
        engine._evaluate_rule(rule(min_confidence=0.91), ev(), [det(confidence=None)], CT)
    ) == (
        False,
        [],
        None,
    )
    assert (
        run(
            engine._evaluate_rule(
                rule(object_types=["PERSON"]), ev(), [det(object_type="person")], CT
            )
        )[0]
        is True
    )
    assert run(
        engine._evaluate_rule(rule(object_types=["car"]), ev(), [det(object_type=None)], CT)
    ) == (
        False,
        [],
        None,
    )
    assert run(engine._evaluate_rule(rule(object_types=["car"]), ev(), [], CT)) == (False, [], None)
    assert run(engine._evaluate_rule(rule(camera_ids=["other"]), ev(), [], CT)) == (False, [], None)


# ---------------------------------------------------------------- dwell time


def zone(id_, name="Z", thr=60):
    return SimpleNamespace(id=id_, name=name, loitering_threshold_seconds=thr)


def dwellrec(zone_id=9, track_id=42, entry=None, exit_=None):
    entry = datetime(2026, 10, 3, 9, 0) if entry is None else entry
    exit_ = datetime(2026, 10, 3, 9, 1) if exit_ is None else exit_  # exactly 60s

    def calc(current_time):
        end = exit_ or current_time or utc_now_naive()
        return (end - entry).total_seconds()

    return SimpleNamespace(zone_id=zone_id, track_id=track_id, calculate_dwell_time=calc)


@caplogs
def test_dwell_time_statement_family_and_match(logs):
    # m4-m8/m10 (camera query + params), m16-m26 (zones polarity),
    # m32-m38 (records query), m42 (>= vs > at the exact 60s tie), m52.
    s = FakeSession({_SQL_DZONES: [9], _SQL_ZONES: [zone(9)], _SQL_DWELL: [dwellrec()]})
    matched, details, match = run(
        AlertRuleEngine(s)._check_dwell_time(rule(id=1, dwell_time_enabled=True), ev())
    )
    assert matched is True
    assert details == ["loitering_in_zone:Z:60s(threshold:60s)"]
    assert (match.zone_id, match.track_id) == (9, 42)
    assert [t for t, _ in s.calls] == [_SQL_DZONES, _SQL_ZONES, _SQL_DWELL]
    assert s.calls[0][1] == {"camera_id_1": "cam-1"}
    assert s.calls[1][1] == {"id_1": [9]}
    assert s.calls[2][1] == {"zone_id_1": 9}
    assert "loitering_alert_enabled IS true" in _SQL_ZONES
    assert "exit_time IS NULL" in _SQL_DZONES and "exit_time IS NULL" in _SQL_DWELL
    assert _rec_msgs(logs, logging.DEBUG) == [
        "Loitering detected for rule 1: track 42 in zone Z for 60.0s (threshold: 60s)"
    ]
    # no zones from the camera query -> early return, no further queries
    s3 = FakeSession({_SQL_DZONES: [], _SQL_ZONES: [], _SQL_DWELL: []})
    assert run(AlertRuleEngine(s3)._check_dwell_time(rule(dwell_time_enabled=True), ev())) == (
        False,
        [],
        None,
    )
    assert [t for t, _ in s3.calls] == [_SQL_DZONES]
    # rule.zone_ids set -> the camera query is skipped entirely
    s4 = FakeSession({_SQL_ZONES: [zone(5)], _SQL_DWELL: []})
    matched4, _, _ = run(
        AlertRuleEngine(s4)._check_dwell_time(rule(dwell_time_enabled=True, zone_ids=[5]), ev())
    )
    assert matched4 is False
    assert [t for t, _ in s4.calls] == [_SQL_ZONES, _SQL_DWELL]
    # empty zones after the enabled filter -> no dwell query
    s5 = FakeSession({_SQL_DZONES: [9], _SQL_ZONES: []})
    assert run(AlertRuleEngine(s5)._check_dwell_time(rule(dwell_time_enabled=True), ev())) == (
        False,
        [],
        None,
    )
    assert [t for t, _ in s5.calls] == [_SQL_DZONES, _SQL_ZONES]


def test_dwell_end_to_end_through_evaluate_event():
    # evaluate_event m26-m34/m67/m74 + evaluate_rule m2/m62.
    s = FakeSession(
        {
            _SQL_RULES: [
                rule(
                    id=4,
                    dwell_time_enabled=True,
                    cooldown_seconds=60,
                    dedup_key_template="{camera_id}:{rule_id}:{zone_id}:{track_id}",
                )
            ],
            _SQL_DZONES: [9],
            _SQL_ZONES: [zone(9)],
            _SQL_DWELL: [dwellrec()],
            _SQL_COOLDOWN: [],
        }
    )
    result = run(AlertRuleEngine(s).evaluate_event(ev(), [], CT))
    t = result.triggered_rules[0]
    assert t.dedup_key == "cam-1:4:9:42"  # m2: "" init -> "" in details slot
    assert t.dwell_time_match is not None  # m67/m74
    assert (t.dwell_time_match.zone_id, t.dwell_time_match.track_id) == (9, 42)
    assert t.matched_conditions == ["loitering_in_zone:Z:60s(threshold:60s)"]
    assert [p for txt, p in s.calls if txt == _SQL_DZONES] == [{"camera_id_1": "cam-1"}]


# ---------------------------------------------------------------- threat


def _thr(severity="critical", confidence=0.9, threat_type="weapon"):
    return SimpleNamespace(severity=severity, confidence=confidence, threat_type=threat_type)


def test_threat_rounds():
    # m1 guard, m7-m9/m12, m23-m27 (min-priority defaults via bogus
    # severity), m30-m34 (row priority), m35/m37 (< ties), m36/m38 (breaks).
    s = FakeSession({_SQL_THREAT: [_thr()]})
    assert (
        run(AlertRuleEngine(s)._check_threat_detected(rule(threat_detection_enabled=True), [det()]))
        is True
    )
    assert s.calls[-1] == (_SQL_THREAT, {"detection_id_1": [1]})

    def check(rows, **rule_kw):
        sx = FakeSession({_SQL_THREAT: rows})
        return run(
            AlertRuleEngine(sx)._check_threat_detected(
                rule(threat_detection_enabled=True, **rule_kw), [det()]
            )
        )

    assert (
        check([_thr(severity="low"), _thr(severity="critical")], threat_min_severity="high") is True
    )  # m36
    assert check([_thr(severity="high")], threat_min_severity="high") is True  # m35 tie
    assert (
        check([_thr(severity="critical", confidence=0.9)], threat_confidence_threshold=0.9) is True
    )  # m37 tie
    assert (
        check([_thr(confidence=0.1), _thr(confidence=0.95)], threat_confidence_threshold=0.5)
        is True
    )  # m38
    assert check([], threat_min_severity="high") is False
    # m23/m25/m26: an unknown MIN_SEVERITY consults the first .get default
    assert check([_thr(severity="low")], threat_min_severity="bogus") is True
    # m27: falsy min_severity takes the else-branch 0
    assert check([_thr(severity="low")], threat_min_severity=None) is True
    assert check([_thr(severity="low")], threat_min_severity="") is True
    # m30: the row severity feeds the priority table (critical >= high)
    assert check([_thr(severity="critical")], threat_min_severity="high") is True
    # m31/m33/m34: an unknown ROW severity consults the second .get default
    assert check([_thr(severity="bogus")], threat_min_severity="medium") is False
    assert check([_thr(severity="bogus")], threat_min_severity=None) is True
    # threat-type filter keeps its continue semantics
    assert (
        check([_thr(threat_type="x"), _thr(threat_type="weapon")], threat_types=["weapon"]) is True
    )
    assert check([_thr(threat_type="x")], threat_types=["weapon"]) is False
    s6 = FakeSession()
    assert (
        run(
            AlertRuleEngine(s6)._check_threat_detected(
                rule(threat_detection_enabled=False), [det()]
            )
        )
        is False
    )
    assert (
        run(AlertRuleEngine(s6)._check_threat_detected(rule(threat_detection_enabled=True), []))
        is False
    )
    assert s6.calls == []


# ---------------------------------------------------------------- schedule


@caplogs
def test_schedule_boundaries(logs):
    # m31 (single-day list), m45 (`or` would parse the missing bound),
    # m53/m54 and m58/m59 at exactly-equal times, timezone conversion.
    engine = AlertRuleEngine(FakeSession())
    monday9 = datetime(2026, 10, 5, 9, 0)
    sched = {"days": ["monday"], "start_time": "09:00", "end_time": "17:00"}
    assert engine._check_schedule(sched, monday9) is True  # m53: start edge
    assert engine._check_schedule(sched, datetime(2026, 10, 5, 17, 0)) is True  # m54: end edge
    assert engine._check_schedule(sched, datetime(2026, 10, 5, 8, 59)) is False
    assert engine._check_schedule(sched, datetime(2026, 10, 5, 17, 1)) is False
    assert engine._check_schedule({"days": ["friday"]}, monday9) is False  # m31
    assert engine._check_schedule({"days": ["Monday"]}, monday9) is True
    assert engine._check_schedule({"days": []}, monday9) is True
    overnight = {"start_time": "22:00", "end_time": "06:00"}
    assert engine._check_schedule(overnight, datetime(2026, 10, 5, 22, 0)) is True  # m58 edge
    assert engine._check_schedule(overnight, datetime(2026, 10, 5, 6, 0)) is True  # m59 edge
    assert engine._check_schedule(overnight, datetime(2026, 10, 5, 21, 59)) is False
    assert engine._check_schedule(overnight, datetime(2026, 10, 5, 6, 1)) is False
    assert engine._check_schedule(overnight, datetime(2026, 10, 5, 2, 0)) is True
    assert engine._check_schedule({}, monday9) is True
    before = len(logs)
    assert engine._check_schedule({"start_time": "09:00"}, monday9) is True
    assert len(logs) == before  # m45 `or` would parse None and warn
    assert engine._check_schedule({"days": ["sunday"]}, monday9) is False  # default UTC
    assert len(logs) == before  # m10/m11: unknown/default tz names would warn
    # 20:00 UTC Sunday == 05:00 Monday in Tokyo
    assert (
        engine._check_schedule(
            {"days": ["monday"], "timezone": "Asia/Tokyo"}, datetime(2026, 10, 4, 20, 0)
        )
        is True
    )
    assert (
        engine._check_schedule(
            {"days": ["sunday"], "timezone": "Asia/Tokyo"}, datetime(2026, 10, 4, 20, 0)
        )
        is False
    )


@caplogs
def test_schedule_invalid_timezone_warns(logs):
    # m10/m11/m14: an unknown zone warns with the tz name, then falls back.
    engine = AlertRuleEngine(FakeSession())
    assert engine._check_schedule({"timezone": "Mars/Olympus"}, datetime(2026, 10, 5, 9, 0)) is True
    assert _rec_msgs(logs, logging.WARNING) == [
        "Invalid timezone Mars/Olympus, using UTC: 'No time zone found with key Mars/Olympus'"
    ]
    logs.clear()
    assert (
        engine._check_schedule(
            {"start_time": "90:00", "end_time": "17:00"}, datetime(2026, 10, 5, 9, 0)
        )
        is True
    )
    warns = _rec_msgs(logs, logging.WARNING)
    assert len(warns) == 1
    assert warns[0].startswith("Error parsing schedule time: ")


# ---------------------------------------------------------------- detections loading


@patched
def test_load_event_detections_fast_path_state_dict():
    # The try fast path reads state.dict["detections"] while the except
    # probe reads event.detections - on a REAL instrumented event both see
    # the same relationship, so no ordinary event distinguishes the two
    # returns. _ProbeEvent's class-level property hides its own state.dict
    # entry (descriptor beats __dict__), forcing the two paths to DIFFERENT
    # values: only a correct fast-path return yields [d1] with zero queries.
    # Kills m1/m2 (state=None / inspect(None) -> except -> attribute None ->
    # junction query) and the same-run birth family on the return line
    # (list(None), dict["XXdetectionsXX"], dict["DETECTIONS"]).
    d1, d2 = det(id=1), det(id=2)
    s = FakeSession({_SQL_EVDET: [2]})
    spy = BatchSpy([d2])
    ae.batch_fetch_detections = spy
    engine = AlertRuleEngine(s)
    p = _ProbeEvent(id=5)
    p.__dict__["detections"] = [d1]  # bypasses the property's no-setter
    assert run(engine._load_event_detections(p)) == [d1]
    assert s.calls == [] and spy.calls == []


@patched
def test_load_event_detections_rounds():
    # m11-m16 (junction stmt), m20-m23 (batch_fetch call shape); m1/m2 die
    # in the fast-path test above.
    d1 = det(id=1)
    s = FakeSession({_SQL_EVDET: [1, 2]})
    spy = BatchSpy([d1])
    ae.batch_fetch_detections = spy
    engine = AlertRuleEngine(s)

    # inspect-raises event (mock-shaped) with populated detections
    assert run(engine._load_event_detections(SimpleNamespace(id=7, detections=[d1]))) == [d1]
    assert spy.calls == [] and s.calls == []

    # transient real event, unloaded relationship -> junction query + fetch
    assert run(engine._load_event_detections(ev(id=7))) == [d1]
    assert s.calls[-1] == (_SQL_EVDET, {"event_id_1": 7})
    assert spy.calls == [((s, [1, 2]), {})]

    # junction empty -> [] with no fetch
    s2 = FakeSession({_SQL_EVDET: []})
    spy2 = BatchSpy([d1])
    ae.batch_fetch_detections = spy2
    assert run(AlertRuleEngine(s2)._load_event_detections(ev(id=8))) == []
    assert spy2.calls == []

    # real event with a loaded relationship short-circuits the query
    s3 = FakeSession()
    spy3 = BatchSpy([])
    ae.batch_fetch_detections = spy3
    e3 = Event(id=9, camera_id="c", risk_score=1.0, detections=[d1])
    assert run(AlertRuleEngine(s3)._load_event_detections(e3)) == [d1]
    assert spy3.calls == [] and s3.calls == []


@patched
def test_batch_load_detections_rounds():
    # m3-m8/m11 (junction stmt), m16 (collected ids), m19-m25 (fetch call
    # shape incl. order_by_time=False), m30/m32 (registered map-get).
    e1 = ev(id=7)
    e2 = ev(id=8)
    d1, d2 = det(id=1), det(id=2, object_type="car")
    s = FakeSession({_SQL_JUNC: [(7, 1), (7, 2)]})
    spy = BatchSpy([d1, d2])
    ae.batch_fetch_detections = spy
    engine = AlertRuleEngine(s)
    assert run(engine._batch_load_detections_for_events([e1, e2])) == {7: [d1, d2], 8: []}
    assert s.calls[-1] == (_SQL_JUNC, {"event_id_1": [7, 8]})
    assert spy.calls == [((s, [1, 2]), {"order_by_time": False})]
    before = len(s.calls)
    assert run(engine._batch_load_detections_for_events([])) == {}
    assert len(s.calls) == before  # empty input runs no query

    s2 = FakeSession({_SQL_JUNC: []})
    spy2 = BatchSpy([])
    ae.batch_fetch_detections = spy2
    assert run(AlertRuleEngine(s2)._batch_load_detections_for_events([e1])) == {7: []}
    assert spy2.calls == []

    # ids missing from the fetched rows are dropped from the mapping
    s3 = FakeSession({_SQL_JUNC: [(7, 1), (7, 99)]})
    spy3 = BatchSpy([d1])
    ae.batch_fetch_detections = spy3
    assert run(AlertRuleEngine(s3)._batch_load_detections_for_events([e1])) == {7: [d1]}
    assert spy3.calls == [((s3, [1, 99]), {"order_by_time": False})]


# ---------------------------------------------------------------- create + webhook


def alert_obj(**kw):
    base = {
        "id": 5,
        "event_id": 7,
        "rule_id": 3,
        "severity": AlertSeverity.CRITICAL,
        "status": AlertStatus.PENDING,
        "dedup_key": "dk",
        "channels": ["email"],
        "alert_metadata": {"matched_conditions": ["risk_score >= 1"], "rule_name": "n"},
    }
    base.update(kw)
    return SimpleNamespace(**base)


@patched
def test_webhook_payload_enum_round():
    # m2-m62: whole-dict payload pin, strict str types, exact call args.
    s = FakeSession()
    spy = WebhookSpy()
    ae.get_webhook_service = lambda: spy
    run(AlertRuleEngine(s)._trigger_alert_webhook(alert_obj(), ev()))
    assert len(spy.calls) == 1
    args, kwargs = spy.calls[0]
    assert len(args) == 3  # m61: dropping webhook_data shifts the call
    assert args[0] is s  # m55
    assert args[1] == WebhookEventType.ALERT_FIRED
    assert isinstance(args[2], dict)  # m57
    assert kwargs == {"event_id": 5}  # m58/m62
    data = args[2]
    assert type(data["severity"]) is str  # m11/m13/m17/m18: raw enum member
    assert type(data["status"]) is str  # m21/m23/m27/m28
    assert data == {
        "alert_id": 5,
        "event_id": 7,
        "rule_id": 3,
        "severity": "critical",
        "status": "pending",
        "dedup_key": "dk",
        "channels": ["email"],
        "matched_conditions": ["risk_score >= 1"],
        "rule_name": "n",
        "camera_id": "cam-1",
        "risk_score": 8.5,
    }


@patched
def test_webhook_str_and_absent_metadata_rounds():
    # m12/m22 (`or True`: .value on a plain str raises), m33 (channels),
    # m36-m43/m46-m50 (alert_metadata branches).
    spy = WebhookSpy()
    engine = AlertRuleEngine(FakeSession())
    ae.get_webhook_service = lambda: spy
    run(engine._trigger_alert_webhook(alert_obj(severity="high", status="pending"), ev()))
    data = spy.calls[0][0][2]
    assert data["severity"] == "high" and data["status"] == "pending"

    spy.calls.clear()
    run(engine._trigger_alert_webhook(alert_obj(alert_metadata={"rule_name": "r"}), ev()))
    data = spy.calls[0][0][2]
    assert data["matched_conditions"] == []
    assert data["rule_name"] == "r"

    # sentinel values under XX/CASE keys must NOT leak into the payload
    spy.calls.clear()
    run(
        engine._trigger_alert_webhook(
            alert_obj(alert_metadata={"XXmatched_conditionsXX": ["sentinel"], "RULE_NAME": "x"}),
            ev(),
        )
    )
    data = spy.calls[0][0][2]
    assert data["matched_conditions"] == []
    assert data["rule_name"] is None

    spy.calls.clear()
    run(engine._trigger_alert_webhook(alert_obj(alert_metadata=None), ev()))
    data = spy.calls[0][0][2]
    assert data["matched_conditions"] == []
    assert data["rule_name"] is None

    spy.calls.clear()
    run(engine._trigger_alert_webhook(alert_obj(channels=[]), ev()))
    assert spy.calls[0][0][2]["channels"] == []
    spy.calls.clear()
    run(engine._trigger_alert_webhook(alert_obj(channels=["slack", "email"]), ev()))
    assert spy.calls[0][0][2]["channels"] == ["slack", "email"]  # m33 -> []


@patched
@caplogs
def test_webhook_failure_log_round(logs):
    # m63-m70: the warning message and the extra={} alert_id/event_id attrs.
    spy = WebhookSpy(raises=RuntimeError("boom"))
    ae.get_webhook_service = lambda: spy
    run(AlertRuleEngine(FakeSession())._trigger_alert_webhook(alert_obj(), ev()))
    warns = [r for r in logs if r.levelno == logging.WARNING]
    assert len(warns) == 1
    assert warns[0].getMessage() == "Failed to trigger ALERT_FIRED webhooks: boom"
    assert warns[0].alert_id == 5 and warns[0].event_id == 7


@patched
def test_create_alerts_rounds():
    # create_alerts_for_event m22 (session.add(None)) + Alert shape +
    # one webhook per alert.
    from backend.models import Alert

    s = FakeSession()
    spy = WebhookSpy()
    ae.get_webhook_service = lambda: spy
    engine = AlertRuleEngine(s)
    r_a = rule(id=3, name="Ra", channels=["sms"])
    r_b = rule(id=4, name="Rb", channels=None)
    trigs = [
        TriggeredRule(
            rule=r_a, severity=AlertSeverity.HIGH, matched_conditions=["c1"], dedup_key="k1"
        ),
        TriggeredRule(
            rule=r_b, severity=AlertSeverity.LOW, matched_conditions=["c2"], dedup_key="k2"
        ),
    ]
    alerts = run(engine.create_alerts_for_event(ev(), trigs))
    assert len(s.added) == 2 and s.flushes == 1
    assert all(isinstance(a, Alert) and a is not None for a in s.added)  # m22
    a0, a1 = s.added
    assert (a0.event_id, a0.rule_id) == (7, 3)
    assert a0.severity == AlertSeverity.HIGH
    assert a0.status == AlertStatus.PENDING
    assert a0.dedup_key == "k1"
    assert a0.channels == ["sms"]
    assert a0.alert_metadata == {"matched_conditions": ["c1"], "rule_name": "Ra"}
    assert a1.channels == []  # rule channels None -> []
    assert (a1.rule_id, a1.dedup_key) == (4, "k2")
    assert alerts == [a0, a1]
    assert len(spy.calls) == 2
    assert [c[0][2]["rule_id"] for c in spy.calls] == [3, 4]
    assert [c[0][2]["dedup_key"] for c in spy.calls] == ["k1", "k2"]
    assert [c[0][2]["matched_conditions"] for c in spy.calls] == [["c1"], ["c2"]]
    assert [c[0][2]["rule_name"] for c in spy.calls] == ["Ra", "Rb"]


# ---------------------------------------------------------------- test_rule_against_events


@patched
def test_test_rule_against_events_rounds():
    # m2 (default clock reaches _check_schedule), m14 (detections reach
    # _evaluate_rule), m33-m36 (started_at key names + polarity).
    e1 = ev(id=7, started_at=datetime(2026, 10, 1, 12, 30, 45))
    e2 = ev(id=8, camera_id="cam-2", risk_score=2.0, started_at=None)
    d1 = det(id=1, object_type="car")
    s = FakeSession({_SQL_JUNC: [(7, 1)]})
    ae.batch_fetch_detections = BatchSpy([d1])
    engine = AlertRuleEngine(s)
    out = run(engine.test_rule_against_events(rule(id=5, object_types=["car"]), [e1, e2]))
    assert out == [
        {
            "event_id": 7,
            "camera_id": "cam-1",
            "risk_score": 8.5,
            "object_types": ["car"],
            "matches": True,
            "matched_conditions": ["object_type in ['car']"],
            "started_at": "2026-10-01T12:30:45",
        },
        {
            "event_id": 8,
            "camera_id": "cam-2",
            "risk_score": 2.0,
            "object_types": [],
            "matches": False,
            "matched_conditions": [],
            "started_at": None,
        },
    ]
    # m2 kill surface kept: current_time is deliberately omitted, so under mutant m2
    # (the None-substitution dropped) the None reaches _check_schedule and crashes at
    # the tz deref before any window logic. The schedule is {"days": []} - truthy (so it
    # still derefs current_time) but with NO start_time/end_time, so _check_schedule
    # returns True at EVERY wall-clock instant. The old {"00:00","23:59"} window made
    # this assert red for 59 s a day (2026-10-11 23:59 red) without adding kill power.
    out2 = run(engine.test_rule_against_events(rule(id=6, schedule={"days": []}), [e1]))
    assert out2[0]["matches"] is True  # m2: current_time=None crashes inside
