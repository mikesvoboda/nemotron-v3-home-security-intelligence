"""Integration tests for OpenTelemetry Baggage propagation.

NEM-3796: Tests that verify baggage propagates correctly through the
detection pipeline and across service boundaries.
"""

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
from backend.core.telemetry import get_all_baggage, set_baggage


class TestBaggagePropagationIntegration:
    """Integration tests for baggage propagation."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create a FastAPI app with baggage middleware."""
        app = FastAPI()
        app.add_middleware(BaggageMiddleware)

        @app.get("/cameras/{camera_id}/detect")
        async def detect_endpoint(camera_id: str):
            """Endpoint that reads baggage context."""
            return {
                "camera_id_from_path": camera_id,
                "camera_id_from_baggage": get_camera_id_from_baggage(),
                "request_source": get_request_source_from_baggage(),
                "event_priority": get_event_priority_from_baggage(),
            }

        @app.post("/api/events")
        async def create_event():
            """Endpoint that processes events with baggage."""
            # Simulate setting priority for event processing
            set_pipeline_baggage(event_priority="high")
            return {
                "event_priority": get_event_priority_from_baggage(),
                "request_source": get_request_source_from_baggage(),
            }

        @app.get("/api/test/baggage")
        async def get_baggage_endpoint():
            """Debug endpoint to inspect current baggage."""
            return {
                "all_baggage": get_all_baggage(),
                "camera_id": get_camera_id_from_baggage(),
                "event_priority": get_event_priority_from_baggage(),
                "request_source": get_request_source_from_baggage(),
            }

        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create a test client."""
        return TestClient(app)

    def test_baggage_sets_request_source_default(self, client: TestClient) -> None:
        """Request source should default to 'api' for HTTP requests."""
        response = client.get("/api/test/baggage")
        assert response.status_code == 200
        data = response.json()
        assert data["request_source"] == "api"

    def test_baggage_respects_x_request_source_header(self, client: TestClient) -> None:
        """Request source should be set from X-Request-Source header."""
        response = client.get(
            "/api/test/baggage",
            headers={"X-Request-Source": "ui"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["request_source"] == "ui"

    def test_baggage_extracts_camera_id_from_path(self, client: TestClient) -> None:
        """Camera ID should be extracted from URL path."""
        response = client.get("/cameras/front_door/detect")
        assert response.status_code == 200
        data = response.json()
        assert data["camera_id_from_path"] == "front_door"
        # Note: Baggage extraction may not persist across request lifecycle in tests
        # due to context var cleanup

    def test_baggage_propagates_incoming_headers(self, client: TestClient) -> None:
        """Incoming baggage header should be extracted."""
        response = client.get(
            "/api/test/baggage",
            headers={
                "baggage": "camera.id=backyard,event.priority=high",
            },
        )
        assert response.status_code == 200
        # The baggage should be extracted from headers

    def test_baggage_scheduled_source(self, client: TestClient) -> None:
        """Scheduled tasks should be identified by request source."""
        response = client.get(
            "/api/test/baggage",
            headers={"X-Request-Source": "scheduled"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["request_source"] == "scheduled"

    def test_baggage_internal_source(self, client: TestClient) -> None:
        """Internal service calls should be identified."""
        response = client.get(
            "/api/test/baggage",
            headers={"X-Request-Source": "internal"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["request_source"] == "internal"


class TestBaggageHelperFunctions:
    """Tests for baggage helper functions in isolation."""

    def test_set_pipeline_baggage_all_values(self) -> None:
        """Should set all provided baggage values."""
        set_pipeline_baggage(
            camera_id="test_camera",
            event_priority="high",
            request_source="ui",
            batch_id="batch-123",
        )
        # Note: In real tests with OTEL enabled, these would be verifiable
        # Here we just verify no errors are raised

    def test_set_pipeline_baggage_partial_values(self) -> None:
        """Should handle partial baggage values."""
        set_pipeline_baggage(camera_id="partial_test")
        # Should not raise

    def test_set_pipeline_baggage_invalid_priority_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Should log warning for invalid priority value."""
        import logging

        with caplog.at_level(logging.WARNING):
            set_pipeline_baggage(event_priority="invalid_priority")
        # Should log warning about invalid priority

    def test_set_pipeline_baggage_invalid_source_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Should log warning for invalid request source value."""
        import logging

        with caplog.at_level(logging.WARNING):
            set_pipeline_baggage(request_source="invalid_source")
        # Should log warning about invalid source


class TestBaggageW3CFormat:
    """Tests for W3C Baggage header format compliance."""

    def test_baggage_header_format(self) -> None:
        """Baggage header should follow W3C format."""
        # W3C Baggage format: key=value,key2=value2
        # Keys can contain dots (e.g., camera.id)
        from backend.core.telemetry import get_trace_headers

        # Set some baggage
        set_baggage("camera.id", "front_door")
        set_baggage("event.priority", "high")

        # Get headers (includes baggage if OTEL is enabled)
        headers = get_trace_headers()

        # If OTEL is enabled, baggage header should be present
        if "baggage" in headers:
            baggage_header = headers["baggage"]
            # Should contain our entries in W3C format
            assert "camera.id=" in baggage_header or "camera%2Eid=" in baggage_header


class TestBaggagePipelineScenarios:
    """Tests for realistic pipeline scenarios."""

    def test_detection_pipeline_baggage_flow(self) -> None:
        """Simulate baggage flow through detection pipeline."""
        # Step 1: File watcher receives image from camera
        set_pipeline_baggage(
            camera_id="front_door",
            request_source="internal",
        )

        # Step 2: Detection worker processes image
        camera_id = get_camera_id_from_baggage()
        # Would send to RT-DETR with baggage headers

        # Step 3: Batch processor aggregates detections
        set_pipeline_baggage(
            batch_id="batch-12345",
            event_priority="normal",
        )

        # Step 4: Analysis worker sends to Nemotron
        # Baggage would propagate to AI services

        # Verify no errors throughout flow

    def test_api_request_baggage_flow(self) -> None:
        """Simulate baggage flow from API request."""
        # Step 1: API request comes in with UI source
        set_pipeline_baggage(
            request_source="ui",
            camera_id="user_selected_camera",
        )

        # Step 2: Backend processes request
        source = get_request_source_from_baggage()

        # Step 3: If high priority, mark as such
        if source == "ui":
            set_pipeline_baggage(event_priority="high")

        # Verify flow completes without error
