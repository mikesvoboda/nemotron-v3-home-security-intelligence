"""Schemas for zone comparison endpoints.

These schemas support comparing metrics (crossings, dwell time, anomalies,
occupancy) across multiple zones for the Zone Analytics Dashboard.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ComparisonMetric(StrEnum):
    """Available metrics for zone comparison."""

    CROSSINGS = "crossings"
    DWELL_TIME = "dwell_time"
    ANOMALIES = "anomalies"
    OCCUPANCY = "occupancy"


class ComparisonPeriod(StrEnum):
    """Time periods for comparison."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class ZoneComparisonData(BaseModel):
    """Comparison data for a single zone.

    Contains the metric value and optional trend information
    for a zone being compared.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zone_id": 1,
                "zone_name": "Front Door Entry",
                "zone_type": "line",
                "camera_id": "front_door",
                "value": 42.5,
                "trend_percent": 12.3,
            }
        }
    )

    zone_id: int = Field(..., description="Unique zone identifier")
    zone_name: str = Field(..., description="Human-readable zone name")
    zone_type: str = Field(..., description="Type of zone: 'line' or polygon type")
    camera_id: str = Field(..., description="Camera ID the zone belongs to")
    value: float = Field(..., description="Metric value for this zone")
    trend_percent: float | None = Field(
        default=None,
        description="Percentage change vs previous period (positive = increase)",
    )


class ZoneComparisonResponse(BaseModel):
    """Response for zone comparison endpoint.

    Contains comparison data across multiple zones for a specific metric
    and time period.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "metric": "crossings",
                "zones": [
                    {
                        "zone_id": 1,
                        "zone_name": "Front Door Entry",
                        "zone_type": "line",
                        "camera_id": "front_door",
                        "value": 42.0,
                        "trend_percent": 12.3,
                    },
                    {
                        "zone_id": 2,
                        "zone_name": "Pool Area",
                        "zone_type": "restricted",
                        "camera_id": "backyard",
                        "value": 15.0,
                        "trend_percent": -5.2,
                    },
                ],
                "start_time": "2026-01-30T12:00:00Z",
                "end_time": "2026-01-31T12:00:00Z",
                "comparison_period": "day",
            }
        }
    )

    metric: ComparisonMetric = Field(..., description="The metric being compared")
    zones: list[ZoneComparisonData] = Field(
        ..., description="Comparison data for each requested zone"
    )
    start_time: datetime = Field(..., description="Start of the comparison time window")
    end_time: datetime = Field(..., description="End of the comparison time window")
    comparison_period: ComparisonPeriod = Field(
        ..., description="Time period for comparison: day, week, or month"
    )


__all__ = [
    "ComparisonMetric",
    "ComparisonPeriod",
    "ZoneComparisonData",
    "ZoneComparisonResponse",
]
