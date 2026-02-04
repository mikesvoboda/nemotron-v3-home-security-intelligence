"""Pydantic schemas for trends API endpoints.

These schemas define the response models for the trend comparison sparklines feature,
which provides time-bucketed event metrics with rolling 24-hour baseline comparisons.

The trends API supports:
- Hourly view: 12 x 5-minute buckets showing the last hour
- Daily view: 24 x 1-hour buckets showing the last 24 hours

Each metric includes:
- values: Array of data points for sparkline visualization
- baseline: Rolling 24-hour average for comparison
- deviation_pct: Percentage above/below baseline (positive = above, negative = below)
"""

from pydantic import BaseModel, ConfigDict, Field


class TrendMetric(BaseModel):
    """Schema for a single trend metric with baseline comparison.

    Contains time-bucketed values for sparkline display, plus a baseline
    (rolling 24-hour average) and deviation percentage for comparison.

    Example:
        {
            "values": [5, 8, 3, 6, 10, 4, 7, 9, 2, 5, 6, 8],
            "baseline": 6.0,
            "deviation_pct": 33.3
        }
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "values": [5, 8, 3, 6, 10, 4, 7, 9, 2, 5, 6, 8],
                "baseline": 6.0,
                "deviation_pct": 33.3,
            }
        }
    )

    values: list[float] = Field(
        ...,
        description="Array of metric values for each time bucket (for sparkline display)",
    )
    baseline: float = Field(
        ...,
        description="Rolling 24-hour average baseline for comparison",
        ge=0,
    )
    deviation_pct: float = Field(
        ...,
        description="Percentage deviation from baseline (positive = above, negative = below)",
    )


class TrendsResponse(BaseModel):
    """Schema for the trends API response.

    Contains three metrics for dashboard sparkline visualization:
    - event_count: Number of events per time bucket
    - avg_risk: Average risk score per time bucket
    - high_risk_count: Number of high-risk events (risk_score >= 70) per time bucket

    Each metric includes values array, baseline, and deviation percentage.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_count": {
                    "values": [5, 8, 3, 6, 10, 4, 7, 9, 2, 5, 6, 8],
                    "baseline": 6.0,
                    "deviation_pct": 33.3,
                },
                "avg_risk": {
                    "values": [45, 52, 38, 60, 72, 40, 55, 65, 35, 48, 50, 58],
                    "baseline": 50.0,
                    "deviation_pct": 16.0,
                },
                "high_risk_count": {
                    "values": [1, 2, 0, 1, 3, 1, 2, 2, 0, 1, 1, 2],
                    "baseline": 1.3,
                    "deviation_pct": 53.8,
                },
            }
        }
    )

    event_count: TrendMetric = Field(
        ...,
        description="Event count per time bucket with baseline comparison",
    )
    avg_risk: TrendMetric = Field(
        ...,
        description="Average risk score per time bucket with baseline comparison",
    )
    high_risk_count: TrendMetric = Field(
        ...,
        description="High-risk event count (>= 70) per time bucket with baseline comparison",
    )
