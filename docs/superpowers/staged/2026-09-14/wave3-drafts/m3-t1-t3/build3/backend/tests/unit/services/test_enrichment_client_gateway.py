"""Unit tests for Enrichment client AI Gateway routing.

Tests cover:
- AI Gateway routing for heavy service URL (enrichment)
- AI Gateway routing for light service URL (enrich-lt)
- Fallback to individual service URLs when use_ai_gateway=False
- Explicit base_url and light_base_url parameters take priority over gateway
- Trailing slash handling on gateway URL
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.services.enrichment_client import EnrichmentClient


@pytest.fixture
def _base_mock_settings() -> MagicMock:
    """Create base mock settings with common fields for enrichment client."""
    settings = MagicMock()
    settings.enrichment_url = "http://ai-enrichment:8094"
    settings.enrichment_light_url = "http://ai-enrichment-light:8096"
    settings.ai_connect_timeout = 10.0
    settings.ai_health_timeout = 5.0
    settings.enrichment_read_timeout = 60.0
    settings.enrichment_cb_failure_threshold = 10
    settings.enrichment_cb_recovery_timeout = 60.0
    settings.enrichment_cb_half_open_max_calls = 3
    settings.enrichment_max_retries = 3
    return settings


class TestEnrichmentClientGatewayRouting:
    """Tests for AI Gateway routing logic in EnrichmentClient.__init__."""

    def test_gateway_enabled_routes_heavy_through_gateway(
        self, _base_mock_settings: MagicMock
    ) -> None:
        """When use_ai_gateway=True, heavy service URL routes through gateway /enrichment."""
        _base_mock_settings.use_ai_gateway = True
        _base_mock_settings.ai_gateway_url = "http://ai-gateway:8090"

        with patch(
            "backend.services.enrichment_client.get_settings", return_value=_base_mock_settings
        ):
            client = EnrichmentClient()

        assert client._base_url == "http://ai-gateway:8090/enrichment"

    def test_gateway_enabled_routes_light_through_gateway(
        self, _base_mock_settings: MagicMock
    ) -> None:
        """When use_ai_gateway=True, light service URL routes through gateway /enrich-lt."""
        _base_mock_settings.use_ai_gateway = True
        _base_mock_settings.ai_gateway_url = "http://ai-gateway:8090"

        with patch(
            "backend.services.enrichment_client.get_settings", return_value=_base_mock_settings
        ):
            client = EnrichmentClient()

        assert client._light_base_url == "http://ai-gateway:8090/enrich-lt"

    def test_gateway_enabled_strips_trailing_slash(self, _base_mock_settings: MagicMock) -> None:
        """Gateway URL trailing slash is stripped before appending service prefix."""
        _base_mock_settings.use_ai_gateway = True
        _base_mock_settings.ai_gateway_url = "http://ai-gateway:8090/"

        with patch(
            "backend.services.enrichment_client.get_settings", return_value=_base_mock_settings
        ):
            client = EnrichmentClient()

        assert client._base_url == "http://ai-gateway:8090/enrichment"
        assert client._light_base_url == "http://ai-gateway:8090/enrich-lt"

    def test_gateway_disabled_uses_individual_urls(self, _base_mock_settings: MagicMock) -> None:
        """When use_ai_gateway=False, client uses individual service URLs from settings."""
        _base_mock_settings.use_ai_gateway = False
        _base_mock_settings.ai_gateway_url = "http://ai-gateway:8090"

        with patch(
            "backend.services.enrichment_client.get_settings", return_value=_base_mock_settings
        ):
            client = EnrichmentClient()

        assert client._base_url == "http://ai-enrichment:8094"
        assert client._light_base_url == "http://ai-enrichment-light:8096"

    def test_gateway_url_none_uses_individual_urls(self, _base_mock_settings: MagicMock) -> None:
        """When ai_gateway_url is None, client falls back to individual service URLs."""
        _base_mock_settings.use_ai_gateway = True
        _base_mock_settings.ai_gateway_url = None

        with patch(
            "backend.services.enrichment_client.get_settings", return_value=_base_mock_settings
        ):
            client = EnrichmentClient()

        assert client._base_url == "http://ai-enrichment:8094"
        assert client._light_base_url == "http://ai-enrichment-light:8096"

    def test_explicit_base_url_overrides_gateway(self, _base_mock_settings: MagicMock) -> None:
        """When base_url is explicitly provided, it takes priority over gateway for heavy."""
        _base_mock_settings.use_ai_gateway = True
        _base_mock_settings.ai_gateway_url = "http://ai-gateway:8090"

        with patch(
            "backend.services.enrichment_client.get_settings", return_value=_base_mock_settings
        ):
            client = EnrichmentClient(base_url="http://custom-enrichment:9999/")

        assert client._base_url == "http://custom-enrichment:9999"
        # Light URL should still route through gateway since not explicitly provided
        assert client._light_base_url == "http://ai-gateway:8090/enrich-lt"

    def test_explicit_light_base_url_overrides_gateway(
        self, _base_mock_settings: MagicMock
    ) -> None:
        """When light_base_url is explicitly provided, it takes priority over gateway for light."""
        _base_mock_settings.use_ai_gateway = True
        _base_mock_settings.ai_gateway_url = "http://ai-gateway:8090"

        with patch(
            "backend.services.enrichment_client.get_settings", return_value=_base_mock_settings
        ):
            client = EnrichmentClient(light_base_url="http://custom-light:9998/")

        # Heavy URL should still route through gateway since not explicitly provided
        assert client._base_url == "http://ai-gateway:8090/enrichment"
        assert client._light_base_url == "http://custom-light:9998"

    def test_both_explicit_urls_override_gateway(self, _base_mock_settings: MagicMock) -> None:
        """When both base_url and light_base_url are provided, both override gateway."""
        _base_mock_settings.use_ai_gateway = True
        _base_mock_settings.ai_gateway_url = "http://ai-gateway:8090"

        with patch(
            "backend.services.enrichment_client.get_settings", return_value=_base_mock_settings
        ):
            client = EnrichmentClient(
                base_url="http://custom-heavy:9999",
                light_base_url="http://custom-light:9998",
            )

        assert client._base_url == "http://custom-heavy:9999"
        assert client._light_base_url == "http://custom-light:9998"

    def test_no_gateway_attributes_falls_back(self, _base_mock_settings: MagicMock) -> None:
        """When settings lack gateway attributes, client falls back to individual URLs."""
        del _base_mock_settings.use_ai_gateway
        del _base_mock_settings.ai_gateway_url

        with patch(
            "backend.services.enrichment_client.get_settings", return_value=_base_mock_settings
        ):
            client = EnrichmentClient()

        assert client._base_url == "http://ai-enrichment:8094"
        assert client._light_base_url == "http://ai-enrichment-light:8096"

    def test_gateway_url_with_path_prefix(self, _base_mock_settings: MagicMock) -> None:
        """Gateway URL with existing path prefix gets service prefixes appended."""
        _base_mock_settings.use_ai_gateway = True
        _base_mock_settings.ai_gateway_url = "http://ai-gateway:8090/v1"

        with patch(
            "backend.services.enrichment_client.get_settings", return_value=_base_mock_settings
        ):
            client = EnrichmentClient()

        assert client._base_url == "http://ai-gateway:8090/v1/enrichment"
        assert client._light_base_url == "http://ai-gateway:8090/v1/enrich-lt"

    def test_individual_urls_trailing_slashes_stripped(
        self, _base_mock_settings: MagicMock
    ) -> None:
        """Individual service URL trailing slashes are stripped."""
        _base_mock_settings.use_ai_gateway = False
        _base_mock_settings.ai_gateway_url = None
        _base_mock_settings.enrichment_url = "http://ai-enrichment:8094/"
        _base_mock_settings.enrichment_light_url = "http://ai-enrichment-light:8096/"

        with patch(
            "backend.services.enrichment_client.get_settings", return_value=_base_mock_settings
        ):
            client = EnrichmentClient()

        assert client._base_url == "http://ai-enrichment:8094"
        assert client._light_base_url == "http://ai-enrichment-light:8096"
