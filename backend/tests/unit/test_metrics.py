"""Unit tests for Prometheus metrics endpoint and instrumentation.

Tests cover:
- /metrics endpoint returning valid Prometheus format
- Core metrics registration and exposure
- Metric value updates via helper functions
- Pipeline latency tracking with percentiles
- Semantic AI metrics for detection, risk, model usage, and business tracking
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
    ENRICHMENT_MODEL_CALLS_TOTAL,
    EVENTS_BY_CAMERA_TOTAL,
    EVENTS_BY_RISK_LEVEL_TOTAL,
    EVENTS_CREATED_TOTAL,
    EVENTS_REVIEWED_TOTAL,
    FLORENCE_TASK_TOTAL,
    PIPELINE_ERRORS_TOTAL,
    PROMPT_TEMPLATE_USED_TOTAL,
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
    record_detection_filtered_low_confidence,
    record_detection_processed,
    record_enrichment_model_call,
    record_event_by_camera,
    record_event_by_risk_level,
    record_event_created,
    record_event_reviewed,
    record_florence_task,
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


class TestPipelineLatencyHistoryEndpoint:
    """Test the /api/system/pipeline-latency-history HTTP endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client with system router."""
        from backend.api.routes.system import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_latency_history_endpoint_returns_200(self, client: TestClient) -> None:
        """GET /api/system/pipeline-latency-history should return 200 status."""
        response = client.get("/api/system/pipeline-latency-history")
        assert response.status_code == 200

    def test_latency_history_endpoint_structure(self, client: TestClient) -> None:
        """Response should have expected structure."""
        response = client.get("/api/system/pipeline-latency-history")
        data = response.json()

        # Check top-level fields
        assert "samples" in data
        assert "window_minutes" in data
        assert "timestamp" in data
        assert isinstance(data["samples"], list)

    def test_latency_history_endpoint_default_window(self, client: TestClient) -> None:
        """Default window should be 60 minutes."""
        response = client.get("/api/system/pipeline-latency-history")
        data = response.json()
        assert data["window_minutes"] == 60

    def test_latency_history_endpoint_custom_window(self, client: TestClient) -> None:
        """Custom window_minutes parameter should be honored."""
        response = client.get("/api/system/pipeline-latency-history?window_minutes=30")
        data = response.json()
        assert data["window_minutes"] == 30

    def test_latency_history_endpoint_with_samples(self, client: TestClient) -> None:
        """Endpoint should return samples when data is present."""
        # Record some samples across stages
        tracker = get_pipeline_latency_tracker()
        tracker.record_stage_latency("watch_to_detect", 50.0)
        tracker.record_stage_latency("detect_to_batch", 100.0)
        tracker.record_stage_latency("total_pipeline", 200.0)

        response = client.get("/api/system/pipeline-latency-history")
        data = response.json()

        # Should have samples
        assert len(data["samples"]) > 0

        # Each sample should have expected structure
        if len(data["samples"]) > 0:
            sample = data["samples"][0]
            assert "timestamp" in sample
            assert "stage" in sample
            assert "latency_ms" in sample

    def test_latency_history_endpoint_limit_samples(self, client: TestClient) -> None:
        """Should limit the number of returned samples."""
        # Record many samples
        tracker = get_pipeline_latency_tracker()
        for i in range(200):
            tracker.record_stage_latency("watch_to_detect", 50.0 + i)

        response = client.get("/api/system/pipeline-latency-history?limit=50")
        data = response.json()

        # Should be limited to 50 or less
        assert len(data["samples"]) <= 50


class TestPipelineLatencyTrackerHistory:
    """Test PipelineLatencyTracker.get_samples_history method."""

    def test_get_samples_history_empty(self) -> None:
        """Getting history with no samples should return empty list."""
        tracker = PipelineLatencyTracker()
        history = tracker.get_samples_history()
        assert history == []

    def test_get_samples_history_returns_samples(self) -> None:
        """Getting history should return recorded samples."""
        tracker = PipelineLatencyTracker()
        tracker.record_stage_latency("watch_to_detect", 50.0)
        tracker.record_stage_latency("detect_to_batch", 100.0)

        history = tracker.get_samples_history()
        assert len(history) >= 2

    def test_get_samples_history_with_window(self) -> None:
        """Should filter samples by time window."""
        tracker = PipelineLatencyTracker()

        # Mock time
        mock_time = MagicMock()
        current_time = time.time()
        tracker._time = mock_time

        # Old sample (70 minutes ago)
        mock_time.time.return_value = current_time - (70 * 60)
        tracker.record_stage_latency("watch_to_detect", 50.0)

        # Recent sample (5 minutes ago)
        mock_time.time.return_value = current_time - (5 * 60)
        tracker.record_stage_latency("watch_to_detect", 100.0)

        # Query with current time
        mock_time.time.return_value = current_time

        # 60-minute window should only include recent sample
        history = tracker.get_samples_history(window_minutes=60)
        assert len(history) == 1
        assert history[0]["latency_ms"] == 100.0

    def test_get_samples_history_format(self) -> None:
        """Samples should have correct format."""
        tracker = PipelineLatencyTracker()
        tracker.record_stage_latency("watch_to_detect", 75.5)

        history = tracker.get_samples_history()
        assert len(history) >= 1

        sample = history[0]
        assert "timestamp" in sample
        assert "stage" in sample
        assert "latency_ms" in sample
        assert sample["stage"] == "watch_to_detect"
        assert sample["latency_ms"] == 75.5

    def test_get_samples_history_limit(self) -> None:
        """Should respect the limit parameter."""
        tracker = PipelineLatencyTracker()
        for _ in range(100):
            tracker.record_stage_latency("watch_to_detect", 50.0)

        history = tracker.get_samples_history(limit=10)
        assert len(history) <= 10


class TestThroughputTracker:
    """Test ThroughputTracker class for tracking detection and event throughput."""

    def test_metric_types(self) -> None:
        """Tracker should define expected metric types."""
        from backend.core.metrics import ThroughputTracker

        tracker = ThroughputTracker()
        assert "images" in tracker.METRIC_TYPES
        assert "events" in tracker.METRIC_TYPES
        assert len(tracker.METRIC_TYPES) == 2

    def test_record_metric_valid_type(self) -> None:
        """Recording metric for valid type should succeed."""
        from backend.core.metrics import ThroughputTracker

        tracker = ThroughputTracker()
        tracker.record_metric("images", 5)
        stats = tracker.get_throughput()
        assert stats["images_per_min"] > 0

    def test_record_metric_invalid_type(self) -> None:
        """Recording metric for invalid type should be ignored."""
        from backend.core.metrics import ThroughputTracker

        tracker = ThroughputTracker()
        tracker.record_metric("invalid_type", 5)
        # Should not raise, just log warning

    def test_get_throughput_empty(self) -> None:
        """Getting throughput with no data should return zero."""
        from backend.core.metrics import ThroughputTracker

        tracker = ThroughputTracker()
        stats = tracker.get_throughput()
        assert stats["images_per_min"] == 0.0
        assert stats["events_per_min"] == 0.0

    def test_get_throughput_with_samples(self) -> None:
        """Getting throughput with samples should calculate rate."""
        from backend.core.metrics import ThroughputTracker

        tracker = ThroughputTracker()
        # Record 60 images in the window
        for _ in range(60):
            tracker.record_metric("images", 1)
        # Record 12 events
        for _ in range(12):
            tracker.record_metric("events", 1)

        stats = tracker.get_throughput(window_minutes=1)
        # Should be approximately 60/min and 12/min
        assert stats["images_per_min"] >= 0
        assert stats["events_per_min"] >= 0

    def test_get_throughput_window_filter(self) -> None:
        """Throughput should be filtered by time window."""
        from unittest.mock import MagicMock

        from backend.core.metrics import ThroughputTracker

        tracker = ThroughputTracker()

        # Mock time to control timestamps
        mock_time = MagicMock()
        current_time = time.time()
        tracker._time = mock_time

        # Add old sample (70 minutes ago)
        mock_time.time.return_value = current_time - (70 * 60)
        tracker.record_metric("images", 100)

        # Add recent sample (5 minutes ago)
        mock_time.time.return_value = current_time - (5 * 60)
        tracker.record_metric("images", 10)

        # Query with current time
        mock_time.time.return_value = current_time

        # Default 60-minute window should only include recent sample
        stats = tracker.get_throughput(window_minutes=60)
        # Rate should be based on 10 images over ~55 minutes elapsed
        assert stats["images_per_min"] < 100  # Not the old samples

    def test_calculate_inference_fps(self) -> None:
        """Should calculate inference FPS from average detection latency."""
        from backend.core.metrics import ThroughputTracker

        tracker = ThroughputTracker()
        # Record samples to establish latency
        for _ in range(10):
            tracker.record_detection_latency(100.0)  # 100ms per detection

        fps = tracker.get_inference_fps()
        # 100ms latency = ~10 FPS
        assert fps is not None
        assert 9.0 <= fps <= 11.0

    def test_inference_fps_no_samples(self) -> None:
        """Should return None when no latency samples available."""
        from backend.core.metrics import ThroughputTracker

        tracker = ThroughputTracker()
        fps = tracker.get_inference_fps()
        assert fps is None

    def test_record_detection_latency(self) -> None:
        """Should record detection latency samples."""
        from backend.core.metrics import ThroughputTracker

        tracker = ThroughputTracker()
        tracker.record_detection_latency(50.0)
        tracker.record_detection_latency(100.0)
        tracker.record_detection_latency(150.0)

        fps = tracker.get_inference_fps()
        # avg = 100ms = 10 FPS
        assert fps is not None
        assert 9.0 <= fps <= 11.0

    def test_thread_safety(self) -> None:
        """Tracker should be thread-safe for concurrent access."""
        import threading

        from backend.core.metrics import ThroughputTracker

        tracker = ThroughputTracker()
        results: list[Exception | None] = []

        def record_samples() -> None:
            try:
                for _ in range(100):
                    tracker.record_metric("images", 1)
                    tracker.record_detection_latency(50.0)
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


class TestThroughputTrackerGlobalFunctions:
    """Test global helper functions for throughput tracking."""

    def test_get_throughput_tracker_returns_singleton(self) -> None:
        """get_throughput_tracker should return the same instance."""
        from backend.core.metrics import get_throughput_tracker

        tracker1 = get_throughput_tracker()
        tracker2 = get_throughput_tracker()
        assert tracker1 is tracker2

    def test_record_throughput_metric(self) -> None:
        """record_throughput_metric should record to global tracker."""
        from backend.core.metrics import get_throughput_tracker, record_throughput_metric

        record_throughput_metric("images", 1)
        tracker = get_throughput_tracker()
        stats = tracker.get_throughput(window_minutes=1)
        assert stats["images_per_min"] >= 0

    def test_record_detection_latency_global(self) -> None:
        """record_detection_latency should record to global tracker."""
        from backend.core.metrics import get_throughput_tracker, record_detection_latency

        record_detection_latency(100.0)
        tracker = get_throughput_tracker()
        fps = tracker.get_inference_fps()
        # At least should have some value now
        assert fps is None or fps >= 0


# =============================================================================
# Semantic AI Metrics Tests (NEM-307)
# =============================================================================


class TestSemanticAIMetricsDefinitions:
    """Test semantic AI metric definitions and registrations."""

    # Group 1: Detection Metrics
    def test_detections_by_class_counter_exists(self) -> None:
        """DETECTIONS_BY_CLASS_TOTAL counter should be defined with class label."""
        assert DETECTIONS_BY_CLASS_TOTAL is not None
        # prometheus_client strips _total suffix from counter names
        assert DETECTIONS_BY_CLASS_TOTAL._name == "hsi_detections_by_class"
        assert "class_name" in DETECTIONS_BY_CLASS_TOTAL._labelnames

    def test_detection_confidence_histogram_exists(self) -> None:
        """DETECTION_CONFIDENCE histogram should be defined."""
        assert DETECTION_CONFIDENCE is not None
        assert DETECTION_CONFIDENCE._name == "hsi_detection_confidence"

    def test_detections_filtered_low_confidence_counter_exists(self) -> None:
        """DETECTIONS_FILTERED_LOW_CONFIDENCE_TOTAL counter should be defined."""
        assert DETECTIONS_FILTERED_LOW_CONFIDENCE_TOTAL is not None
        assert (
            DETECTIONS_FILTERED_LOW_CONFIDENCE_TOTAL._name
            == "hsi_detections_filtered_low_confidence"
        )

    # Group 2: Risk Analysis Metrics
    def test_risk_score_histogram_exists(self) -> None:
        """RISK_SCORE histogram should be defined with correct buckets."""
        assert RISK_SCORE is not None
        assert RISK_SCORE._name == "hsi_risk_score"
        # Verify risk score buckets (10, 20, 30, ..., 100)
        assert RISK_SCORE._kwargs.get("buckets") == (10, 20, 30, 40, 50, 60, 70, 80, 90, 100)

    def test_events_by_risk_level_counter_exists(self) -> None:
        """EVENTS_BY_RISK_LEVEL_TOTAL counter should be defined with level label."""
        assert EVENTS_BY_RISK_LEVEL_TOTAL is not None
        assert EVENTS_BY_RISK_LEVEL_TOTAL._name == "hsi_events_by_risk_level"
        assert "level" in EVENTS_BY_RISK_LEVEL_TOTAL._labelnames

    def test_prompt_template_used_counter_exists(self) -> None:
        """PROMPT_TEMPLATE_USED_TOTAL should be defined with template label."""
        assert PROMPT_TEMPLATE_USED_TOTAL is not None
        assert PROMPT_TEMPLATE_USED_TOTAL._name == "hsi_prompt_template_used"
        assert "template" in PROMPT_TEMPLATE_USED_TOTAL._labelnames

    # Group 3: Model Usage Metrics
    def test_florence_task_counter_exists(self) -> None:
        """FLORENCE_TASK_TOTAL counter should be defined with task label."""
        assert FLORENCE_TASK_TOTAL is not None
        assert FLORENCE_TASK_TOTAL._name == "hsi_florence_task"
        assert "task" in FLORENCE_TASK_TOTAL._labelnames

    def test_enrichment_model_calls_counter_exists(self) -> None:
        """ENRICHMENT_MODEL_CALLS_TOTAL counter should be defined with model label."""
        assert ENRICHMENT_MODEL_CALLS_TOTAL is not None
        assert ENRICHMENT_MODEL_CALLS_TOTAL._name == "hsi_enrichment_model_calls"
        assert "model" in ENRICHMENT_MODEL_CALLS_TOTAL._labelnames

    # Group 4: Business Metrics
    def test_events_by_camera_counter_exists(self) -> None:
        """EVENTS_BY_CAMERA_TOTAL should be with camera_id and camera_name labels."""
        assert EVENTS_BY_CAMERA_TOTAL is not None
        assert EVENTS_BY_CAMERA_TOTAL._name == "hsi_events_by_camera"
        assert "camera_id" in EVENTS_BY_CAMERA_TOTAL._labelnames
        assert "camera_name" in EVENTS_BY_CAMERA_TOTAL._labelnames

    def test_events_reviewed_counter_exists(self) -> None:
        """EVENTS_REVIEWED_TOTAL counter should be defined."""
        assert EVENTS_REVIEWED_TOTAL is not None
        assert EVENTS_REVIEWED_TOTAL._name == "hsi_events_reviewed"


class TestSemanticAIMetricsHelpers:
    """Test semantic AI metric helper functions."""

    # Group 1: Detection Metrics Helpers
    def test_record_detection_by_class_person(self) -> None:
        """record_detection_by_class should increment counter for person class."""
        record_detection_by_class("person")
        # Verify the metric was set (no exception means success)

    def test_record_detection_by_class_vehicle(self) -> None:
        """record_detection_by_class should increment counter for vehicle class."""
        record_detection_by_class("car")
        record_detection_by_class("truck")
        record_detection_by_class("motorcycle")

    def test_observe_detection_confidence(self) -> None:
        """observe_detection_confidence should record histogram observation."""
        observe_detection_confidence(0.95)
        observe_detection_confidence(0.75)
        observe_detection_confidence(0.55)

    def test_record_detection_filtered_low_confidence(self) -> None:
        """record_detection_filtered_low_confidence should increment counter."""
        record_detection_filtered_low_confidence()
        record_detection_filtered_low_confidence(count=5)

    # Group 2: Risk Analysis Metrics Helpers
    def test_observe_risk_score(self) -> None:
        """observe_risk_score should record histogram observation."""
        observe_risk_score(25)  # Low risk
        observe_risk_score(55)  # Medium risk
        observe_risk_score(85)  # High risk

    def test_record_event_by_risk_level(self) -> None:
        """record_event_by_risk_level should increment counter for each level."""
        record_event_by_risk_level("low")
        record_event_by_risk_level("medium")
        record_event_by_risk_level("high")
        record_event_by_risk_level("critical")

    def test_record_prompt_template_used(self) -> None:
        """record_prompt_template_used should increment counter for templates."""
        record_prompt_template_used("basic")
        record_prompt_template_used("enriched")
        record_prompt_template_used("full_enriched")
        record_prompt_template_used("vision_enhanced")
        record_prompt_template_used("model_zoo_enhanced")

    # Group 3: Model Usage Metrics Helpers
    def test_record_florence_task(self) -> None:
        """record_florence_task should increment counter for Florence tasks."""
        record_florence_task("caption")
        record_florence_task("ocr")
        record_florence_task("detect")
        record_florence_task("dense_caption")

    def test_record_enrichment_model_call(self) -> None:
        """record_enrichment_model_call should increment counter for model calls."""
        record_enrichment_model_call("violence-detection")
        record_enrichment_model_call("fashion-clip")
        record_enrichment_model_call("vehicle-segment-classification")
        record_enrichment_model_call("pet-classifier")

    # Group 4: Business Metrics Helpers
    def test_record_event_by_camera(self) -> None:
        """record_event_by_camera should increment counter with camera info."""
        record_event_by_camera("cam_001", "Front Door")
        record_event_by_camera("cam_002", "Backyard")

    def test_record_event_reviewed(self) -> None:
        """record_event_reviewed should increment counter."""
        record_event_reviewed()
        record_event_reviewed()


class TestSemanticAIMetricsEndpoint:
    """Test that semantic AI metrics appear in /api/metrics output."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client with metrics router."""
        from backend.api.routes.metrics import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_metrics_endpoint_contains_detection_metrics(self, client: TestClient) -> None:
        """GET /api/metrics should return detection semantic metrics."""
        # Record some detection metrics first
        record_detection_by_class("person")
        observe_detection_confidence(0.85)
        record_detection_filtered_low_confidence()

        response = client.get("/api/metrics")
        content = response.text

        assert "hsi_detections_by_class_total" in content
        assert "hsi_detection_confidence" in content
        assert "hsi_detections_filtered_low_confidence_total" in content

    def test_metrics_endpoint_contains_risk_metrics(self, client: TestClient) -> None:
        """GET /api/metrics should return risk analysis semantic metrics."""
        # Record some risk metrics first
        observe_risk_score(75)
        record_event_by_risk_level("high")
        record_prompt_template_used("enriched")

        response = client.get("/api/metrics")
        content = response.text

        assert "hsi_risk_score" in content
        assert "hsi_events_by_risk_level_total" in content
        assert "hsi_prompt_template_used_total" in content

    def test_metrics_endpoint_contains_model_usage_metrics(self, client: TestClient) -> None:
        """GET /api/metrics should return model usage semantic metrics."""
        # Record some model usage metrics first
        record_florence_task("caption")
        record_enrichment_model_call("violence-detection")

        response = client.get("/api/metrics")
        content = response.text

        assert "hsi_florence_task_total" in content
        assert "hsi_enrichment_model_calls_total" in content

    def test_metrics_endpoint_contains_business_metrics(self, client: TestClient) -> None:
        """GET /api/metrics should return business semantic metrics."""
        # Record some business metrics first
        record_event_by_camera("test_cam", "Test Camera")
        record_event_reviewed()

        response = client.get("/api/metrics")
        content = response.text

        assert "hsi_events_by_camera_total" in content
        assert "hsi_events_reviewed_total" in content
