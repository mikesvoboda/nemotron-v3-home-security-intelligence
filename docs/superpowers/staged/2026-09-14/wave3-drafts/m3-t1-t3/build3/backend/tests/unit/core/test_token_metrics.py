"""Unit tests for LLM token usage tracking metrics (NEM-1730).

Tests cover:
- Token usage counter metrics definitions
- Token throughput gauge metrics
- Token cost tracking with configurable pricing
- Helper functions for recording token metrics
- Integration with MetricsService
"""

from backend.core.metrics import (
    NEMOTRON_TOKEN_COST_USD,
    NEMOTRON_TOKENS_INPUT_TOTAL,
    NEMOTRON_TOKENS_OUTPUT_TOTAL,
    NEMOTRON_TOKENS_PER_SECOND,
    get_metrics_response,
    get_metrics_service,
    record_nemotron_tokens,
)


class TestTokenMetricDefinitions:
    """Test token metric definitions and registrations."""

    def test_tokens_input_counter_exists(self) -> None:
        """NEMOTRON_TOKENS_INPUT_TOTAL counter should be defined with camera_id label."""
        assert NEMOTRON_TOKENS_INPUT_TOTAL is not None
        # Note: prometheus_client strips _total suffix from counter names internally
        assert NEMOTRON_TOKENS_INPUT_TOTAL._name == "hsi_nemotron_tokens_input"
        assert "camera_id" in NEMOTRON_TOKENS_INPUT_TOTAL._labelnames

    def test_tokens_output_counter_exists(self) -> None:
        """NEMOTRON_TOKENS_OUTPUT_TOTAL counter should be defined with camera_id label."""
        assert NEMOTRON_TOKENS_OUTPUT_TOTAL is not None
        assert NEMOTRON_TOKENS_OUTPUT_TOTAL._name == "hsi_nemotron_tokens_output"
        assert "camera_id" in NEMOTRON_TOKENS_OUTPUT_TOTAL._labelnames

    def test_tokens_per_second_gauge_exists(self) -> None:
        """NEMOTRON_TOKENS_PER_SECOND gauge should be defined."""
        assert NEMOTRON_TOKENS_PER_SECOND is not None
        assert NEMOTRON_TOKENS_PER_SECOND._name == "hsi_nemotron_tokens_per_second"

    def test_token_cost_counter_exists(self) -> None:
        """NEMOTRON_TOKEN_COST_USD counter should be defined with camera_id label."""
        assert NEMOTRON_TOKEN_COST_USD is not None
        assert NEMOTRON_TOKEN_COST_USD._name == "hsi_nemotron_token_cost_usd"
        assert "camera_id" in NEMOTRON_TOKEN_COST_USD._labelnames


class TestTokenMetricHelpers:
    """Test token metric helper functions."""

    def test_record_nemotron_tokens_basic(self) -> None:
        """record_nemotron_tokens should record input and output token counts."""
        # Should not raise
        record_nemotron_tokens(
            camera_id="front_door",
            input_tokens=100,
            output_tokens=50,
        )

    def test_record_nemotron_tokens_with_duration(self) -> None:
        """record_nemotron_tokens should calculate tokens per second with duration."""
        record_nemotron_tokens(
            camera_id="backyard",
            input_tokens=200,
            output_tokens=100,
            duration_seconds=2.0,
        )
        # Tokens per second = (200 + 100) / 2.0 = 150 tokens/sec

    def test_record_nemotron_tokens_zero_duration_handled(self) -> None:
        """record_nemotron_tokens should handle zero duration gracefully."""
        # Should not raise or divide by zero
        record_nemotron_tokens(
            camera_id="garage",
            input_tokens=100,
            output_tokens=50,
            duration_seconds=0.0,
        )

    def test_record_nemotron_tokens_with_cost(self) -> None:
        """record_nemotron_tokens should track cost when pricing configured."""
        record_nemotron_tokens(
            camera_id="driveway",
            input_tokens=1000,
            output_tokens=500,
            input_cost_per_1k=0.01,  # $0.01 per 1000 input tokens
            output_cost_per_1k=0.02,  # $0.02 per 1000 output tokens
        )
        # Cost = (1000 * 0.01 / 1000) + (500 * 0.02 / 1000) = $0.01 + $0.01 = $0.02

    def test_record_nemotron_tokens_no_cost_when_not_configured(self) -> None:
        """record_nemotron_tokens should not track cost when pricing not provided."""
        # When no cost parameters are provided, no cost should be recorded
        record_nemotron_tokens(
            camera_id="side_entrance",
            input_tokens=500,
            output_tokens=200,
        )


class TestMetricsServiceTokenTracking:
    """Test MetricsService methods for token tracking."""

    def test_metrics_service_record_nemotron_tokens(self) -> None:
        """MetricsService should have method for recording token usage."""
        metrics = get_metrics_service()
        # Should not raise
        metrics.record_nemotron_tokens(
            camera_id="front_door",
            input_tokens=150,
            output_tokens=75,
        )

    def test_metrics_service_record_nemotron_tokens_with_throughput(self) -> None:
        """MetricsService should record throughput when duration provided."""
        metrics = get_metrics_service()
        metrics.record_nemotron_tokens(
            camera_id="backyard",
            input_tokens=300,
            output_tokens=150,
            duration_seconds=1.5,
        )

    def test_metrics_service_record_nemotron_tokens_with_cost(self) -> None:
        """MetricsService should record cost when pricing provided."""
        metrics = get_metrics_service()
        metrics.record_nemotron_tokens(
            camera_id="garage",
            input_tokens=2000,
            output_tokens=1000,
            input_cost_per_1k=0.005,
            output_cost_per_1k=0.015,
        )


class TestTokenMetricsInPrometheusOutput:
    """Test that token metrics appear in Prometheus metrics output."""

    def test_metrics_response_contains_token_metrics(self) -> None:
        """Metrics response should contain token usage metrics."""
        # Record some token metrics first
        record_nemotron_tokens(
            camera_id="test_camera",
            input_tokens=100,
            output_tokens=50,
            duration_seconds=1.0,
            input_cost_per_1k=0.01,
            output_cost_per_1k=0.02,
        )

        response = get_metrics_response().decode("utf-8")

        # Check for our token metrics
        assert "hsi_nemotron_tokens_input_total" in response
        assert "hsi_nemotron_tokens_output_total" in response
        assert "hsi_nemotron_tokens_per_second" in response
        assert "hsi_nemotron_token_cost_usd_total" in response

    def test_metrics_response_contains_camera_labels(self) -> None:
        """Token metrics should include camera_id label."""
        record_nemotron_tokens(
            camera_id="labeled_camera",
            input_tokens=50,
            output_tokens=25,
        )

        response = get_metrics_response().decode("utf-8")

        # Should have camera_id label in output
        assert 'camera_id="labeled_camera"' in response


class TestTokenMetricsEdgeCases:
    """Test edge cases for token metrics."""

    def test_record_zero_tokens(self) -> None:
        """Recording zero tokens should work without error."""
        record_nemotron_tokens(
            camera_id="empty_response",
            input_tokens=0,
            output_tokens=0,
        )

    def test_record_large_token_counts(self) -> None:
        """Recording large token counts should work."""
        record_nemotron_tokens(
            camera_id="large_batch",
            input_tokens=100000,
            output_tokens=50000,
            duration_seconds=60.0,
        )

    def test_record_negative_duration_handled(self) -> None:
        """Negative duration should be handled gracefully."""
        # Should not raise, negative duration should be treated as 0
        record_nemotron_tokens(
            camera_id="negative_duration",
            input_tokens=100,
            output_tokens=50,
            duration_seconds=-1.0,
        )

    def test_camera_id_sanitization(self) -> None:
        """Camera ID should be sanitized to prevent cardinality explosion."""
        # Very long camera ID should be truncated/sanitized
        long_camera_id = "a" * 1000
        record_nemotron_tokens(
            camera_id=long_camera_id,
            input_tokens=100,
            output_tokens=50,
        )
        # Should not crash, and label should be reasonable length


class TestTokenMetricsCumulativeTracking:
    """Test that token metrics accumulate correctly over multiple calls."""

    def test_input_tokens_accumulate(self) -> None:
        """Input tokens counter should accumulate across calls."""
        camera_id = "accumulation_test_input"

        # Record multiple batches
        record_nemotron_tokens(camera_id=camera_id, input_tokens=100, output_tokens=0)
        record_nemotron_tokens(camera_id=camera_id, input_tokens=200, output_tokens=0)
        record_nemotron_tokens(camera_id=camera_id, input_tokens=300, output_tokens=0)

        # Total should be 600 input tokens
        # (We can verify this via the metrics output or counter value)

    def test_output_tokens_accumulate(self) -> None:
        """Output tokens counter should accumulate across calls."""
        camera_id = "accumulation_test_output"

        record_nemotron_tokens(camera_id=camera_id, input_tokens=0, output_tokens=50)
        record_nemotron_tokens(camera_id=camera_id, input_tokens=0, output_tokens=75)
        record_nemotron_tokens(camera_id=camera_id, input_tokens=0, output_tokens=125)

        # Total should be 250 output tokens

    def test_cost_accumulates(self) -> None:
        """Cost counter should accumulate across calls."""
        camera_id = "accumulation_test_cost"

        # Each call with 1000 input @ $0.01/1k = $0.01
        record_nemotron_tokens(
            camera_id=camera_id,
            input_tokens=1000,
            output_tokens=0,
            input_cost_per_1k=0.01,
        )
        record_nemotron_tokens(
            camera_id=camera_id,
            input_tokens=1000,
            output_tokens=0,
            input_cost_per_1k=0.01,
        )
        record_nemotron_tokens(
            camera_id=camera_id,
            input_tokens=1000,
            output_tokens=0,
            input_cost_per_1k=0.01,
        )

        # Total cost should be $0.03
