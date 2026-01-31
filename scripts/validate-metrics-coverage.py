#!/usr/bin/env python3
"""Validate Prometheus metrics coverage after seeding (NEM-3986).

This script queries Prometheus for all hsi_* metrics and verifies each has
at least one non-zero value, reporting coverage percentage.

Usage:
    ./scripts/validate-metrics-coverage.py
    ./scripts/validate-metrics-coverage.py --url http://localhost:9090
    ./scripts/validate-metrics-coverage.py --threshold 80 --verbose
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import requests
from requests.exceptions import ConnectionError, RequestException, Timeout


@dataclass
class MetricStatus:
    """Status information for a single metric."""

    name: str
    has_data: bool
    sample_count: int = 0
    error: str | None = None


@dataclass
class CoverageReport:
    """Coverage report for all metrics."""

    total_metrics: int
    populated_metrics: int
    coverage_percentage: float
    metrics: list[MetricStatus]

    @property
    def unpopulated_metrics(self) -> list[MetricStatus]:
        """Get list of metrics without data."""
        return [m for m in self.metrics if not m.has_data]


def get_all_hsi_metrics(prometheus_url: str, timeout: int = 10) -> list[str]:
    """Query Prometheus for all hsi_* metrics.

    Args:
        prometheus_url: Base URL of Prometheus server
        timeout: Request timeout in seconds

    Returns:
        List of metric names starting with 'hsi_'

    Raises:
        ConnectionError: If Prometheus is not reachable
        RequestException: If the API request fails
    """
    url = f"{prometheus_url}/api/v1/label/__name__/values"
    # nosemgrep: ssrf-requests - prometheus_url is a controlled CLI argument for internal monitoring
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    data = response.json()
    if data.get("status") != "success":
        raise RequestException(f"Prometheus API error: {data.get('error', 'Unknown error')}")

    all_metrics = data.get("data", [])
    return sorted([m for m in all_metrics if m.startswith("hsi_")])


def check_metric_has_data(prometheus_url: str, metric_name: str, timeout: int = 10) -> MetricStatus:
    """Check if a metric has non-zero values.

    Args:
        prometheus_url: Base URL of Prometheus server
        metric_name: Name of the metric to check
        timeout: Request timeout in seconds

    Returns:
        MetricStatus with data availability information
    """
    url = f"{prometheus_url}/api/v1/query"
    params = {"query": metric_name}

    try:
        # nosemgrep: ssrf-requests - prometheus_url is a controlled CLI argument for internal monitoring
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()

        data = response.json()
        if data.get("status") != "success":
            return MetricStatus(
                name=metric_name,
                has_data=False,
                error=data.get("error", "Unknown error"),
            )

        results = data.get("data", {}).get("result", [])
        sample_count = len(results)

        # Check if any result has a non-zero value
        has_nonzero = False
        for result in results:
            value = result.get("value", [None, "0"])
            if len(value) >= 2:
                try:
                    numeric_value = float(value[1])
                    if numeric_value != 0:
                        has_nonzero = True
                        break
                except (ValueError, TypeError):
                    continue

        return MetricStatus(
            name=metric_name,
            has_data=has_nonzero,
            sample_count=sample_count,
        )
    except (RequestException, Timeout) as e:
        return MetricStatus(
            name=metric_name,
            has_data=False,
            error=str(e),
        )


def validate_metrics_coverage(
    prometheus_url: str,
    timeout: int = 10,
    verbose: bool = False,
) -> CoverageReport:
    """Validate coverage of all hsi_* metrics.

    Args:
        prometheus_url: Base URL of Prometheus server
        timeout: Request timeout in seconds
        verbose: Print progress during validation

    Returns:
        CoverageReport with coverage statistics
    """
    metrics = get_all_hsi_metrics(prometheus_url, timeout)

    if verbose:
        print(f"Found {len(metrics)} hsi_* metrics")

    statuses: list[MetricStatus] = []
    for i, metric in enumerate(metrics, 1):
        if verbose:
            print(f"  [{i}/{len(metrics)}] Checking {metric}...", end=" ", flush=True)

        status = check_metric_has_data(prometheus_url, metric, timeout)
        statuses.append(status)

        if verbose:
            status_str = "OK" if status.has_data else "EMPTY"
            if status.error:
                status_str = f"ERROR: {status.error}"
            print(status_str)

    populated = sum(1 for s in statuses if s.has_data)
    total = len(statuses)
    coverage = (populated / total * 100) if total > 0 else 0.0

    return CoverageReport(
        total_metrics=total,
        populated_metrics=populated,
        coverage_percentage=coverage,
        metrics=statuses,
    )


def print_report(report: CoverageReport, show_unpopulated: bool = True) -> None:
    """Print coverage report to stdout.

    Args:
        report: Coverage report to print
        show_unpopulated: Show list of unpopulated metrics
    """
    print("\n" + "=" * 60)
    print("METRICS COVERAGE REPORT")
    print("=" * 60)
    print(f"Total hsi_* metrics:    {report.total_metrics}")
    print(f"Populated metrics:      {report.populated_metrics}")
    print(f"Coverage:               {report.coverage_percentage:.1f}%")
    print("=" * 60)

    if show_unpopulated and report.unpopulated_metrics:
        print("\nUnpopulated metrics:")
        for metric in report.unpopulated_metrics:
            error_info = f" (error: {metric.error})" if metric.error else ""
            print(f"  - {metric.name}{error_info}")


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for coverage below threshold)
    """
    parser = argparse.ArgumentParser(
        description="Validate Prometheus metrics coverage for hsi_* metrics"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:9090",
        help="Prometheus server URL (default: http://localhost:9090)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=80.0,
        help="Minimum coverage percentage required (default: 80)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Request timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show progress during validation",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output report as JSON",
    )
    args = parser.parse_args()

    try:
        report = validate_metrics_coverage(
            prometheus_url=args.url,
            timeout=args.timeout,
            verbose=args.verbose,
        )
    except ConnectionError:
        print(f"ERROR: Cannot connect to Prometheus at {args.url}", file=sys.stderr)
        print("Make sure Prometheus is running and the URL is correct.", file=sys.stderr)
        return 1
    except RequestException as e:
        print(f"ERROR: Prometheus API error: {e}", file=sys.stderr)
        return 1

    if args.json:
        import json

        output = {
            "total_metrics": report.total_metrics,
            "populated_metrics": report.populated_metrics,
            "coverage_percentage": report.coverage_percentage,
            "threshold": args.threshold,
            "passed": report.coverage_percentage >= args.threshold,
            "unpopulated_metrics": [m.name for m in report.unpopulated_metrics],
        }
        print(json.dumps(output, indent=2))
    else:
        print_report(report)

    if report.coverage_percentage < args.threshold:
        print(
            f"\nWARNING: Coverage {report.coverage_percentage:.1f}% is below {args.threshold}% threshold"
        )
        return 1

    print(
        f"\nSUCCESS: Coverage {report.coverage_percentage:.1f}% meets {args.threshold}% threshold"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
