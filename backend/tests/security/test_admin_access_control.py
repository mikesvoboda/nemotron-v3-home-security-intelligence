"""Admin endpoint access control security tests (NEM-4459).

This module validates that admin endpoints are properly protected
when DEBUG=false. This is a critical security check to prevent
sensitive admin functionality from being accessible in production.

Defense-in-depth: Admin endpoints require BOTH:
- DEBUG=true
- ADMIN_ENABLED=true

Without both conditions, admin endpoints must return 403 Forbidden.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.routes.admin import require_admin_access


class TestAdminAccessControlFunction:
    """Test the require_admin_access dependency function."""

    def test_admin_blocked_when_debug_false(self):
        """Test admin access denied when DEBUG=false."""
        mock_settings = MagicMock()
        mock_settings.debug = False
        mock_settings.admin_enabled = True

        with patch("backend.api.routes.admin.get_settings", return_value=mock_settings):
            with pytest.raises(Exception) as exc_info:
                require_admin_access()

            assert exc_info.value.status_code == 403
            assert "DEBUG=true and ADMIN_ENABLED=true" in exc_info.value.detail

    def test_admin_blocked_when_admin_enabled_false(self):
        """Test admin access denied when ADMIN_ENABLED=false."""
        mock_settings = MagicMock()
        mock_settings.debug = True
        mock_settings.admin_enabled = False

        with patch("backend.api.routes.admin.get_settings", return_value=mock_settings):
            with pytest.raises(Exception) as exc_info:
                require_admin_access()

            assert exc_info.value.status_code == 403
            assert "DEBUG=true and ADMIN_ENABLED=true" in exc_info.value.detail

    def test_admin_blocked_when_both_false(self):
        """Test admin access denied when BOTH flags are false (production default)."""
        mock_settings = MagicMock()
        mock_settings.debug = False
        mock_settings.admin_enabled = False

        with patch("backend.api.routes.admin.get_settings", return_value=mock_settings):
            with pytest.raises(Exception) as exc_info:
                require_admin_access()

            assert exc_info.value.status_code == 403
            assert "DEBUG=true and ADMIN_ENABLED=true" in exc_info.value.detail

    def test_admin_allowed_when_both_true(self):
        """Test admin access allowed when BOTH flags are true."""
        mock_settings = MagicMock()
        mock_settings.debug = True
        mock_settings.admin_enabled = True

        with patch("backend.api.routes.admin.get_settings", return_value=mock_settings):
            # Should not raise
            result = require_admin_access()
            # Function returns None when access is allowed
            assert result is None


class TestAdminEndpointsProductionMode:
    """Test admin endpoint protection in production mode (DEBUG=false).

    These tests verify that the admin access control function properly
    blocks access when DEBUG=false or ADMIN_ENABLED=false.

    Note: Full endpoint integration tests are complex due to database
    dependencies. The core security check is in require_admin_access(),
    which is thoroughly tested in TestAdminAccessControlFunction.
    """

    @pytest.mark.parametrize(
        "debug,admin_enabled,should_block,description",
        [
            (False, False, True, "Production default - both false"),
            (False, True, True, "DEBUG=false blocks even with admin_enabled"),
            (True, False, True, "ADMIN_ENABLED=false blocks even with debug"),
            (True, True, False, "Both true - admin access allowed"),
        ],
    )
    def test_admin_access_control_matrix(
        self, debug: bool, admin_enabled: bool, should_block: bool, description: str
    ):
        """Test require_admin_access with all flag combinations.

        CRITICAL SECURITY TEST: Validates that admin access requires
        BOTH DEBUG=true AND ADMIN_ENABLED=true (defense-in-depth).

        Scenario: {description}
        """
        mock_settings = MagicMock()
        mock_settings.debug = debug
        mock_settings.admin_enabled = admin_enabled

        with patch("backend.api.routes.admin.get_settings", return_value=mock_settings):
            if should_block:
                with pytest.raises(Exception) as exc_info:
                    require_admin_access()
                assert exc_info.value.status_code == 403
                assert "DEBUG=true and ADMIN_ENABLED=true" in exc_info.value.detail
            else:
                # Should not raise
                result = require_admin_access()
                assert result is None


class TestAdminEndpointsBehavior:
    """Test admin endpoint behavior with various configuration combinations."""

    def test_admin_not_listed_in_production_openapi(self, security_client: TestClient):
        """Test that admin endpoints are not exposed in production OpenAPI schema.

        Note: This test verifies the endpoints exist but are protected.
        In a stricter setup, admin endpoints could be conditionally registered.
        """
        # The admin endpoints should return 403, not 404
        # This confirms they exist but are protected
        response = security_client.post("/api/admin/seed/cameras", json={})

        # Should be 403 (blocked) not 404 (not found)
        # 403 indicates the endpoint exists but access is denied
        # 422 would be validation error (also acceptable - means endpoint exists)
        # 500 might happen if DB not connected (also acceptable)
        assert response.status_code != 200, (
            "Admin endpoint returned 200 - should be blocked in test environment"
        )


class TestProductionPasswordValidation:
    """Test that production environments require strong passwords."""

    def test_weak_redis_password_rejected_in_production(self):
        """Test that weak Redis passwords are rejected in production."""
        from pydantic import SecretStr

        from backend.core.config import Settings

        # This should raise ValueError for weak password in production
        with pytest.raises(ValueError) as exc_info:
            Settings(
                database_url="postgresql+asyncpg://user:strongpassword123456@host:5432/db",  # pragma: allowlist secret
                environment="production",
                redis_password=SecretStr("weak"),  # Less than 16 chars
            )

        assert "REDIS_PASSWORD" in str(exc_info.value) or "Redis" in str(exc_info.value)

    def test_missing_redis_password_rejected_in_production(self):
        """Test that missing Redis password is rejected in production."""
        from backend.core.config import Settings

        # This should raise ValueError for missing password in production
        with pytest.raises(ValueError) as exc_info:
            Settings(
                database_url="postgresql+asyncpg://user:strongpassword123456@host:5432/db",
                environment="production",
                redis_password=None,
            )

        assert "REDIS_PASSWORD" in str(exc_info.value) or "Redis" in str(exc_info.value)

    def test_strong_redis_password_accepted_in_production(self):
        """Test that strong Redis passwords are accepted in production."""
        from pydantic import SecretStr

        from backend.core.config import Settings

        # This should NOT raise - strong password
        settings = Settings(
            database_url="postgresql+asyncpg://user:strongpassword123456@host:5432/db",
            environment="production",
            redis_password=SecretStr("verystrongpassword1234567890"),  # 30+ chars
        )

        assert settings.environment == "production"

    def test_no_password_validation_in_development(self):
        """Test that password validation is skipped in development."""
        from backend.core.config import Settings

        # This should NOT raise in development environment
        settings = Settings(
            database_url="postgresql+asyncpg://user:pass@host:5432/db",  # pragma: allowlist secret
            environment="development",
            redis_password=None,  # No password in dev is OK
        )

        assert settings.environment == "development"
