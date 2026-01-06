#!/usr/bin/env python3
"""Analyze test coverage reports and identify modules below threshold.

This script parses coverage XML reports (Cobertura format) and:
1. Generates per-module coverage breakdown
2. Identifies modules below the 85% threshold
3. Tracks coverage trends over time
4. Outputs actionable recommendations

Usage:
    python scripts/coverage-analysis.py coverage.xml
    python scripts/coverage-analysis.py coverage.xml --output coverage-report.json
    python scripts/coverage-analysis.py coverage.xml --trend-file coverage-trend.json
    python scripts/coverage-analysis.py --list-uncovered coverage.xml

Environment variables:
    COVERAGE_THRESHOLD: Minimum coverage percentage (default: 85.0)
    CRITICAL_THRESHOLD: Coverage for critical paths (default: 90.0)
    WARNING_THRESHOLD: Percentage below which to warn (default: 90.0)

Output:
    - Console report with per-module coverage breakdown
    - Optional JSON report for programmatic consumption
    - GitHub Actions job summary if GITHUB_STEP_SUMMARY is set
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import defusedxml.ElementTree as ET

if TYPE_CHECKING:
    from collections.abc import Sequence

# Critical paths that require higher coverage (90%+)
# These contain security-critical and core business logic
CRITICAL_PATHS = [
    "backend/api/routes",
    "backend/services",
    "backend/core/security",
    "backend/core/auth",
]

# Paths to ignore in coverage analysis (tests, examples, etc.)
IGNORED_PATHS = [
    "backend/tests",
    "backend/examples",
    "__pycache__",
    ".venv",
    "venv",
]


@dataclass
class ModuleCoverage:
    """Coverage data for a single module."""

    name: str
    filename: str
    line_rate: float
    branch_rate: float
    lines_covered: int
    lines_total: int
    branches_covered: int
    branches_total: int
    is_critical: bool = False
    uncovered_lines: list[int] = field(default_factory=list)

    @property
    def line_coverage_percent(self) -> float:
        """Return line coverage as a percentage."""
        return self.line_rate * 100

    @property
    def branch_coverage_percent(self) -> float:
        """Return branch coverage as a percentage."""
        return self.branch_rate * 100


@dataclass
class CoverageReport:
    """Complete coverage report with analysis."""

    timestamp: str
    total_line_rate: float
    total_branch_rate: float
    modules: list[ModuleCoverage]
    below_threshold: list[ModuleCoverage]
    critical_below_threshold: list[ModuleCoverage]
    warnings: list[ModuleCoverage]

    @property
    def total_line_percent(self) -> float:
        """Return total line coverage as percentage."""
        return self.total_line_rate * 100

    @property
    def total_branch_percent(self) -> float:
        """Return total branch coverage as percentage."""
        return self.total_branch_rate * 100


@dataclass
class CoverageTrend:
    """Historical coverage trend data."""

    timestamp: str
    commit_sha: str | None
    branch: str | None
    total_line_rate: float
    total_branch_rate: float
    modules_below_threshold: int
    critical_below_threshold: int


def get_config() -> dict:
    """Get configuration from environment variables."""
    return {
        "coverage_threshold": float(os.environ.get("COVERAGE_THRESHOLD", "85.0")),
        "critical_threshold": float(os.environ.get("CRITICAL_THRESHOLD", "90.0")),
        "warning_threshold": float(os.environ.get("WARNING_THRESHOLD", "90.0")),
    }


def is_ignored_path(filepath: str) -> bool:
    """Check if filepath should be ignored."""
    return any(ignored in filepath for ignored in IGNORED_PATHS)


def is_critical_path(filepath: str) -> bool:
    """Check if filepath is in critical paths requiring higher coverage."""
    return any(critical in filepath for critical in CRITICAL_PATHS)


def _parse_branch_coverage(condition_coverage: str) -> tuple[int, int]:
    """Parse Cobertura branch coverage string.

    Args:
        condition_coverage: String in format "X% (covered/total)"

    Returns:
        Tuple of (branches_covered, branches_total)
    """
    if not condition_coverage:
        return 0, 0

    # Cobertura format is "X% (covered/total)"
    parts = condition_coverage.split("(")
    if len(parts) <= 1:
        return 0, 0

    branch_info = parts[1].rstrip(")").split("/")
    if len(branch_info) != 2:
        return 0, 0

    return int(branch_info[0]), int(branch_info[1])


def _categorize_module(
    module: ModuleCoverage,
    config: dict,
    below_threshold: list[ModuleCoverage],
    critical_below_threshold: list[ModuleCoverage],
    warnings: list[ModuleCoverage],
) -> None:
    """Categorize a module by its coverage threshold status.

    Args:
        module: The module to categorize
        config: Configuration dict with thresholds
        below_threshold: List to append modules below standard threshold
        critical_below_threshold: List to append critical modules below threshold
        warnings: List to append modules with warnings
    """
    line_pct = module.line_coverage_percent
    threshold = config["critical_threshold"] if module.is_critical else config["coverage_threshold"]

    if line_pct < threshold:
        if module.is_critical:
            critical_below_threshold.append(module)
        else:
            below_threshold.append(module)
    elif line_pct < config["warning_threshold"]:
        warnings.append(module)


def parse_coverage_xml(filepath: Path) -> CoverageReport:
    """Parse a Cobertura coverage XML file.

    Args:
        filepath: Path to the coverage.xml file

    Returns:
        CoverageReport with parsed coverage data
    """
    config = get_config()

    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Error: Could not parse {filepath}: {e}", file=sys.stderr)
        sys.exit(1)

    # Get overall coverage from root attributes
    total_line_rate = float(root.get("line-rate", "0"))
    total_branch_rate = float(root.get("branch-rate", "0"))

    modules: list[ModuleCoverage] = []
    below_threshold: list[ModuleCoverage] = []
    critical_below_threshold: list[ModuleCoverage] = []
    warnings: list[ModuleCoverage] = []

    # Parse packages (modules)
    for package in root.findall(".//package"):
        package_name = package.get("name", "")

        # Skip ignored paths
        if is_ignored_path(package_name):
            continue

        pkg_line_rate = float(package.get("line-rate", "0"))
        pkg_branch_rate = float(package.get("branch-rate", "0"))

        # Calculate totals from classes within package
        lines_covered = 0
        lines_total = 0
        branches_covered = 0
        branches_total = 0
        uncovered_lines: list[int] = []
        filename = ""

        for cls in package.findall("classes/class"):
            if not filename:
                filename = cls.get("filename", package_name)

            for line in cls.findall("lines/line"):
                line_num = int(line.get("number", "0"))
                hits = int(line.get("hits", "0"))
                lines_total += 1
                if hits > 0:
                    lines_covered += 1
                else:
                    uncovered_lines.append(line_num)

                # Count branches if present
                if line.get("branch") == "true":
                    condition_coverage = line.get("condition-coverage", "")
                    bc, bt = _parse_branch_coverage(condition_coverage)
                    branches_covered += bc
                    branches_total += bt

        is_critical = is_critical_path(package_name)

        module = ModuleCoverage(
            name=package_name,
            filename=filename or package_name,
            line_rate=pkg_line_rate,
            branch_rate=pkg_branch_rate,
            lines_covered=lines_covered,
            lines_total=lines_total,
            branches_covered=branches_covered,
            branches_total=branches_total,
            is_critical=is_critical,
            uncovered_lines=sorted(uncovered_lines)[:20],  # Limit to first 20
        )
        modules.append(module)
        _categorize_module(module, config, below_threshold, critical_below_threshold, warnings)

    # Sort modules by coverage (lowest first for prioritization)
    modules.sort(key=lambda m: m.line_rate)
    below_threshold.sort(key=lambda m: m.line_rate)
    critical_below_threshold.sort(key=lambda m: m.line_rate)
    warnings.sort(key=lambda m: m.line_rate)

    return CoverageReport(
        timestamp=datetime.now(UTC).isoformat(),
        total_line_rate=total_line_rate,
        total_branch_rate=total_branch_rate,
        modules=modules,
        below_threshold=below_threshold,
        critical_below_threshold=critical_below_threshold,
        warnings=warnings,
    )


def load_trend_file(filepath: Path) -> list[CoverageTrend]:
    """Load historical coverage trend data."""
    if not filepath.exists():
        return []

    try:
        with filepath.open() as f:
            data = json.load(f)
            return [
                CoverageTrend(
                    timestamp=entry["timestamp"],
                    commit_sha=entry.get("commit_sha"),
                    branch=entry.get("branch"),
                    total_line_rate=entry["total_line_rate"],
                    total_branch_rate=entry["total_branch_rate"],
                    modules_below_threshold=entry["modules_below_threshold"],
                    critical_below_threshold=entry["critical_below_threshold"],
                )
                for entry in data
            ]
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Warning: Could not parse trend file {filepath}: {e}", file=sys.stderr)
        return []


def save_trend_file(
    filepath: Path, trends: Sequence[CoverageTrend], max_entries: int = 100
) -> None:
    """Save coverage trend data, keeping only recent entries."""
    # Keep only the most recent entries
    recent_trends = list(trends)[-max_entries:]

    with filepath.open("w") as f:
        json.dump([asdict(t) for t in recent_trends], f, indent=2)


def update_trend(
    trend_file: Path,
    report: CoverageReport,
    commit_sha: str | None = None,
    branch: str | None = None,
) -> list[CoverageTrend]:
    """Update trend file with current coverage data."""
    trends = load_trend_file(trend_file)

    # Get git info from environment if not provided
    if commit_sha is None:
        commit_sha = os.environ.get("GITHUB_SHA")
    if branch is None:
        branch = os.environ.get("GITHUB_REF_NAME")

    new_trend = CoverageTrend(
        timestamp=report.timestamp,
        commit_sha=commit_sha,
        branch=branch,
        total_line_rate=report.total_line_rate,
        total_branch_rate=report.total_branch_rate,
        modules_below_threshold=len(report.below_threshold),
        critical_below_threshold=len(report.critical_below_threshold),
    )

    trends.append(new_trend)
    save_trend_file(trend_file, trends)

    return trends


def analyze_trend(trends: Sequence[CoverageTrend]) -> dict:
    """Analyze coverage trends and detect regressions."""
    if len(trends) < 2:
        return {
            "status": "insufficient_data",
            "message": "Need at least 2 data points for trend analysis",
        }

    latest = trends[-1]
    previous = trends[-2]

    line_delta = latest.total_line_rate - previous.total_line_rate
    branch_delta = latest.total_branch_rate - previous.total_branch_rate
    modules_delta = latest.modules_below_threshold - previous.modules_below_threshold

    # Determine overall trend
    if line_delta < -0.01:  # More than 1% decrease
        status = "regression"
    elif line_delta > 0.01:  # More than 1% increase
        status = "improvement"
    else:
        status = "stable"

    return {
        "status": status,
        "line_delta": line_delta * 100,
        "branch_delta": branch_delta * 100,
        "modules_delta": modules_delta,
        "entries_analyzed": len(trends),
    }


def print_console_report(report: CoverageReport, config: dict) -> None:
    """Print a human-readable coverage report to console."""
    print("=" * 70)
    print("COVERAGE ANALYSIS REPORT")
    print("=" * 70)
    print()

    # Configuration
    print("Configuration:")
    print(f"  Coverage threshold: {config['coverage_threshold']}%")
    print(f"  Critical path threshold: {config['critical_threshold']}%")
    print(f"  Warning threshold: {config['warning_threshold']}%")
    print()

    # Overall summary
    print("OVERALL COVERAGE:")
    print("-" * 40)
    print(f"  Line coverage:   {report.total_line_percent:.2f}%")
    print(f"  Branch coverage: {report.total_branch_percent:.2f}%")
    print()

    # Critical path failures (highest priority)
    if report.critical_below_threshold:
        print(
            f"CRITICAL PATH FAILURES ({len(report.critical_below_threshold)} modules below {config['critical_threshold']}%):"
        )
        print("-" * 40)
        for module in report.critical_below_threshold:
            print(f"  {module.line_coverage_percent:5.1f}% | {module.name}")
            print(f"         {module.lines_covered}/{module.lines_total} lines covered")
            if module.uncovered_lines:
                lines_preview = ", ".join(str(ln) for ln in module.uncovered_lines[:10])
                suffix = "..." if len(module.uncovered_lines) > 10 else ""
                print(f"         Uncovered lines: {lines_preview}{suffix}")
        print()

    # Modules below threshold
    if report.below_threshold:
        print(
            f"MODULES BELOW {config['coverage_threshold']}% THRESHOLD ({len(report.below_threshold)} modules):"
        )
        print("-" * 40)
        for module in report.below_threshold:
            print(f"  {module.line_coverage_percent:5.1f}% | {module.name}")
            if module.lines_total > 0:
                print(f"         {module.lines_covered}/{module.lines_total} lines covered")
        print()

    # Warnings (approaching threshold)
    if report.warnings:
        print(
            f"WARNINGS (between {config['coverage_threshold']}% and {config['warning_threshold']}%):"
        )
        print("-" * 40)
        for module in report.warnings[:10]:
            print(f"  {module.line_coverage_percent:5.1f}% | {module.name}")
        if len(report.warnings) > 10:
            print(f"  ... and {len(report.warnings) - 10} more")
        print()

    # Top covered modules (for comparison)
    well_covered = [
        m for m in report.modules if m.line_coverage_percent >= config["warning_threshold"]
    ]
    if well_covered:
        print(
            f"WELL COVERED MODULES ({len(well_covered)} modules at {config['warning_threshold']}%+):"
        )
        print("-" * 40)
        # Show top 5 by coverage
        for module in sorted(well_covered, key=lambda m: -m.line_rate)[:5]:
            print(f"  {module.line_coverage_percent:5.1f}% | {module.name}")
        print()

    # Recommendations
    print("RECOMMENDATIONS:")
    print("-" * 40)
    _print_recommendations(report, config)


def _print_recommendations(report: CoverageReport, config: dict) -> None:
    """Print actionable recommendations based on analysis."""
    if report.critical_below_threshold:
        print("  1. URGENT: Address critical path coverage gaps first")
        print("     These modules contain security-critical and core business logic")
        for module in report.critical_below_threshold[:3]:
            gap = config["critical_threshold"] - module.line_coverage_percent
            print(f"     - {module.name}: needs +{gap:.1f}% coverage")
        print()

    if report.below_threshold:
        print("  2. Prioritize testing for lowest-coverage modules:")
        for module in report.below_threshold[:5]:
            gap = config["coverage_threshold"] - module.line_coverage_percent
            print(f"     - {module.name}: needs +{gap:.1f}% coverage")
        print()

    if not report.critical_below_threshold and not report.below_threshold:
        print("  All modules meet coverage thresholds!")
        if report.warnings:
            print(f"  Consider improving {len(report.warnings)} modules approaching threshold.")
    print()


def print_uncovered_lines(report: CoverageReport) -> None:
    """Print detailed uncovered lines for each module."""
    print("=" * 70)
    print("UNCOVERED LINES BY MODULE")
    print("=" * 70)
    print()

    for module in report.modules:
        if not module.uncovered_lines:
            continue
        print(f"{module.name} ({module.line_coverage_percent:.1f}% coverage):")
        print(f"  File: {module.filename}")
        print(f"  Uncovered lines: {', '.join(str(ln) for ln in module.uncovered_lines)}")
        print()


def write_github_summary(report: CoverageReport, config: dict) -> None:
    """Write GitHub Actions job summary if running in CI."""
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return

    with open(summary_file, "a") as f:
        f.write("## Coverage Analysis Report\n\n")

        # Overall summary
        f.write(f"**Total Line Coverage:** {report.total_line_percent:.2f}%\n")
        f.write(f"**Total Branch Coverage:** {report.total_branch_percent:.2f}%\n\n")

        # Status badge
        if report.critical_below_threshold:
            f.write("> :warning: **CRITICAL**: Some critical paths are below threshold\n\n")
        elif report.below_threshold:
            f.write("> :large_orange_diamond: **WARNING**: Some modules are below threshold\n\n")
        else:
            f.write("> :white_check_mark: **PASS**: All modules meet coverage thresholds\n\n")

        # Critical failures table
        if report.critical_below_threshold:
            f.write(
                f"### Critical Path Failures ({len(report.critical_below_threshold)} modules)\n\n"
            )
            f.write("| Module | Coverage | Required | Gap |\n")
            f.write("|--------|----------|----------|-----|\n")
            for module in report.critical_below_threshold[:10]:
                gap = config["critical_threshold"] - module.line_coverage_percent
                f.write(
                    f"| `{module.name}` | {module.line_coverage_percent:.1f}% | {config['critical_threshold']}% | -{gap:.1f}% |\n"
                )
            if len(report.critical_below_threshold) > 10:
                f.write(f"\n*...and {len(report.critical_below_threshold) - 10} more*\n")
            f.write("\n")

        # Below threshold table
        if report.below_threshold:
            f.write(f"### Modules Below {config['coverage_threshold']}% Threshold\n\n")
            f.write("| Module | Coverage | Gap |\n")
            f.write("|--------|----------|-----|\n")
            for module in report.below_threshold[:15]:
                gap = config["coverage_threshold"] - module.line_coverage_percent
                f.write(
                    f"| `{module.name}` | {module.line_coverage_percent:.1f}% | -{gap:.1f}% |\n"
                )
            if len(report.below_threshold) > 15:
                f.write(f"\n*...and {len(report.below_threshold) - 15} more*\n")
            f.write("\n")


def write_json_report(report: CoverageReport, output_path: Path) -> None:
    """Write JSON report for programmatic consumption."""
    # Convert dataclasses to dicts
    report_dict = {
        "timestamp": report.timestamp,
        "total_line_rate": report.total_line_rate,
        "total_branch_rate": report.total_branch_rate,
        "total_line_percent": report.total_line_percent,
        "total_branch_percent": report.total_branch_percent,
        "modules": [asdict(m) for m in report.modules],
        "below_threshold": [asdict(m) for m in report.below_threshold],
        "critical_below_threshold": [asdict(m) for m in report.critical_below_threshold],
        "warnings": [asdict(m) for m in report.warnings],
        "summary": {
            "total_modules": len(report.modules),
            "modules_below_threshold": len(report.below_threshold),
            "critical_modules_below_threshold": len(report.critical_below_threshold),
            "modules_with_warnings": len(report.warnings),
        },
    }

    with output_path.open("w") as f:
        json.dump(report_dict, f, indent=2)

    print(f"JSON report written to: {output_path}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze test coverage reports and identify gaps",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s coverage.xml
    %(prog)s coverage.xml --output coverage-report.json
    %(prog)s coverage.xml --trend-file coverage-trend.json
    %(prog)s --list-uncovered coverage.xml

Environment variables:
    COVERAGE_THRESHOLD    Minimum coverage percentage (default: 85.0)
    CRITICAL_THRESHOLD    Coverage for critical paths (default: 90.0)
    WARNING_THRESHOLD     Percentage below which to warn (default: 90.0)
""",
    )
    parser.add_argument(
        "coverage_file",
        type=Path,
        help="Path to coverage.xml file (Cobertura format)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output JSON report file",
    )
    parser.add_argument(
        "--trend-file",
        type=Path,
        help="Path to trend tracking JSON file (will be created/updated)",
    )
    parser.add_argument(
        "--list-uncovered",
        action="store_true",
        help="List uncovered lines for each module",
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="Exit with error if total coverage is below this percentage",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Skip writing GitHub Actions summary",
    )

    args = parser.parse_args()

    if not args.coverage_file.exists():
        print(f"Error: Coverage file not found: {args.coverage_file}", file=sys.stderr)
        return 1

    config = get_config()

    # Parse coverage report
    report = parse_coverage_xml(args.coverage_file)

    # Print console report
    print_console_report(report, config)

    # Print uncovered lines if requested
    if args.list_uncovered:
        print_uncovered_lines(report)

    # Update trend file if provided
    if args.trend_file:
        trends = update_trend(args.trend_file, report)
        trend_analysis = analyze_trend(trends)

        print("COVERAGE TREND:")
        print("-" * 40)
        print(f"  Status: {trend_analysis['status']}")
        if trend_analysis["status"] != "insufficient_data":
            print(f"  Line coverage change: {trend_analysis['line_delta']:+.2f}%")
            print(f"  Branch coverage change: {trend_analysis['branch_delta']:+.2f}%")
            print(f"  Module gap change: {trend_analysis['modules_delta']:+d}")
            print(f"  Data points: {trend_analysis['entries_analyzed']}")
        print()

    # Write GitHub summary
    if not args.no_summary:
        write_github_summary(report, config)

    # Write JSON report if requested
    if args.output:
        write_json_report(report, args.output)

    # Summary
    print("=" * 70)
    exit_code = 0

    if report.critical_below_threshold:
        print(
            f"RESULT: FAIL - {len(report.critical_below_threshold)} critical module(s) below threshold"
        )
        exit_code = 1
    elif report.below_threshold:
        print(
            f"RESULT: WARN - {len(report.below_threshold)} module(s) below {config['coverage_threshold']}% threshold"
        )
        # Don't fail for non-critical modules below threshold, just warn
    else:
        print("RESULT: PASS - All modules meet coverage thresholds")

    # Check fail-under if specified
    if args.fail_under is not None and report.total_line_percent < args.fail_under:
        print(
            f"FAIL: Total coverage {report.total_line_percent:.2f}% is below --fail-under {args.fail_under}%"
        )
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
