"""Unit tests for nested settings with env_nested_delimiter (NEM-3778).

This module tests Pydantic Settings nested configuration via environment variables
using the env_nested_delimiter feature. This allows complex nested configuration
like REDIS__POOL__SIZE=50 to map to settings.redis.pool.size.

Tests cover:
- Nested model configuration via environment variables
- Double-underscore delimiter parsing
- Default value handling for nested settings
- Validation of nested settings
- Compatibility with existing flat settings
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.core.config_nested import (
    AIServiceSettings,
    DatabaseSettings,
    NestedSettings,
    NotificationSettings,
    RedisPoolSettings,
    RedisSettings,
    SMTPSettings,
    WebhookSettings,
    get_nested_settings,
)


@pytest.fixture
def clean_nested_env(monkeypatch):
    """Clean environment variables for nested settings tests.

    Clears nested settings cache and removes relevant environment variables.
    """
    # Clear all nested config-related environment variables
    env_vars = [
        # Database nested settings
        "DATABASE__URL",
        "DATABASE__POOL_SIZE",
        "DATABASE__POOL_OVERFLOW",
        "DATABASE__POOL_TIMEOUT",
        "DATABASE__POOL_RECYCLE",
        "DATABASE__ECHO",
        # Redis nested settings
        "REDIS__URL",
        "REDIS__PASSWORD",
        "REDIS__POOL__SIZE",
        "REDIS__POOL__TIMEOUT",
        "REDIS__POOL__RETRY_ON_TIMEOUT",
        "REDIS__SSL__ENABLED",
        "REDIS__SSL__CERT_PATH",
        # AI service nested settings
        "AI__DETECTOR__URL",
        "AI__DETECTOR__TIMEOUT",
        "AI__DETECTOR__RETRY_COUNT",
        "AI__LLM__URL",
        "AI__LLM__TIMEOUT",
        "AI__LLM__MAX_TOKENS",
        # Notification nested settings
        "NOTIFICATION__SMTP__HOST",
        "NOTIFICATION__SMTP__PORT",
        "NOTIFICATION__SMTP__USERNAME",
        "NOTIFICATION__WEBHOOK__URL",
        "NOTIFICATION__WEBHOOK__TIMEOUT",
    ]

    for var in env_vars:
        monkeypatch.delenv(var, raising=False)

    # Clear the lru_cache on get_nested_settings
    get_nested_settings.cache_clear()

    yield monkeypatch


class TestRedisPoolSettings:
    """Tests for Redis pool nested settings."""

    def test_default_pool_settings(self, clean_nested_env) -> None:
        """Test default Redis pool settings."""
        pool = RedisPoolSettings()
        assert pool.size == 50
        assert pool.timeout == 30.0
        assert pool.retry_on_timeout is True
        assert pool.max_connections == 100

    def test_pool_settings_from_env(self, clean_nested_env) -> None:
        """Test Redis pool settings from environment variables."""
        clean_nested_env.setenv("REDIS__POOL__SIZE", "100")
        clean_nested_env.setenv("REDIS__POOL__TIMEOUT", "60.0")
        clean_nested_env.setenv("REDIS__POOL__RETRY_ON_TIMEOUT", "false")

        # Create fresh settings to pick up env vars
        pool = RedisPoolSettings()
        assert pool.size == 100
        assert pool.timeout == 60.0
        assert pool.retry_on_timeout is False

    def test_pool_settings_validation(self, clean_nested_env) -> None:
        """Test Redis pool settings validation."""
        # Size must be >= 1
        with pytest.raises(ValidationError):
            RedisPoolSettings(size=0)

        # Timeout must be positive
        with pytest.raises(ValidationError):
            RedisPoolSettings(timeout=-1.0)


class TestRedisSettings:
    """Tests for Redis nested settings."""

    def test_default_redis_settings(self, clean_nested_env) -> None:
        """Test default Redis settings with nested pool."""
        redis = RedisSettings()
        assert redis.url == "redis://localhost:6379/0"
        assert redis.password is None
        assert redis.pool.size == 50  # Nested access

    def test_redis_settings_from_env(self, clean_nested_env) -> None:
        """Test Redis settings from nested environment variables."""
        clean_nested_env.setenv("REDIS__URL", "redis://redis-server:6379/1")
        clean_nested_env.setenv("REDIS__POOL__SIZE", "75")

        redis = RedisSettings()
        assert redis.url == "redis://redis-server:6379/1"
        assert redis.pool.size == 75

    def test_redis_ssl_settings(self, clean_nested_env) -> None:
        """Test Redis SSL nested settings."""
        clean_nested_env.setenv("REDIS__SSL__ENABLED", "true")
        clean_nested_env.setenv("REDIS__SSL__CERT_PATH", "/etc/ssl/redis.crt")

        redis = RedisSettings()
        assert redis.ssl.enabled is True
        assert redis.ssl.cert_path == "/etc/ssl/redis.crt"


class TestDatabaseSettings:
    """Tests for Database nested settings."""

    def test_default_database_settings(self, clean_nested_env) -> None:
        """Test default database settings."""
        db = DatabaseSettings()
        assert db.url == ""  # Required, but can be empty for tests
        assert db.pool_size == 20
        assert db.pool_overflow == 30
        assert db.pool_timeout == 30
        assert db.echo is False

    def test_database_settings_from_env(self, clean_nested_env) -> None:
        """Test database settings from environment variables."""
        clean_nested_env.setenv(
            "DATABASE__URL",
            "postgresql+asyncpg://user:pass@localhost:5432/db",  # pragma: allowlist secret
        )
        clean_nested_env.setenv("DATABASE__POOL_SIZE", "50")
        clean_nested_env.setenv("DATABASE__ECHO", "true")

        db = DatabaseSettings()
        assert "postgresql" in db.url
        assert db.pool_size == 50
        assert db.echo is True

    def test_database_pool_validation(self, clean_nested_env) -> None:
        """Test database pool size validation."""
        # Pool size must be >= 5
        with pytest.raises(ValidationError):
            DatabaseSettings(url="test", pool_size=2)


class TestAIServiceSettings:
    """Tests for AI service nested settings."""

    def test_default_ai_settings(self, clean_nested_env) -> None:
        """Test default AI service settings."""
        ai = AIServiceSettings()
        assert ai.detector.url == "http://localhost:8090"
        assert ai.detector.timeout == 30.0
        assert ai.llm.url == "http://localhost:8091"
        assert ai.llm.max_tokens == 4096

    def test_ai_settings_from_env(self, clean_nested_env) -> None:
        """Test AI settings from nested environment variables."""
        clean_nested_env.setenv("AI__DETECTOR__URL", "http://detector:8090")
        clean_nested_env.setenv("AI__DETECTOR__TIMEOUT", "60.0")
        clean_nested_env.setenv("AI__LLM__URL", "http://llm:8091")
        clean_nested_env.setenv("AI__LLM__MAX_TOKENS", "8192")

        ai = AIServiceSettings()
        assert ai.detector.url == "http://detector:8090"
        assert ai.detector.timeout == 60.0
        assert ai.llm.url == "http://llm:8091"
        assert ai.llm.max_tokens == 8192

    def test_ai_retry_settings(self, clean_nested_env) -> None:
        """Test AI service retry configuration."""
        clean_nested_env.setenv("AI__DETECTOR__RETRY_COUNT", "5")
        clean_nested_env.setenv("AI__DETECTOR__RETRY_DELAY", "2.0")

        ai = AIServiceSettings()
        assert ai.detector.retry_count == 5
        assert ai.detector.retry_delay == 2.0


class TestNotificationSettings:
    """Tests for notification nested settings."""

    def test_default_notification_settings(self, clean_nested_env) -> None:
        """Test default notification settings."""
        notif = NotificationSettings()
        assert notif.smtp is None  # Optional
        assert notif.webhook is None  # Optional
        assert notif.enabled is True

    def test_smtp_settings_from_env(self, clean_nested_env) -> None:
        """Test SMTP settings from nested environment variables."""
        clean_nested_env.setenv("NOTIFICATION__SMTP__HOST", "smtp.example.com")
        clean_nested_env.setenv("NOTIFICATION__SMTP__PORT", "587")
        clean_nested_env.setenv("NOTIFICATION__SMTP__USERNAME", "user@example.com")

        # SMTPSettings loads directly from env
        smtp = SMTPSettings()
        assert smtp.host == "smtp.example.com"
        assert smtp.port == 587
        assert smtp.username == "user@example.com"

    def test_webhook_settings_from_env(self, clean_nested_env) -> None:
        """Test webhook settings from nested environment variables."""
        clean_nested_env.setenv("NOTIFICATION__WEBHOOK__URL", "https://hooks.example.com/notify")
        clean_nested_env.setenv("NOTIFICATION__WEBHOOK__TIMEOUT", "15.0")

        # WebhookSettings loads directly from env
        webhook = WebhookSettings()
        assert webhook.url == "https://hooks.example.com/notify"
        assert webhook.timeout == 15.0


class TestNestedSettings:
    """Tests for main NestedSettings class with all nested groups."""

    def test_default_nested_settings(self, clean_nested_env) -> None:
        """Test default nested settings structure."""
        settings = NestedSettings()

        # Check all nested groups exist
        assert settings.database is not None
        assert settings.redis is not None
        assert settings.ai is not None
        assert settings.notification is not None

    def test_nested_settings_from_env(self, clean_nested_env) -> None:
        """Test nested settings from multiple environment variables."""
        # Set various nested settings
        clean_nested_env.setenv("DATABASE__POOL_SIZE", "30")
        clean_nested_env.setenv("REDIS__POOL__SIZE", "80")
        clean_nested_env.setenv("AI__DETECTOR__TIMEOUT", "45.0")
        clean_nested_env.setenv("NOTIFICATION__ENABLED", "false")

        settings = NestedSettings()

        assert settings.database.pool_size == 30
        assert settings.redis.pool.size == 80
        assert settings.ai.detector.timeout == 45.0
        assert settings.notification.enabled is False

    def test_get_nested_settings_cached(self, clean_nested_env) -> None:
        """Test that get_nested_settings returns cached instance."""
        settings1 = get_nested_settings()
        settings2 = get_nested_settings()

        assert settings1 is settings2

    def test_nested_settings_serialization(self, clean_nested_env) -> None:
        """Test that nested settings can be serialized to dict."""
        settings = NestedSettings()
        data = settings.model_dump()

        assert "database" in data
        assert "redis" in data
        assert "pool" in data["redis"]
        assert "size" in data["redis"]["pool"]


class TestNestedDelimiterParsing:
    """Tests for environment variable delimiter parsing."""

    def test_double_underscore_delimiter(self, clean_nested_env) -> None:
        """Test that double underscore is used as nested delimiter."""
        # Single underscore in key should be preserved
        clean_nested_env.setenv("REDIS__POOL__MAX_CONNECTIONS", "200")

        pool = RedisPoolSettings()
        assert pool.max_connections == 200

    def test_mixed_flat_and_nested(self, clean_nested_env) -> None:
        """Test that flat settings work alongside nested."""
        clean_nested_env.setenv("DATABASE__URL", "postgresql://test")  # pragma: allowlist secret
        clean_nested_env.setenv("DATABASE__POOL_SIZE", "40")  # Flat underscore in name

        db = DatabaseSettings()
        assert "test" in db.url
        assert db.pool_size == 40

    def test_deeply_nested_settings(self, clean_nested_env) -> None:
        """Test three-level deep nested settings."""
        clean_nested_env.setenv("REDIS__SSL__CERT_PATH", "/path/to/cert.pem")
        clean_nested_env.setenv("REDIS__SSL__KEY_PATH", "/path/to/key.pem")
        clean_nested_env.setenv("REDIS__SSL__VERIFY_MODE", "required")

        redis = RedisSettings()
        assert redis.ssl.cert_path == "/path/to/cert.pem"
        assert redis.ssl.key_path == "/path/to/key.pem"
        assert redis.ssl.verify_mode == "required"


class TestNestedSettingsDocumentation:
    """Tests for nested settings documentation generation."""

    def test_nested_model_has_description(self, clean_nested_env) -> None:
        """Test that nested models have descriptions."""
        schema = RedisPoolSettings.model_json_schema()
        # Schema should have description
        assert "description" in schema or any(
            "description" in prop for prop in schema.get("properties", {}).values()
        )

    def test_nested_fields_have_descriptions(self, clean_nested_env) -> None:
        """Test that nested fields have descriptions."""
        schema = RedisSettings.model_json_schema()
        props = schema.get("properties", {})

        # URL field should have description
        if "url" in props:
            assert "description" in props["url"]
