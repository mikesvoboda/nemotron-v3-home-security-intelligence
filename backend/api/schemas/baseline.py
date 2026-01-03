"""Pydantic schemas for baseline activity API endpoints.

These schemas support the camera baseline endpoints that expose
activity pattern data for anomaly detection.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DeviationInterpretation(str, Enum):
    """Interpretation of current deviation from baseline."""

    FAR_BELOW_NORMAL = "far_below_normal"
    BELOW_NORMAL = "below_normal"
    NORMAL = "normal"
    SLIGHTLY_ABOVE_NORMAL = "slightly_above_normal"
    ABOVE_NORMAL = "above_normal"
    FAR_ABOVE_NORMAL = "far_above_normal"


class HourlyPattern(BaseModel):
    """Activity pattern for a specific hour."""

    avg_detections: float = Field(
        ...,
        description="Average number of detections during this hour",
        ge=0,
    )
    std_dev: float = Field(
        ...,
        description="Standard deviation of detection count",
        ge=0,
    )
    sample_count: int = Field(
        ...,
        description="Number of samples used for this calculation",
        ge=0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "avg_detections": 2.5,
                "std_dev": 0.8,
                "sample_count": 30,
            }
        }
    )


class DailyPattern(BaseModel):
    """Activity pattern for a specific day of the week."""

    avg_detections: float = Field(
        ...,
        description="Average number of detections for this day",
        ge=0,
    )
    peak_hour: int = Field(
        ...,
        description="Hour with most activity (0-23)",
        ge=0,
        le=23,
    )
    total_samples: int = Field(
        ...,
        description="Total samples for this day",
        ge=0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "avg_detections": 45.0,
                "peak_hour": 17,
                "total_samples": 168,
            }
        }
    )


class ObjectBaseline(BaseModel):
    """Baseline statistics for a specific object class."""

    avg_hourly: float = Field(
        ...,
        description="Average hourly detection count for this object type",
        ge=0,
    )
    peak_hour: int = Field(
        ...,
        description="Hour with most detections of this type (0-23)",
        ge=0,
        le=23,
    )
    total_detections: int = Field(
        ...,
        description="Total detections of this type in the baseline period",
        ge=0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "avg_hourly": 2.3,
                "peak_hour": 17,
                "total_detections": 550,
            }
        }
    )


class CurrentDeviation(BaseModel):
    """Current activity deviation from established baseline."""

    score: float = Field(
        ...,
        description="Deviation score (standard deviations from mean, can be negative)",
    )
    interpretation: DeviationInterpretation = Field(
        ...,
        description="Human-readable interpretation of the deviation",
    )
    contributing_factors: list[str] = Field(
        default_factory=list,
        description="Factors contributing to current deviation",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "score": 1.8,
                "interpretation": "slightly_above_normal",
                "contributing_factors": ["person_count_elevated", "unusual_hour"],
            }
        }
    )


class BaselineSummaryResponse(BaseModel):
    """Response schema for camera baseline summary endpoint.

    Provides comprehensive baseline data for a camera including:
    - Hourly activity patterns (0-23 hours)
    - Daily patterns (by day of week)
    - Object-specific baselines
    - Current deviation from baseline
    """

    camera_id: str = Field(
        ...,
        description="Camera ID",
    )
    camera_name: str = Field(
        ...,
        description="Human-readable camera name",
    )
    baseline_established: datetime | None = Field(
        None,
        description="When baseline data collection started (null if no data)",
    )
    data_points: int = Field(
        ...,
        description="Total number of data points in baseline",
        ge=0,
    )
    hourly_patterns: dict[str, HourlyPattern] = Field(
        default_factory=dict,
        description="Activity patterns by hour (0-23)",
    )
    daily_patterns: dict[str, DailyPattern] = Field(
        default_factory=dict,
        description="Activity patterns by day of week (monday-sunday)",
    )
    object_baselines: dict[str, ObjectBaseline] = Field(
        default_factory=dict,
        description="Baseline statistics by object type",
    )
    current_deviation: CurrentDeviation | None = Field(
        None,
        description="Current deviation from baseline (null if insufficient data)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "front_door",
                "camera_name": "Front Door",
                "baseline_established": "2026-01-01T00:00:00Z",
                "data_points": 720,
                "hourly_patterns": {
                    "0": {"avg_detections": 0.5, "std_dev": 0.3, "sample_count": 30},
                    "17": {"avg_detections": 5.2, "std_dev": 1.1, "sample_count": 30},
                },
                "daily_patterns": {
                    "monday": {"avg_detections": 45, "peak_hour": 17, "total_samples": 24},
                },
                "object_baselines": {
                    "person": {"avg_hourly": 2.3, "peak_hour": 17, "total_detections": 550},
                },
                "current_deviation": {
                    "score": 1.8,
                    "interpretation": "slightly_above_normal",
                    "contributing_factors": ["person_count_elevated"],
                },
            }
        }
    )


class AnomalyEvent(BaseModel):
    """A single anomaly event detected for a camera."""

    timestamp: datetime = Field(
        ...,
        description="When the anomaly was detected",
    )
    detection_class: str = Field(
        ...,
        description="Object class that triggered the anomaly",
    )
    anomaly_score: float = Field(
        ...,
        description="Anomaly score (0.0-1.0, higher is more anomalous)",
        ge=0.0,
        le=1.0,
    )
    expected_frequency: float = Field(
        ...,
        description="Expected frequency for this class at this time",
        ge=0.0,
    )
    observed_frequency: float = Field(
        ...,
        description="Observed frequency that triggered the anomaly",
        ge=0.0,
    )
    reason: str = Field(
        ...,
        description="Human-readable explanation of why this is anomalous",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2026-01-03T02:30:00Z",
                "detection_class": "vehicle",
                "anomaly_score": 0.95,
                "expected_frequency": 0.1,
                "observed_frequency": 5.0,
                "reason": "Vehicle detected at 2:30 AM when rarely seen at this hour",
            }
        }
    )


class AnomalyListResponse(BaseModel):
    """Response schema for camera anomaly list endpoint."""

    camera_id: str = Field(
        ...,
        description="Camera ID",
    )
    anomalies: list[AnomalyEvent] = Field(
        default_factory=list,
        description="List of recent anomaly events",
    )
    count: int = Field(
        ...,
        description="Total number of anomalies returned",
        ge=0,
    )
    period_days: int = Field(
        ...,
        description="Number of days covered by this query",
        ge=1,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "front_door",
                "anomalies": [
                    {
                        "timestamp": "2026-01-03T02:30:00Z",
                        "detection_class": "vehicle",
                        "anomaly_score": 0.95,
                        "expected_frequency": 0.1,
                        "observed_frequency": 5.0,
                        "reason": "Vehicle detected at 2:30 AM when rarely seen",
                    }
                ],
                "count": 1,
                "period_days": 7,
            }
        }
    )
