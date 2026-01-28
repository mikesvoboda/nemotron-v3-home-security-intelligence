"""Unit tests for the Florence HTTP client service.

Tests for backend/services/florence_client.py which provides an HTTP client
interface to the ai-florence service.

Tests cover:
    - Client initialization (default URL, custom URL, base_url parameter)
- check_health() method and error handling
- extract() method for image captioning and VQA
- ocr() method for text extraction
- ocr_with_regions() method for text with bounding boxes
- detect() method for object detection
- dense_caption() method for region captioning
- Error handling (connection errors, timeouts, HTTP 4xx, HTTP 5xx, unexpected errors)
- Dataclass models (OCRRegion, Detection, CaptionedRegion)
- Global singleton functions (get_florence_client, reset_florence_client)
"""

from __future__ import annotations

import base64
import io
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image

from backend.services.florence_client import (
    DEFAULT_FLORENCE_URL,
    FLORENCE_CONNECT_TIMEOUT,
    FLORENCE_HEALTH_TIMEOUT,
    FLORENCE_READ_TIMEOUT,
    BoundingBox,
    CaptionedRegion,
    Detection,
    FlorenceClient,
    FlorenceUnavailableError,
    GroundedPhrase,
    OCRRegion,
    get_florence_client,
    reset_florence_client,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
async def reset_global_client():
    """Reset global client before and after each test."""
    await reset_florence_client()
    yield
    await reset_florence_client()


@pytest.fixture
def mock_settings():
    """Create mock settings for FlorenceClient."""
    with patch("backend.services.florence_client.get_settings") as mock:
        mock.return_value.florence_url = "http://localhost:8092"
        mock.return_value.ai_connect_timeout = 10.0
        mock.return_value.ai_health_timeout = 5.0
        # Circuit breaker settings
        mock.return_value.florence_cb_failure_threshold = 5
        mock.return_value.florence_cb_recovery_timeout = 60.0
        mock.return_value.florence_cb_half_open_max_calls = 3
        yield mock


@pytest.fixture
def sample_image():
    """Create a sample PIL image for testing."""
    return Image.new("RGB", (224, 224), color=(128, 128, 128))


@pytest.fixture
def client(mock_settings):
    """Create a FlorenceClient with mocked HTTP clients for testing.

    The FlorenceClient uses persistent HTTP clients (NEM-1721), so we mock
    httpx.AsyncClient during construction to inject testable mock clients.
    """
    mock_http_client = AsyncMock()
    mock_http_client.aclose = AsyncMock()
    mock_health_client = AsyncMock()
    mock_health_client.aclose = AsyncMock()

    with (
        patch(
            "backend.services.florence_client.get_settings", return_value=mock_settings.return_value
        ),
        patch("httpx.AsyncClient", side_effect=[mock_http_client, mock_health_client]),
    ):
        client = FlorenceClient()

    return client


# =============================================================================
# Dataclass Tests
# =============================================================================


class TestOCRRegionDataclass:
    """Tests for OCRRegion dataclass."""

    def test_ocr_region_creation(self) -> None:
        """Test OCRRegion dataclass creation."""
        region = OCRRegion(text="Hello", bbox=[10, 10, 50, 10, 50, 30, 10, 30])
        assert region.text == "Hello"
        assert region.bbox == [10, 10, 50, 10, 50, 30, 10, 30]

    def test_ocr_region_empty_text(self) -> None:
        """Test OCRRegion with empty text."""
        region = OCRRegion(text="", bbox=[0, 0, 10, 10, 10, 20, 0, 20])
        assert region.text == ""
        assert len(region.bbox) == 8

    def test_ocr_region_empty_bbox(self) -> None:
        """Test OCRRegion with empty bbox."""
        region = OCRRegion(text="Some text", bbox=[])
        assert region.text == "Some text"
        assert region.bbox == []


class TestDetectionDataclass:
    """Tests for Detection dataclass."""

    def test_detection_with_all_fields(self) -> None:
        """Test Detection dataclass with all fields."""
        detection = Detection(label="person", bbox=[10, 20, 100, 200], score=0.95)
        assert detection.label == "person"
        assert detection.bbox == [10, 20, 100, 200]
        assert detection.score == 0.95

    def test_detection_default_score(self) -> None:
        """Test Detection dataclass with default score."""
        detection = Detection(label="car", bbox=[0, 0, 50, 50])
        assert detection.score == 1.0

    def test_detection_zero_score(self) -> None:
        """Test Detection with zero score."""
        detection = Detection(label="unknown", bbox=[0, 0, 1, 1], score=0.0)
        assert detection.score == 0.0

    def test_detection_empty_label(self) -> None:
        """Test Detection with empty label."""
        detection = Detection(label="", bbox=[10, 10, 20, 20])
        assert detection.label == ""


class TestCaptionedRegionDataclass:
    """Tests for CaptionedRegion dataclass."""

    def test_captioned_region_creation(self) -> None:
        """Test CaptionedRegion dataclass creation."""
        region = CaptionedRegion(caption="a person walking", bbox=[10, 20, 100, 200])
        assert region.caption == "a person walking"
        assert region.bbox == [10, 20, 100, 200]

    def test_captioned_region_empty_caption(self) -> None:
        """Test CaptionedRegion with empty caption."""
        region = CaptionedRegion(caption="", bbox=[0, 0, 50, 50])
        assert region.caption == ""

    def test_captioned_region_empty_bbox(self) -> None:
        """Test CaptionedRegion with empty bbox."""
        region = CaptionedRegion(caption="some caption", bbox=[])
        assert region.caption == "some caption"
        assert region.bbox == []


# =============================================================================
# FlorenceUnavailableError Tests
# =============================================================================


class TestFlorenceUnavailableError:
    """Tests for FlorenceUnavailableError exception."""

    def test_error_with_message_only(self) -> None:
        """Test error creation with message only."""
        error = FlorenceUnavailableError("Service unavailable")
        assert str(error) == "Service unavailable"
        assert error.original_error is None

    def test_error_with_original_error(self) -> None:
        """Test error creation with original error."""
        original = ValueError("Original error")
        error = FlorenceUnavailableError("Wrapped error", original_error=original)
        assert str(error) == "Wrapped error"
        assert error.original_error is original
        assert isinstance(error.original_error, ValueError)

    def test_error_is_exception(self) -> None:
        """Test FlorenceUnavailableError is an Exception."""
        error = FlorenceUnavailableError("test")
        assert isinstance(error, Exception)

    def test_error_with_httpx_error(self) -> None:
        """Test error with httpx exception as original."""
        original = httpx.ConnectError("Connection refused")
        error = FlorenceUnavailableError("Connection failed", original_error=original)
        assert error.original_error is original


# =============================================================================
# Constants Tests
# =============================================================================


class TestModuleConstants:
    """Tests for module-level constants."""

    def test_default_florence_url(self) -> None:
        """Test default Florence URL constant."""
        assert DEFAULT_FLORENCE_URL == "http://ai-florence:8092"

    def test_florence_connect_timeout(self) -> None:
        """Test Florence connect timeout constant."""
        assert FLORENCE_CONNECT_TIMEOUT == 10.0

    def test_florence_read_timeout(self) -> None:
        """Test Florence read timeout constant."""
        assert FLORENCE_READ_TIMEOUT == 30.0

    def test_florence_health_timeout(self) -> None:
        """Test Florence health timeout constant."""
        assert FLORENCE_HEALTH_TIMEOUT == 5.0


# =============================================================================
# FlorenceClient Initialization Tests
# =============================================================================


class TestFlorenceClientInit:
    """Tests for FlorenceClient initialization."""

    def test_init_with_default_url(self, mock_settings) -> None:
        """Test initialization with default URL from settings."""
        client = FlorenceClient()
        assert client._base_url == "http://localhost:8092"

    def test_init_with_custom_base_url(self, mock_settings) -> None:
        """Test initialization with custom base_url parameter."""
        client = FlorenceClient(base_url="http://custom-host:9000")
        assert client._base_url == "http://custom-host:9000"

    def test_init_strips_trailing_slash(self, mock_settings) -> None:
        """Test initialization strips trailing slash from base_url."""
        client = FlorenceClient(base_url="http://custom-host:9000/")
        assert client._base_url == "http://custom-host:9000"

    def test_init_with_multiple_trailing_slashes(self, mock_settings) -> None:
        """Test initialization strips multiple trailing slashes."""
        client = FlorenceClient(base_url="http://custom-host:9000///")
        # rstrip("/") removes all trailing slashes
        assert client._base_url == "http://custom-host:9000"

    def test_init_timeout_configuration(self, mock_settings) -> None:
        """Test initialization configures timeouts correctly."""
        client = FlorenceClient()
        assert client._timeout is not None
        assert client._health_timeout is not None

    def test_init_uses_settings_florence_url(self) -> None:
        """Test initialization uses florence_url from settings."""
        with patch("backend.services.florence_client.get_settings") as mock:
            # Create a mock with florence_url configured
            settings_obj = MagicMock()
            settings_obj.florence_url = "http://custom-florence:9999"
            settings_obj.ai_connect_timeout = 10.0
            settings_obj.ai_health_timeout = 5.0
            mock.return_value = settings_obj

            client = FlorenceClient()
            assert client._base_url == "http://custom-florence:9999"


# =============================================================================
# FlorenceClient._encode_image_to_base64 Tests
# =============================================================================


class TestEncodeImageToBase64:
    """Tests for _encode_image_to_base64 private method."""

    def test_encode_rgb_image(self, mock_settings, sample_image) -> None:
        """Test encoding RGB image to base64."""
        client = FlorenceClient()
        result = client._encode_image_to_base64(sample_image)

        # Verify it's valid base64
        decoded = base64.b64decode(result)
        assert len(decoded) > 0

        # Verify it can be read back as an image
        buffer = io.BytesIO(decoded)
        loaded_image = Image.open(buffer)
        assert loaded_image.size == (224, 224)

    def test_encode_rgba_image(self, mock_settings) -> None:
        """Test encoding RGBA image to base64."""
        client = FlorenceClient()
        image = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        result = client._encode_image_to_base64(image)

        decoded = base64.b64decode(result)
        buffer = io.BytesIO(decoded)
        loaded_image = Image.open(buffer)
        assert loaded_image.size == (100, 100)

    def test_encode_grayscale_image(self, mock_settings) -> None:
        """Test encoding grayscale image to base64."""
        client = FlorenceClient()
        image = Image.new("L", (50, 50), color=128)
        result = client._encode_image_to_base64(image)

        decoded = base64.b64decode(result)
        assert len(decoded) > 0


# =============================================================================
# FlorenceClient.check_health Tests
# =============================================================================


class TestCheckHealth:
    """Tests for FlorenceClient.check_health() method."""

    @pytest.mark.asyncio
    async def test_check_health_success(self, client) -> None:
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        client._health_http_client.get = AsyncMock(return_value=mock_response)

        result = await client.check_health()

        assert result is True
        # NEM-3147: Health check now includes W3C Trace Context headers
        client._health_http_client.get.assert_called_once()
        call_args = client._health_http_client.get.call_args
        assert call_args[0][0] == "http://localhost:8092/health"
        assert "headers" in call_args[1]

    @pytest.mark.asyncio
    async def test_check_health_connection_error(self, client) -> None:
        """Test health check with connection error returns False."""
        client._health_http_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        result = await client.check_health()
        assert result is False

    @pytest.mark.asyncio
    async def test_check_health_timeout(self, client) -> None:
        """Test health check with timeout returns False."""
        client._health_http_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        result = await client.check_health()
        assert result is False

    @pytest.mark.asyncio
    async def test_check_health_http_status_error(self, client) -> None:
        """Test health check with HTTP status error returns False."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Service unavailable",
            request=MagicMock(),
            response=mock_response,
        )
        client._health_http_client.get = AsyncMock(return_value=mock_response)

        result = await client.check_health()
        assert result is False

    @pytest.mark.asyncio
    async def test_check_health_unexpected_error(self, client) -> None:
        """Test health check with unexpected error returns False."""
        client._health_http_client.get = AsyncMock(side_effect=RuntimeError("Unexpected error"))

        result = await client.check_health()
        assert result is False


# =============================================================================
# FlorenceClient.extract Tests
# =============================================================================


class TestExtract:
    """Tests for FlorenceClient.extract() method."""

    @pytest.mark.asyncio
    async def test_extract_success(self, client, sample_image) -> None:
        """Test successful extraction."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": "A gray square image",
            "inference_time_ms": 50.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.extract(sample_image, "<CAPTION>")

        assert result == "A gray square image"
        client._http_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_with_vqa_prompt(self, client, sample_image) -> None:
        """Test extraction with VQA prompt."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": "The image is gray",
            "inference_time_ms": 60.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.extract(sample_image, "<VQA>What color is this?")

        assert result == "The image is gray"

    @pytest.mark.asyncio
    async def test_extract_connection_error(self, client, sample_image) -> None:
        """Test extract with connection error raises FlorenceUnavailableError."""
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with pytest.raises(FlorenceUnavailableError, match="Failed to connect"):
            await client.extract(sample_image, "<CAPTION>")

    @pytest.mark.asyncio
    async def test_extract_timeout(self, client, sample_image) -> None:
        """Test extract with timeout raises FlorenceUnavailableError."""
        client._http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Read timeout"))

        with pytest.raises(FlorenceUnavailableError, match="timed out"):
            await client.extract(sample_image, "<CAPTION>")

    @pytest.mark.asyncio
    async def test_extract_server_error_5xx(self, client, sample_image) -> None:
        """Test extract with HTTP 5xx error raises FlorenceUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(FlorenceUnavailableError, match="server error"):
            await client.extract(sample_image, "<CAPTION>")

    @pytest.mark.asyncio
    async def test_extract_server_error_502(self, client, sample_image) -> None:
        """Test extract with HTTP 502 error raises FlorenceUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Gateway",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(FlorenceUnavailableError, match="server error"):
            await client.extract(sample_image, "<CAPTION>")

    @pytest.mark.asyncio
    async def test_extract_server_error_503(self, client, sample_image) -> None:
        """Test extract with HTTP 503 error raises FlorenceUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Service Unavailable",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(FlorenceUnavailableError, match="server error"):
            await client.extract(sample_image, "<CAPTION>")

    @pytest.mark.asyncio
    async def test_extract_client_error_4xx(self, client, sample_image) -> None:
        """Test extract with HTTP 4xx error returns empty string."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.extract(sample_image, "<CAPTION>")
        assert result == ""

    @pytest.mark.asyncio
    async def test_extract_client_error_404(self, client, sample_image) -> None:
        """Test extract with HTTP 404 error returns empty string."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.extract(sample_image, "<CAPTION>")
        assert result == ""

    @pytest.mark.asyncio
    async def test_extract_client_error_422(self, client, sample_image) -> None:
        """Test extract with HTTP 422 error returns empty string."""
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unprocessable Entity",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.extract(sample_image, "<CAPTION>")
        assert result == ""

    @pytest.mark.asyncio
    async def test_extract_malformed_response_missing_result(
        self, mock_settings, sample_image
    ) -> None:
        """Test extract with malformed response (missing \'result\' key) returns empty string."""
        client = FlorenceClient()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"inference_time_ms": 50.0}
        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.extract(sample_image, "<CAPTION>")
        assert result == ""

    @pytest.mark.asyncio
    async def test_extract_unexpected_error(self, client, sample_image) -> None:
        """Test extract with unexpected error raises FlorenceUnavailableError."""
        client._http_client.post = AsyncMock(side_effect=RuntimeError("Unexpected error"))

        with pytest.raises(FlorenceUnavailableError, match="Unexpected error"):
            await client.extract(sample_image, "<CAPTION>")


# =============================================================================
# FlorenceClient.ocr Tests
# =============================================================================


class TestOCR:
    """Tests for FlorenceClient.ocr() method."""

    @pytest.mark.asyncio
    async def test_ocr_success(self, client, sample_image) -> None:
        """Test successful OCR text extraction."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "text": "Hello World",
            "inference_time_ms": 50.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        text = await client.ocr(sample_image)

        assert text == "Hello World"

    @pytest.mark.asyncio
    async def test_ocr_connection_error(self, client, sample_image) -> None:
        """Test OCR with connection error raises FlorenceUnavailableError."""
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with pytest.raises(FlorenceUnavailableError, match="Failed to connect"):
            await client.ocr(sample_image)

    @pytest.mark.asyncio
    async def test_ocr_timeout(self, client, sample_image) -> None:
        """Test OCR with timeout raises FlorenceUnavailableError."""
        client._http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with pytest.raises(FlorenceUnavailableError, match="timed out"):
            await client.ocr(sample_image)

    @pytest.mark.asyncio
    async def test_ocr_server_error_5xx(self, client, sample_image) -> None:
        """Test OCR with HTTP 5xx error raises FlorenceUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(FlorenceUnavailableError, match="server error"):
            await client.ocr(sample_image)

    @pytest.mark.asyncio
    async def test_ocr_client_error_4xx(self, client, sample_image) -> None:
        """Test OCR with HTTP 4xx error returns empty string."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.ocr(sample_image)
        assert result == ""

    @pytest.mark.asyncio
    async def test_ocr_malformed_response(self, client, sample_image) -> None:
        """Test OCR with malformed response returns empty string."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"inference_time_ms": 50.0}
        client._http_client.post = AsyncMock(return_value=mock_response)

        text = await client.ocr(sample_image)
        assert text == ""

    @pytest.mark.asyncio
    async def test_ocr_unexpected_error(self, client, sample_image) -> None:
        """Test OCR with unexpected error raises FlorenceUnavailableError."""
        client._http_client.post = AsyncMock(side_effect=RuntimeError("Unexpected"))

        with pytest.raises(FlorenceUnavailableError, match="Unexpected error"):
            await client.ocr(sample_image)


# =============================================================================
# FlorenceClient.ocr_with_regions Tests
# =============================================================================


class TestOCRWithRegions:
    """Tests for FlorenceClient.ocr_with_regions() method."""

    @pytest.mark.asyncio
    async def test_ocr_with_regions_success(self, client, sample_image) -> None:
        """Test successful OCR with regions extraction."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "regions": [
                {"text": "Hello", "bbox": [10, 10, 50, 10, 50, 30, 10, 30]},
                {"text": "World", "bbox": [60, 10, 100, 10, 100, 30, 60, 30]},
            ],
            "inference_time_ms": 60.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        regions = await client.ocr_with_regions(sample_image)

        assert len(regions) == 2
        assert isinstance(regions[0], OCRRegion)
        assert regions[0].text == "Hello"
        assert regions[1].text == "World"

    @pytest.mark.asyncio
    async def test_ocr_with_regions_empty_result(self, client, sample_image) -> None:
        """Test OCR with regions when no text found."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "regions": [],
            "inference_time_ms": 40.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        regions = await client.ocr_with_regions(sample_image)
        assert regions == []

    @pytest.mark.asyncio
    async def test_ocr_with_regions_connection_error(self, client, sample_image) -> None:
        """Test OCR with regions connection error raises FlorenceUnavailableError."""
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with pytest.raises(FlorenceUnavailableError, match="Failed to connect"):
            await client.ocr_with_regions(sample_image)

    @pytest.mark.asyncio
    async def test_ocr_with_regions_timeout(self, client, sample_image) -> None:
        """Test OCR with regions timeout raises FlorenceUnavailableError."""
        client._http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with pytest.raises(FlorenceUnavailableError, match="timed out"):
            await client.ocr_with_regions(sample_image)

    @pytest.mark.asyncio
    async def test_ocr_with_regions_server_error_5xx(self, client, sample_image) -> None:
        """Test OCR with regions HTTP 5xx error raises FlorenceUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Service Unavailable",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(FlorenceUnavailableError, match="server error"):
            await client.ocr_with_regions(sample_image)

    @pytest.mark.asyncio
    async def test_ocr_with_regions_client_error_4xx(self, client, sample_image) -> None:
        """Test OCR with regions HTTP 4xx error returns empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        regions = await client.ocr_with_regions(sample_image)
        assert regions == []

    @pytest.mark.asyncio
    async def test_ocr_with_regions_malformed_response(self, client, sample_image) -> None:
        """Test OCR with regions malformed response returns empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"inference_time_ms": 60.0}
        client._http_client.post = AsyncMock(return_value=mock_response)

        regions = await client.ocr_with_regions(sample_image)
        assert regions == []

    @pytest.mark.asyncio
    async def test_ocr_with_regions_handles_missing_fields_in_region(
        self, client, sample_image
    ) -> None:
        """Test OCR with regions handles regions with missing fields."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "regions": [
                {},  # Missing both text and bbox
                {"text": "Hello"},  # Missing bbox
                {"bbox": [0, 0, 10, 10]},  # Missing text
            ],
            "inference_time_ms": 50.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        regions = await client.ocr_with_regions(sample_image)
        assert len(regions) == 3
        assert regions[0].text == ""
        assert regions[0].bbox == []
        assert regions[1].text == "Hello"
        assert regions[1].bbox == []
        assert regions[2].text == ""
        assert regions[2].bbox == [0, 0, 10, 10]

    @pytest.mark.asyncio
    async def test_ocr_with_regions_unexpected_error(self, client, sample_image) -> None:
        """Test OCR with regions unexpected error raises FlorenceUnavailableError."""
        client._http_client.post = AsyncMock(side_effect=RuntimeError("Unexpected"))

        with pytest.raises(FlorenceUnavailableError, match="Unexpected error"):
            await client.ocr_with_regions(sample_image)


# =============================================================================
# FlorenceClient.detect Tests
# =============================================================================


class TestDetect:
    """Tests for FlorenceClient.detect() method."""

    @pytest.mark.asyncio
    async def test_detect_success(self, client, sample_image) -> None:
        """Test successful object detection."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "detections": [
                {"label": "person", "bbox": [10, 20, 100, 200], "score": 0.95},
                {"label": "car", "bbox": [150, 50, 300, 180], "score": 0.87},
            ],
            "inference_time_ms": 45.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        detections = await client.detect(sample_image)

        assert len(detections) == 2
        assert isinstance(detections[0], Detection)
        assert detections[0].label == "person"
        assert detections[0].score == 0.95
        assert detections[1].label == "car"

    @pytest.mark.asyncio
    async def test_detect_empty_result(self, client, sample_image) -> None:
        """Test detection with no objects found."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "detections": [],
            "inference_time_ms": 30.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        detections = await client.detect(sample_image)
        assert detections == []

    @pytest.mark.asyncio
    async def test_detect_connection_error(self, client, sample_image) -> None:
        """Test detect with connection error raises FlorenceUnavailableError."""
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with pytest.raises(FlorenceUnavailableError, match="Failed to connect"):
            await client.detect(sample_image)

    @pytest.mark.asyncio
    async def test_detect_timeout(self, client, sample_image) -> None:
        """Test detect with timeout raises FlorenceUnavailableError."""
        client._http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with pytest.raises(FlorenceUnavailableError, match="timed out"):
            await client.detect(sample_image)

    @pytest.mark.asyncio
    async def test_detect_server_error_5xx(self, client, sample_image) -> None:
        """Test detect with HTTP 5xx error raises FlorenceUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(FlorenceUnavailableError, match="server error"):
            await client.detect(sample_image)

    @pytest.mark.asyncio
    async def test_detect_client_error_4xx(self, client, sample_image) -> None:
        """Test detect with HTTP 4xx error returns empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        detections = await client.detect(sample_image)
        assert detections == []

    @pytest.mark.asyncio
    async def test_detect_malformed_response(self, client, sample_image) -> None:
        """Test detect with malformed response returns empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"inference_time_ms": 45.0}
        client._http_client.post = AsyncMock(return_value=mock_response)

        detections = await client.detect(sample_image)
        assert detections == []

    @pytest.mark.asyncio
    async def test_detect_handles_missing_fields_in_detection(self, client, sample_image) -> None:
        """Test detect handles detections with missing fields."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "detections": [
                {},  # Missing all fields
                {"label": "person"},  # Missing bbox and score
                {"bbox": [0, 0, 10, 10]},  # Missing label and score
            ],
            "inference_time_ms": 50.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        detections = await client.detect(sample_image)
        assert len(detections) == 3
        assert detections[0].label == ""
        assert detections[0].bbox == []
        assert detections[0].score == 1.0
        assert detections[1].label == "person"
        assert detections[1].bbox == []
        assert detections[2].label == ""
        assert detections[2].bbox == [0, 0, 10, 10]

    @pytest.mark.asyncio
    async def test_detect_unexpected_error(self, client, sample_image) -> None:
        """Test detect with unexpected error raises FlorenceUnavailableError."""
        client._http_client.post = AsyncMock(side_effect=RuntimeError("Unexpected"))

        with pytest.raises(FlorenceUnavailableError, match="Unexpected error"):
            await client.detect(sample_image)


# =============================================================================
# FlorenceClient.dense_caption Tests
# =============================================================================


class TestDenseCaption:
    """Tests for FlorenceClient.dense_caption() method."""

    @pytest.mark.asyncio
    async def test_dense_caption_success(self, client, sample_image) -> None:
        """Test successful dense captioning."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "regions": [
                {"caption": "a person walking", "bbox": [10, 20, 100, 200]},
                {"caption": "a red car parked", "bbox": [150, 50, 300, 180]},
            ],
            "inference_time_ms": 80.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        regions = await client.dense_caption(sample_image)

        assert len(regions) == 2
        assert isinstance(regions[0], CaptionedRegion)
        assert regions[0].caption == "a person walking"
        assert regions[1].caption == "a red car parked"

    @pytest.mark.asyncio
    async def test_dense_caption_empty_result(self, client, sample_image) -> None:
        """Test dense caption with no regions found."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "regions": [],
            "inference_time_ms": 50.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        regions = await client.dense_caption(sample_image)
        assert regions == []

    @pytest.mark.asyncio
    async def test_dense_caption_connection_error(self, client, sample_image) -> None:
        """Test dense_caption with connection error raises FlorenceUnavailableError."""
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with pytest.raises(FlorenceUnavailableError, match="Failed to connect"):
            await client.dense_caption(sample_image)

    @pytest.mark.asyncio
    async def test_dense_caption_timeout(self, client, sample_image) -> None:
        """Test dense_caption with timeout raises FlorenceUnavailableError."""
        client._http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with pytest.raises(FlorenceUnavailableError, match="timed out"):
            await client.dense_caption(sample_image)

    @pytest.mark.asyncio
    async def test_dense_caption_server_error_5xx(self, client, sample_image) -> None:
        """Test dense_caption with HTTP 5xx error raises FlorenceUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Gateway",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(FlorenceUnavailableError, match="server error"):
            await client.dense_caption(sample_image)

    @pytest.mark.asyncio
    async def test_dense_caption_client_error_4xx(self, client, sample_image) -> None:
        """Test dense_caption with HTTP 4xx error returns empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unprocessable Entity",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        regions = await client.dense_caption(sample_image)
        assert regions == []

    @pytest.mark.asyncio
    async def test_dense_caption_malformed_response(self, client, sample_image) -> None:
        """Test dense_caption with malformed response returns empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"inference_time_ms": 80.0}
        client._http_client.post = AsyncMock(return_value=mock_response)

        regions = await client.dense_caption(sample_image)
        assert regions == []

    @pytest.mark.asyncio
    async def test_dense_caption_handles_missing_fields_in_region(
        self, client, sample_image
    ) -> None:
        """Test dense_caption handles regions with missing fields."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "regions": [
                {},  # Missing both caption and bbox
                {"caption": "test caption"},  # Missing bbox
                {"bbox": [0, 0, 10, 10]},  # Missing caption
            ],
            "inference_time_ms": 60.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        regions = await client.dense_caption(sample_image)
        assert len(regions) == 3
        assert regions[0].caption == ""
        assert regions[0].bbox == []
        assert regions[1].caption == "test caption"
        assert regions[1].bbox == []
        assert regions[2].caption == ""
        assert regions[2].bbox == [0, 0, 10, 10]

    @pytest.mark.asyncio
    async def test_dense_caption_unexpected_error(self, client, sample_image) -> None:
        """Test dense_caption with unexpected error raises FlorenceUnavailableError."""
        client._http_client.post = AsyncMock(side_effect=RuntimeError("Unexpected"))

        with pytest.raises(FlorenceUnavailableError, match="Unexpected error"):
            await client.dense_caption(sample_image)


# =============================================================================
# Global Singleton Tests
# =============================================================================


class TestGlobalClientFunctions:
    """Tests for global client singleton functions."""

    def test_get_florence_client_singleton(self, mock_settings) -> None:
        """Test get_florence_client returns singleton instance."""
        client1 = get_florence_client()
        client2 = get_florence_client()

        assert client1 is client2

    @pytest.mark.asyncio
    async def test_reset_florence_client(self, mock_settings) -> None:
        """Test reset_florence_client clears the singleton."""
        client1 = get_florence_client()
        await reset_florence_client()
        client2 = get_florence_client()

        assert client1 is not client2

    @pytest.mark.asyncio
    async def test_get_florence_client_creates_new_after_reset(self, mock_settings) -> None:
        """Test get_florence_client creates new instance after reset."""
        client1 = get_florence_client()
        await reset_florence_client()
        client2 = get_florence_client()
        client3 = get_florence_client()

        assert client1 is not client2
        assert client2 is client3

    @pytest.mark.asyncio
    async def test_reset_florence_client_multiple_times(self, mock_settings) -> None:
        """Test reset_florence_client can be called multiple times safely."""
        await reset_florence_client()
        await reset_florence_client()
        await reset_florence_client()

        # Should not raise any errors
        client = get_florence_client()
        assert client is not None


# =============================================================================
# Metrics Recording Tests
# =============================================================================


class TestMetricsRecording:
    """Tests for metrics recording during client operations."""

    @pytest.mark.asyncio
    async def test_extract_records_ai_duration(self, client, sample_image) -> None:
        """Test extract method records AI request duration."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "test"}
        client._http_client.post = AsyncMock(return_value=mock_response)

        with patch("backend.services.florence_client.observe_ai_request_duration") as mock_observe:
            await client.extract(sample_image, "<CAPTION>")
            mock_observe.assert_called_once()
            args = mock_observe.call_args[0]
            assert args[0] == "florence"
            assert isinstance(args[1], float)

    @pytest.mark.asyncio
    async def test_ocr_records_ai_duration(self, client, sample_image) -> None:
        """Test ocr method records AI request duration."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": "test"}
        client._http_client.post = AsyncMock(return_value=mock_response)

        with patch("backend.services.florence_client.observe_ai_request_duration") as mock_observe:
            await client.ocr(sample_image)
            mock_observe.assert_called_once()
            args = mock_observe.call_args[0]
            assert args[0] == "florence_ocr"

    @pytest.mark.asyncio
    async def test_detect_records_ai_duration(self, client, sample_image) -> None:
        """Test detect method records AI request duration."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"detections": []}
        client._http_client.post = AsyncMock(return_value=mock_response)

        with patch("backend.services.florence_client.observe_ai_request_duration") as mock_observe:
            await client.detect(sample_image)
            mock_observe.assert_called_once()
            args = mock_observe.call_args[0]
            assert args[0] == "florence_detect"

    @pytest.mark.asyncio
    async def test_connection_error_records_pipeline_error(self, client, sample_image) -> None:
        """Test connection error records pipeline error metric."""
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with patch("backend.services.florence_client.record_pipeline_error") as mock_record:
            with pytest.raises(FlorenceUnavailableError):
                await client.extract(sample_image, "<CAPTION>")
            mock_record.assert_called_once_with("florence_connection_error")

    @pytest.mark.asyncio
    async def test_timeout_records_pipeline_error(self, client, sample_image) -> None:
        """Test timeout records pipeline error metric."""
        client._http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with patch("backend.services.florence_client.record_pipeline_error") as mock_record:
            with pytest.raises(FlorenceUnavailableError):
                await client.extract(sample_image, "<CAPTION>")
            mock_record.assert_called_once_with("florence_timeout")

    @pytest.mark.asyncio
    async def test_server_error_records_pipeline_error(self, client, sample_image) -> None:
        """Test server error records pipeline error metric."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        with patch("backend.services.florence_client.record_pipeline_error") as mock_record:
            with pytest.raises(FlorenceUnavailableError):
                await client.extract(sample_image, "<CAPTION>")
            mock_record.assert_called_once_with("florence_server_error")

    @pytest.mark.asyncio
    async def test_client_error_records_pipeline_error(self, client, sample_image) -> None:
        """Test client error records pipeline error metric."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        with patch("backend.services.florence_client.record_pipeline_error") as mock_record:
            await client.extract(sample_image, "<CAPTION>")
            mock_record.assert_called_once_with("florence_client_error")

    @pytest.mark.asyncio
    async def test_malformed_response_records_pipeline_error(self, client, sample_image) -> None:
        """Test malformed response records pipeline error metric."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # Missing 'result' key
        client._http_client.post = AsyncMock(return_value=mock_response)

        with patch("backend.services.florence_client.record_pipeline_error") as mock_record:
            await client.extract(sample_image, "<CAPTION>")
            mock_record.assert_called_once_with("florence_malformed_response")


# =============================================================================
# HTTP Request Verification Tests
# =============================================================================


class TestHTTPRequestVerification:
    """Tests to verify HTTP request details."""

    @pytest.mark.asyncio
    async def test_extract_sends_correct_payload(self, client, sample_image) -> None:
        """Test extract sends correct payload to service."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "test"}
        client._http_client.post = AsyncMock(return_value=mock_response)

        await client.extract(sample_image, "<DETAILED_CAPTION>")

        client._http_client.post.assert_called_once()
        call_args = client._http_client.post.call_args
        assert call_args[0][0] == "http://localhost:8092/extract"
        payload = call_args[1]["json"]
        assert "image" in payload
        assert "prompt" in payload
        assert payload["prompt"] == "<DETAILED_CAPTION>"

    @pytest.mark.asyncio
    async def test_ocr_sends_correct_endpoint(self, client, sample_image) -> None:
        """Test ocr sends request to correct endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": "test"}
        client._http_client.post = AsyncMock(return_value=mock_response)

        await client.ocr(sample_image)

        call_args = client._http_client.post.call_args
        assert call_args[0][0] == "http://localhost:8092/ocr"

    @pytest.mark.asyncio
    async def test_detect_sends_correct_endpoint(self, client, sample_image) -> None:
        """Test detect sends request to correct endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"detections": []}
        client._http_client.post = AsyncMock(return_value=mock_response)

        await client.detect(sample_image)

        call_args = client._http_client.post.call_args
        assert call_args[0][0] == "http://localhost:8092/detect"

    @pytest.mark.asyncio
    async def test_dense_caption_sends_correct_endpoint(self, client, sample_image) -> None:
        """Test dense_caption sends request to correct endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"regions": []}
        client._http_client.post = AsyncMock(return_value=mock_response)

        await client.dense_caption(sample_image)

        call_args = client._http_client.post.call_args
        assert call_args[0][0] == "http://localhost:8092/dense-caption"

    @pytest.mark.asyncio
    async def test_ocr_with_regions_sends_correct_endpoint(self, client, sample_image) -> None:
        """Test ocr_with_regions sends request to correct endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"regions": []}
        client._http_client.post = AsyncMock(return_value=mock_response)

        await client.ocr_with_regions(sample_image)

        call_args = client._http_client.post.call_args
        assert call_args[0][0] == "http://localhost:8092/ocr-with-regions"

    @pytest.mark.asyncio
    async def test_check_health_sends_correct_endpoint(self, client) -> None:
        """Test check_health sends request to correct endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        client._health_http_client.get = AsyncMock(return_value=mock_response)

        await client.check_health()

        # NEM-3147: Health check now includes W3C Trace Context headers
        client._health_http_client.get.assert_called_once()
        call_args = client._health_http_client.get.call_args
        assert call_args[0][0] == "http://localhost:8092/health"
        assert "headers" in call_args[1]


# =============================================================================
# Circuit Breaker Integration Tests
# =============================================================================


class TestCircuitBreakerIntegration:
    """Tests for circuit breaker integration in FlorenceClient."""

    @pytest.mark.asyncio
    async def test_client_initializes_circuit_breaker(self, client) -> None:
        """Test that client initializes a circuit breaker."""
        # mock_settings.return_value.florence_cb_failure_threshold  # Not needed with fixture = 5
        # mock_settings.return_value.florence_cb_recovery_timeout  # Not needed with fixture = 60
        # mock_settings.return_value.florence_cb_half_open_max_calls  # Not needed with fixture = 3

        client = FlorenceClient()

        assert hasattr(client, "_circuit_breaker")
        assert client._circuit_breaker is not None

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self, client, sample_image) -> None:
        """Test that circuit breaker opens after reaching failure threshold."""
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        # Trigger failures up to threshold (fixture default is 5)
        for _ in range(5):
            with pytest.raises(FlorenceUnavailableError):
                await client.extract(sample_image, "<CAPTION>")

        # Circuit should be open now - next request should fail immediately
        from backend.core.circuit_breaker import CircuitState

        assert client._circuit_breaker.get_state() == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_rejects_when_open(self, client, sample_image) -> None:
        """Test that requests are rejected when circuit is open."""
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        # Trigger failures to open circuit (fixture default is 5)
        for _ in range(5):
            with pytest.raises(FlorenceUnavailableError):
                await client.extract(sample_image, "<CAPTION>")

        # Reset the mock to not raise - but circuit should block
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "test"}
        client._http_client.post.side_effect = None
        client._http_client.post.return_value = mock_response

        # Request should be rejected due to open circuit
        with pytest.raises(FlorenceUnavailableError, match=r"[Cc]ircuit"):
            await client.extract(sample_image, "<CAPTION>")

    @pytest.mark.asyncio
    async def test_circuit_breaker_records_success(self, client, sample_image) -> None:
        """Test that successful requests record success with circuit breaker."""
        # mock_settings.return_value.florence_cb_failure_threshold  # Not needed with fixture = 5
        # mock_settings.return_value.florence_cb_recovery_timeout  # Not needed with fixture = 60
        # mock_settings.return_value.florence_cb_half_open_max_calls  # Not needed with fixture = 3

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "test"}
        client._http_client.post = AsyncMock(return_value=mock_response)

        # Record some failures first
        client._http_client.post.side_effect = httpx.ConnectError("Connection refused")
        with pytest.raises(FlorenceUnavailableError):
            await client.extract(sample_image, "<CAPTION>")

        # Circuit should still be closed (only 1 failure)
        from backend.core.circuit_breaker import CircuitState

        assert client._circuit_breaker.get_state() == CircuitState.CLOSED
        assert client._circuit_breaker._failure_count == 1

        # Now succeed - failure count should reset
        client._http_client.post.side_effect = None
        client._http_client.post.return_value = mock_response
        await client.extract(sample_image, "<CAPTION>")

        assert client._circuit_breaker._failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_applies_to_all_methods(self, client, sample_image) -> None:
        """Test that circuit breaker applies to all Florence client methods."""
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        # Open circuit via extract - need 5 failures (fixture default)
        for _ in range(5):
            with pytest.raises(FlorenceUnavailableError):
                await client.extract(sample_image, "<CAPTION>")

        # All other methods should also be blocked
        with pytest.raises(FlorenceUnavailableError, match=r"[Cc]ircuit"):
            await client.ocr(sample_image)

        with pytest.raises(FlorenceUnavailableError, match=r"[Cc]ircuit"):
            await client.detect(sample_image)

        with pytest.raises(FlorenceUnavailableError, match=r"[Cc]ircuit"):
            await client.dense_caption(sample_image)

        with pytest.raises(FlorenceUnavailableError, match=r"[Cc]ircuit"):
            await client.ocr_with_regions(sample_image)

    @pytest.mark.asyncio
    async def test_circuit_breaker_health_check_reflects_state(self, client) -> None:
        """Test that health check reflects circuit breaker state."""
        # mock_settings.return_value.florence_cb_failure_threshold  # Not needed with fixture = 2
        # mock_settings.return_value.florence_cb_recovery_timeout  # Not needed with fixture = 60
        # mock_settings.return_value.florence_cb_half_open_max_calls  # Not needed with fixture = 2

        client = FlorenceClient()

        # Manually open circuit for testing
        client._circuit_breaker._state = client._circuit_breaker._state.__class__.OPEN

        # Health check should return False when circuit is open
        # (or at least consider circuit state in the result)
        result = await client.check_health()
        assert result is False

    @pytest.mark.asyncio
    async def test_get_circuit_breaker_state(self, client) -> None:
        """Test that circuit breaker state can be accessed."""
        # mock_settings.return_value.florence_cb_failure_threshold  # Not needed with fixture = 5
        # mock_settings.return_value.florence_cb_recovery_timeout  # Not needed with fixture = 60
        # mock_settings.return_value.florence_cb_half_open_max_calls  # Not needed with fixture = 3

        client = FlorenceClient()

        from backend.core.circuit_breaker import CircuitState

        # Should start closed
        assert client.get_circuit_breaker_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_uses_config_settings(self, client) -> None:
        """Test that circuit breaker uses configuration settings from fixture."""
        # Fixture provides: failure_threshold=5, recovery_timeout=60.0, half_open_max_calls=3
        assert client._circuit_breaker._failure_threshold == 5
        assert client._circuit_breaker._recovery_timeout == 60.0
        assert client._circuit_breaker._half_open_max_calls == 3


# =============================================================================
# BoundingBox and GroundedPhrase Dataclass Tests (NEM-3911)
# =============================================================================


class TestBoundingBoxDataclass:
    """Tests for BoundingBox dataclass (NEM-3911)."""

    def test_bounding_box_creation(self) -> None:
        """Test BoundingBox dataclass creation."""

        bbox = BoundingBox(x1=10, y1=20, x2=100, y2=200)
        assert bbox.x1 == 10
        assert bbox.y1 == 20
        assert bbox.x2 == 100
        assert bbox.y2 == 200

    def test_bounding_box_as_list(self) -> None:
        """Test BoundingBox.as_list() method."""

        bbox = BoundingBox(x1=10, y1=20, x2=100, y2=200)
        assert bbox.as_list() == [10, 20, 100, 200]

    def test_bounding_box_as_dict(self) -> None:
        """Test BoundingBox.as_dict() method."""

        bbox = BoundingBox(x1=10, y1=20, x2=100, y2=200)
        assert bbox.as_dict() == {"x1": 10, "y1": 20, "x2": 100, "y2": 200}

    def test_bounding_box_from_list(self) -> None:
        """Test BoundingBox.from_list() classmethod."""

        bbox = BoundingBox.from_list([10, 20, 100, 200])
        assert bbox.x1 == 10
        assert bbox.y1 == 20
        assert bbox.x2 == 100
        assert bbox.y2 == 200


class TestGroundedPhraseDataclass:
    """Tests for GroundedPhrase dataclass (NEM-3911)."""

    def test_grounded_phrase_creation(self) -> None:
        """Test GroundedPhrase dataclass creation."""

        grounded = GroundedPhrase(
            phrase="person",
            bboxes=[[10, 20, 100, 200], [150, 50, 250, 180]],
            confidence_scores=[0.95, 0.87],
        )
        assert grounded.phrase == "person"
        assert len(grounded.bboxes) == 2
        assert len(grounded.confidence_scores) == 2

    def test_grounded_phrase_empty_bboxes(self) -> None:
        """Test GroundedPhrase with no matches."""

        grounded = GroundedPhrase(phrase="elephant", bboxes=[], confidence_scores=[])
        assert grounded.phrase == "elephant"
        assert grounded.bboxes == []


# =============================================================================
# FlorenceClient.describe_regions Tests (NEM-3911)
# =============================================================================


class TestDescribeRegions:
    """Tests for FlorenceClient.describe_regions() method (NEM-3911)."""

    @pytest.mark.asyncio
    async def test_describe_regions_success(self, client, sample_image) -> None:
        """Test successful region description."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "descriptions": [
                {"caption": "a person in blue jacket", "bbox": [10, 20, 100, 200]},
                {"caption": "a brown package on ground", "bbox": [150, 300, 250, 400]},
            ],
            "inference_time_ms": 180.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        regions = [
            BoundingBox(x1=10, y1=20, x2=100, y2=200),
            BoundingBox(x1=150, y1=300, x2=250, y2=400),
        ]
        descriptions = await client.describe_regions(sample_image, regions)

        assert len(descriptions) == 2
        assert isinstance(descriptions[0], CaptionedRegion)
        assert descriptions[0].caption == "a person in blue jacket"
        assert descriptions[1].caption == "a brown package on ground"

    @pytest.mark.asyncio
    async def test_describe_regions_single_region(self, client, sample_image) -> None:
        """Test describing a single region."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "descriptions": [
                {"caption": "a delivery driver", "bbox": [50, 100, 200, 400]},
            ],
            "inference_time_ms": 120.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        regions = [BoundingBox(x1=50, y1=100, x2=200, y2=400)]
        descriptions = await client.describe_regions(sample_image, regions)

        assert len(descriptions) == 1
        assert descriptions[0].caption == "a delivery driver"

    @pytest.mark.asyncio
    async def test_describe_regions_connection_error(self, client, sample_image) -> None:
        """Test describe_regions with connection error raises FlorenceUnavailableError."""

        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        regions = [BoundingBox(x1=0, y1=0, x2=100, y2=100)]
        with pytest.raises(FlorenceUnavailableError, match="Failed to connect"):
            await client.describe_regions(sample_image, regions)

    @pytest.mark.asyncio
    async def test_describe_regions_timeout(self, client, sample_image) -> None:
        """Test describe_regions with timeout raises FlorenceUnavailableError."""

        client._http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        regions = [BoundingBox(x1=0, y1=0, x2=100, y2=100)]
        with pytest.raises(FlorenceUnavailableError, match="timed out"):
            await client.describe_regions(sample_image, regions)

    @pytest.mark.asyncio
    async def test_describe_regions_server_error_5xx(self, client, sample_image) -> None:
        """Test describe_regions with HTTP 5xx error raises FlorenceUnavailableError."""

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        regions = [BoundingBox(x1=0, y1=0, x2=100, y2=100)]
        with pytest.raises(FlorenceUnavailableError, match="server error"):
            await client.describe_regions(sample_image, regions)

    @pytest.mark.asyncio
    async def test_describe_regions_client_error_4xx(self, client, sample_image) -> None:
        """Test describe_regions with HTTP 4xx error returns empty list."""

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        regions = [BoundingBox(x1=0, y1=0, x2=100, y2=100)]
        descriptions = await client.describe_regions(sample_image, regions)
        assert descriptions == []

    @pytest.mark.asyncio
    async def test_describe_regions_malformed_response(self, client, sample_image) -> None:
        """Test describe_regions with malformed response returns empty list."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"inference_time_ms": 80.0}
        client._http_client.post = AsyncMock(return_value=mock_response)

        regions = [BoundingBox(x1=0, y1=0, x2=100, y2=100)]
        descriptions = await client.describe_regions(sample_image, regions)
        assert descriptions == []

    @pytest.mark.asyncio
    async def test_describe_regions_sends_correct_endpoint(self, client, sample_image) -> None:
        """Test describe_regions sends request to correct endpoint."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"descriptions": []}
        client._http_client.post = AsyncMock(return_value=mock_response)

        regions = [BoundingBox(x1=0, y1=0, x2=100, y2=100)]
        await client.describe_regions(sample_image, regions)

        call_args = client._http_client.post.call_args
        assert call_args[0][0] == "http://localhost:8092/describe-region"


# =============================================================================
# FlorenceClient.phrase_grounding Tests (NEM-3911)
# =============================================================================


class TestPhraseGrounding:
    """Tests for FlorenceClient.phrase_grounding() method (NEM-3911)."""

    @pytest.mark.asyncio
    async def test_phrase_grounding_success(self, client, sample_image) -> None:
        """Test successful phrase grounding."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "grounded_phrases": [
                {"phrase": "person", "bboxes": [[10, 20, 100, 200]], "confidence_scores": [0.95]},
                {"phrase": "car", "bboxes": [[150, 50, 300, 180]], "confidence_scores": [0.88]},
            ],
            "inference_time_ms": 200.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        phrases = ["person", "car"]
        grounded = await client.phrase_grounding(sample_image, phrases)

        assert len(grounded) == 2
        assert isinstance(grounded[0], GroundedPhrase)
        assert grounded[0].phrase == "person"
        assert len(grounded[0].bboxes) == 1
        assert grounded[1].phrase == "car"

    @pytest.mark.asyncio
    async def test_phrase_grounding_single_phrase(self, client, sample_image) -> None:
        """Test phrase grounding with single phrase."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "grounded_phrases": [
                {
                    "phrase": "delivery driver",
                    "bboxes": [[50, 100, 200, 400]],
                    "confidence_scores": [0.92],
                },
            ],
            "inference_time_ms": 150.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        phrases = ["delivery driver"]
        grounded = await client.phrase_grounding(sample_image, phrases)

        assert len(grounded) == 1
        assert grounded[0].phrase == "delivery driver"

    @pytest.mark.asyncio
    async def test_phrase_grounding_no_matches(self, client, sample_image) -> None:
        """Test phrase grounding when phrase has no matches."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "grounded_phrases": [
                {"phrase": "elephant", "bboxes": [], "confidence_scores": []},
            ],
            "inference_time_ms": 100.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        phrases = ["elephant"]
        grounded = await client.phrase_grounding(sample_image, phrases)

        assert len(grounded) == 1
        assert grounded[0].phrase == "elephant"
        assert grounded[0].bboxes == []

    @pytest.mark.asyncio
    async def test_phrase_grounding_multiple_instances(self, client, sample_image) -> None:
        """Test phrase grounding with multiple instances of same object."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "grounded_phrases": [
                {
                    "phrase": "person",
                    "bboxes": [[10, 20, 100, 200], [150, 30, 250, 220], [300, 50, 400, 250]],
                    "confidence_scores": [0.95, 0.92, 0.89],
                },
            ],
            "inference_time_ms": 180.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        phrases = ["person"]
        grounded = await client.phrase_grounding(sample_image, phrases)

        assert len(grounded) == 1
        assert grounded[0].phrase == "person"
        assert len(grounded[0].bboxes) == 3
        assert len(grounded[0].confidence_scores) == 3

    @pytest.mark.asyncio
    async def test_phrase_grounding_connection_error(self, client, sample_image) -> None:
        """Test phrase_grounding with connection error raises FlorenceUnavailableError."""
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with pytest.raises(FlorenceUnavailableError, match="Failed to connect"):
            await client.phrase_grounding(sample_image, ["person"])

    @pytest.mark.asyncio
    async def test_phrase_grounding_timeout(self, client, sample_image) -> None:
        """Test phrase_grounding with timeout raises FlorenceUnavailableError."""
        client._http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with pytest.raises(FlorenceUnavailableError, match="timed out"):
            await client.phrase_grounding(sample_image, ["person"])

    @pytest.mark.asyncio
    async def test_phrase_grounding_server_error_5xx(self, client, sample_image) -> None:
        """Test phrase_grounding with HTTP 5xx error raises FlorenceUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Gateway",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(FlorenceUnavailableError, match="server error"):
            await client.phrase_grounding(sample_image, ["person"])

    @pytest.mark.asyncio
    async def test_phrase_grounding_client_error_4xx(self, client, sample_image) -> None:
        """Test phrase_grounding with HTTP 4xx error returns empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unprocessable Entity",
            request=MagicMock(),
            response=mock_response,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        grounded = await client.phrase_grounding(sample_image, ["person"])
        assert grounded == []

    @pytest.mark.asyncio
    async def test_phrase_grounding_malformed_response(self, client, sample_image) -> None:
        """Test phrase_grounding with malformed response returns empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"inference_time_ms": 100.0}
        client._http_client.post = AsyncMock(return_value=mock_response)

        grounded = await client.phrase_grounding(sample_image, ["person"])
        assert grounded == []

    @pytest.mark.asyncio
    async def test_phrase_grounding_sends_correct_endpoint(self, client, sample_image) -> None:
        """Test phrase_grounding sends request to correct endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"grounded_phrases": []}
        client._http_client.post = AsyncMock(return_value=mock_response)

        await client.phrase_grounding(sample_image, ["person", "car"])

        call_args = client._http_client.post.call_args
        assert call_args[0][0] == "http://localhost:8092/phrase-grounding"

    @pytest.mark.asyncio
    async def test_phrase_grounding_sends_correct_payload(self, client, sample_image) -> None:
        """Test phrase_grounding sends correct payload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"grounded_phrases": []}
        client._http_client.post = AsyncMock(return_value=mock_response)

        await client.phrase_grounding(sample_image, ["person in blue jacket", "car"])

        call_args = client._http_client.post.call_args
        payload = call_args[1]["json"]
        assert "image" in payload
        assert "phrases" in payload
        assert payload["phrases"] == ["person in blue jacket", "car"]
