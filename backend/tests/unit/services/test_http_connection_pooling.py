"""Unit tests for HTTP connection pooling in AI service clients (NEM-1721).

Tests verify that an AI service client:
1. Create a persistent httpx.AsyncClient in __init__
2. Configure proper connection limits (max_connections=10, max_keepalive_connections=5)
3. Reuse the HTTP client across requests
4. Implement proper cleanup via close() method

These tests use TDD approach - written BEFORE implementation to define expected behavior.

R8 S3 (2026-09-29) leaves DetectorClient as the only subject: this file's other
two classes (TestCLIPClientConnectionPooling, TestFlorenceClientConnectionPooling)
and TestGlobalClientCleanup were deleted with their modules — backend/services/
clip_client.py (ruling 5's CLIP prune) and florence_client.py (ruling 1) are both
gone, and a pooling test for a client that does not ship is a test of nothing.
Their properties are not lost: the pooling contract is pinned here on the
survivor, and the shutdown-cleanup half of it has no surviving shipped mechanism
to pin (grep: no `def reset_*_client` remains in backend/services/, and nothing
in backend/core/ or backend/main.py calls one — DetectorClient is a plain
container-registered singleton with close(), which property 4 above still
covers).
"""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

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
        with patch(
            "backend.services.detector_client.get_settings",
            return_value=mock_settings,
            autospec=True,
        ):
            from backend.services.detector_client import DetectorClient

            client = DetectorClient()

            # Should have a persistent HTTP client
            assert hasattr(client, "_http_client")
            assert isinstance(client._http_client, httpx.AsyncClient)

    def test_init_configures_connection_limits(self, mock_settings):
        """Test that __init__ configures proper connection limits."""
        with patch(
            "backend.services.detector_client.get_settings",
            return_value=mock_settings,
            autospec=True,
        ):
            from backend.services.detector_client import DetectorClient

            client = DetectorClient()

            # Should have configured limits (stored in transport pool)
            pool = client._http_client._transport._pool
            assert pool._max_connections == 10
            assert pool._max_keepalive_connections == 5

    def test_init_configures_timeout(self, mock_settings):
        """Test that __init__ configures timeout on the persistent client."""
        with patch(
            "backend.services.detector_client.get_settings",
            return_value=mock_settings,
            autospec=True,
        ):
            from backend.services.detector_client import DetectorClient

            client = DetectorClient()

            # Should have timeout configured
            assert client._http_client.timeout.connect == mock_settings.ai_connect_timeout
            assert client._http_client.timeout.read == mock_settings.yolo26_read_timeout

    @pytest.mark.asyncio
    async def test_close_method_exists_and_works(self, mock_settings):
        """Test that close() method properly closes the HTTP client."""
        with patch(
            "backend.services.detector_client.get_settings",
            return_value=mock_settings,
            autospec=True,
        ):
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
        with patch(
            "backend.services.detector_client.get_settings",
            return_value=mock_settings,
            autospec=True,
        ):
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
