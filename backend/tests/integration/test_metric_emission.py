"""Integration tests for Prometheus metric emission after API operations.

Tests verify that Prometheus metrics are correctly emitted when API operations
are performed. This ensures observability of the security intelligence pipeline.

Tests cover:
- Event creation metrics (hsi_events_created_total)
- Detection processing metrics (hsi_detections_processed_total)
- Detection by class metrics (hsi_detections_by_class_total)
- Stage duration histograms (hsi_stage_duration_seconds)
- AI request duration histograms (hsi_ai_request_duration_seconds)
- Risk score histograms (hsi_risk_score)
- Events by risk level counters (hsi_events_by_risk_level_total)
- Queue depth gauges (hsi_detection_queue_depth, hsi_analysis_queue_depth)
- Cache metrics (hsi_cache_hits_total, hsi_cache_misses_total)
- Pipeline errors (hsi_pipeline_errors_total)

Uses shared fixtures from conftest.py:
- integration_db: Clean PostgreSQL test database
- mock_redis: Mock Redis client
- client: httpx AsyncClient with test app
"""

import re

import pytest


def parse_prometheus_counter(content: str, metric_name: str) -> float | None:
    """Parse a Prometheus counter value from metrics output.

    Args:
        content: The raw Prometheus metrics text
        metric_name: The full metric name (e.g., 'hsi_events_created_total')

    Returns:
        The counter value as a float, or None if not found
    """
    # Match lines like: metric_name 42.0 or metric_name 42
    pattern = rf"^{re.escape(metric_name)}\s+(\d+\.?\d*)$"
    for line in content.split("\n"):
        match = re.match(pattern, line.strip())
        if match:
            return float(match.group(1))
    return None


def parse_prometheus_labeled_counter(
    content: str,
    metric_name: str,
    labels: dict[str, str],
) -> float | None:
    """Parse a Prometheus counter value with specific labels from metrics output.

    Args:
        content: The raw Prometheus metrics text
        metric_name: The metric name without labels
        labels: Dictionary of label name to expected value

    Returns:
        The counter value as a float, or None if not found
    """
    # Build label pattern
    label_pattern = ".*".join(f'{k}="{v}"' for k, v in labels.items())
    pattern = rf"^{re.escape(metric_name)}\{{.*{label_pattern}.*\}}\s+(\d+\.?\d*)"

    for line in content.split("\n"):
        match = re.match(pattern, line.strip())
        if match:
            return float(match.group(1))
    return None


def parse_prometheus_gauge(content: str, metric_name: str) -> float | None:
    """Parse a Prometheus gauge value from metrics output.

    Args:
        content: The raw Prometheus metrics text
        metric_name: The full metric name

    Returns:
        The gauge value as a float, or None if not found
    """
    # Same format as counter for simple gauges
    return parse_prometheus_counter(content, metric_name)


def check_histogram_has_observations(content: str, histogram_name: str) -> bool:
    """Check if a histogram has any observations (count > 0).

    Args:
        content: The raw Prometheus metrics text
        histogram_name: The histogram metric name (without _bucket/_sum/_count suffix)

    Returns:
        True if the histogram has at least one observation
    """
    count_pattern = rf"^{re.escape(histogram_name)}_count\{{.*\}}\s+(\d+\.?\d*)"
    for line in content.split("\n"):
        match = re.match(count_pattern, line.strip())
        if match:
            count = float(match.group(1))
            if count > 0:
                return True

    # Also check for unlabeled histograms
    simple_pattern = rf"^{re.escape(histogram_name)}_count\s+(\d+\.?\d*)"
    for line in content.split("\n"):
        match = re.match(simple_pattern, line.strip())
        if match:
            count = float(match.group(1))
            if count > 0:
                return True

    return False


class TestEventMetricEmission:
    """Tests for event-related metric emission."""

    @pytest.mark.asyncio
    async def test_record_event_created_increments_counter(self, client, mock_redis):
        """Test that record_event_created() increments hsi_events_created_total counter."""
        from backend.core.metrics import EVENTS_CREATED_TOTAL, record_event_created

        # Get initial counter value
        initial_value = EVENTS_CREATED_TOTAL._value.get()

        # Record event creations directly (simulating what the pipeline does)
        record_event_created()
        record_event_created()

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Counter should have increased by 2
        expected_value = initial_value + 2
        actual_value = parse_prometheus_counter(content, "hsi_events_created_total")
        assert actual_value is not None
        assert actual_value >= expected_value

    @pytest.mark.asyncio
    async def test_events_by_risk_level_increments(self, client, mock_redis):
        """Test that risk level events increment hsi_events_by_risk_level_total counter."""
        from backend.core.metrics import record_event_by_risk_level

        # Record events at different risk levels
        record_event_by_risk_level("low")
        record_event_by_risk_level("medium")
        record_event_by_risk_level("high")
        record_event_by_risk_level("critical")

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Check that all risk levels are present in metrics
        assert 'level="low"' in content
        assert 'level="medium"' in content
        assert 'level="high"' in content
        assert 'level="critical"' in content

    @pytest.mark.asyncio
    async def test_event_reviewed_increments_counter(self, client, mock_redis):
        """Test that record_event_reviewed() increments hsi_events_reviewed_total counter."""
        from backend.core.metrics import EVENTS_REVIEWED_TOTAL, record_event_reviewed

        # Get initial counter value
        initial_value = EVENTS_REVIEWED_TOTAL._value.get()

        # Record event reviews
        record_event_reviewed()
        record_event_reviewed()
        record_event_reviewed()

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Counter should have increased by 3
        expected_value = initial_value + 3
        actual_value = parse_prometheus_counter(content, "hsi_events_reviewed_total")
        assert actual_value is not None
        assert actual_value >= expected_value


class TestDetectionMetricEmission:
    """Tests for detection-related metric emission."""

    @pytest.mark.asyncio
    async def test_detection_processed_increments_counter(self, client, mock_redis):
        """Test that record_detection_processed() increments hsi_detections_processed_total."""
        from backend.core.metrics import DETECTIONS_PROCESSED_TOTAL, record_detection_processed

        # Get initial counter value
        initial_value = DETECTIONS_PROCESSED_TOTAL._value.get()

        # Record detection processing
        record_detection_processed()  # Single detection
        record_detection_processed(count=5)  # Batch of 5

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Counter should have increased by 6 (1 + 5)
        expected_value = initial_value + 6
        actual_value = parse_prometheus_counter(content, "hsi_detections_processed_total")
        assert actual_value is not None
        assert actual_value >= expected_value

    @pytest.mark.asyncio
    async def test_detections_by_class_increments_per_class(self, client, mock_redis):
        """Test that record_detection_by_class() increments per-class counters."""
        from backend.core.metrics import record_detection_by_class

        # Record detections for various object classes
        record_detection_by_class("person")
        record_detection_by_class("person")
        record_detection_by_class("car")
        record_detection_by_class("dog")
        record_detection_by_class("truck")

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Check that all classes are present in metrics
        assert 'object_class="person"' in content
        assert 'object_class="car"' in content
        assert 'object_class="dog"' in content
        assert 'object_class="truck"' in content

    @pytest.mark.asyncio
    async def test_detection_confidence_histogram_records_values(self, client, mock_redis):
        """Test that observe_detection_confidence() records to histogram."""
        from backend.core.metrics import observe_detection_confidence

        # Record confidence values across the range
        observe_detection_confidence(0.55)
        observe_detection_confidence(0.75)
        observe_detection_confidence(0.92)
        observe_detection_confidence(0.99)

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Histogram should have observations
        assert "hsi_detection_confidence_bucket" in content
        assert "hsi_detection_confidence_sum" in content
        assert "hsi_detection_confidence_count" in content

    @pytest.mark.asyncio
    async def test_detection_filtered_increments_counter(self, client, mock_redis):
        """Test that record_detection_filtered() increments low confidence filter counter."""
        from backend.core.metrics import (
            DETECTIONS_FILTERED_LOW_CONFIDENCE_TOTAL,
            record_detection_filtered,
        )

        # Get initial counter value
        initial_value = DETECTIONS_FILTERED_LOW_CONFIDENCE_TOTAL._value.get()

        # Record filtered detections
        record_detection_filtered()
        record_detection_filtered()

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        expected_value = initial_value + 2
        actual_value = parse_prometheus_counter(
            content, "hsi_detections_filtered_low_confidence_total"
        )
        assert actual_value is not None
        assert actual_value >= expected_value


class TestHistogramMetricEmission:
    """Tests for histogram metric emission."""

    @pytest.mark.asyncio
    async def test_stage_duration_histogram_records_latency(self, client, mock_redis):
        """Test that observe_stage_duration() records to stage duration histogram."""
        from backend.core.metrics import observe_stage_duration

        # Record various stage durations
        observe_stage_duration("detect", 0.15)  # 150ms
        observe_stage_duration("batch", 0.5)  # 500ms
        observe_stage_duration("analyze", 2.5)  # 2.5s

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Histogram should have stage labels
        assert "hsi_stage_duration_seconds_bucket" in content
        assert 'stage="detect"' in content
        assert 'stage="batch"' in content
        assert 'stage="analyze"' in content

    @pytest.mark.asyncio
    async def test_ai_request_duration_histogram_records_latency(self, client, mock_redis):
        """Test that observe_ai_request_duration() records to AI request histogram."""
        from backend.core.metrics import observe_ai_request_duration

        # Record AI service request durations
        observe_ai_request_duration("rtdetr", 0.3)  # RT-DETR detection
        observe_ai_request_duration("nemotron", 5.0)  # Nemotron analysis

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Histogram should have service labels
        assert "hsi_ai_request_duration_seconds_bucket" in content
        assert 'service="rtdetr"' in content
        assert 'service="nemotron"' in content

    @pytest.mark.asyncio
    async def test_risk_score_histogram_records_values(self, client, mock_redis):
        """Test that observe_risk_score() records to risk score histogram."""
        from backend.core.metrics import observe_risk_score

        # Record risk scores across the range
        observe_risk_score(15)  # Low risk
        observe_risk_score(45)  # Medium risk
        observe_risk_score(75)  # High risk
        observe_risk_score(95)  # Critical risk

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Histogram should have observations
        assert "hsi_risk_score_bucket" in content
        assert "hsi_risk_score_sum" in content
        assert "hsi_risk_score_count" in content

    @pytest.mark.asyncio
    async def test_db_query_duration_histogram_records_latency(self, client, mock_redis):
        """Test that observe_db_query_duration() records to database query histogram."""
        from backend.core.metrics import observe_db_query_duration

        # Record database query durations
        observe_db_query_duration(0.05)  # 50ms - fast query
        observe_db_query_duration(0.15)  # 150ms - normal query
        observe_db_query_duration(0.5)  # 500ms - slow query

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Histogram should have observations
        assert "hsi_db_query_duration_seconds_bucket" in content
        assert "hsi_db_query_duration_seconds_sum" in content
        assert "hsi_db_query_duration_seconds_count" in content


class TestQueueMetricEmission:
    """Tests for queue-related metric emission."""

    @pytest.mark.asyncio
    async def test_queue_depth_gauge_updates(self, client, mock_redis):
        """Test that set_queue_depth() updates queue depth gauges."""
        from backend.core.metrics import set_queue_depth

        # Set queue depths
        set_queue_depth("detection", 25)
        set_queue_depth("analysis", 10)

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Gauges should have the correct values
        detection_depth = parse_prometheus_gauge(content, "hsi_detection_queue_depth")
        analysis_depth = parse_prometheus_gauge(content, "hsi_analysis_queue_depth")

        assert detection_depth == 25.0
        assert analysis_depth == 10.0

    @pytest.mark.asyncio
    async def test_queue_overflow_increments_counter(self, client, mock_redis):
        """Test that record_queue_overflow() increments overflow counters."""
        from backend.core.metrics import record_queue_overflow

        # Record overflow events
        record_queue_overflow("detection", "dlq")
        record_queue_overflow("analysis", "drop_oldest")

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Check overflow metrics with labels
        assert "hsi_queue_overflow_total" in content
        assert 'queue_name="detection"' in content or "queue_name='detection'" in content


class TestCacheMetricEmission:
    """Tests for cache-related metric emission."""

    @pytest.mark.asyncio
    async def test_cache_hit_increments_counter(self, client, mock_redis):
        """Test that record_cache_hit() increments cache hit counter."""
        from backend.core.metrics import record_cache_hit

        # Record cache hits
        record_cache_hit("event_stats")
        record_cache_hit("cameras")
        record_cache_hit("event_stats")

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Cache hit counter should be present
        assert "hsi_cache_hits_total" in content
        assert 'cache_type="event_stats"' in content
        assert 'cache_type="cameras"' in content

    @pytest.mark.asyncio
    async def test_cache_miss_increments_counter(self, client, mock_redis):
        """Test that record_cache_miss() increments cache miss counter."""
        from backend.core.metrics import record_cache_miss

        # Record cache misses
        record_cache_miss("event_stats")
        record_cache_miss("cameras")

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Cache miss counter should be present
        assert "hsi_cache_misses_total" in content
        assert 'cache_type="event_stats"' in content

    @pytest.mark.asyncio
    async def test_cache_invalidation_increments_counter(self, client, mock_redis):
        """Test that record_cache_invalidation() increments invalidation counter."""
        from backend.core.metrics import record_cache_invalidation

        # Record cache invalidations
        record_cache_invalidation("event_stats", "event_created")
        record_cache_invalidation("cameras", "camera_updated")

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Cache invalidation counter should be present
        assert "hsi_cache_invalidations_total" in content


class TestPipelineErrorMetricEmission:
    """Tests for pipeline error metric emission."""

    @pytest.mark.asyncio
    async def test_pipeline_error_increments_counter(self, client, mock_redis):
        """Test that record_pipeline_error() increments error counter by type."""
        from backend.core.metrics import record_pipeline_error

        # Record various error types
        record_pipeline_error("connection_error")
        record_pipeline_error("timeout_error")
        record_pipeline_error("connection_error")

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Error counter should have error_type labels
        assert "hsi_pipeline_errors_total" in content
        assert 'error_type="connection_error"' in content
        assert 'error_type="timeout_error"' in content


class TestEnrichmentMetricEmission:
    """Tests for enrichment-related metric emission."""

    @pytest.mark.asyncio
    async def test_enrichment_model_call_increments_counter(self, client, mock_redis):
        """Test that record_enrichment_model_call() increments model call counter."""
        from backend.core.metrics import record_enrichment_model_call

        # Record enrichment model calls
        record_enrichment_model_call("brisque")
        record_enrichment_model_call("violence")
        record_enrichment_model_call("clothing")

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Enrichment model counter should be present
        assert "hsi_enrichment_model_calls_total" in content
        assert 'model="brisque"' in content
        assert 'model="violence"' in content
        assert 'model="clothing"' in content

    @pytest.mark.asyncio
    async def test_enrichment_failure_increments_counter(self, client, mock_redis):
        """Test that record_enrichment_failure() increments failure counter."""
        from backend.core.metrics import record_enrichment_failure

        # Record enrichment failures
        record_enrichment_failure("vehicle")
        record_enrichment_failure("pet")

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Enrichment failure counter should be present
        assert "hsi_enrichment_failures_total" in content
        assert 'model="vehicle"' in content
        assert 'model="pet"' in content

    @pytest.mark.asyncio
    async def test_enrichment_batch_status_increments_counter(self, client, mock_redis):
        """Test that record_enrichment_batch_status() increments batch status counter."""
        from backend.core.metrics import record_enrichment_batch_status

        # Record various batch statuses
        record_enrichment_batch_status("full")
        record_enrichment_batch_status("partial")
        record_enrichment_batch_status("failed")

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Batch status counter should be present
        assert "hsi_enrichment_batch_status_total" in content
        assert 'status="full"' in content
        assert 'status="partial"' in content
        assert 'status="failed"' in content


class TestPromptMetricEmission:
    """Tests for prompt-related metric emission."""

    @pytest.mark.asyncio
    async def test_prompt_template_used_increments_counter(self, client, mock_redis):
        """Test that record_prompt_template_used() increments template counter."""
        from backend.core.metrics import record_prompt_template_used

        # Record prompt template usage
        record_prompt_template_used("basic")
        record_prompt_template_used("enriched")
        record_prompt_template_used("vision")

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Prompt template counter should be present
        assert "hsi_prompt_template_used_total" in content
        assert 'template="basic"' in content
        assert 'template="enriched"' in content
        assert 'template="vision"' in content

    @pytest.mark.asyncio
    async def test_prompt_tokens_histogram_records_values(self, client, mock_redis):
        """Test that observe_prompt_tokens() records to token histogram."""
        from backend.core.metrics import observe_prompt_tokens

        # Record prompt token counts
        observe_prompt_tokens(500)
        observe_prompt_tokens(1500)
        observe_prompt_tokens(3000)

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Histogram should have observations
        assert "hsi_prompt_tokens_bucket" in content
        assert "hsi_prompt_tokens_sum" in content
        assert "hsi_prompt_tokens_count" in content


class TestLLMTokenMetricEmission:
    """Tests for LLM token usage metric emission."""

    @pytest.mark.asyncio
    async def test_nemotron_tokens_increments_counters(self, client, mock_redis):
        """Test that record_nemotron_tokens() increments token counters."""
        from backend.core.metrics import record_nemotron_tokens

        # Record token usage
        record_nemotron_tokens(
            camera_id="front_door",
            input_tokens=500,
            output_tokens=200,
            duration_seconds=5.0,
        )

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Token counters should be present
        assert "hsi_nemotron_tokens_input_total" in content
        assert "hsi_nemotron_tokens_output_total" in content
        assert "hsi_nemotron_tokens_per_second" in content


class TestModelWarmupMetricEmission:
    """Tests for AI model warmup metric emission."""

    @pytest.mark.asyncio
    async def test_model_warmup_duration_records_to_histogram(self, client, mock_redis):
        """Test that observe_model_warmup_duration() records to histogram."""
        from backend.core.metrics import observe_model_warmup_duration

        # Record warmup durations
        observe_model_warmup_duration("rtdetr", 2.5)
        observe_model_warmup_duration("nemotron", 10.0)

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Warmup histogram should be present
        assert "hsi_model_warmup_duration_seconds_bucket" in content
        assert 'model="rtdetr"' in content
        assert 'model="nemotron"' in content

    @pytest.mark.asyncio
    async def test_model_cold_start_increments_counter(self, client, mock_redis):
        """Test that record_model_cold_start() increments cold start counter."""
        from backend.core.metrics import record_model_cold_start

        # Record cold starts
        record_model_cold_start("rtdetr")
        record_model_cold_start("nemotron")

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Cold start counter should be present
        assert "hsi_model_cold_start_total" in content
        assert 'model="rtdetr"' in content
        assert 'model="nemotron"' in content

    @pytest.mark.asyncio
    async def test_model_warmth_state_gauge_updates(self, client, mock_redis):
        """Test that set_model_warmth_state() updates warmth state gauge."""
        from backend.core.metrics import set_model_warmth_state

        # Set warmth states
        set_model_warmth_state("rtdetr", "warm")
        set_model_warmth_state("nemotron", "cold")

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Warmth state gauge should be present
        assert "hsi_model_warmth_state" in content


class TestMetricsServiceEmission:
    """Tests for MetricsService class emission."""

    @pytest.mark.asyncio
    async def test_metrics_service_records_all_metrics(self, client, mock_redis):
        """Test that MetricsService correctly records all metric types."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()

        # Record various metrics through the service
        metrics.record_event_created()
        metrics.record_detection_processed(count=3)
        metrics.record_detection_by_class("person")
        metrics.observe_stage_duration("detect", 0.2)
        metrics.observe_ai_request_duration("rtdetr", 0.5)
        metrics.record_pipeline_error("validation_error")
        metrics.observe_risk_score(65)
        metrics.record_event_by_risk_level("medium")
        metrics.set_queue_depth("detection", 15)
        metrics.record_cache_hit("events")
        metrics.record_cache_miss("cameras")

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # All metrics should be present
        assert "hsi_events_created_total" in content
        assert "hsi_detections_processed_total" in content
        assert "hsi_detections_by_class_total" in content
        assert "hsi_stage_duration_seconds" in content
        assert "hsi_ai_request_duration_seconds" in content
        assert "hsi_pipeline_errors_total" in content
        assert "hsi_risk_score" in content
        assert "hsi_events_by_risk_level_total" in content
        assert "hsi_detection_queue_depth" in content
        assert "hsi_cache_hits_total" in content
        assert "hsi_cache_misses_total" in content


class TestCoreMetricsPresence:
    """Tests verifying presence of all key metrics defined in the system."""

    @pytest.mark.asyncio
    async def test_all_core_counters_exposed(self, client, mock_redis):
        """Test that all core counter metrics are exposed on /api/metrics."""
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Core counters that must be present
        core_counters = [
            "hsi_events_created_total",
            "hsi_detections_processed_total",
            "hsi_events_reviewed_total",
            "hsi_pipeline_errors_total",
            "hsi_queue_overflow_total",
        ]

        for counter in core_counters:
            assert counter in content, f"Missing core counter: {counter}"

    @pytest.mark.asyncio
    async def test_all_core_gauges_exposed(self, client, mock_redis):
        """Test that all core gauge metrics are exposed on /api/metrics."""
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Core gauges that must be present
        core_gauges = [
            "hsi_detection_queue_depth",
            "hsi_analysis_queue_depth",
        ]

        for gauge in core_gauges:
            assert gauge in content, f"Missing core gauge: {gauge}"

    @pytest.mark.asyncio
    async def test_all_core_histograms_exposed(self, client, mock_redis):
        """Test that all core histogram metrics are exposed on /api/metrics."""
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Core histograms that must be present (check HELP/TYPE declarations)
        core_histograms = [
            "hsi_stage_duration_seconds",
            "hsi_ai_request_duration_seconds",
            "hsi_risk_score",
            "hsi_detection_confidence",
        ]

        for histogram in core_histograms:
            assert f"# TYPE {histogram} histogram" in content, (
                f"Missing core histogram TYPE: {histogram}"
            )

    @pytest.mark.asyncio
    async def test_metric_help_descriptions_complete(self, client, mock_redis):
        """Test that all key metrics have HELP descriptions."""
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Key metrics that should have help text
        metrics_with_help = [
            "hsi_events_created_total",
            "hsi_detections_processed_total",
            "hsi_stage_duration_seconds",
            "hsi_ai_request_duration_seconds",
            "hsi_detection_queue_depth",
            "hsi_pipeline_errors_total",
        ]

        for metric in metrics_with_help:
            assert f"# HELP {metric}" in content, f"Missing HELP for {metric}"


class TestRealUserMonitoringMetrics:
    """Tests for Real User Monitoring (RUM) metric emission."""

    @pytest.mark.asyncio
    async def test_rum_lcp_records_to_histogram(self, client, mock_redis):
        """Test that observe_rum_lcp() records to LCP histogram."""
        from backend.core.metrics import observe_rum_lcp

        # Record LCP values
        observe_rum_lcp(1500.0, path="/", rating="good")
        observe_rum_lcp(3000.0, path="/events", rating="needs-improvement")

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # LCP histogram should be present
        assert "hsi_rum_lcp_seconds" in content
        assert "hsi_rum_metrics_total" in content

    @pytest.mark.asyncio
    async def test_rum_cls_records_to_histogram(self, client, mock_redis):
        """Test that observe_rum_cls() records to CLS histogram."""
        from backend.core.metrics import observe_rum_cls

        # Record CLS values
        observe_rum_cls(0.05, path="/", rating="good")
        observe_rum_cls(0.2, path="/cameras", rating="needs-improvement")

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # CLS histogram should be present
        assert "hsi_rum_cls" in content


class TestBudgetAndCostMetrics:
    """Tests for budget and cost tracking metric emission."""

    @pytest.mark.asyncio
    async def test_gpu_seconds_increments_counter(self, client, mock_redis):
        """Test that GPU seconds counter increments correctly."""
        from backend.core.metrics import GPU_SECONDS_TOTAL

        # Record GPU time
        GPU_SECONDS_TOTAL.labels(model="nemotron").inc(10.0)
        GPU_SECONDS_TOTAL.labels(model="rtdetr").inc(2.5)

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # GPU seconds counter should be present
        assert "hsi_gpu_seconds_total" in content
        assert 'model="nemotron"' in content
        assert 'model="rtdetr"' in content

    @pytest.mark.asyncio
    async def test_cost_tracking_gauges_update(self, client, mock_redis):
        """Test that cost tracking gauges update correctly."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()

        # Set cost values
        metrics.set_daily_cost(1.50)
        metrics.set_monthly_cost(45.00)
        metrics.set_budget_utilization("daily", 0.75)
        metrics.set_budget_utilization("monthly", 0.45)

        # Verify via metrics endpoint
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        content = response.text

        # Cost gauges should be present
        assert "hsi_daily_cost_usd" in content
        assert "hsi_monthly_cost_usd" in content
        assert "hsi_budget_utilization_ratio" in content
