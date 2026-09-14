"""Unit tests for CLIP client AI Gateway routing.

Tests cover:
- AI Gateway routing: when use_ai_gateway=True, base URL routes through gateway
- Fallback to individual service URL when use_ai_gateway=False
- Explicit base_url parameter takes priority over gateway
- Trailing slash handling on gateway URL
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.services.clip_client import CLIPClient


@pytest.fixture
def _base_mock_settings() -> MagicMock:
    """Create base mock settings with common fields."""
    settings = MagicMock()
    settings.clip_url = "http://ai-clip:8093"
    settings.ai_connect_timeout = 10.0
    settings.ai_health_timeout = 5.0
    settings.clip_read_timeout = 15.0
    settings.clip_cb_failure_threshold = 5
    settings.clip_cb_recovery_timeout = 60.0
    settings.clip_cb_half_open_max_calls = 3
    return settings


class TestCLIPClientGatewayRouting:
    """Tests for AI Gateway routing logic in CLIPClient.__init__."""

    def test_gateway_enabled_routes_through_gateway(self, _base_mock_settings: MagicMock) -> None:
        """When use_ai_gateway=True and ai_gateway_url is set, base URL routes through gateway."""
        _base_mock_settings.use_ai_gateway = True
        _base_mock_settings.ai_gateway_url = "http://ai-gateway:8090"

        with patch("backend.services.clip_client.get_settings", return_value=_base_mock_settings):
            client = CLIPClient()

        assert client._base_url == "http://ai-gateway:8090/clip"

    def test_gateway_enabled_strips_trailing_slash(self, _base_mock_settings: MagicMock) -> None:
        """Gateway URL trailing slash is stripped before appending service prefix."""
        _base_mock_settings.use_ai_gateway = True
        _base_mock_settings.ai_gateway_url = "http://ai-gateway:8090/"

        with patch("backend.services.clip_client.get_settings", return_value=_base_mock_settings):
            client = CLIPClient()

        assert client._base_url == "http://ai-gateway:8090/clip"

    def test_gateway_disabled_uses_individual_url(self, _base_mock_settings: MagicMock) -> None:
        """When use_ai_gateway=False, client uses the individual clip_url from settings."""
        _base_mock_settings.use_ai_gateway = False
        _base_mock_settings.ai_gateway_url = "http://ai-gateway:8090"

        with patch("backend.services.clip_client.get_settings", return_value=_base_mock_settings):
            client = CLIPClient()

        assert client._base_url == "http://ai-clip:8093"

    def test_gateway_url_none_uses_individual_url(self, _base_mock_settings: MagicMock) -> None:
        """When ai_gateway_url is None, client falls back to individual service URL."""
        _base_mock_settings.use_ai_gateway = True
        _base_mock_settings.ai_gateway_url = None

        with patch("backend.services.clip_client.get_settings", return_value=_base_mock_settings):
            client = CLIPClient()

        assert client._base_url == "http://ai-clip:8093"

    def test_explicit_base_url_overrides_gateway(self, _base_mock_settings: MagicMock) -> None:
        """When base_url is explicitly provided, it takes priority over gateway."""
        _base_mock_settings.use_ai_gateway = True
        _base_mock_settings.ai_gateway_url = "http://ai-gateway:8090"

        with patch("backend.services.clip_client.get_settings", return_value=_base_mock_settings):
            client = CLIPClient(base_url="http://custom-clip:9999/")

        assert client._base_url == "http://custom-clip:9999"

    def test_explicit_base_url_overrides_individual_url(
        self, _base_mock_settings: MagicMock
    ) -> None:
        """When base_url is explicitly provided, it takes priority over settings URL."""
        _base_mock_settings.use_ai_gateway = False
        _base_mock_settings.ai_gateway_url = None

        with patch("backend.services.clip_client.get_settings", return_value=_base_mock_settings):
            client = CLIPClient(base_url="http://custom-clip:9999")

        assert client._base_url == "http://custom-clip:9999"

    def test_no_gateway_attributes_falls_back(self, _base_mock_settings: MagicMock) -> None:
        """When settings lack gateway attributes, client falls back to clip_url."""
        # Remove gateway attributes so getattr returns defaults
        del _base_mock_settings.use_ai_gateway
        del _base_mock_settings.ai_gateway_url

        with patch("backend.services.clip_client.get_settings", return_value=_base_mock_settings):
            client = CLIPClient()

        assert client._base_url == "http://ai-clip:8093"

    def test_gateway_url_with_path_prefix(self, _base_mock_settings: MagicMock) -> None:
        """Gateway URL with existing path prefix gets /clip appended."""
        _base_mock_settings.use_ai_gateway = True
        _base_mock_settings.ai_gateway_url = "http://ai-gateway:8090/v1"

        with patch("backend.services.clip_client.get_settings", return_value=_base_mock_settings):
            client = CLIPClient()

        assert client._base_url == "http://ai-gateway:8090/v1/clip"

    def test_individual_url_trailing_slash_stripped(self, _base_mock_settings: MagicMock) -> None:
        """Individual service URL trailing slash is stripped."""
        _base_mock_settings.use_ai_gateway = False
        _base_mock_settings.ai_gateway_url = None
        _base_mock_settings.clip_url = "http://ai-clip:8093/"

        with patch("backend.services.clip_client.get_settings", return_value=_base_mock_settings):
            client = CLIPClient()

        assert client._base_url == "http://ai-clip:8093"
