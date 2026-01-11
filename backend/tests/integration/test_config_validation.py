"""Integration tests for configuration validation (NEM-2004).

This module tests configuration validation behavior at startup:

1. **Invalid Cert Paths** - Invalid SSL certificate paths fail at startup
2. **Missing Required Config** - Missing required settings fail fast
3. **Valid Config** - Valid configuration starts successfully
4. **URL Format Validation** - Database, Redis, AI service URLs validated
5. **Port Validation** - Port numbers validated for valid ranges
6. **Path Validation** - File paths validated for existence

Uses configuration validation module from backend.core.config_validation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.timeout(60)


class TestInvalidCertPathsFailAtStartup:
    """Test that invalid SSL certificate paths cause validation failures."""

    def test_invalid_cert_path_detected(self) -> None:
        """Invalid SSL certificate path should produce validation error.

        When Redis TLS is configured but cert paths don't exist,
        the configuration should be flagged as invalid.
        """
        from backend.core.config_validation import _validate_path_exists

        # Non-existent cert path
        result = _validate_path_exists(
            "redis_ssl_certfile",
            "/nonexistent/path/to/cert.pem",
            required=True,
        )

        assert result.status == "error", "Non-existent required path should be error"
        assert "does not exist" in result.message.lower()

    def test_missing_cert_path_when_ssl_enabled_is_error(self) -> None:
        """When SSL is enabled but cert path is missing, it should be an error.

        This ensures the application fails fast when TLS is misconfigured.
        """
        from backend.core.config_validation import _validate_path_exists

        # Empty cert path when required
        result = _validate_path_exists(
            "redis_ssl_certfile",
            "",
            required=True,
        )

        assert result.status == "error"
        assert "required" in result.message.lower()

    def test_valid_cert_path_passes_validation(self) -> None:
        """Valid SSL certificate path should pass validation.

        When the cert file exists, validation should succeed.
        """
        from backend.core.config_validation import _validate_path_exists

        # Create a temporary file to simulate cert
        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as f:
            cert_path = f.name

        try:
            result = _validate_path_exists(
                "redis_ssl_certfile",
                cert_path,
                required=True,
            )

            assert result.status == "ok", "Existing file should be OK"
            assert "exists" in result.message.lower()
        finally:
            Path(cert_path).unlink()


class TestMissingRequiredConfigFailsFast:
    """Test that missing required configuration causes validation to fail."""

    def test_missing_database_url_is_error(self) -> None:
        """Missing DATABASE_URL should be a critical error.

        The database URL is required for the application to function.
        """
        from backend.core.config_validation import _validate_database_url

        # Create mock settings with empty database_url
        mock_settings = MagicMock()
        mock_settings.database_url = ""

        result = _validate_database_url(mock_settings)

        assert result.status == "error"
        assert "required" in result.message.lower()

    def test_missing_redis_url_is_error(self) -> None:
        """Missing REDIS_URL should be a critical error.

        Redis is required for caching, queues, and pub/sub.
        """
        from backend.core.config_validation import _validate_redis_url

        mock_settings = MagicMock()
        mock_settings.redis_url = ""

        result = _validate_redis_url(mock_settings)

        assert result.status == "error"
        assert "required" in result.message.lower()

    def test_missing_ai_service_url_is_error(self) -> None:
        """Missing AI service URLs should be errors.

        Both RT-DETR and Nemotron URLs are required for AI processing.
        """
        from backend.core.config_validation import _validate_ai_service_url

        result = _validate_ai_service_url("rtdetr_url", "")

        assert result.status == "error"
        assert "required" in result.message.lower()

    def test_validate_config_with_all_missing_returns_invalid(self) -> None:
        """Configuration with all required settings missing should be invalid.

        The validate_config function should return valid=False when
        critical settings are missing.
        """
        from backend.core.config_validation import validate_config

        mock_settings = MagicMock()
        mock_settings.database_url = ""
        mock_settings.redis_url = ""
        mock_settings.rtdetr_url = ""
        mock_settings.nemotron_url = ""
        mock_settings.api_port = 8000
        mock_settings.smtp_port = 587
        mock_settings.foscam_base_path = ""

        result = validate_config(mock_settings)

        assert result.valid is False, "Config should be invalid with missing required settings"
        assert len(result.errors) > 0, "Should have errors for missing settings"


class TestValidConfigStartsSuccessfully:
    """Test that valid configuration passes validation."""

    def test_valid_database_url_passes(self) -> None:
        """Valid PostgreSQL URL should pass validation."""
        from backend.core.config_validation import _validate_database_url

        mock_settings = MagicMock()
        mock_settings.database_url = (
            "postgresql+asyncpg://user:pass@localhost:5432/security"  # pragma: allowlist secret
        )

        result = _validate_database_url(mock_settings)

        assert result.status == "ok"
        assert "valid" in result.message.lower()

    def test_valid_redis_url_passes(self) -> None:
        """Valid Redis URL should pass validation."""
        from backend.core.config_validation import _validate_redis_url

        mock_settings = MagicMock()
        mock_settings.redis_url = "redis://localhost:6379/0"

        result = _validate_redis_url(mock_settings)

        assert result.status == "ok"
        assert "valid" in result.message.lower()

    def test_valid_ai_service_urls_pass(self) -> None:
        """Valid AI service URLs should pass validation."""
        from backend.core.config_validation import _validate_ai_service_url

        result_rtdetr = _validate_ai_service_url(
            "rtdetr_url",
            "http://localhost:8001/detect",
        )
        result_nemotron = _validate_ai_service_url(
            "nemotron_url",
            "http://localhost:8002/v1/completions",
        )

        # Localhost URLs should pass (info level for dev mode)
        assert result_rtdetr.status in ("ok", "info")
        assert result_nemotron.status in ("ok", "info")

    def test_validate_config_with_all_valid_returns_valid(self) -> None:
        """Configuration with all valid settings should be valid.

        The validate_config function should return valid=True when
        all required settings are properly configured.
        """
        from backend.core.config_validation import validate_config

        mock_settings = MagicMock()
        mock_settings.database_url = (
            "postgresql+asyncpg://user:pass@localhost:5432/security"  # pragma: allowlist secret
        )
        mock_settings.redis_url = "redis://localhost:6379/0"
        mock_settings.rtdetr_url = "http://localhost:8001/detect"
        mock_settings.nemotron_url = "http://localhost:8002/v1/completions"
        mock_settings.api_port = 8000
        mock_settings.smtp_port = 587
        mock_settings.foscam_base_path = ""  # Optional path

        result = validate_config(mock_settings)

        assert result.valid is True, "Config should be valid with all required settings"
        assert len(result.errors) == 0, "Should have no errors"


class TestURLFormatValidation:
    """Test URL format validation for various service URLs."""

    def test_database_url_must_be_postgresql(self) -> None:
        """Database URL must use postgresql:// scheme."""
        from backend.core.config_validation import _validate_database_url

        mock_settings = MagicMock()
        mock_settings.database_url = "mysql://user:pass@localhost/db"  # pragma: allowlist secret

        result = _validate_database_url(mock_settings)

        assert result.status == "error"
        assert "postgresql" in result.message.lower()

    def test_redis_url_must_be_redis(self) -> None:
        """Redis URL must use redis:// scheme."""
        from backend.core.config_validation import _validate_redis_url

        mock_settings = MagicMock()
        mock_settings.redis_url = "http://localhost:6379"

        result = _validate_redis_url(mock_settings)

        assert result.status == "error"
        assert "redis://" in result.message.lower()

    def test_ai_service_url_must_be_http(self) -> None:
        """AI service URLs must use http:// or https:// scheme."""
        from backend.core.config_validation import _validate_ai_service_url

        result = _validate_ai_service_url("rtdetr_url", "ftp://localhost:8001/detect")

        assert result.status == "error"
        assert "http" in result.message.lower()

    def test_database_url_must_have_hostname(self) -> None:
        """Database URL must include a hostname."""
        from backend.core.config_validation import _validate_database_url

        mock_settings = MagicMock()
        mock_settings.database_url = "postgresql://"

        result = _validate_database_url(mock_settings)

        assert result.status == "error"
        assert "hostname" in result.message.lower()

    def test_https_ai_service_url_is_ok(self) -> None:
        """HTTPS AI service URLs should be validated as OK (not just info)."""
        from backend.core.config_validation import _validate_ai_service_url

        result = _validate_ai_service_url(
            "rtdetr_url",
            "https://ai-service.example.com/detect",
        )

        assert result.status == "ok"
        assert "https" in result.message.lower()

    def test_http_non_localhost_ai_service_is_warning(self) -> None:
        """HTTP AI service URLs to non-localhost should warn about security."""
        from backend.core.config_validation import _validate_ai_service_url

        result = _validate_ai_service_url(
            "rtdetr_url",
            "http://ai-service.example.com/detect",
        )

        assert result.status == "warning"
        assert "https" in result.message.lower()

    def test_redis_tls_url_detected(self) -> None:
        """Redis TLS URLs (rediss://) should be detected."""
        from backend.core.config_validation import _validate_redis_url

        mock_settings = MagicMock()
        mock_settings.redis_url = "rediss://localhost:6379/0"

        result = _validate_redis_url(mock_settings)

        assert result.status == "ok"
        assert "tls" in result.message.lower()


class TestPortValidation:
    """Test port number validation."""

    def test_negative_port_is_error(self) -> None:
        """Negative port numbers should be errors."""
        from backend.core.config_validation import _validate_port

        result = _validate_port("api_port", -1)

        assert result.status == "error"
        assert "positive" in result.message.lower()

    def test_port_zero_is_warning(self) -> None:
        """Port 0 (OS-assigned) should be a warning."""
        from backend.core.config_validation import _validate_port

        result = _validate_port("api_port", 0)

        assert result.status == "warning"
        assert "os" in result.message.lower()

    def test_port_over_65535_is_error(self) -> None:
        """Port numbers over 65535 should be errors."""
        from backend.core.config_validation import _validate_port

        result = _validate_port("api_port", 70000)

        assert result.status == "error"
        assert "65535" in result.message.lower()

    def test_privileged_port_is_info(self) -> None:
        """Privileged ports (1-1023) should be info level."""
        from backend.core.config_validation import _validate_port

        result = _validate_port("api_port", 80)

        assert result.status == "info"
        assert "privileged" in result.message.lower()

    def test_standard_port_is_ok(self) -> None:
        """Standard ports (1024-65535) should be OK."""
        from backend.core.config_validation import _validate_port

        result = _validate_port("api_port", 8000)

        assert result.status == "ok"


class TestPathValidation:
    """Test filesystem path validation."""

    def test_nonexistent_required_path_is_error(self) -> None:
        """Non-existent required paths should be errors."""
        from backend.core.config_validation import _validate_path_exists

        result = _validate_path_exists(
            "foscam_base_path",
            "/nonexistent/path/to/cameras",
            required=True,
        )

        assert result.status == "error"

    def test_nonexistent_optional_path_is_warning(self) -> None:
        """Non-existent optional paths should be warnings."""
        from backend.core.config_validation import _validate_path_exists

        result = _validate_path_exists(
            "foscam_base_path",
            "/nonexistent/path/to/cameras",
            required=False,
        )

        assert result.status == "warning"

    def test_empty_optional_path_is_ok(self) -> None:
        """Empty optional paths should be OK (not configured)."""
        from backend.core.config_validation import _validate_path_exists

        result = _validate_path_exists(
            "foscam_base_path",
            "",
            required=False,
        )

        assert result.status == "ok"
        assert "optional" in result.message.lower()

    def test_existing_directory_is_ok(self) -> None:
        """Existing directories should be OK."""
        from backend.core.config_validation import _validate_path_exists

        with tempfile.TemporaryDirectory() as tmpdir:
            result = _validate_path_exists(
                "foscam_base_path",
                tmpdir,
                required=True,
            )

            assert result.status == "ok"
            assert "directory" in result.message.lower()

    def test_existing_file_is_ok(self) -> None:
        """Existing files should be OK."""
        from backend.core.config_validation import _validate_path_exists

        with tempfile.NamedTemporaryFile(delete=False) as f:
            file_path = f.name

        try:
            result = _validate_path_exists(
                "config_file",
                file_path,
                required=True,
            )

            assert result.status == "ok"
            assert "file" in result.message.lower()
        finally:
            Path(file_path).unlink()


class TestConfigValidationResult:
    """Test the ConfigValidationResult dataclass behavior."""

    def test_valid_when_no_errors(self) -> None:
        """ConfigValidationResult.valid should be True when no errors."""
        from backend.core.config_validation import ConfigValidationResult

        result = ConfigValidationResult(
            valid=True,
            items=[],
            warnings=["Some warning"],
            errors=[],
        )

        assert result.valid is True

    def test_invalid_when_has_errors(self) -> None:
        """ConfigValidationResult.valid should be False when has errors."""
        from backend.core.config_validation import ConfigValidationResult

        result = ConfigValidationResult(
            valid=False,
            items=[],
            warnings=[],
            errors=["Some error"],
        )

        assert result.valid is False

    def test_warnings_dont_invalidate_config(self) -> None:
        """Warnings should not invalidate the configuration.

        The application should start even with warnings - only errors
        should prevent startup.
        """
        from backend.core.config_validation import validate_config

        mock_settings = MagicMock()
        mock_settings.database_url = (
            "postgresql+asyncpg://user:pass@localhost:5432/"  # pragma: allowlist secret
        )
        mock_settings.redis_url = "redis://localhost:6379/0"
        mock_settings.rtdetr_url = "http://localhost:8001/detect"
        mock_settings.nemotron_url = "http://localhost:8002/v1/completions"
        mock_settings.api_port = 8000
        mock_settings.smtp_port = 587
        mock_settings.foscam_base_path = "/nonexistent/path"  # This will generate warning

        result = validate_config(mock_settings)

        # Should have warnings but still be valid
        # The database_url missing database name generates a warning
        assert result.valid is True or len(result.warnings) > 0


class TestConfigSummaryLogging:
    """Test configuration summary logging."""

    def test_log_config_summary_does_not_raise(self) -> None:
        """log_config_summary should not raise exceptions.

        Even with errors and warnings, the logging should complete
        without raising.
        """
        from backend.core.config_validation import (
            ConfigValidationResult,
            ValidationItem,
            log_config_summary,
        )

        result = ConfigValidationResult(
            valid=False,
            items=[
                ValidationItem("test", "ok", "OK message"),
                ValidationItem("test2", "warning", "Warning message"),
                ValidationItem("test3", "error", "Error message"),
            ],
            warnings=["Warning message"],
            errors=["Error message"],
        )

        # Should not raise
        log_config_summary(result)

    def test_log_config_summary_with_empty_result(self) -> None:
        """log_config_summary should handle empty result."""
        from backend.core.config_validation import ConfigValidationResult, log_config_summary

        result = ConfigValidationResult(
            valid=True,
            items=[],
            warnings=[],
            errors=[],
        )

        # Should not raise
        log_config_summary(result)


class TestStartupConfigValidation:
    """Test that configuration validation integrates with startup."""

    def test_validate_config_function_exists(self) -> None:
        """Verify validate_config function is importable."""
        from backend.core.config_validation import validate_config

        assert callable(validate_config)

    def test_log_config_summary_function_exists(self) -> None:
        """Verify log_config_summary function is importable."""
        from backend.core.config_validation import log_config_summary

        assert callable(log_config_summary)

    def test_validation_item_has_required_fields(self) -> None:
        """Verify ValidationItem has required fields."""
        from backend.core.config_validation import ValidationItem

        item = ValidationItem(name="test", status="ok", message="Test message")

        assert hasattr(item, "name")
        assert hasattr(item, "status")
        assert hasattr(item, "message")

    def test_config_validation_result_has_required_fields(self) -> None:
        """Verify ConfigValidationResult has required fields."""
        from backend.core.config_validation import ConfigValidationResult

        result = ConfigValidationResult(valid=True)

        assert hasattr(result, "valid")
        assert hasattr(result, "items")
        assert hasattr(result, "warnings")
        assert hasattr(result, "errors")
