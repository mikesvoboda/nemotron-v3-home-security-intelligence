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


class ActivityBaselineEntry(BaseModel):
    """A single activity baseline entry for a specific hour and day combination.

    This represents one cell in the 24x7 activity heatmap (168 total entries).
    """

    hour: int = Field(
        ...,
        description="Hour of day (0-23)",
        ge=0,
        le=23,
    )
    day_of_week: int = Field(
        ...,
        description="Day of week (0=Monday, 6=Sunday)",
        ge=0,
        le=6,
    )
    avg_count: float = Field(
        ...,
        description="Average activity count for this time slot",
        ge=0,
    )
    sample_count: int = Field(
        ...,
        description="Number of samples used to calculate this average",
        ge=0,
    )
    is_peak: bool = Field(
        default=False,
        description="Whether this time slot has above-average activity",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hour": 17,
                "day_of_week": 0,
                "avg_count": 5.2,
                "sample_count": 30,
                "is_peak": True,
            }
        }
    )


class ActivityBaselineResponse(BaseModel):
    """Response for camera activity baseline endpoint.

    Contains 168 entries (24 hours x 7 days) representing the full weekly
    activity heatmap for a camera.
    """

    camera_id: str = Field(
        ...,
        description="Camera ID",
    )
    entries: list[ActivityBaselineEntry] = Field(
        default_factory=list,
        description="Activity baseline entries (up to 168 = 24h x 7 days)",
    )
    total_samples: int = Field(
        ...,
        description="Total number of samples across all entries",
        ge=0,
    )
    peak_hour: int | None = Field(
        None,
        description="Hour with highest average activity (0-23)",
        ge=0,
        le=23,
    )
    peak_day: int | None = Field(
        None,
        description="Day with highest average activity (0=Monday, 6=Sunday)",
        ge=0,
        le=6,
    )
    learning_complete: bool = Field(
        default=False,
        description="Whether baseline has sufficient samples for reliable anomaly detection",
    )
    min_samples_required: int = Field(
        default=10,
        description="Minimum samples required per time slot for learning completion",
        ge=1,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "front_door",
                "entries": [
                    {
                        "hour": 0,
                        "day_of_week": 0,
                        "avg_count": 0.5,
                        "sample_count": 30,
                        "is_peak": False,
                    },
                    {
                        "hour": 17,
                        "day_of_week": 4,
                        "avg_count": 5.2,
                        "sample_count": 30,
                        "is_peak": True,
                    },
                ],
                "total_samples": 720,
                "peak_hour": 17,
                "peak_day": 4,
                "learning_complete": True,
                "min_samples_required": 10,
            }
        }
    )


class ClassBaselineEntry(BaseModel):
    """Baseline entry for a specific object class at a specific hour."""

    object_class: str = Field(
        ...,
        description="Object class (e.g., person, vehicle, animal)",
    )
    hour: int = Field(
        ...,
        description="Hour of day (0-23)",
        ge=0,
        le=23,
    )
    frequency: float = Field(
        ...,
        description="Frequency of this class at this hour",
        ge=0,
    )
    sample_count: int = Field(
        ...,
        description="Number of samples for this class/hour combination",
        ge=0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "object_class": "person",
                "hour": 17,
                "frequency": 3.5,
                "sample_count": 45,
            }
        }
    )


class ClassBaselineResponse(BaseModel):
    """Response for camera class frequency baseline endpoint."""

    camera_id: str = Field(
        ...,
        description="Camera ID",
    )
    entries: list[ClassBaselineEntry] = Field(
        default_factory=list,
        description="Class baseline entries grouped by class and hour",
    )
    unique_classes: list[str] = Field(
        default_factory=list,
        description="List of unique object classes detected for this camera",
    )
    total_samples: int = Field(
        ...,
        description="Total number of samples across all entries",
        ge=0,
    )
    most_common_class: str | None = Field(
        None,
        description="Most frequently detected object class",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "front_door",
                "entries": [
                    {"object_class": "person", "hour": 17, "frequency": 3.5, "sample_count": 45},
                    {"object_class": "vehicle", "hour": 8, "frequency": 2.1, "sample_count": 30},
                ],
                "unique_classes": ["person", "vehicle", "animal"],
                "total_samples": 150,
                "most_common_class": "person",
            }
        }
    )


class AnomalyConfig(BaseModel):
    """Current anomaly detection configuration."""

    threshold_stdev: float = Field(
        ...,
        description="Number of standard deviations from mean for anomaly detection",
        gt=0,
    )
    min_samples: int = Field(
        ...,
        description="Minimum samples required before anomaly detection is reliable",
        ge=1,
    )
    decay_factor: float = Field(
        ...,
        description="Exponential decay factor for EWMA (0 < factor <= 1)",
        gt=0,
        le=1,
    )
    window_days: int = Field(
        ...,
        description="Rolling window size in days for baseline calculations",
        ge=1,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "threshold_stdev": 2.0,
                "min_samples": 10,
                "decay_factor": 0.1,
                "window_days": 30,
            }
        }
    )


class AnomalyConfigUpdate(BaseModel):
    """Request to update anomaly detection configuration."""

    threshold_stdev: float | None = Field(
        None,
        description="Number of standard deviations from mean for anomaly detection",
        gt=0,
    )
    min_samples: int | None = Field(
        None,
        description="Minimum samples required before anomaly detection is reliable",
        ge=1,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "threshold_stdev": 2.5,
                "min_samples": 15,
            }
        }
    )
