"""
Test suite for LLM response quality scoring module.

This module tests the quality assessment of LLM responses against ground truth data,
evaluating risk score accuracy, classification correctness, JSON validity, and
reasoning quality.

TDD Phase: RED - Tests are written first and should FAIL until implementation is complete.
"""

from typing import Any

import pytest

from scripts.benchmark.quality import (
    QualityReport,
    QualityScorer,
    RiskScoreMetrics,
    calculate_risk_score_mae,
    check_reasoning_quality,
    validate_json_response,
)


@pytest.fixture
def valid_ground_truth() -> dict[str, Any]:
    """Valid ground truth response for testing."""
    return {
        "risk_score": 25,
        "risk_level": "low",
        "summary": "Person detected at front door during business hours",
        "reasoning": "Low risk because detection occurred during normal hours with expected activity patterns.",
    }


@pytest.fixture
def valid_llm_response() -> dict[str, Any]:
    """Valid LLM response matching ground truth closely."""
    return {
        "risk_score": 27,
        "risk_level": "low",
        "summary": "Person seen at entrance during daytime",
        "reasoning": "Minimal risk due to daytime detection and normal behavior indicators.",
    }


@pytest.fixture
def quality_scorer() -> QualityScorer:
    """Initialize QualityScorer instance for testing."""
    return QualityScorer()


@pytest.fixture
def sample_dataset() -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Sample dataset with ground truth and LLM response pairs."""
    return [
        (
            {
                "risk_score": 25,
                "risk_level": "low",
                "summary": "Person at door",
                "reasoning": "Low risk during daytime",
            },
            {
                "risk_score": 27,
                "risk_level": "low",
                "summary": "Person detected",
                "reasoning": "Minimal risk",
            },
        ),
        (
            {
                "risk_score": 60,
                "risk_level": "high",
                "summary": "Suspicious activity",
                "reasoning": "High risk due to nighttime activity",
            },
            {
                "risk_score": 58,
                "risk_level": "high",
                "summary": "Suspicious behavior",
                "reasoning": "Elevated risk at night",
            },
        ),
        (
            {
                "risk_score": 85,
                "risk_level": "critical",
                "summary": "Break-in attempt",
                "reasoning": "Critical risk with forced entry attempt",
            },
            {
                "risk_score": 90,
                "risk_level": "critical",
                "summary": "Intrusion detected",
                "reasoning": "Severe threat detected",
            },
        ),
    ]


class TestRiskScoreAccuracy:
    """Test suite for risk score accuracy metrics."""

    def test_calculate_mae_exact_match(self):
        """Test MAE calculation when predictions exactly match ground truth."""
        ground_truth = [25, 50, 75]
        predictions = [25, 50, 75]
        mae = calculate_risk_score_mae(ground_truth, predictions)
        assert mae == 0.0, "MAE should be 0.0 for exact matches"

    def test_calculate_mae_basic(self):
        """Test basic MAE calculation with known values."""
        ground_truth = [25, 50, 75]
        predictions = [30, 45, 80]
        # MAE = (|25-30| + |50-45| + |75-80|) / 3 = (5 + 5 + 5) / 3 = 5.0
        mae = calculate_risk_score_mae(ground_truth, predictions)
        assert mae == 5.0, "MAE calculation incorrect"

    def test_calculate_mae_within_acceptable_threshold(self):
        """Test MAE within acceptable threshold (±5)."""
        ground_truth = [25, 50, 75]
        predictions = [27, 53, 78]
        mae = calculate_risk_score_mae(ground_truth, predictions)
        assert mae <= 5.0, "MAE should be within acceptable threshold"

    def test_calculate_mae_within_marginal_threshold(self):
        """Test MAE within marginal threshold (±10)."""
        ground_truth = [25, 50, 75]
        predictions = [32, 58, 85]
        mae = calculate_risk_score_mae(ground_truth, predictions)
        assert mae <= 10.0, "MAE should be within marginal threshold"

    def test_calculate_mae_exceeds_thresholds(self):
        """Test MAE exceeding both thresholds."""
        ground_truth = [25, 50, 75]
        predictions = [50, 80, 100]
        mae = calculate_risk_score_mae(ground_truth, predictions)
        assert mae > 10.0, "MAE should exceed marginal threshold"

    def test_calculate_mae_empty_lists(self):
        """Test MAE calculation with empty lists."""
        with pytest.raises(ValueError, match="Cannot calculate MAE.*empty"):
            calculate_risk_score_mae([], [])

    def test_calculate_mae_mismatched_lengths(self):
        """Test MAE calculation with mismatched list lengths."""
        ground_truth = [25, 50, 75]
        predictions = [30, 45]
        with pytest.raises(ValueError, match="Length mismatch"):
            calculate_risk_score_mae(ground_truth, predictions)

    def test_calculate_mae_out_of_range_scores(self):
        """Test MAE with out-of-range risk scores."""
        ground_truth = [25, 50, 75]
        predictions = [150, -10, 75]  # Invalid: >100 and <0
        with pytest.raises(ValueError, match="Risk scores must be between 0 and 100"):
            calculate_risk_score_mae(ground_truth, predictions)


class TestRiskLevelMatching:
    """Test suite for risk level classification accuracy."""

    def test_exact_risk_level_match(self, quality_scorer):
        """Test exact match rate when all classifications are correct."""
        ground_truth_levels = ["low", "high", "critical"]
        predicted_levels = ["low", "high", "critical"]
        match_rate = quality_scorer.calculate_risk_level_match_rate(
            ground_truth_levels, predicted_levels
        )
        assert match_rate == 1.0, "Match rate should be 100% for exact matches"

    def test_partial_risk_level_match(self, quality_scorer):
        """Test partial match rate."""
        ground_truth_levels = ["low", "high", "critical", "medium"]
        predicted_levels = ["low", "medium", "critical", "medium"]
        # 3 out of 4 correct
        match_rate = quality_scorer.calculate_risk_level_match_rate(
            ground_truth_levels, predicted_levels
        )
        assert match_rate == 0.75, "Match rate should be 75%"

    def test_no_risk_level_matches(self, quality_scorer):
        """Test zero match rate when all classifications are wrong."""
        ground_truth_levels = ["low", "medium", "high"]
        predicted_levels = ["critical", "high", "low"]
        match_rate = quality_scorer.calculate_risk_level_match_rate(
            ground_truth_levels, predicted_levels
        )
        assert match_rate == 0.0, "Match rate should be 0% for no matches"

    def test_risk_level_match_empty_lists(self, quality_scorer):
        """Test match rate calculation with empty lists."""
        with pytest.raises(ValueError, match="Cannot calculate.*empty"):
            quality_scorer.calculate_risk_level_match_rate([], [])

    def test_risk_level_match_mismatched_lengths(self, quality_scorer):
        """Test match rate with mismatched list lengths."""
        ground_truth_levels = ["low", "high", "critical"]
        predicted_levels = ["low", "high"]
        with pytest.raises(ValueError, match="Length mismatch"):
            quality_scorer.calculate_risk_level_match_rate(ground_truth_levels, predicted_levels)

    def test_invalid_risk_level_values(self, quality_scorer):
        """Test validation of risk level values."""
        ground_truth_levels = ["low", "high", "invalid"]
        predicted_levels = ["low", "high", "critical"]
        with pytest.raises(ValueError, match="Invalid risk level.*must be one of"):
            quality_scorer.calculate_risk_level_match_rate(ground_truth_levels, predicted_levels)


class TestJSONValidity:
    """Test suite for JSON response validation."""

    def test_valid_json_string(self):
        """Test validation of valid JSON string."""
        valid_json = (
            '{"risk_score": 25, "risk_level": "low", "summary": "test", "reasoning": "test"}'
        )
        is_valid, parsed_data = validate_json_response(valid_json)
        assert is_valid is True, "Should validate valid JSON"
        assert parsed_data["risk_score"] == 25
        assert parsed_data["risk_level"] == "low"

    def test_valid_json_dict(self):
        """Test validation of valid JSON dict."""
        valid_dict = {
            "risk_score": 25,
            "risk_level": "low",
            "summary": "test",
            "reasoning": "test",
        }
        is_valid, parsed_data = validate_json_response(valid_dict)
        assert is_valid is True, "Should validate valid dict"
        assert parsed_data == valid_dict

    def test_invalid_json_string(self):
        """Test handling of invalid JSON string."""
        invalid_json = '{"risk_score": 25, "risk_level": "low"'  # Missing closing brace
        is_valid, error_msg = validate_json_response(invalid_json)
        assert is_valid is False, "Should fail for invalid JSON"
        assert "parse error" in error_msg.lower()

    def test_json_missing_required_fields(self):
        """Test validation of JSON missing required fields."""
        incomplete_json = '{"risk_score": 25}'
        is_valid, error_msg = validate_json_response(incomplete_json)
        assert is_valid is False, "Should fail for missing required fields"
        assert "missing required field" in error_msg.lower()

    def test_json_invalid_field_types(self):
        """Test validation of JSON with invalid field types."""
        invalid_types = {
            "risk_score": "not a number",
            "risk_level": "low",
            "summary": "test",
            "reasoning": "test",
        }
        is_valid, error_msg = validate_json_response(invalid_types)
        assert is_valid is False, "Should fail for invalid field types"
        assert "invalid type" in error_msg.lower()

    def test_json_out_of_range_risk_score(self):
        """Test validation of risk score out of range."""
        out_of_range = {
            "risk_score": 150,
            "risk_level": "low",
            "summary": "test",
            "reasoning": "test",
        }
        is_valid, error_msg = validate_json_response(out_of_range)
        assert is_valid is False, "Should fail for out-of-range risk score"
        assert "out of range" in error_msg.lower()

    def test_json_invalid_risk_level(self):
        """Test validation of invalid risk level."""
        invalid_level = {
            "risk_score": 25,
            "risk_level": "invalid",
            "summary": "test",
            "reasoning": "test",
        }
        is_valid, error_msg = validate_json_response(invalid_level)
        assert is_valid is False, "Should fail for invalid risk level"
        assert "invalid risk level" in error_msg.lower()

    def test_json_empty_string(self):
        """Test validation of empty string."""
        is_valid, error_msg = validate_json_response("")
        assert is_valid is False, "Should fail for empty string"
        assert "empty" in error_msg.lower()

    def test_json_none_value(self):
        """Test validation of None value."""
        is_valid, error_msg = validate_json_response(None)
        assert is_valid is False, "Should fail for None value"
        assert "none" in error_msg.lower() or "empty" in error_msg.lower()


class TestReasoningQuality:
    """Test suite for reasoning quality checks."""

    def test_valid_reasoning_present(self):
        """Test detection of valid reasoning."""
        response = {
            "risk_score": 25,
            "risk_level": "low",
            "summary": "Person at door",
            "reasoning": "Low risk because detection occurred during normal business hours with expected activity patterns.",
        }
        is_valid, score = check_reasoning_quality(response)
        assert is_valid is True, "Should validate present reasoning"
        assert score > 0.5, "Quality score should be high for valid reasoning"

    def test_reasoning_missing(self):
        """Test detection of missing reasoning field."""
        response = {
            "risk_score": 25,
            "risk_level": "low",
            "summary": "Person at door",
        }
        is_valid, score = check_reasoning_quality(response)
        assert is_valid is False, "Should fail when reasoning is missing"
        assert score == 0.0, "Quality score should be 0 for missing reasoning"

    def test_reasoning_empty_string(self):
        """Test detection of empty reasoning string."""
        response = {
            "risk_score": 25,
            "risk_level": "low",
            "summary": "Person at door",
            "reasoning": "",
        }
        is_valid, score = check_reasoning_quality(response)
        assert is_valid is False, "Should fail for empty reasoning"
        assert score == 0.0, "Quality score should be 0 for empty reasoning"

    def test_reasoning_too_short(self):
        """Test detection of too-short reasoning."""
        response = {
            "risk_score": 25,
            "risk_level": "low",
            "summary": "Person at door",
            "reasoning": "Low risk",  # Too short to be meaningful
        }
        is_valid, score = check_reasoning_quality(response)
        assert is_valid is False, "Should fail for too-short reasoning"
        assert score < 0.5, "Quality score should be low for insufficient reasoning"

    def test_reasoning_coherence_check(self):
        """Test coherence checking of reasoning."""
        # Good coherence - mentions key factors
        good_response = {
            "risk_score": 75,
            "risk_level": "high",
            "summary": "Suspicious activity",
            "reasoning": "High risk detected due to nighttime activity, unusual movement patterns, and proximity to entry points.",
        }
        is_valid, score = check_reasoning_quality(good_response)
        assert is_valid is True, "Should validate coherent reasoning"
        assert score > 0.7, "Quality score should be high for coherent reasoning"

        # Poor coherence - generic/vague
        poor_response = {
            "risk_score": 75,
            "risk_level": "high",
            "summary": "Suspicious activity",
            "reasoning": "Something seems wrong and bad things might happen maybe.",
        }
        is_valid, score = check_reasoning_quality(poor_response)
        assert score < 0.5, "Quality score should be lower for vague reasoning"

    def test_reasoning_consistency_with_risk_level(self):
        """Test consistency between reasoning and risk level."""
        # Inconsistent: low risk but critical reasoning
        inconsistent_response = {
            "risk_score": 10,
            "risk_level": "low",
            "summary": "Person at door",
            "reasoning": "Critical security breach detected with forced entry attempt and multiple suspects.",
        }
        is_valid, score = check_reasoning_quality(inconsistent_response)
        assert score < 0.6, "Quality score should be reduced for inconsistent reasoning"


class TestQualityScorer:
    """Test suite for QualityScorer class integration."""

    def test_score_single_response(self, quality_scorer, valid_ground_truth, valid_llm_response):
        """Test scoring a single response."""
        metrics = quality_scorer.score_response(valid_ground_truth, valid_llm_response)

        assert isinstance(metrics, RiskScoreMetrics)
        assert metrics.mae <= 5.0, "MAE should be within acceptable range"
        assert metrics.risk_level_match is True, "Risk levels should match"
        assert metrics.json_valid is True, "JSON should be valid"
        assert metrics.reasoning_score > 0.5, "Reasoning should be acceptable"

    def test_score_multiple_responses(self, quality_scorer, sample_dataset):
        """Test scoring multiple responses and aggregation."""
        report = quality_scorer.score_dataset(sample_dataset)

        assert isinstance(report, QualityReport)
        assert 0.0 <= report.overall_quality <= 1.0, "Overall quality should be 0-1"
        assert report.total_samples == 3, "Should process all samples"
        assert report.json_validity_rate >= 0.0, "Should track JSON validity rate"
        assert report.risk_level_accuracy >= 0.0, "Should track risk level accuracy"

    def test_quality_report_perfect_score(self, quality_scorer):
        """Test quality report with perfect scores."""
        perfect_dataset = [
            (
                {
                    "risk_score": 25,
                    "risk_level": "low",
                    "summary": "test",
                    "reasoning": "Detailed reasoning here",
                },
                {
                    "risk_score": 25,
                    "risk_level": "low",
                    "summary": "test",
                    "reasoning": "Detailed reasoning here",
                },
            )
        ]
        report = quality_scorer.score_dataset(perfect_dataset)

        assert report.overall_quality == 1.0, "Perfect dataset should score 1.0"
        assert report.average_mae == 0.0, "MAE should be 0 for identical scores"
        assert report.risk_level_accuracy == 1.0, "Risk level accuracy should be 100%"

    def test_quality_report_zero_score(self, quality_scorer):
        """Test quality report with worst possible scores."""
        worst_dataset = [
            (
                {
                    "risk_score": 0,
                    "risk_level": "low",
                    "summary": "test",
                    "reasoning": "Detailed reasoning",
                },
                {
                    "risk_score": 100,
                    "risk_level": "critical",
                    "summary": "test",
                    "reasoning": "",  # Empty reasoning
                },
            )
        ]
        report = quality_scorer.score_dataset(worst_dataset)

        assert report.overall_quality < 0.3, "Worst dataset should score very low"
        assert report.average_mae > 50.0, "MAE should be very high"
        assert report.risk_level_accuracy == 0.0, "Risk level accuracy should be 0%"

    def test_quality_scorer_with_invalid_json(self, quality_scorer):
        """Test scorer handling of invalid JSON responses."""
        invalid_dataset = [
            (
                {
                    "risk_score": 25,
                    "risk_level": "low",
                    "summary": "test",
                    "reasoning": "test",
                },
                '{"invalid": "json"',  # Invalid JSON string
            )
        ]
        report = quality_scorer.score_dataset(invalid_dataset)

        assert report.json_validity_rate == 0.0, "Should detect invalid JSON"
        assert report.overall_quality < 0.5, "Overall quality should be poor"

    def test_quality_scorer_empty_dataset(self, quality_scorer):
        """Test scorer with empty dataset."""
        with pytest.raises(ValueError, match="Cannot score empty dataset"):
            quality_scorer.score_dataset([])

    def test_quality_report_metrics_tracking(self, quality_scorer, sample_dataset):
        """Test that all metrics are properly tracked in the report."""
        report = quality_scorer.score_dataset(sample_dataset)

        # Verify all expected fields are present
        assert hasattr(report, "overall_quality")
        assert hasattr(report, "average_mae")
        assert hasattr(report, "mae_acceptable_rate")  # % within ±5
        assert hasattr(report, "mae_marginal_rate")  # % within ±10
        assert hasattr(report, "risk_level_accuracy")
        assert hasattr(report, "json_validity_rate")
        assert hasattr(report, "average_reasoning_score")
        assert hasattr(report, "total_samples")

    def test_quality_scorer_threshold_categorization(self, quality_scorer):
        """Test MAE threshold categorization (acceptable vs marginal)."""
        test_dataset = [
            # Within acceptable (±5)
            (
                {"risk_score": 25, "risk_level": "low", "summary": "test", "reasoning": "test"},
                {"risk_score": 27, "risk_level": "low", "summary": "test", "reasoning": "test"},
            ),
            # Within marginal (±10)
            (
                {"risk_score": 50, "risk_level": "medium", "summary": "test", "reasoning": "test"},
                {"risk_score": 58, "risk_level": "medium", "summary": "test", "reasoning": "test"},
            ),
            # Exceeds thresholds
            (
                {"risk_score": 25, "risk_level": "low", "summary": "test", "reasoning": "test"},
                {"risk_score": 50, "risk_level": "medium", "summary": "test", "reasoning": "test"},
            ),
        ]

        report = quality_scorer.score_dataset(test_dataset)

        # 1 out of 3 within acceptable
        assert report.mae_acceptable_rate == pytest.approx(1 / 3, 0.01)
        # 2 out of 3 within marginal
        assert report.mae_marginal_rate == pytest.approx(2 / 3, 0.01)


class TestEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_risk_score_boundary_values(self):
        """Test risk scores at boundary values (0 and 100)."""
        ground_truth = [0, 100]
        predictions = [0, 100]
        mae = calculate_risk_score_mae(ground_truth, predictions)
        assert mae == 0.0, "Should handle boundary values correctly"

    def test_risk_score_float_values(self):
        """Test risk scores with float values."""
        ground_truth = [25.5, 50.7, 75.2]
        predictions = [25.3, 50.9, 75.0]
        mae = calculate_risk_score_mae(ground_truth, predictions)
        assert mae < 1.0, "Should handle float values correctly"

    def test_large_dataset_performance(self, quality_scorer):
        """Test scorer performance with large dataset."""
        large_dataset = [
            (
                {
                    "risk_score": i % 100,
                    "risk_level": "low",
                    "summary": "test",
                    "reasoning": "test",
                },
                {
                    "risk_score": (i + 2) % 100,
                    "risk_level": "low",
                    "summary": "test",
                    "reasoning": "test",
                },
            )
            for i in range(1000)
        ]

        report = quality_scorer.score_dataset(large_dataset)
        assert report.total_samples == 1000, "Should process all samples"
        assert 0.0 <= report.overall_quality <= 1.0, "Should compute valid quality score"

    def test_unicode_in_reasoning(self):
        """Test handling of unicode characters in reasoning."""
        response = {
            "risk_score": 25,
            "risk_level": "low",
            "summary": "Test with émojis 🎯",
            "reasoning": "Détection avec caractères spéciaux: ñ, ü, 中文",
        }
        is_valid, score = check_reasoning_quality(response)
        assert is_valid is True, "Should handle unicode characters"
        assert score > 0.0, "Should score unicode text"

    def test_very_long_reasoning(self):
        """Test handling of very long reasoning text."""
        response = {
            "risk_score": 25,
            "risk_level": "low",
            "summary": "Test",
            "reasoning": " ".join(["This is a very detailed reasoning."] * 100),
        }
        is_valid, score = check_reasoning_quality(response)
        assert is_valid is True, "Should handle long reasoning text"
        assert score > 0.0, "Should score long text"
