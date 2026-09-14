"""Unit tests for zone comparison service.

Tests the ZoneComparisonService:
- compare_zones with different metrics
- Zone info retrieval for line and polygon zones
- Metric calculations (crossings, dwell_time, anomalies, occupancy)
- Trend calculation

These tests follow TDD methodology with proper mocking.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.zone_comparison_service import (
    ZoneComparisonService,
    get_zone_comparison_service,
)


class TestZoneComparisonService:
    """Tests for ZoneComparisonService class."""

    @pytest.mark.asyncio
    async def test_compare_zones_crossings_metric(self) -> None:
        """Test comparing crossings metric across zones."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        # Mock _get_zone_info to return zone data
        with patch.object(service, "_get_zone_info", new_callable=AsyncMock) as mock_zone_info:
            mock_zone_info.side_effect = [
                {"name": "Entry Line", "type": "line", "camera_id": "front"},
                {"name": "Pool Zone", "type": "restricted", "camera_id": "back"},
            ]

            with patch.object(
                service, "_get_crossing_count", new_callable=AsyncMock
            ) as mock_crossings:
                mock_crossings.side_effect = [50.0, 10.0]

                with patch.object(
                    service, "_calculate_trend", new_callable=AsyncMock
                ) as mock_trend:
                    mock_trend.return_value = None

                    results = await service.compare_zones(
                        zone_ids=[1, 2],
                        metric="crossings",
                        start_time=start_time,
                        end_time=now,
                    )

        assert len(results) == 2
        assert results[0]["zone_id"] == 1
        assert results[0]["zone_name"] == "Entry Line"
        assert results[0]["value"] == 50.0
        assert results[1]["zone_id"] == 2
        assert results[1]["value"] == 10.0

    @pytest.mark.asyncio
    async def test_compare_zones_dwell_time_metric(self) -> None:
        """Test comparing dwell_time metric across zones."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        with patch.object(service, "_get_zone_info", new_callable=AsyncMock) as mock_zone_info:
            mock_zone_info.return_value = {
                "name": "Entry Zone",
                "type": "entry",
                "camera_id": "front",
            }

            with patch.object(service, "_get_avg_dwell_time", new_callable=AsyncMock) as mock_dwell:
                mock_dwell.return_value = 120.5

                with patch.object(
                    service, "_calculate_trend", new_callable=AsyncMock
                ) as mock_trend:
                    mock_trend.return_value = 15.0

                    results = await service.compare_zones(
                        zone_ids=[1],
                        metric="dwell_time",
                        start_time=start_time,
                        end_time=now,
                    )

        assert len(results) == 1
        assert results[0]["value"] == 120.5
        assert results[0]["trend_percent"] == 15.0

    @pytest.mark.asyncio
    async def test_compare_zones_anomalies_metric(self) -> None:
        """Test comparing anomalies metric across zones."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        with patch.object(service, "_get_zone_info", new_callable=AsyncMock) as mock_zone_info:
            mock_zone_info.return_value = {
                "name": "Restricted Zone",
                "type": "restricted",
                "camera_id": "secure",
            }

            with patch.object(
                service, "_get_anomaly_count", new_callable=AsyncMock
            ) as mock_anomalies:
                mock_anomalies.return_value = 3.0

                with patch.object(
                    service, "_calculate_trend", new_callable=AsyncMock
                ) as mock_trend:
                    mock_trend.return_value = -10.0

                    results = await service.compare_zones(
                        zone_ids=[1],
                        metric="anomalies",
                        start_time=start_time,
                        end_time=now,
                    )

        assert results[0]["value"] == 3.0
        assert results[0]["trend_percent"] == -10.0

    @pytest.mark.asyncio
    async def test_compare_zones_occupancy_metric(self) -> None:
        """Test comparing occupancy metric across zones."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        with patch.object(service, "_get_zone_info", new_callable=AsyncMock) as mock_zone_info:
            mock_zone_info.return_value = {
                "name": "Lobby",
                "type": "monitored",
                "camera_id": "lobby",
            }

            with patch.object(
                service, "_get_current_occupancy", new_callable=AsyncMock
            ) as mock_occupancy:
                mock_occupancy.return_value = 5.0

                with patch.object(
                    service, "_calculate_trend", new_callable=AsyncMock
                ) as mock_trend:
                    mock_trend.return_value = None

                    results = await service.compare_zones(
                        zone_ids=[1],
                        metric="occupancy",
                        start_time=start_time,
                        end_time=now,
                    )

        assert results[0]["value"] == 5.0

    @pytest.mark.asyncio
    async def test_compare_zones_skips_missing_zones(self) -> None:
        """Test that missing zones are skipped without error."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        with patch.object(service, "_get_zone_info", new_callable=AsyncMock) as mock_zone_info:
            # First zone exists, second doesn't
            mock_zone_info.side_effect = [
                {"name": "Zone 1", "type": "line", "camera_id": "cam1"},
                None,  # Zone 2 not found
            ]

            with patch.object(
                service, "_get_crossing_count", new_callable=AsyncMock
            ) as mock_crossings:
                mock_crossings.return_value = 10.0

                with patch.object(
                    service, "_calculate_trend", new_callable=AsyncMock
                ) as mock_trend:
                    mock_trend.return_value = None

                    results = await service.compare_zones(
                        zone_ids=[1, 999],
                        metric="crossings",
                        start_time=start_time,
                        end_time=now,
                    )

        # Only zone 1 should be in results
        assert len(results) == 1
        assert results[0]["zone_id"] == 1

    @pytest.mark.asyncio
    async def test_compare_zones_unknown_metric_defaults_to_zero(self) -> None:
        """Test that unknown metric defaults to 0 value."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        with patch.object(service, "_get_zone_info", new_callable=AsyncMock) as mock_zone_info:
            mock_zone_info.return_value = {
                "name": "Zone 1",
                "type": "line",
                "camera_id": "cam1",
            }

            with patch.object(service, "_calculate_trend", new_callable=AsyncMock) as mock_trend:
                mock_trend.return_value = None

                results = await service.compare_zones(
                    zone_ids=[1],
                    metric="unknown_metric",
                    start_time=start_time,
                    end_time=now,
                )

        assert results[0]["value"] == 0.0


class TestGetZoneInfo:
    """Tests for _get_zone_info method."""

    @pytest.mark.asyncio
    async def test_get_zone_info_polygon_zone(self) -> None:
        """Test getting info for a polygon zone."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        # Create mock polygon zone
        mock_polygon_zone = MagicMock()
        mock_polygon_zone.name = "Pool Area"
        mock_polygon_zone.zone_type = "restricted"
        mock_polygon_zone.camera_id = "backyard"

        # Mock the database query to return polygon zone
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_polygon_zone
        mock_db.execute.return_value = mock_result

        result = await service._get_zone_info(1)

        assert result is not None
        assert result["name"] == "Pool Area"
        assert result["type"] == "restricted"
        assert result["camera_id"] == "backyard"

    @pytest.mark.asyncio
    async def test_get_zone_info_line_zone(self) -> None:
        """Test getting info for a line zone when polygon not found."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        # Create mock line zone
        mock_line_zone = MagicMock()
        mock_line_zone.name = "Entry Line"
        mock_line_zone.camera_id = "front_door"

        # Mock - first query returns None (no polygon), second returns line zone
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = None

        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_line_zone

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        result = await service._get_zone_info(1)

        assert result is not None
        assert result["name"] == "Entry Line"
        assert result["type"] == "line"
        assert result["camera_id"] == "front_door"

    @pytest.mark.asyncio
    async def test_get_zone_info_not_found(self) -> None:
        """Test getting info for non-existent zone returns None."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        # Both queries return None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await service._get_zone_info(999)

        assert result is None


class TestCrossingCount:
    """Tests for _get_crossing_count method."""

    @pytest.mark.asyncio
    async def test_get_crossing_count_line_zone(self) -> None:
        """Test getting crossing count for a line zone."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        mock_zone = MagicMock()
        mock_zone.in_count = 25
        mock_zone.out_count = 20

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_zone
        mock_db.execute.return_value = mock_result

        result = await service._get_crossing_count(1)

        assert result == 45.0

    @pytest.mark.asyncio
    async def test_get_crossing_count_not_found(self) -> None:
        """Test crossing count returns 0 for non-existent zone."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await service._get_crossing_count(999)

        assert result == 0.0


class TestAvgDwellTime:
    """Tests for _get_avg_dwell_time method."""

    @pytest.mark.asyncio
    async def test_get_avg_dwell_time_with_records(self) -> None:
        """Test getting average dwell time with existing records."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 150.5
        mock_db.execute.return_value = mock_result

        result = await service._get_avg_dwell_time(1, start_time, now)

        assert result == 150.5

    @pytest.mark.asyncio
    async def test_get_avg_dwell_time_no_records(self) -> None:
        """Test average dwell time returns 0 with no records."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await service._get_avg_dwell_time(1, start_time, now)

        assert result == 0.0


class TestAnomalyCount:
    """Tests for _get_anomaly_count method."""

    @pytest.mark.asyncio
    async def test_get_anomaly_count_with_anomalies(self) -> None:
        """Test getting anomaly count with existing anomalies."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 5
        mock_db.execute.return_value = mock_result

        result = await service._get_anomaly_count(1, start_time, now)

        assert result == 5.0

    @pytest.mark.asyncio
    async def test_get_anomaly_count_no_anomalies(self) -> None:
        """Test anomaly count returns 0 with no anomalies."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await service._get_anomaly_count(1, start_time, now)

        assert result == 0.0


class TestCurrentOccupancy:
    """Tests for _get_current_occupancy method."""

    @pytest.mark.asyncio
    async def test_get_current_occupancy_polygon_zone(self) -> None:
        """Test getting current occupancy for a polygon zone."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        mock_zone = MagicMock()
        mock_zone.current_count = 3

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_zone
        mock_db.execute.return_value = mock_result

        result = await service._get_current_occupancy(1)

        assert result == 3.0

    @pytest.mark.asyncio
    async def test_get_current_occupancy_not_found(self) -> None:
        """Test occupancy returns 0 for non-existent zone."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await service._get_current_occupancy(999)

        assert result == 0.0


class TestCalculateTrend:
    """Tests for _calculate_trend method."""

    @pytest.mark.asyncio
    async def test_calculate_trend_dwell_time_increase(self) -> None:
        """Test trend calculation for dwell_time with increase."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        with patch.object(service, "_get_avg_dwell_time", new_callable=AsyncMock) as mock_dwell:
            # Current period: 120s, Previous period: 100s
            mock_dwell.side_effect = [120.0, 100.0]

            result = await service._calculate_trend(
                zone_id=1,
                metric="dwell_time",
                start_time=start_time,
                end_time=now,
            )

        assert result == 20.0  # 20% increase

    @pytest.mark.asyncio
    async def test_calculate_trend_anomalies_decrease(self) -> None:
        """Test trend calculation for anomalies with decrease."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        with patch.object(service, "_get_anomaly_count", new_callable=AsyncMock) as mock_anomalies:
            # Current period: 8, Previous period: 10
            mock_anomalies.side_effect = [8.0, 10.0]

            result = await service._calculate_trend(
                zone_id=1,
                metric="anomalies",
                start_time=start_time,
                end_time=now,
            )

        assert result == -20.0  # 20% decrease

    @pytest.mark.asyncio
    async def test_calculate_trend_crossings_returns_none(self) -> None:
        """Test trend calculation for crossings returns None (no historical data)."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        result = await service._calculate_trend(
            zone_id=1,
            metric="crossings",
            start_time=start_time,
            end_time=now,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_calculate_trend_from_zero(self) -> None:
        """Test trend calculation when previous period is zero."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        with patch.object(service, "_get_anomaly_count", new_callable=AsyncMock) as mock_anomalies:
            # Current period: 5, Previous period: 0
            mock_anomalies.side_effect = [5.0, 0.0]

            result = await service._calculate_trend(
                zone_id=1,
                metric="anomalies",
                start_time=start_time,
                end_time=now,
            )

        assert result == 100.0  # 100% increase from 0

    @pytest.mark.asyncio
    async def test_calculate_trend_both_zero(self) -> None:
        """Test trend calculation when both periods are zero."""
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        with patch.object(service, "_get_anomaly_count", new_callable=AsyncMock) as mock_anomalies:
            mock_anomalies.side_effect = [0.0, 0.0]

            result = await service._calculate_trend(
                zone_id=1,
                metric="anomalies",
                start_time=start_time,
                end_time=now,
            )

        assert result == 0.0


class TestGetZoneComparisonService:
    """Tests for get_zone_comparison_service factory function."""

    def test_get_zone_comparison_service_returns_instance(self) -> None:
        """Test factory function returns a ZoneComparisonService instance."""
        mock_db = MagicMock()
        service = get_zone_comparison_service(mock_db)

        assert isinstance(service, ZoneComparisonService)
        assert service.db is mock_db
