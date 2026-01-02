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
    E2E_TEST_THRESHOLD: Max seconds for E2E/Playwright tests (default: 5.0)
    SLOW_TEST_THRESHOLD: Max seconds for known slow tests (default: 60.0)
    WARN_THRESHOLD_PERCENT: Warn at this % of limit (default: 80)
"""

import os
import re
import sys
from pathlib import Path

import defusedxml.ElementTree as ET

# Known slow test patterns - tests marked with @pytest.mark.slow
# These use real worker timeouts (10-30s) and are expected to be slow
SLOW_TEST_PATTERNS = [
    # Pipeline worker manager tests that use real stop timeouts
    r"test_pipeline_workers.*test_manager_start_stop",
    r"test_pipeline_workers.*test_manager_idempotent",
    r"test_pipeline_workers.*test_manager_signal_handler",
    r"test_pipeline_workers.*test_manager_stops_all",
    r"test_pipeline_workers.*test_stop_pipeline_manager_clears",
    # Health monitor tests with subprocess timeouts
    r"test_health_monitor.*test_subprocess_timeout",
    # System broadcaster reconnection tests
    r"test_system_broadcaster.*reconnection",
    r"test_system_broadcaster.*restarts_with_fresh",
    # Media route tests (thumbnail generation)
    r"test_media_api.*test_compat_thumbnail",
    # Property-based tests with text generation overhead
    r"test_alert.*test_alert_dedup_key_roundtrip",
    r"test_alert.*test_alert_event_id_roundtrip",
    r"test_event.*test_risk_score_roundtrip",
    r"test_audit_log.*test_details_roundtrip",
    # TLS certificate generation tests - RSA key generation is CPU-intensive
    r"test_tls.*test_custom_key_size_4096",
    # E2E error state tests - wait for API retry exhaustion (~15s)
    r".*Error State.*shows error",
    r".*Error State.*error state",
    r".*Error State.*reload button",
    r".*Error Handling.*shows error",
    r".*Error Handling.*error message",
    r".*Error Handling.*reload button",
    r".*Network Error Messages.*user-friendly",
    r".*Partial API Failure",
    r".*Empty State.*dashboard",
    r".*Empty State.*no activity",
    # E2E dashboard tests - initial page load overhead in CI (~7s)
    r"Dashboard Stats Row.*displays",
    r"Dashboard Camera Grid.*displays",
    r"Dashboard Camera Grid.*visible",
    r"Dashboard Activity Feed.*visible",
    r"Dashboard Activity Feed.*heading",
    r"Dashboard Risk Gauge.*visible",
    r"Dashboard Risk Gauge.*heading",
    r"Dashboard High Alert State.*loads",
    # E2E alerts page tests - page load overhead (~5-7s)
    r"Alerts Page Load.*title",
    r"Alerts Page Load.*displays",
    r"Alerts Page Load.*loads",
    r"Alerts Filter.*",
    r"Alerts Refresh.*",
    r"Alerts Pagination.*",
    r"Alerts Empty State.*",
    r"Alerts Error State.*",
    r"Alerts High Alert Mode.*",
    # E2E Event Timeline page tests - page load overhead in CI (~7s)
    r"Event Timeline Page Load.*",
    r"Event Timeline Filters.*",
    r"Event Timeline Search.*",
    r"Event Timeline Export.*",
    r"Event Timeline Pagination.*",
    r"Event Timeline Bulk Actions.*",
    r"Event Timeline Empty State.*",
    r"Event Timeline Error State.*",
    # Error State tests with specific naming patterns
    r".*Error State.*handles API error",
    # Model loading tests - may download/initialize models on first run
    r"test_vehicle_damage_loader.*test_load_model",
    r"test_violence_loader.*test_load_violence_model",
    r"test_model_zoo.*test_load_context_manager",
    r"test_benchmark_vram.*test_clear_gpu_cache",
    # Full pipeline integration test - multi-stage AI processing
    r"test_pipeline_e2e.*test_full_pipeline",
]


def get_thresholds() -> tuple[float, float, float, float, float]:
    """Get threshold values from environment or defaults."""
    unit = float(os.environ.get("UNIT_TEST_THRESHOLD", "1.0"))
    integration = float(os.environ.get("INTEGRATION_TEST_THRESHOLD", "5.0"))
    e2e = float(os.environ.get("E2E_TEST_THRESHOLD", "5.0"))
    slow = float(os.environ.get("SLOW_TEST_THRESHOLD", "60.0"))
    warn_pct = float(os.environ.get("WARN_THRESHOLD_PERCENT", "80")) / 100
    return unit, integration, e2e, slow, warn_pct


def is_known_slow_test(classname: str, name: str) -> bool:
    """Check if test matches known slow test patterns."""
    full_path = f"{classname}::{name}"
    return any(re.search(pattern, full_path, re.IGNORECASE) for pattern in SLOW_TEST_PATTERNS)


def categorize_test(classname: str, name: str, filepath: str = "") -> str:
    """Determine if a test is unit, integration, e2e, or slow based on path/patterns."""
    full_path = f"{classname}.{name}".lower()
    file_lower = filepath.lower()

    # Check if it matches known slow test patterns
    if is_known_slow_test(classname, name):
        return "slow"

    # E2E/Playwright tests (from e2e-results.xml or .spec.ts patterns)
    if "e2e" in file_lower or ".spec." in full_path or "playwright" in file_lower:
        return "e2e"

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
                            "category": categorize_test(classname, name, str(filepath)),
                            "file": str(filepath),
                        }
                    )
    except ET.ParseError as e:
        print(f"Warning: Could not parse {filepath}: {e}", file=sys.stderr)

    return tests


def analyze_tests(results_dir: Path) -> tuple[list[dict], list[dict], list[dict]]:
    """Analyze all JUnit XML files in directory."""
    unit_threshold, integration_threshold, e2e_threshold, slow_threshold, warn_pct = (
        get_thresholds()
    )

    failures = []
    warnings = []
    slow_tests = []

    # Find all XML files
    xml_files = list(results_dir.glob("**/*.xml"))
    if not xml_files:
        print(f"Warning: No XML files found in {results_dir}", file=sys.stderr)
        return [], [], []

    for xml_file in xml_files:
        tests = parse_junit_xml(xml_file)

        for test in tests:
            # Determine threshold based on category
            if test["category"] == "slow":
                threshold = slow_threshold
                slow_tests.append(test)
            elif test["category"] == "integration":
                threshold = integration_threshold
            elif test["category"] == "e2e":
                threshold = e2e_threshold
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
    slow_tests.sort(key=lambda x: x["duration"], reverse=True)

    return failures, warnings, slow_tests


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

    failures, warnings, slow_tests = analyze_tests(results_dir)

    print("=" * 70)
    print("TEST PERFORMANCE AUDIT")
    print("=" * 70)
    print()

    unit_threshold, integration_threshold, e2e_threshold, slow_threshold, warn_pct = (
        get_thresholds()
    )
    print(
        f"Thresholds: unit={unit_threshold}s, integration={integration_threshold}s, "
        f"e2e={e2e_threshold}s, slow={slow_threshold}s"
    )
    print(f"Warning at: {warn_pct * 100:.0f}% of threshold")
    print()

    if slow_tests:
        print(f"KNOWN SLOW TESTS ({len(slow_tests)} tests with extended threshold):")
        print("-" * 40)
        for test in slow_tests[:5]:  # Show top 5 slow tests
            print(
                f"  {test['duration']:.2f}s (limit: {test['threshold']:.1f}s) [{test['category']}]"
            )
            print(f"    {format_test_name(test)}")
        if len(slow_tests) > 5:
            print(f"  ... and {len(slow_tests) - 5} more")
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
        print(f"RESULT: PASS with {len(warnings)} warning(s), {len(slow_tests)} known slow test(s)")
        return 0
    else:
        print(f"RESULT: PASS - All tests within time limits ({len(slow_tests)} known slow)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
