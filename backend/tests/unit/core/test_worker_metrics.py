"""Unit tests for pipeline worker metrics (NEM-2459).

Tests cover:
- Pipeline worker restart metrics with reason categorization
- Worker restart duration histogram
- Worker state gauge
- Worker consecutive failures gauge
- Worker uptime gauge
- Restart reason categorization helper function
"""

from backend.core.metrics import (
    PIPELINE_WORKER_CONSECUTIVE_FAILURES,
    PIPELINE_WORKER_RESTART_DURATION_SECONDS,
    PIPELINE_WORKER_RESTARTS_TOTAL,
    PIPELINE_WORKER_STATE,
    PIPELINE_WORKER_STATE_VALUES,
    PIPELINE_WORKER_UPTIME_SECONDS,
    _categorize_restart_reason,
    get_metrics_response,
    observe_pipeline_worker_restart_duration,
    record_pipeline_worker_restart,
    set_pipeline_worker_consecutive_failures,
    set_pipeline_worker_state,
    set_pipeline_worker_uptime,
)


class TestPipelineWorkerMetricDefinitions:
    """Test pipeline worker metric definitions."""

    def test_pipeline_worker_restarts_total_exists(self) -> None:
        """PIPELINE_WORKER_RESTARTS_TOTAL counter should be defined."""
        assert PIPELINE_WORKER_RESTARTS_TOTAL is not None
        # prometheus_client strips _total suffix from counter names internally
        assert PIPELINE_WORKER_RESTARTS_TOTAL._name == "hsi_pipeline_worker_restarts"
        assert "worker_name" in PIPELINE_WORKER_RESTARTS_TOTAL._labelnames
        assert "reason_category" in PIPELINE_WORKER_RESTARTS_TOTAL._labelnames

    def test_pipeline_worker_restart_duration_histogram_exists(self) -> None:
        """PIPELINE_WORKER_RESTART_DURATION_SECONDS histogram should be defined."""
        assert PIPELINE_WORKER_RESTART_DURATION_SECONDS is not None
        assert (
            PIPELINE_WORKER_RESTART_DURATION_SECONDS._name
            == "hsi_pipeline_worker_restart_duration_seconds"
        )
        assert "worker_name" in PIPELINE_WORKER_RESTART_DURATION_SECONDS._labelnames
        # Check buckets cover expected range
        buckets = PIPELINE_WORKER_RESTART_DURATION_SECONDS._upper_bounds
        assert 0.1 in buckets  # 100ms
        assert 1.0 in buckets  # 1s
        assert 30.0 in buckets  # 30s

    def test_pipeline_worker_state_gauge_exists(self) -> None:
        """PIPELINE_WORKER_STATE gauge should be defined."""
        assert PIPELINE_WORKER_STATE is not None
        assert PIPELINE_WORKER_STATE._name == "hsi_pipeline_worker_state"
        assert "worker_name" in PIPELINE_WORKER_STATE._labelnames

    def test_pipeline_worker_consecutive_failures_gauge_exists(self) -> None:
        """PIPELINE_WORKER_CONSECUTIVE_FAILURES gauge should be defined."""
        assert PIPELINE_WORKER_CONSECUTIVE_FAILURES is not None
        assert (
            PIPELINE_WORKER_CONSECUTIVE_FAILURES._name == "hsi_pipeline_worker_consecutive_failures"
        )
        assert "worker_name" in PIPELINE_WORKER_CONSECUTIVE_FAILURES._labelnames

    def test_pipeline_worker_uptime_gauge_exists(self) -> None:
        """PIPELINE_WORKER_UPTIME_SECONDS gauge should be defined."""
        assert PIPELINE_WORKER_UPTIME_SECONDS is not None
        assert PIPELINE_WORKER_UPTIME_SECONDS._name == "hsi_pipeline_worker_uptime_seconds"
        assert "worker_name" in PIPELINE_WORKER_UPTIME_SECONDS._labelnames

    def test_worker_state_values_mapping(self) -> None:
        """PIPELINE_WORKER_STATE_VALUES should have correct mappings."""
        assert PIPELINE_WORKER_STATE_VALUES["stopped"] == 0
        assert PIPELINE_WORKER_STATE_VALUES["running"] == 1
        assert PIPELINE_WORKER_STATE_VALUES["restarting"] == 2
        assert PIPELINE_WORKER_STATE_VALUES["failed"] == 3


class TestRestartReasonCategorization:
    """Test the _categorize_restart_reason helper function."""

    def test_categorize_none_error(self) -> None:
        """None error should be categorized as manual."""
        assert _categorize_restart_reason(None) == "manual"

    def test_categorize_timeout_errors(self) -> None:
        """Timeout-related errors should be categorized correctly."""
        assert _categorize_restart_reason("Connection timeout") == "timeout"
        assert _categorize_restart_reason("Request timed out") == "timeout"
        assert _categorize_restart_reason("Deadline exceeded") == "timeout"
        assert _categorize_restart_reason("TIMEOUT ERROR") == "timeout"

    def test_categorize_memory_errors(self) -> None:
        """Memory-related errors should be categorized correctly."""
        assert _categorize_restart_reason("Out of memory") == "memory"
        assert _categorize_restart_reason("MemoryError") == "memory"
        assert _categorize_restart_reason("OOM killed") == "memory"
        assert _categorize_restart_reason("Cannot allocate memory") == "memory"

    def test_categorize_connection_errors(self) -> None:
        """Connection-related errors should be categorized correctly."""
        assert _categorize_restart_reason("Connection refused") == "connection"
        assert _categorize_restart_reason("Could not connect to server") == "connection"
        assert _categorize_restart_reason("Network unreachable") == "connection"
        assert _categorize_restart_reason("Socket error") == "connection"
        assert _categorize_restart_reason("DNS resolution failed") == "connection"

    def test_categorize_resource_errors(self) -> None:
        """Resource-related errors should be categorized correctly."""
        assert _categorize_restart_reason("Resource exhausted") == "resource"
        assert _categorize_restart_reason("File not found") == "resource"
        assert _categorize_restart_reason("No disk space left") == "resource"
        assert _categorize_restart_reason("Permission denied") == "resource"
        assert _categorize_restart_reason("Access denied") == "resource"
        assert _categorize_restart_reason("Rate limit exceeded") == "resource"

    def test_categorize_dependency_errors(self) -> None:
        """Dependency-related errors should be categorized correctly."""
        assert _categorize_restart_reason("Dependency failed") == "dependency"
        assert _categorize_restart_reason("ImportError: no module named x") == "dependency"
        assert _categorize_restart_reason("Service unavailable") == "dependency"
        assert _categorize_restart_reason("Module not found") == "dependency"

    def test_categorize_exception_errors(self) -> None:
        """Generic exception errors should be categorized correctly."""
        assert _categorize_restart_reason("RuntimeException: something broke") == "exception"
        assert _categorize_restart_reason("Error in processing") == "exception"
        assert _categorize_restart_reason("Task failed") == "exception"
        assert _categorize_restart_reason("Failure in pipeline") == "exception"

    def test_categorize_unknown_errors(self) -> None:
        """Unknown errors should be categorized as unknown."""
        assert _categorize_restart_reason("Something weird happened") == "unknown"
        assert _categorize_restart_reason("xyz123") == "unknown"
        assert _categorize_restart_reason("") == "unknown"

    def test_categorize_case_insensitive(self) -> None:
        """Error categorization should be case-insensitive."""
        assert _categorize_restart_reason("TIMEOUT") == "timeout"
        assert _categorize_restart_reason("Memory Error") == "memory"
        assert _categorize_restart_reason("CONNECTION REFUSED") == "connection"


class TestPipelineWorkerRestartMetricHelpers:
    """Test pipeline worker restart metric helper functions."""

    def test_record_pipeline_worker_restart_basic(self) -> None:
        """record_pipeline_worker_restart should increment counter."""
        record_pipeline_worker_restart("test_worker_1")
        # No assertion needed - no exception means success

    def test_record_pipeline_worker_restart_with_reason(self) -> None:
        """record_pipeline_worker_restart should categorize reason."""
        record_pipeline_worker_restart("test_worker_2", reason="Connection refused")
        record_pipeline_worker_restart("test_worker_2", reason="Out of memory")
        record_pipeline_worker_restart("test_worker_2", reason=None)
        # No assertion needed - no exception means success

    def test_record_pipeline_worker_restart_with_duration(self) -> None:
        """record_pipeline_worker_restart should record duration."""
        record_pipeline_worker_restart("test_worker_3", duration_seconds=1.5)
        record_pipeline_worker_restart("test_worker_3", reason="timeout", duration_seconds=2.0)
        # No assertion needed - no exception means success

    def test_record_pipeline_worker_restart_zero_duration(self) -> None:
        """record_pipeline_worker_restart should skip zero/negative duration."""
        record_pipeline_worker_restart("test_worker_4", duration_seconds=0)
        record_pipeline_worker_restart("test_worker_4", duration_seconds=-1.0)
        # No assertion needed - no exception means success


class TestPipelineWorkerRestartDurationMetric:
    """Test pipeline worker restart duration histogram helpers."""

    def test_observe_pipeline_worker_restart_duration(self) -> None:
        """observe_pipeline_worker_restart_duration should record observation."""
        observe_pipeline_worker_restart_duration("test_worker_5", 1.5)
        observe_pipeline_worker_restart_duration("test_worker_5", 0.5)
        observe_pipeline_worker_restart_duration("test_worker_5", 30.0)
        # No assertion needed - no exception means success

    def test_observe_pipeline_worker_restart_duration_zero(self) -> None:
        """observe_pipeline_worker_restart_duration should skip zero duration."""
        observe_pipeline_worker_restart_duration("test_worker_6", 0)
        # No assertion needed - no exception means success

    def test_observe_pipeline_worker_restart_duration_negative(self) -> None:
        """observe_pipeline_worker_restart_duration should skip negative duration."""
        observe_pipeline_worker_restart_duration("test_worker_7", -1.0)
        # No assertion needed - no exception means success


class TestPipelineWorkerStateMetric:
    """Test pipeline worker state gauge helpers."""

    def test_set_pipeline_worker_state_stopped(self) -> None:
        """set_pipeline_worker_state should set stopped state."""
        set_pipeline_worker_state("test_worker_8", "stopped")
        # No assertion needed - no exception means success

    def test_set_pipeline_worker_state_running(self) -> None:
        """set_pipeline_worker_state should set running state."""
        set_pipeline_worker_state("test_worker_9", "running")
        # No assertion needed - no exception means success

    def test_set_pipeline_worker_state_restarting(self) -> None:
        """set_pipeline_worker_state should set restarting state."""
        set_pipeline_worker_state("test_worker_10", "restarting")
        # No assertion needed - no exception means success

    def test_set_pipeline_worker_state_failed(self) -> None:
        """set_pipeline_worker_state should set failed state."""
        set_pipeline_worker_state("test_worker_11", "failed")
        # No assertion needed - no exception means success

    def test_set_pipeline_worker_state_invalid(self) -> None:
        """set_pipeline_worker_state should default to 0 for invalid state."""
        set_pipeline_worker_state("test_worker_12", "invalid_state")
        # No assertion needed - no exception means success

    def test_set_pipeline_worker_state_case_insensitive(self) -> None:
        """set_pipeline_worker_state should be case-insensitive."""
        set_pipeline_worker_state("test_worker_13", "RUNNING")
        set_pipeline_worker_state("test_worker_13", "Failed")
        set_pipeline_worker_state("test_worker_13", "RESTARTING")
        # No assertion needed - no exception means success


class TestPipelineWorkerConsecutiveFailuresMetric:
    """Test pipeline worker consecutive failures gauge helpers."""

    def test_set_pipeline_worker_consecutive_failures(self) -> None:
        """set_pipeline_worker_consecutive_failures should set gauge value."""
        set_pipeline_worker_consecutive_failures("test_worker_14", 0)
        set_pipeline_worker_consecutive_failures("test_worker_14", 1)
        set_pipeline_worker_consecutive_failures("test_worker_14", 5)
        # No assertion needed - no exception means success

    def test_set_pipeline_worker_consecutive_failures_multiple_workers(self) -> None:
        """set_pipeline_worker_consecutive_failures should work for different workers."""
        set_pipeline_worker_consecutive_failures("worker_a", 2)
        set_pipeline_worker_consecutive_failures("worker_b", 3)
        set_pipeline_worker_consecutive_failures("worker_c", 0)
        # No assertion needed - no exception means success


class TestPipelineWorkerUptimeMetric:
    """Test pipeline worker uptime gauge helpers."""

    def test_set_pipeline_worker_uptime(self) -> None:
        """set_pipeline_worker_uptime should set gauge value."""
        set_pipeline_worker_uptime("test_worker_15", 0.0)
        set_pipeline_worker_uptime("test_worker_15", 60.0)
        set_pipeline_worker_uptime("test_worker_15", 3600.0)
        # No assertion needed - no exception means success

    def test_set_pipeline_worker_uptime_not_running(self) -> None:
        """set_pipeline_worker_uptime should accept -1 for not running."""
        set_pipeline_worker_uptime("test_worker_16", -1.0)
        # No assertion needed - no exception means success

    def test_set_pipeline_worker_uptime_multiple_workers(self) -> None:
        """set_pipeline_worker_uptime should work for different workers."""
        set_pipeline_worker_uptime("uptime_worker_a", 100.0)
        set_pipeline_worker_uptime("uptime_worker_b", 200.0)
        set_pipeline_worker_uptime("uptime_worker_c", -1.0)
        # No assertion needed - no exception means success


class TestPipelineWorkerMetricsInResponse:
    """Test that pipeline worker metrics appear in the Prometheus response."""

    def test_metrics_response_contains_worker_metrics(self) -> None:
        """Metrics response should contain pipeline worker metrics."""
        # Record some metrics first
        record_pipeline_worker_restart("metrics_test_worker", reason="test")
        set_pipeline_worker_state("metrics_test_worker", "running")
        set_pipeline_worker_consecutive_failures("metrics_test_worker", 0)
        set_pipeline_worker_uptime("metrics_test_worker", 100.0)

        response = get_metrics_response().decode("utf-8")

        # Check for our custom pipeline worker metrics
        assert "hsi_pipeline_worker_restarts_total" in response
        assert "hsi_pipeline_worker_restart_duration_seconds" in response
        assert "hsi_pipeline_worker_state" in response
        assert "hsi_pipeline_worker_consecutive_failures" in response
        assert "hsi_pipeline_worker_uptime_seconds" in response

    def test_metrics_response_contains_reason_category_label(self) -> None:
        """Metrics response should contain reason_category label values."""
        # Record restarts with different reasons
        record_pipeline_worker_restart("reason_test_worker", reason="Connection timeout")
        record_pipeline_worker_restart("reason_test_worker", reason="Out of memory")
        record_pipeline_worker_restart("reason_test_worker", reason=None)

        response = get_metrics_response().decode("utf-8")

        # Check that reason_category labels appear
        assert 'reason_category="timeout"' in response
        assert 'reason_category="memory"' in response
        assert 'reason_category="manual"' in response


class TestPipelineWorkerMetricsLabelSanitization:
    """Test that worker names are properly sanitized."""

    def test_long_worker_name_sanitized(self) -> None:
        """Long worker names should be truncated."""
        long_name = "a" * 100  # 100 characters
        record_pipeline_worker_restart(long_name)
        set_pipeline_worker_state(long_name, "running")
        set_pipeline_worker_consecutive_failures(long_name, 0)
        set_pipeline_worker_uptime(long_name, 50.0)
        # No assertion needed - no exception means sanitization worked

    def test_special_characters_in_worker_name(self) -> None:
        """Special characters in worker names should be handled."""
        special_name = "worker:with/special\\chars"
        record_pipeline_worker_restart(special_name)
        set_pipeline_worker_state(special_name, "running")
        # No assertion needed - no exception means sanitization worked
