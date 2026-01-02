"""Unit tests for the CLIP HTTP client service.

Tests for backend/services/clip_client.py which provides an HTTP client
interface to the ai-clip embedding service.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image

from backend.services.clip_client import (
    CLIP_READ_TIMEOUT,
    EMBEDDING_DIMENSION,
    CLIPClient,
    CLIPUnavailableError,
    get_clip_client,
    reset_clip_client,
)


class TestCLIPClient:
    """Tests for CLIPClient class."""

    def test_client_initialization(self) -> None:
        """Test CLIPClient initializes with default URL."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient()
            assert client._base_url == "http://localhost:8093"

    def test_client_initialization_custom_url(self) -> None:
        """Test CLIPClient initializes with custom URL."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient(base_url="http://custom:9999/")
            assert client._base_url == "http://custom:9999"

    def test_encode_image_to_base64(self) -> None:
        """Test image encoding to base64."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient()

            # Create a small test image
            image = Image.new("RGB", (10, 10), color=(255, 0, 0))
            encoded = client._encode_image_to_base64(image)

            # Should be a non-empty base64 string
            assert isinstance(encoded, str)
            assert len(encoded) > 0

    @pytest.mark.asyncio
    async def test_check_health_success(self) -> None:
        """Test successful health check."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient()

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_client.get.return_value = mock_response

                result = await client.check_health()
                assert result is True

    @pytest.mark.asyncio
    async def test_check_health_connection_error(self) -> None:
        """Test health check with connection error."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient()

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client
                mock_client.get.side_effect = httpx.ConnectError("Connection refused")

                result = await client.check_health()
                assert result is False

    @pytest.mark.asyncio
    async def test_check_health_timeout(self) -> None:
        """Test health check with timeout."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient()

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client
                mock_client.get.side_effect = httpx.TimeoutException("Timeout")

                result = await client.check_health()
                assert result is False

    @pytest.mark.asyncio
    async def test_embed_success(self) -> None:
        """Test successful embedding generation."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient()

            # Create a test image
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "embedding": [0.1] * EMBEDDING_DIMENSION,
                    "inference_time_ms": 25.5,
                }
                mock_client.post.return_value = mock_response

                embedding = await client.embed(image)

                assert len(embedding) == EMBEDDING_DIMENSION
                assert embedding[0] == 0.1

    @pytest.mark.asyncio
    async def test_embed_connection_error(self) -> None:
        """Test embedding with connection error raises CLIPUnavailableError."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client
                mock_client.post.side_effect = httpx.ConnectError("Connection refused")

                with pytest.raises(CLIPUnavailableError, match="Failed to connect"):
                    await client.embed(image)

    @pytest.mark.asyncio
    async def test_embed_timeout(self) -> None:
        """Test embedding with timeout raises CLIPUnavailableError."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client
                mock_client.post.side_effect = httpx.TimeoutException("Timeout")

                with pytest.raises(CLIPUnavailableError, match="timed out"):
                    await client.embed(image)

    @pytest.mark.asyncio
    async def test_embed_server_error(self) -> None:
        """Test embedding with server error raises CLIPUnavailableError."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client

                mock_response = MagicMock()
                mock_response.status_code = 500
                mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                    "Server Error",
                    request=MagicMock(),
                    response=mock_response,
                )
                mock_client.post.return_value = mock_response

                with pytest.raises(CLIPUnavailableError, match="server error"):
                    await client.embed(image)

    @pytest.mark.asyncio
    async def test_embed_malformed_response(self) -> None:
        """Test embedding with malformed response raises CLIPUnavailableError."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client

                mock_response = MagicMock()
                mock_response.status_code = 200
                # Missing 'embedding' key
                mock_response.json.return_value = {"inference_time_ms": 25.5}
                mock_client.post.return_value = mock_response

                with pytest.raises(CLIPUnavailableError, match="missing 'embedding'"):
                    await client.embed(image)

    @pytest.mark.asyncio
    async def test_embed_invalid_dimension(self) -> None:
        """Test embedding with wrong dimension raises CLIPUnavailableError."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client

                mock_response = MagicMock()
                mock_response.status_code = 200
                # Wrong dimension (should be 768)
                mock_response.json.return_value = {
                    "embedding": [0.1] * 512,
                    "inference_time_ms": 25.5,
                }
                mock_client.post.return_value = mock_response

                with pytest.raises(CLIPUnavailableError, match="invalid dimension"):
                    await client.embed(image)

    @pytest.mark.asyncio
    async def test_anomaly_score_success(self) -> None:
        """Test successful anomaly score computation."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient()

            # Create a test image
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))
            # Create a baseline embedding
            baseline = [0.1] * EMBEDDING_DIMENSION

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "anomaly_score": 0.35,
                    "similarity_to_baseline": 0.65,
                    "inference_time_ms": 30.5,
                }
                mock_client.post.return_value = mock_response

                anomaly, similarity = await client.anomaly_score(image, baseline)

                assert anomaly == 0.35
                assert similarity == 0.65

                # Verify the correct endpoint was called
                mock_client.post.assert_called_once()
                call_args = mock_client.post.call_args
                assert "/anomaly-score" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_anomaly_score_invalid_baseline_dimension(self) -> None:
        """Test anomaly_score with wrong baseline dimension raises ValueError."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))
            # Wrong dimension (should be 768)
            baseline = [0.1] * 512

            with pytest.raises(ValueError, match="768 dimensions"):
                await client.anomaly_score(image, baseline)

    @pytest.mark.asyncio
    async def test_anomaly_score_connection_error(self) -> None:
        """Test anomaly_score with connection error raises CLIPUnavailableError."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))
            baseline = [0.1] * EMBEDDING_DIMENSION

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client
                mock_client.post.side_effect = httpx.ConnectError("Connection refused")

                with pytest.raises(CLIPUnavailableError, match="Failed to connect"):
                    await client.anomaly_score(image, baseline)

    @pytest.mark.asyncio
    async def test_anomaly_score_timeout(self) -> None:
        """Test anomaly_score with timeout raises CLIPUnavailableError."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))
            baseline = [0.1] * EMBEDDING_DIMENSION

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client
                mock_client.post.side_effect = httpx.TimeoutException("Timeout")

                with pytest.raises(CLIPUnavailableError, match="timed out"):
                    await client.anomaly_score(image, baseline)

    @pytest.mark.asyncio
    async def test_anomaly_score_missing_anomaly_score(self) -> None:
        """Test anomaly_score with missing anomaly_score field raises error."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))
            baseline = [0.1] * EMBEDDING_DIMENSION

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client

                mock_response = MagicMock()
                mock_response.status_code = 200
                # Missing 'anomaly_score' key
                mock_response.json.return_value = {
                    "similarity_to_baseline": 0.65,
                    "inference_time_ms": 30.5,
                }
                mock_client.post.return_value = mock_response

                with pytest.raises(CLIPUnavailableError, match="missing 'anomaly_score'"):
                    await client.anomaly_score(image, baseline)

    @pytest.mark.asyncio
    async def test_anomaly_score_missing_similarity(self) -> None:
        """Test anomaly_score with missing similarity_to_baseline field raises error."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))
            baseline = [0.1] * EMBEDDING_DIMENSION

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client

                mock_response = MagicMock()
                mock_response.status_code = 200
                # Missing 'similarity_to_baseline' key
                mock_response.json.return_value = {
                    "anomaly_score": 0.35,
                    "inference_time_ms": 30.5,
                }
                mock_client.post.return_value = mock_response

                with pytest.raises(CLIPUnavailableError, match="missing 'similarity_to_baseline'"):
                    await client.anomaly_score(image, baseline)

    @pytest.mark.asyncio
    async def test_anomaly_score_server_error(self) -> None:
        """Test anomaly_score with server error raises CLIPUnavailableError."""
        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client = CLIPClient()
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))
            baseline = [0.1] * EMBEDDING_DIMENSION

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client

                mock_response = MagicMock()
                mock_response.status_code = 500
                mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                    "Server Error",
                    request=MagicMock(),
                    response=mock_response,
                )
                mock_client.post.return_value = mock_response

                with pytest.raises(CLIPUnavailableError, match="server error"):
                    await client.anomaly_score(image, baseline)


class TestGlobalClientFunctions:
    """Tests for global client singleton functions."""

    def test_get_clip_client_singleton(self) -> None:
        """Test get_clip_client returns singleton instance."""
        reset_clip_client()

        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client1 = get_clip_client()
            client2 = get_clip_client()

            assert client1 is client2

        reset_clip_client()

    def test_reset_clip_client(self) -> None:
        """Test reset_clip_client clears the singleton."""
        reset_clip_client()

        with patch("backend.services.clip_client.get_settings") as mock_settings:
            mock_settings.return_value.clip_url = "http://localhost:8093"
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.ai_health_timeout = 5.0

            client1 = get_clip_client()
            reset_clip_client()
            client2 = get_clip_client()

            assert client1 is not client2

        reset_clip_client()


class TestCLIPUnavailableError:
    """Tests for CLIPUnavailableError exception."""

    def test_error_with_message(self) -> None:
        """Test error creation with message."""
        error = CLIPUnavailableError("Service unavailable")
        assert str(error) == "Service unavailable"
        assert error.original_error is None

    def test_error_with_original_error(self) -> None:
        """Test error creation with original error."""
        original = ValueError("Original error")
        error = CLIPUnavailableError("Wrapped error", original_error=original)
        assert str(error) == "Wrapped error"
        assert error.original_error is original


class TestConstants:
    """Tests for module constants."""

    def test_embedding_dimension(self) -> None:
        """Test EMBEDDING_DIMENSION is correct for CLIP ViT-L."""
        assert EMBEDDING_DIMENSION == 768

    def test_timeout_values(self) -> None:
        """Test timeout values are reasonable."""
        assert CLIP_READ_TIMEOUT == 15.0  # Embeddings should be fast
