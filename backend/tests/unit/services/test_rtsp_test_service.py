"""Unit tests for RTSP connection testing service.

NEM-4382: Test-Driven Development for RTSP connection validation.
These tests define the expected behavior for the RTSPTestService class.

Tests cover:
- Successful connection testing
- Timeout handling (5 second limit)
- Authentication failure detection
- Invalid URL format handling
- Capability detection (resolution, codec, fps)
- Error message clarity
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from backend.services.rtsp_test_service import (
    RTSPCapabilities,
    RTSPTestResult,
    RTSPTestService,
)


class TestRTSPTestService:
    """Test suite for RTSPTestService."""

    @pytest.fixture
    def service(self) -> RTSPTestService:
        """Create an RTSPTestService instance."""
        return RTSPTestService()

    @pytest.mark.asyncio
    async def test_successful_connection(self, service: RTSPTestService) -> None:
        """Test successful RTSP connection returns capabilities.

        Success criteria:
        - Returns success=True
        - Includes latency_ms
        - Includes capabilities (resolution, codec, fps)
        - No error message
        """
        url = "rtsp://192.168.1.100:554/stream1"
        username = "admin"
        password = "secret123"  # nosemgrep: hardcoded-password # pragma: allowlist secret

        # Mock successful connection
        with patch("backend.services.rtsp_test_service.cv2.VideoCapture") as mock_cap:
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = True
            mock_instance.get.side_effect = lambda prop: {
                3: 1920,  # CV_CAP_PROP_FRAME_WIDTH
                4: 1080,  # CV_CAP_PROP_FRAME_HEIGHT
                5: 25.0,  # CV_CAP_PROP_FPS
            }.get(prop, 0)
            mock_cap.return_value = mock_instance

            result = await service.test_connection(
                rtsp_url=url, username=username, password=password
            )

            assert result.success is True
            assert result.latency_ms is not None
            assert result.latency_ms > 0
            assert result.error_message is None

            # Check capabilities
            assert result.capabilities is not None
            assert result.capabilities.video is True
            assert result.capabilities.resolution == "1920x1080"
            assert result.capabilities.codec == "H.264"  # Default assumption
            assert result.capabilities.fps == 25

    @pytest.mark.asyncio
    async def test_connection_timeout(self, service: RTSPTestService) -> None:
        """Test that connection attempts timeout after 5 seconds.

        Timeout criteria:
        - Operation completes within 5 seconds
        - Returns success=False
        - Includes clear timeout error message
        """
        url = "rtsp://192.168.1.100:554/stream1"

        # Mock a hanging connection
        async def slow_connection(*args, **kwargs):
            await asyncio.sleep(10)  # Exceed 5 second timeout
            return MagicMock()

        with patch(
            "backend.services.rtsp_test_service.cv2.VideoCapture", side_effect=slow_connection
        ):
            result = await service.test_connection(rtsp_url=url)

            assert result.success is False
            assert result.error_message is not None
            assert "timeout" in result.error_message.lower()
            assert result.capabilities is None

    @pytest.mark.asyncio
    async def test_authentication_failure(self, service: RTSPTestService) -> None:
        """Test authentication failure detection.

        Auth failure criteria:
        - Returns success=False
        - Error message indicates authentication issue
        - Suggests checking username/password
        """
        url = "rtsp://192.168.1.100:554/stream1"
        username = "wrong_user"
        password = "wrong_password"  # nosemgrep: hardcoded-password # pragma: allowlist secret

        # Mock authentication failure
        with patch("backend.services.rtsp_test_service.cv2.VideoCapture") as mock_cap:
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = False
            mock_cap.return_value = mock_instance

            result = await service.test_connection(
                rtsp_url=url, username=username, password=password
            )

            assert result.success is False
            assert result.error_message is not None
            assert (
                "authentication" in result.error_message.lower()
                or "credentials" in result.error_message.lower()
            )

    @pytest.mark.asyncio
    async def test_invalid_url_format(self, service: RTSPTestService) -> None:
        """Test invalid RTSP URL format handling.

        Invalid URL criteria:
        - Returns success=False
        - Error message indicates URL format issue
        - Validates before attempting connection
        """
        invalid_urls = [
            "http://192.168.1.100:80/stream",  # Wrong protocol
            "192.168.1.100:554/stream",  # Missing protocol
            "rtsp://",  # Missing host
            "rtsp://invalid url with spaces",  # Invalid characters
        ]

        for url in invalid_urls:
            result = await service.test_connection(rtsp_url=url)

            assert result.success is False
            assert result.error_message is not None
            assert "url" in result.error_message.lower() or "format" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_capability_detection(self, service: RTSPTestService) -> None:
        """Test detection of camera capabilities.

        Capability criteria:
        - Detects video support
        - Detects audio support (if available)
        - Detects PTZ support (if available)
        - Detects resolution
        - Detects codec
        - Detects frame rate
        """
        url = "rtsp://192.168.1.100:554/stream1"

        # Mock full-featured camera
        with patch("backend.services.rtsp_test_service.cv2.VideoCapture") as mock_cap:
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = True
            mock_instance.get.side_effect = lambda prop: {
                3: 3840,  # 4K width
                4: 2160,  # 4K height
                5: 30.0,  # 30 fps
            }.get(prop, 0)
            mock_cap.return_value = mock_instance

            result = await service.test_connection(rtsp_url=url)

            assert result.success is True
            assert result.capabilities is not None
            assert result.capabilities.video is True
            assert result.capabilities.resolution == "3840x2160"
            assert result.capabilities.fps == 30

    @pytest.mark.asyncio
    async def test_connection_with_port(self, service: RTSPTestService) -> None:
        """Test connection to RTSP URL with custom port."""
        url = "rtsp://192.168.1.100:8554/stream1"

        with patch("backend.services.rtsp_test_service.cv2.VideoCapture") as mock_cap:
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = True
            mock_instance.get.return_value = 1920  # Some default value
            mock_cap.return_value = mock_instance

            result = await service.test_connection(rtsp_url=url)

            assert result.success is True

    @pytest.mark.asyncio
    async def test_connection_with_path(self, service: RTSPTestService) -> None:
        """Test connection to RTSP URL with complex path."""
        url = "rtsp://192.168.1.100:554/Streaming/Channels/101"

        with patch("backend.services.rtsp_test_service.cv2.VideoCapture") as mock_cap:
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = True
            mock_instance.get.return_value = 1920
            mock_cap.return_value = mock_instance

            result = await service.test_connection(rtsp_url=url)

            assert result.success is True

    @pytest.mark.asyncio
    async def test_rtsps_secure_connection(self, service: RTSPTestService) -> None:
        """Test secure RTSP (rtsps://) connection."""
        url = "rtsps://192.168.1.100:322/stream1"

        with patch("backend.services.rtsp_test_service.cv2.VideoCapture") as mock_cap:
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = True
            mock_instance.get.return_value = 1920
            mock_cap.return_value = mock_instance

            result = await service.test_connection(rtsp_url=url)

            assert result.success is True

    @pytest.mark.asyncio
    async def test_network_unreachable(self, service: RTSPTestService) -> None:
        """Test handling of network unreachable errors."""
        url = "rtsp://192.168.99.99:554/stream1"

        with patch("backend.services.rtsp_test_service.cv2.VideoCapture") as mock_cap:
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = False
            mock_cap.return_value = mock_instance

            result = await service.test_connection(rtsp_url=url)

            assert result.success is False
            assert result.error_message is not None
            assert (
                "unreachable" in result.error_message.lower()
                or "connect" in result.error_message.lower()
            )

    @pytest.mark.asyncio
    async def test_stream_not_found(self, service: RTSPTestService) -> None:
        """Test handling of stream not found errors (404-equivalent)."""
        url = "rtsp://192.168.1.100:554/nonexistent_stream"

        with patch("backend.services.rtsp_test_service.cv2.VideoCapture") as mock_cap:
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = False
            mock_cap.return_value = mock_instance

            result = await service.test_connection(rtsp_url=url)

            assert result.success is False
            assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_latency_measurement(self, service: RTSPTestService) -> None:
        """Test that latency is measured and reasonable.

        Latency criteria:
        - Latency is positive
        - Latency is reasonable (< 5000ms for success)
        """
        url = "rtsp://192.168.1.100:554/stream1"

        with patch("backend.services.rtsp_test_service.cv2.VideoCapture") as mock_cap:
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = True
            mock_instance.get.return_value = 1920
            mock_cap.return_value = mock_instance

            result = await service.test_connection(rtsp_url=url)

            assert result.success is True
            assert result.latency_ms is not None
            assert 0 < result.latency_ms < 5000

    @pytest.mark.asyncio
    async def test_cleanup_on_error(self, service: RTSPTestService) -> None:
        """Test that resources are cleaned up even when errors occur."""
        url = "rtsp://192.168.1.100:554/stream1"

        with patch("backend.services.rtsp_test_service.cv2.VideoCapture") as mock_cap:
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = True
            mock_instance.read.side_effect = Exception("Camera error")
            mock_cap.return_value = mock_instance

            result = await service.test_connection(rtsp_url=url)

            # Should call release even on error
            mock_instance.release.assert_called()

    @pytest.mark.asyncio
    async def test_credentials_in_url(self, service: RTSPTestService) -> None:
        """Test handling of credentials embedded in URL.

        Should support: rtsp://user:pass@host:port/path  # pragma: allowlist secret
        """
        url = "rtsp://admin:password123@192.168.1.100:554/stream1"  # pragma: allowlist secret

        with patch("backend.services.rtsp_test_service.cv2.VideoCapture") as mock_cap:
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = True
            mock_instance.get.return_value = 1920
            mock_cap.return_value = mock_instance

            result = await service.test_connection(rtsp_url=url)

            assert result.success is True


class TestRTSPCapabilities:
    """Test suite for RTSPCapabilities dataclass."""

    def test_capabilities_creation(self) -> None:
        """Test creating RTSPCapabilities with all fields."""
        caps = RTSPCapabilities(
            video=True,
            audio=False,
            ptz=False,
            resolution="1920x1080",
            codec="H.264",
            fps=25,
        )

        assert caps.video is True
        assert caps.audio is False
        assert caps.ptz is False
        assert caps.resolution == "1920x1080"
        assert caps.codec == "H.264"
        assert caps.fps == 25

    def test_capabilities_defaults(self) -> None:
        """Test that optional fields have sensible defaults."""
        caps = RTSPCapabilities(video=True)

        assert caps.video is True
        assert caps.audio is False
        assert caps.ptz is False


class TestRTSPTestResult:
    """Test suite for RTSPTestResult dataclass."""

    def test_success_result(self) -> None:
        """Test creating a successful test result."""
        caps = RTSPCapabilities(video=True, resolution="1920x1080", codec="H.264", fps=25)
        result = RTSPTestResult(success=True, latency_ms=150, capabilities=caps)

        assert result.success is True
        assert result.latency_ms == 150
        assert result.capabilities is not None
        assert result.error_message is None

    def test_failure_result(self) -> None:
        """Test creating a failed test result."""
        result = RTSPTestResult(
            success=False, error_message="Connection timeout", latency_ms=None, capabilities=None
        )

        assert result.success is False
        assert result.error_message == "Connection timeout"
        assert result.latency_ms is None
        assert result.capabilities is None
