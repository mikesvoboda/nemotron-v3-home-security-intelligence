"""Pydantic schemas for track API endpoints.

Object tracking schemas for multi-object tracking (MOT) functionality,
supporting trajectory visualization and movement analytics.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TrajectoryPoint(BaseModel):
    """Single point in a track trajectory.

    Represents a discrete position observation of a tracked object
    at a specific point in time.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "x": 640.5,
                "y": 480.2,
                "timestamp": "2026-01-26T12:00:00Z",
            }
        }
    )

    x: float = Field(..., description="X coordinate (pixels)")
    y: float = Field(..., description="Y coordinate (pixels)")
    timestamp: datetime = Field(..., description="Time of this position")


class MovementMetrics(BaseModel):
    """Calculated movement metrics for a track.

    Aggregated statistics computed from the track's trajectory points,
    useful for behavioral analysis and anomaly detection.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_distance": 1250.5,
                "avg_speed": 45.2,
                "direction": 135.0,
                "duration_seconds": 27.7,
            }
        }
    )

    total_distance: float = Field(..., ge=0, description="Total distance traveled (pixels)")
    avg_speed: float = Field(..., ge=0, description="Average speed (pixels/second)")
    direction: float | None = Field(
        None,
        ge=0,
        le=360,
        description="Overall direction in degrees (0-360, where 0=right, 90=down)",
    )
    duration_seconds: float = Field(..., ge=0, description="Track duration in seconds")


class TrackResponse(BaseModel):
    """Response for a single track.

    Basic track information without full trajectory data.
    Use TrackHistoryResponse for full trajectory details.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "track_id": 42,
                "camera_id": "front_door",
                "object_class": "person",
                "first_seen": "2026-01-26T12:00:00Z",
                "last_seen": "2026-01-26T12:00:27Z",
                "metrics": {
                    "total_distance": 1250.5,
                    "avg_speed": 45.2,
                    "direction": 135.0,
                    "duration_seconds": 27.7,
                },
            }
        },
    )

    id: int = Field(..., description="Database track ID")
    track_id: int = Field(..., description="Tracker-assigned ID (unique per camera session)")
    camera_id: str = Field(..., description="Camera ID where track was observed")
    object_class: str = Field(..., description="Detected object class (person, car, etc.)")
    first_seen: datetime = Field(..., description="Timestamp of first observation")
    last_seen: datetime = Field(..., description="Timestamp of last observation")
    metrics: MovementMetrics | None = Field(
        None, description="Computed movement metrics (may be null for short tracks)"
    )


class TrackHistoryResponse(BaseModel):
    """Response with full track history including trajectory.

    Includes complete trajectory data for visualization and analysis.
    Use for track detail views and trajectory plotting.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "track_id": 42,
                "camera_id": "front_door",
                "object_class": "person",
                "first_seen": "2026-01-26T12:00:00Z",
                "last_seen": "2026-01-26T12:00:27Z",
                "trajectory": [
                    {"x": 100.0, "y": 200.0, "timestamp": "2026-01-26T12:00:00Z"},
                    {"x": 150.5, "y": 220.3, "timestamp": "2026-01-26T12:00:05Z"},
                    {"x": 210.2, "y": 245.8, "timestamp": "2026-01-26T12:00:10Z"},
                    {"x": 280.0, "y": 270.0, "timestamp": "2026-01-26T12:00:15Z"},
                    {"x": 350.5, "y": 300.2, "timestamp": "2026-01-26T12:00:20Z"},
                    {"x": 420.0, "y": 330.5, "timestamp": "2026-01-26T12:00:27Z"},
                ],
                "metrics": {
                    "total_distance": 1250.5,
                    "avg_speed": 45.2,
                    "direction": 135.0,
                    "duration_seconds": 27.7,
                },
            }
        },
    )

    id: int = Field(..., description="Database track ID")
    track_id: int = Field(..., description="Tracker-assigned ID (unique per camera session)")
    camera_id: str = Field(..., description="Camera ID where track was observed")
    object_class: str = Field(..., description="Detected object class (person, car, etc.)")
    first_seen: datetime = Field(..., description="Timestamp of first observation")
    last_seen: datetime = Field(..., description="Timestamp of last observation")
    trajectory: list[TrajectoryPoint] = Field(..., description="Ordered list of trajectory points")
    metrics: MovementMetrics = Field(..., description="Computed movement metrics")


class TrackListResponse(BaseModel):
    """Paginated list of tracks.

    Standard pagination envelope for track list endpoints.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tracks": [
                    {
                        "id": 1,
                        "track_id": 42,
                        "camera_id": "front_door",
                        "object_class": "person",
                        "first_seen": "2026-01-26T12:00:00Z",
                        "last_seen": "2026-01-26T12:00:27Z",
                        "metrics": {
                            "total_distance": 1250.5,
                            "avg_speed": 45.2,
                            "direction": 135.0,
                            "duration_seconds": 27.7,
                        },
                    },
                    {
                        "id": 2,
                        "track_id": 43,
                        "camera_id": "front_door",
                        "object_class": "car",
                        "first_seen": "2026-01-26T12:01:00Z",
                        "last_seen": "2026-01-26T12:01:15Z",
                        "metrics": {
                            "total_distance": 2100.0,
                            "avg_speed": 140.0,
                            "direction": 270.0,
                            "duration_seconds": 15.0,
                        },
                    },
                ],
                "total": 2,
                "page": 1,
                "page_size": 50,
            }
        }
    )

    tracks: list[TrackResponse] = Field(..., description="List of tracks")
    total: int = Field(..., ge=0, description="Total number of tracks matching the query")
    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(..., ge=1, le=1000, description="Number of items per page")
