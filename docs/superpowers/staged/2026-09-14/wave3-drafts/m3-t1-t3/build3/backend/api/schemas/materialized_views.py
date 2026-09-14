"""Pydantic schemas for Materialized Views Admin API (NEM-4933).

These schemas define the request and response models for administering
materialized views, including listing views, checking status, and
triggering refreshes.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MaterializedViewInfo(BaseModel):
    """Schema for materialized view information."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "view_name": "mv_daily_detection_counts",
                "exists": True,
                "row_count": 1500,
                "size_bytes": 102400,
                "size_human": "100 KB",
            }
        }
    )

    view_name: str = Field(..., description="Name of the materialized view")
    exists: bool = Field(..., description="Whether the view exists in the database")
    row_count: int = Field(default=0, ge=0, description="Number of rows in the view")
    size_bytes: int = Field(default=0, ge=0, description="Size of the view in bytes")
    size_human: str | None = Field(default=None, description="Human-readable size (e.g., '100 KB')")
    error: str | None = Field(default=None, description="Error message if stats collection failed")


class MaterializedViewListResponse(BaseModel):
    """Response schema for listing all materialized views."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "views": [
                    {
                        "view_name": "mv_daily_detection_counts",
                        "exists": True,
                        "row_count": 1500,
                        "size_bytes": 102400,
                        "size_human": "100 KB",
                    },
                    {
                        "view_name": "mv_hourly_event_stats",
                        "exists": True,
                        "row_count": 5000,
                        "size_bytes": 256000,
                        "size_human": "250 KB",
                    },
                ],
                "total_views": 6,
                "total_size_bytes": 512000,
                "total_size_human": "500 KB",
            }
        }
    )

    views: list[MaterializedViewInfo] = Field(
        default_factory=list, description="List of materialized views with their stats"
    )
    total_views: int = Field(..., ge=0, description="Total number of managed views")
    total_size_bytes: int = Field(default=0, ge=0, description="Total size of all views in bytes")
    total_size_human: str | None = Field(default=None, description="Human-readable total size")


class MaterializedViewRefreshRequest(BaseModel):
    """Request schema for refreshing materialized views."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "view_name": "mv_daily_detection_counts",
                "concurrently": True,
            }
        }
    )

    view_name: str | None = Field(
        default=None,
        description="Name of a specific view to refresh. If not provided, all views are refreshed.",
    )
    concurrently: bool = Field(
        default=True,
        description="If True, use CONCURRENTLY option which allows reads during refresh. "
        "Requires unique index on the view. If False, blocks reads during refresh.",
    )


class MaterializedViewRefreshResult(BaseModel):
    """Result of a single view refresh operation."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "view_name": "mv_daily_detection_counts",
                "success": True,
                "duration_ms": 150,
                "error": None,
            }
        }
    )

    view_name: str = Field(..., description="Name of the materialized view")
    success: bool = Field(..., description="Whether the refresh succeeded")
    duration_ms: float | None = Field(
        default=None, ge=0, description="Duration of the refresh operation in milliseconds"
    )
    error: str | None = Field(default=None, description="Error message if refresh failed")


class MaterializedViewRefreshResponse(BaseModel):
    """Response schema for materialized view refresh operation."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "results": [
                    {
                        "view_name": "mv_daily_detection_counts",
                        "success": True,
                        "duration_ms": 150,
                        "error": None,
                    },
                    {
                        "view_name": "mv_hourly_event_stats",
                        "success": True,
                        "duration_ms": 200,
                        "error": None,
                    },
                ],
                "total_refreshed": 6,
                "success_count": 6,
                "failure_count": 0,
                "total_duration_ms": 850,
                "concurrently": True,
                "refreshed_at": "2025-12-23T14:30:00Z",
            }
        }
    )

    results: list[MaterializedViewRefreshResult] = Field(
        default_factory=list, description="Results for each view refresh"
    )
    total_refreshed: int = Field(..., ge=0, description="Total number of views that were refreshed")
    success_count: int = Field(..., ge=0, description="Number of views that refreshed successfully")
    failure_count: int = Field(..., ge=0, description="Number of views that failed to refresh")
    total_duration_ms: float = Field(
        default=0, ge=0, description="Total duration of all refresh operations"
    )
    concurrently: bool = Field(..., description="Whether CONCURRENTLY option was used")
    refreshed_at: datetime = Field(
        ..., description="Timestamp when the refresh operation completed"
    )


class MaterializedViewStatusResponse(BaseModel):
    """Response schema for materialized view status check."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "view_name": "mv_daily_detection_counts",
                "exists": True,
                "row_count": 1500,
                "size_bytes": 102400,
                "size_human": "100 KB",
                "is_populated": True,
                "last_refresh": "2025-12-23T14:00:00Z",
            }
        }
    )

    view_name: str = Field(..., description="Name of the materialized view")
    exists: bool = Field(..., description="Whether the view exists")
    row_count: int = Field(default=0, ge=0, description="Number of rows in the view")
    size_bytes: int = Field(default=0, ge=0, description="Size of the view in bytes")
    size_human: str | None = Field(default=None, description="Human-readable size")
    is_populated: bool = Field(
        default=False,
        description="Whether the view has been populated (row_count > 0)",
    )
    last_refresh: datetime | None = Field(
        default=None,
        description="When the view was last refreshed (if tracked)",
    )
    error: str | None = Field(default=None, description="Error message if status check failed")
