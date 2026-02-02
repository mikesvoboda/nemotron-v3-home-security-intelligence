"""Unit tests for zone activity heatmap schemas (NEM-5024).

Tests schema validation for zone activity heatmap API request/response models.
"""

from datetime import UTC, datetime

import pytest

from backend.api.schemas.zone_activity_heatmap import (
    HeatmapDataPoint,
    HeatmapTimeRange,
    HourlyActivity,
    ZoneActivityHeatmapResponse,
)


class TestHeatmapTimeRange:
    """Tests for HeatmapTimeRange enum."""

    def test_valid_values(self) -> None:
        """Test that all expected time range values exist."""
        assert HeatmapTimeRange.HOUR_1 == "1h"
        assert HeatmapTimeRange.HOUR_6 == "6h"
        assert HeatmapTimeRange.HOUR_24 == "24h"
        assert HeatmapTimeRange.DAY_7 == "7d"
        assert HeatmapTimeRange.DAY_30 == "30d"

    def test_from_string(self) -> None:
        """Test converting string to enum."""
        assert HeatmapTimeRange("1h") == HeatmapTimeRange.HOUR_1
        assert HeatmapTimeRange("7d") == HeatmapTimeRange.DAY_7


class TestHeatmapDataPoint:
    """Tests for HeatmapDataPoint schema."""

    def test_valid_data_point(self) -> None:
        """Test creating a valid data point."""
        dp = HeatmapDataPoint(hour=14, day_of_week=1, value=12)
        assert dp.hour == 14
        assert dp.day_of_week == 1
        assert dp.value == 12

    def test_boundary_values(self) -> None:
        """Test boundary values for hour and day."""
        # Minimum values
        dp_min = HeatmapDataPoint(hour=0, day_of_week=0, value=0)
        assert dp_min.hour == 0
        assert dp_min.day_of_week == 0

        # Maximum values
        dp_max = HeatmapDataPoint(hour=23, day_of_week=6, value=1000)
        assert dp_max.hour == 23
        assert dp_max.day_of_week == 6

    def test_invalid_hour(self) -> None:
        """Test that invalid hour values are rejected."""
        with pytest.raises(ValueError):
            HeatmapDataPoint(hour=24, day_of_week=0, value=0)
        with pytest.raises(ValueError):
            HeatmapDataPoint(hour=-1, day_of_week=0, value=0)

    def test_invalid_day_of_week(self) -> None:
        """Test that invalid day_of_week values are rejected."""
        with pytest.raises(ValueError):
            HeatmapDataPoint(hour=0, day_of_week=7, value=0)
        with pytest.raises(ValueError):
            HeatmapDataPoint(hour=0, day_of_week=-1, value=0)

    def test_invalid_value(self) -> None:
        """Test that negative values are rejected."""
        with pytest.raises(ValueError):
            HeatmapDataPoint(hour=0, day_of_week=0, value=-1)


class TestHourlyActivity:
    """Tests for HourlyActivity schema."""

    def test_valid_hourly_activity(self) -> None:
        """Test creating a valid hourly activity."""
        ha = HourlyActivity(hour=9, count=15)
        assert ha.hour == 9
        assert ha.count == 15

    def test_boundary_values(self) -> None:
        """Test boundary values."""
        # Minimum
        ha_min = HourlyActivity(hour=0, count=0)
        assert ha_min.hour == 0
        assert ha_min.count == 0

        # Maximum hour
        ha_max = HourlyActivity(hour=23, count=1000)
        assert ha_max.hour == 23

    def test_invalid_hour(self) -> None:
        """Test that invalid hour values are rejected."""
        with pytest.raises(ValueError):
            HourlyActivity(hour=24, count=0)

    def test_invalid_count(self) -> None:
        """Test that negative count values are rejected."""
        with pytest.raises(ValueError):
            HourlyActivity(hour=0, count=-1)


class TestZoneActivityHeatmapResponse:
    """Tests for ZoneActivityHeatmapResponse schema."""

    def test_valid_response(self) -> None:
        """Test creating a valid response."""
        now = datetime.now(UTC)
        start = datetime(2026, 1, 25, 0, 0, 0, tzinfo=UTC)

        response = ZoneActivityHeatmapResponse(
            zone_id=1,
            zone_name="Front Door",
            time_range=HeatmapTimeRange.DAY_7,
            weekly_data=[
                HeatmapDataPoint(hour=8, day_of_week=1, value=15),
                HeatmapDataPoint(hour=9, day_of_week=1, value=22),
            ],
            hourly_data=[
                HourlyActivity(hour=0, count=2),
                HourlyActivity(hour=8, count=12),
            ],
            total_activity=342,
            start_time=start,
            end_time=now,
        )

        assert response.zone_id == 1
        assert response.zone_name == "Front Door"
        assert response.time_range == HeatmapTimeRange.DAY_7
        assert len(response.weekly_data) == 2
        assert len(response.hourly_data) == 2
        assert response.total_activity == 342

    def test_empty_data(self) -> None:
        """Test response with empty data arrays."""
        now = datetime.now(UTC)
        start = datetime(2026, 1, 25, 0, 0, 0, tzinfo=UTC)

        response = ZoneActivityHeatmapResponse(
            zone_id=1,
            zone_name="Empty Zone",
            time_range=HeatmapTimeRange.HOUR_1,
            weekly_data=[],
            hourly_data=[],
            total_activity=0,
            start_time=start,
            end_time=now,
        )

        assert len(response.weekly_data) == 0
        assert len(response.hourly_data) == 0
        assert response.total_activity == 0

    def test_invalid_total_activity(self) -> None:
        """Test that negative total_activity is rejected."""
        now = datetime.now(UTC)
        start = datetime(2026, 1, 25, 0, 0, 0, tzinfo=UTC)

        with pytest.raises(ValueError):
            ZoneActivityHeatmapResponse(
                zone_id=1,
                zone_name="Test",
                time_range=HeatmapTimeRange.DAY_7,
                weekly_data=[],
                hourly_data=[],
                total_activity=-1,
                start_time=start,
                end_time=now,
            )

    def test_json_serialization(self) -> None:
        """Test that response can be serialized to JSON."""
        now = datetime.now(UTC)
        start = datetime(2026, 1, 25, 0, 0, 0, tzinfo=UTC)

        response = ZoneActivityHeatmapResponse(
            zone_id=1,
            zone_name="Test Zone",
            time_range=HeatmapTimeRange.DAY_7,
            weekly_data=[HeatmapDataPoint(hour=0, day_of_week=0, value=5)],
            hourly_data=[HourlyActivity(hour=0, count=3)],
            total_activity=5,
            start_time=start,
            end_time=now,
        )

        json_data = response.model_dump_json()
        assert "zone_id" in json_data
        assert "weekly_data" in json_data
        assert "hourly_data" in json_data
