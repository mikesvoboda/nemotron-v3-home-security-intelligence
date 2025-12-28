"""Unit tests for severity service and utilities.

Tests cover:
- Severity enum definition
- Risk score to severity mapping
- Configurable thresholds
- Boundary conditions
- Utility functions
- API endpoint
"""

import pytest

from backend.core.config import get_settings

# Import directly from the module to avoid __init__.py import chain issues
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


@pytest.fixture(autouse=True)
def reset_service_cache():
    """Reset the severity service cache before and after each test."""
    reset_severity_service()
    get_settings.cache_clear()
    yield
    reset_severity_service()
    get_settings.cache_clear()


class TestSeverityEnum:
    """Test the Severity enum definition."""

    def test_severity_values(self):
        """Test that all expected severity values exist."""
        assert Severity.LOW.value == "low"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.HIGH.value == "high"
        assert Severity.CRITICAL.value == "critical"

    def test_severity_str_conversion(self):
        """Test that severity converts to string properly."""
        assert str(Severity.LOW) == "low"
        assert str(Severity.MEDIUM) == "medium"
        assert str(Severity.HIGH) == "high"
        assert str(Severity.CRITICAL) == "critical"

    def test_severity_is_string_enum(self):
        """Test that Severity is a string enum."""
        assert isinstance(Severity.LOW, str)
        assert isinstance(Severity.MEDIUM, str)

    def test_severity_count(self):
        """Test that there are exactly 4 severity levels."""
        assert len(Severity) == 4


class TestSeverityServiceDefaults:
    """Test SeverityService with default thresholds."""

    def test_default_thresholds(self):
        """Test that service uses default thresholds from settings."""
        service = SeverityService()
        assert service.low_max == 29
        assert service.medium_max == 59
        assert service.high_max == 84

    def test_low_severity_scores(self):
        """Test that scores 0-29 map to LOW severity."""
        service = SeverityService()
        assert service.risk_score_to_severity(0) == Severity.LOW
        assert service.risk_score_to_severity(15) == Severity.LOW
        assert service.risk_score_to_severity(29) == Severity.LOW

    def test_medium_severity_scores(self):
        """Test that scores 30-59 map to MEDIUM severity."""
        service = SeverityService()
        assert service.risk_score_to_severity(30) == Severity.MEDIUM
        assert service.risk_score_to_severity(45) == Severity.MEDIUM
        assert service.risk_score_to_severity(59) == Severity.MEDIUM

    def test_high_severity_scores(self):
        """Test that scores 60-84 map to HIGH severity."""
        service = SeverityService()
        assert service.risk_score_to_severity(60) == Severity.HIGH
        assert service.risk_score_to_severity(70) == Severity.HIGH
        assert service.risk_score_to_severity(84) == Severity.HIGH

    def test_critical_severity_scores(self):
        """Test that scores 85-100 map to CRITICAL severity."""
        service = SeverityService()
        assert service.risk_score_to_severity(85) == Severity.CRITICAL
        assert service.risk_score_to_severity(90) == Severity.CRITICAL
        assert service.risk_score_to_severity(100) == Severity.CRITICAL


class TestSeverityServiceBoundaries:
    """Test boundary conditions for severity mapping."""

    def test_boundary_low_medium(self):
        """Test boundary between LOW and MEDIUM (29-30)."""
        service = SeverityService()
        assert service.risk_score_to_severity(29) == Severity.LOW
        assert service.risk_score_to_severity(30) == Severity.MEDIUM

    def test_boundary_medium_high(self):
        """Test boundary between MEDIUM and HIGH (59-60)."""
        service = SeverityService()
        assert service.risk_score_to_severity(59) == Severity.MEDIUM
        assert service.risk_score_to_severity(60) == Severity.HIGH

    def test_boundary_high_critical(self):
        """Test boundary between HIGH and CRITICAL (84-85)."""
        service = SeverityService()
        assert service.risk_score_to_severity(84) == Severity.HIGH
        assert service.risk_score_to_severity(85) == Severity.CRITICAL

    def test_extreme_values(self):
        """Test extreme values 0 and 100."""
        service = SeverityService()
        assert service.risk_score_to_severity(0) == Severity.LOW
        assert service.risk_score_to_severity(100) == Severity.CRITICAL


class TestSeverityServiceValidation:
    """Test validation in SeverityService."""

    def test_score_below_zero_raises_error(self):
        """Test that score below 0 raises ValueError."""
        service = SeverityService()
        with pytest.raises(ValueError, match="between 0 and 100"):
            service.risk_score_to_severity(-1)

    def test_score_above_100_raises_error(self):
        """Test that score above 100 raises ValueError."""
        service = SeverityService()
        with pytest.raises(ValueError, match="between 0 and 100"):
            service.risk_score_to_severity(101)

    def test_invalid_threshold_ordering_raises_error(self):
        """Test that invalid threshold ordering raises ValueError."""
        # Case 1: low_max >= medium_max - should fail
        with pytest.raises(ValueError, match="Invalid severity thresholds"):
            SeverityService(low_max=60, medium_max=59, high_max=84)

        # Case 2: medium_max >= high_max - should fail
        with pytest.raises(ValueError, match="Invalid severity thresholds"):
            SeverityService(low_max=29, medium_max=85, high_max=84)

        # Case 3: low_max < 0 - should fail
        with pytest.raises(ValueError, match="Invalid severity thresholds"):
            SeverityService(low_max=-1, medium_max=59, high_max=84)

        # Case 4: high_max > 100 - should fail
        with pytest.raises(ValueError, match="Invalid severity thresholds"):
            SeverityService(low_max=29, medium_max=59, high_max=101)


class TestSeverityServiceCustomThresholds:
    """Test SeverityService with custom thresholds."""

    def test_custom_thresholds(self):
        """Test service with custom thresholds."""
        service = SeverityService(low_max=20, medium_max=50, high_max=80)

        assert service.risk_score_to_severity(20) == Severity.LOW
        assert service.risk_score_to_severity(21) == Severity.MEDIUM
        assert service.risk_score_to_severity(50) == Severity.MEDIUM
        assert service.risk_score_to_severity(51) == Severity.HIGH
        assert service.risk_score_to_severity(80) == Severity.HIGH
        assert service.risk_score_to_severity(81) == Severity.CRITICAL

    def test_tight_thresholds(self):
        """Test service with tight thresholds."""
        service = SeverityService(low_max=10, medium_max=20, high_max=30)

        assert service.risk_score_to_severity(10) == Severity.LOW
        assert service.risk_score_to_severity(11) == Severity.MEDIUM
        assert service.risk_score_to_severity(20) == Severity.MEDIUM
        assert service.risk_score_to_severity(21) == Severity.HIGH
        assert service.risk_score_to_severity(30) == Severity.HIGH
        assert service.risk_score_to_severity(31) == Severity.CRITICAL


class TestSeverityDefinitions:
    """Test severity definitions retrieval."""

    def test_get_definitions_returns_all_severities(self):
        """Test that get_severity_definitions returns all 4 levels."""
        service = SeverityService()
        definitions = service.get_severity_definitions()

        assert len(definitions) == 4

        severity_values = [d.severity for d in definitions]
        assert Severity.LOW in severity_values
        assert Severity.MEDIUM in severity_values
        assert Severity.HIGH in severity_values
        assert Severity.CRITICAL in severity_values

    def test_definitions_have_correct_score_ranges(self):
        """Test that definitions have correct score ranges."""
        service = SeverityService()
        definitions = service.get_severity_definitions()

        # Find each definition
        low_def = next(d for d in definitions if d.severity == Severity.LOW)
        medium_def = next(d for d in definitions if d.severity == Severity.MEDIUM)
        high_def = next(d for d in definitions if d.severity == Severity.HIGH)
        critical_def = next(d for d in definitions if d.severity == Severity.CRITICAL)

        # Check ranges
        assert low_def.min_score == 0
        assert low_def.max_score == 29

        assert medium_def.min_score == 30
        assert medium_def.max_score == 59

        assert high_def.min_score == 60
        assert high_def.max_score == 84

        assert critical_def.min_score == 85
        assert critical_def.max_score == 100

    def test_definitions_have_colors(self):
        """Test that all definitions have color codes."""
        service = SeverityService()
        definitions = service.get_severity_definitions()

        for defn in definitions:
            assert defn.color is not None
            assert defn.color.startswith("#")
            assert len(defn.color) == 7  # #RRGGBB format

    def test_definitions_to_dict(self):
        """Test that definitions can be serialized to dict."""
        service = SeverityService()
        definitions = service.get_severity_definitions()

        for defn in definitions:
            d = defn.to_dict()
            assert "severity" in d
            assert "label" in d
            assert "description" in d
            assert "color" in d
            assert "priority" in d
            assert "min_score" in d
            assert "max_score" in d


class TestSeverityThresholds:
    """Test threshold retrieval."""

    def test_get_thresholds(self):
        """Test that get_thresholds returns correct values."""
        service = SeverityService()
        thresholds = service.get_thresholds()

        assert thresholds["low_max"] == 29
        assert thresholds["medium_max"] == 59
        assert thresholds["high_max"] == 84

    def test_get_thresholds_custom(self):
        """Test get_thresholds with custom values."""
        service = SeverityService(low_max=20, medium_max=50, high_max=80)
        thresholds = service.get_thresholds()

        assert thresholds["low_max"] == 20
        assert thresholds["medium_max"] == 50
        assert thresholds["high_max"] == 80


class TestSeverityColors:
    """Test severity color utilities."""

    def test_severity_colors_dict(self):
        """Test that SEVERITY_COLORS contains all severities."""
        assert Severity.LOW in SEVERITY_COLORS
        assert Severity.MEDIUM in SEVERITY_COLORS
        assert Severity.HIGH in SEVERITY_COLORS
        assert Severity.CRITICAL in SEVERITY_COLORS

    def test_expected_colors(self):
        """Test that colors match expected values."""
        assert SEVERITY_COLORS[Severity.LOW] == "#22c55e"  # green
        assert SEVERITY_COLORS[Severity.MEDIUM] == "#eab308"  # yellow
        assert SEVERITY_COLORS[Severity.HIGH] == "#f97316"  # orange
        assert SEVERITY_COLORS[Severity.CRITICAL] == "#ef4444"  # red

    def test_get_severity_color(self):
        """Test get_severity_color utility function."""
        assert get_severity_color(Severity.LOW) == "#22c55e"
        assert get_severity_color(Severity.MEDIUM) == "#eab308"
        assert get_severity_color(Severity.HIGH) == "#f97316"
        assert get_severity_color(Severity.CRITICAL) == "#ef4444"


class TestSeverityPriority:
    """Test severity priority utilities."""

    def test_severity_priority_dict(self):
        """Test that SEVERITY_PRIORITY contains all severities."""
        assert Severity.LOW in SEVERITY_PRIORITY
        assert Severity.MEDIUM in SEVERITY_PRIORITY
        assert Severity.HIGH in SEVERITY_PRIORITY
        assert Severity.CRITICAL in SEVERITY_PRIORITY

    def test_priority_ordering(self):
        """Test that priorities are ordered correctly (critical = 0, low = 3)."""
        assert SEVERITY_PRIORITY[Severity.CRITICAL] == 0
        assert SEVERITY_PRIORITY[Severity.HIGH] == 1
        assert SEVERITY_PRIORITY[Severity.MEDIUM] == 2
        assert SEVERITY_PRIORITY[Severity.LOW] == 3

    def test_get_severity_priority(self):
        """Test get_severity_priority utility function."""
        assert get_severity_priority(Severity.CRITICAL) == 0
        assert get_severity_priority(Severity.HIGH) == 1
        assert get_severity_priority(Severity.MEDIUM) == 2
        assert get_severity_priority(Severity.LOW) == 3


class TestSeverityComparisons:
    """Test severity comparison utilities."""

    def test_severity_gte(self):
        """Test severity_gte (greater than or equal)."""
        # Same severity
        assert severity_gte(Severity.LOW, Severity.LOW)
        assert severity_gte(Severity.CRITICAL, Severity.CRITICAL)

        # Greater severity
        assert severity_gte(Severity.CRITICAL, Severity.LOW)
        assert severity_gte(Severity.HIGH, Severity.MEDIUM)
        assert severity_gte(Severity.MEDIUM, Severity.LOW)

        # Lesser severity
        assert not severity_gte(Severity.LOW, Severity.CRITICAL)
        assert not severity_gte(Severity.MEDIUM, Severity.HIGH)

    def test_severity_gt(self):
        """Test severity_gt (strictly greater than)."""
        # Same severity - should be False
        assert not severity_gt(Severity.LOW, Severity.LOW)
        assert not severity_gt(Severity.CRITICAL, Severity.CRITICAL)

        # Greater severity
        assert severity_gt(Severity.CRITICAL, Severity.LOW)
        assert severity_gt(Severity.HIGH, Severity.MEDIUM)
        assert severity_gt(Severity.MEDIUM, Severity.LOW)

        # Lesser severity
        assert not severity_gt(Severity.LOW, Severity.CRITICAL)
        assert not severity_gt(Severity.MEDIUM, Severity.HIGH)

    def test_severity_lte(self):
        """Test severity_lte (less than or equal)."""
        # Same severity
        assert severity_lte(Severity.LOW, Severity.LOW)
        assert severity_lte(Severity.CRITICAL, Severity.CRITICAL)

        # Lesser severity
        assert severity_lte(Severity.LOW, Severity.CRITICAL)
        assert severity_lte(Severity.MEDIUM, Severity.HIGH)
        assert severity_lte(Severity.LOW, Severity.MEDIUM)

        # Greater severity
        assert not severity_lte(Severity.CRITICAL, Severity.LOW)
        assert not severity_lte(Severity.HIGH, Severity.MEDIUM)

    def test_severity_lt(self):
        """Test severity_lt (strictly less than)."""
        # Same severity - should be False
        assert not severity_lt(Severity.LOW, Severity.LOW)
        assert not severity_lt(Severity.CRITICAL, Severity.CRITICAL)

        # Lesser severity
        assert severity_lt(Severity.LOW, Severity.CRITICAL)
        assert severity_lt(Severity.MEDIUM, Severity.HIGH)
        assert severity_lt(Severity.LOW, Severity.MEDIUM)

        # Greater severity
        assert not severity_lt(Severity.CRITICAL, Severity.LOW)
        assert not severity_lt(Severity.HIGH, Severity.MEDIUM)


class TestSeverityFromString:
    """Test severity_from_string utility."""

    def test_valid_lowercase(self):
        """Test conversion of lowercase strings."""
        assert severity_from_string("low") == Severity.LOW
        assert severity_from_string("medium") == Severity.MEDIUM
        assert severity_from_string("high") == Severity.HIGH
        assert severity_from_string("critical") == Severity.CRITICAL

    def test_valid_uppercase(self):
        """Test conversion of uppercase strings."""
        assert severity_from_string("LOW") == Severity.LOW
        assert severity_from_string("MEDIUM") == Severity.MEDIUM
        assert severity_from_string("HIGH") == Severity.HIGH
        assert severity_from_string("CRITICAL") == Severity.CRITICAL

    def test_valid_mixed_case(self):
        """Test conversion of mixed case strings."""
        assert severity_from_string("Low") == Severity.LOW
        assert severity_from_string("Medium") == Severity.MEDIUM
        assert severity_from_string("High") == Severity.HIGH
        assert severity_from_string("Critical") == Severity.CRITICAL

    def test_invalid_string_raises_error(self):
        """Test that invalid strings raise ValueError."""
        with pytest.raises(ValueError, match="Invalid severity value"):
            severity_from_string("invalid")

        with pytest.raises(ValueError, match="Invalid severity value"):
            severity_from_string("")

        with pytest.raises(ValueError, match="Invalid severity value"):
            severity_from_string("warning")


class TestSeverityServiceCaching:
    """Test severity service caching."""

    def test_get_severity_service_returns_same_instance(self):
        """Test that get_severity_service returns cached instance."""
        service1 = get_severity_service()
        service2 = get_severity_service()
        assert service1 is service2

    def test_reset_severity_service_clears_cache(self):
        """Test that reset_severity_service creates new instance."""
        service1 = get_severity_service()
        reset_severity_service()
        service2 = get_severity_service()
        assert service1 is not service2


class TestSeverityServiceWithEnvironment:
    """Test severity service with environment configuration."""

    def test_service_reads_from_settings(self, monkeypatch):
        """Test that service reads thresholds from settings."""
        # Clear caches first
        reset_severity_service()
        get_settings.cache_clear()

        # Set custom environment variables
        monkeypatch.setenv("SEVERITY_LOW_MAX", "25")
        monkeypatch.setenv("SEVERITY_MEDIUM_MAX", "55")
        monkeypatch.setenv("SEVERITY_HIGH_MAX", "80")

        # Clear cache again to pick up new env vars
        get_settings.cache_clear()

        # Create service (will read from settings)
        service = SeverityService()

        assert service.low_max == 25
        assert service.medium_max == 55
        assert service.high_max == 80

        # Verify mapping uses new thresholds
        assert service.risk_score_to_severity(25) == Severity.LOW
        assert service.risk_score_to_severity(26) == Severity.MEDIUM
        assert service.risk_score_to_severity(55) == Severity.MEDIUM
        assert service.risk_score_to_severity(56) == Severity.HIGH
        assert service.risk_score_to_severity(80) == Severity.HIGH
        assert service.risk_score_to_severity(81) == Severity.CRITICAL


class TestSeverityDefinitionDataclass:
    """Test SeverityDefinition dataclass."""

    def test_severity_definition_frozen(self):
        """Test that SeverityDefinition is immutable."""
        from dataclasses import FrozenInstanceError

        defn = SeverityDefinition(
            severity=Severity.LOW,
            label="Low",
            description="Test",
            color="#22c55e",
            priority=3,
            min_score=0,
            max_score=29,
        )

        with pytest.raises(FrozenInstanceError):
            defn.label = "Changed"

    def test_severity_definition_equality(self):
        """Test that SeverityDefinition supports equality."""
        defn1 = SeverityDefinition(
            severity=Severity.LOW,
            label="Low",
            description="Test",
            color="#22c55e",
            priority=3,
            min_score=0,
            max_score=29,
        )
        defn2 = SeverityDefinition(
            severity=Severity.LOW,
            label="Low",
            description="Test",
            color="#22c55e",
            priority=3,
            min_score=0,
            max_score=29,
        )

        assert defn1 == defn2

    def test_to_dict_serialization(self):
        """Test to_dict produces correct structure."""
        defn = SeverityDefinition(
            severity=Severity.HIGH,
            label="High",
            description="Concerning activity",
            color="#f97316",
            priority=1,
            min_score=60,
            max_score=84,
        )

        d = defn.to_dict()

        assert d["severity"] == "high"
        assert d["label"] == "High"
        assert d["description"] == "Concerning activity"
        assert d["color"] == "#f97316"
        assert d["priority"] == 1
        assert d["min_score"] == 60
        assert d["max_score"] == 84


class TestAllScoreMappings:
    """Test all score values map correctly."""

    def test_all_scores_0_to_100(self):
        """Test that every score from 0-100 maps to a valid severity."""
        service = SeverityService()

        for score in range(101):
            severity = service.risk_score_to_severity(score)
            assert severity in Severity
            assert isinstance(severity, Severity)

    def test_score_ranges_complete(self):
        """Test that score ranges cover 0-100 completely."""
        service = SeverityService()
        definitions = service.get_severity_definitions()

        # Sort by min_score
        sorted_defs = sorted(definitions, key=lambda d: d.min_score)

        # Check no gaps
        assert sorted_defs[0].min_score == 0
        assert sorted_defs[-1].max_score == 100

        for i in range(len(sorted_defs) - 1):
            assert sorted_defs[i].max_score + 1 == sorted_defs[i + 1].min_score
