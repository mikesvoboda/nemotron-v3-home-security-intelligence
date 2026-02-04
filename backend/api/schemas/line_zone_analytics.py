"""Schemas for line zone analytics endpoints.

This module defines schemas for line zone crossing analytics:
- CrossingTrendDataPoint: Single data point in time-series crossing data
- CrossingTrendsResponse: Full response for crossing trends endpoint
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CrossingTrendDataPoint(BaseModel):
    """Single data point in crossing trends time series.

    Represents aggregated crossing counts for a specific time bucket
    (e.g., one hour or one day).

    Attributes:
        timestamp: Start of the time bucket.
        in_count: Number of crossings in the positive direction during this period.
        out_count: Number of crossings in the negative direction during this period.
        net_flow: Net flow calculated as in_count - out_count.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "timestamp": "2026-01-26T12:00:00Z",
                "in_count": 15,
                "out_count": 12,
                "net_flow": 3,
            }
        },
    )

    timestamp: datetime = Field(..., description="Start of the time bucket")
    in_count: int = Field(ge=0, description="Crossings in positive direction")
    out_count: int = Field(ge=0, description="Crossings in negative direction")
    net_flow: int = Field(description="Net flow (in - out)")


class CrossingTrendsResponse(BaseModel):
    """Response for crossing trends endpoint.

    Contains time-series crossing data for a line zone, aggregated
    by the specified interval (hour or day).

    Attributes:
        zone_id: The unique identifier of the line zone.
        zone_name: Human-readable name of the line zone.
        trends: List of time-bucketed crossing data points.
        total_in: Total crossings in positive direction across all buckets.
        total_out: Total crossings in negative direction across all buckets.
        start_time: Start of the query time window.
        end_time: End of the query time window.
        interval: The aggregation interval used ('hour' or 'day').
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "zone_id": 1,
                "zone_name": "Driveway Entrance",
                "trends": [
                    {
                        "timestamp": "2026-01-26T12:00:00Z",
                        "in_count": 15,
                        "out_count": 12,
                        "net_flow": 3,
                    },
                    {
                        "timestamp": "2026-01-26T13:00:00Z",
                        "in_count": 8,
                        "out_count": 10,
                        "net_flow": -2,
                    },
                ],
                "total_in": 23,
                "total_out": 22,
                "start_time": "2026-01-26T12:00:00Z",
                "end_time": "2026-01-26T14:00:00Z",
                "interval": "hour",
            }
        },
    )

    zone_id: int = Field(..., description="ID of the line zone")
    zone_name: str = Field(..., description="Name of the line zone")
    trends: list[CrossingTrendDataPoint] = Field(
        ..., description="Time-bucketed crossing data points"
    )
    total_in: int = Field(ge=0, description="Total crossings in positive direction")
    total_out: int = Field(ge=0, description="Total crossings in negative direction")
    start_time: datetime = Field(..., description="Start of the query time window")
    end_time: datetime = Field(..., description="End of the query time window")
    interval: str = Field(description="Aggregation interval: 'hour' or 'day'")


# Export all schemas
__all__ = [
    "CrossingTrendDataPoint",
    "CrossingTrendsResponse",
]
