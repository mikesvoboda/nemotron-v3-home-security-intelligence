"""Unit tests for the Florence HTTP client service.

Tests for backend/services/florence_client.py which provides an HTTP client
interface to the ai-florence service.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image

from backend.services.florence_client import (
    CaptionedRegion,
    Detection,
    FlorenceClient,
    FlorenceUnavailableError,
    OCRRegion,
    get_florence_client,
    reset_florence_client,
)


class TestFlorenceClientOCR:
    """Tests for FlorenceClient.ocr() method."""

    @pytest.mark.asyncio
    async def test_ocr_success(self) -> None:
        """Test successful OCR text extraction."""
        with patch("backend.services.florence_client.get_settings") as mock_settings:
            mock_settings.return_value.florence_url = "http://localhost:8092"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = FlorenceClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "text": "Hello World",
                    "inference_time_ms": 50.0,
                }
                mock_client.post.return_value = mock_response

                text = await client.ocr(image)

                assert text == "Hello World"

    @pytest.mark.asyncio
    async def test_ocr_connection_error(self) -> None:
        """Test OCR with connection error raises FlorenceUnavailableError."""
        with patch("backend.services.florence_client.get_settings") as mock_settings:
            mock_settings.return_value.florence_url = "http://localhost:8092"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = FlorenceClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client
                mock_client.post.side_effect = httpx.ConnectError("Connection refused")

                with pytest.raises(FlorenceUnavailableError, match="Failed to connect"):
                    await client.ocr(image)

    @pytest.mark.asyncio
    async def test_ocr_timeout(self) -> None:
        """Test OCR with timeout raises FlorenceUnavailableError."""
        with patch("backend.services.florence_client.get_settings") as mock_settings:
            mock_settings.return_value.florence_url = "http://localhost:8092"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = FlorenceClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client
                mock_client.post.side_effect = httpx.TimeoutException("Timeout")

                with pytest.raises(FlorenceUnavailableError, match="timed out"):
                    await client.ocr(image)

    @pytest.mark.asyncio
    async def test_ocr_malformed_response(self) -> None:
        """Test OCR with malformed response returns empty string."""
        with patch("backend.services.florence_client.get_settings") as mock_settings:
            mock_settings.return_value.florence_url = "http://localhost:8092"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = FlorenceClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"inference_time_ms": 50.0}
                mock_client.post.return_value = mock_response

                text = await client.ocr(image)
                assert text == ""


class TestFlorenceClientOCRWithRegions:
    """Tests for FlorenceClient.ocr_with_regions() method."""

    @pytest.mark.asyncio
    async def test_ocr_with_regions_success(self) -> None:
        """Test successful OCR with regions extraction."""
        with patch("backend.services.florence_client.get_settings") as mock_settings:
            mock_settings.return_value.florence_url = "http://localhost:8092"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = FlorenceClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "regions": [
                        {"text": "Hello", "bbox": [10, 10, 50, 10, 50, 30, 10, 30]},
                        {"text": "World", "bbox": [60, 10, 100, 10, 100, 30, 60, 30]},
                    ],
                    "inference_time_ms": 60.0,
                }
                mock_client.post.return_value = mock_response

                regions = await client.ocr_with_regions(image)

                assert len(regions) == 2
                assert isinstance(regions[0], OCRRegion)
                assert regions[0].text == "Hello"
                assert regions[1].text == "World"

    @pytest.mark.asyncio
    async def test_ocr_with_regions_connection_error(self) -> None:
        """Test OCR with regions connection error raises FlorenceUnavailableError."""
        with patch("backend.services.florence_client.get_settings") as mock_settings:
            mock_settings.return_value.florence_url = "http://localhost:8092"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = FlorenceClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client
                mock_client.post.side_effect = httpx.ConnectError("Connection refused")

                with pytest.raises(FlorenceUnavailableError, match="Failed to connect"):
                    await client.ocr_with_regions(image)

    @pytest.mark.asyncio
    async def test_ocr_with_regions_malformed_response(self) -> None:
        """Test OCR with regions malformed response returns empty list."""
        with patch("backend.services.florence_client.get_settings") as mock_settings:
            mock_settings.return_value.florence_url = "http://localhost:8092"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = FlorenceClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"inference_time_ms": 60.0}
                mock_client.post.return_value = mock_response

                regions = await client.ocr_with_regions(image)
                assert regions == []


class TestFlorenceClientDetect:
    """Tests for FlorenceClient.detect() method."""

    @pytest.mark.asyncio
    async def test_detect_success(self) -> None:
        """Test successful object detection."""
        with patch("backend.services.florence_client.get_settings") as mock_settings:
            mock_settings.return_value.florence_url = "http://localhost:8092"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = FlorenceClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "detections": [
                        {"label": "person", "bbox": [10, 20, 100, 200], "score": 0.95},
                        {"label": "car", "bbox": [150, 50, 300, 180], "score": 0.87},
                    ],
                    "inference_time_ms": 45.0,
                }
                mock_client.post.return_value = mock_response

                detections = await client.detect(image)

                assert len(detections) == 2
                assert isinstance(detections[0], Detection)
                assert detections[0].label == "person"
                assert detections[0].score == 0.95
                assert detections[1].label == "car"

    @pytest.mark.asyncio
    async def test_detect_connection_error(self) -> None:
        """Test detect with connection error raises FlorenceUnavailableError."""
        with patch("backend.services.florence_client.get_settings") as mock_settings:
            mock_settings.return_value.florence_url = "http://localhost:8092"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = FlorenceClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client
                mock_client.post.side_effect = httpx.ConnectError("Connection refused")

                with pytest.raises(FlorenceUnavailableError, match="Failed to connect"):
                    await client.detect(image)

    @pytest.mark.asyncio
    async def test_detect_malformed_response(self) -> None:
        """Test detect with malformed response returns empty list."""
        with patch("backend.services.florence_client.get_settings") as mock_settings:
            mock_settings.return_value.florence_url = "http://localhost:8092"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = FlorenceClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"inference_time_ms": 45.0}
                mock_client.post.return_value = mock_response

                detections = await client.detect(image)
                assert detections == []


class TestFlorenceClientDenseCaption:
    """Tests for FlorenceClient.dense_caption() method."""

    @pytest.mark.asyncio
    async def test_dense_caption_success(self) -> None:
        """Test successful dense captioning."""
        with patch("backend.services.florence_client.get_settings") as mock_settings:
            mock_settings.return_value.florence_url = "http://localhost:8092"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = FlorenceClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "regions": [
                        {"caption": "a person walking", "bbox": [10, 20, 100, 200]},
                        {"caption": "a red car parked", "bbox": [150, 50, 300, 180]},
                    ],
                    "inference_time_ms": 80.0,
                }
                mock_client.post.return_value = mock_response

                regions = await client.dense_caption(image)

                assert len(regions) == 2
                assert isinstance(regions[0], CaptionedRegion)
                assert regions[0].caption == "a person walking"
                assert regions[1].caption == "a red car parked"

    @pytest.mark.asyncio
    async def test_dense_caption_connection_error(self) -> None:
        """Test dense_caption with connection error raises FlorenceUnavailableError."""
        with patch("backend.services.florence_client.get_settings") as mock_settings:
            mock_settings.return_value.florence_url = "http://localhost:8092"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = FlorenceClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client
                mock_client.post.side_effect = httpx.ConnectError("Connection refused")

                with pytest.raises(FlorenceUnavailableError, match="Failed to connect"):
                    await client.dense_caption(image)

    @pytest.mark.asyncio
    async def test_dense_caption_malformed_response(self) -> None:
        """Test dense_caption with malformed response returns empty list."""
        with patch("backend.services.florence_client.get_settings") as mock_settings:
            mock_settings.return_value.florence_url = "http://localhost:8092"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = FlorenceClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"inference_time_ms": 80.0}
                mock_client.post.return_value = mock_response

                regions = await client.dense_caption(image)
                assert regions == []


class TestGlobalClientFunctions:
    """Tests for global client singleton functions."""

    def test_get_florence_client_singleton(self) -> None:
        """Test get_florence_client returns singleton instance."""
        reset_florence_client()

        with patch("backend.services.florence_client.get_settings") as mock_settings:
            mock_settings.return_value.florence_url = "http://localhost:8092"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client1 = get_florence_client()
            client2 = get_florence_client()

            assert client1 is client2

        reset_florence_client()

    def test_reset_florence_client(self) -> None:
        """Test reset_florence_client clears the singleton."""
        reset_florence_client()

        with patch("backend.services.florence_client.get_settings") as mock_settings:
            mock_settings.return_value.florence_url = "http://localhost:8092"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client1 = get_florence_client()
            reset_florence_client()
            client2 = get_florence_client()

            assert client1 is not client2

        reset_florence_client()


class TestFlorenceUnavailableError:
    """Tests for FlorenceUnavailableError exception."""

    def test_error_with_message(self) -> None:
        """Test error creation with message."""
        error = FlorenceUnavailableError("Service unavailable")
        assert str(error) == "Service unavailable"
        assert error.original_error is None

    def test_error_with_original_error(self) -> None:
        """Test error creation with original error."""
        original = ValueError("Original error")
        error = FlorenceUnavailableError("Wrapped error", original_error=original)
        assert str(error) == "Wrapped error"
        assert error.original_error is original


class TestDataclasses:
    """Tests for dataclass models."""

    def test_ocr_region(self) -> None:
        """Test OCRRegion dataclass."""
        region = OCRRegion(text="Hello", bbox=[10, 10, 50, 10, 50, 30, 10, 30])
        assert region.text == "Hello"
        assert region.bbox == [10, 10, 50, 10, 50, 30, 10, 30]

    def test_detection(self) -> None:
        """Test Detection dataclass."""
        detection = Detection(label="person", bbox=[10, 20, 100, 200], score=0.95)
        assert detection.label == "person"
        assert detection.bbox == [10, 20, 100, 200]
        assert detection.score == 0.95

    def test_detection_default_score(self) -> None:
        """Test Detection dataclass with default score."""
        detection = Detection(label="car", bbox=[0, 0, 50, 50])
        assert detection.score == 1.0

    def test_captioned_region(self) -> None:
        """Test CaptionedRegion dataclass."""
        region = CaptionedRegion(caption="a person walking", bbox=[10, 20, 100, 200])
        assert region.caption == "a person walking"
        assert region.bbox == [10, 20, 100, 200]
