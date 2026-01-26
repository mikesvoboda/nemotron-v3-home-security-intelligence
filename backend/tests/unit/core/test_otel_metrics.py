"""Tests for OpenTelemetry metrics module.

NEM-3798: Tests for AI model latency histogram metrics.
NEM-3799: Tests for circuit breaker state tracking metrics.
"""

from unittest.mock import MagicMock, patch


class TestAIModelLatencyBuckets:
    """Tests for AI model latency bucket definitions."""

    def test_detection_latency_buckets_are_ascending(self) -> None:
        """Detection latency buckets should be in ascending order."""
        from backend.core.otel_metrics import DETECTION_LATENCY_BUCKETS

        for i in range(1, len(DETECTION_LATENCY_BUCKETS)):
            assert DETECTION_LATENCY_BUCKETS[i] > DETECTION_LATENCY_BUCKETS[i - 1]

    def test_detection_latency_buckets_cover_expected_range(self) -> None:
        """Detection latency buckets should cover 1ms to 1000ms."""
        from backend.core.otel_metrics import DETECTION_LATENCY_BUCKETS

        assert DETECTION_LATENCY_BUCKETS[0] <= 5.0  # Minimum bucket
        assert DETECTION_LATENCY_BUCKETS[-1] >= 500.0  # Maximum bucket

    def test_nemotron_latency_buckets_are_ascending(self) -> None:
        """Nemotron latency buckets should be in ascending order."""
        from backend.core.otel_metrics import NEMOTRON_LATENCY_BUCKETS

        for i in range(1, len(NEMOTRON_LATENCY_BUCKETS)):
            assert NEMOTRON_LATENCY_BUCKETS[i] > NEMOTRON_LATENCY_BUCKETS[i - 1]

    def test_nemotron_latency_buckets_cover_expected_range(self) -> None:
        """Nemotron latency buckets should cover 100ms to 10000ms."""
        from backend.core.otel_metrics import NEMOTRON_LATENCY_BUCKETS

        assert NEMOTRON_LATENCY_BUCKETS[0] <= 100.0  # Minimum bucket
        assert NEMOTRON_LATENCY_BUCKETS[-1] >= 5000.0  # Maximum bucket

    def test_florence_latency_buckets_are_ascending(self) -> None:
        """Florence latency buckets should be in ascending order."""
        from backend.core.otel_metrics import FLORENCE_LATENCY_BUCKETS

        for i in range(1, len(FLORENCE_LATENCY_BUCKETS)):
            assert FLORENCE_LATENCY_BUCKETS[i] > FLORENCE_LATENCY_BUCKETS[i - 1]

    def test_florence_latency_buckets_cover_expected_range(self) -> None:
        """Florence latency buckets should cover 50ms to 3000ms."""
        from backend.core.otel_metrics import FLORENCE_LATENCY_BUCKETS

        assert FLORENCE_LATENCY_BUCKETS[0] <= 100.0  # Minimum bucket
        assert FLORENCE_LATENCY_BUCKETS[-1] >= 2000.0  # Maximum bucket

    def test_pipeline_latency_buckets_are_ascending(self) -> None:
        """Pipeline latency buckets should be in ascending order."""
        from backend.core.otel_metrics import PIPELINE_LATENCY_BUCKETS

        for i in range(1, len(PIPELINE_LATENCY_BUCKETS)):
            assert PIPELINE_LATENCY_BUCKETS[i] > PIPELINE_LATENCY_BUCKETS[i - 1]

    def test_batch_processing_buckets_are_ascending(self) -> None:
        """Batch processing buckets should be in ascending order."""
        from backend.core.otel_metrics import BATCH_PROCESSING_BUCKETS

        for i in range(1, len(BATCH_PROCESSING_BUCKETS)):
            assert BATCH_PROCESSING_BUCKETS[i] > BATCH_PROCESSING_BUCKETS[i - 1]


class TestRecordDetectionLatency:
    """Tests for record_detection_latency function."""

    def test_record_detection_latency_when_not_initialized(self) -> None:
        """Should not raise when metrics not initialized."""
        from backend.core.otel_metrics import (
            record_detection_latency,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        # Should not raise
        record_detection_latency(
            latency_ms=45.2,
            model_version="yolo26-l",
            batch_size=1,
            gpu_id="0",
        )

    def test_record_detection_latency_with_initialized_metrics(self) -> None:
        """Should record latency when metrics are initialized."""
        from backend.core.otel_metrics import (
            record_detection_latency,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        # Mock the histogram
        mock_histogram = MagicMock()

        from backend.core import otel_metrics

        otel_metrics._is_initialized = True
        otel_metrics._detection_latency_histogram = mock_histogram

        record_detection_latency(
            latency_ms=45.2,
            model_version="yolo26-l",
            batch_size=1,
            gpu_id="0",
        )

        mock_histogram.record.assert_called_once_with(
            45.2,
            attributes={
                "model.version": "yolo26-l",
                "batch.size": 1,
                "gpu.id": "0",
            },
        )

        # Cleanup
        reset_otel_metrics_for_testing()

    def test_record_detection_latency_default_attributes(self) -> None:
        """Should use default attributes when not specified."""
        from backend.core.otel_metrics import (
            record_detection_latency,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        mock_histogram = MagicMock()

        from backend.core import otel_metrics

        otel_metrics._is_initialized = True
        otel_metrics._detection_latency_histogram = mock_histogram

        record_detection_latency(latency_ms=100.0)

        mock_histogram.record.assert_called_once()
        call_args = mock_histogram.record.call_args
        assert call_args[0][0] == 100.0
        assert call_args[1]["attributes"]["model.version"] == "yolo26-l"
        assert call_args[1]["attributes"]["batch.size"] == 1
        assert call_args[1]["attributes"]["gpu.id"] == "0"

        reset_otel_metrics_for_testing()


class TestRecordNemotronLatency:
    """Tests for record_nemotron_latency function."""

    def test_record_nemotron_latency_when_not_initialized(self) -> None:
        """Should not raise when metrics not initialized."""
        from backend.core.otel_metrics import (
            record_nemotron_latency,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        # Should not raise
        record_nemotron_latency(
            latency_ms=1250.5,
            model_version="nemotron-mini-4b-instruct",
            batch_size=1,
            gpu_id="1",
        )

    def test_record_nemotron_latency_with_initialized_metrics(self) -> None:
        """Should record latency when metrics are initialized."""
        from backend.core.otel_metrics import (
            record_nemotron_latency,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        mock_histogram = MagicMock()

        from backend.core import otel_metrics

        otel_metrics._is_initialized = True
        otel_metrics._nemotron_latency_histogram = mock_histogram

        record_nemotron_latency(
            latency_ms=1250.5,
            model_version="nemotron-mini-4b-instruct",
            batch_size=1,
            gpu_id="1",
        )

        mock_histogram.record.assert_called_once()
        call_args = mock_histogram.record.call_args
        assert call_args[0][0] == 1250.5
        assert call_args[1]["attributes"]["model.version"] == "nemotron-mini-4b-instruct"
        assert call_args[1]["attributes"]["batch.size"] == 1
        assert call_args[1]["attributes"]["gpu.id"] == "1"

        reset_otel_metrics_for_testing()

    def test_record_nemotron_latency_with_tokens(self) -> None:
        """Should include tokens_generated when specified."""
        from backend.core.otel_metrics import (
            record_nemotron_latency,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        mock_histogram = MagicMock()

        from backend.core import otel_metrics

        otel_metrics._is_initialized = True
        otel_metrics._nemotron_latency_histogram = mock_histogram

        record_nemotron_latency(
            latency_ms=1500.0,
            model_version="nemotron-mini-4b-instruct",
            tokens_generated=150,
        )

        mock_histogram.record.assert_called_once()
        call_args = mock_histogram.record.call_args
        assert call_args[1]["attributes"]["tokens.generated"] == 150

        reset_otel_metrics_for_testing()


class TestRecordFlorenceLatency:
    """Tests for record_florence_latency function."""

    def test_record_florence_latency_when_not_initialized(self) -> None:
        """Should not raise when metrics not initialized."""
        from backend.core.otel_metrics import (
            record_florence_latency,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        # Should not raise
        record_florence_latency(
            latency_ms=320.5,
            model_version="florence-2-large",
            task_type="caption",
        )

    def test_record_florence_latency_with_initialized_metrics(self) -> None:
        """Should record latency when metrics are initialized."""
        from backend.core.otel_metrics import (
            record_florence_latency,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        mock_histogram = MagicMock()

        from backend.core import otel_metrics

        otel_metrics._is_initialized = True
        otel_metrics._florence_latency_histogram = mock_histogram

        record_florence_latency(
            latency_ms=320.5,
            model_version="florence-2-large",
            batch_size=1,
            gpu_id="0",
            task_type="ocr",
        )

        mock_histogram.record.assert_called_once_with(
            320.5,
            attributes={
                "model.version": "florence-2-large",
                "batch.size": 1,
                "gpu.id": "0",
                "task.type": "ocr",
            },
        )

        reset_otel_metrics_for_testing()


class TestRecordPipelineLatency:
    """Tests for record_pipeline_latency function."""

    def test_record_pipeline_latency_when_not_initialized(self) -> None:
        """Should not raise when metrics not initialized."""
        from backend.core.otel_metrics import (
            record_pipeline_latency,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        # Should not raise
        record_pipeline_latency(
            latency_ms=3500.0,
            camera_id="front_door",
            pipeline_stage="full",
        )

    def test_record_pipeline_latency_with_initialized_metrics(self) -> None:
        """Should record latency when metrics are initialized."""
        from backend.core.otel_metrics import (
            record_pipeline_latency,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        mock_histogram = MagicMock()

        from backend.core import otel_metrics

        otel_metrics._is_initialized = True
        otel_metrics._pipeline_latency_histogram = mock_histogram

        record_pipeline_latency(
            latency_ms=3500.0,
            camera_id="front_door",
            pipeline_stage="full",
            detection_count=5,
        )

        mock_histogram.record.assert_called_once_with(
            3500.0,
            attributes={
                "camera.id": "front_door",
                "pipeline.stage": "full",
                "detection.count": 5,
            },
        )

        reset_otel_metrics_for_testing()


class TestRecordBatchProcessingTime:
    """Tests for record_batch_processing_time function."""

    def test_record_batch_processing_time_when_not_initialized(self) -> None:
        """Should not raise when metrics not initialized."""
        from backend.core.otel_metrics import (
            record_batch_processing_time,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        # Should not raise
        record_batch_processing_time(
            processing_time_ms=150.0,
            batch_size=12,
            camera_count=3,
        )

    def test_record_batch_processing_time_with_initialized_metrics(self) -> None:
        """Should record processing time when metrics are initialized."""
        from backend.core.otel_metrics import (
            record_batch_processing_time,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        mock_histogram = MagicMock()

        from backend.core import otel_metrics

        otel_metrics._is_initialized = True
        otel_metrics._batch_processing_histogram = mock_histogram

        record_batch_processing_time(
            processing_time_ms=150.0,
            batch_size=12,
            camera_count=3,
            batch_id="batch-abc123",
        )

        mock_histogram.record.assert_called_once_with(
            150.0,
            attributes={
                "batch.size": 12,
                "camera.count": 3,
                "batch.id": "batch-abc123",
            },
        )

        reset_otel_metrics_for_testing()


class TestSetupOtelMetrics:
    """Tests for setup_otel_metrics function."""

    def test_setup_otel_metrics_returns_false_if_already_initialized(self) -> None:
        """Should return False if metrics are already initialized."""
        from backend.core.otel_metrics import (
            reset_otel_metrics_for_testing,
            setup_otel_metrics,
        )

        reset_otel_metrics_for_testing()

        from backend.core import otel_metrics

        otel_metrics._is_initialized = True

        result = setup_otel_metrics()

        assert result is False

        reset_otel_metrics_for_testing()

    def test_setup_otel_metrics_initializes_all_histograms(self) -> None:
        """Should initialize all AI model latency histograms."""
        from backend.core.otel_metrics import (
            reset_otel_metrics_for_testing,
            setup_otel_metrics,
        )

        reset_otel_metrics_for_testing()

        # Mock OpenTelemetry modules
        mock_meter = MagicMock()
        mock_histogram = MagicMock()
        mock_meter.create_histogram.return_value = mock_histogram
        mock_meter.create_gauge.return_value = MagicMock()
        mock_meter.create_counter.return_value = MagicMock()

        mock_provider = MagicMock()
        mock_metrics = MagicMock()
        mock_metrics.get_meter.return_value = mock_meter

        with (
            patch("opentelemetry.metrics.set_meter_provider"),
            patch("opentelemetry.metrics.get_meter", return_value=mock_meter),
            patch("opentelemetry.sdk.metrics.MeterProvider", return_value=mock_provider),
            patch("opentelemetry.sdk.resources.Resource"),
            patch("opentelemetry.sdk.metrics.view.View"),
            patch("opentelemetry.sdk.metrics.view.ExplicitBucketHistogramAggregation"),
        ):
            result = setup_otel_metrics()

        # Verify histograms were created
        assert mock_meter.create_histogram.call_count >= 5  # 5 AI histograms

        # Verify histogram names
        histogram_names = [call[1]["name"] for call in mock_meter.create_histogram.call_args_list]
        assert "ai.detection.latency" in histogram_names
        assert "ai.nemotron.latency" in histogram_names
        assert "ai.florence.latency" in histogram_names
        assert "ai.pipeline.latency" in histogram_names
        assert "ai.batch.processing_time" in histogram_names

        reset_otel_metrics_for_testing()


class TestIsOtelMetricsEnabled:
    """Tests for is_otel_metrics_enabled function."""

    def test_returns_false_when_not_initialized(self) -> None:
        """Should return False when metrics are not initialized."""
        from backend.core.otel_metrics import (
            is_otel_metrics_enabled,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()
        assert is_otel_metrics_enabled() is False

    def test_returns_true_when_initialized(self) -> None:
        """Should return True when metrics are initialized."""
        from backend.core.otel_metrics import (
            is_otel_metrics_enabled,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        from backend.core import otel_metrics

        otel_metrics._is_initialized = True

        assert is_otel_metrics_enabled() is True

        reset_otel_metrics_for_testing()


class TestCircuitBreakerStateValue:
    """Tests for CircuitBreakerStateValue enum."""

    def test_state_values(self) -> None:
        """Should have correct numeric values for states."""
        from backend.core.otel_metrics import CircuitBreakerStateValue

        assert CircuitBreakerStateValue.CLOSED == 0
        assert CircuitBreakerStateValue.OPEN == 1
        assert CircuitBreakerStateValue.HALF_OPEN == 2

    def test_state_values_are_int(self) -> None:
        """State values should be integers."""
        from backend.core.otel_metrics import CircuitBreakerStateValue

        assert isinstance(CircuitBreakerStateValue.CLOSED, int)
        assert isinstance(CircuitBreakerStateValue.OPEN, int)
        assert isinstance(CircuitBreakerStateValue.HALF_OPEN, int)


class TestCircuitBreakerOtelMetrics:
    """Tests for CircuitBreakerOtelMetrics dataclass."""

    def test_default_values(self) -> None:
        """Should have sensible default values."""
        from backend.core.otel_metrics import (
            CircuitBreakerOtelMetrics,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()
        metrics = CircuitBreakerOtelMetrics(name="test")

        assert metrics.name == "test"
        assert metrics.state == 0
        assert metrics.transitions_total == 0
        assert metrics.failures_total == 0
        assert metrics.successes_total == 0
        assert metrics.rejected_total == 0
        assert metrics.time_in_current_state_seconds == 0.0

        reset_otel_metrics_for_testing()

    def test_custom_values(self) -> None:
        """Should accept custom values."""
        from backend.core.otel_metrics import (
            CircuitBreakerOtelMetrics,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()
        metrics = CircuitBreakerOtelMetrics(
            name="custom",
            state=1,
            transitions_total=5,
            failures_total=10,
            successes_total=100,
            rejected_total=3,
            time_in_current_state_seconds=45.5,
        )

        assert metrics.name == "custom"
        assert metrics.state == 1
        assert metrics.transitions_total == 5
        assert metrics.failures_total == 10
        assert metrics.successes_total == 100
        assert metrics.rejected_total == 3
        assert metrics.time_in_current_state_seconds == 45.5

        reset_otel_metrics_for_testing()


class TestRecordCircuitBreakerState:
    """Tests for record_circuit_breaker_state function."""

    def test_record_state_when_not_initialized(self) -> None:
        """Should not raise when metrics not initialized."""
        from backend.core.otel_metrics import (
            record_circuit_breaker_state,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        # Should not raise
        record_circuit_breaker_state("test_breaker", 1)

        reset_otel_metrics_for_testing()

    def test_record_state_with_initialized_metrics(self) -> None:
        """Should record state when metrics are initialized."""
        from backend.core.otel_metrics import (
            record_circuit_breaker_state,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        mock_gauge = MagicMock()

        from backend.core import otel_metrics

        otel_metrics._is_initialized = True
        otel_metrics._circuit_state_gauge = mock_gauge

        record_circuit_breaker_state("test_breaker", 1)

        mock_gauge.set.assert_called_with(1, {"breaker": "test_breaker"})

        reset_otel_metrics_for_testing()


class TestRecordCircuitBreakerStateChange:
    """Tests for record_circuit_breaker_state_change function."""

    def test_record_state_change_when_not_initialized(self) -> None:
        """Should not raise when metrics not initialized."""
        from backend.core.otel_metrics import (
            record_circuit_breaker_state_change,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        # Should not raise
        record_circuit_breaker_state_change("test_breaker", "closed", "open")

        reset_otel_metrics_for_testing()

    def test_record_state_change_with_initialized_metrics(self) -> None:
        """Should record state transition when metrics are initialized."""
        from backend.core.otel_metrics import (
            record_circuit_breaker_state_change,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        mock_counter = MagicMock()
        mock_gauge = MagicMock()

        from backend.core import otel_metrics

        otel_metrics._is_initialized = True
        otel_metrics._circuit_transitions_counter = mock_counter
        otel_metrics._circuit_state_gauge = mock_gauge

        record_circuit_breaker_state_change("test_breaker", "closed", "open")

        mock_counter.add.assert_called_once_with(
            1,
            {"breaker": "test_breaker", "from_state": "closed", "to_state": "open"},
        )

        reset_otel_metrics_for_testing()


class TestRecordCircuitBreakerFailure:
    """Tests for record_circuit_breaker_failure function."""

    def test_record_failure_when_not_initialized(self) -> None:
        """Should not raise when metrics not initialized."""
        from backend.core.otel_metrics import (
            record_circuit_breaker_failure,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        # Should not raise
        record_circuit_breaker_failure("test_breaker")

        reset_otel_metrics_for_testing()

    def test_record_failure_with_initialized_metrics(self) -> None:
        """Should record failure when metrics are initialized."""
        from backend.core.otel_metrics import (
            record_circuit_breaker_failure,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        mock_counter = MagicMock()

        from backend.core import otel_metrics

        otel_metrics._is_initialized = True
        otel_metrics._circuit_failures_counter = mock_counter

        record_circuit_breaker_failure("test_breaker")

        mock_counter.add.assert_called_once_with(1, {"breaker": "test_breaker"})

        reset_otel_metrics_for_testing()


class TestRecordCircuitBreakerSuccess:
    """Tests for record_circuit_breaker_success function."""

    def test_record_success_when_not_initialized(self) -> None:
        """Should not raise when metrics not initialized."""
        from backend.core.otel_metrics import (
            record_circuit_breaker_success,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        # Should not raise
        record_circuit_breaker_success("test_breaker")

        reset_otel_metrics_for_testing()

    def test_record_success_with_initialized_metrics(self) -> None:
        """Should record success when metrics are initialized."""
        from backend.core.otel_metrics import (
            record_circuit_breaker_success,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        mock_counter = MagicMock()

        from backend.core import otel_metrics

        otel_metrics._is_initialized = True
        otel_metrics._circuit_successes_counter = mock_counter

        record_circuit_breaker_success("test_breaker")

        mock_counter.add.assert_called_once_with(1, {"breaker": "test_breaker"})

        reset_otel_metrics_for_testing()


class TestRecordCircuitBreakerRejected:
    """Tests for record_circuit_breaker_rejected function."""

    def test_record_rejected_when_not_initialized(self) -> None:
        """Should not raise when metrics not initialized."""
        from backend.core.otel_metrics import (
            record_circuit_breaker_rejected,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        # Should not raise
        record_circuit_breaker_rejected("test_breaker")

        reset_otel_metrics_for_testing()

    def test_record_rejected_with_initialized_metrics(self) -> None:
        """Should record rejection when metrics are initialized."""
        from backend.core.otel_metrics import (
            record_circuit_breaker_rejected,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        mock_counter = MagicMock()

        from backend.core import otel_metrics

        otel_metrics._is_initialized = True
        otel_metrics._circuit_rejected_counter = mock_counter

        record_circuit_breaker_rejected("test_breaker")

        mock_counter.add.assert_called_once_with(1, {"breaker": "test_breaker"})

        reset_otel_metrics_for_testing()


class TestGetTimeInCurrentState:
    """Tests for get_time_in_current_state function."""

    def test_returns_zero_for_unknown_breaker(self) -> None:
        """Should return 0.0 for breakers not tracked."""
        from backend.core.otel_metrics import (
            get_time_in_current_state,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()
        result = get_time_in_current_state("unknown_breaker")
        assert result == 0.0

        reset_otel_metrics_for_testing()

    def test_returns_elapsed_time(self) -> None:
        """Should return elapsed time since last state change."""
        import time

        from backend.core.otel_metrics import (
            get_time_in_current_state,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        from backend.core import otel_metrics

        # Simulate a state timestamp
        otel_metrics._breaker_state_timestamps = {
            "test_breaker": time.monotonic() - 1.0  # 1 second ago
        }

        elapsed = get_time_in_current_state("test_breaker")
        assert elapsed >= 0.9  # At least 0.9 seconds (accounting for timing)

        reset_otel_metrics_for_testing()


class TestGetCircuitBreakerOtelMetrics:
    """Tests for get_circuit_breaker_otel_metrics function."""

    def test_returns_default_metrics_for_unknown_breaker(self) -> None:
        """Should return default metrics for unknown breaker."""
        from backend.core.otel_metrics import (
            get_circuit_breaker_otel_metrics,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()
        metrics = get_circuit_breaker_otel_metrics("unknown_breaker")

        assert metrics.name == "unknown_breaker"
        assert metrics.state == 0
        assert metrics.time_in_current_state_seconds >= 0

        reset_otel_metrics_for_testing()

    def test_returns_tracked_state(self) -> None:
        """Should return tracked state after state change."""
        from backend.core.otel_metrics import (
            CircuitBreakerStateValue,
            get_circuit_breaker_otel_metrics,
            reset_otel_metrics_for_testing,
        )

        reset_otel_metrics_for_testing()

        from backend.core import otel_metrics

        # Manually set state tracking
        otel_metrics._breaker_current_states["test_breaker"] = CircuitBreakerStateValue.OPEN
        import time

        otel_metrics._breaker_state_timestamps["test_breaker"] = time.monotonic()

        metrics = get_circuit_breaker_otel_metrics("test_breaker")

        assert metrics.name == "test_breaker"
        assert metrics.state == CircuitBreakerStateValue.OPEN

        reset_otel_metrics_for_testing()


class TestResetOtelMetricsForTesting:
    """Tests for reset_otel_metrics_for_testing function."""

    def test_resets_all_state(self) -> None:
        """Should reset all module-level state."""
        from backend.core import otel_metrics
        from backend.core.otel_metrics import reset_otel_metrics_for_testing

        # Set some state
        otel_metrics._is_initialized = True
        otel_metrics._meter = MagicMock()
        otel_metrics._detection_latency_histogram = MagicMock()
        otel_metrics._nemotron_latency_histogram = MagicMock()
        otel_metrics._florence_latency_histogram = MagicMock()
        otel_metrics._pipeline_latency_histogram = MagicMock()
        otel_metrics._batch_processing_histogram = MagicMock()

        reset_otel_metrics_for_testing()

        # Verify all state is reset
        assert otel_metrics._is_initialized is False
        assert otel_metrics._meter is None
        assert otel_metrics._detection_latency_histogram is None
        assert otel_metrics._nemotron_latency_histogram is None
        assert otel_metrics._florence_latency_histogram is None
        assert otel_metrics._pipeline_latency_histogram is None
        assert otel_metrics._batch_processing_histogram is None
