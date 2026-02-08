"""Unit tests for AI Gateway configuration settings.

Tests cover:
- validate_ai_gateway_url with valid URLs, None, empty string, invalid URLs
- use_ai_gateway default is False
- ai_gateway_url default is None
"""

import pytest
from pydantic import ValidationError

from backend.core.config import Settings, get_settings


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Clean environment and settings cache for isolated config tests.

    Sets required environment variables to valid test values.
    """
    # Clear gateway-related env vars
    for var in [
        "AI_GATEWAY_URL",
        "USE_AI_GATEWAY",
        "DATABASE_URL",
        "REDIS_URL",
        "ENVIRONMENT",
        "FOSCAM_BASE_PATH",
    ]:
        monkeypatch.delenv(var, raising=False)

    # Set required env vars
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
    )
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("FOSCAM_BASE_PATH", "/export/foscam")

    # Clear cached settings
    get_settings.cache_clear()

    yield monkeypatch

    # Clear cache again to avoid leaking into other tests
    get_settings.cache_clear()


class TestValidateAiGatewayUrl:
    """Tests for the validate_ai_gateway_url field validator."""

    def test_valid_http_url(self, _clean_env: pytest.MonkeyPatch) -> None:
        """Valid HTTP URL is accepted and returned as string."""
        _clean_env.setenv("AI_GATEWAY_URL", "http://ai-gateway:8090")
        settings = Settings()
        assert settings.ai_gateway_url is not None
        assert "ai-gateway" in settings.ai_gateway_url
        assert "8090" in settings.ai_gateway_url

    def test_valid_https_url(self, _clean_env: pytest.MonkeyPatch) -> None:
        """Valid HTTPS URL is accepted."""
        _clean_env.setenv("AI_GATEWAY_URL", "https://ai-gateway.example.com:8090")
        settings = Settings()
        assert settings.ai_gateway_url is not None
        assert "https" in settings.ai_gateway_url

    def test_none_value(self, _clean_env: pytest.MonkeyPatch) -> None:
        """None value is accepted (gateway disabled)."""
        # AI_GATEWAY_URL not set, default is None
        settings = Settings()
        assert settings.ai_gateway_url is None

    def test_empty_string_returns_none(self, _clean_env: pytest.MonkeyPatch) -> None:
        """Empty string is converted to None (gateway disabled)."""
        _clean_env.setenv("AI_GATEWAY_URL", "")
        settings = Settings()
        assert settings.ai_gateway_url is None

    def test_invalid_url_raises_error(self, _clean_env: pytest.MonkeyPatch) -> None:
        """Invalid URL raises ValueError during validation."""
        _clean_env.setenv("AI_GATEWAY_URL", "not-a-valid-url")
        with pytest.raises(ValidationError, match="Invalid AI Gateway URL"):
            Settings()

    def test_ftp_url_raises_error(self, _clean_env: pytest.MonkeyPatch) -> None:
        """Non-HTTP protocol (ftp) raises ValueError."""
        _clean_env.setenv("AI_GATEWAY_URL", "ftp://ai-gateway:8090")
        with pytest.raises(ValidationError, match="Invalid AI Gateway URL"):
            Settings()

    def test_trailing_slash_stripped(self, _clean_env: pytest.MonkeyPatch) -> None:
        """Trailing slash is stripped from validated URL."""
        _clean_env.setenv("AI_GATEWAY_URL", "http://ai-gateway:8090/")
        settings = Settings()
        assert settings.ai_gateway_url is not None
        assert not settings.ai_gateway_url.endswith("/")

    def test_url_with_path(self, _clean_env: pytest.MonkeyPatch) -> None:
        """URL with path component is accepted."""
        _clean_env.setenv("AI_GATEWAY_URL", "http://ai-gateway:8090/v1")
        settings = Settings()
        assert settings.ai_gateway_url is not None
        assert "v1" in settings.ai_gateway_url


class TestUseAiGateway:
    """Tests for the use_ai_gateway boolean setting."""

    def test_default_is_false(self, _clean_env: pytest.MonkeyPatch) -> None:
        """use_ai_gateway defaults to False."""
        settings = Settings()
        assert settings.use_ai_gateway is False

    def test_enabled_via_env(self, _clean_env: pytest.MonkeyPatch) -> None:
        """use_ai_gateway can be enabled via environment variable."""
        _clean_env.setenv("USE_AI_GATEWAY", "true")
        settings = Settings()
        assert settings.use_ai_gateway is True

    def test_disabled_via_env(self, _clean_env: pytest.MonkeyPatch) -> None:
        """use_ai_gateway can be explicitly disabled via environment variable."""
        _clean_env.setenv("USE_AI_GATEWAY", "false")
        settings = Settings()
        assert settings.use_ai_gateway is False


class TestAiGatewayUrlDefault:
    """Tests for the ai_gateway_url default value."""

    def test_default_is_none(self, _clean_env: pytest.MonkeyPatch) -> None:
        """ai_gateway_url defaults to None."""
        settings = Settings()
        assert settings.ai_gateway_url is None
