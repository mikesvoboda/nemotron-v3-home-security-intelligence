"""Unit tests for Detector client AI Gateway routing.

Tests cover:
- AI Gateway routing: when use_ai_gateway=True, detector URL routes through gateway
- Fallback to individual service URL when use_ai_gateway=False
- Trailing slash handling on gateway URL

Note: DetectorClient does not accept a base_url parameter in __init__.
It reads from settings.yolo26_url or the gateway URL directly.
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.services.detector_client import DetectorClient


@pytest.fixture
def _base_mock_settings() -> MagicMock:
    """Create base mock settings with common fields for detector client."""
    settings = MagicMock()
    settings.yolo26_url = "http://ai-yolo26:8095"
    settings.yolo26_api_key = None
    settings.yolo26_read_timeout = 60.0
    settings.ai_connect_timeout = 10.0
    settings.ai_health_timeout = 5.0
    settings.detection_confidence_threshold = 0.25
    settings.detection_class_thresholds = {}
    settings.detector_max_retries = 3
    settings.ai_max_concurrent_inferences = 4
    settings.ai_warmup_enabled = False
    settings.ai_cold_start_threshold_seconds = 300.0
    return settings


class TestDetectorClientGatewayRouting:
    """Tests for AI Gateway routing logic in DetectorClient.__init__."""

    def test_gateway_enabled_routes_through_gateway(self, _base_mock_settings: MagicMock) -> None:
        """When use_ai_gateway=True and ai_gateway_url is set, URL routes through gateway."""
        _base_mock_settings.use_ai_gateway = True
        _base_mock_settings.ai_gateway_url = "http://ai-gateway:8090"

        with patch(
            "backend.services.detector_client.get_settings", return_value=_base_mock_settings
        ):
            client = DetectorClient()

        assert client._detector_url == "http://ai-gateway:8090/yolo26"

    def test_gateway_enabled_strips_trailing_slash(self, _base_mock_settings: MagicMock) -> None:
        """Gateway URL trailing slash is stripped before appending service prefix."""
        _base_mock_settings.use_ai_gateway = True
        _base_mock_settings.ai_gateway_url = "http://ai-gateway:8090/"

        with patch(
            "backend.services.detector_client.get_settings", return_value=_base_mock_settings
        ):
            client = DetectorClient()

        assert client._detector_url == "http://ai-gateway:8090/yolo26"

    def test_gateway_disabled_uses_individual_url(self, _base_mock_settings: MagicMock) -> None:
        """When use_ai_gateway=False, client uses the individual yolo26_url from settings."""
        _base_mock_settings.use_ai_gateway = False
        _base_mock_settings.ai_gateway_url = "http://ai-gateway:8090"

        with patch(
            "backend.services.detector_client.get_settings", return_value=_base_mock_settings
        ):
            client = DetectorClient()

        assert client._detector_url == "http://ai-yolo26:8095"

    def test_gateway_url_none_uses_individual_url(self, _base_mock_settings: MagicMock) -> None:
        """When ai_gateway_url is None, client falls back to individual service URL."""
        _base_mock_settings.use_ai_gateway = True
        _base_mock_settings.ai_gateway_url = None

        with patch(
            "backend.services.detector_client.get_settings", return_value=_base_mock_settings
        ):
            client = DetectorClient()

        assert client._detector_url == "http://ai-yolo26:8095"

    def test_no_gateway_attributes_falls_back(self, _base_mock_settings: MagicMock) -> None:
        """When settings lack gateway attributes, client falls back to yolo26_url."""
        del _base_mock_settings.use_ai_gateway
        del _base_mock_settings.ai_gateway_url

        with patch(
            "backend.services.detector_client.get_settings", return_value=_base_mock_settings
        ):
            client = DetectorClient()

        assert client._detector_url == "http://ai-yolo26:8095"

    def test_gateway_url_with_path_prefix(self, _base_mock_settings: MagicMock) -> None:
        """Gateway URL with existing path prefix gets /yolo26 appended."""
        _base_mock_settings.use_ai_gateway = True
        _base_mock_settings.ai_gateway_url = "http://ai-gateway:8090/v1"

        with patch(
            "backend.services.detector_client.get_settings", return_value=_base_mock_settings
        ):
            client = DetectorClient()

        assert client._detector_url == "http://ai-gateway:8090/v1/yolo26"

    def test_detector_type_is_yolo26(self, _base_mock_settings: MagicMock) -> None:
        """Detector type is always yolo26 regardless of gateway setting."""
        _base_mock_settings.use_ai_gateway = True
        _base_mock_settings.ai_gateway_url = "http://ai-gateway:8090"

        with patch(
            "backend.services.detector_client.get_settings", return_value=_base_mock_settings
        ):
            client = DetectorClient()

        assert client._detector_type == "yolo26"
