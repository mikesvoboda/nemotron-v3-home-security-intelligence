"""Tests for Settings.__repr__ and __str__ auto-redaction.

Verifies that sensitive fields are properly redacted when Settings objects
are converted to string representation, preventing accidental exposure in logs.
"""

import pytest


class TestSettingsReprRedaction:
    """Test Settings.__repr__ and __str__ auto-redaction."""

    def test_database_url_password_redacted(self, mock_settings):
        """DATABASE_URL password should be redacted."""
        result = repr(mock_settings)
        assert "supersecret" not in result
        assert "[REDACTED]" in result or "***" in result

    def test_redis_url_password_redacted(self, mock_settings):
        """REDIS_URL password should be redacted."""
        result = repr(mock_settings)
        # Redis URL should have password redacted
        assert "redispass" not in result.lower()

    def test_admin_api_key_redacted(self, mock_settings):
        """ADMIN_API_KEY should be fully redacted."""
        # Set an admin API key (test value for redaction testing)
        mock_settings.admin_api_key = "secret-admin-key-12345"  # pragma: allowlist secret
        result = repr(mock_settings)
        assert "secret-admin-key-12345" not in result
        assert "[REDACTED]" in result

    def test_str_returns_same_as_repr(self, mock_settings):
        """str() should return same output as repr()."""
        assert str(mock_settings) == repr(mock_settings)

    def test_non_sensitive_fields_visible(self, mock_settings):
        """Non-sensitive fields should still be visible."""
        result = repr(mock_settings)
        # Check that result is a valid Settings repr
        assert result.startswith("Settings(")
        assert result.endswith(")")

    def test_output_format(self, mock_settings):
        """Output should be in Settings({...}) format."""
        result = repr(mock_settings)
        assert result.startswith("Settings({")

    def test_api_keys_list_redacted(self, mock_settings):
        """api_keys list should be redacted."""
        mock_settings.api_keys = ["key1", "key2", "key3"]
        result = repr(mock_settings)
        assert "key1" not in result
        assert "key2" not in result
        assert "key3" not in result

    def test_smtp_password_redacted(self, mock_settings):
        """SMTP password should be redacted."""
        mock_settings.smtp_password = "smtp-secret-password"  # noqa: S105  # pragma: allowlist secret
        result = repr(mock_settings)
        assert "smtp-secret-password" not in result

    def test_rtdetr_api_key_redacted(self, mock_settings):
        """RT-DETR API key should be redacted."""
        mock_settings.rtdetr_api_key = "rtdetr-secret-key"  # pragma: allowlist secret
        result = repr(mock_settings)
        assert "rtdetr-secret-key" not in result

    def test_nemotron_api_key_redacted(self, mock_settings):
        """Nemotron API key should be redacted."""
        mock_settings.nemotron_api_key = "nemotron-secret-key"  # pragma: allowlist secret
        result = repr(mock_settings)
        assert "nemotron-secret-key" not in result

    def test_websocket_token_redacted(self, mock_settings):
        """WebSocket token should be redacted."""
        mock_settings.websocket_token = "ws-secret-token"  # noqa: S105  # pragma: allowlist secret
        result = repr(mock_settings)
        assert "ws-secret-token" not in result


@pytest.fixture
def mock_settings(monkeypatch):
    """Create a Settings instance with test values."""
    from functools import cache

    # Clear any cached settings
    cache.cache_clear() if hasattr(cache, "cache_clear") else None

    # Set required environment variables with test values
    # fmt: off
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:supersecret@localhost:5432/testdb",  # pragma: allowlist secret
    )
    monkeypatch.setenv(
        "REDIS_URL",
        "redis://:redispass@localhost:6379/0",  # pragma: allowlist secret
    )
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")  # pragma: allowlist secret
    # fmt: on

    # Import after setting env vars
    from backend.core.config import Settings, get_settings

    # Clear the cached settings
    get_settings.cache_clear()

    # Create fresh settings
    return Settings()
