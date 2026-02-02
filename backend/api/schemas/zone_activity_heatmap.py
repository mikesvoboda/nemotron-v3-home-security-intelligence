"""Pydantic schemas for zone activity heatmap API endpoints.

This module provides request/response schemas for zone activity heatmaps,
which visualize activity patterns by hour of day and day of week.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class HeatmapTimeRange(StrEnum):
    """Time range options for heatmap data aggregation."""

    HOUR_1 = "1h"
    HOUR_6 = "6h"
    HOUR_24 = "24h"
    DAY_7 = "7d"
    DAY_30 = "30d"


class HeatmapDataPoint(BaseModel):
    """A single data point in the activity heatmap.

    Represents activity count for a specific hour and day of week combination.

    Attributes:
        hour: Hour of day (0-23)
        day_of_week: Day of week (0=Sunday, 6=Saturday)
        value: Activity count/intensity for this time slot
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hour": 14,
                "day_of_week": 1,
                "value": 12,
            }
        }
    )

    hour: int = Field(..., ge=0, le=23, description="Hour of day (0-23)")
    day_of_week: int = Field(..., ge=0, le=6, description="Day of week (0=Sunday, 6=Saturday)")
    value: int = Field(..., ge=0, description="Activity count for this time slot")


class HourlyActivity(BaseModel):
    """Hourly activity data for today's summary.

    Attributes:
        hour: Hour of day (0-23)
        count: Number of activity events during this hour
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hour": 9,
                "count": 15,
            }
        }
    )

    hour: int = Field(..., ge=0, le=23, description="Hour of day (0-23)")
    count: int = Field(..., ge=0, description="Activity count for this hour")


class ZoneActivityHeatmapResponse(BaseModel):
    """Response containing zone activity heatmap data.

    Provides activity patterns aggregated by hour and day of week for
    visualizing when a zone is most active.

    Attributes:
        zone_id: ID of the polygon zone
        zone_name: Name of the zone for display
        time_range: Time range used for aggregation
        weekly_data: Activity data points for the hour/day matrix (7 days x 24 hours)
        hourly_data: Today's activity by hour
        total_activity: Total activity count in the time range
        start_time: Start of the query time window
        end_time: End of the query time window
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zone_id": 1,
                "zone_name": "Front Door",
                "time_range": "7d",
                "weekly_data": [
                    {"hour": 8, "day_of_week": 1, "value": 15},
                    {"hour": 9, "day_of_week": 1, "value": 22},
                    {"hour": 17, "day_of_week": 1, "value": 18},
                ],
                "hourly_data": [
                    {"hour": 0, "count": 2},
                    {"hour": 1, "count": 0},
                    {"hour": 8, "count": 12},
                ],
                "total_activity": 342,
                "start_time": "2026-01-25T00:00:00Z",
                "end_time": "2026-02-01T00:00:00Z",
            }
        }
    )

    zone_id: int = Field(..., description="ID of the polygon zone")
    zone_name: str = Field(..., description="Name of the zone for display")
    time_range: HeatmapTimeRange = Field(..., description="Time range used for aggregation")
    weekly_data: list[HeatmapDataPoint] = Field(
        ..., description="Activity data points for hour/day matrix"
    )
    hourly_data: list[HourlyActivity] = Field(..., description="Today's activity by hour")
    total_activity: int = Field(..., ge=0, description="Total activity count in time range")
    start_time: datetime = Field(..., description="Start of the query time window")
    end_time: datetime = Field(..., description="End of the query time window")


# Export all schemas
__all__ = [
    "HeatmapDataPoint",
    "HeatmapTimeRange",
    "HourlyActivity",
    "ZoneActivityHeatmapResponse",
]
