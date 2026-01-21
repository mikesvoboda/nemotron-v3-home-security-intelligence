"""Unit tests for backend.evaluation.metrics module."""

from __future__ import annotations

import pytest

pd = pytest.importorskip("pandas", reason="pandas required for evaluation tests")

from backend.evaluation.metrics import (  # noqa: E402
    _tokenize,
    aggregate_metrics,
    calculate_key_point_coverage,
    calculate_reasoning_similarity,
    calculate_risk_deviation,
    rank_templates,
)


class TestCalculateRiskDeviation:
    """Tests for calculate_risk_deviation function."""

    def test_score_within_range_returns_zero(self) -> None:
        """Score within expected range should return 0."""
        assert calculate_risk_deviation(50, (40, 60)) == 0.0
        assert calculate_risk_deviation(40, (40, 60)) == 0.0  # At lower bound
        assert calculate_risk_deviation(60, (40, 60)) == 0.0  # At upper bound

    def test_score_below_range_returns_positive_deviation(self) -> None:
        """Score below range should return positive distance to min."""
        assert calculate_risk_deviation(30, (40, 60)) == 10.0
        assert calculate_risk_deviation(0, (40, 60)) == 40.0
        assert calculate_risk_deviation(39, (40, 60)) == 1.0

    def test_score_above_range_returns_positive_deviation(self) -> None:
        """Score above range should return positive distance to max."""
        assert calculate_risk_deviation(70, (40, 60)) == 10.0
        assert calculate_risk_deviation(100, (40, 60)) == 40.0
        assert calculate_risk_deviation(61, (40, 60)) == 1.0

    def test_edge_cases_with_zero_range(self) -> None:
        """Test with single-point range (min == max)."""
        assert calculate_risk_deviation(50, (50, 50)) == 0.0
        assert calculate_risk_deviation(49, (50, 50)) == 1.0
        assert calculate_risk_deviation(51, (50, 50)) == 1.0

    def test_typical_scenario_types(self) -> None:
        """Test with actual scenario type risk ranges."""
        # Normal: 0-25
        assert calculate_risk_deviation(15, (0, 25)) == 0.0
        assert calculate_risk_deviation(30, (0, 25)) == 5.0

        # Suspicious: 30-55
        assert calculate_risk_deviation(40, (30, 55)) == 0.0
        assert calculate_risk_deviation(20, (30, 55)) == 10.0

        # Threat: 70-100
        assert calculate_risk_deviation(85, (70, 100)) == 0.0
        assert calculate_risk_deviation(50, (70, 100)) == 20.0

        # Edge case: 20-60
        assert calculate_risk_deviation(40, (20, 60)) == 0.0


class TestTokenize:
    """Tests for _tokenize helper function."""

    def test_basic_tokenization(self) -> None:
        """Basic text should be tokenized into lowercase words."""
        tokens = _tokenize("Hello World")
        assert tokens == ["hello", "world"]

    def test_removes_punctuation(self) -> None:
        """Punctuation should be removed."""
        tokens = _tokenize("Hello, World! How are you?")
        assert tokens == ["hello", "world", "how", "are", "you"]

    def test_empty_string_returns_empty_list(self) -> None:
        """Empty string should return empty list."""
        assert _tokenize("") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        """Whitespace-only string should return empty list."""
        assert _tokenize("   ") == []


class TestCalculateReasoningSimilarity:
    """Tests for calculate_reasoning_similarity function."""

    def test_identical_strings_return_one(self) -> None:
        """Identical strings should have similarity of 1.0."""
        text = "unknown person at door"
        assert calculate_reasoning_similarity(text, text) == 1.0

    def test_empty_strings_return_zero(self) -> None:
        """Empty strings should return 0."""
        assert calculate_reasoning_similarity("", "some text") == 0.0
        assert calculate_reasoning_similarity("some text", "") == 0.0
        assert calculate_reasoning_similarity("", "") == 0.0

    def test_partial_overlap(self) -> None:
        """Strings with partial overlap should return appropriate similarity."""
        # "unknown person at door" vs "unknown person at front door"
        # Shared: unknown, person, at, door (4)
        # Union: unknown, person, at, door, front (5)
        # Jaccard = 4/5 = 0.8
        sim = calculate_reasoning_similarity(
            "unknown person at door", "unknown person at front door"
        )
        assert sim == pytest.approx(0.8)

    def test_no_overlap(self) -> None:
        """Completely different strings should return 0."""
        sim = calculate_reasoning_similarity("hello world", "goodbye universe")
        assert sim == 0.0

    def test_case_insensitive(self) -> None:
        """Similarity should be case-insensitive."""
        sim = calculate_reasoning_similarity("HELLO WORLD", "hello world")
        assert sim == 1.0


class TestCalculateKeyPointCoverage:
    """Tests for calculate_key_point_coverage function."""

    def test_all_key_points_covered(self) -> None:
        """All key points mentioned should return 1.0."""
        reasoning = "Unknown person detected at night near the front door"
        key_points = ["unknown person", "night", "front door"]
        assert calculate_key_point_coverage(reasoning, key_points) == 1.0

    def test_partial_coverage(self) -> None:
        """Partial coverage should return appropriate fraction."""
        reasoning = "Unknown person detected during the day"
        key_points = ["unknown person", "night", "entry point"]
        # Only "unknown person" is covered (1 of 3)
        assert calculate_key_point_coverage(reasoning, key_points) == pytest.approx(1 / 3)

    def test_no_coverage(self) -> None:
        """No key points mentioned should return 0."""
        reasoning = "Normal activity observed"
        key_points = ["unknown person", "night", "threat"]
        assert calculate_key_point_coverage(reasoning, key_points) == 0.0

    def test_empty_key_points_returns_one(self) -> None:
        """Empty key points list should return 1.0 (full coverage vacuously true)."""
        assert calculate_key_point_coverage("any reasoning", []) == 1.0

    def test_empty_reasoning_returns_zero(self) -> None:
        """Empty reasoning with non-empty key points should return 0."""
        assert calculate_key_point_coverage("", ["some point"]) == 0.0

    def test_case_insensitive(self) -> None:
        """Coverage check should be case-insensitive."""
        reasoning = "UNKNOWN PERSON at the DOOR"
        key_points = ["unknown person", "door"]
        assert calculate_key_point_coverage(reasoning, key_points) == 1.0


class TestAggregateMetrics:
    """Tests for aggregate_metrics function."""

    @pytest.fixture
    def sample_results(self) -> pd.DataFrame:
        """Create sample results DataFrame for testing."""
        return pd.DataFrame(
            {
                "template_name": [
                    "basic",
                    "basic",
                    "enriched",
                    "enriched",
                ],
                "scenario_type": [
                    "normal",
                    "threat",
                    "normal",
                    "threat",
                ],
                "enrichment_level": ["none", "none", "basic", "basic"],
                "risk_deviation": [0.0, 5.0, 0.0, 0.0],
                "key_point_coverage": [0.8, 0.6, 0.9, 0.85],
                "reasoning_similarity": [0.7, 0.5, 0.8, 0.75],
                "risk_score": [20, 75, 15, 80],
            }
        )

    def test_empty_dataframe_returns_zeros(self) -> None:
        """Empty DataFrame should return zeroed metrics."""
        metrics = aggregate_metrics(pd.DataFrame())
        assert metrics["overall"]["total_scenarios"] == 0
        assert metrics["overall"]["mean_risk_deviation"] == 0.0

    def test_overall_metrics_calculated(self, sample_results: pd.DataFrame) -> None:
        """Overall metrics should be correctly calculated."""
        metrics = aggregate_metrics(sample_results)
        overall = metrics["overall"]

        assert overall["total_scenarios"] == 4
        assert overall["mean_risk_deviation"] == pytest.approx(1.25)  # (0+5+0+0)/4
        assert overall["mean_key_point_coverage"] == pytest.approx(0.7875)
        assert overall["within_range_pct"] == pytest.approx(75.0)  # 3 of 4 have 0 deviation

    def test_by_template_metrics(self, sample_results: pd.DataFrame) -> None:
        """Per-template metrics should be correctly calculated."""
        metrics = aggregate_metrics(sample_results)
        by_template = metrics["by_template"]

        assert "basic" in by_template
        assert "enriched" in by_template
        assert by_template["basic"]["count"] == 2
        assert by_template["enriched"]["count"] == 2
        assert by_template["basic"]["mean_risk_deviation"] == pytest.approx(2.5)
        assert by_template["enriched"]["mean_risk_deviation"] == pytest.approx(0.0)

    def test_by_scenario_type_metrics(self, sample_results: pd.DataFrame) -> None:
        """Per-scenario-type metrics should be correctly calculated."""
        metrics = aggregate_metrics(sample_results)
        by_type = metrics["by_scenario_type"]

        assert "normal" in by_type
        assert "threat" in by_type
        assert by_type["normal"]["count"] == 2
        assert by_type["threat"]["count"] == 2

    def test_percentiles_calculated(self, sample_results: pd.DataFrame) -> None:
        """Percentiles should be calculated for key metrics."""
        metrics = aggregate_metrics(sample_results)
        percentiles = metrics["percentiles"]

        assert "risk_deviation" in percentiles
        assert "p50" in percentiles["risk_deviation"]
        assert "p90" in percentiles["risk_deviation"]
        assert "p99" in percentiles["risk_deviation"]


class TestRankTemplates:
    """Tests for rank_templates function."""

    def test_empty_metrics_returns_empty_list(self) -> None:
        """Empty by_template metrics should return empty list."""
        rankings = rank_templates({"by_template": {}})
        assert rankings == []

    def test_templates_ranked_by_composite_score(self) -> None:
        """Templates should be ranked by composite score (higher is better)."""
        metrics = {
            "by_template": {
                "template_a": {
                    "count": 10,
                    "mean_risk_deviation": 0.0,  # Perfect deviation (score: 1.0)
                    "mean_key_point_coverage": 1.0,  # Perfect coverage
                    "mean_reasoning_similarity": 1.0,  # Perfect similarity
                    "within_range_pct": 100.0,
                },
                "template_b": {
                    "count": 10,
                    "mean_risk_deviation": 50.0,  # Bad deviation (score: 0.5)
                    "mean_key_point_coverage": 0.5,
                    "mean_reasoning_similarity": 0.5,
                    "within_range_pct": 50.0,
                },
            }
        }
        rankings = rank_templates(metrics)

        assert len(rankings) == 2
        assert rankings[0]["template_name"] == "template_a"
        assert rankings[0]["rank"] == 1
        assert rankings[1]["template_name"] == "template_b"
        assert rankings[1]["rank"] == 2

    def test_ranking_includes_all_metrics(self) -> None:
        """Rankings should include all relevant metrics."""
        metrics = {
            "by_template": {
                "test_template": {
                    "count": 5,
                    "mean_risk_deviation": 10.0,
                    "mean_key_point_coverage": 0.8,
                    "mean_reasoning_similarity": 0.7,
                    "within_range_pct": 80.0,
                }
            }
        }
        rankings = rank_templates(metrics)

        assert len(rankings) == 1
        r = rankings[0]
        assert "rank" in r
        assert "template_name" in r
        assert "composite_score" in r
        assert "mean_risk_deviation" in r
        assert "mean_key_point_coverage" in r
        assert "mean_reasoning_similarity" in r
        assert "within_range_pct" in r
        assert "count" in r
