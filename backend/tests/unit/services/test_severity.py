"""Unit tests for severity service.

Tests cover:
- SeverityService initialization with validation
- Risk score to severity mapping
- Severity definitions
- Severity comparison functions
- String conversion and color/priority utilities
- Cached singleton behavior
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.enums import Severity
from backend.services.severity import (
    SEVERITY_COLORS,
    SEVERITY_PRIORITY,
    SeverityDefinition,
    SeverityService,
    get_severity_color,
    get_severity_priority,
    get_severity_service,
    reset_severity_service,
    severity_from_string,
    severity_gt,
    severity_gte,
    severity_lt,
    severity_lte,
)
from backend.tests.strategies import severity_thresholds, valid_risk_scores

# =============================================================================
# SeverityService Initialization Tests
# =============================================================================


class TestSeverityServiceInit:
    """Tests for SeverityService initialization and validation."""

    def test_init_default_values(self) -> None:
        """Test initialization with default values from settings."""
        service = SeverityService()
        # Default values from settings: low_max=29, medium_max=59, high_max=84
        assert service.low_max == 29
        assert service.medium_max == 59
        assert service.high_max == 84

    def test_init_custom_values(self) -> None:
        """Test initialization with custom threshold values."""
        service = SeverityService(low_max=20, medium_max=50, high_max=80)
        assert service.low_max == 20
        assert service.medium_max == 50
        assert service.high_max == 80

    def test_init_boundary_values(self) -> None:
        """Test initialization with extreme boundary values."""
        # Minimum valid thresholds (all different, in order)
        service = SeverityService(low_max=0, medium_max=1, high_max=2)
        assert service.low_max == 0
        assert service.medium_max == 1
        assert service.high_max == 2

    def test_init_max_boundary_values(self) -> None:
        """Test initialization with maximum boundary values."""
        # Maximum valid thresholds
        service = SeverityService(low_max=97, medium_max=98, high_max=99)
        assert service.low_max == 97
        assert service.medium_max == 98
        assert service.high_max == 99

    def test_init_high_max_at_100(self) -> None:
        """Test initialization with high_max exactly at 100."""
        service = SeverityService(low_max=29, medium_max=59, high_max=100)
        assert service.high_max == 100

    def test_init_invalid_low_max_negative(self) -> None:
        """Test that low_max cannot be negative."""
        with pytest.raises(ValueError) as exc_info:
            SeverityService(low_max=-1, medium_max=50, high_max=80)
        assert "Invalid severity thresholds" in str(exc_info.value)
        assert "low_max=-1" in str(exc_info.value)

    def test_init_invalid_ordering_low_equals_medium(self) -> None:
        """Test that low_max must be strictly less than medium_max."""
        with pytest.raises(ValueError) as exc_info:
            SeverityService(low_max=50, medium_max=50, high_max=80)
        assert "Invalid severity thresholds" in str(exc_info.value)

    def test_init_invalid_ordering_low_greater_than_medium(self) -> None:
        """Test that low_max cannot be greater than medium_max."""
        with pytest.raises(ValueError) as exc_info:
            SeverityService(low_max=60, medium_max=50, high_max=80)
        assert "Invalid severity thresholds" in str(exc_info.value)

    def test_init_invalid_ordering_medium_equals_high(self) -> None:
        """Test that medium_max must be strictly less than high_max."""
        with pytest.raises(ValueError) as exc_info:
            SeverityService(low_max=20, medium_max=80, high_max=80)
        assert "Invalid severity thresholds" in str(exc_info.value)

    def test_init_invalid_ordering_medium_greater_than_high(self) -> None:
        """Test that medium_max cannot be greater than high_max."""
        with pytest.raises(ValueError) as exc_info:
            SeverityService(low_max=20, medium_max=90, high_max=80)
        assert "Invalid severity thresholds" in str(exc_info.value)

    def test_init_invalid_high_max_over_100(self) -> None:
        """Test that high_max cannot exceed 100."""
        with pytest.raises(ValueError) as exc_info:
            SeverityService(low_max=29, medium_max=59, high_max=101)
        assert "Invalid severity thresholds" in str(exc_info.value)


# =============================================================================
# Risk Score to Severity Mapping Tests
# =============================================================================


class TestRiskScoreToSeverity:
    """Tests for risk_score_to_severity method."""

    def test_score_zero(self) -> None:
        """Test that score 0 maps to LOW."""
        service = SeverityService()
        assert service.risk_score_to_severity(0) == Severity.LOW

    def test_score_at_low_max(self) -> None:
        """Test that score at low_max boundary maps to LOW."""
        service = SeverityService(low_max=29, medium_max=59, high_max=84)
        assert service.risk_score_to_severity(29) == Severity.LOW

    def test_score_at_medium_start(self) -> None:
        """Test that score at low_max+1 maps to MEDIUM."""
        service = SeverityService(low_max=29, medium_max=59, high_max=84)
        assert service.risk_score_to_severity(30) == Severity.MEDIUM

    def test_score_at_medium_max(self) -> None:
        """Test that score at medium_max boundary maps to MEDIUM."""
        service = SeverityService(low_max=29, medium_max=59, high_max=84)
        assert service.risk_score_to_severity(59) == Severity.MEDIUM

    def test_score_at_high_start(self) -> None:
        """Test that score at medium_max+1 maps to HIGH."""
        service = SeverityService(low_max=29, medium_max=59, high_max=84)
        assert service.risk_score_to_severity(60) == Severity.HIGH

    def test_score_at_high_max(self) -> None:
        """Test that score at high_max boundary maps to HIGH."""
        service = SeverityService(low_max=29, medium_max=59, high_max=84)
        assert service.risk_score_to_severity(84) == Severity.HIGH

    def test_score_at_critical_start(self) -> None:
        """Test that score at high_max+1 maps to CRITICAL."""
        service = SeverityService(low_max=29, medium_max=59, high_max=84)
        assert service.risk_score_to_severity(85) == Severity.CRITICAL

    def test_score_at_100(self) -> None:
        """Test that score 100 maps to CRITICAL."""
        service = SeverityService(low_max=29, medium_max=59, high_max=84)
        assert service.risk_score_to_severity(100) == Severity.CRITICAL

    def test_score_negative_raises_error(self) -> None:
        """Test that negative scores raise ValueError."""
        service = SeverityService()
        with pytest.raises(ValueError) as exc_info:
            service.risk_score_to_severity(-1)
        assert "Risk score must be between 0 and 100" in str(exc_info.value)

    def test_score_over_100_raises_error(self) -> None:
        """Test that scores over 100 raise ValueError."""
        service = SeverityService()
        with pytest.raises(ValueError) as exc_info:
            service.risk_score_to_severity(101)
        assert "Risk score must be between 0 and 100" in str(exc_info.value)

    def test_score_large_negative_raises_error(self) -> None:
        """Test that large negative scores raise ValueError."""
        service = SeverityService()
        with pytest.raises(ValueError) as exc_info:
            service.risk_score_to_severity(-1000)
        assert "Risk score must be between 0 and 100" in str(exc_info.value)

    def test_score_large_positive_raises_error(self) -> None:
        """Test that large positive scores raise ValueError."""
        service = SeverityService()
        with pytest.raises(ValueError) as exc_info:
            service.risk_score_to_severity(1000)
        assert "Risk score must be between 0 and 100" in str(exc_info.value)


class TestRiskScoreToSeverityParametrized:
    """Parametrized tests for risk score to severity mapping."""

    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            # LOW range (0-29)
            (0, Severity.LOW),
            (1, Severity.LOW),
            (15, Severity.LOW),
            (28, Severity.LOW),
            (29, Severity.LOW),
            # MEDIUM range (30-59)
            (30, Severity.MEDIUM),
            (31, Severity.MEDIUM),
            (45, Severity.MEDIUM),
            (58, Severity.MEDIUM),
            (59, Severity.MEDIUM),
            # HIGH range (60-84)
            (60, Severity.HIGH),
            (61, Severity.HIGH),
            (72, Severity.HIGH),
            (83, Severity.HIGH),
            (84, Severity.HIGH),
            # CRITICAL range (85-100)
            (85, Severity.CRITICAL),
            (86, Severity.CRITICAL),
            (92, Severity.CRITICAL),
            (99, Severity.CRITICAL),
            (100, Severity.CRITICAL),
        ],
    )
    def test_score_mapping(self, score: int, expected: Severity) -> None:
        """Test score to severity mapping with default thresholds."""
        service = SeverityService()
        assert service.risk_score_to_severity(score) == expected

    @pytest.mark.parametrize(
        "score",
        [-100, -10, -1, 101, 110, 1000],
    )
    def test_invalid_scores_raise_error(self, score: int) -> None:
        """Test that out-of-range scores raise ValueError."""
        service = SeverityService()
        with pytest.raises(ValueError):
            service.risk_score_to_severity(score)


class TestRiskScoreToSeverityCustomThresholds:
    """Tests for risk score mapping with custom thresholds."""

    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (0, Severity.LOW),
            (19, Severity.LOW),
            (20, Severity.LOW),
            (21, Severity.MEDIUM),
            (49, Severity.MEDIUM),
            (50, Severity.MEDIUM),
            (51, Severity.HIGH),
            (79, Severity.HIGH),
            (80, Severity.HIGH),
            (81, Severity.CRITICAL),
            (100, Severity.CRITICAL),
        ],
    )
    def test_custom_thresholds(self, score: int, expected: Severity) -> None:
        """Test score mapping with custom thresholds (20, 50, 80)."""
        service = SeverityService(low_max=20, medium_max=50, high_max=80)
        assert service.risk_score_to_severity(score) == expected


# =============================================================================
# Severity Definitions Tests
# =============================================================================


class TestGetSeverityDefinitions:
    """Tests for get_severity_definitions method."""

    def test_returns_all_four_levels(self) -> None:
        """Test that definitions include all four severity levels."""
        service = SeverityService()
        definitions = service.get_severity_definitions()
        assert len(definitions) == 4

    def test_definitions_ordered_by_severity(self) -> None:
        """Test that definitions are ordered from LOW to CRITICAL."""
        service = SeverityService()
        definitions = service.get_severity_definitions()
        severities = [d.severity for d in definitions]
        assert severities == [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]

    def test_low_definition_correct(self) -> None:
        """Test LOW severity definition."""
        service = SeverityService(low_max=29, medium_max=59, high_max=84)
        definitions = service.get_severity_definitions()
        low_def = definitions[0]

        assert low_def.severity == Severity.LOW
        assert low_def.label == "Low"
        assert low_def.description == "Routine activity, no concern"
        assert low_def.color == SEVERITY_COLORS[Severity.LOW]
        assert low_def.priority == SEVERITY_PRIORITY[Severity.LOW]
        assert low_def.min_score == 0
        assert low_def.max_score == 29

    def test_medium_definition_correct(self) -> None:
        """Test MEDIUM severity definition."""
        service = SeverityService(low_max=29, medium_max=59, high_max=84)
        definitions = service.get_severity_definitions()
        medium_def = definitions[1]

        assert medium_def.severity == Severity.MEDIUM
        assert medium_def.label == "Medium"
        assert medium_def.description == "Notable activity, worth reviewing"
        assert medium_def.color == SEVERITY_COLORS[Severity.MEDIUM]
        assert medium_def.priority == SEVERITY_PRIORITY[Severity.MEDIUM]
        assert medium_def.min_score == 30
        assert medium_def.max_score == 59

    def test_high_definition_correct(self) -> None:
        """Test HIGH severity definition."""
        service = SeverityService(low_max=29, medium_max=59, high_max=84)
        definitions = service.get_severity_definitions()
        high_def = definitions[2]

        assert high_def.severity == Severity.HIGH
        assert high_def.label == "High"
        assert high_def.description == "Concerning activity, review soon"
        assert high_def.color == SEVERITY_COLORS[Severity.HIGH]
        assert high_def.priority == SEVERITY_PRIORITY[Severity.HIGH]
        assert high_def.min_score == 60
        assert high_def.max_score == 84

    def test_critical_definition_correct(self) -> None:
        """Test CRITICAL severity definition."""
        service = SeverityService(low_max=29, medium_max=59, high_max=84)
        definitions = service.get_severity_definitions()
        critical_def = definitions[3]

        assert critical_def.severity == Severity.CRITICAL
        assert critical_def.label == "Critical"
        assert critical_def.description == "Immediate attention required"
        assert critical_def.color == SEVERITY_COLORS[Severity.CRITICAL]
        assert critical_def.priority == SEVERITY_PRIORITY[Severity.CRITICAL]
        assert critical_def.min_score == 85
        assert critical_def.max_score == 100

    def test_definitions_with_custom_thresholds(self) -> None:
        """Test definitions reflect custom thresholds."""
        service = SeverityService(low_max=20, medium_max=50, high_max=80)
        definitions = service.get_severity_definitions()

        assert definitions[0].min_score == 0
        assert definitions[0].max_score == 20  # low_max

        assert definitions[1].min_score == 21  # low_max + 1
        assert definitions[1].max_score == 50  # medium_max

        assert definitions[2].min_score == 51  # medium_max + 1
        assert definitions[2].max_score == 80  # high_max

        assert definitions[3].min_score == 81  # high_max + 1
        assert definitions[3].max_score == 100

    def test_definitions_score_ranges_are_contiguous(self) -> None:
        """Test that score ranges are contiguous with no gaps or overlaps."""
        service = SeverityService()
        definitions = service.get_severity_definitions()

        # Check first starts at 0
        assert definitions[0].min_score == 0

        # Check last ends at 100
        assert definitions[-1].max_score == 100

        # Check contiguity
        for i in range(len(definitions) - 1):
            current_max = definitions[i].max_score
            next_min = definitions[i + 1].min_score
            assert next_min == current_max + 1, (
                f"Gap between {definitions[i].severity} and {definitions[i + 1].severity}"
            )


class TestSeverityDefinitionToDict:
    """Tests for SeverityDefinition.to_dict method."""

    def test_to_dict_returns_correct_structure(self) -> None:
        """Test that to_dict returns correct dictionary structure."""
        definition = SeverityDefinition(
            severity=Severity.HIGH,
            label="High",
            description="Test description",
            color="#f97316",
            priority=1,
            min_score=60,
            max_score=84,
        )
        result = definition.to_dict()

        assert result == {
            "severity": "high",
            "label": "High",
            "description": "Test description",
            "color": "#f97316",
            "priority": 1,
            "min_score": 60,
            "max_score": 84,
        }

    def test_to_dict_severity_value_is_string(self) -> None:
        """Test that to_dict converts severity to its string value."""
        definition = SeverityDefinition(
            severity=Severity.CRITICAL,
            label="Critical",
            description="Test",
            color="#ef4444",
            priority=0,
            min_score=85,
            max_score=100,
        )
        result = definition.to_dict()

        assert isinstance(result["severity"], str)
        assert result["severity"] == "critical"


# =============================================================================
# Get Thresholds Tests
# =============================================================================


class TestGetThresholds:
    """Tests for get_thresholds method."""

    def test_get_thresholds_default(self) -> None:
        """Test get_thresholds returns default thresholds."""
        service = SeverityService()
        thresholds = service.get_thresholds()

        assert thresholds == {
            "low_max": 29,
            "medium_max": 59,
            "high_max": 84,
        }

    def test_get_thresholds_custom(self) -> None:
        """Test get_thresholds returns custom thresholds."""
        service = SeverityService(low_max=20, medium_max=50, high_max=80)
        thresholds = service.get_thresholds()

        assert thresholds == {
            "low_max": 20,
            "medium_max": 50,
            "high_max": 80,
        }


# =============================================================================
# Severity Color Tests
# =============================================================================


class TestGetSeverityColor:
    """Tests for get_severity_color utility function."""

    def test_low_color(self) -> None:
        """Test LOW severity color."""
        assert get_severity_color(Severity.LOW) == "#22c55e"

    def test_medium_color(self) -> None:
        """Test MEDIUM severity color."""
        assert get_severity_color(Severity.MEDIUM) == "#eab308"

    def test_high_color(self) -> None:
        """Test HIGH severity color."""
        assert get_severity_color(Severity.HIGH) == "#f97316"

    def test_critical_color(self) -> None:
        """Test CRITICAL severity color."""
        assert get_severity_color(Severity.CRITICAL) == "#ef4444"

    @pytest.mark.parametrize(
        ("severity", "expected_color"),
        [
            (Severity.LOW, "#22c55e"),
            (Severity.MEDIUM, "#eab308"),
            (Severity.HIGH, "#f97316"),
            (Severity.CRITICAL, "#ef4444"),
        ],
    )
    def test_all_colors_parametrized(self, severity: Severity, expected_color: str) -> None:
        """Parametrized test for all severity colors."""
        assert get_severity_color(severity) == expected_color


# =============================================================================
# Severity Priority Tests
# =============================================================================


class TestGetSeverityPriority:
    """Tests for get_severity_priority utility function."""

    def test_critical_priority(self) -> None:
        """Test CRITICAL has highest priority (0)."""
        assert get_severity_priority(Severity.CRITICAL) == 0

    def test_high_priority(self) -> None:
        """Test HIGH priority (1)."""
        assert get_severity_priority(Severity.HIGH) == 1

    def test_medium_priority(self) -> None:
        """Test MEDIUM priority (2)."""
        assert get_severity_priority(Severity.MEDIUM) == 2

    def test_low_priority(self) -> None:
        """Test LOW has lowest priority (3)."""
        assert get_severity_priority(Severity.LOW) == 3

    def test_priority_ordering_critical_highest(self) -> None:
        """Test that CRITICAL has the lowest priority number (highest priority)."""
        assert get_severity_priority(Severity.CRITICAL) < get_severity_priority(Severity.HIGH)
        assert get_severity_priority(Severity.HIGH) < get_severity_priority(Severity.MEDIUM)
        assert get_severity_priority(Severity.MEDIUM) < get_severity_priority(Severity.LOW)

    @pytest.mark.parametrize(
        ("severity", "expected_priority"),
        [
            (Severity.CRITICAL, 0),
            (Severity.HIGH, 1),
            (Severity.MEDIUM, 2),
            (Severity.LOW, 3),
        ],
    )
    def test_all_priorities_parametrized(self, severity: Severity, expected_priority: int) -> None:
        """Parametrized test for all severity priorities."""
        assert get_severity_priority(severity) == expected_priority


# =============================================================================
# Severity Comparison Tests
# =============================================================================


class TestSeverityGte:
    """Tests for severity_gte (greater than or equal) comparison."""

    def test_critical_gte_all(self) -> None:
        """Test CRITICAL is >= all severity levels."""
        assert severity_gte(Severity.CRITICAL, Severity.LOW)
        assert severity_gte(Severity.CRITICAL, Severity.MEDIUM)
        assert severity_gte(Severity.CRITICAL, Severity.HIGH)
        assert severity_gte(Severity.CRITICAL, Severity.CRITICAL)

    def test_high_gte_lower_and_equal(self) -> None:
        """Test HIGH is >= LOW, MEDIUM, and HIGH."""
        assert severity_gte(Severity.HIGH, Severity.LOW)
        assert severity_gte(Severity.HIGH, Severity.MEDIUM)
        assert severity_gte(Severity.HIGH, Severity.HIGH)
        assert not severity_gte(Severity.HIGH, Severity.CRITICAL)

    def test_medium_gte_lower_and_equal(self) -> None:
        """Test MEDIUM is >= LOW and MEDIUM only."""
        assert severity_gte(Severity.MEDIUM, Severity.LOW)
        assert severity_gte(Severity.MEDIUM, Severity.MEDIUM)
        assert not severity_gte(Severity.MEDIUM, Severity.HIGH)
        assert not severity_gte(Severity.MEDIUM, Severity.CRITICAL)

    def test_low_gte_only_self(self) -> None:
        """Test LOW is >= only LOW."""
        assert severity_gte(Severity.LOW, Severity.LOW)
        assert not severity_gte(Severity.LOW, Severity.MEDIUM)
        assert not severity_gte(Severity.LOW, Severity.HIGH)
        assert not severity_gte(Severity.LOW, Severity.CRITICAL)


class TestSeverityGt:
    """Tests for severity_gt (strictly greater than) comparison."""

    def test_critical_gt_lower_levels(self) -> None:
        """Test CRITICAL is > all lower severity levels."""
        assert severity_gt(Severity.CRITICAL, Severity.LOW)
        assert severity_gt(Severity.CRITICAL, Severity.MEDIUM)
        assert severity_gt(Severity.CRITICAL, Severity.HIGH)
        assert not severity_gt(Severity.CRITICAL, Severity.CRITICAL)

    def test_high_gt_lower_levels(self) -> None:
        """Test HIGH is > LOW and MEDIUM only."""
        assert severity_gt(Severity.HIGH, Severity.LOW)
        assert severity_gt(Severity.HIGH, Severity.MEDIUM)
        assert not severity_gt(Severity.HIGH, Severity.HIGH)
        assert not severity_gt(Severity.HIGH, Severity.CRITICAL)

    def test_medium_gt_low_only(self) -> None:
        """Test MEDIUM is > LOW only."""
        assert severity_gt(Severity.MEDIUM, Severity.LOW)
        assert not severity_gt(Severity.MEDIUM, Severity.MEDIUM)
        assert not severity_gt(Severity.MEDIUM, Severity.HIGH)
        assert not severity_gt(Severity.MEDIUM, Severity.CRITICAL)

    def test_low_gt_none(self) -> None:
        """Test LOW is not > any severity level."""
        assert not severity_gt(Severity.LOW, Severity.LOW)
        assert not severity_gt(Severity.LOW, Severity.MEDIUM)
        assert not severity_gt(Severity.LOW, Severity.HIGH)
        assert not severity_gt(Severity.LOW, Severity.CRITICAL)


class TestSeverityLte:
    """Tests for severity_lte (less than or equal) comparison."""

    def test_low_lte_all(self) -> None:
        """Test LOW is <= all severity levels."""
        assert severity_lte(Severity.LOW, Severity.LOW)
        assert severity_lte(Severity.LOW, Severity.MEDIUM)
        assert severity_lte(Severity.LOW, Severity.HIGH)
        assert severity_lte(Severity.LOW, Severity.CRITICAL)

    def test_medium_lte_higher_and_equal(self) -> None:
        """Test MEDIUM is <= MEDIUM, HIGH, and CRITICAL."""
        assert not severity_lte(Severity.MEDIUM, Severity.LOW)
        assert severity_lte(Severity.MEDIUM, Severity.MEDIUM)
        assert severity_lte(Severity.MEDIUM, Severity.HIGH)
        assert severity_lte(Severity.MEDIUM, Severity.CRITICAL)

    def test_high_lte_higher_and_equal(self) -> None:
        """Test HIGH is <= HIGH and CRITICAL only."""
        assert not severity_lte(Severity.HIGH, Severity.LOW)
        assert not severity_lte(Severity.HIGH, Severity.MEDIUM)
        assert severity_lte(Severity.HIGH, Severity.HIGH)
        assert severity_lte(Severity.HIGH, Severity.CRITICAL)

    def test_critical_lte_only_self(self) -> None:
        """Test CRITICAL is <= only CRITICAL."""
        assert not severity_lte(Severity.CRITICAL, Severity.LOW)
        assert not severity_lte(Severity.CRITICAL, Severity.MEDIUM)
        assert not severity_lte(Severity.CRITICAL, Severity.HIGH)
        assert severity_lte(Severity.CRITICAL, Severity.CRITICAL)


class TestSeverityLt:
    """Tests for severity_lt (strictly less than) comparison."""

    def test_low_lt_higher_levels(self) -> None:
        """Test LOW is < all higher severity levels."""
        assert not severity_lt(Severity.LOW, Severity.LOW)
        assert severity_lt(Severity.LOW, Severity.MEDIUM)
        assert severity_lt(Severity.LOW, Severity.HIGH)
        assert severity_lt(Severity.LOW, Severity.CRITICAL)

    def test_medium_lt_higher_levels(self) -> None:
        """Test MEDIUM is < HIGH and CRITICAL only."""
        assert not severity_lt(Severity.MEDIUM, Severity.LOW)
        assert not severity_lt(Severity.MEDIUM, Severity.MEDIUM)
        assert severity_lt(Severity.MEDIUM, Severity.HIGH)
        assert severity_lt(Severity.MEDIUM, Severity.CRITICAL)

    def test_high_lt_critical_only(self) -> None:
        """Test HIGH is < CRITICAL only."""
        assert not severity_lt(Severity.HIGH, Severity.LOW)
        assert not severity_lt(Severity.HIGH, Severity.MEDIUM)
        assert not severity_lt(Severity.HIGH, Severity.HIGH)
        assert severity_lt(Severity.HIGH, Severity.CRITICAL)

    def test_critical_lt_none(self) -> None:
        """Test CRITICAL is not < any severity level."""
        assert not severity_lt(Severity.CRITICAL, Severity.LOW)
        assert not severity_lt(Severity.CRITICAL, Severity.MEDIUM)
        assert not severity_lt(Severity.CRITICAL, Severity.HIGH)
        assert not severity_lt(Severity.CRITICAL, Severity.CRITICAL)


class TestSeverityComparisonParametrized:
    """Parametrized tests for severity comparisons."""

    @pytest.mark.parametrize(
        ("a", "b", "expected_gte", "expected_gt", "expected_lte", "expected_lt"),
        [
            # Same severity
            (Severity.LOW, Severity.LOW, True, False, True, False),
            (Severity.MEDIUM, Severity.MEDIUM, True, False, True, False),
            (Severity.HIGH, Severity.HIGH, True, False, True, False),
            (Severity.CRITICAL, Severity.CRITICAL, True, False, True, False),
            # LOW vs others
            (Severity.LOW, Severity.MEDIUM, False, False, True, True),
            (Severity.LOW, Severity.HIGH, False, False, True, True),
            (Severity.LOW, Severity.CRITICAL, False, False, True, True),
            # MEDIUM vs others
            (Severity.MEDIUM, Severity.LOW, True, True, False, False),
            (Severity.MEDIUM, Severity.HIGH, False, False, True, True),
            (Severity.MEDIUM, Severity.CRITICAL, False, False, True, True),
            # HIGH vs others
            (Severity.HIGH, Severity.LOW, True, True, False, False),
            (Severity.HIGH, Severity.MEDIUM, True, True, False, False),
            (Severity.HIGH, Severity.CRITICAL, False, False, True, True),
            # CRITICAL vs others
            (Severity.CRITICAL, Severity.LOW, True, True, False, False),
            (Severity.CRITICAL, Severity.MEDIUM, True, True, False, False),
            (Severity.CRITICAL, Severity.HIGH, True, True, False, False),
        ],
    )
    def test_all_comparisons(
        self,
        a: Severity,
        b: Severity,
        expected_gte: bool,
        expected_gt: bool,
        expected_lte: bool,
        expected_lt: bool,
    ) -> None:
        """Parametrized test for all comparison combinations."""
        assert severity_gte(a, b) == expected_gte, f"gte({a}, {b}) should be {expected_gte}"
        assert severity_gt(a, b) == expected_gt, f"gt({a}, {b}) should be {expected_gt}"
        assert severity_lte(a, b) == expected_lte, f"lte({a}, {b}) should be {expected_lte}"
        assert severity_lt(a, b) == expected_lt, f"lt({a}, {b}) should be {expected_lt}"


# =============================================================================
# Severity From String Tests
# =============================================================================


class TestSeverityFromString:
    """Tests for severity_from_string utility function."""

    def test_lowercase_values(self) -> None:
        """Test parsing lowercase severity strings."""
        assert severity_from_string("low") == Severity.LOW
        assert severity_from_string("medium") == Severity.MEDIUM
        assert severity_from_string("high") == Severity.HIGH
        assert severity_from_string("critical") == Severity.CRITICAL

    def test_uppercase_values(self) -> None:
        """Test parsing uppercase severity strings (case insensitive)."""
        assert severity_from_string("LOW") == Severity.LOW
        assert severity_from_string("MEDIUM") == Severity.MEDIUM
        assert severity_from_string("HIGH") == Severity.HIGH
        assert severity_from_string("CRITICAL") == Severity.CRITICAL

    def test_mixed_case_values(self) -> None:
        """Test parsing mixed case severity strings (case insensitive)."""
        assert severity_from_string("Low") == Severity.LOW
        assert severity_from_string("Medium") == Severity.MEDIUM
        assert severity_from_string("High") == Severity.HIGH
        assert severity_from_string("Critical") == Severity.CRITICAL
        assert severity_from_string("cRiTiCaL") == Severity.CRITICAL
        assert severity_from_string("mEdIuM") == Severity.MEDIUM

    def test_invalid_value_raises_error(self) -> None:
        """Test that invalid values raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            severity_from_string("invalid")
        assert "Invalid severity value" in str(exc_info.value)
        assert "'invalid'" in str(exc_info.value)
        assert "low" in str(exc_info.value)  # Should list valid values

    def test_empty_string_raises_error(self) -> None:
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            severity_from_string("")
        assert "Invalid severity value" in str(exc_info.value)

    def test_whitespace_only_raises_error(self) -> None:
        """Test that whitespace-only string raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            severity_from_string("   ")
        assert "Invalid severity value" in str(exc_info.value)

    def test_partial_match_raises_error(self) -> None:
        """Test that partial matches raise ValueError."""
        with pytest.raises(ValueError):
            severity_from_string("lo")
        with pytest.raises(ValueError):
            severity_from_string("med")
        with pytest.raises(ValueError):
            severity_from_string("hi")
        with pytest.raises(ValueError):
            severity_from_string("crit")

    def test_numeric_string_raises_error(self) -> None:
        """Test that numeric strings raise ValueError."""
        with pytest.raises(ValueError):
            severity_from_string("1")
        with pytest.raises(ValueError):
            severity_from_string("0")
        with pytest.raises(ValueError):
            severity_from_string("100")

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("low", Severity.LOW),
            ("LOW", Severity.LOW),
            ("Low", Severity.LOW),
            ("medium", Severity.MEDIUM),
            ("MEDIUM", Severity.MEDIUM),
            ("Medium", Severity.MEDIUM),
            ("high", Severity.HIGH),
            ("HIGH", Severity.HIGH),
            ("High", Severity.HIGH),
            ("critical", Severity.CRITICAL),
            ("CRITICAL", Severity.CRITICAL),
            ("Critical", Severity.CRITICAL),
        ],
    )
    def test_valid_values_parametrized(self, value: str, expected: Severity) -> None:
        """Parametrized test for valid severity strings."""
        assert severity_from_string(value) == expected

    @pytest.mark.parametrize(
        "value",
        [
            "invalid",
            "",
            "none",
            "warning",
            "error",
            "info",
            "debug",
            "severe",
            "minor",
            "major",
        ],
    )
    def test_invalid_values_parametrized(self, value: str) -> None:
        """Parametrized test for invalid severity strings."""
        with pytest.raises(ValueError):
            severity_from_string(value)


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSeveritySingleton:
    """Tests for severity service singleton functions."""

    def test_get_severity_service_creates_singleton(self) -> None:
        """Test that get_severity_service creates and returns singleton."""
        reset_severity_service()
        service1 = get_severity_service()
        service2 = get_severity_service()

        assert service1 is service2
        reset_severity_service()

    def test_reset_severity_service_clears_cache(self) -> None:
        """Test that reset_severity_service clears the singleton."""
        service1 = get_severity_service()
        reset_severity_service()
        service2 = get_severity_service()

        # After reset, a new instance should be created
        # Note: The instances may have same values but could be different objects
        # depending on caching behavior
        assert service1 is not service2
        reset_severity_service()

    def test_singleton_has_default_thresholds(self) -> None:
        """Test that singleton uses default thresholds."""
        reset_severity_service()
        service = get_severity_service()

        assert service.low_max == 29
        assert service.medium_max == 59
        assert service.high_max == 84
        reset_severity_service()


# =============================================================================
# Constants Tests
# =============================================================================


class TestSeverityConstants:
    """Tests for SEVERITY_COLORS and SEVERITY_PRIORITY constants."""

    def test_severity_colors_contains_all_levels(self) -> None:
        """Test SEVERITY_COLORS contains all severity levels."""
        assert Severity.LOW in SEVERITY_COLORS
        assert Severity.MEDIUM in SEVERITY_COLORS
        assert Severity.HIGH in SEVERITY_COLORS
        assert Severity.CRITICAL in SEVERITY_COLORS

    def test_severity_colors_are_hex_codes(self) -> None:
        """Test that all colors are valid hex codes."""
        import re

        hex_pattern = re.compile(r"^#[0-9a-fA-F]{6}$")
        for severity, color in SEVERITY_COLORS.items():
            assert hex_pattern.match(color), f"Color for {severity} is not valid hex: {color}"

    def test_severity_priority_contains_all_levels(self) -> None:
        """Test SEVERITY_PRIORITY contains all severity levels."""
        assert Severity.LOW in SEVERITY_PRIORITY
        assert Severity.MEDIUM in SEVERITY_PRIORITY
        assert Severity.HIGH in SEVERITY_PRIORITY
        assert Severity.CRITICAL in SEVERITY_PRIORITY

    def test_severity_priority_values_are_unique(self) -> None:
        """Test that all priority values are unique."""
        priorities = list(SEVERITY_PRIORITY.values())
        assert len(priorities) == len(set(priorities))

    def test_severity_priority_critical_is_highest(self) -> None:
        """Test that CRITICAL has the lowest number (highest priority)."""
        min_priority = min(SEVERITY_PRIORITY.values())
        assert SEVERITY_PRIORITY[Severity.CRITICAL] == min_priority

    def test_severity_priority_low_is_lowest(self) -> None:
        """Test that LOW has the highest number (lowest priority)."""
        max_priority = max(SEVERITY_PRIORITY.values())
        assert SEVERITY_PRIORITY[Severity.LOW] == max_priority


# =============================================================================
# SeverityDefinition Frozen Dataclass Tests
# =============================================================================


class TestSeverityDefinitionImmutable:
    """Tests for SeverityDefinition frozen dataclass behavior."""

    def test_definition_is_immutable(self) -> None:
        """Test that SeverityDefinition instances are immutable."""
        definition = SeverityDefinition(
            severity=Severity.LOW,
            label="Low",
            description="Test",
            color="#22c55e",
            priority=3,
            min_score=0,
            max_score=29,
        )

        with pytest.raises(AttributeError):
            definition.label = "Changed"  # type: ignore[misc]

        with pytest.raises(AttributeError):
            definition.min_score = 10  # type: ignore[misc]

    def test_definition_equality(self) -> None:
        """Test SeverityDefinition equality comparison."""
        def1 = SeverityDefinition(
            severity=Severity.LOW,
            label="Low",
            description="Test",
            color="#22c55e",
            priority=3,
            min_score=0,
            max_score=29,
        )
        def2 = SeverityDefinition(
            severity=Severity.LOW,
            label="Low",
            description="Test",
            color="#22c55e",
            priority=3,
            min_score=0,
            max_score=29,
        )
        def3 = SeverityDefinition(
            severity=Severity.HIGH,
            label="High",
            description="Test",
            color="#f97316",
            priority=1,
            min_score=60,
            max_score=84,
        )

        assert def1 == def2
        assert def1 != def3

    def test_definition_hashable(self) -> None:
        """Test that SeverityDefinition is hashable."""
        definition = SeverityDefinition(
            severity=Severity.LOW,
            label="Low",
            description="Test",
            color="#22c55e",
            priority=3,
            min_score=0,
            max_score=29,
        )

        # Should be able to use as dict key or in set
        definition_set = {definition}
        assert definition in definition_set
        definition_dict = {definition: "value"}
        assert definition_dict[definition] == "value"


# =============================================================================
# Hypothesis Property-Based Tests
# =============================================================================
# These tests use Hypothesis to discover edge cases through random input generation.
# They verify invariants that must hold for all valid inputs.


class TestSeverityHypothesis:
    """Property-based tests for severity service using Hypothesis."""

    @given(score=valid_risk_scores)
    @settings(max_examples=100)
    def test_risk_score_always_bounded_0_100(self, score: int) -> None:
        """Property: risk_score_to_severity accepts all values in [0, 100]."""
        service = SeverityService()
        # Should not raise for any valid score
        result = service.risk_score_to_severity(score)
        assert result in [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]

    @given(score=valid_risk_scores)
    @settings(max_examples=100)
    def test_severity_mapping_is_deterministic(self, score: int) -> None:
        """Property: Same score always maps to same severity (determinism)."""
        service = SeverityService()
        result1 = service.risk_score_to_severity(score)
        result2 = service.risk_score_to_severity(score)
        assert result1 == result2

    @given(thresholds=severity_thresholds())
    @settings(max_examples=50)
    def test_custom_thresholds_always_valid(self, thresholds: tuple[int, int, int]) -> None:
        """Property: Valid threshold tuples always create valid services."""
        low_max, medium_max, high_max = thresholds
        service = SeverityService(low_max=low_max, medium_max=medium_max, high_max=high_max)

        assert service.low_max == low_max
        assert service.medium_max == medium_max
        assert service.high_max == high_max

    @given(
        score1=valid_risk_scores,
        score2=valid_risk_scores,
    )
    @settings(max_examples=100)
    def test_severity_ordering_consistent_with_score_ordering(
        self, score1: int, score2: int
    ) -> None:
        """Property: Higher risk score implies equal or higher severity."""
        service = SeverityService()
        sev1 = service.risk_score_to_severity(score1)
        sev2 = service.risk_score_to_severity(score2)

        # If score1 > score2, then severity1 >= severity2
        # (using priority where lower number = higher severity)
        if score1 > score2:
            assert get_severity_priority(sev1) <= get_severity_priority(sev2)
        elif score1 < score2:
            assert get_severity_priority(sev1) >= get_severity_priority(sev2)
        else:
            assert sev1 == sev2

    @given(thresholds=severity_thresholds(), score=valid_risk_scores)
    @settings(max_examples=100)
    def test_score_range_coverage_is_complete(
        self, thresholds: tuple[int, int, int], score: int
    ) -> None:
        """Property: Every valid score maps to exactly one severity level."""
        low_max, medium_max, high_max = thresholds
        service = SeverityService(low_max=low_max, medium_max=medium_max, high_max=high_max)

        result = service.risk_score_to_severity(score)

        # Result is exactly one of the four severities
        assert result in [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]

        # Verify correct range mapping
        if score <= low_max:
            assert result == Severity.LOW
        elif score <= medium_max:
            assert result == Severity.MEDIUM
        elif score <= high_max:
            assert result == Severity.HIGH
        else:
            assert result == Severity.CRITICAL

    @given(thresholds=severity_thresholds())
    @settings(max_examples=50)
    def test_definitions_score_ranges_contiguous(self, thresholds: tuple[int, int, int]) -> None:
        """Property: Severity definitions have contiguous, non-overlapping score ranges."""
        low_max, medium_max, high_max = thresholds
        service = SeverityService(low_max=low_max, medium_max=medium_max, high_max=high_max)

        definitions = service.get_severity_definitions()

        # First range starts at 0
        assert definitions[0].min_score == 0

        # Last range ends at 100
        assert definitions[-1].max_score == 100

        # Check contiguity - each range starts where the previous ended + 1
        for i in range(len(definitions) - 1):
            current_max = definitions[i].max_score
            next_min = definitions[i + 1].min_score
            assert next_min == current_max + 1, (
                f"Gap between {definitions[i].severity} and {definitions[i + 1].severity}"
            )

    @given(sev_a=st.sampled_from(list(Severity)), sev_b=st.sampled_from(list(Severity)))
    @settings(max_examples=50)
    def test_severity_comparison_reflexivity(self, sev_a: Severity, sev_b: Severity) -> None:
        """Property: Severity comparison is reflexive (a >= a is always true)."""
        assert severity_gte(sev_a, sev_a)
        assert severity_lte(sev_a, sev_a)
        assert not severity_gt(sev_a, sev_a)
        assert not severity_lt(sev_a, sev_a)

    @given(sev_a=st.sampled_from(list(Severity)), sev_b=st.sampled_from(list(Severity)))
    @settings(max_examples=50)
    def test_severity_comparison_antisymmetry(self, sev_a: Severity, sev_b: Severity) -> None:
        """Property: If a > b, then not (b > a) - antisymmetric for strict comparison."""
        if severity_gt(sev_a, sev_b):
            assert not severity_gt(sev_b, sev_a)
            assert severity_lt(sev_b, sev_a)

    @given(
        sev_a=st.sampled_from(list(Severity)),
        sev_b=st.sampled_from(list(Severity)),
        sev_c=st.sampled_from(list(Severity)),
    )
    @settings(max_examples=100)
    def test_severity_comparison_transitivity(
        self, sev_a: Severity, sev_b: Severity, sev_c: Severity
    ) -> None:
        """Property: If a >= b and b >= c, then a >= c (transitivity)."""
        if severity_gte(sev_a, sev_b) and severity_gte(sev_b, sev_c):
            assert severity_gte(sev_a, sev_c)

    @given(sev=st.sampled_from(list(Severity)))
    @settings(max_examples=20)
    def test_severity_string_roundtrip(self, sev: Severity) -> None:
        """Property: Severity survives string roundtrip conversion."""
        as_string = sev.value
        recovered = severity_from_string(as_string)
        assert recovered == sev

    @given(sev=st.sampled_from(list(Severity)))
    @settings(max_examples=20)
    def test_severity_priority_is_consistent(self, sev: Severity) -> None:
        """Property: Severity priority is always consistent with comparison operators."""
        for other in Severity:
            prio_sev = get_severity_priority(sev)
            prio_other = get_severity_priority(other)

            # Lower priority number = higher severity
            if prio_sev < prio_other:
                assert severity_gt(sev, other)
                assert severity_gte(sev, other)
            elif prio_sev > prio_other:
                assert severity_lt(sev, other)
                assert severity_lte(sev, other)
            else:
                assert not severity_gt(sev, other)
                assert not severity_lt(sev, other)
                assert severity_gte(sev, other)
                assert severity_lte(sev, other)


class TestSeverityEdgeCasesHypothesis:
    """Property tests for edge cases discovered by Hypothesis."""

    @given(
        low=st.integers(min_value=0, max_value=98),
    )
    @settings(max_examples=50)
    def test_minimal_threshold_gaps_work(self, low: int) -> None:
        """Property: Thresholds with minimal gaps (1 apart) still work correctly."""
        # Create thresholds with minimal gaps
        low_max = low
        medium_max = min(99, low + 1)
        high_max = min(100, medium_max + 1)

        # Skip invalid configurations
        if not (low_max < medium_max < high_max <= 100):
            return

        service = SeverityService(low_max=low_max, medium_max=medium_max, high_max=high_max)

        # Boundary tests
        assert service.risk_score_to_severity(low_max) == Severity.LOW
        assert service.risk_score_to_severity(low_max + 1) == Severity.MEDIUM
        assert service.risk_score_to_severity(medium_max) == Severity.MEDIUM
        if medium_max + 1 <= high_max:
            assert service.risk_score_to_severity(medium_max + 1) == Severity.HIGH

    @given(score=st.integers(min_value=-1000, max_value=-1))
    @settings(max_examples=25)
    def test_negative_scores_always_rejected(self, score: int) -> None:
        """Property: Negative risk scores are always rejected."""
        service = SeverityService()
        with pytest.raises(ValueError) as exc_info:
            service.risk_score_to_severity(score)
        assert "Risk score must be between 0 and 100" in str(exc_info.value)

    @given(score=st.integers(min_value=101, max_value=10000))
    @settings(max_examples=25)
    def test_scores_over_100_always_rejected(self, score: int) -> None:
        """Property: Risk scores over 100 are always rejected."""
        service = SeverityService()
        with pytest.raises(ValueError) as exc_info:
            service.risk_score_to_severity(score)
        assert "Risk score must be between 0 and 100" in str(exc_info.value)

    def test_boundary_scores_edge_case(self) -> None:
        """Edge case: Verify exact boundary behavior at 0 and 100."""
        service = SeverityService()

        # Score 0 should be LOW
        assert service.risk_score_to_severity(0) == Severity.LOW

        # Score 100 should be CRITICAL
        assert service.risk_score_to_severity(100) == Severity.CRITICAL
