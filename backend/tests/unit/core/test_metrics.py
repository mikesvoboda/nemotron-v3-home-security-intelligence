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

    def test_observe_ai_request_duration_rtdetr(self) -> None:
        """observe_ai_request_duration should record RT-DETRv2 duration."""
        observe_ai_request_duration("rtdetr", 0.3)

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
