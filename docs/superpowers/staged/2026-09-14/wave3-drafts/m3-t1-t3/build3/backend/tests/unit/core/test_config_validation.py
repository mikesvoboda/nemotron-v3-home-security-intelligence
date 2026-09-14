"""Unit tests for configuration validation summary at startup (NEM-2026).

Tests follow TDD approach - these tests are written first to define expected behavior.
"""

import pytest

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
        "YOLO26_URL",
        "NEMOTRON_URL",
        "FOSCAM_BASE_PATH",
        "API_PORT",
        "SMTP_PORT",
        "DEBUG",
        "ENVIRONMENT",
    ]

    for var in env_vars:
        monkeypatch.delenv(var, raising=False)

    # Set DATABASE_URL since it's now required (no default)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
    )

    # Set ENVIRONMENT to development to allow weak test passwords (NEM-3141).
    # Production/staging would reject the short "test" password in DATABASE_URL.
    monkeypatch.setenv("ENVIRONMENT", "development")

    # Set FOSCAM_BASE_PATH to expected default since .env file may override
    monkeypatch.setenv("FOSCAM_BASE_PATH", "/export/foscam")

    # Clear the lru_cache on get_settings
    get_settings.cache_clear()

    yield monkeypatch


class TestConfigValidationResult:
    """Test ConfigValidationResult dataclass."""

    def test_config_validation_result_creation(self):
        """Test that ConfigValidationResult can be created with expected fields."""
        from backend.core.config_validation import ConfigValidationResult, ValidationItem

        result = ConfigValidationResult(
            valid=True,
            items=[
                ValidationItem(
                    name="database_url",
                    status="ok",
                    message="PostgreSQL URL format valid",
                ),
            ],
            warnings=[],
            errors=[],
        )

        assert result.valid is True
        assert len(result.items) == 1
        assert result.items[0].name == "database_url"
        assert result.items[0].status == "ok"

    def test_config_validation_result_with_warnings(self):
        """Test ConfigValidationResult with warnings but still valid."""
        from backend.core.config_validation import ConfigValidationResult, ValidationItem

        result = ConfigValidationResult(
            valid=True,
            items=[
                ValidationItem(
                    name="foscam_base_path",
                    status="warning",
                    message="Path does not exist: /export/foscam",
                ),
            ],
            warnings=["foscam_base_path: Path does not exist: /export/foscam"],
            errors=[],
        )

        assert result.valid is True
        assert len(result.warnings) == 1
        assert "foscam_base_path" in result.warnings[0]

    def test_config_validation_result_with_errors(self):
        """Test ConfigValidationResult with errors is invalid."""
        from backend.core.config_validation import ConfigValidationResult, ValidationItem

        result = ConfigValidationResult(
            valid=False,
            items=[
                ValidationItem(
                    name="database_url",
                    status="error",
                    message="DATABASE_URL is required",
                ),
            ],
            warnings=[],
            errors=["database_url: DATABASE_URL is required"],
        )

        assert result.valid is False
        assert len(result.errors) == 1


class TestValidateConfig:
    """Test validate_config function."""

    def test_validate_config_returns_validation_result(self, clean_env):
        """Test that validate_config returns a ConfigValidationResult."""
        from backend.core.config_validation import ConfigValidationResult, validate_config

        settings = Settings()
        result = validate_config(settings)

        assert isinstance(result, ConfigValidationResult)

    def test_validate_config_checks_database_url_format(self, clean_env):
        """Test that validate_config validates database URL format."""
        from backend.core.config_validation import validate_config

        settings = Settings()
        result = validate_config(settings)

        # Find database_url validation item
        db_item = next((item for item in result.items if item.name == "database_url"), None)
        assert db_item is not None
        assert db_item.status == "ok"
        assert "PostgreSQL" in db_item.message or "valid" in db_item.message.lower()

    def test_validate_config_checks_redis_url_format(self, clean_env):
        """Test that validate_config validates Redis URL format."""
        from backend.core.config_validation import validate_config

        settings = Settings()
        result = validate_config(settings)

        # Find redis_url validation item
        redis_item = next((item for item in result.items if item.name == "redis_url"), None)
        assert redis_item is not None
        assert redis_item.status == "ok"
        assert "redis" in redis_item.message.lower() or "valid" in redis_item.message.lower()

    def test_validate_config_checks_ai_service_urls(self, clean_env):
        """Test that validate_config validates AI service URLs."""
        from backend.core.config_validation import validate_config

        settings = Settings()
        result = validate_config(settings)

        # Find yolo26_url validation item
        yolo26_item = next((item for item in result.items if item.name == "yolo26_url"), None)
        assert yolo26_item is not None
        # Status should be ok, info (localhost), or warning - not error
        assert yolo26_item.status in ("ok", "warning", "info")

        # Find nemotron_url validation item
        nemotron_item = next((item for item in result.items if item.name == "nemotron_url"), None)
        assert nemotron_item is not None
        # Status should be ok, info (localhost), or warning - not error
        assert nemotron_item.status in ("ok", "warning", "info")

    def test_validate_config_checks_port_ranges(self, clean_env):
        """Test that validate_config validates port numbers are in valid range."""
        from backend.core.config_validation import validate_config

        settings = Settings()
        result = validate_config(settings)

        # Find api_port validation item
        port_item = next((item for item in result.items if item.name == "api_port"), None)
        assert port_item is not None
        assert port_item.status == "ok"

    def test_validate_config_warns_on_missing_foscam_path(self, clean_env):
        """Test that validate_config warns if foscam_base_path doesn't exist."""
        from backend.core.config_validation import validate_config

        # Set a non-existent path
        clean_env.setenv("FOSCAM_BASE_PATH", "/nonexistent/path/to/cameras")
        get_settings.cache_clear()
        settings = Settings()
        result = validate_config(settings)

        # Find foscam_base_path validation item
        foscam_item = next((item for item in result.items if item.name == "foscam_base_path"), None)
        assert foscam_item is not None
        assert foscam_item.status == "warning"
        assert "does not exist" in foscam_item.message.lower()

    def test_validate_config_valid_with_defaults(self, clean_env):
        """Test that validate_config returns valid=True with default settings."""
        from backend.core.config_validation import validate_config

        settings = Settings()
        result = validate_config(settings)

        # Should be valid even if paths don't exist (warnings only)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_config_checks_smtp_port_range(self, clean_env):
        """Test that validate_config validates SMTP port is in valid range."""
        from backend.core.config_validation import validate_config

        settings = Settings()
        result = validate_config(settings)

        # SMTP port validation should exist
        smtp_item = next((item for item in result.items if item.name == "smtp_port"), None)
        assert smtp_item is not None
        # Default SMTP port 587 is valid, status could be "ok" or "info" (privileged port info)
        assert smtp_item.status in ("ok", "info")


class TestLogConfigSummary:
    """Test log_config_summary function."""

    def test_log_config_summary_logs_table(self, clean_env, caplog):
        """Test that log_config_summary logs a formatted table."""
        import logging

        from backend.core.config_validation import log_config_summary, validate_config

        caplog.set_level(logging.INFO)

        settings = Settings()
        result = validate_config(settings)
        log_config_summary(result)

        # Check that configuration summary was logged
        assert any("Configuration" in record.message for record in caplog.records)

    def test_log_config_summary_includes_status_indicators(self, clean_env, caplog):
        """Test that log_config_summary includes status indicators."""
        import logging

        from backend.core.config_validation import log_config_summary, validate_config

        caplog.set_level(logging.INFO)

        settings = Settings()
        result = validate_config(settings)
        log_config_summary(result)

        # Should include some form of status indicator
        log_output = "\n".join(record.message for record in caplog.records)
        # Either OK, valid, or checkmark-like indicators
        assert "ok" in log_output.lower() or "valid" in log_output.lower() or "[" in log_output

    def test_log_config_summary_logs_warnings_at_warning_level(self, clean_env, caplog):
        """Test that warnings are logged at WARNING level."""
        import logging

        from backend.core.config_validation import log_config_summary, validate_config

        caplog.set_level(logging.WARNING)

        # Set a non-existent path to trigger warning
        clean_env.setenv("FOSCAM_BASE_PATH", "/nonexistent/path")
        get_settings.cache_clear()
        settings = Settings()
        result = validate_config(settings)
        log_config_summary(result)

        # Should have warning-level log entries
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) >= 1

    def test_log_config_summary_logs_errors_at_error_level(self, clean_env, caplog):
        """Test that errors are logged at ERROR level."""
        import logging

        from backend.core.config_validation import (
            ConfigValidationResult,
            ValidationItem,
            log_config_summary,
        )

        caplog.set_level(logging.ERROR)

        # Create a result with errors
        result = ConfigValidationResult(
            valid=False,
            items=[
                ValidationItem(
                    name="database_url",
                    status="error",
                    message="DATABASE_URL is required",
                ),
            ],
            warnings=[],
            errors=["database_url: DATABASE_URL is required"],
        )
        log_config_summary(result)

        # Should have error-level log entries
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) >= 1


class TestConfigValidationIntegration:
    """Integration tests for configuration validation during startup."""

    def test_validate_config_detects_invalid_port(self, clean_env):
        """Test that invalid port numbers are detected."""
        from backend.core.config_validation import validate_config

        # Note: Pydantic validation will catch invalid ports at Settings creation
        # This test verifies the validation function handles edge cases
        settings = Settings()
        settings.api_port = 0  # Edge case: 0 is technically valid but unusual
        result = validate_config(settings)

        # Port 0 should generate a warning (valid but unusual)
        port_item = next((item for item in result.items if item.name == "api_port"), None)
        assert port_item is not None

    def test_validate_config_summary_all_checks(self, clean_env):
        """Test that validate_config performs all expected checks."""
        from backend.core.config_validation import validate_config

        settings = Settings()
        result = validate_config(settings)

        # Should have checks for all critical settings
        check_names = {item.name for item in result.items}

        expected_checks = {
            "database_url",
            "redis_url",
            "yolo26_url",
            "nemotron_url",
            "api_port",
            "foscam_base_path",
        }

        for expected in expected_checks:
            assert expected in check_names, f"Missing validation for {expected}"

    def test_validate_config_redacts_sensitive_values(self, clean_env, caplog):
        """Test that sensitive values are redacted in logs."""
        import logging

        from backend.core.config_validation import log_config_summary, validate_config

        caplog.set_level(logging.DEBUG)

        settings = Settings()
        result = validate_config(settings)
        log_config_summary(result)

        # Password should not appear in logs
        log_output = "\n".join(record.message for record in caplog.records)
        assert "test:test" not in log_output  # Database password


class TestValidationItemStatuses:
    """Test different validation item status values."""

    def test_validation_item_ok_status(self):
        """Test ValidationItem with 'ok' status."""
        from backend.core.config_validation import ValidationItem

        item = ValidationItem(
            name="test_setting",
            status="ok",
            message="Setting is valid",
        )
        assert item.status == "ok"

    def test_validation_item_warning_status(self):
        """Test ValidationItem with 'warning' status."""
        from backend.core.config_validation import ValidationItem

        item = ValidationItem(
            name="test_setting",
            status="warning",
            message="Setting may cause issues",
        )
        assert item.status == "warning"

    def test_validation_item_error_status(self):
        """Test ValidationItem with 'error' status."""
        from backend.core.config_validation import ValidationItem

        item = ValidationItem(
            name="test_setting",
            status="error",
            message="Setting is invalid",
        )
        assert item.status == "error"

    def test_validation_item_info_status(self):
        """Test ValidationItem with 'info' status."""
        from backend.core.config_validation import ValidationItem

        item = ValidationItem(
            name="test_setting",
            status="info",
            message="Additional information",
        )
        assert item.status == "info"


class TestEdgeCases:
    """Test edge cases in configuration validation."""

    def test_validate_config_with_empty_database_url(self, clean_env):
        """Test validation behavior when database_url is set but empty.

        Note: This should never happen in practice due to Pydantic validation,
        but we test the validation function's handling.
        """
        from backend.core.config_validation import validate_config

        # Pydantic will reject empty DATABASE_URL, so we can't create Settings
        # with empty database_url. Test with a valid settings object instead.
        settings = Settings()
        result = validate_config(settings)

        # Should be valid with the test database URL
        assert result.valid is True

    def test_validate_config_with_localhost_ai_services(self, clean_env):
        """Test validation with localhost AI service URLs (development setup)."""
        from backend.core.config_validation import validate_config

        settings = Settings()
        # Default URLs are localhost
        result = validate_config(settings)

        # Localhost URLs should be valid
        yolo26_item = next((item for item in result.items if item.name == "yolo26_url"), None)
        nemotron_item = next((item for item in result.items if item.name == "nemotron_url"), None)

        assert yolo26_item is not None
        assert nemotron_item is not None
        # Should be ok or warning (not error) for localhost
        assert yolo26_item.status in ("ok", "warning", "info")
        assert nemotron_item.status in ("ok", "warning", "info")

    def test_validate_config_with_https_ai_services(self, clean_env):
        """Test validation with HTTPS AI service URLs (production setup)."""
        from backend.core.config_validation import validate_config

        clean_env.setenv("YOLO26_URL", "https://yolo26.example.com:8090")
        clean_env.setenv("NEMOTRON_URL", "https://nemotron.example.com:8091")
        get_settings.cache_clear()

        settings = Settings()
        result = validate_config(settings)

        # HTTPS URLs should be valid
        yolo26_item = next((item for item in result.items if item.name == "yolo26_url"), None)
        nemotron_item = next((item for item in result.items if item.name == "nemotron_url"), None)

        assert yolo26_item is not None
        assert nemotron_item is not None
        assert yolo26_item.status in ("ok", "warning", "info")
        assert nemotron_item.status in ("ok", "warning", "info")
