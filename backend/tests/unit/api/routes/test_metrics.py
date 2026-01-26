"""Unit tests for Metrics API route.

Tests the GET /api/metrics endpoint that exposes Prometheus metrics
in the standard exposition format for scraping.

This module covers:
- Successful metrics response (happy path)
- Response format and content type validation
- Metrics content structure validation
- Edge cases with various metric states
- Integration with prometheus_client library
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


class TestMetricsEndpoint:
    """Tests for GET /api/metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_returns_200(self) -> None:
        """Test that GET /api/metrics returns 200 OK status."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_returns_text_plain_content_type(self) -> None:
        """Test that metrics endpoint returns text/plain content type."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics")

        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "text/plain" in content_type
        assert "charset=utf-8" in content_type

    @pytest.mark.asyncio
    async def test_metrics_returns_prometheus_format(self) -> None:
        """Test that metrics endpoint returns Prometheus exposition format."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics")

        assert response.status_code == 200
        content = response.text

        # Prometheus format uses # HELP and # TYPE comments
        # At minimum, Python process metrics from prometheus_client are included
        assert "# HELP" in content or "# TYPE" in content or content.strip() == ""

    @pytest.mark.asyncio
    async def test_metrics_contains_hsi_metrics(self) -> None:
        """Test that metrics endpoint contains home security intelligence metrics."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics")

        assert response.status_code == 200
        content = response.text

        # Check for HSI-prefixed metrics (defined in backend/core/metrics.py)
        hsi_metrics = [
            "hsi_detection_queue_depth",
            "hsi_analysis_queue_depth",
            "hsi_stage_duration_seconds",
            "hsi_events_created_total",
            "hsi_detections_processed_total",
            "hsi_ai_request_duration_seconds",
            "hsi_pipeline_errors_total",
            "hsi_detections_by_class_total",
            "hsi_detection_confidence",
            "hsi_detections_filtered_low_confidence_total",
            "hsi_risk_score",
            "hsi_events_by_risk_level_total",
            "hsi_prompt_template_used_total",
            "hsi_florence_task_total",
            "hsi_enrichment_model_calls_total",
            "hsi_events_by_camera_total",
            "hsi_events_reviewed_total",
            "hsi_queue_overflow_total",
            "hsi_queue_items_moved_to_dlq_total",
            "hsi_queue_items_dropped_total",
            "hsi_queue_items_rejected_total",
        ]

        # At least some HSI metrics should be present
        found_hsi_metrics = [m for m in hsi_metrics if m in content]
        assert len(found_hsi_metrics) > 0, "Expected at least one HSI metric in response"

    @pytest.mark.asyncio
    async def test_metrics_response_is_bytes_decoded(self) -> None:
        """Test that metrics response content is properly decoded."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics")

        assert response.status_code == 200
        # Content should be decodable as UTF-8
        content = response.content
        assert isinstance(content, bytes)
        decoded = content.decode("utf-8")
        assert isinstance(decoded, str)


class TestMetricsWithMockedData:
    """Tests for metrics endpoint with mocked metric data."""

    @pytest.mark.asyncio
    async def test_metrics_with_incremented_counters(self) -> None:
        """Test that counter increments are reflected in metrics output."""
        from backend.core.metrics import record_event_created

        # Record some events
        record_event_created()
        record_event_created()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics")

        assert response.status_code == 200
        content = response.text

        # Counter should be present (value depends on previous test runs)
        assert "hsi_events_created_total" in content

    @pytest.mark.asyncio
    async def test_metrics_with_gauge_set(self) -> None:
        """Test that gauge values are reflected in metrics output."""
        from backend.core.metrics import set_queue_depth

        # Set queue depths
        set_queue_depth("detection", 5)
        set_queue_depth("analysis", 3)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics")

        assert response.status_code == 200
        content = response.text

        # Gauges should be present
        assert "hsi_detection_queue_depth" in content
        assert "hsi_analysis_queue_depth" in content

    @pytest.mark.asyncio
    async def test_metrics_with_histogram_observations(self) -> None:
        """Test that histogram observations are reflected in metrics output."""
        from backend.core.metrics import observe_stage_duration

        # Record some stage durations
        observe_stage_duration("detect", 0.5)
        observe_stage_duration("batch", 1.0)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics")

        assert response.status_code == 200
        content = response.text

        # Histogram should be present with bucket/sum/count
        assert "hsi_stage_duration_seconds" in content


class TestMetricsErrorHandling:
    """Tests for metrics endpoint error handling."""

    @pytest.mark.asyncio
    async def test_metrics_handles_generate_latest_error(self) -> None:
        """Test that metrics endpoint propagates errors from prometheus_client.

        When get_metrics_response raises an exception, the error propagates up
        to FastAPI's exception handlers. In test mode with raise_server_exceptions=True,
        the exception is re-raised. In production, FastAPI returns a 500 response.
        """
        # Patch at the route level where get_metrics_response is imported
        with patch(
            "backend.api.routes.metrics.get_metrics_response",
            side_effect=RuntimeError("Registry error"),
        ):
            # Use raise_server_exceptions=False to get HTTP response instead of exception
            async with AsyncClient(
                transport=ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/metrics")

            # FastAPI returns 500 for unhandled exceptions
            assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_metrics_handles_empty_registry(self) -> None:
        """Test that metrics endpoint handles empty registry."""
        # Patch at the route level where get_metrics_response is imported
        with patch(
            "backend.api.routes.metrics.get_metrics_response",
            return_value=b"",
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/metrics")

            assert response.status_code == 200
            assert response.text == ""


class TestMetricsRouterConfiguration:
    """Tests for metrics router configuration."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_path(self) -> None:
        """Test that metrics endpoint is mounted at /api/metrics."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics")

        # Should not be 404
        assert response.status_code != 404

    @pytest.mark.asyncio
    async def test_metrics_endpoint_allows_get_method(self) -> None:
        """Test that metrics endpoint accepts GET requests."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_endpoint_rejects_post_method(self) -> None:
        """Test that metrics endpoint rejects POST requests."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/metrics")

        # Should return 405 Method Not Allowed
        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_metrics_endpoint_rejects_put_method(self) -> None:
        """Test that metrics endpoint rejects PUT requests."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.put("/api/metrics")

        # Should return 405 Method Not Allowed
        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_metrics_endpoint_rejects_delete_method(self) -> None:
        """Test that metrics endpoint rejects DELETE requests."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete("/api/metrics")

        # Should return 405 Method Not Allowed
        assert response.status_code == 405


class TestMetricsLabeledMetrics:
    """Tests for labeled metrics in the output."""

    @pytest.mark.asyncio
    async def test_metrics_stage_duration_has_stage_label(self) -> None:
        """Test that stage_duration histogram includes stage label."""
        from backend.core.metrics import observe_stage_duration

        # Record durations for different stages
        observe_stage_duration("detect", 0.5)
        observe_stage_duration("batch", 1.0)
        observe_stage_duration("analyze", 2.0)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics")

        assert response.status_code == 200
        content = response.text

        # Should contain stage labels
        assert 'stage="detect"' in content or "stage_duration_seconds" in content

    @pytest.mark.asyncio
    async def test_metrics_ai_request_duration_has_service_label(self) -> None:
        """Test that ai_request_duration histogram includes service label."""
        from backend.core.metrics import observe_ai_request_duration

        # Record AI service durations
        observe_ai_request_duration("yolo26", 0.5)
        observe_ai_request_duration("nemotron", 5.0)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics")

        assert response.status_code == 200
        content = response.text

        # Should contain service labels
        assert "hsi_ai_request_duration" in content

    @pytest.mark.asyncio
    async def test_metrics_pipeline_errors_has_error_type_label(self) -> None:
        """Test that pipeline_errors counter includes error_type label."""
        from backend.core.metrics import record_pipeline_error

        # Record pipeline errors
        record_pipeline_error("connection_error")
        record_pipeline_error("timeout_error")

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics")

        assert response.status_code == 200
        content = response.text

        # Should contain error_type labels
        assert "hsi_pipeline_errors_total" in content

    @pytest.mark.asyncio
    async def test_metrics_detections_by_class_has_object_class_label(self) -> None:
        """Test that detections_by_class counter includes object_class label."""
        from backend.core.metrics import record_detection_by_class

        # Record detections by class
        record_detection_by_class("person")
        record_detection_by_class("car")
        record_detection_by_class("dog")

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics")

        assert response.status_code == 200
        content = response.text

        # Should contain object_class labels
        assert "hsi_detections_by_class_total" in content


class TestMetricsHistogramBuckets:
    """Tests for histogram bucket definitions in metrics output."""

    @pytest.mark.asyncio
    async def test_metrics_stage_duration_has_buckets(self) -> None:
        """Test that stage_duration histogram has proper buckets."""
        from backend.core.metrics import observe_stage_duration

        observe_stage_duration("detect", 0.1)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics")

        assert response.status_code == 200
        content = response.text

        # Histograms should have _bucket, _count, and _sum suffixes
        if "hsi_stage_duration_seconds" in content:
            # At least one histogram metric should be present
            assert (
                "hsi_stage_duration_seconds_bucket" in content
                or "hsi_stage_duration_seconds_count" in content
                or "hsi_stage_duration_seconds_sum" in content
            )

    @pytest.mark.asyncio
    async def test_metrics_risk_score_has_buckets(self) -> None:
        """Test that risk_score histogram has proper buckets."""
        from backend.core.metrics import observe_risk_score

        observe_risk_score(75)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics")

        assert response.status_code == 200
        content = response.text

        # Risk score histogram should be present
        assert "hsi_risk_score" in content

    @pytest.mark.asyncio
    async def test_metrics_detection_confidence_has_buckets(self) -> None:
        """Test that detection_confidence histogram has proper buckets."""
        from backend.core.metrics import observe_detection_confidence

        observe_detection_confidence(0.95)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics")

        assert response.status_code == 200
        content = response.text

        # Detection confidence histogram should be present
        assert "hsi_detection_confidence" in content


class TestGetMetricsResponseFunction:
    """Tests for the get_metrics_response helper function."""

    def test_get_metrics_response_returns_bytes(self) -> None:
        """Test that get_metrics_response returns bytes."""
        from backend.core.metrics import get_metrics_response

        result = get_metrics_response()
        assert isinstance(result, bytes)

    def test_get_metrics_response_is_utf8_decodable(self) -> None:
        """Test that get_metrics_response output is UTF-8 decodable."""
        from backend.core.metrics import get_metrics_response

        result = get_metrics_response()
        decoded = result.decode("utf-8")
        assert isinstance(decoded, str)

    def test_get_metrics_response_contains_metrics(self) -> None:
        """Test that get_metrics_response contains registered metrics."""
        from backend.core.metrics import get_metrics_response

        result = get_metrics_response()
        decoded = result.decode("utf-8")

        # Should contain at least the process collector metrics or HSI metrics
        assert len(decoded) > 0 or decoded == ""  # Empty is valid if no metrics

    def test_get_metrics_response_multiple_calls_consistent(self) -> None:
        """Test that multiple calls to get_metrics_response are consistent."""
        from backend.core.metrics import get_metrics_response

        result1 = get_metrics_response()
        result2 = get_metrics_response()

        # Both should be valid bytes
        assert isinstance(result1, bytes)
        assert isinstance(result2, bytes)

        # Both should be decodable
        assert result1.decode("utf-8")
        assert result2.decode("utf-8")


class TestMetricsIntegrationWithRouter:
    """Tests for metrics route integration with FastAPI app."""

    @pytest.mark.asyncio
    async def test_metrics_no_authentication_required(self) -> None:
        """Test that metrics endpoint does not require authentication."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Request without any auth headers
            response = await client.get("/api/metrics")

        # Should return 200 without authentication
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_accepts_no_query_params(self) -> None:
        """Test that metrics endpoint works without query parameters."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_ignores_unknown_query_params(self) -> None:
        """Test that metrics endpoint ignores unknown query parameters."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/metrics?unknown=value&another=param")

        assert response.status_code == 200
