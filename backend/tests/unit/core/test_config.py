"""Unit tests for application configuration settings."""

import pytest
from pydantic import ValidationError

from backend.core.config import Settings, get_settings


@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment variables and settings cache before each test.

    Sets DATABASE_URL to a valid test value since it's now required.
    Sets ENVIRONMENT=development to allow weak test passwords (NEM-3141).
    """
    # Clear all config-related environment variables
    env_vars = [
        "DATABASE_URL",
        "REDIS_URL",
        "APP_NAME",
        "APP_VERSION",
        "DEBUG",
        "API_HOST",
        "API_PORT",
        "CORS_ORIGINS",
        "FOSCAM_BASE_PATH",
        "FILE_WATCHER_POLLING",
        "FILE_WATCHER_POLLING_INTERVAL",
        "RETENTION_DAYS",
        "BATCH_WINDOW_SECONDS",
        "BATCH_IDLE_TIMEOUT_SECONDS",
        "YOLO26_URL",
        "NEMOTRON_URL",
        "ENVIRONMENT",
    ]

    for var in env_vars:
        monkeypatch.delenv(var, raising=False)

    # Set DATABASE_URL since it's now required (no default)
    # pragma: allowlist secret
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
    )

    # Set ENVIRONMENT to development to allow weak test passwords (NEM-3141).
    # Production/staging would reject the short "test" password in DATABASE_URL.
    monkeypatch.setenv("ENVIRONMENT", "development")

    # Python 3.14: Pydantic Settings still reads .env after delenv.
    # Set explicit values for all settings that tests rely on having defaults.
    monkeypatch.setenv("FOSCAM_BASE_PATH", "/export/foscam")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("YOLO26_URL", "http://localhost:8090")
    monkeypatch.setenv("NEMOTRON_URL", "http://localhost:8091")
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:5173"]')
    monkeypatch.setenv("API_HOST", "0.0.0.0")  # noqa: S104
    monkeypatch.setenv("API_PORT", "8000")
    monkeypatch.setenv("RETENTION_DAYS", "30")
    monkeypatch.setenv("BATCH_WINDOW_SECONDS", "90")

    # Clear the lru_cache on get_settings
    get_settings.cache_clear()

    yield monkeypatch


class TestSettingsDefaults:
    """Test that Settings class has correct default values."""

    def test_database_url_from_env(self, clean_env):
        """Test database URL is read from environment (no default value)."""
        settings = Settings()
        # DATABASE_URL is now required - test fixture sets it
        # pragma: allowlist secret
        assert (
            settings.database_url
            == "postgresql+asyncpg://test:test@localhost:5432/test"  # pragma: allowlist secret
        )

    def test_default_redis_url(self, clean_env):
        """Test default Redis URL points to localhost."""
        settings = Settings()
        assert settings.redis_url == "redis://localhost:6379/0"

    def test_default_app_settings(self, clean_env):
        """Test default application name, version, and debug mode."""
        settings = Settings()
        assert settings.app_name == "Home Security Intelligence"
        assert settings.app_version == "0.1.0"
        assert settings.debug is False

    def test_default_api_settings(self, clean_env):
        """Test default API host and port configuration."""
        settings = Settings()
        assert settings.api_host == "0.0.0.0"  # noqa: S104
        assert settings.api_port == 8000

    def test_default_cors_origins(self, clean_env):
        """Test default CORS origins include localhost and 127.0.0.1 development URLs."""
        # Delete CORS_ORIGINS to test the actual default value
        clean_env.delenv("CORS_ORIGINS", raising=False)
        settings = Settings()
        assert settings.cors_origins == [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://0.0.0.0:3000",
            "http://0.0.0.0:5173",
        ]
        assert isinstance(settings.cors_origins, list)

    def test_default_foscam_path(self, clean_env):
        """Test default Foscam base path."""
        settings = Settings()
        assert settings.foscam_base_path == "/export/foscam"

    def test_default_file_watcher_polling(self, clean_env):
        """Test default file watcher polling settings."""
        settings = Settings()
        assert settings.file_watcher_polling is False
        assert settings.file_watcher_polling_interval == 1.0

    def test_default_retention_days(self, clean_env):
        """Test default retention period is 30 days."""
        settings = Settings()
        assert settings.retention_days == 30

    def test_default_batch_settings(self, clean_env):
        """Test default batch processing time windows."""
        settings = Settings()
        assert settings.batch_window_seconds == 90
        assert settings.batch_idle_timeout_seconds == 30
        assert settings.batch_max_detections == 500  # NEM-1726

    def test_default_ai_service_urls(self, clean_env):
        """Test default AI service endpoint URLs.

        Note: URLs are normalized without trailing slashes to prevent
        double-slash issues when appending paths like /health.
        """
        settings = Settings()
        # URLs should NOT have trailing slashes to avoid //health issues
        assert settings.yolo26_url == "http://localhost:8090"
        assert settings.nemotron_url == "http://localhost:8091"


class TestEnvironmentOverrides:
    """Test that environment variables override default settings."""

    def test_override_database_url(self, clean_env):
        """Test DATABASE_URL environment variable overrides default."""
        # pragma: allowlist secret
        clean_env.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://user:pass@localhost:5432/testdb",  # pragma: allowlist secret
        )
        settings = Settings()
        # pragma: allowlist secret
        assert (
            settings.database_url
            == "postgresql+asyncpg://user:pass@localhost:5432/testdb"  # pragma: allowlist secret
        )  # pragma: allowlist secret

    def test_override_redis_url(self, clean_env):
        """Test REDIS_URL environment variable overrides default."""
        clean_env.setenv("REDIS_URL", "redis://redis-server:6380/1")
        settings = Settings()
        assert settings.redis_url == "redis://redis-server:6380/1"

    def test_override_app_name(self, clean_env):
        """Test APP_NAME environment variable overrides default."""
        clean_env.setenv("APP_NAME", "Custom App Name")
        settings = Settings()
        assert settings.app_name == "Custom App Name"

    def test_override_api_host(self, clean_env):
        """Test API_HOST environment variable overrides default."""
        clean_env.setenv("API_HOST", "127.0.0.1")
        settings = Settings()
        assert settings.api_host == "127.0.0.1"

    def test_override_api_port(self, clean_env):
        """Test API_PORT environment variable overrides default."""
        clean_env.setenv("API_PORT", "9000")
        settings = Settings()
        assert settings.api_port == 9000


class TestCORSConfiguration:
    """Test CORS configuration parsing and validation."""

    def test_cors_from_json_string(self, clean_env):
        """Test CORS_ORIGINS parses JSON array string correctly."""
        clean_env.setenv(
            "CORS_ORIGINS",
            '["http://frontend.local:3000", "https://app.example.com"]',
        )
        settings = Settings()
        assert settings.cors_origins == [
            "http://frontend.local:3000",
            "https://app.example.com",
        ]

    def test_cors_from_single_origin(self, clean_env):
        """Test CORS_ORIGINS handles single origin in JSON array.

        Note: Pydantic Settings v2 requires JSON format for list fields.
        Space-separated values are not supported.
        """
        clean_env.setenv(
            "CORS_ORIGINS",
            '["http://localhost:3000"]',
        )
        settings = Settings()
        assert settings.cors_origins == [
            "http://localhost:3000",
        ]

    def test_cors_from_json_array(self, clean_env):
        """Test CORS_ORIGINS parses JSON array format."""
        clean_env.setenv(
            "CORS_ORIGINS",
            '["http://localhost:3000","http://localhost:5173"]',
        )
        settings = Settings()
        assert settings.cors_origins == [
            "http://localhost:3000",
            "http://localhost:5173",
        ]

    def test_cors_json_array_with_spaces(self, clean_env):
        """Test CORS_ORIGINS handles JSON array with spaces."""
        clean_env.setenv(
            "CORS_ORIGINS",
            '["http://localhost:3000", "http://localhost:5173"]',
        )
        settings = Settings()
        assert settings.cors_origins == [
            "http://localhost:3000",
            "http://localhost:5173",
        ]

    def test_cors_default_when_not_set(self, clean_env):
        """Test CORS_ORIGINS uses default when set to default JSON array."""
        # Setting to default value explicitly - Pydantic Settings requires JSON for list types
        clean_env.setenv("CORS_ORIGINS", '["http://localhost:5173"]')
        settings = Settings()
        assert isinstance(settings.cors_origins, list)
        assert len(settings.cors_origins) > 0


class TestDatabaseConfiguration:
    """Test database connection configuration and validation."""

    def test_database_url_is_required(self, monkeypatch, tmp_path):
        """Test that DATABASE_URL raises error when not set.

        Note: We change to a temp directory to avoid reading DATABASE_URL
        from the project's .env file, which Python 3.14+ Pydantic Settings
        reads even after delenv().
        """
        # Change to temp directory to avoid reading from project .env
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        get_settings.cache_clear()

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        # PostgreSQL URL is required, empty string is not allowed
        assert "database_url" in str(exc_info.value).lower()


class TestFileWatcherSettings:
    """Test file watcher configuration settings."""

    def test_file_watcher_polling_boolean_conversion(self, clean_env):
        """Test FILE_WATCHER_POLLING converts string to boolean."""
        clean_env.setenv("FILE_WATCHER_POLLING", "true")
        settings = Settings()
        assert settings.file_watcher_polling is True

    def test_file_watcher_polling_interval_float_conversion(self, clean_env):
        """Test FILE_WATCHER_POLLING_INTERVAL converts to float."""
        clean_env.setenv("FILE_WATCHER_POLLING_INTERVAL", "2.5")
        settings = Settings()
        assert settings.file_watcher_polling_interval == 2.5


class TestBatchProcessingSettings:
    """Test batch processing configuration settings."""

    def test_batch_window_seconds_integer_conversion(self, clean_env):
        """Test BATCH_WINDOW_SECONDS converts to integer."""
        clean_env.setenv("BATCH_WINDOW_SECONDS", "120")
        settings = Settings()
        assert settings.batch_window_seconds == 120

    def test_batch_idle_timeout_integer_conversion(self, clean_env):
        """Test BATCH_IDLE_TIMEOUT_SECONDS converts to integer."""
        clean_env.setenv("BATCH_IDLE_TIMEOUT_SECONDS", "45")
        settings = Settings()
        assert settings.batch_idle_timeout_seconds == 45


class TestSettingsConfiguration:
    """Test Settings model configuration and behavior."""

    def test_settings_is_case_insensitive(self, clean_env):
        """Test Settings accepts lowercase environment variable names."""
        clean_env.setenv("api_port", "7000")
        settings = Settings()
        assert settings.api_port == 7000

    def test_settings_ignores_extra_env_vars(self, clean_env):
        """Test Settings model ignores unknown environment variables."""
        clean_env.setenv("UNKNOWN_SETTING", "should_be_ignored")
        settings = Settings()
        assert not hasattr(settings, "unknown_setting")
        assert not hasattr(settings, "UNKNOWN_SETTING")

    def test_settings_loads_from_env_file(self, tmp_path, monkeypatch):
        """Test Settings loads from .env file when DATABASE_URL is set."""
        env_file = tmp_path / ".env"
        # Write a test .env file with all required fields
        # Include ENVIRONMENT=development to allow weak test passwords (NEM-3141)
        env_file.write_text(
            'DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test"\n'  # pragma: allowlist secret
            "ENVIRONMENT=development\n"
            "API_PORT=8888\n"
        )

        # Clear environment variables that might be set from project .env
        monkeypatch.delenv("API_PORT", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("REDIS_URL", raising=False)

        # Change to tmp directory so Settings finds our .env file
        monkeypatch.chdir(tmp_path)
        get_settings.cache_clear()

        settings = Settings()
        assert settings.api_port == 8888

    def test_env_variables_override_env_file(self, tmp_path, monkeypatch):
        """Test environment variables take precedence over .env file."""
        env_file = tmp_path / ".env"
        # Include ENVIRONMENT=development to allow weak test passwords (NEM-3141)
        env_file.write_text(
            'DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test"\n'  # pragma: allowlist secret
            "ENVIRONMENT=development\n"
            "API_PORT=8888\n"
        )

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("API_PORT", "9999")
        get_settings.cache_clear()

        settings = Settings()
        assert settings.api_port == 9999  # Environment variable wins

    def test_get_settings_caches_instance(self, clean_env):
        """Test get_settings returns cached Settings instance."""
        get_settings.cache_clear()
        settings1 = get_settings()
        settings2 = get_settings()
        # Should be the same instance due to lru_cache
        assert settings1 is settings2

    def test_settings_field_descriptions(self, clean_env):
        """Test that all Settings fields have descriptions."""
        settings = Settings()
        fields = settings.model_fields

        # Check a sample of fields have descriptions
        assert "description" in str(fields["database_url"])
        assert "description" in str(fields["redis_url"])
        assert "description" in str(fields["api_host"])


class TestAIServiceConfiguration:
    """Test AI service endpoint configuration and URL normalization."""

    def test_yolo26_url_removes_trailing_slash(self, clean_env):
        """Test YOLO26 URL strips trailing slash to prevent double slashes."""
        clean_env.setenv("YOLO26_URL", "http://localhost:8090/")
        settings = Settings()
        # Validator should strip trailing slash
        assert settings.yolo26_url == "http://localhost:8090"
        assert not settings.yolo26_url.endswith("/")

    def test_nemotron_url_removes_trailing_slash(self, clean_env):
        """Test Nemotron URL strips trailing slash."""
        clean_env.setenv("NEMOTRON_URL", "http://localhost:8091/")
        settings = Settings()
        assert settings.nemotron_url == "http://localhost:8091"
        assert not settings.nemotron_url.endswith("/")

    def test_ai_service_urls_accept_custom_ports(self, clean_env):
        """Test AI service URLs work with non-standard ports."""
        clean_env.setenv("YOLO26_URL", "http://ai-server:9000")
        clean_env.setenv("NEMOTRON_URL", "http://ai-server:9001")
        settings = Settings()
        assert settings.yolo26_url == "http://ai-server:9000"
        assert settings.nemotron_url == "http://ai-server:9001"


class TestOrchestratorSettings:
    """Test orchestrator settings configuration."""

    def test_orchestrator_enabled_default(self, clean_env):
        """Test orchestrator is enabled by default."""
        settings = Settings()
        assert settings.orchestrator.enabled is True

    def test_orchestrator_enabled_can_be_disabled(self, clean_env):
        """Test orchestrator can be disabled via environment variable."""
        clean_env.setenv("ORCHESTRATOR_ENABLED", "false")
        get_settings.cache_clear()
        settings = Settings()
        assert settings.orchestrator.enabled is False

    def test_orchestrator_health_check_interval_default(self, clean_env):
        """Test orchestrator health check interval default value."""
        settings = Settings()
        assert settings.orchestrator.health_check_interval == 30

    def test_orchestrator_health_check_interval_can_be_overridden(self, clean_env):
        """Test orchestrator health check interval can be overridden."""
        clean_env.setenv("ORCHESTRATOR_HEALTH_CHECK_INTERVAL", "60")
        get_settings.cache_clear()
        settings = Settings()
        assert settings.orchestrator.health_check_interval == 60


class TestValidationRules:
    """Test Settings field validation rules."""

    def test_api_port_must_be_positive(self, clean_env):
        """Test API_PORT rejects negative values."""
        clean_env.setenv("API_PORT", "-1")
        get_settings.cache_clear()

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "api_port" in str(exc_info.value).lower()

    def test_retention_days_must_be_positive(self, clean_env):
        """Test RETENTION_DAYS rejects negative values."""
        clean_env.setenv("RETENTION_DAYS", "0")
        get_settings.cache_clear()

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "retention_days" in str(exc_info.value).lower()

    def test_batch_window_seconds_must_be_positive(self, clean_env):
        """Test BATCH_WINDOW_SECONDS rejects negative values."""
        clean_env.setenv("BATCH_WINDOW_SECONDS", "0")
        get_settings.cache_clear()

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "batch_window_seconds" in str(exc_info.value).lower()

    def test_database_pool_size_has_min_max(self, clean_env):
        """Test DATABASE_POOL_SIZE enforces min/max constraints."""
        clean_env.setenv("DATABASE_POOL_SIZE", "3")  # Below minimum of 5
        get_settings.cache_clear()

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "database_pool_size" in str(exc_info.value).lower()

    def test_database_pool_size_max_constraint(self, clean_env):
        """Test DATABASE_POOL_SIZE rejects values above maximum."""
        clean_env.setenv("DATABASE_POOL_SIZE", "150")  # Above maximum of 100
        get_settings.cache_clear()

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "database_pool_size" in str(exc_info.value).lower()


class TestDatabaseConnectionString:
    """Test database connection string parsing and validation."""

    def test_database_url_accepts_asyncpg_driver(self, clean_env):
        """Test DATABASE_URL accepts asyncpg driver prefix."""
        # pragma: allowlist secret
        clean_env.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://user:pass@host:5432/db",  # pragma: allowlist secret
        )
        settings = Settings()
        # pragma: allowlist secret
        assert (
            settings.database_url
            == "postgresql+asyncpg://user:pass@host:5432/db"  # pragma: allowlist secret
        )

    def test_database_url_preserves_query_parameters(self, clean_env):
        """Test DATABASE_URL preserves connection query parameters."""
        # pragma: allowlist secret
        url_with_params = "postgresql+asyncpg://user:pass@host:5432/db?ssl=require&connect_timeout=10"  # pragma: allowlist secret
        clean_env.setenv("DATABASE_URL", url_with_params)
        settings = Settings()
        assert settings.database_url == url_with_params
        assert "ssl=require" in settings.database_url
        assert "connect_timeout=10" in settings.database_url


class TestProductionPasswordValidation:
    """Test production password validation (NEM-3141).

    Ensures weak/default passwords are rejected in production and staging environments.
    """

    def test_production_rejects_weak_database_password(self, clean_env):
        """Test that production environment rejects weak database passwords."""
        clean_env.setenv("ENVIRONMENT", "production")
        # Use the old hardcoded development password  # pragma: allowlist secret
        clean_env.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
        )
        get_settings.cache_clear()

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "weak" in str(exc_info.value).lower() or "password" in str(exc_info.value).lower()

    def test_production_rejects_short_database_password(self, clean_env):
        """Test that production environment rejects short database passwords."""
        clean_env.setenv("ENVIRONMENT", "production")
        # Use a short password (less than 16 chars)
        clean_env.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://security:short@localhost:5432/security",  # pragma: allowlist secret
        )
        get_settings.cache_clear()

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "weak" in str(exc_info.value).lower() or "password" in str(exc_info.value).lower()

    def test_production_accepts_strong_password(self, clean_env):
        """Test that production environment accepts strong passwords."""
        clean_env.setenv("ENVIRONMENT", "production")
        # Use a strong password (32 chars, unique)
        clean_env.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://security:a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6@localhost:5432/security",  # pragma: allowlist secret
        )
        get_settings.cache_clear()

        # Should not raise
        settings = Settings()
        assert settings.environment == "production"

    def test_staging_rejects_weak_password(self, clean_env):
        """Test that staging environment also rejects weak passwords."""
        clean_env.setenv("ENVIRONMENT", "staging")
        clean_env.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://security:password@localhost:5432/security",  # pragma: allowlist secret
        )
        get_settings.cache_clear()

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "weak" in str(exc_info.value).lower() or "password" in str(exc_info.value).lower()

    def test_development_allows_weak_password(self, clean_env):
        """Test that development environment allows weak passwords."""
        clean_env.setenv("ENVIRONMENT", "development")
        # Use the old hardcoded development password  # pragma: allowlist secret
        clean_env.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
        )
        get_settings.cache_clear()

        # Should not raise in development
        settings = Settings()
        assert settings.environment == "development"

    def test_test_environment_allows_weak_password(self, clean_env):
        """Test that test environment allows weak passwords."""
        clean_env.setenv("ENVIRONMENT", "test")
        clean_env.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://security:test@localhost:5432/security",  # pragma: allowlist secret
        )
        get_settings.cache_clear()

        # Should not raise in test environment
        settings = Settings()
        assert settings.environment == "test"

    def test_production_rejects_common_weak_passwords(self, clean_env):
        """Test that production rejects various common weak passwords."""
        weak_passwords = [
            "password",
            "postgres",
            "admin",
            "root",
            "123456",
            "changeme",
            "secret",
            "ftp_dev_password",
        ]

        for weak_pw in weak_passwords:
            clean_env.setenv("ENVIRONMENT", "production")
            clean_env.setenv(
                "DATABASE_URL",
                f"postgresql+asyncpg://security:{weak_pw}@localhost:5432/security",  # pragma: allowlist secret
            )
            get_settings.cache_clear()

            with pytest.raises(ValidationError, match=r"(?i)weak|password"):
                Settings()
