"""Unit tests for CLIP HTTP client service.

Tests cover:
- CLIPClient initialization and configuration
- Image encoding to base64
- Health check functionality
- Embedding generation (embed method)
- Anomaly score computation
- Zero-shot classification (classify method)
- Image-text similarity (similarity method)
- Batch similarity computation
- Error handling (connection, timeout, HTTP errors)
- Global client singleton functions
"""

import base64
import io
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image

from backend.services.clip_client import (
    CLIP_READ_TIMEOUT,
    DEFAULT_CLIP_URL,
    EMBEDDING_DIMENSION,
    MAX_BATCH_SIZE,
    CLIPClient,
    CLIPUnavailableError,
    get_clip_client,
    reset_clip_client,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.clip_url = "http://test-clip:8093"
    settings.ai_connect_timeout = 10.0
    settings.ai_health_timeout = 5.0
    return settings


@pytest.fixture
def sample_image() -> Image.Image:
    """Create a sample PIL image for testing."""
    # Create a simple 100x100 RGB image
    return Image.new("RGB", (100, 100), color="red")


@pytest.fixture
def valid_embedding() -> list[float]:
    """Create a valid 768-dimensional embedding."""
    return [0.1] * EMBEDDING_DIMENSION


@pytest.fixture
def invalid_embedding_short() -> list[float]:
    """Create an invalid (too short) embedding."""
    return [0.1] * 512


@pytest.fixture
def invalid_embedding_long() -> list[float]:
    """Create an invalid (too long) embedding."""
    return [0.1] * 1024


@pytest.fixture
def client(mock_settings: MagicMock) -> CLIPClient:
    """Create a CLIPClient with mocked settings."""
    with patch("backend.services.clip_client.get_settings", return_value=mock_settings):
        return CLIPClient()


@pytest.fixture
def client_with_url() -> CLIPClient:
    """Create a CLIPClient with explicit URL."""
    with patch("backend.services.clip_client.get_settings") as mock_get_settings:
        mock_get_settings.return_value = MagicMock(
            clip_url="http://default:8093",
            ai_connect_timeout=10.0,
            ai_health_timeout=5.0,
        )
        return CLIPClient(base_url="http://custom-clip:9000/")


# =============================================================================
# CLIPUnavailableError Tests
# =============================================================================


class TestCLIPUnavailableError:
    """Tests for CLIPUnavailableError exception class."""

    def test_init_with_message_only(self) -> None:
        """Test creating error with message only."""
        error = CLIPUnavailableError("Test error message")
        assert str(error) == "Test error message"
        assert error.original_error is None

    def test_init_with_original_error(self) -> None:
        """Test creating error with original exception."""
        original = ValueError("Original error")
        error = CLIPUnavailableError("Test error message", original_error=original)
        assert str(error) == "Test error message"
        assert error.original_error is original

    def test_inheritance(self) -> None:
        """Test that CLIPUnavailableError inherits from Exception."""
        error = CLIPUnavailableError("Test")
        assert isinstance(error, Exception)


# =============================================================================
# CLIPClient Initialization Tests
# =============================================================================


class TestCLIPClientInit:
    """Tests for CLIPClient initialization."""

    def test_init_with_default_url(self, mock_settings: MagicMock) -> None:
        """Test initialization uses settings URL by default."""
        with patch("backend.services.clip_client.get_settings", return_value=mock_settings):
            client = CLIPClient()
            assert client._base_url == "http://test-clip:8093"

    def test_init_with_custom_url(self, mock_settings: MagicMock) -> None:
        """Test initialization with custom URL."""
        with patch("backend.services.clip_client.get_settings", return_value=mock_settings):
            client = CLIPClient(base_url="http://custom:9000")
            assert client._base_url == "http://custom:9000"

    def test_init_strips_trailing_slash(self, mock_settings: MagicMock) -> None:
        """Test that trailing slashes are stripped from URLs."""
        with patch("backend.services.clip_client.get_settings", return_value=mock_settings):
            client = CLIPClient(base_url="http://custom:9000/")
            assert client._base_url == "http://custom:9000"

    def test_init_strips_trailing_slash_from_settings(self) -> None:
        """Test that trailing slashes are stripped from settings URL."""
        settings = MagicMock()
        settings.clip_url = "http://test-clip:8093/"
        settings.ai_connect_timeout = 10.0
        settings.ai_health_timeout = 5.0

        with patch("backend.services.clip_client.get_settings", return_value=settings):
            client = CLIPClient()
            assert client._base_url == "http://test-clip:8093"

    def test_init_creates_timeout_config(self, mock_settings: MagicMock) -> None:
        """Test that timeout configuration is created correctly."""
        with patch("backend.services.clip_client.get_settings", return_value=mock_settings):
            client = CLIPClient()
            assert isinstance(client._timeout, httpx.Timeout)
            assert isinstance(client._health_timeout, httpx.Timeout)


# =============================================================================
# Image Encoding Tests
# =============================================================================


class TestEncodeImageToBase64:
    """Tests for _encode_image_to_base64 method."""

    def test_encode_rgb_image(self, client: CLIPClient, sample_image: Image.Image) -> None:
        """Test encoding an RGB image to base64."""
        result = client._encode_image_to_base64(sample_image)

        # Result should be a string
        assert isinstance(result, str)

        # Result should be valid base64
        decoded = base64.b64decode(result)
        assert len(decoded) > 0

        # Decoded should be a valid PNG image
        buffer = io.BytesIO(decoded)
        loaded_image = Image.open(buffer)
        assert loaded_image.format == "PNG"
        assert loaded_image.size == (100, 100)

    def test_encode_grayscale_image(self, client: CLIPClient) -> None:
        """Test encoding a grayscale image to base64."""
        grayscale_image = Image.new("L", (50, 50), color=128)
        result = client._encode_image_to_base64(grayscale_image)

        # Result should be valid base64
        decoded = base64.b64decode(result)
        buffer = io.BytesIO(decoded)
        loaded_image = Image.open(buffer)
        assert loaded_image.format == "PNG"

    def test_encode_rgba_image(self, client: CLIPClient) -> None:
        """Test encoding an RGBA image with alpha channel to base64."""
        rgba_image = Image.new("RGBA", (50, 50), color=(255, 0, 0, 128))
        result = client._encode_image_to_base64(rgba_image)

        decoded = base64.b64decode(result)
        buffer = io.BytesIO(decoded)
        loaded_image = Image.open(buffer)
        assert loaded_image.format == "PNG"


# =============================================================================
# Health Check Tests
# =============================================================================


class TestCheckHealth:
    """Tests for check_health method."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, client: CLIPClient) -> None:
        """Test successful health check returns True."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await client.check_health()

            assert result is True
            mock_client.get.assert_called_once_with("http://test-clip:8093/health")

    @pytest.mark.asyncio
    async def test_health_check_connect_error(self, client: CLIPClient) -> None:
        """Test health check returns False on connection error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_class.return_value = mock_client

            result = await client.check_health()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_timeout_error(self, client: CLIPClient) -> None:
        """Test health check returns False on timeout."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value = mock_client

            result = await client.check_health()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_http_status_error(self, client: CLIPClient) -> None:
        """Test health check returns False on HTTP error status."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=mock_response
            )
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await client.check_health()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_unexpected_error(self, client: CLIPClient) -> None:
        """Test health check returns False on unexpected error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(side_effect=RuntimeError("Unexpected error"))
            mock_client_class.return_value = mock_client

            result = await client.check_health()

            assert result is False


# =============================================================================
# Embed Method Tests
# =============================================================================


class TestEmbed:
    """Tests for embed method."""

    @pytest.mark.asyncio
    async def test_embed_success(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float]
    ) -> None:
        """Test successful embedding generation."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"embedding": valid_embedding})

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.observe_ai_request_duration") as mock_observe,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await client.embed(sample_image)

            assert result == valid_embedding
            assert len(result) == EMBEDDING_DIMENSION
            mock_observe.assert_called_once()
            mock_client.post.assert_called_once()
            # Verify the URL
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "http://test-clip:8093/embed"

    @pytest.mark.asyncio
    async def test_embed_missing_embedding_field(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test embed raises error when 'embedding' field is missing."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"other": "data"})

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.embed(sample_image)

            assert "missing 'embedding'" in str(exc_info.value)
            mock_record.assert_called_once_with("clip_malformed_response")

    @pytest.mark.asyncio
    async def test_embed_invalid_dimension(
        self, client: CLIPClient, sample_image: Image.Image, invalid_embedding_short: list[float]
    ) -> None:
        """Test embed raises error when embedding dimension is invalid."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"embedding": invalid_embedding_short})

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.embed(sample_image)

            assert "invalid dimension" in str(exc_info.value)
            mock_record.assert_called_once_with("clip_invalid_dimension")

    @pytest.mark.asyncio
    async def test_embed_connect_error(self, client: CLIPClient, sample_image: Image.Image) -> None:
        """Test embed raises CLIPUnavailableError on connection error."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.embed(sample_image)

            assert "Failed to connect" in str(exc_info.value)
            assert isinstance(exc_info.value.original_error, httpx.ConnectError)
            mock_record.assert_called_once_with("clip_connection_error")

    @pytest.mark.asyncio
    async def test_embed_timeout_error(self, client: CLIPClient, sample_image: Image.Image) -> None:
        """Test embed raises CLIPUnavailableError on timeout."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.embed(sample_image)

            assert "timed out" in str(exc_info.value)
            assert isinstance(exc_info.value.original_error, httpx.TimeoutException)
            mock_record.assert_called_once_with("clip_timeout")

    @pytest.mark.asyncio
    async def test_embed_server_error_5xx(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test embed raises CLIPUnavailableError on 5xx HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_response)

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=error)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.embed(sample_image)

            assert "server error: 500" in str(exc_info.value)
            mock_record.assert_called_once_with("clip_server_error")

    @pytest.mark.asyncio
    async def test_embed_client_error_4xx(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test embed raises CLIPUnavailableError on 4xx HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        error = httpx.HTTPStatusError("Bad request", request=MagicMock(), response=mock_response)

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=error)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.embed(sample_image)

            assert "client error: 400" in str(exc_info.value)
            mock_record.assert_called_once_with("clip_client_error")

    @pytest.mark.asyncio
    async def test_embed_unexpected_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test embed raises CLIPUnavailableError on unexpected error."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=RuntimeError("Unexpected"))
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.embed(sample_image)

            assert "Unexpected error" in str(exc_info.value)
            mock_record.assert_called_once_with("clip_unexpected_error")


# =============================================================================
# Anomaly Score Tests
# =============================================================================


class TestAnomalyScore:
    """Tests for anomaly_score method."""

    @pytest.mark.asyncio
    async def test_anomaly_score_success(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float]
    ) -> None:
        """Test successful anomaly score computation."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={"anomaly_score": 0.3, "similarity_to_baseline": 0.7}
        )

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.observe_ai_request_duration") as mock_observe,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            anomaly_score, similarity = await client.anomaly_score(sample_image, valid_embedding)

            assert anomaly_score == 0.3
            assert similarity == 0.7
            mock_observe.assert_called_once()

    @pytest.mark.asyncio
    async def test_anomaly_score_invalid_baseline_dimension(
        self, client: CLIPClient, sample_image: Image.Image, invalid_embedding_short: list[float]
    ) -> None:
        """Test anomaly_score raises ValueError for wrong baseline dimension."""
        with pytest.raises(ValueError) as exc_info:
            await client.anomaly_score(sample_image, invalid_embedding_short)

        assert "768 dimensions" in str(exc_info.value)
        assert "512" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_anomaly_score_missing_anomaly_score_field(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float]
    ) -> None:
        """Test anomaly_score raises error when 'anomaly_score' field is missing."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"similarity_to_baseline": 0.7})

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.anomaly_score(sample_image, valid_embedding)

            assert "missing 'anomaly_score'" in str(exc_info.value)
            mock_record.assert_called_once_with("clip_anomaly_malformed_response")

    @pytest.mark.asyncio
    async def test_anomaly_score_missing_similarity_field(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float]
    ) -> None:
        """Test anomaly_score raises error when 'similarity_to_baseline' field is missing."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"anomaly_score": 0.3})

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.anomaly_score(sample_image, valid_embedding)

            assert "missing 'similarity_to_baseline'" in str(exc_info.value)
            mock_record.assert_called_once_with("clip_anomaly_malformed_response")

    @pytest.mark.asyncio
    async def test_anomaly_score_connect_error(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float]
    ) -> None:
        """Test anomaly_score raises CLIPUnavailableError on connection error."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.anomaly_score(sample_image, valid_embedding)

            assert "Failed to connect" in str(exc_info.value)
            mock_record.assert_called_once_with("clip_anomaly_connection_error")

    @pytest.mark.asyncio
    async def test_anomaly_score_timeout_error(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float]
    ) -> None:
        """Test anomaly_score raises CLIPUnavailableError on timeout."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.anomaly_score(sample_image, valid_embedding)

            assert "timed out" in str(exc_info.value)
            mock_record.assert_called_once_with("clip_anomaly_timeout")

    @pytest.mark.asyncio
    async def test_anomaly_score_server_error(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float]
    ) -> None:
        """Test anomaly_score raises CLIPUnavailableError on server error."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        error = httpx.HTTPStatusError(
            "Service unavailable", request=MagicMock(), response=mock_response
        )

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=error)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.anomaly_score(sample_image, valid_embedding)

            assert "server error: 503" in str(exc_info.value)
            mock_record.assert_called_once_with("clip_anomaly_server_error")

    @pytest.mark.asyncio
    async def test_anomaly_score_client_error(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float]
    ) -> None:
        """Test anomaly_score raises CLIPUnavailableError on client error."""
        mock_response = MagicMock()
        mock_response.status_code = 422
        error = httpx.HTTPStatusError(
            "Unprocessable entity", request=MagicMock(), response=mock_response
        )

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=error)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.anomaly_score(sample_image, valid_embedding)

            assert "client error: 422" in str(exc_info.value)
            mock_record.assert_called_once_with("clip_anomaly_client_error")

    @pytest.mark.asyncio
    async def test_anomaly_score_unexpected_error(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float]
    ) -> None:
        """Test anomaly_score raises CLIPUnavailableError on unexpected error."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=RuntimeError("Unexpected"))
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.anomaly_score(sample_image, valid_embedding)

            assert "Unexpected error" in str(exc_info.value)
            mock_record.assert_called_once_with("clip_anomaly_unexpected_error")

    @pytest.mark.asyncio
    async def test_anomaly_score_reraises_clip_unavailable_error(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float]
    ) -> None:
        """Test that anomaly_score re-raises CLIPUnavailableError without wrapping."""
        original_error = CLIPUnavailableError("Original error")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=original_error)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.anomaly_score(sample_image, valid_embedding)

            assert exc_info.value is original_error


# =============================================================================
# Classify Method Tests
# =============================================================================


class TestClassify:
    """Tests for classify method."""

    @pytest.mark.asyncio
    async def test_classify_success(self, client: CLIPClient, sample_image: Image.Image) -> None:
        """Test successful zero-shot classification."""
        labels = ["cat", "dog", "person"]
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={"scores": {"cat": 0.1, "dog": 0.2, "person": 0.7}, "top_label": "person"}
        )

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.observe_ai_request_duration") as mock_observe,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            scores, top_label = await client.classify(sample_image, labels)

            assert scores == {"cat": 0.1, "dog": 0.2, "person": 0.7}
            assert top_label == "person"
            mock_observe.assert_called_once()

    @pytest.mark.asyncio
    async def test_classify_empty_labels(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test classify raises ValueError for empty labels list."""
        with pytest.raises(ValueError) as exc_info:
            await client.classify(sample_image, [])

        assert "cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_classify_missing_scores_field(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test classify raises error when 'scores' field is missing."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"top_label": "person"})

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.classify(sample_image, ["cat", "dog"])

            assert "missing 'scores' or 'top_label'" in str(exc_info.value)
            mock_record.assert_called_once_with("clip_malformed_response")

    @pytest.mark.asyncio
    async def test_classify_missing_top_label_field(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test classify raises error when 'top_label' field is missing."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"scores": {"cat": 0.5, "dog": 0.5}})

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.classify(sample_image, ["cat", "dog"])

            assert "missing 'scores' or 'top_label'" in str(exc_info.value)
            mock_record.assert_called_once_with("clip_malformed_response")

    @pytest.mark.asyncio
    async def test_classify_connect_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test classify raises CLIPUnavailableError on connection error."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError):
                await client.classify(sample_image, ["cat"])

            mock_record.assert_called_once_with("clip_connection_error")

    @pytest.mark.asyncio
    async def test_classify_timeout_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test classify raises CLIPUnavailableError on timeout."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError):
                await client.classify(sample_image, ["cat"])

            mock_record.assert_called_once_with("clip_timeout")

    @pytest.mark.asyncio
    async def test_classify_server_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test classify raises CLIPUnavailableError on server error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError(
            "Internal server error", request=MagicMock(), response=mock_response
        )

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=error)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError):
                await client.classify(sample_image, ["cat"])

            mock_record.assert_called_once_with("clip_server_error")

    @pytest.mark.asyncio
    async def test_classify_client_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test classify raises CLIPUnavailableError on client error."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        error = httpx.HTTPStatusError("Bad request", request=MagicMock(), response=mock_response)

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=error)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError):
                await client.classify(sample_image, ["cat"])

            mock_record.assert_called_once_with("clip_client_error")

    @pytest.mark.asyncio
    async def test_classify_unexpected_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test classify raises CLIPUnavailableError on unexpected error."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=RuntimeError("Unexpected"))
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError):
                await client.classify(sample_image, ["cat"])

            mock_record.assert_called_once_with("clip_unexpected_error")

    @pytest.mark.asyncio
    async def test_classify_reraises_clip_unavailable_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test that classify re-raises CLIPUnavailableError without wrapping."""
        original_error = CLIPUnavailableError("Original error")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=original_error)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.classify(sample_image, ["cat"])

            assert exc_info.value is original_error


# =============================================================================
# Similarity Method Tests
# =============================================================================


class TestSimilarity:
    """Tests for similarity method."""

    @pytest.mark.asyncio
    async def test_similarity_success(self, client: CLIPClient, sample_image: Image.Image) -> None:
        """Test successful similarity computation."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"similarity": 0.85})

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.observe_ai_request_duration") as mock_observe,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await client.similarity(sample_image, "a photo of a red square")

            assert result == 0.85
            mock_observe.assert_called_once()

    @pytest.mark.asyncio
    async def test_similarity_missing_field(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test similarity raises error when 'similarity' field is missing."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"other": "data"})

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.similarity(sample_image, "text")

            assert "missing 'similarity'" in str(exc_info.value)
            mock_record.assert_called_once_with("clip_malformed_response")

    @pytest.mark.asyncio
    async def test_similarity_connect_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test similarity raises CLIPUnavailableError on connection error."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError):
                await client.similarity(sample_image, "text")

            mock_record.assert_called_once_with("clip_connection_error")

    @pytest.mark.asyncio
    async def test_similarity_timeout_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test similarity raises CLIPUnavailableError on timeout."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError):
                await client.similarity(sample_image, "text")

            mock_record.assert_called_once_with("clip_timeout")

    @pytest.mark.asyncio
    async def test_similarity_server_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test similarity raises CLIPUnavailableError on server error."""
        mock_response = MagicMock()
        mock_response.status_code = 502
        error = httpx.HTTPStatusError("Bad gateway", request=MagicMock(), response=mock_response)

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=error)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError):
                await client.similarity(sample_image, "text")

            mock_record.assert_called_once_with("clip_server_error")

    @pytest.mark.asyncio
    async def test_similarity_client_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test similarity raises CLIPUnavailableError on client error."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        error = httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=error)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError):
                await client.similarity(sample_image, "text")

            mock_record.assert_called_once_with("clip_client_error")

    @pytest.mark.asyncio
    async def test_similarity_unexpected_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test similarity raises CLIPUnavailableError on unexpected error."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=RuntimeError("Unexpected"))
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError):
                await client.similarity(sample_image, "text")

            mock_record.assert_called_once_with("clip_unexpected_error")

    @pytest.mark.asyncio
    async def test_similarity_reraises_clip_unavailable_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test that similarity re-raises CLIPUnavailableError without wrapping."""
        original_error = CLIPUnavailableError("Original error")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=original_error)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.similarity(sample_image, "text")

            assert exc_info.value is original_error


# =============================================================================
# Batch Similarity Tests
# =============================================================================


class TestBatchSimilarity:
    """Tests for batch_similarity method."""

    @pytest.mark.asyncio
    async def test_batch_similarity_success(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test successful batch similarity computation."""
        texts = ["cat", "dog", "bird"]
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={"similarities": {"cat": 0.3, "dog": 0.6, "bird": 0.1}}
        )

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.observe_ai_request_duration") as mock_observe,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await client.batch_similarity(sample_image, texts)

            assert result == {"cat": 0.3, "dog": 0.6, "bird": 0.1}
            mock_observe.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_similarity_empty_texts(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test batch_similarity raises ValueError for empty texts list."""
        with pytest.raises(ValueError) as exc_info:
            await client.batch_similarity(sample_image, [])

        assert "cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_batch_similarity_exceeds_max_batch_size(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test batch_similarity raises ValueError when texts exceed MAX_BATCH_SIZE."""
        # Create a list with more texts than allowed
        oversized_texts = [f"text_{i}" for i in range(MAX_BATCH_SIZE + 1)]

        with pytest.raises(ValueError) as exc_info:
            await client.batch_similarity(sample_image, oversized_texts)

        error_msg = str(exc_info.value)
        assert f"Batch size {MAX_BATCH_SIZE + 1}" in error_msg
        assert f"exceeds maximum of {MAX_BATCH_SIZE}" in error_msg
        assert "Split the texts into smaller batches" in error_msg

    @pytest.mark.asyncio
    async def test_batch_similarity_at_max_batch_size(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test batch_similarity accepts exactly MAX_BATCH_SIZE texts."""
        # Create exactly MAX_BATCH_SIZE texts
        max_texts = [f"text_{i}" for i in range(MAX_BATCH_SIZE)]
        expected_similarities = dict.fromkeys(max_texts, 0.5)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"similarities": expected_similarities})

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.observe_ai_request_duration"),
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await client.batch_similarity(sample_image, max_texts)

            assert result == expected_similarities
            assert len(result) == MAX_BATCH_SIZE

    @pytest.mark.asyncio
    async def test_batch_similarity_large_overage(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test batch_similarity rejects significantly oversized batches."""
        # Create a list with many more texts than allowed (e.g., 500)
        large_oversized_texts = [f"text_{i}" for i in range(500)]

        with pytest.raises(ValueError) as exc_info:
            await client.batch_similarity(sample_image, large_oversized_texts)

        error_msg = str(exc_info.value)
        assert "500" in error_msg
        assert f"exceeds maximum of {MAX_BATCH_SIZE}" in error_msg

    @pytest.mark.asyncio
    async def test_batch_similarity_missing_field(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test batch_similarity raises error when 'similarities' field is missing."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"other": "data"})

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.batch_similarity(sample_image, ["cat"])

            assert "missing 'similarities'" in str(exc_info.value)
            mock_record.assert_called_once_with("clip_malformed_response")

    @pytest.mark.asyncio
    async def test_batch_similarity_connect_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test batch_similarity raises CLIPUnavailableError on connection error."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError):
                await client.batch_similarity(sample_image, ["cat"])

            mock_record.assert_called_once_with("clip_connection_error")

    @pytest.mark.asyncio
    async def test_batch_similarity_timeout_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test batch_similarity raises CLIPUnavailableError on timeout."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError):
                await client.batch_similarity(sample_image, ["cat"])

            mock_record.assert_called_once_with("clip_timeout")

    @pytest.mark.asyncio
    async def test_batch_similarity_server_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test batch_similarity raises CLIPUnavailableError on server error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError(
            "Internal server error", request=MagicMock(), response=mock_response
        )

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=error)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError):
                await client.batch_similarity(sample_image, ["cat"])

            mock_record.assert_called_once_with("clip_server_error")

    @pytest.mark.asyncio
    async def test_batch_similarity_client_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test batch_similarity raises CLIPUnavailableError on client error."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        error = httpx.HTTPStatusError("Bad request", request=MagicMock(), response=mock_response)

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=error)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError):
                await client.batch_similarity(sample_image, ["cat"])

            mock_record.assert_called_once_with("clip_client_error")

    @pytest.mark.asyncio
    async def test_batch_similarity_unexpected_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test batch_similarity raises CLIPUnavailableError on unexpected error."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=RuntimeError("Unexpected"))
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError):
                await client.batch_similarity(sample_image, ["cat"])

            mock_record.assert_called_once_with("clip_unexpected_error")

    @pytest.mark.asyncio
    async def test_batch_similarity_reraises_clip_unavailable_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test that batch_similarity re-raises CLIPUnavailableError without wrapping."""
        original_error = CLIPUnavailableError("Original error")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=original_error)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.batch_similarity(sample_image, ["cat"])

            assert exc_info.value is original_error


# =============================================================================
# Global Client Singleton Tests
# =============================================================================


class TestGlobalClientSingleton:
    """Tests for global client singleton functions."""

    def test_get_clip_client_creates_instance(self, mock_settings: MagicMock) -> None:
        """Test that get_clip_client creates a new instance."""
        reset_clip_client()

        with patch("backend.services.clip_client.get_settings", return_value=mock_settings):
            client = get_clip_client()
            assert isinstance(client, CLIPClient)

    def test_get_clip_client_returns_same_instance(self, mock_settings: MagicMock) -> None:
        """Test that get_clip_client returns the same instance on subsequent calls."""
        reset_clip_client()

        with patch("backend.services.clip_client.get_settings", return_value=mock_settings):
            client1 = get_clip_client()
            client2 = get_clip_client()
            assert client1 is client2

    def test_reset_clip_client_clears_instance(self, mock_settings: MagicMock) -> None:
        """Test that reset_clip_client clears the global instance."""
        reset_clip_client()

        with patch("backend.services.clip_client.get_settings", return_value=mock_settings):
            client1 = get_clip_client()
            reset_clip_client()
            client2 = get_clip_client()
            assert client1 is not client2

    def test_reset_clip_client_when_none(self) -> None:
        """Test that reset_clip_client works when client is already None."""
        reset_clip_client()
        # Should not raise
        reset_clip_client()


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_default_clip_url(self) -> None:
        """Test the default CLIP URL constant."""
        assert DEFAULT_CLIP_URL == "http://ai-clip:8093"

    def test_embedding_dimension(self) -> None:
        """Test the embedding dimension constant."""
        assert EMBEDDING_DIMENSION == 768

    def test_clip_read_timeout(self) -> None:
        """Test the CLIP read timeout constant."""
        assert CLIP_READ_TIMEOUT == 15.0

    def test_max_batch_size(self) -> None:
        """Test the MAX_BATCH_SIZE constant."""
        assert MAX_BATCH_SIZE == 100


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and integration scenarios."""

    @pytest.mark.asyncio
    async def test_embed_with_large_image(
        self, client: CLIPClient, valid_embedding: list[float]
    ) -> None:
        """Test embedding generation with a large image."""
        large_image = Image.new("RGB", (4096, 4096), color="blue")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"embedding": valid_embedding})

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.observe_ai_request_duration"),
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await client.embed(large_image)
            assert len(result) == EMBEDDING_DIMENSION

    @pytest.mark.asyncio
    async def test_embed_reraises_clip_unavailable_error(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test that embed re-raises CLIPUnavailableError without wrapping."""
        original_error = CLIPUnavailableError("Original error")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=original_error)
            mock_client_class.return_value = mock_client

            with pytest.raises(CLIPUnavailableError) as exc_info:
                await client.embed(sample_image)

            assert exc_info.value is original_error

    @pytest.mark.asyncio
    async def test_anomaly_score_verifies_url_endpoint(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float]
    ) -> None:
        """Test that anomaly_score uses the correct endpoint."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={"anomaly_score": 0.3, "similarity_to_baseline": 0.7}
        )

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.observe_ai_request_duration"),
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await client.anomaly_score(sample_image, valid_embedding)

            call_args = mock_client.post.call_args
            assert call_args[0][0] == "http://test-clip:8093/anomaly-score"

    @pytest.mark.asyncio
    async def test_classify_verifies_url_endpoint(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test that classify uses the correct endpoint."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"scores": {"cat": 1.0}, "top_label": "cat"})

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.observe_ai_request_duration"),
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await client.classify(sample_image, ["cat"])

            call_args = mock_client.post.call_args
            assert call_args[0][0] == "http://test-clip:8093/classify"

    @pytest.mark.asyncio
    async def test_similarity_verifies_url_endpoint(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test that similarity uses the correct endpoint."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"similarity": 0.5})

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.observe_ai_request_duration"),
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await client.similarity(sample_image, "text")

            call_args = mock_client.post.call_args
            assert call_args[0][0] == "http://test-clip:8093/similarity"

    @pytest.mark.asyncio
    async def test_batch_similarity_verifies_url_endpoint(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Test that batch_similarity uses the correct endpoint."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"similarities": {"cat": 0.5}})

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.observe_ai_request_duration"),
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await client.batch_similarity(sample_image, ["cat"])

            call_args = mock_client.post.call_args
            assert call_args[0][0] == "http://test-clip:8093/batch-similarity"

    @pytest.mark.asyncio
    async def test_embed_sends_correct_payload(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float]
    ) -> None:
        """Test that embed sends the correct JSON payload."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"embedding": valid_embedding})

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.clip_client.observe_ai_request_duration"),
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await client.embed(sample_image)

            call_kwargs = mock_client.post.call_args[1]
            assert "json" in call_kwargs
            assert "image" in call_kwargs["json"]
            # Verify the image is base64 encoded
            decoded = base64.b64decode(call_kwargs["json"]["image"])
            buffer = io.BytesIO(decoded)
            loaded_image = Image.open(buffer)
            assert loaded_image.format == "PNG"
