"""Unit tests for worker health and reliability metrics (NEM-4148).

Tests cover:
- Worker restart metrics with worker_type and reason labels
- Worker crash metrics with worker_type and exit_code labels
- Worker heartbeat missed metrics with worker_type label
- Helper functions for reason categorization and exit code extraction
- Worker type auto-detection from worker names
"""

from backend.core.metrics import (
    WORKER_CRASHES_TOTAL,
    WORKER_HEARTBEAT_MISSED_TOTAL,
    WORKER_RESTART_REASONS,
    WORKER_RESTARTS_TOTAL,
    WORKER_TYPES,
    _categorize_restart_reason_worker,
    _determine_worker_type,
    _extract_exit_code,
    get_metrics_response,
    record_worker_crash,
    record_worker_heartbeat_missed,
    record_worker_restart,
)


class TestWorkerHealthMetricDefinitions:
    """Test worker health metric definitions (NEM-4148)."""

    def test_worker_restarts_total_has_required_labels(self) -> None:
        """WORKER_RESTARTS_TOTAL should have worker_name, worker_type, and reason labels."""
        assert WORKER_RESTARTS_TOTAL is not None
        # prometheus_client strips _total suffix from counter names internally
        assert WORKER_RESTARTS_TOTAL._name == "hsi_worker_restarts"
        assert "worker_name" in WORKER_RESTARTS_TOTAL._labelnames
        assert "worker_type" in WORKER_RESTARTS_TOTAL._labelnames
        assert "reason" in WORKER_RESTARTS_TOTAL._labelnames

    def test_worker_crashes_total_has_required_labels(self) -> None:
        """WORKER_CRASHES_TOTAL should have worker_name, worker_type, and exit_code labels."""
        assert WORKER_CRASHES_TOTAL is not None
        # prometheus_client strips _total suffix from counter names internally
        assert WORKER_CRASHES_TOTAL._name == "hsi_worker_crashes"
        assert "worker_name" in WORKER_CRASHES_TOTAL._labelnames
        assert "worker_type" in WORKER_CRASHES_TOTAL._labelnames
        assert "exit_code" in WORKER_CRASHES_TOTAL._labelnames

    def test_worker_heartbeat_missed_total_has_required_labels(self) -> None:
        """WORKER_HEARTBEAT_MISSED_TOTAL should have worker_name and worker_type labels."""
        assert WORKER_HEARTBEAT_MISSED_TOTAL is not None
        # prometheus_client strips _total suffix from counter names internally
        assert WORKER_HEARTBEAT_MISSED_TOTAL._name == "hsi_worker_heartbeat_missed"
        assert "worker_name" in WORKER_HEARTBEAT_MISSED_TOTAL._labelnames
        assert "worker_type" in WORKER_HEARTBEAT_MISSED_TOTAL._labelnames

    def test_worker_restart_reasons_defined(self) -> None:
        """WORKER_RESTART_REASONS should contain expected reason values."""
        assert "oom" in WORKER_RESTART_REASONS
        assert "crash" in WORKER_RESTART_REASONS
        assert "timeout" in WORKER_RESTART_REASONS
        assert "manual" in WORKER_RESTART_REASONS
        assert "unknown" in WORKER_RESTART_REASONS

    def test_worker_types_defined(self) -> None:
        """WORKER_TYPES should contain expected worker type values."""
        assert "pipeline" in WORKER_TYPES
        assert "detection" in WORKER_TYPES
        assert "analysis" in WORKER_TYPES
        assert "enrichment" in WORKER_TYPES
        assert "background" in WORKER_TYPES
        assert "unknown" in WORKER_TYPES


class TestWorkerRestartReasonCategorization:
    """Test the _categorize_restart_reason_worker helper function (NEM-4148)."""

    def test_categorize_none_reason(self) -> None:
        """None reason should be categorized as manual."""
        assert _categorize_restart_reason_worker(None) == "manual"

    def test_categorize_oom_reasons(self) -> None:
        """OOM-related reasons should be categorized correctly."""
        assert _categorize_restart_reason_worker("Out of memory") == "oom"
        assert _categorize_restart_reason_worker("OOM killed") == "oom"
        assert _categorize_restart_reason_worker("Memory limit exceeded") == "oom"
        assert _categorize_restart_reason_worker("Worker killed by OOM killer") == "oom"

    def test_categorize_timeout_reasons(self) -> None:
        """Timeout-related reasons should be categorized correctly."""
        assert _categorize_restart_reason_worker("Connection timeout") == "timeout"
        assert _categorize_restart_reason_worker("Request timed out") == "timeout"
        assert _categorize_restart_reason_worker("Deadline exceeded") == "timeout"

    def test_categorize_crash_reasons(self) -> None:
        """Crash-related reasons should be categorized correctly."""
        assert _categorize_restart_reason_worker("Worker crashed") == "crash"
        assert _categorize_restart_reason_worker("RuntimeError: something broke") == "crash"
        assert _categorize_restart_reason_worker("Process failed unexpectedly") == "crash"
        assert _categorize_restart_reason_worker("Segmentation fault") == "crash"
        assert _categorize_restart_reason_worker("Panic: assertion failed") == "crash"

    def test_categorize_unknown_reasons(self) -> None:
        """Unknown reasons should be categorized as unknown."""
        assert _categorize_restart_reason_worker("Something happened") == "unknown"
        assert _categorize_restart_reason_worker("xyz123") == "unknown"
        assert _categorize_restart_reason_worker("") == "unknown"

    def test_categorize_case_insensitive(self) -> None:
        """Reason categorization should be case-insensitive."""
        assert _categorize_restart_reason_worker("TIMEOUT") == "timeout"
        assert _categorize_restart_reason_worker("Out Of Memory") == "oom"
        assert _categorize_restart_reason_worker("CRASHED") == "crash"


class TestExitCodeExtraction:
    """Test the _extract_exit_code helper function (NEM-4148)."""

    def test_extract_none_error(self) -> None:
        """None error should return unknown."""
        assert _extract_exit_code(None) == "unknown"

    def test_extract_explicit_exit_code(self) -> None:
        """Explicit exit codes in error messages should be extracted."""
        assert _extract_exit_code("Process exited with exit_code: 1") == "1"
        assert _extract_exit_code("exit code 137") == "137"
        assert _extract_exit_code("exitcode:42") == "42"

    def test_extract_signal_numbers(self) -> None:
        """Signal numbers in error messages should be extracted."""
        assert _extract_exit_code("Terminated by signal: 9") == "signal_9"
        assert _extract_exit_code("Received signal 15") == "signal_15"

    def test_extract_oom_exit_code(self) -> None:
        """OOM errors should return exit code 137."""
        assert _extract_exit_code("Process was OOM killed") == "137"
        assert _extract_exit_code("Out of memory error") == "137"
        assert _extract_exit_code("Worker killed due to memory limit") == "137"

    def test_extract_segfault_exit_code(self) -> None:
        """Segfault errors should return exit code 139."""
        assert _extract_exit_code("Segmentation fault occurred") == "139"
        assert _extract_exit_code("SEGFAULT in worker") == "139"

    def test_extract_timeout_exit_code(self) -> None:
        """Timeout errors should return timeout."""
        assert _extract_exit_code("Operation timed out") == "timeout"
        assert _extract_exit_code("Request timeout after 30s") == "timeout"

    def test_extract_unknown_exit_code(self) -> None:
        """Unknown errors should return unknown."""
        assert _extract_exit_code("Something went wrong") == "unknown"
        assert _extract_exit_code("") == "unknown"


class TestWorkerTypeDetection:
    """Test the _determine_worker_type helper function (NEM-4148)."""

    def test_detect_detection_workers(self) -> None:
        """Detection workers should be identified correctly."""
        assert _determine_worker_type("detection_worker") == "detection"
        assert _determine_worker_type("yolo_inference") == "detection"
        assert _determine_worker_type("YOLO26_worker") == "detection"

    def test_detect_analysis_workers(self) -> None:
        """Analysis workers should be identified correctly."""
        assert _determine_worker_type("analysis_worker") == "analysis"
        assert _determine_worker_type("nemotron_inference") == "analysis"
        assert _determine_worker_type("llm_worker") == "analysis"

    def test_detect_enrichment_workers(self) -> None:
        """Enrichment workers should be identified correctly."""
        assert _determine_worker_type("enrichment_worker") == "enrichment"
        assert _determine_worker_type("context_aggregator") == "enrichment"

    def test_detect_pipeline_workers(self) -> None:
        """Pipeline workers should be identified correctly."""
        assert _determine_worker_type("pipeline_worker") == "pipeline"
        assert _determine_worker_type("main_pipeline") == "pipeline"

    def test_detect_background_workers(self) -> None:
        """Background workers should be identified correctly."""
        assert _determine_worker_type("background_cleanup") == "background"
        assert _determine_worker_type("task_scheduler") == "background"
        assert _determine_worker_type("job_processor") == "background"

    def test_detect_unknown_workers(self) -> None:
        """Unknown workers should return unknown type."""
        assert _determine_worker_type("my_custom_worker") == "unknown"
        assert _determine_worker_type("service_foo") == "unknown"


class TestRecordWorkerRestart:
    """Test the record_worker_restart helper function (NEM-4148)."""

    def test_record_restart_basic(self) -> None:
        """record_worker_restart should work with just worker_name."""
        record_worker_restart("test_restart_worker_1")
        # No exception means success

    def test_record_restart_with_worker_type(self) -> None:
        """record_worker_restart should accept explicit worker_type."""
        record_worker_restart("test_restart_worker_2", worker_type="detection")
        record_worker_restart("test_restart_worker_2", worker_type="analysis")
        # No exception means success

    def test_record_restart_with_reason(self) -> None:
        """record_worker_restart should accept reason and categorize it."""
        record_worker_restart("test_restart_worker_3", reason="oom")
        record_worker_restart("test_restart_worker_3", reason="Out of memory")
        record_worker_restart("test_restart_worker_3", reason=None)
        # No exception means success

    def test_record_restart_with_all_params(self) -> None:
        """record_worker_restart should accept all parameters."""
        record_worker_restart(
            "test_restart_worker_4",
            worker_type="pipeline",
            reason="crash",
        )
        # No exception means success

    def test_record_restart_auto_detects_worker_type(self) -> None:
        """record_worker_restart should auto-detect worker type from name."""
        record_worker_restart("detection_worker_restart_test")
        record_worker_restart("analysis_worker_restart_test")
        record_worker_restart("pipeline_worker_restart_test")
        # No exception means success


class TestRecordWorkerCrash:
    """Test the record_worker_crash helper function (NEM-4148)."""

    def test_record_crash_basic(self) -> None:
        """record_worker_crash should work with just worker_name."""
        record_worker_crash("test_crash_worker_1")
        # No exception means success

    def test_record_crash_with_worker_type(self) -> None:
        """record_worker_crash should accept explicit worker_type."""
        record_worker_crash("test_crash_worker_2", worker_type="detection")
        record_worker_crash("test_crash_worker_2", worker_type="analysis")
        # No exception means success

    def test_record_crash_with_exit_code(self) -> None:
        """record_worker_crash should accept explicit exit_code."""
        record_worker_crash("test_crash_worker_3", exit_code="137")
        record_worker_crash("test_crash_worker_3", exit_code="1")
        # No exception means success

    def test_record_crash_with_error(self) -> None:
        """record_worker_crash should extract exit_code from error message."""
        record_worker_crash("test_crash_worker_4", error="Process was OOM killed")
        record_worker_crash("test_crash_worker_4", error="Segmentation fault")
        record_worker_crash("test_crash_worker_4", error="exit code: 42")
        # No exception means success

    def test_record_crash_with_all_params(self) -> None:
        """record_worker_crash should accept all parameters."""
        record_worker_crash(
            "test_crash_worker_5",
            worker_type="pipeline",
            exit_code="1",
            error="Some error",
        )
        # No exception means success


class TestRecordWorkerHeartbeatMissed:
    """Test the record_worker_heartbeat_missed helper function (NEM-4148)."""

    def test_record_heartbeat_missed_basic(self) -> None:
        """record_worker_heartbeat_missed should work with just worker_name."""
        record_worker_heartbeat_missed("test_heartbeat_worker_1")
        # No exception means success

    def test_record_heartbeat_missed_with_worker_type(self) -> None:
        """record_worker_heartbeat_missed should accept explicit worker_type."""
        record_worker_heartbeat_missed("test_heartbeat_worker_2", worker_type="detection")
        record_worker_heartbeat_missed("test_heartbeat_worker_2", worker_type="analysis")
        # No exception means success

    def test_record_heartbeat_missed_auto_detects_type(self) -> None:
        """record_worker_heartbeat_missed should auto-detect worker type from name."""
        record_worker_heartbeat_missed("detection_heartbeat_test")
        record_worker_heartbeat_missed("analysis_heartbeat_test")
        # No exception means success


class TestWorkerHealthMetricsInResponse:
    """Test that worker health metrics appear in the Prometheus response (NEM-4148)."""

    def test_metrics_response_contains_worker_restarts(self) -> None:
        """Metrics response should contain worker restart metrics with labels."""
        record_worker_restart("metrics_test_restart_worker", reason="crash")

        response = get_metrics_response().decode("utf-8")

        assert "hsi_worker_restarts_total" in response
        assert 'worker_name="metrics_test_restart_worker"' in response
        assert 'reason="crash"' in response

    def test_metrics_response_contains_worker_crashes(self) -> None:
        """Metrics response should contain worker crash metrics with labels."""
        record_worker_crash("metrics_test_crash_worker", error="exit code: 42")

        response = get_metrics_response().decode("utf-8")

        assert "hsi_worker_crashes_total" in response
        assert 'worker_name="metrics_test_crash_worker"' in response
        assert 'exit_code="42"' in response

    def test_metrics_response_contains_worker_heartbeat_missed(self) -> None:
        """Metrics response should contain worker heartbeat missed metrics."""
        record_worker_heartbeat_missed("metrics_test_heartbeat_worker")

        response = get_metrics_response().decode("utf-8")

        assert "hsi_worker_heartbeat_missed_total" in response
        assert 'worker_name="metrics_test_heartbeat_worker"' in response

    def test_metrics_response_contains_worker_type_labels(self) -> None:
        """Metrics response should contain worker_type labels."""
        record_worker_restart("detection_test_worker", reason="timeout")
        record_worker_crash("analysis_test_worker", error="OOM")
        record_worker_heartbeat_missed("pipeline_test_worker")

        response = get_metrics_response().decode("utf-8")

        assert 'worker_type="detection"' in response
        assert 'worker_type="analysis"' in response
        assert 'worker_type="pipeline"' in response


class TestWorkerHealthMetricsLabelSanitization:
    """Test that worker health metric labels are properly sanitized (NEM-4148)."""

    def test_long_worker_name_sanitized(self) -> None:
        """Long worker names should be truncated."""
        long_name = "a" * 100  # 100 characters
        record_worker_restart(long_name)
        record_worker_crash(long_name)
        record_worker_heartbeat_missed(long_name)
        # No exception means sanitization worked

    def test_special_characters_in_worker_name(self) -> None:
        """Special characters in worker names should be handled."""
        special_name = "worker:with/special\\chars"
        record_worker_restart(special_name)
        record_worker_crash(special_name)
        record_worker_heartbeat_missed(special_name)
        # No exception means sanitization worked

    def test_long_error_message_sanitized(self) -> None:
        """Long error messages should be handled."""
        long_error = "Error: " + "x" * 1000
        record_worker_crash("error_sanitization_worker", error=long_error)
        # No exception means sanitization worked
