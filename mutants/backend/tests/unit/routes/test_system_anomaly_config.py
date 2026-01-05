"""Unit tests for anomaly detection configuration API endpoints.

Tests the anomaly config endpoints:
- GET /api/system/anomaly-config
- PATCH /api/system/anomaly-config

These tests follow TDD methodology - written before implementation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.api.schemas.baseline import (
    AnomalyConfig,
    AnomalyConfigUpdate,
)


class TestGetAnomalyConfig:
    """Tests for GET /api/system/anomaly-config endpoint."""

    @pytest.mark.asyncio
    async def test_get_anomaly_config_returns_current_settings(self) -> None:
        """Test that get_anomaly_config returns current service configuration."""
        from backend.api.routes.system import get_anomaly_config

        mock_service = MagicMock()
        mock_service.anomaly_threshold_std = 2.5
        mock_service.min_samples = 15
        mock_service.decay_factor = 0.1
        mock_service.window_days = 30

        with patch(
            "backend.services.baseline.get_baseline_service",
            return_value=mock_service,
        ):
            result = await get_anomaly_config()

        assert isinstance(result, AnomalyConfig)
        assert result.threshold_stdev == 2.5
        assert result.min_samples == 15
        assert result.decay_factor == 0.1
        assert result.window_days == 30

    @pytest.mark.asyncio
    async def test_get_anomaly_config_default_values(self) -> None:
        """Test that get_anomaly_config returns default values when service is fresh."""
        from backend.api.routes.system import get_anomaly_config

        mock_service = MagicMock()
        mock_service.anomaly_threshold_std = 2.0
        mock_service.min_samples = 10
        mock_service.decay_factor = 0.1
        mock_service.window_days = 30

        with patch(
            "backend.services.baseline.get_baseline_service",
            return_value=mock_service,
        ):
            result = await get_anomaly_config()

        assert result.threshold_stdev == 2.0
        assert result.min_samples == 10


class TestUpdateAnomalyConfig:
    """Tests for PATCH /api/system/anomaly-config endpoint."""

    @pytest.mark.asyncio
    async def test_update_anomaly_config_threshold_stdev(self) -> None:
        """Test updating threshold_stdev value."""
        from backend.api.routes.system import update_anomaly_config

        mock_service = MagicMock()
        mock_service.anomaly_threshold_std = 2.0
        mock_service.min_samples = 10
        mock_service.decay_factor = 0.1
        mock_service.window_days = 30
        mock_service.update_config = MagicMock()

        mock_db = AsyncMock()
        mock_request = MagicMock()

        config_update = AnomalyConfigUpdate(threshold_stdev=3.0)

        with (
            patch(
                "backend.services.baseline.get_baseline_service",
                return_value=mock_service,
            ),
            patch(
                "backend.services.audit.AuditService.log_action",
                new_callable=AsyncMock,
            ),
        ):
            # Update the mock to return new value after update
            def update_threshold(**kwargs):
                if kwargs.get("threshold_stdev"):
                    mock_service.anomaly_threshold_std = kwargs["threshold_stdev"]

            mock_service.update_config.side_effect = update_threshold

            result = await update_anomaly_config(
                config_update=config_update,
                request=mock_request,
                db=mock_db,
            )

        mock_service.update_config.assert_called_once()
        assert result.threshold_stdev == 3.0

    @pytest.mark.asyncio
    async def test_update_anomaly_config_min_samples(self) -> None:
        """Test updating min_samples value."""
        from backend.api.routes.system import update_anomaly_config

        mock_service = MagicMock()
        mock_service.anomaly_threshold_std = 2.0
        mock_service.min_samples = 10
        mock_service.decay_factor = 0.1
        mock_service.window_days = 30
        mock_service.update_config = MagicMock()

        mock_db = AsyncMock()
        mock_request = MagicMock()

        config_update = AnomalyConfigUpdate(min_samples=20)

        with (
            patch(
                "backend.services.baseline.get_baseline_service",
                return_value=mock_service,
            ),
            patch(
                "backend.services.audit.AuditService.log_action",
                new_callable=AsyncMock,
            ),
        ):
            # Update the mock to return new value after update
            def update_samples(**kwargs):
                if kwargs.get("min_samples"):
                    mock_service.min_samples = kwargs["min_samples"]

            mock_service.update_config.side_effect = update_samples

            result = await update_anomaly_config(
                config_update=config_update,
                request=mock_request,
                db=mock_db,
            )

        mock_service.update_config.assert_called_once()
        assert result.min_samples == 20

    @pytest.mark.asyncio
    async def test_update_anomaly_config_both_values(self) -> None:
        """Test updating both threshold_stdev and min_samples."""
        from backend.api.routes.system import update_anomaly_config

        mock_service = MagicMock()
        mock_service.anomaly_threshold_std = 2.0
        mock_service.min_samples = 10
        mock_service.decay_factor = 0.1
        mock_service.window_days = 30
        mock_service.update_config = MagicMock()

        mock_db = AsyncMock()
        mock_request = MagicMock()

        config_update = AnomalyConfigUpdate(threshold_stdev=2.5, min_samples=15)

        with (
            patch(
                "backend.services.baseline.get_baseline_service",
                return_value=mock_service,
            ),
            patch(
                "backend.services.audit.AuditService.log_action",
                new_callable=AsyncMock,
            ),
        ):
            # Update the mock to return new values after update
            def update_both(**kwargs):
                if kwargs.get("threshold_stdev"):
                    mock_service.anomaly_threshold_std = kwargs["threshold_stdev"]
                if kwargs.get("min_samples"):
                    mock_service.min_samples = kwargs["min_samples"]

            mock_service.update_config.side_effect = update_both

            result = await update_anomaly_config(
                config_update=config_update,
                request=mock_request,
                db=mock_db,
            )

        assert result.threshold_stdev == 2.5
        assert result.min_samples == 15

    @pytest.mark.asyncio
    async def test_update_anomaly_config_invalid_threshold_returns_400(self) -> None:
        """Test that invalid threshold_stdev value returns 400 error.

        Note: Pydantic validation catches invalid values (0 or negative) before the
        endpoint is called. This test verifies the service-level error handling for
        values that pass schema validation but fail service validation.
        """
        from backend.api.routes.system import update_anomaly_config

        mock_service = MagicMock()
        mock_service.anomaly_threshold_std = 2.0
        mock_service.min_samples = 10
        mock_service.decay_factor = 0.1
        mock_service.window_days = 30
        mock_service.update_config = MagicMock(
            side_effect=ValueError("threshold_stdev must be positive")
        )

        mock_db = AsyncMock()
        mock_request = MagicMock()

        # Use a valid value that would pass schema validation but fail service validation
        config_update = AnomalyConfigUpdate(threshold_stdev=0.001)

        with patch(
            "backend.services.baseline.get_baseline_service",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_anomaly_config(
                    config_update=config_update,
                    request=mock_request,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 400
            assert "threshold_stdev" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_update_anomaly_config_invalid_min_samples_returns_400(self) -> None:
        """Test that invalid min_samples value returns 400 error.

        Note: Pydantic validation catches invalid values (0 or negative) before the
        endpoint is called. This test verifies the service-level error handling for
        values that pass schema validation but fail service validation.
        """
        from backend.api.routes.system import update_anomaly_config

        mock_service = MagicMock()
        mock_service.anomaly_threshold_std = 2.0
        mock_service.min_samples = 10
        mock_service.decay_factor = 0.1
        mock_service.window_days = 30
        mock_service.update_config = MagicMock(
            side_effect=ValueError("min_samples must be at least 1")
        )

        mock_db = AsyncMock()
        mock_request = MagicMock()

        # Use a valid value that would pass schema validation but fail service validation
        config_update = AnomalyConfigUpdate(min_samples=1)

        with patch(
            "backend.services.baseline.get_baseline_service",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_anomaly_config(
                    config_update=config_update,
                    request=mock_request,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 400
            assert "min_samples" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_update_anomaly_config_logs_audit_entry(self) -> None:
        """Test that updating config logs an audit entry."""
        from backend.api.routes.system import update_anomaly_config

        mock_service = MagicMock()
        mock_service.anomaly_threshold_std = 2.0
        mock_service.min_samples = 10
        mock_service.decay_factor = 0.1
        mock_service.window_days = 30
        mock_service.update_config = MagicMock()

        mock_db = AsyncMock()
        mock_request = MagicMock()

        config_update = AnomalyConfigUpdate(threshold_stdev=3.0)
        mock_audit_log = AsyncMock()

        with (
            patch(
                "backend.services.baseline.get_baseline_service",
                return_value=mock_service,
            ),
            patch(
                "backend.services.audit.AuditService.log_action",
                mock_audit_log,
            ),
        ):
            # Update the mock to return new value after update
            def update_threshold(**kwargs):
                if kwargs.get("threshold_stdev"):
                    mock_service.anomaly_threshold_std = kwargs["threshold_stdev"]

            mock_service.update_config.side_effect = update_threshold

            await update_anomaly_config(
                config_update=config_update,
                request=mock_request,
                db=mock_db,
            )

        # Verify audit log was called
        mock_audit_log.assert_called_once()
        call_kwargs = mock_audit_log.call_args.kwargs
        assert call_kwargs["resource_type"] == "anomaly_config"
        assert "changes" in call_kwargs["details"]


class TestAnomalyConfigSchemas:
    """Tests for anomaly config Pydantic schemas."""

    def test_anomaly_config_validation(self) -> None:
        """Test AnomalyConfig schema validation."""
        config = AnomalyConfig(
            threshold_stdev=2.5,
            min_samples=15,
            decay_factor=0.1,
            window_days=30,
        )
        assert config.threshold_stdev == 2.5
        assert config.min_samples == 15
        assert config.decay_factor == 0.1
        assert config.window_days == 30

    def test_anomaly_config_threshold_must_be_positive(self) -> None:
        """Test that threshold_stdev must be greater than 0."""
        with pytest.raises(ValueError):
            AnomalyConfig(
                threshold_stdev=0.0,
                min_samples=10,
                decay_factor=0.1,
                window_days=30,
            )

        with pytest.raises(ValueError):
            AnomalyConfig(
                threshold_stdev=-1.0,
                min_samples=10,
                decay_factor=0.1,
                window_days=30,
            )

    def test_anomaly_config_min_samples_must_be_positive(self) -> None:
        """Test that min_samples must be at least 1."""
        with pytest.raises(ValueError):
            AnomalyConfig(
                threshold_stdev=2.0,
                min_samples=0,
                decay_factor=0.1,
                window_days=30,
            )

    def test_anomaly_config_decay_factor_bounds(self) -> None:
        """Test that decay_factor must be in (0, 1]."""
        # Valid boundary
        config = AnomalyConfig(
            threshold_stdev=2.0,
            min_samples=10,
            decay_factor=1.0,
            window_days=30,
        )
        assert config.decay_factor == 1.0

        # Invalid: zero
        with pytest.raises(ValueError):
            AnomalyConfig(
                threshold_stdev=2.0,
                min_samples=10,
                decay_factor=0.0,
                window_days=30,
            )

        # Invalid: greater than 1
        with pytest.raises(ValueError):
            AnomalyConfig(
                threshold_stdev=2.0,
                min_samples=10,
                decay_factor=1.5,
                window_days=30,
            )

    def test_anomaly_config_update_optional_fields(self) -> None:
        """Test AnomalyConfigUpdate allows optional fields."""
        # All fields are optional
        update_empty = AnomalyConfigUpdate()
        assert update_empty.threshold_stdev is None
        assert update_empty.min_samples is None

        # Only threshold
        update_threshold = AnomalyConfigUpdate(threshold_stdev=3.0)
        assert update_threshold.threshold_stdev == 3.0
        assert update_threshold.min_samples is None

        # Only min_samples
        update_samples = AnomalyConfigUpdate(min_samples=20)
        assert update_samples.threshold_stdev is None
        assert update_samples.min_samples == 20

        # Both fields
        update_both = AnomalyConfigUpdate(threshold_stdev=2.5, min_samples=15)
        assert update_both.threshold_stdev == 2.5
        assert update_both.min_samples == 15

    def test_anomaly_config_update_validates_threshold(self) -> None:
        """Test that AnomalyConfigUpdate validates threshold when provided."""
        with pytest.raises(ValueError):
            AnomalyConfigUpdate(threshold_stdev=0.0)

        with pytest.raises(ValueError):
            AnomalyConfigUpdate(threshold_stdev=-1.0)

    def test_anomaly_config_update_validates_min_samples(self) -> None:
        """Test that AnomalyConfigUpdate validates min_samples when provided."""
        with pytest.raises(ValueError):
            AnomalyConfigUpdate(min_samples=0)
