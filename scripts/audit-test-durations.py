#!/usr/bin/env python3
"""Analyze JUnit XML test results and flag slow tests.

This script parses JUnit XML files from CI test runs and:
1. Identifies tests exceeding their category threshold
2. Warns about tests approaching the threshold (>80%)
3. Exits non-zero if any test exceeds its limit

Usage:
    python scripts/audit-test-durations.py <results-dir>

Environment variables:
    UNIT_TEST_THRESHOLD: Max seconds for unit tests (default: 1.0)
    INTEGRATION_TEST_THRESHOLD: Max seconds for integration tests (default: 5.0)
    WARN_THRESHOLD_PERCENT: Warn at this % of limit (default: 80)
"""

import os
import sys
from pathlib import Path

import defusedxml.ElementTree as ET


def get_thresholds() -> tuple[float, float, float]:
    """Get threshold values from environment or defaults."""
    unit = float(os.environ.get("UNIT_TEST_THRESHOLD", "1.0"))
    integration = float(os.environ.get("INTEGRATION_TEST_THRESHOLD", "5.0"))
    warn_pct = float(os.environ.get("WARN_THRESHOLD_PERCENT", "80")) / 100
    return unit, integration, warn_pct


def categorize_test(classname: str, name: str) -> str:
    """Determine if a test is unit or integration based on path."""
    full_path = f"{classname}.{name}".lower()
    if "integration" in full_path:
        return "integration"
    return "unit"


def parse_junit_xml(filepath: Path) -> list[dict]:
    """Parse a JUnit XML file and extract test timing data."""
    tests = []
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()

        # Handle both <testsuites> and <testsuite> root elements
        testsuites = root.findall("testsuite") if root.tag == "testsuites" else [root]

        for testsuite in testsuites:
            for testcase in testsuite.findall("testcase"):
                classname = testcase.get("classname", "")
                name = testcase.get("name", "")
                time_str = testcase.get("time", "0")

                try:
                    duration = float(time_str)
                except ValueError:
                    duration = 0.0

                # Skip tests with 0 duration (likely skipped)
                if duration > 0:
                    tests.append(
                        {
                            "classname": classname,
                            "name": name,
                            "duration": duration,
                            "category": categorize_test(classname, name),
                            "file": str(filepath),
                        }
                    )
    except ET.ParseError as e:
        print(f"Warning: Could not parse {filepath}: {e}", file=sys.stderr)

    return tests


def analyze_tests(results_dir: Path) -> tuple[list[dict], list[dict]]:
    """Analyze all JUnit XML files in directory."""
    unit_threshold, integration_threshold, warn_pct = get_thresholds()

    failures = []
    warnings = []

    # Find all XML files
    xml_files = list(results_dir.glob("**/*.xml"))
    if not xml_files:
        print(f"Warning: No XML files found in {results_dir}", file=sys.stderr)
        return [], []

    for xml_file in xml_files:
        tests = parse_junit_xml(xml_file)

        for test in tests:
            # Determine threshold based on category
            if test["category"] == "integration":
                threshold = integration_threshold
            else:
                threshold = unit_threshold

            test["threshold"] = threshold

            # Check if exceeds threshold
            if test["duration"] > threshold:
                failures.append(test)
            # Check if approaching threshold
            elif test["duration"] > threshold * warn_pct:
                warnings.append(test)

    # Sort by duration descending
    failures.sort(key=lambda x: x["duration"], reverse=True)
    warnings.sort(key=lambda x: x["duration"], reverse=True)

    return failures, warnings


def format_test_name(test: dict) -> str:
    """Format test name for display."""
    return f"{test['classname']}::{test['name']}"


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: audit-test-durations.py <results-dir>", file=sys.stderr)
        return 1

    results_dir = Path(sys.argv[1])
    if not results_dir.exists():
        print(f"Error: Directory not found: {results_dir}", file=sys.stderr)
        return 1

    failures, warnings = analyze_tests(results_dir)

    print("=" * 70)
    print("TEST PERFORMANCE AUDIT")
    print("=" * 70)
    print()

    unit_threshold, integration_threshold, warn_pct = get_thresholds()
    print(f"Thresholds: unit={unit_threshold}s, integration={integration_threshold}s")
    print(f"Warning at: {warn_pct * 100:.0f}% of threshold")
    print()

    if failures:
        print("FAILURES (exceeded threshold):")
        print("-" * 40)
        for test in failures:
            print(
                f"  {test['duration']:.2f}s (limit: {test['threshold']:.1f}s) [{test['category']}]"
            )
            print(f"    {format_test_name(test)}")
        print()

    if warnings:
        print("WARNINGS (>80% of threshold):")
        print("-" * 40)
        for test in warnings:
            pct = (test["duration"] / test["threshold"]) * 100
            print(
                f"  {test['duration']:.2f}s ({pct:.0f}% of {test['threshold']:.1f}s) "
                f"[{test['category']}]"
            )
            print(f"    {format_test_name(test)}")
        print()

    # Summary
    print("=" * 70)
    if failures:
        print(f"RESULT: FAIL - {len(failures)} test(s) exceeded time limit")
        return 1
    elif warnings:
        print(f"RESULT: PASS with {len(warnings)} warning(s)")
        return 0
    else:
        print("RESULT: PASS - All tests within time limits")
        return 0


if __name__ == "__main__":
    sys.exit(main())
