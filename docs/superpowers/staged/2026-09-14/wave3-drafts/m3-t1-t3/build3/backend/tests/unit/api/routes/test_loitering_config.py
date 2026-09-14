"""Unit tests for loitering configuration API endpoints.

Tests the loitering configuration endpoints:
- GET /api/analytics-zones/polygon-zones/{zone_id}/loitering-config
- PATCH /api/analytics-zones/polygon-zones/{zone_id}/loitering-config

These tests follow TDD methodology with proper mocking.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.api.schemas.loitering_config import (
    LoiteringConfigResponse,
    LoiteringConfigUpdate,
)


class TestGetLoiteringConfig:
    """Tests for GET /api/analytics-zones/polygon-zones/{zone_id}/loitering-config endpoint."""

    @pytest.mark.asyncio
    async def test_get_loitering_config_success(self) -> None:
        """Test successfully retrieving loitering configuration for a polygon zone."""
        from backend.api.routes.analytics_zones import get_loitering_config

        mock_db = AsyncMock()

        # Create mock zone
        mock_zone = MagicMock()
        mock_zone.id = 1
        mock_zone.name = "Backyard"
        mock_zone.loitering_threshold_seconds = 300
        mock_zone.loitering_alert_enabled = True

        with patch(
            "backend.api.routes.analytics_zones.get_polygon_zone_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_zone = AsyncMock(return_value=mock_zone)
            mock_get_service.return_value = mock_service

            result = await get_loitering_config(
                zone_id=1,
                db=mock_db,
            )

        assert result.zone_id == 1
        assert result.zone_name == "Backyard"
        assert result.threshold_seconds == 300
        assert result.alert_enabled is True

    @pytest.mark.asyncio
    async def test_get_loitering_config_zone_not_found(self) -> None:
        """Test get loitering config returns 404 if polygon zone doesn't exist."""
        from backend.api.routes.analytics_zones import get_loitering_config

        mock_db = AsyncMock()

        with patch(
            "backend.api.routes.analytics_zones.get_polygon_zone_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            # Service returns None when zone not found
            mock_service.get_zone = AsyncMock(return_value=None)
            mock_get_service.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await get_loitering_config(
                    zone_id=999,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 404
            assert "999" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_loitering_config_with_disabled_alerts(self) -> None:
        """Test retrieving loitering config when alerts are disabled."""
        from backend.api.routes.analytics_zones import get_loitering_config

        mock_db = AsyncMock()

        mock_zone = MagicMock()
        mock_zone.id = 2
        mock_zone.name = "Pool Area"
        mock_zone.loitering_threshold_seconds = 600
        mock_zone.loitering_alert_enabled = False

        with patch(
            "backend.api.routes.analytics_zones.get_polygon_zone_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_zone = AsyncMock(return_value=mock_zone)
            mock_get_service.return_value = mock_service

            result = await get_loitering_config(
                zone_id=2,
                db=mock_db,
            )

        assert result.zone_id == 2
        assert result.zone_name == "Pool Area"
        assert result.threshold_seconds == 600
        assert result.alert_enabled is False

    @pytest.mark.asyncio
    async def test_get_loitering_config_calls_service_with_zone_id(self) -> None:
        """Test get loitering config calls service with correct zone_id."""
        from backend.api.routes.analytics_zones import get_loitering_config

        mock_db = AsyncMock()

        mock_zone = MagicMock()
        mock_zone.id = 42
        mock_zone.name = "Test Zone"
        mock_zone.loitering_threshold_seconds = 300
        mock_zone.loitering_alert_enabled = True

        with patch(
            "backend.api.routes.analytics_zones.get_polygon_zone_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_zone = AsyncMock(return_value=mock_zone)
            mock_get_service.return_value = mock_service

            await get_loitering_config(
                zone_id=42,
                db=mock_db,
            )

            # Verify zone_id is passed to service
            mock_service.get_zone.assert_called_once_with(42)


class TestUpdateLoiteringConfig:
    """Tests for PATCH /api/analytics-zones/polygon-zones/{zone_id}/loitering-config endpoint."""

    @pytest.mark.asyncio
    async def test_update_loitering_config_success(self) -> None:
        """Test successfully updating loitering configuration."""
        from backend.api.routes.analytics_zones import update_loitering_config

        mock_db = AsyncMock()

        mock_zone = MagicMock()
        mock_zone.id = 1
        mock_zone.name = "Backyard"
        mock_zone.loitering_threshold_seconds = 300
        mock_zone.loitering_alert_enabled = True

        config = LoiteringConfigUpdate(
            threshold_seconds=600,
            alert_enabled=False,
        )

        with patch(
            "backend.api.routes.analytics_zones.get_polygon_zone_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_zone = AsyncMock(return_value=mock_zone)
            mock_get_service.return_value = mock_service

            result = await update_loitering_config(
                zone_id=1,
                config=config,
                db=mock_db,
            )

        # Verify the zone was updated
        assert mock_zone.loitering_threshold_seconds == 600
        assert mock_zone.loitering_alert_enabled is False

        # Verify commit and refresh were called
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_zone)

        # Verify response
        assert result.zone_id == 1
        assert result.zone_name == "Backyard"
        assert result.threshold_seconds == 600
        assert result.alert_enabled is False

    @pytest.mark.asyncio
    async def test_update_loitering_config_zone_not_found(self) -> None:
        """Test update loitering config returns 404 if polygon zone doesn't exist."""
        from backend.api.routes.analytics_zones import update_loitering_config

        mock_db = AsyncMock()

        config = LoiteringConfigUpdate(
            threshold_seconds=300,
            alert_enabled=True,
        )

        with patch(
            "backend.api.routes.analytics_zones.get_polygon_zone_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_zone = AsyncMock(return_value=None)
            mock_get_service.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await update_loitering_config(
                    zone_id=999,
                    config=config,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 404
            assert "999" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_loitering_config_enable_alerts(self) -> None:
        """Test enabling alerts via update."""
        from backend.api.routes.analytics_zones import update_loitering_config

        mock_db = AsyncMock()

        mock_zone = MagicMock()
        mock_zone.id = 1
        mock_zone.name = "Pool Area"
        mock_zone.loitering_threshold_seconds = 300
        mock_zone.loitering_alert_enabled = False  # Initially disabled

        config = LoiteringConfigUpdate(
            threshold_seconds=300,
            alert_enabled=True,  # Enable alerts
        )

        with patch(
            "backend.api.routes.analytics_zones.get_polygon_zone_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_zone = AsyncMock(return_value=mock_zone)
            mock_get_service.return_value = mock_service

            result = await update_loitering_config(
                zone_id=1,
                config=config,
                db=mock_db,
            )

        assert result.alert_enabled is True
        assert mock_zone.loitering_alert_enabled is True

    @pytest.mark.asyncio
    async def test_update_loitering_config_minimum_threshold(self) -> None:
        """Test setting threshold to minimum value (0 seconds)."""
        from backend.api.routes.analytics_zones import update_loitering_config

        mock_db = AsyncMock()

        mock_zone = MagicMock()
        mock_zone.id = 1
        mock_zone.name = "Entry Zone"
        mock_zone.loitering_threshold_seconds = 300
        mock_zone.loitering_alert_enabled = True

        config = LoiteringConfigUpdate(
            threshold_seconds=0,  # Minimum value
            alert_enabled=True,
        )

        with patch(
            "backend.api.routes.analytics_zones.get_polygon_zone_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_zone = AsyncMock(return_value=mock_zone)
            mock_get_service.return_value = mock_service

            result = await update_loitering_config(
                zone_id=1,
                config=config,
                db=mock_db,
            )

        assert result.threshold_seconds == 0
        assert mock_zone.loitering_threshold_seconds == 0

    @pytest.mark.asyncio
    async def test_update_loitering_config_maximum_threshold(self) -> None:
        """Test setting threshold to maximum value (3600 seconds)."""
        from backend.api.routes.analytics_zones import update_loitering_config

        mock_db = AsyncMock()

        mock_zone = MagicMock()
        mock_zone.id = 1
        mock_zone.name = "Parking Area"
        mock_zone.loitering_threshold_seconds = 300
        mock_zone.loitering_alert_enabled = True

        config = LoiteringConfigUpdate(
            threshold_seconds=3600,  # Maximum value (1 hour)
            alert_enabled=True,
        )

        with patch(
            "backend.api.routes.analytics_zones.get_polygon_zone_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_zone = AsyncMock(return_value=mock_zone)
            mock_get_service.return_value = mock_service

            result = await update_loitering_config(
                zone_id=1,
                config=config,
                db=mock_db,
            )

        assert result.threshold_seconds == 3600
        assert mock_zone.loitering_threshold_seconds == 3600


class TestLoiteringConfigValidation:
    """Tests for validation of loitering configuration schemas."""

    def test_threshold_below_minimum_raises_error(self) -> None:
        """Test that threshold below 0 raises validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            LoiteringConfigUpdate(
                threshold_seconds=-1,  # Invalid: below 0
                alert_enabled=True,
            )

        assert "threshold_seconds" in str(exc_info.value)

    def test_threshold_above_maximum_raises_error(self) -> None:
        """Test that threshold above 3600 raises validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            LoiteringConfigUpdate(
                threshold_seconds=3601,  # Invalid: above 3600
                alert_enabled=True,
            )

        assert "threshold_seconds" in str(exc_info.value)

    def test_valid_threshold_at_boundaries(self) -> None:
        """Test that threshold at boundaries is valid."""
        # Minimum boundary
        config_min = LoiteringConfigUpdate(
            threshold_seconds=0,
            alert_enabled=True,
        )
        assert config_min.threshold_seconds == 0

        # Maximum boundary
        config_max = LoiteringConfigUpdate(
            threshold_seconds=3600,
            alert_enabled=True,
        )
        assert config_max.threshold_seconds == 3600

    def test_alert_enabled_defaults_to_true(self) -> None:
        """Test that alert_enabled defaults to True when not specified."""
        config = LoiteringConfigUpdate(threshold_seconds=300)
        assert config.alert_enabled is True

    def test_response_model_from_attributes(self) -> None:
        """Test that response model can be created from zone attributes."""
        response = LoiteringConfigResponse(
            zone_id=1,
            zone_name="Test Zone",
            threshold_seconds=300,
            alert_enabled=True,
        )
        assert response.zone_id == 1
        assert response.zone_name == "Test Zone"
        assert response.threshold_seconds == 300
        assert response.alert_enabled is True
