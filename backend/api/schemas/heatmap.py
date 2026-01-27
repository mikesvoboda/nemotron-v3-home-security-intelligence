"""Pydantic schemas for heatmap API endpoints.

This module provides request/response schemas for the heatmap visualization API,
including schemas for heatmap images, metadata, and query parameters.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class HeatmapResolution(StrEnum):
    """Resolution levels for heatmap data aggregation."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class HeatmapMetadata(BaseModel):
    """Metadata about a heatmap record.

    Attributes:
        id: Unique identifier of the heatmap record.
        camera_id: ID of the camera this heatmap belongs to.
        time_bucket: Start time of the aggregation period.
        resolution: Aggregation resolution (hourly, daily, weekly).
        width: Width of the heatmap grid in pixels.
        height: Height of the heatmap grid in pixels.
        total_detections: Total number of detections in this time bucket.
        created_at: When this record was created.
        updated_at: When this record was last updated.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "camera_id": "front_door",
                "time_bucket": "2026-01-26T10:00:00Z",
                "resolution": "hourly",
                "width": 64,
                "height": 48,
                "total_detections": 150,
                "created_at": "2026-01-26T11:00:00Z",
                "updated_at": "2026-01-26T11:00:00Z",
            }
        }
    )

    id: int = Field(..., description="Unique identifier of the heatmap record")
    camera_id: str = Field(..., description="ID of the camera this heatmap belongs to")
    time_bucket: datetime = Field(..., description="Start time of the aggregation period")
    resolution: HeatmapResolution = Field(
        ..., description="Aggregation resolution (hourly, daily, weekly)"
    )
    width: int = Field(..., description="Width of the heatmap grid in pixels", ge=1)
    height: int = Field(..., description="Height of the heatmap grid in pixels", ge=1)
    total_detections: int = Field(
        ..., description="Total number of detections in this time bucket", ge=0
    )
    created_at: datetime = Field(..., description="When this record was created")
    updated_at: datetime = Field(..., description="When this record was last updated")


class HeatmapResponse(BaseModel):
    """Response containing a heatmap image and metadata.

    The image is returned as a base64-encoded PNG string that can be
    directly used in HTML img tags or decoded for further processing.

    Attributes:
        camera_id: ID of the camera this heatmap belongs to.
        resolution: Aggregation resolution used.
        time_bucket: Start time of the aggregation period.
        image_base64: Base64-encoded PNG image of the heatmap.
        width: Width of the heatmap image in pixels.
        height: Height of the heatmap image in pixels.
        total_detections: Total detections used to generate this heatmap.
        colormap: Name of the colormap used (e.g., 'jet', 'hot', 'viridis').
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "front_door",
                "resolution": "hourly",
                "time_bucket": "2026-01-26T10:00:00Z",
                "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk...",
                "width": 640,
                "height": 480,
                "total_detections": 150,
                "colormap": "jet",
            }
        }
    )

    camera_id: str = Field(..., description="ID of the camera this heatmap belongs to")
    resolution: HeatmapResolution = Field(..., description="Aggregation resolution used")
    time_bucket: datetime = Field(..., description="Start time of the aggregation period")
    image_base64: str = Field(..., description="Base64-encoded PNG image of the heatmap")
    width: int = Field(..., description="Width of the heatmap image in pixels", ge=1)
    height: int = Field(..., description="Height of the heatmap image in pixels", ge=1)
    total_detections: int = Field(
        ..., description="Total detections used to generate this heatmap", ge=0
    )
    colormap: str = Field(
        default="jet", description="Name of the colormap used (e.g., 'jet', 'hot', 'viridis')"
    )


class HeatmapListResponse(BaseModel):
    """Response containing a list of heatmap metadata records.

    Used for querying historical heatmaps without the full image data.

    Attributes:
        heatmaps: List of heatmap metadata records.
        total: Total number of heatmaps matching the query.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "heatmaps": [
                    {
                        "id": 1,
                        "camera_id": "front_door",
                        "time_bucket": "2026-01-26T10:00:00Z",
                        "resolution": "hourly",
                        "width": 64,
                        "height": 48,
                        "total_detections": 150,
                        "created_at": "2026-01-26T11:00:00Z",
                        "updated_at": "2026-01-26T11:00:00Z",
                    }
                ],
                "total": 1,
            }
        }
    )

    heatmaps: list[HeatmapMetadata] = Field(..., description="List of heatmap metadata records")
    total: int = Field(..., description="Total number of heatmaps matching the query", ge=0)


class HeatmapSnapshotRequest(BaseModel):
    """Request to force save the current heatmap accumulator.

    Attributes:
        resolution: Resolution at which to save the snapshot.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "resolution": "hourly",
            }
        }
    )

    resolution: HeatmapResolution = Field(
        default=HeatmapResolution.HOURLY,
        description="Resolution at which to save the snapshot",
    )


class HeatmapSnapshotResponse(BaseModel):
    """Response after saving a heatmap snapshot.

    Attributes:
        success: Whether the snapshot was saved successfully.
        message: Status message.
        heatmap_id: ID of the created heatmap record, if successful.
        total_detections: Number of detections in the saved snapshot.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Heatmap snapshot saved successfully",
                "heatmap_id": 42,
                "total_detections": 150,
            }
        }
    )

    success: bool = Field(..., description="Whether the snapshot was saved successfully")
    message: str = Field(..., description="Status message")
    heatmap_id: int | None = Field(
        default=None, description="ID of the created heatmap record, if successful"
    )
    total_detections: int = Field(
        default=0, description="Number of detections in the saved snapshot", ge=0
    )


class HeatmapMergeRequest(BaseModel):
    """Request to merge multiple heatmaps into one.

    Attributes:
        heatmap_ids: List of heatmap record IDs to merge.
        output_resolution: Resolution for the merged output.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "heatmap_ids": [1, 2, 3, 4],
                "output_resolution": "daily",
            }
        }
    )

    heatmap_ids: list[int] = Field(
        ..., description="List of heatmap record IDs to merge", min_length=1
    )
    output_resolution: HeatmapResolution = Field(
        default=HeatmapResolution.DAILY,
        description="Resolution for the merged output",
    )


class HeatmapQueryParams(BaseModel):
    """Query parameters for fetching heatmap history.

    Attributes:
        start_time: Start of the time range (inclusive).
        end_time: End of the time range (inclusive).
        resolution: Filter by resolution level.
        limit: Maximum number of records to return.
        offset: Number of records to skip.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2026-01-31T23:59:59Z",
                "resolution": "hourly",
                "limit": 50,
                "offset": 0,
            }
        }
    )

    start_time: datetime | None = Field(
        default=None, description="Start of the time range (inclusive)"
    )
    end_time: datetime | None = Field(default=None, description="End of the time range (inclusive)")
    resolution: HeatmapResolution | None = Field(
        default=None, description="Filter by resolution level"
    )
    limit: int = Field(default=50, description="Maximum number of records to return", ge=1, le=1000)
    offset: int = Field(default=0, description="Number of records to skip", ge=0)
