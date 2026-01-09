"""Integration tests for configuration validation on application startup.

These tests verify that the application properly validates configuration settings
and fails fast with clear error messages when misconfigured, rather than failing
later with cryptic errors.

Tests cover:
- Required environment variables (DATABASE_URL)
- Invalid values (wrong types, out of range)
- Default value application
- Configuration override in tests
- URL validation for services (Redis, AI services)
- Nested settings (OrchestratorSettings)
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from backend.core.config import Settings, get_settings

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def clean_env(monkeypatch) -> Generator[pytest.MonkeyPatch]:
    """Clean environment variables and settings cache for isolated testing.

    Sets DATABASE_URL to a valid test value since it's required.
    """
    # Store original values to restore later
    original_values = {}
    env_vars_to_manage = [
        "DATABASE_URL",
        "REDIS_URL",
        "RTDETR_URL",
        "NEMOTRON_URL",
        "FLORENCE_URL",
        "CLIP_URL",
        "ENRICHMENT_URL",
        "GRAFANA_URL",
        "DEBUG",
        "ADMIN_ENABLED",
        "TLS_MODE",
        "RATE_LIMIT_ENABLED",
        "BATCH_WINDOW_SECONDS",
        "BATCH_IDLE_TIMEOUT_SECONDS",
        "DETECTION_CONFIDENCE_THRESHOLD",
        "FILE_WATCHER_POLLING_INTERVAL",
        "DATABASE_POOL_SIZE",
        "DATABASE_POOL_OVERFLOW",
        "DATABASE_POOL_TIMEOUT",
        "DATABASE_POOL_RECYCLE",
        "QUEUE_MAX_SIZE",
        "QUEUE_OVERFLOW_POLICY",
        "AI_CONNECT_TIMEOUT",
        "AI_HEALTH_TIMEOUT",
        "RTDETR_READ_TIMEOUT",
        "NEMOTRON_READ_TIMEOUT",
        "ORCHESTRATOR_ENABLED",
        "ORCHESTRATOR_HEALTH_CHECK_INTERVAL",
        "HSI_RUNTIME_ENV_PATH",
    ]

    for var in env_vars_to_manage:
        original_values[var] = os.environ.get(var)
        monkeypatch.delenv(var, raising=False)

    # Set DATABASE_URL since it's required (no default)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
    )

    # Create a temporary runtime.env file to avoid reading from real files
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime_env_path = str(Path(tmpdir) / "runtime.env")
        monkeypatch.setenv("HSI_RUNTIME_ENV_PATH", runtime_env_path)

        # Clear the lru_cache on get_settings
        get_settings.cache_clear()

        yield monkeypatch

        # Restore original environment
        get_settings.cache_clear()


class TestRequiredConfigurationValidation:
    """Test that required configuration causes startup failure when missing."""

    def test_missing_database_url_raises_validation_error(self, clean_env):
        """Test that missing DATABASE_URL causes validation failure.

        DATABASE_URL is required with no default value. The application should
        fail fast with a clear error message when this is not set.
        """
        clean_env.delenv("DATABASE_URL", raising=False)
        get_settings.cache_clear()

        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None)

        # Verify error message is helpful
        error_str = str(exc_info.value)
        assert "DATABASE_URL" in error_str or "database_url" in error_str

    def test_empty_database_url_raises_validation_error(self, clean_env):
        """Test that empty DATABASE_URL causes validation failure.

        Even if the environment variable is set but empty, validation should fail.
        """
        clean_env.setenv("DATABASE_URL", "")
        get_settings.cache_clear()

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        error_str = str(exc_info.value)
        assert "DATABASE_URL" in error_str or "database_url" in error_str


class TestInvalidValueValidation:
    """Test that invalid configuration values are rejected."""

    def test_invalid_database_url_scheme_rejected(self, clean_env):
        """Test that non-PostgreSQL database URLs are rejected."""
        clean_env.setenv("DATABASE_URL", "sqlite+aiosqlite:///./data/test.db")
        get_settings.cache_clear()

        with pytest.raises(ValueError, match="Only PostgreSQL is supported"):
            Settings()

    def test_invalid_redis_url_scheme_rejected(self, clean_env):
        """Test that invalid Redis URL schemes are rejected."""
        clean_env.setenv("REDIS_URL", "http://localhost:6379/0")
        get_settings.cache_clear()

        with pytest.raises(ValueError, match="must start with 'redis://'"):
            Settings()

    def test_invalid_ai_service_url_rejected(self, clean_env):
        """Test that invalid AI service URLs are rejected."""
        clean_env.setenv("RTDETR_URL", "not-a-valid-url")
        get_settings.cache_clear()

        with pytest.raises(ValueError, match="Invalid AI service URL"):
            Settings()

    def test_invalid_protocol_ai_service_url_rejected(self, clean_env):
        """Test that non-HTTP protocols for AI service URLs are rejected."""
        clean_env.setenv("NEMOTRON_URL", "ftp://gpu-server:8091")
        get_settings.cache_clear()

        with pytest.raises(ValueError):
            Settings()

    def test_database_pool_size_below_minimum_rejected(self, clean_env):
        """Test that database pool size below minimum (5) is rejected."""
        clean_env.setenv("DATABASE_POOL_SIZE", "2")
        get_settings.cache_clear()

        with pytest.raises(ValidationError):
            Settings()

    def test_database_pool_size_above_maximum_rejected(self, clean_env):
        """Test that database pool size above maximum (100) is rejected."""
        clean_env.setenv("DATABASE_POOL_SIZE", "150")
        get_settings.cache_clear()

        with pytest.raises(ValidationError):
            Settings()

    def test_detection_confidence_threshold_out_of_range_rejected(self, clean_env):
        """Test that detection confidence outside 0.0-1.0 is rejected."""
        clean_env.setenv("DETECTION_CONFIDENCE_THRESHOLD", "1.5")
        get_settings.cache_clear()

        with pytest.raises(ValidationError):
            Settings()

    def test_negative_detection_confidence_threshold_rejected(self, clean_env):
        """Test that negative detection confidence is rejected."""
        clean_env.setenv("DETECTION_CONFIDENCE_THRESHOLD", "-0.1")
        get_settings.cache_clear()

        with pytest.raises(ValidationError):
            Settings()

    def test_file_watcher_polling_interval_below_minimum_rejected(self, clean_env):
        """Test that polling interval below 0.1 seconds is rejected."""
        clean_env.setenv("FILE_WATCHER_POLLING_INTERVAL", "0.05")
        get_settings.cache_clear()

        with pytest.raises(ValidationError):
            Settings()

    def test_file_watcher_polling_interval_above_maximum_rejected(self, clean_env):
        """Test that polling interval above 30.0 seconds is rejected."""
        clean_env.setenv("FILE_WATCHER_POLLING_INTERVAL", "31.0")
        get_settings.cache_clear()

        with pytest.raises(ValidationError):
            Settings()

    def test_invalid_tls_mode_rejected(self, clean_env):
        """Test that invalid TLS mode is rejected."""
        clean_env.setenv("TLS_MODE", "invalid_mode")
        get_settings.cache_clear()

        with pytest.raises(ValidationError, match="tls_mode must be one of"):
            Settings()

    def test_invalid_redis_ssl_cert_reqs_rejected(self, clean_env):
        """Test that invalid Redis SSL cert_reqs mode is rejected."""
        clean_env.setenv("REDIS_SSL_CERT_REQS", "invalid_mode")
        get_settings.cache_clear()

        with pytest.raises(ValueError, match="redis_ssl_cert_reqs must be one of"):
            Settings()

    def test_invalid_queue_max_size_below_minimum_rejected(self, clean_env):
        """Test that queue max size below minimum (100) is rejected."""
        clean_env.setenv("QUEUE_MAX_SIZE", "50")
        get_settings.cache_clear()

        with pytest.raises(ValidationError):
            Settings()

    def test_ai_timeout_below_minimum_rejected(self, clean_env):
        """Test that AI timeout below minimum is rejected."""
        clean_env.setenv("AI_CONNECT_TIMEOUT", "0.5")  # Minimum is 1.0
        get_settings.cache_clear()

        with pytest.raises(ValidationError):
            Settings()

    def test_invalid_integer_value_rejected(self, clean_env):
        """Test that non-integer values for integer fields are rejected."""
        clean_env.setenv("BATCH_WINDOW_SECONDS", "not_an_integer")
        get_settings.cache_clear()

        with pytest.raises(ValidationError):
            Settings()

    def test_invalid_float_value_rejected(self, clean_env):
        """Test that non-float values for float fields are rejected."""
        clean_env.setenv("AI_CONNECT_TIMEOUT", "not_a_float")
        get_settings.cache_clear()

        with pytest.raises(ValidationError):
            Settings()


class TestDefaultValueApplication:
    """Test that default values are correctly applied."""

    def test_redis_url_default_applied(self, clean_env):
        """Test that Redis URL defaults to localhost when not set."""
        clean_env.delenv("REDIS_URL", raising=False)
        get_settings.cache_clear()

        settings = Settings()
        assert settings.redis_url == "redis://localhost:6379/0"

    def test_ai_service_url_defaults_applied(self, clean_env):
        """Test that AI service URLs default to localhost."""
        clean_env.delenv("RTDETR_URL", raising=False)
        clean_env.delenv("NEMOTRON_URL", raising=False)
        get_settings.cache_clear()

        settings = Settings()
        assert settings.rtdetr_url == "http://localhost:8090"
        assert settings.nemotron_url == "http://localhost:8091"

    def test_debug_mode_defaults_to_false(self, clean_env):
        """Test that debug mode defaults to False for security."""
        clean_env.delenv("DEBUG", raising=False)
        get_settings.cache_clear()

        settings = Settings()
        assert settings.debug is False

    def test_admin_enabled_defaults_to_false(self, clean_env):
        """Test that admin endpoints are disabled by default."""
        clean_env.delenv("ADMIN_ENABLED", raising=False)
        get_settings.cache_clear()

        settings = Settings()
        assert settings.admin_enabled is False

    def test_tls_mode_defaults_to_disabled(self, clean_env):
        """Test that TLS mode defaults to disabled."""
        clean_env.delenv("TLS_MODE", raising=False)
        get_settings.cache_clear()

        settings = Settings()
        assert settings.tls_mode == "disabled"

    def test_rate_limiting_defaults_to_enabled(self, clean_env):
        """Test that rate limiting is enabled by default."""
        clean_env.delenv("RATE_LIMIT_ENABLED", raising=False)
        get_settings.cache_clear()

        settings = Settings()
        assert settings.rate_limit_enabled is True

    def test_batch_processing_defaults_applied(self, clean_env):
        """Test that batch processing settings have correct defaults."""
        clean_env.delenv("BATCH_WINDOW_SECONDS", raising=False)
        clean_env.delenv("BATCH_IDLE_TIMEOUT_SECONDS", raising=False)
        get_settings.cache_clear()

        settings = Settings()
        assert settings.batch_window_seconds == 90
        assert settings.batch_idle_timeout_seconds == 30

    def test_database_pool_defaults_applied(self, clean_env):
        """Test that database pool settings have correct defaults."""
        clean_env.delenv("DATABASE_POOL_SIZE", raising=False)
        clean_env.delenv("DATABASE_POOL_OVERFLOW", raising=False)
        clean_env.delenv("DATABASE_POOL_TIMEOUT", raising=False)
        clean_env.delenv("DATABASE_POOL_RECYCLE", raising=False)
        get_settings.cache_clear()

        settings = Settings()
        assert settings.database_pool_size == 20
        assert settings.database_pool_overflow == 30
        assert settings.database_pool_timeout == 30
        assert settings.database_pool_recycle == 1800

    def test_orchestrator_settings_defaults_applied(self, clean_env):
        """Test that nested orchestrator settings have correct defaults."""
        clean_env.delenv("ORCHESTRATOR_ENABLED", raising=False)
        clean_env.delenv("ORCHESTRATOR_HEALTH_CHECK_INTERVAL", raising=False)
        get_settings.cache_clear()

        settings = Settings()
        assert settings.orchestrator.enabled is True
        assert settings.orchestrator.health_check_interval == 30
        assert settings.orchestrator.max_consecutive_failures == 5


class TestConfigurationOverrideInTests:
    """Test that configuration can be properly overridden for testing."""

    def test_environment_variable_override(self, clean_env):
        """Test that environment variables properly override defaults."""
        clean_env.setenv("REDIS_URL", "redis://test-redis:6380/1")
        clean_env.setenv("DEBUG", "true")
        clean_env.setenv("BATCH_WINDOW_SECONDS", "120")
        get_settings.cache_clear()

        settings = Settings()

        assert settings.redis_url == "redis://test-redis:6380/1"
        assert settings.debug is True
        assert settings.batch_window_seconds == 120

    def test_settings_cache_clear_reflects_new_environment(self, clean_env):
        """Test that clearing cache allows settings to reflect environment changes."""
        # Initial settings
        settings1 = get_settings()
        original_debug = settings1.debug

        # Change environment
        clean_env.setenv("DEBUG", "true" if not original_debug else "false")
        get_settings.cache_clear()

        # New settings should reflect change
        settings2 = get_settings()
        assert settings2.debug != original_debug

    def test_direct_settings_instantiation_bypasses_cache(self, clean_env):
        """Test that directly instantiating Settings bypasses the cache."""
        cached_settings = get_settings()

        clean_env.setenv("DEBUG", "true")

        # Direct instantiation should see new environment
        direct_settings = Settings()
        assert direct_settings.debug is True

        # Cached settings unchanged
        assert cached_settings.debug is False


class TestDatabaseConfigurationValidation:
    """Test database-specific configuration validation."""

    def test_valid_postgresql_asyncpg_url_accepted(self, clean_env):
        """Test that postgresql+asyncpg:// URLs are accepted."""
        clean_env.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://user:password@host:5432/dbname",  # pragma: allowlist secret
        )
        get_settings.cache_clear()

        settings = Settings()
        assert "postgresql+asyncpg://" in settings.database_url

    def test_valid_postgresql_url_accepted(self, clean_env):
        """Test that postgresql:// URLs (without driver) are accepted."""
        clean_env.setenv(
            "DATABASE_URL",
            "postgresql://user:password@host:5432/dbname",  # pragma: allowlist secret
        )
        get_settings.cache_clear()

        settings = Settings()
        assert "postgresql://" in settings.database_url

    def test_mysql_url_rejected(self, clean_env):
        """Test that MySQL URLs are rejected."""
        clean_env.setenv(
            "DATABASE_URL",
            "mysql+aiomysql://user:password@host:3306/dbname",  # pragma: allowlist secret
        )
        get_settings.cache_clear()

        with pytest.raises(ValueError, match="Only PostgreSQL is supported"):
            Settings()

    def test_mongodb_url_rejected(self, clean_env):
        """Test that MongoDB URLs are rejected."""
        clean_env.setenv("DATABASE_URL", "mongodb://host:27017/dbname")
        get_settings.cache_clear()

        with pytest.raises(ValidationError):
            Settings()


class TestRedisConfigurationValidation:
    """Test Redis-specific configuration validation."""

    def test_valid_redis_url_accepted(self, clean_env):
        """Test that redis:// URLs are accepted."""
        clean_env.setenv("REDIS_URL", "redis://localhost:6379/0")
        get_settings.cache_clear()

        settings = Settings()
        assert settings.redis_url == "redis://localhost:6379/0"

    def test_valid_rediss_url_accepted(self, clean_env):
        """Test that rediss:// (TLS) URLs are accepted."""
        clean_env.setenv("REDIS_URL", "rediss://secure-redis:6379/0")
        get_settings.cache_clear()

        settings = Settings()
        assert settings.redis_url == "rediss://secure-redis:6379/0"

    def test_redis_url_with_password_accepted(self, clean_env):
        """Test that Redis URLs with password are accepted."""
        clean_env.setenv("REDIS_URL", "redis://:password@localhost:6379/0")
        get_settings.cache_clear()

        settings = Settings()
        assert ":password@" in settings.redis_url

    def test_redis_url_missing_host_rejected(self, clean_env):
        """Test that Redis URLs without host are rejected."""
        clean_env.setenv("REDIS_URL", "redis:///0")
        get_settings.cache_clear()

        with pytest.raises(ValueError, match="missing host"):
            Settings()

    def test_redis_ssl_settings_accepted(self, clean_env):
        """Test that Redis SSL settings are properly configured."""
        clean_env.setenv("REDIS_SSL_ENABLED", "true")
        clean_env.setenv("REDIS_SSL_CERT_REQS", "required")
        clean_env.setenv("REDIS_SSL_CHECK_HOSTNAME", "true")
        get_settings.cache_clear()

        settings = Settings()
        assert settings.redis_ssl_enabled is True
        assert settings.redis_ssl_cert_reqs == "required"
        assert settings.redis_ssl_check_hostname is True


class TestAIServiceConfigurationValidation:
    """Test AI service configuration validation."""

    def test_valid_ai_service_urls_accepted(self, clean_env):
        """Test that valid HTTP/HTTPS URLs for AI services are accepted."""
        clean_env.setenv("RTDETR_URL", "http://gpu-server:8090")
        clean_env.setenv("NEMOTRON_URL", "https://gpu-server:8091/v1")
        get_settings.cache_clear()

        settings = Settings()
        assert settings.rtdetr_url == "http://gpu-server:8090"
        assert settings.nemotron_url == "https://gpu-server:8091/v1"

    def test_ai_service_url_trailing_slash_stripped(self, clean_env):
        """Test that trailing slashes are stripped from AI service URLs."""
        clean_env.setenv("RTDETR_URL", "http://gpu-server:8090/")
        get_settings.cache_clear()

        settings = Settings()
        # Trailing slash should be stripped to prevent //health issues
        assert settings.rtdetr_url == "http://gpu-server:8090"

    def test_ai_timeout_settings_accepted(self, clean_env):
        """Test that AI timeout settings within valid ranges are accepted."""
        clean_env.setenv("AI_CONNECT_TIMEOUT", "15.0")
        clean_env.setenv("AI_HEALTH_TIMEOUT", "10.0")
        clean_env.setenv("RTDETR_READ_TIMEOUT", "90.0")
        clean_env.setenv("NEMOTRON_READ_TIMEOUT", "180.0")
        get_settings.cache_clear()

        settings = Settings()
        assert settings.ai_connect_timeout == 15.0
        assert settings.ai_health_timeout == 10.0
        assert settings.rtdetr_read_timeout == 90.0
        assert settings.nemotron_read_timeout == 180.0

    def test_ai_timeout_above_maximum_rejected(self, clean_env):
        """Test that AI timeouts above maximum are rejected."""
        clean_env.setenv("AI_CONNECT_TIMEOUT", "100.0")  # Max is 60
        get_settings.cache_clear()

        with pytest.raises(ValidationError):
            Settings()

    def test_vision_service_urls_accepted(self, clean_env):
        """Test that vision service URLs are properly validated."""
        clean_env.setenv("FLORENCE_URL", "http://florence:8092")
        clean_env.setenv("CLIP_URL", "http://clip:8093")
        clean_env.setenv("ENRICHMENT_URL", "http://enrichment:8094")
        get_settings.cache_clear()

        settings = Settings()
        assert settings.florence_url == "http://florence:8092"
        assert settings.clip_url == "http://clip:8093"
        assert settings.enrichment_url == "http://enrichment:8094"


class TestRateLimitConfigurationValidation:
    """Test rate limiting configuration validation."""

    def test_rate_limit_settings_accepted(self, clean_env):
        """Test that valid rate limit settings are accepted."""
        clean_env.setenv("RATE_LIMIT_ENABLED", "true")
        clean_env.setenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "120")
        clean_env.setenv("RATE_LIMIT_BURST", "20")
        get_settings.cache_clear()

        settings = Settings()
        assert settings.rate_limit_enabled is True
        assert settings.rate_limit_requests_per_minute == 120
        assert settings.rate_limit_burst == 20

    def test_rate_limit_below_minimum_rejected(self, clean_env):
        """Test that rate limit below minimum (1) is rejected."""
        clean_env.setenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "0")
        get_settings.cache_clear()

        with pytest.raises(ValidationError):
            Settings()


class TestOrchestratorConfigurationValidation:
    """Test container orchestrator configuration validation."""

    def test_orchestrator_settings_accepted(self, clean_env):
        """Test that valid orchestrator settings are accepted."""
        clean_env.setenv("ORCHESTRATOR_ENABLED", "true")
        clean_env.setenv("ORCHESTRATOR_HEALTH_CHECK_INTERVAL", "60")
        clean_env.setenv("ORCHESTRATOR_HEALTH_CHECK_TIMEOUT", "10")
        clean_env.setenv("ORCHESTRATOR_STARTUP_GRACE_PERIOD", "120")
        get_settings.cache_clear()

        settings = Settings()
        assert settings.orchestrator.enabled is True
        assert settings.orchestrator.health_check_interval == 60
        assert settings.orchestrator.health_check_timeout == 10
        assert settings.orchestrator.startup_grace_period == 120

    def test_orchestrator_interval_below_minimum_rejected(self, clean_env):
        """Test that health check interval below minimum (5) is rejected."""
        clean_env.setenv("ORCHESTRATOR_HEALTH_CHECK_INTERVAL", "2")
        get_settings.cache_clear()

        with pytest.raises(ValidationError):
            Settings()

    def test_orchestrator_timeout_above_maximum_rejected(self, clean_env):
        """Test that health check timeout above maximum (60) is rejected."""
        clean_env.setenv("ORCHESTRATOR_HEALTH_CHECK_TIMEOUT", "120")
        get_settings.cache_clear()

        with pytest.raises(ValidationError):
            Settings()


class TestFeatureFlagConfiguration:
    """Test feature flag configuration."""

    def test_feature_flags_can_be_enabled(self, clean_env):
        """Test that feature flags can be enabled via environment."""
        clean_env.setenv("VISION_EXTRACTION_ENABLED", "true")
        clean_env.setenv("REID_ENABLED", "true")
        clean_env.setenv("SCENE_CHANGE_ENABLED", "true")
        clean_env.setenv("OTEL_ENABLED", "true")
        get_settings.cache_clear()

        settings = Settings()
        assert settings.vision_extraction_enabled is True
        assert settings.reid_enabled is True
        assert settings.scene_change_enabled is True
        assert settings.otel_enabled is True

    def test_feature_flags_can_be_disabled(self, clean_env):
        """Test that feature flags can be disabled via environment."""
        clean_env.setenv("VISION_EXTRACTION_ENABLED", "false")
        clean_env.setenv("CLIP_GENERATION_ENABLED", "false")
        clean_env.setenv("NOTIFICATION_ENABLED", "false")
        get_settings.cache_clear()

        settings = Settings()
        assert settings.vision_extraction_enabled is False
        assert settings.clip_generation_enabled is False
        assert settings.notification_enabled is False


class TestQueueConfigurationValidation:
    """Test queue and backpressure configuration validation."""

    def test_queue_settings_accepted(self, clean_env):
        """Test that valid queue settings are accepted."""
        clean_env.setenv("QUEUE_MAX_SIZE", "5000")
        clean_env.setenv("QUEUE_OVERFLOW_POLICY", "dlq")
        clean_env.setenv("QUEUE_BACKPRESSURE_THRESHOLD", "0.75")
        get_settings.cache_clear()

        settings = Settings()
        assert settings.queue_max_size == 5000
        assert settings.queue_overflow_policy == "dlq"
        assert settings.queue_backpressure_threshold == 0.75

    def test_queue_backpressure_threshold_out_of_range_rejected(self, clean_env):
        """Test that backpressure threshold outside 0.5-1.0 is rejected."""
        clean_env.setenv("QUEUE_BACKPRESSURE_THRESHOLD", "0.3")
        get_settings.cache_clear()

        with pytest.raises(ValidationError):
            Settings()


class TestStartupValidationWithApp:
    """Test that configuration validation happens before app startup."""

    @pytest.mark.asyncio
    async def test_app_fails_fast_with_invalid_config(self, clean_env, monkeypatch):
        """Test that the app fails fast when configuration is invalid.

        This test verifies the fail-fast principle: the application should
        refuse to start with invalid configuration rather than starting and
        failing later with cryptic errors.
        """
        # Set invalid database URL
        monkeypatch.setenv("DATABASE_URL", "invalid-url-format")
        get_settings.cache_clear()

        # App should fail during settings initialization
        with pytest.raises((ValueError, ValidationError)):
            from backend.main import app  # noqa: F401

            # Force settings reload
            get_settings.cache_clear()
            _ = get_settings()

    @pytest.mark.asyncio
    async def test_app_starts_with_valid_config(self, integration_db, mock_redis):
        """Test that the app starts successfully with valid configuration.

        This test verifies that when all required configuration is present
        and valid, the application starts without errors.
        """
        from backend.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"


class TestGrafanaUrlValidation:
    """Test Grafana URL validation with SSRF protection."""

    def test_valid_grafana_url_accepted(self, clean_env):
        """Test that valid Grafana URLs are accepted."""
        clean_env.setenv("GRAFANA_URL", "http://localhost:3002")
        get_settings.cache_clear()

        settings = Settings()
        assert settings.grafana_url == "http://localhost:3002"

    def test_grafana_url_defaults_to_localhost(self, clean_env):
        """Test that Grafana URL defaults to localhost when not set."""
        clean_env.delenv("GRAFANA_URL", raising=False)
        get_settings.cache_clear()

        settings = Settings()
        assert settings.grafana_url == "http://localhost:3002"

    def test_empty_grafana_url_uses_default(self, clean_env):
        """Test that empty Grafana URL falls back to default."""
        clean_env.setenv("GRAFANA_URL", "")
        get_settings.cache_clear()

        settings = Settings()
        assert settings.grafana_url == "http://localhost:3002"
