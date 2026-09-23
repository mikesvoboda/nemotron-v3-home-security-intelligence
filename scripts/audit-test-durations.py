#!/usr/bin/env python3
"""Analyze JUnit XML test results and flag slow tests.

This script parses JUnit XML files from CI test runs and:
1. Identifies tests exceeding their category threshold
2. Warns about tests approaching the threshold (>80%)
3. Exits non-zero if any test exceeds its limit

Usage:
    python scripts/audit-test-durations.py <results-dir> [--baseline-dir DIR]

Environment variables:
    UNIT_TEST_THRESHOLD: Max seconds for unit tests (default: 1.0)
    INTEGRATION_TEST_THRESHOLD: Max seconds for integration tests (default: 5.0)
    E2E_TEST_THRESHOLD: Max seconds for E2E/Playwright tests (default: 5.0)
    SLOW_TEST_THRESHOLD: Max seconds for known slow tests (default: 60.0)
    WARN_THRESHOLD_PERCENT: Warn at this % of limit (default: 80)
    BASELINE_DIR: optional dir of the SAME corpus's previous junit XMLs — the
        run's own baseline (WP1.3). With it, a threshold breach is downgraded
        to a warning UNLESS the same test-id also breached in the baseline OR
        the duration is >= BASELINE_SEVERITY_FACTOR (default 3) x threshold.

WP1.3 baseline rule (measured, ledger WP1.3): a single timing sample on a
contended shared runner reddened 15/45 PR runs on identical code; suite-wide
medians are identical red-vs-green, so global calibration cannot work. The
runner's own previous run IS the calibration. Fail-closed everywhere:
baseline missing/unreadable/zero-XML -> every breach is RED exactly like the
pre-WP1.3 gate (a CI bug cannot silently widen the gate), and a severe breach
(>= factor x threshold) is always RED — a new test's first 4.5s unit hit still
bites on its first run.
"""

import os
import re
import sys
from pathlib import Path

import defusedxml.ElementTree as ET

# Known slow test patterns - tests marked with @pytest.mark.slow
# These use real worker timeouts (10-30s) and are expected to be slow
SLOW_TEST_PATTERNS = [
    # WP1.3 PRUNE (2026-09-20): this list was 150 patterns / ~80% not slow
    # (census: 146 patterns covered NO test that breaches its native
    # threshold, while pre-exempting unwritten tests with `.*` wildcards —
    # an exemption channel outside suppression-census.py). Pruned to the
    # seven tests MEASURED genuinely slow over 18 main junit datasets
    # (ledger WP1.3); any future entrant needs a measured breach in the
    # corpus AND a `tpa_slow_list` census entry. Category name kept as
    # "slow" for the 60s cap + KNOWN SLOW TESTS report section.
    r"test_job_progress_reporter.*test_complete_calculates_duration",  # ~15.3s measured
    r"test_pipeline_e2e.*test_pipeline_llm_failure_fallback",  # ~15.3s
    r"test_error_handler.*test_timestamp_auto_generated",  # ~16.5s
    r"test_rtsp_test_service.*test_connection_timeout",  # ~6.0s real socket timeout
    r"TestDurationTracking::test_duration_after_start",  # persistent spike x10/17 runs, 18s peak (WP1.3)
    r"test_fast_path_high_priority_detection",  # persistent x8/17, 18.5s peak (WP1.3)
    r"TestHandleUnhealthy::test_handle_unhealthy_stamps",  # persistent x7/17, 18.2s peak (WP1.3)
    r"test_enrichment_pipeline_household_matching.*test_vehicle_household_matching_via_license_plate",  # 4.18s x2 + 4.297s main corpus, 1.20s alone — -n8 contention (2026-09-23)
]

# Benchmark patterns - tests that should be excluded from audit entirely
# These are intentionally slow and measure performance, not correctness
BENCHMARK_PATTERNS = [
    # API benchmarks - intentionally slow, measure performance
    r"TestAPIBenchmarks::",
    r"TestAPIBenchmarksAsync::",
    # Memory profiling tests
    r"TestMemoryProfiling.*",
    r"TestMemoryProfilingFallback.*",
    # Big-O complexity tests
    r"TestBatchAggregatorComplexity::",
    r"TestFileWatcherComplexity::",
    # Any test in benchmarks directory
    r"backend\.tests\.benchmarks\.",
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


def is_benchmark_test(classname: str, name: str) -> bool:
    """Check if test is a benchmark test (should be excluded from audit)."""
    full_path = f"{classname}::{name}"
    return any(re.search(pattern, full_path, re.IGNORECASE) for pattern in BENCHMARK_PATTERNS)


def categorize_test(classname: str, name: str, filepath: str = "") -> str:
    """Determine if a test is unit, integration, e2e, slow, or benchmark."""
    full_path = f"{classname}.{name}".lower()
    file_lower = filepath.lower()

    # Check if it's a benchmark test (excluded from audit)
    if is_benchmark_test(classname, name):
        return "benchmark"

    # Check if it matches known slow test patterns
    if is_known_slow_test(classname, name):
        return "slow"

    # E2E/Playwright tests (from e2e-results.xml or .spec.ts patterns)
    if "e2e" in file_lower or ".spec." in full_path or "playwright" in file_lower:
        return "e2e"

    # Integration-level tests: explicit integration, contracts, chaos, gpu, security
    # - Contract tests: API schema validation
    # - Chaos tests: Fault injection with deliberate delays (30-120s)
    # - GPU tests: Hardware-specific with longer runtimes
    # - Security tests: Validation tests with extended runtimes
    integration_patterns = ("integration", "contract", "chaos", "gpu", "security")
    if any(pattern in full_path or pattern in file_lower for pattern in integration_patterns):
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


def parse_baseline(baseline_dir: Path) -> tuple[set[str], set[str]] | None:
    """(known_test_ids, violating_ids) from a previous run's junit corpus.

    Existence comes from EVERY <testcase> element, including zero-duration
    ones: a test that was SKIPPED in the baseline run still proves the test
    EXISTS — measured (replay vs a real main-run corpus, ledger WP1.3),
    reusing parse_junit_xml's duration>0 filter mislabeled a handful of
    historically-skipped tests as brand-new every run and denied them the
    baseline downgrade. Violations still require duration > threshold, so a
    skip can never make a breach look persistent; it can only make a test
    recognizable.

    Returns None when a usable baseline does not exist (dir missing/absent or
    zero parseable XML) — callers must then fail CLOSED: WP1.3's downgrade is
    calibrated against a real previous sample, and a CI-side fetch bug must
    not silently widen the gate.
    """
    if not baseline_dir or not baseline_dir.is_dir():
        return None
    ut, it, et, st, _ = get_thresholds()
    seen: set[str] = set()
    violators: set[str] = set()
    for xml_file in baseline_dir.glob("**/*.xml"):
        try:
            root = ET.parse(xml_file).getroot()
        except ET.ParseError:
            continue
        suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
        for suite in suites:
            for tc in suite.findall("testcase"):
                cn, nm = tc.get("classname", ""), tc.get("name", "")
                try:
                    duration = float(tc.get("time", "0"))
                except ValueError:
                    duration = 0.0
                category = categorize_test(cn, nm, str(xml_file))
                if category == "benchmark":
                    continue
                tid = f"{cn}::{nm}"
                seen.add(tid)
                threshold = {"slow": st, "integration": it, "e2e": et}.get(category, ut)
                if duration > threshold:
                    violators.add(tid)
    if not seen:
        return None
    return seen, violators


def analyze_tests(
    results_dir: Path,
    baseline: tuple[set[str], set[str]] | None = None,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Analyze all JUnit XML files in directory.

    With `baseline` (WP1.3): a breach is RED when the same test-id also
    breached in the baseline corpus (persistence — the runner was slow for
    THIS test twice), when duration >= factor x threshold (severity — a big
    jump is a real regression whatever the history says), or when the id is
    ABSENT from the baseline corpus entirely (a new/renamed test has no
    history to be forgiven by — its first breach bites immediately). A mild
    one-run spike on a previously healthy test is downgraded to a WARNING:
    measured, that population is what reddened 15/45 PR runs on identical
    code (single timing sample on a contended runner; global calibration is
    impossible — suite medians are identical red-vs-green).
    """
    unit_threshold, integration_threshold, e2e_threshold, slow_threshold, warn_pct = (
        get_thresholds()
    )
    severity_factor = float(os.environ.get("BASELINE_SEVERITY_FACTOR", "3"))
    baseline_seen, baseline_violators = baseline if baseline else (set(), set())

    failures = []
    warnings = []
    slow_tests = []
    benchmark_tests = []  # Track benchmarks separately (excluded from audit)

    # Find all XML files
    xml_files = list(results_dir.glob("**/*.xml"))
    if not xml_files:
        print(f"Warning: No XML files found in {results_dir}", file=sys.stderr)
        return [], [], [], []

    for xml_file in xml_files:
        tests = parse_junit_xml(xml_file)

        for test in tests:
            # Benchmark tests are excluded from threshold checking
            if test["category"] == "benchmark":
                benchmark_tests.append(test)
                continue

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
                if baseline is not None:
                    tid = format_test_name(test)
                    severe = test["duration"] >= severity_factor * threshold
                    if tid not in baseline_violators and not severe and tid in baseline_seen:
                        test["baseline_note"] = (
                            f"WP1.3 baseline: not in previous run's violations "
                            f"(< {severity_factor:g}x limit) -> warning, run-it-again-red"
                        )
                        warnings.append(test)
                        continue
                failures.append(test)
            # Check if approaching threshold
            elif test["duration"] > threshold * warn_pct:
                warnings.append(test)

    # Sort by duration descending
    failures.sort(key=lambda x: x["duration"], reverse=True)
    warnings.sort(key=lambda x: x["duration"], reverse=True)
    slow_tests.sort(key=lambda x: x["duration"], reverse=True)
    benchmark_tests.sort(key=lambda x: x["duration"], reverse=True)

    return failures, warnings, slow_tests, benchmark_tests


def format_test_name(test: dict) -> str:
    """Format test name for display."""
    return f"{test['classname']}::{test['name']}"


def print_benchmark_section(benchmark_tests: list[dict]) -> None:
    """Print benchmark tests section."""
    if not benchmark_tests:
        return
    print(f"BENCHMARK TESTS ({len(benchmark_tests)} - excluded from audit):")
    print("-" * 40)
    for test in benchmark_tests[:5]:
        print(f"  {test['duration']:.2f}s - {format_test_name(test)}")
    if len(benchmark_tests) > 5:
        print(f"  ... and {len(benchmark_tests) - 5} more")
    print()


def print_slow_tests_section(slow_tests: list[dict]) -> None:
    """Print known slow tests section."""
    if not slow_tests:
        return
    print(f"KNOWN SLOW TESTS ({len(slow_tests)} tests with extended threshold):")
    print("-" * 40)
    for test in slow_tests[:5]:
        print(f"  {test['duration']:.2f}s (limit: {test['threshold']:.1f}s) [{test['category']}]")
        print(f"    {format_test_name(test)}")
    if len(slow_tests) > 5:
        print(f"  ... and {len(slow_tests) - 5} more")
    print()


def print_failures_section(failures: list[dict]) -> None:
    """Print failures section."""
    if not failures:
        return
    print("FAILURES (exceeded threshold):")
    print("-" * 40)
    for test in failures:
        print(f"  {test['duration']:.2f}s (limit: {test['threshold']:.1f}s) [{test['category']}]")
        print(f"    {format_test_name(test)}")
    print()


def print_warnings_section(warnings: list[dict]) -> None:
    """Print warnings section."""
    if not warnings:
        return
    print("WARNINGS (>80% of threshold):")
    print("-" * 40)
    for test in warnings:
        pct = (test["duration"] / test["threshold"]) * 100
        print(
            f"  {test['duration']:.2f}s ({pct:.0f}% of {test['threshold']:.1f}s) "
            f"[{test['category']}]"
        )
        if "baseline_note" in test:
            print(f"    {test['baseline_note']}")
        print(f"    {format_test_name(test)}")
    print()


def main() -> int:
    """Main entry point."""
    argv = sys.argv[1:]
    baseline_dir: Path | None = None
    if "--baseline-dir" in argv:
        i = argv.index("--baseline-dir")
        if i + 1 >= len(argv):
            print("Error: --baseline-dir requires a directory", file=sys.stderr)
            return 1
        baseline_dir = Path(argv[i + 1])
        argv = argv[:i] + argv[i + 2 :]
    elif os.environ.get("BASELINE_DIR"):
        baseline_dir = Path(os.environ["BASELINE_DIR"])
    if not argv:
        print("Usage: audit-test-durations.py <results-dir> [--baseline-dir DIR]", file=sys.stderr)
        return 1

    results_dir = Path(argv[0])
    if not results_dir.exists():
        print(f"Error: Directory not found: {results_dir}", file=sys.stderr)
        return 1

    # WP0.5: a gate with no test data must FAIL, not vacuously pass. The job
    # only runs when its tier actually ran (ci.yml `if:` mirrors unit-tests'
    # own trigger), so zero XML here means the pipeline broke — exactly the
    # class of silent lie the pre-push gate repair (WP0.1) pinned.
    if not list(results_dir.glob("**/*.xml")):
        print(
            f"Error: no JUnit XML found under {results_dir} — the audit job "
            "ran with no test data; failing rather than passing vacuously.",
            file=sys.stderr,
        )
        return 1

    baseline = parse_baseline(baseline_dir) if baseline_dir else None
    if baseline_dir and baseline is None:
        # Fail-closed, LOUDLY: the fetch step asked for a baseline and none is
        # usable. Verdicts then equal the pre-WP1.3 gate (every breach red).
        print(
            f"Warning: baseline dir {baseline_dir} has no parseable JUnit XML — "
            "running FAIL-CLOSED (WP1.3 baseline downgrades disabled).",
            file=sys.stderr,
        )

    failures, warnings, slow_tests, benchmark_tests = analyze_tests(results_dir, baseline=baseline)

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
    if baseline is not None:
        print(
            f"WP1.3 baseline: {len(baseline[0])} test(s) from previous run; "
            f"{len(baseline[1])} breached there. Mild one-run spikes on tests "
            f"that were healthy there downgrade to warnings; severity "
            f">= {os.environ.get('BASELINE_SEVERITY_FACTOR', '3')}x and new tests bite."
        )
    elif baseline_dir:
        print("WP1.3 baseline: requested but UNUSABLE — fail-closed (every breach red)")
    print()

    # Print all sections using helper functions
    print_benchmark_section(benchmark_tests)
    print_slow_tests_section(slow_tests)
    print_failures_section(failures)
    print_warnings_section(warnings)

    # Summary
    print("=" * 70)
    if failures:
        print(f"RESULT: FAIL - {len(failures)} test(s) exceeded time limit")
        return 1

    if warnings:
        print(
            f"RESULT: PASS with {len(warnings)} warning(s), "
            f"{len(slow_tests)} known slow test(s), "
            f"{len(benchmark_tests)} benchmark(s) excluded"
        )
    else:
        print(
            f"RESULT: PASS - All tests within time limits "
            f"({len(slow_tests)} known slow, {len(benchmark_tests)} benchmarks excluded)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
