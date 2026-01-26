"""Unit tests for HTTP connection pooling in AI service clients (NEM-1721).

Tests verify that AI service clients:
1. Create a persistent httpx.AsyncClient in __init__
2. Configure proper connection limits (max_connections=10, max_keepalive_connections=5)
3. Reuse the HTTP client across requests
4. Implement proper cleanup via close() method

These tests use TDD approach - written BEFORE implementation to define expected behavior.
"""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image

# =============================================================================
# DetectorClient Connection Pooling Tests
# =============================================================================


class TestDetectorClientConnectionPooling:
    """Tests for DetectorClient HTTP connection pooling."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for DetectorClient."""
        settings = MagicMock()
        settings.yolo26_url = "http://test-yolo26:8091"
        settings.detection_confidence_threshold = 0.5
        settings.yolo26_api_key = None
        settings.ai_connect_timeout = 10.0
        settings.yolo26_read_timeout = 60.0
        settings.ai_health_timeout = 5.0
        settings.detector_max_retries = 3
        settings.ai_max_concurrent_inferences = 4
        return settings

    def test_init_creates_http_client(self, mock_settings):
        """Test that __init__ creates a persistent httpx.AsyncClient."""
        with patch("backend.services.detector_client.get_settings", return_value=mock_settings):
            from backend.services.detector_client import DetectorClient

            client = DetectorClient()

            # Should have a persistent HTTP client
            assert hasattr(client, "_http_client")
            assert isinstance(client._http_client, httpx.AsyncClient)

    def test_init_configures_connection_limits(self, mock_settings):
        """Test that __init__ configures proper connection limits."""
        with patch("backend.services.detector_client.get_settings", return_value=mock_settings):
            from backend.services.detector_client import DetectorClient

            client = DetectorClient()

            # Should have configured limits (stored in transport pool)
            pool = client._http_client._transport._pool
            assert pool._max_connections == 10
            assert pool._max_keepalive_connections == 5

    def test_init_configures_timeout(self, mock_settings):
        """Test that __init__ configures timeout on the persistent client."""
        with patch("backend.services.detector_client.get_settings", return_value=mock_settings):
            from backend.services.detector_client import DetectorClient

            client = DetectorClient()

            # Should have timeout configured
            assert client._http_client.timeout.connect == mock_settings.ai_connect_timeout
            assert client._http_client.timeout.read == mock_settings.yolo26_read_timeout

    @pytest.mark.asyncio
    async def test_close_method_exists_and_works(self, mock_settings):
        """Test that close() method properly closes the HTTP client."""
        with patch("backend.services.detector_client.get_settings", return_value=mock_settings):
            from backend.services.detector_client import DetectorClient

            client = DetectorClient()

            # Should have close method
            assert hasattr(client, "close")
            assert inspect.iscoroutinefunction(client.close)

            # Should be able to close without error
            await client.close()

            # Client should be closed
            assert client._http_client.is_closed

    @pytest.mark.asyncio
    async def test_health_check_reuses_http_client(self, mock_settings):
        """Test that health_check reuses the persistent HTTP client."""
        with patch("backend.services.detector_client.get_settings", return_value=mock_settings):
            from backend.services.detector_client import DetectorClient

            client = DetectorClient()

            # Mock the health HTTP client's get method
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()

            with patch.object(
                client._health_http_client,
                "get",
                new_callable=AsyncMock,
                return_value=mock_response,
            ):
                await client.health_check()

                # Should use the persistent health client
                client._health_http_client.get.assert_called_once()

            await client.close()


# =============================================================================
# CLIPClient Connection Pooling Tests
# =============================================================================


class TestCLIPClientConnectionPooling:
    """Tests for CLIPClient HTTP connection pooling."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for CLIPClient."""
        settings = MagicMock()
        settings.clip_url = "http://test-clip:8093"
        settings.ai_connect_timeout = 10.0
        settings.ai_health_timeout = 5.0
        settings.clip_cb_failure_threshold = 5
        settings.clip_cb_recovery_timeout = 60.0
        settings.clip_cb_half_open_max_calls = 3
        return settings

    @pytest.fixture
    def sample_image(self):
        """Create a sample PIL image for testing."""
        return Image.new("RGB", (100, 100), color="red")

    def test_init_creates_http_client(self, mock_settings):
        """Test that __init__ creates a persistent httpx.AsyncClient."""
        with patch("backend.services.clip_client.get_settings", return_value=mock_settings):
            from backend.services.clip_client import CLIPClient

            client = CLIPClient()

            # Should have a persistent HTTP client
            assert hasattr(client, "_http_client")
            assert isinstance(client._http_client, httpx.AsyncClient)

    def test_init_configures_connection_limits(self, mock_settings):
        """Test that __init__ configures proper connection limits."""
        with patch("backend.services.clip_client.get_settings", return_value=mock_settings):
            from backend.services.clip_client import CLIPClient

            client = CLIPClient()

            # Should have configured limits (stored in transport pool)
            pool = client._http_client._transport._pool
            assert pool._max_connections == 10
            assert pool._max_keepalive_connections == 5

    @pytest.mark.asyncio
    async def test_close_method_exists_and_works(self, mock_settings):
        """Test that close() method properly closes the HTTP client."""
        with patch("backend.services.clip_client.get_settings", return_value=mock_settings):
            from backend.services.clip_client import CLIPClient

            client = CLIPClient()

            # Should have close method
            assert hasattr(client, "close")
            assert inspect.iscoroutinefunction(client.close)

            # Should be able to close without error
            await client.close()

            # Client should be closed
            assert client._http_client.is_closed

    @pytest.mark.asyncio
    async def test_embed_reuses_http_client(self, mock_settings, sample_image):
        """Test that embed() reuses the persistent HTTP client."""
        with patch("backend.services.clip_client.get_settings", return_value=mock_settings):
            from backend.services.clip_client import EMBEDDING_DIMENSION, CLIPClient

            client = CLIPClient()

            # Mock the HTTP client's post method
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"embedding": [0.1] * EMBEDDING_DIMENSION}

            with patch.object(
                client._http_client, "post", new_callable=AsyncMock, return_value=mock_response
            ):
                await client.embed(sample_image)

                # Should use the persistent client
                client._http_client.post.assert_called_once()

            await client.close()


# =============================================================================
# FlorenceClient Connection Pooling Tests
# =============================================================================


class TestFlorenceClientConnectionPooling:
    """Tests for FlorenceClient HTTP connection pooling."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for FlorenceClient."""
        settings = MagicMock()
        settings.florence_url = "http://test-florence:8092"
        settings.ai_connect_timeout = 10.0
        settings.ai_health_timeout = 5.0
        settings.florence_cb_failure_threshold = 5
        settings.florence_cb_recovery_timeout = 60.0
        settings.florence_cb_half_open_max_calls = 3
        return settings

    @pytest.fixture
    def sample_image(self):
        """Create a sample PIL image for testing."""
        return Image.new("RGB", (100, 100), color="blue")

    def test_init_creates_http_client(self, mock_settings):
        """Test that __init__ creates a persistent httpx.AsyncClient."""
        with patch("backend.services.florence_client.get_settings", return_value=mock_settings):
            from backend.services.florence_client import FlorenceClient

            client = FlorenceClient()

            # Should have a persistent HTTP client
            assert hasattr(client, "_http_client")
            assert isinstance(client._http_client, httpx.AsyncClient)

    def test_init_configures_connection_limits(self, mock_settings):
        """Test that __init__ configures proper connection limits."""
        with patch("backend.services.florence_client.get_settings", return_value=mock_settings):
            from backend.services.florence_client import FlorenceClient

            client = FlorenceClient()

            # Should have configured limits (stored in transport pool)
            pool = client._http_client._transport._pool
            assert pool._max_connections == 10
            assert pool._max_keepalive_connections == 5

    @pytest.mark.asyncio
    async def test_close_method_exists_and_works(self, mock_settings):
        """Test that close() method properly closes the HTTP client."""
        with patch("backend.services.florence_client.get_settings", return_value=mock_settings):
            from backend.services.florence_client import FlorenceClient

            client = FlorenceClient()

            # Should have close method
            assert hasattr(client, "close")
            assert inspect.iscoroutinefunction(client.close)

            # Should be able to close without error
            await client.close()

            # Client should be closed
            assert client._http_client.is_closed

    @pytest.mark.asyncio
    async def test_extract_reuses_http_client(self, mock_settings, sample_image):
        """Test that extract() reuses the persistent HTTP client."""
        with patch("backend.services.florence_client.get_settings", return_value=mock_settings):
            from backend.services.florence_client import FlorenceClient

            client = FlorenceClient()

            # Mock the HTTP client's post method
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"result": "A caption"}

            with patch.object(
                client._http_client, "post", new_callable=AsyncMock, return_value=mock_response
            ):
                await client.extract(sample_image, "<CAPTION>")

                # Should use the persistent client
                client._http_client.post.assert_called_once()

            await client.close()


# =============================================================================
# EnrichmentClient Connection Pooling Tests
# =============================================================================


class TestEnrichmentClientConnectionPooling:
    """Tests for EnrichmentClient HTTP connection pooling."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for EnrichmentClient."""
        settings = MagicMock()
        settings.enrichment_url = "http://test-enrichment:8094"
        settings.ai_connect_timeout = 10.0
        settings.ai_health_timeout = 5.0
        settings.enrichment_cb_failure_threshold = 5
        settings.enrichment_cb_recovery_timeout = 60.0
        settings.enrichment_cb_half_open_max_calls = 3
        # Retry configuration (NEM-1732)
        settings.enrichment_max_retries = 3
        # Read timeout configuration (NEM-2524)
        settings.enrichment_read_timeout = 120.0
        return settings

    @pytest.fixture
    def sample_image(self):
        """Create a sample PIL image for testing."""
        return Image.new("RGB", (100, 100), color="green")

    def test_init_creates_http_client(self, mock_settings):
        """Test that __init__ creates a persistent httpx.AsyncClient."""
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            from backend.services.enrichment_client import EnrichmentClient

            client = EnrichmentClient()

            # Should have a persistent HTTP client
            assert hasattr(client, "_http_client")
            assert isinstance(client._http_client, httpx.AsyncClient)

    def test_init_configures_connection_limits(self, mock_settings):
        """Test that __init__ configures proper connection limits."""
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            from backend.services.enrichment_client import EnrichmentClient

            client = EnrichmentClient()

            # Should have configured limits (stored in transport pool)
            pool = client._http_client._transport._pool
            assert pool._max_connections == 10
            assert pool._max_keepalive_connections == 5

    @pytest.mark.asyncio
    async def test_close_method_exists_and_works(self, mock_settings):
        """Test that close() method properly closes the HTTP client."""
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            from backend.services.enrichment_client import EnrichmentClient

            client = EnrichmentClient()

            # Should have close method
            assert hasattr(client, "close")
            assert inspect.iscoroutinefunction(client.close)

            # Should be able to close without error
            await client.close()

            # Client should be closed
            assert client._http_client.is_closed

    @pytest.mark.asyncio
    async def test_classify_vehicle_reuses_http_client(self, mock_settings, sample_image):
        """Test that classify_vehicle() reuses the persistent HTTP client."""
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            from backend.services.enrichment_client import EnrichmentClient

            client = EnrichmentClient()

            # Mock the HTTP client's post method
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "vehicle_type": "sedan",
                "display_name": "Sedan",
                "confidence": 0.95,
                "is_commercial": False,
                "all_scores": {"sedan": 0.95},
                "inference_time_ms": 50.0,
            }

            with patch.object(
                client._http_client, "post", new_callable=AsyncMock, return_value=mock_response
            ):
                await client.classify_vehicle(sample_image)

                # Should use the persistent client
                client._http_client.post.assert_called_once()

            await client.close()


# =============================================================================
# Global Client Instance Cleanup Tests
# =============================================================================


class TestGlobalClientCleanup:
    """Tests for global client instance cleanup on application shutdown."""

    @pytest.mark.asyncio
    async def test_clip_client_cleanup_on_reset(self):
        """Test that reset_clip_client properly cleans up resources."""
        with patch("backend.services.clip_client.get_settings") as mock_get_settings:
            mock_get_settings.return_value = MagicMock(
                clip_url="http://test:8093",
                ai_connect_timeout=10.0,
                ai_health_timeout=5.0,
                clip_cb_failure_threshold=5,
                clip_cb_recovery_timeout=60.0,
                clip_cb_half_open_max_calls=3,
            )

            from backend.services.clip_client import get_clip_client, reset_clip_client

            # Get a client instance
            client = get_clip_client()
            assert not client._http_client.is_closed

            # Store reference before reset
            http_client_ref = client._http_client

            # Reset should close the HTTP client
            await reset_clip_client()

            # The HTTP client should be closed
            assert http_client_ref.is_closed

    @pytest.mark.asyncio
    async def test_florence_client_cleanup_on_reset(self):
        """Test that reset_florence_client properly cleans up resources."""
        with patch("backend.services.florence_client.get_settings") as mock_get_settings:
            mock_get_settings.return_value = MagicMock(
                florence_url="http://test:8092",
                ai_connect_timeout=10.0,
                ai_health_timeout=5.0,
                florence_cb_failure_threshold=5,
                florence_cb_recovery_timeout=60.0,
                florence_cb_half_open_max_calls=3,
            )

            from backend.services.florence_client import (
                get_florence_client,
                reset_florence_client,
            )

            # Get a client instance
            client = get_florence_client()
            assert not client._http_client.is_closed

            # Store reference before reset
            http_client_ref = client._http_client

            # Reset should close the HTTP client
            await reset_florence_client()

            # The HTTP client should be closed
            assert http_client_ref.is_closed

    @pytest.mark.asyncio
    async def test_enrichment_client_cleanup_on_reset(self):
        """Test that reset_enrichment_client properly cleans up resources."""
        with patch("backend.services.enrichment_client.get_settings") as mock_get_settings:
            mock_get_settings.return_value = MagicMock(
                enrichment_url="http://test:8094",
                ai_connect_timeout=10.0,
                ai_health_timeout=5.0,
                enrichment_cb_failure_threshold=5,
                enrichment_cb_recovery_timeout=60.0,
                enrichment_cb_half_open_max_calls=3,
            )

            from backend.services.enrichment_client import (
                get_enrichment_client,
                reset_enrichment_client,
            )

            # Get a client instance
            client = get_enrichment_client()
            assert not client._http_client.is_closed

            # Store reference before reset
            http_client_ref = client._http_client

            # Reset should close the HTTP client
            await reset_enrichment_client()

            # The HTTP client should be closed
            assert http_client_ref.is_closed
