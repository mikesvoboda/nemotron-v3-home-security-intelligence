"""Example property-based tests using Hypothesis.

This module demonstrates property-based testing with Hypothesis for the
SeverityService. Property-based testing generates many random inputs to
verify that certain properties always hold, rather than testing specific
hand-picked examples.

Key properties tested:
1. Score mapping is total: Every valid score (0-100) maps to exactly one severity
2. Score mapping is monotonic: Higher scores never produce lower severities
3. Severity comparisons form a total ordering
4. Severity definitions cover the entire 0-100 range without gaps or overlaps
"""

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from backend.models.enums import Severity
from backend.services.severity import (
    SeverityService,
    get_severity_priority,
    severity_gt,
    severity_gte,
    severity_lt,
    severity_lte,
)

# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid risk scores (0-100 inclusive)
valid_risk_scores = st.integers(min_value=0, max_value=100)

# Strategy for invalid risk scores (outside 0-100)
invalid_risk_scores = st.one_of(
    st.integers(max_value=-1),
    st.integers(min_value=101),
)

# Strategy for Severity enum values
severities = st.sampled_from(list(Severity))


# Strategy for valid threshold configurations
# Must satisfy: 0 <= low_max < medium_max < high_max <= 100
@st.composite
def valid_thresholds(draw: st.DrawFn) -> tuple[int, int, int]:
    """Generate valid (low_max, medium_max, high_max) thresholds.

    Constraints:
    - 0 <= low_max < medium_max < high_max <= 100
    - At least 4 distinct values to cover all severity levels
    """
    # Pick 3 strictly increasing values in [0, 100]
    low_max = draw(st.integers(min_value=0, max_value=97))
    medium_max = draw(st.integers(min_value=low_max + 1, max_value=98))
    high_max = draw(st.integers(min_value=medium_max + 1, max_value=99))
    return (low_max, medium_max, high_max)


# =============================================================================
# Property Tests: Score to Severity Mapping
# =============================================================================


class TestRiskScoreToSeverityProperties:
    """Property-based tests for risk_score_to_severity."""

    @given(score=valid_risk_scores)
    @settings(max_examples=200)
    def test_all_valid_scores_map_to_severity(self, score: int) -> None:
        """Property: Every valid score (0-100) maps to exactly one severity.

        This is a totality property - the function is defined for all valid inputs.
        """
        service = SeverityService(low_max=29, medium_max=59, high_max=84)
        result = service.risk_score_to_severity(score)

        # Result must be one of the valid Severity values
        assert result in Severity
        assert isinstance(result, Severity)

    @given(score=invalid_risk_scores)
    @settings(max_examples=100)
    def test_invalid_scores_raise_value_error(self, score: int) -> None:
        """Property: Scores outside 0-100 always raise ValueError.

        This is a safety property - invalid inputs are rejected.
        """
        service = SeverityService(low_max=29, medium_max=59, high_max=84)

        with pytest.raises(ValueError, match="must be between 0 and 100"):
            service.risk_score_to_severity(score)

    @given(score_low=valid_risk_scores, score_high=valid_risk_scores)
    @settings(max_examples=200)
    def test_monotonicity(self, score_low: int, score_high: int) -> None:
        """Property: Higher scores never produce lower severities.

        If score_high >= score_low, then severity(score_high) >= severity(score_low).
        This is a monotonicity property.
        """
        assume(score_high >= score_low)

        service = SeverityService(low_max=29, medium_max=59, high_max=84)
        severity_low = service.risk_score_to_severity(score_low)
        severity_high = service.risk_score_to_severity(score_high)

        # Higher or equal score should produce higher or equal severity
        assert severity_gte(severity_high, severity_low), (
            f"Monotonicity violated: score {score_high} -> {severity_high}, "
            f"but score {score_low} -> {severity_low}"
        )

    @given(thresholds=valid_thresholds(), score=valid_risk_scores)
    @settings(max_examples=200)
    def test_configurable_thresholds_maintain_properties(
        self, thresholds: tuple[int, int, int], score: int
    ) -> None:
        """Property: Score mapping works correctly for any valid threshold config.

        Regardless of threshold configuration, the mapping should still be total
        and produce valid Severity values.
        """
        low_max, medium_max, high_max = thresholds
        service = SeverityService(low_max=low_max, medium_max=medium_max, high_max=high_max)

        result = service.risk_score_to_severity(score)
        assert result in Severity


# =============================================================================
# Property Tests: Severity Comparisons
# =============================================================================


class TestSeverityComparisonProperties:
    """Property-based tests for severity comparison functions."""

    @given(a=severities)
    @settings(max_examples=50)
    def test_reflexivity_of_gte(self, a: Severity) -> None:
        """Property: severity_gte(a, a) is always True (reflexive).

        Every severity is at least as severe as itself.
        """
        assert severity_gte(a, a)

    @given(a=severities)
    @settings(max_examples=50)
    def test_reflexivity_of_lte(self, a: Severity) -> None:
        """Property: severity_lte(a, a) is always True (reflexive).

        Every severity is at most as severe as itself.
        """
        assert severity_lte(a, a)

    @given(a=severities)
    @settings(max_examples=50)
    def test_irreflexivity_of_strict_comparisons(self, a: Severity) -> None:
        """Property: severity_gt(a, a) and severity_lt(a, a) are always False.

        No severity is strictly greater/less than itself (irreflexive).
        """
        assert not severity_gt(a, a)
        assert not severity_lt(a, a)

    @given(a=severities, b=severities)
    @settings(max_examples=100)
    def test_trichotomy(self, a: Severity, b: Severity) -> None:
        """Property: Exactly one of (a < b), (a == b), (a > b) holds.

        This is the trichotomy property of total ordering.
        """
        lt = severity_lt(a, b)
        eq = get_severity_priority(a) == get_severity_priority(b)
        gt = severity_gt(a, b)

        # Exactly one must be True
        assert sum([lt, eq, gt]) == 1, (
            f"Trichotomy violated for {a}, {b}: lt={lt}, eq={eq}, gt={gt}"
        )

    @given(a=severities, b=severities, c=severities)
    @settings(max_examples=100)
    def test_transitivity_of_gte(self, a: Severity, b: Severity, c: Severity) -> None:
        """Property: If a >= b and b >= c, then a >= c (transitive).

        This is the transitivity property for ordering.
        """
        if severity_gte(a, b) and severity_gte(b, c):
            assert severity_gte(a, c), (
                f"Transitivity violated: {a} >= {b} and {b} >= {c} but not {a} >= {c}"
            )

    @given(a=severities, b=severities)
    @settings(max_examples=100)
    def test_gt_iff_gte_and_not_equal(self, a: Severity, b: Severity) -> None:
        """Property: severity_gt(a, b) iff severity_gte(a, b) and a != b.

        Strict greater-than is equivalent to gte-and-not-equal.
        """
        same_priority = get_severity_priority(a) == get_severity_priority(b)

        if severity_gt(a, b):
            assert severity_gte(a, b) and not same_priority
        else:
            # Not gt means either not gte, or same priority
            assert not severity_gte(a, b) or same_priority

    @given(a=severities, b=severities)
    @settings(max_examples=100)
    def test_gte_and_lte_symmetry(self, a: Severity, b: Severity) -> None:
        """Property: severity_gte(a, b) iff severity_lte(b, a).

        Greater-than-or-equal in one direction equals less-than-or-equal reversed.
        """
        assert severity_gte(a, b) == severity_lte(b, a)


# =============================================================================
# Property Tests: Severity Definitions
# =============================================================================


class TestSeverityDefinitionsProperties:
    """Property-based tests for severity definitions."""

    @given(thresholds=valid_thresholds())
    @settings(max_examples=100)
    def test_definitions_cover_entire_range(self, thresholds: tuple[int, int, int]) -> None:
        """Property: Severity definitions cover 0-100 with no gaps.

        For any valid threshold config, the severity definitions should partition
        the score space [0, 100] into non-overlapping, adjacent ranges.
        """
        low_max, medium_max, high_max = thresholds
        service = SeverityService(low_max=low_max, medium_max=medium_max, high_max=high_max)
        definitions = service.get_severity_definitions()

        # Should have exactly 4 severity levels
        assert len(definitions) == 4

        # First definition should start at 0
        assert definitions[0].min_score == 0

        # Last definition should end at 100
        assert definitions[-1].max_score == 100

        # Each definition should be adjacent to the next (no gaps)
        for i in range(len(definitions) - 1):
            current_max = definitions[i].max_score
            next_min = definitions[i + 1].min_score
            assert next_min == current_max + 1, (
                f"Gap between {definitions[i].severity} and {definitions[i + 1].severity}: "
                f"{current_max} to {next_min}"
            )

    @given(thresholds=valid_thresholds(), score=valid_risk_scores)
    @settings(max_examples=200)
    def test_score_maps_to_containing_definition(
        self, thresholds: tuple[int, int, int], score: int
    ) -> None:
        """Property: Every score falls within exactly one definition's range.

        The severity returned by risk_score_to_severity should match the severity
        of the definition whose range contains the score.
        """
        low_max, medium_max, high_max = thresholds
        service = SeverityService(low_max=low_max, medium_max=medium_max, high_max=high_max)

        severity = service.risk_score_to_severity(score)
        definitions = service.get_severity_definitions()

        # Find the definition that contains this score
        matching_definitions = [d for d in definitions if d.min_score <= score <= d.max_score]

        # Exactly one definition should match
        assert len(matching_definitions) == 1, (
            f"Score {score} matched {len(matching_definitions)} definitions"
        )

        # The matched definition's severity should equal the computed severity
        assert matching_definitions[0].severity == severity
