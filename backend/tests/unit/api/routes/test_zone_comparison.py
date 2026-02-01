"""Unit tests for zone comparison API endpoint.

Tests the GET /api/analytics-zones/comparison endpoint:
- Successful comparison across multiple zones
- Different metrics (crossings, dwell_time, anomalies, occupancy)
- Different time periods (day, week, month)
- Invalid metric/period validation
- Handling of non-existent zone IDs

These tests follow TDD methodology with proper mocking.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


class TestCompareZones:
    """Tests for GET /api/analytics-zones/comparison endpoint."""

    @pytest.mark.asyncio
    async def test_compare_zones_crossings_success(self) -> None:
        """Test successfully comparing crossings metric across zones."""
        from backend.api.routes.analytics_zones import compare_zones

        mock_db = AsyncMock()

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        mock_zones_data = [
            {
                "zone_id": 1,
                "zone_name": "Front Door Entry",
                "zone_type": "line",
                "camera_id": "front_door",
                "value": 42.0,
                "trend_percent": None,
            },
            {
                "zone_id": 2,
                "zone_name": "Pool Area",
                "zone_type": "restricted",
                "camera_id": "backyard",
                "value": 15.0,
                "trend_percent": None,
            },
        ]

        with patch(
            "backend.services.zone_comparison_service.get_zone_comparison_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.compare_zones = AsyncMock(return_value=mock_zones_data)
            mock_get_service.return_value = mock_service

            with patch("backend.api.routes.analytics_zones.utc_now", return_value=now):
                result = await compare_zones(
                    db=mock_db,
                    zone_ids=[1, 2],
                    metric="crossings",
                    period="day",
                )

        assert result.metric.value == "crossings"
        assert len(result.zones) == 2
        assert result.zones[0].zone_id == 1
        assert result.zones[0].zone_name == "Front Door Entry"
        assert result.zones[0].value == 42.0
        assert result.zones[1].zone_id == 2
        assert result.zones[1].value == 15.0
        assert result.comparison_period.value == "day"

    @pytest.mark.asyncio
    async def test_compare_zones_dwell_time_metric(self) -> None:
        """Test comparing dwell_time metric across zones."""
        from backend.api.routes.analytics_zones import compare_zones

        mock_db = AsyncMock()

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        mock_zones_data = [
            {
                "zone_id": 1,
                "zone_name": "Entry Zone",
                "zone_type": "entry",
                "camera_id": "front",
                "value": 120.5,  # Average dwell time in seconds
                "trend_percent": 15.3,
            },
        ]

        with patch(
            "backend.services.zone_comparison_service.get_zone_comparison_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.compare_zones = AsyncMock(return_value=mock_zones_data)
            mock_get_service.return_value = mock_service

            with patch("backend.api.routes.analytics_zones.utc_now", return_value=now):
                result = await compare_zones(
                    db=mock_db,
                    zone_ids=[1],
                    metric="dwell_time",
                    period="day",
                )

        assert result.metric.value == "dwell_time"
        assert len(result.zones) == 1
        assert result.zones[0].value == 120.5
        assert result.zones[0].trend_percent == 15.3

    @pytest.mark.asyncio
    async def test_compare_zones_anomalies_metric(self) -> None:
        """Test comparing anomalies metric across zones."""
        from backend.api.routes.analytics_zones import compare_zones

        mock_db = AsyncMock()

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        mock_zones_data = [
            {
                "zone_id": 1,
                "zone_name": "Restricted Zone",
                "zone_type": "restricted",
                "camera_id": "back",
                "value": 5.0,
                "trend_percent": -10.0,
            },
        ]

        with patch(
            "backend.services.zone_comparison_service.get_zone_comparison_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.compare_zones = AsyncMock(return_value=mock_zones_data)
            mock_get_service.return_value = mock_service

            with patch("backend.api.routes.analytics_zones.utc_now", return_value=now):
                result = await compare_zones(
                    db=mock_db,
                    zone_ids=[1],
                    metric="anomalies",
                    period="week",
                )

        assert result.metric.value == "anomalies"
        assert result.zones[0].value == 5.0
        assert result.zones[0].trend_percent == -10.0

    @pytest.mark.asyncio
    async def test_compare_zones_occupancy_metric(self) -> None:
        """Test comparing occupancy metric across zones."""
        from backend.api.routes.analytics_zones import compare_zones

        mock_db = AsyncMock()

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        mock_zones_data = [
            {
                "zone_id": 3,
                "zone_name": "Living Room",
                "zone_type": "monitored",
                "camera_id": "interior",
                "value": 2.0,
                "trend_percent": None,
            },
        ]

        with patch(
            "backend.services.zone_comparison_service.get_zone_comparison_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.compare_zones = AsyncMock(return_value=mock_zones_data)
            mock_get_service.return_value = mock_service

            with patch("backend.api.routes.analytics_zones.utc_now", return_value=now):
                result = await compare_zones(
                    db=mock_db,
                    zone_ids=[3],
                    metric="occupancy",
                    period="day",
                )

        assert result.metric.value == "occupancy"
        assert result.zones[0].value == 2.0

    @pytest.mark.asyncio
    async def test_compare_zones_week_period(self) -> None:
        """Test comparison with week period calculates correct time window."""
        from backend.api.routes.analytics_zones import compare_zones

        mock_db = AsyncMock()

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        expected_start = now - timedelta(days=7)

        with patch(
            "backend.services.zone_comparison_service.get_zone_comparison_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.compare_zones = AsyncMock(return_value=[])
            mock_get_service.return_value = mock_service

            with patch("backend.api.routes.analytics_zones.utc_now", return_value=now):
                result = await compare_zones(
                    db=mock_db,
                    zone_ids=[1],
                    metric="crossings",
                    period="week",
                )

        assert result.comparison_period.value == "week"
        assert result.start_time == expected_start
        assert result.end_time == now

        # Verify service was called with correct time window
        mock_service.compare_zones.assert_called_once()
        call_kwargs = mock_service.compare_zones.call_args[1]
        assert call_kwargs["start_time"] == expected_start
        assert call_kwargs["end_time"] == now

    @pytest.mark.asyncio
    async def test_compare_zones_month_period(self) -> None:
        """Test comparison with month period calculates correct time window."""
        from backend.api.routes.analytics_zones import compare_zones

        mock_db = AsyncMock()

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        expected_start = now - timedelta(days=30)

        with patch(
            "backend.services.zone_comparison_service.get_zone_comparison_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.compare_zones = AsyncMock(return_value=[])
            mock_get_service.return_value = mock_service

            with patch("backend.api.routes.analytics_zones.utc_now", return_value=now):
                result = await compare_zones(
                    db=mock_db,
                    zone_ids=[1],
                    metric="crossings",
                    period="month",
                )

        assert result.comparison_period.value == "month"
        assert result.start_time == expected_start

    @pytest.mark.asyncio
    async def test_compare_zones_invalid_metric(self) -> None:
        """Test comparison with invalid metric returns 400."""
        from backend.api.routes.analytics_zones import compare_zones

        mock_db = AsyncMock()

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)

        with patch("backend.api.routes.analytics_zones.utc_now", return_value=now):
            with pytest.raises(HTTPException) as exc_info:
                await compare_zones(
                    db=mock_db,
                    zone_ids=[1],
                    metric="invalid_metric",
                    period="day",
                )

        assert exc_info.value.status_code == 400
        assert "Invalid metric" in exc_info.value.detail
        assert "invalid_metric" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_compare_zones_invalid_period(self) -> None:
        """Test comparison with invalid period returns 400."""
        from backend.api.routes.analytics_zones import compare_zones

        mock_db = AsyncMock()

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)

        with patch("backend.api.routes.analytics_zones.utc_now", return_value=now):
            with pytest.raises(HTTPException) as exc_info:
                await compare_zones(
                    db=mock_db,
                    zone_ids=[1],
                    metric="crossings",
                    period="year",
                )

        assert exc_info.value.status_code == 400
        assert "Invalid period" in exc_info.value.detail
        assert "year" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_compare_zones_empty_results(self) -> None:
        """Test comparison when no zones are found returns empty list."""
        from backend.api.routes.analytics_zones import compare_zones

        mock_db = AsyncMock()

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)

        with patch(
            "backend.services.zone_comparison_service.get_zone_comparison_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.compare_zones = AsyncMock(return_value=[])
            mock_get_service.return_value = mock_service

            with patch("backend.api.routes.analytics_zones.utc_now", return_value=now):
                result = await compare_zones(
                    db=mock_db,
                    zone_ids=[999, 888],
                    metric="crossings",
                    period="day",
                )

        assert result.zones == []
        assert result.metric.value == "crossings"

    @pytest.mark.asyncio
    async def test_compare_zones_multiple_zones(self) -> None:
        """Test comparing multiple zones in single request."""
        from backend.api.routes.analytics_zones import compare_zones

        mock_db = AsyncMock()

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        mock_zones_data = [
            {
                "zone_id": 1,
                "zone_name": "Zone 1",
                "zone_type": "line",
                "camera_id": "cam1",
                "value": 10.0,
                "trend_percent": None,
            },
            {
                "zone_id": 2,
                "zone_name": "Zone 2",
                "zone_type": "monitored",
                "camera_id": "cam2",
                "value": 20.0,
                "trend_percent": 5.0,
            },
            {
                "zone_id": 3,
                "zone_name": "Zone 3",
                "zone_type": "restricted",
                "camera_id": "cam3",
                "value": 30.0,
                "trend_percent": -2.5,
            },
        ]

        with patch(
            "backend.services.zone_comparison_service.get_zone_comparison_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.compare_zones = AsyncMock(return_value=mock_zones_data)
            mock_get_service.return_value = mock_service

            with patch("backend.api.routes.analytics_zones.utc_now", return_value=now):
                result = await compare_zones(
                    db=mock_db,
                    zone_ids=[1, 2, 3],
                    metric="crossings",
                    period="day",
                )

        assert len(result.zones) == 3
        assert result.zones[0].zone_id == 1
        assert result.zones[1].zone_id == 2
        assert result.zones[2].zone_id == 3

        # Verify service was called with all zone IDs
        mock_service.compare_zones.assert_called_once()
        call_kwargs = mock_service.compare_zones.call_args[1]
        assert call_kwargs["zone_ids"] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_compare_zones_passes_metric_to_service(self) -> None:
        """Test that metric parameter is correctly passed to service."""
        from backend.api.routes.analytics_zones import compare_zones

        mock_db = AsyncMock()

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)

        with patch(
            "backend.services.zone_comparison_service.get_zone_comparison_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.compare_zones = AsyncMock(return_value=[])
            mock_get_service.return_value = mock_service

            with patch("backend.api.routes.analytics_zones.utc_now", return_value=now):
                await compare_zones(
                    db=mock_db,
                    zone_ids=[1],
                    metric="dwell_time",
                    period="day",
                )

        mock_service.compare_zones.assert_called_once()
        call_kwargs = mock_service.compare_zones.call_args[1]
        assert call_kwargs["metric"] == "dwell_time"
