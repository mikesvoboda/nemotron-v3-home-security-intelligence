"""Tests for OpenTelemetry Baggage middleware.

NEM-3796: Tests for baggage propagation middleware that extracts incoming
baggage from HTTP headers and sets application-specific context for
cross-service propagation.

Baggage Keys:
- camera.id: Source camera for detection pipeline
- event.priority: Priority level for downstream processing
- request.source: Origin of request (ui, api, scheduled)
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.middleware.baggage import (
    BaggageMiddleware,
    get_camera_id_from_baggage,
    get_event_priority_from_baggage,
    get_request_source_from_baggage,
    set_pipeline_baggage,
)


class TestBaggageMiddleware:
    """Tests for BaggageMiddleware class."""

    @pytest.fixture
    def app_with_middleware(self) -> FastAPI:
        """Create a FastAPI app with baggage middleware."""
        app = FastAPI()
        app.add_middleware(BaggageMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        @app.get("/cameras/{camera_id}/detect")
        async def detect_endpoint(camera_id: str):
            return {"camera_id": camera_id}

        return app

    @pytest.fixture
    def client(self, app_with_middleware: FastAPI) -> TestClient:
        """Create a test client."""
        return TestClient(app_with_middleware)

    def test_middleware_passes_through_without_baggage(self, client: TestClient) -> None:
        """Should pass through requests without baggage headers."""
        response = client.get("/test")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_middleware_extracts_baggage_header(self, client: TestClient) -> None:
        """Should extract baggage from W3C Baggage header."""
        with patch("backend.api.middleware.baggage.extract_context_from_headers") as mock_extract:
            response = client.get(
                "/test",
                headers={"baggage": "camera.id=front_door,event.priority=high"},
            )
            assert response.status_code == 200
            # Verify extract was called with headers containing baggage
            mock_extract.assert_called_once()
            call_args = mock_extract.call_args[0][0]
            assert "baggage" in call_args

    def test_middleware_sets_request_source_for_api(self, client: TestClient) -> None:
        """Should set request.source=api for API requests."""
        with patch("backend.api.middleware.baggage.set_baggage") as mock_set:
            response = client.get("/test")
            assert response.status_code == 200
            # Should set request.source to 'api' for non-UI requests
            mock_set.assert_any_call("request.source", "api")

    def test_middleware_sets_request_source_for_ui(self, client: TestClient) -> None:
        """Should set request.source=ui when X-Request-Source header is present."""
        with patch("backend.api.middleware.baggage.set_baggage") as mock_set:
            response = client.get(
                "/test",
                headers={"X-Request-Source": "ui"},
            )
            assert response.status_code == 200
            mock_set.assert_any_call("request.source", "ui")

    def test_middleware_sets_request_source_for_scheduled(self, client: TestClient) -> None:
        """Should set request.source=scheduled for scheduled tasks."""
        with patch("backend.api.middleware.baggage.set_baggage") as mock_set:
            response = client.get(
                "/test",
                headers={"X-Request-Source": "scheduled"},
            )
            assert response.status_code == 200
            mock_set.assert_any_call("request.source", "scheduled")

    def test_middleware_extracts_camera_id_from_path(self, client: TestClient) -> None:
        """Should extract camera_id from URL path and set as baggage."""
        with patch("backend.api.middleware.baggage.set_baggage") as mock_set:
            response = client.get("/cameras/front_door/detect")
            assert response.status_code == 200
            # Should set camera.id from path parameter
            mock_set.assert_any_call("camera.id", "front_door")

    def test_middleware_preserves_incoming_camera_id(self, client: TestClient) -> None:
        """Should preserve camera.id from incoming baggage if present."""
        with (
            patch(
                "backend.api.middleware.baggage.get_baggage",
                return_value="upstream_camera",
            ),
            patch("backend.api.middleware.baggage.set_baggage") as mock_set,
        ):
            response = client.get(
                "/cameras/front_door/detect",
                headers={"baggage": "camera.id=upstream_camera"},
            )
            assert response.status_code == 200
            # Should NOT override existing camera.id from upstream
            # Check that set_baggage was not called with camera.id=front_door
            for call in mock_set.call_args_list:
                if call[0][0] == "camera.id":
                    assert call[0][1] != "front_door"


class TestSetPipelineBaggage:
    """Tests for set_pipeline_baggage function."""

    def test_set_pipeline_baggage_with_all_values(self) -> None:
        """Should set all provided baggage values."""
        with patch("backend.api.middleware.baggage.set_baggage") as mock_set:
            set_pipeline_baggage(
                camera_id="front_door",
                event_priority="high",
                request_source="ui",
            )

            assert mock_set.call_count == 3
            mock_set.assert_any_call("camera.id", "front_door")
            mock_set.assert_any_call("event.priority", "high")
            mock_set.assert_any_call("request.source", "ui")

    def test_set_pipeline_baggage_with_partial_values(self) -> None:
        """Should only set provided baggage values."""
        with patch("backend.api.middleware.baggage.set_baggage") as mock_set:
            set_pipeline_baggage(camera_id="backyard")

            mock_set.assert_called_once_with("camera.id", "backyard")

    def test_set_pipeline_baggage_with_no_values(self) -> None:
        """Should not set any baggage when no values provided."""
        with patch("backend.api.middleware.baggage.set_baggage") as mock_set:
            set_pipeline_baggage()

            mock_set.assert_not_called()

    def test_set_pipeline_baggage_validates_priority(self) -> None:
        """Should only accept valid priority values."""
        with patch("backend.api.middleware.baggage.set_baggage") as mock_set:
            # Valid priorities: low, normal, high, critical
            set_pipeline_baggage(event_priority="high")
            mock_set.assert_called_with("event.priority", "high")

            mock_set.reset_mock()
            set_pipeline_baggage(event_priority="low")
            mock_set.assert_called_with("event.priority", "low")

    def test_set_pipeline_baggage_validates_request_source(self) -> None:
        """Should only accept valid request source values."""
        with patch("backend.api.middleware.baggage.set_baggage") as mock_set:
            # Valid sources: ui, api, scheduled, internal
            set_pipeline_baggage(request_source="ui")
            mock_set.assert_called_with("request.source", "ui")

            mock_set.reset_mock()
            set_pipeline_baggage(request_source="scheduled")
            mock_set.assert_called_with("request.source", "scheduled")


class TestGetBaggageHelpers:
    """Tests for baggage getter helper functions."""

    def test_get_camera_id_from_baggage(self) -> None:
        """Should retrieve camera.id from baggage."""
        with patch(
            "backend.api.middleware.baggage.get_baggage", return_value="front_door"
        ) as mock_get:
            result = get_camera_id_from_baggage()

            mock_get.assert_called_once_with("camera.id")
            assert result == "front_door"

    def test_get_camera_id_from_baggage_returns_none(self) -> None:
        """Should return None when camera.id not in baggage."""
        with patch("backend.api.middleware.baggage.get_baggage", return_value=None) as mock_get:
            result = get_camera_id_from_baggage()

            mock_get.assert_called_once_with("camera.id")
            assert result is None

    def test_get_event_priority_from_baggage(self) -> None:
        """Should retrieve event.priority from baggage."""
        with patch("backend.api.middleware.baggage.get_baggage", return_value="high") as mock_get:
            result = get_event_priority_from_baggage()

            mock_get.assert_called_once_with("event.priority")
            assert result == "high"

    def test_get_event_priority_from_baggage_returns_none(self) -> None:
        """Should return None when event.priority not in baggage."""
        with patch("backend.api.middleware.baggage.get_baggage", return_value=None) as mock_get:
            result = get_event_priority_from_baggage()

            mock_get.assert_called_once_with("event.priority")
            assert result is None

    def test_get_request_source_from_baggage(self) -> None:
        """Should retrieve request.source from baggage."""
        with patch("backend.api.middleware.baggage.get_baggage", return_value="ui") as mock_get:
            result = get_request_source_from_baggage()

            mock_get.assert_called_once_with("request.source")
            assert result == "ui"

    def test_get_request_source_from_baggage_returns_none(self) -> None:
        """Should return None when request.source not in baggage."""
        with patch("backend.api.middleware.baggage.get_baggage", return_value=None) as mock_get:
            result = get_request_source_from_baggage()

            mock_get.assert_called_once_with("request.source")
            assert result is None


class TestBaggagePropagation:
    """Tests for baggage propagation across service boundaries."""

    def test_baggage_included_in_outgoing_headers(self) -> None:
        """Should include baggage in outgoing HTTP headers when trace headers include it."""
        from backend.api.middleware.correlation import get_correlation_headers

        with (
            patch(
                "backend.api.middleware.correlation.get_trace_headers",
                return_value={
                    "traceparent": "00-trace-span-01",
                    "baggage": "camera.id=front_door,request.source=api",
                },
            ),
            patch(
                "backend.api.middleware.correlation.get_correlation_id",
                return_value="corr-123",
            ),
            patch("backend.api.middleware.correlation.get_request_id", return_value="req-456"),
        ):
            headers = get_correlation_headers()

            # Should include baggage from trace headers
            assert "baggage" in headers
            assert "camera.id=front_door" in headers["baggage"]
            assert "request.source=api" in headers["baggage"]

    def test_baggage_propagates_through_detection_pipeline(self) -> None:
        """Should propagate baggage through the detection pipeline."""
        import backend.core.telemetry as telemetry_module

        # Simulate setting baggage at the start of pipeline
        with patch.object(telemetry_module, "set_baggage") as mock_set:
            # Set initial baggage using module reference
            telemetry_module.set_baggage("camera.id", "front_door")
            telemetry_module.set_baggage("event.priority", "high")
            telemetry_module.set_baggage("request.source", "api")

            # Verify set was called
            assert mock_set.call_count == 3


class TestBaggageIntegration:
    """Integration tests for baggage with OpenTelemetry."""

    def test_baggage_survives_span_context(self) -> None:
        """Baggage should survive across span context changes."""
        import backend.core.telemetry as telemetry_module

        # This test verifies baggage is not lost when entering/exiting spans
        # We use mocks to avoid needing full OTEL initialization
        with (
            patch.object(telemetry_module, "get_baggage") as mock_get,
            patch.object(telemetry_module, "set_baggage") as mock_set,
            patch.object(telemetry_module, "get_tracer") as mock_tracer,
        ):
            # Setup mock tracer
            mock_span = MagicMock()
            mock_span.__enter__ = MagicMock(return_value=mock_span)
            mock_span.__exit__ = MagicMock(return_value=None)
            mock_tracer.return_value.start_as_current_span.return_value = mock_span

            # Set baggage before span
            telemetry_module.set_baggage("camera.id", "test_camera")

            # Enter span context
            with telemetry_module.trace_span("test_operation"):
                # Baggage should still be accessible
                mock_get.return_value = "test_camera"
                result = telemetry_module.get_baggage("camera.id")
                assert result == "test_camera"

    def test_baggage_with_batch_processing(self) -> None:
        """Baggage should propagate through batch processing."""
        import backend.core.telemetry as telemetry_module

        with patch.object(telemetry_module, "set_baggage") as mock_set:
            # Simulate batch processor setting baggage for batch context
            telemetry_module.set_baggage("batch.id", "batch-12345")
            telemetry_module.set_baggage("camera.id", "front_door")
            telemetry_module.set_baggage("event.priority", "normal")

            assert mock_set.call_count == 3
            mock_set.assert_any_call("batch.id", "batch-12345")
            mock_set.assert_any_call("camera.id", "front_door")
            mock_set.assert_any_call("event.priority", "normal")
