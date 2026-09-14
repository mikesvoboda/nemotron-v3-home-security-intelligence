"""Unit tests for enums module (Severity enum).

Tests cover:
- Enum values and ordering
- String representation
- Enum membership
- Comparison with strings
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.enums import Severity

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Severity Enum Value Tests
# =============================================================================


class TestSeverityEnumValues:
    """Tests for Severity enum values."""

    def test_severity_low_value(self):
        """Test LOW severity value."""
        assert Severity.LOW.value == "low"

    def test_severity_medium_value(self):
        """Test MEDIUM severity value."""
        assert Severity.MEDIUM.value == "medium"

    def test_severity_high_value(self):
        """Test HIGH severity value."""
        assert Severity.HIGH.value == "high"

    def test_severity_critical_value(self):
        """Test CRITICAL severity value."""
        assert Severity.CRITICAL.value == "critical"


class TestSeverityEnumCount:
    """Tests for Severity enum member count."""

    def test_severity_has_four_members(self):
        """Test Severity has exactly 4 members."""
        assert len(Severity) == 4

    def test_severity_members_list(self):
        """Test all Severity members are present."""
        members = list(Severity)
        assert Severity.LOW in members
        assert Severity.MEDIUM in members
        assert Severity.HIGH in members
        assert Severity.CRITICAL in members


# =============================================================================
# Severity Enum Type Tests
# =============================================================================


class TestSeverityEnumType:
    """Tests for Severity enum type properties."""

    def test_severity_is_string_enum(self):
        """Test Severity is a string enum (inherits from str)."""
        for severity in Severity:
            assert isinstance(severity, str)

    def test_severity_value_is_string(self):
        """Test Severity values are strings."""
        for severity in Severity:
            assert isinstance(severity.value, str)

    def test_severity_can_compare_to_string(self):
        """Test Severity can be compared to string."""
        assert Severity.LOW == "low"
        assert Severity.MEDIUM == "medium"
        assert Severity.HIGH == "high"
        assert Severity.CRITICAL == "critical"

    def test_severity_name_matches_uppercase_value(self):
        """Test Severity name matches uppercase of value."""
        for severity in Severity:
            assert severity.name == severity.value.upper()


# =============================================================================
# Severity Enum String Representation Tests
# =============================================================================


class TestSeverityStr:
    """Tests for Severity __str__ method."""

    def test_severity_str_low(self):
        """Test str(Severity.LOW)."""
        assert str(Severity.LOW) == "low"

    def test_severity_str_medium(self):
        """Test str(Severity.MEDIUM)."""
        assert str(Severity.MEDIUM) == "medium"

    def test_severity_str_high(self):
        """Test str(Severity.HIGH)."""
        assert str(Severity.HIGH) == "high"

    def test_severity_str_critical(self):
        """Test str(Severity.CRITICAL)."""
        assert str(Severity.CRITICAL) == "critical"

    def test_severity_str_equals_value(self):
        """Test str() equals .value for all severities."""
        for severity in Severity:
            assert str(severity) == severity.value


# =============================================================================
# Severity Enum Lookup Tests
# =============================================================================


class TestSeverityLookup:
    """Tests for looking up Severity enum members."""

    def test_lookup_by_value_low(self):
        """Test looking up LOW by value."""
        assert Severity("low") == Severity.LOW

    def test_lookup_by_value_medium(self):
        """Test looking up MEDIUM by value."""
        assert Severity("medium") == Severity.MEDIUM

    def test_lookup_by_value_high(self):
        """Test looking up HIGH by value."""
        assert Severity("high") == Severity.HIGH

    def test_lookup_by_value_critical(self):
        """Test looking up CRITICAL by value."""
        assert Severity("critical") == Severity.CRITICAL

    def test_lookup_by_name_low(self):
        """Test looking up LOW by name."""
        assert Severity["LOW"] == Severity.LOW

    def test_lookup_by_name_medium(self):
        """Test looking up MEDIUM by name."""
        assert Severity["MEDIUM"] == Severity.MEDIUM

    def test_lookup_by_name_high(self):
        """Test looking up HIGH by name."""
        assert Severity["HIGH"] == Severity.HIGH

    def test_lookup_by_name_critical(self):
        """Test looking up CRITICAL by name."""
        assert Severity["CRITICAL"] == Severity.CRITICAL

    def test_invalid_value_raises_error(self):
        """Test invalid value raises ValueError."""
        with pytest.raises(ValueError):
            Severity("invalid")

    def test_invalid_name_raises_error(self):
        """Test invalid name raises KeyError."""
        with pytest.raises(KeyError):
            Severity["INVALID"]


# =============================================================================
# Severity Enum Membership Tests
# =============================================================================


class TestSeverityMembership:
    """Tests for Severity enum membership checks."""

    def test_low_in_severity(self):
        """Test LOW is in Severity."""
        assert Severity.LOW in Severity

    def test_medium_in_severity(self):
        """Test MEDIUM is in Severity."""
        assert Severity.MEDIUM in Severity

    def test_high_in_severity(self):
        """Test HIGH is in Severity."""
        assert Severity.HIGH in Severity

    def test_critical_in_severity(self):
        """Test CRITICAL is in Severity."""
        assert Severity.CRITICAL in Severity

    def test_string_equals_but_not_identical_to_severity(self):
        """Test plain string equals but is not identical to Severity member."""
        # Note: "low" == Severity.LOW due to str inheritance
        # But "low" is Severity.LOW returns False (different objects)
        assert Severity.LOW == "low"  # Equal due to StrEnum
        assert Severity.LOW is not "low"  # But not identical objects  # noqa: F632


# =============================================================================
# Severity Enum Ordering Tests
# =============================================================================


class TestSeverityOrdering:
    """Tests for Severity ordering semantics."""

    def test_severity_values_are_lowercase(self):
        """Test all severity values are lowercase."""
        for severity in Severity:
            assert severity.value == severity.value.lower()

    def test_severity_iteration_order(self):
        """Test severity iteration follows definition order."""
        severities = list(Severity)
        # Definition order in the enum
        expected = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
        assert severities == expected


# =============================================================================
# Severity Enum Identity Tests
# =============================================================================


class TestSeverityIdentity:
    """Tests for Severity enum identity."""

    def test_same_severity_is_identical(self):
        """Test same severity is identical (is)."""
        assert Severity.LOW is Severity.LOW
        assert Severity.MEDIUM is Severity.MEDIUM
        assert Severity.HIGH is Severity.HIGH
        assert Severity.CRITICAL is Severity.CRITICAL

    def test_different_severities_not_identical(self):
        """Test different severities are not identical."""
        assert Severity.LOW is not Severity.MEDIUM
        assert Severity.MEDIUM is not Severity.HIGH
        assert Severity.HIGH is not Severity.CRITICAL

    def test_lookup_returns_same_object(self):
        """Test lookup returns same enum object."""
        assert Severity("low") is Severity.LOW
        assert Severity["HIGH"] is Severity.HIGH


# =============================================================================
# Severity Use Cases Tests
# =============================================================================


class TestSeverityUseCases:
    """Tests for real-world Severity use cases."""

    def test_severity_in_dict_key(self):
        """Test Severity can be used as dict key."""
        scores = {
            Severity.LOW: 0,
            Severity.MEDIUM: 30,
            Severity.HIGH: 60,
            Severity.CRITICAL: 85,
        }
        assert scores[Severity.LOW] == 0
        assert scores[Severity.CRITICAL] == 85

    def test_severity_in_set(self):
        """Test Severity can be used in sets."""
        high_severity = {Severity.HIGH, Severity.CRITICAL}
        assert Severity.HIGH in high_severity
        assert Severity.LOW not in high_severity

    def test_severity_serialization(self):
        """Test Severity serializes to string."""
        # Common pattern for JSON serialization
        assert Severity.HIGH.value == "high"
        assert str(Severity.HIGH) == "high"

    def test_severity_from_api_response(self):
        """Test creating Severity from API response string."""
        api_value = "medium"
        severity = Severity(api_value)
        assert severity == Severity.MEDIUM

    def test_severity_for_display(self):
        """Test Severity can be used for display."""
        severity = Severity.CRITICAL
        # Can use .value or str() for display
        assert f"Alert: {severity.value}" == "Alert: critical"
        assert f"Alert: {severity}" == "Alert: critical"


# =============================================================================
# Property-based Tests
# =============================================================================


class TestSeverityProperties:
    """Property-based tests for Severity enum."""

    @given(severity=st.sampled_from(list(Severity)))
    @settings(max_examples=20)
    def test_severity_str_equals_value(self, severity: Severity):
        """Property: str(severity) equals severity.value."""
        assert str(severity) == severity.value

    @given(severity=st.sampled_from(list(Severity)))
    @settings(max_examples=20)
    def test_severity_lookup_roundtrip(self, severity: Severity):
        """Property: Looking up by value returns same member."""
        looked_up = Severity(severity.value)
        assert looked_up is severity

    @given(severity=st.sampled_from(list(Severity)))
    @settings(max_examples=20)
    def test_severity_name_lookup_roundtrip(self, severity: Severity):
        """Property: Looking up by name returns same member."""
        looked_up = Severity[severity.name]
        assert looked_up is severity

    @given(severity=st.sampled_from(list(Severity)))
    @settings(max_examples=20)
    def test_severity_value_is_lowercase(self, severity: Severity):
        """Property: All severity values are lowercase."""
        assert severity.value == severity.value.lower()

    @given(severity=st.sampled_from(list(Severity)))
    @settings(max_examples=20)
    def test_severity_name_is_uppercase(self, severity: Severity):
        """Property: All severity names are uppercase."""
        assert severity.name == severity.name.upper()

    @given(severity=st.sampled_from(list(Severity)))
    @settings(max_examples=20)
    def test_severity_is_string_instance(self, severity: Severity):
        """Property: All severities are string instances."""
        assert isinstance(severity, str)

    @given(sev1=st.sampled_from(list(Severity)), sev2=st.sampled_from(list(Severity)))
    @settings(max_examples=50)
    def test_severity_equality_reflexive(self, sev1: Severity, sev2: Severity):
        """Property: Equality is reflexive (a == a)."""
        assert sev1 == sev1  # noqa: PLR0124 - intentional reflexive equality test
        assert sev2 == sev2  # noqa: PLR0124 - intentional reflexive equality test
        # And symmetric: if a == b then b == a
        if sev1 == sev2:
            assert sev2 == sev1
