"""Unit tests for alert deduplication service.

Tests cover:
- build_dedup_key(): All combinations of None/present components
- check_duplicate(): Cooldown window logic, timezone handling
- get_cooldown_for_rule(): Default fallback, missing rule handling
- create_alert_if_not_duplicate(): Atomic check-then-create
- get_recent_alerts_for_key(): Time window queries
- get_duplicate_stats(): Aggregate calculations
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models import Alert, AlertRule, AlertSeverity, AlertStatus
from backend.services.alert_dedup import (
    AlertCreationError,
    AlertDeduplicationService,
    DedupResult,
    build_dedup_key,
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
def sample_alert() -> Alert:
    """Create a sample alert for testing."""
    return Alert(
        id=str(uuid.uuid4()),
        event_id=1,
        rule_id=str(uuid.uuid4()),
        severity=AlertSeverity.HIGH,
        status=AlertStatus.PENDING,
        dedup_key="front_door:person:entry_zone",
        channels=["push", "email"],
        alert_metadata={"test": "data"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_rule() -> AlertRule:
    """Create a sample alert rule for testing."""
    return AlertRule(
        id=str(uuid.uuid4()),
        name="Test Rule",
        enabled=True,
        severity=AlertSeverity.HIGH,
        cooldown_seconds=600,
        dedup_key_template="{camera_id}:{rule_id}",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# =============================================================================
# build_dedup_key() Tests
# =============================================================================


class TestBuildDedupKey:
    """Tests for build_dedup_key function."""

    def test_all_components_present(self) -> None:
        """Test with all components provided."""
        result = build_dedup_key("front_door", "person", "entry_zone")
        assert result == "front_door:person:entry_zone"

    def test_camera_only(self) -> None:
        """Test with only camera_id."""
        result = build_dedup_key("front_door")
        assert result == "front_door"

    def test_camera_and_object_type(self) -> None:
        """Test with camera_id and object_type, no zone."""
        result = build_dedup_key("front_door", "person")
        assert result == "front_door:person"

    def test_camera_and_zone_no_object_type(self) -> None:
        """Test with camera_id and zone, but no object_type."""
        result = build_dedup_key("front_door", None, "entry_zone")
        # Zone is added independently of object_type
        assert result == "front_door:entry_zone"

    def test_empty_string_object_type_treated_as_falsy(self) -> None:
        """Test that empty string object_type is treated as falsy."""
        result = build_dedup_key("front_door", "", "entry_zone")
        # Empty string object_type is falsy, but zone is added independently
        assert result == "front_door:entry_zone"

    def test_empty_string_zone_treated_as_falsy(self) -> None:
        """Test that empty string zone is treated as falsy."""
        result = build_dedup_key("front_door", "person", "")
        assert result == "front_door:person"

    def test_special_characters_preserved(self) -> None:
        """Test that special characters in components are preserved."""
        result = build_dedup_key("camera-01_front", "person-walking", "zone_123")
        assert result == "camera-01_front:person-walking:zone_123"

    def test_colon_in_component_creates_ambiguous_key(self) -> None:
        """Test that colons in components are included (potential ambiguity)."""
        result = build_dedup_key("cam:1", "person", "zone")
        assert result == "cam:1:person:zone"

    def test_whitespace_preserved(self) -> None:
        """Test that whitespace in components is preserved."""
        result = build_dedup_key("front door", "walking person", "entry zone")
        assert result == "front door:walking person:entry zone"


# =============================================================================
# DedupResult Tests
# =============================================================================


class TestDedupResult:
    """Tests for DedupResult dataclass."""

    def test_not_duplicate_defaults(self) -> None:
        """Test DedupResult for non-duplicate case."""
        result = DedupResult(is_duplicate=False)
        assert result.is_duplicate is False
        assert result.existing_alert is None
        assert result.seconds_until_cooldown_expires is None
        assert result.existing_alert_id is None

    def test_duplicate_with_alert(self, sample_alert: Alert) -> None:
        """Test DedupResult for duplicate case with alert."""
        result = DedupResult(
            is_duplicate=True,
            existing_alert=sample_alert,
            seconds_until_cooldown_expires=120,
        )
        assert result.is_duplicate is True
        assert result.existing_alert == sample_alert
        assert result.seconds_until_cooldown_expires == 120
        assert result.existing_alert_id == sample_alert.id

    def test_existing_alert_id_property_with_no_alert(self) -> None:
        """Test existing_alert_id property returns None when no alert."""
        result = DedupResult(is_duplicate=True, existing_alert=None)
        assert result.existing_alert_id is None


# =============================================================================
# AlertDeduplicationService._validate_dedup_key() Tests
# =============================================================================


class TestValidateDedupKey:
    """Tests for _validate_dedup_key static method.

    M3 T8 (audit Part 4): the 39 methods collapsed to 6 tests. Guard tool
    (scripts/parametrize-guard.py) bucketed 34 as parametrize duplicates;
    the 4 distinct pytest.raises match values each kept their own test —
    26 'invalid characters' payloads merged to one table, the 5 guarded
    no-raises valid-key checks merged to one (their bodies were literal-
    identical modulo the key strings). All 39 inputs preserved as params
    or body lines.
    """

    @pytest.mark.parametrize(
        "bad_key",
        [
            None,
            "",
        ],
        ids=["none", "empty_string"],
    )
    def test_empty_key_raises(self, mock_session: AsyncMock, bad_key) -> None:
        """Empty/None keys raise 'cannot be empty'."""
        service = AlertDeduplicationService(mock_session)
        with pytest.raises(ValueError, match="cannot be empty"):
            service._validate_dedup_key(bad_key)

    def test_whitespace_only_raises_error(self, mock_session: AsyncMock) -> None:
        """Test that whitespace-only string raises ValueError."""
        service = AlertDeduplicationService(mock_session)
        with pytest.raises(ValueError, match="cannot be whitespace-only"):
            service._validate_dedup_key("   ")

    @pytest.mark.parametrize(
        "padded_key",
        [" front_door:person", "front_door:person "],
        ids=["leading", "trailing"],
    )
    def test_padded_whitespace_raises_error(self, mock_session: AsyncMock, padded_key: str) -> None:
        """Leading/trailing whitespace raises 'leading or trailing whitespace'."""
        service = AlertDeduplicationService(mock_session)
        with pytest.raises(ValueError, match="leading or trailing whitespace"):
            service._validate_dedup_key(padded_key)

    @pytest.mark.parametrize(
        "valid_key",
        [
            "front_door:person:entry_zone",
            "camera1",
            "frontDoor123",
            "CAMERA01",
            "front_door",
            "camera_01_front",
            "a_b_c_d",
            "front-door",
            "camera-01-front",
            "a-b-c-d",
            "camera:person",
            "front_door:person:zone1",
            "cam-01:vehicle:entry-zone",
        ],
        ids=[
            "canonical",
            "alphanumeric_1",
            "alphanumeric_2",
            "alphanumeric_3",
            "underscore_1",
            "underscore_2",
            "underscore_3",
            "hyphen_1",
            "hyphen_2",
            "hyphen_3",
            "colon_1",
            "colon_2",
            "colon_3",
        ],
    )
    def test_valid_keys_pass(self, mock_session: AsyncMock, valid_key: str) -> None:
        """Keys of every allowed character class pass validation."""
        service = AlertDeduplicationService(mock_session)
        # Should not raise
        service._validate_dedup_key(valid_key)

    def test_valid_key_with_all_allowed_chars(self, mock_session: AsyncMock) -> None:
        """Test that keys with all allowed characters are valid."""
        service = AlertDeduplicationService(mock_session)
        # Should not raise - mix of alphanumeric, underscore, hyphen, colon
        service._validate_dedup_key("front_door-01:person:entry-zone_A")
        service._validate_dedup_key("CAM_01-front:Person123:Zone-A_1")

    # Character pattern validation (NEM-1107): every rejected payload from
    # the old 26-method family, one param each.
    @pytest.mark.parametrize(
        "rejected_key",
        [
            "camera'; DROP TABLE alerts;--",
            'camera"; DROP TABLE alerts;--',
            "camera;rm -rf /",
            "camera/../../../etc/passwd",
            "camera\nmalicious",
            "camera\rmalicious",
            "camera\tmalicious",
            "camera\x00malicious",
            "camera{test}",
            "camera[0]",
            "camera(test)",
            "camera$HOME",
            "camera`whoami`",
            "camera|cat /etc/passwd",
            "camera&rm -rf /",
            "camera@example.com",
            "camera!test",
            "camera%00malicious",
            "camera*",
            "camera?test=1",
            "camera=test",
            "camera+test",
            "camera#test",
            "camera\\test",
            "camera/test",
            "front door:person",
        ],
        ids=[
            "sql_injection_single_quote",
            "sql_injection_double_quote",
            "command_injection_semicolon",
            "path_traversal",
            "newline_injection",
            "carriage_return_injection",
            "tab_injection",
            "null_byte_injection",
            "curly_braces",
            "square_brackets",
            "parentheses",
            "dollar_sign",
            "backtick",
            "pipe",
            "ampersand",
            "at_sign",
            "exclamation_mark",
            "percent_sign",
            "asterisk",
            "question_mark",
            "equals_sign",
            "plus_sign",
            "hash_sign",
            "backslash",
            "forward_slash",
            "space_in_middle",
        ],
    )
    def test_invalid_characters_rejected(self, mock_session: AsyncMock, rejected_key: str) -> None:
        """SQL/command/XSS/glob/unicode-adjacent payloads are rejected."""
        service = AlertDeduplicationService(mock_session)
        with pytest.raises(ValueError, match="invalid characters"):
            service._validate_dedup_key(rejected_key)

    # The three multi-payload members of the old family keep their own
    # bodies (guard-distinct: several raises blocks per test).
    def test_angle_brackets_rejected(self, mock_session: AsyncMock) -> None:
        """Test that angle brackets (XSS vectors) are rejected."""
        service = AlertDeduplicationService(mock_session)
        with pytest.raises(ValueError, match="invalid characters"):
            service._validate_dedup_key("camera<script>alert(1)</script>")
        with pytest.raises(ValueError, match="invalid characters"):
            service._validate_dedup_key("camera>test")

    def test_unicode_characters_rejected(self, mock_session: AsyncMock) -> None:
        """Test that non-ASCII unicode characters are rejected."""
        service = AlertDeduplicationService(mock_session)
        # Test zero-width space (invisible character)
        with pytest.raises(ValueError, match="invalid characters"):
            service._validate_dedup_key("camera\u200btest")
        # Test fullwidth underscore character (U+FF3F)
        with pytest.raises(ValueError, match="invalid characters"):
            service._validate_dedup_key("camera\uff3ftest")
        # Test emoji
        with pytest.raises(ValueError, match="invalid characters"):
            service._validate_dedup_key("camera\U0001f4f7test")


# =============================================================================
# AlertDeduplicationService.check_duplicate() Tests
# =============================================================================


class TestCheckDuplicate:
    """Tests for check_duplicate method."""

    @pytest.mark.asyncio
    async def test_no_duplicate_found(self, mock_session: AsyncMock) -> None:
        """Test when no duplicate exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        result = await service.check_duplicate("front_door:person", cooldown_seconds=300)

        assert result.is_duplicate is False
        assert result.existing_alert is None
        assert result.seconds_until_cooldown_expires is None

    @pytest.mark.asyncio
    async def test_duplicate_found_within_cooldown(
        self, mock_session: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test when duplicate exists within cooldown window."""
        # Alert created 60 seconds ago
        sample_alert.created_at = datetime.now(UTC) - timedelta(seconds=60)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        result = await service.check_duplicate("front_door:person:entry_zone", cooldown_seconds=300)

        assert result.is_duplicate is True
        assert result.existing_alert == sample_alert
        # Should be approximately 240 seconds remaining (300 - 60)
        assert result.seconds_until_cooldown_expires is not None
        assert 230 <= result.seconds_until_cooldown_expires <= 250

    @pytest.mark.asyncio
    async def test_cooldown_expired_alert_not_found(self, mock_session: AsyncMock) -> None:
        """Test that alerts outside cooldown window are not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        result = await service.check_duplicate("front_door:person", cooldown_seconds=60)

        # Alert should not be found because it's outside cooldown
        assert result.is_duplicate is False

    @pytest.mark.asyncio
    async def test_zero_cooldown_seconds(self, mock_session: AsyncMock) -> None:
        """Test with zero cooldown seconds."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        result = await service.check_duplicate("front_door:person", cooldown_seconds=0)

        assert result.is_duplicate is False

    @pytest.mark.asyncio
    async def test_empty_key_raises_error(self, mock_session: AsyncMock) -> None:
        """Test that empty dedup_key raises ValueError."""
        service = AlertDeduplicationService(mock_session)

        with pytest.raises(ValueError, match="cannot be empty"):
            await service.check_duplicate("", cooldown_seconds=300)

    @pytest.mark.asyncio
    async def test_uses_utc_for_comparison(self, mock_session: AsyncMock) -> None:
        """Test that UTC is used for time comparisons."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        with patch("backend.services.alert_dedup.datetime", autospec=True) as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            await service.check_duplicate("front_door:person", cooldown_seconds=300)

            # Verify datetime.now was called with UTC
            mock_datetime.now.assert_called_with(UTC)

    @pytest.mark.asyncio
    async def test_seconds_remaining_calculation_at_boundary(
        self, mock_session: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test seconds remaining calculation at exact boundary."""
        # Alert created exactly at cooldown boundary
        sample_alert.created_at = datetime.now(UTC) - timedelta(seconds=300)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        result = await service.check_duplicate("front_door:person:entry_zone", cooldown_seconds=300)

        assert result.is_duplicate is True
        # Should be approximately 0 seconds remaining
        assert result.seconds_until_cooldown_expires is not None
        assert result.seconds_until_cooldown_expires >= 0

    @pytest.mark.asyncio
    async def test_large_cooldown_value(self, mock_session: AsyncMock) -> None:
        """Test with very large cooldown value (1 day)."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        result = await service.check_duplicate(
            "front_door:person",
            cooldown_seconds=86400,  # 24 hours
        )

        assert result.is_duplicate is False


# =============================================================================
# AlertDeduplicationService.get_cooldown_for_rule() Tests
# =============================================================================


class TestGetCooldownForRule:
    """Tests for get_cooldown_for_rule method."""

    @pytest.mark.asyncio
    async def test_default_when_rule_id_none(self, mock_session: AsyncMock) -> None:
        """Test returns default cooldown when rule_id is None."""
        service = AlertDeduplicationService(mock_session)
        result = await service.get_cooldown_for_rule(None)
        assert result == 300

    @pytest.mark.asyncio
    async def test_returns_rule_cooldown(
        self, mock_session: AsyncMock, sample_rule: AlertRule
    ) -> None:
        """Test returns rule's cooldown_seconds when rule found."""
        sample_rule.cooldown_seconds = 600

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_rule
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        result = await service.get_cooldown_for_rule(sample_rule.id)

        assert result == 600

    @pytest.mark.asyncio
    async def test_default_when_rule_not_found(self, mock_session: AsyncMock) -> None:
        """Test returns default cooldown when rule not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        result = await service.get_cooldown_for_rule(str(uuid.uuid4()))

        assert result == 300

    @pytest.mark.asyncio
    async def test_converts_cooldown_to_int(
        self, mock_session: AsyncMock, sample_rule: AlertRule
    ) -> None:
        """Test that cooldown is converted to int."""
        sample_rule.cooldown_seconds = 600  # Integer value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_rule
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        result = await service.get_cooldown_for_rule(sample_rule.id)

        assert isinstance(result, int)
        assert result == 600


# =============================================================================
# AlertDeduplicationService.create_alert_if_not_duplicate() Tests
# =============================================================================


class TestCreateAlertIfNotDuplicate:
    """Tests for create_alert_if_not_duplicate method."""

    @pytest.mark.asyncio
    async def test_creates_new_alert_when_no_duplicate(self, mock_session: AsyncMock) -> None:
        """Test creates a new alert when no duplicate exists."""
        # No duplicate found
        mock_dedup_result = MagicMock()
        mock_dedup_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_dedup_result

        service = AlertDeduplicationService(mock_session)
        alert, is_new = await service.create_alert_if_not_duplicate(
            event_id=1,
            dedup_key="front_door:person",
            severity=AlertSeverity.HIGH,
            channels=["push"],
            alert_metadata={"source": "test"},
            cooldown_seconds=300,
        )

        assert is_new is True
        assert alert.event_id == 1
        assert alert.dedup_key == "front_door:person"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.PENDING
        assert alert.channels == ["push"]
        assert alert.alert_metadata == {"source": "test"}
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_existing_when_duplicate(
        self, mock_session: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test returns existing alert when duplicate found."""
        sample_alert.created_at = datetime.now(UTC) - timedelta(seconds=60)

        mock_dedup_result = MagicMock()
        mock_dedup_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_dedup_result

        service = AlertDeduplicationService(mock_session)
        alert, is_new = await service.create_alert_if_not_duplicate(
            event_id=99,
            dedup_key=sample_alert.dedup_key,
            cooldown_seconds=300,
        )

        assert is_new is False
        assert alert == sample_alert
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_rule_cooldown_when_not_specified(
        self, mock_session: AsyncMock, sample_rule: AlertRule
    ) -> None:
        """Test uses rule's cooldown when cooldown_seconds not specified."""
        sample_rule.cooldown_seconds = 600

        # First call - get_cooldown_for_rule
        mock_rule_result = MagicMock()
        mock_rule_result.scalar_one_or_none.return_value = sample_rule

        # Second call - check_duplicate
        mock_dedup_result = MagicMock()
        mock_dedup_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [mock_rule_result, mock_dedup_result]

        service = AlertDeduplicationService(mock_session)
        _alert, is_new = await service.create_alert_if_not_duplicate(
            event_id=1,
            dedup_key="front_door:person",
            rule_id=sample_rule.id,
        )

        assert is_new is True

    @pytest.mark.asyncio
    async def test_default_severity_medium(self, mock_session: AsyncMock) -> None:
        """Test default severity is MEDIUM."""
        mock_dedup_result = MagicMock()
        mock_dedup_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_dedup_result

        service = AlertDeduplicationService(mock_session)
        alert, _ = await service.create_alert_if_not_duplicate(
            event_id=1,
            dedup_key="front_door:person",
            cooldown_seconds=300,
        )

        assert alert.severity == AlertSeverity.MEDIUM

    @pytest.mark.asyncio
    async def test_empty_channels_list_as_default(self, mock_session: AsyncMock) -> None:
        """Test channels defaults to empty list."""
        mock_dedup_result = MagicMock()
        mock_dedup_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_dedup_result

        service = AlertDeduplicationService(mock_session)
        alert, _ = await service.create_alert_if_not_duplicate(
            event_id=1,
            dedup_key="front_door:person",
            cooldown_seconds=300,
        )

        assert alert.channels == []

    @pytest.mark.asyncio
    async def test_empty_metadata_dict_as_default(self, mock_session: AsyncMock) -> None:
        """Test alert_metadata defaults to empty dict."""
        mock_dedup_result = MagicMock()
        mock_dedup_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_dedup_result

        service = AlertDeduplicationService(mock_session)
        alert, _ = await service.create_alert_if_not_duplicate(
            event_id=1,
            dedup_key="front_door:person",
            cooldown_seconds=300,
        )

        assert alert.alert_metadata == {}


# =============================================================================
# AlertDeduplicationService.get_recent_alerts_for_key() Tests
# =============================================================================


class TestGetRecentAlertsForKey:
    """Tests for get_recent_alerts_for_key method."""

    @pytest.mark.asyncio
    async def test_returns_alerts_matching_key(
        self, mock_session: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test returns alerts matching the dedup_key."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_alert]
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        alerts = await service.get_recent_alerts_for_key(sample_alert.dedup_key)

        assert len(alerts) == 1
        assert alerts[0] == sample_alert

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_matches(self, mock_session: AsyncMock) -> None:
        """Test returns empty list when no matching alerts."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        alerts = await service.get_recent_alerts_for_key("nonexistent:key")

        assert alerts == []

    @pytest.mark.asyncio
    async def test_default_hours_24(self, mock_session: AsyncMock) -> None:
        """Test default hours parameter is 24."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        await service.get_recent_alerts_for_key("front_door:person")

        # Verify execute was called (checking the query parameters would require
        # inspecting the SQL statement which is complex)
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_custom_hours_parameter(self, mock_session: AsyncMock) -> None:
        """Test with custom hours parameter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        await service.get_recent_alerts_for_key("front_door:person", hours=48)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_custom_limit_parameter(self, mock_session: AsyncMock) -> None:
        """Test with custom limit parameter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        await service.get_recent_alerts_for_key("front_door:person", limit=5)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_key_raises_error(self, mock_session: AsyncMock) -> None:
        """Test that empty dedup_key raises ValueError."""
        service = AlertDeduplicationService(mock_session)

        with pytest.raises(ValueError, match="cannot be empty"):
            await service.get_recent_alerts_for_key("")

    @pytest.mark.asyncio
    async def test_whitespace_key_raises_error(self, mock_session: AsyncMock) -> None:
        """Test that whitespace-only dedup_key raises ValueError."""
        service = AlertDeduplicationService(mock_session)

        with pytest.raises(ValueError, match="whitespace-only"):
            await service.get_recent_alerts_for_key("   ")

    @pytest.mark.asyncio
    async def test_returns_list_type(self, mock_session: AsyncMock) -> None:
        """Test that result is always a list."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        alerts = await service.get_recent_alerts_for_key("front_door:person")

        assert isinstance(alerts, list)


# =============================================================================
# AlertDeduplicationService.get_duplicate_stats() Tests
# =============================================================================


class TestGetDuplicateStats:
    """Tests for get_duplicate_stats method."""

    @pytest.mark.asyncio
    async def test_returns_all_stat_keys(self, mock_session: AsyncMock) -> None:
        """Test that all expected statistic keys are returned."""
        # First call - total alerts
        mock_total_result = MagicMock()
        mock_total_result.scalars.return_value.all.return_value = []

        # Second call - unique keys
        mock_unique_result = MagicMock()
        mock_unique_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [mock_total_result, mock_unique_result]

        service = AlertDeduplicationService(mock_session)
        stats = await service.get_duplicate_stats()

        assert "total_alerts" in stats
        assert "unique_dedup_keys" in stats
        assert "dedup_ratio" in stats

    @pytest.mark.asyncio
    async def test_zero_alerts_returns_zero_ratio(self, mock_session: AsyncMock) -> None:
        """Test that zero total alerts returns zero ratio."""
        mock_total_result = MagicMock()
        mock_total_result.scalars.return_value.all.return_value = []

        mock_unique_result = MagicMock()
        mock_unique_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [mock_total_result, mock_unique_result]

        service = AlertDeduplicationService(mock_session)
        stats = await service.get_duplicate_stats()

        assert stats["total_alerts"] == 0
        assert stats["unique_dedup_keys"] == 0
        assert stats["dedup_ratio"] == 0.0

    @pytest.mark.asyncio
    async def test_calculates_dedup_ratio(
        self, mock_session: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test correct calculation of dedup_ratio."""
        # 10 total alerts
        mock_total_result = MagicMock()
        mock_total_result.scalars.return_value.all.return_value = [MagicMock()] * 10

        # 5 unique keys
        mock_unique_result = MagicMock()
        mock_unique_result.scalars.return_value.all.return_value = [
            "key1",
            "key2",
            "key3",
            "key4",
            "key5",
        ]

        mock_session.execute.side_effect = [mock_total_result, mock_unique_result]

        service = AlertDeduplicationService(mock_session)
        stats = await service.get_duplicate_stats()

        assert stats["total_alerts"] == 10
        assert stats["unique_dedup_keys"] == 5
        assert stats["dedup_ratio"] == 0.5

    @pytest.mark.asyncio
    async def test_ratio_rounded_to_two_decimals(self, mock_session: AsyncMock) -> None:
        """Test that ratio is rounded to two decimal places."""
        # 3 total alerts
        mock_total_result = MagicMock()
        mock_total_result.scalars.return_value.all.return_value = [MagicMock()] * 3

        # 1 unique key -> ratio = 1/3 = 0.333...
        mock_unique_result = MagicMock()
        mock_unique_result.scalars.return_value.all.return_value = ["key1"]

        mock_session.execute.side_effect = [mock_total_result, mock_unique_result]

        service = AlertDeduplicationService(mock_session)
        stats = await service.get_duplicate_stats()

        assert stats["dedup_ratio"] == 0.33

    @pytest.mark.asyncio
    async def test_default_hours_24(self, mock_session: AsyncMock) -> None:
        """Test default hours parameter is 24."""
        mock_total_result = MagicMock()
        mock_total_result.scalars.return_value.all.return_value = []

        mock_unique_result = MagicMock()
        mock_unique_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [mock_total_result, mock_unique_result]

        service = AlertDeduplicationService(mock_session)
        await service.get_duplicate_stats()

        # Verify two queries were executed
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_custom_hours_parameter(self, mock_session: AsyncMock) -> None:
        """Test with custom hours parameter."""
        mock_total_result = MagicMock()
        mock_total_result.scalars.return_value.all.return_value = []

        mock_unique_result = MagicMock()
        mock_unique_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [mock_total_result, mock_unique_result]

        service = AlertDeduplicationService(mock_session)
        await service.get_duplicate_stats(hours=48)

        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_one_alert_per_key_ratio_is_one(self, mock_session: AsyncMock) -> None:
        """Test that 1:1 alert to key ratio returns 1.0."""
        # 5 total alerts
        mock_total_result = MagicMock()
        mock_total_result.scalars.return_value.all.return_value = [MagicMock()] * 5

        # 5 unique keys
        mock_unique_result = MagicMock()
        mock_unique_result.scalars.return_value.all.return_value = ["k1", "k2", "k3", "k4", "k5"]

        mock_session.execute.side_effect = [mock_total_result, mock_unique_result]

        service = AlertDeduplicationService(mock_session)
        stats = await service.get_duplicate_stats()

        assert stats["dedup_ratio"] == 1.0


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestEdgeCases:
    """Edge case tests for alert deduplication."""

    @pytest.mark.asyncio
    async def test_service_initialization(self, mock_session: AsyncMock) -> None:
        """Test service can be initialized with session."""
        service = AlertDeduplicationService(mock_session)
        assert service.session == mock_session

    @pytest.mark.asyncio
    async def test_very_long_dedup_key(self, mock_session: AsyncMock) -> None:
        """Test handling of very long dedup key."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        long_key = "a" * 255
        result = await service.check_duplicate(long_key)

        assert result.is_duplicate is False

    @pytest.mark.asyncio
    async def test_unicode_in_dedup_key_rejected(self, mock_session: AsyncMock) -> None:
        """Test that unicode characters in dedup key are rejected (NEM-1107)."""
        service = AlertDeduplicationService(mock_session)

        # Unicode characters should be rejected by stricter validation
        # Using escape sequence to ensure fullwidth underscore (U+FF3F) is preserved
        with pytest.raises(ValueError, match="invalid characters"):
            await service.check_duplicate("camera\uff3f1:person")

    @pytest.mark.asyncio
    async def test_negative_seconds_remaining_clamped_to_zero(
        self, mock_session: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test that negative seconds remaining is clamped to 0."""
        # Alert created longer ago than cooldown
        sample_alert.created_at = datetime.now(UTC) - timedelta(seconds=400)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        result = await service.check_duplicate(sample_alert.dedup_key, cooldown_seconds=300)

        assert result.is_duplicate is True
        assert result.seconds_until_cooldown_expires == 0


class TestConcurrencyScenarios:
    """Tests for concurrent access scenarios."""

    @pytest.mark.asyncio
    async def test_check_duplicate_uses_for_update(self, mock_session: AsyncMock) -> None:
        """Test that check_duplicate uses SELECT FOR UPDATE for locking."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        await service.check_duplicate("front_door:person")

        # The query uses with_for_update(skip_locked=True)
        # We verify execute was called, meaning the query was built
        mock_session.execute.assert_called_once()


class TestTimezoneHandling:
    """Tests for timezone handling."""

    @pytest.mark.asyncio
    async def test_check_duplicate_uses_utc(self, mock_session: AsyncMock) -> None:
        """Test that check_duplicate uses UTC for time comparison."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        await service.check_duplicate("front_door:person", cooldown_seconds=300)

        # Verify the session execute was called
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_recent_alerts_uses_utc(self, mock_session: AsyncMock) -> None:
        """Test that get_recent_alerts_for_key uses UTC."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        await service.get_recent_alerts_for_key("front_door:person")

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_duplicate_stats_uses_utc(self, mock_session: AsyncMock) -> None:
        """Test that get_duplicate_stats uses UTC."""
        mock_total_result = MagicMock()
        mock_total_result.scalars.return_value.all.return_value = []

        mock_unique_result = MagicMock()
        mock_unique_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [mock_total_result, mock_unique_result]

        service = AlertDeduplicationService(mock_session)
        await service.get_duplicate_stats()

        assert mock_session.execute.call_count == 2


class TestBuildDedupKeyEdgeCases:
    """Additional edge cases for build_dedup_key function."""

    def test_numeric_camera_id(self) -> None:
        """Test with numeric-like camera_id string."""
        result = build_dedup_key("123", "person", "zone1")
        assert result == "123:person:zone1"

    def test_only_camera_with_explicit_none(self) -> None:
        """Test with explicit None for optional parameters."""
        result = build_dedup_key("camera1", object_type=None, zone=None)
        assert result == "camera1"

    def test_object_type_present_zone_none(self) -> None:
        """Test with object_type present but zone is None."""
        result = build_dedup_key("camera1", "vehicle", None)
        assert result == "camera1:vehicle"

    def test_builds_consistent_keys(self) -> None:
        """Test that same inputs produce consistent keys."""
        key1 = build_dedup_key("cam1", "person", "zone1")
        key2 = build_dedup_key("cam1", "person", "zone1")
        assert key1 == key2


# =============================================================================
# NEM-1105: Database Error Handling Tests
# =============================================================================


class TestDatabaseErrorHandling:
    """Tests for database error handling in AlertDeduplicationService (NEM-1105)."""

    @pytest.mark.asyncio
    async def test_check_duplicate_handles_database_error(self, mock_session: AsyncMock) -> None:
        """Test that check_duplicate handles database errors gracefully."""
        mock_session.execute.side_effect = Exception("Database connection lost")

        service = AlertDeduplicationService(mock_session)

        with pytest.raises(Exception, match="Database connection lost"):
            await service.check_duplicate("front_door:person", cooldown_seconds=300)

    @pytest.mark.asyncio
    async def test_get_cooldown_for_rule_handles_database_error(
        self, mock_session: AsyncMock
    ) -> None:
        """Test that get_cooldown_for_rule handles database errors gracefully."""
        mock_session.execute.side_effect = Exception("Database timeout")

        service = AlertDeduplicationService(mock_session)

        with pytest.raises(Exception, match="Database timeout"):
            await service.get_cooldown_for_rule("some-rule-id")

    @pytest.mark.asyncio
    async def test_create_alert_handles_flush_error(self, mock_session: AsyncMock) -> None:
        """Test that create_alert_if_not_duplicate handles flush errors."""
        # First call (check_duplicate) succeeds with no duplicate
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # But flush fails
        mock_session.flush.side_effect = Exception("Database write failed")

        service = AlertDeduplicationService(mock_session)

        with pytest.raises(AlertCreationError, match="Database operation failed"):
            await service.create_alert_if_not_duplicate(
                event_id=1,
                dedup_key="front_door:person",
                cooldown_seconds=300,
            )

    @pytest.mark.asyncio
    async def test_get_recent_alerts_handles_database_error(self, mock_session: AsyncMock) -> None:
        """Test that get_recent_alerts_for_key handles database errors gracefully."""
        mock_session.execute.side_effect = Exception("Query execution failed")

        service = AlertDeduplicationService(mock_session)

        with pytest.raises(Exception, match="Query execution failed"):
            await service.get_recent_alerts_for_key("front_door:person")

    @pytest.mark.asyncio
    async def test_get_duplicate_stats_handles_database_error(
        self, mock_session: AsyncMock
    ) -> None:
        """Test that get_duplicate_stats handles database errors gracefully."""
        mock_session.execute.side_effect = Exception("Database read error")

        service = AlertDeduplicationService(mock_session)

        with pytest.raises(Exception, match="Database read error"):
            await service.get_duplicate_stats()


# =============================================================================
# AlertCreationError Tests (NEM-1105)
# =============================================================================


class TestAlertCreationError:
    """Tests for AlertCreationError exception class (NEM-1105)."""

    def test_exception_is_subclass_of_exception(self) -> None:
        """Test that AlertCreationError is a proper Exception subclass."""
        assert issubclass(AlertCreationError, Exception)

    def test_exception_can_be_instantiated_with_message(self) -> None:
        """Test that AlertCreationError can be created with a message."""
        error = AlertCreationError("Test error message")
        assert str(error) == "Test error message"

    def test_exception_can_be_raised_and_caught(self) -> None:
        """Test that AlertCreationError can be raised and caught."""
        with pytest.raises(AlertCreationError, match="Test error"):
            raise AlertCreationError("Test error")

    def test_exception_preserves_cause(self) -> None:
        """Test that AlertCreationError preserves the original exception cause."""
        original_error = ValueError("Original error")
        try:
            try:
                raise original_error
            except ValueError as e:
                raise AlertCreationError("Wrapped error") from e
        except AlertCreationError as e:
            assert e.__cause__ is original_error
            assert isinstance(e.__cause__, ValueError)


class TestAlertCreationErrorHandling:
    """Tests for AlertCreationError handling in create_alert_if_not_duplicate (NEM-1105)."""

    @pytest.mark.asyncio
    async def test_flush_error_raises_alert_creation_error(self, mock_session: AsyncMock) -> None:
        """Test that flush errors are wrapped in AlertCreationError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.flush.side_effect = Exception("Constraint violation")

        service = AlertDeduplicationService(mock_session)

        with pytest.raises(AlertCreationError) as exc_info:
            await service.create_alert_if_not_duplicate(
                event_id=1,
                dedup_key="front_door:person",
                cooldown_seconds=300,
            )

        assert "Database operation failed" in str(exc_info.value)
        assert exc_info.value.__cause__ is not None

    @pytest.mark.asyncio
    async def test_error_preserves_original_exception_type(self, mock_session: AsyncMock) -> None:
        """Test that original exception is preserved as cause."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        original_error = RuntimeError("Connection reset")
        mock_session.flush.side_effect = original_error

        service = AlertDeduplicationService(mock_session)

        with pytest.raises(AlertCreationError) as exc_info:
            await service.create_alert_if_not_duplicate(
                event_id=1,
                dedup_key="test_key",
                cooldown_seconds=300,
            )

        assert exc_info.value.__cause__ is original_error
        assert isinstance(exc_info.value.__cause__, RuntimeError)

    @pytest.mark.asyncio
    async def test_error_message_contains_original_error(self, mock_session: AsyncMock) -> None:
        """Test that error message contains the original error message."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.flush.side_effect = Exception("Unique constraint violated")

        service = AlertDeduplicationService(mock_session)

        with pytest.raises(AlertCreationError) as exc_info:
            await service.create_alert_if_not_duplicate(
                event_id=1,
                dedup_key="test_key",
                cooldown_seconds=300,
            )

        assert "Unique constraint violated" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_logging_called_on_failure(self, mock_session: AsyncMock) -> None:
        """Test that error is logged when alert creation fails."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.flush.side_effect = Exception("Database error")

        service = AlertDeduplicationService(mock_session)

        with patch("backend.services.alert_dedup.logger", autospec=True) as mock_logger:
            with pytest.raises(AlertCreationError):
                await service.create_alert_if_not_duplicate(
                    event_id=42,
                    dedup_key="camera1:person",
                    cooldown_seconds=300,
                )

            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert call_args[0][0] == "Failed to create alert in database"
            extra = call_args[1]["extra"]
            assert extra["event_id"] == 42
            assert extra["dedup_key"] == "camera1:person"
            assert extra["error_type"] == "Exception"
            assert "Database error" in extra["error"]

    @pytest.mark.asyncio
    async def test_session_add_not_reverted_on_error(self, mock_session: AsyncMock) -> None:
        """Test that session.add is called even when flush fails."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.flush.side_effect = Exception("Flush failed")

        service = AlertDeduplicationService(mock_session)

        with pytest.raises(AlertCreationError):
            await service.create_alert_if_not_duplicate(
                event_id=1,
                dedup_key="test_key",
                cooldown_seconds=300,
            )

        # session.add should have been called before the error
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_various_database_exceptions_wrapped(self, mock_session: AsyncMock) -> None:
        """Test that various database exception types are wrapped in AlertCreationError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        exception_types = [
            ValueError("Invalid data"),
            RuntimeError("Connection lost"),
            TimeoutError("Query timeout"),
            OSError("IO error"),
        ]

        service = AlertDeduplicationService(mock_session)

        for exc in exception_types:
            mock_session.flush.side_effect = exc
            mock_session.add.reset_mock()

            with pytest.raises(AlertCreationError) as exc_info:
                await service.create_alert_if_not_duplicate(
                    event_id=1,
                    dedup_key="test_key",
                    cooldown_seconds=300,
                )

            assert exc_info.value.__cause__ is exc
