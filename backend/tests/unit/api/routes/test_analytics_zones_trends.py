"""Unit tests for line zone crossing trends API endpoint.

Tests the GET /api/analytics-zones/line-zones/{zone_id}/crossing-trends endpoint:
- Successful retrieval of crossing trends
- 404 for non-existent zone
- Query parameter handling (start_time, end_time, interval)

These tests follow TDD methodology with proper mocking.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.api.schemas.line_zone_analytics import (
    CrossingTrendDataPoint,
    CrossingTrendsResponse,
)


class TestGetCrossingTrends:
    """Tests for GET /api/analytics-zones/line-zones/{zone_id}/crossing-trends endpoint."""

    @pytest.mark.asyncio
    async def test_get_crossing_trends_success(self) -> None:
        """Test successfully retrieving crossing trends for a line zone."""
        from backend.api.routes.analytics_zones import get_crossing_trends

        mock_db = AsyncMock()

        # Create mock response
        now = datetime(2026, 1, 26, 12, 0, 0, tzinfo=UTC)
        mock_trends_response = CrossingTrendsResponse(
            zone_id=1,
            zone_name="Driveway Entrance",
            trends=[
                CrossingTrendDataPoint(
                    timestamp=now,
                    in_count=15,
                    out_count=12,
                    net_flow=3,
                )
            ],
            total_in=15,
            total_out=12,
            start_time=now - timedelta(hours=24),
            end_time=now,
            interval="hour",
        )

        with patch("backend.api.routes.analytics_zones.get_line_zone_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_crossing_trends = AsyncMock(return_value=mock_trends_response)
            mock_get_service.return_value = mock_service

            with patch("backend.api.routes.analytics_zones.utc_now", return_value=now):
                result = await get_crossing_trends(
                    zone_id=1,
                    db=mock_db,
                    start_time=None,
                    end_time=None,
                    interval="hour",
                )

        assert result.zone_id == 1
        assert result.zone_name == "Driveway Entrance"
        assert len(result.trends) == 1
        assert result.trends[0].in_count == 15
        assert result.trends[0].out_count == 12
        assert result.trends[0].net_flow == 3
        assert result.total_in == 15
        assert result.total_out == 12
        assert result.interval == "hour"

    @pytest.mark.asyncio
    async def test_get_crossing_trends_zone_not_found(self) -> None:
        """Test crossing trends returns 404 if line zone doesn't exist."""
        from backend.api.routes.analytics_zones import get_crossing_trends

        mock_db = AsyncMock()

        with patch("backend.api.routes.analytics_zones.get_line_zone_service") as mock_get_service:
            mock_service = MagicMock()
            # Service returns None when zone not found
            mock_service.get_crossing_trends = AsyncMock(return_value=None)
            mock_get_service.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await get_crossing_trends(
                    zone_id=999,
                    db=mock_db,
                    start_time=None,
                    end_time=None,
                    interval="hour",
                )

            assert exc_info.value.status_code == 404
            assert "999" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_crossing_trends_with_custom_time_window(self) -> None:
        """Test crossing trends with custom start_time and end_time."""
        from backend.api.routes.analytics_zones import get_crossing_trends

        mock_db = AsyncMock()

        custom_start = datetime(2026, 1, 25, 0, 0, 0, tzinfo=UTC)
        custom_end = datetime(2026, 1, 26, 0, 0, 0, tzinfo=UTC)

        mock_trends_response = CrossingTrendsResponse(
            zone_id=1,
            zone_name="Test Zone",
            trends=[],
            total_in=0,
            total_out=0,
            start_time=custom_start,
            end_time=custom_end,
            interval="hour",
        )

        with patch("backend.api.routes.analytics_zones.get_line_zone_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_crossing_trends = AsyncMock(return_value=mock_trends_response)
            mock_get_service.return_value = mock_service

            result = await get_crossing_trends(
                zone_id=1,
                db=mock_db,
                start_time=custom_start,
                end_time=custom_end,
                interval="hour",
            )

        # Verify custom times are passed to service
        mock_service.get_crossing_trends.assert_called_once_with(
            zone_id=1,
            start_time=custom_start,
            end_time=custom_end,
            interval="hour",
        )
        assert result.start_time == custom_start
        assert result.end_time == custom_end

    @pytest.mark.asyncio
    async def test_get_crossing_trends_with_day_interval(self) -> None:
        """Test crossing trends with day interval."""
        from backend.api.routes.analytics_zones import get_crossing_trends

        mock_db = AsyncMock()

        now = datetime(2026, 1, 26, 12, 0, 0, tzinfo=UTC)
        mock_trends_response = CrossingTrendsResponse(
            zone_id=1,
            zone_name="Test Zone",
            trends=[],
            total_in=50,
            total_out=45,
            start_time=now - timedelta(days=7),
            end_time=now,
            interval="day",
        )

        with patch("backend.api.routes.analytics_zones.get_line_zone_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_crossing_trends = AsyncMock(return_value=mock_trends_response)
            mock_get_service.return_value = mock_service

            with patch("backend.api.routes.analytics_zones.utc_now", return_value=now):
                result = await get_crossing_trends(
                    zone_id=1,
                    db=mock_db,
                    start_time=None,
                    end_time=None,
                    interval="day",
                )

        assert result.interval == "day"
        # Verify interval is passed correctly
        mock_service.get_crossing_trends.assert_called_once()
        call_kwargs = mock_service.get_crossing_trends.call_args[1]
        assert call_kwargs["interval"] == "day"

    @pytest.mark.asyncio
    async def test_get_crossing_trends_default_time_window(self) -> None:
        """Test crossing trends uses last 24 hours when no times specified."""
        from backend.api.routes.analytics_zones import get_crossing_trends

        mock_db = AsyncMock()

        now = datetime(2026, 1, 26, 12, 0, 0, tzinfo=UTC)
        expected_start = now - timedelta(hours=24)

        mock_trends_response = CrossingTrendsResponse(
            zone_id=1,
            zone_name="Test Zone",
            trends=[],
            total_in=10,
            total_out=8,
            start_time=expected_start,
            end_time=now,
            interval="hour",
        )

        with patch("backend.api.routes.analytics_zones.get_line_zone_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_crossing_trends = AsyncMock(return_value=mock_trends_response)
            mock_get_service.return_value = mock_service

            with patch("backend.api.routes.analytics_zones.utc_now", return_value=now):
                result = await get_crossing_trends(
                    zone_id=1,
                    db=mock_db,
                    start_time=None,  # No start time
                    end_time=None,  # No end time
                    interval="hour",
                )

        # Verify default time window is 24 hours
        mock_service.get_crossing_trends.assert_called_once()
        call_kwargs = mock_service.get_crossing_trends.call_args[1]
        assert call_kwargs["start_time"] == expected_start
        assert call_kwargs["end_time"] == now

    @pytest.mark.asyncio
    async def test_get_crossing_trends_empty_trends_list(self) -> None:
        """Test crossing trends returns empty list for zone with no crossings."""
        from backend.api.routes.analytics_zones import get_crossing_trends

        mock_db = AsyncMock()

        now = datetime(2026, 1, 26, 12, 0, 0, tzinfo=UTC)
        mock_trends_response = CrossingTrendsResponse(
            zone_id=1,
            zone_name="Empty Zone",
            trends=[],
            total_in=0,
            total_out=0,
            start_time=now - timedelta(hours=24),
            end_time=now,
            interval="hour",
        )

        with patch("backend.api.routes.analytics_zones.get_line_zone_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_crossing_trends = AsyncMock(return_value=mock_trends_response)
            mock_get_service.return_value = mock_service

            with patch("backend.api.routes.analytics_zones.utc_now", return_value=now):
                result = await get_crossing_trends(
                    zone_id=1,
                    db=mock_db,
                    start_time=None,
                    end_time=None,
                    interval="hour",
                )

        assert result.zone_id == 1
        assert result.zone_name == "Empty Zone"
        assert result.trends == []
        assert result.total_in == 0
        assert result.total_out == 0

    @pytest.mark.asyncio
    async def test_get_crossing_trends_with_partial_end_time(self) -> None:
        """Test crossing trends with only end_time specified uses defaults for start."""
        from backend.api.routes.analytics_zones import get_crossing_trends

        mock_db = AsyncMock()

        now = datetime(2026, 1, 26, 12, 0, 0, tzinfo=UTC)
        custom_end = datetime(2026, 1, 26, 6, 0, 0, tzinfo=UTC)
        expected_start = now - timedelta(hours=24)

        mock_trends_response = CrossingTrendsResponse(
            zone_id=1,
            zone_name="Test Zone",
            trends=[],
            total_in=5,
            total_out=3,
            start_time=expected_start,
            end_time=custom_end,
            interval="hour",
        )

        with patch("backend.api.routes.analytics_zones.get_line_zone_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_crossing_trends = AsyncMock(return_value=mock_trends_response)
            mock_get_service.return_value = mock_service

            with patch("backend.api.routes.analytics_zones.utc_now", return_value=now):
                result = await get_crossing_trends(
                    zone_id=1,
                    db=mock_db,
                    start_time=None,  # Not specified, uses default
                    end_time=custom_end,
                    interval="hour",
                )

        # Verify custom end time is used and start time defaults to 24h before now
        mock_service.get_crossing_trends.assert_called_once()
        call_kwargs = mock_service.get_crossing_trends.call_args[1]
        assert call_kwargs["end_time"] == custom_end
        assert call_kwargs["start_time"] == expected_start

    @pytest.mark.asyncio
    async def test_get_crossing_trends_verifies_zone_exists(self) -> None:
        """Test crossing trends calls service with correct zone_id."""
        from backend.api.routes.analytics_zones import get_crossing_trends

        mock_db = AsyncMock()

        now = datetime(2026, 1, 26, 12, 0, 0, tzinfo=UTC)
        mock_trends_response = CrossingTrendsResponse(
            zone_id=42,
            zone_name="Zone 42",
            trends=[],
            total_in=0,
            total_out=0,
            start_time=now - timedelta(hours=24),
            end_time=now,
            interval="hour",
        )

        with patch("backend.api.routes.analytics_zones.get_line_zone_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_crossing_trends = AsyncMock(return_value=mock_trends_response)
            mock_get_service.return_value = mock_service

            with patch("backend.api.routes.analytics_zones.utc_now", return_value=now):
                result = await get_crossing_trends(
                    zone_id=42,
                    db=mock_db,
                    start_time=None,
                    end_time=None,
                    interval="hour",
                )

        # Verify zone_id is passed to service
        mock_service.get_crossing_trends.assert_called_once()
        call_kwargs = mock_service.get_crossing_trends.call_args[1]
        assert call_kwargs["zone_id"] == 42
        assert result.zone_id == 42
