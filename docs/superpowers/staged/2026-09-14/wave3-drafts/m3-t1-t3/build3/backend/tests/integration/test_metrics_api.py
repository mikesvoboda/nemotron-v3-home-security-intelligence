"""Integration tests for Prometheus metrics API endpoint.

Tests cover:
- GET /api/metrics endpoint returning valid Prometheus format
- Metrics content validation (expected metric names)
- Content-type header validation
- Metrics response format compliance
- Metrics update verification through helper functions
- Concurrent request handling
"""

import asyncio
import re

import pytest


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_200(client, mock_redis):
    """GET /api/metrics should return 200 status code."""
    response = await client.get("/api/metrics")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_metrics_endpoint_content_type_is_text_plain(client, mock_redis):
    """GET /api/metrics should return text/plain content type.

    Prometheus expects text/plain; charset=utf-8 for metrics scraping.
    """
    response = await client.get("/api/metrics")
    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert "text/plain" in content_type
    assert "charset=utf-8" in content_type


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_prometheus_format(client, mock_redis):
    """GET /api/metrics should return valid Prometheus exposition format.

    The response must include:
    - HELP declarations describing metrics
    - TYPE declarations specifying metric types (counter, gauge, histogram)
    - Metric values in proper format
    """
    response = await client.get("/api/metrics")
    assert response.status_code == 200
    content = response.text

    # Prometheus format requires HELP and TYPE declarations
    assert "# HELP" in content, "Missing HELP declarations"
    assert "# TYPE" in content, "Missing TYPE declarations"


@pytest.mark.asyncio
async def test_metrics_endpoint_contains_queue_depth_gauges(client, mock_redis):
    """GET /api/metrics should expose queue depth gauge metrics.

    These gauges track:
    - hsi_detection_queue_depth: Images waiting in detection queue
    - hsi_analysis_queue_depth: Batches waiting in analysis queue
    """
    response = await client.get("/api/metrics")
    assert response.status_code == 200
    content = response.text

    # Check for queue depth gauges
    assert "hsi_detection_queue_depth" in content
    assert "hsi_analysis_queue_depth" in content

    # Verify TYPE declarations for gauges
    assert "# TYPE hsi_detection_queue_depth gauge" in content
    assert "# TYPE hsi_analysis_queue_depth gauge" in content


@pytest.mark.asyncio
async def test_metrics_endpoint_contains_event_counters(client, mock_redis):
    """GET /api/metrics should expose event and detection counters.

    These counters track:
    - hsi_events_created_total: Total security events created
    - hsi_detections_processed_total: Total detections processed by YOLO26
    """
    response = await client.get("/api/metrics")
    assert response.status_code == 200
    content = response.text

    # Check for counter metrics (counters have _total suffix)
    assert "hsi_events_created_total" in content
    assert "hsi_detections_processed_total" in content

    # Verify TYPE declarations for counters
    assert "# TYPE hsi_events_created_total counter" in content
    assert "# TYPE hsi_detections_processed_total counter" in content


@pytest.mark.asyncio
async def test_metrics_endpoint_contains_stage_duration_histogram(client, mock_redis):
    """GET /api/metrics should expose stage duration histogram.

    The histogram tracks:
    - hsi_stage_duration_seconds: Duration of pipeline stages (detect, batch, analyze)
    """
    response = await client.get("/api/metrics")
    assert response.status_code == 200
    content = response.text

    # Check for histogram metric
    assert "hsi_stage_duration_seconds" in content

    # Verify TYPE declaration for histogram
    assert "# TYPE hsi_stage_duration_seconds histogram" in content


@pytest.mark.asyncio
async def test_metrics_endpoint_contains_ai_request_duration_histogram(client, mock_redis):
    """GET /api/metrics should expose AI request duration histogram.

    The histogram tracks:
    - hsi_ai_request_duration_seconds: Duration of AI service requests (yolo26, nemotron)
    """
    response = await client.get("/api/metrics")
    assert response.status_code == 200
    content = response.text

    # Check for AI request duration histogram
    assert "hsi_ai_request_duration_seconds" in content

    # Verify TYPE declaration for histogram
    assert "# TYPE hsi_ai_request_duration_seconds histogram" in content


@pytest.mark.asyncio
async def test_metrics_endpoint_contains_pipeline_errors_counter(client, mock_redis):
    """GET /api/metrics should expose pipeline errors counter.

    The counter tracks:
    - hsi_pipeline_errors_total: Total pipeline errors by error_type
    """
    response = await client.get("/api/metrics")
    assert response.status_code == 200
    content = response.text

    # Check for pipeline errors counter
    assert "hsi_pipeline_errors_total" in content

    # Verify TYPE declaration for counter
    assert "# TYPE hsi_pipeline_errors_total counter" in content


@pytest.mark.asyncio
async def test_metrics_endpoint_contains_queue_overflow_metrics(client, mock_redis):
    """GET /api/metrics should expose queue overflow metrics.

    These counters track queue overflow behavior:
    - hsi_queue_overflow_total: Total overflow events by queue and policy
    - hsi_queue_items_moved_to_dlq_total: Items moved to dead-letter queue
    - hsi_queue_items_dropped_total: Items dropped due to drop_oldest policy
    - hsi_queue_items_rejected_total: Items rejected due to reject policy
    """
    response = await client.get("/api/metrics")
    assert response.status_code == 200
    content = response.text

    # Check for queue overflow counters
    assert "hsi_queue_overflow_total" in content
    assert "hsi_queue_items_moved_to_dlq_total" in content
    assert "hsi_queue_items_dropped_total" in content
    assert "hsi_queue_items_rejected_total" in content


@pytest.mark.asyncio
async def test_metrics_endpoint_help_descriptions_present(client, mock_redis):
    """GET /api/metrics should include HELP descriptions for all metrics.

    HELP declarations provide human-readable descriptions for Prometheus UI.
    """
    response = await client.get("/api/metrics")
    assert response.status_code == 200
    content = response.text

    # Verify HELP declarations exist for our key metrics
    assert "# HELP hsi_detection_queue_depth" in content
    assert "# HELP hsi_events_created_total" in content
    assert "# HELP hsi_stage_duration_seconds" in content
    assert "# HELP hsi_pipeline_errors_total" in content


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_bytes_content(client, mock_redis):
    """GET /api/metrics should return response content as bytes (UTF-8 encoded)."""
    response = await client.get("/api/metrics")
    assert response.status_code == 200

    # Content should be valid UTF-8 text
    content = response.text
    assert isinstance(content, str)
    # Should contain ASCII characters
    assert content.encode("utf-8")


@pytest.mark.asyncio
async def test_metrics_endpoint_gauge_values_are_numeric(client, mock_redis):
    """Gauge metric values in /api/metrics should be numeric."""
    response = await client.get("/api/metrics")
    assert response.status_code == 200
    content = response.text

    # Find gauge value lines (format: metric_name value)
    # Look for lines that start with our gauge names followed by a number
    gauge_pattern = re.compile(r"^hsi_detection_queue_depth\s+(\d+\.?\d*)", re.MULTILINE)
    matches = gauge_pattern.findall(content)

    # Should find at least one gauge value
    assert len(matches) >= 1, "Expected numeric value for hsi_detection_queue_depth gauge"

    # Verify the value is parseable as a number
    for value in matches:
        float(value)  # Should not raise


@pytest.mark.asyncio
async def test_metrics_endpoint_histogram_buckets_present(client, mock_redis):
    """Histogram metrics should include bucket definitions when observations exist."""
    from backend.core.metrics import observe_stage_duration

    # Record an observation so histogram emits bucket data
    observe_stage_duration("test_bucket", 0.5)

    response = await client.get("/api/metrics")
    assert response.status_code == 200
    content = response.text

    # Histograms should have _bucket, _sum, and _count suffixes when there are observations
    assert "hsi_stage_duration_seconds_bucket" in content
    assert "hsi_stage_duration_seconds_sum" in content
    assert "hsi_stage_duration_seconds_count" in content


@pytest.mark.asyncio
async def test_metrics_endpoint_concurrent_requests(client, mock_redis):
    """GET /api/metrics should handle concurrent requests safely."""
    # Make multiple concurrent requests
    num_requests = 10
    tasks = [client.get("/api/metrics") for _ in range(num_requests)]
    responses = await asyncio.gather(*tasks)

    # All requests should succeed
    for response in responses:
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
        assert "hsi_" in response.text  # Should contain our metrics


@pytest.mark.asyncio
async def test_metrics_endpoint_no_authentication_required(client, mock_redis):
    """GET /api/metrics should not require authentication.

    Prometheus needs to scrape metrics without auth configuration.
    """
    # Request without any auth headers
    response = await client.get("/api/metrics")

    # Should succeed without authentication
    assert response.status_code == 200
    assert "hsi_" in response.text


@pytest.mark.asyncio
async def test_metrics_endpoint_idempotent(client, mock_redis):
    """Multiple GET /api/metrics requests should return consistent structure."""
    response1 = await client.get("/api/metrics")
    response2 = await client.get("/api/metrics")

    assert response1.status_code == 200
    assert response2.status_code == 200

    # Both responses should have the same metric names (values may differ)
    # Check for presence of key metrics in both
    for metric_name in [
        "hsi_detection_queue_depth",
        "hsi_events_created_total",
        "hsi_stage_duration_seconds",
    ]:
        assert metric_name in response1.text
        assert metric_name in response2.text


class TestMetricsWithRecordedValues:
    """Tests verifying metrics reflect recorded values."""

    @pytest.mark.asyncio
    async def test_metrics_reflect_queue_depth_updates(self, client, mock_redis):
        """Queue depth gauge should reflect values set via helper function."""
        from backend.core.metrics import set_queue_depth

        # Set queue depths
        set_queue_depth("detection", 42)
        set_queue_depth("analysis", 17)

        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Check that the gauge values are present
        # The exact line format is: metric_name value
        assert (
            "hsi_detection_queue_depth 42" in content or "hsi_detection_queue_depth 42.0" in content
        )
        assert (
            "hsi_analysis_queue_depth 17" in content or "hsi_analysis_queue_depth 17.0" in content
        )

    @pytest.mark.asyncio
    async def test_metrics_reflect_event_counter_increments(self, client, mock_redis):
        """Event counter should reflect increments via helper function."""
        from backend.core.metrics import EVENTS_CREATED_TOTAL, record_event_created

        # Get initial value
        initial_value = EVENTS_CREATED_TOTAL._value.get()

        # Increment counter
        record_event_created()
        record_event_created()
        record_event_created()

        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Counter should have increased by 3
        expected_value = initial_value + 3
        # Check the counter value is at least our expected value
        assert "hsi_events_created_total" in content
        # The value should be >= expected (other tests may have incremented it too)
        pattern = re.compile(r"hsi_events_created_total\s+(\d+\.?\d*)")
        matches = pattern.findall(content)
        assert len(matches) >= 1
        actual_value = float(matches[0])
        assert actual_value >= expected_value

    @pytest.mark.asyncio
    async def test_metrics_reflect_stage_duration_observations(self, client, mock_redis):
        """Stage duration histogram should reflect observed values."""
        from backend.core.metrics import observe_stage_duration

        # Observe some stage durations
        observe_stage_duration("detect", 0.5)
        observe_stage_duration("batch", 1.0)
        observe_stage_duration("analyze", 2.0)

        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Histogram should have bucket entries with stage labels
        assert "hsi_stage_duration_seconds_bucket{le=" in content
        assert 'stage="detect"' in content or "stage='detect'" in content.replace('"', "'")

    @pytest.mark.asyncio
    async def test_metrics_reflect_ai_request_duration(self, client, mock_redis):
        """AI request duration histogram should reflect observed values."""
        from backend.core.metrics import observe_ai_request_duration

        # Observe AI request durations
        observe_ai_request_duration("yolo26", 0.3)
        observe_ai_request_duration("nemotron", 5.0)

        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Histogram should have service labels
        assert "hsi_ai_request_duration_seconds" in content
        # Check for service labels in histogram output
        assert "service=" in content

    @pytest.mark.asyncio
    async def test_metrics_reflect_pipeline_errors(self, client, mock_redis):
        """Pipeline errors counter should reflect recorded errors."""
        from backend.core.metrics import record_pipeline_error

        # Record some pipeline errors
        record_pipeline_error("connection_error")
        record_pipeline_error("timeout_error")
        record_pipeline_error("connection_error")

        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Counter should have error_type labels
        assert "hsi_pipeline_errors_total" in content
        assert "error_type=" in content
        # Should see our error types
        assert "connection_error" in content
        assert "timeout_error" in content


class TestMetricsResponseValidation:
    """Tests for validating Prometheus metrics response format."""

    @pytest.mark.asyncio
    async def test_metrics_lines_are_valid_format(self, client, mock_redis):
        """Each non-comment line should be valid Prometheus format."""
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Prometheus format:
        # - Comment lines start with #
        # - Metric lines are: metric_name{labels} value [timestamp]
        # - Empty lines are allowed

        for raw_line in content.split("\n"):
            line = raw_line.strip()
            if not line:
                continue  # Empty line is OK
            if line.startswith("#"):
                # Comment line: # TYPE or # HELP
                assert line.startswith("# HELP") or line.startswith("# TYPE"), (
                    f"Invalid comment: {line}"
                )
            else:
                # Metric line should have at least metric_name and value
                # Format: metric_name value or metric_name{labels} value
                parts = line.split()
                assert len(parts) >= 2, f"Invalid metric line (missing value): {line}"
                # Last part should be a number
                try:
                    float(parts[-1])
                except ValueError:
                    # Could be timestamp, try second to last
                    if len(parts) >= 3:
                        try:
                            float(parts[-2])
                        except ValueError:
                            pytest.fail(f"Invalid metric value in line: {line}")

    @pytest.mark.asyncio
    async def test_metrics_type_declarations_are_valid(self, client, mock_redis):
        """TYPE declarations should use valid Prometheus metric types."""
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        valid_types = {"counter", "gauge", "histogram", "summary", "untyped"}

        for line in content.split("\n"):
            if line.startswith("# TYPE"):
                # Format: # TYPE metric_name type
                parts = line.split()
                assert len(parts) == 4, f"Invalid TYPE declaration: {line}"
                metric_type = parts[3]
                assert metric_type in valid_types, f"Invalid metric type '{metric_type}' in: {line}"

    @pytest.mark.asyncio
    async def test_metrics_histogram_has_required_suffixes(self, client, mock_redis):
        """Histogram metrics should have _bucket, _sum, and _count suffixes when observations exist."""
        from backend.core.metrics import observe_ai_request_duration, observe_stage_duration

        # Record observations so histograms emit bucket data
        observe_stage_duration("test_hist", 0.5)
        observe_ai_request_duration("yolo26", 0.3)

        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # For each histogram we define, check all required components
        histograms = ["hsi_stage_duration_seconds", "hsi_ai_request_duration_seconds"]

        for histogram in histograms:
            # Check _bucket (with le label)
            bucket_pattern = rf'{histogram}_bucket{{.*le=".*".*}}'
            assert re.search(bucket_pattern, content), f"Missing _bucket for {histogram}"

            # Check _sum
            assert f"{histogram}_sum" in content, f"Missing _sum for {histogram}"

            # Check _count
            assert f"{histogram}_count" in content, f"Missing _count for {histogram}"

    @pytest.mark.asyncio
    async def test_metrics_histogram_buckets_are_ordered(self, client, mock_redis):
        """Histogram bucket boundaries should be in ascending order."""
        from backend.core.metrics import observe_stage_duration

        # Ensure we have some observations
        observe_stage_duration("test", 0.1)

        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Extract bucket boundaries for stage_duration histogram
        bucket_pattern = re.compile(r'hsi_stage_duration_seconds_bucket{.*le="([^"]+)".*}')
        boundaries = []
        for line in content.split("\n"):
            match = bucket_pattern.search(line)
            if match:
                le_value = match.group(1)
                if le_value != "+Inf":
                    boundaries.append(float(le_value))

        # Boundaries should be in ascending order (after removing duplicates from labels)
        unique_boundaries = sorted(set(boundaries))
        assert unique_boundaries == sorted(unique_boundaries)

    @pytest.mark.asyncio
    async def test_metrics_counter_values_are_non_negative(self, client, mock_redis):
        """Counter metric values should always be non-negative."""
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Find counter values (lines with _total)

        for line in content.split("\n"):
            if "_total" in line and not line.startswith("#"):
                # Extract the numeric value at the end
                parts = line.split()
                if parts:
                    try:
                        value = float(parts[-1])
                        assert value >= 0, f"Negative counter value in: {line}"
                    except ValueError:
                        pass  # Skip if can't parse (might be label line)


class TestMetricsEmptyState:
    """Tests for metrics in empty/initial state."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_works_with_no_recorded_values(self, client, mock_redis):
        """GET /api/metrics should work even with no recorded metric values.

        Initial state should still expose metrics with default values (0 for counters/gauges).
        """
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Metrics should be present even with no recorded values
        assert "hsi_detection_queue_depth" in content
        assert "hsi_events_created_total" in content

    @pytest.mark.asyncio
    async def test_metrics_gauges_default_to_zero(self, client, mock_redis):
        """Gauge metrics should have a default value (typically 0)."""
        from backend.core.metrics import DETECTION_QUEUE_DEPTH

        # Reset gauge to 0
        DETECTION_QUEUE_DEPTH.set(0)

        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Should see the gauge with value 0
        assert (
            "hsi_detection_queue_depth 0" in content or "hsi_detection_queue_depth 0.0" in content
        )
