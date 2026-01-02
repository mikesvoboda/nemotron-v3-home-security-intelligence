"""Unit tests for application configuration.

Tests cover:
- grafana_url setting default value
- grafana_url setting custom value via environment variable
"""

import pytest

from backend.core.config import Settings, get_settings


class TestGrafanaUrlSetting:
    """Tests for grafana_url configuration setting."""

    def test_grafana_url_default_value(self) -> None:
        """Test that grafana_url has correct default value."""
        settings = Settings(database_url="postgresql+asyncpg://test:test@localhost:5432/test")
        assert settings.grafana_url == "http://localhost:3002"

    def test_grafana_url_custom_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that grafana_url can be customized via environment."""
        monkeypatch.setenv("GRAFANA_URL", "http://grafana.local:3000")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
        # Clear cache to pick up new env var
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.grafana_url == "http://grafana.local:3000"
        get_settings.cache_clear()
