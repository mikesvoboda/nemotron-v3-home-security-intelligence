# ABOUTME: Generates JSON test reports for synthetic data A/B testing.
# ABOUTME: Creates reports with summary stats, per-model results, and failure details.
"""
Report generator for synthetic data A/B testing.

Generates structured JSON reports containing:
- Summary statistics (total samples, pass/fail counts, pass rate)
- Per-model accuracy metrics
- Detailed failure information with expected vs actual comparisons
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass
class SampleModelResult:
    """Result of comparing expected vs actual model output for a single sample.

    This represents the test result for ONE model on ONE media sample. It is used
    by the ReportGenerator to aggregate results across all models and samples.

    Note: This is different from comparison_engine.ComparisonResult, which represents
    the result of comparing ALL expected fields for a single comparison operation.

    Attributes:
        sample_id: Identifier for the media sample (e.g., "001.mp4")
        model_name: Name of the model being tested (e.g., "rt_detrv2")
        passed: Whether the comparison passed all assertions
        expected: Expected output values from ground truth
        actual: Actual output values from model
        diff: Dictionary of fields that differed (only populated on failure)
        inference_time_ms: Time taken for model inference in milliseconds
    """

    sample_id: str
    model_name: str
    passed: bool
    expected: dict[str, Any]
    actual: dict[str, Any]
    diff: dict[str, dict[str, Any]] = field(default_factory=dict)
    inference_time_ms: float | None = None


@dataclass
class ModelResult:
    """Aggregated test results for a single model.

    Attributes:
        model_name: Name of the model
        passed: Number of samples that passed
        failed: Number of samples that failed
        accuracy: Pass rate (passed / total)
    """

    model_name: str
    passed: int
    failed: int
    accuracy: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "passed": self.passed,
            "failed": self.failed,
            "accuracy": self.accuracy,
        }


@dataclass
class ReportSummary:
    """Summary statistics for a test run.

    Attributes:
        total_samples: Total number of media samples tested
        passed: Number of samples where all models passed
        failed: Number of samples with at least one model failure
        pass_rate: Overall pass rate (passed / total)
        models_tested: Number of distinct models tested
        avg_inference_time_ms: Average inference time across all tests
    """

    total_samples: int
    passed: int
    failed: int
    pass_rate: float
    models_tested: int
    avg_inference_time_ms: float | None


@dataclass
class FailureDetail:
    """Detailed information about a test failure.

    Attributes:
        sample: Sample identifier (e.g., "003.mp4")
        model: Model that failed
        expected: Expected output values
        actual: Actual output values
        diff: Dictionary showing field-by-field differences
    """

    sample: str
    model: str
    expected: dict[str, Any]
    actual: dict[str, Any]
    diff: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "sample": self.sample,
            "model": self.model,
            "expected": self.expected,
            "actual": self.actual,
            "diff": self.diff,
        }


@dataclass
class TestReport:
    """Complete test report for a synthetic data test run.

    Attributes:
        run_id: Unique identifier for the test run (e.g., "20260125_143022")
        scenario: Scenario that was tested (e.g., "loitering")
        generated_at: ISO timestamp when media was generated
        tested_at: ISO timestamp when tests were run
        summary: Summary statistics
        model_results: Per-model results keyed by model name
        failures: List of failure details
    """

    run_id: str
    scenario: str
    generated_at: str
    tested_at: str
    summary: ReportSummary
    model_results: dict[str, ModelResult]
    failures: list[FailureDetail]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "scenario": self.scenario,
            "generated_at": self.generated_at,
            "tested_at": self.tested_at,
            "summary": asdict(self.summary),
            "model_results": {
                name: result.to_dict() for name, result in self.model_results.items()
            },
            "failures": [f.to_dict() for f in self.failures],
        }


class ReportGenerator:
    """Generates JSON test reports for synthetic data A/B testing.

    This class aggregates comparison results from multiple models and samples,
    calculates summary statistics, and generates structured JSON reports.

    Example:
        generator = ReportGenerator()
        results = [SampleModelResult(...), SampleModelResult(...)]
        report = generator.create_report("20260125_143022", "loitering", results)
        generator.save_report(report, Path("data/synthetic/results/report.json"))
    """

    def __init__(self, results_dir: Path | None = None) -> None:
        """Initialize the report generator.

        Args:
            results_dir: Directory for saving reports. Defaults to
                data/synthetic/results/ relative to project root.
        """
        if results_dir is None:
            # Default to project's data/synthetic/results directory
            self.results_dir = Path(__file__).parents[2] / "data" / "synthetic" / "results"
        else:
            self.results_dir = results_dir

    def create_report(
        self,
        run_id: str,
        scenario: str,
        results: Sequence[SampleModelResult],
        generated_at: str | None = None,
    ) -> dict[str, Any]:
        """Create a complete test report from comparison results.

        Args:
            run_id: Unique identifier for the test run
            scenario: Name of the scenario being tested
            results: List of comparison results from all models/samples
            generated_at: ISO timestamp when media was generated (optional)

        Returns:
            Dictionary containing the complete report structure
        """
        tested_at = datetime.now(timezone.utc).isoformat()

        if generated_at is None:
            # Default to tested_at if not provided
            generated_at = tested_at

        summary = self.calculate_summary(results)
        model_results = self._aggregate_model_results(results)
        failures = self.format_failures(results)

        report = TestReport(
            run_id=run_id,
            scenario=scenario,
            generated_at=generated_at,
            tested_at=tested_at,
            summary=summary,
            model_results=model_results,
            failures=failures,
        )

        return report.to_dict()

    def calculate_summary(self, results: Sequence[SampleModelResult]) -> ReportSummary:
        """Calculate summary statistics from comparison results.

        Calculates total samples (unique sample IDs), passed/failed counts,
        pass rate, number of models tested, and average inference time.

        A sample is considered "passed" only if ALL models passed for that sample.

        Args:
            results: List of comparison results

        Returns:
            ReportSummary with aggregated statistics
        """
        if not results:
            return ReportSummary(
                total_samples=0,
                passed=0,
                failed=0,
                pass_rate=0.0,
                models_tested=0,
                avg_inference_time_ms=None,
            )

        # Group results by sample to determine sample-level pass/fail
        sample_results: dict[str, list[SampleModelResult]] = {}
        for result in results:
            if result.sample_id not in sample_results:
                sample_results[result.sample_id] = []
            sample_results[result.sample_id].append(result)

        # A sample passes only if all its model results pass
        total_samples = len(sample_results)
        passed_samples = sum(
            1
            for sample_results_list in sample_results.values()
            if all(r.passed for r in sample_results_list)
        )
        failed_samples = total_samples - passed_samples

        # Calculate pass rate
        pass_rate = passed_samples / total_samples if total_samples > 0 else 0.0

        # Count unique models
        models_tested = len({r.model_name for r in results})

        # Calculate average inference time
        inference_times = [
            r.inference_time_ms for r in results if r.inference_time_ms is not None
        ]
        avg_inference_time_ms = (
            sum(inference_times) / len(inference_times) if inference_times else None
        )

        return ReportSummary(
            total_samples=total_samples,
            passed=passed_samples,
            failed=failed_samples,
            pass_rate=round(pass_rate, 4),
            models_tested=models_tested,
            avg_inference_time_ms=(
                round(avg_inference_time_ms, 2) if avg_inference_time_ms else None
            ),
        )

    def format_failures(
        self, results: Sequence[SampleModelResult]
    ) -> list[FailureDetail]:
        """Extract and format failure details from results.

        Args:
            results: List of comparison results

        Returns:
            List of FailureDetail objects for failed comparisons
        """
        failures = []
        for result in results:
            if not result.passed:
                failure = FailureDetail(
                    sample=result.sample_id,
                    model=result.model_name,
                    expected=result.expected,
                    actual=result.actual,
                    diff=result.diff,
                )
                failures.append(failure)
        return failures

    def save_report(self, report: dict[str, Any], output_path: Path) -> bool:
        """Save a report to a JSON file.

        Creates parent directories if they don't exist.

        Args:
            report: Report dictionary to save
            output_path: Path to save the JSON file

        Returns:
            True if save was successful, False otherwise
        """
        try:
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with output_path.open("w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            return True
        except (OSError, TypeError, ValueError) as e:
            # Log error but don't raise - return False to indicate failure
            print(f"Error saving report to {output_path}: {e}")
            return False

    def save_report_for_run(
        self, report: dict[str, Any], run_id: str | None = None
    ) -> Path | None:
        """Save a report to the default results directory.

        Uses the run_id from the report or a provided override to generate
        the filename: {run_id}_report.json

        Args:
            report: Report dictionary to save
            run_id: Optional override for the run ID in filename

        Returns:
            Path to saved file if successful, None otherwise
        """
        report_run_id = run_id or report.get("run_id")
        if not report_run_id:
            print("Error: No run_id provided or found in report")
            return None

        output_path = self.results_dir / f"{report_run_id}_report.json"
        success = self.save_report(report, output_path)
        return output_path if success else None

    def _aggregate_model_results(
        self, results: Sequence[SampleModelResult]
    ) -> dict[str, ModelResult]:
        """Aggregate results by model name.

        Args:
            results: List of comparison results

        Returns:
            Dictionary mapping model names to ModelResult objects
        """
        # Group results by model
        model_groups: dict[str, list[SampleModelResult]] = {}
        for result in results:
            if result.model_name not in model_groups:
                model_groups[result.model_name] = []
            model_groups[result.model_name].append(result)

        # Calculate per-model statistics
        model_results = {}
        for model_name, model_result_list in model_groups.items():
            passed = sum(1 for r in model_result_list if r.passed)
            failed = len(model_result_list) - passed
            total = len(model_result_list)
            accuracy = passed / total if total > 0 else 0.0

            model_results[model_name] = ModelResult(
                model_name=model_name,
                passed=passed,
                failed=failed,
                accuracy=round(accuracy, 4),
            )

        return model_results
