"""Unit tests for backend.evaluation.reports module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas", reason="pandas required for evaluation tests")

from backend.evaluation.reports import (  # noqa: E402
    _escape_html,
    generate_html_report,
    generate_json_report,
    generate_summary_table,
    save_report,
)


class TestEscapeHtml:
    """Tests for _escape_html helper function."""

    def test_escapes_ampersand(self) -> None:
        """Should escape ampersand."""
        assert _escape_html("A & B") == "A &amp; B"

    def test_escapes_less_than(self) -> None:
        """Should escape less-than sign."""
        assert _escape_html("A < B") == "A &lt; B"

    def test_escapes_greater_than(self) -> None:
        """Should escape greater-than sign."""
        assert _escape_html("A > B") == "A &gt; B"

    def test_escapes_quotes(self) -> None:
        """Should escape quotes."""
        assert _escape_html('A "quoted" B') == "A &quot;quoted&quot; B"
        assert _escape_html("A 'quoted' B") == "A &#x27;quoted&#x27; B"

    def test_multiple_escapes(self) -> None:
        """Should handle multiple special characters."""
        assert _escape_html("<script>alert('xss')</script>") == (
            "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"
        )


class TestGenerateJsonReport:
    """Tests for generate_json_report function."""

    @pytest.fixture
    def sample_results(self) -> pd.DataFrame:
        """Create sample results DataFrame."""
        return pd.DataFrame(
            {
                "scenario_id": ["s1", "s2", "s3", "s4"],
                "template_name": ["basic", "basic", "enriched", "enriched"],
                "scenario_type": ["normal", "threat", "normal", "threat"],
                "enrichment_level": ["none", "none", "basic", "basic"],
                "risk_score": [20, 75, 15, 80],
                "risk_level": ["low", "high", "low", "high"],
                "reasoning": ["Normal", "Threat", "Normal", "Threat"],
                "summary": ["OK", "Alert", "OK", "Alert"],
                "ground_truth_min": [0, 70, 0, 70],
                "ground_truth_max": [25, 100, 25, 100],
                "risk_deviation": [0.0, 0.0, 0.0, 0.0],
                "key_point_coverage": [0.8, 0.9, 0.85, 0.95],
                "reasoning_similarity": [0.7, 0.8, 0.75, 0.85],
                "latency_ms": [100, 150, 120, 140],
                "success": [True, True, True, True],
                "error_message": ["", "", "", ""],
            }
        )

    @pytest.fixture
    def sample_metrics(self) -> dict:
        """Create sample metrics."""
        return {
            "overall": {
                "total_scenarios": 4,
                "mean_risk_deviation": 0.0,
                "std_risk_deviation": 0.0,
                "mean_key_point_coverage": 0.875,
                "std_key_point_coverage": 0.06,
                "mean_reasoning_similarity": 0.775,
                "std_reasoning_similarity": 0.06,
                "within_range_pct": 100.0,
            },
            "by_template": {
                "basic": {
                    "count": 2,
                    "mean_risk_deviation": 0.0,
                    "std_risk_deviation": 0.0,
                    "mean_key_point_coverage": 0.85,
                    "mean_reasoning_similarity": 0.75,
                    "within_range_pct": 100.0,
                },
                "enriched": {
                    "count": 2,
                    "mean_risk_deviation": 0.0,
                    "std_risk_deviation": 0.0,
                    "mean_key_point_coverage": 0.9,
                    "mean_reasoning_similarity": 0.8,
                    "within_range_pct": 100.0,
                },
            },
            "by_scenario_type": {
                "normal": {
                    "count": 2,
                    "mean_risk_deviation": 0.0,
                    "std_risk_deviation": 0.0,
                    "mean_key_point_coverage": 0.825,
                    "mean_reasoning_similarity": 0.725,
                    "within_range_pct": 100.0,
                },
                "threat": {
                    "count": 2,
                    "mean_risk_deviation": 0.0,
                    "std_risk_deviation": 0.0,
                    "mean_key_point_coverage": 0.925,
                    "mean_reasoning_similarity": 0.825,
                    "within_range_pct": 100.0,
                },
            },
            "by_enrichment_level": {},
            "percentiles": {
                "risk_deviation": {"p50": 0.0, "p90": 0.0, "p99": 0.0, "min": 0.0, "max": 0.0},
            },
        }

    def test_generates_valid_structure(
        self, sample_results: pd.DataFrame, sample_metrics: dict
    ) -> None:
        """Report should have all required sections."""
        report = generate_json_report(sample_results, sample_metrics)

        assert "metadata" in report
        assert "summary" in report
        assert "template_rankings" in report
        assert "detailed_metrics" in report
        assert "failure_cases" in report

    def test_metadata_includes_timestamp(
        self, sample_results: pd.DataFrame, sample_metrics: dict
    ) -> None:
        """Metadata should include generation timestamp."""
        report = generate_json_report(sample_results, sample_metrics)

        assert "generated_at" in report["metadata"]
        assert "report_version" in report["metadata"]
        assert report["metadata"]["total_evaluations"] == 4

    def test_summary_includes_key_metrics(
        self, sample_results: pd.DataFrame, sample_metrics: dict
    ) -> None:
        """Summary should include key metrics."""
        report = generate_json_report(sample_results, sample_metrics)
        summary = report["summary"]

        assert "overall_metrics" in summary
        assert "best_template" in summary
        assert "failure_count" in summary
        assert "success_rate" in summary

    def test_template_rankings_sorted(
        self, sample_results: pd.DataFrame, sample_metrics: dict
    ) -> None:
        """Template rankings should be sorted by composite score."""
        report = generate_json_report(sample_results, sample_metrics)
        rankings = report["template_rankings"]

        # Should have 2 templates
        assert len(rankings) == 2

        # Should be sorted by rank
        assert rankings[0]["rank"] == 1
        assert rankings[1]["rank"] == 2

        # Higher composite score should be ranked first
        assert rankings[0]["composite_score"] >= rankings[1]["composite_score"]

    def test_failure_cases_captured(
        self, sample_results: pd.DataFrame, sample_metrics: dict
    ) -> None:
        """Failure cases should be captured when deviation > 0."""
        # Add a failure case
        sample_results.loc[0, "risk_deviation"] = 10.0
        report = generate_json_report(sample_results, sample_metrics)

        assert len(report["failure_cases"]) >= 1
        assert report["failure_cases"][0]["risk_deviation"] == 10.0

    def test_is_json_serializable(self, sample_results: pd.DataFrame, sample_metrics: dict) -> None:
        """Report should be JSON serializable."""
        report = generate_json_report(sample_results, sample_metrics)

        # Should not raise
        json_str = json.dumps(report, default=str)
        assert len(json_str) > 0


class TestGenerateHtmlReport:
    """Tests for generate_html_report function."""

    @pytest.fixture
    def sample_results(self) -> pd.DataFrame:
        """Create sample results DataFrame."""
        return pd.DataFrame(
            {
                "scenario_id": ["s1", "s2"],
                "template_name": ["basic", "enriched"],
                "scenario_type": ["normal", "threat"],
                "enrichment_level": ["none", "basic"],
                "risk_score": [20, 75],
                "risk_level": ["low", "high"],
                "reasoning": ["Normal", "Threat"],
                "summary": ["OK", "Alert"],
                "ground_truth_min": [0, 70],
                "ground_truth_max": [25, 100],
                "risk_deviation": [0.0, 5.0],
                "key_point_coverage": [0.8, 0.9],
                "reasoning_similarity": [0.7, 0.8],
                "latency_ms": [100, 150],
                "success": [True, True],
                "error_message": ["", ""],
            }
        )

    @pytest.fixture
    def sample_metrics(self) -> dict:
        """Create sample metrics."""
        return {
            "overall": {
                "total_scenarios": 2,
                "mean_risk_deviation": 2.5,
                "std_risk_deviation": 2.5,
                "mean_key_point_coverage": 0.85,
                "std_key_point_coverage": 0.05,
                "mean_reasoning_similarity": 0.75,
                "std_reasoning_similarity": 0.05,
                "within_range_pct": 50.0,
            },
            "by_template": {
                "basic": {
                    "count": 1,
                    "mean_risk_deviation": 0.0,
                    "std_risk_deviation": 0.0,
                    "mean_key_point_coverage": 0.8,
                    "mean_reasoning_similarity": 0.7,
                    "within_range_pct": 100.0,
                },
                "enriched": {
                    "count": 1,
                    "mean_risk_deviation": 5.0,
                    "std_risk_deviation": 0.0,
                    "mean_key_point_coverage": 0.9,
                    "mean_reasoning_similarity": 0.8,
                    "within_range_pct": 0.0,
                },
            },
            "by_scenario_type": {
                "normal": {
                    "count": 1,
                    "mean_risk_deviation": 0.0,
                    "std_risk_deviation": 0.0,
                    "mean_key_point_coverage": 0.8,
                    "mean_reasoning_similarity": 0.7,
                    "within_range_pct": 100.0,
                },
                "threat": {
                    "count": 1,
                    "mean_risk_deviation": 5.0,
                    "std_risk_deviation": 0.0,
                    "mean_key_point_coverage": 0.9,
                    "mean_reasoning_similarity": 0.8,
                    "within_range_pct": 0.0,
                },
            },
            "by_enrichment_level": {},
            "percentiles": {},
        }

    def test_generates_valid_html(self, sample_results: pd.DataFrame, sample_metrics: dict) -> None:
        """Should generate valid HTML structure."""
        html = generate_html_report(sample_results, sample_metrics)

        assert html.startswith("<!DOCTYPE html>")
        assert "<html" in html
        assert "</html>" in html
        assert "<head>" in html
        assert "<body>" in html

    def test_includes_title(self, sample_results: pd.DataFrame, sample_metrics: dict) -> None:
        """Should include report title."""
        html = generate_html_report(sample_results, sample_metrics)
        assert "<title>Prompt Evaluation Report</title>" in html

    def test_includes_summary_metrics(
        self, sample_results: pd.DataFrame, sample_metrics: dict
    ) -> None:
        """Should include summary metrics."""
        html = generate_html_report(sample_results, sample_metrics)
        assert "Total Evaluations" in html or "total" in html.lower()
        assert "Mean Risk Deviation" in html or "deviation" in html.lower()

    def test_includes_template_rankings(
        self, sample_results: pd.DataFrame, sample_metrics: dict
    ) -> None:
        """Should include template rankings table."""
        html = generate_html_report(sample_results, sample_metrics)
        assert "Template Rankings" in html
        assert "basic" in html
        assert "enriched" in html

    def test_includes_scenario_type_breakdown(
        self, sample_results: pd.DataFrame, sample_metrics: dict
    ) -> None:
        """Should include scenario type breakdown."""
        html = generate_html_report(sample_results, sample_metrics)
        assert "Scenario Type" in html or "scenario" in html.lower()

    def test_escapes_html_in_content(
        self, sample_results: pd.DataFrame, sample_metrics: dict
    ) -> None:
        """Should escape HTML special characters in content."""
        # Add a scenario with special characters
        sample_results.loc[0, "reasoning"] = "<script>alert('xss')</script>"
        html = generate_html_report(sample_results, sample_metrics)

        # Should not contain raw script tag
        assert "<script>alert" not in html


class TestSaveReport:
    """Tests for save_report function."""

    def test_save_json_report(self) -> None:
        """Should save JSON report to file."""
        report = {"test": "data", "value": 123}

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"
            save_report(report, path, "json")

            assert path.exists()
            # nosemgrep: path-traversal-open - path is known-safe temp directory in test
            with path.open() as f:
                loaded = json.load(f)
            assert loaded == report

    def test_save_html_report(self) -> None:
        """Should save HTML report to file."""
        html = "<html><body>Test</body></html>"

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.html"
            save_report(html, path, "html")

            assert path.exists()
            # nosemgrep: path-traversal-open - path is known-safe temp directory in test
            with path.open() as f:
                loaded = f.read()
            assert loaded == html

    def test_creates_parent_directories(self) -> None:
        """Should create parent directories if they don't exist."""
        report = {"test": "data"}

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "dir" / "report.json"
            save_report(report, path, "json")

            assert path.exists()

    def test_invalid_format_raises(self) -> None:
        """Should raise ValueError for invalid format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.txt"
            with pytest.raises(ValueError, match="Unknown format"):
                save_report({"test": "data"}, path, "invalid")


class TestGenerateSummaryTable:
    """Tests for generate_summary_table function."""

    def test_generates_text_table(self) -> None:
        """Should generate readable text table."""
        metrics = {
            "overall": {
                "total_scenarios": 100,
                "mean_risk_deviation": 5.5,
                "std_risk_deviation": 2.3,
                "mean_key_point_coverage": 0.85,
                "mean_reasoning_similarity": 0.78,
                "within_range_pct": 90.0,
            },
            "by_template": {
                "basic": {
                    "count": 50,
                    "mean_risk_deviation": 6.0,
                    "std_risk_deviation": 2.5,
                    "mean_key_point_coverage": 0.8,
                    "mean_reasoning_similarity": 0.75,
                    "within_range_pct": 88.0,
                },
                "enriched": {
                    "count": 50,
                    "mean_risk_deviation": 5.0,
                    "std_risk_deviation": 2.0,
                    "mean_key_point_coverage": 0.9,
                    "mean_reasoning_similarity": 0.81,
                    "within_range_pct": 92.0,
                },
            },
            "by_scenario_type": {},
            "by_enrichment_level": {},
            "percentiles": {},
        }

        table = generate_summary_table(metrics)

        assert "PROMPT EVALUATION SUMMARY" in table
        assert "TEMPLATE RANKINGS" in table
        assert "OVERALL METRICS" in table
        assert "Total Evaluations" in table
        assert "100" in table  # total_scenarios
