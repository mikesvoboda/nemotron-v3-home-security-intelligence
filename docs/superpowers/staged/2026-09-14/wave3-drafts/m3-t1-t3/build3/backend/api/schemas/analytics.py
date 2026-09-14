"""Pydantic schemas for analytics API endpoints."""

from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field


class DetectionTrendDataPoint(BaseModel):
    """Schema for a single detection trend data point."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2025-01-07",
                "count": 25,
            }
        }
    )

    date: Date = Field(..., description="Date of the data point")
    count: int = Field(..., description="Number of detections on this date", ge=0)


class DetectionTrendsResponse(BaseModel):
    """Schema for detection trends aggregated by day."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data_points": [
                    {"date": "2025-01-01", "count": 20},
                    {"date": "2025-01-02", "count": 25},
                    {"date": "2025-01-03", "count": 18},
                ],
                "total_detections": 63,
                "start_date": "2025-01-01",
                "end_date": "2025-01-03",
            }
        }
    )

    data_points: list[DetectionTrendDataPoint] = Field(
        ..., description="Detection counts aggregated by day"
    )
    total_detections: int = Field(..., description="Total detections in date range", ge=0)
    start_date: Date = Field(..., description="Start date of the date range")
    end_date: Date = Field(..., description="End date of the date range")


class RiskHistoryDataPoint(BaseModel):
    """Schema for a single risk history data point."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2025-01-07",
                "low": 10,
                "medium": 5,
                "high": 2,
                "critical": 1,
            }
        }
    )

    date: Date = Field(..., description="Date of the data point")
    low: int = Field(0, description="Count of low risk events", ge=0)
    medium: int = Field(0, description="Count of medium risk events", ge=0)
    high: int = Field(0, description="Count of high risk events", ge=0)
    critical: int = Field(0, description="Count of critical risk events", ge=0)


class RiskHistoryResponse(BaseModel):
    """Schema for risk score distribution over time."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data_points": [
                    {"date": "2025-01-01", "low": 10, "medium": 5, "high": 2, "critical": 1},
                    {"date": "2025-01-02", "low": 12, "medium": 4, "high": 3, "critical": 0},
                ],
                "start_date": "2025-01-01",
                "end_date": "2025-01-02",
            }
        }
    )

    data_points: list[RiskHistoryDataPoint] = Field(
        ..., description="Risk level counts aggregated by day"
    )
    start_date: Date = Field(..., description="Start date of the date range")
    end_date: Date = Field(..., description="End date of the date range")


class CameraUptimeDataPoint(BaseModel):
    """Schema for a single camera uptime data point."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "front_door",
                "camera_name": "Front Door",
                "uptime_percentage": 98.5,
                "detection_count": 150,
            }
        }
    )

    camera_id: str = Field(..., description="Normalized camera ID (e.g., 'front_door')")
    camera_name: str = Field(..., description="Camera name")
    uptime_percentage: float = Field(..., description="Uptime percentage (0-100)", ge=0.0, le=100.0)
    detection_count: int = Field(..., description="Total detections in date range", ge=0)


class CameraUptimeResponse(BaseModel):
    """Schema for camera uptime percentage per camera."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cameras": [
                    {
                        "camera_id": "front_door",
                        "camera_name": "Front Door",
                        "uptime_percentage": 98.5,
                        "detection_count": 150,
                    },
                    {
                        "camera_id": "back_door",
                        "camera_name": "Back Door",
                        "uptime_percentage": 95.2,
                        "detection_count": 120,
                    },
                ],
                "start_date": "2025-01-01",
                "end_date": "2025-01-07",
            }
        }
    )

    cameras: list[CameraUptimeDataPoint] = Field(..., description="Uptime data per camera")
    start_date: Date = Field(..., description="Start date of the date range")
    end_date: Date = Field(..., description="End date of the date range")


class ObjectDistributionDataPoint(BaseModel):
    """Schema for a single object distribution data point."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "object_type": "person",
                "count": 120,
                "percentage": 45.5,
            }
        }
    )

    object_type: str = Field(..., description="Detected object type (e.g., 'person', 'car')")
    count: int = Field(..., description="Number of detections for this object type", ge=0)
    percentage: float = Field(
        ..., description="Percentage of total detections (0-100)", ge=0.0, le=100.0
    )


class ObjectDistributionResponse(BaseModel):
    """Schema for detection counts by object type."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "object_types": [
                    {"object_type": "person", "count": 120, "percentage": 45.5},
                    {"object_type": "car", "count": 80, "percentage": 30.3},
                    {"object_type": "dog", "count": 64, "percentage": 24.2},
                ],
                "total_detections": 264,
                "start_date": "2025-01-01",
                "end_date": "2025-01-07",
            }
        }
    )

    object_types: list[ObjectDistributionDataPoint] = Field(
        ..., description="Detection counts by object type"
    )
    total_detections: int = Field(..., description="Total detections in date range", ge=0)
    start_date: Date = Field(..., description="Start date of the date range")
    end_date: Date = Field(..., description="End date of the date range")


# ============================================================================
# Risk Score Distribution Types (NEM-3602)
# ============================================================================


class RiskScoreDistributionBucket(BaseModel):
    """Schema for a single risk score distribution bucket."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "min_score": 0,
                "max_score": 10,
                "count": 15,
            }
        }
    )

    min_score: int = Field(..., description="Minimum score in this bucket (inclusive)", ge=0)
    max_score: int = Field(..., description="Maximum score in this bucket (exclusive)", ge=0)
    count: int = Field(..., description="Number of events in this bucket", ge=0)


class RiskScoreDistributionResponse(BaseModel):
    """Schema for risk score distribution histogram."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "buckets": [
                    {"min_score": 0, "max_score": 10, "count": 15},
                    {"min_score": 10, "max_score": 20, "count": 12},
                    {"min_score": 20, "max_score": 30, "count": 8},
                    {"min_score": 30, "max_score": 40, "count": 6},
                    {"min_score": 40, "max_score": 50, "count": 4},
                    {"min_score": 50, "max_score": 60, "count": 3},
                    {"min_score": 60, "max_score": 70, "count": 2},
                    {"min_score": 70, "max_score": 80, "count": 2},
                    {"min_score": 80, "max_score": 90, "count": 1},
                    {"min_score": 90, "max_score": 100, "count": 1},
                ],
                "total_events": 54,
                "start_date": "2025-01-01",
                "end_date": "2025-01-07",
                "bucket_size": 10,
            }
        }
    )

    buckets: list[RiskScoreDistributionBucket] = Field(
        ..., description="Risk score distribution buckets"
    )
    total_events: int = Field(..., description="Total events with risk scores in date range", ge=0)
    start_date: Date = Field(..., description="Start date of the date range")
    end_date: Date = Field(..., description="End date of the date range")
    bucket_size: int = Field(..., description="Size of each bucket", ge=1)


# ============================================================================
# Risk Score Trends Types (NEM-3602)
# ============================================================================


class RiskScoreTrendDataPoint(BaseModel):
    """Schema for a single risk score trend data point."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2025-01-07",
                "avg_score": 45.5,
                "count": 12,
            }
        }
    )

    date: Date = Field(..., description="Date of the data point")
    avg_score: float = Field(..., description="Average risk score on this date", ge=0.0, le=100.0)
    count: int = Field(..., description="Number of events on this date", ge=0)


class RiskScoreTrendsResponse(BaseModel):
    """Schema for risk score trends over time."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data_points": [
                    {"date": "2025-01-01", "avg_score": 35.2, "count": 10},
                    {"date": "2025-01-02", "avg_score": 42.1, "count": 15},
                    {"date": "2025-01-03", "avg_score": 38.7, "count": 12},
                ],
                "start_date": "2025-01-01",
                "end_date": "2025-01-03",
            }
        }
    )

    data_points: list[RiskScoreTrendDataPoint] = Field(
        ..., description="Average risk score aggregated by day"
    )
    start_date: Date = Field(..., description="Start date of the date range")
    end_date: Date = Field(..., description="End date of the date range")


# ============================================================================
# Camera Activity Heatmap Types (NEM-5388/5389/5390/5391)
# ============================================================================


class CameraActivityDataPoint(BaseModel):
    """Schema for camera activity data point.

    Represents aggregated event data for a single camera including
    the highest-risk detection thumbnail for visual representation.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "front_door",
                "camera_name": "Front Door",
                "event_count": 45,
                "max_risk_score": 87,
                "risk_level": "high",
                "thumbnail_path": "/data/thumbnails/2026/01/front_door_high.jpg",
            }
        }
    )

    camera_id: str = Field(..., description="Normalized camera ID")
    camera_name: str = Field(..., description="Human-readable camera name")
    event_count: int = Field(..., description="Total events in date range", ge=0)
    max_risk_score: int | None = Field(None, description="Highest risk score in date range (0-100)")
    risk_level: str | None = Field(
        None,
        description="Risk level derived from max_risk_score (low, medium, high, critical)",
    )
    thumbnail_path: str | None = Field(None, description="Path to highest-risk detection thumbnail")


class CameraActivityResponse(BaseModel):
    """Schema for camera activity heatmap response.

    Returns aggregated event data per camera for building an activity
    heatmap visualization with color intensity based on activity level.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cameras": [
                    {
                        "camera_id": "front_door",
                        "camera_name": "Front Door",
                        "event_count": 45,
                        "max_risk_score": 87,
                        "risk_level": "high",
                        "thumbnail_path": "/data/thumbnails/2026/01/front_door.jpg",
                    },
                    {
                        "camera_id": "back_door",
                        "camera_name": "Back Door",
                        "event_count": 12,
                        "max_risk_score": 45,
                        "risk_level": "medium",
                        "thumbnail_path": "/data/thumbnails/2026/01/back_door.jpg",
                    },
                ],
                "start_date": "2026-01-01",
                "end_date": "2026-01-07",
            }
        }
    )

    cameras: list[CameraActivityDataPoint] = Field(
        ..., description="Activity data per camera, sorted by event_count descending"
    )
    start_date: Date = Field(..., description="Start date of the date range")
    end_date: Date = Field(..., description="End date of the date range")


# ============================================================================
# Calibration Drift Monitoring Types (NEM-5535)
# ============================================================================


class CalibrationTierStatus(BaseModel):
    """Status of a single risk tier in the calibration distribution."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tier": "low",
                "actual_pct": 82.5,
                "target_pct": 85.0,
                "deviation_pct": 2.5,
                "is_drifting": False,
            }
        }
    )

    tier: str = Field(..., description="Tier name (low, elevated, moderate, high, critical)")
    actual_pct: float = Field(..., description="Actual percentage of scores in this tier", ge=0.0)
    target_pct: float = Field(..., description="Target percentage for this tier", ge=0.0)
    deviation_pct: float = Field(
        ..., description="Absolute deviation from target (percentage points)", ge=0.0
    )
    is_drifting: bool = Field(..., description="True if deviation exceeds the drift threshold")


class CalibrationResponse(BaseModel):
    """Response schema for the calibration drift monitoring endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_scores": 1200,
                "window_seconds": 86400,
                "drift_threshold_pct": 5.0,
                "is_drifting": False,
                "drifting_tiers": [],
                "tiers": [
                    {
                        "tier": "low",
                        "actual_pct": 83.5,
                        "target_pct": 85.0,
                        "deviation_pct": 1.5,
                        "is_drifting": False,
                    },
                    {
                        "tier": "medium",
                        "actual_pct": 11.2,
                        "target_pct": 10.0,
                        "deviation_pct": 1.2,
                        "is_drifting": False,
                    },
                    {
                        "tier": "high",
                        "actual_pct": 4.3,
                        "target_pct": 4.0,
                        "deviation_pct": 0.3,
                        "is_drifting": False,
                    },
                    {
                        "tier": "critical",
                        "actual_pct": 1.0,
                        "target_pct": 1.0,
                        "deviation_pct": 0.0,
                        "is_drifting": False,
                    },
                ],
            }
        }
    )

    total_scores: int = Field(
        ..., description="Total number of scores in the monitoring window", ge=0
    )
    window_seconds: int = Field(..., description="Size of the rolling window in seconds", ge=0)
    drift_threshold_pct: float = Field(
        ..., description="Maximum acceptable deviation in percentage points", ge=0.0
    )
    is_drifting: bool = Field(..., description="True if any tier exceeds the drift threshold")
    drifting_tiers: list[str] = Field(
        ..., description="List of tier names that are currently drifting"
    )
    tiers: list[CalibrationTierStatus] = Field(..., description="Detailed status for each tier")
