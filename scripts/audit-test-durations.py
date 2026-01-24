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
    # Vehicle classifier tests - batch processing overhead (~1.1s in CI)
    r"test_vehicle_classifier_loader.*test_classify_vehicles_batch",
    # Log model extra properties - JSON serialization overhead (~1.0s in CI)
    r"test_log_model.*test_extra_roundtrip",
    # Full pipeline integration test - multi-stage AI processing
    r"test_pipeline_e2e.*test_full_pipeline",
    # Navigation smoke test - loads 8 routes sequentially (expected ~12s)
    r"All Routes Smoke Tests.*all 8 routes",
    r"navigation\.spec\.ts.*all 8 routes",
    # Navigation transition tests - page loads and transitions (~9-12s in CI)
    r"Navigation Tests.*page transitions",
    r"Navigation Tests.*sidebar persists",
    r"Navigation Tests.*can navigate to",
    # System page error state tests (~10s due to retry exhaustion)
    r"System Error State.*page loads",
    r"system\.spec\.ts.*Error State",
    # Performance collector container health tests - multiple HTTP health checks
    r"test_performance_collector.*TestCollectContainerHealth",
    r"test_performance_collector.*test_collect_container_health",
    # Alert rules E2E tests - UI-heavy interactions take 8-12s in CI
    r"alert-rules\.spec\.ts.*",
    # Re-identification tests - require Redis connection setup overhead
    r"test_enrichment_pipeline.*test_run_reid_requires_redis",
    # Accessibility tests - axe-core analysis takes 15-25s per page in CI
    r"accessibility\.spec\.ts.*",
    r".*Accessibility.*accessible",
    r".*Accessibility.*violations",
    r".*Color Contrast.*",
    r".*keyboard accessible",
    r".*focus correctly",
    # Property-based JSON parsing tests - Hypothesis text generation overhead
    r"test_json_utils.*PropertyBased.*",
    r"test_json_utils.*test_valid_json_always_parses",
    r"test_json_utils.*test_json_after_think_block_parses",
    # ReID service retry/backoff tests - use actual delays for timing verification
    r"test_reid_service.*TestReIDRetryBehavior.*",
    r"test_reid_service.*TestReIDRetryLogging.*",
    r"test_reid_service.*TestGenerateEmbedding.*test_generate_embedding_generic_error",
    r"test_reid_service.*TestRateLimitingEdgeCases.*test_rate_limit_released_on_exception",
    # Linear migration script retry tests - use actual delays
    r"test_migrate_beads_to_linear.*TestLinearClientRetryLogic.*",
    r"test_migrate_beads_to_linear.*TestLinearClientRetryLogging.*",
    # VitPose loader exception tests - model loading overhead
    r"test_vitpose_loader.*test_extract_pose_from_crop_exception",
    # File watcher stability tests - use actual sleep() for file stability timing
    r"test_file_watcher.*test_wait_for_file_stability",
    r"test_file_watcher.*test_stability_check_file_grows",
    r"test_file_watcher.*test_process_file_queues_with_normalized_id",
    r"test_file_watcher.*test_process_file_triggers_auto_create",
    # Video support tests - file processing with stability checks
    r"test_video_support.*TestFileWatcherVideoProcessing",
    # Vehicle classifier loader tests - model initialization overhead
    r"test_vehicle_classifier_loader.*test_classify_vehicle_runtime_error",
    # System broadcaster degradation tests - reconnection timing
    r"test_system_broadcaster.*is_degraded.*reestablish",
    # Enrichment client timeout/retry/error tests - use actual delays for timeout testing
    r"test_enrichment_client.*timeout",
    r"test_enrichment_client.*connection_error",
    r"test_enrichment_client.*server_error",
    r"test_enrichment_client.*asyncio_timeout",
    r"test_enrichment_client.*retries_on",
    r"test_enrichment_client_errors.*",
    r"test_enrichment_client_circuit_breaker.*",
    # Redis retry/timeout tests - use actual delays for retry logic verification
    r"test_redis.*test_get_redis_optional_returns_none_on_timeout_error",
    r"test_redis.*test_get_redis_optional_returns_none_on_connection_error",
    r"test_redis.*test_with_retry_executes_with",
    # Nemotron analyzer timeout/retry/error tests - use actual delays
    r"test_nemotron_analyzer.*test_call_llm_timeout",
    r"test_nemotron_analyzer.*test_call_llm_connection_error",
    r"test_nemotron_analyzer.*test_call_llm_http_error",
    r"test_nemotron_analyzer.*test_call_llm_asyncio_timeout",
    r"test_nemotron_analyzer.*test_call_llm_unexpected_error",
    r"test_nemotron_analyzer.*test_session_mock_with_helper",
    r"test_nemotron_analyzer.*test_analyze_batch_stores_idempotency",
    r"test_nemotron_analyzer.*test_analyze_batch_skips_enrichment",
    # Job progress reporter tests with throttling delays
    r"test_job_progress_reporter.*test_report_progress_throttling",
    r"test_job_progress_reporter.*test_complete_calculates_duration",
    # Property-based tests with Hypothesis generation overhead
    r"test_bbox_validation.*TestBboxValidationProperties.*",
    r"test_baseline.*TestPropertyBasedAnomalyScores.*",
    r"test_event_feedback.*TestEventFeedbackProperties.*test_event_id_roundtrip",
    r"test_job_transition.*TestJobTransitionProperties.*test_trigger_roundtrip",
    r"test_zone.*TestZoneProperties.*test_zone_color_roundtrip",
    r"test_camera.*TestCameraFromFolderNameProperties.*",
    r"test_dedupe.*TestDedupeProperties.*",
    r"test_prompt_parser.*TestDetectVariableStyleProperties.*",
    # Transcode cache cleanup tests - deliberate delays for LRU testing
    r"test_transcode_cache.*test_cache_cleanup_removes_lru_entries",
    # Model zoo tests - model loading/unloading overhead
    r"test_model_zoo.*TestConcurrentModelLoading.*",
    r"test_shutdown_cleanup.*TestModelUnloading.*",
    # Pet/vehicle classifier loader error tests - model initialization overhead
    r"test_pet_classifier_loader.*test_classify_pet_runtime_error",
    r"test_vehicle_classifier_loader.*test_classify_vehicle_runtime_error",
    # Plate detector tests with image caching
    r"test_plate_detector.*test_detect_plates_with_cached_images",
    # Token counter tests
    r"test_token_counter.*TestEnrichmentTokenEstimation.*",
    # Pipeline E2E test - fast path with multi-stage processing
    r"test_pipeline_e2e.*test_fast_path_high_priority_detection",
    # Pipeline E2E LLM failure test - uses retry logic with timeouts (~13s in CI)
    r"test_pipeline_e2e.*test_pipeline_llm_failure_fallback",
    # Enrichment pipeline tests - model initialization and processing overhead
    r"test_enrichment_pipeline.*test_enrich_batch_no_shared_image",
    r"test_enrichment_pipeline_household_matching.*test_household_matching_skipped_when_disabled",
    # Hypothesis property-based tests - generation overhead for large input spaces
    r"test_models_hypothesis.*TestZoneCoordinateValidation.*test_out_of_range_coordinates_rejected",
    # Service registry singleton tests - initialization overhead with multiple services
    r"test_managed_service.*TestGlobalRegistry.*test_get_service_registry_creates_singleton",
    # Model tests with property-based generation - Hypothesis overhead
    r"test_detection.*TestDetectionProperties.*test_video_metadata_roundtrip",
    r"test_job_attempt.*TestJobAttemptProperties.*test_worker_id_roundtrip",
    r"test_job_attempt.*TestJobAttemptProperties.*test_error_message_roundtrip",
    r"test_job_transition.*TestJobTransitionProperties.*test_status_transition_roundtrip",
    r"test_scene_change.*TestSceneChangeProperties.*test_id_roundtrip",
    r"test_models_hypothesis.*TestZoneModelProperties.*test_zone_type_values",
    # Job progress reporter duration tracking tests - use actual time.time() calls
    r"test_job_progress_reporter.*TestDurationTracking.*test_duration_after_start",
    # Model zoo preload/unload tests - model initialization and GPU resource management
    r"test_model_zoo.*TestModelManager.*test_preload_and_unload",
    # API middleware correlation tests - HTTP request overhead
    r"test_correlation_propagation.*TestNemotronAnalyzerCorrelation.*test_call_llm_includes_correlation_headers",
    # Segformer clothing segmentation error tests - model initialization overhead
    r"test_segformer_loader.*test_segment_clothing_error_handling",
    # Violence classification error tests - model initialization overhead
    r"test_violence_loader.*TestClassifyViolence.*test_classify_violence_error_handling",
    # Worker supervisor circuit breaker tests - use real delays for testing timeout logic
    r"test_worker_supervisor.*TestWorkerCrashRestart.*test_max_restarts_exceeded",
    r"test_worker_supervisor.*TestCircuitBreaker.*test_circuit_opens_after_max_restarts",
    # Detection properties roundtrip tests - Hypothesis generation overhead
    r"test_detection.*TestDetectionProperties.*test_required_fields_roundtrip",
    # Hypothesis vehicle detection format tests - generation overhead
    r"test_hypothesis_strategies.*test_example_vehicle_detection_format",
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


def analyze_tests(
    results_dir: Path,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Analyze all JUnit XML files in directory."""
    unit_threshold, integration_threshold, e2e_threshold, slow_threshold, warn_pct = (
        get_thresholds()
    )

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
        print(f"    {format_test_name(test)}")
    print()


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: audit-test-durations.py <results-dir>", file=sys.stderr)
        return 1

    results_dir = Path(sys.argv[1])
    if not results_dir.exists():
        print(f"Error: Directory not found: {results_dir}", file=sys.stderr)
        return 1

    failures, warnings, slow_tests, benchmark_tests = analyze_tests(results_dir)

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
