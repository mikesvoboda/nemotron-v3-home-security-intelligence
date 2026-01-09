"""Unit tests for application configuration settings."""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.core.config import Settings, get_settings


@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment variables and settings cache before each test.

    Sets DATABASE_URL to a valid test value since it's now required.
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
        "RTDETR_URL",
        "NEMOTRON_URL",
    ]

    for var in env_vars:
        monkeypatch.delenv(var, raising=False)

    # Set DATABASE_URL since it's now required (no default)
    # pragma: allowlist secret
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
    )

    # Set FOSCAM_BASE_PATH to expected default since .env file may override
    # (monkeypatch.delenv only clears os.environ, but Pydantic still reads .env file)
    monkeypatch.setenv("FOSCAM_BASE_PATH", "/export/foscam")

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
        assert settings.rtdetr_url == "http://localhost:8090"
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
        clean_env.setenv("APP_NAME", "Custom Security App")
        settings = Settings()
        assert settings.app_name == "Custom Security App"

    def test_override_app_version(self, clean_env):
        """Test APP_VERSION environment variable overrides default."""
        clean_env.setenv("APP_VERSION", "1.2.3")
        settings = Settings()
        assert settings.app_version == "1.2.3"

    def test_override_debug_mode(self, clean_env):
        """Test DEBUG environment variable enables debug mode."""
        clean_env.setenv("DEBUG", "true")
        settings = Settings()
        assert settings.debug is True

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

    def test_override_cors_origins(self, clean_env):
        """Test CORS_ORIGINS environment variable overrides default."""
        clean_env.setenv(
            "CORS_ORIGINS",
            '["http://example.com", "https://app.example.com"]',
        )
        settings = Settings()
        assert settings.cors_origins == [
            "http://example.com",
            "https://app.example.com",
        ]

    def test_override_foscam_path(self, clean_env):
        """Test FOSCAM_BASE_PATH environment variable overrides default."""
        clean_env.setenv("FOSCAM_BASE_PATH", "/mnt/cameras/foscam")
        settings = Settings()
        assert settings.foscam_base_path == "/mnt/cameras/foscam"

    def test_override_file_watcher_polling(self, clean_env):
        """Test FILE_WATCHER_POLLING environment variable overrides default."""
        clean_env.setenv("FILE_WATCHER_POLLING", "true")
        settings = Settings()
        assert settings.file_watcher_polling is True

    def test_override_file_watcher_polling_interval(self, clean_env):
        """Test FILE_WATCHER_POLLING_INTERVAL environment variable overrides default."""
        clean_env.setenv("FILE_WATCHER_POLLING_INTERVAL", "5.0")
        settings = Settings()
        assert settings.file_watcher_polling_interval == 5.0

    def test_override_retention_days(self, clean_env):
        """Test RETENTION_DAYS environment variable overrides default."""
        clean_env.setenv("RETENTION_DAYS", "60")
        settings = Settings()
        assert settings.retention_days == 60

    def test_override_batch_window_seconds(self, clean_env):
        """Test BATCH_WINDOW_SECONDS environment variable overrides default."""
        clean_env.setenv("BATCH_WINDOW_SECONDS", "120")
        settings = Settings()
        assert settings.batch_window_seconds == 120

    def test_override_batch_idle_timeout(self, clean_env):
        """Test BATCH_IDLE_TIMEOUT_SECONDS environment variable overrides default."""
        clean_env.setenv("BATCH_IDLE_TIMEOUT_SECONDS", "45")
        settings = Settings()
        assert settings.batch_idle_timeout_seconds == 45

    def test_override_rtdetr_url(self, clean_env):
        """Test RTDETR_URL environment variable overrides default."""
        clean_env.setenv("RTDETR_URL", "http://gpu-server:8001")
        settings = Settings()
        # URLs normalized without trailing slash to avoid //health issues
        assert settings.rtdetr_url == "http://gpu-server:8001"

    def test_override_nemotron_url(self, clean_env):
        """Test NEMOTRON_URL environment variable overrides default."""
        clean_env.setenv("NEMOTRON_URL", "http://gpu-server:8002")
        settings = Settings()
        # URLs normalized without trailing slash to avoid //health issues
        assert settings.nemotron_url == "http://gpu-server:8002"


class TestTypeCoercion:
    """Test that environment variables are correctly coerced to expected types."""

    def test_integer_coercion_from_string(self, clean_env):
        """Test that string integers are coerced to int type."""
        clean_env.setenv("API_PORT", "3000")
        clean_env.setenv("RETENTION_DAYS", "45")
        clean_env.setenv("BATCH_WINDOW_SECONDS", "180")
        clean_env.setenv("BATCH_IDLE_TIMEOUT_SECONDS", "60")

        settings = Settings()
        assert isinstance(settings.api_port, int)
        assert settings.api_port == 3000
        assert isinstance(settings.retention_days, int)
        assert settings.retention_days == 45
        assert isinstance(settings.batch_window_seconds, int)
        assert settings.batch_window_seconds == 180
        assert isinstance(settings.batch_idle_timeout_seconds, int)
        assert settings.batch_idle_timeout_seconds == 60

    def test_float_coercion_from_string(self, clean_env):
        """Test that string floats are coerced to float type."""
        clean_env.setenv("FILE_WATCHER_POLLING_INTERVAL", "2.5")
        settings = Settings()
        assert isinstance(settings.file_watcher_polling_interval, float)
        assert settings.file_watcher_polling_interval == 2.5

    def test_boolean_coercion_from_string(self, clean_env):
        """Test that string booleans are coerced to bool type."""
        # Test various truthy values
        for truthy in ["true", "True", "TRUE", "1", "yes", "Yes", "on"]:
            clean_env.setenv("DEBUG", truthy)
            get_settings.cache_clear()
            settings = Settings()
            assert settings.debug is True, f"Failed for truthy value: {truthy}"

        # Test various falsy values
        for falsy in ["false", "False", "FALSE", "0", "no", "No", "off"]:
            clean_env.setenv("DEBUG", falsy)
            get_settings.cache_clear()
            settings = Settings()
            assert settings.debug is False, f"Failed for falsy value: {falsy}"

    def test_list_coercion_from_json_string(self, clean_env):
        """Test that JSON array strings are coerced to list type."""
        clean_env.setenv(
            "CORS_ORIGINS",
            '["http://localhost:8080", "https://secure.example.com"]',
        )
        settings = Settings()
        assert isinstance(settings.cors_origins, list)
        assert len(settings.cors_origins) == 2
        assert "http://localhost:8080" in settings.cors_origins
        assert "https://secure.example.com" in settings.cors_origins

    def test_invalid_integer_raises_error(self, clean_env):
        """Test that invalid integer values raise validation errors."""
        clean_env.setenv("API_PORT", "not_a_number")
        with pytest.raises(ValueError):  # Pydantic will raise validation error
            Settings()

    def test_invalid_json_list_raises_error(self, clean_env):
        """Test that invalid JSON for list fields raises validation errors."""
        clean_env.setenv("CORS_ORIGINS", "not-valid-json")
        with pytest.raises(ValueError):  # Pydantic will raise validation error
            Settings()

    def test_file_watcher_polling_interval_too_low_raises_error(self, clean_env):
        """Test that polling interval below 0.1 raises validation error."""
        clean_env.setenv("FILE_WATCHER_POLLING_INTERVAL", "0.05")
        with pytest.raises(ValueError):
            Settings()

    def test_file_watcher_polling_interval_too_high_raises_error(self, clean_env):
        """Test that polling interval above 30.0 raises validation error."""
        clean_env.setenv("FILE_WATCHER_POLLING_INTERVAL", "31.0")
        with pytest.raises(ValueError):
            Settings()

    def test_file_watcher_polling_interval_at_bounds(self, clean_env):
        """Test that polling interval at boundary values is accepted."""
        clean_env.setenv("FILE_WATCHER_POLLING_INTERVAL", "0.1")
        settings = Settings()
        assert settings.file_watcher_polling_interval == 0.1

        get_settings.cache_clear()
        clean_env.setenv("FILE_WATCHER_POLLING_INTERVAL", "30.0")
        settings = Settings()
        assert settings.file_watcher_polling_interval == 30.0


class TestSettingsSingleton:
    """Test that get_settings() implements singleton pattern correctly."""

    def test_get_settings_returns_same_instance(self, clean_env):
        """Test that get_settings() returns the same cached instance."""
        settings1 = get_settings()
        settings2 = get_settings()

        # Should be the exact same object
        assert settings1 is settings2

    def test_cache_clear_creates_new_instance(self, clean_env):
        """Test that clearing cache creates a new Settings instance."""
        settings1 = get_settings()

        # Clear cache
        get_settings.cache_clear()

        settings2 = get_settings()

        # Should be different objects after cache clear
        assert settings1 is not settings2

    def test_singleton_reflects_environment_after_cache_clear(self, clean_env):
        """Test that new settings reflect environment changes after cache clear."""
        # First instance with default values
        settings1 = get_settings()
        assert settings1.api_port == 8000

        # Change environment
        clean_env.setenv("API_PORT", "9000")

        # Without clearing cache, still returns old instance
        settings2 = get_settings()
        assert settings2.api_port == 8000  # Still cached

        # Clear cache and create new instance
        get_settings.cache_clear()
        settings3 = get_settings()
        assert settings3.api_port == 9000  # Reflects new environment

    def test_multiple_direct_instances_are_independent(self, clean_env):
        """Test that directly instantiated Settings objects are independent."""
        settings1 = Settings()
        settings2 = Settings()

        # Should be different objects (not singleton when created directly)
        assert settings1 is not settings2


class TestDatabaseUrlValidation:
    """Test the database URL validator for PostgreSQL."""

    def test_validator_accepts_postgresql_urls(self, clean_env):
        """Test that PostgreSQL URLs are accepted."""
        valid_urls = [
            "postgresql://user:pass@localhost:5432/db",  # pragma: allowlist secret
            "postgresql+asyncpg://user:pass@localhost:5432/db",  # pragma: allowlist secret
        ]

        for db_url in valid_urls:
            clean_env.setenv("DATABASE_URL", db_url)
            settings = Settings()
            assert settings.database_url == db_url

    def test_validator_rejects_sqlite_url(self, clean_env):
        """Test that SQLite URLs are rejected."""
        sqlite_url = "sqlite+aiosqlite:///./data/test.db"
        clean_env.setenv("DATABASE_URL", sqlite_url)
        with pytest.raises(ValueError, match="Only PostgreSQL is supported"):
            Settings()

    def test_validator_rejects_mysql_url(self, clean_env):
        """Test that MySQL URLs are rejected."""
        mysql_url = "mysql+aiomysql://user:pass@localhost:3306/dbname"  # pragma: allowlist secret
        clean_env.setenv("DATABASE_URL", mysql_url)
        with pytest.raises(ValueError, match="Only PostgreSQL is supported"):
            Settings()

    def test_validator_rejects_memory_database(self, clean_env):
        """Test that in-memory SQLite database is rejected."""
        clean_env.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
        with pytest.raises(ValueError, match="Only PostgreSQL is supported"):
            Settings()

    def test_validator_rejects_invalid_urls(self, clean_env):
        """Test that invalid database URLs are rejected."""
        invalid_urls = [
            "mongodb://localhost:27017/db",
            "invalid-url",
        ]

        for db_url in invalid_urls:
            clean_env.setenv("DATABASE_URL", db_url)
            with pytest.raises(ValidationError):
                Settings()


class TestSettingsConfiguration:
    """Test Settings class configuration and behavior."""

    def test_settings_case_insensitive(self, clean_env):
        """Test that environment variables are case-insensitive."""
        # Set with different case
        clean_env.setenv("api_port", "7000")
        clean_env.setenv("DEBUG", "true")

        settings = Settings()
        assert settings.api_port == 7000
        assert settings.debug is True

    def test_settings_extra_fields_ignored(self, clean_env):
        """Test that extra environment variables don't cause errors."""
        clean_env.setenv("UNKNOWN_CONFIG_FIELD", "some_value")
        clean_env.setenv("ANOTHER_UNKNOWN", "another_value")

        # Should not raise an error due to extra fields
        _ = Settings()

    def test_settings_field_descriptions(self, clean_env):
        """Test that fields have proper descriptions defined."""
        settings = Settings()

        # Check that Field objects have descriptions
        fields = settings.model_fields

        assert fields["database_url"].description is not None
        assert fields["redis_url"].description is not None
        assert fields["foscam_base_path"].description is not None
        assert fields["retention_days"].description is not None

    def test_settings_model_dump(self, clean_env):
        """Test that settings can be dumped to dictionary."""
        settings = Settings()
        config_dict = settings.model_dump()

        assert isinstance(config_dict, dict)
        assert "database_url" in config_dict
        assert "redis_url" in config_dict
        assert "api_host" in config_dict
        assert "api_port" in config_dict
        assert config_dict["api_port"] == 8000

    def test_settings_immutability(self, clean_env):
        """Test that Settings objects can be modified (not frozen by default)."""
        settings = Settings()

        # Pydantic v2 allows modification by default
        original_port = settings.api_port
        settings.api_port = 9999
        assert settings.api_port == 9999
        assert settings.api_port != original_port


class TestAIServiceUrlValidation:
    """Test URL validation for AI service endpoints."""

    def test_rtdetr_url_validates_http(self, clean_env):
        """Test that RTDETR_URL accepts valid HTTP URLs."""
        clean_env.setenv("RTDETR_URL", "http://localhost:8090")
        settings = Settings()
        # URLs normalized without trailing slash to avoid //health issues
        assert settings.rtdetr_url == "http://localhost:8090"

    def test_rtdetr_url_validates_https(self, clean_env):
        """Test that RTDETR_URL accepts valid HTTPS URLs."""
        clean_env.setenv("RTDETR_URL", "https://secure-server:8090/api")
        settings = Settings()
        assert settings.rtdetr_url == "https://secure-server:8090/api"

    def test_nemotron_url_validates_http(self, clean_env):
        """Test that NEMOTRON_URL accepts valid HTTP URLs."""
        clean_env.setenv("NEMOTRON_URL", "http://localhost:8091")
        settings = Settings()
        # URLs normalized without trailing slash to avoid //health issues
        assert settings.nemotron_url == "http://localhost:8091"

    def test_nemotron_url_validates_https(self, clean_env):
        """Test that NEMOTRON_URL accepts valid HTTPS URLs."""
        clean_env.setenv("NEMOTRON_URL", "https://secure-server:8091/v1/completions")
        settings = Settings()
        assert settings.nemotron_url == "https://secure-server:8091/v1/completions"

    def test_invalid_rtdetr_url_raises_error(self, clean_env):
        """Test that invalid RTDETR_URL raises validation error."""
        clean_env.setenv("RTDETR_URL", "not-a-valid-url")
        with pytest.raises(ValueError):
            Settings()

    def test_invalid_nemotron_url_raises_error(self, clean_env):
        """Test that invalid NEMOTRON_URL raises validation error."""
        clean_env.setenv("NEMOTRON_URL", "ftp://wrong-protocol:8091")
        with pytest.raises(ValueError):
            Settings()

    def test_missing_scheme_rtdetr_url_raises_error(self, clean_env):
        """Test that RTDETR_URL without http/https scheme raises validation error."""
        clean_env.setenv("RTDETR_URL", "localhost:8090")
        with pytest.raises(ValueError):
            Settings()

    def test_missing_scheme_nemotron_url_raises_error(self, clean_env):
        """Test that NEMOTRON_URL without http/https scheme raises validation error."""
        clean_env.setenv("NEMOTRON_URL", "gpu-server:8091")
        with pytest.raises(ValueError):
            Settings()


class TestEnvFileAlignment:
    """Test that .env.example variables align with config.py field names.

    This catches mismatches like:
    - CAMERA_ROOT vs FOSCAM_BASE_PATH
    - DETECTOR_URL vs RTDETR_URL
    - LLM_URL vs NEMOTRON_URL
    - VITE_API_URL vs VITE_API_BASE_URL
    """

    def test_env_example_variables_match_config_fields(self):
        """Verify .env.example variable names match Settings field names.

        This test ensures that environment variables in .env.example have
        corresponding fields in config.py (case-insensitive, since pydantic
        Settings uses case_sensitive=False).
        """
        # Read .env.example
        env_example_path = Path(__file__).parent.parent.parent.parent / ".env.example"
        if not env_example_path.exists():
            pytest.skip(".env.example not found")

        env_example_content = env_example_path.read_text()

        # Docker Compose-only variables that aren't used by the Python backend.
        # These are used by docker-compose.prod.yml to configure containers.
        docker_compose_only_vars = {
            "postgres_user",  # PostgreSQL container user
            "postgres_password",  # PostgreSQL container password
            "postgres_db",  # PostgreSQL container database name
            "gpu_layers",  # ai-llm container GPU config
            "ctx_size",  # ai-llm container context size
            "rtdetr_model_path",  # ai-detector container model path
            "hf_cache",  # HuggingFace cache directory mount
        }

        # Extract env var names (exclude comments and VITE_* which are frontend-only)
        env_vars = set()
        for line in env_example_content.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                var_name = stripped.split("=")[0].strip()
                var_name_lower = var_name.lower()
                # Skip VITE_* vars - they're frontend-only and not loaded by backend
                # Skip Docker Compose-only vars - they configure containers, not the app
                if (
                    not var_name.startswith("VITE_")
                    and var_name_lower not in docker_compose_only_vars
                ):
                    env_vars.add(var_name_lower)

        # Get config field names
        config_fields = {name.lower() for name in Settings.model_fields}

        # Check that every env var in .env.example has a matching config field
        missing_from_config = env_vars - config_fields
        assert not missing_from_config, (
            f"Environment variables in .env.example without matching config.py fields: "
            f"{sorted(missing_from_config)}. "
            f"Either add fields to Settings class or fix variable names in .env.example."
        )

    def test_deprecated_env_var_names_not_present(self):
        """Ensure deprecated variable names are not used in .env.example.

        This prevents regression to the old naming convention.
        """
        env_example_path = Path(__file__).parent.parent.parent.parent / ".env.example"
        if not env_example_path.exists():
            pytest.skip(".env.example not found")

        env_example_content = env_example_path.read_text()

        # List of deprecated variable names that should NOT be used
        deprecated_names = [
            "CAMERA_ROOT",  # Should be FOSCAM_BASE_PATH
            "DETECTOR_URL",  # Should be RTDETR_URL
            "LLM_URL",  # Should be NEMOTRON_URL
            "VITE_API_URL",  # Should be VITE_API_BASE_URL
        ]

        found_deprecated = []
        for deprecated in deprecated_names:
            # Check if the deprecated name appears as an env var assignment
            pattern = rf"^{deprecated}="
            if re.search(pattern, env_example_content, re.MULTILINE):
                found_deprecated.append(deprecated)

        assert not found_deprecated, (
            f"Deprecated environment variable names found in .env.example: "
            f"{found_deprecated}. Use the current naming convention."
        )


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string_environment_variables(self, clean_env):
        """Test behavior with empty string environment variables."""
        _ = Settings()

    def test_whitespace_in_string_values(self, clean_env):
        """Test that whitespace is preserved in string values."""
        clean_env.setenv("APP_NAME", "  Spaces Around  ")
        settings = Settings()
        assert settings.app_name == "  Spaces Around  "

    def test_zero_values_for_integers(self, clean_env):
        """Test that zero is accepted for integer fields."""
        clean_env.setenv("RETENTION_DAYS", "0")
        clean_env.setenv("API_PORT", "0")
        settings = Settings()
        assert settings.retention_days == 0
        assert settings.api_port == 0

    def test_negative_values_for_integers(self, clean_env):
        """Test that negative values are accepted for integer fields."""
        clean_env.setenv("RETENTION_DAYS", "-1")
        clean_env.setenv("API_PORT", "-1")
        settings = Settings()
        assert settings.retention_days == -1
        assert settings.api_port == -1

    def test_very_large_integer_values(self, clean_env):
        """Test handling of very large integer values."""
        clean_env.setenv("API_PORT", "65535")
        clean_env.setenv("RETENTION_DAYS", "999999")
        settings = Settings()
        assert settings.api_port == 65535
        assert settings.retention_days == 999999

    def test_empty_list_cors_origins(self, clean_env):
        """Test that empty list is accepted for CORS origins."""
        clean_env.setenv("CORS_ORIGINS", "[]")
        settings = Settings()
        assert settings.cors_origins == []
        assert isinstance(settings.cors_origins, list)

    def test_special_characters_in_urls(self, clean_env):
        """Test URLs with special characters like credentials."""
        clean_env.setenv(
            "DATABASE_URL",
            "postgresql://user%40name:p%40ssw0rd!@host:5432/db",
        )
        clean_env.setenv("REDIS_URL", "redis://:password123!@redis-host:6380/2")

        settings = Settings()
        assert "user%40name" in settings.database_url
        assert "p%40ssw0rd" in settings.database_url
        assert ":password123!" in settings.redis_url


class TestRedisUrlValidation:
    """Test URL validation for Redis connection strings."""

    def test_redis_url_validates_standard_scheme(self, clean_env):
        """Test that REDIS_URL accepts valid redis:// URLs."""
        clean_env.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        assert settings.redis_url == "redis://localhost:6379/0"

    def test_redis_url_validates_secure_scheme(self, clean_env):
        """Test that REDIS_URL accepts valid rediss:// URLs (TLS)."""
        clean_env.setenv("REDIS_URL", "rediss://secure-redis:6379/0")
        settings = Settings()
        assert settings.redis_url == "rediss://secure-redis:6379/0"

    def test_redis_url_with_password(self, clean_env):
        """Test that REDIS_URL accepts URLs with authentication."""
        clean_env.setenv("REDIS_URL", "redis://:mypassword@localhost:6379/0")
        settings = Settings()
        assert settings.redis_url == "redis://:mypassword@localhost:6379/0"

    def test_redis_url_with_username_password(self, clean_env):
        """Test that REDIS_URL accepts URLs with username and password."""
        # pragma: allowlist secret
        clean_env.setenv(
            "REDIS_URL",
            "redis://user:password@localhost:6379/0",  # pragma: allowlist secret
        )
        settings = Settings()
        # pragma: allowlist secret
        assert (
            settings.redis_url
            == "redis://user:password@localhost:6379/0"  # pragma: allowlist secret
        )  # pragma: allowlist secret

    def test_redis_url_without_database(self, clean_env):
        """Test that REDIS_URL accepts URLs without database number."""
        clean_env.setenv("REDIS_URL", "redis://localhost:6379")
        settings = Settings()
        assert settings.redis_url == "redis://localhost:6379"

    def test_redis_url_without_port(self, clean_env):
        """Test that REDIS_URL accepts URLs without port."""
        clean_env.setenv("REDIS_URL", "redis://localhost")
        settings = Settings()
        assert settings.redis_url == "redis://localhost"

    def test_invalid_redis_url_wrong_scheme(self, clean_env):
        """Test that REDIS_URL rejects URLs with wrong scheme."""
        clean_env.setenv("REDIS_URL", "http://localhost:6379/0")
        with pytest.raises(ValueError, match="must start with 'redis://'"):
            Settings()

    def test_invalid_redis_url_no_scheme(self, clean_env):
        """Test that REDIS_URL rejects URLs without scheme."""
        clean_env.setenv("REDIS_URL", "localhost:6379/0")
        with pytest.raises(ValueError, match="must start with 'redis://'"):
            Settings()

    def test_invalid_redis_url_missing_host(self, clean_env):
        """Test that REDIS_URL rejects URLs without host."""
        clean_env.setenv("REDIS_URL", "redis:///0")
        with pytest.raises(ValueError, match="missing host"):
            Settings()

    def test_invalid_redis_url_ftp_scheme(self, clean_env):
        """Test that REDIS_URL rejects FTP URLs."""
        clean_env.setenv("REDIS_URL", "ftp://localhost:6379/0")
        with pytest.raises(ValueError, match="must start with 'redis://'"):
            Settings()


class TestRedisSSLSettings:
    """Test Redis SSL/TLS configuration settings."""

    def test_default_redis_ssl_disabled(self, clean_env):
        """Test that Redis SSL is disabled by default."""
        settings = Settings()
        assert settings.redis_ssl_enabled is False

    def test_default_redis_ssl_cert_reqs(self, clean_env):
        """Test that default Redis SSL cert_reqs is 'required'."""
        settings = Settings()
        assert settings.redis_ssl_cert_reqs == "required"

    def test_default_redis_ssl_check_hostname(self, clean_env):
        """Test that default Redis SSL check_hostname is True."""
        settings = Settings()
        assert settings.redis_ssl_check_hostname is True

    def test_default_redis_ssl_paths_are_none(self, clean_env):
        """Test that default Redis SSL certificate paths are None."""
        settings = Settings()
        assert settings.redis_ssl_ca_certs is None
        assert settings.redis_ssl_certfile is None
        assert settings.redis_ssl_keyfile is None

    def test_redis_ssl_enabled_from_env(self, clean_env):
        """Test that REDIS_SSL_ENABLED can be set via environment."""
        clean_env.setenv("REDIS_SSL_ENABLED", "true")
        settings = Settings()
        assert settings.redis_ssl_enabled is True

    def test_redis_ssl_cert_reqs_from_env(self, clean_env):
        """Test that REDIS_SSL_CERT_REQS can be set via environment."""
        clean_env.setenv("REDIS_SSL_CERT_REQS", "none")
        settings = Settings()
        assert settings.redis_ssl_cert_reqs == "none"

    def test_redis_ssl_cert_reqs_optional(self, clean_env):
        """Test that REDIS_SSL_CERT_REQS accepts 'optional'."""
        clean_env.setenv("REDIS_SSL_CERT_REQS", "optional")
        settings = Settings()
        assert settings.redis_ssl_cert_reqs == "optional"

    def test_redis_ssl_cert_reqs_required(self, clean_env):
        """Test that REDIS_SSL_CERT_REQS accepts 'required'."""
        clean_env.setenv("REDIS_SSL_CERT_REQS", "REQUIRED")  # Test case-insensitive
        settings = Settings()
        assert settings.redis_ssl_cert_reqs == "required"

    def test_redis_ssl_cert_reqs_invalid(self, clean_env):
        """Test that invalid REDIS_SSL_CERT_REQS is rejected."""
        clean_env.setenv("REDIS_SSL_CERT_REQS", "invalid_mode")
        with pytest.raises(ValueError, match="redis_ssl_cert_reqs must be one of"):
            Settings()

    def test_redis_ssl_ca_certs_from_env(self, clean_env, tmp_path):
        """Test that REDIS_SSL_CA_CERTS can be set via environment."""
        ca_file = tmp_path / "ca.crt"
        ca_file.write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")
        clean_env.setenv("REDIS_SSL_CA_CERTS", str(ca_file))
        settings = Settings()
        assert settings.redis_ssl_ca_certs == str(ca_file)

    def test_redis_ssl_certfile_from_env(self, clean_env, tmp_path):
        """Test that REDIS_SSL_CERTFILE can be set via environment."""
        # Need both certfile and keyfile together
        cert_file = tmp_path / "client.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")
        key_file = tmp_path / "client.key"
        # Test key content (not a real private key)
        key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"  # pragma: allowlist secret
        )
        clean_env.setenv("REDIS_SSL_CERTFILE", str(cert_file))
        clean_env.setenv("REDIS_SSL_KEYFILE", str(key_file))
        settings = Settings()
        assert settings.redis_ssl_certfile == str(cert_file)

    def test_redis_ssl_keyfile_from_env(self, clean_env, tmp_path):
        """Test that REDIS_SSL_KEYFILE can be set via environment."""
        # Need both certfile and keyfile together
        cert_file = tmp_path / "client.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")
        key_file = tmp_path / "client.key"
        # Test key content (not a real private key)
        key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"  # pragma: allowlist secret
        )
        clean_env.setenv("REDIS_SSL_CERTFILE", str(cert_file))
        clean_env.setenv("REDIS_SSL_KEYFILE", str(key_file))
        settings = Settings()
        assert settings.redis_ssl_keyfile == str(key_file)

    def test_redis_ssl_check_hostname_from_env(self, clean_env):
        """Test that REDIS_SSL_CHECK_HOSTNAME can be set via environment."""
        clean_env.setenv("REDIS_SSL_CHECK_HOSTNAME", "false")
        settings = Settings()
        assert settings.redis_ssl_check_hostname is False

    def test_redis_ssl_full_config(self, clean_env, tmp_path):
        """Test that all Redis SSL settings can be configured together."""
        # Create temp files for SSL paths
        ca_file = tmp_path / "ca.crt"
        ca_file.write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")
        cert_file = tmp_path / "client.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")
        key_file = tmp_path / "client.key"
        # Test key content (not a real private key)
        key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"  # pragma: allowlist secret
        )

        clean_env.setenv("REDIS_SSL_ENABLED", "true")
        clean_env.setenv("REDIS_SSL_CERT_REQS", "required")
        clean_env.setenv("REDIS_SSL_CA_CERTS", str(ca_file))
        clean_env.setenv("REDIS_SSL_CERTFILE", str(cert_file))
        clean_env.setenv("REDIS_SSL_KEYFILE", str(key_file))
        clean_env.setenv("REDIS_SSL_CHECK_HOSTNAME", "true")

        settings = Settings()

        assert settings.redis_ssl_enabled is True
        assert settings.redis_ssl_cert_reqs == "required"
        assert settings.redis_ssl_ca_certs == str(ca_file)
        assert settings.redis_ssl_certfile == str(cert_file)
        assert settings.redis_ssl_keyfile == str(key_file)
        assert settings.redis_ssl_check_hostname is True


class TestOrchestratorSettings:
    """Test container orchestrator configuration settings (NEM-1280)."""

    def test_default_orchestrator_enabled(self, clean_env):
        """Test that orchestrator is enabled by default."""
        settings = Settings()
        assert settings.orchestrator.enabled is True

    def test_default_orchestrator_docker_host(self, clean_env):
        """Test that orchestrator docker_host is None by default."""
        settings = Settings()
        assert settings.orchestrator.docker_host is None

    def test_default_orchestrator_health_check_interval(self, clean_env):
        """Test that orchestrator health_check_interval defaults to 30 seconds."""
        settings = Settings()
        assert settings.orchestrator.health_check_interval == 30

    def test_default_orchestrator_health_check_timeout(self, clean_env):
        """Test that orchestrator health_check_timeout defaults to 5 seconds."""
        settings = Settings()
        assert settings.orchestrator.health_check_timeout == 5

    def test_default_orchestrator_startup_grace_period(self, clean_env):
        """Test that orchestrator startup_grace_period defaults to 60 seconds."""
        settings = Settings()
        assert settings.orchestrator.startup_grace_period == 60

    def test_default_orchestrator_max_consecutive_failures(self, clean_env):
        """Test that orchestrator max_consecutive_failures defaults to 5."""
        settings = Settings()
        assert settings.orchestrator.max_consecutive_failures == 5

    def test_default_orchestrator_restart_backoff_base(self, clean_env):
        """Test that orchestrator restart_backoff_base defaults to 5.0 seconds."""
        settings = Settings()
        assert settings.orchestrator.restart_backoff_base == 5.0

    def test_default_orchestrator_restart_backoff_max(self, clean_env):
        """Test that orchestrator restart_backoff_max defaults to 300.0 seconds."""
        settings = Settings()
        assert settings.orchestrator.restart_backoff_max == 300.0

    def test_orchestrator_enabled_from_env(self, clean_env):
        """Test that ORCHESTRATOR_ENABLED can be set via environment variable."""
        clean_env.setenv("ORCHESTRATOR_ENABLED", "false")
        settings = Settings()
        assert settings.orchestrator.enabled is False

    def test_orchestrator_docker_host_from_env(self, clean_env):
        """Test that ORCHESTRATOR_DOCKER_HOST can be set via environment variable."""
        clean_env.setenv("ORCHESTRATOR_DOCKER_HOST", "unix:///var/run/docker.sock")
        settings = Settings()
        assert settings.orchestrator.docker_host == "unix:///var/run/docker.sock"

    def test_orchestrator_health_check_interval_from_env(self, clean_env):
        """Test that ORCHESTRATOR_HEALTH_CHECK_INTERVAL can be set via environment variable."""
        clean_env.setenv("ORCHESTRATOR_HEALTH_CHECK_INTERVAL", "60")
        settings = Settings()
        assert settings.orchestrator.health_check_interval == 60

    def test_orchestrator_health_check_timeout_from_env(self, clean_env):
        """Test that ORCHESTRATOR_HEALTH_CHECK_TIMEOUT can be set via environment variable."""
        clean_env.setenv("ORCHESTRATOR_HEALTH_CHECK_TIMEOUT", "10")
        settings = Settings()
        assert settings.orchestrator.health_check_timeout == 10

    def test_orchestrator_startup_grace_period_from_env(self, clean_env):
        """Test that ORCHESTRATOR_STARTUP_GRACE_PERIOD can be set via environment variable."""
        clean_env.setenv("ORCHESTRATOR_STARTUP_GRACE_PERIOD", "120")
        settings = Settings()
        assert settings.orchestrator.startup_grace_period == 120

    def test_orchestrator_max_consecutive_failures_from_env(self, clean_env):
        """Test that ORCHESTRATOR_MAX_CONSECUTIVE_FAILURES can be set via environment variable."""
        clean_env.setenv("ORCHESTRATOR_MAX_CONSECUTIVE_FAILURES", "10")
        settings = Settings()
        assert settings.orchestrator.max_consecutive_failures == 10

    def test_orchestrator_restart_backoff_base_from_env(self, clean_env):
        """Test that ORCHESTRATOR_RESTART_BACKOFF_BASE can be set via environment variable."""
        clean_env.setenv("ORCHESTRATOR_RESTART_BACKOFF_BASE", "10.0")
        settings = Settings()
        assert settings.orchestrator.restart_backoff_base == 10.0

    def test_orchestrator_restart_backoff_max_from_env(self, clean_env):
        """Test that ORCHESTRATOR_RESTART_BACKOFF_MAX can be set via environment variable."""
        clean_env.setenv("ORCHESTRATOR_RESTART_BACKOFF_MAX", "600.0")
        settings = Settings()
        assert settings.orchestrator.restart_backoff_max == 600.0

    def test_orchestrator_full_config_from_env(self, clean_env):
        """Test that all orchestrator settings can be configured together."""
        clean_env.setenv("ORCHESTRATOR_ENABLED", "false")
        clean_env.setenv("ORCHESTRATOR_DOCKER_HOST", "tcp://localhost:2375")
        clean_env.setenv("ORCHESTRATOR_HEALTH_CHECK_INTERVAL", "45")
        clean_env.setenv("ORCHESTRATOR_HEALTH_CHECK_TIMEOUT", "15")
        clean_env.setenv("ORCHESTRATOR_STARTUP_GRACE_PERIOD", "90")
        clean_env.setenv("ORCHESTRATOR_MAX_CONSECUTIVE_FAILURES", "3")
        clean_env.setenv("ORCHESTRATOR_RESTART_BACKOFF_BASE", "2.5")
        clean_env.setenv("ORCHESTRATOR_RESTART_BACKOFF_MAX", "180.0")

        settings = Settings()

        assert settings.orchestrator.enabled is False
        assert settings.orchestrator.docker_host == "tcp://localhost:2375"
        assert settings.orchestrator.health_check_interval == 45
        assert settings.orchestrator.health_check_timeout == 15
        assert settings.orchestrator.startup_grace_period == 90
        assert settings.orchestrator.max_consecutive_failures == 3
        assert settings.orchestrator.restart_backoff_base == 2.5
        assert settings.orchestrator.restart_backoff_max == 180.0


class TestRedisPasswordSettings:
    """Test Redis password authentication configuration settings (NEM-1089).

    NOTE: S105/S106 are false positives - these are test fixtures, not real passwords.
    """

    def test_default_redis_password_is_none(self, clean_env):
        """Test that Redis password is None by default (no auth required for local dev)."""
        # Use _env_file=None to test true default value without .env file influence
        settings = Settings(_env_file=None)
        assert settings.redis_password is None

    def test_redis_password_from_env(self, clean_env):
        """Test that REDIS_PASSWORD can be set via environment variable."""
        clean_env.setenv("REDIS_PASSWORD", "my_secure_password")  # pragma: allowlist secret
        settings = Settings()
        assert settings.redis_password == "my_secure_password"  # noqa: S105 - Test fixture  # pragma: allowlist secret

    def test_redis_password_empty_string_is_preserved(self, clean_env):
        """Test that empty string password is preserved as empty string."""
        clean_env.setenv("REDIS_PASSWORD", "")
        settings = Settings()
        # Empty string should be preserved - the connection layer handles this
        assert settings.redis_password == ""

    def test_redis_password_special_characters(self, clean_env):
        """Test that Redis password can contain special characters."""
        special_password = "p@ss!w0rd#123$%^&*()"  # noqa: S105 - Test fixture  # pragma: allowlist secret
        clean_env.setenv("REDIS_PASSWORD", special_password)
        settings = Settings()
        assert settings.redis_password == special_password

    def test_redis_password_with_url_also_set(self, clean_env):
        """Test that Redis password works alongside Redis URL."""
        clean_env.setenv("REDIS_URL", "redis://redis-host:6379/0")
        clean_env.setenv("REDIS_PASSWORD", "secure_password")  # pragma: allowlist secret
        settings = Settings()
        assert settings.redis_url == "redis://redis-host:6379/0"
        assert settings.redis_password == "secure_password"  # noqa: S105 - Test fixture  # pragma: allowlist secret

    def test_redis_password_with_ssl_settings(self, clean_env):
        """Test that Redis password works alongside SSL settings."""
        clean_env.setenv("REDIS_PASSWORD", "secure_password")  # pragma: allowlist secret
        clean_env.setenv("REDIS_SSL_ENABLED", "true")
        clean_env.setenv("REDIS_SSL_CERT_REQS", "none")
        settings = Settings()
        assert settings.redis_password == "secure_password"  # noqa: S105  # pragma: allowlist secret
        assert settings.redis_ssl_enabled is True


class TestTLSCertificatePathValidation:
    """Test TLS certificate path validators (NEM-2024).

    These validators ensure TLS certificate paths are validated at startup
    rather than failing at runtime when paths are invalid.
    """

    def test_tls_cert_path_none_allowed(self, clean_env):
        """Test that None is allowed for tls_cert_path (optional field)."""
        clean_env.delenv("TLS_CERT_PATH", raising=False)
        settings = Settings()
        assert settings.tls_cert_path is None

    def test_tls_key_path_none_allowed(self, clean_env):
        """Test that None is allowed for tls_key_path (optional field)."""
        clean_env.delenv("TLS_KEY_PATH", raising=False)
        settings = Settings()
        assert settings.tls_key_path is None

    def test_tls_cert_path_valid_file(self, clean_env, tmp_path):
        """Test that valid certificate file path passes validation."""
        cert_file = tmp_path / "server.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")
        clean_env.setenv("TLS_CERT_PATH", str(cert_file))
        settings = Settings()
        assert settings.tls_cert_path == str(cert_file)

    def test_tls_key_path_valid_file(self, clean_env, tmp_path):
        """Test that valid key file path passes validation."""
        key_file = tmp_path / "server.key"
        # Test key content (not a real private key)
        key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"  # pragma: allowlist secret
        )
        # Set restrictive permissions (owner read/write only)
        key_file.chmod(0o600)
        clean_env.setenv("TLS_KEY_PATH", str(key_file))
        settings = Settings()
        assert settings.tls_key_path == str(key_file)

    def test_tls_cert_path_missing_file_raises_error(self, clean_env, tmp_path):
        """Test that missing certificate file raises ValueError at startup."""
        nonexistent_path = tmp_path / "does_not_exist.crt"
        clean_env.setenv("TLS_CERT_PATH", str(nonexistent_path))
        with pytest.raises(ValueError, match="Certificate file not found"):
            Settings()

    def test_tls_key_path_missing_file_raises_error(self, clean_env, tmp_path):
        """Test that missing key file raises ValueError at startup."""
        nonexistent_path = tmp_path / "does_not_exist.key"
        clean_env.setenv("TLS_KEY_PATH", str(nonexistent_path))
        with pytest.raises(ValueError, match="Certificate file not found"):
            Settings()

    def test_tls_cert_path_directory_raises_error(self, clean_env, tmp_path):
        """Test that directory path for certificate raises ValueError."""
        cert_dir = tmp_path / "certs"
        cert_dir.mkdir()
        clean_env.setenv("TLS_CERT_PATH", str(cert_dir))
        with pytest.raises(ValueError, match="Certificate path is not a file"):
            Settings()

    def test_tls_key_path_directory_raises_error(self, clean_env, tmp_path):
        """Test that directory path for key raises ValueError."""
        key_dir = tmp_path / "keys"
        key_dir.mkdir()
        clean_env.setenv("TLS_KEY_PATH", str(key_dir))
        with pytest.raises(ValueError, match="Certificate path is not a file"):
            Settings()

    def test_tls_key_world_readable_triggers_warning(self, clean_env, tmp_path):
        """Test that world-readable key file triggers security warning."""
        key_file = tmp_path / "server.key"
        # Test key content (not a real private key)
        key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"  # pragma: allowlist secret
        )
        # Set world-readable permissions (insecure)
        key_file.chmod(0o644)
        clean_env.setenv("TLS_KEY_PATH", str(key_file))

        with pytest.warns(UserWarning, match="TLS key file .* is readable by others"):
            Settings()

    def test_tls_key_group_readable_triggers_warning(self, clean_env, tmp_path):
        """Test that group-readable key file triggers security warning."""
        key_file = tmp_path / "server.key"
        # Test key content (not a real private key)
        key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"  # pragma: allowlist secret
        )
        # Set group-readable permissions (insecure)
        key_file.chmod(0o640)
        clean_env.setenv("TLS_KEY_PATH", str(key_file))

        with pytest.warns(UserWarning, match="TLS key file .* is readable by others"):
            Settings()

    def test_tls_key_owner_only_no_warning(self, clean_env, tmp_path):
        """Test that owner-only permissions do not trigger warning."""
        key_file = tmp_path / "server.key"
        # Test key content (not a real private key)
        key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"  # pragma: allowlist secret
        )
        # Set secure permissions (owner read/write only)
        key_file.chmod(0o600)
        clean_env.setenv("TLS_KEY_PATH", str(key_file))

        # Should NOT emit any warnings
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            settings = Settings()
            assert settings.tls_key_path == str(key_file)

    def test_tls_cert_and_key_both_valid(self, clean_env, tmp_path):
        """Test that both cert and key paths can be validated together."""
        cert_file = tmp_path / "server.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")
        key_file = tmp_path / "server.key"
        # Test key content (not a real private key)
        key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"  # pragma: allowlist secret
        )
        key_file.chmod(0o600)

        clean_env.setenv("TLS_CERT_PATH", str(cert_file))
        clean_env.setenv("TLS_KEY_PATH", str(key_file))

        settings = Settings()
        assert settings.tls_cert_path == str(cert_file)
        assert settings.tls_key_path == str(key_file)

    def test_tls_ca_path_valid_file(self, clean_env, tmp_path):
        """Test that valid CA certificate file path passes validation."""
        ca_file = tmp_path / "ca.crt"
        ca_file.write_text("-----BEGIN CERTIFICATE-----\nca-cert\n-----END CERTIFICATE-----")
        clean_env.setenv("TLS_CA_PATH", str(ca_file))
        settings = Settings()
        assert settings.tls_ca_path == str(ca_file)

    def test_tls_ca_path_missing_file_raises_error(self, clean_env, tmp_path):
        """Test that missing CA certificate file raises ValueError at startup."""
        nonexistent_path = tmp_path / "does_not_exist_ca.crt"
        clean_env.setenv("TLS_CA_PATH", str(nonexistent_path))
        with pytest.raises(ValueError, match="Certificate file not found"):
            Settings()


class TestRedisSSLPathValidation:
    """Test Redis SSL certificate path validation (NEM-2025).

    These tests verify that:
    1. Valid file paths pass validation
    2. Missing files raise ValueError
    3. Partial SSL config (only cert, no key) raises ValueError
    4. Partial SSL config (only key, no cert) raises ValueError
    5. CA certs alone is allowed (for verify-only mode)
    6. All None values are allowed
    """

    def test_redis_ssl_paths_all_none_allowed(self, clean_env):
        """Test that all None values for SSL paths are allowed (default case)."""
        settings = Settings()
        assert settings.redis_ssl_certfile is None
        assert settings.redis_ssl_keyfile is None
        assert settings.redis_ssl_ca_certs is None

    def test_redis_ssl_certfile_valid_path(self, clean_env, tmp_path):
        """Test that a valid certfile path passes validation."""
        # Create a temp cert file
        cert_file = tmp_path / "client.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")
        # Need keyfile too since they must be provided together
        key_file = tmp_path / "client.key"
        # Test key content (not a real private key)
        key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"  # pragma: allowlist secret
        )

        clean_env.setenv("REDIS_SSL_CERTFILE", str(cert_file))
        clean_env.setenv("REDIS_SSL_KEYFILE", str(key_file))
        settings = Settings()
        assert settings.redis_ssl_certfile == str(cert_file)
        assert settings.redis_ssl_keyfile == str(key_file)

    def test_redis_ssl_keyfile_valid_path(self, clean_env, tmp_path):
        """Test that a valid keyfile path passes validation."""
        # Create temp key and cert files (both required together)
        cert_file = tmp_path / "client.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")
        key_file = tmp_path / "client.key"
        # Test key content (not a real private key)
        key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"  # pragma: allowlist secret
        )

        clean_env.setenv("REDIS_SSL_CERTFILE", str(cert_file))
        clean_env.setenv("REDIS_SSL_KEYFILE", str(key_file))
        settings = Settings()
        assert settings.redis_ssl_keyfile == str(key_file)

    def test_redis_ssl_ca_certs_valid_path(self, clean_env, tmp_path):
        """Test that a valid CA certs path passes validation."""
        # Create a temp CA cert file
        ca_file = tmp_path / "ca.crt"
        ca_file.write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")

        clean_env.setenv("REDIS_SSL_CA_CERTS", str(ca_file))
        settings = Settings()
        assert settings.redis_ssl_ca_certs == str(ca_file)

    def test_redis_ssl_ca_certs_alone_is_allowed(self, clean_env, tmp_path):
        """Test that CA certs alone (without cert/key pair) is allowed for verify-only mode."""
        # Create a temp CA cert file
        ca_file = tmp_path / "ca.crt"
        ca_file.write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")

        clean_env.setenv("REDIS_SSL_CA_CERTS", str(ca_file))
        # No certfile or keyfile set
        settings = Settings()
        assert settings.redis_ssl_ca_certs == str(ca_file)
        assert settings.redis_ssl_certfile is None
        assert settings.redis_ssl_keyfile is None

    def test_redis_ssl_certfile_missing_raises_error(self, clean_env):
        """Test that a missing certfile raises ValueError."""
        clean_env.setenv("REDIS_SSL_CERTFILE", "/nonexistent/path/to/client.crt")
        clean_env.setenv("REDIS_SSL_KEYFILE", "/nonexistent/path/to/client.key")
        with pytest.raises(ValueError, match="Redis SSL file not found"):
            Settings()

    def test_redis_ssl_keyfile_missing_raises_error(self, clean_env, tmp_path):
        """Test that a missing keyfile raises ValueError."""
        # Create only the cert file
        cert_file = tmp_path / "client.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")

        clean_env.setenv("REDIS_SSL_CERTFILE", str(cert_file))
        clean_env.setenv("REDIS_SSL_KEYFILE", "/nonexistent/path/to/client.key")
        with pytest.raises(ValueError, match="Redis SSL file not found"):
            Settings()

    def test_redis_ssl_ca_certs_missing_raises_error(self, clean_env):
        """Test that a missing CA certs file raises ValueError."""
        clean_env.setenv("REDIS_SSL_CA_CERTS", "/nonexistent/path/to/ca.crt")
        with pytest.raises(ValueError, match="Redis SSL file not found"):
            Settings()

    def test_redis_ssl_partial_config_certfile_only_raises_error(self, clean_env, tmp_path):
        """Test that providing only certfile (without keyfile) raises ValueError."""
        # Create a temp cert file
        cert_file = tmp_path / "client.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")

        clean_env.setenv("REDIS_SSL_CERTFILE", str(cert_file))
        # No keyfile set
        with pytest.raises(
            ValueError, match="redis_ssl_certfile and redis_ssl_keyfile must be provided together"
        ):
            Settings()

    def test_redis_ssl_partial_config_keyfile_only_raises_error(self, clean_env, tmp_path):
        """Test that providing only keyfile (without certfile) raises ValueError."""
        # Create a temp key file
        key_file = tmp_path / "client.key"
        # Test key content (not a real private key)
        key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"  # pragma: allowlist secret
        )

        clean_env.setenv("REDIS_SSL_KEYFILE", str(key_file))
        # No certfile set
        with pytest.raises(
            ValueError, match="redis_ssl_certfile and redis_ssl_keyfile must be provided together"
        ):
            Settings()

    def test_redis_ssl_full_config_with_all_paths(self, clean_env, tmp_path):
        """Test that a full SSL config with all paths passes validation."""
        # Create temp files
        ca_file = tmp_path / "ca.crt"
        ca_file.write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")
        cert_file = tmp_path / "client.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")
        key_file = tmp_path / "client.key"
        # Test key content (not a real private key)
        key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"  # pragma: allowlist secret
        )

        clean_env.setenv("REDIS_SSL_CA_CERTS", str(ca_file))
        clean_env.setenv("REDIS_SSL_CERTFILE", str(cert_file))
        clean_env.setenv("REDIS_SSL_KEYFILE", str(key_file))

        settings = Settings()
        assert settings.redis_ssl_ca_certs == str(ca_file)
        assert settings.redis_ssl_certfile == str(cert_file)
        assert settings.redis_ssl_keyfile == str(key_file)

    def test_redis_ssl_path_validation_clear_error_message(self, clean_env):
        """Test that error messages clearly indicate which file is missing."""
        nonexistent_path = "/nonexistent/path/to/client.crt"
        clean_env.setenv("REDIS_SSL_CERTFILE", nonexistent_path)
        clean_env.setenv("REDIS_SSL_KEYFILE", "/nonexistent/path/to/client.key")

        with pytest.raises(ValueError) as exc_info:
            Settings()

        # Error message should contain the problematic path
        assert nonexistent_path in str(exc_info.value) or "Redis SSL file not found" in str(
            exc_info.value
        )
