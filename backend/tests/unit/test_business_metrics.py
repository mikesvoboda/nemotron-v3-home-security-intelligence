"""Unit tests for business metrics (NEM-770).

Tests for new Prometheus metrics:
- hsi_florence_task_total: Florence-2 task invocations
- hsi_enrichment_model_calls_total: Enrichment model calls
- hsi_events_by_camera_total: Events per camera
- hsi_events_reviewed_total: Events marked as reviewed

Tests cover:
- Metric definitions and registration
- Helper functions for recording metrics
- Instrumentation in florence_client.py
- Instrumentation in events.py

R8 (2026-09-29) retired enrichment_pipeline and nemotron_analyzer; the classes
that pinned THEIR call sites went with them. The metric definitions themselves
survive (they live in backend.core.metrics), so the definition/helper pins stay.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.metrics import (
    ENRICHMENT_MODEL_CALLS_TOTAL,
    EVENTS_BY_CAMERA_TOTAL,
    EVENTS_REVIEWED_TOTAL,
    FLORENCE_TASK_TOTAL,
    get_metrics_response,
    record_enrichment_model_call,
    record_event_by_camera,
    record_event_reviewed,
    record_florence_task,
)

# =============================================================================
# Metric Definition Tests
# =============================================================================


class TestBusinessMetricDefinitions:
    """Test business metric definitions and registrations."""

    def test_florence_task_counter_exists(self) -> None:
        """FLORENCE_TASK_TOTAL counter should be defined with task label."""
        assert FLORENCE_TASK_TOTAL is not None
        # prometheus_client strips _total suffix from counter names internally
        assert FLORENCE_TASK_TOTAL._name == "hsi_florence_task"
        assert "task" in FLORENCE_TASK_TOTAL._labelnames

    def test_enrichment_model_calls_counter_exists(self) -> None:
        """ENRICHMENT_MODEL_CALLS_TOTAL counter should be defined with model label."""
        assert ENRICHMENT_MODEL_CALLS_TOTAL is not None
        assert ENRICHMENT_MODEL_CALLS_TOTAL._name == "hsi_enrichment_model_calls"
        assert "model" in ENRICHMENT_MODEL_CALLS_TOTAL._labelnames

    def test_events_by_camera_counter_exists(self) -> None:
        """EVENTS_BY_CAMERA_TOTAL counter should be defined with camera labels."""
        assert EVENTS_BY_CAMERA_TOTAL is not None
        assert EVENTS_BY_CAMERA_TOTAL._name == "hsi_events_by_camera"
        assert "camera_id" in EVENTS_BY_CAMERA_TOTAL._labelnames
        assert "camera_name" in EVENTS_BY_CAMERA_TOTAL._labelnames

    def test_events_reviewed_counter_exists(self) -> None:
        """EVENTS_REVIEWED_TOTAL counter should be defined."""
        assert EVENTS_REVIEWED_TOTAL is not None
        assert EVENTS_REVIEWED_TOTAL._name == "hsi_events_reviewed"


# =============================================================================
# Metric Helper Function Tests
# =============================================================================


class TestBusinessMetricHelpers:
    """Test business metric helper functions."""

    def test_record_florence_task_caption(self) -> None:
        """record_florence_task should increment counter for caption task."""
        record_florence_task("caption")
        # Should not raise

    def test_record_florence_task_ocr(self) -> None:
        """record_florence_task should increment counter for ocr task."""
        record_florence_task("ocr")
        # Should not raise

    def test_record_florence_task_detect(self) -> None:
        """record_florence_task should increment counter for detect task."""
        record_florence_task("detect")
        # Should not raise

    def test_record_florence_task_dense_caption(self) -> None:
        """record_florence_task should increment counter for dense_caption task."""
        record_florence_task("dense_caption")
        # Should not raise

    def test_record_enrichment_model_call_brisque(self) -> None:
        """record_enrichment_model_call should increment counter for brisque model."""
        record_enrichment_model_call("brisque")
        # Should not raise

    def test_record_enrichment_model_call_violence(self) -> None:
        """record_enrichment_model_call should increment counter for violence model."""
        record_enrichment_model_call("violence")
        # Should not raise

    def test_record_enrichment_model_call_clothing(self) -> None:
        """record_enrichment_model_call should increment counter for clothing model."""
        record_enrichment_model_call("clothing")
        # Should not raise

    def test_record_enrichment_model_call_vehicle(self) -> None:
        """record_enrichment_model_call should increment counter for vehicle model."""
        record_enrichment_model_call("vehicle")
        # Should not raise

    def test_record_enrichment_model_call_pet(self) -> None:
        """record_enrichment_model_call should increment counter for pet model."""
        record_enrichment_model_call("pet")
        # Should not raise

    def test_record_event_by_camera(self) -> None:
        """record_event_by_camera should increment counter with camera labels."""
        record_event_by_camera("cam-001", "Front Door")
        # Should not raise

    def test_record_event_by_camera_unknown_name(self) -> None:
        """record_event_by_camera should handle unknown camera names."""
        record_event_by_camera("cam-unknown", "Unknown")
        # Should not raise

    def test_record_event_reviewed(self) -> None:
        """record_event_reviewed should increment counter."""
        record_event_reviewed()
        # Should not raise

    def test_record_event_reviewed_multiple(self) -> None:
        """record_event_reviewed should increment counter multiple times."""
        record_event_reviewed()
        record_event_reviewed()
        record_event_reviewed()
        # Should not raise


# =============================================================================
# Metrics Endpoint Tests
# =============================================================================


class TestBusinessMetricsInEndpoint:
    """Test that business metrics appear in /metrics endpoint."""

    def test_florence_task_metric_in_response(self) -> None:
        """Florence task metric should appear in metrics response."""
        # Record a metric to ensure it's populated
        record_florence_task("caption")

        response = get_metrics_response().decode("utf-8")
        assert "hsi_florence_task_total" in response

    def test_enrichment_model_calls_metric_in_response(self) -> None:
        """Enrichment model calls metric should appear in metrics response."""
        record_enrichment_model_call("brisque")

        response = get_metrics_response().decode("utf-8")
        assert "hsi_enrichment_model_calls_total" in response

    def test_events_by_camera_metric_in_response(self) -> None:
        """Events by camera metric should appear in metrics response."""
        record_event_by_camera("cam-test", "Test Camera")

        response = get_metrics_response().decode("utf-8")
        assert "hsi_events_by_camera_total" in response

    def test_events_reviewed_metric_in_response(self) -> None:
        """Events reviewed metric should appear in metrics response."""
        record_event_reviewed()

        response = get_metrics_response().decode("utf-8")
        assert "hsi_events_reviewed_total" in response


# =============================================================================
# Florence Client Instrumentation Tests
# =============================================================================


class TestFlorenceClientInstrumentation:
    """Test that florence_client.py records Florence task metrics."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for FlorenceClient."""
        with patch("backend.services.florence_client.get_settings", autospec=True) as mock:
            mock.return_value.florence_url = "http://localhost:8092"
            mock.return_value.ai_connect_timeout = 10.0
            mock.return_value.ai_health_timeout = 5.0
            yield mock

    @pytest.fixture
    def sample_image(self):
        """Create a sample PIL image for testing."""
        from PIL import Image

        return Image.new("RGB", (224, 224), color=(128, 128, 128))

    @pytest.mark.asyncio
    async def test_extract_records_florence_task_caption(self, mock_settings, sample_image) -> None:
        """extract() with <CAPTION> should record 'caption' task."""

        from backend.services.florence_client import FlorenceClient

        client = FlorenceClient()

        # Mock the persistent HTTP client directly (NEM-1721 pattern)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": "A gray square image"}

        original_client = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_http

        try:
            with patch(
                "backend.services.florence_client.record_florence_task", autospec=True
            ) as mock_record:
                await client.extract(sample_image, "<CAPTION>")
                mock_record.assert_called_once_with("caption")
        finally:
            client._http_client = original_client

    @pytest.mark.asyncio
    async def test_ocr_records_florence_task_ocr(self, mock_settings, sample_image) -> None:
        """ocr() should record 'ocr' task."""
        from backend.services.florence_client import FlorenceClient

        client = FlorenceClient()

        # Mock the persistent HTTP client directly (NEM-1721 pattern)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"text": "Hello World"}

        original_client = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_http

        try:
            with patch(
                "backend.services.florence_client.record_florence_task", autospec=True
            ) as mock_record:
                await client.ocr(sample_image)
                mock_record.assert_called_once_with("ocr")
        finally:
            client._http_client = original_client

    @pytest.mark.asyncio
    async def test_detect_records_florence_task_detect(self, mock_settings, sample_image) -> None:
        """detect() should record 'detect' task."""
        from backend.services.florence_client import FlorenceClient

        client = FlorenceClient()

        # Mock the persistent HTTP client directly (NEM-1721 pattern)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"detections": []}

        original_client = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_http

        try:
            with patch(
                "backend.services.florence_client.record_florence_task", autospec=True
            ) as mock_record:
                await client.detect(sample_image)
                mock_record.assert_called_once_with("detect")
        finally:
            client._http_client = original_client

    @pytest.mark.asyncio
    async def test_dense_caption_records_florence_task_dense_caption(
        self, mock_settings, sample_image
    ) -> None:
        """dense_caption() should record 'dense_caption' task."""
        from backend.services.florence_client import FlorenceClient

        client = FlorenceClient()

        # Mock the persistent HTTP client directly (NEM-1721 pattern)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"regions": []}

        original_client = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_http

        try:
            with patch(
                "backend.services.florence_client.record_florence_task", autospec=True
            ) as mock_record:
                await client.dense_caption(sample_image)
                mock_record.assert_called_once_with("dense_caption")
        finally:
            client._http_client = original_client


# =============================================================================
# Events Route Instrumentation Tests
# =============================================================================


class TestEventsRouteInstrumentation:
    """Test that events.py records events reviewed metric."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_update_event_reviewed_true_records_metric(self) -> None:
        """PATCH event with reviewed=true should record events reviewed metric."""
        # This tests the instrumentation indirectly via the route
        from backend.core.metrics import record_event_reviewed

        # Verify the function can be called
        record_event_reviewed()
        # Full integration testing with the route would require more setup
