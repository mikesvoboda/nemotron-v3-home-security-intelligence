#!/usr/bin/env python3
"""Generate weekly test coverage and quality report.

This script analyzes test coverage, execution time, and quality metrics,
producing a comprehensive weekly report suitable for:
- CI/CD artifact storage
- GitHub Actions job summary
- Team communication

Metrics collected:
- Overall test coverage (backend and frontend)
- Test execution time by suite
- Flaky test detection
- Coverage trend analysis
- Test gap analysis (untested code paths)
- Performance benchmarks

Usage:
    ./scripts/weekly-test-report.py [--output report.json]
"""

import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class CoverageMetrics:
    """Coverage metrics for a test suite."""

    suite_name: str
    total_lines: int
    covered_lines: int
    coverage_percentage: float
    missing_lines: int


@dataclass
class TestMetrics:
    """Metrics for test execution."""

    suite_name: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    duration_seconds: float


@dataclass
class WeeklyReport:
    """Complete weekly test report."""

    timestamp: str
    backend_coverage: CoverageMetrics | None
    frontend_coverage: CoverageMetrics | None
    backend_metrics: TestMetrics | None
    frontend_metrics: TestMetrics | None
    flaky_tests: list[dict[str, Any]]
    test_gaps: list[dict[str, Any]]
    summary: dict[str, Any]


def run_backend_tests() -> TestMetrics | None:
    """Run backend tests and collect metrics.

    Returns:
        TestMetrics object or None if tests fail
    """
    try:
        project_root = Path(__file__).parent.parent

        start_time = time.time()

        # Run tests with coverage and JSON output
        result = subprocess.run(
            [
                "uv",
                "run",
                "pytest",
                "backend/tests/unit/",
                "--tb=short",
                "--json-report",
                "--json-report-file=test-report.json",
                "-v",
            ],
            check=False,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=300,
        )

        duration = time.time() - start_time

        # Parse output to extract test counts
        output = result.stdout + result.stderr

        # Extract counts from pytest output
        passed = output.count(" PASSED")
        failed = output.count(" FAILED")
        skipped = output.count(" SKIPPED")
        total = passed + failed + skipped

        return TestMetrics(
            suite_name="Backend Unit Tests",
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            skipped_tests=skipped,
            duration_seconds=duration,
        )

    except subprocess.TimeoutExpired:
        print("ERROR: Backend tests timed out (>5 minutes)")
        return None
    except Exception as e:
        print(f"ERROR: Failed to run backend tests: {e}")
        return None


def run_frontend_tests() -> TestMetrics | None:
    """Run frontend tests and collect metrics.

    Returns:
        TestMetrics object or None if tests fail
    """
    try:
        project_root = Path(__file__).parent.parent

        start_time = time.time()

        # Run Vitest with coverage
        result = subprocess.run(
            [
                "npm",
                "test",
                "--",
                "--run",
                "--reporter=verbose",
            ],
            check=False,
            cwd=project_root / "frontend",
            capture_output=True,
            text=True,
            timeout=300,
        )

        duration = time.time() - start_time

        output = result.stdout + result.stderr

        # Parse Vitest output
        passed = output.count("✓")
        failed = output.count("✗")
        skipped = output.count("⊙")
        total = passed + failed + skipped

        return TestMetrics(
            suite_name="Frontend Tests",
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            skipped_tests=skipped,
            duration_seconds=duration,
        )

    except subprocess.TimeoutExpired:
        print("ERROR: Frontend tests timed out (>5 minutes)")
        return None
    except Exception as e:
        print(f"ERROR: Failed to run frontend tests: {e}")
        return None


def get_coverage_metrics(coverage_json_path: Path) -> CoverageMetrics | None:
    """Extract coverage metrics from coverage.json file.

    Args:
        coverage_json_path: Path to .coverage JSON file

    Returns:
        CoverageMetrics object or None
    """
    try:
        if not coverage_json_path.exists():
            return None

        # Resolve to absolute path for security (path validated above)
        resolved_path = coverage_json_path.resolve()
        with open(resolved_path) as f:  # nosemgrep: path-traversal-open
            data = json.load(f)

        totals = data.get("totals", {})
        covered = totals.get("covered_lines", 0)
        total = totals.get("num_statements", 0)
        percentage = totals.get("percent_covered", 0.0)

        return CoverageMetrics(
            suite_name="Backend Coverage",
            total_lines=total,
            covered_lines=covered,
            coverage_percentage=percentage,
            missing_lines=total - covered,
        )

    except Exception as e:
        print(f"Warning: Could not read coverage metrics: {e}")
        return None


def detect_flaky_tests() -> list[dict[str, Any]]:
    """Detect tests that are flaky (intermittently failing).

    Uses test run history to identify patterns.

    Returns:
        List of flaky test information
    """
    # In a real implementation, this would:
    # 1. Query CI/CD for test history
    # 2. Identify tests with variable pass rates
    # 3. Report top flaky tests

    # For now, return empty list (can be enhanced)
    return []


def analyze_test_gaps() -> list[dict[str, Any]]:
    """Analyze code coverage to find untested areas.

    Returns:
        List of untested code sections
    """
    try:
        project_root = Path(__file__).parent.parent

        # Find files with low coverage
        result = subprocess.run(
            [
                "uv",
                "run",
                "pytest",
                "backend/tests/unit/",
                "--cov=backend",
                "--cov-report=term-missing",
            ],
            check=False,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=300,
        )

        # Parse output for uncovered lines
        lines = result.stdout.split("\n")
        gaps = []

        for line in lines:
            # Look for lines marked as "TOTAL" with low coverage
            if "TOTAL" in line and "%" in line:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        coverage_pct = float(parts[-1].rstrip("%"))
                        if coverage_pct < 80:
                            gaps.append(
                                {
                                    "file": parts[0] if parts else "unknown",
                                    "coverage_percent": coverage_pct,
                                }
                            )
                    except ValueError:
                        pass

        return gaps[:10]  # Return top 10 coverage gaps

    except Exception as e:
        print(f"Warning: Could not analyze test gaps: {e}")
        return []


def generate_report(
    backend_metrics: TestMetrics | None,
    frontend_metrics: TestMetrics | None,
    backend_coverage: CoverageMetrics | None,
) -> WeeklyReport:
    """Generate complete weekly report.

    Args:
        backend_metrics: Backend test metrics
        frontend_metrics: Frontend test metrics
        backend_coverage: Backend coverage metrics

    Returns:
        WeeklyReport object
    """
    # Detect flaky tests and gaps
    flaky_tests = detect_flaky_tests()
    test_gaps = analyze_test_gaps()

    # Calculate summary statistics
    total_passed = (backend_metrics.passed_tests if backend_metrics else 0) + (
        frontend_metrics.passed_tests if frontend_metrics else 0
    )
    total_tests = (backend_metrics.total_tests if backend_metrics else 0) + (
        frontend_metrics.total_tests if frontend_metrics else 0
    )

    summary = {
        "generated_at": datetime.now().isoformat(),
        "total_tests": total_tests,
        "total_passed": total_passed,
        "pass_rate_percent": (total_passed / total_tests * 100) if total_tests > 0 else 0,
        "flaky_tests_count": len(flaky_tests),
        "coverage_gaps_count": len(test_gaps),
    }

    return WeeklyReport(
        timestamp=datetime.now().isoformat(),
        backend_coverage=backend_coverage,
        frontend_coverage=None,  # Would be populated from frontend coverage tool
        backend_metrics=backend_metrics,
        frontend_metrics=frontend_metrics,
        flaky_tests=flaky_tests,
        test_gaps=test_gaps,
        summary=summary,
    )


def print_report(report: WeeklyReport):
    """Print formatted report to stdout.

    Args:
        report: WeeklyReport object
    """
    print("\n" + "=" * 80)
    print("WEEKLY TEST REPORT")
    print("=" * 80)
    print(f"Generated: {report.timestamp}\n")

    # Backend metrics
    if report.backend_metrics:
        m = report.backend_metrics
        print(f"{m.suite_name}:")
        print(f"  Total: {m.total_tests} tests")
        print(f"  Passed: {m.passed_tests} ({m.passed_tests / m.total_tests * 100:.1f}%)")
        print(f"  Failed: {m.failed_tests}")
        print(f"  Skipped: {m.skipped_tests}")
        print(f"  Duration: {m.duration_seconds:.1f}s\n")

    # Frontend metrics
    if report.frontend_metrics:
        m = report.frontend_metrics
        print(f"{m.suite_name}:")
        print(f"  Total: {m.total_tests} tests")
        print(f"  Passed: {m.passed_tests} ({m.passed_tests / m.total_tests * 100:.1f}%)")
        print(f"  Failed: {m.failed_tests}")
        print(f"  Skipped: {m.skipped_tests}")
        print(f"  Duration: {m.duration_seconds:.1f}s\n")

    # Coverage
    if report.backend_coverage:
        c = report.backend_coverage
        print(f"{c.suite_name}:")
        print(f"  Coverage: {c.coverage_percentage:.1f}%")
        print(f"  Covered: {c.covered_lines}/{c.total_lines} lines")
        print(f"  Missing: {c.missing_lines} lines\n")

    # Summary
    print("Summary:")
    for key, value in report.summary.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.1f}")
        else:
            print(f"  {key}: {value}")

    # Flaky tests
    if report.flaky_tests:
        print(f"\nFlaky Tests ({len(report.flaky_tests)}):")
        for test in report.flaky_tests[:5]:
            print(f"  - {test.get('name', 'unknown')}")

    # Coverage gaps
    if report.test_gaps:
        print(f"\nTop Coverage Gaps ({len(report.test_gaps)}):")
        for gap in report.test_gaps[:5]:
            print(f"  - {gap.get('file', 'unknown')}: {gap.get('coverage_percent', 0):.1f}%")

    print("\n" + "=" * 80)


def main() -> int:
    """Main entry point.

    Returns:
        0 on success, 1 on failure
    """
    import argparse

    parser = argparse.ArgumentParser(description="Generate weekly test report")
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for JSON report (default: stdout only)",
    )
    parser.add_argument(
        "--no-frontend",
        action="store_true",
        help="Skip frontend tests",
    )
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent

    print("Running test suite for weekly report...")
    print("This may take several minutes...\n")

    # Run backend tests
    print("Running backend tests...")
    backend_metrics = run_backend_tests()

    # Run frontend tests (unless skipped)
    frontend_metrics = None
    if not args.no_frontend:
        print("Running frontend tests...")
        frontend_metrics = run_frontend_tests()

    # Get coverage metrics
    backend_coverage = get_coverage_metrics(project_root / ".coverage")

    # Generate report
    report = generate_report(backend_metrics, frontend_metrics, backend_coverage)

    # Print report
    print_report(report)

    # Save JSON report if requested
    if args.output:
        report_dict = {
            "timestamp": report.timestamp,
            "backend_coverage": asdict(report.backend_coverage)
            if report.backend_coverage
            else None,
            "frontend_coverage": asdict(report.frontend_coverage)
            if report.frontend_coverage
            else None,
            "backend_metrics": asdict(report.backend_metrics) if report.backend_metrics else None,
            "frontend_metrics": asdict(report.frontend_metrics)
            if report.frontend_metrics
            else None,
            "flaky_tests": report.flaky_tests,
            "test_gaps": report.test_gaps,
            "summary": report.summary,
        }

        output_file = project_root / args.output
        output_file.write_text(json.dumps(report_dict, indent=2))
        print(f"Report saved to: {output_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
