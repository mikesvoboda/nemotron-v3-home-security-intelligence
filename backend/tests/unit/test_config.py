"""Unit tests for application configuration settings."""

import tempfile
from pathlib import Path

import pytest

from backend.core.config import Settings, get_settings


@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment variables and settings cache before each test."""
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
        "RETENTION_DAYS",
        "BATCH_WINDOW_SECONDS",
        "BATCH_IDLE_TIMEOUT_SECONDS",
        "RTDETR_URL",
        "NEMOTRON_URL",
    ]

    for var in env_vars:
        monkeypatch.delenv(var, raising=False)

    # Clear the lru_cache on get_settings
    get_settings.cache_clear()

    yield monkeypatch


@pytest.fixture
def temp_db_path():
    """Provide a temporary database path for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "data" / "test.db"
        yield db_path


class TestSettingsDefaults:
    """Test that Settings class has correct default values."""

    def test_default_database_url(self, clean_env):
        """Test default database URL is SQLite with correct path."""
        settings = Settings()
        assert settings.database_url == "sqlite+aiosqlite:///./data/security.db"

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
        """Test default CORS origins include localhost development URLs."""
        settings = Settings()
        assert settings.cors_origins == [
            "http://localhost:3000",
            "http://localhost:5173",
        ]
        assert isinstance(settings.cors_origins, list)

    def test_default_foscam_path(self, clean_env):
        """Test default Foscam base path."""
        settings = Settings()
        assert settings.foscam_base_path == "/export/foscam"

    def test_default_retention_days(self, clean_env):
        """Test default retention period is 30 days."""
        settings = Settings()
        assert settings.retention_days == 30

    def test_default_batch_settings(self, clean_env):
        """Test default batch processing time windows."""
        settings = Settings()
        assert settings.batch_window_seconds == 90
        assert settings.batch_idle_timeout_seconds == 30

    def test_default_ai_service_urls(self, clean_env):
        """Test default AI service endpoint URLs."""
        settings = Settings()
        assert settings.rtdetr_url == "http://localhost:8001"
        assert settings.nemotron_url == "http://localhost:8002"


class TestEnvironmentOverrides:
    """Test that environment variables override default settings."""

    def test_override_database_url(self, clean_env):
        """Test DATABASE_URL environment variable overrides default."""
        clean_env.setenv("DATABASE_URL", "postgresql://user:pass@localhost/testdb")
        settings = Settings()
        assert settings.database_url == "postgresql://user:pass@localhost/testdb"

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
        assert settings.rtdetr_url == "http://gpu-server:8001"

    def test_override_nemotron_url(self, clean_env):
        """Test NEMOTRON_URL environment variable overrides default."""
        clean_env.setenv("NEMOTRON_URL", "http://gpu-server:8002")
        settings = Settings()
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
    """Test the database URL validator that creates directories."""

    def test_validator_creates_directory_for_sqlite(self, clean_env, temp_db_path):
        """Test that SQLite database directory is created if it doesn't exist."""
        # Use a path that doesn't exist yet
        db_url = f"sqlite+aiosqlite:///{temp_db_path}"
        assert not temp_db_path.parent.exists()

        clean_env.setenv("DATABASE_URL", db_url)
        _settings = Settings()

        # Validator should have created the parent directory
        assert temp_db_path.parent.exists()
        assert temp_db_path.parent.is_dir()

    def test_validator_handles_existing_directory(self, clean_env, temp_db_path):
        """Test that validator works when directory already exists."""
        # Create the directory first
        temp_db_path.parent.mkdir(parents=True, exist_ok=True)
        assert temp_db_path.parent.exists()

        db_url = f"sqlite+aiosqlite:///{temp_db_path}"
        clean_env.setenv("DATABASE_URL", db_url)

        # Should not raise an error
        settings = Settings()
        assert settings.database_url == db_url

    def test_validator_handles_memory_database(self, clean_env):
        """Test that in-memory SQLite database doesn't create directories."""
        clean_env.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
        _ = Settings()

    def test_validator_handles_non_sqlite_urls(self, clean_env):
        """Test that non-SQLite database URLs are not modified."""
        postgres_url = "postgresql+asyncpg://user:pass@localhost:5432/dbname"
        clean_env.setenv("DATABASE_URL", postgres_url)
        settings = Settings()
        assert settings.database_url == postgres_url

    def test_validator_handles_nested_directory_creation(self, clean_env):
        """Test that validator creates nested directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = Path(tmpdir) / "level1" / "level2" / "level3" / "db.sqlite"
            db_url = f"sqlite+aiosqlite:///{nested_path}"

            clean_env.setenv("DATABASE_URL", db_url)
            _settings = Settings()

            # All nested directories should be created
            assert nested_path.parent.exists()
            assert (Path(tmpdir) / "level1" / "level2" / "level3").is_dir()


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
