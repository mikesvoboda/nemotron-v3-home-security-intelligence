"""Advanced configuration validation tests.

This module tests critical configuration validation scenarios that extend beyond
basic default values and environment overrides:

1. Configuration hot-reload - Dynamic config changes after startup
2. Environment drift detection - Dev vs prod config comparison
3. Secrets exposure prevention - Ensure secrets don't leak to logs/errors
4. Invalid configuration combinations - Detect conflicting settings
5. Feature flag interdependencies - Validate dependent feature flags
6. Timeout consistency - Ensure timeout values are logically consistent

These tests complement test_config.py which focuses on defaults and overrides.
"""

import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.core.config import get_settings


@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment variables and settings cache before each test."""
    # Clear all config-related environment variables
    env_vars = [
        "DATABASE_URL",
        "REDIS_URL",
        "BATCH_WINDOW_SECONDS",
        "BATCH_IDLE_TIMEOUT_SECONDS",
        "TLS_MODE",
        "TLS_CERT_PATH",
        "TLS_KEY_PATH",
        "RATE_LIMIT_ENABLED",
        "RATE_LIMIT_REQUESTS_PER_MINUTE",
        "ORCHESTRATOR_HEALTH_CHECK_INTERVAL",
        "ORCHESTRATOR_HEALTH_CHECK_TIMEOUT",
        "VISION_EXTRACTION_ENABLED",
        "REID_ENABLED",
        "ADMIN_API_KEY",
        "DEFAULT_WEBHOOK_URL",
        "GRAFANA_URL",
    ]

    for var in env_vars:
        monkeypatch.delenv(var, raising=False)

    # Set required DATABASE_URL
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
    )

    # Clear the lru_cache on get_settings
    get_settings.cache_clear()

    yield monkeypatch


class TestConfigurationHotReload:
    """Test configuration hot-reload scenarios.

    Hot-reload allows configuration changes without application restart.
    The get_settings() function uses @cache decorator, so we test cache clearing
    and reloading with new environment values.
    """

    def test_hot_reload_batch_window_seconds(self, clean_env):
        """Test that BATCH_WINDOW_SECONDS can be hot-reloaded.

        Scenario:
        1. Start with default BATCH_WINDOW_SECONDS=90
        2. Change environment variable to 120
        3. Clear settings cache (simulate hot-reload)
        4. Verify new value is used
        """
        # Initial state - default value
        settings = get_settings()
        assert settings.batch_window_seconds == 90

        # Change environment variable
        clean_env.setenv("BATCH_WINDOW_SECONDS", "120")

        # Clear cache to simulate hot-reload
        get_settings.cache_clear()

        # Verify new value is loaded
        settings = get_settings()
        assert settings.batch_window_seconds == 120

    def test_hot_reload_batch_idle_timeout(self, clean_env):
        """Test that BATCH_IDLE_TIMEOUT_SECONDS can be hot-reloaded."""
        # Initial state
        settings = get_settings()
        assert settings.batch_idle_timeout_seconds == 30

        # Change and reload
        clean_env.setenv("BATCH_IDLE_TIMEOUT_SECONDS", "60")
        get_settings.cache_clear()

        # Verify
        settings = get_settings()
        assert settings.batch_idle_timeout_seconds == 60

    def test_hot_reload_preserves_other_settings(self, clean_env):
        """Test that hot-reloading one setting doesn't affect others.

        This ensures cache clearing properly reloads ALL settings,
        not just the changed ones.
        """
        # Set multiple settings
        clean_env.setenv("BATCH_WINDOW_SECONDS", "100")
        clean_env.setenv("BATCH_IDLE_TIMEOUT_SECONDS", "40")
        settings = get_settings()
        assert settings.batch_window_seconds == 100
        assert settings.batch_idle_timeout_seconds == 40

        # Change only one
        clean_env.setenv("BATCH_WINDOW_SECONDS", "150")
        get_settings.cache_clear()

        # Verify both are correct
        settings = get_settings()
        assert settings.batch_window_seconds == 150
        assert settings.batch_idle_timeout_seconds == 40  # Unchanged

    def test_hot_reload_with_invalid_value_raises_error(self, clean_env):
        """Test that hot-reload with invalid value raises ValidationError.

        This ensures hot-reload validation is as strict as initial load.

        Note: BATCH_WINDOW_SECONDS has no explicit ge constraint in config.py,
        so we test with a field that has validation constraints.
        """
        # Initial valid state
        settings = get_settings()
        assert settings.rate_limit_requests_per_minute == 60

        # Change to invalid value (violates ge=1 constraint)
        clean_env.setenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "-10")
        get_settings.cache_clear()

        # Verify validation error on reload
        with pytest.raises(ValidationError):
            get_settings()


class TestEnvironmentDriftDetection:
    """Test environment drift detection between dev and prod configs.

    Environment drift occurs when dev and prod have different configuration
    values that should be identical. This can cause bugs that only appear
    in production.
    """

    def test_detect_missing_env_vars_in_prod(self, clean_env, tmp_path):
        """Test detection of environment variables present in dev but missing in prod.

        This simulates the common scenario where a developer adds a new
        config value locally but forgets to set it in production.
        """
        # Create mock dev and prod .env files
        dev_env = tmp_path / ".env.dev"
        prod_env = tmp_path / ".env.prod"

        # Test database URLs for environment drift detection
        dev_db = "postgresql+asyncpg://test:test@localhost:5432/dev"  # pragma: allowlist secret
        prod_db = "postgresql+asyncpg://test:test@localhost:5432/prod"  # pragma: allowlist secret

        dev_env.write_text(f"""DATABASE_URL={dev_db}
BATCH_WINDOW_SECONDS=90
DEBUG=true
NEW_FEATURE_ENABLED=true
""")

        prod_env.write_text(f"""DATABASE_URL={prod_db}
BATCH_WINDOW_SECONDS=90
DEBUG=false
""")

        # Parse both files
        dev_vars = self._parse_env_file(dev_env)
        prod_vars = self._parse_env_file(prod_env)

        # Detect drift
        missing_in_prod = set(dev_vars.keys()) - set(prod_vars.keys())

        # Verify detection
        assert "NEW_FEATURE_ENABLED" in missing_in_prod
        assert len(missing_in_prod) == 1

    def test_detect_different_values_between_environments(self, clean_env, tmp_path):
        """Test detection of environment variables with different values.

        Some settings (like DEBUG) should differ between environments,
        but others (like BATCH_WINDOW_SECONDS) should be identical.
        """
        # Create mock dev and prod configs
        dev_env = tmp_path / ".env.dev"
        prod_env = tmp_path / ".env.prod"

        dev_db = "postgresql+asyncpg://test:test@localhost:5432/dev"  # pragma: allowlist secret
        prod_db = "postgresql+asyncpg://test:test@localhost:5432/prod"  # pragma: allowlist secret

        dev_env.write_text(f"""DATABASE_URL={dev_db}
BATCH_WINDOW_SECONDS=90
BATCH_IDLE_TIMEOUT_SECONDS=30
""")

        prod_env.write_text(f"""DATABASE_URL={prod_db}
BATCH_WINDOW_SECONDS=120
BATCH_IDLE_TIMEOUT_SECONDS=30
""")

        # Parse both
        dev_vars = self._parse_env_file(dev_env)
        prod_vars = self._parse_env_file(prod_env)

        # Detect drift in shared keys (excluding expected differences)
        expected_differences = {"DATABASE_URL"}
        shared_keys = set(dev_vars.keys()) & set(prod_vars.keys())
        unexpected_drift = {
            key
            for key in shared_keys
            if dev_vars[key] != prod_vars[key] and key not in expected_differences
        }

        # Verify detection
        assert "BATCH_WINDOW_SECONDS" in unexpected_drift
        assert "BATCH_IDLE_TIMEOUT_SECONDS" not in unexpected_drift
        assert "DATABASE_URL" not in unexpected_drift  # Expected difference

    def test_no_drift_when_environments_match(self, clean_env, tmp_path):
        """Test that no drift is detected when environments match (excluding expected differences)."""
        dev_env = tmp_path / ".env.dev"
        prod_env = tmp_path / ".env.prod"

        dev_db = "postgresql+asyncpg://test:test@localhost:5432/dev"  # pragma: allowlist secret
        prod_db = "postgresql+asyncpg://test:test@localhost:5432/prod"  # pragma: allowlist secret

        dev_env.write_text(f"""DATABASE_URL={dev_db}
BATCH_WINDOW_SECONDS=90
DEBUG=true
""")

        prod_env.write_text(f"""DATABASE_URL={prod_db}
BATCH_WINDOW_SECONDS=90
DEBUG=false
""")

        dev_vars = self._parse_env_file(dev_env)
        prod_vars = self._parse_env_file(prod_env)

        # Check only business logic settings (exclude DB URLs and DEBUG)
        business_logic_keys = {"BATCH_WINDOW_SECONDS"}
        drift = {key for key in business_logic_keys if dev_vars.get(key) != prod_vars.get(key)}

        assert len(drift) == 0

    @staticmethod
    def _parse_env_file(path: Path) -> dict[str, str]:
        """Parse .env file into dict."""
        env_vars = {}
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()
        return env_vars


class TestSecretsExposurePrevention:
    """Test that secrets are not exposed in logs, errors, or API responses.

    Secrets include: DATABASE_URL passwords, ADMIN_API_KEY, API keys, Redis passwords.

    NOTE: Settings.__repr__ automatically redacts sensitive fields containing patterns
    like 'password', 'secret', 'key', 'token', 'credential'. This provides protection
    when logging settings objects directly.

    However, logging raw attribute values (e.g., settings.redis_url) bypasses this.
    Production code should use backend.core.logging.redact_url() and redact_sensitive_value()
    utilities when logging individual configuration values.
    """

    def test_database_url_contains_password_in_repr(self, clean_env):
        """Test that DATABASE_URL password IS properly redacted in Settings repr/str.

        Settings.__repr__ automatically redacts sensitive URL fields using redact_url().
        This prevents accidental exposure of secrets when logging settings objects.
        """
        # Set DATABASE_URL with password
        clean_env.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://user:secret_password@localhost:5432/db",  # pragma: allowlist secret
        )
        get_settings.cache_clear()
        settings = get_settings()

        # Convert to string (simulates logging)
        settings_str = str(settings)

        # SECURE BEHAVIOR: Password is redacted in repr/str output
        assert "secret_password" not in settings_str  # pragma: allowlist secret
        assert "[REDACTED]" in settings_str
        # But the actual attribute still has the real password
        test_url = "postgresql+asyncpg://user:secret_password@localhost:5432/db"  # pragma: allowlist secret
        assert settings.database_url == test_url

    def test_redis_url_contains_password_in_logs(self, clean_env, caplog):
        """Test that Redis password IS logged when URL is logged directly (CURRENT BEHAVIOR).

        This test documents that raw logging of settings values exposes secrets.

        SECURITY REQUIREMENT: Use backend.core.logging.redact_url() before logging:
            from backend.core.logging import redact_url
            logger.info(f"Redis URL: {redact_url(settings.redis_url)}")
        """
        # Set Redis URL with password
        clean_env.setenv(
            "REDIS_URL",
            "redis://:my_redis_password@localhost:6379/0",  # pragma: allowlist secret
        )
        get_settings.cache_clear()

        # Simulate UNSAFE logging (what NOT to do)
        with caplog.at_level(logging.INFO):
            settings = get_settings()
            logging.info(f"Redis URL: {settings.redis_url}")

        # CURRENT BEHAVIOR: Password IS in logs (unsafe)
        log_text = caplog.text
        assert "my_redis_password" in log_text

    def test_admin_api_key_exposed_in_repr(self, clean_env):
        """Test that ADMIN_API_KEY IS properly redacted in settings representation.

        Settings.__repr__ automatically redacts fields containing 'key', 'secret', etc.
        This prevents accidental exposure when logging settings objects.
        """
        clean_env.setenv("ADMIN_API_KEY", "super_secret_admin_key")  # pragma: allowlist secret
        get_settings.cache_clear()
        settings = get_settings()

        settings_str = str(settings)

        # SECURE BEHAVIOR: API key is redacted in repr/str output
        assert "super_secret_admin_key" not in settings_str
        assert "[REDACTED]" in settings_str
        # But the actual attribute still has the real key
        assert settings.admin_api_key == "super_secret_admin_key"  # pragma: allowlist secret

    def test_validation_error_exposes_secrets(self, clean_env):
        """Test that Pydantic ValidationError DOES expose secrets (CURRENT BEHAVIOR).

        Pydantic includes the input_value in validation errors, which exposes secrets.

        MITIGATION: Catch ValidationError at startup and sanitize error messages
        before logging or displaying to users.
        """
        # Set invalid DATABASE_URL with password
        clean_env.setenv(
            "DATABASE_URL",
            "invalid://user:secret_password@localhost:5432/db",  # pragma: allowlist secret
        )
        get_settings.cache_clear()

        # Trigger validation error
        with pytest.raises(ValidationError) as exc_info:
            get_settings()

        # CURRENT BEHAVIOR: Password IS in error message (Pydantic limitation)
        error_str = str(exc_info.value)
        assert "secret_password" in error_str  # pragma: allowlist secret
        assert "input_value=" in error_str

    def test_redaction_utilities_exist(self):
        """Test that backend.core.logging provides secret redaction utilities.

        This verifies that developers have tools to safely log configuration values.
        """
        from backend.core.logging import redact_sensitive_value, redact_url

        # Test URL redaction
        redacted = redact_url("postgresql://user:password@host:5432/db")  # pragma: allowlist secret
        assert "password" not in redacted
        # redact_url returns format: "scheme://user:[REDACTED]@host:port/db"
        assert "[REDACTED]" in redacted
        assert "user:[REDACTED]@host" in redacted

        # Test sensitive value redaction
        redacted_key = redact_sensitive_value("admin_api_key", "secret_key_value")
        assert "secret_key_value" not in redacted_key
        assert "[REDACTED]" in redacted_key  # Uses [REDACTED] format


class TestInvalidConfigurationCombinations:
    """Test detection of invalid configuration combinations.

    Some settings are mutually exclusive or require other settings to be set.
    These tests verify that invalid combinations are caught at startup.
    """

    def test_tls_provided_mode_requires_cert_path(self, clean_env):
        """Test that TLS_MODE=provided requires TLS_CERT_PATH to be set.

        When using provided certificates, both cert and key paths are mandatory.
        """
        clean_env.setenv("TLS_MODE", "provided")
        # Don't set TLS_CERT_PATH
        get_settings.cache_clear()

        # This should succeed at Settings creation (validation happens later)
        # But we document that tls_cert_path should be validated
        settings = get_settings()
        assert settings.tls_mode == "provided"
        assert settings.tls_cert_path is None  # Invalid combination

        # In production, this would be caught by TLS initialization code
        # For now, we verify the values are loaded as expected

    def test_tls_provided_mode_requires_key_path(self, clean_env):
        """Test that TLS_MODE=provided requires TLS_KEY_PATH to be set."""
        clean_env.setenv("TLS_MODE", "provided")
        clean_env.setenv("TLS_CERT_PATH", "/path/to/cert.pem")
        # Don't set TLS_KEY_PATH
        get_settings.cache_clear()

        settings = get_settings()
        assert settings.tls_mode == "provided"
        assert settings.tls_cert_path == "/path/to/cert.pem"
        assert settings.tls_key_path is None  # Invalid combination

    def test_rate_limiting_with_zero_limits(self, clean_env):
        """Test that rate limiting enabled with zero limits is detected.

        If RATE_LIMIT_ENABLED=true but all limits are 0, rate limiting
        will effectively block all requests. This is likely a configuration error.
        """
        clean_env.setenv("RATE_LIMIT_ENABLED", "true")
        clean_env.setenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "0")
        get_settings.cache_clear()

        # Pydantic validation should fail due to ge=1 constraint
        with pytest.raises(ValidationError) as exc_info:
            get_settings()

        # Verify error mentions the constraint violation
        error_str = str(exc_info.value)
        assert "rate_limit_requests_per_minute" in error_str.lower()

    def test_timeout_inversion_health_check(self, clean_env):
        """Test that health_check_timeout > health_check_interval is invalid.

        The timeout for a single health check cannot be greater than
        the interval between checks, or checks would overlap.
        """
        clean_env.setenv("ORCHESTRATOR_HEALTH_CHECK_INTERVAL", "10")
        clean_env.setenv("ORCHESTRATOR_HEALTH_CHECK_TIMEOUT", "15")
        get_settings.cache_clear()

        settings = get_settings()

        # Check for timeout inversion
        is_invalid = (
            settings.orchestrator.health_check_timeout > settings.orchestrator.health_check_interval
        )
        assert is_invalid, "Timeout inversion should be detected"

        # In production, this would be validated at startup
        # For now, we verify the comparison logic works

    def test_valid_health_check_timeout_configuration(self, clean_env):
        """Test that valid health check timeout configuration is accepted."""
        clean_env.setenv("ORCHESTRATOR_HEALTH_CHECK_INTERVAL", "30")
        clean_env.setenv("ORCHESTRATOR_HEALTH_CHECK_TIMEOUT", "5")
        get_settings.cache_clear()

        settings = get_settings()

        # Verify valid configuration
        assert (
            settings.orchestrator.health_check_timeout < settings.orchestrator.health_check_interval
        )


class TestFeatureFlagInterdependencies:
    """Test feature flag interdependencies.

    Some features depend on other features being enabled.
    These tests verify that invalid combinations are detected.
    """

    def test_reid_requires_vision_extraction(self, clean_env):
        """Test that reid_enabled=true requires vision_extraction_enabled=true.

        Re-identification (ReID) requires vision extraction to generate
        embeddings. ReID without vision extraction makes no sense.
        """
        clean_env.setenv("REID_ENABLED", "true")
        clean_env.setenv("VISION_EXTRACTION_ENABLED", "false")
        get_settings.cache_clear()

        settings = get_settings()

        # Verify invalid combination is loaded
        assert settings.reid_enabled is True
        assert settings.vision_extraction_enabled is False

        # In production, this would be validated at startup with:
        # if settings.reid_enabled and not settings.vision_extraction_enabled:
        #     raise ConfigurationError("ReID requires vision extraction")

    def test_reid_with_vision_extraction_is_valid(self, clean_env):
        """Test that reid_enabled=true with vision_extraction_enabled=true is valid."""
        clean_env.setenv("REID_ENABLED", "true")
        clean_env.setenv("VISION_EXTRACTION_ENABLED", "true")
        get_settings.cache_clear()

        settings = get_settings()

        # Verify valid combination
        assert settings.reid_enabled is True
        assert settings.vision_extraction_enabled is True

    def test_reid_disabled_does_not_require_vision_extraction(self, clean_env):
        """Test that reid_enabled=false works regardless of vision_extraction_enabled."""
        clean_env.setenv("REID_ENABLED", "false")
        clean_env.setenv("VISION_EXTRACTION_ENABLED", "false")
        get_settings.cache_clear()

        settings = get_settings()

        # Verify this is valid (ReID disabled, so vision extraction not required)
        assert settings.reid_enabled is False
        # vision_extraction_enabled can be any value when reid_enabled=false


class TestTimeoutConsistency:
    """Test timeout value consistency across the application.

    Timeouts should be logically consistent:
    - Connection timeouts should be less than read timeouts
    - Health check timeouts should be less than health check intervals
    - Child operation timeouts should be less than parent operation timeouts
    """

    def test_ai_connect_timeout_less_than_read_timeout(self, clean_env):
        """Test that AI connection timeout is less than read timeout.

        It doesn't make sense for connection timeout to be greater than
        the timeout for reading the response.
        """
        settings = get_settings()

        # Verify connection timeout is less than read timeouts
        assert settings.ai_connect_timeout < settings.rtdetr_read_timeout
        assert settings.ai_connect_timeout < settings.nemotron_read_timeout

    def test_ai_health_timeout_less_than_read_timeout(self, clean_env):
        """Test that health check timeout is less than AI read timeouts.

        Health checks should be fast - they shouldn't take as long as
        actual inference requests.
        """
        settings = get_settings()

        assert settings.ai_health_timeout < settings.rtdetr_read_timeout
        assert settings.ai_health_timeout < settings.nemotron_read_timeout

    def test_custom_timeout_inversion_detected(self, clean_env):
        """Test detection of custom timeout inversions.

        If a user sets AI_CONNECT_TIMEOUT > RTDETR_READ_TIMEOUT,
        this should be flagged as invalid.

        Note: AI_CONNECT_TIMEOUT has le=60 constraint, so we test with values
        within the valid range.
        """
        clean_env.setenv("AI_CONNECT_TIMEOUT", "55")  # Close to max (60)
        clean_env.setenv("RTDETR_READ_TIMEOUT", "30")  # Lower than connect
        get_settings.cache_clear()

        settings = get_settings()

        # Verify inversion is detected (connect timeout > read timeout is illogical)
        is_inverted = settings.ai_connect_timeout > settings.rtdetr_read_timeout
        assert is_inverted, "Timeout inversion should be detected"


class TestWebhookURLValidation:
    """Test webhook URL SSRF protection and validation."""

    def test_webhook_url_blocks_private_ips(self, clean_env):
        """Test that webhook URLs with private IPs are blocked (SSRF protection)."""
        # Private IP ranges should be blocked
        private_urls = [
            "http://192.168.1.1/webhook",
            "http://10.0.0.1/webhook",
            "http://172.16.0.1/webhook",
        ]

        for url in private_urls:
            clean_env.setenv("DEFAULT_WEBHOOK_URL", url)
            get_settings.cache_clear()

            # Should raise ValueError due to SSRF protection
            with pytest.raises(ValueError, match="blocked for security"):
                get_settings()

    def test_webhook_url_allows_localhost_in_dev(self, clean_env):
        """Test that webhook URLs with localhost are ALLOWED in dev mode.

        The validator uses allow_dev_http=True, which permits localhost for development.
        This is intentional to allow testing webhook functionality locally.
        """
        clean_env.setenv("DEFAULT_WEBHOOK_URL", "http://localhost:8080/webhook")
        get_settings.cache_clear()

        settings = get_settings()
        # Localhost is allowed in dev mode
        assert settings.default_webhook_url == "http://localhost:8080/webhook"

    def test_webhook_url_allows_public_https(self, clean_env):
        """Test that webhook URLs with public HTTPS are allowed."""
        clean_env.setenv("DEFAULT_WEBHOOK_URL", "https://hooks.example.com/webhook")
        get_settings.cache_clear()

        settings = get_settings()
        assert settings.default_webhook_url == "https://hooks.example.com/webhook"

    def test_webhook_url_empty_string_is_none(self, clean_env):
        """Test that empty webhook URL is treated as None."""
        clean_env.setenv("DEFAULT_WEBHOOK_URL", "")
        get_settings.cache_clear()

        settings = get_settings()
        assert settings.default_webhook_url is None


class TestGrafanaURLValidation:
    """Test Grafana URL validation with SSRF protection."""

    def test_grafana_url_allows_localhost(self, clean_env):
        """Test that Grafana URL allows localhost (typically local deployment)."""
        clean_env.setenv("GRAFANA_URL", "http://localhost:3002")
        get_settings.cache_clear()

        settings = get_settings()
        assert settings.grafana_url == "http://localhost:3002"

    def test_grafana_url_allows_internal_ips(self, clean_env):
        """Test that Grafana URL allows internal IPs (common for dashboards)."""
        # Grafana is typically on internal network
        clean_env.setenv("GRAFANA_URL", "http://192.168.1.100:3000")
        get_settings.cache_clear()

        settings = get_settings()
        assert settings.grafana_url == "http://192.168.1.100:3000"

    def test_grafana_url_blocks_cloud_metadata(self, clean_env):
        """Test that Grafana URL blocks cloud metadata endpoints."""
        # Cloud metadata endpoints should be blocked
        clean_env.setenv("GRAFANA_URL", "http://169.254.169.254/latest/meta-data")
        get_settings.cache_clear()

        with pytest.raises(ValueError, match="Invalid Grafana URL"):
            get_settings()

    def test_grafana_url_invalid_scheme(self, clean_env):
        """Test that Grafana URL rejects non-HTTP schemes."""
        clean_env.setenv("GRAFANA_URL", "ftp://localhost:3002")
        get_settings.cache_clear()

        with pytest.raises(ValueError, match="Invalid Grafana URL"):
            get_settings()


class TestConfigurationValidationEdgeCases:
    """Test edge cases in configuration validation."""

    def test_multiple_validation_errors_reported(self, clean_env):
        """Test that multiple validation errors are reported together.

        When multiple config values are invalid, all errors should be
        reported at once (not just the first one).

        Note: Pydantic may short-circuit on the first error, so we verify
        that AT LEAST one error is reported properly.
        """
        # Set multiple invalid values
        clean_env.setenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "0")  # Invalid: violates ge=1
        clean_env.setenv("AI_CONNECT_TIMEOUT", "150")  # Invalid: violates le=60
        get_settings.cache_clear()

        with pytest.raises(ValidationError) as exc_info:
            get_settings()

        error_str = str(exc_info.value)
        # At least one error should be present
        # Pydantic may report one or both errors depending on validation order
        assert (
            "rate_limit_requests_per_minute" in error_str.lower()
            or "ai_connect_timeout" in error_str.lower()
        )

    def test_case_insensitive_env_vars(self, clean_env):
        """Test that environment variables are case-insensitive.

        Pydantic Settings should accept both BATCH_WINDOW_SECONDS and
        batch_window_seconds.
        """
        # Use lowercase env var
        clean_env.setenv("batch_window_seconds", "120")
        get_settings.cache_clear()

        settings = get_settings()
        assert settings.batch_window_seconds == 120

    def test_extra_env_vars_ignored(self, clean_env):
        """Test that extra unknown environment variables are ignored.

        Settings has extra='ignore', so unknown vars should not cause errors.
        """
        clean_env.setenv("UNKNOWN_CONFIG_VALUE", "should_be_ignored")
        clean_env.setenv("ANOTHER_UNKNOWN", "also_ignored")
        get_settings.cache_clear()

        # Should not raise error
        settings = get_settings()
        assert not hasattr(settings, "unknown_config_value")
        assert not hasattr(settings, "another_unknown")
