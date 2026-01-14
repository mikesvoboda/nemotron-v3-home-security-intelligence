"""Unit tests for configurable pagination limits (NEM-2591).

Tests for the pagination limit validation functionality including:
- Settings configuration for pagination limits
- Validation functions that enforce maximum limits
- PaginationLimits dependency injection

Related to NEM-2591: Add configurable pagination limits with validation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.api.pagination import (
    get_validated_limit,
    validate_pagination_limit,
)
from backend.core.dependencies import PaginationLimits, get_pagination_limits


class TestPaginationSettings:
    """Tests for pagination settings in configuration."""

    def test_settings_has_pagination_max_limit(self) -> None:
        """Test that Settings includes pagination_max_limit field."""
        from backend.core.config import Settings

        assert "pagination_max_limit" in Settings.model_fields

    def test_settings_has_pagination_default_limit(self) -> None:
        """Test that Settings includes pagination_default_limit field."""
        from backend.core.config import Settings

        assert "pagination_default_limit" in Settings.model_fields

    def test_pagination_max_limit_default_is_1000(self) -> None:
        """Test that default pagination_max_limit is 1000."""
        from backend.core.config import Settings

        default = Settings.model_fields["pagination_max_limit"].default
        assert default == 1000

    def test_pagination_default_limit_default_is_50(self) -> None:
        """Test that default pagination_default_limit is 50."""
        from backend.core.config import Settings

        default = Settings.model_fields["pagination_default_limit"].default
        assert default == 50

    def test_pagination_max_limit_has_reasonable_bounds(self) -> None:
        """Test that pagination_max_limit has reasonable bounds."""
        from backend.core.config import Settings

        field = Settings.model_fields["pagination_max_limit"]
        assert field.metadata[0].ge == 100
        assert field.metadata[1].le == 10000


class TestValidatePaginationLimit:
    """Tests for validate_pagination_limit function."""

    def test_returns_valid_limit_when_within_max(self) -> None:
        """Test that valid limits are returned unchanged."""
        result = validate_pagination_limit(50, max_limit=1000)
        assert result == 50

    def test_returns_limit_at_exactly_max(self) -> None:
        """Test that limit at exactly max is accepted."""
        result = validate_pagination_limit(1000, max_limit=1000)
        assert result == 1000

    def test_raises_value_error_when_limit_exceeds_max(self) -> None:
        """Test that ValueError is raised when limit exceeds max."""
        with pytest.raises(ValueError) as exc_info:
            validate_pagination_limit(2000, max_limit=1000)
        assert "exceeds maximum allowed value" in str(exc_info.value)
        assert "2000" in str(exc_info.value)
        assert "1000" in str(exc_info.value)

    def test_error_includes_parameter_name(self) -> None:
        """Test that error message includes parameter name."""
        with pytest.raises(ValueError) as exc_info:
            validate_pagination_limit(2000, max_limit=1000, param_name="page_size")
        assert "page_size" in str(exc_info.value)

    def test_uses_default_param_name(self) -> None:
        """Test that default param name is 'limit'."""
        with pytest.raises(ValueError) as exc_info:
            validate_pagination_limit(2000, max_limit=1000)
        assert "'limit'" in str(exc_info.value)

    def test_rejects_limit_one_above_max(self) -> None:
        """Test that limit one above max is rejected."""
        with pytest.raises(ValueError):
            validate_pagination_limit(1001, max_limit=1000)

    @patch("backend.api.pagination.get_settings")
    def test_uses_settings_when_max_limit_not_provided(self, mock_get_settings: MagicMock) -> None:
        """Test that settings.pagination_max_limit is used when not provided."""
        mock_settings = MagicMock()
        mock_settings.pagination_max_limit = 500
        mock_get_settings.return_value = mock_settings

        result = validate_pagination_limit(400)
        assert result == 400

    @patch("backend.api.pagination.get_settings")
    def test_rejects_based_on_settings_max_limit(self, mock_get_settings: MagicMock) -> None:
        """Test that validation uses settings max limit."""
        mock_settings = MagicMock()
        mock_settings.pagination_max_limit = 500
        mock_get_settings.return_value = mock_settings

        with pytest.raises(ValueError) as exc_info:
            validate_pagination_limit(600)
        assert "500" in str(exc_info.value)


class TestGetValidatedLimit:
    """Tests for get_validated_limit function."""

    @patch("backend.api.pagination.get_settings")
    def test_returns_default_when_limit_is_none(self, mock_get_settings: MagicMock) -> None:
        """Test that default limit is returned when limit is None."""
        mock_settings = MagicMock()
        mock_settings.pagination_default_limit = 50
        mock_settings.pagination_max_limit = 1000
        mock_get_settings.return_value = mock_settings

        result = get_validated_limit(None)
        assert result == 50

    @patch("backend.api.pagination.get_settings")
    def test_returns_provided_limit_when_valid(self, mock_get_settings: MagicMock) -> None:
        """Test that provided limit is returned when valid."""
        mock_settings = MagicMock()
        mock_settings.pagination_default_limit = 50
        mock_settings.pagination_max_limit = 1000
        mock_get_settings.return_value = mock_settings

        result = get_validated_limit(100)
        assert result == 100

    @patch("backend.api.pagination.get_settings")
    def test_raises_when_limit_exceeds_max(self, mock_get_settings: MagicMock) -> None:
        """Test that ValueError is raised when limit exceeds max."""
        mock_settings = MagicMock()
        mock_settings.pagination_default_limit = 50
        mock_settings.pagination_max_limit = 1000
        mock_get_settings.return_value = mock_settings

        with pytest.raises(ValueError) as exc_info:
            get_validated_limit(2000)
        assert "exceeds maximum" in str(exc_info.value)

    def test_uses_override_default_when_provided(self) -> None:
        """Test that override default is used when provided."""
        result = get_validated_limit(None, default=25, max_limit=1000)
        assert result == 25

    def test_uses_override_max_limit_when_provided(self) -> None:
        """Test that override max_limit is used when provided."""
        result = get_validated_limit(500, default=50, max_limit=500)
        assert result == 500

        with pytest.raises(ValueError):
            get_validated_limit(501, default=50, max_limit=500)


class TestPaginationLimits:
    """Tests for PaginationLimits container class."""

    def test_stores_max_limit(self) -> None:
        """Test that max_limit is stored correctly."""
        limits = PaginationLimits(max_limit=1000, default_limit=50)
        assert limits.max_limit == 1000

    def test_stores_default_limit(self) -> None:
        """Test that default_limit is stored correctly."""
        limits = PaginationLimits(max_limit=1000, default_limit=50)
        assert limits.default_limit == 50

    def test_accepts_custom_values(self) -> None:
        """Test that custom values are accepted."""
        limits = PaginationLimits(max_limit=5000, default_limit=100)
        assert limits.max_limit == 5000
        assert limits.default_limit == 100


class TestGetPaginationLimitsDependency:
    """Tests for get_pagination_limits FastAPI dependency."""

    @patch("backend.core.dependencies.get_settings")
    def test_returns_pagination_limits_from_settings(self, mock_get_settings: MagicMock) -> None:
        """Test that dependency returns PaginationLimits from settings."""
        mock_settings = MagicMock()
        mock_settings.pagination_max_limit = 2000
        mock_settings.pagination_default_limit = 100
        mock_get_settings.return_value = mock_settings

        result = get_pagination_limits()

        assert isinstance(result, PaginationLimits)
        assert result.max_limit == 2000
        assert result.default_limit == 100


class TestRepositoryMaxLimit:
    """Tests for repository base class max limit handling."""

    def test_max_limit_constant_exists(self) -> None:
        """Test that MAX_LIMIT constant exists in repository base."""
        from backend.repositories.base import MAX_LIMIT

        assert MAX_LIMIT == 1000

    def test_get_max_limit_function_exists(self) -> None:
        """Test that get_max_limit function exists."""
        from backend.repositories.base import get_max_limit

        assert callable(get_max_limit)

    @patch("backend.repositories.base.get_settings")
    def test_get_max_limit_returns_settings_value(self, mock_get_settings: MagicMock) -> None:
        """Test that get_max_limit returns value from settings."""
        from backend.repositories.base import get_max_limit

        mock_settings = MagicMock()
        mock_settings.pagination_max_limit = 2000
        mock_get_settings.return_value = mock_settings

        result = get_max_limit()
        assert result == 2000

    def test_get_max_limit_falls_back_to_constant(self) -> None:
        """Test that get_max_limit falls back to MAX_LIMIT on error."""
        from backend.repositories.base import MAX_LIMIT, get_max_limit

        with patch(
            "backend.repositories.base.get_settings",
            side_effect=Exception("Config error"),
        ):
            result = get_max_limit()
            assert result == MAX_LIMIT
