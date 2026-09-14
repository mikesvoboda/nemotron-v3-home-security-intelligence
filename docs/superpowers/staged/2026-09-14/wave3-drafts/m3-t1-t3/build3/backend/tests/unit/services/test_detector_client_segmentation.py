"""Unit tests for DetectorClient instance segmentation support (NEM-3912).

Tests for the segment_image method added to DetectorClient.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.services.detector_client import DetectorClient


class TestDetectorClientSegmentation:
    """Test the segment_image method on DetectorClient."""

    @pytest.fixture
    def mock_http_client(self):
        """Create a mock HTTP client."""
        mock = AsyncMock()
        mock.post = AsyncMock()
        return mock

    @pytest.fixture
    def detector_client(self, mock_http_client):
        """Create a DetectorClient with mocked HTTP client."""
        with patch.object(DetectorClient, "_get_semaphore", return_value=AsyncMock()):
            client = DetectorClient()
            client._http_client = mock_http_client
            return client

    @pytest.mark.asyncio
    async def test_segment_image_success(self, detector_client, mock_http_client):
        """Test successful segmentation request."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "detections": [
                {
                    "class": "person",
                    "confidence": 0.95,
                    "bbox": {"x": 100, "y": 150, "width": 200, "height": 400},
                    "mask_rle": {"counts": [32, 2, 8, 2, 46], "size": [480, 640]},
                    "mask_polygon": [[100, 150, 300, 150, 300, 550, 100, 550]],
                }
            ],
            "inference_time_ms": 45.2,
            "image_width": 640,
            "image_height": 480,
        }
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        # Make request
        image_data = b"fake_image_data"
        result = await detector_client.segment_image(image_data)

        # Verify result
        assert "detections" in result
        assert len(result["detections"]) == 1
        assert result["detections"][0]["class"] == "person"
        assert "mask_rle" in result["detections"][0]
        assert "mask_polygon" in result["detections"][0]

    @pytest.mark.asyncio
    async def test_segment_image_calls_segment_endpoint(self, detector_client, mock_http_client):
        """Test that segment_image calls the /segment endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"detections": []}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        await detector_client.segment_image(b"fake_image")

        # Verify the correct endpoint was called
        call_args = mock_http_client.post.call_args
        assert "/segment" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_segment_image_retries_on_connection_error(
        self, detector_client, mock_http_client
    ):
        """Test that segment_image retries on connection errors."""
        # First call fails, second succeeds
        mock_response = MagicMock()
        mock_response.json.return_value = {"detections": []}
        mock_response.raise_for_status = MagicMock()

        mock_http_client.post.side_effect = [
            httpx.ConnectError("Connection failed"),
            mock_response,
        ]

        # Should succeed on retry
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await detector_client.segment_image(b"fake_image")

        assert result == {"detections": []}
        assert mock_http_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_segment_image_raises_on_all_retries_exhausted(
        self, detector_client, mock_http_client
    ):
        """Test that segment_image raises after all retries exhausted."""
        from backend.core.exceptions import DetectorUnavailableError

        # All calls fail
        mock_http_client.post.side_effect = httpx.ConnectError("Connection failed")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(DetectorUnavailableError):
                await detector_client.segment_image(b"fake_image")

    @pytest.mark.asyncio
    async def test_segment_image_raises_value_error_on_4xx(self, detector_client, mock_http_client):
        """Test that segment_image raises ValueError on 4xx errors."""
        mock_response = MagicMock()
        mock_response.status_code = 400

        mock_http_client.post.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=mock_response
        )

        with pytest.raises(ValueError, match="Segmentation client error"):
            await detector_client.segment_image(b"fake_image")

    @pytest.mark.asyncio
    async def test_segment_image_empty_detections(self, detector_client, mock_http_client):
        """Test segment_image with no detections."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "detections": [],
            "inference_time_ms": 30.0,
            "image_width": 640,
            "image_height": 480,
        }
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        result = await detector_client.segment_image(b"fake_image")

        assert result["detections"] == []


class TestSegmentImageIntegration:
    """Integration tests for segment_image method."""

    @pytest.mark.asyncio
    async def test_segment_image_method_exists(self):
        """Test that DetectorClient has segment_image method."""
        assert hasattr(DetectorClient, "segment_image")
        assert callable(DetectorClient.segment_image)
