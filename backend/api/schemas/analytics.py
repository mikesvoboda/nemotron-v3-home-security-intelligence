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
