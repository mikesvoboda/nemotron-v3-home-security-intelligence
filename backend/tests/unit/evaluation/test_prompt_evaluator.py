"""Unit tests for backend.evaluation.prompt_evaluator module."""

from __future__ import annotations

import pytest

from backend.evaluation.prompt_eval_dataset import PromptEvalSample
from backend.evaluation.prompt_evaluator import (
    EvaluationResult,
    calculate_metrics,
    evaluate_batch,
    evaluate_prediction,
    get_misclassified,
    summarize_results,
)


@pytest.fixture
def sample_low_risk() -> PromptEvalSample:
    """Create a low-risk sample for testing."""
    return PromptEvalSample(
        scenario_id="normal_001",
        category="normal",
        media_path=None,
        expected_risk_range=(0, 25),
        expected_risk_level="low",
        expected_factors=[],
    )


@pytest.fixture
def sample_medium_risk() -> PromptEvalSample:
    """Create a medium-risk sample for testing."""
    return PromptEvalSample(
        scenario_id="suspicious_001",
        category="suspicious",
        media_path=None,
        expected_risk_range=(35, 60),
        expected_risk_level="medium",
        expected_factors=["prolonged_observation", "unknown_person"],
    )


@pytest.fixture
def sample_high_risk() -> PromptEvalSample:
    """Create a high-risk sample for testing."""
    return PromptEvalSample(
        scenario_id="threat_001",
        category="threats",
        media_path=None,
        expected_risk_range=(70, 90),
        expected_risk_level="high",
        expected_factors=["forced_entry", "unknown_person"],
    )


@pytest.fixture
def sample_critical_risk() -> PromptEvalSample:
    """Create a critical-risk sample for testing."""
    return PromptEvalSample(
        scenario_id="threat_002",
        category="threats",
        media_path=None,
        expected_risk_range=(85, 100),
        expected_risk_level="critical",
        expected_factors=["weapon_visible", "immediate_threat"],
    )


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating an evaluation result."""
        result = EvaluationResult(
            scenario_id="test_001",
            category="normal",
            actual_score=15,
            expected_range=(0, 25),
            score_in_range=True,
            actual_level="low",
            expected_level="low",
            level_match=True,
        )

        assert result.scenario_id == "test_001"
        assert result.category == "normal"
        assert result.actual_score == 15
        assert result.expected_range == (0, 25)
        assert result.score_in_range is True
        assert result.level_match is True

    def test_is_accurate_both_correct(self) -> None:
        """Test is_accurate when both score and level are correct."""
        result = EvaluationResult(
            scenario_id="test_001",
            category="normal",
            actual_score=15,
            expected_range=(0, 25),
            score_in_range=True,
            actual_level="low",
            expected_level="low",
            level_match=True,
        )

        assert result.is_accurate is True

    def test_is_accurate_score_wrong(self) -> None:
        """Test is_accurate when score is out of range."""
        result = EvaluationResult(
            scenario_id="test_001",
            category="normal",
            actual_score=50,
            expected_range=(0, 25),
            score_in_range=False,
            actual_level="low",
            expected_level="low",
            level_match=True,
        )

        assert result.is_accurate is False

    def test_is_accurate_level_wrong(self) -> None:
        """Test is_accurate when level doesn't match."""
        result = EvaluationResult(
            scenario_id="test_001",
            category="normal",
            actual_score=15,
            expected_range=(0, 25),
            score_in_range=True,
            actual_level="medium",
            expected_level="low",
            level_match=False,
        )

        assert result.is_accurate is False

    def test_is_accurate_both_wrong(self) -> None:
        """Test is_accurate when both are wrong."""
        result = EvaluationResult(
            scenario_id="test_001",
            category="normal",
            actual_score=50,
            expected_range=(0, 25),
            score_in_range=False,
            actual_level="medium",
            expected_level="low",
            level_match=False,
        )

        assert result.is_accurate is False

    def test_default_values(self) -> None:
        """Test default values for optional fields."""
        result = EvaluationResult(
            scenario_id="test_001",
            category="normal",
            actual_score=15,
            expected_range=(0, 25),
            score_in_range=True,
            actual_level="low",
            expected_level="low",
            level_match=True,
        )

        assert result.deviation == 0.0
        assert result.expected_factors is None


class TestEvaluatePrediction:
    """Tests for evaluate_prediction function."""

    def test_score_within_range(self, sample_low_risk: PromptEvalSample) -> None:
        """Test evaluation with score within expected range."""
        result = evaluate_prediction(sample_low_risk, actual_score=15, actual_level="low")

        assert result.score_in_range is True
        assert result.deviation == 0.0
        assert result.level_match is True
        assert result.scenario_id == "normal_001"
        assert result.category == "normal"

    def test_score_at_minimum(self, sample_low_risk: PromptEvalSample) -> None:
        """Test evaluation with score at minimum of range."""
        result = evaluate_prediction(sample_low_risk, actual_score=0, actual_level="low")

        assert result.score_in_range is True
        assert result.deviation == 0.0

    def test_score_at_maximum(self, sample_low_risk: PromptEvalSample) -> None:
        """Test evaluation with score at maximum of range."""
        result = evaluate_prediction(sample_low_risk, actual_score=25, actual_level="low")

        assert result.score_in_range is True
        assert result.deviation == 0.0

    def test_score_below_range(self, sample_medium_risk: PromptEvalSample) -> None:
        """Test evaluation with score below expected range."""
        # Range is (35, 60), score of 20 is 15 below minimum
        result = evaluate_prediction(sample_medium_risk, actual_score=20, actual_level="medium")

        assert result.score_in_range is False
        assert result.deviation == 15.0

    def test_score_above_range(self, sample_medium_risk: PromptEvalSample) -> None:
        """Test evaluation with score above expected range."""
        # Range is (35, 60), score of 75 is 15 above maximum
        result = evaluate_prediction(sample_medium_risk, actual_score=75, actual_level="medium")

        assert result.score_in_range is False
        assert result.deviation == 15.0

    def test_level_match_case_insensitive(self, sample_low_risk: PromptEvalSample) -> None:
        """Test that level matching is case-insensitive."""
        result = evaluate_prediction(sample_low_risk, actual_score=15, actual_level="LOW")

        assert result.level_match is True

    def test_level_match_with_whitespace(self, sample_low_risk: PromptEvalSample) -> None:
        """Test that level matching handles whitespace."""
        result = evaluate_prediction(sample_low_risk, actual_score=15, actual_level="  low  ")

        assert result.level_match is True

    def test_level_mismatch(self, sample_low_risk: PromptEvalSample) -> None:
        """Test evaluation with incorrect level."""
        result = evaluate_prediction(sample_low_risk, actual_score=15, actual_level="high")

        assert result.level_match is False
        assert result.actual_level == "high"
        assert result.expected_level == "low"

    def test_expected_factors_preserved(self, sample_medium_risk: PromptEvalSample) -> None:
        """Test that expected factors are preserved in result."""
        result = evaluate_prediction(sample_medium_risk, actual_score=50, actual_level="medium")

        assert result.expected_factors == ["prolonged_observation", "unknown_person"]

    def test_various_risk_levels(
        self,
        sample_low_risk: PromptEvalSample,
        sample_medium_risk: PromptEvalSample,
        sample_high_risk: PromptEvalSample,
        sample_critical_risk: PromptEvalSample,
    ) -> None:
        """Test evaluation across different risk levels."""
        results = [
            evaluate_prediction(sample_low_risk, actual_score=10, actual_level="low"),
            evaluate_prediction(sample_medium_risk, actual_score=45, actual_level="medium"),
            evaluate_prediction(sample_high_risk, actual_score=80, actual_level="high"),
            evaluate_prediction(sample_critical_risk, actual_score=95, actual_level="critical"),
        ]

        assert all(r.score_in_range for r in results)
        assert all(r.level_match for r in results)


class TestCalculateMetrics:
    """Tests for calculate_metrics function."""

    def test_empty_results(self) -> None:
        """Test metrics calculation with empty results."""
        metrics = calculate_metrics([])

        assert metrics["accuracy"] == 0.0
        assert metrics["level_accuracy"] == 0.0
        assert metrics["combined_accuracy"] == 0.0
        assert metrics["count"] == 0
        assert metrics["mean_deviation"] == 0.0
        assert metrics["by_category"] == {}

    def test_all_accurate(self) -> None:
        """Test metrics when all predictions are accurate."""
        results = [
            EvaluationResult(
                scenario_id="test_1",
                category="normal",
                actual_score=15,
                expected_range=(0, 25),
                score_in_range=True,
                actual_level="low",
                expected_level="low",
                level_match=True,
                deviation=0.0,
            ),
            EvaluationResult(
                scenario_id="test_2",
                category="normal",
                actual_score=20,
                expected_range=(0, 25),
                score_in_range=True,
                actual_level="low",
                expected_level="low",
                level_match=True,
                deviation=0.0,
            ),
        ]

        metrics = calculate_metrics(results)

        assert metrics["accuracy"] == 1.0
        assert metrics["level_accuracy"] == 1.0
        assert metrics["combined_accuracy"] == 1.0
        assert metrics["count"] == 2
        assert metrics["mean_deviation"] == 0.0

    def test_all_inaccurate(self) -> None:
        """Test metrics when all predictions are inaccurate."""
        results = [
            EvaluationResult(
                scenario_id="test_1",
                category="normal",
                actual_score=50,
                expected_range=(0, 25),
                score_in_range=False,
                actual_level="high",
                expected_level="low",
                level_match=False,
                deviation=25.0,
            ),
            EvaluationResult(
                scenario_id="test_2",
                category="suspicious",
                actual_score=10,
                expected_range=(35, 60),
                score_in_range=False,
                actual_level="low",
                expected_level="medium",
                level_match=False,
                deviation=25.0,
            ),
        ]

        metrics = calculate_metrics(results)

        assert metrics["accuracy"] == 0.0
        assert metrics["level_accuracy"] == 0.0
        assert metrics["combined_accuracy"] == 0.0
        assert metrics["count"] == 2
        assert metrics["mean_deviation"] == 25.0

    def test_mixed_results(self) -> None:
        """Test metrics with mixed accuracy."""
        results = [
            EvaluationResult(
                scenario_id="test_1",
                category="normal",
                actual_score=15,
                expected_range=(0, 25),
                score_in_range=True,
                actual_level="low",
                expected_level="low",
                level_match=True,
                deviation=0.0,
            ),
            EvaluationResult(
                scenario_id="test_2",
                category="suspicious",
                actual_score=80,
                expected_range=(35, 60),
                score_in_range=False,
                actual_level="high",
                expected_level="medium",
                level_match=False,
                deviation=20.0,
            ),
        ]

        metrics = calculate_metrics(results)

        assert metrics["accuracy"] == 0.5
        assert metrics["level_accuracy"] == 0.5
        assert metrics["combined_accuracy"] == 0.5
        assert metrics["count"] == 2
        assert metrics["mean_deviation"] == 10.0

    def test_by_category_breakdown(self) -> None:
        """Test category-level metrics breakdown."""
        results = [
            EvaluationResult(
                scenario_id="normal_1",
                category="normal",
                actual_score=15,
                expected_range=(0, 25),
                score_in_range=True,
                actual_level="low",
                expected_level="low",
                level_match=True,
                deviation=0.0,
            ),
            EvaluationResult(
                scenario_id="normal_2",
                category="normal",
                actual_score=30,
                expected_range=(0, 25),
                score_in_range=False,
                actual_level="low",
                expected_level="low",
                level_match=True,
                deviation=5.0,
            ),
            EvaluationResult(
                scenario_id="suspicious_1",
                category="suspicious",
                actual_score=50,
                expected_range=(35, 60),
                score_in_range=True,
                actual_level="medium",
                expected_level="medium",
                level_match=True,
                deviation=0.0,
            ),
        ]

        metrics = calculate_metrics(results)

        assert "normal" in metrics["by_category"]
        assert "suspicious" in metrics["by_category"]

        normal_metrics = metrics["by_category"]["normal"]
        assert normal_metrics["accuracy"] == 0.5  # 1 of 2 in range
        assert normal_metrics["level_accuracy"] == 1.0  # 2 of 2 correct level
        assert normal_metrics["count"] == 2
        assert normal_metrics["mean_deviation"] == 2.5  # (0 + 5) / 2

        suspicious_metrics = metrics["by_category"]["suspicious"]
        assert suspicious_metrics["accuracy"] == 1.0
        assert suspicious_metrics["level_accuracy"] == 1.0
        assert suspicious_metrics["count"] == 1

    def test_combined_accuracy_score_right_level_wrong(self) -> None:
        """Test combined accuracy when score is right but level is wrong."""
        results = [
            EvaluationResult(
                scenario_id="test_1",
                category="normal",
                actual_score=15,
                expected_range=(0, 25),
                score_in_range=True,
                actual_level="high",
                expected_level="low",
                level_match=False,
                deviation=0.0,
            ),
        ]

        metrics = calculate_metrics(results)

        assert metrics["accuracy"] == 1.0  # Score is in range
        assert metrics["level_accuracy"] == 0.0  # Level is wrong
        assert metrics["combined_accuracy"] == 0.0  # Both must be correct


class TestEvaluateBatch:
    """Tests for evaluate_batch function."""

    def test_evaluates_all_samples(
        self,
        sample_low_risk: PromptEvalSample,
        sample_medium_risk: PromptEvalSample,
    ) -> None:
        """Test that all samples are evaluated."""
        samples = [sample_low_risk, sample_medium_risk]
        predictions = [(15, "low"), (50, "medium")]

        results = evaluate_batch(samples, predictions)

        assert len(results) == 2
        assert results[0].scenario_id == "normal_001"
        assert results[1].scenario_id == "suspicious_001"

    def test_mismatched_lengths_raises(
        self,
        sample_low_risk: PromptEvalSample,
    ) -> None:
        """Test that mismatched lengths raise ValueError."""
        samples = [sample_low_risk]
        predictions = [(15, "low"), (50, "medium")]  # More predictions than samples

        with pytest.raises(ValueError, match="Number of samples"):
            evaluate_batch(samples, predictions)

    def test_empty_batch(self) -> None:
        """Test evaluating empty batch."""
        results = evaluate_batch([], [])

        assert results == []


class TestSummarizeResults:
    """Tests for summarize_results function."""

    def test_empty_results(self) -> None:
        """Test summary of empty results."""
        summary = summarize_results([])

        assert "No evaluation results" in summary

    def test_contains_key_metrics(self) -> None:
        """Test that summary contains key metrics."""
        results = [
            EvaluationResult(
                scenario_id="test_1",
                category="normal",
                actual_score=15,
                expected_range=(0, 25),
                score_in_range=True,
                actual_level="low",
                expected_level="low",
                level_match=True,
                deviation=0.0,
            ),
        ]

        summary = summarize_results(results)

        assert "Total samples evaluated" in summary
        assert "Score accuracy" in summary
        assert "Level accuracy" in summary
        assert "Mean deviation" in summary
        assert "By Category" in summary

    def test_includes_category_breakdown(self) -> None:
        """Test that summary includes category breakdown."""
        results = [
            EvaluationResult(
                scenario_id="test_1",
                category="normal",
                actual_score=15,
                expected_range=(0, 25),
                score_in_range=True,
                actual_level="low",
                expected_level="low",
                level_match=True,
                deviation=0.0,
            ),
            EvaluationResult(
                scenario_id="test_2",
                category="suspicious",
                actual_score=50,
                expected_range=(35, 60),
                score_in_range=True,
                actual_level="medium",
                expected_level="medium",
                level_match=True,
                deviation=0.0,
            ),
        ]

        summary = summarize_results(results)

        assert "normal" in summary
        assert "suspicious" in summary


class TestGetMisclassified:
    """Tests for get_misclassified function."""

    def test_returns_empty_when_all_correct(self) -> None:
        """Test that empty list is returned when all predictions are correct."""
        results = [
            EvaluationResult(
                scenario_id="test_1",
                category="normal",
                actual_score=15,
                expected_range=(0, 25),
                score_in_range=True,
                actual_level="low",
                expected_level="low",
                level_match=True,
            ),
        ]

        misclassified = get_misclassified(results)

        assert misclassified == []

    def test_returns_score_misclassified(self) -> None:
        """Test finding results with score out of range."""
        results = [
            EvaluationResult(
                scenario_id="correct",
                category="normal",
                actual_score=15,
                expected_range=(0, 25),
                score_in_range=True,
                actual_level="low",
                expected_level="low",
                level_match=True,
            ),
            EvaluationResult(
                scenario_id="wrong_score",
                category="normal",
                actual_score=50,
                expected_range=(0, 25),
                score_in_range=False,
                actual_level="low",
                expected_level="low",
                level_match=True,
            ),
        ]

        misclassified = get_misclassified(results, by_score=True, by_level=False)

        assert len(misclassified) == 1
        assert misclassified[0].scenario_id == "wrong_score"

    def test_returns_level_misclassified(self) -> None:
        """Test finding results with incorrect level."""
        results = [
            EvaluationResult(
                scenario_id="correct",
                category="normal",
                actual_score=15,
                expected_range=(0, 25),
                score_in_range=True,
                actual_level="low",
                expected_level="low",
                level_match=True,
            ),
            EvaluationResult(
                scenario_id="wrong_level",
                category="normal",
                actual_score=15,
                expected_range=(0, 25),
                score_in_range=True,
                actual_level="high",
                expected_level="low",
                level_match=False,
            ),
        ]

        misclassified = get_misclassified(results, by_score=False, by_level=True)

        assert len(misclassified) == 1
        assert misclassified[0].scenario_id == "wrong_level"

    def test_returns_both_misclassified(self) -> None:
        """Test finding results with both types of errors."""
        results = [
            EvaluationResult(
                scenario_id="correct",
                category="normal",
                actual_score=15,
                expected_range=(0, 25),
                score_in_range=True,
                actual_level="low",
                expected_level="low",
                level_match=True,
            ),
            EvaluationResult(
                scenario_id="wrong_score",
                category="normal",
                actual_score=50,
                expected_range=(0, 25),
                score_in_range=False,
                actual_level="low",
                expected_level="low",
                level_match=True,
            ),
            EvaluationResult(
                scenario_id="wrong_level",
                category="normal",
                actual_score=15,
                expected_range=(0, 25),
                score_in_range=True,
                actual_level="high",
                expected_level="low",
                level_match=False,
            ),
        ]

        misclassified = get_misclassified(results, by_score=True, by_level=True)

        assert len(misclassified) == 2
        scenario_ids = {r.scenario_id for r in misclassified}
        assert scenario_ids == {"wrong_score", "wrong_level"}

    def test_no_duplicates(self) -> None:
        """Test that results with both errors don't appear twice."""
        results = [
            EvaluationResult(
                scenario_id="both_wrong",
                category="normal",
                actual_score=50,
                expected_range=(0, 25),
                score_in_range=False,
                actual_level="high",
                expected_level="low",
                level_match=False,
            ),
        ]

        misclassified = get_misclassified(results, by_score=True, by_level=True)

        assert len(misclassified) == 1
        assert misclassified[0].scenario_id == "both_wrong"
