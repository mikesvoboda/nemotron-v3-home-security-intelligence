"""Unit tests for Prometheus metrics endpoint and instrumentation.

Tests cover:
- /metrics endpoint returning valid Prometheus format
- Core metrics registration and exposure
- Metric value updates via helper functions
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.metrics import (
    AI_REQUEST_DURATION,
    ANALYSIS_QUEUE_DEPTH,
    DETECTION_QUEUE_DEPTH,
    DETECTIONS_PROCESSED_TOTAL,
    EVENTS_CREATED_TOTAL,
    PIPELINE_ERRORS_TOTAL,
    STAGE_DURATION_SECONDS,
    get_metrics_response,
    observe_ai_request_duration,
    observe_stage_duration,
    record_detection_processed,
    record_event_created,
    record_pipeline_error,
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
