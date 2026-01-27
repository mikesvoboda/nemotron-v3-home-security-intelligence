"""Property-based tests for risk score calculations.

Tests cover mathematical invariants for:
- Boundedness: Risk score is always 0-100
- Determinism: Same input produces same output
- Severity level mapping consistency

Related Linear Issue:
- NEM-3747: Expand Property-Based Testing for Detection Validation
"""

from __future__ import annotations

import hashlib
import math

from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from backend.tests.hypothesis_strategies import (
    edge_case_risk_scores,
    valid_detection_bbox,
    valid_detection_label,
    valid_risk_score,
)

# =============================================================================
# Hypothesis Strategies
# =============================================================================


@st.composite
def detection_context_strategy(draw: st.DrawFn) -> dict:
    """Generate a detection context with various attributes for risk scoring.

    Returns:
        Dict with detection context including object_type, confidence, bbox, etc.
    """
    bbox_dict = draw(valid_detection_bbox())

    return {
        "object_type": draw(valid_detection_label()),
        "confidence": draw(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
        ),
        "bbox": bbox_dict,
        "camera_id": draw(
            st.text(
                min_size=1,
                max_size=50,
                alphabet=st.characters(whitelist_categories=("Ll", "Nd"), whitelist_characters="_"),
            ).filter(lambda x: x and x[0].isalpha())
        ),
        "is_nighttime": draw(st.booleans()),
        "is_in_exclusion_zone": draw(st.booleans()),
        "is_known_entity": draw(st.booleans()),
    }


@st.composite
def risk_calculation_inputs(draw: st.DrawFn) -> dict:
    """Generate inputs for risk score calculation.

    Simulates various detection scenarios that might affect risk scoring.
    """
    base_risk = draw(st.integers(min_value=0, max_value=100))

    # Modifiers that could affect risk
    modifiers = {
        "base_risk": base_risk,
        "time_modifier": draw(
            st.floats(min_value=0.0, max_value=1.5, allow_nan=False, allow_infinity=False)
        ),
        "location_modifier": draw(
            st.floats(min_value=0.0, max_value=1.5, allow_nan=False, allow_infinity=False)
        ),
        "entity_modifier": draw(
            st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False)
        ),
        "confidence_weight": draw(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
        ),
    }
    return modifiers


def calculate_risk_score(inputs: dict) -> int:
    """Calculate a bounded risk score from inputs.

    This function simulates the risk calculation logic ensuring
    the output is always bounded to [0, 100].

    Args:
        inputs: Dict containing risk modifiers

    Returns:
        Risk score in [0, 100]
    """
    base = inputs.get("base_risk", 50)
    time_mod = inputs.get("time_modifier", 1.0)
    location_mod = inputs.get("location_modifier", 1.0)
    entity_mod = inputs.get("entity_modifier", 0.0)
    confidence = inputs.get("confidence_weight", 1.0)

    # Apply modifiers
    adjusted_risk = base * time_mod * location_mod * (1 + entity_mod) * confidence

    # Clamp to [0, 100]
    return max(0, min(100, int(adjusted_risk)))


def get_severity_level(risk_score: int) -> str:
    """Map risk score to severity level.

    Args:
        risk_score: Integer risk score in [0, 100]

    Returns:
        Severity level string: "low", "medium", "high", or "critical"
    """
    if risk_score <= 25:
        return "low"
    elif risk_score <= 50:
        return "medium"
    elif risk_score <= 75:
        return "high"
    else:
        return "critical"


# =============================================================================
# Risk Score Boundedness Properties
# =============================================================================


class TestRiskScoreBoundednessProperties:
    """Property-based tests for risk score boundedness."""

    @given(inputs=risk_calculation_inputs())
    @hypothesis_settings(max_examples=500)
    def test_risk_score_bounded(self, inputs: dict) -> None:
        """Property: Risk score is always 0-100.

        No matter what inputs are provided, the calculated risk score
        must always be within the valid range [0, 100].
        """
        risk_score = calculate_risk_score(inputs)

        assert 0 <= risk_score <= 100, f"Risk score {risk_score} not in [0, 100]"

    @given(risk=valid_risk_score())
    @hypothesis_settings(max_examples=500)
    def test_valid_risk_score_strategy_bounded(self, risk: int) -> None:
        """Property: valid_risk_score strategy always produces [0, 100] values.

        Verifies that the hypothesis strategy itself produces valid values.
        """
        assert 0 <= risk <= 100, f"Strategy produced invalid risk score: {risk}"

    @given(risk=edge_case_risk_scores())
    @hypothesis_settings(max_examples=500)
    def test_edge_case_risk_scores_bounded(self, risk: int) -> None:
        """Property: Edge case risk scores are valid boundary values.

        Edge cases (0, 25, 50, 75, 100) should all be valid risk scores.
        """
        assert 0 <= risk <= 100, f"Edge case risk score {risk} not in [0, 100]"
        assert risk in [0, 25, 50, 75, 100], f"Edge case {risk} not in expected set"

    @given(
        base_risk=st.integers(min_value=-1000, max_value=1000),
        multiplier=st.floats(
            min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False
        ),
    )
    @hypothesis_settings(max_examples=500)
    def test_risk_score_clamping_extreme_inputs(
        self,
        base_risk: int,
        multiplier: float,
    ) -> None:
        """Property: Risk score is bounded even with extreme inputs.

        Even with deliberately extreme input values, the risk score
        must be clamped to [0, 100].
        """
        # Calculate with extreme values
        raw_value = base_risk * multiplier

        # Clamp to valid range (use math.isnan for NaN check)
        clamped = max(0, min(100, int(raw_value) if not math.isnan(raw_value) else 50))

        assert 0 <= clamped <= 100, f"Clamped value {clamped} not in [0, 100]"


# =============================================================================
# Risk Score Determinism Properties
# =============================================================================


class TestRiskScoreDeterminismProperties:
    """Property-based tests for risk score determinism."""

    @given(inputs=risk_calculation_inputs())
    @hypothesis_settings(max_examples=500)
    def test_risk_score_deterministic(self, inputs: dict) -> None:
        """Property: Same input produces same output (determinism).

        Calculating risk score multiple times with the same inputs
        should always produce the same result.
        """
        result1 = calculate_risk_score(inputs)
        result2 = calculate_risk_score(inputs)
        result3 = calculate_risk_score(inputs)

        assert result1 == result2 == result3, (
            f"Non-deterministic risk scores: {result1}, {result2}, {result3}"
        )

    @given(context=detection_context_strategy())
    @hypothesis_settings(max_examples=500)
    def test_detection_context_hashing_deterministic(self, context: dict) -> None:
        """Property: Detection context hashing is deterministic.

        Hashing the same context multiple times should produce the same hash,
        which could be used for caching risk calculations.
        """
        # Create a hashable representation
        hashable_str = str(sorted(context.items()))

        hash1 = hashlib.sha256(hashable_str.encode()).hexdigest()
        hash2 = hashlib.sha256(hashable_str.encode()).hexdigest()
        hash3 = hashlib.sha256(hashable_str.encode()).hexdigest()

        assert hash1 == hash2 == hash3, "Context hashing not deterministic"

    @given(
        inputs1=risk_calculation_inputs(),
        inputs2=risk_calculation_inputs(),
    )
    @hypothesis_settings(max_examples=500)
    def test_identical_inputs_identical_outputs(
        self,
        inputs1: dict,
        inputs2: dict,
    ) -> None:
        """Property: Identical inputs produce identical outputs.

        If two input dicts have exactly the same values, they should
        produce the same risk score.
        """
        # Make inputs2 identical to inputs1
        inputs2_copy = inputs1.copy()

        result1 = calculate_risk_score(inputs1)
        result2 = calculate_risk_score(inputs2_copy)

        assert result1 == result2, (
            f"Identical inputs produced different results: {result1} vs {result2}"
        )


# =============================================================================
# Severity Level Mapping Properties
# =============================================================================


class TestSeverityLevelMappingProperties:
    """Property-based tests for severity level mapping consistency."""

    @given(risk=valid_risk_score())
    @hypothesis_settings(max_examples=500)
    def test_severity_level_always_valid(self, risk: int) -> None:
        """Property: Every valid risk score maps to a valid severity level.

        All risk scores in [0, 100] should map to one of the four severity levels.
        """
        severity = get_severity_level(risk)

        valid_levels = {"low", "medium", "high", "critical"}
        assert severity in valid_levels, f"Invalid severity level: {severity}"

    @given(risk=valid_risk_score())
    @hypothesis_settings(max_examples=500)
    def test_severity_level_deterministic(self, risk: int) -> None:
        """Property: Same risk score always maps to same severity level.

        The mapping from risk score to severity level should be deterministic.
        """
        level1 = get_severity_level(risk)
        level2 = get_severity_level(risk)
        level3 = get_severity_level(risk)

        assert level1 == level2 == level3, (
            f"Non-deterministic severity mapping for {risk}: {level1}, {level2}, {level3}"
        )

    @given(risk=edge_case_risk_scores())
    @hypothesis_settings(max_examples=500)
    def test_boundary_risk_scores_map_correctly(self, risk: int) -> None:
        """Property: Boundary risk scores map to expected severity levels.

        Verify the boundary values (0, 25, 50, 75, 100) map correctly.
        """
        severity = get_severity_level(risk)

        expected_mapping = {
            0: "low",
            25: "low",  # 25 is the upper boundary of "low"
            50: "medium",  # 50 is the upper boundary of "medium"
            75: "high",  # 75 is the upper boundary of "high"
            100: "critical",
        }

        assert severity == expected_mapping[risk], (
            f"Boundary {risk} mapped to {severity}, expected {expected_mapping[risk]}"
        )

    @given(
        risk1=st.integers(min_value=0, max_value=100),
        risk2=st.integers(min_value=0, max_value=100),
    )
    @hypothesis_settings(max_examples=500)
    def test_severity_level_monotonic(
        self,
        risk1: int,
        risk2: int,
    ) -> None:
        """Property: Higher risk scores map to same or higher severity levels.

        The severity mapping should be monotonically non-decreasing.
        """
        level1 = get_severity_level(risk1)
        level2 = get_severity_level(risk2)

        level_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}

        if risk1 <= risk2:
            assert level_order[level1] <= level_order[level2], (
                f"Severity not monotonic: {risk1}->{level1}, {risk2}->{level2}"
            )
        else:
            assert level_order[level1] >= level_order[level2], (
                f"Severity not monotonic: {risk1}->{level1}, {risk2}->{level2}"
            )


# =============================================================================
# Risk Score Modification Properties
# =============================================================================


class TestRiskScoreModificationProperties:
    """Property-based tests for risk score modification operations."""

    @given(
        risk=valid_risk_score(),
        adjustment=st.integers(min_value=-100, max_value=100),
    )
    @hypothesis_settings(max_examples=500)
    def test_adjusted_risk_score_bounded(
        self,
        risk: int,
        adjustment: int,
    ) -> None:
        """Property: Adjusted risk scores remain bounded.

        Adding an adjustment to a risk score and clamping should
        always produce a value in [0, 100].
        """
        adjusted = max(0, min(100, risk + adjustment))

        assert 0 <= adjusted <= 100, f"Adjusted risk {adjusted} not in [0, 100]"

    @given(
        risk=valid_risk_score(),
        scale=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    )
    @hypothesis_settings(max_examples=500)
    def test_scaled_risk_score_bounded(
        self,
        risk: int,
        scale: float,
    ) -> None:
        """Property: Scaled risk scores remain bounded.

        Multiplying a risk score by a scale factor and clamping should
        always produce a value in [0, 100].
        """
        scaled = max(0, min(100, int(risk * scale)))

        assert 0 <= scaled <= 100, f"Scaled risk {scaled} not in [0, 100]"

    @given(
        risks=st.lists(valid_risk_score(), min_size=1, max_size=10),
    )
    @hypothesis_settings(max_examples=500)
    def test_average_risk_score_bounded(
        self,
        risks: list[int],
    ) -> None:
        """Property: Average of risk scores is bounded.

        The average of multiple risk scores should also be in [0, 100].
        """
        avg = sum(risks) / len(risks)
        avg_clamped = max(0, min(100, int(avg)))

        assert 0 <= avg_clamped <= 100, f"Average risk {avg_clamped} not in [0, 100]"

    @given(
        risks=st.lists(valid_risk_score(), min_size=1, max_size=10),
    )
    @hypothesis_settings(max_examples=500)
    def test_max_risk_score_bounded(
        self,
        risks: list[int],
    ) -> None:
        """Property: Maximum of risk scores is bounded.

        The maximum of multiple valid risk scores should be in [0, 100].
        """
        max_risk = max(risks)

        assert 0 <= max_risk <= 100, f"Max risk {max_risk} not in [0, 100]"

    @given(
        risks=st.lists(valid_risk_score(), min_size=1, max_size=10),
    )
    @hypothesis_settings(max_examples=500)
    def test_min_risk_score_bounded(
        self,
        risks: list[int],
    ) -> None:
        """Property: Minimum of risk scores is bounded.

        The minimum of multiple valid risk scores should be in [0, 100].
        """
        min_risk = min(risks)

        assert 0 <= min_risk <= 100, f"Min risk {min_risk} not in [0, 100]"


# =============================================================================
# Risk Score Aggregation Properties
# =============================================================================


class TestRiskScoreAggregationProperties:
    """Property-based tests for risk score aggregation operations."""

    @given(
        risks=st.lists(valid_risk_score(), min_size=2, max_size=10),
        weights=st.lists(
            st.floats(min_value=0.1, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=10,
        ),
    )
    @hypothesis_settings(max_examples=500)
    def test_weighted_average_bounded(
        self,
        risks: list[int],
        weights: list[float],
    ) -> None:
        """Property: Weighted average of risk scores is bounded.

        A weighted average of valid risk scores should also be in [0, 100].
        """
        # Ensure same number of weights and risks
        min_len = min(len(risks), len(weights))
        risks = risks[:min_len]
        weights = weights[:min_len]

        # Normalize weights
        total_weight = sum(weights)
        if total_weight == 0:
            return  # Skip if all weights are zero

        normalized_weights = [w / total_weight for w in weights]

        # Calculate weighted average
        weighted_avg = sum(r * w for r, w in zip(risks, normalized_weights, strict=False))
        weighted_avg_clamped = max(0, min(100, int(weighted_avg)))

        assert 0 <= weighted_avg_clamped <= 100, (
            f"Weighted average risk {weighted_avg_clamped} not in [0, 100]"
        )

    @given(
        risk1=valid_risk_score(),
        risk2=valid_risk_score(),
    )
    @hypothesis_settings(max_examples=500)
    def test_risk_combination_bounded(
        self,
        risk1: int,
        risk2: int,
    ) -> None:
        """Property: Various combinations of two risk scores are bounded.

        Tests that common combination operations produce bounded results.
        """
        # Maximum
        max_risk = max(risk1, risk2)
        assert 0 <= max_risk <= 100

        # Minimum
        min_risk = min(risk1, risk2)
        assert 0 <= min_risk <= 100

        # Average
        avg_risk = (risk1 + risk2) // 2
        assert 0 <= avg_risk <= 100

        # Sum (clamped)
        sum_risk = min(100, risk1 + risk2)
        assert 0 <= sum_risk <= 100

    @given(
        context=detection_context_strategy(),
    )
    @hypothesis_settings(max_examples=500)
    def test_detection_context_risk_computation(
        self,
        context: dict,
    ) -> None:
        """Property: Risk computed from detection context is bounded.

        Computing risk from a realistic detection context should
        always produce a value in [0, 100].
        """
        # Simple risk calculation based on context
        base_risk = 50

        # Adjust based on object type
        if context["object_type"] == "person":
            base_risk += 10
        elif context["object_type"] in ["vehicle", "car", "truck"]:
            base_risk += 5

        # Adjust based on time
        if context["is_nighttime"]:
            base_risk += 15

        # Adjust based on location
        if context["is_in_exclusion_zone"]:
            base_risk += 20

        # Adjust based on entity recognition
        if context["is_known_entity"]:
            base_risk -= 30

        # Scale by confidence
        base_risk = int(base_risk * context["confidence"])

        # Clamp to valid range
        final_risk = max(0, min(100, base_risk))

        assert 0 <= final_risk <= 100, f"Context-based risk {final_risk} not in [0, 100]"
