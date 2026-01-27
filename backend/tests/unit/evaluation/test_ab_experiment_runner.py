"""Unit tests for A/B Experiment Runner (NEM-3731).

Tests the statistical analysis functions including select_variant,
analyze_experiment, and summarize_results.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.config.prompt_ab_config import PromptExperiment
from backend.evaluation.ab_experiment_runner import (
    ExperimentResults,
    _interpret_effect_size,
    analyze_experiment,
    select_variant,
    summarize_results,
)

# =============================================================================
# ExperimentResults Dataclass Tests
# =============================================================================


class TestExperimentResults:
    """Tests for ExperimentResults dataclass."""

    def test_create_experiment_results(self) -> None:
        """Test creating ExperimentResults with all fields."""
        results = ExperimentResults(
            control_scores=[0.8, 0.82, 0.79],
            variant_scores=[0.9, 0.88, 0.91],
            control_mean=0.803,
            variant_mean=0.897,
            control_std=0.015,
            variant_std=0.015,
            t_statistic=-5.5,
            p_value=0.005,
            is_significant=True,
            effect_size=6.27,
        )

        assert results.control_scores == [0.8, 0.82, 0.79]
        assert results.variant_scores == [0.9, 0.88, 0.91]
        assert results.control_mean == 0.803
        assert results.variant_mean == 0.897
        assert results.is_significant is True
        assert results.effect_size == 6.27


# =============================================================================
# select_variant() Tests
# =============================================================================


class TestSelectVariant:
    """Tests for select_variant() function."""

    @pytest.fixture
    def experiment(self) -> PromptExperiment:
        """Create a test experiment with 10% traffic to variant."""
        return PromptExperiment(
            name="test",
            description="Test experiment",
            control_prompt_key="control_key",
            variant_prompt_key="variant_key",
            traffic_split=0.1,
        )

    @pytest.fixture
    def fifty_fifty_experiment(self) -> PromptExperiment:
        """Create a test experiment with 50% traffic to variant."""
        return PromptExperiment(
            name="fifty_fifty",
            description="50/50 split",
            control_prompt_key="control_key",
            variant_prompt_key="variant_key",
            traffic_split=0.5,
        )

    def test_select_variant_returns_control_when_random_above_split(
        self, experiment: PromptExperiment
    ) -> None:
        """Test that control is returned when random > traffic_split."""
        with patch("backend.evaluation.ab_experiment_runner.random.random", return_value=0.5):
            result = select_variant(experiment)

        assert result == "control_key"

    def test_select_variant_returns_variant_when_random_below_split(
        self, experiment: PromptExperiment
    ) -> None:
        """Test that variant is returned when random < traffic_split."""
        with patch("backend.evaluation.ab_experiment_runner.random.random", return_value=0.05):
            result = select_variant(experiment)

        assert result == "variant_key"

    def test_select_variant_boundary_at_split(self, experiment: PromptExperiment) -> None:
        """Test boundary condition when random equals traffic_split."""
        # At exactly the split value, should return control (not <)
        with patch("backend.evaluation.ab_experiment_runner.random.random", return_value=0.1):
            result = select_variant(experiment)

        assert result == "control_key"

    def test_select_variant_fifty_fifty_below(
        self, fifty_fifty_experiment: PromptExperiment
    ) -> None:
        """Test 50/50 split returns variant when random < 0.5."""
        with patch("backend.evaluation.ab_experiment_runner.random.random", return_value=0.3):
            result = select_variant(fifty_fifty_experiment)

        assert result == "variant_key"

    def test_select_variant_fifty_fifty_above(
        self, fifty_fifty_experiment: PromptExperiment
    ) -> None:
        """Test 50/50 split returns control when random >= 0.5."""
        with patch("backend.evaluation.ab_experiment_runner.random.random", return_value=0.7):
            result = select_variant(fifty_fifty_experiment)

        assert result == "control_key"

    def test_select_variant_zero_split_always_control(self) -> None:
        """Test that 0% split always returns control."""
        experiment = PromptExperiment(
            name="all_control",
            description="All control",
            control_prompt_key="control_key",
            variant_prompt_key="variant_key",
            traffic_split=0.0,
        )

        # Test multiple random values
        for random_val in [0.0, 0.5, 0.99]:
            with patch(
                "backend.evaluation.ab_experiment_runner.random.random",
                return_value=random_val,
            ):
                result = select_variant(experiment)
                assert result == "control_key"

    def test_select_variant_full_split_always_variant(self) -> None:
        """Test that 100% split always returns variant."""
        experiment = PromptExperiment(
            name="all_variant",
            description="All variant",
            control_prompt_key="control_key",
            variant_prompt_key="variant_key",
            traffic_split=1.0,
        )

        # Test multiple random values
        for random_val in [0.0, 0.5, 0.99]:
            with patch(
                "backend.evaluation.ab_experiment_runner.random.random",
                return_value=random_val,
            ):
                result = select_variant(experiment)
                assert result == "variant_key"

    def test_select_variant_distribution_over_many_calls(
        self, experiment: PromptExperiment
    ) -> None:
        """Test that distribution roughly matches traffic split over many calls."""
        # Run without mocking to test real distribution
        n_trials = 1000
        variant_count = sum(
            1 for _ in range(n_trials) if select_variant(experiment) == "variant_key"
        )

        # With 10% split, expect ~100 variants (allow tolerance)
        expected = n_trials * experiment.traffic_split
        tolerance = n_trials * 0.05  # 5% tolerance
        assert abs(variant_count - expected) < tolerance


# =============================================================================
# analyze_experiment() Tests
# =============================================================================


class TestAnalyzeExperiment:
    """Tests for analyze_experiment() function."""

    def test_analyze_with_significant_difference(self) -> None:
        """Test analysis with clearly significant difference."""
        # Control: low scores, Variant: high scores
        control = [0.50, 0.52, 0.48, 0.51, 0.49, 0.50, 0.51, 0.49, 0.52, 0.48]
        variant = [0.90, 0.88, 0.92, 0.89, 0.91, 0.90, 0.88, 0.91, 0.89, 0.90]

        results = analyze_experiment(control, variant)

        assert results.is_significant is True
        assert results.p_value < 0.05
        assert results.variant_mean > results.control_mean
        # Large effect size expected
        assert abs(results.effect_size) > 0.8

    def test_analyze_with_no_significant_difference(self) -> None:
        """Test analysis with no significant difference."""
        # Very similar distributions
        control = [0.50, 0.51, 0.49, 0.50, 0.51, 0.50, 0.49, 0.50, 0.51, 0.50]
        variant = [0.50, 0.52, 0.48, 0.51, 0.49, 0.50, 0.52, 0.49, 0.51, 0.50]

        results = analyze_experiment(control, variant)

        assert results.is_significant is False
        assert results.p_value > 0.05
        # Small effect size expected
        assert abs(results.effect_size) < 0.5

    def test_analyze_with_custom_alpha(self) -> None:
        """Test analysis with custom alpha level."""
        control = [0.50, 0.52, 0.48, 0.51, 0.49]
        variant = [0.55, 0.57, 0.53, 0.56, 0.54]

        # With standard alpha=0.05
        results_standard = analyze_experiment(control, variant, alpha=0.05)

        # With very strict alpha=0.001
        results_strict = analyze_experiment(control, variant, alpha=0.001)

        # Same p-value, different significance decisions possible
        assert results_standard.p_value == results_strict.p_value
        # With strict alpha, might not be significant
        if results_standard.is_significant:
            # Only if p < 0.001 would strict also be significant
            if results_standard.p_value >= 0.001:
                assert results_strict.is_significant is False

    def test_analyze_returns_correct_statistics(self) -> None:
        """Test that analyze returns correct mean and std values."""
        control = [1.0, 2.0, 3.0, 4.0, 5.0]
        variant = [6.0, 7.0, 8.0, 9.0, 10.0]

        results = analyze_experiment(control, variant)

        # Check means
        assert results.control_mean == 3.0
        assert results.variant_mean == 8.0

        # Check sample sizes preserved
        assert results.control_scores == control
        assert results.variant_scores == variant

    def test_analyze_with_identical_values(self) -> None:
        """Test analysis when all values in a group are identical."""
        control = [0.5, 0.5, 0.5, 0.5, 0.5]
        variant = [0.8, 0.8, 0.8, 0.8, 0.8]

        results = analyze_experiment(control, variant)

        # Standard deviations should be 0
        assert results.control_std == 0.0
        assert results.variant_std == 0.0
        # Effect size should handle zero std gracefully
        # (division by zero case - should return 0 or be handled)

    def test_analyze_raises_error_with_single_control_value(self) -> None:
        """Test that single control value raises ValueError."""
        with pytest.raises(ValueError, match="control_scores must have at least 2 values"):
            analyze_experiment([0.5], [0.6, 0.7, 0.8])

    def test_analyze_raises_error_with_single_variant_value(self) -> None:
        """Test that single variant value raises ValueError."""
        with pytest.raises(ValueError, match="variant_scores must have at least 2 values"):
            analyze_experiment([0.5, 0.6, 0.7], [0.8])

    def test_analyze_raises_error_with_empty_control(self) -> None:
        """Test that empty control raises ValueError."""
        with pytest.raises(ValueError, match="control_scores must have at least 2 values"):
            analyze_experiment([], [0.6, 0.7, 0.8])

    def test_analyze_raises_error_with_empty_variant(self) -> None:
        """Test that empty variant raises ValueError."""
        with pytest.raises(ValueError, match="variant_scores must have at least 2 values"):
            analyze_experiment([0.5, 0.6, 0.7], [])

    def test_analyze_effect_size_positive_when_variant_better(self) -> None:
        """Test that effect size is positive when variant > control."""
        control = [0.3, 0.35, 0.32, 0.33, 0.34]
        variant = [0.7, 0.72, 0.68, 0.71, 0.69]

        results = analyze_experiment(control, variant)

        assert results.effect_size > 0

    def test_analyze_effect_size_negative_when_control_better(self) -> None:
        """Test that effect size is negative when control > variant."""
        control = [0.7, 0.72, 0.68, 0.71, 0.69]
        variant = [0.3, 0.35, 0.32, 0.33, 0.34]

        results = analyze_experiment(control, variant)

        assert results.effect_size < 0

    def test_analyze_with_known_values(self) -> None:
        """Test analysis with known statistical values for verification."""
        # Use simple values that are easy to verify
        control = [1.0, 2.0, 3.0]
        variant = [4.0, 5.0, 6.0]

        results = analyze_experiment(control, variant)

        # Mean of [1,2,3] = 2.0, Mean of [4,5,6] = 5.0
        assert results.control_mean == 2.0
        assert results.variant_mean == 5.0

        # Sample std of [1,2,3] = 1.0, Sample std of [4,5,6] = 1.0
        assert results.control_std == 1.0
        assert results.variant_std == 1.0

        # With means 3 apart and pooled std of 1, effect size = 3.0
        assert abs(results.effect_size - 3.0) < 0.001


# =============================================================================
# _interpret_effect_size() Tests
# =============================================================================


class TestInterpretEffectSize:
    """Tests for _interpret_effect_size() helper function."""

    def test_negligible_effect(self) -> None:
        """Test interpretation of negligible effect size."""
        assert _interpret_effect_size(0.0) == "negligible"
        assert _interpret_effect_size(0.1) == "negligible"
        assert _interpret_effect_size(0.19) == "negligible"
        assert _interpret_effect_size(-0.1) == "negligible"

    def test_small_effect(self) -> None:
        """Test interpretation of small effect size."""
        assert _interpret_effect_size(0.2) == "small"
        assert _interpret_effect_size(0.3) == "small"
        assert _interpret_effect_size(0.49) == "small"
        assert _interpret_effect_size(-0.3) == "small"

    def test_medium_effect(self) -> None:
        """Test interpretation of medium effect size."""
        assert _interpret_effect_size(0.5) == "medium"
        assert _interpret_effect_size(0.6) == "medium"
        assert _interpret_effect_size(0.79) == "medium"
        assert _interpret_effect_size(-0.6) == "medium"

    def test_large_effect(self) -> None:
        """Test interpretation of large effect size."""
        assert _interpret_effect_size(0.8) == "large"
        assert _interpret_effect_size(1.0) == "large"
        assert _interpret_effect_size(2.0) == "large"
        assert _interpret_effect_size(-1.5) == "large"


# =============================================================================
# summarize_results() Tests
# =============================================================================


class TestSummarizeResults:
    """Tests for summarize_results() function."""

    @pytest.fixture
    def significant_results(self) -> ExperimentResults:
        """Create results with significant difference."""
        return ExperimentResults(
            control_scores=[0.5, 0.52, 0.48, 0.51, 0.49],
            variant_scores=[0.9, 0.88, 0.92, 0.89, 0.91],
            control_mean=0.5,
            variant_mean=0.9,
            control_std=0.015,
            variant_std=0.015,
            t_statistic=-26.67,
            p_value=0.0001,
            is_significant=True,
            effect_size=26.67,
        )

    @pytest.fixture
    def not_significant_results(self) -> ExperimentResults:
        """Create results with no significant difference."""
        return ExperimentResults(
            control_scores=[0.5, 0.52, 0.48, 0.51, 0.49],
            variant_scores=[0.51, 0.53, 0.47, 0.52, 0.48],
            control_mean=0.5,
            variant_mean=0.502,
            control_std=0.015,
            variant_std=0.024,
            t_statistic=-0.14,
            p_value=0.89,
            is_significant=False,
            effect_size=0.1,
        )

    def test_summary_contains_significant_header(
        self, significant_results: ExperimentResults
    ) -> None:
        """Test that summary shows SIGNIFICANT in header."""
        summary = summarize_results(significant_results)

        assert "SIGNIFICANT" in summary
        assert "NOT SIGNIFICANT" not in summary

    def test_summary_contains_not_significant_header(
        self, not_significant_results: ExperimentResults
    ) -> None:
        """Test that summary shows NOT SIGNIFICANT in header."""
        summary = summarize_results(not_significant_results)

        assert "NOT SIGNIFICANT" in summary

    def test_summary_contains_control_stats(self, significant_results: ExperimentResults) -> None:
        """Test that summary includes control statistics."""
        summary = summarize_results(significant_results)

        assert "Control:" in summary
        assert "mean=" in summary
        assert "std=" in summary
        assert "n=5" in summary

    def test_summary_contains_variant_stats(self, significant_results: ExperimentResults) -> None:
        """Test that summary includes variant statistics."""
        summary = summarize_results(significant_results)

        assert "Variant:" in summary

    def test_summary_contains_statistical_analysis(
        self, significant_results: ExperimentResults
    ) -> None:
        """Test that summary includes statistical analysis section."""
        summary = summarize_results(significant_results)

        assert "Statistical Analysis:" in summary
        assert "t-statistic:" in summary
        assert "p-value:" in summary
        assert "Effect size" in summary
        assert "Cohen's d" in summary

    def test_summary_contains_effect_size_interpretation(
        self, significant_results: ExperimentResults
    ) -> None:
        """Test that summary includes effect size interpretation."""
        summary = summarize_results(significant_results)

        # Should have one of the interpretations
        assert any(interp in summary for interp in ["negligible", "small", "medium", "large"])

    def test_summary_indicates_variant_better(self, significant_results: ExperimentResults) -> None:
        """Test that summary indicates variant performs better."""
        summary = summarize_results(significant_results)

        assert "Variant performs BETTER than control" in summary

    def test_summary_indicates_variant_worse(self) -> None:
        """Test that summary indicates when variant performs worse."""
        results = ExperimentResults(
            control_scores=[0.9, 0.88, 0.92, 0.89, 0.91],
            variant_scores=[0.5, 0.52, 0.48, 0.51, 0.49],
            control_mean=0.9,
            variant_mean=0.5,
            control_std=0.015,
            variant_std=0.015,
            t_statistic=26.67,
            p_value=0.0001,
            is_significant=True,
            effect_size=-26.67,
        )

        summary = summarize_results(results)

        assert "Variant performs WORSE than control" in summary

    def test_summary_indicates_no_difference(self) -> None:
        """Test that summary indicates no difference when means equal."""
        results = ExperimentResults(
            control_scores=[0.5, 0.52, 0.48],
            variant_scores=[0.51, 0.49, 0.50],
            control_mean=0.5,
            variant_mean=0.5,  # Same mean
            control_std=0.02,
            variant_std=0.01,
            t_statistic=0.0,
            p_value=1.0,
            is_significant=False,
            effect_size=0.0,
        )

        summary = summarize_results(results)

        assert "No difference between variant and control" in summary

    def test_summary_interpretation_for_significant(
        self, significant_results: ExperimentResults
    ) -> None:
        """Test interpretation text for significant results."""
        summary = summarize_results(significant_results)

        assert "The difference IS statistically significant" in summary

    def test_summary_interpretation_for_not_significant(
        self, not_significant_results: ExperimentResults
    ) -> None:
        """Test interpretation text for non-significant results."""
        summary = summarize_results(not_significant_results)

        assert "The difference is NOT statistically significant" in summary

    def test_summary_is_readable_string(self, significant_results: ExperimentResults) -> None:
        """Test that summary is a non-empty readable string."""
        summary = summarize_results(significant_results)

        assert isinstance(summary, str)
        assert len(summary) > 100  # Should be a substantial summary
        assert "=====" in summary  # Contains separator
