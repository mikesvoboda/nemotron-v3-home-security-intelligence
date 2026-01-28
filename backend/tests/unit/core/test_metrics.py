"""Unit tests for Prometheus metrics endpoint and instrumentation.

Tests cover:
- /metrics endpoint returning valid Prometheus format
- Core metrics registration and exposure
- Metric value updates via helper functions
- Pipeline latency tracking with percentiles
- Risk score and analysis metrics (NEM-769)
- Detection class and confidence metrics (NEM-768)
"""

import time
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.metrics import (
    AI_REQUEST_DURATION,
    ANALYSIS_QUEUE_DEPTH,
    DETECTION_CONFIDENCE,
    DETECTION_QUEUE_DEPTH,
    DETECTIONS_BY_CLASS_TOTAL,
    DETECTIONS_FILTERED_LOW_CONFIDENCE_TOTAL,
    DETECTIONS_PROCESSED_TOTAL,
    DLQ_DEPTH,
    EVENTS_BY_RISK_LEVEL,
    EVENTS_CREATED_TOTAL,
    PIPELINE_ERRORS_TOTAL,
    PROMPT_TEMPLATE_USED,
    RISK_SCORE,
    STAGE_DURATION_SECONDS,
    PipelineLatencyTracker,
    get_metrics_response,
    get_pipeline_latency_tracker,
    observe_ai_request_duration,
    observe_detection_confidence,
    observe_risk_score,
    observe_stage_duration,
    record_detection_by_class,
    record_detection_filtered,
    record_detection_processed,
    record_event_by_risk_level,
    record_event_created,
    record_pipeline_error,
    record_pipeline_stage_latency,
    record_prompt_template_used,
    set_dlq_depth,
    set_queue_depth,
)


class TestMetricsDefinitions:
    """Test metric definitions and registrations."""

    def test_detection_queue_depth_metric_exists(self) -> None:
        """DETECTION_QUEUE_DEPTH gauge should be defined."""
        assert DETECTION_QUEUE_DEPTH is not None
        assert DETECTION_QUEUE_DEPTH._name == "hsi_detection_queue_depth"

    def test_analysis_queue_depth_metric_exists(self) -> None:
        """ANALYSIS_QUEUE_DEPTH gauge should be defined."""
        assert ANALYSIS_QUEUE_DEPTH is not None
        assert ANALYSIS_QUEUE_DEPTH._name == "hsi_analysis_queue_depth"

    def test_dlq_depth_metric_exists(self) -> None:
        """DLQ_DEPTH gauge should be defined with queue_name label (NEM-3891)."""
        assert DLQ_DEPTH is not None
        assert DLQ_DEPTH._name == "hsi_dlq_depth"
        assert "queue_name" in DLQ_DEPTH._labelnames

    def test_stage_duration_histogram_exists(self) -> None:
        """STAGE_DURATION_SECONDS histogram should be defined with stage label."""
        assert STAGE_DURATION_SECONDS is not None
        assert STAGE_DURATION_SECONDS._name == "hsi_stage_duration_seconds"
        assert "stage" in STAGE_DURATION_SECONDS._labelnames

    def test_events_created_counter_exists(self) -> None:
        """EVENTS_CREATED_TOTAL counter should be defined."""
        assert EVENTS_CREATED_TOTAL is not None
        # Note: prometheus_client strips _total suffix from counter names internally
        assert EVENTS_CREATED_TOTAL._name == "hsi_events_created"

    def test_detections_processed_counter_exists(self) -> None:
        """DETECTIONS_PROCESSED_TOTAL counter should be defined."""
        assert DETECTIONS_PROCESSED_TOTAL is not None
        # Note: prometheus_client strips _total suffix from counter names internally
        assert DETECTIONS_PROCESSED_TOTAL._name == "hsi_detections_processed"

    def test_ai_request_duration_histogram_exists(self) -> None:
        """AI_REQUEST_DURATION histogram should be defined with service label."""
        assert AI_REQUEST_DURATION is not None
        assert AI_REQUEST_DURATION._name == "hsi_ai_request_duration_seconds"
        assert "service" in AI_REQUEST_DURATION._labelnames

    def test_pipeline_errors_counter_exists(self) -> None:
        """PIPELINE_ERRORS_TOTAL counter should be defined with error_type label."""
        assert PIPELINE_ERRORS_TOTAL is not None
        # Note: prometheus_client strips _total suffix from counter names internally
        assert PIPELINE_ERRORS_TOTAL._name == "hsi_pipeline_errors"
        assert "error_type" in PIPELINE_ERRORS_TOTAL._labelnames

    def test_risk_score_histogram_exists(self) -> None:
        """RISK_SCORE histogram should be defined with appropriate buckets."""
        assert RISK_SCORE is not None
        assert RISK_SCORE._name == "hsi_risk_score"
        # Verify buckets cover risk score range 0-100
        # prometheus_client stores buckets as upper_bound values
        buckets = RISK_SCORE._upper_bounds
        assert 10 in buckets
        assert 50 in buckets
        assert 100 in buckets

    def test_events_by_risk_level_counter_exists(self) -> None:
        """EVENTS_BY_RISK_LEVEL counter should be defined with level label."""
        assert EVENTS_BY_RISK_LEVEL is not None
        # Note: prometheus_client strips _total suffix from counter names internally
        assert EVENTS_BY_RISK_LEVEL._name == "hsi_events_by_risk_level"
        assert "level" in EVENTS_BY_RISK_LEVEL._labelnames

    def test_prompt_template_used_counter_exists(self) -> None:
        """PROMPT_TEMPLATE_USED counter should be defined with template label."""
        assert PROMPT_TEMPLATE_USED is not None
        # Note: prometheus_client strips _total suffix from counter names internally
        assert PROMPT_TEMPLATE_USED._name == "hsi_prompt_template_used"
        assert "template" in PROMPT_TEMPLATE_USED._labelnames

    # Detection class and confidence metrics (NEM-768)

    def test_detections_by_class_counter_exists(self) -> None:
        """DETECTIONS_BY_CLASS_TOTAL counter should be defined with object_class label."""
        assert DETECTIONS_BY_CLASS_TOTAL is not None
        # Note: prometheus_client strips _total suffix from counter names internally
        assert DETECTIONS_BY_CLASS_TOTAL._name == "hsi_detections_by_class"
        assert "object_class" in DETECTIONS_BY_CLASS_TOTAL._labelnames

    def test_detection_confidence_histogram_exists(self) -> None:
        """DETECTION_CONFIDENCE histogram should be defined with appropriate buckets."""
        assert DETECTION_CONFIDENCE is not None
        assert DETECTION_CONFIDENCE._name == "hsi_detection_confidence"
        # Verify buckets cover confidence range
        buckets = DETECTION_CONFIDENCE._upper_bounds
        assert 0.5 in buckets
        assert 0.7 in buckets
        assert 0.9 in buckets
        assert 0.99 in buckets

    def test_detections_filtered_counter_exists(self) -> None:
        """DETECTIONS_FILTERED_LOW_CONFIDENCE_TOTAL counter should be defined."""
        assert DETECTIONS_FILTERED_LOW_CONFIDENCE_TOTAL is not None
        # Note: prometheus_client strips _total suffix from counter names internally
        assert (
            DETECTIONS_FILTERED_LOW_CONFIDENCE_TOTAL._name
            == "hsi_detections_filtered_low_confidence"
        )


class TestMetricHelpers:
    """Test metric helper functions."""

    def test_set_queue_depth_detection(self) -> None:
        """set_queue_depth should update detection queue gauge."""
        set_queue_depth("detection", 5)
        # Verify the metric was set (no exception means success)

    def test_set_queue_depth_analysis(self) -> None:
        """set_queue_depth should update analysis queue gauge."""
        set_queue_depth("analysis", 10)
        # Verify the metric was set (no exception means success)

    def test_set_queue_depth_invalid_queue(self) -> None:
        """set_queue_depth should handle invalid queue names gracefully."""
        # Should not raise, just log warning
        set_queue_depth("invalid_queue", 5)

    def test_set_dlq_depth_detection_queue(self) -> None:
        """set_dlq_depth should update DLQ gauge for detection queue (NEM-3891)."""
        set_dlq_depth("dlq:detection_queue", 5)
        # Verify the metric was set (no exception means success)

    def test_set_dlq_depth_analysis_queue(self) -> None:
        """set_dlq_depth should update DLQ gauge for analysis queue (NEM-3891)."""
        set_dlq_depth("dlq:analysis_queue", 3)
        # Verify the metric was set (no exception means success)

    def test_set_dlq_depth_zero_does_not_warn(self, caplog: pytest.LogCaptureFixture) -> None:
        """set_dlq_depth with zero depth should not log warning (NEM-3891)."""
        import logging

        with caplog.at_level(logging.WARNING):
            set_dlq_depth("dlq:detection_queue", 0)
        # No warning should be logged for zero depth
        assert "DLQ contains" not in caplog.text

    def test_set_dlq_depth_nonzero_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """set_dlq_depth with non-zero depth should log warning (NEM-3891)."""
        import logging

        with caplog.at_level(logging.WARNING):
            set_dlq_depth("dlq:test_queue", 9)
        assert "DLQ contains 9 messages" in caplog.text

    def test_observe_stage_duration(self) -> None:
        """observe_stage_duration should record histogram observation."""
        observe_stage_duration("detect", 0.5)
        observe_stage_duration("batch", 1.2)
        observe_stage_duration("analyze", 2.0)

    def test_record_event_created(self) -> None:
        """record_event_created should increment counter."""
        record_event_created()
        record_event_created()

    def test_record_detection_processed(self) -> None:
        """record_detection_processed should increment counter."""
        record_detection_processed()
        record_detection_processed(count=5)

    def test_observe_ai_request_duration_yolo26(self) -> None:
        """observe_ai_request_duration should record YOLO26 duration."""
        observe_ai_request_duration("yolo26", 0.3)

    def test_observe_ai_request_duration_nemotron(self) -> None:
        """observe_ai_request_duration should record Nemotron duration."""
        observe_ai_request_duration("nemotron", 1.5)

    def test_record_pipeline_error(self) -> None:
        """record_pipeline_error should increment error counter with type."""
        record_pipeline_error("connection_error")
        record_pipeline_error("timeout_error")
        record_pipeline_error("validation_error")

    def test_observe_risk_score(self) -> None:
        """observe_risk_score should record histogram observation."""
        observe_risk_score(25)  # Low risk
        observe_risk_score(50)  # Medium risk
        observe_risk_score(75)  # High risk
        observe_risk_score(95)  # Critical risk

    def test_observe_risk_score_boundary_values(self) -> None:
        """observe_risk_score should handle boundary values."""
        observe_risk_score(0)  # Minimum
        observe_risk_score(100)  # Maximum
        observe_risk_score(10)  # Bucket boundary
        observe_risk_score(90)  # Bucket boundary

    def test_record_event_by_risk_level(self) -> None:
        """record_event_by_risk_level should increment counter with level."""
        record_event_by_risk_level("low")
        record_event_by_risk_level("medium")
        record_event_by_risk_level("high")
        record_event_by_risk_level("critical")

    def test_record_event_by_risk_level_multiple_calls(self) -> None:
        """record_event_by_risk_level should increment on each call."""
        record_event_by_risk_level("high")
        record_event_by_risk_level("high")
        record_event_by_risk_level("high")
        # No assertion needed - no exception means success
        # Prometheus counter increments are verified through /metrics endpoint

    def test_record_prompt_template_used(self) -> None:
        """record_prompt_template_used should increment counter with template name."""
        record_prompt_template_used("basic")
        record_prompt_template_used("enriched")
        record_prompt_template_used("vision")
        record_prompt_template_used("model_zoo")

    def test_record_prompt_template_used_multiple_calls(self) -> None:
        """record_prompt_template_used should increment on each call."""
        record_prompt_template_used("vision")
        record_prompt_template_used("vision")
        # No assertion needed - no exception means success

    # Detection class and confidence helper tests (NEM-768)

    def test_record_detection_by_class(self) -> None:
        """record_detection_by_class should increment counter with object class."""
        record_detection_by_class("person")
        record_detection_by_class("car")
        record_detection_by_class("dog")
        record_detection_by_class("bicycle")

    def test_record_detection_by_class_multiple_calls(self) -> None:
        """record_detection_by_class should increment on each call."""
        record_detection_by_class("person")
        record_detection_by_class("person")
        record_detection_by_class("person")
        # No assertion needed - no exception means success

    def test_observe_detection_confidence(self) -> None:
        """observe_detection_confidence should record histogram observation."""
        observe_detection_confidence(0.55)  # Just above threshold
        observe_detection_confidence(0.75)  # Medium confidence
        observe_detection_confidence(0.95)  # High confidence
        observe_detection_confidence(0.99)  # Very high confidence

    def test_observe_detection_confidence_boundary_values(self) -> None:
        """observe_detection_confidence should handle boundary values."""
        observe_detection_confidence(0.5)  # Minimum typical threshold
        observe_detection_confidence(0.6)  # Bucket boundary
        observe_detection_confidence(0.9)  # Bucket boundary
        observe_detection_confidence(1.0)  # Maximum

    def test_record_detection_filtered(self) -> None:
        """record_detection_filtered should increment counter."""
        record_detection_filtered()
        record_detection_filtered()
        record_detection_filtered()
        # No assertion needed - no exception means success


class TestMetricsEndpoint:
    """Test the /metrics endpoint."""

    def test_get_metrics_response_returns_bytes(self) -> None:
        """get_metrics_response should return bytes in Prometheus format."""
        response = get_metrics_response()
        assert isinstance(response, bytes)

    def test_get_metrics_response_contains_expected_metrics(self) -> None:
        """Metrics response should contain our registered metrics."""
        response = get_metrics_response().decode("utf-8")

        # Check for our custom metrics (counters have _total suffix in output)
        assert "hsi_detection_queue_depth" in response
        assert "hsi_analysis_queue_depth" in response
        assert "hsi_stage_duration_seconds" in response
        assert "hsi_events_created_total" in response
        assert "hsi_detections_processed_total" in response
        assert "hsi_ai_request_duration_seconds" in response
        assert "hsi_pipeline_errors_total" in response
        # Risk analysis metrics (NEM-769)
        assert "hsi_risk_score" in response
        assert "hsi_events_by_risk_level_total" in response
        assert "hsi_prompt_template_used_total" in response
        # Detection class and confidence metrics (NEM-768)
        assert "hsi_detections_by_class_total" in response
        assert "hsi_detection_confidence" in response
        assert "hsi_detections_filtered_low_confidence_total" in response

    def test_get_metrics_response_valid_prometheus_format(self) -> None:
        """Metrics response should be valid Prometheus exposition format."""
        response = get_metrics_response().decode("utf-8")

        # Valid Prometheus format should have:
        # 1. TYPE declarations
        # 2. HELP declarations
        # 3. Metric values
        assert "# HELP" in response
        assert "# TYPE" in response


class TestMetricsAPIEndpoint:
    """Test the /api/metrics HTTP endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client with metrics router."""
        from backend.api.routes.metrics import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_metrics_endpoint_returns_200(self, client: TestClient) -> None:
        """GET /api/metrics should return 200 status."""
        response = client.get("/api/metrics")
        assert response.status_code == 200

    def test_metrics_endpoint_content_type(self, client: TestClient) -> None:
        """GET /api/metrics should return text/plain content type."""
        response = client.get("/api/metrics")
        assert "text/plain" in response.headers["content-type"]

    def test_metrics_endpoint_contains_metrics(self, client: TestClient) -> None:
        """GET /api/metrics should return Prometheus metrics."""
        response = client.get("/api/metrics")
        content = response.text

        assert "hsi_detection_queue_depth" in content
        assert "hsi_events_created_total" in content


class TestPipelineLatencyTracker:
    """Test PipelineLatencyTracker class for pipeline observability."""

    def test_valid_stages(self) -> None:
        """Tracker should define expected pipeline stages."""
        tracker = PipelineLatencyTracker()
        assert "watch_to_detect" in tracker.STAGES
        assert "detect_to_batch" in tracker.STAGES
        assert "batch_to_analyze" in tracker.STAGES
        assert "total_pipeline" in tracker.STAGES
        assert len(tracker.STAGES) == 4

    def test_record_stage_latency_valid_stage(self) -> None:
        """Recording latency for valid stage should succeed."""
        tracker = PipelineLatencyTracker()
        tracker.record_stage_latency("watch_to_detect", 100.5)
        # Should not raise, sample should be recorded
        stats = tracker.get_stage_stats("watch_to_detect")
        assert stats["sample_count"] == 1
        assert stats["avg_ms"] == 100.5

    def test_record_stage_latency_invalid_stage(self) -> None:
        """Recording latency for invalid stage should be ignored."""
        tracker = PipelineLatencyTracker()
        tracker.record_stage_latency("invalid_stage", 100.5)
        # Invalid stage returns empty stats
        stats = tracker.get_stage_stats("invalid_stage")
        assert stats["sample_count"] == 0

    def test_get_stage_stats_empty(self) -> None:
        """Getting stats for empty stage should return None values."""
        tracker = PipelineLatencyTracker()
        stats = tracker.get_stage_stats("watch_to_detect")
        assert stats["avg_ms"] is None
        assert stats["min_ms"] is None
        assert stats["max_ms"] is None
        assert stats["p50_ms"] is None
        assert stats["p95_ms"] is None
        assert stats["p99_ms"] is None
        assert stats["sample_count"] == 0

    def test_get_stage_stats_single_sample(self) -> None:
        """Getting stats with single sample should work."""
        tracker = PipelineLatencyTracker()
        tracker.record_stage_latency("detect_to_batch", 150.0)
        stats = tracker.get_stage_stats("detect_to_batch")
        assert stats["avg_ms"] == 150.0
        assert stats["min_ms"] == 150.0
        assert stats["max_ms"] == 150.0
        assert stats["p50_ms"] == 150.0
        assert stats["p95_ms"] == 150.0
        assert stats["p99_ms"] == 150.0
        assert stats["sample_count"] == 1

    def test_get_stage_stats_multiple_samples(self) -> None:
        """Getting stats with multiple samples should calculate correctly."""
        tracker = PipelineLatencyTracker()
        # Add samples: 100, 200, 300, 400, 500
        for latency in [100, 200, 300, 400, 500]:
            tracker.record_stage_latency("batch_to_analyze", float(latency))

        stats = tracker.get_stage_stats("batch_to_analyze")
        assert stats["avg_ms"] == 300.0
        assert stats["min_ms"] == 100.0
        assert stats["max_ms"] == 500.0
        assert stats["sample_count"] == 5

    def test_percentile_calculation(self) -> None:
        """Percentile calculations should be accurate."""
        tracker = PipelineLatencyTracker()
        # Add 100 samples: 1, 2, 3, ..., 100
        for i in range(1, 101):
            tracker.record_stage_latency("total_pipeline", float(i))

        stats = tracker.get_stage_stats("total_pipeline")
        # p50 should be around 50
        assert 49 <= stats["p50_ms"] <= 51
        # p95 should be around 95
        assert 94 <= stats["p95_ms"] <= 96
        # p99 should be around 99
        assert 98 <= stats["p99_ms"] <= 100
        assert stats["sample_count"] == 100

    def test_circular_buffer_max_samples(self) -> None:
        """Tracker should respect max_samples limit."""
        max_samples = 10
        tracker = PipelineLatencyTracker(max_samples=max_samples)

        # Add 20 samples, should only keep last 10
        for i in range(20):
            tracker.record_stage_latency("watch_to_detect", float(i))

        stats = tracker.get_stage_stats("watch_to_detect")
        assert stats["sample_count"] == max_samples
        # Last 10 samples are 10-19, min should be 10, max should be 19
        assert stats["min_ms"] == 10.0
        assert stats["max_ms"] == 19.0

    def test_window_minutes_filter(self) -> None:
        """Samples should be filtered by time window."""
        tracker = PipelineLatencyTracker()

        # Mock time to control timestamps
        mock_time = MagicMock()
        current_time = time.time()
        tracker._time = mock_time

        # Add old sample (70 minutes ago)
        mock_time.time.return_value = current_time - (70 * 60)
        tracker.record_stage_latency("detect_to_batch", 1000.0)

        # Add recent sample (5 minutes ago)
        mock_time.time.return_value = current_time - (5 * 60)
        tracker.record_stage_latency("detect_to_batch", 500.0)

        # Query with current time
        mock_time.time.return_value = current_time

        # Default 60-minute window should only include recent sample
        stats = tracker.get_stage_stats("detect_to_batch", window_minutes=60)
        assert stats["sample_count"] == 1
        assert stats["avg_ms"] == 500.0

        # 120-minute window should include both samples
        stats_long = tracker.get_stage_stats("detect_to_batch", window_minutes=120)
        assert stats_long["sample_count"] == 2
        assert stats_long["avg_ms"] == 750.0

    def test_get_pipeline_summary(self) -> None:
        """get_pipeline_summary should return stats for all stages."""
        tracker = PipelineLatencyTracker()
        tracker.record_stage_latency("watch_to_detect", 50.0)
        tracker.record_stage_latency("detect_to_batch", 100.0)
        tracker.record_stage_latency("batch_to_analyze", 5000.0)
        tracker.record_stage_latency("total_pipeline", 10000.0)

        summary = tracker.get_pipeline_summary()

        assert "watch_to_detect" in summary
        assert "detect_to_batch" in summary
        assert "batch_to_analyze" in summary
        assert "total_pipeline" in summary

        assert summary["watch_to_detect"]["avg_ms"] == 50.0
        assert summary["detect_to_batch"]["avg_ms"] == 100.0
        assert summary["batch_to_analyze"]["avg_ms"] == 5000.0
        assert summary["total_pipeline"]["avg_ms"] == 10000.0

    def test_thread_safety(self) -> None:
        """Tracker should be thread-safe for concurrent access."""
        import threading

        tracker = PipelineLatencyTracker()
        results: list[Exception | None] = []

        def record_samples() -> None:
            try:
                for _ in range(100):
                    tracker.record_stage_latency("watch_to_detect", 100.0)
            except Exception as e:
                results.append(e)
            else:
                results.append(None)

        threads = [threading.Thread(target=record_samples) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should complete without exception
        assert all(r is None for r in results)
        # Should have 500 samples (5 threads * 100 samples)
        stats = tracker.get_stage_stats("watch_to_detect")
        assert stats["sample_count"] == 500


class TestPipelineLatencyGlobalFunctions:
    """Test global helper functions for pipeline latency tracking."""

    def test_get_pipeline_latency_tracker_returns_singleton(self) -> None:
        """get_pipeline_latency_tracker should return the same instance."""
        tracker1 = get_pipeline_latency_tracker()
        tracker2 = get_pipeline_latency_tracker()
        assert tracker1 is tracker2

    def test_record_pipeline_stage_latency(self) -> None:
        """record_pipeline_stage_latency should record to global tracker."""
        # Record a unique value to verify
        unique_value = float(int(time.time() * 1000) % 100000)
        record_pipeline_stage_latency("total_pipeline", unique_value)

        tracker = get_pipeline_latency_tracker()
        stats = tracker.get_stage_stats("total_pipeline", window_minutes=1)
        # Should find our value in recent samples
        assert stats["sample_count"] >= 1


class TestPipelineLatencyAPIEndpoint:
    """Test the /api/system/pipeline-latency HTTP endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client with system router."""
        from backend.api.routes.system import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_pipeline_latency_endpoint_returns_200(self, client: TestClient) -> None:
        """GET /api/system/pipeline-latency should return 200 status."""
        response = client.get("/api/system/pipeline-latency")
        assert response.status_code == 200

    def test_pipeline_latency_endpoint_structure(self, client: TestClient) -> None:
        """Response should have expected structure."""
        response = client.get("/api/system/pipeline-latency")
        data = response.json()

        # Check top-level fields
        assert "watch_to_detect" in data
        assert "detect_to_batch" in data
        assert "batch_to_analyze" in data
        assert "total_pipeline" in data
        assert "window_minutes" in data
        assert "timestamp" in data

    def test_pipeline_latency_endpoint_default_window(self, client: TestClient) -> None:
        """Default window should be 60 minutes."""
        response = client.get("/api/system/pipeline-latency")
        data = response.json()
        assert data["window_minutes"] == 60

    def test_pipeline_latency_endpoint_custom_window(self, client: TestClient) -> None:
        """Custom window_minutes parameter should be honored."""
        response = client.get("/api/system/pipeline-latency?window_minutes=30")
        data = response.json()
        assert data["window_minutes"] == 30

    def test_pipeline_latency_endpoint_with_samples(self, client: TestClient) -> None:
        """Endpoint should return stats when samples are present."""
        # Record some samples
        tracker = get_pipeline_latency_tracker()
        tracker.record_stage_latency("watch_to_detect", 50.0)
        tracker.record_stage_latency("watch_to_detect", 100.0)
        tracker.record_stage_latency("watch_to_detect", 150.0)

        response = client.get("/api/system/pipeline-latency")
        data = response.json()

        # watch_to_detect should have stats
        stage_stats = data["watch_to_detect"]
        assert stage_stats is not None
        assert stage_stats["sample_count"] >= 3
        assert stage_stats["avg_ms"] is not None
        assert stage_stats["min_ms"] is not None
        assert stage_stats["max_ms"] is not None
        assert stage_stats["p50_ms"] is not None
        assert stage_stats["p95_ms"] is not None
        assert stage_stats["p99_ms"] is not None


# =============================================================================
# Cache Metrics Tests (NEM-1682)
# =============================================================================


class TestCacheMetrics:
    """Test cache-related Prometheus metrics."""

    def test_cache_hits_metric_exists(self) -> None:
        """CACHE_HITS_TOTAL counter should be defined with cache_type label."""
        from backend.core.metrics import CACHE_HITS_TOTAL

        assert CACHE_HITS_TOTAL is not None
        # Note: prometheus_client strips _total suffix from counter names internally
        assert CACHE_HITS_TOTAL._name == "hsi_cache_hits"
        assert "cache_type" in CACHE_HITS_TOTAL._labelnames

    def test_cache_misses_metric_exists(self) -> None:
        """CACHE_MISSES_TOTAL counter should be defined with cache_type label."""
        from backend.core.metrics import CACHE_MISSES_TOTAL

        assert CACHE_MISSES_TOTAL is not None
        # Note: prometheus_client strips _total suffix from counter names internally
        assert CACHE_MISSES_TOTAL._name == "hsi_cache_misses"
        assert "cache_type" in CACHE_MISSES_TOTAL._labelnames

    def test_cache_invalidations_metric_exists(self) -> None:
        """CACHE_INVALIDATIONS_TOTAL counter should be defined with cache_type and reason labels."""
        from backend.core.metrics import CACHE_INVALIDATIONS_TOTAL

        assert CACHE_INVALIDATIONS_TOTAL is not None
        # Note: prometheus_client strips _total suffix from counter names internally
        assert CACHE_INVALIDATIONS_TOTAL._name == "hsi_cache_invalidations"
        assert "cache_type" in CACHE_INVALIDATIONS_TOTAL._labelnames
        assert "reason" in CACHE_INVALIDATIONS_TOTAL._labelnames


class TestCacheMetricHelpers:
    """Test cache metric helper functions."""

    def test_record_cache_hit(self) -> None:
        """record_cache_hit should increment counter with cache_type."""
        from backend.core.metrics import record_cache_hit

        record_cache_hit("event_stats")
        record_cache_hit("cameras")
        record_cache_hit("system")
        # No assertion needed - no exception means success

    def test_record_cache_miss(self) -> None:
        """record_cache_miss should increment counter with cache_type."""
        from backend.core.metrics import record_cache_miss

        record_cache_miss("event_stats")
        record_cache_miss("cameras")
        record_cache_miss("other")
        # No assertion needed - no exception means success

    def test_record_cache_invalidation(self) -> None:
        """record_cache_invalidation should increment counter with cache_type and reason."""
        from backend.core.metrics import record_cache_invalidation

        record_cache_invalidation("event_stats", "event_created")
        record_cache_invalidation("cameras", "camera_updated")
        record_cache_invalidation("cameras", "camera_deleted")
        # No assertion needed - no exception means success


class TestMetricsServiceCacheMethods:
    """Test MetricsService cache-related methods."""

    def test_metrics_service_record_cache_hit(self) -> None:
        """MetricsService.record_cache_hit should increment counter."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_cache_hit("event_stats")
        metrics.record_cache_hit("cameras")
        # No assertion needed - no exception means success

    def test_metrics_service_record_cache_miss(self) -> None:
        """MetricsService.record_cache_miss should increment counter."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_cache_miss("event_stats")
        metrics.record_cache_miss("cameras")
        # No assertion needed - no exception means success

    def test_metrics_service_record_cache_invalidation(self) -> None:
        """MetricsService.record_cache_invalidation should increment counter."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_cache_invalidation("event_stats", "event_created")
        metrics.record_cache_invalidation("cameras", "camera_updated")
        # No assertion needed - no exception means success


# =============================================================================
# MetricsService Full Coverage Tests
# =============================================================================


class TestMetricsServiceQueueMethods:
    """Test MetricsService queue-related methods."""

    def test_set_queue_depth_detection(self) -> None:
        """MetricsService should set detection queue depth."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.set_queue_depth("detection", 5)
        metrics.set_queue_depth("detection", 0)

    def test_set_queue_depth_analysis(self) -> None:
        """MetricsService should set analysis queue depth."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.set_queue_depth("analysis", 10)
        metrics.set_queue_depth("analysis", 0)

    def test_set_queue_depth_unknown(self) -> None:
        """MetricsService should handle unknown queue name gracefully."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.set_queue_depth("unknown_queue", 5)  # Should log warning but not crash

    def test_record_queue_overflow(self) -> None:
        """MetricsService should record queue overflow events."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_queue_overflow("detection", "dlq")
        metrics.record_queue_overflow("analysis", "drop_oldest")
        metrics.record_queue_overflow("detection", "reject")

    def test_record_queue_items_moved_to_dlq(self) -> None:
        """MetricsService should record items moved to DLQ."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_queue_items_moved_to_dlq("detection", 1)
        metrics.record_queue_items_moved_to_dlq("analysis", 5)

    def test_record_queue_items_dropped(self) -> None:
        """MetricsService should record dropped items."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_queue_items_dropped("detection", 1)
        metrics.record_queue_items_dropped("analysis", 3)

    def test_record_queue_items_rejected(self) -> None:
        """MetricsService should record rejected items."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_queue_items_rejected("detection", 1)
        metrics.record_queue_items_rejected("analysis", 2)


class TestMetricsServiceStageDuration:
    """Test MetricsService stage duration methods."""

    def test_observe_stage_duration(self) -> None:
        """MetricsService should observe stage durations."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.observe_stage_duration("detect", 0.5)
        metrics.observe_stage_duration("batch", 1.2)
        metrics.observe_stage_duration("analyze", 2.0)


class TestMetricsServiceEventDetection:
    """Test MetricsService event and detection methods."""

    def test_record_event_created(self) -> None:
        """MetricsService should record event creation."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_event_created()

    def test_record_detection_processed(self) -> None:
        """MetricsService should record detection processing."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_detection_processed()
        metrics.record_detection_processed(count=5)

    def test_record_detection_by_class(self) -> None:
        """MetricsService should record detections by class."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_detection_by_class("person")
        metrics.record_detection_by_class("car")

    def test_observe_detection_confidence(self) -> None:
        """MetricsService should observe detection confidence."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.observe_detection_confidence(0.75)
        metrics.observe_detection_confidence(0.95)

    def test_record_detection_filtered(self) -> None:
        """MetricsService should record filtered detections."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_detection_filtered()


class TestMetricsServiceAI:
    """Test MetricsService AI-related methods."""

    def test_observe_ai_request_duration(self) -> None:
        """MetricsService should observe AI request durations."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.observe_ai_request_duration("yolo26", 0.3)
        metrics.observe_ai_request_duration("nemotron", 1.5)

    def test_record_pipeline_error(self) -> None:
        """MetricsService should record pipeline errors."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_pipeline_error("connection_error")
        metrics.record_pipeline_error("timeout_error")


class TestMetricsServiceRisk:
    """Test MetricsService risk analysis methods."""

    def test_observe_risk_score(self) -> None:
        """MetricsService should observe risk scores."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.observe_risk_score(25)
        metrics.observe_risk_score(75)
        metrics.observe_risk_score(95.5)

    def test_record_event_by_risk_level(self) -> None:
        """MetricsService should record events by risk level."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_event_by_risk_level("low")
        metrics.record_event_by_risk_level("high")

    def test_record_prompt_template_used(self) -> None:
        """MetricsService should record prompt template usage."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_prompt_template_used("basic")
        metrics.record_prompt_template_used("enriched")


class TestMetricsServiceBusiness:
    """Test MetricsService business metrics methods."""

    def test_record_florence_task(self) -> None:
        """MetricsService should record Florence task invocations."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_florence_task("caption")
        metrics.record_florence_task("ocr")

    def test_record_enrichment_model_call(self) -> None:
        """MetricsService should record enrichment model calls."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_enrichment_model_call("brisque")
        metrics.record_enrichment_model_call("violence")

    def test_set_enrichment_success_rate(self) -> None:
        """MetricsService should set enrichment success rate."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.set_enrichment_success_rate("brisque", 0.95)
        metrics.set_enrichment_success_rate("violence", 0.88)

    def test_record_enrichment_partial_batch(self) -> None:
        """MetricsService should record partial enrichment batches."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_enrichment_partial_batch()

    def test_record_enrichment_failure(self) -> None:
        """MetricsService should record enrichment failures."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_enrichment_failure("brisque")
        metrics.record_enrichment_failure("violence")

    def test_record_enrichment_batch_status(self) -> None:
        """MetricsService should record enrichment batch status."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_enrichment_batch_status("full")
        metrics.record_enrichment_batch_status("partial")
        metrics.record_enrichment_batch_status("failed")

    def test_record_event_by_camera(self) -> None:
        """MetricsService should record events by camera."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_event_by_camera("cam1", "Front Door")
        metrics.record_event_by_camera("cam2", "Back Yard")

    def test_record_event_reviewed(self) -> None:
        """MetricsService should record reviewed events."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_event_reviewed()


class TestMetricsServiceTokens:
    """Test MetricsService token usage methods."""

    def test_record_nemotron_tokens_basic(self) -> None:
        """MetricsService should record basic token usage."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_nemotron_tokens("cam1", 100, 50)

    def test_record_nemotron_tokens_with_duration(self) -> None:
        """MetricsService should calculate throughput with duration."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_nemotron_tokens("cam1", 100, 50, duration_seconds=1.5)

    def test_record_nemotron_tokens_with_zero_duration(self) -> None:
        """MetricsService should skip throughput with zero duration."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_nemotron_tokens("cam1", 100, 50, duration_seconds=0)

    def test_record_nemotron_tokens_with_negative_duration(self) -> None:
        """MetricsService should skip throughput with negative duration."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_nemotron_tokens("cam1", 100, 50, duration_seconds=-1.0)

    def test_record_nemotron_tokens_with_costs(self) -> None:
        """MetricsService should calculate costs with pricing."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_nemotron_tokens(
            "cam1", 1000, 500, input_cost_per_1k=0.01, output_cost_per_1k=0.02
        )

    def test_record_nemotron_tokens_with_input_cost_only(self) -> None:
        """MetricsService should handle input cost only."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_nemotron_tokens("cam1", 1000, 500, input_cost_per_1k=0.01)

    def test_record_nemotron_tokens_with_output_cost_only(self) -> None:
        """MetricsService should handle output cost only."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_nemotron_tokens("cam1", 1000, 500, output_cost_per_1k=0.02)


class TestMetricsServiceCostTracking:
    """Test MetricsService cost tracking methods."""

    def test_record_gpu_seconds(self) -> None:
        """MetricsService should record GPU seconds."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_gpu_seconds("nemotron", 1.5)
        metrics.record_gpu_seconds("yolo26", 0.3)

    def test_record_gpu_seconds_zero(self) -> None:
        """MetricsService should skip zero GPU seconds."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_gpu_seconds("nemotron", 0)

    def test_record_gpu_seconds_negative(self) -> None:
        """MetricsService should skip negative GPU seconds."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_gpu_seconds("nemotron", -1.0)

    def test_record_estimated_cost(self) -> None:
        """MetricsService should record estimated costs."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_estimated_cost("nemotron", 0.05)
        metrics.record_estimated_cost("yolo26", 0.01)

    def test_record_estimated_cost_zero(self) -> None:
        """MetricsService should skip zero cost."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_estimated_cost("nemotron", 0)

    def test_record_event_analysis_cost(self) -> None:
        """MetricsService should record event analysis cost."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_event_analysis_cost("cam1", 0.05)

    def test_record_event_analysis_cost_zero(self) -> None:
        """MetricsService should skip zero event cost."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_event_analysis_cost("cam1", 0)

    def test_set_daily_cost(self) -> None:
        """MetricsService should set daily cost gauge."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.set_daily_cost(1.50)

    def test_set_monthly_cost(self) -> None:
        """MetricsService should set monthly cost gauge."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.set_monthly_cost(45.00)

    def test_set_budget_utilization(self) -> None:
        """MetricsService should set budget utilization ratio."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.set_budget_utilization("daily", 0.75)
        metrics.set_budget_utilization("monthly", 0.60)

    def test_record_budget_exceeded(self) -> None:
        """MetricsService should record budget exceeded events."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_budget_exceeded("daily")
        metrics.record_budget_exceeded("monthly")

    def test_set_cost_per_detection(self) -> None:
        """MetricsService should set cost per detection gauge."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.set_cost_per_detection(0.00005)

    def test_set_cost_per_event(self) -> None:
        """MetricsService should set cost per event gauge."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.set_cost_per_event(0.0012)


# =============================================================================
# Legacy Helper Functions Coverage Tests
# =============================================================================


class TestContextUtilizationHelpers:
    """Test context utilization helper functions."""

    def test_observe_context_utilization_below_threshold(self) -> None:
        """observe_context_utilization should record low utilization."""
        from backend.core.metrics import observe_context_utilization

        observe_context_utilization(0.5)
        observe_context_utilization(0.7)

    def test_observe_context_utilization_above_threshold(self) -> None:
        """observe_context_utilization should record high utilization warning."""
        from backend.core.metrics import observe_context_utilization

        observe_context_utilization(0.85)
        observe_context_utilization(0.95)
        observe_context_utilization(1.0)

    def test_record_prompt_truncated(self) -> None:
        """record_prompt_truncated should increment counter."""
        from backend.core.metrics import record_prompt_truncated

        record_prompt_truncated()


class TestBusinessMetricHelpers:
    """Test business metric helper functions."""

    def test_increment_enrichment_retry(self) -> None:
        """increment_enrichment_retry should increment counter."""
        from backend.core.metrics import increment_enrichment_retry

        increment_enrichment_retry("vehicle")
        increment_enrichment_retry("pet")
        increment_enrichment_retry("clothing")


class TestQueueOverflowHelpers:
    """Test queue overflow helper functions."""

    def test_record_queue_overflow_helper(self) -> None:
        """record_queue_overflow should increment counter."""
        from backend.core.metrics import record_queue_overflow

        record_queue_overflow("detection", "dlq")
        record_queue_overflow("analysis", "drop_oldest")

    def test_record_queue_items_moved_to_dlq_helper(self) -> None:
        """record_queue_items_moved_to_dlq should increment counter."""
        from backend.core.metrics import record_queue_items_moved_to_dlq

        record_queue_items_moved_to_dlq("detection")
        record_queue_items_moved_to_dlq("analysis", 5)

    def test_record_queue_items_dropped_helper(self) -> None:
        """record_queue_items_dropped should increment counter."""
        from backend.core.metrics import record_queue_items_dropped

        record_queue_items_dropped("detection")
        record_queue_items_dropped("analysis", 3)

    def test_record_queue_items_rejected_helper(self) -> None:
        """record_queue_items_rejected should increment counter."""
        from backend.core.metrics import record_queue_items_rejected

        record_queue_items_rejected("detection")
        record_queue_items_rejected("analysis", 2)


class TestTokenUsageHelpers:
    """Test token usage helper functions."""

    def test_record_nemotron_tokens_basic(self) -> None:
        """record_nemotron_tokens should record basic token usage."""
        from backend.core.metrics import record_nemotron_tokens

        record_nemotron_tokens("cam1", 100, 50)

    def test_record_nemotron_tokens_with_duration(self) -> None:
        """record_nemotron_tokens should calculate throughput."""
        from backend.core.metrics import record_nemotron_tokens

        record_nemotron_tokens("cam1", 1000, 500, duration_seconds=2.5)

    def test_record_nemotron_tokens_with_costs(self) -> None:
        """record_nemotron_tokens should calculate costs."""
        from backend.core.metrics import record_nemotron_tokens

        record_nemotron_tokens(
            "cam1", 2000, 1000, input_cost_per_1k=0.005, output_cost_per_1k=0.015
        )


# =============================================================================
# Model Latency Tracker Tests
# =============================================================================


class TestModelLatencyTracker:
    """Test ModelLatencyTracker class for Model Zoo observability."""

    def test_record_model_latency(self) -> None:
        """Recording model latency should work for any model name."""
        from backend.core.metrics import ModelLatencyTracker

        tracker = ModelLatencyTracker()
        tracker.record_model_latency("yolo11-license-plate", 45.5)
        tracker.record_model_latency("yolo11-face", 38.2)
        # Should not raise

    def test_get_model_stats_empty(self) -> None:
        """Getting stats for unknown model should return None values."""
        from backend.core.metrics import ModelLatencyTracker

        tracker = ModelLatencyTracker()
        stats = tracker.get_model_stats("unknown-model")
        assert stats["avg_ms"] is None
        assert stats["p50_ms"] is None
        assert stats["p95_ms"] is None
        assert stats["sample_count"] == 0

    def test_get_model_stats_single_sample(self) -> None:
        """Getting stats with single sample should work."""
        from backend.core.metrics import ModelLatencyTracker

        tracker = ModelLatencyTracker()
        tracker.record_model_latency("clip-vit-l", 120.0)
        stats = tracker.get_model_stats("clip-vit-l")
        assert stats["avg_ms"] == 120.0
        assert stats["p50_ms"] == 120.0
        assert stats["p95_ms"] == 120.0
        assert stats["sample_count"] == 1

    def test_get_model_stats_multiple_samples(self) -> None:
        """Getting stats with multiple samples should calculate correctly."""
        from backend.core.metrics import ModelLatencyTracker

        tracker = ModelLatencyTracker()
        for latency in [10, 20, 30, 40, 50]:
            tracker.record_model_latency("paddleocr", float(latency))

        stats = tracker.get_model_stats("paddleocr")
        assert stats["avg_ms"] == 30.0
        assert stats["sample_count"] == 5

    def test_circular_buffer_max_samples(self) -> None:
        """Tracker should respect max_samples limit."""
        from backend.core.metrics import ModelLatencyTracker

        max_samples = 5
        tracker = ModelLatencyTracker(max_samples=max_samples)

        # Add 10 samples, should only keep last 5
        for i in range(10):
            tracker.record_model_latency("test-model", float(i))

        stats = tracker.get_model_stats("test-model")
        assert stats["sample_count"] == max_samples

    def test_window_minutes_filter(self) -> None:
        """Samples should be filtered by time window."""
        from backend.core.metrics import ModelLatencyTracker

        tracker = ModelLatencyTracker()

        # Mock time to control timestamps
        mock_time = MagicMock()
        current_time = time.time()
        tracker._time = mock_time

        # Add old sample (70 minutes ago)
        mock_time.time.return_value = current_time - (70 * 60)
        tracker.record_model_latency("model-a", 1000.0)

        # Add recent sample (5 minutes ago)
        mock_time.time.return_value = current_time - (5 * 60)
        tracker.record_model_latency("model-a", 500.0)

        # Query with current time
        mock_time.time.return_value = current_time

        # Default 60-minute window should only include recent sample
        stats = tracker.get_model_stats("model-a", window_minutes=60)
        assert stats["sample_count"] == 1
        assert stats["avg_ms"] == 500.0

    def test_get_model_latency_history_empty(self) -> None:
        """Getting history for unknown model should return empty buckets."""
        from backend.core.metrics import ModelLatencyTracker

        tracker = ModelLatencyTracker()
        history = tracker.get_model_latency_history("unknown", window_minutes=5)
        assert len(history) > 0
        assert all(entry["stats"] is None for entry in history)

    def test_get_model_latency_history_with_data(self) -> None:
        """Getting history with data should return stats."""
        from backend.core.metrics import ModelLatencyTracker

        tracker = ModelLatencyTracker()
        tracker.record_model_latency("model-b", 100.0)
        tracker.record_model_latency("model-b", 200.0)

        history = tracker.get_model_latency_history("model-b", window_minutes=5, bucket_seconds=60)
        assert len(history) > 0
        # At least one bucket should have data
        assert any(entry["stats"] is not None for entry in history)

    def test_get_or_create_deque(self) -> None:
        """_get_or_create_deque should create deque on first access."""
        from backend.core.metrics import ModelLatencyTracker

        tracker = ModelLatencyTracker()
        deque1 = tracker._get_or_create_deque("new-model")
        deque2 = tracker._get_or_create_deque("new-model")
        assert deque1 is deque2  # Should return same instance


class TestModelLatencyGlobalFunctions:
    """Test global helper functions for model latency tracking."""

    def test_get_model_latency_tracker_returns_singleton(self) -> None:
        """get_model_latency_tracker should return the same instance."""
        from backend.core.metrics import get_model_latency_tracker

        tracker1 = get_model_latency_tracker()
        tracker2 = get_model_latency_tracker()
        assert tracker1 is tracker2
        assert tracker1 is not None

    def test_record_model_zoo_latency(self) -> None:
        """record_model_zoo_latency should record to global tracker."""
        from backend.core.metrics import get_model_latency_tracker, record_model_zoo_latency

        unique_model = f"test-model-{int(time.time())}"
        record_model_zoo_latency(unique_model, 123.45)

        tracker = get_model_latency_tracker()
        assert tracker is not None
        stats = tracker.get_model_stats(unique_model, window_minutes=1)
        assert stats["sample_count"] >= 1


# =============================================================================
# Additional Metric Function Coverage Tests
# =============================================================================


class TestBatchSizeLimitMetrics:
    """Test batch size limit metrics."""

    def test_record_batch_max_reached(self) -> None:
        """record_batch_max_reached should increment counter."""
        from backend.core.metrics import record_batch_max_reached

        record_batch_max_reached("cam1")
        record_batch_max_reached("cam2")


class TestDatabaseQueryMetrics:
    """Test database query metrics."""

    def test_observe_db_query_duration(self) -> None:
        """observe_db_query_duration should record histogram observation."""
        from backend.core.metrics import observe_db_query_duration

        observe_db_query_duration(0.05)
        observe_db_query_duration(0.5)
        observe_db_query_duration(2.0)

    def test_record_slow_query(self) -> None:
        """record_slow_query should increment counter."""
        from backend.core.metrics import record_slow_query

        record_slow_query()


class TestTokenCountingMetrics:
    """Test token counting metrics."""

    def test_observe_prompt_tokens(self) -> None:
        """observe_prompt_tokens should record histogram observation."""
        from backend.core.metrics import observe_prompt_tokens

        observe_prompt_tokens(500)
        observe_prompt_tokens(1500)
        observe_prompt_tokens(3000)

    def test_record_prompt_section_truncated(self) -> None:
        """record_prompt_section_truncated should increment counter."""
        from backend.core.metrics import record_prompt_section_truncated

        record_prompt_section_truncated("cross_camera")
        record_prompt_section_truncated("baseline")
        record_prompt_section_truncated("zones")


class TestAIModelWarmupMetrics:
    """Test AI model warmup and cold start metrics."""

    def test_observe_model_warmup_duration(self) -> None:
        """observe_model_warmup_duration should record histogram observation."""
        from backend.core.metrics import observe_model_warmup_duration

        observe_model_warmup_duration("yolo26", 1.5)
        observe_model_warmup_duration("nemotron", 5.0)

    def test_record_model_cold_start(self) -> None:
        """record_model_cold_start should increment counter."""
        from backend.core.metrics import record_model_cold_start

        record_model_cold_start("yolo26")
        record_model_cold_start("nemotron")

    def test_set_model_warmth_state(self) -> None:
        """set_model_warmth_state should set gauge value."""
        from backend.core.metrics import set_model_warmth_state

        set_model_warmth_state("yolo26", "cold")
        set_model_warmth_state("nemotron", "warming")
        set_model_warmth_state("yolo26", "warm")

    def test_set_model_warmth_state_invalid(self) -> None:
        """set_model_warmth_state should handle invalid state."""
        from backend.core.metrics import set_model_warmth_state

        set_model_warmth_state("yolo26", "invalid_state")  # Should default to 0

    def test_set_model_last_inference_ago(self) -> None:
        """set_model_last_inference_ago should set gauge value."""
        from backend.core.metrics import set_model_last_inference_ago

        set_model_last_inference_ago("yolo26", 30.5)
        set_model_last_inference_ago("nemotron", 120.0)

    def test_set_model_last_inference_ago_none(self) -> None:
        """set_model_last_inference_ago should handle None (never used)."""
        from backend.core.metrics import set_model_last_inference_ago

        set_model_last_inference_ago("new_model", None)  # Should set to -1


class TestRUMMetrics:
    """Test Real User Monitoring (RUM) metrics."""

    def test_observe_rum_lcp(self) -> None:
        """observe_rum_lcp should record LCP metric."""
        from backend.core.metrics import observe_rum_lcp

        observe_rum_lcp(1500.0, "/", "good")
        observe_rum_lcp(3000.0, "/dashboard", "needs-improvement")
        observe_rum_lcp(5000.0, "/events", "poor")

    def test_observe_rum_fid(self) -> None:
        """observe_rum_fid should record FID metric."""
        from backend.core.metrics import observe_rum_fid

        observe_rum_fid(50.0, "/", "good")
        observe_rum_fid(150.0, "/dashboard", "needs-improvement")
        observe_rum_fid(400.0, "/events", "poor")

    def test_observe_rum_inp(self) -> None:
        """observe_rum_inp should record INP metric."""
        from backend.core.metrics import observe_rum_inp

        observe_rum_inp(80.0, "/", "good")
        observe_rum_inp(200.0, "/dashboard", "needs-improvement")
        observe_rum_inp(450.0, "/events", "poor")

    def test_observe_rum_cls(self) -> None:
        """observe_rum_cls should record CLS metric."""
        from backend.core.metrics import observe_rum_cls

        observe_rum_cls(0.05, "/", "good")
        observe_rum_cls(0.15, "/dashboard", "needs-improvement")
        observe_rum_cls(0.3, "/events", "poor")

    def test_observe_rum_ttfb(self) -> None:
        """observe_rum_ttfb should record TTFB metric."""
        from backend.core.metrics import observe_rum_ttfb

        observe_rum_ttfb(500.0, "/", "good")
        observe_rum_ttfb(1200.0, "/api/events", "needs-improvement")
        observe_rum_ttfb(2500.0, "/api/stats", "poor")

    def test_observe_rum_fcp(self) -> None:
        """observe_rum_fcp should record FCP metric."""
        from backend.core.metrics import observe_rum_fcp

        observe_rum_fcp(1200.0, "/", "good")
        observe_rum_fcp(2200.0, "/dashboard", "needs-improvement")
        observe_rum_fcp(3500.0, "/events", "poor")


class TestPromptABTestingMetrics:
    """Test prompt A/B testing metrics."""

    def test_record_prompt_latency(self) -> None:
        """record_prompt_latency should record histogram observation."""
        from backend.core.metrics import record_prompt_latency

        record_prompt_latency("v1", 1.5)
        record_prompt_latency("v2", 1.2)
        record_prompt_latency("v2-experimental", 2.0)

    def test_record_risk_score_variance(self) -> None:
        """record_risk_score_variance should set gauge value."""
        from backend.core.metrics import record_risk_score_variance

        record_risk_score_variance("v1", "v2", 5.5)
        record_risk_score_variance("v1", "v3", 12.3)

    def test_record_prompt_ab_traffic(self) -> None:
        """record_prompt_ab_traffic should increment counter."""
        from backend.core.metrics import record_prompt_ab_traffic

        record_prompt_ab_traffic("v1", False)
        record_prompt_ab_traffic("v2", True)

    def test_record_shadow_comparison(self) -> None:
        """record_shadow_comparison should increment counter."""
        from backend.core.metrics import record_shadow_comparison

        record_shadow_comparison("nemotron")

    def test_record_prompt_rollback(self) -> None:
        """record_prompt_rollback should increment counter."""
        from backend.core.metrics import record_prompt_rollback

        record_prompt_rollback("nemotron", "latency")
        record_prompt_rollback("nemotron", "variance")


# =============================================================================
# Shadow Mode Risk Distribution Metrics Tests (NEM-3337)
# =============================================================================


class TestShadowModeRiskDistributionMetrics:
    """Test shadow mode risk distribution comparison metrics."""

    def test_shadow_risk_score_distribution_metric_exists(self) -> None:
        """SHADOW_RISK_SCORE_DISTRIBUTION histogram should be defined."""
        from backend.core.metrics import SHADOW_RISK_SCORE_DISTRIBUTION

        assert SHADOW_RISK_SCORE_DISTRIBUTION is not None
        assert SHADOW_RISK_SCORE_DISTRIBUTION._name == "hsi_shadow_risk_score_distribution"
        assert "prompt_version" in SHADOW_RISK_SCORE_DISTRIBUTION._labelnames

    def test_record_shadow_risk_score(self) -> None:
        """record_shadow_risk_score should record histogram observation."""
        from backend.core.metrics import record_shadow_risk_score

        record_shadow_risk_score("control", 50)
        record_shadow_risk_score("treatment", 35)

    def test_shadow_risk_score_diff_metric_exists(self) -> None:
        """SHADOW_RISK_SCORE_DIFF histogram should be defined."""
        from backend.core.metrics import SHADOW_RISK_SCORE_DIFF

        assert SHADOW_RISK_SCORE_DIFF is not None
        assert SHADOW_RISK_SCORE_DIFF._name == "hsi_shadow_risk_score_diff"

    def test_record_shadow_risk_score_diff(self) -> None:
        """record_shadow_risk_score_diff should record histogram observation."""
        from backend.core.metrics import record_shadow_risk_score_diff

        record_shadow_risk_score_diff(15)
        record_shadow_risk_score_diff(0)
        record_shadow_risk_score_diff(30)

    def test_shadow_avg_risk_score_gauge_exists(self) -> None:
        """SHADOW_AVG_RISK_SCORE gauge should be defined."""
        from backend.core.metrics import SHADOW_AVG_RISK_SCORE

        assert SHADOW_AVG_RISK_SCORE is not None
        assert SHADOW_AVG_RISK_SCORE._name == "hsi_shadow_avg_risk_score"
        assert "prompt_version" in SHADOW_AVG_RISK_SCORE._labelnames

    def test_update_shadow_avg_risk_score(self) -> None:
        """update_shadow_avg_risk_score should set gauge value."""
        from backend.core.metrics import update_shadow_avg_risk_score

        update_shadow_avg_risk_score("control", 55.5)
        update_shadow_avg_risk_score("treatment", 42.3)

    def test_shadow_risk_level_shift_metric_exists(self) -> None:
        """SHADOW_RISK_LEVEL_SHIFT_TOTAL counter should be defined."""
        from backend.core.metrics import SHADOW_RISK_LEVEL_SHIFT_TOTAL

        assert SHADOW_RISK_LEVEL_SHIFT_TOTAL is not None
        assert SHADOW_RISK_LEVEL_SHIFT_TOTAL._name == "hsi_shadow_risk_level_shift"
        assert "direction" in SHADOW_RISK_LEVEL_SHIFT_TOTAL._labelnames

    def test_record_shadow_risk_level_shift(self) -> None:
        """record_shadow_risk_level_shift should increment counter."""
        from backend.core.metrics import record_shadow_risk_level_shift

        record_shadow_risk_level_shift("lower")
        record_shadow_risk_level_shift("same")
        record_shadow_risk_level_shift("higher")


class TestShadowModeLatencyMetrics:
    """Test shadow mode latency comparison metrics."""

    def test_shadow_latency_diff_metric_exists(self) -> None:
        """SHADOW_LATENCY_DIFF histogram should be defined."""
        from backend.core.metrics import SHADOW_LATENCY_DIFF

        assert SHADOW_LATENCY_DIFF is not None
        assert SHADOW_LATENCY_DIFF._name == "hsi_shadow_latency_diff_seconds"

    def test_record_shadow_latency_diff(self) -> None:
        """record_shadow_latency_diff should record histogram observation."""
        from backend.core.metrics import record_shadow_latency_diff

        record_shadow_latency_diff(0.5)  # Treatment 500ms slower
        record_shadow_latency_diff(-0.2)  # Treatment 200ms faster
        record_shadow_latency_diff(0.0)  # Same latency

    def test_shadow_latency_warning_metric_exists(self) -> None:
        """SHADOW_LATENCY_WARNING_TOTAL counter should be defined."""
        from backend.core.metrics import SHADOW_LATENCY_WARNING_TOTAL

        assert SHADOW_LATENCY_WARNING_TOTAL is not None
        assert SHADOW_LATENCY_WARNING_TOTAL._name == "hsi_shadow_latency_warning"
        assert "model" in SHADOW_LATENCY_WARNING_TOTAL._labelnames

    def test_record_shadow_latency_warning(self) -> None:
        """record_shadow_latency_warning should increment counter."""
        from backend.core.metrics import record_shadow_latency_warning

        record_shadow_latency_warning("nemotron")


class TestShadowModeErrorMetrics:
    """Test shadow mode comparison error metrics."""

    def test_shadow_comparison_errors_metric_exists(self) -> None:
        """SHADOW_COMPARISON_ERRORS_TOTAL counter should be defined."""
        from backend.core.metrics import SHADOW_COMPARISON_ERRORS_TOTAL

        assert SHADOW_COMPARISON_ERRORS_TOTAL is not None
        assert SHADOW_COMPARISON_ERRORS_TOTAL._name == "hsi_shadow_comparison_errors"
        assert "error_type" in SHADOW_COMPARISON_ERRORS_TOTAL._labelnames

    def test_record_shadow_comparison_error(self) -> None:
        """record_shadow_comparison_error should increment counter."""
        from backend.core.metrics import record_shadow_comparison_error

        record_shadow_comparison_error("control_failed")
        record_shadow_comparison_error("treatment_failed")
        record_shadow_comparison_error("both_failed")


class TestPipelineLatencyHistoryMethods:
    """Test pipeline latency history methods."""

    def test_get_latency_history_empty(self) -> None:
        """get_latency_history should return empty snapshots."""
        from backend.core.metrics import PipelineLatencyTracker

        tracker = PipelineLatencyTracker()
        history = tracker.get_latency_history(window_minutes=5, bucket_seconds=60)
        assert isinstance(history, list)
        assert len(history) >= 0

    def test_get_latency_history_with_data(self) -> None:
        """get_latency_history should return stats for each bucket."""
        from backend.core.metrics import PipelineLatencyTracker

        tracker = PipelineLatencyTracker()
        tracker.record_stage_latency("watch_to_detect", 100.0)
        tracker.record_stage_latency("watch_to_detect", 200.0)

        history = tracker.get_latency_history(window_minutes=5, bucket_seconds=60)
        assert isinstance(history, list)
        # Each entry should have timestamp and stages
        for entry in history:
            assert "timestamp" in entry
            assert "stages" in entry
            assert "watch_to_detect" in entry["stages"]


# =============================================================================
# Enrichment Model Duration and Error Metrics Tests
# =============================================================================


class TestEnrichmentModelDurationMetrics:
    """Test enrichment model duration histogram metrics."""

    def test_enrichment_model_duration_metric_exists(self) -> None:
        """ENRICHMENT_MODEL_DURATION histogram should be defined with model label."""
        from backend.core.metrics import ENRICHMENT_MODEL_DURATION

        assert ENRICHMENT_MODEL_DURATION is not None
        assert ENRICHMENT_MODEL_DURATION._name == "hsi_enrichment_model_duration_seconds"
        assert "model" in ENRICHMENT_MODEL_DURATION._labelnames

    def test_observe_enrichment_model_duration(self) -> None:
        """observe_enrichment_model_duration should record histogram observation."""
        from backend.core.metrics import observe_enrichment_model_duration

        observe_enrichment_model_duration("violence-detection", 0.5)
        observe_enrichment_model_duration("weather-classification", 1.2)
        observe_enrichment_model_duration("brisque-quality", 0.1)

    def test_observe_enrichment_model_duration_various_models(self) -> None:
        """observe_enrichment_model_duration should work with various model names."""
        from backend.core.metrics import observe_enrichment_model_duration

        observe_enrichment_model_duration("depth-anything-v2", 2.5)
        observe_enrichment_model_duration("vitpose", 1.8)
        observe_enrichment_model_duration("xclip", 3.0)
        observe_enrichment_model_duration("fashion-clip", 0.9)


class TestEnrichmentModelErrorMetrics:
    """Test enrichment model error counter metrics."""

    def test_enrichment_model_errors_metric_exists(self) -> None:
        """ENRICHMENT_MODEL_ERRORS_TOTAL counter should be defined with model label."""
        from backend.core.metrics import ENRICHMENT_MODEL_ERRORS_TOTAL

        assert ENRICHMENT_MODEL_ERRORS_TOTAL is not None
        # Note: prometheus_client strips _total suffix from counter names internally
        assert ENRICHMENT_MODEL_ERRORS_TOTAL._name == "hsi_enrichment_model_errors"
        assert "model" in ENRICHMENT_MODEL_ERRORS_TOTAL._labelnames

    def test_record_enrichment_model_error(self) -> None:
        """record_enrichment_model_error should increment counter with model name."""
        from backend.core.metrics import record_enrichment_model_error

        record_enrichment_model_error("violence-detection")
        record_enrichment_model_error("weather-classification")
        record_enrichment_model_error("brisque-quality")

    def test_record_enrichment_model_error_various_models(self) -> None:
        """record_enrichment_model_error should work with various model names."""
        from backend.core.metrics import record_enrichment_model_error

        record_enrichment_model_error("depth-anything-v2")
        record_enrichment_model_error("vitpose")
        record_enrichment_model_error("xclip")


class TestMetricsServiceEnrichmentDurationMethods:
    """Test MetricsService enrichment model duration methods."""

    def test_observe_enrichment_model_duration(self) -> None:
        """MetricsService should observe enrichment model durations."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.observe_enrichment_model_duration("violence-detection", 0.5)
        metrics.observe_enrichment_model_duration("weather-classification", 1.2)
        metrics.observe_enrichment_model_duration("brisque-quality", 0.1)

    def test_record_enrichment_model_error(self) -> None:
        """MetricsService should record enrichment model errors."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_enrichment_model_error("violence-detection")
        metrics.record_enrichment_model_error("weather-classification")


class TestEnrichmentMetricsInResponse:
    """Test enrichment metrics appear in Prometheus response."""

    def test_enrichment_model_duration_in_response(self) -> None:
        """Enrichment model duration metric should appear in metrics response."""
        from backend.core.metrics import get_metrics_response, observe_enrichment_model_duration

        # Record a metric to ensure it appears in output
        observe_enrichment_model_duration("test-model", 1.0)

        response = get_metrics_response().decode("utf-8")
        assert "hsi_enrichment_model_duration_seconds" in response

    def test_enrichment_model_errors_in_response(self) -> None:
        """Enrichment model errors metric should appear in metrics response."""
        from backend.core.metrics import get_metrics_response, record_enrichment_model_error

        # Record a metric to ensure it appears in output
        record_enrichment_model_error("test-model")

        response = get_metrics_response().decode("utf-8")
        assert "hsi_enrichment_model_errors_total" in response


# =============================================================================
# Workload-Specific AI Model Histogram Tests (NEM-3381)
# =============================================================================


class TestWorkloadSpecificHistograms:
    """Test workload-specific AI model histogram definitions and helpers."""

    def test_yolo26_inference_histogram_exists(self) -> None:
        """YOLO26_INFERENCE_DURATION histogram should be defined with optimized buckets."""
        from backend.core.metrics import YOLO26_INFERENCE_DURATION

        assert YOLO26_INFERENCE_DURATION is not None
        assert YOLO26_INFERENCE_DURATION._name == "hsi_yolo26_inference_seconds"
        # Verify buckets are optimized for fast inference (10ms - 500ms range)
        buckets = YOLO26_INFERENCE_DURATION._upper_bounds
        assert 0.01 in buckets  # 10ms minimum
        assert 0.05 in buckets  # 50ms typical
        assert 0.1 in buckets  # 100ms P95
        assert 0.5 in buckets  # 500ms timeout

    def test_nemotron_inference_histogram_exists(self) -> None:
        """NEMOTRON_INFERENCE_DURATION histogram should be defined with optimized buckets."""
        from backend.core.metrics import NEMOTRON_INFERENCE_DURATION

        assert NEMOTRON_INFERENCE_DURATION is not None
        assert NEMOTRON_INFERENCE_DURATION._name == "hsi_nemotron_inference_seconds"
        # Verify buckets are optimized for LLM inference (500ms - 30s range)
        buckets = NEMOTRON_INFERENCE_DURATION._upper_bounds
        assert 0.5 in buckets  # 500ms fast
        assert 1.0 in buckets  # 1s typical P50
        assert 3.0 in buckets  # 3s P95
        assert 10.0 in buckets  # 10s extended

    def test_florence_inference_histogram_exists(self) -> None:
        """FLORENCE_INFERENCE_DURATION histogram should be defined with optimized buckets."""
        from backend.core.metrics import FLORENCE_INFERENCE_DURATION

        assert FLORENCE_INFERENCE_DURATION is not None
        assert FLORENCE_INFERENCE_DURATION._name == "hsi_florence_inference_seconds"
        # Verify buckets are optimized for vision-language (100ms - 3s range)
        buckets = FLORENCE_INFERENCE_DURATION._upper_bounds
        assert 0.1 in buckets  # 100ms fast
        assert 0.3 in buckets  # 300ms P50
        assert 1.0 in buckets  # 1s P95
        assert 2.0 in buckets  # 2s P99

    def test_observe_yolo26_inference(self) -> None:
        """observe_yolo26_inference should record to workload-specific histogram."""
        from backend.core.metrics import observe_yolo26_inference

        observe_yolo26_inference(0.05)  # 50ms
        observe_yolo26_inference(0.1)  # 100ms
        observe_yolo26_inference(0.03)  # 30ms
        # No assertion needed - no exception means success

    def test_observe_nemotron_inference(self) -> None:
        """observe_nemotron_inference should record to workload-specific histogram."""
        from backend.core.metrics import observe_nemotron_inference

        observe_nemotron_inference(1.0)  # 1s
        observe_nemotron_inference(2.5)  # 2.5s
        observe_nemotron_inference(5.0)  # 5s
        # No assertion needed - no exception means success

    def test_observe_florence_inference(self) -> None:
        """observe_florence_inference should record to workload-specific histogram."""
        from backend.core.metrics import observe_florence_inference

        observe_florence_inference(0.3)  # 300ms
        observe_florence_inference(0.8)  # 800ms
        observe_florence_inference(1.5)  # 1.5s
        # No assertion needed - no exception means success

    def test_workload_histograms_in_metrics_response(self) -> None:
        """Workload-specific histograms should appear in metrics response."""
        from backend.core.metrics import (
            get_metrics_response,
            observe_florence_inference,
            observe_nemotron_inference,
            observe_yolo26_inference,
        )

        # Record metrics to ensure they appear
        observe_yolo26_inference(0.05)
        observe_nemotron_inference(1.0)
        observe_florence_inference(0.3)

        response = get_metrics_response().decode("utf-8")
        assert "hsi_yolo26_inference_seconds" in response
        assert "hsi_nemotron_inference_seconds" in response
        assert "hsi_florence_inference_seconds" in response


class TestMetricsServiceWorkloadMethods:
    """Test MetricsService workload-specific methods."""

    def test_observe_yolo26_inference(self) -> None:
        """MetricsService should observe YOLO26 inference duration."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.observe_yolo26_inference(0.05)
        metrics.observe_yolo26_inference(0.1)

    def test_observe_nemotron_inference(self) -> None:
        """MetricsService should observe Nemotron inference duration."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.observe_nemotron_inference(1.0)
        metrics.observe_nemotron_inference(3.0)

    def test_observe_florence_inference(self) -> None:
        """MetricsService should observe Florence inference duration."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.observe_florence_inference(0.3)
        metrics.observe_florence_inference(0.8)


# =============================================================================
# Exemplar Support Tests (NEM-3379)
# =============================================================================


class TestExemplarSupport:
    """Test exemplar support for trace-metric correlation."""

    def test_get_trace_exemplar_returns_none_without_trace(self) -> None:
        """_get_trace_exemplar should return None when no trace is active."""
        from backend.core.metrics import _get_trace_exemplar

        # Without an active trace, should return None
        result = _get_trace_exemplar()
        assert result is None

    def test_observe_with_exemplar_without_trace(self) -> None:
        """observe_with_exemplar should work without active trace."""
        from backend.core.metrics import YOLO26_INFERENCE_DURATION, observe_with_exemplar

        # Should not raise even without a trace
        observe_with_exemplar(YOLO26_INFERENCE_DURATION, 0.05)

    def test_observe_yolo26_with_exemplar(self) -> None:
        """observe_yolo26_with_exemplar should record to histogram."""
        from backend.core.metrics import observe_yolo26_with_exemplar

        observe_yolo26_with_exemplar(0.05)
        observe_yolo26_with_exemplar(0.1)
        # No assertion needed - no exception means success

    def test_observe_nemotron_with_exemplar(self) -> None:
        """observe_nemotron_with_exemplar should record to histogram."""
        from backend.core.metrics import observe_nemotron_with_exemplar

        observe_nemotron_with_exemplar(1.0)
        observe_nemotron_with_exemplar(2.5)
        # No assertion needed - no exception means success

    def test_observe_florence_with_exemplar(self) -> None:
        """observe_florence_with_exemplar should record to histogram."""
        from backend.core.metrics import observe_florence_with_exemplar

        observe_florence_with_exemplar(0.3)
        observe_florence_with_exemplar(0.8)
        # No assertion needed - no exception means success

    def test_observe_ai_request_with_exemplar(self) -> None:
        """observe_ai_request_with_exemplar should record to histogram with service label."""
        from backend.core.metrics import observe_ai_request_with_exemplar

        observe_ai_request_with_exemplar("yolo26", 0.05)
        observe_ai_request_with_exemplar("nemotron", 1.5)
        observe_ai_request_with_exemplar("florence", 0.5)
        # No assertion needed - no exception means success

    def test_get_trace_exemplar_with_mock_span(self) -> None:
        """_get_trace_exemplar should return trace_id when span is recording."""
        from unittest.mock import MagicMock, patch

        from backend.core.metrics import _get_trace_exemplar

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_span_context = MagicMock()
        mock_span_context.is_valid = True
        mock_span_context.trace_id = 12345678901234567890123456789012
        mock_span.get_span_context.return_value = mock_span_context

        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            result = _get_trace_exemplar()

        assert result is not None
        assert "trace_id" in result
        assert len(result["trace_id"]) == 32  # 32 hex chars

    def test_get_trace_exemplar_with_non_recording_span(self) -> None:
        """_get_trace_exemplar should return None when span is not recording."""
        from unittest.mock import MagicMock, patch

        from backend.core.metrics import _get_trace_exemplar

        mock_span = MagicMock()
        mock_span.is_recording.return_value = False

        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            result = _get_trace_exemplar()

        assert result is None


# =============================================================================
# NEM-3795: Disabled _created Suffix Metrics Test
# =============================================================================


class TestCreatedMetricsDisabled:
    """Test that _created suffix metrics are disabled (NEM-3795).

    The _created suffix adds a Unix timestamp metric for each counter, histogram,
    and summary indicating when the metric was first created. While useful for
    some use cases, it doubles the metric cardinality. By disabling it, we
    reduce Prometheus storage and query overhead by approximately 50%.
    """

    def test_created_suffix_metrics_not_in_response(self) -> None:
        """Metrics response should NOT contain _created suffix metrics.

        This test verifies that the prometheus_client.disable_created_metrics()
        call at the top of metrics.py successfully prevents _created metrics
        from being generated. Without this optimization, counters like
        hsi_events_created_total would have a companion metric
        hsi_events_created_total_created with a Unix timestamp.

        Note: We look for patterns like "*_total_created" or "*_seconds_created"
        which are the actual Prometheus _created suffix patterns. We need to
        exclude metric names that happen to contain the word "created" as part
        of their semantic name (e.g., hsi_events_created_total counts events
        that were created).
        """
        from backend.core.metrics import get_metrics_response

        # Get the full metrics response
        response = get_metrics_response().decode("utf-8")

        # Split into lines for easier debugging if test fails
        lines = response.split("\n")

        # The _created suffix is appended to the full metric name.
        # For counters: metric_total -> metric_total_created
        # For histograms: metric_seconds -> metric_seconds_created
        # We need to find lines that end with "_created" followed by labels/value
        # Patterns to look for (these are the actual Prometheus _created suffixes):
        created_suffix_patterns = [
            "_total_created",  # Counter created timestamps
            "_seconds_created",  # Histogram created timestamps
            "_bucket_created",  # Shouldn't exist but check anyway
            "_count_created",  # Shouldn't exist but check anyway
            "_sum_created",  # Shouldn't exist but check anyway
        ]

        # Check that no lines contain the _created suffix pattern
        # Exclude comment lines (TYPE/HELP declarations)
        created_lines = [
            line
            for line in lines
            if any(pattern in line for pattern in created_suffix_patterns)
            and not line.startswith("# ")
        ]

        # If any _created metrics are found, the test fails
        assert len(created_lines) == 0, (
            f"Found {len(created_lines)} _created suffix metrics. "
            f"disable_created_metrics() may not be working. "
            f"First few: {created_lines[:5]}"
        )

    def test_counter_metrics_exist_without_created_suffix(self) -> None:
        """Counters should exist normally, just without _created companion metrics."""
        from backend.core.metrics import get_metrics_response, record_event_created

        # Record a metric to ensure it exists
        record_event_created()

        response = get_metrics_response().decode("utf-8")

        # The main counter should exist
        assert "hsi_events_created_total" in response

        # But _created suffix should NOT exist
        # Note: The pattern is "metricname_created" not "metricname_total_created"
        assert "hsi_events_created_created" not in response

    def test_histogram_metrics_exist_without_created_suffix(self) -> None:
        """Histograms should exist normally, just without _created companion metrics."""
        from backend.core.metrics import get_metrics_response, observe_stage_duration

        # Record a metric to ensure it exists
        observe_stage_duration("detect", 0.5)

        response = get_metrics_response().decode("utf-8")

        # The histogram should exist (with bucket, sum, count)
        assert "hsi_stage_duration_seconds_bucket" in response
        assert "hsi_stage_duration_seconds_sum" in response
        assert "hsi_stage_duration_seconds_count" in response

        # But _created suffix should NOT exist
        assert "hsi_stage_duration_seconds_created" not in response


class TestMetricsServiceExemplarMethods:
    """Test MetricsService exemplar methods."""

    def test_observe_yolo26_with_exemplar(self) -> None:
        """MetricsService should observe YOLO26 with exemplar."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.observe_yolo26_with_exemplar(0.05)
        metrics.observe_yolo26_with_exemplar(0.1)

    def test_observe_nemotron_with_exemplar(self) -> None:
        """MetricsService should observe Nemotron with exemplar."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.observe_nemotron_with_exemplar(1.0)
        metrics.observe_nemotron_with_exemplar(3.0)

    def test_observe_florence_with_exemplar(self) -> None:
        """MetricsService should observe Florence with exemplar."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.observe_florence_with_exemplar(0.3)
        metrics.observe_florence_with_exemplar(0.8)

    def test_observe_ai_request_with_exemplar(self) -> None:
        """MetricsService should observe AI request with exemplar."""
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.observe_ai_request_with_exemplar("yolo26", 0.05)
        metrics.observe_ai_request_with_exemplar("nemotron", 1.5)


class TestProcessMemoryMetrics:
    """Test process memory metrics (NEM-3890)."""

    def test_process_memory_rss_metric_exists(self) -> None:
        """PROCESS_MEMORY_RSS_BYTES gauge should be defined."""
        from backend.core.metrics import PROCESS_MEMORY_RSS_BYTES

        assert PROCESS_MEMORY_RSS_BYTES is not None
        assert PROCESS_MEMORY_RSS_BYTES._name == "hsi_process_memory_rss_bytes"

    def test_process_memory_container_limit_metric_exists(self) -> None:
        """PROCESS_MEMORY_CONTAINER_LIMIT_BYTES gauge should be defined."""
        from backend.core.metrics import PROCESS_MEMORY_CONTAINER_LIMIT_BYTES

        assert PROCESS_MEMORY_CONTAINER_LIMIT_BYTES is not None
        assert (
            PROCESS_MEMORY_CONTAINER_LIMIT_BYTES._name == "hsi_process_memory_container_limit_bytes"
        )

    def test_process_memory_container_usage_metric_exists(self) -> None:
        """PROCESS_MEMORY_CONTAINER_USAGE_RATIO gauge should be defined."""
        from backend.core.metrics import PROCESS_MEMORY_CONTAINER_USAGE_RATIO

        assert PROCESS_MEMORY_CONTAINER_USAGE_RATIO is not None
        assert (
            PROCESS_MEMORY_CONTAINER_USAGE_RATIO._name == "hsi_process_memory_container_usage_ratio"
        )

    def test_update_process_memory_metrics_with_container_limit(self) -> None:
        """update_process_memory_metrics should update all gauges with container limit."""
        from backend.core.metrics import (
            PROCESS_MEMORY_CONTAINER_LIMIT_BYTES,
            PROCESS_MEMORY_CONTAINER_USAGE_RATIO,
            PROCESS_MEMORY_RSS_BYTES,
            update_process_memory_metrics,
        )

        update_process_memory_metrics(
            rss_bytes=2_147_483_648,  # 2GB
            container_limit_bytes=6_442_450_944,  # 6GB
            container_usage_percent=33.3,
        )

        # Verify gauges are updated
        assert PROCESS_MEMORY_RSS_BYTES._value._value == 2_147_483_648
        assert PROCESS_MEMORY_CONTAINER_LIMIT_BYTES._value._value == 6_442_450_944
        # Container usage ratio should be percent / 100
        assert abs(PROCESS_MEMORY_CONTAINER_USAGE_RATIO._value._value - 0.333) < 0.001

    def test_update_process_memory_metrics_without_container_limit(self) -> None:
        """update_process_memory_metrics should handle None container limit."""
        from backend.core.metrics import (
            PROCESS_MEMORY_CONTAINER_LIMIT_BYTES,
            PROCESS_MEMORY_CONTAINER_USAGE_RATIO,
            PROCESS_MEMORY_RSS_BYTES,
            update_process_memory_metrics,
        )

        update_process_memory_metrics(
            rss_bytes=1_073_741_824,  # 1GB
            container_limit_bytes=None,
            container_usage_percent=None,
        )

        # RSS should still be set
        assert PROCESS_MEMORY_RSS_BYTES._value._value == 1_073_741_824
        # Container limit and usage should be 0 when not available
        assert PROCESS_MEMORY_CONTAINER_LIMIT_BYTES._value._value == 0
        assert PROCESS_MEMORY_CONTAINER_USAGE_RATIO._value._value == 0.0

    def test_metrics_response_contains_process_memory_metrics(self) -> None:
        """Metrics response should contain process memory metrics (NEM-3890)."""
        response = get_metrics_response().decode("utf-8")

        assert "hsi_process_memory_rss_bytes" in response
        assert "hsi_process_memory_container_limit_bytes" in response
        assert "hsi_process_memory_container_usage_ratio" in response
